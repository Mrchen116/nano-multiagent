# Worktree Runtime Isolation

本文负责在 worktree 或临时目录中运行真实 IM、Gateway 和可选 Vite 时的隔离、观察与清理。这里的服务用于开发和 E2E 验证，生命周期随本次任务结束；主仓日常使用的持久服务见 [`../operations/`](../operations/README.md)。

## 适用场景

- 用当前分支代码运行真实 IM + Gateway，验证一次 change。
- 多个 worker、reviewer 或测试进程需要并行启动服务。
- E2E 需要独立端口、数据库、Gateway config、agent workspace 和 node identity。
- 需要在不污染用户主实例的前提下观察日志、runtime state 或 LLM 调用。

单元测试、静态检查和不依赖真实进程的集成测试不需要启动这套环境。

## 隔离与清理红线

1. worktree 不使用主实例的 IM 端口 `8011` 或常用 Vite 端口 `5173`，所有监听服务分配空闲高位端口。
2. Gateway 必须使用 worktree 内的 config 副本，不能让验证过程读写用户的 `~/.nano-assistant/config.yaml`。
3. IM 数据库、JWT secret、Gateway runtime state、agent workspace 和 node identity 必须属于本次运行。
4. 谁启动进程，谁负责记录进程身份、停止进程并确认端口已经释放。
5. config 副本、secret、PID、日志、数据库、凭据和 workspace 都是本地运行数据，不提交。
6. 内核是进程内库：Gateway 进程内持有内核，Coding CLI 进程内运行，不为内核分配独立端口。

## 前置条件

- 当前 Python 环境已安装项目依赖，并且 `python -c "import yaml"` 成功。worktree 没有独立 `.venv` 时，可以复用主 checkout 的虚拟环境。
- 仓库内的 [`../../config/e2e/gateway.yaml`](../../config/e2e/gateway.yaml) 是默认的、无密钥 E2E 配置，包含固定 agent、Web IM channel 和可选模型目录。需要另一个受控 config 时，才通过 `--main-config` 显式指定。
- `curl` 可用；手工改写 YAML 时 `yq` 可选，脚本在没有 `yq` 时使用 PyYAML。
- `WT_ROOT` 使用实际 worktree 或临时目录的绝对路径。Agent 收到派发包中的 `worktree_dir` 时直接使用该值，不根据调用 shell 的 `$PWD` 猜测。

### 专用 Feishu E2E profile

真实 Feishu 验收只使用仓库 [`../../config/e2e/gateway.yaml`](../../config/e2e/gateway.yaml) 中固定的 `e2e`、`e2e-peer` agents 和默认禁用的 `feishu:e2e` channel；`--feishu` 只在 worktree 副本中启用该 channel。`e2e-peer` 用于内部 IM 双 Agent 群聊；外部 Feishu 群聊用测试用户与当前测试 Bot 验证。它绝不从个人 Gateway config 或根目录 `.env` 继承 channel，且需要两项**本机私有**准备：

1. 创建权限为 `0600` 的 `${XDG_CONFIG_HOME:-~/.config}/nano-multiagent/feishu-e2e.env`，包含 `NANO_MULTIAGENT_E2E_FEISHU_APP_ID`、`NANO_MULTIAGENT_E2E_FEISHU_APP_SECRET`、`NANO_MULTIAGENT_E2E_FEISHU_BOT_OPEN_ID` 和 `NANO_MULTIAGENT_E2E_FEISHU_LARK_PROFILE`。这些值不得提交、打印或放进仓库 `.env`。
2. 以该文件声明的**非 default** `lark-cli` profile 完成一次用户身份登录。开始前执行 `lark-cli --profile <profile> auth status --json --verify`；profile 必须同时验证测试 App、测试 Bot 和测试用户。

`e2e-up.sh --feishu` 在启动 Gateway 前用 App 凭据查询 Bot identity；与 `BOT_OPEN_ID` 不一致时立即失败，不会把生产 Bot 凭据接入隔离栈。它还为该 Bot 取得本机 listener lock；同一 Bot 的第二个 worktree 会在启动 Gateway 前失败，必须先对原 worktree 执行 `e2e-down.sh`。`scripts/e2e-feishu-probe.py` 也拒绝 default 或跨 App/Bot 的 CLI profile，故不会因忘记 `--profile` 向生产 Bot 发消息。

## 推荐路径：脚本化起停

`scripts/e2e-up.sh` 是完整 IM + Gateway 隔离栈的可执行入口，`scripts/e2e-down.sh` 是与它配对的退出入口。即使启动或验证失败，也必须执行 down。

下面的范式把启动、验证和清理放在同一个受控 shell 中。若当前 shell 已激活包含 PyYAML 的环境，可以去掉 `PATH` 前缀。

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
WT_ROOT="$REPO_ROOT"
NANO_MAIN_ROOT="/absolute/path/to/main-checkout"
E2E_UP="$REPO_ROOT/scripts/e2e-up.sh"
E2E_DOWN="$REPO_ROOT/scripts/e2e-down.sh"

cleanup() {
  trap - EXIT INT TERM
  "$E2E_DOWN" --wt "$WT_ROOT"
}
trap cleanup EXIT INT TERM

PATH="$NANO_MAIN_ROOT/.venv/bin:$PATH" \
  "$E2E_UP" --wt "$WT_ROOT"

source "$WT_ROOT/.e2e-ports.env"
curl -fsS "$IM_URL/openapi.json" >/dev/null

# 在这里运行 API、浏览器或测试验证。
```

需要跨多次 Agent tool call 保持服务时，把这组命令放在受控的 `tmux` session 中，并保留 session 名称。短生命周期后台 shell 可能在 tool call 结束后被宿主回收，PID 文件和旧日志不能证明进程仍然存活。

脚本支持：

```bash
./scripts/e2e-up.sh --feishu
./scripts/e2e-feishu-probe.py --wt "$WT_ROOT"
./scripts/e2e-up.sh --main-config /path/to/config.yaml
./scripts/e2e-up.sh --wt /absolute/worktree/or/temp/path
./scripts/e2e-down.sh --wt /absolute/worktree/or/temp/path
```

## `e2e-up.sh` 建立的隔离

| 方面 | 脚本行为 |
|---|---|
| 端口 | 通过 `scripts/free-ports.sh` 为 IM 分配空闲端口；内核和 Gateway 不监听业务端口 |
| IM identity | 为本次运行生成随机 `IM_JWT_SECRET`，在全新 IM 中注册隔离测试用户 |
| IM 数据 | 以 `WT_ROOT` 为 cwd，使用其中的 `data/im_service.sqlite3`，启动前清理本目录的旧 E2E 状态 |
| Gateway config | 默认从 `config/e2e/gateway.yaml` 复制 `.gateway-config.yaml`，不修改源文件；`--feishu` 仅向该副本注入私有测试 App 凭据 |
| Gateway identity | 生成唯一 `node_id`，把 `im_service.url` 指向本次 IM，并同步本次测试用户的 `node.user_id` |
| Agent workspace | 将 `node.workspace_base` 和所有预置 agent 的 `workspace_root` 改到 `.gateway-workspace/` |
| Binding | Gateway 使用 `--auto-bind`，避免自动化流程停在浏览器确认页 |
| 进程 | IM 和 Gateway 的 PID 分别写入 `.im.pid`、`.gateway.pid`；Gateway 以 `--foreground` 运行，由外部脚本拥有生命周期 |
| Readiness | 等待 IM OpenAPI 可访问，并等待 Gateway 进程给出连接或启动信号 |
| 后续入口 | 写出 `.e2e-ports.env`，提供 `IM_PORT`、`IM_URL`、`IM_JWT_SECRET`、`NODE_ID` 和 `VITE_IM_PROXY_TARGET` |

源 config 必须包含可解析的 `llm:` 段。本文不复制完整模型配置；模型、provider 和凭据变化时只维护其 canonical 配置说明。

## 运行产物与保留边界

| 路径 | 作用 | `e2e-down.sh` 后 |
|---|---|---|
| `.e2e-ports.env` | 本次端口和 URL | 删除 |
| `.e2e-jwt-secret` | 本次 IM JWT secret | 删除 |
| `.gateway-config.yaml` | 隔离 Gateway config，可能含凭据 | 删除 |
| `.im.pid`、`.gateway.pid` | 外部进程身份 | 删除 |
| `channel-credentials-v1.pem`、`channel-manifest-v1.json` | 本次 channel 凭据与 manifest | 删除 |
| `.im.log`、`.gateway.log` | 本次运行日志 | 保留用于排障 |
| `.gateway-workspace/` | 本次 agent workspace | 保留用于排障 |
| `data/im_service.sqlite3` 及 Gateway SQLite state | 本次运行数据 | 保留或由下次 E2E 启动重建 |

保留下来的内容仍然是本地运行数据。提交前检查 `git status`；需要删除时先解析并确认具体 worktree 路径，不对仓库根或不明确变量执行递归删除。

## 如何确认当前栈仍然有效

先读取本次端口，再组合进程、监听端口和新日志判断。单独看到 PID 文件、`.gateway-state.json` 或历史日志都不构成存活证据。

```bash
source "$WT_ROOT/.e2e-ports.env"

kill -0 "$(cat "$WT_ROOT/.im.pid")"
kill -0 "$(cat "$WT_ROOT/.gateway.pid")"
curl -fsS "$IM_URL/openapi.json" >/dev/null
lsof -nP -iTCP:"$IM_PORT" -sTCP:LISTEN
tail -n 50 "$WT_ROOT/.gateway.log"
```

`e2e-up.sh` 的 readiness 只证明启动阶段通过。具体功能仍应执行与 change 对应的 API、E2E 或产品验收。

### 浏览器验收身份

脚本会按源 Gateway config 的 `im_service.username` 和 `im_service.password` 注册并绑定隔离用户；
浏览器验收必须以这一账号登录，不能临时注册另一个用户（新用户不会拥有这次 Gateway node）。仓库默认
`config/e2e/gateway.yaml` 使用 `nano` / `nano1234`；受控替代 config 则以其自身的 `im_service` 字段为准。
这只是隔离栈的测试身份，不得用于生产服务。

## 可选：启动 Vite

`e2e-up.sh` 只启动 IM 和 Gateway，不启动 Vite。需要前端 dev server 时，先加载它生成的代理目标，再单独分配端口：

```bash
source "$WT_ROOT/.e2e-ports.env"
VITE_PORT="$("$REPO_ROOT/scripts/free-ports.sh" 1)"

cd "$REPO_ROOT/src/IM/frontend"
VITE_IM_PROXY_TARGET="$IM_URL" \
  npm run dev -- --host 127.0.0.1 --port "$VITE_PORT" --strictPort
```

推荐让 Vite 在受控终端前台运行。若把它放到后台，调用者必须单独记录并停止其 PID；`e2e-down.sh` 当前只管理 IM 和 Gateway。

## 手工调试时必须保持的契约

完整栈优先修改或调用脚本，不在 Markdown 中复制另一套完整启动程序。只调试某个服务时，仍必须保持以下契约：

| 服务 | 启动方式 | 生命周期所有者 |
|---|---|---|
| IM | `python -m uvicorn IM.app:app --host 127.0.0.1 --port <free-port>`，设置随机 `IM_JWT_SECRET`，cwd 指向隔离目录 | 外部 shell/PID 文件 |
| Gateway | 显式传隔离 `--config`、本次 `--im-service-url`、`--foreground`、`--auto-bind` | 外部 shell/PID 文件 |
| Vite | 显式传空闲 `--port`、`--strictPort` 和本次 `VITE_IM_PROXY_TARGET` | 前台终端或调用者自己的 PID 文件 |

手工派生 Gateway config 时至少改写：

- `node.node_id`：不能与主实例或其他 worktree 重复。
- `node.workspace_base`：动态创建的 agent 也必须落在 worktree。
- `im_service.url`：只连接本次隔离 IM。
- `agents[].workspace_root`：预置 agent 不写入主目录。
- `node.user_id`：必须对应本次隔离 IM 中实际登录用户，不能复用主实例 ID。

Gateway 的两种生命周期不能混用：

- worktree 验证使用 `--foreground`，`.gateway.pid` 是外部 shell 记录的进程身份。
- 主仓持久实例使用 Gateway wrapper 的 start/stop/restart 和 config 同目录的 `.gateway-state.json`，详见 [`../operations/gateway.md`](../operations/gateway.md)。

## 退出与完成证明

先保存本次端口，再执行清理：

```bash
source "$WT_ROOT/.e2e-ports.env"
RUN_IM_PORT="$IM_PORT"

"$REPO_ROOT/scripts/e2e-down.sh" --wt "$WT_ROOT"

test ! -e "$WT_ROOT/.im.pid"
test ! -e "$WT_ROOT/.gateway.pid"
if lsof -nP -iTCP:"$RUN_IM_PORT" -sTCP:LISTEN; then
  echo "IM port still has a listener: $RUN_IM_PORT" >&2
  exit 1
fi
```

`e2e-down.sh` 先向 Gateway 发送 SIGTERM 并等待在途任务收口，超时后强制停止，再关闭 IM。脚本可以重复执行。

unit 完成或 worktree 删除前，还要确认：

- 没有本次 IM、Gateway、Vite 监听端口。
- 没有本次 PID 对应的存活进程或相关 `tmux` session。
- `.gateway-config.yaml`、secret 和 channel 凭据已经删除。
- 保留的日志、数据库和 workspace 没有被暂存或提交。

## 常见失败

| 症状 | 优先检查 |
|---|---|
| `ModuleNotFoundError: yaml` | 当前 `python` 不属于项目环境；激活 `.venv` 或把主 checkout 的 `.venv/bin` 放到 `PATH` 前部 |
| `E2E config not found` | 恢复仓库 `config/e2e/gateway.yaml`，或显式传 `--main-config` |
| config 缺少 `llm:` | 修正仓库 E2E config；不要在生成后的临时副本里维护第二份长期配置 |
| Feishu identity 校验失败 | 检查私有 `feishu-e2e.env` 是否仍指向专用测试 App/Bot；不要复用生产 App 凭据 |
| probe 拒绝 CLI profile | 执行文档中的 `auth status --verify`，并使用 env 文件指定的非 default profile |
| 提示 PID 仍在运行 | 先执行 `e2e-down.sh --wt <exact-path>`，再组合 PID、端口和日志确认 |
| Gateway 启动后无能力或节点异常 | 检查旧 Gateway 是否仍存活、`node_id` 是否碰撞、config 是否指向本次 IM |
| 启动被中断或日志像旧结果 | 先执行 down；必要时用 `zsh -x ./scripts/e2e-up.sh`，并核对新 PID、端口和日志时间 |
| 需要模拟 LLM 上游错误 | 复用 [`../../scripts/fixtures/README.md`](../../scripts/fixtures/README.md) 中的 HTTP fixtures |

Gateway 当前可观察生命周期以 [`../specs/gateway/service-lifecycle.md`](../specs/gateway/service-lifecycle.md) 为准；本文只负责开发隔离环境。
