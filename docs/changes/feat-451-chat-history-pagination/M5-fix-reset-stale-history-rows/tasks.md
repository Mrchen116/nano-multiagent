# feat-451-M5: fix-reset-stale-history-rows — Tasks

> 对齐: ../design.md Changelog 2026-07-02 / Milestones feat-451-M5

## 目标

修复 Round 4 code-review confirmed correctness issue：历史 reset 必须收敛到服务端历史响应，不再保留同会话旧 state 中已被后端 suppress 的 synthetic `:relay:` mirror row；同时保留 M4 的切换期间 live-before-history 行为和外会话隔离。

## 退出标准

- [ ] `[worker]` history reset 不得保留同会话旧 state 中已不在服务端历史响应里的消息，例如后端 `list_messages` suppress 的 synthetic `:relay:` mirror row。
- [ ] `[worker]` active pane 在 history reset 后与服务端 history response 收敛。
- [ ] `[worker]` 保持 M4 行为：c1 -> c2 切换且 c2 history response 未返回时，c2 live event 先到不丢。
- [ ] `[worker]` 保持 M4 行为：随后 c2 history response 到达后，不覆盖/删除 history 尚未包含的 live row。
- [ ] `[worker]` 外会话 event 仍不污染 active pane。
- [ ] `[worker]` 补充 stale/suppressed row 被 reset 移除和 live-before-history row 仍保留的回归测试。
- [ ] `[worker]` `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx` 通过。
- [ ] `[worker]` `cd src/IM/frontend && npm run test` 通过。
- [ ] `[worker]` `cd src/IM/frontend && npx tsc -b` 通过。

## 测试策略

- 被测行为（来自退出标准）：
  - 同会话旧 state 中的 suppressed synthetic relay mirror row 不在 REST history reset 响应中时，active pane 必须移除它。
  - 切换到 active conversation 后，history pending 期间先到的 same-conversation live row 必须显示；history reset 后仍保留。
  - 外会话 shared user stream event 不得污染 active pane。
- 已有测试在：`src/IM/frontend/src/features/chat/v2/chat-workspace.integration.test.tsx`（扩展 active pane reset/live/refetch 回归）。
- 落层/目录/marker：Vitest integration（`src/IM/frontend/src/features/chat/v2/chat-workspace.integration.test.tsx`），marker：无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：前端真实浏览器 spot check 记录；不提交临时脚本。

## 前端 UI 状态矩阵

用户路径分类：`critical-path` + `bug-regression`。

| 状态 | 覆盖计划 |
|---|---|
| default | same-conversation history reset 后 active pane 收敛到服务端 rows |
| loading | c2 history 延迟期间 c2 live row 先到并渲染 |
| empty | c2 history 可为空但 live row 保留，不显示外会话内容 |
| error | N/A，本 milestone 不改错误 UI |
| disabled | N/A，本 milestone 不改 controls |
| submitting | N/A，本 milestone 不改 send mutation |
| permission denied | N/A，本 milestone 不改权限卡 |
| long content | N/A，本 milestone 不改文本布局 |
| missing/nullable data | reducer conversation binding / stale row pruning 覆盖 |
| mobile viewport | 真实浏览器 spot check active pane 渲染 |
| desktop viewport | 真实浏览器 spot check active pane 渲染 |
| dark mode（如项目支持） | N/A，项目当前无 dark mode scope |

## 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| suppressed relay mirror reset 后残留 | integration regression | 是 |
| live-before-history row 被 history reset 误删 | 既有 M4 regression 保持 + targeted rerun | 是 |
| 外会话 event 污染 active pane | 既有 M3/M4 regression 保持 + targeted rerun | 是 |
| active pane 真实入口显示 stale row 修复 | 浏览器 spot check + 测试证据 | 临时证据 |

## Roadpoints

### R1 — Reset 收敛并保留 pending live rows

- 状态: TODO
- 步骤:
  - C1: 补 suppressed synthetic relay mirror stale row 红测。
  - C2: 调整 `streamReducer` reset 合并策略，只保留 history response 后先到的 live/pending rows，不无条件回填旧 state rows。
  - C3: 更新 tasks/progress，记录窄测、全测、类型检查和浏览器 spot check 证据。
- 验证:
  - `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx`
  - `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx`
  - `cd src/IM/frontend && npm run test`
  - `cd src/IM/frontend && npx tsc -b`
