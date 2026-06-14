#!/usr/bin/env python3
"""
Aggregate ALFWorld per-game JSON results into paper-style metrics.

Metrics (per run directory):
  - average reward / success rate  (mean of binary `reward`)
  - average steps
  - average token_usage.total_tokens
  - average agent_runtime_seconds

Usage:
  uv run python evaluation/aggregate_alfworld_results.py \\
    results/alfworld/gpt-4o-mini/dev_eval10_gos_skills500_mode_gos

  # Compare multiple runs; also print mean of per-run averages (for 2-run settings)
  uv run python evaluation/aggregate_alfworld_results.py --compare \\
    results/alfworld/gpt-4o/dev_full_gos_run1_mode_gos \\
    results/alfworld/gpt-4o/dev_full_gos_run2_mode_gos
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class RunMetrics:
    path: Path
    n_games: int
    success_rate: float
    avg_steps: float
    avg_total_tokens: float
    avg_agent_runtime_seconds: float
    missing_indices: list[int]

    @property
    def success_pct(self) -> float:
        return self.success_rate * 100.0


def _load_game_files(result_dir: Path) -> list[Path]:
    if not result_dir.is_dir():
        raise FileNotFoundError(f"Not a directory: {result_dir}")
    files = sorted(result_dir.glob("idx_*.json"))
    if not files:
        raise FileNotFoundError(f"No idx_*.json files under {result_dir}")
    return files


def _parse_index(path: Path) -> int | None:
    stem = path.stem  # idx_12
    if not stem.startswith("idx_"):
        return None
    try:
        return int(stem.split("_", 1)[1])
    except ValueError:
        return None


def _reward_to_float(value) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if value is None:
        return 0.0
    return float(value)


def aggregate_directory(result_dir: Path, *, expected_games: int | None) -> RunMetrics:
    files = _load_game_files(result_dir)
    rewards: list[float] = []
    steps: list[float] = []
    tokens: list[float] = []
    runtimes: list[float] = []
    indices: list[int] = []

    for path in files:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        idx = _parse_index(path)
        if idx is not None:
            indices.append(idx)

        rewards.append(_reward_to_float(data.get("reward")))
        steps.append(float(data.get("steps") or 0))

        usage = data.get("token_usage") or {}
        tokens.append(float(usage.get("total_tokens") or 0))
        runtimes.append(float(data.get("agent_runtime_seconds") or 0))

    n = len(rewards)
    missing_indices: list[int] = []
    if expected_games is not None and indices:
        index_set = set(indices)
        missing_indices = [i for i in range(expected_games) if i not in index_set]

    def mean(values: Iterable[float]) -> float:
        values = list(values)
        return sum(values) / len(values) if values else 0.0

    return RunMetrics(
        path=result_dir.resolve(),
        n_games=n,
        success_rate=mean(rewards),
        avg_steps=mean(steps),
        avg_total_tokens=mean(tokens),
        avg_agent_runtime_seconds=mean(runtimes),
        missing_indices=missing_indices,
    )


def _format_metrics(metrics: RunMetrics) -> str:
    label = metrics.path.name
    lines = [
        f"目录: {metrics.path}",
        f"  局数: {metrics.n_games}",
        f"  平均 reward / 成功率: {metrics.success_rate:.3f} ({metrics.success_pct:.1f}%)",
        f"  平均 steps: {metrics.avg_steps:.2f}",
        f"  平均 token_usage.total_tokens: {metrics.avg_total_tokens:.1f}",
        f"  平均 agent_runtime_seconds: {metrics.avg_agent_runtime_seconds:.2f}s",
    ]
    if metrics.missing_indices:
        preview = metrics.missing_indices[:10]
        suffix = "..." if len(metrics.missing_indices) > 10 else ""
        lines.append(
            f"  缺失 idx（相对 expected_games）: {preview}{suffix} "
            f"(共 {len(metrics.missing_indices)} 个)"
        )
    return "\n".join(lines)


def _mean_of_runs(runs: list[RunMetrics], attr: str) -> float:
    if not runs:
        return 0.0
    return sum(getattr(run, attr) for run in runs) / len(runs)


def _print_compare_table(runs: list[RunMetrics]) -> None:
    headers = ["run", "n", "success", "steps", "tokens", "runtime_s"]
    rows = []
    for run in runs:
        rows.append(
            [
                run.path.name,
                str(run.n_games),
                f"{run.success_rate:.3f}",
                f"{run.avg_steps:.2f}",
                f"{run.avg_total_tokens:.0f}",
                f"{run.avg_agent_runtime_seconds:.2f}",
            ]
        )

    if len(runs) > 1:
        rows.append(
            [
                "mean_of_runs",
                "-",
                f"{_mean_of_runs(runs, 'success_rate'):.3f}",
                f"{_mean_of_runs(runs, 'avg_steps'):.2f}",
                f"{_mean_of_runs(runs, 'avg_total_tokens'):.0f}",
                f"{_mean_of_runs(runs, 'avg_agent_runtime_seconds'):.2f}",
            ]
        )

    widths = [max(len(row[i]) for row in [headers] + rows) for i in range(len(headers))]
    print("\n对比表:")
    print("  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    for row in rows:
        print("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate ALFWorld idx_*.json metrics (reward, steps, tokens, runtime)."
    )
    parser.add_argument(
        "result_dirs",
        nargs="+",
        type=Path,
        help="One or more result directories containing idx_*.json",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Print a compact comparison table when multiple directories are given",
    )
    parser.add_argument(
        "--expected-games",
        type=int,
        default=140,
        help="Expected number of games for missing-index warnings (default: 140; use 10 for smoke runs)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON to stdout",
    )
    args = parser.parse_args(argv)

    runs: list[RunMetrics] = []
    for result_dir in args.result_dirs:
        try:
            runs.append(aggregate_directory(result_dir, expected_games=args.expected_games))
        except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    if args.json:
        payload = {
            "runs": [
                {
                    "path": str(run.path),
                    "n_games": run.n_games,
                    "success_rate": run.success_rate,
                    "avg_steps": run.avg_steps,
                    "avg_total_tokens": run.avg_total_tokens,
                    "avg_agent_runtime_seconds": run.avg_agent_runtime_seconds,
                    "missing_indices": run.missing_indices,
                }
                for run in runs
            ]
        }
        if len(runs) > 1:
            payload["mean_of_runs"] = {
                "success_rate": _mean_of_runs(runs, "success_rate"),
                "avg_steps": _mean_of_runs(runs, "avg_steps"),
                "avg_total_tokens": _mean_of_runs(runs, "avg_total_tokens"),
                "avg_agent_runtime_seconds": _mean_of_runs(runs, "avg_agent_runtime_seconds"),
            }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    for run in runs:
        print(_format_metrics(run))
        print()

    if args.compare or len(runs) > 1:
        _print_compare_table(runs)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
