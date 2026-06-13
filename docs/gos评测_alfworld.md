# 一、代码主线

GoS 的 ALFWorld 运行主线是：

```text
evaluation/alfworld_run.py
        │
        ├── 读取 evaluation/alfworld/base_config.yaml
        │
        ├── 初始化 ALFWorld 文本环境 AlfredTWEnv
        │
        ├── 根据参数创建 SkillModule
        │       │
        │       └── evaluation/skill.py
        │               │
        │               └── gos.SkillGraphRAG
        │                       │
        │                       ├── gos/core/engine.py
        │                       └── gos/core/retrieval.py
        │
        ├── LLM 输出 Action 或 SkillRequest
        │
        ├── env.step(action)
        │
        └── 保存 results/alfworld/.../idx_*.json
```

---

# 二、ALFWorld 的数据划分


| 数据目录           | 在官方环境中的含义                                                           |
| -------------- | ------------------------------------------------------------------- |
| `train`        | 训练数据，训练 Agent，让它学会行动策略                                              |
| `valid_seen`   | in-distribution validation，检查 Agent 在训练时见过类型/场景附近的表现                |
| `valid_unseen` | out-of-distribution validation，即面向未见环境场景的验证任务，检查 Agent 是否能泛化到未见过的环境 |


数量是：`train` 3553 个、`valid_seen` 140 个、`valid_unseen` 134 个。

---

# 三、GoS 的评测使用了 train、valid_seen、valid_train、valid_unseen 中的哪些部分？

```text
evaluation/alfworld_run.py
evaluation/alfworld/base_config.yaml
```

在 `evaluation/alfworld_run.py` 中

```python
split = "eval_in_distribution" if args.split == 'dev' else "eval_out_of_distribution"
```

在 `AlfredTWEnv.collect_game_files()` 中

```python
if self.train_eval == "train":
    data_path = config['dataset']['data_path']
elif self.train_eval == "eval_in_distribution":
    data_path = config['dataset']['eval_id_data_path']
elif self.train_eval == "eval_out_of_distribution":
    data_path = config['dataset']['eval_ood_data_path']
```


| 传入的参数                              | runner 内部使用值               | ALFWorld 读取的数据目录 |
| ---------------------------------- | -------------------------- | ---------------- |
| `--split dev`                      | `eval_in_distribution`     | `valid_seen`     |
| `--split eval_out_of_distribution` | `eval_out_of_distribution` | `valid_unseen`   |


---

# 四、ALFWorld 动作和 GoS 技能

## 1. ALFWorld 中的动作

### 动作

`evaluation/alfworld/prompts/system_prompt.py` 告诉 LLM 应使用的格式：

```text
go to {recep}
take {obj} from {recep}
move {obj} to {recep}
open {recep}
close {recep}
use {obj}
clean {obj} with {recep}
heat {obj} with {recep}
cool {obj} with {recep}
```

### 流程

```text
evaluation/alfworld/base_config.yaml
         └── 指向 eval_id_data_path / eval_ood_data_path

alfworld 包 AlfredTWEnv.collect_game_files()
         └── 遍历目录，收集 solvable 的 game.tw-pddl 路径 → gamefiles[game_idx]

env.reset() 时 textworld PddlEnv 读取 game.tw-pddl：
         ├── pddl_domain  → 允许哪些动作、前提和效果（GotoLocation、PickupObject…）
         ├── grammar      → 英文模板 + 任务句 + Observation 反馈规则
         └── pddl_problem → 本关物体/家具、(:init) 开局、(:goal) 过关条件

reset 后 grammar 生成 #intro# → Agent 看到：
         「房间里有 desk 1, …」+「Your task is to: …」

LLM 输出 Action: take alarmclock 1 from desk 1
         → parse_action → env.step(["take alarmclock 1 from desk 1"])
         → 环境在当前状态下查合法命令列表：
              合法 → 更新 pddl 状态 → grammar 生成 Observation（如 You pick up…）
              非法 → Observation: Nothing happens.
```

## 2. GoS 中的技能

GoS 的 skill 是：

```text
data/skillsets/skills_200/<skill_name>/SKILL.md
```

---

# 五、评测主循环

```text
evaluation/alfworld_run.py
```

---

## 函数调用链

```text
【1】调度多局（主进程）
main → ProcessPoolExecutor.submit(eval_single_game, game_idx=0, ...)

【2】单局准备（子进程，只做一次）
eval_single_game
  → env.reset 定位到第 game_idx 局，得到初始 ob
  → SkillModule(...) 加载预建 GoS 图
  → alfworld_run_single
        → messages += 规则 / 协议 / ob / 开局检索 guidance
        → retrieve_relevant_skills(ob)   # 只检索，不 step

【3】单局内重复（while，最多 max_steps 次）
run_standard_procedure_with_skill_module
  → llm(messages)                       # 模型说话
  → 若是 SkillRequest → 塞技能文字，continue（不 step）
  → 若是 Action → env.step → Observation 写回 messages
  → 若 Observation 像失败 → 可能再注入 runtime 技能 hint
```

---

# 六、GoS 具体如何调用技能

```text
evaluation/skill.py
gos/core/engine.py
gos/core/retrieval.py
```

```
预建技能图 → 任务运行时多次查询现有技能图（不建图、不插入节点）。
```

## 1. 第一次检索

在 alfworld_run_single（evaluation/alfworld_run.py）里，进循环前：

```python
Skill_Module.retrieve_relevant_skills(ob)
retrieval_guidance = Skill_Module.get_retrieval_guidance()
messages.append({"role": "user", "content": retrieval_guidance})  # 有结果才 append
```

**retrieve_relevant_skills(task, top_k=15)** — evaluation/skill.py

1. _build_targeted_retrieval_query(task) → ALFWorld 任务转成结构化 query（object=mug、task_type=heat_and_place 等）。
2. gos 模式：self.rag.async_retrieve(retrieval_query, top_n=effective_top_k)；ALFWorld 上 effective_top_k 最多 4。
3. 把检索结论记在 SkillModule 的几个变量里（写进 idx_*.json）：
  - last_retrieved_skill_names：搜到了哪些技能，例如 ["simulation-metrics", "planning-with-files", "object_counter"]
  - last_retrieval_status：SKILL_HIT（至少命中 1 个）或 NO_SKILL_HIT（没有返回技能）
  - 另有 last_retrieval_query（发给 GoS 的 query）、last_retrieval_summary（GoS 返回的长摘要）

**get_retrieval_guidance()** — evaluation/skill.py

- 仅 gos/vector 且 SKILL_HIT 时返回非空字符串。
- 内容：前 3 个技能名 + SKILL.md 里的 description 摘要 + 若干 ALFWorld 动作提示；不是完整技能正文。

**async_retrieve(query, top_n=...)** — gos/core/engine.py

- 读预建 workspace 的节点/边 → 语义种子 → PageRank（gos/core/retrieval.py）→ 返回 top-N 技能。

---

## 2. 执行过程中再次检索

在 run_standard_procedure_with_skill_module（evaluation/alfworld_run.py）的 while 循环内。

### 2.1 自动触发

```python
runtime_hint = skill_module.maybe_get_runtime_skill_hint(task_text, messages, observation, current_steps)
if runtime_hint:
    messages.append({"role": "user", "content": runtime_hint})
```

**maybe_get_runtime_skill_hint(...)** — evaluation/skill.py

1. _runtime_trigger_reason(observation, current_step)：观测含 nothing happens、you can't、cannot、not found、don't see 等；且距上次注入 ≥3 步；且本局自动注入 <2 次。不满足则返回空字符串，不塞消息。
2. _build_runtime_retrieval_query：结构化任务 query + recent_actions=最近 Action + runtime_observation=当前观测前 400 字。
3. gos：async_retrieve(dynamic_query, top_n=2) → _format_runtime_skill_hint 拼成以 Additional runtime skill support was injected because: ... 开头的第二条 user 消息（可含 SKILL 片段）。

### 2.2 Agent 主动请求

```python
if _maybe_handle_skill_request(messages, response, skill_module, task_text, current_steps):
    continue  # 本步不 env.step
```

**_maybe_handle_skill_request** — alfworld_run.py  
**handle_agent_skill_request** — evaluation/skill.py

1. _parse_skill_request(response)：识别 SkillRequest: GOS_RETRIEVE ... 或 READ_SKILL ...。
2. GOS_RETRIEVE：async_retrieve(query, top_n=2) → _format_retrieval_shortlist 返回短名单（技能名 + description），不是全文。
3. READ_SKILL：_get_skill_contents 从 skills_dir 读该技能目录文件，截断后返回。

##  idx_3.json

look_at_obj_in_light：找到 CD、拿到手里、到台灯处 use desklamp 开灯。

**怎么数 step**

在 **messages** 里找对应位置：**只数 role 为 assistant 的条目**。

**第 0 步（进循环前）** 
— alfworld_run_single 拼好 messages：system 规则、SkillRequest 说明、初始观测（任务 examine the cd with the desklamp）、开局 GoS 检索 guidance（react-best-practices 等）。不计入 current_steps。

| 循环 step | Agent 输出 | 观测 / 环境反馈 | 备注 |
| --- | --- | --- | --- |
| 1 | Action: go to desk 1 | 到达 desk 1，见 desklamp 1、pencil 1 | |
| 2 | Action: open drawer 1 | Nothing happens | runtime 注入（step=2）：react-best-practices、dc-power-flow |
| 3 | Action: open drawer 2 | Nothing happens | |
| 4 | Action: go to shelf 1 | shelf 1 上什么都没有 | |
| 5 | Action: go to shelf 2 | shelf 2 上什么都没有 | |
| 6 | Action: go to shelf 3 | shelf 3 上有 desklamp 1 | |
| 7 | Action: go to shelf 4 | shelf 4 上有 alarmclock 1、2 | |
| 8 | Action: go to shelf 5 | shelf 5 上什么都没有 | |
| 9 | Action: go to shelf 6 | shelf 6 上什么都没有 | |
| 10 | Action: go to drawer 3 | 到达 drawer 3，上面什么都没有 | |
| 11 | Action: open drawer 3 | Nothing happens | runtime 注入（step=11）：react-best-practices、dc-power-flow |
| 12 | SkillRequest: GOS_RETRIEVE CD location drawer open | 短名单：nanogpt-training、jax-skills | 无 env.step；agent_request:gos_retrieve |
| 13 | Action: go to drawer 4 | drawer 4 关着 | Agent 认为检索结果无关，继续探索 |
| 14 | Action: open drawer 4 | 打开 drawer 4，里面有 pen 1 | |
| 15 | Action: go to drawer 5 | 到达 drawer 5 | |
| 16 | Action: open drawer 5 | Nothing happens | |
| 17 | Action: go to drawer 6 | drawer 6 关着 | |
| 18 | Action: open drawer 6 | 打开 drawer 6，里面有 creditcard 2 | |
| 19 | Action: go to desk 2 | desk 2 上有 bowl 1、cd 3、mug 1 | |
| 20 | Action: take cd 3 from desk 2 | 拿起 cd 3 | |
| 21 | Action: go to desk 1 | 到达 desk 1，见 desklamp 1 | |
| 22 | Action: use desklamp 1 | 打开 desklamp 1 | reward=1，过关 |
