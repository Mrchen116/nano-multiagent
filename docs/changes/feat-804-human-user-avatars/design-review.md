# Design Review: feat-804-human-user-avatars

## Round 1

- **reviewer**: Independent Gate 2 Design Reviewer (`change-design-reviewer` + `frontend-experience-review` + `agent-context-review`)
- **target**: `docs/changes/feat-804-human-user-avatars/{spec.md,design.md,prototype.html,specs/im/{spec,auth-tenancy,web-chat-ux,ios-client}.md,M1-human-user-avatars/}`
- **commit**: `7580c9c9b` (`unit/feat-804-human-user-avatars`)
- **review_mode**: `full`
- **mode_reason**: 首轮独立 Gate 2 设计审查，尚无既有审查基线；按规范对现状断言、架构与关键决策、安全与多租户边界、Agent Context 影响、前端原型体验、delta-spec 锚点与场景完整性及 Milestone / Runbook 安排执行全量核查。
- **started_at**: `2026-11-27T21:23:30+09:00`
- **completed_at**: `2026-11-27T21:43:30+09:00`
- **duration**: `20m`

### Verdict

**Issues Found** — `3 CRITICAL / 4 WARNING / 2 Recommendations`

设计整体方向合理：以 `users.avatar_version` 作为跨端缓存与失效真源、在服务端统一经 `sharp` 归一化为 `256×256` 静态去元数据 WebP、复用现有受保护二进制拉取 + 单飞内存缓存模式、保持真人圆形照片/首字母圆章与 Agent 几何剪影的清晰区分，符合 `SPEC.md` 跨包边界与 `docs/product/web-im-principles.md` 体验原则。

但对照冻结代码 `7580c9c9b` 逐链路核查后，存在 **3 项阻塞实施正确性的 CRITICAL 问题**（`server.ts` 全局鉴权门禁与 Fastify 解析器冲突、`projectMessage` 动态注入 `avatar_version` 破坏 PA 授权证据哈希/观察重放并泄漏进多条模型上下文、iOS SQLite `actors` 表与实时事件消费链丢失 `avatar_version`）以及 **4 项导致局部功能失灵或并发竞态的 WARNING 问题**，需在进入实施前修订收口。

---

### Coverage 与证据

#### 1. 现状断言核查（Current-State Assertions）

- **数据层与中心服务**：已核实 `apps/im-server/src/schema.sql:4-25` 与 `db.ts:132-277` 中 `users` 表当前无头像字段；`identity-routes.ts:103-147` 仅有 `GET/PATCH /im/v1/account`；`contacts.ts`、`message-records.ts`、`messaging.ts`、`personal-images.ts`（已使用 `sharp(..., { animated: false, limitInputPixels: 4096 * 4096 })`）及 `gateway.ts` `publishUserEvent` 现状与 `design.md` 基本一致。
- **遗漏或失真的现状事实**：
  1. `apps/im-server/src/server.ts:75-77, 113-131, 157-165` 存在根级 `bodyLimit: 2 MiB` 以及对非白名单 `/im/v1/*` 路由强制 `requireActive = true` 的全局 `preHandler`/`onSend` 门禁，直接影响新增头像端点的请求体解析与 `200`/`404` 契约（见 `R1-C1`）。
  2. `src/IM/ios/NanoIM/Storage/ChatRepository.swift:158-161, 991-995, 1171-1177` 会将同步与列表响应写入 SQLite `actors` 表后再重读投影回内存，当前 `actors` 表无 `avatar_version` 列（见 `R1-C3`）。
  3. `design.md` L18、L189、L221 断言 `src/IM/frontend/src/features/me/me-page.tsx` “仍硬编码紫色首字母圆块，未接入共享 `<Avatar>`” 与事实不符——`me-page.tsx:58` 已接入 `<Avatar id={user?.id ?? ""} size={62} />`（真正仍硬编码首字母圆块的是 iOS `SettingsCompanyView.swift:71-75`，见 `R1-W2`）。

#### 2. 架构判断、职责归属与关键决策核查（Architecture & Key Decisions）

- **跨包红线与模块复用**：变更集中在 `packages/product-contracts`、`apps/im-server`、`packages/personal-assistant` 与 `src/IM/{frontend,ios}`；未越界引入 DSH 非公开依赖，未让 PA/Channels/IM 直接耦合运行时内部实现；Desktop 客户端复用 `apps/desktop/src/host_server.rs:288, 535` 既有的 `/im/{*path}` 与 `/im/ws/user` 同源反代（且 `apps/desktop/tauri.conf.json:13` 未限制 `blob:` 图片），无需新增 Rust 端点，复用判断成立。
- **关键决策风险**：
  - 决策 1（固定 `${uploadDir}/avatars/${userId}.webp` 覆盖写 + 递增 `avatar_version`）：异步 `sharp` 转码位于 SQLite 事务外，并发 `PUT`/`DELETE` 存在写盘与版本号竞态（见 `R1-W3`）。
  - 决策 2（受保护二进制读取 + 按版本缓存）：服务端钩子会提前把非活跃账号变成 `403`（见 `R1-C1`）。
  - 决策 5（在 `projectMessage` 动态解析 `sender.avatar_version` 与 `reply_to.sender.avatar_version`）：破坏了中心服务将 `messaging.message(id)` 同时用作人类展示 DTO 与 PA 安全哈希/观察幂等输入的不变量（见 `R1-C2`）。

#### 3. 用户约束与安全/多租户边界（User Constraints & Security Boundaries）

- 逐项核对 `spec.md` 与 `docs/specs/im/auth-tenancy.md`：
  - 头像 URL 不拼 query token、不走公开静态目录，Web 走 `authFetch` + `ObjectURL`、iOS 走 `client.protectedResource` + 内存缓存并在退出/切服/401 时清空，满足隐私与分区清理契约（`docs/specs/im/ios-client.md:119-143`）。
  - 跨空间、无共享会话、目标为 Agent/外部身份、`avatar_version === 0` 或磁盘文件缺失时统一返回 `404 avatar not found` 的反枚举设计正确，但受 `server.ts` 全局门禁影响在 `!accountEnabled(viewer)` 分支尚未闭合（见 `R1-C1`）。
  - 头像文件不计入 1 GiB/10 GiB 聊天附件配额但仍受 5 MiB 单次输入、`4096×4096` 像素上限、静态帧校验、EXIF/ICC 剥离与认证写限流约束，安全边界清晰。

#### 4. Agent Context 专项审查（`agent-context-review` 设计模式）

- **可见消费者盘点**：已完整追踪本仓全部模型与独立审查入口：
  1. Global / 普通 Agent 工具返回：`packages/personal-assistant/src/tool-references.ts`（`conversations`、`read_messages`、`search_messages`、`send_message`、`send_user_message`、`task_graph`）与 `inbox.ts`（`inbox`）。
  2. SingleThread 会话输入与审批转录：`packages/personal-assistant/src/global-agent.ts:624` -> `packages/dsh-integration/src/policy/sources.ts:88-92, 123, 227`。
  3. Personal Agent 主模型与独立安全审查模型（`pa.review`）：`apps/im-server/src/personal-agent.ts:208-218, 351`、`personal-actions.ts:252`、`global-agent.ts:840-845, 952` -> `packages/dsh-integration/src/personal-security.ts:84, 211-215, 317` 及 `packages/dsh-integration/src/index.ts:1157-1175`。
- **审查结论**：`design.md` 识别到了“零视觉噪音泄漏”目标并提供了实施后检查点（L199-203, L273），但实际剥离点覆盖不全，漏掉了 `task_graph`（`tool-references.ts:544` 并无身份遍历出口）、SingleThread `source.sender`、`pa.input.context` / `pa.action.prepare` 进入的 `pa.review` 独立审查模型，且动态修改 `reply_to.sender` 直接破坏了 PA `authorization_guard` 与 `InboxStore.acceptRelay` 哈希稳定性（见 `R1-C2`）。系统提示词与缓存前缀本身未新增动态块。

#### 5. 前端体验与原型专项审查（`frontend-experience-review` 设计模式）

- **原型必要性与聚焦度**：本次新增账号页头像管理行、圆形裁剪弹窗及全站人机身份同场呈现，提供单文件可交互 `prototype.html` 必要且恰当；顶部演示条可通过 `?clean=1` 隐藏，`must-match` / `may-adapt` / `out-of-scope` 边界明确。
- **视觉层次与自解释性（基于 `01`–`06` 渲染图及源码核验）**：
  - 账号页将“个人头像直存/移除”置于“个人身份”首行，与下方“显示名称 + 放弃修改/保存账号”操作区视觉分离清楚；错误横幅（`04-account-error-and-draft-1120x780.png`）原地说明原因且保留已生效头像与未提交名称草稿。
  - 群聊混排场景（`03`、`03b`）中，真人圆形照片、未设头像同事的柔和色首字母圆章、PA 与专业数字员工的无框几何剪影以及方形圆角群头像层次分明，符合 *Let the UI speak for itself*。
- **体验缺口**：缺少 `390×844` 手机视口下裁剪弹窗的门禁核验证据，底部三按钮在窄屏/英文文案下存在挤压风险，且未明确超限像素（`> 4096px`）的前端预检与关闭弹窗释放 `ObjectURL` 细节（见 `R1-W4`）。

#### 6. Delta-Spec 锚点、`MODIFIED` 场景完整性与文档门禁

- 已逐一比对 `docs/changes/feat-804-human-user-avatars/specs/im/{spec,auth-tenancy,web-chat-ux,ios-client}.md` 与 `docs/specs/im/` 长青契约：
  - `specs/im/spec.md` 将 `Auth and Tenancy` Requirement 计数由 `16` 增至 `17`，`Web Chat UX`（`38`）与 `iOS Client`（`20`）计数保持一致。
  - `auth-tenancy.md`、`web-chat-ux.md`、`ios-client.md` 中所有 `MODIFIED` Requirement 标题均精确命中现有长青标题，且完整保留了原契约下的全部既有 Scenario（`auth-tenancy` 1+2 个、`web-chat-ux` 原 5 个 + 新增 1 个、`ios-client` 3+3 个），无遗漏删除。
  - 需随 `R1-C1`–`R1-C3` 的设计修订保持 delta-spec 表述一致（归并细节建议见 `R1-R2`）。

#### 7. Milestone 拆分、审查安排与 `Runbook for Reviewer`

- 单里程碑 `M1-human-user-avatars` 在同一原子交付内闭合服务端存储/鉴权、Agent Context 隔离、Web/Desktop 与 iOS 客户端，避免半成品中间态，拆分粒度合理。
- `本次审查安排` 纳入 `change-code-review`、`agent-context-review`、`frontend-experience-review` 与 `product-journey-review`，`Runbook for Reviewer` 给出了隔离 worktree 启动与多视口/鉴权/Context 复核步骤；补齐下述 Issues 后即可直接指导实施与独立验收。

---

### 历史问题闭环

首轮审查（Round 1），无历史遗留问题。

---

### Issues

#### `R1-C1` [CRITICAL] `server.ts` 全局活跃账号门禁与根级 Fastify 解析器/请求体上限会阻断头像读写端点契约

- **位置**：
  - `docs/changes/feat-804-human-user-avatars/design.md`：`核心改动文件`（L12-13）、`接口与数据流 -> 1. 服务端存储、校验与鉴权契约`（L129-145）、`Milestones -> M1`（L247, L270）
  - `docs/changes/feat-804-human-user-avatars/specs/im/auth-tenancy.md`：`Requirement: 真人账号可管理受保护的自定义静态图片头像`（L9, L23-25）
- **证据**：
  1. `apps/im-server/src/server.ts:113-131`（`preHandler`）与 `157-165`（`onSend`）对除 `publicIdentity`（仅含 `/im/v1/auth/*` 与 `/im/v1/public/install`）、`/im/v1/node-update/report`、`/im/v1/device-binding/*` 及 `workSync` 外的全部 `/im/v1/*` 路由调用 `ctx.messaging.principal(req)`（`apps/im-server/src/messaging.ts:73-77`），默认执行 `ctx.identity.authenticateRequest(req, true)`（`apps/im-server/src/identity.ts:404-410`）。当请求者为已停用账号或尚未启用个人空间的待审批账号（`!accountEnabled(viewer)`）时，全局钩子会在进入路由处理函数前直接抛出 `403 { code: "company_membership_required" }`，`onSend` 也会对 `< 400` 响应再次拦截。
  2. `apps/im-server/src/server.ts:75-77` 将根级 Fastify `bodyLimit` 设为 `2 * 1024 * 1024`（2 MiB），且流式二进制 Content-Type 解析器仅封装在 `media.ts` 子插件内（仓库亦未引入 `@fastify/multipart`）。`design.md` 计划在 `identity-routes.ts` 直接注册 `PUT /im/v1/account/avatar` 接收最高 **5 MiB** 的 `multipart/form-data` 或 `image/{png,jpeg,webp}`，但未声明独立封装的二进制/multipart 解析器与路由级请求体上限。
- **未修后果**：
  1. `GET /im/v1/users/:user_id/avatar` 在分支 `(2)`（`pending`/`suspended` 账号读取本人头像应返回 `200`）与分支 `(3)`（`!accountEnabled(viewer)` 请求他人头像应返回 `404 avatar not found` 防枚举）都会被 `server.ts` 提前变成 `403`，直接违背 `specs/im/auth-tenancy.md` 与 `M1` `[reviewer] #3`（且若误传 Gateway Bearer token，`principal(req)` 还会放行网关身份而非强制人类会话）。
  2. `PUT /im/v1/account/avatar` 上传 `image/*` 或 `multipart/form-data` 会触发 `415 FST_ERR_CTP_INVALID_MEDIA_TYPE`，2 MiB–5 MiB 的合法图片也会被全局 2 MiB `bodyLimit` 截断报错。
  - **收口方向**：在 `server.ts` 的 `preHandler` 与 `onSend` 中为 `GET /im/v1/users/:user_id/avatar` 显式放行（如路由 `config` 标记交由路由自身调用 `authenticateRequest(req, false)` 鉴权），并为 `PUT /im/v1/account/avatar` 明确独立封装的原始图片流/multipart 解析方案及 5 MiB 超限读取控制（类似 `media.ts` 的有界流读取而不依赖未安装的第三方插件）。

#### `R1-C2` [CRITICAL] `projectMessage` 动态注入 `avatar_version` 会破坏 PA 授权证据哈希与观察重放幂等，且多条模型上下文链路存在视觉字段泄漏

- **位置**：
  - `docs/changes/feat-804-human-user-avatars/design.md`：`现状分析`（L30）、`关键决策 5`（L116）、`接口与数据流 -> 2. 统一身份版本投影与实时同步`（L158-160）、`接口与数据流 -> 6. Agent Context 零泄漏门禁`（L199-203）
- **证据**：
  1. **PA 外发授权 `409 owner_authorization_changed` 误触发**：`PersonalAgents.authorizationGuard`（`apps/im-server/src/personal-agent.ts:382-389`）对主人直聊所有历史消息计算 `JSON.stringify(this.messageEvidence(b, message))` 的 SHA-256 哈希，在 `PersonalActions.validate`（`apps/im-server/src/personal-actions.ts:139`）比对 `prepared.authorization_guard`。`messageEvidence`（`personal-agent.ts:208-218`）调用 `this.ctx.messaging.message(message.id)` 并将 `reply_to: original.reply_to` 原样纳入哈希对象。若按 `design.md` L158 在 `projectMessage`（`apps/im-server/src/message-records.ts:301-334`）中将历史消息 `reply_to.sender` 动态覆写为最新 `users.avatar_version`，只要主人曾在直聊中引用过任一真人，任何被引用人（或主人）在 `pa.action.prepare` 与 `pa.action.commit` 之间改/删头像，都会改变历史消息证据哈希，导致 PA 外发动作误报 `409 owner_authorization_changed`。
  2. **PA 观察恢复 `Relay input identity conflict` 卡死**：`PersonalAgents.observations`（`personal-agent.ts:351`）读取 `this.ctx.messaging.message(e.message_id)`，经 `GlobalAgent.recoverPersonalObservations`（`packages/personal-assistant/src/global-agent.ts:840-845`）将 `sender: message.sender`、`reply_to: message.reply_to` 传入 `InboxStore.acceptRelay`（`packages/personal-assistant/src/inbox.ts:347, 370`）。当某条观察已入箱但 `pa.observations.ack` 完成前重试时，`inbox.ts:370` 比对 `identity(prevInput) !== identity(input)`（对整条 `value.message` 做 JSON 哈希）；期间发言人或被引用人更新 `avatar_version` 会直接抛出 `Error('Relay input identity conflict')`，使观察批次恢复持续中断。
  3. **模型与独立安全审查 Context 泄漏**：
     - `TaskGraphService.identity`（`apps/im-server/src/task-graphs.ts:454-458`）同时服务于人类 HTTP 请求与 Gateway Agent 工具请求；`design.md` L201 声称在 `packages/personal-assistant/src/tool-references.ts` 的“任务图身份投影出口”剥离 `avatar_version`，但 `tool-references.ts:544` 对 `task_graph` 只做顶层游标清洗，完全没有遍历 `list/focus/nodes/get` 中的 `created_by` / `assignee` / `updated_by_actor`。
     - SingleThread 会话输入（`global-agent.ts:624` 直接提交 `payload.sender`，随后进入 `packages/dsh-integration/src/policy/sources.ts:88-92, 123, 227` 审批模型转录）以及 PA 独立安全审查 `pa.review`（`personal-agent.ts:215` 的 `pa.input.context` `sender`、`personal-actions.ts:252` 的 `pa.action.prepare` `payload.reply_to.sender` -> `packages/dsh-integration/src/personal-security.ts:84, 211-215, 317`）均不经过 `tool-references.ts` 或 `inbox.ts` 的 `actor()` 过滤，会把 `avatar_version`（及既有 `avatar_variant`）送入审查 LLM 上下文。
- **未修后果**：真人日常更换头像会无故打断 PA 待提交动作（`409`）或锁死未确认的 PA 观察恢复流，且 `avatar_version` 会泄漏进 `task_graph` 工具输出、SingleThread 审批转录与 `pa.review` 独立审查上下文，违背 `spec.md` 的 Agent Context 零泄漏约束。
  - **收口方向**：将 `avatar_version` 严格限制在**面向人类客户端的投影边界**（例如：① `TaskGraphService` 仅在 `actor.kind === 'user'` 时附加视觉字段，同时在 `tool-references.ts` 兜底；② 保持内部 `messaging.message()` / `relay_tasks` / `pa.input.context` / `pa.action.prepare` / `pa.observations` 的 `sender` 与 `reply_to.sender` 不附带动态 `avatar_version`，仅在面向浏览器/iOS 的 HTTP 响应出口与浏览器 `user_events` 载荷附加，或在 `messageEvidence`、`observations`、`prepare`、`global-agent.ts` 入口统一剥离视觉字段；同时前端/iOS 对引用回复本身已可通过 `sender.id` 从会话/联系人目录取最新 `avatar_version`，无需改写内部证据快照）。

#### `R1-C3` [CRITICAL] iOS 本地 SQLite `actors` 表与 `user.profile_updated` 消费链遗漏 `avatar_version`，导致冷启动与同步后会话头像丢失且无法实时刷新

- **位置**：
  - `docs/changes/feat-804-human-user-avatars/design.md`：`核心改动文件`（L24-28）、`接口与数据流 -> 5. iOS 原生查看与缓存生命周期`（L191-197）、`Milestones -> M1`（L249）
  - `docs/changes/feat-804-human-user-avatars/specs/im/ios-client.md`：`Requirement: iOS 独立客户端保持 IM 业务与权限契约`（L18-24）
- **证据**：
  1. **SQLite `actors` 表落库裁剪**：iOS 的 `ChatStore.conversations` 始终由 `ChatRepository` 落库后再经 `Self.loadConversations(db)` 重读生成（见 `src/IM/ios/NanoIM/Features/Chat/ChatStore.swift:695-704` 与冷启动 `loadSeed` `L336-352`）。当前 `src/IM/ios/NanoIM/Storage/ChatRepository.swift` 的 `actors` 表仅有 `v5_actor_portrait` 迁移列 `role` 与 `avatar_variant`（`L158-161`），`INSERT INTO actors(...)`（`L991-995`）与 `loadConversations` 的 `SELECT`（`L1171-1177`）均未持久化或读取 `avatar_version`，`design.md` 也未把 `ChatRepository.swift` 纳入改动文件。因此 `/im/v1/sync` 与 `/im/v1/conversations` 返回的 `participants[].avatar_version` 落盘重投影后全部丢失为 `nil`（仅持久化在 `messages.payload_json` 中的单条消息 JSON 保留发送时快照）。
  2. **`user.profile_updated` 实时刷新断链**：服务端 `user.profile_updated` 事件不含 `conversation_id`。在 `ChatStore.consume(_ event: UserEvent)`（`ChatStore.swift:1109-1139`）中，该事件仅触发 `needsList = true` -> `loadConversations()`，既不会重新拉取 `client.contacts()` 更新 `RootTabs.avatarContacts`（`NanoIMApp.swift:335-337` 仅在切前台时拉取一次），也不会在 `user_id == user.id` 时调用 `client.session.updateUser()` / `accountUpdated()` 刷新 `RootTabs.user` 与 `MeView`，亦不会刷新当前打开会话的 `timelines[selectedID]` 或驱逐 `IMClient` 内存头像缓存中的旧版本条目。
- **未修后果**：iOS 冷启动首绘、非通讯录群成员/已停用同事的会话头像一律退化为首字母圆章；App 在线期间同事或本人在其他设备更换/移除头像后，`avatarContacts`、`MeView` 与当前打开会话均不会实时更新。
  - **收口方向**：在 `ChatRepository.swift` 新增轻量 schema 迁移（如 `v9_actor_avatar_version`：`ALTER TABLE actors ADD COLUMN avatar_version INTEGER`）并贯通 `actors` 读写；明确 iOS 收到 `user.profile_updated` 时按 `user_id` 驱逐旧版内存头像缓存、刷新 `client.contacts()`（或原位 patch `avatarContacts` 的 `display_name`/`avatar_version`）、当 `user_id == user.id` 时同步 `session.updateUser()`，并在当前选中会话涉及该用户时刷新详情/时间线。

#### `R1-W1` [WARNING] Web/Desktop 实时 `user.profile_updated` 监听挂载范围与 Query 失效集合不完整

- **位置**：
  - `docs/changes/feat-804-human-user-avatars/design.md`：`接口与数据流 -> 2`（L157）、`接口与数据流 -> 4`（L189）
  - `docs/changes/feat-804-human-user-avatars/specs/im/web-chat-ux.md`（L19-23）
- **证据**：
  1. `design.md` L189 将 `user.profile_updated` 消费放在 `src/IM/frontend/src/features/chat/chat-workspace-page.tsx`。当用户位于 `/people`、`/tasks`、`/settings/company`、`/settings/account` 或移动端 `/me` 时，`ChatWorkspacePage` 未挂载，只有全局 hook `src/IM/frontend/src/features/chat/use-membership-cache.ts:12-83` 常驻监听 `subscribeUserStream`。
  2. 在已打开会话中，`activeConversation` 取自 `["chat", "conversation-detail", conversationId, selfUserId]`（`chat-workspace-page.tsx:386`），非联系人/已停用前同事的历史气泡、引用头与已读回执取自 `["chat", "messages", conversationId]` 及 `["chat", "thread", conversationId]`；且当 `event.payload.user_id === selfUserId`（同账号另一设备改头像/改名）时，顶栏个人菜单与 `/me` 依赖 `useAuthStore` 的 `user`（最高优先级 `self`），`/settings/account` 依赖 `["settings", "account"]`。`design.md` L189 仅失效 `["contacts"]`、`["chat", "conversations"]` 与 `["company", "members"]`，遗漏了上述缓存与 `authStore` 同步。
- **未修后果**：用户在通讯录、任务、团队成员、账号或「我的」页面停留时无法实时收到头像变更；聊天页中已停用同事的历史气泡以及本人在另一端刚换的顶栏头像会保持旧状态。
  - **收口方向**：将全局 Query/Auth 失效逻辑收拢到常驻的 `useMembershipCache`（或同级应用壳层订阅），覆盖 `["contacts"]`、`["chat", "conversations"]`、`["chat", "conversation-detail"]`、`["company", "members"]`、`["task-graphs"]`、按需 `["personal-agent"]`，在 `user_id === selfUserId` 时同步更新 `useAuthStore` `user` 与 `["settings", "account"]`，并在 `ChatWorkspacePage` 对当前活跃会话补刷 `["chat", "messages", activeId]` / `["chat", "thread", activeId]`。

#### `R1-W2` [WARNING] Web `<AvatarIdentities>` 优先级覆盖、iOS 团队成员/PA 管理页身份透传缺口及 `me-page.tsx` 现状断言偏差

- **位置**：
  - `docs/changes/feat-804-human-user-avatars/design.md`：`现状分析`（L18-28）、`接口与数据流 -> 4`（L182-189）、`接口与数据流 -> 5`（L191-196）
- **证据**：
  1. **Web `source="names"` 优先级被外层吞没**：`src/IM/frontend/src/features/chat/components/avatar.tsx:66` 中 `SOURCE_PRIORITY` 为 `{ names: 0, history: 1, members: 2, contacts: 3 }`。`actor-profile-popover.tsx:107` 与 `task-wait.tsx:143, 200, 241` 均使用 `source="names"`；当它们在 `ChatWorkspacePage`（外层 `source="members"`，`L1422`）或 `MessagePane`（外层 `source="history"`，`L1379`）内部挂载（例如群任务面板 `GroupTaskPanel` 或消息区弹出的 `ActorProfilePopover`）时，内层携带最新 `avatar_version` 的 `actor` 因优先级 `0 < 1 < 2` 无法覆盖外层旧值或缺省值。此外 `src/IM/frontend/src/features/chat/contacts-api.ts:24-26` 的 `contactActor(contact)` 仅返回 `{ type, id }`，丢弃了 `display_name`、`role`、`avatar_variant` 与 `avatar_version`。
  2. **iOS `SettingsCompanyView`、`Contact.actor` 与 PA 管理页不一致**：
     - `src/IM/ios/NanoIM/Features/Me/SettingsCompanyView.swift:71` 中的 `pending` / `suspended` 成员不在 `contacts` 或 `conversations` 内，`RootTabs.avatarDirectory` 无其条目；若仅按 `design.md` L27 传入 `.userID(member.id)`，这些成员会显示 `"?"` 且丢失 `member.avatar_version`。
     - `src/IM/ios/NanoIM/Client/CommonModels.swift:32` 的 `Contact.actor` 未透传 `display_name`、`user_id`、`role`、`avatar_variant` 与 `avatar_version`。
     - `design.md` L159 在服务端为 PA `incidents` 与 `blocked-contacts` 增加了 `actor_id` / `avatar_version` 并更新了 Web 组件（L189），但未同步处理或说明 iOS 对等页面 `src/IM/ios/NanoIM/Features/Agents/PersonalAgentManagementView.swift:50-64, 201-241`。
  3. **`me-page.tsx` 现状描述失真**：`src/IM/frontend/src/features/me/me-page.tsx:58` 已使用 `<Avatar id={user?.id ?? ""} size={62} />`，无需再做“替换硬编码圆块”改造。
- **未修后果**：聊天内打开群任务或成员卡片时头像版本可能回退；iOS 团队管理页中的待审批和已停用成员头像退化为 `"?"` 且无法显示已上传照片；Web 与 iOS 的 PA 风险事件/受限联系人身份展示不一致。
  - **收口方向**：在 `avatar.tsx` 合并逻辑中允许高新鲜度字段（如非空 `avatarVersion`）补充或调高显式单对象卡片的 `source` 优先级，补齐 Web `contactActor` 与 iOS `Contact.actor` 字段；在 iOS `AvatarIdentity` 增加 `.member(SettingsMember)` 构造入口并明确 `PersonalAgentManagementView.swift` 的头像对齐方案；修正 `design.md` 对 `me-page.tsx` 的失真描述。

#### `R1-W3` [WARNING] 同一账号并发 `PUT / DELETE /im/v1/account/avatar` 存在磁盘文件与 `avatar_version` 失步竞态

- **位置**：
  - `docs/changes/feat-804-human-user-avatars/design.md`：`关键决策 1`（L112）、`接口与数据流 -> 1. 服务端存储、校验与鉴权契约`（L131-136）
- **证据**：
  - `design.md` 采用单文件固定路径 `${uploadDir}/avatars/${userId}.webp` 配合 `users.avatar_version` 递增；`PUT` 需先完成异步 `sharp` 解码重编码与文件 `rename`，再更新 SQLite `avatar_version = avatar_version + 1`，而 `DELETE` 直接置 `avatar_version = 0` 并 `unlink` 同一路径。
  - 若同一用户触发并发请求（例如弱网重试上传的同时点击“移除头像”，或连续两次更换头像且第一次大图 `sharp` 转码更慢），先完成的 `DELETE`（`avatar_version = 0`）或新 `PUT` 会被后完成的旧 `PUT` 覆盖 `${userId}.webp` 并递增 `avatar_version`，导致已移除头像“复活”或最新 `avatar_version` 实际对应旧图片字节（且客户端按 `userId:avatarVersion` 缓存后整次会话不会自愈）。
- **未修后果**：快速重传或“上传中移除”场景下出现数据库版本号与磁盘文件内容错位，用户看到已删除或过期的旧头像。
  - **收口方向**：在中心服务（单 worker 进程，见 `server.ts:62-66`）按 `userId` 增加进程内串行互斥队列（per-user mutex），或在写盘前读取起始 `expectedVersion`、先写 `${userId}.${tmpId}.webp` 并在 `UPDATE users SET avatar_version = ? WHERE id = ? AND avatar_version = ?` CAS 成功后原子 `rename` 到目标路径（CAS 失败则清理临时文件并拒绝覆盖；或者直接按 `${userId}.${nextVersion}.webp` 存储并清理旧版本文件）。

#### `R1-W4` [WARNING] 原型缺少移动端裁剪弹窗（`390×844`）门禁渲染核验，且未闭合超限像素预检与裁剪弹窗资源释放契约

- **位置**：
  - `docs/changes/feat-804-human-user-avatars/design.md`：`接口与数据流 -> 3`（L171-180）、`前端原型与体验契约`（L204-230）
  - `docs/changes/feat-804-human-user-avatars/prototype.html`（L671-766, L1076-1109, L1387-1408）
- **证据**：
  1. 按 `docs/development/frontend-experience.md` 与 `frontend-experience-review` 门禁，新增核心交互须覆盖桌面与 `390×844` 手机视口。当前证据集仅包含桌面裁剪图（`02-crop-modal-1120x780.png`）与手机账号/我的静态页（`05`、`06`），未核验 `390×844` 下的圆形裁剪弹窗；`prototype.html:1101-1107` 的弹窗底栏在一行内左右并排放置“重新选图…”、“取消”、“保存头像”三枚按钮且未配置窄屏折行，在 `390px` 尤其是英文界面（`"Choose another…"` / `"Cancel"` / `"Save avatar"`）下容易横向挤压。
  2. 服务端限制输入像素不超过 `4096×4096`（`design.md` L131），但前端选图校验（`design.md` L173 与 `prototype.html:1390`）仅检查 MIME 与 `<= 5 MiB`，未说明当用户选择 `<= 5 MiB` 但边长 `> 4096px` 的图片时（或前端 Canvas 直接导出 `512×512` 后再上传时）究竟上传裁剪后结果还是原图：按 `design.md` L176 浏览器实际上传的是 `512×512` 裁剪 PNG/WebP Blob（天然满足 `<= 4096×4096`），但若超大原图在浏览器解码阶段超限或 iOS `PhotosPicker` 原图过大时的降采样上限未写清，易导致大图解码卡顿或 `415` 误报；同时 `prototype.html:1407` 创建 `ObjectURL` 后未在关闭/换图时 `revokeObjectURL`，也未绑定 `Escape` 关闭弹窗。
- **未修后果**：手机窄视口下裁剪弹窗底栏按钮在双语文案下易拥挤折行；超大尺寸低体积照片在 Web/iOS 选图裁剪时可能出现内存峰值或前后端报错语义不一致。
  - **收口方向**：补齐 `390×844` 裁剪弹窗视口核验并在 `must-match` / `may-adapt` 明确窄屏底栏按钮排布与 `Escape`/焦点管理；在 `design.md` 明确 Web/iOS 选图解码阶段的最大边长预缩放保护（例如解码后超过 `4096px` 先等比缩放到安全工作画布再进入 `512×512` 裁剪导出）以及 `ObjectURL` 在换图/关闭时的立即回收。

---

### Recommendations

#### `R1-R1` 原型手机端 `/me` 背景卡片副标题建议对齐真实 `@username` 展示

- `prototype.html:1052` 在手机端「我的」演示卡片中渲染了内部 ID `u_linxia_01`，而当前真实代码 `src/IM/frontend/src/features/me/me-page.tsx:60` 与 iOS `MeView.swift:57` 均展示 `@${username}`（符合不暴露内部 `u_...` ID 的产品规范）。虽属原型背景区，顺手改为 `@linxia` 可避免实施阶段误解。

#### `R1-R2` Delta-Spec 归并链接提醒与任务表面文字对齐

- `docs/changes/feat-804-human-user-avatars/specs/im/web-chat-ux.md:7` 为适配 `docs/changes/` 目录深度使用了 `[Agent 身份头像](../../../../specs/im/agents-nodes.md#...)`，后续归并回 `docs/specs/im/web-chat-ux.md` 时需恢复同目录相对路径 `agents-nodes.md#...` 以通过 `scripts/docs_check.py`。
- `design.md` L159、L189 已将任务图（`task-graphs.ts` / `task-wait.tsx` / iOS `TaskActorLabel`）纳入真人自定义头像展示范围，可顺手在 `specs/im/web-chat-ux.md:20` 的统一展示枚举中补充“任务创建者与负责人”，使契约枚举与设计表面完全同构。


---

### Author Resolutions

- **`R1-C1`**: `accepted` — 已在 `design.md`（§现状分析、§关键决策 2、§接口与数据流 1、§Milestones）收口：在 `apps/im-server/src/server.ts` 的 `preHandler` 与 `onSend` 中为 `GET /im/v1/users/:user_id/avatar` 显式识别 `config: { selfManagedAuth: true }` 跳过默认 `messaging.principal(req)`，交由路由自身执行 `identity.authenticateRequest(req, false)`（未登录与 Gateway 令牌返回 `401`、待审/已停用真人读自身头像返回 `200`、`!accountEnabled(viewer)` 读他人返回防枚举 `404`）；并将 `PUT /im/v1/me/avatar` 封装在独立子插件内注册 `removeAllContentTypeParsers()` + 原始流解析器（设路由 `bodyLimit: 6 MiB` 并在流读取层精确执行 `5 MiB` -> `413 avatar_too_large` 截断，无需引入 `@fastify/multipart`）。
- **`R1-C2`**: `accepted` — 已在 `design.md`（§关键决策 3、§接口与数据流 2 & 5、§Milestones）彻底重构身份版本注入边界：保持内部 `MessageRecords.projectMessage`、`messaging.message()`、`messaging.actor()`、`enqueueRelays`、`syncTaskContext`、`PersonalAgents.{messageEvidence,compactMessageEvidence,observations}`、`PersonalActions.prepare` 与 Gateway 鉴权的 `TaskGraphService` **不含 `avatar_version`**，由新增纯函数模块 `human-avatar-projection.ts` 仅在 `principal.kind !== 'gateway'` 的人类客户端 HTTP 响应出口与 `Gateway.broadcast` 人类 `user-stream` 帧出口批量附着最新 `avatar_version: string | null`，同时在 `packages/personal-assistant/src/tool-references.ts` 的 `result()` 出口保留递归剥离函数作为纵深防御，确保 PA `authorizationGuard` SHA-256、`InboxStore.acceptRelay` 观察重放幂等哈希、SingleThread 审批转录、`pa.review` 与 `task_graph` 工具输出 100% 字节级不变。
- **`R1-C3`**: `accepted` — 已将 `src/IM/ios/NanoIM/Storage/ChatRepository.swift` 与 `ChatStore.swift` 完整纳入 `design.md`（§现状分析、§关键决策 5、§接口与数据流 4、§Milestones）：新增 GRDB 迁移 `v9_actor_avatar_version`（`ALTER TABLE actors ADD COLUMN avatar_version TEXT`）贯通 `upsertConversation` 与 `loadConversations`；在 `ChatStore.consume` 无游标事件分支处理 `user.profile_updated`，同步驱逐 `AvatarImageStore` 旧缓存、更新本地 `actors` 表与活跃会话时间线、通知 `RootTabs` 更新 `avatarContacts`，并在 `uid == user.id` 时触发 `accountUpdated()` 刷新 `Session` 持久化的 `AuthUser` 与 `MeView`。
- **`R1-W1`**: `accepted` — 已在 `design.md`（§接口与数据流 3、§Milestones）将 Web/Desktop 的 `user.profile_updated` 监听收拢至应用壳层常驻的 `src/IM/frontend/src/features/chat/use-membership-cache.ts`，覆盖 `AvatarBlobStore` 驱逐、同账号跨设备 `useAuthStore.replaceUser` + `["settings", "account"]` 刷新，以及 `["contacts"]`、`["chat", "conversations"]`、`["chat", "conversation-detail"]`、`["chat", "messages"]`、`["chat", "thread"]`、`["company", "members"]`、`["task-graphs"]` 与 `["personal-agent"]` 的按需失效。
- **`R1-W2`**: `accepted` — 已在 `design.md`（§现状分析、§接口与数据流 3 & 4、§现有 UX grounding）修正对 `me-page.tsx:58` 的现状描述（该页已接入 `<Avatar id={user?.id ?? ""} size={62} />`）；明确服务端人类出口显式返回 `avatar_version: string | null`，令 `IdentityDirectory.get` 在高优先级记录 `avatar_version === undefined`（名称占位 stub）时合并低优先级显式传入的 `avatar_version`，而对权威 `null`/字符串保持高优先级胜出；补全 Web `contactActor` 与 iOS `Contact.actor` 字段透传；为 iOS 新增 `AvatarIdentity.member(SettingsMember)` 与 `PersonalAgentManagementView.swift` 风险事件/受限联系人头像对齐。
- **`R1-W3`**: `accepted` — 已在 `design.md`（§关键决策 1、§接口与数据流 1、§风险与回退、§Milestones）增加单进程内按 `user.id` 的串行互斥队列 `perUserAvatarLock(uid)`，使同一账号的并发 `PUT` 与 `DELETE /im/v1/me/avatar` 严格串行化落盘（独立 `<uuid>` 文件名 + 事务更新新随机 `avatar_version` 后清理旧文件），杜绝旧图覆盖新版本或已删头像复活。
- **`R1-W4`**: `accepted` — 已更新 `prototype.html` 与 `design.md`（§关键决策 4、§接口与数据流 3 & 4、§前端原型）：客户端选图解码后对边长 `> 2048px` 的高像素原图先等比降采样至安全工作画布再导出 `512×512` 裁剪图像上传，换图/关闭立即调用 `URL.revokeObjectURL` 并支持 `Escape` 关闭与焦点归还；补齐并视觉核验了 `390×844` 手机窄视口下的中英文裁剪弹窗渲染图（`07-mobile-crop-modal-zh-390x844.png`、`08-mobile-crop-modal-en-390x844.png`），底栏按钮排布充裕无挤压。
- **`R1-R1`**: `accepted` — 已将 `prototype.html` 手机端 `/me` 演示卡片副标题改为 `@linxia`（已复采 `06-mobile-me-390x720.png`）。
- **`R1-R2`**: `accepted` — 已在 `specs/im/web-chat-ux.md` 的统一展示枚举中补充「任务创建者与负责人」，并在 `design.md` §契约层增量中显式注明阶段 4 归并回 `docs/specs/im/web-chat-ux.md` 时恢复同目录相对链接 `agents-nodes.md`。

---

## Round 2

- **reviewer**: Independent Gate 2 Design Reviewer (`change-design-reviewer` + `frontend-experience-review` + `agent-context-review`)
- **target**: `docs/changes/feat-804-human-user-avatars/{spec.md,design.md,prototype.html,specs/im/{spec,auth-tenancy,web-chat-ux,ios-client}.md,M1-human-user-avatars/}`
- **commit**: `9d2b56296` (`7580c9c9b..9d2b56296`, branch `unit/feat-804-human-user-avatars`)
- **review_mode**: `delta`
- **retained_from**: `Round 1`
- **mode_reason**: 本轮修订针对 Round 1 的 7 项问题与 2 项建议进行了有界架构与交互收口（新增 `human-avatar-projection.ts` 人类出口投影层、`users` 三列与 `avatar_version: string | null` 随机版本方案、`server.ts` `selfManagedAuth` 与子插件流解析、`perUserAvatarLock` 串行互斥、Web `useMembershipCache` 全局失效与 `IdentityDirectory` `undefined`/`null` 合并、iOS `ChatRepository` `v9` 迁移与无游标事件消费、以及 `prototype.html` `390×844` 中英文裁剪弹窗核验）；`spec.md` 需求范围、`specs/im/{spec,auth-tenancy,ios-client}.md` 主体条款、跨包依赖拓扑与单里程碑 `M1` 结构未发生变化，故采用 `delta` 模式重点审查全部变更段落及其波及链路，未受影响部分沿用 Round 1 核查证据。
- **started_at**: `2026-11-27T21:55:07+09:00`
- **completed_at**: `2026-11-27T22:00:30+09:00`
- **duration**: `6m`

### Verdict

**Approved** — `0 CRITICAL / 0 WARNING / 2 Recommendations`

Round 1 提出的 `R1-C1`–`R1-C3`、`R1-W1`–`R1-W4` 与 `R1-R1`–`R1-R2` 已在冻结提交 `9d2b56296` 中全部实质闭环；本轮引入的新机制与改动波及面（`selfManagedAuth`、子插件 `5 MiB` 流读取、`perUserAvatarLock`、`human-avatar-projection.ts`、Web/iOS 状态同步及窄屏双语原型）经对照真实代码逐项复核均严密自洽，无新增阻塞或警告问题，满足进入实施阶段的 Gate 2 准出条件。

---

### Coverage 与证据（`delta`，未变项沿用 `retained_from: Round 1`）

1. **服务端管线、存储互斥与鉴权边界（`design.md` §关键决策 1–2、§接口与数据流 1）**：
   - `server.ts` `preHandler`（`L130`）与 `onSend`（`L164`）复用现有 `workSync` 路由 `config` 模式扩展识别 `selfManagedAuth: true`，使 `GET /im/v1/users/:user_id/avatar` 跳过默认 `messaging.principal(req)`，由路由内部调用 `identity.authenticateRequest(req, false)` + `canReadUserAvatar`，准确兑现未登录/Gateway 令牌 `401`、待审批/已停用真人读自身头像 `200`、`!accountEnabled(viewer)` 读他人头像返回防枚举 `404` 的契约；`PUT/DELETE /im/v1/me/avatar` 路径与现有 `identity-routes.ts:159, 164`（`GET/PATCH /im/v1/me`）及 `specs/im/auth-tenancy.md:10, 15` 完全一致。
   - `PUT /im/v1/me/avatar` 封装在独立 Fastify 子插件内使用 `removeAllContentTypeParsers()` + 通配原始流解析与 `bodyLimit: 6 MiB`（流读取层执行 `5 MiB` -> `413` 硬截断），无需新增第三方依赖即可支持 2–5 MiB 图片上传。
   - `users` 表改用 `(avatar_storage_name, avatar_version, avatar_content_type)` 配合进程内 `perUserAvatarLock(uid)` 串行互斥队列，每次写入独立 `<uuid>` 文件并在事务提交新 12 位 hex `avatar_version` 后删除旧文件，彻底消除了事务外异步 `sharp` 转码导致的并发覆盖与已删头像复活竞态。
2. **人类出口投影与 Agent Context 零污染（`design.md` §关键决策 3、§接口与数据流 2 & 5）**：
   - 内部 `MessageRecords.projectMessage`、`messaging.message()`、`messaging.actor()`、`enqueueRelays`、`syncTaskContext`、`PersonalAgents.{messageEvidence,compactMessageEvidence,observations}`、`PersonalActions.prepare` 与 `TaskGraphService` 保持零改动、不生成 `avatar_version`；新增 `human-avatar-projection.ts`（`attachHumanAvatars`）仅在 `principal.kind !== 'gateway'` 的会话/消息 HTTP 路由、纯人类认证的 `registerTaskGraphRoutes`（已核实 `apps/im-server/src/task-graphs.ts:1646-1653` 仅服务于 `identity.authenticateRequest` 人类调用）及人类实时流出口附着 `avatar_version: string | null`，并对 `type === 'agent'`、`external:*` 与 `sender_source_id != null` 严格跳过。
   - 配合 `packages/personal-assistant/src/tool-references.ts` 的递归 `stripVisualActorFields` 纵深防御，确保 PA `authorizationGuard` SHA-256、`InboxStore.acceptRelay` 观察幂等哈希、SingleThread `sources.ts`、`pa.review`（`personal-security.ts`）与 `task_graph` 工具输出 100% 字节级不变。
3. **Web/Desktop 与 iOS 跨端状态同步及缓存边界（`design.md` §接口与数据流 3 & 4）**：
   - **Web/Desktop**：已核实 `src/IM/frontend/src/realtime/user-stream/{user-stream-runtime,canonical-event}.ts` 原生放行无 `event_id` 的 `user.profile_updated` 帧并分发至常驻 `useMembershipCache`；`IdentityDirectory.get` 区分权威 `null`（已移除头像）与局部 `undefined`（仅名称占位 stub）的合并规则清晰闭合，且已修正 `me-page.tsx:58` 现状断言并补全 `contactActor`。
   - **iOS**：`ChatRepository.swift` 新增 `v9_actor_avatar_version` 迁移贯通 `actors` 表持久化，`ChatStore.consume` 在 `L1109` 游标门禁前消费无游标 `user.profile_updated` 事件驱动内存缓存驱逐、`actors` 表更新、`selectedID` 时间线刷新、`avatarContacts` 更新与本人 `accountUpdated()`；`AvatarIdentity` 新增 `.member` 与 `.incidentActor` 补齐 `SettingsCompanyView`（含 `pending`/`suspended` 成员）与 `PersonalAgentManagementView` 头像渲染，`Session.makeRequest` 显式 `.reloadIgnoringLocalCacheData` 保证受保护头像字节零磁盘落盘。
4. **前端原型多视口与体验复核（`prototype.html`、`06`–`08` 截图、`specs/im/web-chat-ux.md`）**：
   - 已核验新增渲染图 `07-mobile-crop-modal-zh-390x844.png`、`08-mobile-crop-modal-en-390x844.png` 与复采 `06-mobile-me-390x720.png`：`390×844` 窄视口下 `208×208` 圆形取景框比例舒展，中文三按钮单行留白充裕，英文长文案（`Choose another…` / `Cancel` / `Save avatar`）自动折为左次右主两行对齐、无文字截断或拥挤；`prototype.html` 已补齐 `> 2048px` 离屏预降采样、`URL.revokeObjectURL` 即时回收、`Escape` 关闭归还焦点及 `/me` `@linxia` 副标题。
   - `specs/im/web-chat-ux.md:20` 已补入「任务创建者与负责人」，`python3 scripts/docs_check.py` 校验全绿（249 个受管文档、74 条必检路由全部通过）。
5. **未受影响部分沿用说明（`retained_from: Round 1`）**：
   - 跨包依赖边界、Crewden Desktop `host_server.rs` 反代复用、`specs/im/{spec,auth-tenancy,ios-client}.md` 的锚点与既有 Scenario 保留、以及单里程碑 `M1` 与双编组实施后审查安排均未改变，沿用 Round 1 已核实的通过证据。

---

### 历史问题闭环

| Issue ID | Author Resolution | 本轮核查证据 | 状态 |
|---|---|---|---|
| `R1-C1` | `accepted`：`server.ts` 识别 `selfManagedAuth: true`，`PUT /im/v1/me/avatar` 使用独立子插件原始流解析与 `5 MiB` 硬截断 | `design.md` L14, L38, L90-92, L113-129, L302 已明确 `server.ts:130, 164` 放行配置、子插件 `removeAllContentTypeParsers()` + `bodyLimit: 6 MiB` + `5 MiB` 流截断及 `401/200/404` 全分支可见性规则 | **closed** |
| `R1-C2` | `accepted`：内部消息/PA/任务服务不注入 `avatar_version`，改由 `human-avatar-projection.ts` 在人类出口附着 + `tool-references.ts` 递归剥离兜底 | `design.md` L15-16, L94-96, L135-149, L210-217, L302；核对 `task-graphs.ts:1646-1653` 与 PA 证据链路，确认 `authorizationGuard`、`acceptRelay`、SingleThread、`pa.review` 与 `task_graph` 均零变动 | **closed** |
| `R1-C3` | `accepted`：纳入 iOS `ChatRepository.swift` `v9_actor_avatar_version` 迁移与 `ChatStore.consume` 无游标 `user.profile_updated` 消费链 | `design.md` L23-24, L40, L101-102, L196-206, L302 已完整覆盖 SQLite `actors.avatar_version` 读写、`AvatarImageStore` 驱逐、`avatarContacts` 通知、`uid == user.id` 账户刷新及 `selectedID` 刷新 | **closed** |
| `R1-W1` | `accepted`：Web `user.profile_updated` 收拢至全局常驻 `useMembershipCache` 并补齐缓存与 `authStore` 同步 | `design.md` L19, L39, L182-186；核实 `user-stream-runtime.ts` 与 `canonical-event.ts` 支持无游标事件广播至 `useMembershipCache`，失效范围完整覆盖跨路由与同账号跨设备场景 | **closed** |
| `R1-W2` | `accepted`：修正 `me-page.tsx` 现状断言，定义 `IdentityDirectory` `undefined` vs `null` 合并规则，补全 `contactActor`/`Contact.actor` 与 iOS `.member`/PA 页面头像 | `design.md` L18, L24, L178-181, L193-200, L236, L238 已逐项落实，消除了聊天内局部弹层被外层覆盖及 iOS 待审/停用成员显示 `"?"` 的问题 | **closed** |
| `R1-W3` | `accepted`：新增按 `user.id` 的进程内串行互斥锁 `perUserAvatarLock` + 独立 `<uuid>` 存储文件名 | `design.md` L86-88, L120-122, L277, L302 明确同账号 `PUT`/`DELETE` 严格串行化并在事务提交新随机 `avatar_version` 后再清理旧文件 | **closed** |
| `R1-W4` | `accepted`：补齐 `> 2048px` 选图预降采样、`ObjectURL` 及时回收、`Escape` 关闭焦点归还及 `390×844` 中英文裁剪弹窗渲染核验 | `design.md` L98-99, L187-189, L208, L252-257；`prototype.html:768-774, 1394-1499, 1565-1572` 与截图 `07`、`08` 核验无挤压、无溢出 | **closed** |
| `R1-R1` | `accepted`：原型手机 `/me` 副标题改为 `@linxia` | `prototype.html:1059` 与复采截图 `06-mobile-me-390x720.png` 已核实 | **closed** |
| `R1-R2` | `accepted`：`specs/im/web-chat-ux.md` 补入任务创建者与负责人，并在 `design.md` 记录阶段 4 归并相对路径恢复 | `specs/im/web-chat-ux.md:20`、`design.md:271` 已更新，`python3 scripts/docs_check.py` 通过 | **closed** |

---

### Issues

无（`0 CRITICAL / 0 WARNING`）。

---

### Recommendations

#### `R2-R1` 实施细节提示：重连同步与事件重放出口顺手保持身份新鲜度一致

- **iOS 前台断网重连**：在 `NanoIMApp.swift:251-256` 与 `AvatarIdentity.swift:78-81` 中，`AvatarDirectory` 初始化时 `contacts`（`avatarContacts`）会后置覆盖同 ID 的 `conversations` 参与者条目。实施阶段当 `ChatStore.run()` 在断线重连后完成 `GET /im/v1/sync` 时（`ChatStore.swift:591`），建议顺手刷新一次 `client.contacts()`（或将同步到的最新参与者 `display_name`/`avatar_version` 合并进 `avatarContacts`），避免断网窗口内错过的无游标 `user.profile_updated` 被旧内存 `avatarContacts` 覆盖；Web 端的 `useMembershipCache.onRecovery` 亦可顺手 `invalidateQueries({ queryKey: ["contacts"] })`，使停留在 `/people` 时的断线恢复同样即时收敛。
- **服务端事件重放出口**：`Gateway.broadcast`（代码仓属性名为 `this.browsers`，见 `apps/im-server/src/gateway.ts:47, 226`）与断线补帧的 `Gateway.replay`（`gateway.ts:260`）均向人类客户端写出 `op: "event"` 帧，实施 `attachHumanAvatars` 时可顺手在两处统一调用以保持实时帧与重放帧结构完全同构。

#### `R2-R2` 实施细节提示：iOS `ChatRepository` 新增 `v9` 迁移时同步更新 `schema.version` 元数据记录

- `src/IM/ios/NanoIM/Storage/ChatRepository.swift:199` 维护了 `cache_meta('schema.version', '8')` 写入，实施 `v9_actor_avatar_version` 迁移时顺手同步更新该版本号并在迁移单测覆盖从 `v8` 存量库平滑升级即可。


---

### Author Resolutions

- **`R2-R1`**: `accepted` — 作为 M1 实施阶段的精确接线提示保留执行（不修改已通过 Round 2 审查的设计产物以保持冻结一致性）：实施 `M1` 时在服务端 `Gateway.broadcast`（`this.browsers`）与 `Gateway.replay` 两处统一调用 `attachHumanAvatars`，在 Web `useMembershipCache.onRecovery` 同步失效 `["contacts"]`，并在 iOS `ChatStore.run()` 完成断线重连 `GET /im/v1/sync` 后同步刷新/合并 `avatarContacts`。
- **`R2-R2`**: `accepted` — 作为 M1 实施细节保留执行：实施 `ChatRepository.swift` `v9_actor_avatar_version` 迁移时同步将 `cache_meta('schema.version', ...)` 更新为 `'9'` 并在迁移单测中覆盖 `v8 -> v9` 升级校验。

---

## Round 3

- **reviewer**: Independent Gate 2 Design Reviewer (`change-design-reviewer` + `frontend-experience-review` + `agent-context-review`)
- **target**: `docs/changes/feat-804-human-user-avatars/{spec.md,design.md,prototype.html,specs/im/{spec,auth-tenancy,web-chat-ux,ios-client}.md,M1-human-user-avatars/}`
- **commit**: `5c1ad766e` (`fe5e11464..5c1ad766e`, branch `unit/feat-804-human-user-avatars`)
- **review_mode**: `delta`
- **retained_from**: `Round 2`
- **mode_reason**: 本轮由用户明确的体验收敛要求触发（移除引用消息内冗余头像，按商业科技产品克制标准精简界面噪音），有界修订了 `spec.md`、`design.md`、`prototype.html` 与 `specs/im/{web-chat-ux,ios-client}.md`，同时将 Round 2 的 `R2-R1`/`R2-R2` 实施接线建议正式合入 `design.md`；服务端存储互斥、鉴权模型、Agent Context 隔离与单里程碑 `M1` 架构未变，故采用 `delta` 模式重点核查次级结构头像边界、线上真实组件基线对齐、更新后的 2x Retina 多视口截图及跨文档契约一致性，未变部分沿用 Round 1–2 证据。
- **started_at**: `2026-11-27T22:34:10+09:00`
- **completed_at**: `2026-11-27T22:38:30+09:00`
- **duration**: `5m`

### Verdict

**Approved** — `0 CRITICAL / 0 WARNING / 0 Recommendations`

本轮修订准确兑现了用户提出的商业级信息层级克制要求：彻底剥离了消息引用块（`reply_to`）等次级内嵌文本结构的头像渲染与服务端投影，去除了账号页常驻相机贴纸、裁剪弹窗重复预览条与群聊气泡外堆叠小头像串等视觉噪音，并与仓库真实线上组件基线（`.chat-message-quote`、`ReceiptStatusPopover`、`ChatReplyLabel`、`MessageReceiptButton`）完全一致，无新增阻塞或警告问题，满足 Gate 2 准出条件。

---

### Coverage 与证据（`delta`，未变项沿用 `retained_from: Round 2`）

1. **次级结构边界收敛与真实代码基线核实（`spec.md`、`design.md`、`specs/im/{web-chat-ux,ios-client}.md`）**：
   - 对照当前代码仓核实：Web 端 `src/IM/frontend/src/features/chat/components/message-pane.tsx:2456-2467` 的 `.chat-message-quote` 与 iOS 端 `src/IM/ios/NanoIM/Features/Chat/ChatMessageSearch.swift:113-126` 的 `ChatReplyLabel` 原本即为「左强调竖线 + 粗体姓名 + 摘要」纯文本结构（不含头像）；iOS `PersonalAgentManagementView.swift:201-241` 的风险事件与受限联系人原本即为紧凑 `DisclosureGroup` 纯文本行（而 Web 端 `personal-agent-{blocked-contacts,incidents}.tsx` 原本即有 `28px` `<Avatar>` 槽位）。
   - 本轮修订将规则精确收敛为「自定义头像仅赋能既有主身份槽位（`<Avatar>` / `AvatarView`），绝不在消息内引用块（`reply_to`）、输入框待引用预览条、气泡底栏双勾图标、正文 `@` 提及胶囊、系统通知行或紧凑纯文本折叠行中新增或内嵌头像」，并同步从服务端 `human-avatar-projection.ts`（`design.md` L50, L148）移除了对 `reply_to` 的 `avatar_version` 附着，前后端数据流与视觉层级高度统一，全文检索无残留冲突描述。
2. **前端原型商业级减噪与多视口画面核验（`prototype.html` 及 `01`、`02`、`04`、`05`、`07`、`08` 截图）**：
   - **账号页（`01-account-desktop-1120x780.png`）**：移除了遮挡人像且易与右下角在线圆点混淆的常驻相机角标，保留纯净可点击的 `56px` 圆形头像 + 姓名/`@username` + 右侧次级按钮「更换头像」与幽灵按钮「移除」，与下方显示名草稿及底部保存栏层次清爽。
   - **圆形裁剪弹窗（`02` 桌面 `1120×780`、`07` 手机中文 `390×844`、`08` 手机英文 `390×844`）**：移除了重复的 `40px/24px` 小圆预览条与工程感 `1.2×` 倍率数值，聚焦单一圆形取景视口（桌面 `240×240`、窄屏 `208×208`）与简洁的 `−` 滑杆 `+` 控制；底栏「重新选择 / Choose another」与「取消 / Cancel」、「保存 / Save」在 `390×844` 中英文视口下均单行舒展排布、无挤压截断。
   - **群聊混排、纯文本引用与按需回执浮层（`04-chat-mixed-popover-1160x780.png`、`05-chat-receipt-popover-1160x780.png`）**：移除了顶栏说明胶囊与气泡下方堆叠头像串，将演示台词替换为真实研发协作对话（符合 *Let the UI speak for itself*）；发出消息内的引用块呈现干净的左竖线 + 粗体姓名 + 单行摘要（无内嵌头像），气泡底栏还原与线上 `message-pane.tsx:2090-2120, 2505-2507` 及 `ChatMessageView.swift:221-266` 一致的轻量双勾 `✓✓` 触发器与按需展开的 `24px` 头像已读回执浮层。
3. **契约完整性与文档门禁**：
   - `specs/im/web-chat-ux.md`（L19-22）与 `specs/im/ios-client.md`（L27）已同步更新次级结构无头像约束，且完整保留原契约全部既有 Scenario；`design.md` 的 `must-match` / `may-adapt` 对齐表、审查编组、Runbook 与 `M1` 退出标准已全部同步；`python3 scripts/docs_check.py` 校验通过（249 个受管文档、74 条必检路由零错误）。
4. **未受影响部分沿用说明（`retained_from: Round 2`）**：
   - 服务端 `server.ts` `selfManagedAuth`、子插件 `5 MiB` 原始流读取、`perUserAvatarLock` 串行互斥、Agent Context 零污染机制、Web/Desktop 与 iOS 内存图像缓存及退出清理语义均未改变，沿用 Round 1–2 已核实的通过证据。

---

### 历史问题闭环

| Item ID | Author Resolution | 本轮核查证据 | 状态 |
|---|---|---|---|
| `R2-R1` | `accepted` 并合入 `design.md` 正文：`Gateway.broadcast`（`this.browsers`）与 `Gateway.replay` 统一附着主身份 `avatar_version`，Web `useMembershipCache.onRecovery` 失效 `["contacts"]`，iOS `ChatStore.run()` 重连同步后刷新/合并 `avatarContacts` | `design.md` L50, L148, L186, L206, L303 已正式写入正文与 `M1` `[worker]` 测试退出标准 | **closed** |
| `R2-R2` | `accepted` 并合入 `design.md` 正文：iOS `ChatRepository.swift` `v9_actor_avatar_version` 迁移同步更新 `cache_meta('schema.version', ...)` 为 `'9'` | `design.md` L197, L303 已正式写入正文与 `M1` `[worker]` 迁移单测标准 | **closed** |

---

### Issues

无（`0 CRITICAL / 0 WARNING`）。

---

### Recommendations

无。
