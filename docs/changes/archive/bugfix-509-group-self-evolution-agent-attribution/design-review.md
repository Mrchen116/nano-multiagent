# Design Review: bugfix-509-group-self-evolution-agent-attribution

## Round 1

### Metadata

- reviewer: `/root/bugfix_509_design_reviewer`
- review_mode: `full`
- mode_reason: `Round 1; first independent Gate 2 review requires full mode.`
- started_at: `2026-08-06T16:47:21+08:00`
- completed_at: `2026-08-06T17:04:43+08:00`
- duration: `17m 22s`

### Verdict

Issues Found — 2 CRITICAL / 1 WARNING

### Coverage

- 输入完整读取：`incident.md`、`design.md`、三个 `specs/**` delta、`prototype.html`、M1/M2 空目录骨架。
- current contract 核对：`docs/specs/im/gateway-relay.md`、`docs/specs/im/web-chat-ux.md`、`docs/specs/im/conversations-messages.md` 及 specs 编写规则。
- 生产正向路径核对：Gateway composition → background subscription → session-event callback → IM connection → authenticated dispatcher → `GatewayRelay` → message repository / user stream → Web IM reducer / `MessagePane`；另查 direct-chat fork copy 与 Agent profile/user 显示名写路径。
- 运行与原型核对：review runbook 的脚本参数、隔离配置、依赖与健康检查可用；原型覆盖 group/direct、zh/en、三类 targets、desktop/mobile，且未把原型控制条泄漏为生产需求。
- 本轮为 `full`：下列台账覆盖全部现状断言、编号决策、incident 澄清/根因/不变量/Requirement/Scenario/范围与非目标、所有 delta Requirement/Scenario 与两个 milestone，并执行四角度架构进攻。

### 核实台账

#### 1. 现状断言

| ID | 原子 | 本轮核实与证据 | 结论 |
|---|---|---|---|
| S1 | Kernel 已发布结构化 review event，本 unit 不必改 hook | `src/agent/platform/hooks/builtins/self_improvement.py:242-255` 已发布 `reviewed_skills`、`reviewed_memory`；生产消费通过 SDK stream。 | 成立 |
| S2 | subscription request 有 `agent_id`，callback 丢失它 | `src/personal_assistant/gateway/background_subscriptions.py:24-38,63-68,167-175` 保存 identity，但 callback 仍只有 context/event。 | 成立 |
| S3 | Gateway 固定英文且仅发 conversation/text | `src/personal_assistant/gateway/runtime_delivery/background.py:40-77` 正是该逻辑。 | 成立 |
| S4 | `node.system_message` 只落库、不发 canonical created | `src/IM/ws/gateway/relay.py:392-434` 直接 `create_message`，未开启 `emit_created_event`。 | 成立 |
| S5 | domain/DB/repository/REST/live projection 当前无 notice | `src/IM/domain/models.py:275-305`、`src/IM/infra/db.py:116-137`、`src/IM/infra/repositories/messages.py:65-82`、`src/IM/infra/repositories/_message_projection.py:55-79`、`src/IM/api/routes/messages.py:150-173` 都没有该字段。 | 成立 |
| S6 | IM 已有 Agent/user/conversation identity primitives | `src/IM/infra/gateway_persistence.py:301-356` 有 profile/user/conversation repositories 和 synthetic user/participant 查询；source membership 仍需本 unit 新增严格校验。 | 成立 |
| S7 | Web IM 历史/实时/type/pane 是真实消费链 | `chat-types.ts:135-162,229-234`、`chat-stream-reducer.ts:221-265`、`message-pane.tsx:1264-1402`；`chat-workspace-page.tsx:1088-1108` 在生产路由传入 `isDirectChat`。 | 成立 |
| S8 | 浏览器 i18n 是当前语言权威 | `src/IM/frontend/src/i18n/index.ts:7-46` 从 browser storage 初始化并即时切换；服务端没有等价的当前-tab语言。 | 成立 |
| S9 | Kernel/IM 依赖边界 | 根 `AGENTS.md` 的架构红线与当前 `composition.py:480-540` 均保持 PA 通过 SDK/WS 组装，IM 未 import Kernel。 | 成立 |
| S10 | system row 仍应为低层级非第一人称消息 | `message-pane.tsx:1285-1287` 只渲染 content；`src/IM/frontend/src/styles/global.css:1700-1706` 是居中 system 行。 | 成立 |
| S11 | Coding CLI 是独立 formatter | `src/coding_cli/events/background_runs.py:70-96` 自行格式化 review event，目标调用链不经过 PA callback。 | 成立 |
| S12 | nullable JSON migration 可兼容旧行 | `src/IM/infra/db.py:584-645` 已有 nullable JSON column migration 模式；旧 Message row 映射在 `messages.py:1104-1154` 可按 optional 字段扩展。 | 成立 |
| S13 | 服务端持久化单一语言会与即时切换冲突 | `i18n/index.ts:29-46` 的语言切换在当前浏览器发生，支持 design 的 browser-side rendering。 | 成立 |
| S14 | dist 与截图约束 | 根 `AGENTS.md` 明确 `src/IM/frontend/dist/` 不提交；prototype/evidence 仅是评审输入。 | 成立 |
| S15 | 复用现有 system row，而非新 timeline item | system message 已有完整 REST/timeline path；另一路 `agent.config.changed` 在 `chat-types.ts:169` 与 reducer `:267-270` 带独立 anchor 语义，不能等价复用。 | 成立 |
| S16 | 复用 JSON sidecar 链 | attachments/tool calls/thinking 已经贯穿 `Message`、repository、projection 与 frontend type；新增单一 optional field 不需要新存储框架。 | 成立 |
| S17 | 复用 `emit_created_event` | `MessageRepository.create_message` 已暴露该参数（`messages.py:65-82`），canonical payload 由 `_message_projection.py:55-79` 构造。 | 成立 |
| S18 | identity resolver 自然归 GatewayConversationPersistence | 该类已同时持有 conversation/profile/user repos（`gateway_persistence.py:301-310`），且 authenticated node 由 dispatcher 在 `src/IM/ws/gateway/sessions.py:347-391` 绑定。 | 成立，但显示名权威有歧义，见 R1-W1 |
| S19 | 前端 shared formatter + i18n key 是既有模式 | `MessagePane` 已持有 `useTranslation()`，message-created 的统一 `Message` 归并已存在；无需解析 fallback text。 | 成立 |
| S20 | 独立 config boundary 不适用 | `agent.config.changed` 具有 `before_message_id` 锚点和独立 timeline item（`chat-types.ts:169,230`），删除该新 sidecar 方案而复用 boundary 会扩大 fork/分页契约。 | 成立 |
| H1 | feat-349 的当前遗产是 per-agent event + meta/system delivery | hook 与 `composition.py:480-492` 的生产 wiring 仍保留该形态。 | 成立 |
| H2 | bugfix-399 后为每 session 单一 subscriber/replay anchor | `background_subscriptions.py:77-92` 按 session 去重；`background_session_events.py:173-188` 按 sequence 续读。 | 成立 |
| H3 | bugfix-404 已建立 durable created seam | repository 已支持 `emit_created_event`，当前 agent output 的实时投影使用 canonical message event；system relay 尚未接入。 | 成立 |
| H4 | feat-397 参与者关系可作为群聊归属权威 | `conversation_participants` 是真实 schema（`db.py:108-112`），conversation repository 持久维护该集合。 | 成立 |

#### 2. 编号决策

| 决策 | 拍板/歧义/自洽/spec 驱动核实 | 结论 |
|---|---|---|
| D1 optional `system_notice` sidecar | 选择、拒绝项、compatibility 与 owner 均已拍死；由轻量 system、不伪造 agent 消息、动态 i18n 驱动。现有 fork 消费者未纳入数据链，见 R1-C2。 | 方向成立，完整性不通过 |
| D2 浏览器用完整句子 key | 语言权威、三类 targets、direct/group 六种句式与旧客户端 fallback 清楚，和 Q2/Q3 一致。 | 成立 |
| D3 IM 校验 node/membership 并快照名 | trust boundary 与改名后历史稳定性明确；但 current profile/user 两份 display name 可能漂移，文档未拍死当前名称取哪份，见 R1-W1。 | 部分成立 |
| D4 durable write + canonical created | durable-before-live 的方向正确；“message id 去重足够，不另加 dedupe”与现有 ACK 重试语义冲突，且 error ACK 无法被当前 callback 观察，见 R1-C1。 | 不成立 |
| D5 unknown/legacy fallback，CLI/Kernel 不动 | recognized notice 的进入条件、旧行正文回退和边界明确；符合非目标。 | 成立 |

#### 3. Incident 约束

| ID | Incident 原子 | Design 落点与本轮判断 |
|---|---|---|
| Q1 | 仅群聊显示 Agent；IM direct/CLI 不显示 | D2/D5 + formatter `isDirectChat` 分支与 CLI no-delta 覆盖。 |
| Q2 | 保持轻量 system，注意 i18n | D1/D2、prototype P1/P2 覆盖。 |
| Q3 | 所有 IM notice 随当前 UI 语言 | D2、REST/live 同一 sidecar 与语言切换场景覆盖；fork copy 缺口会破坏“所有 IM”，见 R1-C2。 |
| RCA1 | identity 在 subscription callback 边界丢失 | S2/S3 已由生产路径证实；D3 回补。 |
| RCA2 | semantic 被压成英文，IM/frontend 仅处理正文 | S3-S8 已证实；D1/D2 治到结构化语义。 |
| INV1 | skill/memory per-agent 隔离不变 | hook/写入不改，只有展示 sidecar。 |
| INV2 | 仅一行轻量 meta/system | D1 + prototype P1 保持。 |
| INV3 | 不伪装 agent 第一人称 | `sender_type=system` 保持。 |
| INV4 | 后台沉淀/通知失败不打断当前对话 | D3 风险段声明，但当前 ACK 观察契约不闭合，见 R1-C1。 |
| R1 | 群聊 notice 显示真实来源 Agent 与更新对象 | D3 + group formatter + M2 覆盖。 |
| R1-S1 | 单个 Agent memory notice 可明确归因且非 agent bubble | D2 表格、D3 snapshot、P1/M2 reviewer exit 覆盖。 |
| R1-S2 | 两个 Agent 连续更新分别归因 | snapshot 随每条 Message 持久化，M2 group E2E 覆盖；重试重复风险见 R1-C1。 |
| R2 | group/direct 全部 notice 按 UI 语言，三类 targets | D2 六句 key、target mapping、P2/M1 覆盖。 |
| R2-S1 | 中文界面中文，群聊带来源 | delta + P2/M1/M2 覆盖。 |
| R2-S2 | 英文界面英文，群聊带来源 | delta + P2/M1/M2 覆盖。 |
| R2-S3 | 实时、刷新、重进归因/targets/语言一致 | durable sidecar + REST/created 同 formatter 覆盖；fork 是另一个既有入口，遗漏见 R1-C2。 |
| R3 | direct 不重复名；CLI 不变 | D2/D5 与 no CLI delta 覆盖。 |
| R3-S1 | direct 只本地化、不显示 Agent 名 | `isDirectChat` formatter contract 与 M2 exit 覆盖。 |
| R3-S2 | Coding CLI 行为不变 | 目标文件/测试明确排除，S11 证实路径独立。 |
| IN1 | group attribution | D3/M2。 |
| IN2 | group/direct zh/en | D2/M1。 |
| IN3 | live + history reload | D4/REST-live projection；但 R1-C1 会让 reconnect 重复。 |
| IN4 | skills/memory/both | mapping 与六句 key。 |
| NG1 | 不改 CLI | D5/no delta。 |
| NG2 | 不改成 agent message | D1。 |
| NG3 | 不改 self-evolution 执行与隔离 | hook/kernel no delta。 |
| NG4 | 不扩成通用 system-message 平台 | narrow `SystemNotice` kind，普通 message optional NULL。 |
| NG5 | 不回填历史英文 | nullable migration + fallback。 |
| NG6 | 历史不随 Agent 改名；新行使用当时正确名称 | snapshot 策略覆盖历史；“当时正确”来源未消歧，见 R1-W1。 |

#### 4. Delta specs

| ID | Delta 原子 | 设计覆盖与消费者可观察性 |
|---|---|---|
| G-REQ | Gateway 向 IM 保留 source id + targets，不改 CLI | callback contract、wire payload、target mapping、CLI no delta 覆盖。 |
| G-S1 | group source 与 targets 结构化保留 | D3 + mapping 覆盖。 |
| G-S2 | direct 走同一结构化路径 | D1 wire contract 与 direct formatter 覆盖。 |
| G-S3 | 断线/拒绝/持久化失败可诊断且不影响后台/前台 | 不打断已声明，但 current enqueue API 无法把 negative ACK/timeout 交回 callback；见 R1-C1。 |
| I-REQ | IM 校验 node/membership、快照、持久化并实时发布 | D3/D4 覆盖。 |
| I-S1 | 合法来源持久化，浏览器实时收到完整 notice | D4 主流程；幂等缺口见 R1-C1。 |
| I-S2 | REST 与实时返回同一 snapshot/targets | 单一 Message sidecar 与 projection contract 覆盖。 |
| I-S3 | invalid node/conversation source 稳定拒绝且不写/不发 | D3 风险/ingress contract 覆盖。 |
| I-S4 | legacy system content 兼容 | D1/D5 + nullable migration。 |
| W-REQ | 当前语言 + conversation kind 决定轻量 system 行 | D2/formatter/P1-P3 覆盖。 |
| W-S1 | 中文群聊显示来源与 memory 意义 | D2 文案表 + M2。 |
| W-S2 | 英文群聊连续多个 Agent 分别归因 | per-message snapshot + M2 E2E。 |
| W-S3 | direct 本地化且不重复 Agent 名 | direct branch。 |
| W-S4 | live/reopen/language switch 复用同一语义 | REST/live same object + browser formatter；fork copy 仍缺，见 R1-C2。 |
| W-S5 | 修复前旧历史不改写 | NULL/unknown fallback。 |
| Δ-usage | 三个 target 都使用 ADDED，无 MODIFIED/REMOVED | canonical 中不存在同名/同义既有 Requirement；这是平行新增的窄行为。各 THEN 都是 Gateway consumer、IM client、Web user 可观察结果，没有实现函数断言。 | 用法成立 |

#### 5. Milestones

| Milestone | 拆分/交集/退出标准核实 | 结论 |
|---|---|---|
| M1 localized-system-notice | 设计明确给出 16–20 文件、500–750 行的单 worker 窗口证据；M1 端到端交付 direct/group notice 的结构化、实时、zh/en 语义，reviewer/worker 两轨齐全。 | 成立；R1-C1/R1-C2 修订后需把相应 backend/fork 回归纳入范围 |
| M2 group-agent-attribution | 串行依赖 M1，不属于同组并行冲突；交付 group name/direct no-name 与 desktop/mobile 可观察价值，P1/P3 和测试矩阵可验。 | 成立；display-name authority 需先按 R1-W1 拍死 |

### 整体判断

- 上层表达清楚：总览、图和五条一句话决策足以让人快速理解“Gateway 留语义、IM 校验/快照、browser 本地化”的主线，未被实现步骤淹没。
- 分层和主要生产落点正确，runbook 也能直接驱动真实栈；prototype 对目标状态有信息价值。
- 数据流尚未闭合：一处是 reliable WS 的 delivery identity/ACK 结果，一处是既有 direct fork 的 Message copy consumer。两者不补都会让 worker 按文档完成后留下确定的用户行为错误。
- 其余 naming、delta target、兼容/回滚、常驻服务启停与两轨退出标准一致。

### 架构进攻

| 角度 | 主动攻击与发现 |
|---|---|
| 归属 | Kernel event 只表达 review 事实、Gateway 携带 source、IM 作为 node/membership/display-name trust owner、browser 作为语言 owner，依赖方向自然且不触碰架构红线。唯一歧义是 IM 内 profile vs synthetic user 的显示名权威；长期代价是 rename 后新 notice 继续显示旧名，见 R1-W1。 |
| 该不该存在 | 删除 `system_notice` 而直接用 text 会重新丢失动态语言和 identity；复用 Agent bubble 会破坏非第一人称语义；复用 config boundary 会带来 anchor/pagination/fork 额外契约。窄 sidecar 通过删除测试，没有发现 YAGNI 新抽象。 |
| 深还是浅 | design 复用现有 system message、message JSON chain、canonical created 与 i18n，不新造 event bridge。反向检索发现 repository 已有 `caller_idempotency_key`，但 D4 拒绝使用同类 seam；忽略它会在 ACK 模糊失败时重复落库，见 R1-C1。另一个既有 copy consumer 未复用 sidecar，见 R1-C2。 |
| 治本还是补丁 | 结构化 semantics + IM trust validation + browser rendering 是对“身份/语言在英文正文中丢失”的根因修复，不是 parser/hardcode 补丁；但只靠前端 message id 去重掩盖 reliable transport 重放属于补丁，且不能治理 durable duplicate，见 R1-C1。 |

### Issues

- [R1-C1][CRITICAL] [决策 4 / Gateway → IM 可靠投递]: 方案断言“消息 id 去重继续生效，不另加 dedupe”，但 production connection 的 `send_json()` 只入队并发送、不等待 ACK（`src/personal_assistant/ws/im_connection.py:493-499`）；ACK timeout 会断线（`:1784-1794`），未确认的 business frame 默认重新入队（`:1666-1740`）。IM 当前 handler 每次都创建新 UUID（`src/IM/ws/gateway/relay.py:422-427`），而 repository 已有但方案未使用 `caller_idempotency_key`（`src/IM/infra/repositories/messages.py:65-82,109-125`）；frontend 也只按新生成的 `message_id` 去重（`chat-stream-reducer.ts:221-228`）。因此 IM 已 commit、ACK 在链路上丢失时，同一 review notice 会以两个 id 重复持久化并显示，直接违反 current Web IM “连接恢复后不重复消息”契约（`docs/specs/im/web-chat-ux.md:49-61`）。同一缺口还意味着 current callback 的 try/except 看不到 negative ACK/timeout，无法兑现 Gateway delta 的“记录可诊断失败”。作者需在 design 层拍死稳定 delivery identity（现有 event 已有 `session_id + sequence_num`）如何随重试传到 IM、如何复用 repository idempotency，以及 callback/connection 如何观察 terminal ACK 并仅记录 warning、不反向失败后台任务；同时把 commit-before-ACK-loss/reconnect 与 rejection 作为退出标准。否则 worker 必须猜协议，且即使 happy-path tests 全绿仍会交付重复通知。

- [R1-C2][CRITICAL] [决策 1 / 数据流 / M1 范围]: `system_notice` 被定义为 Message 的持久 sidecar，却没有纳入现有 direct-chat fork copy 路径。生产 `WebIMService.fork_conversation()` 会复制 fork 点前全部消息，但 `create_message` 调用只显式复制 content/attachments/tool_calls/token/kernel/status（`src/IM/application/web_im_service.py:443-465`）；M1 的文件/测试范围也未包含该 service。实现后，只要 fork 点前存在自进化 system row，新 conversation 中该 row 就会丢 sidecar并退回已存英文，破坏 incident 的“所有 IM 提示按当前语言”以及 current fork “带入全部消息并保留完整气泡形态”契约（`docs/specs/im/conversations-messages.md:233-240`）。作者需把 sidecar copy 语义、`WebIMService` 落点和 direct fork regression 纳入 D1 数据流与 M1 exit；否则 worker 按当前范围实施会引入确定的既有功能回归。

- [R1-W1][WARNING] [决策 3 / IM identity owner]: “IM 持有 synthetic user、profile 与显示名”不足以唯一决定 snapshot 来源。当前 `ConfigService.update_profile()` 只更新 `agent_profiles.display_name`（`src/IM/application/config_service.py:167-219`），而 `ensure_agent_user()` 遇到既有 synthetic user 会原样返回、不跟随改名（`:53-75`）；既有 group route 恰好返回 `users.display_name`（`src/IM/infra/gateway_persistence.py:328-355`）。两个 worker 都可合理地把不同表理解为“当前 display_name”，其中一种会让改名后的新 notice 错用旧名，违反 incident “新提示产生时显示正确当前名称”（`incident.md:162`）。请在 D3/interface contract 明确 `AgentProfile.display_name` 是 snapshot 文案权威，synthetic user/participant 仅用于 membership（或拍死另一套能保持同步的权威），并据此写 rename-after-profile-update regression。

### Recommendations

- None beyond resolving the blocking items above.

### Author Resolutions

- **R1-C1 — accepted and resolved.** Production evidence confirmed that `send_json()` cannot observe a terminal business ACK, while the connection may replay an unconfirmed frame after IM has committed it. The design now defines `self-evolution-review:{kernel_session_id}:{event_sequence}` as the stable delivery key, requires `send_json_await_ack()`, passes the key into the existing conversation-scoped `MessageRepository.caller_idempotency_key`, and publishes `message.created` only for the first insert. Decision 4, the interface table, sequence/data flow, risks, Gateway and IM delta specs, and M1 exits now cover commit-before-ACK-loss/reconnect replay, negative ACK diagnostics, and the non-fatal callback boundary.
- **R1-C2 — accepted and resolved.** `WebIMService.fork_conversation()` was confirmed as an existing Message-copy consumer that would otherwise drop the new sidecar. Decision 1, the interface/data flow, risks, reviewer runbook, and M1 scope/exits now require exact `system_notice` snapshot copying without reparsing or name refresh. A MODIFIED `conversations-messages` delta and a Web chat fork scenario define the user-visible contract.
- **R1-W1 — accepted and resolved.** Current config writes update `AgentProfile.display_name`, whereas an existing synthetic user can retain its creation-time name. Decision 3 and the ingress interface now make `AgentProfile.display_name` the sole notice-text snapshot authority; the synthetic user is used only for participant membership. The IM delta, risk handling, and M1 exits now require a profile-rename regression proving new notices use the current profile name while history retains its snapshot.

## Round 2

### Metadata

- reviewer: `/root/bugfix_509_design_reviewer`
- review_mode: `full`
- mode_reason: `The revision changes the reliable-delivery protocol, shared Message contract, fork data flow, delta-spec targets, and M1 boundary; these are high-risk shared contracts that require a full re-review.`
- started_at: `2026-08-06T17:12:39+08:00`
- completed_at: `2026-08-06T17:22:11+08:00`
- duration: `9m 32s`

### Verdict

Approved — 0 CRITICAL / 1 WARNING

### Coverage

- 完整重读当前 `incident.md`、`design.md`、`prototype.html`、四个 `specs/**` delta、M1/M2 范围及 Round 1/Author Resolutions。
- 重跑生产正向路径：Kernel session event sequence → BackgroundSubscriptionManager → runtime delivery → `IMConnectionManager.send_json_await_ack()` → authenticated IM dispatcher → GatewayRelay → conversation-scoped Message idempotency / created event → REST/live/frontend；另重跑 AgentProfile/synthetic user identity 和 direct fork copy 路径。
- 重核 canonical：`docs/specs/im/gateway-relay.md` 的实时/去重、`docs/specs/im/web-chat-ux.md` 的 reconnect consistency、`docs/specs/im/conversations-messages.md` 的 fork requirement，以及 Gateway relay protocol。
- 重核 repository/tooling seam：`caller_idempotency_key` 首次写/重复命中、ACK future/requeue/error ACK、EventStreamHub sequence 形态、nullable migration、profile rename 与 fork rollback。
- `PATH="/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH" ./scripts/docs-check` 本轮实跑通过：223 maintained Markdown sources，66 required routes。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | stable session-event key + awaited ACK + repository idempotency + first-insert created + failure exits | `Kernel.stream()` 确实给出 `session_id/sequence_num`（`src/agent/sdk/kernel.py:1419-1463`）；`send_json_await_ack()` 已有 ACK future（`src/personal_assistant/ws/im_connection.py:566-592`），disconnect 会让 caller 可观察异常并把 frame 以原 payload 重新入队（`:1666-1740`）；repository 的 `(conversation_id, caller_idempotency_key)` 唯一约束及 early return（`src/IM/infra/db.py:116-145,639-645`，`messages.py:120-158`）保证重放返回原 Message 且不再次发布 created。设计、Gateway/IM delta 与 M1 exits 均覆盖 commit-before-ACK-loss 和 negative ACK。 | closed |
| R1-C2 | fork 精确复制 sidecar + MODIFIED canonical delta + runbook/M1 regression | 当前 copy consumer 仍是 `WebIMService.fork_conversation()`（`src/IM/application/web_im_service.py:331-465`）；D1、接口表、主流程旁注、风险、真实 fork runbook 与 M1 全部纳入。新 `conversations-messages` MODIFIED requirement 忠实保留 canonical 原四个 Scenario（`docs/specs/im/conversations-messages.md:233-254`）并只新增 sidecar Scenario；Web UX delta 也加入 current-language fork 行为。 | closed |
| R1-W1 | `AgentProfile.display_name` sole text authority；synthetic user 仅 membership | D3 明确 profile/node/participant 三项校验并在接口表、风险、IM delta、M1 exit 中一致；current `ConfigService.update_profile()` 只更新 profile（`src/IM/application/config_service.py:167-219`），所以该选择正好避开 synthetic user creation-time name 漂移。 | closed |

### 核实台账

#### 1. 现状断言

| ID | 原子 | 本轮证据与结论 |
|---|---|---|
| S1 | hook 已发布 structured review facts | `src/agent/platform/hooks/builtins/self_improvement.py:242-255` 仍发布 skills/memory/completed；成立。 |
| S2 | SDK stream 提供稳定 session/sequence identity | `src/agent/sdk/kernel.py:1419-1463` 输出 session id 与正整数 `sequence_num`；同进程 reconnect identity 成立。 |
| S3 | request 已有 agent/session，callback 当前丢 agent/session | `background_subscriptions.py:24-38,167-175`；修订后的四参 callback 落点正确且是 production manager 使用的 seam。 |
| S4 | current runtime delivery 压成固定英文并 fire-and-queue | `runtime_delivery/background.py:40-77`；需改为 structured payload + awaited ACK，成立。 |
| S5 | awaited ACK 能观察 ACK/error | `im_connection.py:566-592,1487-1503,1541-1574` 已有通用 ack future 与 rejection exception；无需新 connection abstraction。 |
| S6 | unconfirmed business frame reconnect replay | `im_connection.py:1666-1740,1784-1794` 保留原 PendingFrame payload；稳定 key 会随 frame 原样重发。 |
| S7 | system handler 当前无 notice/key/created | `src/IM/ws/gateway/relay.py:392-439` 每次创建新 system Message；目标 handler 是 authenticated runtime 的真实 owner（`runtime.py:107-197`）。 |
| S8 | repository idempotency 是 conversation-scoped | schema/index 在 `db.py:116-145,635-645`；lookup/early return 在 `messages.py:109-158`；首次路径才进入 event insert/notify（`:250-356`）。成立。 |
| S9 | Message 全链当前无 notice | domain/schema/repository/projection/REST/frontend type 均需 optional field；原 R1 production trace 未发生变化。 |
| S10 | profile、node、synthetic participant 能由同一 IM owner 查询 | `gateway_persistence.py:301-356` 持有 profile/user/conversation repos；authenticated node 由 `sessions.py:347-391` 注入。成立。 |
| S11 | profile 是会变更的当前显示配置，synthetic user 可陈旧 | `config_service.py:53-75,167-219` 证实；修订后的 authority 正确。 |
| S12 | direct fork 是 Message copy consumer | `web_im_service.py:331-465` 复制 start→fork point 且显式枚举 Message 字段；sidecar 必须显式传入。成立。 |
| S13 | fork 失败有既有回滚 | `web_im_service.py:438-480` 的 copy try/rollback owner 可承接新字段失败，不需新 transaction owner。 |
| S14 | frontend history/live 汇入同一 Message | `chat-types.ts:135-162,229-234`、`chat-stream-reducer.ts:221-265` 与 production `ChatWorkspacePage` wiring 成立。 |
| S15 | `MessagePane` 已有 conversation kind 与 i18n | `message-pane.tsx:1264-1402` + `chat-workspace-page.tsx:1088-1108`；formatter owner 正确。 |
| S16 | browser 是语言权威 | `src/IM/frontend/src/i18n/index.ts:7-46`；server-side locale 方案仍不成立。 |
| S17 | system row 的低层级视觉已存在 | `global.css:1700-1706` 与 MessagePane system branch；复用成立。 |
| S18 | Coding CLI 独立 | `src/coding_cli/events/background_runs.py:70-96` 不经过 PA callback；no-delta 成立。 |
| S19 | nullable JSON migration 可复用 | `src/IM/infra/db.py:584-645` 已有 optional JSON column migration pattern；旧行 fallback 可实现。 |
| S20 | config boundary timeline item 不适合复用 | 它带 anchor/pagination/fork 专属语义（`chat-types.ts:169,230`）；窄 Message sidecar 更深。 |
| H1 | single subscriber/replay anchor 仍是唯一 production path | `background_subscriptions.py:77-92` 与 `background_session_events.py:173-227`；无平行 test-only implementation。 |
| H2 | canonical created event seam 已存在 | `MessageRepository.emit_created_event` 与 `_message_projection.py:55-79`；system handler 只需接入。 |
| H3 | participant relation 是群聊身份权威 | `conversation_participants` schema/repository 仍是 source membership 的真实事实。 |
| H4 | fork canonical 要求完整复制 | `docs/specs/im/conversations-messages.md:233-254`；新 MODIFIED delta 精确锚定。 |

#### 2. 编号决策

| 决策 | 四问核实 | 结论 |
|---|---|---|
| D1 optional `system_notice` + exact fork copy | sidecar shape、fallback、idempotency key、fork 新 message id/旧 snapshot、拒绝项均拍死；现有 copy owner已加入。 | 成立；R1-C2 closed |
| D2 browser full-sentence i18n | 六个 direct/group × targets keys、language owner、legacy fallback 明确，与 Q2/Q3 一致。 | 成立 |
| D3 IM profile/node/membership trust | `AgentProfile.display_name` sole authority、synthetic participant role、reject conditions、history immutability均无歧义。 | 成立；R1-W1 closed |
| D4 session-event idempotency + awaited ACK + first-insert created | stable key owner、wire/API、repository scope、ACK/error行为、no-outbox拒绝与 test exits 均拍死；现有 seams兼容。 | 成立；R1-C1 closed |
| D5 legacy/unknown fallback；CLI/Kernel不改 | recognized kind gate 与 no-delta 清楚，未扩成通用通知平台。 | 成立 |

#### 3. Incident 约束

| ID | 约束 | 当前 design 覆盖 |
|---|---|---|
| Q1 | 仅 group 增加 Agent 名；direct/CLI 不加 | D2 formatter branch + D5。 |
| Q2 | 继续轻量 system，遵守 i18n | D1/D2 + P1/P2。 |
| Q3 | 所有 IM notice 随当前界面语言 | REST/live/fork 均保存 semantics，browser formatter 统一渲染。 |
| RCA1 | subscription callback 丢 identity | 四参 callback + stable request identity 正面修复。 |
| RCA2 | English text 压平 semantics | structured sidecar + browser formatter 正面修复。 |
| INV1 | per-agent skill/memory 隔离不变 | hook/write path 不改。 |
| INV2 | 一行轻量 meta/system | sender type/style 不改。 |
| INV3 | 不伪装第一人称 Agent 消息 | D1 明确拒绝 Agent bubble。 |
| INV4 | 后台通知不打断主对话 | callback 观察 ACK 但只 warning；Gateway delta 明确 non-fatal。 |
| R1 | 群聊 notice 归因真实 Agent | IM trust validation + snapshot + M2 group formatter。 |
| R1-S1 | 单个 Agent memory notice 带名且非 bubble | D2 example + P1/M2 exit。 |
| R1-S2 | 连续 Agent 分别归因 | per-message snapshot + M2 two-Agent journey；stable delivery key 避免假重复。 |
| R2 | 所有 IM notice zh/en × skills/memory/both | 六句 key + target mapping + M1。 |
| R2-S1 | zh | P2/M1。 |
| R2-S2 | en | P2/M1。 |
| R2-S3 | live/reopen 一致 | first-insert created + REST same sidecar；fork copy也保留。 |
| R3 | direct no name；CLI unchanged | direct branch + no CLI delta。 |
| R3-S1 | direct localized only | M1/M2 exits。 |
| R3-S2 | CLI unchanged | independent CLI formatter untouched。 |
| IN1 | group attribution | D3/M2。 |
| IN2 | group/direct zh/en | D2/M1。 |
| IN3 | live/history | D4 + REST/live/fork regression。 |
| IN4 | three target combinations | mapping + component matrix。 |
| NG1 | 不改 CLI | no delta。 |
| NG2 | 不变 Agent message | system sender 保持。 |
| NG3 | 不改 trigger/execution/isolation | Kernel hook no delta。 |
| NG4 | 不做 generic notification platform | narrow value object。 |
| NG5 | 不回填历史 English | nullable/NULL fallback。 |
| NG6 | history 不因 rename 改写；新行用当前名 | profile snapshot at ingress + fork exact copy + rename regression。 |

#### 4. Delta specs

| ID | Delta 原子 | 核实 |
|---|---|---|
| G-REQ | source/targets/stable delivery identity/awaited ACK/nonfatal/CLI unchanged | D1/D3/D4/D5 全覆盖；消费者是 IM 与外部用户。 |
| G-S1 | group source + targets | 覆盖。 |
| G-S2 | direct same structured path | 覆盖。 |
| G-S3 | ACK-loss replay keeps identity | stable session+sequence key 与 connection requeue闭环。 |
| G-S4 | disconnect/timeout/reject可诊断但不反向失败 | awaited ACK + callback warning 边界覆盖。 |
| I-REQ | profile/node/participant validate + idempotent persistence + first created + REST/live compatibility | D3/D4 与 existing repos匹配。 |
| I-S1 | first valid insert persists/live | 覆盖。 |
| I-S2 | refresh same snapshot | 覆盖。 |
| I-S3 | commit/ACK-loss replay same id/no second event | repository early return + M1 regression覆盖。 |
| I-S4 | invalid identity rejected/no write/no live | D3 reject matrix覆盖。 |
| I-S5 | legacy system message fallback | D5覆盖。 |
| CM-MOD | fork requirement preserves complete persistent semantics | 精确使用 canonical 标题，原 requirement正文与四个原 Scenario 全保留，只增结构化 notice 语义。用法正确。 |
| CM-S1 | original start→M full copy | 保留。 |
| CM-S2 | fork preserves notice targets/snapshot/current language | D1 + fork interface/runbook/M1覆盖。 |
| CM-S3 | agent remembers history | 原样保留。 |
| CM-S4 | original/branch independent | 原样保留。 |
| CM-S5 | fork entry limits | 原样保留。 |
| W-REQ | browser language/kind/targets/system style/live/history | D2 + P1-P3覆盖。 |
| W-S1 | zh group attribution | 覆盖。 |
| W-S2 | en successive Agents | 覆盖。 |
| W-S3 | direct no name | 覆盖。 |
| W-S4 | live/reopen/language switch | 覆盖。 |
| W-S5 | old history unchanged | 覆盖。 |
| W-S6 | forked notice keeps semantics/current language | D1 copy + shared formatter覆盖。 |
| Δ-usage | gateway/IM system behavior用 ADDED；fork existing requirement用 MODIFIED | 四个 target 均为语义最窄位置；MODIFIED忠实保留 canonical，所有 THEN 均为消费者可观察结果。 | 成立 |

#### 5. Milestones

| Milestone | 拆分/范围/退出标准 | 结论 |
|---|---|---|
| M1 localized-system-notice | 有 i18n、实时、fork、CLI不变等独立用户价值；reviewer/worker 两轨齐，R1 三项 regression 全加入。可是 M1 仍拥有所有 Gateway/IM schema+identity+fork/frontend 主链，规模没有被拆分理由实际约束。 | 可交付，但范围警告见 R2-W1 |
| M2 group-agent-attribution | 串行依赖 M1；group per-agent name/direct no-name/P1/P3 是可观察价值，且不同并行组无 worktree collision。 | 成立 |

### 整体判断

- 主方案已经闭环：stable event identity 在 Gateway 产生，IM 用 conversation-scoped key 幂等落库，首次 insert 才发布 created；ACK ambiguity、negative ACK 和 frontend duplicate 三层不再混为一谈。
- fork 是完整 Message consumer，profile 是唯一 snapshot 文案权威；Round 1 两个确定回归与一个 identity 歧义均已消除。
- 新增 MODIFIED delta 用法正确，未静默删除 canonical fork 场景；runbook 能从真实 notice 走到真实 fork。
- 上层总览、接口表、sequence diagram、风险与回退一致。唯一剩余问题是 milestone workload 估算/切片没有跟随新增 ACK+fork scope 更新，不影响设计架构成立，但会削弱 orchestrator 的 worker 边界。

### 架构进攻

| 角度 | 本轮攻击结果 |
|---|---|
| 归属 | session/sequence 与 retry 属 Gateway；node/profile/membership、snapshot、message idempotency 属 IM；language 属 browser；fork copy 属 WebIMService。多个修订叠加后仍无反向 import 或双重 authority。 |
| 该不该存在 | stable key 直接复用 event identity 与 repository seam，不造 outbox；sidecar 仍通过删除测试；fork 只扩已有 copy loop。没有发现 YAGNI module/factory/protocol。 |
| 深还是浅 | awaited ACK、conversation-scoped idempotency、canonical created 和 existing rollback 均是更深的既有能力；修订消除了 R1 的前端-only dedupe浅补丁。 |
| 治本还是补丁 | identity/semantics 丢失在 callback/wire 边界，修复在同一边界保留并由 IM trust owner补全；ACK ambiguity 在 durable write owner处幂等；fork在 copy owner处复制。三处均治根。Milestone 分配仍把大部分链压在 M1，长期代价是 worker scope与审查边界失真，见 R2-W1。 |

### Issues

- [R2-W1][WARNING] [Milestones / bugfix-509-M1]: 拆分理由写的是整个 unit “16–20 个生产/测试文件，超过单 worker 的 10 文件窗口”，但修订后的 M1 范围仍独占至少 17 个 production 落点——Gateway callback/delivery/connection 3 个，IM identity/relay/domain/schema/repository/projection/REST/fork 8 个，frontend types/reducer/formatter/zh/en/MessagePane 6 个——并外加全部相关 Gateway、IM、fork、frontend tests；M2 只剩已在 M1 触及的 formatter/MessagePane 分支。新增 ACK seam 与 fork consumer 后，原总量估算也明显未更新。若不改，orchestrator 仍会把几乎整个跨层变更交给一个超出所引用文件窗口的 M1 worker，拆分没有实际降低该 worker 的探索、实现和 review 面，M2 则承担很薄的尾部呈现。请给出每个 milestone 的独立文件/行数估算并让切片真正约束 worker scope（例如把完整 attribution vertical slice 放入 M2），或明确撤回“>10 文件窗口”作为当前拆分依据并重新选择可执行边界。该问题会降低实施编排质量，但不使最终协议或用户契约本身失效，因此不阻断 Gate 2。

### Recommendations

- [R2-R1] 把 D4/interface 中的 “durable Kernel sequence/stream” 改称 “stable in-process Kernel stream sequence”，并显式注明本 unit 只承诺 connection replay，不新增 Gateway-process-restart durable outbox。当前 `EventStreamHub` 是内存有界 history（`src/agent/core/events/hub.py:46-59,93-96`）；修正术语可避免 worker/reader 误以为跨进程投递已经持久化，但不影响本次已拍死的 reconnect idempotency。

### Author Resolutions

- **R2-W1 — accepted and resolved.** The estimate now separates 16–17 production files, 8–11 test files, and 530–780 lines for the unit. The milestone boundary was rebalanced around two observable results: M1 `reliable-structured-notice` owns the 10–11 production-file Gateway/IM delivery and persistence path and proves live appearance, reconnect dedupe, reopen, and fork retention using the existing fallback UI; M2 `localized-agent-attribution` owns the 6 production-file Web IM consumer and delivers language, direct/group, and attribution behavior together. Each milestone now has its own production/test/line estimate and non-overlapping implementation scope; the skeleton directories were renamed to match.
- **R2-R1 — accepted and resolved.** Decision 4 and the callback interface now call the identity a stable in-process Kernel stream sequence. The rejected-alternative text explicitly limits the contract to connection reconnect within one Gateway process and states that cross-process notification recovery/durable outbox is outside this unit.

## Round 3

### Metadata

- reviewer: `/root/bugfix_509_design_reviewer`
- review_mode: `full`
- mode_reason: `The revision changes milestone decomposition and the delivery durability boundary; milestone boundaries are a high-risk orchestration contract, so the full inventory and all architecture attacks were rerun.`
- started_at: `2026-08-06T17:28:05+08:00`
- completed_at: `2026-08-06T17:31:01+08:00`
- duration: `2m 56s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### Coverage

- 重读当前 `design.md` 全文、Round 2/Author Resolutions、四个 delta-spec、两个重命名后的 milestone skeleton；incident/prototype 约束沿同一 reviewer 已建立的完整上下文逐项重核。
- 重新按产品入口核对 M1：Kernel event → Gateway callback/awaited ACK → authenticated IM relay → identity/persistence/idempotency → canonical `message.created` → 未修改的现有 Web IM fallback system row → refresh/reconnect/fork。
- 重新按产品入口核对 M2：REST/live `system_notice` → frontend Message type/reducer → shared formatter/current i18n → `MessagePane` direct/group branch → P1/P2/P3。
- 核对 per-milestone production/test/line estimate、文件交集、串行依赖、两轨退出标准、Runbook 投影、delta 归属与 skeleton 名称。
- 重核 `EventStreamHub`、SDK stream 与 IM connection：sequence 是同一进程内稳定 identity；delivery contract 仅覆盖同一 Gateway 进程的 connection reconnect，没有暗示跨进程 durable recovery。
- `PATH="/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH" ./scripts/docs-check` 本轮实跑通过：223 maintained Markdown sources，66 required routes；unit whitespace/structure 检查无异常。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R2-W1 | 重估 unit 与两个 milestone；M1 独占 reliable structured backend，M2 独占 localized attribution frontend；同步 skeleton | 总量 `16–17 prod / 8–11 test / 530–780 lines` 与 M1 `10–11 / 6–8 / 350–500` + M2 `6 / 2–3 / 180–280` 算术闭合（`design.md:293-305`）。M1 约 10 个已知 production owner：2 个 Gateway、7 个 IM message/identity owners、1 个 fork owner；M2 恰为 types/reducer/formatter/zh/en/MessagePane 6 个 consumer files。范围不重叠且各自有可观察结果。 | closed |
| R2-R1 | 改称 stable in-process sequence；限定同进程 reconnect，跨进程/outbox 非目标 | D4 拒绝项明确“同一 Gateway 进程内 connection reconnect”及“跨 Gateway 进程重启不在范围”（`design.md:139-145`）；callback interface 使用 `stable in-process Kernel stream`（`:166-174`）。这与 current in-memory bounded `EventStreamHub`（`src/agent/core/events/hub.py:46-59,93-96`）和 connection PendingFrame replay 一致。 | closed |

### 核实台账

#### 1. 现状断言

| ID | 原子 | 本轮证据与结论 |
|---|---|---|
| S1 | self-evolution hook 已给出 targets | `self_improvement.py:242-255`；Kernel 不需改。 |
| S2 | SDK event 有 session + in-process sequence | `src/agent/sdk/kernel.py:1419-1463`；稳定性边界现已准确表述。 |
| S3 | subscription request 有 agent/session，callback 当前丢 identity | `background_subscriptions.py:24-38,167-175`；M1 owner 正确。 |
| S4 | current delivery 固定英文 + `send_json` | `runtime_delivery/background.py:40-77`；M1 改 structured payload/awaited ACK。 |
| S5 | awaited ACK/rejection seam 已存在 | `im_connection.py:566-592,1487-1503,1541-1574`；M1 无需修改 connection implementation。 |
| S6 | same-process disconnect 会重放原 PendingFrame | `im_connection.py:1666-1740,1784-1794`；stable key 原样保留。 |
| S7 | current system relay 每次新建且不发 created | `src/IM/ws/gateway/relay.py:392-439`；M1 是 production handler。 |
| S8 | repository 已有 conversation-scoped idempotency | `db.py:116-145,639-645` 与 `messages.py:120-158`；duplicate early return 不再发 event。 |
| S9 | Message sidecar 需穿过 domain/DB/repo/projection/REST | `domain/models.py`、`infra/db.py`、`repositories/messages.py`、`_message_projection.py`、`api/routes/messages.py` 是同一真实链；M1 独占。 |
| S10 | profile/node/membership trust owner 在 IM | `gateway_persistence.py:301-356` + `sessions.py:347-391`；M1 独占。 |
| S11 | `AgentProfile.display_name` 是会更新的配置名 | `config_service.py:53-75,167-219`；snapshot authority 仍正确。 |
| S12 | fork copy 显式枚举 Message fields | `web_im_service.py:331-465`；M1 精确复制 sidecar。 |
| S13 | fork 失败沿既有 owner 回滚 | `web_im_service.py:438-480`；不需要跨 milestone 新 transaction。 |
| S14 | 未修改 frontend 能显示新 created 的 fallback content | reducer 的 `message.created` 会建立 system Message（`chat-stream-reducer.ts:221-265`），MessagePane 当前 system branch 输出 `message.content`（`message-pane.tsx:1264-1287`）；所以 M1 的 live fallback 是真实用户结果。 |
| S15 | frontend type/reducer 会丢弃未声明 sidecar，M2 必须消费 | `chat-types.ts:135-162,229-234` 与 reducer created mapping当前未带 notice；M2 六个文件边界正确。 |
| S16 | browser 是 locale authority | `i18n/index.ts:7-46`；M2 owner 正确。 |
| S17 | system row 样式无需 M1/M2 新 UI container | `global.css:1700-1706`；MessagePane只改内容选择。 |
| S18 | direct/group kind 已传入 MessagePane | `chat-workspace-page.tsx:1088-1108`；不在 M2 生产文件清单中修改也可完成 branch。 |
| S19 | CLI formatter 独立 | `src/coding_cli/events/background_runs.py:70-96`；两个 M 均不触碰。 |
| S20 | nullable migration兼容旧行 | `src/IM/infra/db.py:584-645`；M1 old fallback 可验。 |
| H1 | single subscriber 是唯一 production path | `background_subscriptions.py:77-92` + `background_session_events.py:173-227`。 |
| H2 | canonical created seam 已存在 | repository `emit_created_event` + `_message_projection.py:55-79`。 |
| H3 | conversation participants 是归属事实 | current schema/repository；M1 validation owner正确。 |
| H4 | direct fork canonical 要完整复制 | `docs/specs/im/conversations-messages.md:233-254`；M1 copy + M2 language共同满足。 |

#### 2. 编号决策

| 决策 | 四问核实 | 结论 |
|---|---|---|
| D1 optional sidecar + exact fork copy | shape、fallback、fork new id/old snapshot、拒绝项清楚；M1生产、M2消费边界兼容。 | 成立 |
| D2 browser complete-sentence i18n | direct/group × three targets、language owner、legacy fallback拍死；全部落M2。 | 成立 |
| D3 IM node/profile/membership validation | trust owner与profile snapshot唯一；全部落M1，M2只读 snapshot。 | 成立 |
| D4 in-process stable identity + ACK + IM idempotency | reconnect范围、跨进程非目标、key、ACK/error与first-insert event清楚；术语已无 durable 歧义。 | 成立 |
| D5 legacy fallback/CLI/Kernel unchanged | M1可借fallback交付，M2 recognized notice覆盖后仍保留unknown/NULL content；两阶段自洽。 | 成立 |

#### 3. Incident 约束

| ID | 约束 | 当前设计/里程碑覆盖 |
|---|---|---|
| Q1 | 只有group显示Agent；direct/CLI不显示 | M2 direct/group formatter；CLI no-delta。 |
| Q2 | 轻量system + i18n | M1保留system row；M2完成i18n/P1。 |
| Q3 | 所有IM notice按当前UI语言 | M2 history/live/fork统一formatter。 |
| RCA1 | callback丢source identity | M1四参callback。 |
| RCA2 | structured semantics被压成English | M1持久sidecar，M2消费。 |
| INV1 | per-agent isolation不变 | Kernel/write path不改。 |
| INV2 | 一行轻量meta | system sender/style不改。 |
| INV3 | 非Agent第一人称 | D1。 |
| INV4 | 通知不打断对话 | M1 awaited ACK callback只warning。 |
| R1 | group source attribution | M1 trustworthy snapshot + M2 group render。 |
| R1-S1 | 单Agent memory notice带名且非bubble | M2 P1/P2。 |
| R1-S2 | 两Agent连续分别归因 | per-message snapshot + M2 two-Agent journey。 |
| R2 | group/direct zh/en × three targets | M2完整矩阵。 |
| R2-S1 | Chinese | M2。 |
| R2-S2 | English | M2。 |
| R2-S3 | live/reopen一致 | M1保证semantic durability，M2同formatter消费。 |
| R3 | direct no name；CLI unchanged | M2 direct branch；CLI不改。 |
| R3-S1 | direct only localized | M2。 |
| R3-S2 | CLI unchanged | M1/M2 exits均保护。 |
| IN1 | group attribution | M1+M2。 |
| IN2 | group/direct i18n | M2。 |
| IN3 | realtime/history | M1可靠投递，M2最终呈现。 |
| IN4 | skills/memory/both | M1规范化，M2文案矩阵。 |
| NG1 | no CLI change | 保持。 |
| NG2 | no Agent bubble | 保持system。 |
| NG3 | no trigger/execution/isolation change | 保持Kernel no-delta。 |
| NG4 | no generic system platform | narrow value object。 |
| NG5 | no history backfill | M1 nullable，M2 fallback。 |
| NG6 | historical snapshot不随rename；new用当前名 | M1 snapshot/fork，M2不从participants覆盖。 |

#### 4. Delta specs

| ID | Delta 原子 | 核实 |
|---|---|---|
| G-REQ | stable identity/source/targets/awaited ACK/nonfatal/CLI unchanged | M1完整交付。 |
| G-S1 | group source/targets | M1 wire。 |
| G-S2 | direct same structured path | M1 wire。 |
| G-S3 | ACK-loss reconnect same identity | M1 in-process connection scope。 |
| G-S4 | failure diagnostic/nonfatal | M1 callback。 |
| I-REQ | validate/snapshot/idempotent persist/first created/REST-live/legacy | M1完整交付并可由现有fallback UI观察live。 |
| I-S1 | legal insert/live | M1。 |
| I-S2 | refresh same snapshot | M1 data；M2 final view。 |
| I-S3 | no duplicate after lost ACK | M1。 |
| I-S4 | invalid source rejected | M1。 |
| I-S5 | old system compatible | M1 backend + existing UI。 |
| CM-MOD | fork complete semantics | canonical标题与四个原Scenario保留；M1复制sidecar，M2按当前语言呈现。 |
| CM-S1 | start→M full copy | M1现有fork owner。 |
| CM-S2 | preserve notice targets/snapshot/current language | M1保存，M2渲染。 |
| CM-S3 | agent memory at fork point | 原行为不变。 |
| CM-S4 | branches independent | 原行为不变。 |
| CM-S5 | fork entry limits | 原行为不变。 |
| W-REQ | locale/kind/targets/style/live/history | M2建立在M1契约上完整交付。 |
| W-S1 | zh group | M2。 |
| W-S2 | en successive Agents | M2。 |
| W-S3 | direct no name | M2。 |
| W-S4 | live/reopen/language switch | M1 semantics + M2 formatter。 |
| W-S5 | old history fallback | M1 NULL + M2 fallback。 |
| W-S6 | fork current language | M1 copy + M2 formatter。 |
| Δ-usage | three ADDED + one faithful MODIFIED | target与THEN仍正确，milestone重排不改变最终delta。 | 成立 |

#### 5. Milestones

| Milestone | 可执行性/价值/交集/退出标准 | 结论 |
|---|---|---|
| M1 reliable-structured-notice | 10–11 prod / 6–8 test / 350–500 lines；Gateway+IM+fork形成端到端链，现有frontend立即显示fallback，所以不是不可观察backend横切。live、same-process reconnect dedupe、reopen、fork与CLI不变均可独立验；reviewer/worker两轨齐。 | 成立；R2-W1 closed |
| M2 localized-agent-attribution | 6 prod / 2–3 test / 180–280 lines；只消费M1 stable sidecar但完整交付language/direct-group/attribution/P1-P3，是独立用户结果。与M1 production文件无交集，串行依赖明确。 | 成立 |

### 整体判断

- 两个 milestone 现在按“可靠结构化通知”和“最终本地化归因”划分，各自能从真实产品入口观察，而不是按修改层机械分组。
- M1 的 fallback 可见性由当前 reducer/MessagePane 真实支持；M2 不需要回改 Gateway/IM，文件归属与 contract handoff 精确。
- 估算加总一致、测试轨和 reviewer 轨完整、prototype P1/P2/P3 全投影到 M2，Runbook 最终旅程同时覆盖 M1可靠性和M2体验。
- delivery durability 口径现与当前 EventStreamHub/connection queue 对齐：保证同进程 connection reconnect，不承诺跨进程通知恢复。

### 架构进攻

| 角度 | 本轮攻击结果 |
|---|---|
| 归属 | M1中Gateway持有event/retry，IM持有trust/persistence/fork；M2中browser持有language/presentation。M1→M2依赖方向和产品架构一致，无反向import或shared-file owner。 |
| 该不该存在 | 两个milestone都通过删除测试：删除M1则没有实时/幂等/持久语义；删除M2则用户仍看到English无归因fallback。每个都有独立可观察差异，不是空骨架。 |
| 深还是浅 | M1复用awaited ACK、repository idempotency、created event、fork loop；M2复用Message reducer/i18n/system row。切片没有为协调新造adapter或临时兼容层。 |
| 治本还是补丁 | M1在数据丢失与ACK ambiguity owner处治本，M2在language/identity消费owner处完成表达；两阶段交界是稳定Message sidecar，而非临时文本协议。进程内范围也不再用“durable”掩盖未实现的outbox。 |

### Issues

- None.

### Recommendations

- None.
