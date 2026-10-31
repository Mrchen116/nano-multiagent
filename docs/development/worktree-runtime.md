# Worktree Runtime Isolation

本文负责在 worktree 或临时目录中运行真实 IM、Gateway 和可选 Vite 时的隔离、观察与清理。这里的服务用于开发和 E2E 验证，生命周期随本次任务结束；独立生产 checkout 中的持久服务见 [`../operations/`](../operations/README.md)。

## 适用场景

- 用当前分支代码运行真实 IM + Gateway，验证一次 change。
- 多个 worker、reviewer 或测试进程需要并行启动服务。
- E2E 需要独立端口、数据库、Gateway config、agent workspace 和 node identity。
- 需要在不污染用户主实例的前提下观察日志、runtime state 或 LLM 调用。

单元测试、静态检查和不依赖真实进程的集成测试不需要启动这套环境。

## 隔离与清理红线

1. worktree 不使用主实例的 IM 端口 `8011` 或常用 Vite 端口 `5173`，所有监听服务分配空闲高位端口。
2. Gateway 必须使用 worktree 内的 config 副本，不能让验证过程读写用户的 `~/.nanoassistant/config.yaml`。
3. IM 数据库、JWT secret、Gateway runtime state、agent workspace 和 node identity 必须属于本次运行。
4. 谁启动进程，谁负责记录进程身份、停止进程并确认端口已经释放。
5. config 副本、secret、PID、日志、数据库、凭据和 workspace 都是本地运行数据，不提交。
6. Node 管理独立 DSH 子进程，只经 stdio 通信；两者都不监听独立业务端口。DSH home 与 owner 配置根也必须隔离。
7. up/down 在任何文件修改或进程停止前检查生产保护路径与 `.nano-production` 标记；拒绝时另选独立目录，不删除标记绕过。配置与判定规则见 [本机开发配置](local-development.md#本机开发配置)。

## 前置条件

- 已执行 `pnpm install --frozen-lockfile`、`pnpm build`。主前端依赖另需 `npm --prefix src/IM/frontend ci`；up 自动校验主前端与原生轨迹查看器，按需构建，不要求手工构建 Web。隔离脚本的 YAML/HTTP 辅助逻辑仍需 Python dev 依赖（PyYAML、httpx）；可以复用主 checkout 的 `.venv`。Python 不承担 IM 或 Agent 服务。
- 先按 [本机开发配置](local-development.md#本机开发配置) 执行 `python3 scripts/dev_host.py check`，确认当前机器的测试源配置和能力；此报告不证明真实 E2E 可用。
- 仓库内的 [`../../config/e2e/gateway.yaml`](../../config/e2e/gateway.yaml) 是未配置本机覆盖时的无密钥 E2E 配置，包含两个普通 Agent（`e2e`、`e2e-peer`）、一个 Global Agent（`e2e-global`）、Web IM channel 和可选模型目录。初始配置提供启动所需工具；default/daily 注册后通过产品 capabilities/config API 同步当前默认工具、固定工具及已启用 Feature 的依赖，再报告 ready。保留仍有效的额外选择，后续新增默认工具自动跟随，不在测试 YAML 另维护完整名单；显式 `--main-config` 和专项限制不自动扩展。Skills 使用空禁用名单，保留正常发现。default 可通过 `--main-config` 显式指定另一个受控 config；配置优先级见本机开发配置。
- `curl` 可用；手工改写 YAML 时 `yq` 可选，脚本在没有 `yq` 时使用 PyYAML。
- `WT_ROOT` 使用实际 worktree 或临时目录的绝对路径。Agent 收到派发包中的 `worktree_dir` 时直接使用该值，不根据调用 shell 的 `$PWD` 猜测。

### 专用 Feishu E2E profile

真实 Feishu 验收使用仓库测试模板或其本机副本中固定的 `e2e`、`e2e-peer` agents 和默认禁用的 `feishu:e2e` channel；`--feishu` 只在 worktree 副本中启用该 channel。`e2e-peer` 用于内部 IM 双 Agent 群聊；外部 Feishu 群聊用测试用户与当前测试 Bot 验证。它绝不从个人 Gateway config 或根目录 `.env` 继承 channel，当前测试 Bot 只在 Air 使用；Mini 的本机能力设置会提前拒绝起栈，验收交接同一代码 SHA 到 Air。Air 需要两项**本机私有**准备：

1. 创建权限为 `0600` 的 `${XDG_CONFIG_HOME:-~/.config}/nano-multiagent/feishu-e2e.env`，包含 `NANO_MULTIAGENT_E2E_FEISHU_APP_ID`、`NANO_MULTIAGENT_E2E_FEISHU_APP_SECRET`、`NANO_MULTIAGENT_E2E_FEISHU_BOT_OPEN_ID` 和 `NANO_MULTIAGENT_E2E_FEISHU_LARK_PROFILE`。这些值不得提交、打印或放进仓库 `.env`。
2. 以该文件声明的**非 default** `lark-cli` profile 完成一次用户身份登录。开始前执行 `lark-cli --profile <profile> auth status --json --verify`；profile 必须同时验证测试 App、测试 Bot 和测试用户。

`e2e-up.sh --feishu` 在启动 Gateway 前用 App 凭据查询 Bot identity；与 `BOT_OPEN_ID` 不一致时立即失败，不会把生产 Bot 凭据接入隔离栈。它还为该 Bot 取得本机 listener lock；同一 Bot 的第二个 worktree 会在启动 Gateway 前失败，必须先对原 worktree 执行 `e2e-down.sh`。`scripts/e2e-feishu-probe.py` 也拒绝 default 或跨 App/Bot 的 CLI profile，故不会因忘记 `--profile` 向生产 Bot 发消息。

## 固定日常验收模板

正常开发流程的真实产品验收使用 `scripts/e2e-up.sh --profile daily --wt <绝对目录>`，每个需求独立实例。角色和初始资料由仓库 [daily 模板](../../config/e2e/daily/team.yaml) 固定维护，初始化使用按本机配置选出的测试模型目录，不读取个人 Gateway 配置或生产聊天。

| 固定角色 | 职责 | 主模型 / 推理档位 |
|---|---|---|
| P · 产品与体验（`daily-product`） | 整理目标、范围和可观察验收标准 | `codexOAuth:gpt-6.1-sol` / `high` |
| E · 工程交付（`daily-engineering`） | 完成交办、自测、交付可检查产物 | `codexOAuth:gpt-6.1-sol` / `high` |
| Q · 独立质量（`daily-quality`） | 依据原始要求和真实产物独立核实 | `codexOAuth:gpt-6.1-sol` / `high` |
| PA · 个人助手（产品生成 ID） | 服务测试主人、读取允许的来源、跟进明确交办 | `codexOAuth:gpt-6-astra` / `medium` |

四者均为 Global 模式，显式选择 Codex 审核规则，无备用主模型；独立工具/PA 审核模型为 `codexOAuth:gpt-6-luna`。审核执行代码优先使用受支持的 `low`，不继承主 Agent 的 effort，也没有额外的模板审核 effort 参数。隔离 owner 配置明确开启 Auto、不跳过权限；权限路由和 PA 对外披露仍遵循[产品审核规则](../operations/auto-permissions.md)。开发侧独立 code reviewer/product reviewer 的模型由各自 skill 派发适配决定，产品内的 Q 不能替代它们。

启动会准备：

- 测试主人 `nano`（密码 `nano1234`）、主人 + P/E/Q 的私密“研发日常”群，以及通过正式产品流程创建的 PA 和主人私聊。PA 默认可观察该群，不作为该群成员。
- 各自 workspace 和共享的虚构“轻记待办”项目资料（背景、反馈、检查清单）。P 接收普通群交办，E/Q 被 @ 时处理；heartbeat 默认关闭，需要验证时在本轮副本开启。
- `.e2e-daily.json`，列出实际角色 ID、模型/effort、审核规则、群/PA 入口与项目位置；不包含 token。只有全部 seed 完成才报告 ready，不发送初始化消息、不制造聊天历史或任务，不调用 LLM。

工作区与 owner 根均按本轮 node_id 隔离。同一目录先 down 再 up 也恢复新的基线，旧文件和 Skill 仅作为排障证据保留，不被新实例继承；不同需求不得共用运行中的目录。停止沿用 `e2e-down.sh`，其保留的配置、密钥和状态仍为本地运行证据，不提交仓库。

主 Agent 集中准备环境，向 reviewer 交接版本、清单、入口和本次场景增量。需要额外用户、Agent、数据、Feature 或权限时只在当前副本补充，并记录差异；不复制或改写生产资源。模板 ready 只说明身份和资源建立完成，真实模型回复与用户旅程仍须验收。

`NANO_MULTIAGENT_E2E_MODEL` 可显式覆盖本轮全部工作模型，采用所选模型目录默认 effort，独立审核仍使用 Luna；清单显示实际值，不把覆盖后的运行冒充默认模型验证。一般验收不设置该变量。daily 不与 `--main-config` 或 `--feishu` 混合。

无参数的 `default` 继续提供 `e2e/e2e-peer/e2e-global` 环境；[关键路径自动回归](e2e-critical-paths.md) 通过 `--main-config` 将所有 provider 替换为本地 recording fixture，不使用模板中的真实代理地址；专用 Feishu、错误上游等场景作为按需补充，不代替日常基线。

## 推荐路径：脚本化起停

`scripts/e2e-up.sh` 是完整 IM + Gateway 隔离栈的可执行入口，`scripts/e2e-down.sh` 是与它配对的退出入口。即使启动或验证失败，也必须执行 down。

下面的范式把启动、验证和清理放在同一个受控 shell 中。若当前 shell 已激活包含 PyYAML 的环境，可以去掉 `PATH` 前缀。

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
WT_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/nano-e2e.XXXXXX")"
NANO_MAIN_ROOT="/absolute/path/to/main-checkout"
E2E_UP="$REPO_ROOT/scripts/e2e-up.sh"
E2E_DOWN="$REPO_ROOT/scripts/e2e-down.sh"

cleanup() {
  trap - EXIT INT TERM
  "$E2E_DOWN" --wt "$WT_ROOT"
}
trap cleanup EXIT INT TERM

PATH="$NANO_MAIN_ROOT/.venv/bin:$PATH" \
  "$E2E_UP" --profile daily --wt "$WT_ROOT"

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
| 端口 | 通过 `scripts/free-ports.sh` 为 IM 和可选 Vite 分配空闲端口；DSH 和 Gateway 不监听业务端口 |
| IM identity | 为本次运行生成随机 `IM_JWT_SECRET`，在全新 IM 中显式初始化隔离测试用户 |
| IM 数据 | 以 `WT_ROOT` 为 cwd，使用其中的 `data/im_service.sqlite3`，启动前清理本目录的旧 E2E 状态 |
| Gateway config | 从选定的本机或仓库测试 YAML 复制 `.gateway-config.yaml`，不修改源文件；`--feishu` 仅向该副本注入私有测试 App 凭据 |
| Gateway identity | 生成唯一 `node_id`，把 `im_service.url` 指向本次 IM，并同步本次测试用户的 `node.user_id` |
| Runtime 根 | 本次 owner 根、Node SQLite 和 DSH home 均在 worktree 隔离目录 |
| Agent workspace | 将 `node.workspace_base` 和所有预置 agent 的 `workspace_root` 改到 `.gateway-workspace/` |
| Binding | Gateway 使用 `--auto-bind`，避免自动化流程停在浏览器确认页 |
| 进程 | IM 和 Gateway 的 PID 分别写入 `.im.pid`、`.gateway.pid`；Gateway 由当前 Node CLI 管理，状态文件记录 Node 与 DSH PID |
| Readiness | 等待 IM health、Node/DSH 完成恢复，再验证目标 owner 的节点 online |
| 后续入口 | 写出 `.e2e-ports.env`，提供 `IM_PORT`、`IM_URL`、`IM_JWT_SECRET`、`NODE_ID`、`UI_URL`、可选 `VITE_PORT` 和 `VITE_IM_PROXY_TARGET` |

源 config 必须包含可解析的 `llm:` 段。本文不复制完整模型配置；模型、provider 和凭据变化时只维护其 canonical 配置说明。

## 运行产物与保留边界

| 路径 | 作用 | `e2e-down.sh` 后 |
|---|---|---|
| `.e2e-ports.env` | 本次端口和 URL（停止后不代表服务在线） | 保留用于排障 |
| `.e2e-jwt-secret` | 本次 IM JWT secret | 保留，与状态配套 |
| `.gateway-config.yaml` | 隔离 Gateway config，可能含凭据 | 保留，与状态配套 |
| `.im.pid`、`.gateway.pid`、可选 `.vite.pid` 及 birth 文件 | 外部进程身份 | 删除 |
| `channel-credentials-v1.pem`、`channel-manifest-v1.json` | 本次 channel 凭据与 manifest | 保留，与状态配套 |
| `.im.log`、`gateway.log` | 本次运行日志 | 保留用于排障 |
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
pnpm pa status --config "$WT_ROOT/.gateway-config.yaml"
tail -n 50 "$WT_ROOT/gateway.log"
```

`e2e-up.sh` 的 readiness 只证明启动阶段通过。具体功能仍应执行与 change 对应的 API、E2E 或产品验收。

### 浏览器验收身份

所有 profile 都显式初始化并绑定测试账号 `nano` / `nano1234`（包括 `--main-config`）。
浏览器使用启动输出中的 `UI_URL`；不能临时注册另一个用户来验收本次 Gateway。
这只是隔离栈的测试身份，不得用于生产服务。

## 默认同源 UI 与可选 Vite

所有 profile 均准备主前端与原生轨迹查看器，并通过绝对 `IM_FRONTEND_DIST_DIR` /
`IM_TRAJECTORY_DIST_DIR` 交给 IM；临时 `--wt` 目录不必含源码。默认直接打开 `IM_URL`，
登录、聊天 WebSocket 和 `/trajectory/` 资源同源，无需 Vite。

up 调用 `scripts/e2e_ui.py`，按内容指纹分别判断两套产物是否仍有效，不依赖 Git 提交或文件修改时间：

- 首次启动、源码增删改、构建配置或依赖锁文件变化，自动构建受影响的前端；对应的 `product-contracts`、`trajectory-ui` 源码和实际导出也纳入判断，重建时先构建这些共享包。
- 输入与上次成功产物均一致时直接复用；只改后端源码无需重建 UI。根依赖锁文件变化保守地使两套构建失效。
- 本地产物缺失或被其他手动构建覆盖时，优先复制同仓库中输入匹配且产物校验通过的缓存，否则重建；构建失败或构建过程中输入变化会停止启动，不使用不匹配的旧产物继续报 ready。
- 构建时固定 API 为同源；检查 Node 版本、相关构建环境与 `.env*` 内容。运行时 IM/Vite 端口不影响复用。

本地构建记录位于 `.cache/e2e-ui/`；同仓库共享缓存与构建锁位于 Git common dir 的 `nano-e2e-ui-cache/`。缓存只保留每套 UI 最近一份成功产物，源文件和构建环境相同的新 worktree 可复制复用；各 worktree 仍使用自己的 dist、账号、数据库和运行目录。共享副本内容损坏时重建，不接受仅有入口文件的未知产物。每次 up 输出 `E2E UI: build ...`、`reuse ...` 或 `restore ...`。

上述缓存不提交；需要强制重新构建某套 UI 时，删除本地对应的 `frontend.json` / `trajectory.json` 和共享目录内该套的 `build.json`，保留运行中的 `build.lock`。此机制只节省 UI 构建，不跳过测试或隔离栈的健康检查。

需要 HMR 时使用同一入口，不另建启动流程：

```bash
./scripts/e2e-up.sh --vite --wt /absolute/isolated/path
source /absolute/isolated/path/.e2e-ports.env
# 打开 $UI_URL；$IM_URL 仍提供完整的构建版 UI。
./scripts/e2e-down.sh --wt /absolute/isolated/path
```

Vite 绑定 loopback 的独立空闲端口并使用 `--strictPort`。`/im` 的 HTTP/WS 和
`/trajectory` 资源均代理到本轮 IM；保留浏览器 Origin，仅将本轮 Vite 精确 origin
加入 IM 的 `IM_BROWSER_ORIGINS`，不使用通配符或关闭安全校验。up 清除继承的其他
origin 白名单。`.vite.pid`、`.vite.process-start` 和 `.vite.log` 属于本轮目录；down
核对进程出生时间后仅停止该实例，不扫描端口杀进程，也不停止调用者手工启动的 Vite。
若启动失败，仍须对同一目录运行 down；日志、配置及数据库作为证据保留。

## 手工调试时必须保持的契约

完整栈优先修改或调用脚本，不在 Markdown 中复制另一套完整启动程序。只调试某个服务时，仍必须保持以下契约：

| 服务 | 启动方式 | 生命周期所有者 |
|---|---|---|
| IM | `node apps/im-server/lib/main.js serve --host 127.0.0.1 --port <free-port>`，设置随机 `IM_JWT_SECRET`，cwd 指向隔离目录 | 外部 shell/PID 文件 |
| Gateway | 使用 Node CLI `bind --auto-bind` 和 `start --config <隔离配置>` | Node CLI 状态文件 |
| Vite | 显式传空闲 `--port`、`--strictPort` 和本次 `VITE_IM_PROXY_TARGET` | 前台终端或调用者自己的 PID 文件 |

手工派生 Gateway config 时至少改写：

- `node.node_id`：不能与主实例或其他 worktree 重复。
- `node.workspace_base`：动态创建的 agent 也必须落在 worktree。
- `im_service.url`：只连接本次隔离 IM。
- `agents[].workspace_root`：预置 agent 不写入主目录。
- `node.user_id`：必须对应本次隔离 IM 中实际登录用户，不能复用主实例 ID。

Gateway 的两种生命周期不能混用：

- worktree 验证复用 Node CLI start/stop，配置同目录 `.gateway-state.json` 记录身份；`.gateway.pid` 是便于检查的副本。
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
- 配置、secret 和 channel 凭据仅保留在本轮隔离目录，不能提交或当作新一轮运行状态。
- 保留的日志、数据库和 workspace 没有被暂存或提交。

## 常见失败

| 症状 | 优先检查 |
|---|---|
| `ModuleNotFoundError: yaml` | 当前 `python` 不属于项目环境；激活 `.venv` 或把主 checkout 的 `.venv/bin` 放到 `PATH` 前部 |
| `E2E config not found` | 用 `dev_host.py check` / `e2e-config --repo <源码目录>` 核对本机源文件；default 也可显式传 `--main-config` |
| config 缺少 `llm:` | 修正仓库 E2E config；不要在生成后的临时副本里维护第二份长期配置 |
| Feishu identity 校验失败 | 检查私有 `feishu-e2e.env` 是否仍指向专用测试 App/Bot；不要复用生产 App 凭据 |
| probe 拒绝 CLI profile | 执行文档中的 `auth status --verify`，并使用 env 文件指定的非 default profile |
| 提示 PID 仍在运行 | 先执行 `e2e-down.sh --wt <exact-path>`，再组合 PID、端口和日志确认 |
| Gateway 启动后无能力或节点异常 | 检查旧 Gateway 是否仍存活、`node_id` 是否碰撞、config 是否指向本次 IM |
| 启动被中断或日志像旧结果 | 先执行 down；必要时用 `zsh -x ./scripts/e2e-up.sh`，并核对新 PID、端口和日志时间 |
| 需要模拟 LLM 上游错误 | 复用 [`../../scripts/fixtures/README.md`](../../scripts/fixtures/README.md) 中的 HTTP fixtures |

Gateway 当前可观察生命周期以 [`../specs/gateway/service-lifecycle.md`](../specs/gateway/service-lifecycle.md) 为准；本文只负责开发隔离环境。
