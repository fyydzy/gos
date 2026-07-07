# -*- coding: utf-8 -*-
# =============================================================================
# 本文件：在 ALFWorld 文本游戏里，用 LLM 当 Agent 跑评测；可选接入 GoS 技能模块。
# 建议阅读顺序：main → eval_single_game → alfworld_run_single → run_standard_procedure*
# =============================================================================

import os  # 读环境变量、建目录、列文件
from openai import OpenAI  # 调用 OpenAI 兼容的聊天 API
import re  # 正则，从 LLM 回复里抠出 "Action: xxx"
import inspect  # 当前未使用，保留作调试
import time  # 计时：单局跑了多少秒
from retry import retry  # 装饰器：LLM 失败时自动重试
import concurrent.futures  # 多进程并行跑多局游戏
from concurrent.futures import ThreadPoolExecutor, as_completed  # 当前未使用（历史遗留）
from tqdm import tqdm  # 命令行进度条
import json  # 把每局结果存成 idx_*.json
import argparse  # 解析命令行参数 --model --split 等
from datetime import datetime, timezone  # 记录每局开始/结束时间（UTC）
import yaml  # 读 evaluation/alfworld/base_config.yaml
import alfworld  # 确保 alfworld 包被加载
import alfworld.agents.environment  # 环境相关子模块
from alfworld.agents.environment import get_environment  # 根据配置创建 ALFWorld 环境类
import sys  # 改 Python 模块搜索路径
from pathlib import Path  # 处理路径，算项目根目录

# 本脚本所在：.../evaluation/alfworld_run.py → parent=evaluation，parent.parent=项目根
project_root = str(Path(__file__).resolve().parent.parent)
evaluation_dir = str(Path(__file__).resolve().parent)
# 把项目根插到 sys.path 最前，才能写 from evaluation.xxx import ...
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if evaluation_dir not in sys.path:
    sys.path.insert(0, evaluation_dir)

# ALFWorld Agent 的系统提示词（规定输出格式 Action: / SkillRequest 等）
from evaluation.alfworld.prompts.system_prompt import alfworld_system_prompt
# GoS 技能封装：检索、注入 guidance、处理 SkillRequest
from evaluation.skill import SkillModule
# 统计本局 LLM 用了多少 token
from evaluation.token_usage import (
    clear_token_usage_tracker as _clear_token_usage_tracker,  # 清掉当前局的 token 计数器
    get_usage_debug_fields as _get_usage_debug_fields,  # 从 API 响应里取出 token 数字段
    new_token_usage as _new_token_usage,  # 新建空 token 统计 dict
    record_usage as _record_usage,  # 每次 llm() 调用后累加 token
    set_token_usage_tracker as _set_token_usage_tracker,  # 绑定本局要写入结果的 dict
)

# 默认技能 JSON 目录（--skills_dir 可改）
DEFAULT_SKILLS_DIR = "data/skillsets/skills_200"
# 默认 GoS 图索引工作区（--gos_workspace 可改）
DEFAULT_GOS_WORKSPACE = "data/gos_workspace/skills_200_v1"
# LLM 单次请求超时秒数；环境变量没设就用 90
LLM_REQUEST_TIMEOUT_SECS = float(os.environ.get("LLM_REQUEST_TIMEOUT_SECS", "90"))
# LLM_API_TYPE=auto 时，仅这些模型走 Responses API；LLM_API_TYPE=chat 可强制改回原逻辑。
LLM_API_TYPE = os.environ.get("LLM_API_TYPE", "auto").strip().lower()
RESPONSES_API_MODELS = {
    name.strip()
    for name in os.environ.get("LLM_RESPONSES_API_MODELS", "gpt-5.3-codex").split(",")
    if name.strip()
}

# 全局 LLM 客户端；运行前必须 export API_KEY 和 BASE_URL
client = OpenAI(
    api_key=os.environ["API_KEY"],  # 你的 API Key
    base_url=os.environ["BASE_URL"]  # 兼容 OpenAI 的网关地址
)


def _message_stats(messages):
    """数一下 messages 有几条、一共多少字符（打日志用）。"""
    total_chars = 0  # 字符总数
    for message in messages:  # 遍历每条对话
        content = message.get("content", "")  # 取 content 字段，没有就空串
        if isinstance(content, str):  # 只统计字符串
            total_chars += len(content)  # 累加长度
    return len(messages), total_chars  # 返回 (条数, 字符数)


def _last_message_preview(messages, limit=240):
    """LLM 报错时，打印最后一条消息的前 240 字，方便排查。"""
    if not messages:  # 没有消息
        return "<empty>"  # 占位

    content = messages[-1].get("content", "")  # 最后一条的 content
    if not isinstance(content, str):  # 不是字符串（少见）
        return "<non-string content>"

    compact = " ".join(content.split())  # 把换行压成空格，变一行
    if len(compact) > limit:  # 太长就截断
        return compact[:limit] + "..."
    return compact  # 原样返回


def _use_responses_api(model):
    """Keep chat.completions as default; opt into Responses only for known models."""
    if LLM_API_TYPE in {"responses", "response"}:
        return True
    if LLM_API_TYPE in {"chat", "chat_completions"}:
        return False
    return model in RESPONSES_API_MODELS


def _extract_response_text(response, *, uses_responses_api):
    """Extract text from either Chat Completions or Responses API results."""
    if not uses_responses_api:
        return response.choices[0].message.content

    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text

    chunks = []
    for item in getattr(response, "output", []) or []:
        for part in getattr(item, "content", []) or []:
            text = getattr(part, "text", None)
            if text:
                chunks.append(text)
    return "\n".join(chunks) if chunks else None


@retry(tries=5, delay=5, backoff=2, jitter=(1, 3))  # 最多重试 5 次，间隔指数退避
def llm(prompt, model="YOUR_MODEL_NAME"):
    """调一次聊天模型；prompt 可以是字符串或 messages 列表。"""
    if isinstance(prompt, list):  # 已经是多轮对话格式
        messages = prompt
    elif isinstance(prompt, str):  # 单条用户话
        messages = [{"role": "user", "content": prompt}]
    else:  # 类型不对
        raise ValueError(f'prompt must be a list or a string, but got {type(prompt)}')

    message_count, total_chars = _message_stats(messages)  # 统计规模
    uses_responses_api = _use_responses_api(model)
    api_type = "responses" if uses_responses_api else "chat.completions"
    print(  # 打日志：用的模型、消息数、字符数、超时
        f'Calling LLM with model: {model} '
        f'(api={api_type}, messages={message_count}, chars={total_chars}, timeout={LLM_REQUEST_TIMEOUT_SECS}s)'
    )
    
    try:
        if uses_responses_api:
            response = client.responses.create(
                model=model,  # 模型名，来自 --model
                input=messages,  # Responses API 也接受 role/content 对话列表
                timeout=LLM_REQUEST_TIMEOUT_SECS,  # 超时秒数
            )
        else:
            response = client.chat.completions.create(  # 真正发 HTTP 请求
                model=model,  # 模型名，来自 --model
                messages=messages,  # 完整对话历史
                timeout=LLM_REQUEST_TIMEOUT_SECS,  # 超时秒数
            )
    except Exception as exc:  # 网络/限流/超时等
        print(  # 红色打印失败原因 + 最后一条消息预览
            f'{Colors.RED}LLM request failed '
            f'(type={type(exc).__name__}, model={model}, timeout={LLM_REQUEST_TIMEOUT_SECS}s, '
            f'messages={message_count}, chars={total_chars}). '
            f'Last message preview: {_last_message_preview(messages)}. '
            f'Error: {exc}{Colors.RESET}'
        )
        raise  # 交给 @retry 再试

    usage = getattr(response, "usage", None)  # API 返回的 token 用量对象
    _record_usage(usage, bucket="agent")  # 累加到本局 token_usage
    if usage is not None:  # 有 usage 才打印
        usage_fields = _get_usage_debug_fields(usage)  # 转成普通 dict
        usage_parts = [  # 拼日志字符串
            f"prompt={usage_fields.get('prompt_tokens')}",
            f"completion={usage_fields.get('completion_tokens')}",
            f"total={usage_fields.get('total_tokens')}",
        ]
        if "cached_prompt_tokens" in usage_fields:  # 缓存命中（部分 API 有）
            usage_parts.append(f"cached_prompt={usage_fields['cached_prompt_tokens']}")
        if "cache_creation_input_tokens" in usage_fields:
            usage_parts.append(f"cache_create={usage_fields['cache_creation_input_tokens']}")
        if "reasoning_tokens" in usage_fields:  # 推理模型额外 token
            usage_parts.append(f"reasoning={usage_fields['reasoning_tokens']}")
        print(
            f"{Colors.BLUE}LLM usage: {'; '.join(usage_parts)}{Colors.RESET}"
        )

    content = _extract_response_text(response, uses_responses_api=uses_responses_api)  # 模型回复正文
    if content is not None:
        return content  # 正常返回字符串
    return "Output Error"  # 模型没给 content 时的兜底


def process_ob(ob):
    """清洗环境观测：去掉开头的 'You arrive at loc ...' 导航句。"""
    if ob.startswith('You arrive at loc '):  # ALFWorld 常带这句
        ob = ob[ob.find('. ')+2:]  # 从第一个 ". " 后面开始保留
    return ob  # 返回清洗后的观测文本


class Colors:
    """终端彩色输出用的 ANSI 转义码。"""
    RED = '\033[91m'      # 错误、当前局标题
    GREEN = '\033[92m'    # Agent 回复、任务成功
    YELLOW = '\033[93m'   # 环境观测
    BLUE = '\033[94m'     # 技能相关注入
    RESET = '\033[0m'     # 恢复默认颜色


def parse_action(response: str) -> str:
    """从模型回复里找一行 Action: go to ...，返回动作字符串。"""
    pattern = re.compile(r"Action:\s*(.+)", re.IGNORECASE)  # 不区分大小写
    match = pattern.search(response)  # 在全文里搜
    if match:
        return match.group(1).strip().strip('"\'*`')  # 去掉首尾引号、反引号
    return ""  # 没找到 Action 就返回空（env 可能报错）


def build_skill_config(args):
    """把命令行参数转成 SkillModule 构造函数需要的 dict。"""
    gos_workspace = args.gos_workspace  # 用户指定的 GoS 工作区
    if args.mode in {'gos', 'vector'} and not gos_workspace:  # 没写就用默认
        gos_workspace = DEFAULT_GOS_WORKSPACE

    resolved_skills_dir = str(Path(args.skills_dir).expanduser().resolve())  # 绝对路径
    resolved_workspace = str(Path(gos_workspace).expanduser().resolve()) if gos_workspace else None

    # 防止 skills_200 和 skills_999 的工作区配错
    if args.mode in {'gos', 'vector'} and resolved_workspace:
        workspace_name = Path(resolved_workspace).name  # 例如 skills_200_v1
        skills_name = Path(resolved_skills_dir).name  # 例如 skills_200
        if workspace_name.startswith('skills_') and skills_name.startswith('skills_'):
            valid_names = {skills_name, f'{skills_name}_v1'}  # 允许的名字
            if not (workspace_name in valid_names or workspace_name.startswith(f'{skills_name}_v')):
                raise ValueError(
                    f'goss workspace / skills_dir mismatch: workspace={resolved_workspace}, skills_dir={resolved_skills_dir}'
                )

    return {  # SkillModule(**这个 dict)
        "skills_dir": resolved_skills_dir,
        "model": args.model,
        "mode": args.mode,  # gos / vector / all_full / none
        "gos_workspace": resolved_workspace,
        "enable_alfworld_gating": args.enable_alfworld_gating,  # 是否启用 ALFWorld 专用门控
    }


def parse_task_indices(raw_value):
    """把 "0,3,5" 变成 [0,3,5]；空字符串返回 None 表示跑全部。"""
    if not raw_value:
        return None

    parsed = []
    for chunk in raw_value.split(','):  # 按逗号切
        chunk = chunk.strip()  # 去空格
        if not chunk:
            continue  # 跳过空段
        parsed.append(int(chunk))  # 转成整数索引
    return parsed or None  # 全是空则 None


def run_standard_procedure(env, llm, model, process_ob, messages, max_steps):
    """
    最基础的 Agent 循环（不用技能）：
      问 LLM → 解析 Action → env.step → 把观测塞回 messages
    """
    task_done = False   # 本局是否结束
    task_reward = 0     # 是否成功（ALFWorld 里 0/1）
    current_steps = 0   # 已走几步

    while not task_done and current_steps < max_steps:  # 没完成且未超步数
        current_steps += 1  # 步数 +1
        try:
            response = llm(messages, model)  # 把当前对话发给 LLM
            print(f'{Colors.GREEN}Agent response: \n{response}{Colors.RESET}')
        except Exception as e:
            print(f'{Colors.RED}Error in LLM call: {e}{Colors.RESET}')
            break  # LLM 挂了就退出循环

        messages.append({"role": "assistant", "content": response})  # 记入对话史
        action = parse_action(response)  # 从回复抠 Action
        action_list = [action]  # env 要的是列表（batch=1）
        
        observation, task_reward, done, info = env.step(action_list)  # 环境执行动作
        observation, task_reward, task_done = (
            process_ob(observation[0]),  # 清洗观测文本
            info["won"][0],              # 是否赢得任务（0 或 1）
            done[0]                      # 是否 episode 结束
        )
        print(f'{Colors.YELLOW}Observation: \n{observation}{Colors.RESET}')
        messages.append({"role": "user", "content": f"Observation: {observation}"})  # 观测当 user 消息

        if task_done:  # 环境说结束了
            print(f'{Colors.GREEN}Whole Task completed! Reward: {task_reward}{Colors.RESET}')
            break

    return messages, task_done, task_reward, current_steps


def _maybe_handle_skill_request(messages, response, skill_module, task_text, current_steps):
    """
    如果 Agent 写的是 SkillRequest 而不是 Action：
      不 step 环境，只把技能内容塞进 messages，返回 True 让外层 continue。
    """
    if skill_module is None:  # 没开技能
        return False

    skill_reply = skill_module.handle_agent_skill_request(task_text, response, current_steps)
    if not skill_reply:  # 不是 SkillRequest 或处理失败
        return False

    print(f'{Colors.BLUE}Handled agent-requested skill access.{Colors.RESET}')
    messages.append({"role": "user", "content": skill_reply})  # 技能内容伪装成 user 消息
    return True  # 告诉外层：这步别 env.step


def run_standard_procedure_with_skill_module(env, llm, model, process_ob, messages, max_steps, skill_module, task_text):
    """
    带技能的 Agent 循环 = 标准循环 + SkillRequest 处理 + 失败时 runtime hint。
    task_text 用整段初始观测 ob（和检索时一样）。
    """
    task_done = False
    task_reward = 0
    current_steps = 0

    while not task_done and current_steps < max_steps:
        current_steps += 1
        try:
            response = llm(messages, model)
            print(f'{Colors.GREEN}Agent response: \n{response}{Colors.RESET}')
        except Exception as e:
            print(f'{Colors.RED}Error in LLM call: {e}{Colors.RESET}')
            break

        messages.append({"role": "assistant", "content": response})
        # 若是 SkillRequest：注入技能回复后直接进入下一轮 LLM，不 step
        if _maybe_handle_skill_request(messages, response, skill_module, task_text, current_steps):
            continue

        action = parse_action(response)
        action_list = [action]

        observation, task_reward, done, info = env.step(action_list)
        observation, task_reward, task_done = (
            process_ob(observation[0]),
            info["won"][0],
            done[0]
        )
        print(f'{Colors.YELLOW}Observation: \n{observation}{Colors.RESET}')
        messages.append({"role": "user", "content": f"Observation: {observation}"})

        # 例如动作无效时，SkillModule 可能再塞一条提示
        runtime_hint = skill_module.maybe_get_runtime_skill_hint(task_text, messages, observation, current_steps)
        if runtime_hint:
            print(f'{Colors.BLUE}Injected runtime skill hint after observation failure.{Colors.RESET}')
            messages.append({"role": "user", "content": runtime_hint})

        if task_done:
            print(f'{Colors.GREEN}Whole Task completed! Reward: {task_reward}{Colors.RESET}')
            break

    return messages, task_done, task_reward, current_steps


def alfworld_run_single(env, obs=[], names=[], max_steps=30, model=None, Skill_Module=None):
    """
    对一个或多个观测跑完整局（通常 obs 只有 1 条 = 一局）。
    返回 list[dict]，每个 dict 是一局的评测结果。
    """
    results = []  # 收集每局结果
    for task_idx, (ob, name) in enumerate(zip(obs, names)):  # 遍历观测与游戏名
        print(f'{Colors.RED}Processing task {task_idx + 1}/{len(obs)}: {name}{Colors.RESET}')
        # 从 "Your task is to: put ..." 里抽出任务短描述
        query = ob.split('Your task is to: ')[-1].split('\n')[0].strip()
        messages = [{"role": "system", "content": alfworld_system_prompt}]  # 第一条：系统提示

        if Skill_Module is not None:
            # all_full 模式：开局把所有技能元数据塞进对话
            all_full_exposures = Skill_Module.get_all_full_exposure_messages()
            if all_full_exposures:
                print(f'{Colors.BLUE}Injected full skill metadata exposure into initial dialogue ({len(all_full_exposures)} messages).{Colors.RESET}')
                for exposure_message in all_full_exposures:
                    messages.append({"role": "user", "content": exposure_message})
            # 告诉 Agent 可以发 SkillRequest 的说明
            skill_request_message = Skill_Module.get_agent_skill_request_message()
            if skill_request_message:
                print(f'{Colors.BLUE}Injected skill request protocol into initial dialogue.{Colors.RESET}')
                messages.append({"role": "user", "content": skill_request_message})

        messages.append({"role": "user", "content": ob})  # 初始房间观测 + 任务
        
        task_done = False
        task_reward = 0
        steps = 0
        relevant_skill_names = []       # 检索到的技能名列表
        retrieval_status = "NOT_RUN"    # 检索状态码
        retrieval_summary = ""          # 检索摘要
        retrieval_query = ""            # 检索用的 query
        runtime_skill_events = []       # 运行时技能事件日志
        token_usage = _new_token_usage()  # 本局 token 统计
        started_at = datetime.now(timezone.utc).isoformat()  # ISO 时间戳
        agent_start_time = time.perf_counter()  # 高精度计时起点
        finished_at = started_at
        agent_runtime_seconds = 0.0

        _set_token_usage_tracker(token_usage)  # 之后每次 llm() 都会写入 token_usage
        try:
            if Skill_Module is not None:
                Skill_Module.retrieve_relevant_skills(ob)  # 用观测文本做 GoS 检索
                relevant_skill_names = list(Skill_Module.last_retrieved_skill_names)
                retrieval_status = Skill_Module.last_retrieval_status
                retrieval_summary = Skill_Module.last_retrieval_summary
                retrieval_query = Skill_Module.last_retrieval_query

                retrieval_guidance = Skill_Module.get_retrieval_guidance()  # 检索结果转成提示语
                if retrieval_guidance:
                    print(f'{Colors.BLUE}Injected GoS retrieval guidance into dialogue.{Colors.RESET}')
                    messages.append({"role": "user", "content": retrieval_guidance})

                if relevant_skill_names:
                    print(f'{Colors.BLUE}Retrieved relevant skills.{Colors.RESET}')
                    print(f'{Colors.BLUE}Using lightweight retrieval guidance only; no procedure generation.{Colors.RESET}')
                else:
                    print(f"[INFO] No relevant skills found. Falling back.")

            # gos/vector/all_full 走带技能循环；none 或未开技能走普通循环
            if Skill_Module is not None and Skill_Module.mode in {'gos', 'vector', 'all_full'}:
                messages, task_done, task_reward, steps = run_standard_procedure_with_skill_module(
                    env, llm, model, process_ob, messages, max_steps, Skill_Module, ob
                )
            else:
                messages, task_done, task_reward, steps = run_standard_procedure(
                    env, llm, model, process_ob, messages, max_steps
                )

            if Skill_Module is not None:
                runtime_skill_events = Skill_Module.get_runtime_skill_events()
        finally:  # 无论成功失败都记录时间和清 tracker
            finished_at = datetime.now(timezone.utc).isoformat()
            agent_runtime_seconds = round(time.perf_counter() - agent_start_time, 3)
            _clear_token_usage_tracker()
        
        results.append({  # 一局的所有字段，后面会 json.dump
            "query": query,
            "name": name,
            "task_done": task_done,
            "reward": task_reward,
            "steps": steps,
            "messages": messages,
            "relevant_skill_names": relevant_skill_names,
            "retrieval_status": retrieval_status,
            "retrieval_summary": retrieval_summary,
            "retrieval_query": retrieval_query,
            "runtime_skill_events": runtime_skill_events,
            "token_usage": token_usage,
            "started_at": started_at,
            "finished_at": finished_at,
            "agent_runtime_seconds": agent_runtime_seconds,
        })
    return results


def eval_single_game(game_idx, args, config, split, output_path):
    """
    子进程里跑一局：创建环境 → reset 到第 game_idx 局 → alfworld_run_single → 写 JSON。
    """
    env = None  # 先置空，finally 里 close
    try:
        env = get_environment(config["env"]["type"])(config, train_eval=split)  # 例如 AlfredTWEnv
        env = env.init_env(batch_size=1)  # batch=1 表示一次只跑一局
        obs_list = []
        info = {}
        # reset 第 0 次是第 0 局，reset game_idx+1 次才到第 game_idx 局
        for _ in range(game_idx + 1):
            obs_list, info = env.reset()
            
        Skill_Module = None
        if args.use_skill:  # 命令行加了 --use_skill 才建 SkillModule
            Skill_Module = SkillModule(**build_skill_config(args))

        # obs_list[0] 用 \n\n 分段，丢掉第一段（往往是纯导航），拼成任务观测
        ob_str = '\n'.join(obs_list[0].split('\n\n')[1:])
        # 从路径里取游戏标识，例如 pick_heat_then_place/...
        game_name = '/'.join(info['extra.gamefile'][0].split('/')[-3:-1])
        
        batch_results = alfworld_run_single(
            env=env,
            obs=[ob_str],
            names=[game_name],
            max_steps=args.max_steps,
            model=args.model,
            Skill_Module=Skill_Module
        )
        result = batch_results[0]  # 只有一局，取第一个
        save_file = f'{output_path}/idx_{game_idx}.json'
        with open(save_file, 'w') as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
        return result
    except Exception as e:
        print(f"Error in game {game_idx}: {e}")
        return None  # 失败返回 None，主进程不计入成功
    finally:
        if env:
            env.close()  # 释放环境


def main(args):
    """主函数：读配置、算要跑哪些局、多进程并行、进度条。"""
    model_name = args.model
    with open('evaluation/alfworld/base_config.yaml') as reader:
        config = yaml.safe_load(reader)  # ALFWorld 数据路径、环境类型等
    # --split dev → 分布内 valid_seen；其它 → 分布外 valid_unseen
    split = "eval_in_distribution" if args.split == 'dev' else "eval_out_of_distribution"
    output_path = f'results/alfworld/{model_name}/{args.split}_{args.exp_name}_mode_{args.mode}'
    os.makedirs(output_path, exist_ok=True)  # 没有目录就创建

    temp_env = get_environment(config["env"]["type"])(config, train_eval=split)
    temp_env = temp_env.init_env(batch_size=1)
    num_games = len(temp_env.gamefiles)  # 这个 split 一共有多少局
    del temp_env  # 用完删掉，真正评测在子进程里建 env

    tasks_to_run = []      # 待跑的游戏索引列表
    finished_games = 0     # 已完成局数（含断点续跑读到的）
    all_rewards = 0        # 累计 reward，算平均分
    all_steps = 0
    existing_files = set()  # 已经存在结果的 idx
    if os.path.exists(output_path):
        for file in os.listdir(output_path):
            if file.endswith('.json') and file.startswith('idx_'):  # 形如 idx_12.json
                try:
                    idx = int(file.split('_')[1].split('.')[0])  # 解析出 12
                    existing_files.add(idx)
                    with open(f'{output_path}/{file}', 'r') as f:
                        res = json.load(f)
                        all_rewards += res['reward']
                        all_steps += res['steps']
                    finished_games += 1
                except:
                    continue  # 坏文件跳过

    requested_indices = parse_task_indices(args.task_indices)  # 用户指定子集
    candidate_indices = requested_indices if requested_indices is not None else list(range(num_games))
    if args.max_games is not None:  # 只跑前 N 个
        candidate_indices = candidate_indices[: args.max_games]

    for idx in candidate_indices:
        if idx not in existing_files:  # 没跑过的才加入队列
            tasks_to_run.append(idx)

    max_workers = args.max_workers  # 并行进程数
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        # 每个 idx 提交一个 eval_single_game 任务
        future_to_idx = {executor.submit(eval_single_game, idx, args, config, split, output_path): idx for idx in tasks_to_run}
        pbar = tqdm(total=len(tasks_to_run), desc="Evaluating ALFWorld")
        for future in concurrent.futures.as_completed(future_to_idx):  # 谁先完成先处理谁
            idx = future_to_idx[future]
            try:
                result = future.result()  # 取子进程返回值
                if result:  # 成功才有 dict
                    finished_games += 1
                    all_rewards += result['reward']
                    all_steps += result['steps']
                    pbar.set_postfix({'Avg R': f'{all_rewards/finished_games:.2f}'})  # 平均成功率
            except Exception as exc:
                print(f'\nGame {idx} error: {exc}')
            pbar.update(1)
        pbar.close()


if __name__ == '__main__':  # 直接 python evaluation/alfworld_run.py 时执行
    parser = argparse.ArgumentParser()  # 定义命令行参数
    parser.add_argument('--model', type=str, default='gpt-4o')  # LLM 模型名
    parser.add_argument('--split', type=str, default='dev')  # dev=ID，其它=OOD
    parser.add_argument('--max_workers', type=int, default=5)  # 并行进程数
    parser.add_argument('--max_steps', type=int, default=30)  # 每局最多几步
    parser.add_argument('--exp_name', type=str, default='')  # 实验名，进结果目录名
    parser.add_argument('--use_skill', action='store_true')  # 加上这个开关才用 GoS
    parser.add_argument('--mode', type=str, default='gos', choices=['all_full', 'gos', 'vector', 'none'])
    parser.add_argument('--gos_workspace', type=str, default=None)  # GoS 索引目录
    parser.add_argument('--skills_dir', type=str, default=DEFAULT_SKILLS_DIR)
    parser.add_argument('--max_games', type=int, default=None)  # 最多跑几局
    parser.add_argument('--task_indices', type=str, default=None)  # 只跑指定 idx
    parser.add_argument('--enable_alfworld_gating', action='store_true')  # ALFWorld 动作门控
    args = parser.parse_args()  # 解析 sys.argv
    main(args)  # 进入主流程
