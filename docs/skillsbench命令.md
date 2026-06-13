# 使用本地 Clash 为服务器 Docker 容器提供代理并运行 Aider 评估

## 1. 在本地电脑确认 Clash 代理可用

本地电脑使用 Clash Verge / Mihomo，代理端口为 `7897`。在**本地电脑终端**执行：

```bash
curl -I --max-time 30 -x http://127.0.0.1:7897 https://github.com
```

如果返回类似：

```text
HTTP/1.1 200 Connection established
HTTP/2 200
```

说明本地代理可以正常访问 GitHub。

---

## 2. 在本地电脑建立 SSH 反向转发

在**本地电脑终端**执行：

```bash
ssh -NT \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=60 \
  -o ServerAliveCountMax=3 \
  -R 7892:127.0.0.1:7897 \
  linfy@192.168.1.85
```

该命令建立以下网络路径：

```text
服务器 127.0.0.1:7892
  → SSH 隧道
本地电脑 127.0.0.1:7897
  → 本地 Clash
  → 外网
```

注意：

* 这个本地终端窗口需要始终保持运行；
* 如果关闭窗口，服务器将无法继续使用本地代理；
* `ExitOnForwardFailure=yes` 可以避免转发创建失败但终端仍保持连接。

---

## 3. 在服务器确认 SSH 转发成功

登录服务器，在**服务器终端**执行：

```bash
curl -I --max-time 30 -x http://127.0.0.1:7892 https://github.com
curl -I --max-time 30 -x http://127.0.0.1:7892 https://aider.chat/install.sh
```

如果两条命令都能返回 HTTP 响应，说明：

```text
服务器 127.0.0.1:7892 → 本地 Clash 7897
```

链路已经正常。

---

## 4. 获取 Docker 容器访问宿主机的地址

Docker 容器不能直接访问服务器宿主机的 `127.0.0.1:7892`，因此需要额外开放一个供容器访问的代理入口。

先在服务器执行：

```bash
DOCKER_GW=$(docker network inspect bridge --format '{{(index .IPAM.Config 0).Gateway}}')
echo "$DOCKER_GW"
```

通常会输出：

```text
172.17.0.1
```

这个地址就是 Docker 容器访问服务器宿主机的入口地址。

---

## 5. 在服务器启动 Docker 可访问的转发端口

在服务器上创建一个 Python 转发脚本，将：

```text
Docker 容器可访问的 宿主机地址:7891
```

转发到：

```text
服务器 127.0.0.1:7892
```

先停止可能残留的旧转发进程：

```bash
pkill -f '/tmp/tcp_forward_7891.py' 2>/dev/null || true
```

然后创建脚本：

```bash
cat > /tmp/tcp_forward_7891.py <<'PY'
import os
import socket
import threading

LISTEN_HOST = os.environ.get("DOCKER_GW", "172.17.0.1")
LISTEN = (LISTEN_HOST, 7891)
TARGET = ("127.0.0.1", 7892)


def relay(source, target):
    try:
        while True:
            data = source.recv(65536)
            if not data:
                break
            target.sendall(data)
    finally:
        for connection in (source, target):
            try:
                connection.close()
            except Exception:
                pass


def handle(client):
    try:
        target = socket.create_connection(TARGET)
    except Exception as exc:
        print(f"connect target failed: {exc}", flush=True)
        client.close()
        return

    threading.Thread(target=relay, args=(client, target), daemon=True).start()
    relay(target, client)


server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(LISTEN)
server.listen(100)

print(f"forwarding {LISTEN} -> {TARGET}", flush=True)

while True:
    client, _ = server.accept()
    threading.Thread(target=handle, args=(client,), daemon=True).start()
PY
```

启动转发服务：

```bash
export DOCKER_GW
nohup python3 /tmp/tcp_forward_7891.py > /tmp/tcp_forward_7891.log 2>&1 &
sleep 1
```

检查是否启动成功：

```bash
ss -lntp | grep 7891
cat /tmp/tcp_forward_7891.log
```

正常应看到类似：

```text
172.17.0.1:7891
forwarding ('172.17.0.1', 7891) -> ('127.0.0.1', 7892)
```

这里必须确认目标端口是：

```python
TARGET = ("127.0.0.1", 7892)
```

不要再指向旧的 `7890`。

---

## 6. 在服务器测试 Docker 将使用的代理入口

在服务器执行：

```bash
curl -I --max-time 30 -x "http://${DOCKER_GW}:7891" https://github.com
curl -I --max-time 30 -x "http://${DOCKER_GW}:7891" https://aider.chat/install.sh
```

如果两条命令都返回正常 HTTP 响应，说明完整代理路径已经正常：

```text
Docker 容器
  → ${DOCKER_GW}:7891
  → 服务器 127.0.0.1:7892
  → SSH 隧道
  → 本地 Clash 127.0.0.1:7897
  → 外网
```

只有这一步通过后，再运行 Harbor 评估。

---

## 7. 配置并加载 GoS 环境变量

在服务器的 `~/graph-of-skills/.env` 中配置智增增的 OpenAI-compatible 接口：

```bash
# ── GoS core settings ────────────────────────────────────────────────────────
GOS_WORKING_DIR=./gos_workspace
GOS_PREBUILT_WORKING_DIR=
GOS_LLM_MODEL=openai/gpt-4o-mini

# ── OpenAI-compatible through 智增增 ─────────────────────────────────────────
OPENAI_API_KEY=你的智增增API_KEY
OPENAI_BASE_URL=https://api.zhizengzeng.com/v1

GOS_EMBEDDING_MODEL=openai/text-embedding-3-large
GOS_EMBEDDING_DIM=3072
```

进入评估目录并加载环境变量：

```bash
cd ~/graph-of-skills/evaluation/skillsbench

set -a
source ../../.env
set +a
```

检查变量是否已加载：

```bash
test -n "$OPENAI_API_KEY" && echo "OPENAI_API_KEY loaded"
echo "$OPENAI_BASE_URL"
```

正常应看到：

```text
OPENAI_API_KEY loaded
https://api.zhizengzeng.com/v1
```

---

## 8. 运行 Aider 评估

使用 Aider 作为 coding agent 运行 GoS 条件下的 `dialogue-parser` 任务：

```bash
DOCKER_GW=$(docker network inspect bridge --format '{{(index .IPAM.Config 0).Gateway}}')

harbor run --agent aider \
  --model openai/gpt-4o-mini \
  --force-build \
  -p generated_verify/tasks_graph_skills/dialogue-parser \
  -o jobs/verify-aider-fixed \
  --ae OPENAI_API_KEY="$OPENAI_API_KEY" \
  --ae OPENAI_BASE_URL="$OPENAI_BASE_URL" \
  --ae https_proxy="http://${DOCKER_GW}:7891" \
  --ae HTTPS_PROXY="http://${DOCKER_GW}:7891" \
  --ae no_proxy="api.zhizengzeng.com,localhost,127.0.0.1" \
  --ae NO_PROXY="api.zhizengzeng.com,localhost,127.0.0.1" \
  -n 1
```

参数说明：

| 参数                           | 作用                                            |
| ---------------------------- | --------------------------------------------- |
| `--agent aider`              | 使用 Aider 作为代码智能体                              |
| `--model openai/gpt-4o-mini` | 通过智增增 OpenAI-compatible 接口调用模型                |
| `https_proxy / HTTPS_PROXY`  | 让容器访问 GitHub、Aider 安装地址等 HTTPS 下载资源时走本地 Clash |
| `no_proxy / NO_PROXY`        | 让智增增 API 直接由服务器访问，不绕过本地代理                     |
| `-n 1`                       | 只运行一个 trial，适合最小验证                            |

注意：**不要传递以下两项：**

```bash
--ae http_proxy="http://${DOCKER_GW}:7891"
--ae HTTP_PROXY="http://${DOCKER_GW}:7891"
```

原因是 `apt-get update` 会访问 Debian 的 HTTP 软件源；此前把 HTTP 请求也交给代理后，出现了 `502 Bad Gateway`，导致 Aider 安装失败。

---

## 9. 判断评估链路是否跑通

Harbor 运行结束后，如果看到：

```text
Trials: 1
Exceptions: 0
```

说明以下链路均已成功：

```text
Docker 环境启动
Aider 安装
容器外网访问
智增增模型调用
任务执行
Verifier 运行
结果文件写出
```

结果含义如下：

| 输出              | 含义                         |
| --------------- | -------------------------- |
| `Trials: 1`     | 一个任务实际完成执行                 |
| `Exceptions: 0` | 运行流程没有系统异常                 |
| `Reward: 0.0`   | 任务未通过 verifier，但环境与调用链路已跑通 |
| `Reward: 1.0`   | 任务通过 verifier              |

查看结果：

```bash
cat jobs/verify-aider-fixed/*/result.json | python -m json.tool
```

或者：

```bash
harbor view jobs/verify-aider-fixed
```

---

## 10. 常见问题

### 10.1 服务器无法通过 `127.0.0.1:7892` 访问 GitHub

先在本地电脑确认 Clash 仍然可用：

```bash
curl -I -x http://127.0.0.1:7897 https://github.com
```

再确认本地用于 SSH 转发的终端窗口仍保持运行：

```bash
ssh -NT \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=60 \
  -o ServerAliveCountMax=3 \
  -R 7892:127.0.0.1:7897 \
  linfy@192.168.1.85
```

### 10.2 `7892` 正常，但 `${DOCKER_GW}:7891` 超时

说明服务器上的 Python 转发不正确或仍然指向旧端口。检查：

```bash
grep 'TARGET' /tmp/tcp_forward_7891.py
```

必须是：

```python
TARGET = ("127.0.0.1", 7892)
```

然后重启转发：

```bash
pkill -f '/tmp/tcp_forward_7891.py' 2>/dev/null || true

export DOCKER_GW
nohup python3 /tmp/tcp_forward_7891.py > /tmp/tcp_forward_7891.log 2>&1 &
```

### 10.3 `apt-get update` 出现 `502 Bad Gateway`

说明错误地把 HTTP 请求也配置为走代理。Harbor 命令中删除：

```bash
--ae http_proxy=...
--ae HTTP_PROXY=...
```

只保留：

```bash
--ae https_proxy="http://${DOCKER_GW}:7891"
--ae HTTPS_PROXY="http://${DOCKER_GW}:7891"
```

### 10.4 Aider 安装阶段出现 `SSL connection timeout`

先分别测试两段链路：

```bash
curl -I --max-time 30 -x http://127.0.0.1:7892 https://aider.chat/install.sh
curl -I --max-time 30 -x "http://${DOCKER_GW}:7891" https://aider.chat/install.sh
```

* 第一条失败：本地 Clash 或 SSH 转发存在问题；
* 第一条成功、第二条失败：服务器 Python 转发存在问题；
* 两条都成功：可以重新运行 Harbor。

### 10.5 `Reward: 0.0`

只要结果为：

```text
Trials: 1
Exceptions: 0
```

就说明流程已经打通。`Reward: 0.0` 表示 Aider 没有正确完成当前任务，需要进一步分析任务轨迹或更换更强模型，而不是继续修网络环境。
