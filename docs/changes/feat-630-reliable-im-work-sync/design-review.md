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
| 实际产品组装和现状断言 | [Node main](../../../apps/node/src/main.ts) 的 100–115、240–249、301–305、357–369 行确实组装 GlobalAgent/Inbox/Channels/DSH，实际 relay 进入 `globalProduct.receive`；DSH ready 内恢复以 `settlePartitions` 并行，relay ready 回调的恢复则按顺序 await。设计移除 ready 全量 Work 依赖的落点正确，不能把仅测试的实现当产品入口。 |
| Work 耦合、输入和执行恢复 | [global-agent.ts](../../../packages/personal-assistant/src/global-agent.ts) 的 67–108、138–143、204–216、392–398、472–555 行确认 main/query/reconcile 的 flush、Inbox 之前的 main、ACK 之后的 wake，以及稳定 `inbox-wake:agent:watermark`；[inbox.ts](../../../packages/personal-assistant/src/inbox.ts) 的 18–32、41–51、137–143、258–288 行确认唯一输入、wakes、读承诺与 journal。设计复用这些事实并新增同事务待回执，比另建输入任务总账更合适；控制 intent 复用 [session-controls.ts](../../../packages/personal-assistant/src/session-controls.ts) 22–55 行，职责仍属 PA。 |
| 实时关联、超时、心跳 | [Channels](../../../packages/channels/src/index.ts) 206–266 行确认单 active、按 type 匹配通用 ACK、十秒超时断连接和队列忙跳过心跳；240–241 行已有不阻塞接收循环的 callback。设计的 request_id/generation、稳定业务身份与有界窗口分别承担传输关联、业务幂等和容量控制，职责有区分；保留 server 发起请求原 request_id、业务 owner 必要串行和撤销终止是必要约束。 |
| 中心投递、确认和普通离线 | [messaging.ts](../../../apps/im-server/src/messaging.ts) 555–584、633–687 行确认 message/relay 同事务、落库后可能 503 和当前逐条投递；[gateway.ts](../../../apps/im-server/src/gateway.ts) 490–515、1052–1078 行确认回执直接覆盖状态与重连全量读取。设计复用 outbox、有界重投和终态单调合理；delta 的普通离线冲突见 R1-W2。 |
| Session 权威与权限 | [work.ts](../../../apps/im-server/src/work.ts) 41–74、103–143、481–507 行确认 main 替换/retired、profile 归属及 query 的 session/node/global_main 检查。把权威 scope 从历史显示事件拆出小请求，既能解除历史依赖，也保留 query 信任来源；历史重放不能激活 retired main 的决定闭合。PA 来源、审批和复核仍落在 [personal-assistant.ts](../../../packages/personal-assistant/src/personal-assistant.ts) 43–84、113–173 行及现有服务端 authority/action；未发现需要另造权限系统的理由。 |
| Work 持久性、大小与背压 | [work.ts](../../../apps/im-server/src/work.ts) 76–169 行确认 node/journal 连续游标、事务 append/project 与重复身份验证；[inbox.ts](../../../packages/personal-assistant/src/inbox.ts) 281–288 行确认原 journal/seq 与未清理历史。设计已规定完整请求字节上限、16 KiB parts、全局/单节点并发、暂存配额、hash/epoch、过限暂停、无进度清理、未知结果查 cursor/parts、惰性读取与 stop。16 MiB 是本设计明确的支持上限，更大事件中心完整回看不在其承诺内，不能把其作为已验收的无限容量能力。 |
| 机器身份、迁移和恢复一致性 | [identity.ts](../../../apps/im-server/src/identity.ts) 565–576 行确认持久 runtime token 校验当前 binding/account；[messaging.ts](../../../apps/im-server/src/messaging.ts) 33–36 行、[gateway.ts](../../../apps/im-server/src/gateway.ts) 53–74 行确认现有 HTTP principal 使用活动连接临时 token；[server.ts](../../../apps/im-server/src/server.ts) 108–118、143–151 行在请求和响应阶段调用通用 principal。专用三路由而不扩大通用 principal 的职责合理，实现时须使两阶段 hook 都采用该专用鉴权规则。能力协商、IM 先行、新旧协议共用游标、旧中心拒绝新 Node 和回滚先停新 Node 已说明；canonical 机器凭据例外缺失见 R1-W3。 |
| 用户约束、真实客户端和 delta | 原始需求明确普通聊天不要内部阶段。设计不新增状态枚举、布局或运维气泡，保留主动 Work、必要失败与授权入口，因此本轮不要求新视觉原型。未启动浏览器，未声称完成视觉或产品运行验收；客户端核对来自 [message-pane.tsx](../../../src/IM/frontend/src/features/chat/components/message-pane.tsx) 651–708 行与 [chat-api.ts](../../../src/IM/frontend/src/features/chat/chat-api.ts) 65–77 行，普通消息未知结果闭合问题见 R1-W1。三个 delta 的 canonical 路径正确；修改首条 WS Requirement 时保留了原非法帧、不支持类型和 durable config boundary 语义，但没有修订两个受影响的既有 Requirement。 |
| Milestone、验收与范围 | 单 M1 把可靠接收、WS 和 WorkSync 作为一个用户可交付结果，避免仅拆上传接口就声称成功。Runbook 复用现有 e2e-up/down 和 secret-free [E2E config](../../../config/e2e/gateway.yaml)，隔离身份来源已说明；故障代理与 deterministic provider 是明确待交付 fixture，现有 [配置连续性 E2E](../../../tests/e2e/critical_paths/test_agent_config_context_continuity_critical_path.py) 有真实 DSH HTTP provider 接线先例。V1–V8 覆盖强杀窗口、晚 ACK、分块、权限、多目标、负载及真实浏览器，负载阈值有基线且未冒充人数承诺。V5 的真实浏览器普通消息要求目前超出设计落点，见 R1-W1；其余验收方案可指导实施，本轮未运行也不代表已通过。 |

### 架构判断

PA 持有本地消息交接、通知/消费和外发恢复；Channels 持有连接、关联和有限在途请求；IM 持有中心消息/任务、账号/设备/聊天资格与 Work 投影。新增 WorkSync 是独立上传 owner，而非第二 Agent Loop；现有同步 append/project 与 SQLite 在有界批次下继续复用，尚无证据要求新增 broker 或第二投影体系。独立 HTTP 传输也有明确成本：必须维护专用机器鉴权和 parts 生命周期，设计已给出 owner、存储/清理、游标及重试边界。上述责任划分与 DSH 公开入口、依赖方向一致。

### 历史问题闭环

本轮为 Round 1，无历史 issue 或 Author Resolution。

### Issues

#### R1-W1 — 普通 Web 消息没有稳定发送身份，V5 的 POST 回包丢失恢复在当前实施范围内无法成立

- **位置**：[design.md](design.md) 28、99、155、195、206 行。
- **证据**：设计 V5 要求“已保存后 POST 响应丢失”仍有“一次消息/稳定 idempotency key”，同时声明不改 Web 组件，M1 落点只列 Node/IM/PA/Channels/contracts。实际普通文本路径在 [message-pane.tsx](../../../src/IM/frontend/src/features/chat/components/message-pane.tsx) 678–684 行没有 attempt/key，直接 `onSend(wireContent, submittedAttachments)`；只有私聊 interactive background 路径生成并复用 key。失败后 686–689 行保留草稿返回；[chat-api.ts](../../../src/IM/frontend/src/features/chat/chat-api.ts) 75–77 行只在 caller 传入 key 时添加请求头；[messaging.ts](../../../apps/im-server/src/messaging.ts) 555–575 行也只按该可选 key 查重。
- **未修后果**：普通消息在中心 commit 后丢 HTTP 回包，客户端按现有行为保留草稿并报告发送错误；用户重试没有原 key，服务端会插入第二条消息和第二组 relay。修改中心离线 503 或 relay 去重均不能把这两个新 message identity 合并。此结论来自实际代码路径，非本轮浏览器复现。
- **所需修订**：把普通 Web 发送 attempt 的稳定身份、未知结果核对/重试和必要生命周期纳入设计及 M1 落点，保持现有聊天信息层级，不需要增加内部状态 UI。V5 必须从真实普通文本/附件发送入口丢 POST 回包并恢复验证，不以 API 测试主动补 key 代替客户端。若要缩小该场景，须先明确调整承诺及验收范围，不能让 V5 与不改客户端的决定同时保留。

#### R1-W2 — 新普通离线排队契约会与保留下来的“普通离线失败”Scenario 正面冲突

- **位置**：[specs/im/gateway-relay.md](specs/im/gateway-relay.md) 26–37 行及 [design.md](design.md) 159–164 行。
- **证据**：delta 新增普通节点不可达时“返回已保存的同一消息、保留待投递、不误报未保存、恢复自动投递”；canonical [gateway-relay.md](../../specs/im/gateway-relay.md) 297–315 行的“已授权更新的切换阶段持久等待新消息”仍明确规定“普通离线”沿用失败语义。该 Requirement 未出现在 MODIFIED/REMOVED。按 [delta 归并规则](../../specs/CONTRIBUTING.md)，ADDED 只追加，不会删除或覆盖这条原 Scenario。
- **未修后果**：归并后 current 同时要求普通离线返回已保存并自动恢复，又要求普通离线失败；实现者或后续回归可能保留现有 503，或者用旧 Scenario 把新行为判为回归。它影响本 unit 的核心用户场景，而非格式问题。
- **所需修订**：在 delta 中完整 MODIFIED 该既有 Requirement，明确普通离线现在采用 durable 排队，更新切换专属提示仍按原更新语义；保留未改变的多电脑、访问变更、取消与恢复失败 Scenario，并同步相关验收预期。

#### R1-W3 — Work 使用离线机器 token 的鉴权例外没有进入既有 HTTP 凭据契约

- **位置**：[design.md](design.md) 125–139、159–164 行及 [specs/im/gateway-relay.md](specs/im/gateway-relay.md)。
- **证据**：设计明确 Work 三条 HTTP 使用 `identity.authenticateRuntime`，不依赖活动 WS 临时 token；这与源码现有专用持久身份能力相符。但 canonical [gateway-relay.md](../../specs/im/gateway-relay.md) 262–295 行的“Gateway HTTP 数据操作使用当前注册连接的运行凭据”，特别是 273–276 行，仍规定绑定/恢复的设备凭据只用于重新注册，HTTP 数据操作必须当前注册在线。delta 仅修改 WS Requirement，没有修订该机器 HTTP Requirement，也未给 Work 路由建立受限例外。
- **未修后果**：按设计实现会违反未修改的现有鉴权契约；按 current 实现则 Work HTTP 仍受 WS 生命周期牵连，失去独立恢复边界。下游也无法从 canonical 判断持久 token 到底只可上传 Work，还是可被错误扩大到消息、附件或真人管理入口。
- **所需修订**：完整 MODIFIED 既有 HTTP 凭据 Requirement，明确仅 WorkSync 这一受限机器入口可以使用当前有效 binding/account/epoch 的持久身份且无需活动 WS；原消息镜像、附件和管理/真人入口约束继续保留。给出 WS 断开但 binding 有效时可同步、撤销/交接后被拒以及 runtime token 不能跨用其他 HTTP 入口的消费者 Scenario。

### Recommendations

无额外可选建议。不要为本轮修订新增内部状态面板、替换 DSH 或扩展中心基础设施。



### Author Resolutions

- **R1-W1 — accepted**：真实普通 Web 路径确无稳定 key，不能用 API fixture 补 key 冒充已覆盖。设计新增决策 7、Web 现状落点、IndexedDB attempt 的创建/对账/重试/草稿版本/账号隔离，扩大 M1 与 V5 至真实普通文字和附件入口；spec 增加普通发送回包丢失 Scenario，新增 conversations-messages delta。不新增或调整 UI/交互，按原型指导不创建假新界面；真实浏览器必须验证原体验及新恢复行为。
- **R1-W2 — accepted**：IM delta 完整 MODIFIED“已授权更新的切换阶段持久等待新消息”，普通离线改为 durable 排队；更新提示、多电脑、权限、取消和恢复失败场景保留。
- **R1-W3 — accepted**：IM delta 完整 MODIFIED 机器 HTTP 凭据 Requirement，并为 WS 暂断、撤销/交接和跨入口拒绝增加场景；同步修改 Gateway relay-protocol 凭据 Requirement，原镜像/附件及真人管理约束保留。设计明确 preHandler 和 onSend 两个认证阶段均使用精确路由规则。

以上均为本轮可靠性承诺的必要闭合，不改普通聊天信息组织，不放宽其他入口权限。受审产物发生实质变化，需独立复审；本段不修改 Round 1 的 Issues Found 结论。
