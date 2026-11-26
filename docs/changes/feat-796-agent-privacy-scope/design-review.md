# feat-796: Agent 与个人助手可见性及双向通信权限管理 — 设计审查报告

## Round 1

### Metadata

- **reviewer_target**: `docs/changes/feat-796-agent-privacy-scope` @ `a7c9a4d328cae35fe69f65997f0b69e96ec49b7f`（branch `unit/feat-796-agent-privacy-scope`，base `origin/develop` `95f074c7a`）
- **review_mode**: `full`
- **mode_reason**: Gate 2 首轮独立设计审查，此前无历史审查轮次，需对现状断言、关键决策、用户确认边界、跨端 UX、模型上下文、delta-spec 与 Milestone 全量核验。
- **started_at**: `2026-11-26T23:38:01+09:00`
- **completed_at**: `2026-11-26T23:56:15+09:00`
- **duration**: `18m 14s`

### Verdict

**Issues Found (Changes Requested)** — `4 CRITICAL, 5 WARNING, 2 Recommendation`

---

### Coverage 与证据

#### 1. 现状断言与真实生产入口核实

已在工作树内逐项核查真实生产组装入口（`apps/im-server/src/server.ts`、`apps/node/src/main.ts`、`packages/dsh-integration/src/index.ts`、`packages/personal-assistant/src/`、`src/IM/frontend/src/`、`src/IM/ios/NanoIM/`）与现行 canonical specs：

- **现状差距 1–5 总体成立，但后端拦截面与 iOS 创建面盘点不完整**：
  - `contacts.ts:68-100` 与 `identity.ts:154-165` 确实未按 `collaboration_scope === 'owner_only'` 隐藏非主人可见性，且对 `personal_space_enabled = 1` 团队成员仅豁免了 `personal_agent_bindings`；
  - `product-contracts/src/collaboration.ts:22` 在 `scope === 'owner_only'` 且 `!facts.ownerDirect` 时一律返回 `'skip'`，`schema.sql:571-587` 与 `personal-agent.ts:261-283` 确实将 `owner_only` 限制在真人主人 1:1 直聊并切断了私有 PA 的 `observer` 旁观；
  - `packages/dsh-integration/src/agent-config.ts:127-149` 与 `chat-scope.ts:271-300` 确实已把 `collaborationScope` 排除在运行时执行指纹之外并支持原地撤回未送达输入，“不修改 `packages/dsh-integration`”的边界判断成立；
  - **偏差点**：`design.md` 漏盘了 `apps/im-server/src/trajectory.ts`（原生轨迹查看器与附件鉴权）、`apps/im-server/src/conversation-actions.ts`（会话命令与分支复制）、`apps/im-server/src/messaging.ts:126, 296-305, 852-869` / `gateway.ts:63, 141, 214, 579, 693` 的硬编码 `space_id` 相等性门禁，以及原生 iOS 新建助手 `AgentsView.swift`（`AgentCreateView`）与聊天只读视图 `ConversationView.swift`（详见 `R1-C1`、`R1-C2`、`R1-W1`）。

#### 2. 架构总览、关键决策与复用判断

- **整体方向合理**：保持 `'team' | 'owner_only'` 协议枚举不变（决策 1）、不改写存量 `agent_profiles.space_id`（决策 2）、以中心权威会话属性统一入/出站与群成员互斥（决策 3）、在配置事务内执行外人群退群与历史 1:1 只读收口（决策 4）、分离 PA 对外参与域与主人旁观域（决策 5），均符合 [AGENTS.md](../../../AGENTS.md) 与 [SPEC.md](../../../SPEC.md) 的跨包边界，未引入平行存储或第二套执行循环。
- **关键机制存在 4 处闭合缺口**：
  1. 决策 2 保留普通 Agent 的 `space_id = 'personal:<owner_id>'` 后，中心 IM 在跨空间会话（`company:default`）上的 Gateway 鉴权、直聊解析、Work 路由、实时广播与原生轨迹均仍按 `agent.space_id === c.space_id` / `canAccessSpace(viewer, profile.space_id)` 硬拦；而拟议放宽 `currentActorCanAccess` 又会破坏 `tenancy.test.ts:400-402` 并让 `owner_only` Agent 混入公开群（`R1-C1`、`R1-C2`）；
  2. 决策 3 与节点入站分类混淆了 `ownerDirect`（真人主人 1:1 直聊，承载 `single_thread` 心跳主会话绑定与即时高优唤醒）和 `ownerInternal`（同主人内部会话准入），按当前写法会导致心跳主会话被群聊/`agent-agent` 私聊劫持、专属群普通消息错误升级为 `'high'` 优先级，且 `SingleThread` 的群背景定时器仍被 `owner_only` 短路（`R1-C3`）；
  3. 决策 5 的节点侧 `ownerObserved` 误将 `meta.pa_observation === true` 当作纯旁观充分条件（忽略了 PA 同时作为外人群参与者时该字段也为 `true`），且 PA 向外部渠道发消息时先由 `ExternalChannels` 发送并持久化 `turn_start` 镜像帧、后做 `pa.action.prepare` 权限检查（`R1-C4`）；
  4. 同主人名下跨空间存量 Agent（`company:default` 与 `personal:<owner_id>`）的内部建群/私聊（`R1-W3`）以及切换 `owner_only` 时的 RPC/事务顺序与陈旧元数据窗口（`R1-W2`）尚未闭合。

#### 3. 用户原始需求与澄清约束覆盖核查

| 用户需求 / 确认约束（`spec.md`） | 设计覆盖状态 | 核查证据与缺口 |
|---|---|---|
| Q1：两档模型，PA 与普通 Agent 新建均默认「团队公开」，各创建入口支持直接选「私有」零瞬间暴露 | 部分缺失 | Web 各入口与 PA `agent_creation` 已覆盖，但 iOS 新建普通/全局 Agent（`AgentsView.swift` 的 `AgentCreateView`）未渲染 `collaboration_scope` 选择器（`R1-W1`）。 |
| Q1 延伸：启用个人空间的有效团队成员将普通 Agent 设为「团队公开」对同事可见、可聊、可看 Work，且不泄漏个人历史会话/停用后个人仍可用 | 链路未闭合 | 目录发现已覆盖，但 `messaging.ts:126`、`work.ts:587`、`gateway.ts:214`、`trajectory.ts`、`conversation-actions.ts:150` 仍因跨空间拦截导致同事发消息无回复、看 Work/轨迹 404（`R1-C1`、`R1-C2`）。 |
| 原始需求：仅主人本人或主人名下 Agent 可与私有助手私聊或拉群协同，禁止对外联系 | 存在缺陷 | 专属群唤醒优先级与 `SingleThread` 会话绑定/背景定时器冲突（`R1-C3`）；同主人混合空间 Agent 互拉群/私聊会 404（`R1-W3`）；群话题关注与回执仍硬判 `'team'`（`R1-W4`）。 |
| Q2(1)：切为私有时自动退出含外人群聊，保留专属群；含私有助手的群锁定私密且禁混入外人 | 存在竞态与平台缺口 | 节点 RPC 先于中心退群事务提交、群由内变外后的陈旧 `owner_internal` 标记（`R1-W2`），以及 iOS 建群默认 `public` 未锁定（`R1-W1`）。 |
| Q2(2)：历史同事 1:1 私聊保留记录、只读提示未对外开放、双向封禁，切回公开自动恢复 | 存在跨端与操作破口 | iOS 只读态会把历史 1:1 私聊误显示为“公开群 · 加入后可参与”（`R1-W1`）；Web 历史私聊仍暴露分支按钮/失效设置跳转且无法置顶免打扰（`R1-W4`）。 |
| Q2(3)：私有 PA 保持对主人允许会话的静默旁观记事，绝不对外发声或代主人发言 | 存在破口 | 外人群 `participant` 积压因 `pa_observation: true` 漏网、飞书出站先落库发送后鉴权、未建会话同事 `resolve` 先抛非结构化错误（`R1-C4`）。 |

#### 4. 专项设计检查（`agent-context-review` + `frontend-experience-review`）

- **Agent Context Engineering（设计模式）**：
  - 静态系统提示词前缀零改动、复用 `agent-config.ts` 原地热更新保持 Prompt Cache 稳定，符合 [agent-context-engineering.md](../../development/agent-context-engineering.md)；
  - `personal-agent-creation.ts` 的 `collaboration_scope` 工具参数描述清晰；
  - **上下文问题**：PA 在飞书出站、未建立直聊同事目标解析及 `gateway.ts:455` 错误码包装三处无法向模型交付 `design.md` L168 承诺的结构化 `{ status: "not_sent", changed_reason: "collaboration_scope_restricted", message: "..." }` 恢复指引（归入 `R1-C4`）；同主人专属群与 `SingleThread` 的会话/优先级错位会污染心跳主会话上下文（归入 `R1-C3`）。
- **Frontend Experience（设计模式）**：
  - 不单独制作 `prototype.html` 的判断符合 `frontend-experience-review/references/prototype-and-runbook.md`（改动均落在既有表单、弹窗和聊天横幅槽位，无新页面骨架或方案分歧）；
  - **体验问题**：iOS 新建助手缺权限选择、iOS 历史私聊只读文案错配为“公开群”（归入 `R1-W1`），Web 历史只读私聊的分支按钮、顶栏入口与置顶/免打扰被连带锁死（归入 `R1-W4`），以及首次引导页文案克制建议（`R1-R1`）。

#### 5. `本次审查安排`、Delta-spec 与 Milestone 核查

- **`本次审查安排` 与 Runbook**：已组合 `change-code-review`、`frontend-experience-review`、`agent-context-review` 并在隔离真栈验证桌面/移动视口与模型结构化拒绝反馈，能力选择与本任务风险匹配；Runbook 构建前置补充建议见 `R1-R2`。
- **Delta-spec 核查**：9 份 delta-spec 的目标路径与 `### Requirement:` 标题均与现行 `docs/specs/` 精确对应，`./scripts/docs-check` 当前通过；但存在 `external-channels.md` / `ios-client.md` / `im/spec.md` 同步遗漏，以及 `web-chat-ux.md`、`routing-delivery.md` 中 `MODIFIED` 块删减既有 Scenario 条款的归并丢失风险（`R1-W5`）。
- **Milestone 核查**：单 Milestone `M1-agent-privacy-scope` 切分合理（中心鉴权、节点分类与前端状态紧密耦合，拆分反而制造中间半残态），退出标准区分了 `[reviewer]` 与 `[worker]`；修正下述阻塞项后需同步覆盖原生轨迹与 iOS 契约测试。

---

### 历史问题闭环

首轮审查（Round 1），无历史问题。

---

### Issues

#### `R1-C1` [CRITICAL] 跨个人空间 `'team'` 普通 Agent 在中心 IM 会话读写、网关回传、命令与直聊解析链路上仍被硬编码 `space_id` 门禁阻断，且拟议放宽 `currentActorCanAccess` 会破坏既有租户隔离测试并让私有助手混入公开群

- **位置**：
  - `docs/changes/feat-796-agent-privacy-scope/design.md` L12、L14、L76–78
  - `apps/im-server/src/messaging.ts` L126、L296–305、L852–869
  - `apps/im-server/src/gateway.ts` L63、L141、L214–217、L579、L693
  - `apps/im-server/src/work.ts` L184–186、L587
  - `apps/im-server/src/conversation-actions.ts` L150、L280–289
  - `apps/im-server/src/conversation-access.ts` L20–31、L48–52、L88–102
  - `apps/im-server/tests/tenancy.test.ts` L400–402
- **证据**：
  1. 个人空间入队成员 C（`personal_space_enabled = 1, membership_status = 'active'`）名下普通 Agent 的 `agent_profiles.space_id` 为 `'personal:u_c'`。当同事 B 与该 `'team'` 普通 Agent 建立会话时：
     - `messaging.ts:296-300` 仅对 `canContactPersonalAgent` 将会话 `space_id` 设为 `'company:default'`；若不改为 `canTeamContactAgent`，会话落入 `'personal:u_c'`，`requireSpace(colleagueB, 'personal:u_c')`（L304）直接抛 `404`；
     - 即使会话建在 `'company:default'`，`Messaging.access` 的 Gateway 分支（`messaging.ts:126`）硬判 `if (!agent || agent.space_id !== c.space_id || !agentAvailable(this.db, agent)) fail(404, "conversation_id not found")`——导致节点端所有回写/读取（`publishAgent` L501、`ChatStreaming` 流式 `turn_start/delta` `gateway.ts:63`、`node.delivery_receipt` `gateway.ts:579`、`agent.config.boundary` `gateway.ts:693`、图片与文件上传 `media.ts:205,218,239,320`）全部 `404`，审批回复 `gateway.ts:141` 也因 `profile.space_id !== conversation.space_id` 被静默丢弃；
     - 当该 `'team'` 普通 Agent 主动调用 `send_message(target = colleagueB)` 时，`Messaging.resolveTarget`（`messaging.ts:852-865`）检查 `canActorAccess(this.db, colleagueB, 'personal:u_c')` 直接抛 `404 target not accessible`，且仅在 `a.space_id`（`personal:u_c`）下查找 `direct_key`，找不到 `'company:default'` 中的既有直聊；
     - 同事 B 访问该全局 Agent 的 Work 页面（`work.ts:587` 调用 `ctx.identity.requireSpace(user, p.space_id)`）返回 `404`；实时 `agent.work.updated` 广播在 `gateway.ts:214-217` 被 `canAccessSpace(user, profile.space_id)` 二次过滤丢弃；群 `conversations(info)` 节点名在 `work.ts:184` 因 `peer.space_id !== 'company:default'` 被隐藏；聊天框斜杠命令/技能在 `conversation-actions.ts:150` 因 `a.space_id !== conversation.space_id` 恒返回 `unavailable`。
  2. 反过来，`design.md` L77 提议在 `currentActorCanAccess` 中“允许活跃团队成员的 Agent 存在于 `company:default` 会话记录中”：
     - `apps/im-server/tests/tenancy.test.ts:400-402` 明确断言：`company:default` 中的双 Agent 直聊在其中一个 Agent `space_id` 变为 `personal:<owner>` 时必须返回 `404`（`observerOwners` L22 也要求双 Agent 直聊 `p.space_id === space`）；
     - 一旦 `currentActorCanAccess(db, agentUser, 'company:default')` 对活跃团队成员的 `owner_only` Agent 返回 `true`，`conversationRowAccess`（`conversation-access.ts:90-101`）、`readableConversationIds`（`conversation-access.ts:48-51`）与 `joinConversation`（`messaging.ts:778-785`）会自动允许该 `owner_only` Agent 读取、搜索并加入 `company:default` 的全部公开群（`visibility = 'public'`）！
- **未修后果**：启用个人空间的团队成员公开普通 Agent 后，同事虽然能在目录看到它，但发消息永远收不到流式/正式回复、打不开 Work、用不了斜杠命令（`spec.md` 第 2 条核心验收标准直接失败）；同时泛化修改 `currentActorCanAccess` 会击穿现有 `tenancy.test.ts` 并打开 `owner_only` Agent 访问公开群的越权缺口。设计需逐一明确上述全部跨空间门禁的精确准入函数（区分通用空间归属与 `'team'` 协作跨空间会话成员准入，且对 `owner_only` Agent 显式阻断非成员 `public` 群读写与加入）。

---

#### `R1-C2` [CRITICAL] 遗漏原生 DSH 轨迹查看器与附件鉴权（`apps/im-server/src/trajectory.ts`），导致公司空间私有全局 Agent 向同事泄露实时轨迹，且个人空间公开全局 Agent 原生轨迹不可读

- **位置**：
  - `docs/changes/feat-796-agent-privacy-scope/design.md` L14、L76–78、L87–91
  - `apps/im-server/src/trajectory.ts` L64–70（`create`）、L165–172（`valid`）、L174（`check`）、L198–208（`authorizeLocal`）、L245–256（`authorizeAttachmentSources`）
  - `apps/im-server/src/control.ts` L476–505（`ConfigOperations.commit`）
- **证据**：
  1. `trajectory.ts` 的 4 个鉴权入口仅检查 `canAccessSpace(user, profile.space_id)` 与 `personal_agent_bindings`，完全未检查 `profile.collaboration_scope` 或 `profile.owner_id === user.owner_id`：
     - 对于 `personal_space_enabled = 0` 的团队成员（例如团队管理员或先加入团队未建 PA 的成员），其全局 Agent 的 `space_id = 'company:default'`。将其设为 `'owner_only'` 后，任何有效团队同事仍可通过 `POST /im/v1/agents/:agent_id/trajectory/prepare`、`/trajectory/authorize`、`/trajectory/authorize-attachment` 及 `/im/ws/agent-trajectory` 直接读取该私有助手的完整推理过程、工具调用与工作区附件；
     - 若同事在 `'team'` 期间已打开 `/im/ws/agent-trajectory` 实时连接，主人切换为 `'owner_only'` 时 `ConfigOperations.commit` 未调用 `ctx.gateway.trajectory.check()` 主动踢出非主人观察连接，实时流将持续向外部同事推送私有助手后续执行的模型输出。
  2. 对 `personal_space_enabled = 1` 团队成员设为 `'team'` 的普通全局 Agent（`profile.space_id = 'personal:<owner_id>'`），同事在 Work 视图点击会话打开原生轨迹时，`trajectory.ts` 因 `!canAccessSpace(user, 'personal:<owner_id>')` 直接抛 `该执行不可访问`。
- **未修后果**：私有全局 Agent 存在严重的跨同事实时思考/工具/工作区附件越权泄漏；个人空间团队成员公开全局 Agent 的 Work 详情页点进会话即报错失效。设计必须将 `trajectory.ts` 的全部鉴权点与 `work.ts` 的 `canTeamViewAgentWork` 对齐，并在 `collaboration_scope` 切换提交后立即调用 `trajectory.check()` 关闭失权 WebSocket。

---

#### `R1-C3` [CRITICAL] `SingleThread` 心跳主会话绑定与 `owner_direct_agent_messages` 视图混淆 `ownerDirect` 与 `ownerInternal`，将劫持主人心跳主会话并破坏专属群 10 分钟背景合并策略

- **位置**：
  - `docs/changes/feat-796-agent-privacy-scope/design.md` L13、L16、L116–129、L205
  - `packages/personal-assistant/src/single-thread.ts` L103、L135、L146、L212–213、L245–252
  - `apps/im-server/src/collaboration.ts` L32–46、`apps/im-server/src/schema.sql` L571–579
  - `docs/changes/feat-796-agent-privacy-scope/specs/gateway/global-agent.md` L19–21、`specs/gateway/routing-delivery.md` L20–23
- **证据**：
  1. **心跳主会话劫持**：`single-thread.ts:212-213` 通过 `const ownerDirect = chatDelivery(input, {...config, collaborationScope:'owner_only'}, this.options.ownerId) !== 'skip'` 判断当前输入是否属于真人主人 1:1 私聊，并在 `chatBinding`（L245–252）中将 `owner:<ownerId>` 心跳会话迁移收编到该 `conversationId` 且执行 `store.markCanonical(binding)`。当 `classifyChatDelivery` 按 `design.md` L128 对 `ownerInternal`（同主人专属群 `G2`、同主人 `agent-agent` 私聊）返回非 `'skip'` 时，`ownerDirect` 变量在群聊和 `agent-agent` 私聊中也会变为 `true`，把原本绑定真人主人 1:1 私聊的 canonical 心跳会话劫持到群聊或另一 Agent 私聊中！
  2. **专属群普通消息被误判为 `'high'` 即时唤醒**：`design.md` L13 与 L205 提出更新 `owner_direct_agent_messages` 视图以覆盖 owner-internal 会话；但 `collaboration.ts:33` 查询 `owner_direct_agent_messages` 生成的是 `owner_direct`（对应 `facts.ownerDirect`），而 `classifyChatDelivery`（`product-contracts/src/collaboration.ts:24`）对 `facts.ownerDirect === true` 一律返回 `'high'`！若把同主人专属群纳入 `owner_direct_agent_messages`，专属群内所有未 `@`、未回复该 Agent 的普通消息都会变成即时 `'high'` 唤醒，直接违背 delta-spec 中“允许接收的群内未点名普通消息按 10 分钟窗口合并作为背景通知”的契约。
  3. **`SingleThread` 群背景定时器在 `owner_only` 下失效**：`single-thread.ts:135`（`schedule`）与 L146（`flushGroup`）硬编码 `if (config?.collaborationScope === 'owner_only') return;`，且 `restrictToOwner`（L103）无条件 `this.clearTimers(agentId)` 后不重排保留的专属群定时器，导致私有 `single_thread` Agent 在同主人专属群中收不到未 `@` 背景批处理。
- **未修后果**：一旦主人在私密专属群或同主人多 Agent 间对话，不仅 `single_thread` Agent 的心跳主会话归属错乱，而且全局/单线程 Agent 在专属群中要么对每条普通闲聊高频抢话（若合入 `owner_direct`），要么永远丢弃未点名群背景（若仅改 `owner_internal` 却未改 `single-thread.ts:135,146`）。设计必须保持 `owner_direct` 严格限定为“真人主人 1:1 私聊 / 飞书绑定主人单聊”（供 `chatBinding` 与 `'high'` 直聊优先级使用），独立计算 `owner_internal` 仅用于准入放行，并放开 `SingleThread` 在 `owner_only` 下对 `owner_internal` 群背景的定时调度。

---

#### `R1-C4` [CRITICAL] 私有 PA 的旁观过滤与出站硬拦截存在执行链破口：外人群参与者积压因 `pa_observation` 漏网、飞书出站先发送落库后鉴权、未建会话同事出站返回非结构化异常

- **位置**：
  - `docs/changes/feat-796-agent-privacy-scope/design.md` L93–95、L129、L167–169
  - `packages/personal-assistant/src/global-agent.ts` L761、`packages/personal-assistant/src/attention.ts` L30–45
  - `packages/personal-assistant/src/personal-assistant.ts` L273–310、L480–496、L599–612
  - `packages/personal-assistant/src/external.ts` L286–298
  - `apps/im-server/src/gateway.ts` L455、`apps/im-server/src/work.ts` L241–248
- **证据**：
  1. **`pa_observation: true` 导致外人群 `participant` 积压无法被清退**：只要主人在群聊 `G1` 中，`schema.sql:581-587` 的触发器就会产生 `pa_source_events`（即便 PA 同时也是 `G1` 的群成员）；`global-agent.ts:761` 拉取时统一写入 `metadata.pa_observation: true`，随后 `personal-assistant.ts:281-304` 经 `pa.source.admit` 判定写入 `metadata.personal_delivery = 'participant'`，但不会删除 `metadata.pa_observation`。按 `design.md` L129 的定义 `ownerObserved = !!config.personal && (meta.personal_delivery === 'observer' || meta.pa_observation === true)`，`restrictToOwner` 会把这些 `personal_delivery === 'participant'` 的外人群消息误判为 `ownerObserved === true` 而继续保留唤醒；此外尚未完成 `pa.source.admit` 分类的 `personal_unclassified: true` 条目在切为 `'owner_only'` 后也需在 `admitSource` 按最新档位降级为纯 `observer`（若主人在场）或拒绝（如无主人在场的旧同事 1:1 PA 私聊）。
  2. **飞书/外部渠道先真实发送并写镜像帧，后做 `pa.action.prepare` 拦截**：`personal-assistant.ts:483-491` 处理 `external:` 目标时，先调用 `this.options.external.request('agent.message', ...)`（`external.ts:288-296` 立即向外部渠道发送并在 `external.sqlite3` 写入 `turn_start` / `message_completed` 镜像帧），之后才在 `this.finish()` 中请求 `pa.action.prepare`。私有 PA 若向非主人飞书单聊或飞书群调用 `send_message`，在中心返回 `collaboration_scope_restricted` 之前，对外消息已发出且 IM 影子会话已产生幽灵气泡！
  3. **错误结构与未建直聊目标解析破口**：
     - `gateway.ts:455` 将 `pa.*` 异常序列化为 `{ code: e.detail ?? "personal_operation_failed", message: e.message }`；若 `PersonalActions` 抛 `fail(403, { code: 'collaboration_scope_restricted', message: '...' })`，`error.code` 会变成对象而非字符串，节点无法匹配；
     - 当私有 PA 尝试 `send_message(target = colleagueUserId)`（无既有会话）时，`PersonalAssistant.resolve`（`personal-assistant.ts:607`）先调 `work.ts:243-247` 的 `resolve_target` 返回 `{ target: null }` 并直接抛 `Error('Recipient is not a resolved conversation')`，模型收不到 `not_sent` 与“当前为私有模式、请改向主人汇报”的引导。
- **未修后果**：私有 PA 不仅会在切入私有后继续作为参与者响应外人群积压消息，还会向非主人飞书会话真实发出消息，并在站内对未建聊同事发送时丢失结构化恢复指引。设计需：(1) 令 `ownerObserved` 严格排除 `personal_delivery === 'participant'`（仅当 `personal_delivery === 'observer'`，或未分类但经中心确认主人在场且按旁观准入时成立）；(2) 在 `PersonalAssistant.send` 调用 `external.request('agent.message')` 之前完成私有范围与目标校验，且对 `owner_only` 下指向外部同事的目标统一返回确定性的 `collaboration_scope_restricted` `not_sent` 结果；(3) 对齐 `gateway.ts:455` 对结构化错误码的提取规则。

---

#### `R1-W1` [WARNING] 原生 iOS 新建普通/全局 Agent 缺失权限档位选择，且 iOS 历史私聊只读文案与建群可见性默认值与契约冲突

- **位置**：
  - `docs/changes/feat-796-agent-privacy-scope/spec.md` L65–68、L112–116、L129–130
  - `docs/changes/feat-796-agent-privacy-scope/design.md` L17、L177–179
  - `src/IM/ios/NanoIM/Features/Agents/AgentsView.swift` L359、L370（`AgentCreateView`）
  - `src/IM/ios/NanoIM/Features/Chat/ConversationView.swift` L194–205、`ChatModels.swift` L31–61、`Storage/ChatStorage.swift` L1129
  - `src/IM/ios/NanoIM/Features/Chat/NewChatView.swift` L11、L38–42、L112
- **证据**：
  1. `AgentsView.swift` 的 `AgentCreateView` 两处调用 `AgentEditorFields`（L359 与 L370）均传 `showProfile: false`，而 `Picker(L("协作范围", ...))` 定义在 `AgentConfigView.swift:282-299` 的 `if showProfile` 区块内，导致 iOS 新建普通/全局 Agent 表单完全没有权限档位控件，用户无法在创建时直接设为私有，违背 `spec.md` L66–68“在原生 iOS 创建或编辑助手……不会先对其他团队成员短暂可见”。
  2. `ConversationView.swift:196` 对 `can_write == false && is_observer != true && dissolved_at == nil` 的会话统一显示 `"公开群 · 加入后可参与"`，且 `ChatModels.swift` / `ChatStorage.swift` 未解码和持久化 `write_blocked_reason`。当同事在 iOS 打开被设为私有的历史 1:1 私聊时，底部会出现“公开群 · 加入后可参与”的错误提示。
  3. `NewChatView.swift` 建群默认 `visibility = "public"` 且未对选中本人私有助手做私密锁定与外部同事互斥，用户在 iOS 勾选私有助手建群将直接触发 409 失败。
- **未修后果**：iOS 客户端在新建私有助手、建专属群和阅读历史私聊三个核心入口上直接违反 `spec.md` 验收标准。设计需把 `AgentsView.swift`、`ChatModels.swift`、`ChatStorage.swift`、`ConversationView.swift` 与 `NewChatView.swift`（及 `ChatInfoView.swift` 加人过滤）纳入方案。

---

#### `R1-W2` [WARNING] `'team' -> 'owner_only'` 切换存在“节点 RPC 先于中心退群事务”及“群由内变外后的陈旧 `owner_internal` 标记”竞态，且退群副作用需覆盖话题关注与任务通知发布

- **位置**：
  - `docs/changes/feat-796-agent-privacy-scope/design.md` L87–91、L140–145
  - `apps/im-server/src/control.ts` L356–365、L476–505
  - `apps/im-server/src/messaging.ts` L1003–1028
  - `packages/personal-assistant/src/inbox.ts` L124–136
- **证据**：
  1. **群成员由内部变外部后的陈旧元数据**：群 `G` 初始仅含主人 A 与 `'team'` 助手 X，消息 `M1` 投递到节点 Inbox 时带有静态快照 `metadata.owner_internal: true`（等待 10 分钟背景唤醒）；随后 A 将同事 B 拉入 `G`（因 X 当时为 `'team'`，操作合法），紧接着 A 将 X 切为 `'owner_only'`。中心把 X 移出 `G` 后，节点侧 `InboxStore.restrict` 若只看 `M1` 入库时的 `input.metadata.owner_internal === true`，会误判 `M1` 仍合法而不撤回。
  2. **RPC 与中心事务顺序窗口**：`control.ts:364` 先向节点发送 `agent.config.apply`，待节点返回后才在中心事务内更新 `collaboration_scope`、移出外人群并执行 `retireTeamBacklog`；在该 RPC 往返期间，并发到达外人群的新消息仍会按旧 `'team'` 生成 `relay_tasks` 发往节点。
  3. **退群清理完整性**：对照 `DELETE /participants/:user_id`（`messaging.ts:1021-1027`），中心自动退群除删除 `conversation_participants` 与调用 `revokeLostTaskContextAccess` 外，还需在事务提交后调用 `publishMessages(notices)` 发布任务撤销系统通知、删除该 Agent 在该群的 `thread_followers` 行，并处理未决 `permission_requests`；同时 `POST /im/v1/personal-agent` 用同一 `request_key` 重试时需校验 `collaboration_scope` 与首次请求一致，避免并发/篡改覆盖。
- **未修后果**：边界时序下私有助手仍可能消费已变成外人群的旧消息，或退群后遗留僵尸 `thread_followers` 与未广播的任务撤销通知。建议在外部成员首次加入原本 owner-internal 的群时同步通知/失效相关缓存（或在节点侧结合退群会话撤销），并在中心 `ConfigOperations.commit` 后对退出的会话列表向节点补齐会话级清退或在节点按当前 `collaborationScope` 拦截晚到的非 `owner_internal` 投递。

---

#### `R1-W3` [WARNING] 启用个人空间的主人名下同时存在存量 `company:default` Agent 与 `personal:<owner_id>` Agent/PA 时，内部私聊与专属群会被单空间检查拒绝

- **位置**：
  - `docs/changes/feat-796-agent-privacy-scope/design.md` L76–86
  - `apps/im-server/src/messaging.ts` L126、L271、L295–305、L847、L852–869、L1003
- **证据**：
  - 先加入团队并创建了普通 Agent X（`space_id = 'company:default'`）、后创建 PA（使 `users.personal_space_enabled = 1`，PA 与后续新建 Agent Y 的 `space_id = 'personal:<owner_id>'`）是团队老成员的标准存量形态。
  - 当该主人按 `spec.md` 用户场景 2 将 PA（`personal:<owner_id>`）与存量私有助手 X（`company:default`）拉入同一个私密专属群，或让 PA / Y 与 X 建立一对一私聊时：
    - `createConversation`（`messaging.ts:300`）只取单个 `space`（如 `profiles[0]?.space_id`），随后 `messaging.ts:305` 与 `POST /participants`（`messaging.ts:1003`）逐个检查 `canActorAccess(db, id, space)`；
    - `Messaging.resolveTarget`（`messaging.ts:852-865`）在 X 联系 Y 与 Y 联系 X 时分别使用各自不同的 `a.space_id` 构造 `direct_key` 并检查 `canActorAccess(db, u.id, a.space_id)`；
    - Gateway 鉴权 `messaging.ts:126` 又要求 `agent.space_id === c.space_id`。
- **未修后果**：老团队成员无法把自己的 PA 与早期创建的私有助手拉进同一个内部工作台群或让它们互发私信，核心用户场景 2 失败。设计需明确同主人名下跨 `company:default` / `personal:<owner_id>` Agent 建立 owner-internal 群与 `agent-agent` 直聊时的会话 `space_id` 选择规则（例如统一归入 `personal:<owner_id>` 或按主人当前默认空间，并在同一 `owner_id` 的 owner-internal 会话上放行同主人非 stale Agent 的成员校验、直聊查找与 Gateway `access`）。

---

#### `R1-W4` [WARNING] 群话题初始关注（`threads.ts`）与消息回执（`message-records.ts`）仍硬判 `collaboration_scope = 'team'`，且 Web 历史只读私聊存在分支按钮/失效配置跳转与置顶免打扰锁死问题

- **位置**：
  - `apps/im-server/src/threads.ts` L35、`apps/im-server/src/message-records.ts` L409–410
  - `apps/im-server/src/messaging.ts` L956–986
  - `src/IM/frontend/src/features/chat/components/message-pane.tsx` L1336–1354、L1823–1839、L2135–2140
  - `src/IM/frontend/src/features/settings/agents/agent-profile-page.tsx` L97
- **证据**：
  1. `threads.ts:35`（`followInitialParticipants`）写死 `coalesce(a.collaboration_scope,'team')='team'`，导致同主人专属群 `G2` 内的 `'owner_only'` Agent 被 `@` 开新话题后不会写入 `thread_followers`，后续该话题内未显式 `@` 的跟帖不会按话题关注规则唤醒该私有助手；`message-records.ts:409-410`（`trackReceipts`）同样写死 `a.collaboration_scope='team'`，导致专属群内 `'owner_only'` 全局 Agent 不产生已读/送达回执（`design.md` 仅在 L13 提及文件名，未在决策与数据流章节定义其 owner-internal 判定规则）。
  2. 在外部同事查看历史 1:1 只读私聊（`can_write = false, write_blocked_reason = 'agent_private'`）时：
     - `MessagePane`（`message-pane.tsx:1823, 2135`）未检查 `conversation.can_write !== false`，仍在历史助手消息上展示「从此处创建分支」操作（并因 `contacts` 不再返回该私有助手而误提示“Agent 离线，无法分支”，或缓存未刷新时点击触发 404 报错）；
     - 顶栏因 `conversation.can_write === false` 隐藏了 `DirectConversationMenu`（且后端 `PATCH /im/v1/conversations/:id` 在 `messaging.ts:959` 使用 `mode = "write"`，导致同事连自己的 `is_pinned` / `is_muted` 会话偏好都无法修改并收到 `403 agent_private`），同时顶栏却渲染了 `⚙` 图标（L1340），点击跳转到 `/settings/agents/:id` 后 `agent-profile-page.tsx:97` 渲染网络故障式的“无法加载智能体 + 重试”，而非明确的不可访问提示。
- **未修后果**：同主人专属群内话题连续追问与消息回执失灵；外部同事在历史私聊中遇到误导性的“Agent 离线”、坏链跳转及无法免打扰/置顶。设计需补齐 `threads.ts` / `message-records.ts` 对 owner-internal 会话的放行条件，在 `PATCH /conversations/:id` 仅修改个人 `is_pinned/is_muted` 时允许已加入成员操作，并在 `MessagePane` / `AgentProfilePage` 收口 `agent_private` 状态下的分支按钮、顶栏菜单与不可访问空态。

---

#### `R1-W5` [WARNING] Delta-spec 遗漏 `external-channels.md` / `ios-client.md` / `im/spec.md` 同步更新，且 `web-chat-ux.md` 与 `routing-delivery.md` 的 `MODIFIED` 块删减了既有仍适用 Scenario 内容

- **位置**：
  - 遗漏的现行 canonical specs：
    - `docs/specs/gateway/external-channels.md` L16、L41、L236、L314、L378、L540
    - `docs/specs/im/ios-client.md`（首次设置与聊天只读相关 Requirement）
    - `docs/specs/im/spec.md` L11
  - 现有 delta-specs：
    - `docs/changes/feat-796-agent-privacy-scope/specs/im/web-chat-ux.md` L5–28（对比 `docs/specs/im/web-chat-ux.md` L24–41）
    - `docs/changes/feat-796-agent-privacy-scope/specs/gateway/routing-delivery.md` L38–61（对比 `docs/specs/gateway/routing-delivery.md` L195–218）
- **证据**：
  1. `docs/specs/gateway/external-channels.md` 多处仍使用旧术语“团队协作 / 仅限本人”，且未覆盖私有助手/私有 PA 通过产品工具向非主人外部渠道会话主动发消息时的拦截行为；`docs/specs/im/ios-client.md` 未反映本次 iOS 首次创建 PA、新建/编辑 Agent 权限档位及历史私聊只读提示变更；`docs/specs/im/spec.md` L11 仍写“普通公司全局 Agent Work 详情对有效公司成员完整开放”（未限定为团队公开档位）。
  2. 按 [docs/specs/CONTRIBUTING.md](../../specs/CONTRIBUTING.md) 规则，`MODIFIED Requirements` 在归并时将**整块替换**目标 Requirement：
     - `specs/im/web-chat-ux.md` 删除了原 `#### Scenario: 新建群聊选择真人同事与本人候选 Agent` 中关于“分‘同事’与‘我的智能体’两组展示、支持姓名与 `@username` 搜索过滤、不混入他人名下普通 Agent”的现行有效契约；
     - `specs/gateway/routing-delivery.md` 在改写 `#### Scenario: IM 在线时投递成功并回执` 时删去了“多段投递中成功段与失败段各自保留真实结果和对应回执”的现行可靠性条款。
- **未修后果**：完成归并后，仓库内会出现 `external-channels.md` / `im/spec.md` 与新规格术语及行为自相矛盾，且 `web-chat-ux.md` 与 `routing-delivery.md` 会无意擦除 `feat-795` 建群分组搜索与多段投递回执的既有规范。

---

### Recommendations

#### `R1-R1` [Recommendation] 首次引导页（`onboarding-page.tsx` Step 2）与弹窗创建 PA（`personal-agent-dialog.tsx`）采用轻量两档分段控件并精简副文案

- **说明**：Onboarding Step 2（`onboarding-page.tsx:198-210`）与 `PersonalAgentDialog`（`personal-agent-dialog.tsx:28-36`）是高频轻量创建面，建议采用紧凑两档分段选择（默认选中「团队公开」）配合单行静态/动态短句（例如说明同事是否可见可联系），避免在首次引导卡片中堆叠“切为私有时自动退群与冻结历史私聊”等仅对存量助手切换才有意义的解释，保持移动端 `390x844` 首屏即可见创建主按钮。

#### `R1-R2` [Recommendation] `Runbook for Reviewer` 明确前端构建产物更新或 `--vite` 方式

- **说明**：`design.md` L217–221 的隔离栈启动命令 `./scripts/e2e-up.sh --wt "$WT_ROOT"` 默认由 `im-server` 提供静态前端资源；建议在步骤 2 前显式注明先运行 `npm --prefix src/IM/frontend run build`（或使用 `--vite`），避免独立审查时浏览器加载到未包含本分支前端改动的旧静态产物。

---

### Author Resolutions

- **`R1-C1`**: `accepted` — 在 [design.md](design.md) 现状分析、关键决策 2 与接口增量中废除泛化放宽 `currentActorCanAccess` 的做法，改为提炼职责正交的 `canTeamContactAgent`、`canViewAgentWork` 与 `canAgentAccessConversation`：逐一覆盖 `messaging.ts:126`（Gateway 分支统一放行 `publishAgent` / `ChatStreaming` / `delivery_receipt` / `config.boundary` / `media.ts`）、`gateway.ts:141`（`permission_response`）、`messaging.ts:296-305`（`createConversation`）、`messaging.ts:852-869`（`resolveTarget` 跨空间查找 `'company:default'`）、`conversation-actions.ts:150`（斜杠命令/技能）、`work.ts:184, 587` 与 `gateway.ts:214`（`agent.work.updated`）；同时保持 `observerOwners` 在 `company:default` 双 Agent 直聊上的 `p.space_id === space` 约束以保障 `tenancy.test.ts:400-402` 恒返回 `404`，并在 `readableConversationIds`、`conversationRowAccess` 与 `joinConversation` 中显式禁止 `'owner_only'` Agent 非成员读取、搜索或加入公开群。
- **`R1-C2`**: `accepted` — 在 [design.md](design.md) 关键决策 2、时序图与 [specs/im/agent-work.md](specs/im/agent-work.md) 中补齐 `apps/im-server/src/trajectory.ts` 全部 4 处鉴权入口（`create`、`valid`、`authorizeLocal`、`authorizeAttachmentSources`）统一调用 `canViewAgentWork`，并在 `ConfigOperations.commit` 提交 `collaboration_scope` 变更后立即调用 `ctx.gateway.trajectory.check()` 以 `1008` 断开失权的外部同事实时轨迹 WebSocket。
- **`R1-C3`**: `accepted` — 在 [design.md](design.md) 关键决策 3 与接口增量中严格分离 `ownerDirect` 与 `ownerInternal`：`owner_direct_agent_messages` 视图与 `facts.ownerDirect` 保持仅匹配“真人主人 1:1 直聊（排除 PA 代发）与飞书绑定主人单聊”，`SingleThread.chatBinding` 仅在真实 `ownerDirect` 下收编绑定 `owner:<ownerId>` canonical 心跳会话；独立下发 `owner_internal` 供准入放行，使同主人专属群未点名消息继续走 `'background'` 10 分钟窗口合并，同时移除 `single-thread.ts` `schedule` / `flushGroup` 对 `'owner_only'` 的短路并在 `restrictToOwner` 后重排幸存专属群定时器。
- **`R1-C4`**: `accepted` — 在 [design.md](design.md) 关键决策 5 与模型可见上下文章节闭合三处破口：(1) `attention.ts` 将 `ownerObserved` 严格限定为 `!!config.personal && meta.personal_delivery === 'observer'`（不再依赖 `meta.pa_observation === true`），配合中心 `admitSource` 实时成员判定与待审 `reviews` 清退彻底移除外人群 `participant` 积压；(2) `PersonalAssistant.send` 对 `external:` 目标在调用 `external.request('agent.message')` 之前前置校验私有范围与绑定主人单聊身份，杜绝飞书误发与影子 `turn_start` 气泡；(3) 修正 `gateway.ts:455` 对对象型 `IdentityError.detail.code` 的解包，并在 `work.ts` `resolve_target` / `PersonalAssistant.resolve` 中对未建聊外部目标统一收敛返回结构化 `{ status: "not_sent", changed_reason: "collaboration_scope_restricted", message: "..." }`。
- **`R1-W1`**: `accepted` — 在 [design.md](design.md) 现状分析、UX Grounding、Milestone 与新增 [specs/im/ios-client.md](specs/im/ios-client.md) 中完整纳入原生 iOS 的 `AgentsView.swift`（`AgentCreateView` 权限选择器）、`PersonalAssistantSetup.swift`、`AgentConfigView.swift`、`ChatModels.swift` + `ChatStorage.swift` + `ConversationView.swift`（解码持久化 `write_blocked_reason == "agent_private"` 并展示未对外开放提示，不再误显“公开群 · 加入后可参与”）及 `NewChatView.swift` / `ChatInfoView.swift`（勾选私有助手锁定 `private` 并与外部同事互斥）。
- **`R1-W2`**: `accepted` — 在 [design.md](design.md) 关键决策 4、时序图与 [specs/im/conversations-messages.md](specs/im/conversations-messages.md)、[specs/im/personal-agent.md](specs/im/personal-agent.md) 中补齐：(1) 退群事务内清理 `thread_followers`、`running` 占位消息与未决 `permission_requests`，二次运行 `retireTeamBacklog` 消除 RPC 窗口期新 `relay_tasks`，事务提交后调用 `publishMessages(notices)`；(2) 外部成员首次加入原本内部群或中心完成退群提交后向在线节点发送 `agent.scope.revoked` 按 `conversation_id` 清退陈旧 `owner_internal` 缓冲；(3) `POST /im/v1/personal-agent` 同一 `request_key` 重试时若显式传入冲突 `collaboration_scope` 返回 `409`。
- **`R1-W3`**: `accepted` — 在 [design.md](design.md) 关键决策 2 中明确同一 `owner_id` 名下存量 `company:default` Agent 与 `personal:<owner_id>` Agent/PA 建立内部专属群或 `agent-agent` 直聊时的空间归属（`personal_space_enabled = 1` 时落入 `personal:<owner_id>`）、跨 `['personal:' + owner_id, 'company:default']` 的既有 `direct_key` 查找复用及 `canAgentAccessConversation` 准入规则。
- **`R1-W4`**: `accepted` — 在 [design.md](design.md) 关键决策 3、4、UX Grounding 与 [specs/im/conversations-messages.md](specs/im/conversations-messages.md)、[specs/im/web-chat-ux.md](specs/im/web-chat-ux.md) 中明确：`threads.ts` `followInitialParticipants` 与 `message-records.ts` `trackReceipts` 对 owner-internal 会话中的 `'owner_only'` Agent 放行；`PATCH /im/v1/conversations/:id` 仅修改个人 `is_pinned` / `is_muted` 时允许已加入成员操作；Web `MessagePane` 在 `can_write === false` 时隐藏分支按钮，在 `agent_private` 下保留置顶/免打扰菜单并隐藏失效 `⚙` 链接，`AgentProfilePage` 展示明确不可访问提示。
- **`R1-W5`**: `accepted` — 新增 [specs/im/spec.md](specs/im/spec.md)、[specs/im/ios-client.md](specs/im/ios-client.md)、[specs/gateway/external-channels.md](specs/gateway/external-channels.md) 3 份 delta-spec 并登记到 [design.md](design.md)；同时修复 [specs/im/web-chat-ux.md](specs/im/web-chat-ux.md)（完整保留 `#### Scenario: 新建群聊选择真人同事与本人候选 Agent` 的分组、搜索及排除他人普通 Agent 条款）与 [specs/gateway/routing-delivery.md](specs/gateway/routing-delivery.md)（完整保留 `#### Scenario: IM 在线时投递成功并回执` 标题与 `ok=True` 回执条款）。
- **`R1-R1`**: `accepted` — 在 [design.md](design.md) UX Grounding 表中明确首次引导 Step 2 与 `PersonalAgentDialog` 使用紧凑两档分段控件配合单行短文案，确保 `390x844` 首屏可见主创建按钮。
- **`R1-R2`**: `accepted` — 在 [design.md](design.md) `Runbook for Reviewer` 启动命令与步骤 2 中显式加入前置 `npm --prefix src/IM/frontend run build`（或 `--vite` 说明）。
