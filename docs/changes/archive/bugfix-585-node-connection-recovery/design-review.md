# bugfix-585 Design Review

## Round 1

### Metadata

- reviewer target: `/root/design_review`，独立于首文档与设计作者。
- review_mode: `full`
- mode_reason: 首次 Gate 2；完整核对需求、当前产品装配、设计、delta 与 milestone。
- started_at: `2026-10-12T18:08:00+08:00`
- completed_at: `2026-10-12T18:11:58+08:00`
- duration: 3 分 58 秒
- baseline: `main` / `649e80311`；审查 working-tree 中冻结的 incident、design、两个 delta 与 `M1-recovery/.gitkeep`。未修改其他 dirty/untracked 内容。

### Verdict

**Issues Found — 0 CRITICAL / 2 WARNING**。

连接恢复与诊断的核心职责划分可实施；页面状态消费者尚未闭合，验收前置仍把已可确定的入口推迟到实施交接，当前不能放行。

### Coverage 与证据

- **现状与根因**：从真实 `createServer` guard（`apps/im-server/src/server.ts:319–325`）、`registerSockets` 与 `Gateway` 核实：超时调用 `revokeNode`；后者先删除连接，close handler 的当前实例判断因而跳过 offline 落库与广播（`gateway.ts:138–143,1000–1011`）。Channels close 1008/4003 进入 revoked，1012 则复用现有退避恢复（`packages/channels/src/index.ts` 的 connect/disconnect）。incident 的当前 RCA 成立；未将旧 Python 事故归因为 Cloudflare 或休眠。
- **恢复与用户约束**：复用现有 generation、取凭据、注册 ACK、指数退避与 request delivery 分类是合理的最小改动。统一清理应由 IM 持有，不能由 Channels 修改中心状态；当前实例 fencing 保留替换连接安全性。用户明确排除离线提交/补投递；设计保留传输不重放与 Node 既有 recover hooks，未增第二套恢复队列。现有 Relay 测试确有 ACK 超时与不重放覆盖，但没有真实 IM guard 链路，新增跨边界回归有必要。
- **撤权与轨迹**：实际账户停用和设备恢复入口调用 `revokeOwner/revokeNode`（`identity-routes.ts:211,260`）；保留终态关闭且统一 offline 清理符合 R3。`trajectory.closeDevice` 与 Node 非 ready 的 `trajectory.closeAll` 都是实际装配路径，设计要求保留合理。
- **诊断责任**：Channels 产生有类型、受限字段的生命周期事件，Node 决定持久输出，不新增跨包依赖；相较新日志服务，这一复用没有额外运维负担。现有 Node `reportError` 会打印 stack（`apps/node/src/main.ts:46`），因此新增安全事件不能把原始远端 Error 直接接进去；设计已明确白名单、固定摘要与 callback 隔离。`apps/node/src/lifecycle.ts:154,281–302` 证明托管 stderr 已有持久日志。
- **前端与验收**：Nodes 页和 Chat 消费 node 状态，但 Agent detail 消费另一事件，见 R1-W1。无布局、文案或新交互设计，当前不要求额外 prototype；这不免除真实浏览器对原有状态和编辑体验的验证。本轮未进行实现验收或声称视觉验证通过。
- **Delta**：两个文件镜像正确 canonical target。IM MODIFIED 保留注册 owner 隔离、超时 offline 与重复扫描幂等的既有 Scenario，追加恢复/旧连接情形；Gateway ADDED 面向使用者与维护者，非内部实现清单。IM 的页面承诺仍受 R1-W1 阻塞。
- **Milestone**：单个 M1 和实际 `.gitkeep` 存在；改动落点集中且无并行冲突。真实 guard + socket + 临时 DB 测试、真实 Agent 回复、撤权、日志脱敏和浏览器证据的层次合理。R2 应明确实际页面覆盖，Runbook 应先落实资源与命令，见下述问题。

### 历史问题闭环

无；这是首轮审查。

### Issues

#### R1-W1：仅沿用 node.status_changed 无法兑现 Agent 详情页的真实状态

- 位置：`design.md:11,29,37,54,62`；`specs/im/agents-nodes.md:7–19`。
- 证据：IM 当前仅在注册/close 广播 `node.status_changed`（`apps/im-server/src/gateway.ts:300–305,1005–1009`）；心跳分支只更新数据库。Agent detail 挂载 `useAgentStatusBroadcastConsumer`（`agent-detail-page.tsx:1277`），该消费者在 `agent-status-ws-consumer.ts:35` 排除 node 事件，只接受 `agent.status_changed`；detail query 无周期刷新（`:1295–1299`），顶部读取 draft 的 `node_status`（`:1518`）。因此浏览器用户流保持连接时，节点掉线仍可在已打开详情页持续显示 online。
- 要求：设计明确状态事件的生产/消费闭环，至少覆盖 Nodes、Chat 和 Agent 详情现有在线标识，并在 M1/R2 写出实际页面验收。可由 IM 复用现有 owner 广播，为关联 Agent 发布已有 `agent.status_changed`，不必新建 UI；也可选择等价的小范围消费者修复，但要锁定方案。
- 相关现有约束：若补发 Agent 事件，不能仅验证 badge。当前 handler patch detail cache 后，`agent-detail-page.tsx:1301–1306` 会把整个 config 重新写入 draft；用户尚未保存的编辑会被状态事件覆盖。应在设计中同时说明保留草稿的落点，并验证“编辑未保存时 offline/online 更新仍保留输入”。这是补齐 producer 后直接触发的现有路径，不是新增编辑需求。
- 未修后果：R2 的“已打开页面不显示假在线”不能成立；简单补 producer 又可能带来用户编辑丢失。

#### R1-W2：Runbook 尚未收敛到已存在的 TypeScript 验收入口和资源

- 位置：`design.md:19,52–56`。
- 证据：`scripts/e2e-up.sh:223–292` 已构建检查并启动 TypeScript IM、通过 Node CLI bind/start、创建测试账号和验证 owner 对齐的节点在线，非假设中的旧 Python 接线。默认来源明确为 `config/e2e/gateway.yaml`，含隔离测试身份、`deepseek:deepseek-v4-flash` 与本机 4000 proxy。Node CLI 实际写 config 同目录 `gateway.log`；设计的 `.gateway.log` 断言沿用了脚本旧注释。Runbook 未列构建、浏览器启动/入口和健康检查命令，也未给出有效模型/浏览器资源的核实依据，而将准确命令和专用账户推迟交接。
- 要求：删除未经验证的 Python fallback，收敛到现有 e2e-up/down；写明必要构建、隔离启动、前端入口/健康检查、停止命令及 fixture 来源，记录真实 LLM proxy/模型与浏览器的可用性依据。无需新增运维脚本或在 Gate 2 提前完成整套产品验收。
- 未修后果：产品 reviewer 仍需重新决定启动路径、身份与模型；R1 真 Agent 回复和 R2 浏览器验收的必需资源没有在 Gate 2 落实，违反 prototype-and-runbook 的验收前置要求。

### Recommendations

- **R1-R1（可选）**：在注册恢复时同时清除旧 `last_error`，并将 milestone 的“重新投递”改为“恢复后新消息投递”，避免实现者误读为新增离线补投递。当前注册 SQL 不清 `last_error`，要到下一次 heartbeat 才清除；这不改变 offline/online 核心决策，但明确后更容易核对恢复结果。

### Author Resolutions

- R1-W1 accepted：设计锁定由 IM 广播关联 Agent 状态，并在 detail 的 config 同步区分仅状态变更与真实配置变更；M1/R2 覆盖 Nodes、Chat、detail 和未保存草稿。无视觉结构变化。
- R1-W2 accepted：runbook 收敛到已验证的 TypeScript e2e-up/down；补构建、静态前端入口、健康检查、测试身份/目录、proxy 实际模型响应与 IAB 可用性。修正日志名 gateway.log。
- R1-R1 accepted：注册清 last_error，事件显式 null；M1 用“恢复后新消息投递”避免补投递歧义。

## Round 2

### Metadata

- reviewer target: `/root/design_review`，与 R1 相同的独立 reviewer。
- review_mode: `full`
- mode_reason: 原计划按修订 delta 复核；实际修订增加 IM 的 Agent 状态生产及 frontend 草稿同步职责，M1 范围也相应扩展，故按技能规则扩大为 full。沿用仍有效的 R1 源码证据，重新核对变化及其真实装配入口。
- started_at: `2026-10-12T18:14:15+08:00`
- completed_at: `2026-10-12T18:14:44+08:00`
- duration: 29 秒
- baseline: `main` / `649e80311`；本轮冻结版本为含 R1 Author Resolutions 的 design 与 IM delta，incident 和 Gateway delta 未改变。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING**。

状态事件和草稿设计已闭合；Runbook 的隔离目录与静态资源路径仍需修正。

### Coverage 与证据

- incident 的 R1–R4、非目标、超时错误关闭码与清理顺序 RCA 没有改变；重新核对 design 与 Gateway delta，恢复、权限终态、诊断安全和不新增离线补投递仍与 R1 所核实际路径一致。
- IM 继续持有状态权威并通过现有 owner 广播发布两类现有事件；frontend 只保留编辑草稿并消费状态，没有新增第二份连接状态权威。与引入轮询或新事件总线相比，复用当前 event/cache 更直接。
- Agent detail 的实际同步入口再次核对于 `agent-detail-page.tsx:1295–1306`。以相邻服务端 config 判断仅状态变化，并仅 patch draft.node_status，可保留未保存字段；真正配置变化继续原有替换语义。现有组件按 agentId remount，设计无需新增跨 Agent 草稿机制。无新视觉结构或交互，不要求额外 prototype；真实浏览器验收仍归 M1。
- IM delta 保留原有注册/超时/owner 隔离 Scenario，加入未保存编辑结果，与新的 M1 范围和退出条件一致。Gateway delta 无新变动。
- Runbook 已给构建、健康检查、测试身份、模型、停止命令；模型与 IAB 前置采用 author 当前回合实际探测证据，不要求重复模型调用或提前实现验收。独立核对脚本/服务入口时发现 R2-W1 的可执行性问题。
- M1 仍是单 milestone，无并行写冲突；前端增量测试复用已有 suite，真实扫描测试与产品验收分工保留。注册清 last_error 与恢复后新消息措辞均明确，不再有新增补投递歧义。

### 历史问题闭环

| 原问题 | Author Resolution | 本轮核对 | 状态 |
|---|---|---|---|
| R1-W1 | IM 补关联 Agent 事件；detail 仅状态变化保留草稿；扩展页面验收 | design 关键决策、IM delta 新 Scenario、M1 与测试归属均已覆盖实际 producer/consumer 和 draft 同步点 | closed |
| R1-W2 | 收敛脚本并补入口、身份、资源与日志名 | 资源/命令主体已补；隔离目录缺少创建且静态路径仍按新 cwd 解析，见 R2-W1 | still-open |
| R1-R1 | 注册清错误，明确恢复后新消息投递 | design 状态决策及 M1 已采纳 | closed |

### Issues

#### R2-W1：隔离启动命令尚不能提供 Runbook 声明的静态页面

- 位置：`design.md` 的 Runbook 命令块；承接 R1-W2。
- 证据：`scripts/e2e-up.sh:113` 对 `--wt` 参数直接 `cd`，当前命令之前没有创建 `.runtime-585`，全新 worktree 会直接失败。即便手动创建，脚本 `:231–236` 将 IM 的 cwd 设为该目录；`apps/im-server/src/server.ts:247–251,282–284` 默认从进程 cwd 解析 `src/IM/frontend/dist`，找不到 index 时重定向到 `127.0.0.1:4173`。Runbook 在 worktree 根构建了前端并明确不启动 Vite，但没有提供 `IM_FRONTEND_DIST_DIR`，因此根目录构建不会被隔离 IM 找到。
- 要求：启动前创建隔离目录，并向脚本传递 worktree 根的绝对 `IM_FRONTEND_DIST_DIR`；若需要轨迹资源也提供对应绝对资源目录。页面健康核对至少确认 `$IM_URL/` 返回构建后的 HTML 且不跳转到未启动的 Vite。保持现有 e2e-up/down，不需要新增启动机制。
- 未修后果：首次启动失败，或 API /health 正常但真实浏览器无页面，R2 必验旅程仍无法按交接命令执行。

### Recommendations

无新增。

### Author Resolutions

- R1-W2 accepted：已核实 server.ts 默认静态路径相对 cwd；runbook 先 mkdir -p .runtime-585，再以绝对 IM_FRONTEND_DIST_DIR 启动，保证隔离目录与浏览器入口实际可用。仅此两行命令改动，其余设计冻结。

## Round 3

### Metadata

- reviewer target: `/root/design_review`，继续由原独立 reviewer 核实闭环。
- review_mode: `closure`
- mode_reason: 本次只补隔离目录创建及静态资源绝对路径；需求、职责、接口、delta 和 M1 均未改变，仅需核实 R2-W1 / R1-W2。
- started_at: `2026-10-12T18:16:00+08:00`
- completed_at: `2026-10-12T18:16:07+08:00`
- duration: 7 秒
- baseline: `main` / `649e80311`；受审版本含 R2 Author Resolutions 及两行 Runbook 修订。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**。

### Coverage 与证据

- `retained_from: Round 2`：R1–R4 需求覆盖、恢复/撤权/诊断职责、状态事件与草稿保护、delta 和 M1 均未变化，保留 R2 的完整设计核对；R1-W1 与 R1-R1 的 closed 结论有效。
- 本轮直接复核 Runbook 命令及真实脚本链：先 `mkdir -p .runtime-585` 满足 `e2e-up.sh:113` 的即时 cd；启动命令在 worktree 根展开绝对 `IM_FRONTEND_DIST_DIR`。脚本 `:231–236` 保留传入环境并以 `env:process.env` 传给 IM 子进程；`server.ts:247–249` 优先读取该变量。因此 IM 即使以隔离目录为 cwd，也会读取本次 worktree 的前端构建。
- 构建、身份、模型/IAB 前置、实际浏览器旅程及清理仍沿用 R2 已核实方案。此结论是设计可实施性放行，不是产品实现或真实恢复验收；M1 仍须证明页面、消息、权限及持久日志结果。

### 历史问题闭环

| 原问题 | Author Resolution | 本轮证据 | 状态 |
|---|---|---|---|
| R2-W1 / R1-W2 | 先创建隔离目录，再传绝对 IM_FRONTEND_DIST_DIR | Runbook 命令、脚本参数处理/子进程环境继承、服务静态路径解析均闭合 | closed |

### Issues

无。

### Recommendations

无新增。

## Round 4

### Metadata

- reviewer target: `/root/design_review`，原独立设计 reviewer。
- review_mode: `delta`
- mode_reason: 本轮新增既有 service-lifecycle Requirement 的替换 delta，并校正 IM 广播措辞；有界契约修订超出纯问题 closure，但未改变首文档、技术决策、职责边界或 milestone。
- started_at: `2026-10-12T18:30:51+08:00`
- completed_at: `2026-10-12T18:31:12+08:00`
- duration: 21 秒
- reviewed checkout: `/Users/czj/.codex/worktrees/bugfix-585/nano-multiagent`，branch `codex/bugfix-585`。
- validated_at: `48287332f5979e0c7aa5fa736aa67d0a2b0fcd4e` 加本轮冻结文档修订；未修改产品代码。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING；Gate 2 retained。**

### Coverage 与证据

- `retained_from: Round 3`：其继承的 R2 技术方案和 R3 Runbook 结论继续有效。核对本轮 design diff，只有 Changelog 与 canonical target 列表改变；incident 相对当前 HEAD 无修改，M1、关闭语义、状态生产/消费、草稿保护、安全诊断及运行前置均未改变。因此不重启完整设计审查，也不把本轮当作实现/产品验收。
- **权威落点**：canonical `docs/specs/gateway/service-lifecycle.md:219` 已完整持有重连行为；新 delta 以 REMOVED 精确匹配旧 Requirement 标题，并以 ADDED 给出更名后完整条目。relay-protocol delta 删除重复恢复条目，只保留独立的持久诊断契约，消除了两处相互矛盾的长期权威。
- **范围与依据**：旧“补发未确认帧”和“保留未受影响队列”与 R1 已核实的 TypeScript 实现不符。当前 `packages/channels/src/index.ts:268–310` 仍在断连时将 active 结算为 unknown、queue 结算为 not-sent 并清空，再按有上限退避重连；`packages/channels/tests/web-relay.test.ts` 的既有重连测试明确断言不会重放已发送或排队帧。本轮契约表达的是既有、已批准的传输边界，不是新增取消业务持久恢复的决定；新文字显式保留 PA 自身持久恢复。
- **Scenario 保留**：逐项对比 canonical 原条目与新 delta，慢控制面、正常 ACK 时限、指数退避、匹配响应/FIFO、外部 IM 自治这五个原 Scenario 正文保持不变；只有未确认帧重放、control rejection 队列处置两项按既有不重放设计校正。临时中断恢复与权限终止从原 relay delta 迁入，用户验收范围未扩展。
- **IM 措辞**：新文字区分心跳更新数据库与上下线转换广播。实际 heartbeat 分支 `apps/im-server/src/gateway.ts:359–364` 只落库，`publishNodeStatus` 由上线注册与当前连接清理调用。此消歧与原 design 的“上线/离线转换”一致；owner 隔离、Agent 同步状态、旧连接 fencing 和未保存输入保证均原样保留。
- **职责判断**：恢复及投递边界继续归传输 owner 与 PA 各自承担，IM 继续持有节点可见状态，未新增机制、依赖或后台队列。没有要求把本 unit 扩大为其他迁移遗留文档的全面清理。

### 历史问题闭环

R1-W1、R1-W2 / R2-W1 及 R1-R1 的已关闭结论 retained；本轮未改动对应解决方案，没有重新打开的问题。

### Issues

无。

### Recommendations

无新增。后续 corrected-delta verifier 仍按实际实现与测试核对最终归并版本；本轮只确认设计 Gate 2 在这次文档修订后继续有效。

## Round 5

### Metadata

- reviewer target: `/root/design_review`，原独立设计 reviewer。
- review_mode: `delta`
- mode_reason: 对实际产品验收发现的 HTTP recovery / WS resume 状态缺口补充局部 IM 行为；本轮只审订阅恢复后的当前状态补发，以及关联消费者、身份与 cursor 边界。
- started_at: `2026-10-12T18:39:50+08:00`
- completed_at: `2026-10-12T18:40:27+08:00`
- duration: 37 秒
- reviewed checkout: `/Users/czj/.codex/worktrees/bugfix-585/nano-multiagent`，branch `codex/bugfix-585`。
- validated_at: `684122882` 加冻结的订阅恢复设计、IM delta 与待实施的真实 socket 回归；本轮未修改产品代码或其他文档。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。** 本次订阅恢复增量可以实施；其余 Gate 2 Approved 结论 retained。

### Coverage 与证据

- `retained_from: Round 4`：Gateway 恢复/撤权/投递边界、诊断、canonical 落点和首文档范围未改变。本增量兑现既有 R2 的“已打开页面状态真实”，没有新增离线业务、持久事件系统或新 milestone。
- **根因与实际装配**：`user-stream-runtime.ts:320–357` 在建 WS 前先 sync 并等待各页面 onRecovery；Nodes 的 onRecovery 刷新 HTTP cache。IM `Gateway.broadcast` 跳过尚未 ready 的浏览器，而 `replay` 当前只回放 conversation_events 后设 ready。节点状态帧不进该表，故 HTTP 完成到 resume 生效之间的注册确会永久丢失这次通知。新增 `node-connection.test.ts:70–78` 用真实 socket 在 open 后、resume 前等待真实 Relay 注册，正好约束该窗口；本轮核对其测试构造和当前源码，不宣称重新执行了 author 已报告的红测。
- **设计闭环**：由 IM 在现有同步 replay 尾部对该 socket 补发 owner 当前节点/非 stale Agent 状态，能覆盖 resume 前已发生的变化；进入 ready 后仍由现有实时广播覆盖后续变化。现有 replay、数据库读取和 WS write 调用都是同步路径，无需新增异步队列或定时轮询。实现应保持这一连续时序，复用现有字段语义，包括 node 的 last_error/null 与 last_heartbeat_at。
- **权限与投递范围**：resume 入口和默认 replay timer 已检查 browserValid；当前用户来自已消费的认证 ticket。状态查询按该浏览器 owner 限定，Agent 同时限定节点归属与非 stale；输出直接写该 socket，不能借 owner broadcast 把每次 resume 快照扩散到其他已在线浏览器。该限制与设计的“向该浏览器”一致，外租不会收到快照。
- **cursor / 聊天隔离**：复用不带 event_id 的现有状态 envelope，符合客户端 `parseEvent` 和 `dispatchFrame`：无 eventId 的帧仍交付消费者，但不参与 cursor 去重或推进。保持原历史回放/cursor/resync 逻辑，状态快照不写 conversation_events；这里的补发是当前 presence，不是离线消息或业务帧重放。
- **现有消费者与编辑保护**：Nodes、Chat、Agent detail 已消费对应事件；状态快照不需新协议或页面结构。Nodes 的现有状态处理也 patch 草稿的只读状态字段，Agent detail 沿用前轮批准的仅状态更新保护，故本方案不要求第二轮 HTTP 替换整个编辑表单。
- **Delta 与验收**：IM delta 新增“浏览器恢复订阅时补齐错过的状态”Scenario，保留其余条目，目标 canonical 不变。既有 M1 的真实页面 R2 与跨 socket/owner 验收可承载这次增量；实施后须跑新增回归并复验真实 IM 重启时已打开 Nodes/Chat/Agent detail 收敛，而非只看 API。新观察到的隔离验收模型切换记录不改变设计边界，真实模型回复结果仍由产品 reviewer 核实。

### 历史问题闭环

R1–R4 已关闭问题保持关闭；本轮订阅恢复问题是新发现的同一 R2 旅程缺口，已由本次增量明确处理，不以此前 Approved 代替其审查。

### Issues

无。

### Recommendations

无新增。
