#!/usr/bin/env python3
"""Create an ALFWorld-only skillset and, optionally, build its GoS workspace.

Default output:
  - data/skillsets/skills_alfworld37
  - data/gos_workspace/skills_alfworld37_v1

The output names intentionally share the same prefix because
evaluation/alfworld_run.py checks that --skills_dir and --gos_workspace match.
"""

from __future__ import annotations

import argparse
import os
import shutil
import shlex
import subprocess
import sys
from pathlib import Path


DEFAULT_SOURCE = Path("data/skillsets/skills_500")
DEFAULT_SKILLSET_OUT = Path("data/skillsets/skills_alfworld37")
DEFAULT_WORKSPACE_OUT = Path("data/gos_workspace/skills_alfworld37_v1")
EXPECTED_COUNT = 37


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else repo_root() / path


def discover_alfworld_skills(source: Path) -> list[Path]:
    if not source.is_dir():
        raise FileNotFoundError(f"source skillset directory not found: {source}")

    skills = [
        path
        for path in sorted(source.iterdir())
        if path.is_dir()
        and path.name.startswith("alfworld-")
        and (path / "SKILL.md").is_file()
    ]
    if len(skills) != EXPECTED_COUNT:
        names = ", ".join(path.name for path in skills[:10])
        raise RuntimeError(
            f"expected {EXPECTED_COUNT} alfworld-* skills under {source}, "
            f"found {len(skills)}. First matches: {names}"
        )
    return skills


def copy_skillset(skills: list[Path], destination: Path, *, clear: bool) -> None:
    if destination.exists():
        if not clear:
            raise FileExistsError(
                f"destination already exists: {destination}. Use --clear to overwrite it."
            )
        shutil.rmtree(destination)

    destination.mkdir(parents=True, exist_ok=True)
    for skill_dir in skills:
        shutil.copytree(skill_dir, destination / skill_dir.name)


def load_repo_env() -> None:
    """Load repo-root .env into os.environ for `uv run gos index`.

    We keep existing shell variables unchanged and avoid printing any values.
    """

    env_path = repo_root() / ".env"
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not key.replace("_", "").isalnum():
            continue

        value = value.strip()
        try:
            parts = shlex.split(value, comments=False, posix=True)
            value = parts[0] if parts else ""
        except ValueError:
            value = value.strip("\"'")

        os.environ.setdefault(key, value)


def build_workspace(skillset_dir: Path, workspace_dir: Path, *, clear: bool) -> None:
    load_repo_env()
    command = [
        "uv",
        "run",
        "gos",
        "index",
        str(skillset_dir),
        "--workspace",
        str(workspace_dir),
    ]
    if clear:
        command.append("--clear")

    print("\nBuilding GoS workspace:")
    print("  " + " ".join(command))
    subprocess.run(command, cwd=repo_root(), check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract the 37 alfworld-* skills into a standalone skillset."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"Source skillset containing alfworld-* skills (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--skillset-out",
        type=Path,
        default=DEFAULT_SKILLSET_OUT,
        help=f"Output skillset directory (default: {DEFAULT_SKILLSET_OUT})",
    )
    parser.add_argument(
        "--workspace-out",
        type=Path,
        default=DEFAULT_WORKSPACE_OUT,
        help=f"Output GoS workspace directory (default: {DEFAULT_WORKSPACE_OUT})",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Overwrite existing output skillset/workspace when present.",
    )
    parser.add_argument(
        "--index",
        action="store_true",
        help="After copying skills, run `uv run gos index` to build the workspace.",
    )
    args = parser.parse_args(argv)

    source = resolve_repo_path(args.source)
    skillset_out = resolve_repo_path(args.skillset_out)
    workspace_out = resolve_repo_path(args.workspace_out)

    skills = discover_alfworld_skills(source)
    copy_skillset(skills, skillset_out, clear=args.clear)

    print(f"Copied {len(skills)} ALFWorld skills")
    print(f"  from: {source}")
    print(f"  to:   {skillset_out}")

    if args.index:
        build_workspace(skillset_out, workspace_out, clear=args.clear)
        print(f"Workspace ready: {workspace_out}")
    else:
        print("\nNext step: build the matching GoS workspace:")
        print(
            "  uv run gos index "
            f"{skillset_out.relative_to(repo_root())} "
            f"--workspace {workspace_out.relative_to(repo_root())} --clear"
        )

    print("\nUse in ALFWorld:")
    print(f"  --skills_dir {skillset_out.relative_to(repo_root())}")
    print(f"  --gos_workspace {workspace_out.relative_to(repo_root())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
