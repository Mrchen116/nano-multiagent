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
