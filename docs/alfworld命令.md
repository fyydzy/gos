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
ls data/skillsets/skills_200 >/dev/null && echo "skills_200 ready"
ls data/gos_workspace/skills_200_v1 >/dev/null && echo "workspace ready"
```

正常应看到：

```text
/home/linfy/.cache/alfworld
API_KEY loaded
https://api.zhizengzeng.com/v1
ALFWorld data ready
skills_200 ready
workspace ready
```

---

## 2. 单任务四种模式对比

首先固定运行第 `0` 个任务，用于确认四种模式都能正常执行，并观察同一任务下的差异。

### 2.1 GoS 模式

```bash
uv run python evaluation/alfworld_run.py \
  --model gpt-4o \
  --split eval_out_of_distribution \
  --use_skill \
  --mode gos \
  --gos_workspace data/gos_workspace/skills_200_v1 \
  --skills_dir data/skillsets/skills_200 \
  --task_indices 0 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name compare_idx0_gos
```

结果文件：

```text
results/alfworld/gpt-4o/eval_out_of_distribution_compare_idx0_gos_mode_gos/idx_0.json
```

### 2.2 Vector Skills 模式

```bash
uv run python evaluation/alfworld_run.py \
  --model gpt-4o \
  --split eval_out_of_distribution \
  --use_skill \
  --mode vector \
  --gos_workspace data/gos_workspace/skills_200_v1 \
  --skills_dir data/skillsets/skills_200 \
  --task_indices 0 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name compare_idx0_vector
```

结果文件：

```text
results/alfworld/gpt-4o/eval_out_of_distribution_compare_idx0_vector_mode_vector/idx_0.json
```

### 2.3 All Full Skills 模式

```bash
uv run python evaluation/alfworld_run.py \
  --model gpt-4o \
  --split eval_out_of_distribution \
  --use_skill \
  --mode all_full \
  --skills_dir data/skillsets/skills_200 \
  --task_indices 0 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name compare_idx0_allfull
```

结果文件：

```text
results/alfworld/gpt-4o/eval_out_of_distribution_compare_idx0_allfull_mode_all_full/idx_0.json
```

### 2.4 No Skills 模式

```bash
uv run python evaluation/alfworld_run.py \
  --model gpt-4o \
  --split eval_out_of_distribution \
  --mode none \
  --task_indices 0 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name compare_idx0_none
```

结果文件：

```text
results/alfworld/gpt-4o/eval_out_of_distribution_compare_idx0_none_mode_none/idx_0.json
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

### 3.1 GoS 模式：前 10 个任务

```bash
uv run python evaluation/alfworld_run.py \
  --model gpt-4o-mini \
  --split dev \
  --use_skill \
  --mode gos \
  --gos_workspace data/gos_workspace/skills_500_v1 \
  --skills_dir data/skillsets/skills_500 \
  --max_games 10 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name eval10_gos_skills500
```

结果目录：

```text
results/alfworld/gpt-4o/eval_out_of_distribution_eval10_gos_mode_gos/
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
  --model gpt-4o \
  --split eval_out_of_distribution \
  --use_skill \
  --mode vector \
  --gos_workspace data/gos_workspace/skills_500_v1 \
  --skills_dir data/skillsets/skills_500 \
  --max_games 10 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name eval10_vector
```

结果目录：

```text
results/alfworld/gpt-4o/eval_out_of_distribution_eval10_vector_mode_vector/
```

### 3.3 All Full Skills 模式：前 10 个任务

```bash
uv run python evaluation/alfworld_run.py \
  --model gpt-4o \
  --split eval_out_of_distribution \
  --use_skill \
  --mode all_full \
  --skills_dir data/skillsets/skills_500 \
  --max_games 10 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name eval10_allfull
```

结果目录：

```text
results/alfworld/gpt-4o/eval_out_of_distribution_eval10_allfull_mode_all_full/
```

注意：`all_full` 会将完整技能库加入上下文，token 消耗可能明显高于其他模式。

### 3.4 No Skills 模式：前 10 个任务

```bash
uv run python evaluation/alfworld_run.py \
  --model gpt-4o \
  --split eval_out_of_distribution \
  --mode none \
  --max_games 10 \
  --max_workers 1 \
  --max_steps 30 \
  --exp_name eval10_none
```

结果目录：

```text
results/alfworld/gpt-4o/eval_out_of_distribution_eval10_none_mode_none/
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
uv run python evaluation/alfworld_run.py --model gpt-4o-mini --split dev --use_skill --mode gos --gos_workspace data/gos_workspace/skills_500_v1 --skills_dir data/skillsets/skills_500 --max_workers 1 --max_steps 30 --exp_name full_gos_run1
# 第二次：将 --exp_name 改为 full_gos_run2
```

**5.2 Vector 全量（跑2次）**

```bash
# 第一次
uv run python evaluation/alfworld_run.py --model gpt-4o --split dev --use_skill --mode vector --gos_workspace data/gos_workspace/skills_200_v1 --skills_dir data/skillsets/skills_200 --max_workers 1 --max_steps 30 --exp_name full_vector_run1
# 第二次：将 --exp_name 改为 full_vector_run2
```

**5.3 All Full 全量（跑2次）**

```bash
# 第一次
uv run python evaluation/alfworld_run.py --model gpt-4o --split dev --use_skill --mode all_full --skills_dir data/skillsets/skills_200 --max_workers 1 --max_steps 30 --exp_name full_allfull_run1
# 第二次：将 --exp_name 改为 full_allfull_run2
```

### 6. 结果检验与对比指标

全部跑完后，每个目录应有约 140 个 `idx_*.json` 文件。

```bash
# 检查数量示例
find results/alfworld/gpt-4o/dev_full_gos_run1_mode_gos -name "idx_*.json" | wc -l
```

**最终提取核心指标对比：** `平均 reward / 成功率`  `平均 steps`  `平均 token_usage.total_tokens`  `平均 agent_runtime_seconds`