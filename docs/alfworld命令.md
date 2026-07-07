# ALFWorld 四种模式实验运行步骤

## 1. 进入项目目录并加载配置

以下命令均在**服务器仓库根目录**执行：

```bash
cd ~/graph-of-skills

set -a
source .env
set +a
```

ALFWorld runner 使用 `API_KEY` 和 `BASE_URL` 调用模型，因此需要额外设置：

```bash
export API_KEY="$OPENAI_API_KEY"
export BASE_URL="$OPENAI_BASE_URL"
```

```bash
# 智增增后台密钥；不要写进 git
export API_KEY="<智增增后台密钥key>"
export BASE_URL="https://api.zhizengzeng.com/v1"

# 当前实测可用：MiniMax-M2.7-highspeed
# MiniMax-M2.7 会返回 “model or service ID does not exist”
export ALFWORLD_MODEL="MiniMax-M2.7-highspeed"
```

由于 ALFWorld 直接在服务器上运行，且服务器可以直连智增增接口，因此清除此前为 Docker 配置的代理变量：

```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
```

确认配置正常：

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



## 2. 单任务四种模式对比

首先固定运行第 `0` 个任务，用于确认四种模式都能正常执行，并观察同一任务下的差异。

### 2.1 GoS 模式

```bash
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split eval_out_of_distribution \
  --use_skill \
  --mode gos \
  --gos_workspace data/gos_workspace/skills_alfworld37_v1 \
  --skills_dir data/skillsets/skills_alfworld37 \
  --task_indices 0 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name compare_idx0_gos_alfworld37_minimax_m27_highspeed
```

结果文件：

```text
results/alfworld/MiniMax-M2.7-highspeed/eval_out_of_distribution_compare_idx0_gos_alfworld37_minimax_m27_highspeed_mode_gos/idx_0.json
```



### 2.2 Vector Skills 模式

```bash
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split eval_out_of_distribution \
  --use_skill \
  --mode vector \
  --gos_workspace data/gos_workspace/skills_alfworld37_v1 \
  --skills_dir data/skillsets/skills_alfworld37 \
  --task_indices 0 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name compare_idx0_vector_alfworld37_minimax_m27_highspeed
```

结果文件：

```text
results/alfworld/MiniMax-M2.7-highspeed/eval_out_of_distribution_compare_idx0_vector_alfworld37_minimax_m27_highspeed_mode_vector/idx_0.json
```



### 2.3 All Full Skills 模式

```bash
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split eval_out_of_distribution \
  --use_skill \
  --mode all_full \
  --skills_dir data/skillsets/skills_alfworld37 \
  --task_indices 0 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name compare_idx0_allfull_alfworld37_minimax_m27_highspeed
```

结果文件：

```text
results/alfworld/MiniMax-M2.7-highspeed/eval_out_of_distribution_compare_idx0_allfull_alfworld37_minimax_m27_highspeed_mode_all_full/idx_0.json
```



### 2.4 No Skills 模式

```bash
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split eval_out_of_distribution \
  --mode none \
  --task_indices 0 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name compare_idx0_none_minimax_m27_highspeed
```

结果文件：

```text
results/alfworld/MiniMax-M2.7-highspeed/eval_out_of_distribution_compare_idx0_none_minimax_m27_highspeed_mode_none/idx_0.json
```

---



## 3. 前 10 个任务的四种模式对比

单任务运行确认没有报错后，再运行前 `10` 个任务。四种模式均使用相同的：

```bash
--max_games 10
--max_workers 1
--max_steps 30
```

这样可以保证实验设置一致。

### 3.0 只用 37 个 ALFWorld 技能的独立技能库

`skills_500` 里包含 37 个 `alfworld-*` 专用技能，但也混有大量其它领域技能。若要单独评测「只给 ALFWorld 技能」的设置，先抽取独立 skillset，并构建匹配的 GoS workspace：

```bash
# 一条命令完成复制 + 建索引；脚本会读取仓库根目录 .env
python3 scripts/extract_alfworld37_skills.py --clear --index
```

如果只想先复制技能、不建 workspace：

```bash
python3 scripts/extract_alfworld37_skills.py --clear
```

如果索引时报 `OpenAIException - Connection error`，说明当前终端访问 embedding 接口失败；先确认 `.env` 中的 GoS embedding 配置可用，再重跑 `python3 scripts/extract_alfworld37_skills.py --clear --index`。

后续 ALFWorld 命令使用这对目录：

```bash
--skills_dir data/skillsets/skills_alfworld37
--gos_workspace data/gos_workspace/skills_alfworld37_v1
```

例如用 **MiniMax M2.7-highspeed** 跑前 10 局 GoS：

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

如果你要先用 **gpt-5.3-codex** 跑前 10 局，先切模型变量：

```bash
export ALFWORLD_MODEL="gpt-5.3-codex"
```

`gpt-5.3-codex` 需要走 OpenAI Responses API。代码默认 `LLM_API_TYPE=auto`，会自动让 `gpt-5.3-codex` 走 responses，其它模型仍走原来的 `chat.completions`。如果以后要强制改回原逻辑：

```bash
export LLM_API_TYPE="chat"
```

如果要显式指定走 responses：

```bash
export LLM_API_TYPE="responses"
```

先跑 GoS（推荐先 smoke 这一条）：

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
  --exp_name eval10_gos_alfworld37_gpt53codex
```

如果要直接跑前 10 局四种模式，对应命令如下（仅 `--mode` / `--exp_name` 不同）：

```bash
# 1) GoS
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split dev \
  --use_skill \
  --mode gos \
  --gos_workspace data/gos_workspace/skills_alfworld37_v1 \
  --skills_dir data/skillsets/skills_alfworld37 \
  --max_games 10 --max_workers 1 --max_steps 30 \
  --exp_name eval10_gos_alfworld37_gpt53codex

# 2) Vector
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split dev \
  --use_skill \
  --mode vector \
  --gos_workspace data/gos_workspace/skills_alfworld37_v1 \
  --skills_dir data/skillsets/skills_alfworld37 \
  --max_games 10 --max_workers 1 --max_steps 30 \
  --exp_name eval10_vector_alfworld37_gpt53codex

# 3) All Full
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split dev \
  --use_skill \
  --mode all_full \
  --skills_dir data/skillsets/skills_alfworld37 \
  --max_games 10 --max_workers 1 --max_steps 30 \
  --exp_name eval10_allfull_alfworld37_gpt53codex

# 4) None
uv run python evaluation/alfworld_run.py \
  --model "$ALFWORLD_MODEL" \
  --split dev \
  --mode none \
  --max_games 10 --max_workers 1 --max_steps 30 \
  --exp_name eval10_none_gpt53codex
```



### 3.1 GoS 模式：前 10 个任务

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

结果目录：

```text
results/alfworld/MiniMax-M2.7-highspeed/dev_eval10_gos_alfworld37_minimax_m27_highspeed_mode_gos/
```

其中每个任务对应一个结果文件，例如：

```text
idx_0.json
idx_1.json
...
idx_9.json
```



### 3.2 Vector Skills 模式：前 10 个任务

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

结果目录：

```text
results/alfworld/MiniMax-M2.7-highspeed/dev_eval10_vector_alfworld37_minimax_m27_highspeed_mode_vector/
```



### 3.3 All Full Skills 模式：前 10 个任务

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

结果目录：

```text
results/alfworld/MiniMax-M2.7-highspeed/dev_eval10_allfull_alfworld37_minimax_m27_highspeed_mode_all_full/
```

注意：`all_full` 会将抽取后的 37 个 ALFWorld 技能全部加入上下文，token 消耗可能明显高于其他模式。

### 3.4 No Skills 模式：前 10 个任务

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

结果目录：

```text
results/alfworld/MiniMax-M2.7-highspeed/dev_eval10_none_minimax_m27_highspeed_mode_none/
```

---



## 4. 运行顺序建议

建议按照以下顺序执行：

```text
1. 单任务：gos
2. 单任务：vector
3. 单任务：all_full
4. 单任务：none
5. 前 10 个任务：gos
6. 前 10 个任务：vector
7. 前 10 个任务：all_full
8. 前 10 个任务：none
```

单任务阶段确认四种模式都能正常生成 `idx_0.json` 后，再开始前 10 个任务的实验。

**5.1 GoS 全量（跑2次）**

```bash
# 第一次
uv run python evaluation/alfworld_run.py --model "$ALFWORLD_MODEL" --split dev --use_skill --mode gos --gos_workspace data/gos_workspace/skills_alfworld37_v1 --skills_dir data/skillsets/skills_alfworld37 --max_workers 1 --max_steps 30 --exp_name full_gos_alfworld37_minimax_m27_highspeed_run1
# 第二次：将 --exp_name 改为 full_gos_alfworld37_minimax_m27_highspeed_run2
```

**5.2 Vector 全量（跑2次）**

```bash
# 第一次
uv run python evaluation/alfworld_run.py --model "$ALFWORLD_MODEL" --split dev --use_skill --mode vector --gos_workspace data/gos_workspace/skills_alfworld37_v1 --skills_dir data/skillsets/skills_alfworld37 --max_workers 1 --max_steps 30 --exp_name full_vector_alfworld37_minimax_m27_highspeed_run1
# 第二次：将 --exp_name 改为 full_vector_alfworld37_minimax_m27_highspeed_run2
```

**5.3 All Full 全量（跑2次）**

```bash
# 第一次
uv run python evaluation/alfworld_run.py --model "$ALFWORLD_MODEL" --split dev --use_skill --mode all_full --skills_dir data/skillsets/skills_alfworld37 --max_workers 1 --max_steps 30 --exp_name full_allfull_alfworld37_minimax_m27_highspeed_run1
# 第二次：将 --exp_name 改为 full_allfull_alfworld37_minimax_m27_highspeed_run2
```

**5.4 No Skills 全量（跑2次）**

```bash
# 第一次
uv run python evaluation/alfworld_run.py --model "$ALFWORLD_MODEL" --split dev --mode none --max_workers 1 --max_steps 30 --exp_name full_none_minimax_m27_highspeed_run1
# 第二次：将 --exp_name 改为 full_none_minimax_m27_highspeed_run2
```



### 6. 结果检验与对比指标

全部跑完后，每个目录应有约 140 个 `idx_*.json` 文件。

```bash
# 检查数量示例
find results/alfworld/MiniMax-M2.7-highspeed/dev_full_gos_alfworld37_minimax_m27_highspeed_run1_mode_gos -name "idx_*.json" | wc -l
```

**汇总核心指标**（脚本：`evaluation/aggregate_alfworld_results.py`）

从结果目录下所有 `idx_*.json` 计算：


| 指标                    | JSON 字段                            |
| --------------------- | ---------------------------------- |
| 平均 reward / 成功率       | `reward`（0/1 均值）                   |
| 平均 steps              | `steps`                            |
| 平均 token              | `token_usage.total_tokens`         |
| 平均 agent-only runtime | `agent_runtime_seconds`（不含环境 init） |


**1）140 局完整实验（默认** `--expected-games 140`**，缺局会提示缺失 idx）：**

```bash
uv run python evaluation/aggregate_alfworld_results.py \
  results/alfworld/MiniMax-M2.7-highspeed/dev_full_gos_alfworld37_minimax_m27_highspeed_run1_mode_gos

uv run python evaluation/aggregate_alfworld_results.py \
  results/alfworld/MiniMax-M2.7-highspeed/dev_full_vector_alfworld37_minimax_m27_highspeed_run1_mode_vector
```

**2）smoke / 前 10 局（**`--max_games 10` **时目录名示例，需显式** `--expected-games 10`**）：**

```bash
uv run python evaluation/aggregate_alfworld_results.py \
  results/alfworld/MiniMax-M2.7-highspeed/dev_eval10_gos_alfworld37_minimax_m27_highspeed_mode_gos \
  --expected-games 10
```

**3）论文两次 run 对比（表格 +** `mean_of_runs` **行，即两次 run 各指标再取平均）：**

```bash
uv run python evaluation/aggregate_alfworld_results.py --compare \
  results/alfworld/MiniMax-M2.7-highspeed/dev_full_gos_alfworld37_minimax_m27_highspeed_run1_mode_gos \
  results/alfworld/MiniMax-M2.7-highspeed/dev_full_gos_alfworld37_minimax_m27_highspeed_run2_mode_gos
```

**4）机器可读 JSON（写表 / 脚本下游用）：**

```bash
uv run python evaluation/aggregate_alfworld_results.py --json \
  results/alfworld/MiniMax-M2.7-highspeed/dev_full_gos_alfworld37_minimax_m27_highspeed_run1_mode_gos
```

**5）同时看多组实验（例如 gos / vector / none 各跑完一次）：**

```bash
uv run python evaluation/aggregate_alfworld_results.py --compare \
  results/alfworld/MiniMax-M2.7-highspeed/dev_full_gos_alfworld37_minimax_m27_highspeed_run1_mode_gos \
  results/alfworld/MiniMax-M2.7-highspeed/dev_full_vector_alfworld37_minimax_m27_highspeed_run1_mode_vector \
  results/alfworld/MiniMax-M2.7-highspeed/dev_full_none_minimax_m27_highspeed_run1_mode_none
```

结果目录命名规则（与 `alfworld_run.py` 一致）：

```text
results/alfworld/{model}/{split}_{exp_name}_mode_{mode}/
```

例如：`results/alfworld/MiniMax-M2.7-highspeed/dev_full_gos_alfworld37_minimax_m27_highspeed_run1_mode_gos/idx_0.json`

```bash
# 1. 追踪并保存所有修改过的文件（注意 add 后面有个空格和英文句号）
git add .

# 2. 提交修改，并写一条简短的备注（引号里的字换成你这次具体改了什么）
git commit -m "修改了xxx参数 / 添加了xxx新功能"

# 3. 把最新的代码推送到 GitHub 云端
git push
```

