# feat-451-M6: fix-pending-live-preserve-lifetime — Tasks

> 对齐: ../design.md Changelog 2026-07-02 / Milestones feat-451-M6

## 目标

修复 Round 5 focused code-review finding：`pendingLiveMessageIdsRef` 里的 live message id 只能为紧随其后的 history reset 提供一次性保留，不能让该 row 在后续 REST history 仍不返回时永久免疫。

## 退出标准

- [ ] `[worker]` pending live id 被紧随其后的 history reset 使用/考虑后立即清理。
- [ ] `[worker]` 后续 REST history 仍不返回该 row 时，active pane 与服务端 history 收敛并移除该 row。
- [ ] `[worker]` 保持 M5 行为：suppressed synthetic `:relay:` mirror row 会在 refreshed history 中被移除。
- [ ] `[worker]` 保持 M4 行为：切换期间 active conversation live event 先于 history 到达不丢，紧随其后的 history response 不覆盖该 live row。
- [ ] `[worker]` 外会话 event 仍不污染 active pane。
- [ ] `[worker]` 补充回归测试覆盖 pending live id 使用一次后清理、后续 reset 收敛，以及 M4/M5 关键回归。
- [ ] `[worker]` `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx` 通过。
- [ ] `[worker]` `cd src/IM/frontend && npm run test` 通过。
- [ ] `[worker]` `cd src/IM/frontend && npx tsc -b` 通过。

## 测试策略

- 被测行为（来自退出标准）：
  - same-conversation `message.created` 在 active messages query fetching 期间到达时，可以保留过紧随其后的 history reset。
  - 该 pending live id 在这次 reset 使用/考虑后必须清理；第二次 REST history 仍不返回该 row 时，active pane 必须移除它。
  - suppressed synthetic relay mirror reset 后仍会被移除。
  - active conversation live-before-history row 仍在第一次 reset 后保留；外会话 event 不污染 active pane。
- 已有测试在：`src/IM/frontend/src/features/chat/v2/chat-workspace.integration.test.tsx`（扩展 active pane reset/live/refetch 回归）。
- 落层/目录/marker：Vitest integration（`src/IM/frontend/src/features/chat/v2/chat-workspace.integration.test.tsx`），marker：无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：前端真实浏览器 spot check 记录；不提交临时脚本。

## 前端 UI 状态矩阵

用户路径分类：`critical-path` + `bug-regression`。

| 状态 | 覆盖计划 |
|---|---|
| default | 第一次 reset 保留 raced live row；后续 reset 收敛移除未返回 row |
| loading | active messages query fetching 期间 same-conversation live row 到达并渲染 |
| empty | c2 history 可为空但第一次 reset 保留 live row；后续空 history 可移除 |
| error | N/A，本 milestone 不改错误 UI |
| disabled | N/A，本 milestone 不改 controls |
| submitting | N/A，本 milestone 不改 send mutation |
| permission denied | N/A，本 milestone 不改权限卡 |
| long content | N/A，本 milestone 不改文本布局 |
| missing/nullable data | reducer conversation binding / pending preserve set 清理覆盖 |
| mobile viewport | 真实浏览器 spot check active pane 渲染 |
| desktop viewport | 真实浏览器 spot check active pane 渲染 |
| dark mode（如项目支持） | N/A，项目当前无 dark mode scope |

## 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| pending live id 永久保留导致 active pane 不收敛 | integration regression | 是 |
| suppressed relay mirror reset 后残留 | 既有 M5 regression 保持 + targeted rerun | 是 |
| live-before-history row 被第一次 history reset 误删 | 既有 M4 regression 保持 + targeted rerun | 是 |
| 外会话 event 污染 active pane | 既有 M3/M4 regression 保持 + targeted rerun | 是 |
| active pane 真实入口仍渲染 | 浏览器 spot check + 测试证据 | 临时证据 |

## Roadpoints

### R1 — Pending live preserve 一次性生命周期

- 状态: TODO
- 步骤:
  - C1: 补 pending live id 第一次 reset 保留、第二次 reset 收敛移除的红测。
  - C2: 调整 reset effect，在每次 reset 构造 preserve set 后清空已考虑的 pending ids，而不是只删除 REST returned ids。
  - C3: 更新 tasks/progress，记录窄测、全测、类型检查和浏览器 spot check 证据。
- 验证:
  - `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx -t "clears pending live preserve ids after one history reset"`
  - `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx`
  - `cd src/IM/frontend && npm run test`
  - `cd src/IM/frontend && npx tsc -b`
