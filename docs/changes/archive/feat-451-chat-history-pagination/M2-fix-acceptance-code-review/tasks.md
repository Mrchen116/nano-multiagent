# feat-451-M2: fix-acceptance-code-review — Tasks

> 对齐: ../design.md Changelog 2026-07-01 / Milestones feat-451-M2

## 目标

修复 round 1 acceptance 的 blocking/major 问题与 code review confirmed correctness findings：打开的聊天页必须实时显示同会话新消息；用户离底看历史时不被打扰、在底部时跟底；移动端长按菜单松手后仍可点 Copy/fork；历史分页切换会话、重复触发和未知 metadata 状态不产生错误 UI；copy 失败有用户可观察反馈。

## 退出标准

- [x] `[reviewer]` 开着聊天页时，同会话新消息可实时出现在 UI；用户看历史时不打扰，用户在底部时自动跟底。
- [x] `[reviewer]` 移动端长按菜单在松手后仍可选择 Copy/fork，不被浏览器原生长按菜单或选择层破坏。
- [x] `[worker]` 历史加载进行中切换会话不复用旧 anchor。
- [x] `[worker]` 重复 `onLoadOlder` / 同 cursor 请求被同步 guard 阻止。
- [x] `[worker]` 会话切换 / 初始 metadata 未知时不错误显示 `No earlier messages`。
- [x] `[worker]` Copy 失败有可观察处理或安全兜底，en/zh 文案同步。
- [x] `[worker]` 补桌面端 Enter 发送独立测试。
- [x] `[worker]` 最窄 Vitest、`npm run test`、`npx tsc -b` 通过。
- [x] `[worker]` 真服务 + 真浏览器验证 blocking/major 路径，并记录 URL / viewport / 关键观察 / console 和 network 结果。

## 测试策略

- 被测行为（来自退出标准）：
  - 当前会话通过真实用户流事件追加同会话新消息，并保持 MessagePane 的底部/离底滚动策略。
  - 历史加载中切换会话清空 anchor/loading refs；同 cursor 并发加载只发一次；history metadata 未知时不显示 no-more。
  - 移动端长按后 release 不关闭菜单，Copy/fork 可点击；长按抑制浏览器原生 contextmenu/文本选择。
  - clipboard 不存在或 rejected 时，菜单不让用户误判为复制成功，并显示可观察失败文案。
  - 桌面端 `isMobile=false`、无 Shift 的 Enter 发送并清空 composer。
- 已有测试在：
  - `src/IM/frontend/src/features/chat/v2/chat-workspace.integration.test.tsx`（扩展当前会话实时流、重复历史请求、metadata 未知状态）
  - `src/IM/frontend/src/features/chat/v2/components/message-pane.test.tsx`（扩展 anchor reset、长按 release/copy/fork/copy failure、desktop Enter）
  - 不新建测试文件：虽现有文件超软上限，但 M2 是修复既有行为，按 TESTING_GUIDE 优先扩相关文件，拆文件属于 verifier warning 的维护建议，不作为本修复主线。
- 落层/目录/marker：Vitest component/integration（`src/IM/frontend/src/features/chat/v2/**`），marker：无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：worktree ephemeral IM + Vite + Playwright 真浏览器运行记录；截图/临时脚本如生成则只记录路径，不提交。

## 前端 UI 状态矩阵

| 状态 | 覆盖计划 |
|---|---|
| default | MessagePane render + realtime append regression |
| loading | history loading anchor/reset tests |
| empty | initial / unknown history metadata 不显示 no-more；空消息不误显 no-more |
| error | copy failure inline/status feedback |
| disabled | fork pending/offline 既有行为保持；R2 spot check |
| submitting | desktop/mobile Enter send existing + new desktop Enter独立测试 |
| permission denied | N/A，本 milestone 不改权限卡 |
| long content | mobile menu long-press on message bubble; composer existing coverage保持 |
| missing/nullable data | history cursor null / metadata unknown tests |
| mobile viewport | 真浏览器 390x844 长按 Copy/fork、Enter send、history scroll |
| desktop viewport | 真浏览器 1366x900 realtime append、底部跟随、离底不打扰、right-click Copy、hover fork |
| dark mode（如项目支持） | N/A，项目当前无 dark mode scope |

## 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| open chat 不实时显示同会话新消息 | integration regression + 真服务真浏览器 API/WS 路径 | 是 |
| 离底不打扰 / 底部跟底 | component regression + 真浏览器观察 scroll / visible message | 是 |
| 历史加载并发/切换状态污染 | component/integration regression | 是 |
| 移动长按菜单 release 后消失、native context menu/selection 干扰 | component pointer/touch regression + 真移动 viewport | 是 |
| Copy 失败静默吞掉 | component regression + i18n 文案 | 是 |
| 桌面 Enter 独立发送 | component regression | 是 |

## Roadpoints

### R1 — 实时消息与历史分页状态正确性

- 状态: DONE
- 步骤:
  - C1: 为当前会话用户流事件追加、重复 `loadOlder` 同 cursor guard、会话切换 anchor reset、unknown metadata 空态补红测。
  - C2: 当前会话气泡更新改用共享用户流事件；增加同步 loading cursor guard；reset history refs / unknown metadata 状态。
  - C3: 记录根因、测试和回滚。
- 验证:
  - `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx`
  - `cd src/IM/frontend && npx tsc -b`

### R2 — 移动菜单、Copy 失败反馈、桌面 Enter 与浏览器验收

- 状态: DONE
- 步骤:
  - C1: 为 touch release 后菜单保持可点、Copy/fork 可选、copy failure、desktop Enter send 补红测。
  - C2: 修复移动端 pointer/touch 菜单生命周期与原生 contextmenu/selection 抑制；新增 copy failure 可见反馈；简化冗余滚底条件。
  - C3: 跑完整前端门禁和真浏览器验收，记录 evidence。
- 验证:
  - `cd src/IM/frontend && npm run test -- src/features/chat/v2/components/message-pane.test.tsx`
  - `cd src/IM/frontend && npm run test`
  - `cd src/IM/frontend && npx tsc -b`
  - worktree ephemeral IM + Vite 真浏览器 desktop/mobile 验收，结束清理 PID。
