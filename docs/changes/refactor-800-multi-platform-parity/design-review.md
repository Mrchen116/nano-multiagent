# refactor-800: 五端体验与行为一致性防漏体系 — 技术设计审查报告

## Round 1

### Metadata

- **reviewer target**:
  - Unit: `docs/changes/refactor-800-multi-platform-parity/`
  - Branch / Commit: `unit/refactor-800-multi-platform-parity` @ `d11e6c1db`（基线 `origin/develop` @ `3b4c0f022`）
  - 受审产物：`motivation.md`、`design.md`、`specs/im/web-chat-ux.md`、`specs/im/ios-client.md`、`specs/im/desktop-client.md`、`M1-platform-parity-foundation/.gitkeep`
- **review_mode**: `full`
- **mode_reason**: 本轮为 Gate 2 首轮独立技术设计审查，尚无既有 `design-review.md` 基线，须对现状断言、关键决策、用户澄清约束、delta-spec 锚点与完备性、性能/带宽与本机直连不变量以及 Milestone 退出标准执行全量核实。
- **started_at**: `2026-11-27T17:47:40+09:00`
- **completed_at**: `2026-11-27T18:06:15+09:00`
- **duration**: `18m 35s`

### Verdict

- **结论**: **Issues Found**
- **统计**: `2 CRITICAL / 4 WARNING / 2 Recommendation`

---

### Coverage 与证据

#### 1. 现状断言与生产组装入口核实

对照受审 worktree 真实生产组装入口逐项核实 `motivation.md` 与 `design.md` 的现状判断：

- **包边界与运行时红线（已核实成立）**：对照 `SPEC.md`、`tests/contract/test_runtime_dependency_contract.py:18-92` 与 `packages/product-contracts/package.json`，`@nano/product-contracts` 零外部运行时依赖；`apps/im-server`、`src/IM/frontend`、`apps/node` 已依赖 `@nano/product-contracts`，而 iOS（`src/IM/ios`）与 Desktop Rust（`apps/desktop`）确系手写协议镜像，扩展 `test_runtime_dependency_contract.py` 仅放行 `src/IM/shared/*.json` 静态测试向量不触碰 DSH 或跨包可执行代码边界。
- **四处跨端行为漂移断言（大体成立，但有两处关键细节与真实代码偏差）**：
  1. *Work 待决权限*：`apps/im-server/src/work.ts:294-298` `notifyUpdated()` 确实只广播 `{ agent_id, revision }`；但 `apps/desktop/src/notifications.rs:1040-1090,1441-1465` 在缺少 `status`/`main_execution` 时并非完全静默失效，而是对**每一帧** `agent.work.updated` 触发 `ensure_agent_owned_by_session`（`GET /im/v1/agents`）与 `enrich_work_updated_payload`（`GET /im/v1/agents/:id/work?view=summary&catalog=separate&limit=1`）HTTP 反查；同时 `main_execution` 并非 `agent_profiles` 表字段，而是由 `agent_work_sessions` + `agent_work_turns` 结合 `gateway.isOnline(node)` 推导（`apps/im-server/src/work-records.ts:10,828-830`、`work.ts:154`）——详见 `R1-W1`。
  2. *飞书/微信外部渠道镜像消息*：`apps/im-server/src/messaging.ts:502,644,691` 确实以 `sender = owner_id` 写入外部会话消息，导致 Desktop `notifications.rs:483` 与 iOS `ChatStore.swift:1120` 因 `sender_user_id == self_user_id` 丢弃提醒；但生产代码同时将 **owner 本人在飞书/微信发出的镜像消息**也存为 `sender_user_id = owner_id`（通过 `owner_direct_agent_messages` / `agent_channels.owner_open_id|owner_user_id` 区分，`packages/personal-assistant/src/external.ts:346,1220-1241`、`apps/im-server/src/schema.sql:562-581`），且 `apps/im-server/src/message-records.ts:390-395` 因 `user_id != sender`（`sender == owner_id`）从不递增 owner 的 `unread_count`——详见 `R1-C1`。
  3. *静音与全局未读角标*：Desktop `notifications.rs:1357-1363` 排除 `is_muted` 会话，iOS `NanoIMApp.swift:31` 直接累加全部会话 `unread_count` 且 `ChatStore.swift:1126` 直接拦截全部 `isMuted` 会话（未放行 `@提及`）；Web `app-shell.tsx:68-145` 不仅未排除 `is_muted`，还在桌面端视口（`!isMobile`）禁用了未读查询、在移动端把 `totalUnread` 同时挂在了 `聊天` 和 `我` 两个 Tab 上；且 `im-server` 从未发出 `notifications.rs:1325` 监听的 `conversation.read` / `conversation.preference_updated` 事件——详见 `R1-C2`、`R1-W2`。
  4. *时间线分隔与裸字符串枚举*：Web `src/IM/frontend/src/features/chat/components/message-pane.tsx:2878-2916` 确用宿主时区 `toDateString()`，iOS `ChatModels.swift:361-379` 用注入 `Calendar`；`TaskPresentation.swift:4-55` 与 `AgentLifecycleView.swift:71-83` 确对共享状态使用裸 `String` + `default:`。
- **可复用底座核实（成立但有两处接线冲突需修正）**：
  - `scripts/generate-ios-interactive.ts`（`--check` 零漂移校验）、`scripts/check_change_unit_archived.py`（活跃与 `archive/` unit 定位）、`NanoIM.xcodeproj`（`NanoIMTests` 与 `NanoIMUITests` 已独立为两个 native target，`project.pbxproj:304-377`）均真实存在可复用；
  - `scripts/docs_check.py` 当前无五端矩阵检查，且 `docs/changes/` 下确有 13 份历史未归档活跃 `design.md` 草稿，白名单增量启用策略合理；
  - 但 `packages/product-contracts/src/index.ts` 已通配导出同名生命周期与协作范围类型，按 `design.md:13,166-179` 直接重导出会触发 `TS2308` 编译错误（详见 `R1-W4`）。

#### 2. 关键决策、模块边界与性能/带宽专项审查（含 `performance-review` 视角）

- **架构分层方向正确**：将跨端一致性拆为「本仓设计/PR 门禁 → `@nano/product-contracts` 跨语言生成 + 业务无 `default:` 穷尽 → `im-server` 轻量控制面提示 + 本地纯函数黄金测试向量 → CI 快慢分层」四层，模块职责总体深且正交，避免了在 Swift/Rust 内嵌 JS 运行时或把重数据收归中心服务。
- **数据面本地直连不变量核实**：`apps/desktop/src/host_server.rs:1364-1495` 与 `apps/node/src/local-bridge.ts:185-235` 通过本机 Unix Domain Socket / Windows Named Pipe 直读 >16MB 原生轨迹与执行工作区文件定位，主设计未将该路径迁回 `im-server`；但 `design.md:232` 抽离 `resolveLocalIpcEndpoint` 时漏掉了与 `apps/desktop/src/config.rs:293-312` 的字节级地址推导对等约束（详见 `R1-W4`）。
- **控制面查询与带宽代价核查（`performance-review`）**：
  - 高频过程帧（`message.delta`、`thinking.segment`、`tool_call.*`、`reply_process.*`、`run.heartbeat`）$O(1)$ 跳过不附带 `notification_hint`，单条完成态提示约 `150~250B`，不会增加流式带宽压力；
  - `Gateway.replay` 上限确为 `MAX_REPLAY = 2000`（`apps/im-server/src/gateway.ts:19`），对非通知事件提前过滤并按 `Set<conversationId>` 批量预取可将回放额外 SQL 控制在常数次；
  - **但存在两处真实性能缺口**（`R1-W1`）：① `gateway.ts:219-225` 现存 `broadcast` 循环内对每个接收者逐次查 SQLite 且直接序列化共享 `frame` 引用，若不一并改造为按 `uniqueUserIds` 批量预取并克隆组装 per-user 帧，既达不到“固定常数次查询”，又会污染共享 `frame.data`；② 若非 `waiting_permission` 的 `agent.work.updated` 不下发显式 `notification_hint: { eligible: false }`（或 `main_execution`），Desktop `notifications.rs:1046` 仍会对每次 Work 更新发起 HTTP `GET /work` 反查。
- **远端 CI 关键路径耗时核查（`performance-review`）**：
  - 静态检查（`<5s`）、`check:client-contracts`（`<3s`）与 `platform-conformance.test.ts`（`<10s`）挂载在现有并行 Job 内，确可隐藏在 ~11 分钟的 Linux `backend` 时间窗中；
  - 拆分普通 PR 的二次 `Release device archive`（约 288s）方向正确，但遗漏了 `ci.yml` 的 `push.branches` 未覆盖 `develop`、普通 iOS 代码 PR 分两次跑 `unit-test` + `ui-test` 的重复构建启动损耗，以及 `desktop-candidate.yml` 在 Windows 上与 `build-desktop-windows.ps1:49` 重复执行 `cargo test`（详见 `R1-W3`）。

#### 3. 用户澄清约束核查（Q0–Q4）

| 澄清项 | 设计落点 | 核查结果 |
|---|---|---|
| **Q0** 控制面与数据面分离，不增加中心流式带宽，不回退 Desktop 本机轨迹直连 | `design.md:26,77-78,107-111,157-160` | 方向符合；需补齐 `resolveLocalIpcEndpoint` 与 `apps/desktop/src/config.rs:294` 的地址对等约束（`R1-W4`）及 `Work` 非权限更新抑制 HTTP 反查（`R1-W1`）。 |
| **Q1** 新增多端快检零增时 + 拆开 iOS 快检与近 5 分钟重复 Release 打包；不强绑 11.5 分钟 Linux `backend` 分片 | `design.md:12,37,120-127` | 符合范围；需修补 `develop` 分支 `push` 归档触发与避免双跑 `xcodebuild test` / Windows `cargo test`（`R1-W3`）。 |
| **Q2** 全套防漏底座 + 高频重灾区先行闭环，不一次性重写全仓存量页面 | `design.md:13-19,101-119` | 符合渐进收敛策略；但先行闭环内的通知/未读重灾区自身存在范围前后矛盾与协议盲区（`R1-C1`、`R1-C2`、`R1-W2`）。 |
| **Q3** Linux 沿用后台 Node + Web IM 边界，不新建 Linux 桌面安装包或新系统自启 | `design.md:20,92,229-234,252` | 完全符合。 |
| **Q4** 完全不修改外部通用独立库 `dev-workflow-skills`，门禁全部落在本仓 | `design.md:11,25,96-99,235-237` | 完全符合。 |

#### 4. 契约层增量（delta-spec）与配套产物核查

- **目标锚点与既有 Scenario 保留性**：
  - `specs/im/web-chat-ux.md` 精确匹配 `docs/specs/im/web-chat-ux.md:451` 的 `### Requirement: Web 应用内新消息提醒按会话类型标识来源`，保留了全部 4 个既有 Scenario 并新增 `全局入口未读汇总排除静音会话`；
  - `specs/im/ios-client.md` 精确匹配 `docs/specs/im/ios-client.md:258` 的 `### Requirement: 前台提醒与后台限制明确`，保留了全部 2 个既有 Scenario；
  - `specs/im/desktop-client.md` 精确匹配 `docs/specs/im/desktop-client.md:30` 的 `### Requirement: Desktop 主窗口保持既有 IM 业务权限、原生通知直达与按服务及账号隔离`，保留了全部 2 个既有 Scenario；
  - `docs/specs/gateway/service-lifecycle.md` 确无需 delta-spec；本 unit 无生产部署配置变更（无需 `deployment-prompt.md`），无新增独立视觉页面或复杂交互流（按 `frontend-experience-review` 规范无需 `prototype.html`）。
- **完备性缺陷**：`specs/im/web-chat-ux.md` 与 `specs/im/ios-client.md` 对 `permission_pending`、`work_waiting_permission` 及点击直达话题/Work 的约定与 `motivation.md:101-104`、`design.md:284` M1 退出标准不一致（详见 `R1-C2`）。

#### 5. Milestones、`本次审查安排` 与 Runbook 核查

- 单 Milestone `M1-platform-parity-foundation` 拆分粒度与本 unit 内聚底座定位匹配，`M1-platform-parity-foundation/.gitkeep` 已就位，Runbook 命令与模拟器资源回收要求明确；
- 但 M1 `[reviewer]` ① 的跨端一致性断言因 `R1-C1`、`R1-C2`、`R1-W2` 当前无法在实现阶段自洽达成，须先在设计层收口。

---

### 历史问题闭环

无（本轮为 Round 1 初审）。

---

### Issues

#### `R1-C1` [CRITICAL] 外部渠道镜像消息未区分“对端入站”与“owner 本人外发镜像”，且服务端 `unread_count` 对外部入站消息恒不递增

- **位置**：
  - `docs/changes/refactor-800-multi-platform-parity/design.md:16,107-111,148-155,284`
  - `docs/changes/refactor-800-multi-platform-parity/motivation.md:101-104`
  - `docs/changes/refactor-800-multi-platform-parity/specs/im/web-chat-ux.md:5,8`、`specs/im/ios-client.md:7`、`specs/im/desktop-client.md:8`
- **证据**：
  1. **Owner 外发与外部对端入站在 `messages` 表同为 `sender_user_id = ownerId`**：在 `packages/personal-assistant/src/external.ts:346,1220-1241`、`apps/im-server/src/schema.sql:562-581`（`owner_direct_agent_messages` 表）及 `apps/im-server/src/messaging.ts:502,644,691` 中，飞书/微信镜像会话不仅将外部对端入站消息写为 `sender_user_id = ownerId, sender_type = 'user'`，**账号 owner 本人在飞书/微信发出的消息**（飞书 `sender_source_id === channel.owner_open_id`、微信 `sender_source_id === channel.owner_user_id`，持久化为 `sender_display_name: '你'` 并登记 `owner_direct_agent_messages`）同样以 `sender_user_id = ownerId, sender_type = 'user'` 落库广播。三份 delta-spec 均明确限定仅对“**入站对端消息**”触发提醒，但 `design.md:107` 仅凭会话级 `external_source` 放行，未排除 owner 本人外发镜像消息。
  2. **服务端 `conversation_participants.unread_count` 对外部入站消息恒为 `0`**：`apps/im-server/src/message-records.ts:390-395` 执行 `UPDATE conversation_participants SET unread_count = unread_count + 1 WHERE conversation_id = ? AND user_id != ?` 时传入 `sender = owner_id`。由于外部镜像会话中人类参与者的 `user_id` 就是 `owner_id`，SQLite 中该会话对 owner 的 `unread_count` **永远为 `0`**（`GET /im/v1/conversations` 与 `GET /im/v1/sync` 恒返回 `0`）。而 iOS `ChatRepository.swift:621-663`（收到事件后重拉服务端会话投影）与 Desktop `notifications.rs:1347-1363`（以服务端同步快照 + 非本人增量为准）及 Web 重新拉取会话列表后均依赖服务端 `unread_count`。
- **未修后果**：
  1. 用户本人在微信/飞书每发一条消息，自己的 Web、Desktop 系统原生通知与 iOS 前台横幅都会误弹“`你: ...`”的自发自收提醒；
  2. 外部对端发来真实消息时，服务端 `unread_count` 保持 `0`，iOS/Desktop/Web 的会话未读数与全局未读总角标全部漏计，无法满足 `motivation.md:104` 与 M1 `[reviewer]` ①。
  - *收敛方向*：在 `im-server` 写入与投射外部镜像消息时明确区分“owner 外发镜像”（命中 `owner_direct_agent_messages` 或匹配绑定渠道 `owner_open_id` / `owner_user_id`）与“外部对端入站”——前者 `eligible: false` 且不计未读，后者 `eligible: true` 且在 `message-records.ts` 递增 owner 参与者的 `unread_count`。

#### `R1-C2` [CRITICAL] 跨端提醒范围在 `motivation.md`/M1 退出标准与端侧设计及 delta-spec 之间前后矛盾，且 `NotificationProjector` 缺少对 `im-server` 双事件/残缺载荷的精确状态表

- **位置**：
  - `docs/changes/refactor-800-multi-platform-parity/motivation.md:99-105`
  - `docs/changes/refactor-800-multi-platform-parity/design.md:106-112,144-156,180-209,249-251,284`
  - `docs/changes/refactor-800-multi-platform-parity/specs/im/web-chat-ux.md:3-26`、`specs/im/ios-client.md:3-13`、`specs/im/desktop-client.md:3-9`
- **证据**：
  1. **三端提醒边界与跳转目标自相矛盾**：`motivation.md:101-104` 要求 Web、Desktop 与 iOS 在“新消息、群话题回复、卡片动作回复、`@提及` 或**待决权限请求**”上保持“是否触发提醒及点击提醒到达的目标位置一致”；`design.md:284` M1 `[reviewer]` ① 明确要求同一事件流（含**本人管理助手 Work `waiting_permission`**）在 **Web、Desktop 与 iOS** 产生一致提醒资格。然而：
     - `specs/im/web-chat-ux.md` 与 `specs/im/ios-client.md` 完全遗漏了会话内 `permission.request`（`permission_pending`）与助手 `agent.work.updated`（`work_waiting_permission`）；
     - Web `use-global-message-toast.ts:249-268` 不处理 `permission.request` / `agent.work.updated`，`in-app-toast.tsx:46` 硬编码跳转 `/chat/${toast.conversationId}`（丢失 `?thread=<root_id>` 且不支持 `/settings/agents/<id>?view=work`）；更严重的是 `use-global-message-toast.ts:261` 在静音过滤**之前**就把全部 `message.completed` 送入 `AgentCompletionNotifier`（`agent-completion-notifier.tsx:102-134`），导致 Web 标签页在后台时**静音会话的 Agent 回复仍会弹出浏览器原生系统通知**且点击丢失 `?thread=`；
     - iOS `ChatStore.swift:1098-1142` 与 `NanoIMApp.swift:317`（`ChatBanner` 仅存 `conversationID`）不消费 `message.completed`、`permission.request`、`agent.work.updated`，点击横幅也无法定位群话题或助手 Work 视图（且因 `im-server` 全仓从不发 `message.sent`，现网 `ChatStore.swift:1120-1121` 忽略 `sender_type == "user" && pa_agent_id == nil` 导致普通真人消息前台横幅也全部失效）。
  2. **`im-server` 真实事件发射契约存在双发与缺字段，`design.md` 未定义确定性投射规则**：
     - 非流式 `Messaging.publishAgent`（`apps/im-server/src/messaging.ts:619-620`）对同一 `message_id` **连发两条事件**：`message.created`（`delivery_status: 'completed'`，含 `sender_*`、`interactive`、`attachments`）+ `message.completed`（`data` 仅含 `{ message_id, content, token_usage: null }`，**无** `sender_*`、`interactive`、`attachments`）；而流式 `ChatStreaming`（`chat-streaming.ts:49,86`）先发空 `message.created`（`delivery_status: 'running'`），完成时发完整 `message.completed`；
     - `WorkerPermissionCards`（`worker-permission-cards.ts:55,65,103`）创建权限卡时连发 `message.created` + `permission.request`，用户批准/拒绝或超时后又发 `permission.resolved` + `message.completed`；
     - `system` 消息（`sender_type: 'system'`）与 PA 本人代发消息（`pa_delegated_messages.authorized_by == viewerUserId`）的 `eligible` 判定未写明；
     - `USER_NOTIFICATION_KINDS`（`design.md:180-187`）定名为 `'permission_pending'` / `'work_waiting_permission'`，与 `apps/desktop/src/notifications.rs:429,572,1643,1656` 现存生产分支及单测断言的 `"chat_permission"` / `"work_permission"` 冲突，违背 `design.md:27,255` 存量单测兼容声明。
- **未修后果**：实施者无法同时满足 M1 退出标准与三份 delta-spec；按当前描述实现会出现 `publishAgent` 重复提醒或卡片摘要丢失、权限卡审批完误弹“回复已就绪”、Web 后台标签页在静音群误弹系统通知、点击提醒落错路由，以及 Rust 存量单测断言破坏。
  - *收敛方向*：① 明确拍板并统一 `motivation.md`、`design.md` 与三份 `specs/im/*.md` 对 `permission_pending` / `work_waiting_permission` 及 `target_route`（含 `?thread=` 与 Work 视图）的三端对齐契约，同时把 Web `AgentCompletionNotifier` 纳入同一 `notification_hint` 静音/关注/路由约束；② 在 `design.md` 补齐按事件类型（流式/非流式 `message.created` vs `message.completed`、权限卡 `create`/`finish`、`system` 消息、PA 本人代发）生成 `eligible`、`kind` 与 `dedupe_key`（如按 `message_id` / `request_id` 跨事件幂等）的精确规则，并对齐或显式迁移 `notifications.rs` 的 `kind` 枚举值。

#### `R1-W1` [WARNING] `Work.notifyUpdated` 与 `Gateway.broadcast` 的控制面性能/去重设计与代码事实存在偏差，遗留 HTTP 反查放大与广播 N+1/串号风险

- **位置**：`docs/changes/refactor-800-multi-platform-parity/design.md:15,26,38,108-113,180-208,244`
- **证据**：
  1. **Desktop 对所有缺少状态的 `agent.work.updated` 发起 HTTP 反查**：`apps/desktop/src/notifications.rs:1040-1090,1441-1465` 在帧内缺少 `status`/`main_execution` 时，会对每一次 `agent.work.updated` 请求 `GET /im/v1/agents/:id/work?view=summary&catalog=separate&limit=1`。若服务端仅在 `waiting_permission` 时附带 `notification_hint`，其余 99% 的 `running`/`completed` Work 更新仍会触发 Desktop HTTP 轮询放大；同时 `main_execution` 须从 `agent_work_sessions`（活跃 `global_main`）+ 最新 `agent_work_turns.execution` + `gateway.isOnline(node)` 读取（`work-records.ts:828-830`、`work.ts:154`），而非 `design.md:109` 所称的“`agent_profiles` 一次主键查询”。
  2. **`work_waiting_permission` 的 `dedupe_key` 未界定**：主会话停留在 `waiting_permission` 期间，子任务每次 `Work.append` 仍会触发 `notifyUpdated`（`revision` 递增）。若 `dedupe_key` 绑 `revision` 会随子事件反复刷屏弹窗，若只绑 `agent_id` 又会吞掉后续新一轮权限审批。
  3. **`Gateway.broadcast` 现存循环内 N+1 查询与共享对象序列化**：`apps/im-server/src/gateway.ts:219-225` 当前在 `for (const b of recipients)` 内逐连接执行 SQLite 查询并直接 `JSON.stringify(frame)`。因 `notification_hint` 含接收者私有字段（`is_muted`、`mentions_viewer`、私聊对端名、本人发送过滤），若不一并重构 `gateway.ts:219-225` 为按 `uniqueUserIds` 批量预取并构造 per-user 帧副本，既无法通过“广播固定常数次 SQL 查询”断言，还会发生共享 `frame.data` 跨用户覆写串号。
- **未修后果**：Agent 运行期间 Desktop 持续发起高频 `/work` HTTP 请求、同一权限等待期重复弹窗或二次权限漏弹、`Gateway.broadcast` 存在 N+1 查询或跨接收者提示串号。
  - *收敛方向*：所有发往 `/im/ws/user` 的 `agent.work.updated` 均附带权威 `notification_hint`（非待决权限或非本人管理时 `eligible: false`），使 Desktop 在见到 `notification_hint` 时直接跳过 `enrich_work_updated_payload` HTTP 反查；以当前待决 turn/permission 标识构造 `dedupe_key`；并在 `Gateway.broadcast` 按 `uniqueUserIds` 批量预取后组装独立下行载荷。

#### `R1-W2` [WARNING] 全局未读总角标缺少“已读/静音变更实时同步（Desktop Rust）”与“Web 桌面导航栏展示”两处闭环

- **位置**：
  - `docs/changes/refactor-800-multi-platform-parity/design.md:17,115-116,218-221,284`
  - `docs/changes/refactor-800-multi-platform-parity/specs/im/web-chat-ux.md:5,16-18`
  - `docs/changes/refactor-800-multi-platform-parity/specs/im/desktop-client.md:8`
- **证据**：
  1. **Desktop Rust 守护进程无法感知纯 Agent 消息已读与静音切换**：`apps/desktop/src/notifications.rs:1325` 监听 `"conversation.updated" | "conversation.preference_updated" | "conversation.read"` 来刷新本地未读与静音表，但这三个事件在 `apps/im-server/src/` 全仓均未实现。当用户调用 `POST /im/v1/conversations/:id/read`（`messaging.ts:1220-1244`，阅读纯 Agent 回复时无人类 `message_receipts` 变更，零 WS 事件发出）或 `PATCH /im/v1/conversations/:id/preferences` 切换会话静音时，Desktop 托盘/Dock/任务栏未读总角标与内存 `muted` 表不会更新；此外流式 `message.completed` 阶段因 `@提及` 新加入话题关注的成员（`message-records.ts:138`）在 `notifications.rs:1347`（仅处理 `message.created`）也会漏计未读。
  2. **Web `app-shell.tsx` 在桌面视口完全不渲染全局未读角标**：`src/IM/frontend/src/app/shell/app-shell.tsx:68-73,90-145` 设置了 `enabled: authed && isMobile`，桌面宽度左侧 `im-shell-rail` 无任何未读角标，而移动端底部导航又在 `聊天` 与 `我`（`shell-me-unread`）重复渲染同一总数，与 `specs/im/web-chat-ux.md:5,16-18` 承诺的“全局导航入口显示的未读总数仅汇总未静音会话”脱节。
- **未修后果**：用户在任一端读完 Agent 消息或静音会话后，Desktop Dock/托盘角标长期卡在旧未读数不归零；Web 桌面端全局导航栏缺失未读总数展示。
  - *收敛方向*：在 `im-server` 的 `markConversationRead` 与 `updateConversationPreferences` 向当前操作用户的 `/im/ws/user` 连接投递轻量用户态同步事件（如 `conversation.read` / `conversation.preference_updated`，携带最新 `unread_count` / `is_muted`），并在 `notifications.rs` 对齐消费；在 Web `app-shell.tsx` 打通桌面 rail 与移动端 `聊天` 入口的统一未静音未读角标。

#### `R1-W3` [WARNING] `check_platform_parity.py` 仅单向检查 `src/IM/ios/**`，且 CI 分层遗漏 `develop` 主干归档触发与双跑测试开销

- **位置**：`docs/changes/refactor-800-multi-platform-parity/design.md:86-93,120-127,236-237`
- **证据**：
  1. **漏端门禁单向盲区**：`design.md:237` 仅在“`src/IM/ios/**` 无改动”时触发检查——若某次 PR 修改了 `packages/product-contracts/src/client-parity.ts`、`src/IM/shared/unread-badge-test-cases.json` 或 `apps/im-server/src/**` 并改了 iOS，却**漏改 `apps/desktop/**` 或 `src/IM/frontend/**`**，门禁直接放行；同理，若 `design.md`《五端对齐矩阵》某行声明为 `native-sync`，但 PR 实际未触碰对应端路径，也缺少矩阵声明与 diff 的双向核对。
  2. **`ci.yml` 主干 `push` 未覆盖 `develop`**：`.github/workflows/ci.yml:7-8` 当前仅配置 `push: branches: [main]`，而本仓开发集成与 PR 目标主干为 `develop`（`docs/development/change-workflow.md:11`）。普通 iOS PR 跳过 `Release archive` 后，合入 `develop` 也不会触发 `archive`，真机 Release 归档在日常主干上完全悬空。
  3. **CI 重复测试损耗**：① `design.md:123` 对 `src/IM/ios/NanoIM/**` 改动分两次执行 `build.sh unit-test` + `build.sh ui-test`，不如保留单次 `xcodebuild test -scheme NanoIM`（一次构建启动跑完 `NanoIMTests` + `NanoIMUITests`），仅在纯共享契约/向量变更时跑 `build.sh unit-test`（且须保持 GitHub Job 名 `iOS build and tests` 不变以兼容分支保护）；② `scripts/build-desktop-windows.ps1:49` 已执行 `cargo test`，`design.md:90` 在 `desktop-candidate.yml` 的 Windows 任务再加 `cargo test` 会重复运行一遍 Rust 测试。
- **未修后果**：忘改 Desktop Rust 或 Web 的跨端变更仍会漏过门禁；`develop` 主干长期失去真机 Release 打包保障；iOS 与 Windows CI 产生可避免的重复编译/测试时间。
  - *收敛方向*：将 `check_platform_parity.py` 扩展为按受影响触发集对称核对《五端对齐矩阵》全部受影响端（含双向核验 `native-sync` 行必有对应路径改动）；在 `ci.yml` 将 `develop` 纳入主干 `push`（或 `archive_required` 条件）；合并 iOS 全量测试调用并复用 `build-desktop-windows.ps1` 既有 `cargo test`。

#### `R1-W4` [WARNING] `@nano/product-contracts` 通配重导出存在 `TS2308` 冲突，且 `resolveLocalIpcEndpoint` 缺少与 Desktop Rust 的地址对等保护

- **位置**：`docs/changes/refactor-800-multi-platform-parity/design.md:13,163-179,229-234`
- **证据**：
  1. **`packages/product-contracts/src/index.ts` 重复导出冲突**：`src/index.ts:1-12` 已 `export *` 自 `./agent-lifecycle.js`、`./collaboration.js`、`./task-graphs.js`、`./worker-runtimes.js`（均已导出 `AgentLifecycleDesired`、`AgentLifecycleObserved`、`CollaborationScope`、`TaskStatus`、`TaskMode`、`WorkerRuntime`）。按 `design.md:13,166-178` 在 `client-parity.ts` 重复定义同名类型并在 `index.ts` 执行 `export * from './client-parity.js'` 会直接触发 TypeScript `TS2308` 重复导出编译失败，并造成双源定义。
  2. **本机轨迹 IPC 端点推导跨语言强耦合**：`apps/desktop/src/config.rs:293-312`（`local_node_bridge_endpoint(config_path)`）与 `apps/node/src/local-bridge.ts` 存在严格的字节级对等契约（Windows 基于 `config_str.to_lowercase()` 的 SHA-256 前 24 位构造 `\\.\pipe\crewden-desktop-node-<digest>`；POSIX 以 `<parent>/.desktop-node.sock` UTF-8 字节长 `<= 96` 为界，超长回退 `<TMPDIR || /tmp>/crewden-node-<sha256(config_str)[..20]>.sock`）。`design.md:232` 将其改写为泛化签名 `resolveLocalIpcEndpoint(rootDir: string, pipeKey: string)`，未约束与 `config.rs:294` 的精确对等性及跨语言断言。
- **未修后果**：`pnpm build` / `pnpm typecheck` 编译失败；若 `platform-io.ts` 改变了 IPC 路径哈希输入或 96 字节回退规则，Desktop 本机 >16MB 轨迹直读与打开工作区文件将静默断连回退。
  - *收敛方向*：将 `as const` 枚举元组放回 `product-contracts` 各权威子模块并由 `client-parity.ts` 引用聚合；保持 `localNodeBridgeEndpoint(configPath)` 算法与 `apps/desktop/src/config.rs:294` 字节级一致，并用共享固定输入/输出测试向量在 `platform-conformance.test.ts` 与 Desktop `cargo test` 双端锁死。

---

### Recommendations

- **`R1-R1` 明确 `src/IM/ios/Tests/` 共享黄金向量符号链接机制**：`NanoIM.xcodeproj` 通过 `PBXFileSystemSynchronizedRootGroup`（`project.pbxproj:317-324`）自动收录 `src/IM/ios/Tests/` 下的文件，现有 `avatar-test-cases.json` 依赖受 Git 跟踪的相对符号链接 `src/IM/ios/Tests/avatar-test-cases.json -> ../../shared/avatar-test-cases.json` 打入 `NanoIMTests` bundle。建议在 `design.md` 点明为 `unread-badge-test-cases.json` 与 `timeline-divider-test-cases.json` 创建同名相对符号链接，无需手改 `project.pbxproj`。
- **`R1-R2` 收窄 `test_client_contract_parity.py` 静态禁 `default:` / `_ =>` 的匹配粒度**：同一 Swift/Rust 业务文件中常并存与共享协议无关的本地 UI 状态或错误分支 `switch`/`match`。建议限定仅对匹配生成协议枚举类型/变体前缀的 `switch`/`match` 块禁止 `default:` 与 `_ =>`，避免全文无差别正则误伤普通本地控制流。

---

### Author Resolutions (Round 1)

- **`R1-C1`**: `accepted` — 已在 `design.md`（§现状分析、关键决策 3、§接口与数据流 2）与三份 `specs/im/*.md` 补齐区分外部渠道“对端入站”与“owner 本人外发镜像”的统一谓词 `isExternalOwnerMirrorMessage`（核验 `owner_direct_agent_messages` 及绑定 `agent_channels` 的 `owner_open_id` / `owner_user_id`）：owner 外发镜像 `eligible: false` 且不计未读；对端入站消息 `eligible: true` 且在 `message-records.ts` 与 `threads.ts` `listUnread` 中同步计入 owner 的 `unread_count`。
- **`R1-C2`**: `accepted` — ① 已对齐 `design.md`、M1 退出标准及 `specs/im/{web-chat-ux,ios-client,desktop-client}.md`：Web（`InAppToast` + 后台 `AgentCompletionNotifier`）、Desktop 与 iOS（`ChatBanner` 扩展支持定位会话/话题/助手 Work 且保持默认不暴露正文，同时修复现网普通真人 `message.created` 前台横幅）一致覆盖新消息、群话题、静音 `@提及`、`chat_permission` 与本人管理助手 `work_permission`；② 在 `design.md` §接口与数据流 2 新增完整确定性事件映射表与跨事件幂等 `dedupe_key`（解决 `publishAgent` 双事件、精简 `message.completed` 字段补齐、`WorkerPermissionCards` 建卡/结案双发、`system` 消息与 PA 代发），并沿用 `'chat_permission'` / `'work_permission'` 保持存量单测兼容。
- **`R1-W1`**: `accepted` — 已在 `design.md`（关键决策 3、§接口与数据流 2）明确：`Work.notifyUpdated` 从活跃 `global_main` 会话 + 最新 `agent_work_turns.execution` + `gateway.isOnline` 计算真实 `main_execution`，对所有 `agent.work.updated` 帧附带 `notification_hint`（非待决权限或非本人管理显式置 `eligible: false`），消除 Desktop 99% 非权限更新的 HTTP `GET /work` 反查；待决权限 `dedupe_key` 锚定为 `work-perm:${agentId}:${mainSessionId}:${activeTurnId}`；`Gateway.broadcast` 按 `uniqueUserIds` 批量预取并构造 per-user 独立浅拷贝帧，杜绝循环内 N+1 查询与共享 `frame` 跨用户污染。
- **`R1-W2`**: `accepted` — 已在 `design.md`（关键决策 3、4）与 `specs/im/{web-chat-ux,desktop-client}.md` 补齐：`im-server` 在标记已读与修改会话偏好时向本人 `/im/ws/user` 连接投递 `conversation.read` 与 `conversation.preference_updated`（含最新 `unread_count` / `is_muted`），打通 Desktop Rust 既有监听与 Web/iOS 实时角标同步；Web `app-shell.tsx` 开放桌面视口查询，在桌面左侧栏与移动底部 `聊天` 统一显示未静音总未读数，移除移动端 `我` Tab 重复角标。
- **`R1-W3`**: `accepted` — 已在 `design.md`（关键决策 1、5）修正：`check_platform_parity.py` 改为双向核验（`native-sync` 行必有对应路径改动，且共享触发集覆盖 Web/Desktop/iOS 全端）；`ci.yml` 将 `develop` 加入 `push.branches` 保障主干真机归档；`iOS build and tests` 保留原 Job 名，对 UI 变更单次执行 `build.sh test` 避免拆跑双倍开销，并在 Windows Desktop CI 复用 `build-desktop-windows.ps1` 既有 `cargo test`。
- **`R1-W4`**: `accepted` — 已在 `design.md`（§涉及范围、关键决策 2、5、§接口与数据流 3）修正：`client-parity.ts` 仅引用既有权威子模块组装生成表而不重复定义重导出同名类型，彻底避免 `TS2308`；`platform-io.ts` 保持 `localNodeBridgeEndpoint` 与 `apps/desktop/src/config.rs:294` 字节级一致，并新增 `src/IM/shared/local-ipc-endpoint-test-cases.json` 在 Node 与 Rust 双端锁死。
- **`R1-R1`**: `accepted` — 已在 `design.md` §接口与数据流 3 明确为新增共享向量在 `src/IM/ios/Tests/` 建立指向 `../../shared/*.json` 的受跟踪相对符号链接。
- **`R1-R2`**: `accepted` — 已在 `design.md` 关键决策 2 明确 `test_client_contract_parity.py` 仅针对生成协议枚举的匹配块（花括号平衡提取）禁止 `default:` 与 `_ =>`，不误伤普通本地 UI 分支。
