# ALFWorld 实验运行命令

本文档只记录两类实验：

- 前 10 局 smoke run：先确认模型、接口、技能检索和结果保存都正常。
- 全量 140 局 run：正式记录指标。

当前只跑两个模型系列（MiniMax 有两种接入方式，**model id 不同**）：

- 智增增：`MiniMax-M2.7-highspeed`
- MiniMax 官方 API + 模型 `MiniMax-M2.7`
- `gpt-5.2-codex`（经智增增，见 §1.1）

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

ALFWorld runner 使用 `API_KEY` 和 `BASE_URL` 调用模型（与 `.env` 里的 `OPENAI_API_KEY` / `OPENAI_BASE_URL` 是两套变量：前者只给 Agent，后者给 GoS embedding / 建索引）。

### 1.1 智增增代理（OpenAI 兼容，当前常用）

```bash
export API_KEY="$OPENAI_API_KEY"
export BASE_URL="$OPENAI_BASE_URL"
```

或手动指定：

```bash
# 智增增后台密钥；不要写进 git
export API_KEY="<智增增后台密钥key>"
export BASE_URL="https://api.zhizengzeng.com/v1"
```

跑 **MiniMax-M2.7-highspeed**、**gpt-5.2-codex** 等经智增增转发的模型时，用这一组即可。

### 1.2 MiniMax 官方 API（不经智增增）

在 [MiniMax 开放平台](https://platform.minimaxi.com/) 创建 API Key 后，在**当前终端**覆盖 Agent 用的地址（也可在 `.env` 中保存 `MINIMAX_API_KEY` / `MINIMAX_BASE_URL`）：

```bash
export API_KEY="<MiniMax 开放平台 API Key>"
export BASE_URL="https://api.minimaxi.com/v1"
export ALFWORLD_MODEL="MiniMax-M2.7"
export LLM_API_TYPE="chat"
```

说明：

- `evaluation/alfworld_run.py` 使用 OpenAI Python SDK 的 `chat.completions`；MiniMax 官方提供 OpenAI 兼容的 `/v1/chat/completions` 接口，因此 `base_url` + `api_key` 的接入方式正确。
- 中国大陆平台使用 `https://api.minimaxi.com/v1`；国际平台使用 `https://api.minimax.io/v1`。API Key 应与注册的平台和 endpoint 对应。
- **官方模型 id 必须使用大小写完全一致的** `MiniMax-M2.7`，不是 `minimax2.7`。因此结果目录中的模型层级也会是 `results/alfworld/MiniMax-M2.7/...`。
- MiniMax M2.x 属于 reasoning 模型，thinking 不能关闭。未启用 `reasoning_split` 时，返回的 `content` 可能包含 `<think>...</think>`；全量实验前应通过 smoke run 确认 `alfworld_run.py` 的动作提取逻辑能够正确处理。
- GoS 技能检索、embedding、`gos index` 仍读取 `.env` 的 `OPENAI_API_KEY` / `OPENAI_BASE_URL`（可继续用智增增），与 Agent 是否走 MiniMax 官方无关。

快速自检（只测 Agent 连通，不跑 ALFWorld）：

```bash
uv run python - <<'PY'
import os
from openai import OpenAI
c = OpenAI(api_key=os.environ["API_KEY"], base_url=os.environ["BASE_URL"])
r = c.chat.completions.create(
    model=os.environ["ALFWORLD_MODEL"],
    messages=[{"role": "user", "content": "reply OK only"}],
    max_completion_tokens=16,
)
print(r.choices[0].message.content)
PY
```

切回智增增跑 Agent 时：

```bash
export API_KEY="$OPENAI_API_KEY"
export BASE_URL="$OPENAI_BASE_URL"
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

正常应看到（智增增示例）：

```text
/home/linfy/.cache/alfworld
API_KEY loaded
https://api.zhizengzeng.com/v1
ALFWorld data ready
skills_alfworld37 ready
workspace ready
```

若使用 MiniMax 官方，`echo "$BASE_URL"` 应为 `https://api.minimaxi.com/v1`（或你配置的 `https://api.minimax.io/v1`）。

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

### 3.1 MiniMax M2.7

先按 §1.1 或 §1.2 配好 `API_KEY` / `BASE_URL`，再设模型名：

**智增增代理（§1.1）**

```bash
export ALFWORLD_MODEL="MiniMax-M2.7-highspeed"
export LLM_API_TYPE="chat"
```

- 走 `chat.completions`。
- 智增增上 `MiniMax-M2.7` 会报 `model or service ID does not exist`，需用 `MiniMax-M2.7-highspeed`。

**MiniMax 官方（§1.2）**

```bash
export ALFWORLD_MODEL="MiniMax-M2.7"
export LLM_API_TYPE="chat"
```

- 同样走 `chat.completions`，但必须保持官方模型 id 的准确大小写：`MiniMax-M2.7`。
- 官方全量命令见 §5.2；实验名统一使用 `minimax_m27_official`，避免与智增增的 `minimax_m27_highspeed` 结果混在一起。


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

### 5.2 MiniMax-M2.7（MiniMax 官方 API）：全量

先确认 Agent 使用 MiniMax 官方 API，而不是智增增：

```bash
export API_KEY="<MiniMax 开放平台 API Key>"
export BASE_URL="https://api.minimaxi.com/v1"
export ALFWORLD_MODEL="MiniMax-M2.7"
export LLM_API_TYPE="chat"
```

> 若使用国际平台账号，将 `BASE_URL` 改为 `https://api.minimax.io/v1`。若 `.env` 已保存 `MINIMAX_API_KEY`，第一行也可写成 `export API_KEY="$MINIMAX_API_KEY"`。

建议先执行 §1.2 的快速自检，并确认：

```bash
echo "$BASE_URL"
echo "$ALFWORLD_MODEL"
```

应分别输出 MiniMax 官方 endpoint 和精确模型 id `MiniMax-M2.7`。

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
  --exp_name full_gos_alfworld37_minimax_m27_official_run1

# run2：将 --exp_name 改为 full_gos_alfworld37_minimax_m27_official_run2
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
  --exp_name full_vector_alfworld37_minimax_m27_official_run1

# run2：将 --exp_name 改为 full_vector_alfworld37_minimax_m27_official_run2
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
  --exp_name full_allfull_alfworld37_minimax_m27_official_run1

# run2：将 --exp_name 改为 full_allfull_alfworld37_minimax_m27_official_run2
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
  --exp_name full_none_minimax_m27_official_run1

# run2：将 --exp_name 改为 full_none_minimax_m27_official_run2
```

### 5.3 gpt-5.2-codex：全量

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
results/alfworld/MiniMax-M2.7/dev_full_gos_alfworld37_minimax_m27_official_run1_mode_gos/
results/alfworld/gpt-5.2-codex/dev_full_gos_alfworld37_gpt52codex_run1_mode_gos/
```

---

## 7. 汇总指标

汇总脚本：

```bash
uv run python evaluation/aggregate_alfworld_results.py <结果目录>
```

指标含义：


| 指标                    | JSON 字段                            |
| --------------------- | ---------------------------------- |
| 平均 reward / 成功率       | `reward`（0/1 均值）                   |
| 平均 steps              | `steps`                            |
| 平均 token              | `token_usage.total_tokens`         |
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
  results/alfworld/MiniMax-M2.7/dev_full_gos_alfworld37_minimax_m27_official_run1_mode_gos

uv run python evaluation/aggregate_alfworld_results.py \
  results/alfworld/gpt-5.2-codex/dev_full_gos_alfworld37_gpt52codex_run1_mode_gos
```

### 7.3 对比多组结果

```bash
uv run python evaluation/aggregate_alfworld_results.py --compare \
  results/alfworld/MiniMax-M2.7-highspeed/dev_full_gos_alfworld37_minimax_m27_highspeed_run1_mode_gos \
  results/alfworld/MiniMax-M2.7/dev_full_gos_alfworld37_minimax_m27_official_run1_mode_gos \
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
1. MiniMax-M2.7-highspeed（智增增）：前 10 局 GoS
2. MiniMax-M2.7-highspeed（智增增）：前 10 局 Vector / All Full / None
3. MiniMax-M2.7（官方）：执行 §1.2 快速自检；需要时复用 §4.1 做 10 局 smoke run，并将实验名改为 `minimax_m27_official`
4. gpt-5.2-codex：前 10 局 GoS
5. gpt-5.2-codex：前 10 局 Vector / All Full / None
6. MiniMax-M2.7-highspeed（智增增）：全量 140 局，四种模式，各跑 run1 / run2
7. MiniMax-M2.7（官方）：按 §5.2 跑全量 140 局，四种模式，各跑 run1 / run2
8. gpt-5.2-codex：全量 140 局，四种模式，各跑 run1 / run2
9. 使用 aggregate_alfworld_results.py 汇总指标
```

