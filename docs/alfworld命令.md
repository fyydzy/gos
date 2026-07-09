# ALFWorld 实验运行命令

本文档只记录两类实验：

- 前 10 局 smoke run：先确认模型、接口、技能检索和结果保存都正常。
- 全量 140 局 run：正式记录指标。

当前只跑两个模型：

- `MiniMax-M2.7-highspeed`
- `gpt-5.2-codex`

默认使用抽取后的 37 个 ALFWorld 专用技能：

```bash
--skills_dir data/skillsets/skills_alfworld37
--gos_workspace data/gos_workspace/skills_alfworld37_v1
```

---

## 1. 进入项目并加载配置

以下命令均在服务器仓库根目录执行：

```bash
cd ~/graph-of-skills

set -a
source .env
set +a
```

ALFWorld runner 使用 `API_KEY` 和 `BASE_URL` 调用模型：

```bash
export API_KEY="$OPENAI_API_KEY"
export BASE_URL="$OPENAI_BASE_URL"
```

如果需要手动指定智增增配置：

```bash
# 智增增后台密钥；不要写进 git
export API_KEY="<智增增后台密钥key>"
export BASE_URL="https://api.zhizengzeng.com/v1"
```

清除此前可能给 Docker 配过的代理变量：

```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
```

确认 ALFWorld 数据和抽取后的技能库都在：

```bash
echo "$ALFWORLD_DATA"
test -n "$API_KEY" && echo "API_KEY loaded"
echo "$BASE_URL"

ls "$ALFWORLD_DATA/json_2.1.1/valid_unseen" >/dev/null && echo "ALFWorld data ready"
ls data/skillsets/skills_alfworld37 >/dev/null && echo "skills_alfworld37 ready"
ls data/gos_workspace/skills_alfworld37_v1 >/dev/null && echo "workspace ready"
```

正常应看到：

```text
/home/linfy/.cache/alfworld
API_KEY loaded
https://api.zhizengzeng.com/v1
ALFWorld data ready
skills_alfworld37 ready
workspace ready
```

---

## 2. 技能库准备

如果 `data/skillsets/skills_alfworld37` 或 `data/gos_workspace/skills_alfworld37_v1` 不存在，先重新抽取并建索引：

```bash
python3 scripts/extract_alfworld37_skills.py --clear --index
```

如果只想复制 37 个技能、不重建 workspace：

```bash
python3 scripts/extract_alfworld37_skills.py --clear
```

如果索引时报 `OpenAIException - Connection error`，通常是当前终端访问 embedding 接口失败；先确认 `.env` 中的 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`GOS_EMBEDDING_MODEL` 可用，再重跑建索引命令。

---

## 3. 模型切换

每次跑一个模型前，先设置模型变量。

### 3.1 MiniMax-M2.7-highspeed

```bash
export ALFWORLD_MODEL="MiniMax-M2.7-highspeed"
export LLM_API_TYPE="chat"
```

说明：

- `MiniMax-M2.7-highspeed` 当前走原来的 `chat.completions`。
- `MiniMax-M2.7` 不是可用 service ID，之前会返回 `model or service ID does not exist`。

### 3.2 gpt-5.2-codex

```bash
export ALFWORLD_MODEL="gpt-5.2-codex"
export LLM_API_TYPE="responses"
```

说明：

- Codex 系列模型如果遇到 `This model is not supported in the v1/chat/completions endpoint`，就必须走 Responses API。
- 这里显式设置 `LLM_API_TYPE="responses"`，便于和 MiniMax 的 `chat` 路径区分。
- 如果以后要改回原来的 chat 路径，只要改成 `export LLM_API_TYPE="chat"`。

---

## 4. 前 10 局实验

前 10 局用于快速确认模型能跑通。四种模式都使用：

```bash
--split dev
--max_games 10
--max_workers 1
--max_steps 30
```

### 4.1 MiniMax-M2.7-highspeed：前 10 局

先切模型：

```bash
export ALFWORLD_MODEL="MiniMax-M2.7-highspeed"
export LLM_API_TYPE="chat"
```

GoS：

```bash
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split dev \
  --use_skill \
  --mode gos \
  --gos_workspace data/gos_workspace/skills_alfworld37_v1 \
  --skills_dir data/skillsets/skills_alfworld37 \
  --max_games 10 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name eval10_gos_alfworld37_minimax_m27_highspeed
```

Vector：

```bash
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split dev \
  --use_skill \
  --mode vector \
  --gos_workspace data/gos_workspace/skills_alfworld37_v1 \
  --skills_dir data/skillsets/skills_alfworld37 \
  --max_games 10 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name eval10_vector_alfworld37_minimax_m27_highspeed
```

All Full：

```bash
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split dev \
  --use_skill \
  --mode all_full \
  --skills_dir data/skillsets/skills_alfworld37 \
  --max_games 10 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name eval10_allfull_alfworld37_minimax_m27_highspeed
```

No Skills：

```bash
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split dev \
  --mode none \
  --max_games 10 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name eval10_none_minimax_m27_highspeed
```

### 4.2 gpt-5.2-codex：前 10 局

先切模型：

```bash
export ALFWORLD_MODEL="gpt-5.2-codex"
export LLM_API_TYPE="responses"
```

GoS：

```bash
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split dev \
  --use_skill \
  --mode gos \
  --gos_workspace data/gos_workspace/skills_alfworld37_v1 \
  --skills_dir data/skillsets/skills_alfworld37 \
  --max_games 10 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name eval10_gos_alfworld37_gpt52codex
```

Vector：

```bash
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split dev \
  --use_skill \
  --mode vector \
  --gos_workspace data/gos_workspace/skills_alfworld37_v1 \
  --skills_dir data/skillsets/skills_alfworld37 \
  --max_games 10 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name eval10_vector_alfworld37_gpt52codex
```

All Full：

```bash
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split dev \
  --use_skill \
  --mode all_full \
  --skills_dir data/skillsets/skills_alfworld37 \
  --max_games 10 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name eval10_allfull_alfworld37_gpt52codex
```

No Skills：

```bash
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split dev \
  --mode none \
  --max_games 10 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name eval10_none_gpt52codex
```

---

## 5. 全量 140 局实验

全量实验不写 `--max_games`，默认跑完整 `dev` split 的 140 局。建议每个模型、每种模式跑两次，第二次只改 `run1` 为 `run2`。

统一参数：

```bash
--split dev
--max_workers 1
--max_steps 30
```

### 5.1 MiniMax-M2.7-highspeed：全量

先切模型：

```bash
export ALFWORLD_MODEL="MiniMax-M2.7-highspeed"
export LLM_API_TYPE="chat"
```

GoS：

```bash
# run1
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split dev \
  --use_skill \
  --mode gos \
  --gos_workspace data/gos_workspace/skills_alfworld37_v1 \
  --skills_dir data/skillsets/skills_alfworld37 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name full_gos_alfworld37_minimax_m27_highspeed_run1

# run2：将 --exp_name 改为 full_gos_alfworld37_minimax_m27_highspeed_run2
```

Vector：

```bash
# run1
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split dev \
  --use_skill \
  --mode vector \
  --gos_workspace data/gos_workspace/skills_alfworld37_v1 \
  --skills_dir data/skillsets/skills_alfworld37 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name full_vector_alfworld37_minimax_m27_highspeed_run1

# run2：将 --exp_name 改为 full_vector_alfworld37_minimax_m27_highspeed_run2
```

All Full：

```bash
# run1
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split dev \
  --use_skill \
  --mode all_full \
  --skills_dir data/skillsets/skills_alfworld37 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name full_allfull_alfworld37_minimax_m27_highspeed_run1

# run2：将 --exp_name 改为 full_allfull_alfworld37_minimax_m27_highspeed_run2
```

No Skills：

```bash
# run1
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split dev \
  --mode none \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name full_none_minimax_m27_highspeed_run1

# run2：将 --exp_name 改为 full_none_minimax_m27_highspeed_run2
```

### 5.2 gpt-5.2-codex：全量

先切模型：

```bash
export ALFWORLD_MODEL="gpt-5.2-codex"
export LLM_API_TYPE="responses"
```

GoS：

```bash
# run1
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split dev \
  --use_skill \
  --mode gos \
  --gos_workspace data/gos_workspace/skills_alfworld37_v1 \
  --skills_dir data/skillsets/skills_alfworld37 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name full_gos_alfworld37_gpt52codex_run1

# run2：将 --exp_name 改为 full_gos_alfworld37_gpt52codex_run2
```

Vector：

```bash
# run1
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split dev \
  --use_skill \
  --mode vector \
  --gos_workspace data/gos_workspace/skills_alfworld37_v1 \
  --skills_dir data/skillsets/skills_alfworld37 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name full_vector_alfworld37_gpt52codex_run1

# run2：将 --exp_name 改为 full_vector_alfworld37_gpt52codex_run2
```

All Full：

```bash
# run1
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split dev \
  --use_skill \
  --mode all_full \
  --skills_dir data/skillsets/skills_alfworld37 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name full_allfull_alfworld37_gpt52codex_run1

# run2：将 --exp_name 改为 full_allfull_alfworld37_gpt52codex_run2
```

No Skills：

```bash
# run1
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split dev \
  --mode none \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name full_none_gpt52codex_run1

# run2：将 --exp_name 改为 full_none_gpt52codex_run2
```

---

## 6. 结果目录规则

`alfworld_run.py` 的结果目录规则是：

```text
results/alfworld/{model}/{split}_{exp_name}_mode_{mode}/
```

例如：

```text
results/alfworld/MiniMax-M2.7-highspeed/dev_eval10_gos_alfworld37_minimax_m27_highspeed_mode_gos/
results/alfworld/gpt-5.2-codex/dev_eval10_gos_alfworld37_gpt52codex_mode_gos/
results/alfworld/MiniMax-M2.7-highspeed/dev_full_gos_alfworld37_minimax_m27_highspeed_run1_mode_gos/
results/alfworld/gpt-5.2-codex/dev_full_gos_alfworld37_gpt52codex_run1_mode_gos/
```

---

## 7. 汇总指标

汇总脚本：

```bash
uv run python evaluation/aggregate_alfworld_results.py <结果目录>
```

指标含义：

| 指标 | JSON 字段 |
| --- | --- |
| 平均 reward / 成功率 | `reward`（0/1 均值） |
| 平均 steps | `steps` |
| 平均 token | `token_usage.total_tokens` |
| 平均 agent-only runtime | `agent_runtime_seconds`（不含环境 init） |

### 7.1 汇总前 10 局

前 10 局需要显式写 `--expected-games 10`：

```bash
uv run python evaluation/aggregate_alfworld_results.py \
  results/alfworld/MiniMax-M2.7-highspeed/dev_eval10_gos_alfworld37_minimax_m27_highspeed_mode_gos \
  --expected-games 10

uv run python evaluation/aggregate_alfworld_results.py \
  results/alfworld/gpt-5.2-codex/dev_eval10_gos_alfworld37_gpt52codex_mode_gos \
  --expected-games 10
```

### 7.2 汇总全量 140 局

全量默认 `--expected-games 140`：

```bash
uv run python evaluation/aggregate_alfworld_results.py \
  results/alfworld/MiniMax-M2.7-highspeed/dev_full_gos_alfworld37_minimax_m27_highspeed_run1_mode_gos

uv run python evaluation/aggregate_alfworld_results.py \
  results/alfworld/gpt-5.2-codex/dev_full_gos_alfworld37_gpt52codex_run1_mode_gos
```

### 7.3 对比多组结果

```bash
uv run python evaluation/aggregate_alfworld_results.py --compare \
  results/alfworld/MiniMax-M2.7-highspeed/dev_full_gos_alfworld37_minimax_m27_highspeed_run1_mode_gos \
  results/alfworld/gpt-5.2-codex/dev_full_gos_alfworld37_gpt52codex_run1_mode_gos
```

两次 run 对比：

```bash
uv run python evaluation/aggregate_alfworld_results.py --compare \
  results/alfworld/MiniMax-M2.7-highspeed/dev_full_gos_alfworld37_minimax_m27_highspeed_run1_mode_gos \
  results/alfworld/MiniMax-M2.7-highspeed/dev_full_gos_alfworld37_minimax_m27_highspeed_run2_mode_gos
```

---

## 8. 建议运行顺序

建议按下面顺序执行，先确认 10 局，再跑全量：

```text
1. MiniMax-M2.7-highspeed：前 10 局 GoS
2. MiniMax-M2.7-highspeed：前 10 局 Vector / All Full / None
3. gpt-5.2-codex：前 10 局 GoS
4. gpt-5.2-codex：前 10 局 Vector / All Full / None
5. MiniMax-M2.7-highspeed：全量 140 局，四种模式，各跑 run1 / run2
6. gpt-5.2-codex：全量 140 局，四种模式，各跑 run1 / run2
7. 使用 aggregate_alfworld_results.py 汇总指标
```
