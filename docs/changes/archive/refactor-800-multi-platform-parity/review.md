# refactor-800-multi-platform-parity: Review

## 范围与版本

- 本次问题与需求/设计位置：[`motivation.md`](motivation.md)、[`design.md`](design.md)（含 §五端对齐矩阵、§本次审查安排）、[`design-review.md`](design-review.md) 及 3 份契约增量 [`specs/im/web-chat-ux.md`](specs/im/web-chat-ux.md)、[`specs/im/ios-client.md`](specs/im/ios-client.md)、[`specs/im/desktop-client.md`](specs/im/desktop-client.md)。
- 实际 executed_base / validated_at：
  - `executed_base`：`953eeb86ecedadd590e7975a5709a2a1ca4cf739`（`origin/develop`，含 `bugfix-802-ci-feedback` 并行 CI 基线）
  - Round 1 `validated_at`（`pre_fix_head`）：`43d69477b895e31385a1099b477d066457827419`
  - Round 2 `validated_at`（修复后关闭复审）：`d1d71712f8ecd2b296e96311b6b4ba34440710a3`
- 最终 effective_base / effective_through 与保留依据：`effective_base = 953eeb86ecedadd590e7975a5709a2a1ca4cf739`，`effective_through` 在 `d1d71712f8ecd2b296e96311b6b4ba34440710a3` 基础上仅包含本审查报告落盘、已通过校对的 3 份 canonical spec 归并与 `docs/changes/archive/` 归档移动，无生产代码或测试变更，Round 2 独立审查结论完整保留。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| 五端实现正确性、需求与设计完整性（Web / Desktop macOS / Desktop Windows / iOS / 三端 Node）、架构红线与最终 delta-spec 校对 | `change-code-review` · 独立审查子代理（Round 1 `full` @ `43d69477b` → Round 2 `closure + patch/delta` @ `d1d71712f`） | `pass` | 独立核实 67 个变更文件与全端测试证据：`@nano/product-contracts` 单源生成 Swift/Rust 协议枚举且 `test_client_contract_parity.py` 验证零 `default:`/`_ =>` 通配兜底；本仓 `docs_check.py` 与 `check_platform_parity.py` 实现双向漏端阻断且零修改外部 `dev-workflow-skills`；共享黄金向量（`unread-badge`、`timeline-divider`、`local-ipc-endpoint`）在 Web Vitest（1,342/1,342）、Desktop `cargo test`（9/9）、iOS `NanoIMTests`（`TEST SUCCEEDED`）与 Node `platform-conformance.test.ts` 全绿；Round 1 发现的 `R1-F1`、`R1-F2` 在 `d1d71712f` 修复并经独立复审确认关闭；3 份 `specs/im/*.md` delta-spec 校对为 `clean`。 |
| 控制面 `Gateway.broadcast` / `replay` 固定常数次 SQL 与独立接收者帧隔离、流式帧零膨胀、Desktop 免 HTTP 反查与 CI 零增时 | `performance-review` · 独立审查子代理（Round 1 `full` @ `43d69477b` → Round 2 `closure + patch/delta` @ `d1d71712f`） | `pass` | `NotificationProjector` 与重构后的 `Gateway.broadcast`（`apps/im-server/src/gateway.ts:202-334`）对会话校验、Work 可见性与会话成员预取统一采用 `json_each` 批量查询，`apps/im-server/tests/notification-parity.test.ts:346-372` 实测 `R = 3` 与 `R = 25` 接收者在 `message.delta`、`message.created`、`agent.work.updated` 上 `db.prepare` 次数严格相等（`O(1)`）且 `replay <= 16`；`message.delta` 零新增字段；`agent.work.updated` 全覆盖 `notification_hint` 使 Desktop `notifications.rs:1681-1709` 短路跳过 HTTP `GET /agents` 与 `GET /work`；`.github/workflows/ci.yml` 保留 `bugfix-802` 独立归档快检、后端双分片与 `iOS ${{ matrix.task }}` 并行矩阵，按变更面动态分流 `unit-test` / `test` / `["test", "archive"]` 并覆盖 `main` 与 `develop` 主干归档。 |

## Findings 与关闭

| ID | 位置与触发条件 | 影响、严重度与证据状态 | Resolution | 独立关闭依据与版本 |
|---|---|---|---|---|
| `R1-F1` | `src/IM/ios/NanoIM/Features/Chat/ConversationView.swift:289-300`、`ChatStore.swift:17`、`NanoIMApp.swift:287,335,378`：点击 iOS 群话题前台横幅或打开 `/chat/:id?thread=:root` 且根消息不在最新 50 条时间线窗口内时，`ConversationView` 直接将 `GET /im/v1/conversations/:id/messages/:root` 解码为 `ChatMessage`（实际服务端返回 `{ message, execution_cleanup_revision }`），且 `pendingThreadRootID` 未绑定 `conversationID`。 | `blocking` / `confirmed`：窗口外历史话题提醒点击无法自动展开 `ThreadView`，且未消费的 `pendingThreadRootID` 会跨会话残留。 | 在 `ChatStore.swift:14-22,569-582` 改为带会话作用域的 `PendingThreadTarget(conversationID:rootMessageID:)` 与 `resolvePendingThreadRoot(conversationID:)`，解码 `MessageDetailEnvelope { let message: ChatMessage }`；同步更新 `ConversationView.swift:289-293`、`NanoIMApp.swift:285-295,338-346,385-395`，并在 `ConventionsParityTests.swift:239-295` 新增跨会话隔离与详情信封解码单测。 | `closed` @ `d1d71712f8ecd2b296e96311b6b4ba34440710a3`（Stage 4 Closure Reviewer 核实代码与 `NanoIMTests` `TEST SUCCEEDED`）。 |
| `R1-F2` | `apps/desktop/src/notifications.rs:1565-1637`：仅在 `"message.created"` 分支将 `notification_hint.conversation_unread` 写入 `NotificationCenterState`，忽略了 `"message.completed"` 与 `"permission.request"` 上的最新 `conversation_unread`。 | `blocking` / `confirmed`：群话题内 Agent 流式回复完成时因 `@提及` 才递增的未读数在 Desktop 托盘/Dock 角标上滞后不更新。 | 在 `apps/desktop/src/notifications.rs:139-167,1627-1635,1660-1671` 提取 `apply_hint_conversation_unread` 统一覆盖 `"message.created"`、`"message.completed"` 与 `"permission.request"`（保留当前聚焦会话抑制），并在 `notifications.rs:2191-2255` 补充流式完成提及、权限请求与聚焦抑制断言。 | `closed` @ `d1d71712f8ecd2b296e96311b6b4ba34440710a3`（Stage 4 Closure Reviewer 核实代码与 `cargo test` 9/9 通过）。 |
| `R1-F3` | `apps/im-server/src/gateway.ts:220-252`、`conversation-access.ts:178-183`：`NotificationProjector` 本身为 `O(1)`，但 `Gateway.broadcast` 前置接收者过滤循环逐连接执行 `browserValid`、`canViewAgentWork`、`canActorAccess` 与 `conversationAccess` 同步 SQLite 查询。 | `blocking` / `confirmed`：广播前置过滤随在线接收者连接数呈 `O(R)` 增长（含流式 `message.delta` 每连接 1 次 SQL、`agent.work.updated` 每连接 6~8 次 SQL）。 | 在 `gateway.ts:202-334` 与 `conversation-access.ts:178-191` 新增 `validBrowserSessionIds` 并按唯一 `sessionId`/`userId` 通过 `json_each` 批量预取会话有效性、用户信息、Work 所属 Agent/PA 绑定及会话参与者，保持失效会话 `close(1008)` 与权限语义完全等价；在 `notification-parity.test.ts:346-372` 断言 `R = 3` 与 `R = 25` 在 `message.delta`、`message.created`、`agent.work.updated` 上 SQL 语句数严格恒等。 | `closed` @ `d1d71712f8ecd2b296e96311b6b4ba34440710a3`（Stage 4 Closure Reviewer 核实权限等价性与 `@nano/im-server` 84 文件 / 531 项测试全绿）。 |

## 流程收口

- 重要目标和关键设计覆盖：`motivation.md` 全部验收场景（本仓五端双向防漏门禁、单源 TS→Swift/Rust 协议契约生成与禁默认兜底、外部对端入站 vs owner 外发镜像区分及未读修复、`notification_hint` 统一投射与双事件幂等、已读/静音三端总角标同步、Desktop 抑制非权限 Work HTTP 反查且保持 >16MB 本机轨迹直读、分层并行 CI 零增时）均已落地并验证。
- 开放问题 / pending / inconclusive：无（0 open，0 pending，0 inconclusive）。
- 最终 delta 校对：独立 `change-code-review` 校对 [`specs/im/web-chat-ux.md`](specs/im/web-chat-ux.md)、[`specs/im/ios-client.md`](specs/im/ios-client.md)、[`specs/im/desktop-client.md`](specs/im/desktop-client.md) 均为 `clean`，已原样归并至 `docs/specs/im/`。
- 版本变化后保留 / 补验的判断与依据：Round 1（`43d69477b`）全端构建与测试通过；Round 2（`d1d71712f`）针对修改涉及的 iOS、Desktop、`im-server` 与 Python 契约门禁全部实跑复验并经独立复审关闭全部 findings；归档提交仅移动文档与归并已校对 spec，原审查结论有效保留。
- 测试资源回收结果：`NanoIMTests` 使用的临时 DerivedData 目录已移除，iOS Simulator `1CE31893-672F-495A-B2B5-3ACF39A7A257` 已核实 `Shutdown`（`simctl list devices booted` 为空），无常驻后台进程或 `.e2e-runtime` 残留。
- 交付范围与剩余事项：归档 `refactor-800-multi-platform-parity` 并推送分支创建面向 `develop` 的 PR；按项目规则在 PR 合入前保留开发 worktree `/Users/czj/.t3/worktrees/nano-multiagent/unit-refactor-800-multi-a6e8ec2c954be970`。
