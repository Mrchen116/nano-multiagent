# Worktree Runtime Isolation

> 本文负责 worktree 内真实 IM/Gateway/Vite 联调时的端口、配置、进程和绑定隔离。主仓正常启动与
> 产品排障见 [`../operator-runbook.md`](../operator-runbook.md)。

## 硬规则

在 worktree 内启动任何监听端口的服务，都必须分配空闲端口，并在退出前停止自己启动的进程。
主仓默认端口（8011 / 8000 / 5173）保留给用户手起的主实例；Gateway 必须使用 worktree 内的
config 副本，不能写回 `~/.nano-assistant/config.yaml`。

## 推荐：一键起停

```bash
./scripts/e2e-up.sh
source .e2e-ports.env
# 使用 $IM_URL / $NODE_ID 做验证
./scripts/e2e-down.sh
```

`e2e-up.sh` 负责空闲端口、随机 JWT secret、config/workspace 隔离、测试身份注册、PID 管理和
auto-bind。它默认从 `~/.nano-assistant/config.yaml` 复制 LLM 配置，也可以显式传：

```bash
./scripts/e2e-up.sh --main-config /path/to/config.yaml
./scripts/e2e-up.sh --wt /absolute/worktree/or/temp/path
```

源 config 必须包含可解析的 `llm:` 段。最小示例：

```yaml
node:
  node_id: demo-node
  user_id: <your-user-id>
agents:
  - agent_id: default-agent
    workspace_root: ~/nano-assistant/workspace/default-agent
channels:
  - name: web_relay
    enabled: true
im_service:
  url: http://127.0.0.1:8011
  username: nano
  password: nano1234
llm:
  default_model: kimiCoding:K2.6
  providers:
    - name: anthropic
      base_url: http://127.0.0.1:4000
      models:
        - name: kimiCoding:K2.6
          extra_request_body:
            thinking:
              type: adaptive
        - name: volcanoArk:doubao-seed-2-0-code-preview-260215
          extra_request_body:
            thinking:
              type: adaptive
    - name: openai_compat
      base_url: http://127.0.0.1:4000
      models:
        - name: codex_oauth:gpt-5.5
```

`username` + `password` 让 Gateway 启动时自动登录，断线或 IM 重启后自动恢复 token。主 config 中
`llm:` 缺失时 Gateway 会拒绝启动，`e2e-up.sh` 也会在起 Gateway 前直接报错。

脚本生成的 `.gateway-config.yaml`、`.gateway-workspace/`、`.e2e-ports.env`、`.e2e-jwt-secret`、
`.im.pid`、`.gateway.pid` 和对应日志都只属于本次本地运行，不提交。

## 端口分配与服务参数

手工联调时先分配互不重复的空闲端口：

```bash
read IM_PORT VITE_PORT < <(scripts/free-ports.sh 2)
```

| 服务 | 指定端口/URL | 关键隔离项 |
|---|---|---|
| IM (`uvicorn`) | `--port <N>` | `IM_JWT_SECRET=<本次随机串>`；`IM_DB_PATH` 默认是 cwd-relative 的 `data/im_service.sqlite3` |
| Gateway | `--im-service-url http://127.0.0.1:<IM_PORT>` | `--config <worktree>/.gateway-config.yaml`、`--foreground`、`--auto-bind` |
| Vite | `npm run dev -- --port <N> --strictPort` | 不使用主实例的 dev port |

内核是进程内库，不单独监听端口。

## 两种进程管理范式

### 裸服务：IM / Vite

裸服务可以由外部 PID 文件管理：

```bash
PYTHONPATH=src .venv/bin/python -m uvicorn IM.app:app \
  --host 127.0.0.1 --port "$IM_PORT" \
  > .im.log 2>&1 &
echo $! > .im.pid
```

### Gateway wrapper

`python -m personal_assistant.main` 是 Gateway 生命周期 wrapper，不是 ASGI app。主仓默认后台模式由
config 同目录的 `.gateway-state.json` 管理；worktree 联调应改用前台模式，让外部 PID 文件掌握生死：

```bash
PYTHONPATH=src .venv/bin/python -m personal_assistant.main \
  --config "$WT_CFG" \
  --im-service-url "http://127.0.0.1:$IM_PORT" \
  --foreground \
  --auto-bind \
  > .gateway.log 2>&1 &
echo $! > .gateway.pid
```

不要用裸 ASGI 的假设管理 Gateway 后台启动器。主仓非 worktree 实例继续使用：

```bash
PYTHONPATH=src .venv/bin/python -m personal_assistant.main
PYTHONPATH=src .venv/bin/python -m personal_assistant.main stop
PYTHONPATH=src .venv/bin/python -m personal_assistant.main restart
```

## 手工停止 helper

不能在发送 SIGTERM 后立刻删 PID 文件；否则未退出的进程会失去追踪。手工流程统一使用：

```bash
stop_pidfile() {
  local pidfile=$1 pid
  [[ -f "$pidfile" ]] || return 0
  pid=$(cat "$pidfile")
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    for _ in {1..20}; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.1
    done
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$pidfile"
}
```

退出或 unit 完成时：

```bash
for f in .im.pid .gateway.pid .vite.pid; do
  stop_pidfile "$f"
done
```

这只适用于以 `--foreground` 启动并由外部 PID 文件管理的 Gateway。后台启动器必须使用对应 config：

```bash
PYTHONPATH=src .venv/bin/python -m personal_assistant.main \
  --config "$WT_CFG" stop
```

## 手工派生隔离 config

Gateway config 路径没有 env override，必须通过 `--config` 显式指定。自动脚本不可用时，从主
config 派生 worktree 本地副本。`WT_ROOT` 必须使用派发包给出的绝对 `worktree_dir`，不能假定
shell 的 `$PWD` 已切到 worktree：

```bash
WT_ROOT=<absolute-worktree-dir>
MAIN_CFG=~/.nano-assistant/config.yaml
WT_CFG="$WT_ROOT/.gateway-config.yaml"

cp "$MAIN_CFG" "$WT_CFG"
yq -i "
  .node.node_id = \"wt-$(basename "$WT_ROOT")\" |
  .node.workspace_base = \"$WT_ROOT/.gateway-workspace\" |
  .im_service.url = \"http://127.0.0.1:$IM_PORT\" |
  .agents[].workspace_root = \"$WT_ROOT/.gateway-workspace/\" + .agents[].agent_id
" "$WT_CFG"

python3 -c "import yaml,os; cfg=yaml.safe_load(open('$WT_CFG')); [os.makedirs(a['workspace_root'], exist_ok=True) for a in cfg['agents']]"
```

必须隔离：

- `node_id`：避免与主实例在 IM 中碰撞；
- `node.workspace_base`：让动态创建的 agent 也落在 worktree；
- `im_service.url`：只连接本次 ephemeral IM；
- `agents[].workspace_root`：预置 agent 的工作区不写入主目录。

## IM Node auto-bind

新 Gateway 首次连接新 IM 时，默认要求用户打开 URL 确认 owner binding。自动化场景必须传
`--auto-bind`，或设置：

```bash
NANO_MULTIAGENT_AUTO_BIND=1
```

否则流程会停在交互式绑定页。`scripts/e2e-up.sh` 已包含该参数。

测试 LLM 上游故障路径时，优先复用 [`../../scripts/fixtures/README.md`](../../scripts/fixtures/README.md)
中的 HTTP fixtures。
