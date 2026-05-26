# AGENTS.md

## Project overview

整体架构：./SPEC.md

开发规范：COMMENTING_GUIDE.md

测试规范：docs/TESTING_GUIDE.md

LLM交互日志：/Users/czj/Repos/LLM_PROXY/logs/<session_id>/

参考项目代码：
- Claude Code(CC) ~/Repos/opensource-hub/claude-code —— Anthropic 官方 Claude Code CLI （TypeScript/Bun），最优秀的商业coding agent harness。本项目agent core / coding agent主要参考实现。
- openclaw ~/Repos/opensource-hub/openclaw —— 开源个人 agent 助手，以 channel 形式接入各类 IM，本项目个人助手产品的整体架构主要参考它。他首创在agent个人助手设计中heartbeat、cron 自动化，agent identity、soul设定等特性。
- hermes agent ~/Repos/opensource-hub/self-evolution/hermes-agent —— 自进化个人 agent 助手，继openclaw 后的下一代技术演进，带闭环学习循环、自创建/自改进 skills、子 agent 并行、多 IM/多终端后端，本项目个人助手的自进化体系参考它。
- opencode ~/Repos/opensource-hub/opencode —— 多 provider / 多客户端架构的开源 AI Coding Agent，本项目 hook 事件设计、单一 agent 内核同时支撑两个产品的架构参考它。
- codex-cli ~/Repos/opensource-hub/codex —— OpenAI 官方coding agent harness（Rust + TypeScript），可参考其agent core / coding agent 设计，与CC对照。

## 常用命令

### 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 运行测试

```bash
# 全部测试
pytest

# 单个测试文件
pytest -xvs tests/unit/test_xxx.py

# 跳过 e2e（不需要本地运行时依赖）
pytest -m "not e2e"
```

### 启动 IM 服务

```bash
PYTHONPATH=src python -m uvicorn IM.app:app --host 0.0.0.0 --port 8011
```

Web IM 入口：`http://127.0.0.1:8011/`

### 启动 Gateway（个人助手）

Gateway 默认读取 `~/.nano-assistant/config.yaml`。该文件是**持久化配置**：
- Gateway 启动时会将 config 中的 agents 同步到 IM
- 在 IM 前端新建 agent 时，Gateway 会自动把新 agent 写回该文件
- 因此服务重启后所有 agent 配置不会丢失

```bash
# 启动（后台，使用默认持久化配置）
PYTHONPATH=src python -m personal_assistant.main

# 或显式指定配置路径
PYTHONPATH=src python -m personal_assistant.main --config ~/.nano-assistant/config.yaml

# 显式指定远端 IM
PYTHONPATH=src python -m personal_assistant.main --im-service-url http://<im-host>:8011

# 停止 / 重启
PYTHONPATH=src python -m personal_assistant.main stop
PYTHONPATH=src python -m personal_assistant.main restart
```

### 启动 Coding CLI

```bash
# Managed 模式（自动起本地 API）
PYTHONPATH=src python3 -m coding_cli.main \
  --mode managed \
  --base-url http://127.0.0.1:8000

# 或指定模型
PYTHONPATH=src python3 -m coding_cli.main --model volcanoArk:doubao-seed-2-0-code-preview-260215
```

### 前端开发（IM）

```bash
cd src/IM/frontend
npm install
npm run dev        # Vite dev server
npm run build      # 生产构建（tsc + vite build）
npm run test       # vitest
```

## 测试账号

```yaml
username:   nano
password:   nano1234
display_name: Test User
im_url:     http://127.0.0.1:8011
```

注册：`curl -X POST $im_url/im/v1/auth/register -H "Content-Type: application/json" -d '{"username":"nano","password":"nano1234","display_name":"Test User"}'`

IM 启动必须带固定 secret，否则 token 随重启失效：
`IM_JWT_SECRET="demo-jwt-secret-for-feat340-testing" PYTHONPATH=src python -m uvicorn IM.app:app --host 0.0.0.0 --port 8011`

**Gateway config 路径**：`~/.nano-assistant/config.yaml`（持久化，不要在 `/tmp` 下创建，否则系统重启后 agent 配置会丢失）

最小可用配置示例：

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
  username: nano      # Gateway 启动时自动登录，无需手动填 token
  password: nano1234
```

`username` + `password` 方式：Gateway 启动时自动调 `POST /im/v1/auth/login` 获取 token，断线后自动重连，IM 重启后自动恢复，全程无需人工干预。

启动：`PYTHONPATH=src python -m personal_assistant.main`

### 非交互式 CLI 命令

```bash
PYTHONPATH=src python3 -m coding_cli.main --mode remote --base-url http://127.0.0.1:8000 health
PYTHONPATH=src python3 -m coding_cli.main --mode remote --base-url http://127.0.0.1:8000 create-session --title "demo"
PYTHONPATH=src python3 -m coding_cli.main --mode remote --base-url http://127.0.0.1:8000 send-message --session-id <id> --text "hello"
```

## 架构总览

四个独立顶层包，无 Python import 依赖，各自独立部署：

```
src/
├── agent/                # Agent 执行内核（HTTP API  only）
│   ├── core/             # 纯逻辑：runtime, loop, tools, hooks, skills, session
│   ├── platform/         # 集成层：HTTP API, LLM providers, persistence, safety
│   └── products/         # 产品 profile：local_coding, personal_assistant
├── coding_cli/           # 本地编码 CLI（终端 REPL）
├── personal_assistant/   # 个人助手 Node Gateway（常驻进程，Channel + Heartbeat）
└── IM/                   # IM 中心服务（Web IM + 配置中心 + 消息中继）
    └── frontend/         # React + TS + Vite
```

依赖方向硬规则（由 `tests/contract/` 自动验收）：
- `coding_cli` → `agent`（HTTP only，禁止直接 import）
- `personal_assistant` → `agent`（HTTP only，禁止直接 import）
- `IM` 不直接调用 `agent`，只与用户和 `personal_assistant` 交互
- 四个包之间禁止相互 import

agent 内核三层：`core`（纯逻辑）→ `platform`（接环境）→ `products`（装配方案）。
依赖方向：`platform → products + core`，禁止反向。`core` 不依赖 `platform` / `products`。

## 运行时服务并行启动

**在 worktree 内起任何监听端口的服务,都必须分配空闲端口,并 kill 自己起的进程**——主仓默认端口(8011 / 8000 / 5173)保留给用户手起的"主"实例,worktree 走 ephemeral 高位口,这样 `lsof -i :8011` 看到的永远是主实例,不会误把分支代码当成主仓。

### 推荐:一键起停

```bash
./scripts/e2e-up.sh        # 起 IM + Kernel API + Gateway,自动分配端口、改 config、auto-bind
source .e2e-ports.env      # 拿到 $IM_URL / $API_URL / $NODE_ID
# ...做你的事...
./scripts/e2e-down.sh      # 干净停掉
```

`e2e-up.sh` 把下面"端口分配 / config 隔离 / PID 管理 / 节点绑定"四件套全打包了。手起的散文流程保留在下面作为参考,工程化路径优先用脚本。

### 端口分配

```bash
read IM_PORT VITE_PORT < <(scripts/free-ports.sh 2)
```

`scripts/free-ports.sh N` 一次性返回 N 个互不重复的空闲端口。

### 每个服务怎么指定端口/URL

| 服务 | 指定端口/URL 方式 | 关键 env |
|---|---|---|
| IM (uvicorn) | `--port <N>`(uvicorn 原生) | `IM_JWT_SECRET=<unit 专属随机串>` 必须设,否则 token 跨重启失效;`IM_DB_PATH` 已支持,默认 `data/im_service.sqlite3`(cwd-relative),worktree 内起服务时天然隔离,无需显式传 |
| Kernel API (uvicorn) | `--port <N>` | `NANO_MULTIAGENT_LLM_BASE_URL` 指向 LLM provider(本地代理或 fixture);**注意是这个名字,不是 LLM_BASE_URL**——bugfix-380 fix-worker-r2 一度被此卡 30 分钟,见 retro |
| Gateway | 不监听端口(只连出);**config 必须用 worktree 本地副本** `--config <worktree>/.gateway-config.yaml`;指 IM 用 `--im-service-url http://127.0.0.1:<IM_PORT>` | `NANO_MULTIAGENT_AUTO_BIND=1` 或 `--auto-bind` 在 worktree e2e **必传**(否则会停在交互式 binding URL) |
| Vite | `npm run dev -- --port <N> --strictPort` | — |
| Coding CLI managed API | `--base-url http://127.0.0.1:<N>`(managed 模式 host/port 都从 base-url 解析) | — |

### 启动 / 关闭范式(两种,**不要混用**)

服务分两类,生死管理范式不一样:

**A. 裸 ASGI 服务**(IM、Kernel API、Vite,本质就是 uvicorn + ASGI app):
通用 `& echo $! > .pid` 范式,外部脚本完全说了算。

```bash
PYTHONPATH=src python -m uvicorn IM.app:app --host 127.0.0.1 --port "$IM_PORT" \
  > .im.log 2>&1 & echo $! > .im.pid

# 关:
kill "$(cat .im.pid)" 2>/dev/null; rm -f .im.pid
```

**B. wrapper 启动器**(Gateway, `python -m personal_assistant.main`):
它**不是** ASGI app —— 是个 supervisor,自己 spawn 多个 worker(channel relay / kernel uvicorn / heartbeat / run_queue 等),**自带内部 PID 单例锁**(写在 `<config 同目录>/gateway.pid`,**不带点**)+ `stop` / `restart` 子命令。

> **不要套用 A 类范式杀它**(`kill $(cat .gateway.pid)` 杀的是 shell job pid,启动器内部 pid 文件还在,下次 restart 撞单例锁报 `gateway is already running pid=...`,循环若干次才能逃出来,bugfix-380 fix-worker-r3 撞 4-5 次)。

worktree 内用 `--foreground` 模式 + 外部 pid 文件,让外部脚本主导生死:

```bash
PYTHONPATH=src python -m personal_assistant.main \
  --config "$WT_CFG" \
  --im-service-url "http://127.0.0.1:$IM_PORT" \
  --foreground \
  --auto-bind \
  > .gateway.log 2>&1 & echo $! > .gateway.pid

# 关(因为 --foreground 不写启动器内部 pid 文件,可以走通用范式):
kill "$(cat .gateway.pid)" 2>/dev/null; rm -f .gateway.pid
```

主仓用户手起的 Gateway(非 worktree e2e)继续用启动器自己的命令更顺手:

```bash
PYTHONPATH=src python -m personal_assistant.main           # 起(默认后台)
PYTHONPATH=src python -m personal_assistant.main stop      # 关
PYTHONPATH=src python -m personal_assistant.main restart   # 重启
```

### 通用清理

worktree 退出 / unit 完成时一律:

```bash
for f in .im.pid .api.pid .gateway.pid .vite.pid .coding-cli.pid; do
  [[ -f $f ]] && kill "$(cat "$f")" 2>/dev/null; rm -f "$f"
done
```

对 Gateway 来说前提是它用 `--foreground` 起的(范式 B),否则要用 `python -m personal_assistant.main --config "$WT_CFG" stop`。

### Gateway config 隔离

Gateway 的 config 路径无 env override,只能靠 `--config` 显式传(默认落到主仓持久化文件 `~/.nano-assistant/config.yaml`)。worktree 内起 Gateway **必须**先从主 config 拷一份本地副本并改写易污染主仓的字段,再用 `--config` 启动:

```bash
# WT_ROOT = 本 worktree 的绝对根目录(派发包里的 worktree_dir,不能用 $PWD —— Bash 的
# cwd 仍是主仓,$PWD 会把副本写进主仓反而破坏隔离)
WT_ROOT=<派发包给的 worktree_dir>

# 从主 config 派生 worktree 本地副本(需 yq;无 yq 则手改对应字段)
MAIN_CFG=~/.nano-assistant/config.yaml
WT_CFG="$WT_ROOT/.gateway-config.yaml"
cp "$MAIN_CFG" "$WT_CFG"
yq -i "
  .node.node_id = \"wt-$(basename "$WT_ROOT")\" |
  .im_service.url = \"http://127.0.0.1:$IM_PORT\" |
  .agents[].workspace_root = \"$WT_ROOT/.gateway-workspace/\" + .agents[].agent_id
" "$WT_CFG"

# 每个 agent 的 workspace_root 必须 pre-mkdir,Gateway 拒绝启动否则:
python3 -c "import yaml,os; cfg=yaml.safe_load(open('$WT_CFG')); [os.makedirs(a['workspace_root'], exist_ok=True) for a in cfg['agents']]"
```

改写三处的原因:`node_id` 唯一→IM 节点不撞主仓;`im_service.url`→指向 worktree 自己的 ephemeral IM;`workspace_root`→agent 工作区落在 worktree 内,Gateway 写回(新建 agent / 刷新 token)只动副本,主仓 config 和工作区零影响。`$WT_ROOT` 下的 `.gateway-config.yaml` / `.gateway-workspace/` 随 worktree 一起清理即可。

### IM Node binding(worktree e2e 必传 `--auto-bind`)

Gateway 第一次连一个新 IM 实例时,IM 要求确认绑定 owner,默认会打印一个 URL 等用户在浏览器点确认 —— **自动化场景下这是死锁**。

`--auto-bind` flag(或 `NANO_MULTIAGENT_AUTO_BIND=1` env var)让 Gateway 启动时**自动**调 `POST /im/v1/bind {action:confirm, bind_token}` 完成绑定,不开浏览器。worktree e2e、CI 脚本、`scripts/e2e-up.sh` 都用这个。

### LLM 上游故障注入(fixtures)

`scripts/fixtures/` 提供一组 ready-made HTTP 桩,触发 `ModelError` 的各种变体:

| 桩 | 触发 |
|---|---|
| `anthropic_sse_error.py <port>` | Anthropic SSE `event: error\ndata: {...}` 帧 → `retryable=False` |
| `openai_compat_error.py <port>` | OpenAI-format top-level `{"error":...}` 帧 → `retryable=False` |
| `http_error.py <port> <code>` | HTTP 401/403/429/500/502/503 |
| `slow_stream.py <port> truncate\|hang` | 流提前结束 / 卡住 → `retryable=True` |

详见 `scripts/fixtures/README.md`。配合 `NANO_MULTIAGENT_LLM_BASE_URL=http://127.0.0.1:<port>` 把 kernel 指过去即可。

## 开发约定

- **注释规范**：见 COMMENTING_GUIDE.md。public API 必须写 Google 风格 docstring；注释写"为什么/约束"而非"做什么"。
- **TODO/FIXME 格式**：`TODO(<issue-id>): <改进> — <删除条件>` / `FIXME(<issue-id>): <缺陷> — <影响/风险>`
- **Commit message 格式**：`<type>(<unit>/<milestone>/<roadpoint>): <desc>`，scope 用 unit 实际目录下的 id（如 `bugfix-355/M5/R1`）。milestone 级 commit 省 roadpoint（`bugfix-355/M5`），unit 级省 milestone（`bugfix-355`）。phase 通过 type 体现：C1 红测=`test`、C2 实现=`feat`/`fix`/`refactor`、C3 文档=`docs`。
- **模块边界**：CLI 只能通过 `ServerClient` 访问 API；不要在 `commands.py` 里重新导出内部实现。
- **单测优先**：修改后先跑最窄的单元测试，再跑集成/contract。
- **前端产物**：`src/IM/frontend/dist/` 是构建产物，不提交；需要时在前端目录执行 `npm run build`。

## 关键文档索引

| 文档 | 路径 | 内容 |
|---|---|---|
| 测试规范 | docs/TESTING_GUIDE.md | 测什么/不测什么、命名落层、临时验收 vs 回归、tasks.md 测试策略必填 |
| 架构总览 | SPEC.md | 四个包职责、依赖方向、部署图 |
| 内核设计 | docs/内核设计SPEC.md | agent 三层架构、模块归属、HTTP API、工具/Hook/Skill/Session 契约 |
| Coding CLI | docs/CodingCLI-SPEC.md | CLI 运行模式、REPL 交互、模块结构、硬约束 |
| Node Gateway | docs/NodeGateway-SPEC.md | Gateway 进程模型、Channel、入站四步决策、Heartbeat |
| IM 服务 | docs/IM-SPEC.md | IM Web IM、配置中心、设备绑定、节点管理、前端 |
| 操作手册 | docs/operator-runbook.md | 启动、调试、常见问题 |
| LLM 联调 | docs/可用LLM_API与联调说明.md | 可用模型、本地代理地址、验证 curl |

## Agent workflow

- Read AGENTS.md / SPEC.md before making changes.
- Prefer small, reviewable diffs.
- After code changes, run the narrowest relevant test first, then broader checks if needed.
- Do not commit secrets or generated local files.
