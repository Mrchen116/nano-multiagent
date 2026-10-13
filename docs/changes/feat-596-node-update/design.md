# feat-596: 用户主动更新电脑端 — 技术方案

> 对齐: spec.md；基线 f486d889f（包含 bugfix-591 显式版本发布）。

## Changelog

- R1：补齐屏障前 relay gate、取消/崩溃后主动重放、本机屏障租约，以及恢复失败后的消息投影。

## 现状分析

### 涉及范围

`apps/im-server/assets/install.sh` 准备私有 Node/pnpm、校验固定 GitHub 包、在按 hash 隔离的 releases 目录安装，再调用 setup。`apps/node/src/cli.ts` 在旧节点 ready 时直接退出，未切换版本。`lifecycle.ts` 已有进程出生时间核对、进程互斥、LaunchAgent/普通后台启停与 readiness。

`main.ts` 注册/心跳仍固定报告 nano-dsh/0.1.0。`Gateway` 已有 owner/epoch 校验、request/response 和重新注册后的 relay 重放。`Messaging` 已持久化 relay_tasks，但投递不成功时向发送者返回 503。Web NodesPage 已有按电脑的卡片、版本、状态、别名和保存动作；聊天顶部 NodeChip 只显示名字与在线状态。

### 既有约束

仅 dsh-integration 使用已声明的 DSH public exports，Node 仅通过 stdio client 使用运行时。IM 不执行本机更新、不读取用户电脑磁盘。维持配置、节点身份和 workspace；不把 token、日志、数据库或录屏缓存提交。真实服务使用独立端口/config/data/workspace/node identity。

### 可复用能力

- 复用：固定 manifest/GitHub Release/SHA-256、releases 按内容隔离、冻结依赖安装；不另建更新分发源。
- 复用并扩展：manageGateway 的启停锁/出生时间/LaunchAgent 定义；状态增加实际 entry、release 与 IM 连接确认。切换由独立进程调用旧/新 CLI，不在被停止的 Node 内执行自我重启。
- 复用：IM runtime token 的 authenticateRuntime，可在节点 WS 临时断开时对更新进程的窄 HTTP 状态接口鉴权；不新增凭据体系。
- 复用：relay_tasks 的持久化与幂等；只对已授权更新的短暂停收区间允许成功排队，普通离线语义不变。
- 复用：DSH AgentRegistry.list、Agent.status/inbox/runMaintenance 公共 API；扩展本仓 integration 提供安全更新屏障，不私自操纵 DSH driver。

### 相关历史

feat-587 首次设置与同源安装；feat-588 模型管理与固定包分发；bugfix-591 的版本以显式 X.Y.Z 发布、source_commit 固定。新实现兼容旧 SHA manifest 的安装读取，不把主干合并自动变成发布。

## 架构总览

Web → IM 的 owner-only 更新操作 → 既有节点 WS 下发固定操作 → Node 启动 detached 更新进程。

更新进程负责下载、校验、依赖安装、切换、回退及窄 HTTP 进度上报；Node 负责判断本机是否安全切换；DSH integration 负责运行时的空闲与冻结屏障。IM 持久化授权目标、阶段与取消请求，并在切换期间保存新消息。不同连接目录具有各自更新锁，程序包可共享而运行状态不可共享。

## 关键决策

**只检查元数据；点击后才产生下载授权。** GET 是只读检查。POST 携带页面展示的 version/hash 及稳定 request_id；服务器与当前已验证清单比较，不在点击后悄悄改成另一个版本。若清单已经改变返回冲突并刷新说明。活动操作重复提交返回同一 operation；失败后的重试产生新 operation。旧 request_id 永不重新执行。

**更新状态由持久操作事实驱动。** 状态为 requested → downloading → installing → waiting → switching → verifying → succeeded；前半段可 cancelled/failed，启动失败进入 rolling_back → rolled_back/recovery_required。UI 只显示有限阶段和受控错误信息，不透传命令日志。updated_at 是独立更新进程的心跳，不以旧节点在线推断仍在更新。失联超时显示 interrupted/recovery_required，不长期冒充正常更新。

**先准备好新目录，再在安全边界停旧进程。** Node 有本地 admission gate，保护 relay、外部 channel、Heartbeat、模型/配置变更；短暂 gate 期间 Web 输入仍留在 IM relay，外部输入仍在 ExternalChannels durable ledger，不能返回成功后吞掉。正在执行的任务和 permission response 继续。准备屏障会核对 Node 的在途 admission/控制操作以及 PA reconciliation；DSH 一次性核对全部 live Agent（含 child）、inbox、ModelPolicy/ModelFallback 待续工作、Workflow live/paused 工作、Knowledge review/tasks。存在工作就返回 busy，不 cancel。没有工作才暂停 cron timer 并用 public runMaintenance 把 idle Agent 保持在真正 idle，相同 scope 禁止新 session admission；竞态发现新增工作则释放并重试。取消或准备失败恢复原 cron/接入，不修改用户保存的 feature 开关。

**等待屏障与消息 gate 按同一操作交接。** 新包准备完成后，worker 先报告 waiting/prepare，由 IM 持久开启该操作的 relay gate，再请求 Node 屏障。已发送但尚未承认的 relay 一并保留；Node admission 拒绝不能写 accepted receipt。屏障发现 busy 时先恢复本机 admission，再报告 waiting/resumed，IM 关闭 gate 并主动重放 queued/sent/accepted；下一次空闲探测重复此顺序。取消只先写 cancel_requested；只有本机释放屏障后才报告 cancelled 并主动重放，不依赖 WS 重连。下载阶段取消无需建立屏障。

**本机屏障有短租约，不能依赖 worker 一直存活。** `.node-update.json` 由 worker 每秒刷新 operation_id、worker PID/birth 和 heartbeat；Node 的屏障绑定该身份及自身 PID/birth。worker 进程死亡或连续 15 秒心跳过期时，Node 自动释放 runMaintenance、恢复 cron/admission、删除匹配 handoff，并通过自己的持久 runtime token 报告 interrupted/resumed；只有该恢复 ACK 或验证通过的在线注册才能解除 IM relay gate。worker claim-switch 前和实际 stop 前都重新核对租约与 handoff；claim 已成功但 stop 前屏障失效时不得停机，先报告 interrupted/resumed 收口；已释放或属于其他进程的 handoff 不可使用。取消、准备失败和租约超时共享这一释放路径。IM 30 秒失联将结果标记 interrupted 或 recovery_required；未取得 resumed/ready 时，既有排队消息保留为等待电脑恢复而非仍在正常更新，恢复节点重新注册后再重放。

**取消与切换在 IM 做一次原子裁决。** 更新进程定期取得 cancel_requested；waiting 阶段拿到本地包含 operation_id、pid/process_start 的 ready handoff 后，向 IM claim-switch。IM 只在同一 owner/epoch/operation 且未取消时切到 switching，同时保持已开启的 relay gate。取消先发生则切换不能发生；切换先发生则取消返回冲突，UI 不再展示取消按钮。准备屏障与 claim 之间仍可取消，释放本地屏障。HTTP ACK 丢失查询同一 operation，不启动第二个切换。

**真实 readiness 后才显示成功。** 新 CLI 使用原 config 与同一 identity 启动；更新进程验证 PID birth、实际 release hash/commit、DSH ready 和该版本已在 IM 注册，随后上报 succeeded。在成功前 IM 保持 relay gate，注册后不提前重放。终态解除 gate 后仅投递仍符合成员/owner/epoch 的既有 relay，Node 的既有输入幂等防重复。已排队输入在刷新后从持久消息状态恢复。

**旧版本保留，回退有明确范围。** 新包 metadata 声明 updater_protocol=1、data_epoch=1；只能按钮更新到兼容 epoch 的包。当前 unit 不做不可逆用户数据迁移，失败仅切回旧 release/Node 可执行文件，保留原 config、身份、DSH home 与 workspace。只有旧版本也完成 readiness 才显示 rolled_back。恢复失败保留日志与安装恢复入口，绝不谎报助手可用。

**旧用户一次性桥接，源码运行明确区分。** 安装器保存已验证 manifest 到对应 release，setup 识别版本而非只看 running。新安装包含更新器，重复相同版本复用。旧版缺少更新屏障时，页面说明先结束现有任务再执行一次安装命令以启用按钮更新；命令显式替换旧运行程序、保留配置。源码部署报告 unmanaged，显示按原部署方式更新，不去改 checkout 或假造受管安装。新版重跑安装命令复用同一安全切换能力。

## 接口与数据流

共享 `product-contracts` 定义 ReleaseManifest 验证和 NodeUpdateState，既有 shell 引导仍做最小自举校验。构建包包含来源 commit 与更新协议/数据 epoch；发布脚本只对同一已校验包生成显式版本清单，并可携带简短纯文本 release_notes；安装记录与包内 source_commit 互证。更新包只能来自当前 IM 已发布固定 GitHub URL，HTTPS 下载/重定向与 SHA 校验，不接受浏览器自带下载地址。

IM 增加受管安装快照及更新操作表；后者保存 operation_id/request_id、node/owner/epoch、目标清单、阶段、cancel_requested、受控错误、更新时间，旧 request_id 保留幂等记录。当前活动操作每个 node 至多一条。

- `GET /im/v1/nodes` 增加 `update`：current/target 信息、可用性、当前 operation、安装类型、必要时一次性安装材料。认证仍按 owner 隔离。
- `POST /im/v1/nodes/:node_id/update`：owner、online、managed/protocol、epoch、manifest/版本/hash 校验后落盘授权并派发 `node.update.request`。网络结果不明保留 requested，重试/重连按同一操作核对。
- `POST /im/v1/nodes/:node_id/update/cancel`：仅 owner 能原子取消未切换的 operation。
- `POST /im/v1/node-update/report`：仅持久 runtime token 可用，核对 node/owner/epoch/operation，白名单阶段迁移。返回当前授权事实/cancel 标志；claim-switch 在该事务裁决。该窄接口明确排除普通 IM session prehandler，仍单独严格鉴权。
- `node.register` 携带实际 release 与 update capability，后续 reconnect 不以相同 Node 名字推断成功。节点快照与 `node.update_changed` 供 Web cache 刷新。
- 本地连接目录保存 `.node-update.json` 和屏障 handoff；下载 staging、锁和日志均保持私有/不入 Git。工作进程独占状态写入，Node 只写带 operation_id/PID 的 ready handoff。每次进程启动检查未收口操作并以真实状态恢复或报告 interrupted，不把旧 ready 当新授权。

消息只在 waiting/prepare 的短屏障及切换期间保持 queued；正常 downloading/installing 继续投递。切换时 HTTP send 返回已持久消息，更新恢复后复用原 relay key。等待提示由 pending 消息对应仍 gated 的 relay 计算，支持一条消息的多节点接收，避免一台更新挡住其他节点。不改普通离线节点发送失败语义。进入 recovery_required 或未恢复的 interrupted 后，不再接受新的“更新中成功排队”发送；已持久排队消息显示“电脑恢复后继续处理，无需重发”，聊天 chip 显示“电脑需要恢复”并链接该电脑恢复入口。取消/下载失败/已回退且在线时，释放 gate 后立即重放；恢复失败则在同身份同 epoch 节点恢复注册后重新校验并重放，原 relay key 始终不变。

## 前端原型

原型文件：[prototype.html](prototype.html)。原型展示现有节点卡片增量和聊天上下文；外层演示控件切换任务忙碌、失败与离线，不伪装实际运行结果。

电脑卡片保留设备名/在线状态，新增独立更新区域：当前→目标版本、说明、短暂暂停解释、一个主动作；更新不占用别名保存按钮。手机将说明与按钮纵向排布，设备名不被版本文本挤掉。聊天入口显示“有新版本”轻提示并链接精确电脑卡片；切换时显示“正在更新”，输入仍可用，排队消息有持久等待说明。只有本人电脑提供管理入口。

### 现有 UX grounding

| 当前产品入口 | 画面与操作基线 | 沿用或改善 | 本次设计 |
|---|---|---|---|
| /settings/nodes | NodesPage 卡片、KPI、版本与别名，真实隔离栈走查 | 保留设备身份与独立保存草稿 | 版本相关动作合并到卡片更新区域 |
| /chat 顶部电脑标识 | MessagePane/NodeChip + 联系人在线状态 | 保留聊天主视线，不弹 modal | 轻提示直达电脑卡片；切换替代普通离线提示 |

### 原型对齐契约

| 区域/状态 | 对齐级别 | 产品入口 | viewport/状态 | 退出标准 |
|---|---|---|---|---|
| 电脑更新区域 | must-match | /settings/nodes#node-ID | 1280、820、390；可更新/下载/等待/切换/完成/失败/离线/旧版 | M1-R1/W1：设备、版本和主动作层级清晰；失败有下一步；无重复确认 |
| 聊天入口与等待提示 | must-match | /chat | 1280、390；新版本/切换中发送并刷新 | M1-R2/W1：不遮聊天；消息可发送、等待状态可见、恢复无重发 |
| 其他节点设置及聊天内容 | out-of-scope | 原有路由 | 背景展示 | 保持现有行为 |

### 原型走查

实际渲染记录与基线对照见 evidence/design-walkthrough.md；截图是设计证据，真实实现另行验收。

## 契约层增量

- IM 电脑更新：specs/im/agents-nodes.md → docs/specs/im/agents-nodes.md。
- IM relay 更新排队：specs/im/gateway-relay.md → docs/specs/im/gateway-relay.md。
- Gateway 更新生命周期：specs/gateway/service-lifecycle.md → docs/specs/gateway/service-lifecycle.md。

## 风险与回退

更新器在本次进程独立于 Node；每连接互斥，身份变更/撤权中止操作。不可下载或校验失败不停止旧程序；启动失败尝试切回已有完整 release。新进程 ready 不能只靠文件存在或 PID：必须验证出生时间与 IM 注册。相同版本和新目标的并发请求均按操作身份处理。

包内 data_epoch 声明是发布约束，不自动推断数据库迁移可逆性；跨 epoch 不提供按钮升级。本 unit 未授权发布 GitHub Release 或部署生产，交付 PR 与真实隔离验收。发布测试使用受控下载 transport 供相同安装逻辑读取真实候选 tar 包，不放宽产品固定 GitHub URL 校验；验证记录明确 fixture 边界。

## Runbook for Reviewer

| 服务 | 停止 | 启动 | 健康检查 |
|---|---|---|---|
| 隔离 IM/Node/DSH | ./scripts/e2e-down.sh --wt <unit-worktree> | PATH=<main>/.venv/bin:$PATH ./scripts/e2e-up.sh --wt <unit-worktree> | 从 .e2e-ports.env 读 IM_URL 后 GET /health；pa status 指定隔离 config |
| 受管安装更新验收 Node | 安装记录中旧/新 CLI stop --config <isolated-path> | 安装器 NANO_INSTALL_ROOT=<isolated-root> NANO_INSTALL_AUTOSTART=0；Node/DSH 不监听端口 | IM 节点版本/状态 + 实际进程身份 |

**Review 驱动方式**：端到端真栈、真实 Web 客户端。必须点更新、取消、重试，观察消息等待与恢复，桌面及手机对照原型。版本包/下载故障为受控分发 fixture，Node、DSH、IM、消息数据库和更新子进程真实运行。

**验收前置**：worktree Node/pnpm 依赖、Web build、主仓 .venv 的 PyYAML/httpx、默认隔离账号 nano/nano1234、受控候选包和下载 transport；已有本地模型代理/受控模型 fixture 用于可重复的忙碌/回复条件，不调用个人助手或外发真实消息。独立 reviewer 接手前在 M1 evidence 记录端口、命令、版本和 fixture 边界。用户另要求真实操作录屏，视频保存在 output/playwright/，交付绝对路径，不提交缓存。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-update | 按钮发起的电脑端更新闭环 | 无 | 单一集成 | apps/node、apps/im-server、product-contracts、dsh-integration、PA 的安全空闲 seam、Web nodes/chat/i18n、发布构建及测试文档 | [reviewer] R1 首文档全部场景通过，设备身份、版本说明与动作可辨认；R2 下载继续工作、忙碌等待可取消、切换排队消息且刷新保留、恢复无重复；失败结果真实、旧版桥接与源码部署可区分。[worker] W1 桌面/手机真实截图及原型对照、用户要求的真实操作视频；W2 元数据/授权隔离/并发取消/安全屏障（child、Workflow、Cron、后台 review）/校验失败/启动失败回退/真实进程切换及消息幂等有相关测试；W3 包构建、typecheck、后端/前端回归、架构约束、docs-check 与适用本地 CI 通过。 |
