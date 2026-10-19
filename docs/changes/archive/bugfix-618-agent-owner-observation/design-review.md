# bugfix-618 Design Review

## Round 1

### Metadata

- reviewer_target: `/root/design_review_618`，独立 reviewer；未参与本轮需求或设计编写。
- review_mode: `full`
- mode_reason: Gate 2 首轮；完整检查需求、当前装配、授权与事件链路、四份 delta、Web/iOS 体验和单 M1 验收前置。
- baseline: `main@dfdbf6bf3`；工作区存在既有 dirty/untracked，未重置、未改动既有文件。
- started_at: `2026-10-19T21:38:31+08:00`（本 reviewer 首次采集的时钟；此前已完成的阅读和原型渲染未计入计时）。
- completed_at: `2026-10-19T21:41:01+08:00`
- duration: `PT2M30S`（仅上述已记录时钟区间，非全程耗时）。
- inputs: `incident.md`、`design.md`、`specs/im/{auth-tenancy,conversations-messages,web-chat-ux,ios-client}.md`、`prototype.html`、`evidence/design-visual.md`、四张设计/基线图片、`evidence/fixture.mts`；受审产物冻结，本轮仅新增本报告。

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING。Gate 2 尚未通过。**

方案的核心职责划分可行：双方 owner 的资格应由 IM 既有聊天授权模块派生；保留正式成员写资格，复用媒体读取与 user-stream，不新增观察成员、ACL 表或 DSH 机制。但 current 契约尚有冲突，Web 撤权后的页面清理没有闭合，iOS 新暴露的列表交互也未纳入方案。

### Coverage 与证据

#### 需求、现状与实际产品装配

- 核对 `apps/im-server/src/server.ts:83` 的 `Messaging` / `Gateway` 实例，以及同文件的 messaging、work、media 路由注册。这些是当前真实服务组装点，不是测试专用实现。`messaging.ts:72` 的 `access()` 委托 `conversationAccess()`，write 模式继续要求成员；`media.ts:48` 的受保护资源读取与 `media.ts:128` 的上传分别复用 read/write。修改集中在 IM，符合仓库包边界。
- 当前 `conversation-access.ts:16` 仅支持成员/公开群；`messaging.ts:166` 的 joined 查询只取成员；`messaging.ts:670` 新建 Agent direct 只插入两个 Agent。这支持 incident 的根因，不能靠修单个 `conversations.owner_id` 解决。
- `identity.ts:41`、`:49`、`:54`、`:62` 已提供账号、空间、真人 owner 与 Agent 身份的分层语义。设计从 profile 的真实 owner 派生、只接受恰好两个同空间 Agent、无法核实不推断，并为 stale/离线历史保留读取，决定已收口；没有要求恢复 Agent 发言能力。实际实现应注意历史读取不能误复用 `agentAvailable()` 对 `is_stale` 的执行限制。
- 同 owner 去重、跨 owner 双方可见、个人空间、旧会话无需新消息、真人不加入、不发送/不改消息或参与者、普通成员聊天不受影响，均在设计或 M1 中有对应结果。服务端拒发不依赖 UI；既有 `TaskGraphService.writable()` 同样要求成员，没有将观察权误用为任务写权。

#### 列表、实时、恢复与媒体

- `messaging.ts:320` 的持久事件有原 event ID；当前 publish 接收者是成员，`gateway.ts:232` replay 也是成员 SQL。设计新增模块级 reader 查询并在 broadcast/replay 末端重新检查当前资格，能够覆盖新事件接收、已有事件恢复与失效防泄漏；保留全局 top cursor、15 分钟/2000 gap 的既有 resync 语义，不需要独立 observer 流或事件复制。
- 核对 Web `chat-workspace-page.tsx:803` 的 message.sent/message.created 分支：收到首条事件会失效并重拉列表；iOS `ChatStore.consume()` 也会标记 needsList 并补读。故新会话发现可以复用现有消费者，不必增加一套通知协议。
- 媒体 read 在实际路由内复用 `Messaging.access()`，因此 owner 能查看附件、无关账号不能借 URL 访问的方向成立。附件 current 契约尚未同步列入 delta，见 R1-W1。
- 资格失效后停止服务端交付的设计明确；但 Web 已显示内容的清理依赖不足，见 R1-W2。该问题不是要求提前实现后端验收，而是当前复用能力与设计断言不符。

#### 独立渲染与体验判断

- 使用 `cua_repl` 独立打开 `http://127.0.0.1:53187/prototype.html`（IAB tab 1），实际看桌面画面，再依次点击 **Web 窄屏 → 模拟新消息 → 模拟资格失效 → iOS**，每次操作后读取 AX 并观察截图。非仅阅读 DOM/CSS；未修改原型。
- 桌面能从 Network 选中项与会话标题对应到 `Atlas ↔ Scout`，消息作者、节点说明、正文与时间层级清楚；底栏明确写“Agent 协作 · 只读”与“不能发送消息”，不需要靠演示数据解释只读含义。390 宽聊天中长消息换行，追加后内部历史滚动，标题与只读底栏保留；模拟失效后正文和底栏消失，显示不可访问。上述阅读与操作结果符合本次核心体验。
- 对照实际基线 `evidence/current-chat.png`：当前成员群的作者/节点、浅色气泡、时间和底部输入区可核实；本方案沿用阅读顺序，用只读条取代输入。基线仅为成员群，未把它当成现有可观察 direct。作者的 `prototype-web.png` / `prototype-narrow.png` / `prototype-ios.png` 与本轮独立观察一致。
- iOS HTML 画面呈现独立居中导航与底栏，可以指导此次提示替换；真实 `ConversationView.swift:85` 已有 safeAreaInset、can_write 门禁和公开群 join 条件，`:117` 已对非成员每 3 秒检查权限。未声称已经验证 SwiftUI 成品或真机。原型尚未覆盖原生观察列表长按/侧滑，现有实际源代码会暴露必拒绝动作，见 R1-W3。
- 窄屏原型只展示聊天，Network 列表与返回是沿用背景而非可操作旅程；当前可确认聊天阅读方案，不能据此声称已经独立验证手机 Network 的发现旅程。实施验收须按 R1 在真实窄屏完成该旅程。

#### delta、milestone 与验收资源

- 四份 delta 的 canonical 文件目标存在；auth-tenancy 的 MODIFIED 保留了原六个 Scenario，并对成员读取增加观察例外；conversations-messages 对原 Agent direct Requirement 的改动对应 incident 的明确用户决定；Web/iOS 的新增只读行为采用消费者视角。仍有未列入 delta 的当前明确断言与目标冲突，见 R1-W1。
- 单 M1 垂直交付有合理性：ACL、事件、客户端任一单独上线都不能完整交付本问题。R1/R2/R3 覆盖发现、只读、实时/历史/恢复；W1/W2/W3 覆盖 HTTP/WS、客户端与门禁，must-match 已投影到 reviewer 用户结果和 worker 对照证据。不存在需要人为并行拆开的独立实施范围。
- 读取 fixture：合成 alice/bob/charlie、双 owner、同 owner、个人空间、原成员群、实际 HTTP 登录与 gateway WS 发言、seed/send/revoke/restore 控制均有明确来源；没有外部真人、生产账号或模型调用依赖。fixture 的 `/revoke` 是合成 DB owner 变更，只证明可驱动该条件，不代表生产整机交接已验收。
- 本轮只读检查 `http://127.0.0.1:58054/health` 得 `{"status":"ok"}`；核实 `/Applications/Xcode.app` 存在，`xcrun simctl list devices available` 包含 `iPhone 17 Pro (1CE31893-672F-495A-B2B5-3ACF39A7A257)`。build/test 脚本支持设计所写环境变量。设计有专用端口、临时数据库、进程退出和资源清理说明。验收前置资源已落实；未运行实现后的矩阵、构建或产品验收，也未启动/停止作者服务。

#### 职责与复用判断

owner 观察资格与 reader 集合由 `conversation-access` 负责，调用层只消费授权结果，优于在列表、媒体、gateway 分别查 owner。`Messaging` 负责 DTO/事件接收者，`Gateway` 负责最后一跳资格与恢复游标，客户端负责当前资格的显示和缓存清理，职责合理。无新的长期状态表、事件复制或跨包依赖；不是为假想场景增加通用 ACL 框架。需要补齐的是现有客户端和契约的实际接缝，不需要扩大架构。

### 历史问题闭环

首轮 full，无历史 issue / Author Resolution。

### Issues

#### R1-W1 — delta 未覆盖仍明确限制“私聊仅成员可读”的媒体与 Work 契约

- **位置**：`design.md:62-67`；`specs/im/conversations-messages.md:16-28`。
- **证据**：current `docs/specs/im/conversations-messages.md:445-452` 的“IM 托管聊天附件按会话成员关系读取 / 普通图片与文件上传”明确写“私密群与私聊仅成员可读”；current `docs/specs/im/agent-work.md:28-31` 也明确写原聊天及附件“私密群与私聊仅成员可读”。设计 `design.md:30,39` 却要求观察者读取同一媒体，并且修改 Work 来源 direct 的读取结果；现有 delta 仅修改另一条 Agent 私聊 Requirement，没有包含这两个断言。另 current 私聊菜单/重命名 Scenario 以“自己可访问的私聊”为条件，新增观察例外后也应明确成员写入前提。
- **未修后果**：即便四份 delta 正确归并，current 仍会同时承诺“非成员 owner 可读”和“私聊/附件仅成员可读”，下游实现者、测试或 Work 链接验收可能按相反规则执行。该冲突直接落在本 unit 明确覆盖的受保护媒体与回执跳转路径。
- **所需收口**：为上述实际受影响 Requirement/Scenario 增加最窄 delta，保留其余未变 Scenario；Work 自身可见性不扩大，只使来源读取规则引用或表达统一会话资格。为观察 direct 排除私聊写菜单的 current 适用前提。

#### R1-W2 — Web 的 owner 变更失效状态没有可兑现的清理触发

- **位置**：`design.md:41`，以及 `design.md:57` 的失效 must-match / M1 R3。
- **证据**：设计称已有内容“沿既有身份/空间切换和权限重查清理”。但本场景 owner 变更时真人仍是同一个有效公司账号，既有身份切换不会发生。Web `chat-workspace-page.tsx:364` 只在会话**不在列表**时轮询详情，本次观察会话将进入 joined 列表，因此该权限检查关闭；`:374` 虽轮询消息，但 `:581-606` 只在有 data 时恢复旧时间线，403/404 没有权限清理分支。明确清理机制在 membership/deleted 事件和 recovery 中（`:680-738`）；实际设备交接 `identity-routes.ts:272-276` 只 revokeNode，不向原 owner 浏览器发送 conversation 失效通知。新 reader 过滤阻止后续受保护事件，也就不能靠这些事件触发列表重读。
- **未修后果**：按当前方案只改 ACL/接收者并复用既有刷新，原 owner 持续打开 Web 时可以一直保留原正文、列表条目或媒体预览；原型展示的“此聊天已不可访问”不会自然发生。服务端停止新内容与客户端切换失效态是两个结果，后者目前悬空。
- **所需收口**：明确一个简单、可执行的触发和负责模块，例如复用非敏感资格变更通知，或对 observer 做有效权限复查并在拒绝时调用既有清理流程；同时约定清理列表/当前正文/已挂载媒体和迟到响应。将“同账号、同空间、保持在线，仅 owner 关系改变”的旅程投影进对应 worker/reviewer 验收，不必增加持久旁观订阅。

#### R1-W3 — iOS 的新增观察列表仍会呈现必失败的会话写动作

- **位置**：`design.md:10-12,32,58,95`；`specs/im/ios-client.md`。
- **证据**：方案将 observer 加入共享会话列表，并让所有 PATCH 等 write 门禁继续要求成员。当前实际 `src/IM/ios/NanoIM/Features/Chat/ChatListView.swift:50-55` 对每一条会话无条件提供长按置顶/静音和两侧 swipeActions，`:77-78` 直接 PATCH；服务端 `messaging.ts:745-750` 在处理这些偏好前就执行 write access。设计的 iOS 落点和原型只覆盖 Conversation DTO 与 `ConversationView` 只读底栏，没有决定位于列表的这些动作如何跟随 observer 权限。
- **未修后果**：原生用户从新增观察条目长按或侧滑，会被引导点击服务端必然拒绝的操作，结果是整个列表出现错误提示；底栏隐藏 composer 无法消除这条用户可达路径。不能以“原生沿用既有流程”声称该端只读方案完整。
- **所需收口**：在设计明确观察列表的可用操作，并让原生列表遵循已决定的只读权限（例如隐藏这些 write 动作）；提供该端对应状态依据，并把长按/侧滑纳入 R2/W2。无需为 observer 新建偏好存储或扩大写权。

### Recommendations

#### R1-R1 — 实施时保留“Network 分类”与“group 业务形态”的区别

当前 Web `classifyConversationKind()` 的 `agent-network` 被 `chat-workspace-page.tsx:502` 同时视为 group，并控制 GroupSettings/任务入口。如果直接把 agent-agent direct 改成这个 kind，需同步以真实 `type`/capability 约束相关消费者，避免 Network direct 被当成群。设计已要求不展示会话写操作，因此这是一条落实既定结果的实施提示，不另增加阻断问题或要求通用分类重构。

### Author Resolutions

- R1-W1 accepted：补 `agent-work` 两条及 `conversations-messages` 附件、私聊菜单、改名的完整 MODIFIED Requirement，保留未变 Scenario；不扩 Work 本身访问权。
- R1-W2 accepted：design 接口与数据流明确由 Web 非成员 3 秒消息复查的 403/404 触发现有 reconcileMembership，取消/清理缓存和迟到请求，并收敛列表与当前页面；R3/W2 与 Web delta 增加同账号同空间仅 owner 改变的旅程。
- R1-W3 accepted：design/iOS delta 明确隐藏观察条目的长按/侧滑偏好写操作，详情仅阅读；R2/W2 包含对应原生验收。原型视觉沿用已有行与底栏，未新增 UI 构型。
- R1-R1 accepted：明确 Network 分类不等于 group，群设置/任务按真实 type 限制。

## Round 2

### Metadata

- reviewer_target: `/root/design_review_618`，沿用 R1 独立 reviewer。
- review_mode: `closure`
- mode_reason: 本轮变化限于 R1 三项问题的局部收口及可选分类提示，没有改变需求、授权核心边界、共享接口形状或 milestone 拆分；已具备 R1 上下文与独立渲染证据。
- baseline: `main@dfdbf6bf3`；核实 branch/HEAD 未变。
- started_at: `2026-10-19T21:42:13+08:00`
- completed_at: `2026-10-19T21:43:24+08:00`
- duration: `PT71S`
- inputs: 冻结后的 `design.md`、五份 `specs/im/` delta 与 R1 Author Resolutions；对照 R1 引用的 current/source。仅追加本报告，不改设计、代码或旧结论。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。Gate 2 尚未通过。**

R1-W1、R1-W2 已关闭。R1-W3 的设计决定、must-match 和验收安排已收口，但冻结输入的 iOS delta 没有写入对应行为，Author Resolution 与实际文件不符；剩余范围仅为契约同步。

### Coverage 与保留证据

- retained_from: **Round 1**。账号/空间/owner 派生语义、IM 实际装配、写权限、list/HTTP/WS/replay/媒体职责、单 M1 垂直交付及资源检查结论保留；本轮没有更改这些决定或资源来源。
- retained_from: **Round 1 独立原型观察**。原型视觉未变化，不重复渲染相同正常/长消息/失效画面；沿用桌面、390 宽聊天和 iOS 底栏的观察边界。新增原生列表方案是移除现有长按菜单/侧滑，不新增视觉构型；设计已明确保留行点击与既有容器，不需要为此另建一套原型。
- 本轮读取所有修订内容，并再次对照 `docs/specs/im/agent-work.md` 的两条完整 Requirement、附件与私聊菜单/改名 Scenario，以及 Web 既有 `reconcileMembership` / `loadOlderMessages`。没有把设计新增措施误称为已经实现或验收。

### 历史问题闭环

#### R1-W1 — closed

- **Author Resolution**：补 Work 两条及附件、私聊菜单、改名的完整 MODIFIED，保留未变 Scenario，不扩 Work 范围。
- **本轮证据**：`specs/im/agent-work.md` 对“聊天沟通与全局工作轨迹分开呈现”和“原生轨迹是既有 Work 权限下的只读检查”均提供完整修改块，分别保留 5 个和 3 个 Scenario；来源读取改为统一资格，Work 自身范围和附件副本不产生旁路的约束保持。`specs/im/conversations-messages.md` 完整保留附件 3 个 Scenario、改名 5 个 Scenario，并补观察者媒体读取例外、私聊菜单与改名的成员写前提。
- **判断**：R1 明确指出的 current 冲突都有对应 canonical delta，未发现借修订扩大 Work 权限，关闭。

#### R1-W2 — closed

- **Author Resolution**：非成员每 3 秒消息复查的 403/404 触发现有 reconcileMembership，清理缓存及迟到请求，R3/W2 与 Web delta 增加在线 owner 变化旅程。
- **本轮证据**：`design.md` 接口与数据流明确保留 HTTP status、403/404 不重试、重拉列表、清理消息/详情缓存/草稿/reducer/挂载媒体、取消在途历史、按 conversationId/请求身份丢弃迟到结果，返回列表且提示失效，并明确前台下一次权限复查后收敛。对照现有 `chat-workspace-page.tsx:374` 的非成员消息轮询与 `:678` 的 reconcileMembership，有可复用的触发点和清理责任；方案没有再假设 owner 变化自动发 membership 事件。`specs/im/web-chat-ux.md` 增加“在线观察资格失效”Scenario；M1 R3 与测试处置包含同账号同空间仅 owner 变化及迟到响应。
- **判断**：触发、结果、责任和验证路径闭合，关闭。真实实现须补齐这些设计措施，R2 不提前声称后端或产品测试通过。

#### R1-W3 — still-open（仅剩 iOS delta 同步）

- **Author Resolution**：design/iOS delta 明确隐藏观察条目的长按/侧滑写操作、详情只阅读；R2/W2 纳入原生验收。
- **已核实部分**：design 涉及范围增加 `ChatListView.swift`；关键决策、must-match、原生列表说明和 M1 R2/测试处置均明确隐藏观察行置顶/静音菜单与 swipeActions、保留点击、详情无写表单，足够指导实施。此设计部分已解决。
- **仍缺证据**：冻结的 `specs/im/ios-client.md:1-10` 仍仅有“原生只读聊天”Scenario，THEN 只写只读说明、双方消息、composer/join 隐藏和非公开群提示；没有列表长按/侧滑或详情写表单的约束。与所述 Resolution 不符，详见 R2-W1。

#### R1-R1 — accepted / verified

design 明确 Network 仅为分类，群设置与任务入口继续按真实 `type=group` 判断；对应既有 isGroupKind 耦合的实施提示已落实为决定，无需增加通用分类重构。

### Issues

#### R2-W1 — iOS 观察列表与详情只读约束尚未进入 delta（承接 R1-W3）

- **位置**：`specs/im/ios-client.md:5-9`；R1 Author Resolutions 的 R1-W3 项。
- **证据**：本轮实际读取并按行核实文件：总共 10 行，唯一 Scenario 是打开聊天后隐藏 composer/join。design 已决定的列表长按/侧滑写动作隐藏、详情无写表单未写入 delta。
- **未修后果**：按当前 delta 归并后，canonical 原生观察契约仍只约束聊天底栏，遗落本轮已确认的列表/详情可达写入口，后续维护或回归可重现 R1-W3；Author Resolution 也不能据此宣称全部闭环。
- **所需收口**：在现有新增 Requirement 下补一个列表/详情只读 Scenario，或补充现有 Scenario 的适用行为，表达设计已经决定的结果即可；不需要新设计、代码、额外视觉构型或扩大验收范围。

### Recommendations

无新增建议。剩余补正为文档契约遗漏，下一轮可继续 closure，只核实 R2-W1 即可。

### Author Resolutions

- R2-W1 accepted：上一轮文字替换未命中实际 iOS delta，已直接补入“观察会话列表与详情只读”Scenario，明确长按/侧滑无偏好写操作及详情无改名表单。design、实现范围与其余 delta 未变。

## Round 3

### Metadata

- reviewer_target: `/root/design_review_618`，沿用 R1/R2 独立 reviewer。
- review_mode: `closure`
- mode_reason: 本轮仅补正 R2-W1 的 iOS delta 遗漏，需求、方案、接口、milestone、原型及其他输入不变。
- baseline: `main@dfdbf6bf3`，本轮已核实 branch/HEAD。
- started_at: `2026-10-19T21:43:47+08:00`
- completed_at: `2026-10-19T21:44:06+08:00`
- duration: `PT19S`
- inputs: 冻结后的 `specs/im/ios-client.md` 与 R2 Author Resolution；本轮只追加本报告。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。Gate 2 通过。**

### Coverage 与保留证据

- retained_from: **Round 1 / Round 2**。沿用实际装配、权限/事件/媒体/恢复、Web/iOS 原型观察、职责复用、验收资源与 M1 判断；本轮没有影响这些范围，不重复渲染或实施后的产品测试。
- 本轮直接读取实际 iOS delta 文件，不仅依据 author 的完成声明。新增行为是既定设计决定的契约表达，没有新增实现机制、视觉构型或验收资源。

### 历史问题闭环

#### R2-W1（承接 R1-W3）— closed

- **Author Resolution**：承认上一轮替换未命中，已在实际 iOS delta 补“观察会话列表与详情只读”Scenario。
- **本轮证据**：`specs/im/ios-client.md` 的新增 Scenario 明确在 owner 长按、侧滑观察会话或打开详情时，条目保留查看入口、不提供置顶/静音等会话写操作，详情展示名称和真实参与者、不显示改名等写表单；原有 composer/join 只读 Scenario 保留。
- **判断**：与 design 的关键决策、原生列表呈现依据及 R2/W2 验收要求一致，原生列表/详情遗漏已闭环。R1-W1/W2 的 closed 结论及 R1-R1 的 accepted/verified 结论沿用 Round 2，无其他开放问题。

### Issues

无。

### Recommendations

无新增建议。本结论仅确认设计可进入实施，不代表代码实现、模拟器成品、HTTP/WS 回归或生产验收已通过。
