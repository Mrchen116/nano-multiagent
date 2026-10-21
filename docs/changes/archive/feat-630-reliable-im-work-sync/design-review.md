# feat-630 独立设计审查

## Round 1

### Metadata

- reviewer_target: `/root/feat630_design_review`（独立 Codex reviewer，非设计作者）
- review_mode: `full`
- mode_reason: 首轮 Gate 2，完整核对需求、真实组装、接口与恢复、用户约束、delta 和 milestone。
- started_at: `2026-10-21T12:15:37+00:00`
- completed_at: `2026-10-21T12:21:27+00:00`
- duration: `350s`
- frozen_head: `1a14fe46feb9c1d356aa250e10713c2e1d1bb57e`
- product_baseline: `11f599938d67f21398570009f1c7e9e0088b81a1`
- reviewed_scope: `spec.md`、`design.md`、`specs/**`、`M1-reliable-im/.gitkeep`
- checkout: detached HEAD；开始时工作区干净。已核对冻结提交相对产品基线没有 apps/packages/src/scripts/config/tests 产品变更。
- 本轮仅写本报告；未启动产品、未部署、未修改受审文档或代码，未创建分支或提交。

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING。**

Work HTTP 与实时 WS 分离、复用现有 Inbox/journal/relay outbox、保留本地 durable barrier 的方向成立。三处未闭合项会使实施范围或归并后的权威契约与承诺冲突；修订后复审。

### Coverage 与证据

| 覆盖面 | 独立核对与判断 |
|---|---|
| 实际产品组装和现状断言 | [Node main](../../../../apps/node/src/main.ts) 的 100–115、240–249、301–305、357–369 行确实组装 GlobalAgent/Inbox/Channels/DSH，实际 relay 进入 `globalProduct.receive`；DSH ready 内恢复以 `settlePartitions` 并行，relay ready 回调的恢复则按顺序 await。设计移除 ready 全量 Work 依赖的落点正确，不能把仅测试的实现当产品入口。 |
| Work 耦合、输入和执行恢复 | [global-agent.ts](../../../../packages/personal-assistant/src/global-agent.ts) 的 67–108、138–143、204–216、392–398、472–555 行确认 main/query/reconcile 的 flush、Inbox 之前的 main、ACK 之后的 wake，以及稳定 `inbox-wake:agent:watermark`；[inbox.ts](../../../../packages/personal-assistant/src/inbox.ts) 的 18–32、41–51、137–143、258–288 行确认唯一输入、wakes、读承诺与 journal。设计复用这些事实并新增同事务待回执，比另建输入任务总账更合适；控制 intent 复用 [session-controls.ts](../../../../packages/personal-assistant/src/session-controls.ts) 22–55 行，职责仍属 PA。 |
| 实时关联、超时、心跳 | [Channels](../../../../packages/channels/src/index.ts) 206–266 行确认单 active、按 type 匹配通用 ACK、十秒超时断连接和队列忙跳过心跳；240–241 行已有不阻塞接收循环的 callback。设计的 request_id/generation、稳定业务身份与有界窗口分别承担传输关联、业务幂等和容量控制，职责有区分；保留 server 发起请求原 request_id、业务 owner 必要串行和撤销终止是必要约束。 |
| 中心投递、确认和普通离线 | [messaging.ts](../../../../apps/im-server/src/messaging.ts) 555–584、633–687 行确认 message/relay 同事务、落库后可能 503 和当前逐条投递；[gateway.ts](../../../../apps/im-server/src/gateway.ts) 490–515、1052–1078 行确认回执直接覆盖状态与重连全量读取。设计复用 outbox、有界重投和终态单调合理；delta 的普通离线冲突见 R1-W2。 |
| Session 权威与权限 | [work.ts](../../../../apps/im-server/src/work.ts) 41–74、103–143、481–507 行确认 main 替换/retired、profile 归属及 query 的 session/node/global_main 检查。把权威 scope 从历史显示事件拆出小请求，既能解除历史依赖，也保留 query 信任来源；历史重放不能激活 retired main 的决定闭合。PA 来源、审批和复核仍落在 [personal-assistant.ts](../../../../packages/personal-assistant/src/personal-assistant.ts) 43–84、113–173 行及现有服务端 authority/action；未发现需要另造权限系统的理由。 |
| Work 持久性、大小与背压 | [work.ts](../../../../apps/im-server/src/work.ts) 76–169 行确认 node/journal 连续游标、事务 append/project 与重复身份验证；[inbox.ts](../../../../packages/personal-assistant/src/inbox.ts) 281–288 行确认原 journal/seq 与未清理历史。设计已规定完整请求字节上限、16 KiB parts、全局/单节点并发、暂存配额、hash/epoch、过限暂停、无进度清理、未知结果查 cursor/parts、惰性读取与 stop。16 MiB 是本设计明确的支持上限，更大事件中心完整回看不在其承诺内，不能把其作为已验收的无限容量能力。 |
| 机器身份、迁移和恢复一致性 | [identity.ts](../../../../apps/im-server/src/identity.ts) 565–576 行确认持久 runtime token 校验当前 binding/account；[messaging.ts](../../../../apps/im-server/src/messaging.ts) 33–36 行、[gateway.ts](../../../../apps/im-server/src/gateway.ts) 53–74 行确认现有 HTTP principal 使用活动连接临时 token；[server.ts](../../../../apps/im-server/src/server.ts) 108–118、143–151 行在请求和响应阶段调用通用 principal。专用三路由而不扩大通用 principal 的职责合理，实现时须使两阶段 hook 都采用该专用鉴权规则。能力协商、IM 先行、新旧协议共用游标、旧中心拒绝新 Node 和回滚先停新 Node 已说明；canonical 机器凭据例外缺失见 R1-W3。 |
| 用户约束、真实客户端和 delta | 原始需求明确普通聊天不要内部阶段。设计不新增状态枚举、布局或运维气泡，保留主动 Work、必要失败与授权入口，因此本轮不要求新视觉原型。未启动浏览器，未声称完成视觉或产品运行验收；客户端核对来自 [message-pane.tsx](../../../../src/IM/frontend/src/features/chat/components/message-pane.tsx) 651–708 行与 [chat-api.ts](../../../../src/IM/frontend/src/features/chat/chat-api.ts) 65–77 行，普通消息未知结果闭合问题见 R1-W1。三个 delta 的 canonical 路径正确；修改首条 WS Requirement 时保留了原非法帧、不支持类型和 durable config boundary 语义，但没有修订两个受影响的既有 Requirement。 |
| Milestone、验收与范围 | 单 M1 把可靠接收、WS 和 WorkSync 作为一个用户可交付结果，避免仅拆上传接口就声称成功。Runbook 复用现有 e2e-up/down 和 secret-free [E2E config](../../../../config/e2e/gateway.yaml)，隔离身份来源已说明；故障代理与 deterministic provider 是明确待交付 fixture，现有 [配置连续性 E2E](../../../../tests/e2e/critical_paths/test_agent_config_context_continuity_critical_path.py) 有真实 DSH HTTP provider 接线先例。V1–V8 覆盖强杀窗口、晚 ACK、分块、权限、多目标、负载及真实浏览器，负载阈值有基线且未冒充人数承诺。V5 的真实浏览器普通消息要求目前超出设计落点，见 R1-W1；其余验收方案可指导实施，本轮未运行也不代表已通过。 |

### 架构判断

PA 持有本地消息交接、通知/消费和外发恢复；Channels 持有连接、关联和有限在途请求；IM 持有中心消息/任务、账号/设备/聊天资格与 Work 投影。新增 WorkSync 是独立上传 owner，而非第二 Agent Loop；现有同步 append/project 与 SQLite 在有界批次下继续复用，尚无证据要求新增 broker 或第二投影体系。独立 HTTP 传输也有明确成本：必须维护专用机器鉴权和 parts 生命周期，设计已给出 owner、存储/清理、游标及重试边界。上述责任划分与 DSH 公开入口、依赖方向一致。

### 历史问题闭环

本轮为 Round 1，无历史 issue 或 Author Resolution。

### Issues

#### R1-W1 — 普通 Web 消息没有稳定发送身份，V5 的 POST 回包丢失恢复在当前实施范围内无法成立

- **位置**：[design.md](design.md) 28、99、155、195、206 行。
- **证据**：设计 V5 要求“已保存后 POST 响应丢失”仍有“一次消息/稳定 idempotency key”，同时声明不改 Web 组件，M1 落点只列 Node/IM/PA/Channels/contracts。实际普通文本路径在 [message-pane.tsx](../../../../src/IM/frontend/src/features/chat/components/message-pane.tsx) 678–684 行没有 attempt/key，直接 `onSend(wireContent, submittedAttachments)`；只有私聊 interactive background 路径生成并复用 key。失败后 686–689 行保留草稿返回；[chat-api.ts](../../../../src/IM/frontend/src/features/chat/chat-api.ts) 75–77 行只在 caller 传入 key 时添加请求头；[messaging.ts](../../../../apps/im-server/src/messaging.ts) 555–575 行也只按该可选 key 查重。
- **未修后果**：普通消息在中心 commit 后丢 HTTP 回包，客户端按现有行为保留草稿并报告发送错误；用户重试没有原 key，服务端会插入第二条消息和第二组 relay。修改中心离线 503 或 relay 去重均不能把这两个新 message identity 合并。此结论来自实际代码路径，非本轮浏览器复现。
- **所需修订**：把普通 Web 发送 attempt 的稳定身份、未知结果核对/重试和必要生命周期纳入设计及 M1 落点，保持现有聊天信息层级，不需要增加内部状态 UI。V5 必须从真实普通文本/附件发送入口丢 POST 回包并恢复验证，不以 API 测试主动补 key 代替客户端。若要缩小该场景，须先明确调整承诺及验收范围，不能让 V5 与不改客户端的决定同时保留。

#### R1-W2 — 新普通离线排队契约会与保留下来的“普通离线失败”Scenario 正面冲突

- **位置**：[specs/im/gateway-relay.md](specs/im/gateway-relay.md) 26–37 行及 [design.md](design.md) 159–164 行。
- **证据**：delta 新增普通节点不可达时“返回已保存的同一消息、保留待投递、不误报未保存、恢复自动投递”；canonical [gateway-relay.md](../../../specs/im/gateway-relay.md) 297–315 行的“已授权更新的切换阶段持久等待新消息”仍明确规定“普通离线”沿用失败语义。该 Requirement 未出现在 MODIFIED/REMOVED。按 [delta 归并规则](../../../specs/CONTRIBUTING.md)，ADDED 只追加，不会删除或覆盖这条原 Scenario。
- **未修后果**：归并后 current 同时要求普通离线返回已保存并自动恢复，又要求普通离线失败；实现者或后续回归可能保留现有 503，或者用旧 Scenario 把新行为判为回归。它影响本 unit 的核心用户场景，而非格式问题。
- **所需修订**：在 delta 中完整 MODIFIED 该既有 Requirement，明确普通离线现在采用 durable 排队，更新切换专属提示仍按原更新语义；保留未改变的多电脑、访问变更、取消与恢复失败 Scenario，并同步相关验收预期。

#### R1-W3 — Work 使用离线机器 token 的鉴权例外没有进入既有 HTTP 凭据契约

- **位置**：[design.md](design.md) 125–139、159–164 行及 [specs/im/gateway-relay.md](specs/im/gateway-relay.md)。
- **证据**：设计明确 Work 三条 HTTP 使用 `identity.authenticateRuntime`，不依赖活动 WS 临时 token；这与源码现有专用持久身份能力相符。但 canonical [gateway-relay.md](../../../specs/im/gateway-relay.md) 262–295 行的“Gateway HTTP 数据操作使用当前注册连接的运行凭据”，特别是 273–276 行，仍规定绑定/恢复的设备凭据只用于重新注册，HTTP 数据操作必须当前注册在线。delta 仅修改 WS Requirement，没有修订该机器 HTTP Requirement，也未给 Work 路由建立受限例外。
- **未修后果**：按设计实现会违反未修改的现有鉴权契约；按 current 实现则 Work HTTP 仍受 WS 生命周期牵连，失去独立恢复边界。下游也无法从 canonical 判断持久 token 到底只可上传 Work，还是可被错误扩大到消息、附件或真人管理入口。
- **所需修订**：完整 MODIFIED 既有 HTTP 凭据 Requirement，明确仅 WorkSync 这一受限机器入口可以使用当前有效 binding/account/epoch 的持久身份且无需活动 WS；原消息镜像、附件和管理/真人入口约束继续保留。给出 WS 断开但 binding 有效时可同步、撤销/交接后被拒以及 runtime token 不能跨用其他 HTTP 入口的消费者 Scenario。

### Recommendations

无额外可选建议。不要为本轮修订新增内部状态面板、替换 DSH 或扩展中心基础设施。



### Author Resolutions

- **R1-W1 — accepted**：真实普通 Web 路径确无稳定 key，不能用 API fixture 补 key 冒充已覆盖。设计新增决策 7、Web 现状落点、IndexedDB attempt 的创建/对账/重试/草稿版本/账号隔离，扩大 M1 与 V5 至真实普通文字和附件入口；spec 增加普通发送回包丢失 Scenario，新增 conversations-messages delta。不新增或调整 UI/交互，按原型指导不创建假新界面；真实浏览器必须验证原体验及新恢复行为。
- **R1-W2 — accepted**：IM delta 完整 MODIFIED“已授权更新的切换阶段持久等待新消息”，普通离线改为 durable 排队；更新提示、多电脑、权限、取消和恢复失败场景保留。
- **R1-W3 — accepted**：IM delta 完整 MODIFIED 机器 HTTP 凭据 Requirement，并为 WS 暂断、撤销/交接和跨入口拒绝增加场景；同步修改 Gateway relay-protocol 凭据 Requirement，原镜像/附件及真人管理约束保留。设计明确 preHandler 和 onSend 两个认证阶段均使用精确路由规则。

以上均为本轮可靠性承诺的必要闭合，不改普通聊天信息组织，不放宽其他入口权限。受审产物发生实质变化，需独立复审；本段不修改 Round 1 的 Issues Found 结论。


## Round 2

### Metadata

- reviewer_target: `/root/feat630_design_review`（同一独立 reviewer，非设计作者）
- review_mode: `full`
- mode_reason: R1-W1 的修订增加普通 Web 持久发送 owner、共享查询接口及 M1 客户端范围，且新增 Gateway 机器凭据 delta；按技能的共享接口/milestone 变化规则采用 full，不仅核对旧问题文字。
- started_at: `2026-10-21T12:27:38+00:00`
- completed_at: `2026-10-21T12:30:41+00:00`
- duration: `183s`
- frozen_head: `47af80ddfbe586d524bc70d306d0ce98573c8d49`
- product_baseline: `11f599938d67f21398570009f1c7e9e0088b81a1`
- reviewed_scope: 本 unit 的 spec/design、五份 delta、M1 和 Round 1 Author Resolutions。
- checkout: 开始时工作区干净；已独立核对从产品基线到本 HEAD 的 apps/packages/src/scripts/config/tests 没有 diff。上游新增文档没有改变本轮产品事实。
- retained_from: Round 1。未受影响的 Node/PA/Channels/IM 源码、Work 协议、DSH 边界和隔离启动证据保持有效；本轮确认相关产品路径无变更，重新对照完整设计与 delta，不将旧结论当作本轮放行依据。
- 本轮只追加本报告，不修改 Round 1 或 Author Resolutions；未启动产品、未部署、未改代码、未提交。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

Round 1 三项原问题已闭合。新增的 Gateway 凭据 delta 复制了旧 canonical 中的一条身份校验规则，与本轮 IM delta 明确保留的机器身份规则互斥；需做一次有界契约消歧，见 R2-W1。

### Coverage 与证据

| 覆盖面 | 本轮核对与判断 |
|---|---|
| 现状、实际组装和职责 | 产品代码与 R1 基线相同，Node 实际组装、global main/query/reconcile 全量 flush、Inbox/wakes 及 Channels 单 active/心跳的 R1 证据仍成立。完整设计仍由 PA 接收/通知/复核，Channels 关联/传输，IM 持久任务及授权，DSH 唯一执行；没有因新增 Web 恢复引入第二 Agent Loop 或改变依赖方向。 |
| 普通 Web 发送与 API 身份 | 重新读取 [message-pane.tsx](../../../../src/IM/frontend/src/features/chat/components/message-pane.tsx) 671–708、[chat-api.ts](../../../../src/IM/frontend/src/features/chat/chat-api.ts) 65–89 和 [messages schema](../../../../apps/im-server/src/schema.sql) 133–160 行；普通路径确实缺 key，现有 conversation/key 唯一约束可复用。[design.md](design.md) 120–130 行已给出首次 POST 前不可变 attempt 持久化、真人本人/会话资格限定查询、404 后仍同 key 重发、异主/异 payload 冲突拒绝及 message_id 合并。它补的是客户端到中心的发送身份，不与 relay_task_id 或 runtime inputId 混用。 |
| Web 恢复与生命周期 | 设计已区分未知结果与明确新发送；自动核对/重发有界；刷新或切回读取本机 attempt；新编辑生成新身份，旧未知 attempt 不后台发送；迟到成功只清匹配草稿版本/附件；退出、切换账号、失去会话资格、多标签和相同正文的两次显式发送都有决定。复用既有 composer attempt owner，未另建独立发送循环。这足以指导普通文字/附件恢复，不再要求测试调用方给普通消息主动补 key。 |
| 普通离线和 delta 保真 | IM delta 73–91 行完整 MODIFIED 原更新等待 Requirement：普通离线改为已保存后待投递；切换提示、多电脑/访问变更、取消/恢复失败均保留。原 R1-W2 冲突已消除；新 ADDED 排队条目与其一致。 |
| Work 机器鉴权及来源复核 | [design.md](design.md) 148–150 行已明确仅三个精确配置路由使用当前 runtime binding/account/epoch，preHandler/onSend 两阶段都采用专用规则，最终分块提交再核撤销；IM delta 26–70 行已保留原消息/附件/skill/真人入口约束，增加 WS 暂断可同步、撤销拒绝与跨入口拒绝。Gateway delta 23–26 行同样声明 Work 独立恢复。R1-W3 所指 Work 例外缺失已闭合，但新 Gateway delta 的旧镜像身份 Scenario 引入本轮范围内的契约冲突，见 R2-W1。 |
| Work 协议、恢复与容量 | 与 R1 相比，Work 批次/分块、cursor 对账、暂存与 epoch、原子 append/project、终态单调、32 项 relay 窗口、有限 WS pending、独立心跳/退避、session scope 与 retired 历史、stop/重启 owner 和升级/回退边界未改；复核完整设计后未见新增不一致。16 MiB 支持上限与更大事件暂停且聊天继续仍是明确限制，不扩大为已实现容量承诺。 |
| 用户约束和客户端呈现 | [design.md](design.md) 29、122–130、198、210、213 行把用户操作限定为原输入框发送、原失败保留草稿/重试及现有 Work 入口，不新增内部状态、气泡、按钮、文案或布局。本轮恢复设计有明确状态决定，但没有新增待用户判断的视觉/交互方案，因此不要求制造新 prototype。未运行浏览器，也不宣称完成视觉保持性验收；真实桌面/窄屏发送、草稿、消息列表和回复已落入实施验收。 |
| 需求、delta、M1 和验收资源 | spec 76–78 行增加普通发送回包丢失 Scenario，范围 123 行增加普通 Web 恢复；新增 conversations-messages delta 三个消费者 Scenario 分别覆盖未知恢复、后来草稿/切换和两次同文发送，canonical 路径正确。M1 221 行已纳入 Web API/composer 内部发送，V5 210 行要求真实入口＋故障代理并验证同 attempt 一次输入、新显式同文两条、后来草稿不被清除和账号隔离；V1–V4/V6–V8、隔离资源与真实 DSH/provider 前置仍有效。未实施/未运行测试并不等于验收已通过。 |

### 架构判断

新增持久 attempt 属于 Web 发送 owner，中心只负责按真人和会话资格核对已保存结果及同 key 内容一致性；它没有侵入 PA 执行去重或把消息恢复状态展示给聊天用户。IndexedDB 的成本对应刷新恢复需求，复用 existing composer attempt 与中心 messages 唯一身份的边界合理。Work 持久机器身份只用于受限同步入口，消息/附件仍依赖活动注册凭据的决定也合理；两份消费者契约对镜像身份如何取得须一致，不能一份要求 owner JWT，一份禁止同一步使用它。

### 历史问题闭环

| issue ID | Author Resolution | 本轮独立证据 | 状态 |
|---|---|---|---|
| R1-W1 | accepted：新增普通 Web attempt、持久快照、查询/同 key 重试、草稿/账号生命周期及真实 V5/M1 | design 120–130、198、210、221 行；spec 76–78、123 行；conversations-messages delta 5–17 行。首次发送身份到刷新恢复、后续草稿与显式新发送已闭合，新增实现落点与浏览器验收一致。 | **closed** |
| R1-W2 | accepted：完整 MODIFIED 更新等待 Requirement | IM gateway-relay delta 73–91 行，普通离线已改为 durable 排队，未改变的更新与恢复 Scenario 保留。 | **closed** |
| R1-W3 | accepted：IM/Gateway 完整声明 Work 持久机器身份例外，双阶段精确路由鉴权 | design 150 行，IM delta 26–70 行，Gateway delta 7、23–26 行；离线例外和其他 HTTP 入口拒绝已明确。新 delta 的另一条镜像身份旧规则冲突单独记 R2-W1，不回写或扩大旧 issue。 | **closed** |

### Issues

#### R2-W1 — 新 Gateway 凭据 delta 对同一镜像身份校验仍要求 owner JWT，与 IM delta 的机器身份规则互斥

- **位置**：[specs/gateway/relay-protocol.md](specs/gateway/relay-protocol.md) 13–16 行，对照 [specs/im/gateway-relay.md](specs/im/gateway-relay.md) 45–48 行。
- **证据**：Gateway 完整 MODIFIED 条目仍写“恢复旧 owner 记录或处理新的外部镜像消息”时，`/im/v1/me`、`/im/v1/nodes` 继续用 owner JWT 查询真实账号/节点；同轮 IM delta 对“准备或恢复外部消息镜像”明确要求 `GET /im/v1/gateway/identity`，并禁止使用真人 `/me` 或节点管理列表。两个前置覆盖同一恢复过程，不能同时满足。
- **当前事实**：Gateway 这句话确实来自旧 canonical [relay-protocol.md](../../../specs/gateway/relay-protocol.md) 352–355 行，属于本轮复制进完整 MODIFIED 的既有契约漂移，不是本轮新增 runtime 故障。实际 Node [main.ts](../../../../apps/node/src/main.ts) 269–283 行给 ExternalChannels 的 IM helper 使用注册返回的机器凭据；[external.ts](../../../../packages/personal-assistant/src/external.ts) 265–284 行镜像路径没有上述 owner JWT 的 `/me`/`/nodes` 调用。IM [server.ts](../../../../apps/im-server/src/server.ts) 178–186 行已有仅机器凭据的 identity 路由，[server E2E](../../../../apps/im-server/tests/e2e/server.test.ts) 8–9 行也区分设备持久 token 被拒与当前注册 token 成功。这里不声称当前镜像路径已经执行了新 identity 查询。
- **未修后果**：新 Work 鉴权设计归并后，两包权威契约仍指导实现者在同一镜像恢复环节使用相反凭据。维护或验收可能重新引入 owner JWT 依赖，或为满足旧 Scenario 而放宽机器 helper/真人数据入口；这与本轮“只给 Work 加受限离线例外，其余身份边界保持”的决定不相容。
- **所需修订**：在已经受审的 Gateway MODIFIED 条目内，消歧这一个 Scenario，使当前机器归属核对与 IM 的受限 gateway identity 规则一致，保留 owner 调和、当前节点一致性、失败保留记录及不得用真人凭据写机器数据的保证。不要以“保留未变 Scenario”为由重新确认互斥的旧端点规则；本问题只要求对齐这一契约，不扩展为新的外部镜像功能或放宽 Work 以外的入口。

### Recommendations

无额外可选建议。

### Author Resolutions

- **R2-W1 — accepted**：Gateway 旧 canonical 的 owner JWT `/me`、`/nodes` 语句与 IM 已有机器身份契约互斥。已在 Gateway delta 的同一 Scenario 中，改为“需要核实当前机器管理者时”遵循现有 `GET /im/v1/gateway/identity` 及当前注册凭据，保留 node/owner 核对、owner 调和、失败保留记录和不得冒用真人入口的约束。来源核对为 `apps/node/src/main.ts` 的机器 helper 和 `external.ts` 现有镜像接线；不宣称现有镜像已经调用该查询，也不新增镜像能力。其余受审产物未变，本轮仅此凭据契约消歧，提交独立复审。


## Round 3

### Metadata

- reviewer_target: `/root/feat630_design_review`（同一独立 reviewer，非设计作者）
- review_mode: `closure`
- mode_reason: 相对 Round 2 冻结版本，仅 Gateway delta 的既有 shadow 身份 Scenario 做局部消歧；其余需求、设计、接口、M1 与产品代码无变更，本轮核闭合及该 Scenario 的两包一致性。
- started_at: `2026-10-21T12:32:14+00:00`
- completed_at: `2026-10-21T12:32:51+00:00`
- duration: `37s`
- frozen_head: `863605b43b715cde715716a91c61deb35c1426e2`
- product_baseline: `11f599938d67f21398570009f1c7e9e0088b81a1`
- retained_from: Round 2（full）。R1-W1/R1-W2/R1-W3 已关闭，普通 Web attempt、Work 协议及鉴权、职责、容量、迁移、用户约束与验收证据未受本次消歧影响。
- checkout: 开始时工作区干净；已独立核对 `47af80ddfbe586d524bc70d306d0ce98573c8d49..HEAD` 仅报告追加和 Gateway delta 两行语义变化。
- 本轮只追加本报告；原 Round/Author Resolutions 保留，未修改设计或代码，未启动服务、部署或提交。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R2-W1 已关闭，未发现本次局部修订引入新的实质问题。结合保留的 Round 2 full 覆盖，当前冻结设计满足 Gate 2 的文档审查条件；不代表产品已实施或运行验收通过。

### Coverage 与证据

- [Gateway delta](specs/gateway/relay-protocol.md) 13–16 行现在要求在需核实机器管理者时，使用当前注册运行凭据查询 `GET /im/v1/gateway/identity`，核对 node_id/owner_id，保留 owner 调和、身份失败时保留待同步记录，以及不使用真人 `/me`、节点管理列表或本地旧 owner 作为授权事实的约束。
- 与 [IM delta](specs/im/gateway-relay.md) 45–48 行对照，两个消费者对所用端点、当前注册机器凭据及禁止真人管理入口的规则一致；Gateway 7、23–26 行的 Work 受限持久身份例外保持，未将该身份扩大到镜像入口。
- Round 2 对 [Node main](../../../../apps/node/src/main.ts) 269–283、[external.ts](../../../../packages/personal-assistant/src/external.ts) 265–284、[server.ts](../../../../apps/im-server/src/server.ts) 178–186 及 [server E2E](../../../../apps/im-server/tests/e2e/server.test.ts) 8–9 行的源码证据保持有效。本次文字明确对齐既有 IM 规则，不声称当前镜像路径已经调用该查询，也不新增镜像功能。
- spec/design、其他四份 delta、M1/验证矩阵均与 Round 2 相同，故保留此前 full 覆盖；本轮没有前端、运行拓扑、协议能力或权限授予变化，不扩大为实现或视觉验收。

### 历史问题闭环

| issue ID | Author Resolution | 本轮证据 | 状态 |
|---|---|---|---|
| R2-W1 | accepted：同一 shadow Scenario 改用既有 gateway identity 与当前注册凭据，保留归属核对、owner 调和、失败保留及真人入口限制，明确不增镜像功能 | Gateway delta 13–16 行与 IM delta 45–48 行已一致；旧 owner JWT `/me`/`/nodes` 要求已移除，Work 独立身份例外及其他 Scenario 未变。 | **closed** |

R1-W1、R1-W2、R1-W3 保持 Round 2 的 **closed**。

### Issues

无。

### Recommendations

无。


### Author Resolutions / Gate 2 收口

- 作者核实 Round 3 无 findings/recommendations，接受其 Approved；R1 三项与 R2 一项均已关闭，无实质异议。此后仅追加审查报告，不修改受审 spec/design/delta/M1。
- `validated_at`: `863605b43b715cde715716a91c61deb35c1426e2`；`executed_base`: 产品基线 `11f599938d67f21398570009f1c7e9e0088b81a1`；`effective_base`: `b6050dcfc9e85209533ab11a0efd25f1358bece0`；`effective_through`: `863605b43b715cde715716a91c61deb35c1426e2` 的受审产物。
- 最终 fetch 确认 origin/main 仍为上述 effective_base，产品路径 apps/packages/src/scripts/config/tests 与执行基线无差异；上游增加的 bugfix-631 首文档不改变本设计或其生产事实，因此 retained。报告提交属非实质文档追加，不新开审查轮次。
- 文档完整性与 diff whitespace 检查通过；未运行产品验收或声称已修复。本 unit 留在 active，实施须由默认 change-orchestrator-simple 接手，另行完成实现、静态审查、产品验收及交付。
