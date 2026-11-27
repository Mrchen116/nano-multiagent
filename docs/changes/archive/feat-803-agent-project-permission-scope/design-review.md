# Design Review Report

## Round 1

### Metadata

- `started_at`: 2026-11-27T20:17:24+09:00
- `completed_at`: 2026-11-27T20:30:30+09:00
- `duration`: ~13m
- `reviewer`: Gate 2 `change-design-reviewer` (independent subagent, combined with `agent-context-review` & `frontend-experience-review` design-mode checks)
- `target`: `feat-803-agent-project-permission-scope` (`unit/feat-803-agent-project-permission-scope` @ `08c9df59d`)
- `review_mode`: `full`
- `mode_reason`: Full unit Gate 2 首次独立设计审查，完整核查 `spec.md`、`design.md`、全部 11 份 `specs/**` delta-spec、`milestones/` 与代码仓及 `docs/specs/` 基线。

### Verdict

**Issues Found**（`3 CRITICAL / 5 WARNING`，另有 `2` 条可选 `Recommendations`）

### Coverage & Evidence

- **现状论断核查（对照真实代码仓 `@ 08c9df59d`）**：
  - 逐文件核实了 `packages/product-contracts/src/{collaboration,configuration,configuration-rpc,index}.ts`、`apps/im-server/src/{schema.sql,db.ts,identity.ts,collaboration.ts,contacts.ts,conversation-access.ts,task-context-access.ts,threads.ts,messaging.ts,message-records.ts,conversation-actions.ts,work.ts,trajectory.ts,control.ts,control-routes.ts,personal-agent.ts,personal-agent-creation.ts,personal-actions.ts,personal-images.ts,agent-lifecycle.ts,task-graphs.ts,gateway.ts,media.ts}`、`packages/dsh-integration/src/{index.ts,personal-security.ts,global-mode.ts,policy/codex.ts,policy/review-session.ts,policy/codex-inspection.ts,policy/codex-context.ts}`、`packages/personal-assistant/src/{attention.ts,personal-assistant.ts,global-agent.ts,single-thread.ts,external.ts,screenshot-delivery.ts}`、`apps/node/src/{file-transfer.ts,main.ts}`，以及 `src/IM/frontend/` 与 `src/IM/ios/` 对应视图。
  - 确认 `design.md` 关于二元 `collaboration_scope`、PA 外发强制经 `PersonalActions.prepareChecked`、非 `256 KiB` UTF-8 文本抛 `attachment_content_review_unavailable`、`ReviewSession` 仅开放 `read`/`read_image`/`glob`/`grep` 四个只读工具等现状描述与代码事实一致；同时定位到若干被遗漏的真实调用点（见 `R1-C1`、`R1-C2`、`R1-W1`、`R1-W2`）。
- **关键决策与用户指定约束核查**：
  - 核对了 `spec.md` 全部已拍板决策与 `design.md` 关键决策 1–6：PA 保持两档且不新增 `project`、普通/全局 Agent 三档（默认仍 `team`）、同项目动态关系由未解散私密群实时推导、多非重叠私密群背景互通确认、纯主人私有域免审直发、跨圈不可读附件按来源与轨迹从严审核、单里程碑 `M1` 交付。
  - 发现 Agent 侧会话权限与任务上下文吊销谓词缺失（`R1-C1`）、纯主人私有域任务图写操作与图片解码前置拦截断裂（`R1-C2`）、私密群非主人拉人越权扩圈/代确认（`R1-W3`）。
- **11 份 Delta-Spec 与 Canonical Spec 锚定核查**：
  - 逐份比对了 `specs/im/{spec,auth-tenancy,agents-nodes,personal-agent,conversations-messages,agent-work,web-chat-ux,ios-client}.md` 与 `specs/gateway/{personal-agent,global-agent,routing-delivery}.md` 对照 `docs/specs/**`：
  - `specs/im/spec.md` 中 `Auth and Tenancy` Requirement 计数 `16 -> 17`（对应 `auth-tenancy.md` 1 个 `ADDED` Requirement）准确；active unit 内 `../../../../specs/...` 相对链接符合 `scripts/docs_check.py` 校验规则。
  - 定位到 `specs/im/agent-work.md` 误删/截断既有 Scenario、`specs/gateway/routing-delivery.md` 漏改 `download_attachment` 返回结构、缺少 `specs/gateway/external-channels.md` delta-spec 以及跨文档矩阵链接未按 `design.md` 承诺落地（`R1-C3`）。
- **Agent Context 专项审查（`agent-context-review` design 模式）**：
  - 核查了披露审核 `ReviewSession` / `codex-context.ts` / `personal-security.ts` 的 `<planned_action>` 与 `<conversation_transcript>` 证据链：`fullEvidence=true` 保留完整历史与工具调用记录，`unreadable_attachments` 带 `sha256` 与 `download_attachment` 返回的 `sha256` 可构成来源可追溯核验，只读工具边界保持不扩张。
  - 定位到 PA 聊天创建独立 Agent 的实际可见 Context（`nano-agent-creation/SKILL.md`、`personal-agent-creation.ts` `options` 字段说明及 `specs/gateway/personal-agent.md` 创建场景）仍只暴露两档，且 `global-mode.ts` / `personal-security.ts` 工具描述与新附件能力不一致（`R1-W4`）。
- **前端与原生体验专项审查（`frontend-experience-review` design 模式）**：
  - 核查了无独立 `prototype.html` 的豁免理由（均在既有表单控件、选择器、只读横幅与确认弹窗模式上增量扩展，不新增页面或重构信息层级，豁免理由成立）。
  - 定位到放宽权限确认弹窗文案将 PA / `single_thread` 与 `global` 普通助手的暴露边界混为一谈（对 PA 形成“开放全局 Work”虚假风险说明），且 iOS 遗漏跨群 `409` 二次确认重试、保存前放宽确认及 `ChatInfoView` 冻结私聊置顶/免打扰豁免（`R1-W5`）。
- **架构与职责边界判断**：
  - 未违反 `AGENTS.md` / `SPEC.md` 架构红线（未引入跨包越界 import、未把产品权限塞入 DSH 内核或扩大 `ReviewSession` 工具面）；`milestones/M1-project-scope-and-pa-review/` 单里程碑切分合理。
- **已检查但未发现问题项**：
  - `/im/v1/contacts` 更新后 Web `/people`（`people-directory-page.tsx`）自动按 `owner_user_id` 聚合展示可见同项目助手，无需额外分叉逻辑；
  - `trajectory.ts` 实时原生轨迹连接与轨迹工作区附件均统一走 `canViewAgentWork` 复核，配合 `closeUnauthorizedViewers(agentId)` 可覆盖权限收紧与退群实时断连；
  - `media.ts` 受保护附件读取按会话可读权限（`messaging.access` read 模式）鉴权，历史一对一私聊冻结为只读后真人仍可正常查看历史图片与附件。

### Issues

#### `R1-C1` [CRITICAL] `project` 档位缺失 Agent 侧会话访问、主动寻址投递与任务上下文吊销谓词，导致失权私聊单向漏发且 `revokeLostTaskContextAccess` 失效

- **位置**：
  - `docs/changes/feat-803-agent-project-permission-scope/design.md`（关键决策 1–3，L76–L88；关键代码锚点，L119）
  - `apps/im-server/src/conversation-access.ts`（L53–L72 `canAgentAccessConversation`、L113–L126 `conversationRowAccess` 的 `isAgent` 分支）
  - `apps/im-server/src/messaging.ts`（L127–L146 `access`、L288–L334 `resolveParticipants`、L867–L870 `joinConversation`、L925–L965 `resolveTarget`）
  - `apps/im-server/src/task-context-access.ts`（L26、L62 `taskContextEligible`）
- **问题与影响**：
  1. `design.md` 只定义了真人视角 `canCollaborateWithAgent(db, viewer, profile)` 与 `conversationRowAccess` 对真人成员设置 `write_blocked_reason = 'agent_project_restricted'`，未定义 `collaboration_scope === 'project'` 时 **Agent 自身视角**的会话读写与寻址边界。
  2. 当外部同事 B 离开或被移出与 `project` 助手 X 最后的共同私密群后，B 与 X 仍是历史一对一私聊 `c_dm` 的成员（`member === true && !c.dissolved_at`）。在现行 `conversationRowAccess` 的 `isAgent` 分支（`conversation-access.ts:113-126`）中，只要 `canAgentAccessConversation` 返回 `true`，就会返回 `can_write: true`，直接造成两处核心契约断裂：
     - **单向漏发越界消息**：X 调用 `send_message(target=c_dm)` 或 `send_message(target=u_bob)` 时，`Messaging.access(..., 'write')` 与 `resolveTarget`（现仅拦截 `owner_only`）均会放行，使 X 继续向已退出项目的同事 B 发消息，违反 `spec.md`（L142）与 `specs/im/conversations-messages.md`（L102）“B 与 X 向该会话发送新消息或修改会话标题均返回 403 拒绝”以及 `specs/gateway/routing-delivery.md`（L60–L63）。
     - **任务上下文吊销失效**：关键决策 3.2（`design.md:88`）依赖 `DELETE /participants` 与 `dissolveGroup` 内的 `captureTaskContextAccess` + `revokeLostTaskContextAccess` 吊销失权私聊任务上下文。但 `task-context-access.ts:26` 仅过滤 `'owner_only'`，且 `:62` `taskContextEligible` 检查的是 Agent 账号自身的 `conversationAccess(db, conversationId, actor.id)?.can_write`——若 `isAgent` 分支在失权 `c_dm` 上仍为 `can_write: true`，`revokeLostTaskContextAccess` 永远检测不到权限丧失，失权私聊的任务上下文不会被撤回。
     - **公开群与新建会话越界**：`messaging.ts:288,331,868,925-965` 现仅检查 `'owner_only'`，未拦截 `project` 助手自行 `join` 公开群、创建公开群或与非同项目外部同事/外部私有或项目助手新建私聊。
- **修改方向**：
  - 在 `design.md` 明确补齐 `collaboration_scope === 'project'` 的 Agent 侧完整谓词与锚点：
    1. `canAgentAccessConversation` / `conversationRowAccess(isAgent)`：外部来源仅放行已绑定主人单聊 shadow；群聊仅放行仍在群内的未解散 `private` 群（拒绝 `public` 群浏览与自动可读）；`direct` 会话要求对端为同 owner（真人或助手）或当前仍与该 `project` 助手共享至少一个未解散私密群的有效团队成员/可协作助手，否则 Agent 侧不可写（返回 `403 collaboration_scope_restricted`，并明确 Agent 侧是否同 `owner_only` 一样在失权外部私聊上撤销 `read_messages`/`download_attachment` 访问以同步触发 `task-context-access.ts` 吊销）。
    2. 同步更新 `messaging.ts` 的 `access`、`resolveParticipants`、`joinConversation`、`resolveTarget` 与 `task-context-access.ts:26`，覆盖 `user-agent` 与 `agent-agent` 两类直聊。

#### `R1-C2` [CRITICAL] 纯主人私有域免审直发链路遗漏任务图写操作（`args.task`）且前置 `decodePersonalImages` 误拦截合法图片附件

- **位置**：
  - `docs/changes/feat-803-agent-project-permission-scope/design.md`（关键决策 4，L90–L93；关键代码锚点，L125）
  - `docs/changes/feat-803-agent-project-permission-scope/spec.md`（L83、L148–L150）
  - `docs/changes/feat-803-agent-project-permission-scope/specs/gateway/personal-agent.md`（L6–L10）
  - `apps/im-server/src/personal-actions.ts`（L160–L170 `args.task` 分支、L283–L286 `prepareChecked`）
  - `apps/im-server/src/personal-images.ts`（L6–L22 `decodePersonalImages`）
  - `apps/im-server/src/gateway.ts`（L529–L532 `task_graph.command` 门禁）
  - `packages/personal-assistant/src/personal-assistant.ts`（L389–L403 `task` / `executeReviewed`）
- **问题与影响**：
  1. **任务图写操作免审链路未闭合**：`spec.md`（L149）与 `specs/gateway/personal-agent.md`（L7–L8）明确规定 PA 向纯主人私有会话（仅含主人本人与同主人 `owner_only` 助手）“发送消息、通用附件或**修改任务内容**”时免除独立披露审核直接提交。但 `design.md` 关键决策 4 仅设计了消息/附件分支返回 `{ state: 'confirmed', message_id }`，未覆盖 `PersonalActions.prepare` 的 `args.task` 分支（`personal-actions.ts:168` 现仅豁免 `destination === b.conversation_id`）。若不改动 `args.task`，纯主人私有会话改任务仍会被迫走披露审核；若简单改为返回 `{ owner_private: true }`，客户端 `PersonalAssistant.task` 回退发送 `task_graph.command` 会被 `gateway.ts:531`（`destination !== personal.conversation_id`）直接抛 `personal_reviewed_delivery_required` 拒绝，且当 PA 不在 `[主人, owner_only 助手]` 会话成员表内时还会失去 `executeDelegated` 的主人委托写权限（`task-graphs.ts:640`）。
  2. **审核专用图片解码器前置误杀合法图片**：`PersonalActions.prepareChecked`（`personal-actions.ts:284`）在调用 `this.prepare` 判定 `pureOwnerPrivateDestination` **之前**无条件对所有光栅图附件执行 `decodePersonalImages`（限制单次 ≤ 5 张、单边 ≤ 4096px、仅限单帧静态 PNG/JPEG/WebP，拒绝 `image/gif` 与超宽长图并抛 `422 attachment_image_unsupported` / `attachment_image_limit`）。该限制原本仅服务于披露审核多模态模型输入，保留前置调用会导致 PA 向同主人 `owner_only` 助手免审发送合法 GIF 或 >4096px 架构长图（≤ 10 MiB）时被 422 误拒。
- **修改方向**：
  - 在 `design.md` 关键决策 4 与 `personal-actions.ts` 锚点中补齐：
    1. 在 `PersonalActions.prepareChecked` 入口先解析目标会话并判定 `pureOwnerPrivateDestination(b, destination)`；命中免审通道时**跳过**审核模型专用的 `decodePersonalImages`。
    2. 对免审 `args.task` 分支，在 `prepareChecked` 内直接执行 `checkTaskWaits` + 事务内 `executeDelegated` + 写入 `pa_operations(state='confirmed', result_json)`（支持同 `request_key` 幂等重放），事务后发布任务通知与 `notifyChange`，返回 `{ state: 'confirmed', result }`（客户端 `PersonalAssistant.task` → `executeReviewed` L398 已原生支持识别 `proposal.state === 'confirmed'` 并直接返回 `{ ok: true, result }`，无需放宽 `gateway.ts:531`）。

#### `R1-C3` [CRITICAL] Delta-spec 在 `im/agent-work.md` 误删/截断既有 Scenario，且遗漏 `gateway/routing-delivery.md`、`gateway/external-channels.md` 与跨页矩阵引用同步

- **位置**：
  - `docs/changes/feat-803-agent-project-permission-scope/specs/im/agent-work.md`（L48–L50，对照 `docs/specs/im/agent-work.md` L89–L98）
  - `docs/changes/feat-803-agent-project-permission-scope/specs/gateway/routing-delivery.md`（对照 `docs/specs/gateway/routing-delivery.md` L601–L604）
  - `docs/specs/gateway/external-channels.md`（L316、L380、L547、L554）
  - `docs/changes/feat-803-agent-project-permission-scope/design.md`（关键决策 6，L103）与 `spec.md`（L179）
- **问题与影响**：
  1. **`MODIFIED` Requirement 丢失并破坏既有契约**：`specs/im/agent-work.md` 中 `### Requirement: Work 提供工作记录与原生轨迹两种查看方式` 彻底删掉了 canonical `docs/specs/im/agent-work.md`（L95–L97）仍适用的 `#### Scenario: 尚无可查看执行`，并将 `#### Scenario: 对照查看存活会话实时工具原始结果与冷态降级提示`（canonical L89–L93）压缩成残缺两行，抹除了“剥离未授权内联图片字节”“已离开内存保留窗口”及“不为此激活冷会话”三项关键安全与运行契约。
  2. **`download_attachment` 返回契约跨文件冲突**：canonical `docs/specs/gateway/routing-delivery.md:603`（`### Requirement: Agent 可通过短标识下载受保护会话附件`）精确规定返回 `{ attachment_id, local_path, file_name, content_type, byte_size }`。本 unit 将返回扩展为含 `sha256`（`design.md:123`、`specs/gateway/personal-agent.md:41`），但同批修改的 `specs/gateway/routing-delivery.md` 未同步 `MODIFIED` 该 Requirement，归并后两份 gateway spec 直接冲突。
  3. **外部渠道规范遗漏三档同步**：`design.md:19` 将飞书/微信外部渠道收发规则调整为对非 `'team'`（含 `'project'` 与 `'owner_only'`）仅放行已绑定主人单聊，但 `docs/specs/gateway/external-channels.md`（L316、L380、L547、L554）仍保留“飞书在两种协作范围下…”及二元 `team`/`owner_only` 表述，未提供对应 delta-spec。
  4. **跨文档引用承诺未兑现**：`design.md:103` 明确承诺从 `docs/README.md` 及 `conversations-messages.md`、`agent-work.md`、`gateway/personal-agent.md` 链接引用 `auth-tenancy.md` 统一权限矩阵（呼应 `spec.md:179`），但上述三份 delta-spec 均未加入该链接，`docs/README.md` 亦未说明是否更新。
- **修改方向**：
  - 在 `specs/im/agent-work.md` 逐字恢复 `#### Scenario: 对照查看存活会话实时工具原始结果与冷态降级提示` 完整约束与 `#### Scenario: 尚无可查看执行`；
  - 在 `specs/gateway/routing-delivery.md` 增补 `MODIFIED` `### Requirement: Agent 可通过短标识下载受保护会话附件`（纳入 `sha256`）；
  - 新增 `specs/gateway/external-channels.md` delta-spec，将二元范围表述更新为三档口径（`project` 与 `owner_only` 在外部渠道均仅递送已绑定主人单聊）；
  - 在 `conversations-messages.md`、`agent-work.md`、`gateway/personal-agent.md` 补齐指向 `auth-tenancy.md` 权限矩阵的引用链接，并核对 `docs/README.md` 索引描述。

#### `R1-W1` [WARNING] `im-server` 实时 Work 广播、生命周期接口、群同伴节点查询与冻结私聊错误码遗漏 `project` 档位适配

- **位置**：
  - `docs/changes/feat-803-agent-project-permission-scope/design.md`（涉及范围 L12；关键决策 1–2）
  - `apps/im-server/src/work.ts`（L129–L143 `notifyUpdated`、L185 `memberExecutionNode`）
  - `apps/im-server/src/agent-lifecycle.ts`（L54 `GET /im/v1/agents/:agent_id/lifecycle`、L156 `publish`）
  - `apps/im-server/src/task-graphs.ts`（L447 `writable`、L1656 错误状态码映射）
  - `apps/im-server/src/conversation-actions.ts`（L271 `/im/v1/conversations/:conversation_id/fork`）
- **问题与影响**：
  1. `work.ts:notifyUpdated`（L138）在构造 `agent.work.updated` 广播目标时只查 `profile.space_id` 并按 `canAccessSpace(u, profile.space_id)` 过滤，未调用 `canViewAgentWork`：当 `project`（或 `team`）全局普通 Agent 创建于个人空间 `personal:<owner>` 时，共享私密群内的外部同事因 `canAccessSpace` 为 `false` 收不到实时 `agent.work.updated` 事件，违反 `specs/im/agent-work.md`（L14、L28）“无论创建于公司空间还是个人空间”均实时可见的契约。
  2. `agent-lifecycle.ts`（L54、L156）仍以 `canTeamContactAgent`（仅 `'team'` 为真）判定非 owner 能否读取生命周期状态及接收 `agent.lifecycle.changed`；Web 与 iOS（`AgentsView.swift:120`、`ConversationView.swift:71`）对可见联系人与聊天内 Agent 均会请求该接口，漏改会导致同项目同事查看 `project` 助手时生命周期接口报 404。
  3. `work.ts:memberExecutionNode`（L185）仍用 `canTeamContactAgent` 过滤群成员执行节点信息，导致私密群内同伴 Agent 调用 `conversations(action="info")` 无法获知 `project` 助手所在节点。
  4. `task-graphs.ts`（L447、L1656）与 `conversation-actions.ts`（L271）仅针对 `write_blocked_reason === 'agent_private'` 返回 `403`，未处理 `'agent_project_restricted'`，导致失权 `project` 历史私聊上的任务图写操作落入 `404 not_found_or_forbidden`，与 `messaging.ts` 的 `403 agent_project_restricted` 不一致。
- **修改方向**：
  - 将 `agent-lifecycle.ts`、`task-graphs.ts`、`conversation-actions.ts` 纳入 `design.md` 涉及范围与代码锚点：`work.ts:notifyUpdated` 改为直接按 `canViewAgentWork` 筛选广播用户；`agent-lifecycle.ts` 与 `work.ts:memberExecutionNode` 改为 `canCollaborateWithAgent`；`task-graphs.ts` 与 `conversation-actions.ts` 同步映射 `agent_project_restricted` 为 403。

#### `R1-W2` [WARNING] Node 与运行时收紧链路硬编码 `'owner_only'`，且 `single-thread.ts` 存在跨私密群误杀在途消息竞态

- **位置**：
  - `docs/changes/feat-803-agent-project-permission-scope/design.md`（涉及范围 L15–L19；关键决策 3，L86–L89）
  - `apps/node/src/main.ts`（L529、L723–L741）
  - `packages/dsh-integration/src/index.ts`（L747、L1524）
  - `packages/personal-assistant/src/single-thread.ts`（L102–L133、L175、L206–L224）
  - `packages/personal-assistant/src/global-agent.ts`（L279–L286）
- **问题与影响**：
  1. **外部渠道在 `project` 档位漏放行与漏清退**：`apps/node/src/main.ts:529` 注入给 `ExternalChannels` 的 `ownerOnly` 仅判断 `collaborationScope === 'owner_only'`，导致 `project` 助手在飞书/微信仍会接收外部群消息与非主人私聊并对外回复；同时 `:723` 仅在 `next.collaborationScope === 'owner_only'` 时执行收紧，`team -> project` 时不会调用 `external.restrictToOwner(agentId)` 清退飞书外部群积压，也不会在 `dsh-integration/src/index.ts:747` 预留 `chatScope`。
  2. **`team -> project` 本地积压清退粒度不匹配**：`global-agent.ts:282` 与 `single-thread.ts:108,111` 的 `restrictToOwner` 写死按 `collaborationScope: 'owner_only'` 重判；若在 `team -> project` 时直接调用，会把仍保留在私密群内的合法未读消息一并清退；若不调用，则会残留公开群与无共同私密群同事私聊的待处理输入。
  3. **SingleThread 跨群误杀在途消息竞态**：在 `single-thread.ts:206,222-224` 中，一旦 `this.scopeChanges` 发生自增，正在排队进入 `receiveAdmitted` 的消息会因 `crossedRestriction === true` 被强制套用 `{...config, collaborationScope: 'owner_only'}` 重判。若 `revokeConversations(agentId, ['G2'])`（如被移出私密群 `G2`）沿用递增 `this.scopeChanges` 的模式，同一 `project` SingleThread 助手在**另一正常私密群 `G1`** 中的合法并发在途消息会被误判为 `'owner_only'` 下的外部群消息而静默 `skip` 丢弃。
- **修改方向**：
  - 在 `design.md` 明确 Node 与运行时收紧协议：
    1. `main.ts:529` 将外部渠道门禁改为 `collaborationScope !== 'team'`；`main.ts:723` 与 `dsh-integration/src/index.ts:747,1524` 覆盖所有收紧跃迁（`team -> project`、`team -> owner_only`、`project -> owner_only`）。
    2. 将 `restrictToOwner` 扩展为 `restrictToScope(agentId, nextScope)`，结合目标档位与当前被撤销会话列表精确过滤越界输入，保留 `team -> project` 下仍在成员表内的私密群输入。
    3. `single-thread.ts` 对 `revokeConversations` 采用按会话维度的撤销代数（`revokedConversationGenerations`）而非复用全局强制 `'owner_only'` 的 `scopeChanges`。

#### `R1-W3` [WARNING] 私密群非主人成员拉人可未经主人同意扩大 `project` 助手项目圈或越权代主人确认跨群互通

- **位置**：
  - `docs/changes/feat-803-agent-project-permission-scope/design.md`（关键决策 2，L82）
  - `docs/changes/feat-803-agent-project-permission-scope/spec.md`（L127–L130）
  - `docs/changes/feat-803-agent-project-permission-scope/specs/im/conversations-messages.md`（L12–L23）
  - `apps/im-server/src/messaging.ts`（L1150–L1180 `POST /im/v1/conversations/:id/participants`）
  - `src/IM/frontend/src/features/chat/components/group-settings.tsx`（L526）
- **问题与影响**：
  1. 现行群治理允许私密群内**任意真人成员**调用 `POST /im/v1/conversations/:id/participants` 添加其他真人同事（Web `GroupSettings` 对所有非只读群成员展示“添加成员”）。当私密群含主人 A 的 `project` 全局助手 X 时：
     - 若外部同事 B 直接拉外部同事 C 入群，C 将在未经主人 A 操作或确认的情况下自动成为 X 的“同项目成员”，立即获得对 X 的一对一私聊权限及完整全局 Work / 原生轨迹查看权（含 X 处理主人 A 私聊的工作记录）。
     - 若 X 已在另一私密群中，B 拉 C 入群会触发 `409 project_agent_cross_group_confirmation_required`。`spec.md:128` 要求“由**主人**确认是否继续”，但 `design.md:82` 未校验 `confirm_project_context_share: true` 的调用者是否为所涉 `project` 助手的 `owner_id`——若不校验，非主人同事 B 可直接传 `confirm_project_context_share: true` 替主人 A 拍板跨群记忆互通；若仅拒绝 B 确认，则未定义 B 拉人时的明确错误码与交互提示。
  2. 口径细微偏差：`spec.md:128` 写“存在新增非重叠成员”，`design.md:82` 写“两群的外部真人成员集合不完全相同”。当 `G1={B,C}` 而新建子集私密群 `G2={B}` 时，虽无“新增”群外成员，但 `G2` 的私密讨论仍会经 X 的全局 Work 与记忆向未入 `G2` 的 `C` 暴露——`design.md:82` 的集合不等判定更安全，需与 `spec.md` / delta-spec 对齐避免实现歧义。
- **修改方向**：
  - 在 `design.md` 与 `specs/im/conversations-messages.md` 明确非主人向含他人 `project` 助手的私密群添加外部真人成员的授权规则（例如：含他人 `project` 助手的私密群新增外部真人成员须由该助手主人操作，或至少在涉及跨群背景互通确认时严格校验调用者为所涉全部 `agent_ids` 的 `owner_id`，对非主人返回可读的 `403` 说明需由助手管理者邀请/确认），并将 `spec.md` 与 delta-spec 统一对齐为“外部真人成员集合不完全相同”。

#### `R1-W4` [WARNING] PA 聊天创建独立 Agent 的模型可见 Context 遗漏 `project` 档位，且工具提示词未同步新附件与哈希契约

- **位置**：
  - `packages/personal-assistant/assets/skills/nano-agent-creation/SKILL.md`（L15）
  - `apps/im-server/src/personal-agent-creation.ts`（L21 `fields.collaboration_scope`）
  - `docs/changes/feat-803-agent-project-permission-scope/specs/gateway/personal-agent.md`（L45–L49）
  - `packages/dsh-integration/src/global-mode.ts`（L103 `download_attachment` 工具描述）
  - `packages/dsh-integration/src/personal-security.ts`（L381 PA 外发附件说明）
- **问题与影响**：
  1. 按 `agent-context-review` 检查模型当轮实际可见输入：当主人在聊天中让 PA 协助创建「项目」档位助手时，PA 加载的 `nano-agent-creation/SKILL.md`（L15）仍写死 `协作范围（团队公开 / 私有）`，`agent_creation(action="options")` 返回的 `configuration_fields.collaboration_scope`（`personal-agent-creation.ts:21`）也只列出 `team` 与 `owner_only`（这两处均未列入 `design.md` 涉及范围），且本 unit 的 delta-spec `specs/gateway/personal-agent.md`（L49）仍沿用旧文“默认 `team`，支持按主人要求直接设为 `owner_only` 私有”。PA 模型在当轮 Context 中看不到 `project` 档位说明，会拒绝或误配为 `team`/`owner_only`。
  2. `packages/dsh-integration/src/global-mode.ts:103`（未列入 `design.md` 涉及范围）中 `download_attachment` 的工具描述未包含新增的 `sha256` 返回字段；同时 `personal-security.ts:381` 现行说明写有 `(non-owner destinations require reviewable static images or supported UTF-8 text formats ... up to 256 KiB). ... Report the limitation if an attachment cannot be reviewed.`——若 `design.md` 不明确改写该段主模型可见规则，PA 主模型会在调用 `send_message(local_files)` 发送 PDF 前自行按旧提示词拒发。
- **修改方向**：
  - 将 `packages/personal-assistant/assets/skills/nano-agent-creation/SKILL.md`、`apps/im-server/src/personal-agent-creation.ts` 与 `packages/dsh-integration/src/global-mode.ts` 补入 `design.md` 涉及范围与 Context 清单；
  - 更新 `specs/gateway/personal-agent.md`（L49）明确 PA 创建独立 Agent 支持 `team` / `project` / `owner_only` 三档；
  - 在 `design.md` 明确 `personal-security.ts:381` 面向 PA 主模型的提示词改写（区分纯主人私有同 owner `owner_only` 助手会话免审直发，以及对外/跨圈会话支持通用附件经独立披露审核外发）。

#### `R1-W5` [WARNING] 放宽权限确认文案混同 PA 与普通全局助手暴露边界，且 iOS 遗漏跨群 `409` 确认流程与冻结私聊详情页开关豁免

- **位置**：
  - `docs/changes/feat-803-agent-project-permission-scope/design.md`（涉及范围 L20–L24；`UX Grounding`，L178–L194）
  - `docs/changes/feat-803-agent-project-permission-scope/specs/im/personal-agent.md`（L18）
  - `src/IM/ios/NanoIM/Features/Agents/AgentConfigView.swift`（L129 `save()`）
  - `src/IM/ios/NanoIM/Features/Chat/NewChatView.swift`（L45–L48、L122 `create`）
  - `src/IM/ios/NanoIM/Features/Chat/ChatInfoView.swift`（L94 置顶/免打扰 `.disabled(...)`、L335 `addMember`）
- **问题与影响**：
  1. **放宽确认文案失真**：`design.md:180` 将所有放宽操作（含 PA 的 `owner_only -> team` 及 `single_thread` 普通助手）统一规定为提示“目录可见性及全局 Work / 历史记忆暴露面扩大”。但 PA 在 `team` 档位下全局 Work 与内部记忆依然严格仅主人可见（仅开放目录可见、同事联系与经披露审核的外发，见 `specs/im/personal-agent.md:18`），`single_thread` 普通助手亦不存在全局 Work 视图与跨会话共享记忆。统一套用该文案会向用户展示错误的权限后果。
  2. **iOS 交互闭环缺失**：
     - `NewChatView.swift:122` 与 `ChatInfoView.swift:335` 未设计捕获 `409 project_agent_cross_group_confirmation_required` 并弹窗确认后附带 `confirm_project_context_share: true` 重试，导致 iPhone 端无法完成跨非重叠私密群添加 `project` 全局助手；
     - `AgentConfigView.swift:129` 未设计保存前放宽权限确认弹窗；
     - `ChatInfoView.swift:94` 置顶/免打扰开关禁用条件写死 `chat.write_blocked_reason != "agent_private"`，漏掉 `"agent_project_restricted"`，会导致 iOS 用户在冻结的同项目历史私聊详情页无法切换置顶/免打扰（违反 `specs/im/ios-client.md:23`）；
     - `NewChatView.swift:45-47` 锁定私密群说明文案写死“群聊仅你与名下助手可参与”，勾选 `project` 助手自动锁私密群时需区分提示“含项目级助手的群聊固定为私密群”，避免误导用户以为不能同时勾选同事。
- **修改方向**：
  - 在 `design.md` `UX Grounding` 中按 `PA`、`global` 普通助手、`single_thread` 普通助手三类分别给出准确的放宽确认提示要点；
  - 在 `design.md` 涉及范围与 `UX Grounding` 中补齐 iOS `AgentConfigView.swift`（放宽确认）、`NewChatView.swift`（`project` 锁私密文案区分 + `409` 跨群互通确认重试）与 `ChatInfoView.swift`（`409` 跨群互通确认重试 + L94 `agent_project_restricted` 置顶/免打扰豁免）。

### Recommendations

- **`R1-R1` SQLite 重建 `agent_profiles` 表时规避事务内 `PRAGMA foreign_keys` 失效与级联删除陷阱**：`apps/im-server/src/db.ts`（L10、L44）默认开启 `PRAGMA foreign_keys=ON` 并在 `BEGIN IMMEDIATE` 内跑迁移，而 `schema.sql` 中 `agent_settings_snapshots`、`agent_lifecycle`、`agent_lifecycle_requests`（均含 `ON DELETE CASCADE`）和 `agent_deletions` 均外键引用 `agent_profiles(agent_id)`，另有 `owner_direct_agent_messages` 视图与 `agent_lifecycle_created` 触发器依赖该表。SQLite 在活跃事务内会忽略 `PRAGMA foreign_keys=OFF`，实施 `db.ts` 表重建迁移时建议在 `BEGIN IMMEDIATE` 之前单独切换 `PRAGMA foreign_keys=OFF`，在事务内完成建新表、拷数据、删旧视图/触发器/旧表、重命名、重建视图/触发器/索引并执行 `PRAGMA foreign_key_check`，提交后恢复 `PRAGMA foreign_keys=ON`，防止存量库启动时报外键错误或误触发级联清空。
- **`R1-R2` `Runbook for Reviewer` 补充与 `--profile daily` 验收模板的关系说明**：`docs/development/frontend-experience.md` 约定常规真实产品验收优先复用 `./scripts/e2e-up.sh --profile daily`。当前 Runbook 使用默认空白 profile 以便自行初始化首个公司管理员与审批第二位成员，建议在修订 `design.md` 时顺手注明不使用 `--profile daily` 的原因（或给出在 `--profile daily` 下新增第二位团队成员的等价步骤），便于实施与旅程验收直接对齐。


### Author Resolutions

- **`R1-C1`**: `accepted` — 已在 `design.md`（涉及范围、关键决策 2.2、接口与数据流）完整补齐 `collaboration_scope === 'project'` 的 Agent 侧谓词 `canAgentAccessConversation` 及 `conversationRowAccess(isAgent)`、`Messaging.access`、`joinConversation`、`createConversation`、`resolveParticipants`、`resolveTarget` 与 `task-context-access.ts` 锚点：失权外部 1:1 私聊在真人侧标记 `agent_project_restricted` 只读，在 Agent 侧同步变为不可访问/不可写（返回 `403 collaboration_scope_restricted`），确保双向禁发并自动触发 `revokeLostTaskContextAccess` 吊销失权私聊任务上下文。
- **`R1-C2`**: `accepted` — 已在 `design.md`（关键决策 4、接口与数据流）与 `specs/gateway/personal-agent.md` 明确：`PersonalActions.prepareChecked` 在入口先解析目标会话（含 `args.task` 目标）并判定 `pureOwnerPrivateDestination`；命中纯主人私有域时跳过审核专用的 `decodePersonalImages`，并对非 `b.conversation_id` 的纯私有会话在 `prepareChecked` 内直接幂等执行任务图 `executeDelegated` 或消息/附件落库返回 `state='confirmed'`，无缝命中 `PersonalAssistant.task / send` 快路径且不误拒合法 GIF 或超长图。
- **`R1-C3`**: `accepted` — 已在 `specs/im/agent-work.md` 逐字恢复 `对照查看存活会话实时工具原始结果与冷态降级提示` 完整条款与 `尚无可查看执行`；在 `specs/gateway/routing-delivery.md` 补充 `MODIFIED` `Agent 可通过短标识下载受保护会话附件`（含 `sha256`）；新增 `specs/gateway/external-channels.md` delta-spec 同步三档外部渠道规则；并在 `conversations-messages.md`、`agent-work.md`、`gateway/personal-agent.md` 与 `design.md`（含 `docs/README.md` 归并说明）补齐统一权限矩阵互链。
- **`R1-W1`**: `accepted` — 已将 `agent-lifecycle.ts`、`task-graphs.ts`、`conversation-actions.ts` 与 `work.ts:notifyUpdated / memberExecutionNode` 纳入 `design.md` 涉及范围与关键决策 2：`notifyUpdated` 改按 `canViewAgentWork` 广播，`agent-lifecycle.ts` 与 `memberExecutionNode` 改用 `canCollaborateWithAgent`，`task-graphs.ts` 与 `conversation-actions.ts` 将 `agent_project_restricted` 映射为 `403`。
- **`R1-W2`**: `accepted` — 已在 `design.md` 关键决策 3.2 明确：`main.ts:529` 外部渠道非主人门禁改为 `collaborationScope !== 'team'`；所有收紧跃迁预留 `chatScope`，`team -> project` 清退外部渠道积压并经 `agent.scope.revoked` 精确清退公开群与失权私聊；`single-thread.ts` 对 `revokeConversations` 采用按会话维度的撤销代数 `revokedConversations`，杜绝误杀其他正常私密群并发在途消息。
- **`R1-W3`**: `accepted` — 已在 `spec.md`、`design.md` 关键决策 2.3、`specs/im/conversations-messages.md`、`specs/im/web-chat-ux.md` 与 `specs/im/ios-client.md` 明确：向含他人 `project` 助手的私密群添加外部真人成员须由该助手管理者本人操作（非主人返回 `403 project_agent_owner_required`），`confirm_project_context_share` 仅对助手主人有效，并统一表述为“外部真人成员集合不完全相同”。
- **`R1-W4`**: `accepted` — 已将 `packages/personal-assistant/assets/skills/nano-agent-creation/SKILL.md`、`apps/im-server/src/personal-agent-creation.ts`、`packages/dsh-integration/src/global-mode.ts` 与 `personal-security.ts:381` 主模型提示词改写完整纳入 `design.md` 涉及范围与 Context Before/After 说明。
- **`R1-W5`**: `accepted` — 已在 `design.md` `UX Grounding`、`specs/im/agents-nodes.md`、`specs/im/personal-agent.md` 与 `specs/im/ios-client.md` 按 `PA`、`global` 普通助手、`single_thread` 普通助手三类精确区分放宽确认文案，并补齐 iOS `AgentConfigView.swift`、`NewChatView.swift` 与 `ChatInfoView.swift`（含 `409` 跨群互通确认重试与 L94 `agent_project_restricted` 置顶/免打扰豁免）。
- **`R1-R1`**: `accepted` — 已纳入 `design.md` 关键决策 1 与风险章节：在 `BEGIN IMMEDIATE` 外先设 `PRAGMA foreign_keys=OFF`，在独占事务内重建表并同步重建依赖视图 `owner_direct_agent_messages` 与触发器 `agent_lifecycle_created`，校验 `PRAGMA foreign_key_check` 后提交并恢复 `PRAGMA foreign_keys=ON`。
- **`R1-R2`**: `accepted` — 已在 `design.md` `Runbook for Reviewer` 说明三角色（主人 A + 同项目成员 B + 圈外同事 C）验证选型及与 `--profile daily` 的配合方式。


## Round 2

### Metadata

- `started_at`: 2026-11-27T20:38:41+09:00
- `completed_at`: 2026-11-27T21:03:00+09:00
- `duration`: ~24m (wall clock incl. tool wait; active review ~5m)
- `reviewer`: Gate 2 `change-design-reviewer` (independent subagent, combined with `agent-context-review` & `frontend-experience-review` design-mode checks)
- `target`: `feat-803-agent-project-permission-scope` (`unit/feat-803-agent-project-permission-scope` @ `fb43ca6be`, diff `08c9df59d..fb43ca6be`)
- `review_mode`: `delta`
- `mode_reason`: `08c9df59d..fb43ca6be` 为围绕 Round 1 问题闭环的有界设计与契约增量（补齐 Agent 侧 `project` 访问谓词、纯私有域 `args.task` 与跳过 `decodePersonalImages` 快路径、按会话撤销代数 `revokedConversations`、非主人私密群扩圈 `403 project_agent_owner_required`、新增 `specs/gateway/external-channels.md` 及修复其余 delta-spec），核心架构边界、职责划分与单里程碑拓扑未变。
- `retained_from`: `Round 1`（未变更的 `specs/im/{spec,auth-tenancy}.md`、`specs/gateway/global-agent.md`、披露审核只读工具面与多租户空间不变量沿用 Round 1 核查证据）

### Verdict

**Approved**（`0 CRITICAL / 0 WARNING`，另有 `1` 条可选实施提示 `Recommendation`）

### Coverage & Evidence (Delta `08c9df59d..fb43ca6be`)

- **变更范围与波及面核查**：
  - 逐行审阅了 `git diff 08c9df59d..fb43ca6be`（涉及 `spec.md`、`design.md`、新增 `specs/gateway/external-channels.md` 及更新 9 份既有 delta-spec），并对照 `packages/dsh-integration/src/{index.ts,chat-scope.ts}`、`apps/node/src/main.ts`、`apps/im-server/src/{control.ts,collaboration.ts,messaging.ts,personal-actions.ts}` 与 `docs/specs/**` 复核了新增决策的上下游影响。
  - 运行 `./scripts/docs-check` 通过（`257 maintained Markdown sources, 74 required routes`），并全量脚本比对全部 **12 份** `specs/**` delta-spec 与 `docs/specs/**` canonical Requirement/Scenario 标题与正文，确认无遗漏或误删既有 Scenario、无跨文档契约冲突。
- **Agent Context 与前端/原生体验增量复核**：
  - `agent-context-review`：`personal-security.ts` 主提示词、`global-mode.ts` `download_attachment` 描述、`nano-agent-creation/SKILL.md` 与 `personal-agent-creation.ts` `options` 说明在 Before/After 清单与退出标准中已全部闭合，静态定义不影响会话内缓存前缀。
  - `frontend-experience-review`：从 `owner_only` 放宽至 `project`/`team` 的确认提示已按 `PA`、`global` 普通助手、`single_thread` 普通助手准确拆分，Web 与 iOS 的建群锁私密提示、非主人扩圈禁用提示、`409 project_agent_cross_group_confirmation_required` 二次确认重试及 `ChatInfoView.swift` 置顶/免打扰豁免均已完整对齐。

### Historical Issue Closure

- **`R1-C1` (`CRITICAL`)**: **closed**
  - *Author Resolution*: `accepted` — 补齐 `collaboration_scope === 'project'` 的 Agent 侧 `canAgentAccessConversation` 及 `conversationRowAccess(isAgent)`, `Messaging.access`, `joinConversation`, `createConversation`, `resolveParticipants`, `resolveTarget` 与 `task-context-access.ts` 锚点。
  - *Round 2 Evidence*: 核实 `design.md`（L15、L85–L89、L133）：当外部成员退出最后一个共同私密群后，`canAgentAccessConversation` 变为 `false`，`conversationRowAccess(isAgent)` 返回 `undefined`，`Messaging.access` 写模式及主动建聊/寻址/加公开群统一返回 `403 collaboration_scope_restricted`，同时 `task-context-access.ts:taskContextEligible` 随之变为 `false`，自动触发 `revokeLostTaskContextAccess` 撤回失权私聊任务上下文。
- **`R1-C2` (`CRITICAL`)**: **closed**
  - *Author Resolution*: `accepted` — 在 `PersonalActions.prepareChecked` 入口先判定 `pureOwnerPrivateDestination`（含 `args.task` 目标），命中时跳过 `decodePersonalImages` 并直接落库返回 `state='confirmed'`。
  - *Round 2 Evidence*: 核实 `design.md`（L19、L36、L106–L107、L137）与 `specs/gateway/personal-agent.md`（L10–L11）：免审分支跳过面向多模态审核模型的 `decodePersonalImages`，对非 `b.conversation_id` 纯私有会话直接在 `prepareChecked` 幂等完成 `executeDelegated`（返回 `{ state: 'confirmed', conversation_id, result }`）或消息落库（返回 `{ state: 'confirmed', message_id, conversation_id }`），与 `PersonalAssistant.task / send` 既有 `confirmed` 分支闭合且无需放宽 `gateway.ts:531`。
- **`R1-C3` (`CRITICAL`)**: **closed**
  - *Author Resolution*: `accepted` — 恢复 `specs/im/agent-work.md` 完整 Scenario，更新 `specs/gateway/routing-delivery.md` 含 `sha256`，新增 `specs/gateway/external-channels.md`，补齐统一权限矩阵互链。
  - *Round 2 Evidence*: 核实 `specs/im/agent-work.md`（L49–L56）、`specs/gateway/routing-delivery.md`（L116–L128）、`specs/gateway/external-channels.md`（L1–L65）及 `conversations-messages.md`（L7）、`agent-work.md`（L13）、`gateway/personal-agent.md`（L7）、`design.md`（L117、L199），与 `docs/specs/**` 逐条一致且 `./scripts/docs-check` 通过。
- **`R1-W1` (`WARNING`)**: **closed**
  - *Author Resolution*: `accepted` — 纳入 `work.ts:notifyUpdated / memberExecutionNode`、`agent-lifecycle.ts`、`task-graphs.ts`、`conversation-actions.ts`。
  - *Round 2 Evidence*: 核实 `design.md`（L12、L16、L84、L89、L127、L133）：`notifyUpdated` 改用 `canViewAgentWork` 覆盖个人空间全局助手实时事件，`agent-lifecycle.ts` 与 `memberExecutionNode` 改用 `canCollaborateWithAgent`，`task-graphs.ts` 与 `conversation-actions.ts` 统一将 `agent_project_restricted` 映射为 `403`。
- **`R1-W2` (`WARNING`)**: **closed**
  - *Author Resolution*: `accepted` — `main.ts:529` 外部渠道门禁改为 `collaborationScope !== 'team'`，收紧跃迁预留 `chatScope` 并清退外部渠道积压，`single-thread.ts` 改用按会话维度的 `revokedConversations`。
  - *Round 2 Evidence*: 核实 `design.md`（L23、L99–L102、L214）与 `chat-scope.ts` / `dsh-integration/src/index.ts:817`（`configuration.apply` 的 `finally` 块自动释放 `chatScope.release` 不会死锁；按会话撤销代数消除了跨私密群误杀并发在途消息的竞态）。
- **`R1-W3` (`WARNING`)**: **closed**
  - *Author Resolution*: `accepted` — 向含他人 `project` 助手的私密群添加外部真人成员要求该助手管理者本人操作（否则返回 `403 project_agent_owner_required`），`confirm_project_context_share` 仅对助手主人有效，统一“外部真人成员集合不完全相同”表述。
  - *Round 2 Evidence*: 核实 `spec.md`（L126–L130）、`design.md`（L17、L92–L93、L131–L132、L186）与 `specs/im/{conversations-messages,web-chat-ux,ios-client}.md`，即使同一私密群含两位不同主人的 `project` 助手，操作者 `p.owner_id` 校验也能防止任一方单方面向新外部成员扩大对方助手的暴露圈。
- **`R1-W4` (`WARNING`)**: **closed**
  - *Author Resolution*: `accepted` — 补入 `nano-agent-creation/SKILL.md`、`personal-agent-creation.ts`、`global-mode.ts` 与 `personal-security.ts` 提示词改写。
  - *Round 2 Evidence*: 核实 `design.md`（L13、L22–L24、L126、L169–L177、L238）与 `specs/gateway/personal-agent.md`（L56），PA 创建与外发两条 Context 链路均已完整覆盖。
- **`R1-W5` (`WARNING`)**: **closed**
  - *Author Resolution*: `accepted` — 按助手类型拆分放宽确认文案，补齐 iOS `AgentConfigView.swift`、`NewChatView.swift`、`ChatInfoView.swift` 确认弹窗与置顶/免打扰豁免。
  - *Round 2 Evidence*: 核实 `design.md`（L25、L94、L185–L187）与 `specs/im/{agents-nodes,personal-agent,ios-client}.md`，文案与双端交互闭环一致。
- **`R1-R1` / `R1-R2` (`Recommendations`)**: **incorporated**（见 `design.md` L79、L213、L230）。

### Issues

None（`0 CRITICAL / 0 WARNING`）。

### Recommendations

- **`R2-R1` 实施 `dsh-integration/src/index.ts:1524` 与 `team -> project` 收紧边界时的细部守卫提示**：
  1. 在 `packages/dsh-integration/src/index.ts:1524`（`config?.collaborationScope === 'owner_only' && input.source.nanoTeamChat`）中，`nanoTeamChat`（由 `single-thread.ts:341` 生成）对所有含外部成员的私密群同样为 `true`，实施时该行应继续仅拦截 `'owner_only'`（切勿误改为 `!== 'team'`，否则会拦截 `project` SingleThread 助手在合法私密群内的输入），`project` 档位的失权会话拦截由 `revokedConversations` 与 `chatScope.restrict` 承担。
  2. `configuration.apply`（`dsh-integration/src/index.ts:817`）返回时会立即 `chatScope.release`，早于中心 `control.ts:530` 事务提交后异步下发 `agent.scope.revoked`；若希望连 `apply` 返回至 `agent.scope.revoked` 抵达之间的极窄窗口也零漏放，实施时可在 `control.ts` 预计算或由 `main.ts:apply` 在 `'team' -> 'project'` 分支一并向 `configuration.restrictChat` 提交已知失权会话变更后再释放 `chatScope`。


### Author Resolutions

- **`R2-R1`**: `accepted` — 在实施阶段严格保持 `packages/dsh-integration/src/index.ts:1524` 仅对 `collaborationScope === 'owner_only'` 拦截 `nanoTeamChat`（不误伤 `project` 共享私密群），并在收紧流中先完成外部渠道与失权会话清退再释放 `chatScope`。
