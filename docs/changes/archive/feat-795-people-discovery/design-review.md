# feat-795: 组织级人机协作找人与通讯录体验 — Design Review

## Round 1

### Metadata

- **reviewer**: Independent Gate 2 Design Reviewer (`f2eab8f0-a8e8-479d-b91a-d9da74d298ec`, `change-design-reviewer` + `frontend-experience-review` design mode)
- **target**: `feat-795-people-discovery @ 8c0616479` (`/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-795-people-discovery`)
- **review_mode**: `full`
- **mode_reason**: Round 1 初审，覆盖全部现状断言、关键设计决策、用户约束、跨包架构边界、前端体验设计（design mode）、delta-specs 与 Milestone M1 范围及退出条件。
- **started_at**: `2026-11-26T18:17:44+09:00`
- **completed_at**: `2026-11-26T18:32:30+09:00`
- **duration**: `14m 46s`

### Verdict

- **Verdict**: `Issues Found` (`Changes Requested`)
- **Counts**: `3 CRITICAL / 5 WARNING / 3 Recommendations`

---

### Coverage 与证据

#### 1. 现状断言与真实代码装配点核对

已逐项将 `design.md` 现状判断与 `apps/im-server`、`src/IM/frontend`、`apps/desktop`、`src/IM/ios` 真实代码核对：

- **可复用链路与边界符合事实的部分**：
  - `apps/im-server/src/contacts.ts:9-53` 已按 `membership_status === "active"` / 个人空间隔离返回真人（`kind: "user"`）、公开 PA（`kind: "agent", role: "personal"`）与公司 Agent，且公开 PA 不暴露 `node_id` / `node_name`。
  - `src/IM/ios/NanoIM/Client/CommonModels.swift` 的 `Contact: Codable` 忽略未知 JSON 字段；在 `contacts.ts` 为真人条目新增可选 `username` 向后兼容原生 iOS 客户端。
  - `apps/desktop/src/host_server.rs:2202` 对非静态资源路径已有 `index.html` 通配回退，Desktop host 本身不拦截 `/people`。
  - `src/IM/frontend/src/app/providers.tsx` 已注入全局 `AvatarIdentitiesProvider`（拉取 `listContacts()`），`NewChatModal` / `ChatWorkspacePage` 复用 `createConversation({ type: "direct", participant_ids })` 的服务端 1:1 去重（`apps/im-server/src/messaging.ts:261-285`）。
  - 本需求完全位于 `apps/im-server` 与 `src/IM/frontend`，不触碰 DSH runtime、`packages/personal-assistant` 或 Agent Context 注入链路，遵守 `AGENTS.md` / `SPEC.md` 跨包边界，也无需一次性数据迁移。
- **现状判断与真实实现存在偏差的关键装配点（已计入 Issues）**：
  1. `apps/im-server/src/server.ts:339-341,384` 采用显式 SPA 路由白名单正则，未包含 `/people`，直连或刷新会返回 `404 {"detail":"not found"}`（`R1-C1`）。
  2. 外部渠道未映射发送者在 `apps/im-server/src/messaging.ts:437-439` 与 `message-records.ts:290-303,318` 中使用代记账号 `c.owner_user_id`（真实团队成员 `users.id`）落库并序列化为 `sender.id` / `sender.user_id`，仅靠 `visibleHumanContactsById.has(userId)` 会误判为该代记同事（`R1-C2`）。
  3. `agent_profiles.owner_id` 存的是 `users.owner_id` 而非 `users.id`（`apps/im-server/src/schema.sql:26-30`、`contacts.ts:29-34`、`tests/control-fixture.ts:14-29`），而 `POST /im/v1/conversations` 要求 `users.id`（`messaging.ts:265`），且 `AgentProfilePage.tsx:33` 仅请求 `kind="agent"`，导致人机归属关联与管理者私聊在 `owner_id !== id` 或现有查询下断裂（`R1-C3`）。
  4. 新批准入企但尚未绑定电脑/PA 且无历史会话的成员在 `ChatWorkspacePage.tsx:1331-1332,1389` 会被 `FirstUseWelcome` 整页遮挡，无法看到会话侧栏（`R1-W1`）。

#### 2. 需求、用户约束与架构判断

- **需求覆盖（`spec.md` 4 项核心目标 + 8 个验收场景）**：
  - 顶层 `/people` 组织通讯录、桌面/移动导航、个人空间克制引导、Chat 侧栏 `⌘K/Ctrl+K` 搜索召回联系人与「同事」筛选、消息流/群成员轻量 `PersonPopover`、新建聊天/群聊/Agent 资料页 `@username` 与管理者发起私聊均有对应设计落点。
  - **架构评价**：复用单一 `/im/v1/contacts` 数据源与 `POST /im/v1/conversations` 幂等 1:1 会话，避免新增平行通讯录表或冗余 API，模块职责清晰；补齐下述 3 个 CRITICAL 数据/路由契约与 5 个 WARNING 交互状态边界后即可闭环。
- **用户附加约束核对**：
  - **跳过静态 HTML 原型**：`design.md:72` 已记录用户跳过独立原型步骤的决定，符合 `frontend-experience-review`「原型服务决策校准而非存档门禁」原则。
  - **保留既有 worktree E2E 服务用于后续验证**：`design.md:166-168` Runbook 已显式写入保留现场约束，但健康检查 URL 误用了不存在的 `/openapi.json`（见 `R1-W5`）。
  - **中英文双语与回归面**：`spec.md` 与 `specs/im/web-chat-ux.md` 已纳入 `zh.json` / `en.json` 对齐与切换刷新验收。

#### 3. 前端体验设计审查（`frontend-experience-review` Design Mode）

围绕桌面（`1280×820`）与移动（`320px–390px`）真实使用路径，重点检查了自明性、操作权重、阅读动线、弹层层级与异常/空状态：

- **自明性与阅读动线**：`/people` 采用连续画布目录承载「同事 + 公开 PA + 管理的数字员工」，把高频找人保留在 Chat `⌘K` /「同事」Tab 与上下文 `PersonPopover`，符合 `docs/product/web-im-principles.md`「会话流绝对主角、少层级克制表达」原则。
- **需在设计阶段收口的体验风险**：
  - 新入职无会话无 PA 成员在 `/chat` 被 `FirstUseWelcome` 挡住侧栏，Scenario 2 动线直接中断（`R1-W1`）。
  - `/people` 与 `PersonPopover` 中点击「同事的公开 PA」与「专业数字员工」未区分目标动作，易跳入对他人不可见的 PA `Work` 页或空白设备资料（`R1-W2`）。
  - `PersonPopover` 复用 `z-index: 80` 在 `GroupSettings`（`z-index: 90–95`）内会被遮挡，且引用回复预览（`replyPreview`）与 `draftMentions` 序列化存在交互冲突（`R1-W3`）。
  - 视觉权重、加载失败态区分与移动端 5 项底栏未读角标偏移见 `R1-R1`、`R1-R2`。

#### 4. 审查安排、Delta-specs 与 Milestone 审计

- **审查安排**：`design.md` 选择 `change-code-review` + `frontend-experience-review`（并在多步骤跨页面串联不通时补充 `product-journey-review`），因不改动模型可见上下文而排除 `agent-context-review`，组合合理。
- **Delta-specs 审计**：
  - `specs/im/agents-nodes.md` 准确补充了真人 `username` 与公开 Agent 资料页管理者私聊能力（需与 `R1-C3` 的可见成员校验和 `owner_user_id` 对齐）。
  - `specs/im/web-chat-ux.md` 覆盖了 `/people`、Chat 搜索/筛选、`PersonPopover` 与双语，但将 `NewGroupModal`（仅本人 Agent）的双行 `Agent ID + 机器名` 硬套到了 `NewChatModal`（含无机器名的同事公开 PA 与归属者信息），与 `spec.md:88` 及 PA 隐私规则冲突，且漏写了桌面主导航入口与 `NewChatModal` 分类筛选（`R1-W4`）。
- **Milestone M1 审计**：单里程碑交付符合本需求内聚度，但 M1 `范围` 漏列了 `apps/im-server/src/server.ts` 及对应路由测试（`R1-C1`）。

---

### 历史问题闭环

- 无（本轮为 Round 1 首轮审查）。

---

### Issues

#### CRITICAL

- **`R1-C1` — `apps/im-server/src/server.ts` SPA 路由白名单未放行 `/people`，且 M1 范围漏列 `server.ts`，导致直连、刷新与登录后回跳返回 HTTP 404**
  - **位置**：`docs/changes/feat-795-people-discovery/design.md`（`## 现状分析 > 涉及范围` 第 11–13 行、`## Milestones` M1 `范围` 第 171 行）对比 `apps/im-server/src/server.ts:339-341,384`、`src/IM/frontend/src/features/auth/membership-page.tsx:8-10`。
  - **证据**：`apps/im-server/src/server.ts:340` 仅当路径命中 `/^\/(chat|tasks|settings|bind\/confirm|login|register|membership|onboarding|me)(\/|$)/` 时才返回前端 `index.html`（或开发态前端重定向），其余路径落入第 384 行 `404 {"detail":"not found"}`。同时 `membership-page.tsx:8-10` 的 `safeReturnPath` 允许任意单斜杠站内路径，未登录访问 `/people` 在登录成功后也会回跳 `/people`。`design.md` 新增顶层 `/people` 路由，却将后端改动严格限定在 `apps/im-server/src/contacts.ts` 与 `tests/contacts.test.ts`。
  - **未修后果**：在生产或 worktree E2E（`$IM_URL/people`）中直接打开 `/people`、分享链接回跳，或执行 `specs/im/web-chat-ux.md:60` 要求的「在 `/people` 切换中英文并刷新」时，服务端直接返回 404，顶层页面不可达。需将 `server.ts` SPA 路由白名单（加入 `people`）及对应服务端路由测试纳入 `design.md` 涉及范围与 M1 范围。

- **`R1-C2` — 外部渠道未映射发送者判据仅依赖 `visibleHumanContactsById.has(userId)`，会把代记账号误识别为可私信真人同事**
  - **位置**：`docs/changes/feat-795-people-discovery/design.md`（`## 关键决策` 第 4 条第 88 行、`## 风险与回退` 第 149 行）对比 `apps/im-server/src/messaging.ts:437-439`、`apps/im-server/src/message-records.ts:290-303,318`、`docs/specs/im/conversations-messages.md:412-415`。
  - **证据**：`design.md:149` 假设未映射外部渠道发送者的 `userId` 不在 `contacts` 目录内。但 `messaging.ts:437-439` 在写入外部入站用户消息时将 `sender_user_id` 设为会话所属节点的真实 IM 用户 `c.owner_user_id`；`message-records.ts:301-302,318` 将 `sender.id` 与 `sender.user_id` 均投影为该真实用户的 `u.id`（且 `sender_source_id` 为 `enumerable: false`，不会随 JSON 下发），线上报文仅通过 `sender.avatar_id` 的 `"external:"` 前缀（及会话级 `conversation.external_source != null`）区分外部未映射身份。该代记 `owner_user_id` 本身就是活跃团队成员，必然存在于其他同事的 `visibleHumanContactsById` 中。
  - **未修后果**：当团队内其他成员（或未来共享/组件视图）查看含外部来源消息的会话时，点击外部发送者头像会弹出**节点代记同事**的 `PersonPopover` 并向错误的人发起站内私聊，直接违反 `spec.md:74-77` 与 `docs/specs/im/conversations-messages.md:415`（「不将代记账号作为可私信发送者」）。设计须明确排除 `message.sender.avatar_id?.startsWith("external:")` 及 `Boolean(conversation?.external_source)` 的消息发送者触发器。

- **`R1-C3` — 真人与名下 PA / 数字员工的归属关联及 `AgentProfilePage` 管理者私聊混用了 `users.owner_id` 与 `users.id`，且 `AgentProfilePage` 未加载真人目录**
  - **位置**：`docs/changes/feat-795-people-discovery/design.md`（`## 现状分析` 第 19 行、`## 关键决策` 第 4 条第 88 行、`## 接口与数据流` 第 100–112 行）对比 `apps/im-server/src/contacts.ts:10,16,29-47`、`apps/im-server/src/messaging.ts:265`、`apps/im-server/src/schema.sql:26-30`、`apps/im-server/tests/control-fixture.ts:14-29`、`src/IM/frontend/src/features/settings/agents/agent-profile-page.tsx:33,158`。
  - **证据**：
    1. 数据库中 `agent_profiles.owner_id` 存放的是 `users.owner_id`（见 `contacts.ts:29` 注释 `"including installations where owner_id differs from id"` 及标准测试夹具 `control-fixture.ts` 中 `id='u1', owner_id='o1'`），而 `contacts.ts:43` 的真人条目只返回 `user_id: users.id`（无 `owner_id`），Agent 条目只返回 `owner_id: ap.owner_id`（无 `owner_user_id`）；甚至 `contacts.ts:16` 的 `LEFT JOIN users owner ON owner.id=ap.owner_id` 在 `owner_id !== id` 时也会拿不到 `owner_display_name`（第 29–34 行特意用 `owners` Map 修补了 PA，却未修补公司 Agent 的 `owner_display_name` 与 `owner_user_id`）。
    2. `POST /im/v1/conversations`（`messaging.ts:265`：`SELECT * FROM users WHERE id=?`）只接受 `users.id`（`user_id`）；若直接传入 `agent.owner_id`，在 `owner_id !== id` 的账号上会直接返回 `404 participant not found`。
    3. `AgentProfilePage.tsx:33` 当前只调用 `listContacts("", "agent")`，根本没有可见真人目录来校验 `specs/im/agents-nodes.md:14` 要求的「当管理者为当前可见团队成员（且非本人）时发起私聊」及展示管理者 `@username`。
  - **未修后果**：在历史升级账号及标准服务端测试夹具下，`/people` 与 `PersonPopover` 无法把真人同事与其公开 PA / 数字员工关联起来，`AgentProfilePage` 点击管理者发私聊会 404 或无法判断可见成员身份。需在 `contacts.ts` 统一对齐归属主键（如为 Agent 补齐解析后的 `owner_user_id` 并修正 `owner_display_name` 回退，或同步对齐真人归属键），并让 `AgentProfilePage` 结合可见真人联系人解析管理者 `user_id`。

#### WARNING

- **`R1-W1` — 新入企但尚未绑定电脑/PA 且零历史会话的成员在 `/chat` 被 `FirstUseWelcome` 隐藏侧栏，阻断 Scenario 2 找人主路径**
  - **位置**：`docs/changes/feat-795-people-discovery/design.md`（`## 关键决策` 第 2–3 条第 80–86 行、`## Runbook for Reviewer` 第 167 行）对比 `src/IM/frontend/src/features/chat/chat-workspace-page.tsx:365,1331-1332,1389`、`apps/im-server/src/identity.ts:253`。
  - **证据**：所有新注册账号默认 `personal_space_enabled = true`（`identity.ts:253`），批准加入企业（`membership_status = "active"`）后该布尔值仍为 `true`。`ChatWorkspacePage.tsx:1331-1332` 中 `showFirstUseWelcome = !conversationId && personalSpace && personalAgent.isSuccess && !personalBinding && conversationsQuery.isSuccess && localConversations.length === 0`，满足条件时第 1389 行直接卸载 `ConversationSidebar` 并全屏渲染面向纯个人空间空账号的 `<FirstUseWelcome />`。
  - **未修后果**：刚加入团队、尚未绑定节点且还没有任何聊天记录的新成员（恰对应 `spec.md` 场景 2「新账号」、`docs/specs/im/agents-nodes.md:823`「不要求已有 Gateway」以及 `design.md:167` Runbook 新注册测试账号）进入 `/chat` 时看不到会话侧栏，无法使用 `⌘K/Ctrl+K` 搜索或点击「同事」筛选发起第一条私聊。设计需明确在 `user.membership_status === "active"`（或存在其他可见团队联系人）时不以全屏 `FirstUseWelcome` 遮蔽 `ConversationSidebar`。

- **`R1-W2` — `/people` 与 `PersonPopover` 中点击同事「公开 PA」与「专业数字员工」缺少隐私安全的动作区分**
  - **位置**：`docs/changes/feat-795-people-discovery/design.md`（`## 现状分析` 第 14、27 行，`## 关键决策` 第 1、4 条第 75、88 行）对比 `src/IM/frontend/src/features/settings/agents/agent-profile-page.tsx:83,130-162`、`apps/im-server/src/personal-agent.ts:535`、`src/IM/frontend/src/features/chat/chat-workspace-page.tsx:1484`。
  - **证据**：`spec.md:25,43` 要求同事条目同时展示公开 PA 与管理的数字员工，并支持「查看对应工作与资料」；但 `personal-agent.ts:535` 将所有 PA 的 `work_mode` 均存为 `"global"`，而 PA 的 Work 看板与配置仅归属者本人可见（`docs/specs/im/personal-agent.md:24`）。当前 `AgentProfilePage.tsx:131` 只要 `agent.work_mode === "global"` 就渲染 `Work` Tab（未像 `ChatWorkspacePage.tsx:1484` 那样排除非本人 `role === "personal"`），且公开 PA 不返回 `node_name`（`AgentProfilePage.tsx:161` 设备字段为空）。`design.md` 未界定点击同事 PA 与点击专业数字员工分别触发什么动作。
  - **未修后果**：若实现统一跳往 `/settings/agents/:id?view=work` 或未收口非本人 PA 的 `AgentProfilePage`，用户点击同事 PA 会落入无权限的 Work 视图或残缺资料页。设计需明确区分：点击同事公开 PA 直接发起与该 PA 的 1:1 协作会话（若允许进公开资料页，则 `AgentProfilePage` 必须对非本人 `role === "personal"` 隐藏 `Work` Tab 与空设备行）；点击专业数字员工（`role !== "personal"`）进入 `/settings/agents/:agentId` 查看工作与资料。

- **`R1-W3` — `PersonPopover` 在群设置抽屉内的层级冲突、双路径 `@mention` 渲染与输入框 `<mention/>` 协议写入未与 `MessagePane` 真实机制对齐**
  - **位置**：`docs/changes/feat-795-people-discovery/design.md`（`## 可复用能力` 第 35 行、`## 关键决策` 第 4 条第 87–89 行）对比 `src/IM/frontend/src/features/chat/components/agent-activity-popover.css:14`、`src/IM/frontend/src/styles/global.css:5467,5478,5898`、`src/IM/frontend/src/features/chat/components/message-pane.tsx:420-427,748,862-872,1572-1576,2191,2321-2344,2421-2453,2529-2531`、`thread-column.tsx:228`。
  - **证据**：
    1. **层级遮挡与外部点击误关**：`AgentActivityPopover` 的样式层级为 `z-index: 80`（`agent-activity-popover.css:14`），而 `GroupSettings` 遮罩/抽屉/移动弹层为 `z-index: 90 / 91 / 95`（`global.css:5467,5478,5898`）。从群成员列表打开 `PersonPopover` 若沿用 `z-index: 80` 会被遮在抽屉后方，且点击关闭弹层时可能误触 `GroupSettings` 背景遮罩。
    2. **消息正文双渲染路径与引用块嵌套陷阱**：真人消息走 `renderInlineContent`（`message-pane.tsx:2530`），而 Agent / PA 消息走 `MarkdownContent` + `remarkMention`（`message-pane.tsx:2321-2344`），两处正文都需支持点击真人 `@mention` 打开名片；但引用预览 `replyPreview`（`message-pane.tsx:1574`）包裹在 `<Link className="chat-message-quote">`（第 2191 行）和 `<button className="chat-message-quote">`（`thread-column.tsx:228`）内部，绝不能把其中的 `@mention` 渲染成 `<button>`。
    3. **输入框 `@` 提及协议与可用条件**：`MessagePane` 发送时仅当 `draftMentions` 数组存在匹配的 `{ label, type: "user", target_id }` 时才会序列化为服务端识别的 `<mention type="user" target_id="..."/>`（`message-pane.tsx:748,868-870`），且现有的 `draftSeed`（第 420–427 行）会整段覆盖 `draft` 并清空 `draftMentions`。此外「`@` 提及」动作仅应在当前群聊可发言（`type === "group" && can_write !== false && !dissolved_at && !external_source`）且目标成员仍在 `conversation.participants` 中时暴露。
  - **未修后果**：群设置内点击成员名片不可见、Agent 消息里的 `@同事` 点不动或引用块出现非法 `<button>` 嵌套，且名片「`@` 提及」会清空用户未发送草稿或只发出纯文本而丢失真实 mention 通知。

- **`R1-W4` — `specs/im/web-chat-ux.md` 将 `NewGroupModal` 的 `Agent ID + 机器名` 双行规则强加给 `NewChatModal`，与 `spec.md` 及公开 PA 隐私边界冲突**
  - **位置**：`docs/changes/feat-795-people-discovery/specs/im/web-chat-ux.md:38-41` 对比 `docs/changes/feat-795-people-discovery/spec.md:38-50,86-88`、`apps/im-server/src/contacts.ts:44-45`、`src/IM/frontend/src/features/chat/components/new-chat-modal.tsx:31-32`。
  - **证据**：delta-spec 将「打开新聊天」合并进 `Scenario: 新建聊天与新建群聊区分真人同事与候选 Agent`，规定「当用户打开新聊天或新建群聊……Agent 候选第一行显示名称及本地化在线状态、第二行显示 Agent ID 与所属机器名（机器名缺省时回退 node ID）」。该规则原本仅适用于只列本人 Agent 的 `NewGroupModal`；而在 `NewChatModal` 中，候选包含跨团队公司 Agent 与同事公开 PA：公开 PA 在 `contacts.ts:44-45` 中刻意隐藏了 `node_name` 与 `node_id`，且 `spec.md:88` 明确要求 `NewChatModal`「提供分类筛选……Agent 条目保持展示归属信息、设备名与在线状态」。此外 `specs/im/web-chat-ux.md` 仅写了移动底栏 5 项顺序，未写明桌面主导航（`Chat / People / Tasks / Agents`）与 `NewChatModal` 的分类筛选。
  - **未修后果**：下游实现与 `change-code-review` 在核对 delta-spec 时会遇到直接矛盾——按 `spec.md` 展示归属者与 PA 身份会违反 delta-spec 的 `Agent ID + node ID` 字面要求，按 delta-spec 实现则会破坏公开 PA 不暴露节点 ID 的契约并丢失归属者信息。需在 `specs/im/web-chat-ux.md` 中拆清 `新聊天`（含分类筛选、跨成员归属与可选设备名）与 `新建群聊`（本人可控 Agent）的副标题规则，并补齐桌面主导航描述。

- **`R1-W5` — `ConversationSidebar` 模式互斥（`searchActive` / `distillMode` / `⌘K`）、1:1 会话去重键与 Reviewer Runbook 健康检查接口存在具体偏差**
  - **位置**：`docs/changes/feat-795-people-discovery/design.md`（`## 关键决策` 第 2–3 条第 80–86 行、`## Runbook for Reviewer` 第 161 行）对比 `src/IM/frontend/src/features/chat/components/conversation-sidebar.tsx:166-175,214-269`、`chat-workspace-page.tsx:1391-1392`、`apps/im-server/src/server.ts:289-290`。
  - **证据**：
    1. **侧栏状态隔离**：`docs/specs/im/web-chat-ux.md:38,447` 规定搜索激活但未输入关键字时为独立空搜索提示视图（不混排常规会话列表），提炼模式（`distillMode`）仅允许选择单线程 Agent 会话。`design.md` 需明确「同事」Tab 下的「未联系同事」分组仅在 `!searchActive && !distillMode` 时展示，且 `⌘K/Ctrl+K` 在弹窗打开、`distillMode` 或移动端会话详情态（侧栏未挂载）时不抢占焦点。
    2. **搜索结果「会话 / 联系人」去重键**：`conversations` 列表中包含飞书等外部映射 1:1 会话（`external_source != null`），且会话参与者中 Agent 的 `actor.id` 为 `agent_id`、`actor.user_id` 为底层用户 ID（`chat-types.ts:31-35`）。联系人去重必须仅将**站内非外部** 1:1 会话（`type === "direct" && !external_source`）视为已有直聊，并分别按真人 `user_id`（`participant.user_id ?? participant.id`）与 Agent `agent_id`（`participant.id`）精确匹配。
    3. **Runbook 健康检查 404**：`design.md:161` 写了 `curl -fsS "$IM_URL/openapi.json" >/dev/null`，但 `apps/im-server`（Fastify，`server.ts:289-290`）不存在 `/openapi.json` 路由（仅旧 Python 时代遗留印象），真实健康检查端点为 `$IM_URL/health`（与 `scripts/e2e-up.sh:343` 一致）。
  - **未修后果**：「未联系同事」泄漏进空搜索页或提炼模式、外部渠道影子会话导致站内真人从联系人召回中误消失，且 Reviewer 按 Runbook 自检服务时第一步即因 `/openapi.json` 404 失败。

---

### Recommendations

- **`R1-R1` — `/people` 操作权重、本人行呈现与异常态区分（`frontend-experience-review`）**
  - 建议 `/people` 沿用 `.im-agent-directory`（`src/IM/frontend/src/features/settings/agents/agent-settings.css:140-159`）的连续列表呼吸感：行尾「发消息」采用次级安静按钮（`.im-settings-action`）而非每行高饱和实心主色按钮，避免满屏主按钮抢夺姓名、`@username` 与数字员工标签的视觉重心；当前登录者本人行仅显示「你 / You」标识而不渲染对自己发消息的按钮；同时区分 `contacts` 的加载骨架态与请求失败态（提供重试按钮，避免接口报错时误显示为个人空间空态或空团队）。

- **`R1-R2` — 移动端 5 项底栏未读角标定位跟随图标而非固定右偏移**
  - `src/IM/frontend/src/app/shell/app-shell.css:39-44` 中 `.im-shell-unread-badge` 目前以固定宽度 `78px` 的 `.im-shell-bottomtab` 为基准写死 `right: 10px`。改为 5 项 `flex: 1; min-width: 0` 后，在 `430px–767px` 宽屏手机/小平板上角标会远离图标漂移，在 `320px`（单项 `64px`）上则会挤压图标。建议将未读角标锚定到 `.im-shell-bottomtab-icon`（或基于 `50%` 中心偏移定位）。

- **`R1-R3` — `GroupSettings` 成员列表与加人候选同步透传 `@username`**
  - `design.md` 关键决策第 5 条已为 `NewChatModal` 与 `NewGroupModal` 真人条目补齐 `@username`；建议顺带在 `ChatWorkspacePage.tsx:571-601` 组装 `GroupSettingsMember` 与加人候选时一并透传 `username`，使群设置抽屉内的非本人成员副标题也与新建聊天/新建群聊保持一致，不再只显示笼统的「人 / Person」。

---

### Author Resolutions

- **`R1-C1`**: `accepted` — 已在 `design.md`（涉及范围、关键决策 1、接口与数据流 1、M1 范围与退出标准）与 `specs/im/web-chat-ux.md` 中将 `apps/im-server/src/server.ts` SPA 路由白名单放行 `people` 及服务端路由测试纳入范围，确保直连、刷新与登录回跳 `/people` 返回 `index.html`。
- **`R1-C2`**: `accepted` — 已在 `design.md`（涉及范围、关键决策 4、风险与回退）与 `specs/im/web-chat-ux.md` 中明确排除 `Boolean(conversation?.external_source)` 及 `message.sender.avatar_id?.startsWith("external:")` 的外部未映射代记发送者，不向代记账号渲染真人名片。
- **`R1-C3`**: `accepted` — 已在 `design.md`（涉及范围、关键决策 4–5、接口与数据流 1）与 `specs/im/agents-nodes.md` 中明确由 `contacts.ts` 通过 `owners` 映射统一补齐 Agent 的 `owner_user_id`（`users.id`）并修复公司 Agent 的 `owner_display_name` 回退，同时让 `AgentProfilePage` 拉取全量 `listContacts("")` 对齐可见真人目录。
- **`R1-W1`**: `accepted` — 已在 `design.md`（涉及范围、关键决策 3、M1 退出标准）与 `specs/im/web-chat-ux.md` 中明确 `FirstUseWelcome` 仅对 `membership_status !== "active"` 的纯个人空间空账号全屏展示，活跃团队成员即使无会话、无绑定节点也始终保留 `ConversationSidebar`。
- **`R1-W2`**: `accepted` — 已在 `design.md`（涉及范围、关键决策 4）与 `specs/im/{agents-nodes,web-chat-ux}.md` 中明确区分动作：点击同事公开 PA（`role === "personal"`）直接打开 1:1 协作会话（且非本人 PA 在 `AgentProfilePage` 隐藏 `Work` Tab 与空设备行）；点击专业数字员工（`role !== "personal"`）进入 `/settings/agents/:agentId`。
- **`R1-W3`**: `accepted` — 已在 `design.md`（涉及范围、关键决策 4）中明确：`PersonPopover` 提升至 `z-index: 110` 并阻止关闭点击穿透 `GroupSettings`；消息正文同时覆盖 `renderInlineContent` 与 `MarkdownContent`（`remarkMention`）且排除 `replyPreview` 引用块；可写非外部未解散群聊中的活跃成员支持通过专用 `insertMention` 追加 `@显示名 ` 与 `draftMentions` 而不覆盖既有草稿或附件。
- **`R1-W4`**: `accepted` — 已在 `specs/im/web-chat-ux.md` 将 `NewChatModal`（含「全部/同事/助手」筛选、同事置顶、归属与可选设备名、公开 PA 不暴露 `node_id`）与 `NewGroupModal`（同事置顶 `@username` + 本人 Agent 的 `Agent ID + 机器名`）拆分为独立 Scenario，并补齐桌面主导航（`Chat、People、Tasks、Agents`）描述。
- **`R1-W5`**: `accepted` — 已在 `design.md`（关键决策 2–3、Runbook）与 `specs/im/web-chat-ux.md` 中明确：未私聊同事分组仅在 `!searchActive && !distillMode && filter === "direct-user"` 展示；`⌘K`/`Ctrl+K` 避开活动模态框、`distillMode` 与侧栏未挂载态；搜索联系人仅对站内非外部 1:1 直聊按真人 `user_id` / Agent `agent_id` 去重；Runbook 健康检查修正为 `$IM_URL/health`。
- **`R1-R1`**: `accepted` — 已在 `design.md`（涉及范围、关键决策 1）采纳：`/people` 行尾使用 `.im-settings-action` 次级安静按钮，本人行仅显示「你 / You」与个人设置入口，并明确区分加载骨架、失败重试、个人空间引导与空搜索态。
- **`R1-R2`**: `accepted` — 已在 `design.md`（涉及范围、关键决策 1）采纳：移动端 5 项底栏 `.im-shell-bottomtab` 自适应宽度并将 `.im-shell-unread-badge` 锚定到 `.im-shell-bottomtab-icon`。
- **`R1-R3`**: `accepted` — 已在 `design.md`（涉及范围、关键决策 5）与 `specs/im/web-chat-ux.md` 采纳：`GroupSettings` 成员列表与加人候选同步透传并展示真人 `@username`。

---

## Round 2

### Metadata

- **reviewer**: Independent Gate 2 Design Reviewer (`f2eab8f0-a8e8-479d-b91a-d9da74d298ec`, `change-design-reviewer` + `frontend-experience-review` design mode)
- **target**: `feat-795-people-discovery @ 146486bbb`（对比 `8c0616479..146486bbb`，`/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-795-people-discovery`）
- **review_mode**: `delta`
- **mode_reason**: `8c0616479..146486bbb` 为针对 Round 1 问题的有界设计修订（仅修改 `design.md`、`specs/im/agents-nodes.md`、`specs/im/web-chat-ux.md` 并追加 `Author Resolutions`），核心需求范围、跨包边界、共享存储 schema 与单里程碑拓扑未变，适用 `delta` 复审全部变更段落、波及装配点与历史问题闭环。
- **started_at**: `2026-11-26T18:42:10+09:00`
- **completed_at**: `2026-11-26T18:45:10+09:00`
- **duration**: `3m 00s`

### Verdict

- **Verdict**: `Approved`
- **Counts**: `0 CRITICAL / 0 WARNING / 1 Recommendation`

---

### Coverage 与证据

- **`retained_from: Round 1`（保留未变部分的既有证据）**：
  - 跨包依赖红线（不触碰 DSH runtime / `packages/personal-assistant`）、Agent Context 零影响、无一次性数据库迁移（无需 `deployment-prompt.md`）、`POST /im/v1/conversations` 幂等 1:1 建连、`apps/desktop/src/host_server.rs:2202` SPA 回退兼容性、`src/IM/ios/NanoIM/Client/CommonModels.swift` 可选字段向后兼容性，以及 `change-code-review` + `frontend-experience-review` 审查能力组合均在 `8c0616479..146486bbb` 中保持不变，沿用 Round 1 已核实的判断与代码证据。
- **本轮变更与波及范围核查（`8c0616479..146486bbb`）**：
  1. **服务端路由与联系人接口（`design.md:13-15,79,96-97,104-120`）**：
     - `apps/im-server/src/server.ts` SPA 白名单正则明确扩展为 `/^\/(chat|tasks|people|settings|bind\/confirm|login|register|membership|onboarding|me)(\/|$)/` 并维持 `Cache-Control: no-store`，与 canonical `docs/specs/im/web-chat-ux.md:60`（HTML 入口 `no-store`）一致。
     - `apps/im-server/src/contacts.ts` 在保留既有 `visible()` 租户/个人空间隔离与公开 PA 节点隐藏的前提下，为 `kind === "human"` 投影 `username`（`q` 支持 `@username` 归一匹配），并为 `kind === "agent"` 通过 `owners` 表（按 `users.owner_id` 索引）补齐 `owner_user_id`（`users.id`）与 `owner_display_name` 回退，闭合了 `contacts.ts` → 前端归属聚合 → `POST /im/v1/conversations`（要求 `users.id`）的数据流。
  2. **前端体验与交互状态边界（`design.md:16-22,78-98,157`）**：
     - `/people` 目录、移动端 5 项底栏角标锚定、活跃团队成员不被 `FirstUseWelcome` 遮挡侧栏、侧栏 `⌘K/Ctrl+K` 焦点保护与 `!searchActive && !distillMode && filter === "direct-user"` 状态隔离、站内非外部 1:1 去重键、外部代记发送者双重排除（`!conversation?.external_source && !message.sender.avatar_id?.startsWith("external:")`）、公开 PA vs 专业数字员工点击分流、`PersonPopover` `z-index: 110` 与防穿透关闭、双正文 `@mention` 渲染（排除 `replyPreview`）及保留草稿/附件的 `insertMention` 均已落入对应组件职责，无新增交互冲突。
  3. **Delta-specs 锚点与条款回归检查（`specs/im/agents-nodes.md`、`specs/im/web-chat-ux.md`）**：
     - 对照 canonical `docs/specs/im/agents-nodes.md:819-833` 与 `docs/specs/im/web-chat-ux.md:28-45,542-581` 逐段复核：所有 `### Requirement:` 标题与既有仍适用 Scenario（含非当年消息年份、窄屏搜索恢复、卡片初始视图搜索、移动端具体会话隐藏底栏、私聊/群聊减少重复身份信息、群聊轻量标题栏、中英文切换保留未发送草稿）完整保留；`NewChatModal` 与 `NewGroupModal` 拆分后既满足 `spec.md:86-88` 的跨团队归属与分类筛选，又保护了公开 PA 不暴露 `node_id` 的隐私契约，不会误伤合法实现。
  4. **Runbook 与 Milestone M1（`design.md:169,181`）**：
     - Runbook 健康检查已修正为真实存在的 `$IM_URL/health`，保留用户待测隔离真栈的约束清晰；M1 `范围` 与 `退出标准` 已完整覆盖 `server.ts`、`contacts.ts`、前后端测试与构建门禁。

---

### 历史问题闭环

- **`R1-C1`**（Author Resolution: `accepted`）：已在 `design.md:14,79,106,181` 与 `specs/im/web-chat-ux.md:60` 纳入 `apps/im-server/src/server.ts` SPA 白名单放行 `people` 及服务端路由测试 — **`closed`**。
- **`R1-C2`**（Author Resolution: `accepted`）：已在 `design.md:21,92,157,181` 与 `specs/im/web-chat-ux.md:60` 明确同时排除 `conversation?.external_source` 与 `message.sender.avatar_id?.startsWith("external:")` 的外部未映射代记发送者 — **`closed`**。
- **`R1-C3`**（Author Resolution: `accepted`）：已在 `design.md:13,15,22,93,97,117,120` 与 `specs/im/agents-nodes.md:14` 补齐 `contacts.ts` 的 `owner_user_id`（`users.id`）解析、`owner_display_name` 回退及 `AgentProfilePage` 全量 `listContacts("")` 可见真人校验 — **`closed`**。
- **`R1-W1`**（Author Resolution: `accepted`）：已在 `design.md:21,87-88,181` 与 `specs/im/web-chat-ux.md:60` 限定 `FirstUseWelcome` 仅用于 `membership_status !== "active"`，保证活跃团队成员始终可见 `ConversationSidebar` — **`closed`**。
- **`R1-W2`**（Author Resolution: `accepted`）：已在 `design.md:17,22,93,181`、`specs/im/agents-nodes.md:14` 与 `specs/im/web-chat-ux.md:60` 明确点击同事公开 PA 直接发起 1:1 会话（且非本人 PA 资料页隐藏 `Work` Tab 与空设备行）、点击专业数字员工进入 `/settings/agents/:agentId` — **`closed`**。
- **`R1-W3`**（Author Resolution: `accepted`）：已在 `design.md:18,21,94,181` 与 `specs/im/web-chat-ux.md:59-60` 明确 `PersonPopover` `z-index: 110` 及防穿透关闭、双正文渲染路径（排除 `replyPreview`）与保留草稿/附件追加 `draftMentions` 的 `insertMention` — **`closed`**。
- **`R1-W4`**（Author Resolution: `accepted`）：已在 `specs/im/web-chat-ux.md:38-46,59` 拆分为 `新建聊天分类筛选并区分真人同事与跨团队 Agent` 与 `新建群聊选择真人同事与本人候选 Agent`，并补齐桌面主导航 `Chat、People、Tasks、Agents` — **`closed`**。
- **`R1-W5`**（Author Resolution: `accepted`）：已在 `design.md:19,84,88,169` 与 `specs/im/web-chat-ux.md:8-9,60` 明确侧栏状态互斥、站内非外部 1:1 按 `user_id`/`agent_id` 去重及 Runbook `$IM_URL/health` 检查端点 — **`closed`**。
- **`R1-R1` ~ `R1-R3`**（Author Resolution: `accepted`）：次级安静按钮权重与状态区分（`design.md:17,79`）、移动端 5 项底栏未读角标锚定（`design.md:16,81`）与 `GroupSettings` `@username` 透传（`design.md:20,97`、`specs/im/web-chat-ux.md:45`）均已妥善融入 — **`closed`**。

---

### Issues

无（`0 CRITICAL / 0 WARNING`）。

---

### Recommendations

- **`R2-R1` — 实施细节顺手对齐 PA 分支的 `owner_display_name` 与 `AgentProfilePage` 本人归属判定**
  - 在落地 `apps/im-server/src/contacts.ts:30-46` 时，`SELECT` `owners` 行顺带取出 `id, display_name`，将 `owner_display_name: row.owner_display_name ?? owner?.display_name` 与 `owner_user_id: owner?.id` 同时写入 `if (binding_id)`（公开 PA）和普通公司 Agent 两个返回分支；并在 `src/IM/frontend/src/features/settings/agents/agent-profile-page.tsx` 判定“是否为本人管理的 Agent”（如第 50、85、88、132 行）时统一使用 `(agent.owner_user_id ?? agent.owner_id) === self`，让 `users.owner_id !== users.id` 的历史账号在查看本人与同事 Agent 时同样零偏差。
