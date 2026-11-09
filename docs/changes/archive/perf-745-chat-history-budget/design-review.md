# 聊天历史轻量过程摘要设计审查

## Round 1

- reviewer: `/root/perf_design_gate_runtime`
- target: `perf-745-chat-history-budget` 首文档、定稿方案与 M1 骨架，代码基线 `04a07bb2`
- review_mode: `full`
- mode_reason: Gate 2 首轮，覆盖中心投影、前端权限与过程交互
- started_at: 2026-11-09T21:32:25+08:00
- completed_at: 2026-11-09T21:33:24+08:00
- duration: 59 秒
- Verdict: **Issues Found**
- 0 CRITICAL / 3 WARNING

### Coverage 与证据

[生产中心](../../../apps/im-server/src/server.ts#L189) 组装消息路由。现有 [历史路由](../../../apps/im-server/src/messaging.ts#L994) 先过会话权限、以消息 rowid 分页，随后调用 [MessageRecords](../../../apps/im-server/src/message-records.ts#L137) 的完整投影。中心应继续负责历史与审批数据的同源投影，轻量查询在数据层隔离工具及思考正文，并与运行中消息和旧客户端完整入口并存。浏览器继续由 [ChatWorkspace](../../../src/IM/frontend/src/features/chat/chat-workspace-page.tsx#L349) 管历史、权限和实时合并，过程面板承担同一消息的展开。单 milestone 可覆盖当前中心和 Web 的共同行为。

性能对照选择同一 50 条历史、工具明细规模与首个请求时序，能解释用户的首屏和页大小改善。实施后需沿实际 Web 入口验证权限变动、过程面板和兼容性。设计模式检查了现有折叠面板源码，当前设计有待补的状态和信息见下。既有入口和布局足以表达范围，无需另做页面原型。未执行真实页面或性能验证。

### Issues

- **R1-W1 — 补齐单条过程读取和 API 消费者契约。** [方案](design.md#L5) 写作复用“已鉴权的会话消息详情入口”，而生产 [消息路由](../../../apps/im-server/src/messaging.ts#L988) 只有历史与互动草稿读写，后者无法读取完整过程。应明确新增同一会话下的消息过程/详情读取，复用现有会话 read 授权，按会话 ID 与消息 ID 共同定位，以免持有两个会话中的其中一个读权限即可组合 ID 取到其他会话的过程。保留旧历史默认行为，在 [会话消息 canonical spec](../../specs/im/conversations-messages.md#L48) 写清新轻量视图、详情读取及授权结果，保留原有 Scenario。当前设计会使实施者在接口复用、DTO 与权限边界上作出不同决策。
- **R1-W2 — 定义折叠可见摘要及首次展开失败恢复。** [消息气泡](../../../src/IM/frontend/src/features/chat/components/message-pane.tsx#L2027) 和 [折叠面板](../../../src/IM/frontend/src/features/chat/components/tool-calls-panel.tsx#L103) 用工具、思考、后台返回、回复过程与已裁定审批计数渲染按钮。只有过程存在标记时，原组件会隐藏入口或丢掉历史中的审批概况。应确定精简投影如何保留现有折叠概况和四类过程项，说明加载、失败可重试和收起后的表现。把普通及审批消息的折叠统计、首次失败后可重试纳入现有 Web 验收。当前设计只检查加载态和成功展开。
- **R1-W3 — 明确当前会话授权结果和过程缓存的失效顺序。** [当前页](../../../src/IM/frontend/src/features/chat/chat-workspace-page.tsx#L356) 优先使用侧栏数据，[切换与失权恢复](../../../src/IM/frontend/src/features/chat/chat-workspace-page.tsx#L726) 也会读取侧栏缓存，[删除执行历史](../../../src/IM/frontend/src/features/chat/chat-workspace-page.tsx#L562) 另有 revision。独立启动详情和消息请求后，旧侧栏、先返回的消息页或在途详情可能与当前详情拒绝或执行清理交错。设计应明确侧栏慢或返回旧成员资格时，以当前独立读授权控制渲染及写入，失权和清理按会话移除详情数据并拒收晚响应，实时过程与摘要刷新合并时保留同一 revision 下的新数据。验收加入旧侧栏、迟到详情、执行清理及刚完成的消息遇到摘要刷新场景。

### Author Resolutions

- R1-W1/W2/W3 accepted。明确新详情入口与摘要兼容契约，保留折叠统计和失败重试，指定授权、清理、迟到和实时合并边界。

## Round 2

- reviewer: `/root/perf_design_gate_runtime`
- target: `perf-745-chat-history-budget` R1 修订方案及会话消息契约增量
- review_mode: `delta`
- mode_reason: 补齐 API 与 DTO 消费边界、前端加载和授权规则；复核相应契约和验证
- started_at: 2026-11-09T21:37:33+08:00
- completed_at: 2026-11-09T21:38:00+08:00
- duration: 27 秒
- Verdict: **Approved**
- 0 CRITICAL / 0 WARNING

### Coverage 与证据

`retained_from: Round 1`。生产路由与数据所有者、分页、既有前端入口、性能对照方法和单 milestone 范围继续成立。复查新 API 与当前路由的关系、canonical target 与未改 Scenario、折叠摘要与失败恢复，以及权限和 revision 交叉时序。方案沿用现有面板，无需另做原型。尚未执行候选实现、真实浏览器或性能测试。

### 历史问题闭环

- **R1-W1 — closed。** Author 接受并新增当前会话下的单消息详情入口，使用与历史相同的 read gate 且按会话与消息共同定位。轻量页明确 opt-in，旧默认保持完整。[设计](design.md#L5) 与 [delta](specs/im/conversations-messages.md#L54) 一致，目标 Requirement 的十个既有 Scenario 均保留。负向授权、旧客户端与分页列入验证。
- **R1-W2 — closed。** Author 接受并明确轻量统计覆盖当前折叠入口，包含已裁定审批和回复过程类型。首次展开懒读，加载或失败保持摘要，失败可重试，收起后可复用仍有效的详情。[设计与验证](design.md#L5) 足以指导面板复用和验收。
- **R1-W3 — closed。** Author 接受并明确当前会话详情主导读写资格，旧侧栏与先到的历史响应不能提前展示，详情缓存隔离账号、会话、消息及清理 revision，撤权或清理使在途请求和缓存失效。[设计](design.md#L7) 也明确同 revision 下的摘要刷新保留完整过程与更新的实时片段，验证覆盖相关交错。

### Recommendations

- **R2-R1。** 实施折叠审批计数回归时，可用一条只有 `reason: "denied"` 的旧历史 tool call 覆盖现有 [gateVerdict](../../../src/IM/frontend/src/features/chat/components/tool-presentation.ts#L101) 的兼容行为。
