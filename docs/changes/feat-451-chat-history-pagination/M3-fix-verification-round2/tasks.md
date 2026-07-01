# feat-451-M3: fix-verification-round2 — Tasks

> 对齐: ../design.md Changelog 2026-07-01 / Milestones feat-451-M3

## 目标

关闭 round 2 verifier 的 critical 会话切换消息泄漏，并修复 code review confirmed 的两个滚动正确性问题：发送失败不残留强制滚底 flag；历史 anchor 恢复后刷新 near-bottom，后续 live 消息尊重用户正在阅读历史的位置。

## 退出标准

- [x] `[verifier]` 切换会话时，新会话历史请求未返回前不显示旧会话消息。
- [x] `[worker]` 共享 user stream 事件不会在 reducer 尚未绑定当前会话时污染消息列表。
- [x] `[worker]` 发送失败或没有消息追加时不残留强制滚底 flag；成功发送 / 本地消息 append 仍滚底。
- [x] `[worker]` 恢复历史 anchor 后重新计算 near-bottom；后续 live arrival 不错误拉到底部。
- [x] `[worker]` 对以上行为补充回归测试。
- [x] `[worker]` `npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx` 通过。
- [x] `[worker]` `npm run test` 与 `npx tsc -b` 在 `src/IM/frontend` 通过。
- [x] `[worker]` 真浏览器 spot check 覆盖切换会话 / 滚动行为，记录 URL / viewport / console / network 观察。

## 测试策略

- 被测行为（来自退出标准）：
  - c1 切到 c2 且 c2 history response 延迟时，c2 heading 下不显示 c1 消息。
  - active conversation 之外的共享 user stream chat event 不进入当前 pane；reducer 未绑定当前会话时也不能被外会话事件 seed。
  - `onSend` 没有追加消息或抛错后，下一条外部消息不会被 stale `forceScrollToBottomRef` 拉到底。
  - history prepend 恢复 anchor 后更新 `nearBottomRef`；用户处在历史阅读位置时，后续 live message arrival 不滚到底。
- 已有测试在：
  - `src/IM/frontend/src/features/chat/v2/chat-workspace.integration.test.tsx`（扩展会话切换和共享 user stream active-conversation guard）
  - `src/IM/frontend/src/features/chat/v2/components/message-pane.test.tsx`（扩展发送失败滚底 flag、anchor restore near-bottom）
  - 不新建测试文件：本 milestone 是现有 chat workspace / MessagePane 行为回归，按 TESTING_GUIDE 优先扩相关文件。
- 落层/目录/marker：Vitest component/integration（`src/IM/frontend/src/features/chat/v2/**`），marker：无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：worktree ephemeral IM + Vite + Playwright 真浏览器 spot check 记录；若产生截图只记录路径，不提交。

## 前端 UI 状态矩阵

| 状态 | 覆盖计划 |
|---|---|
| default | active conversation messages render regression |
| loading | delayed c2 history response while heading already switched |
| empty | c2 pending/empty state must not show c1 messages |
| error | send failure/no append does not leave force-scroll state |
| disabled | N/A，本 milestone 不改 disabled controls |
| submitting | failed `onSend` / no append path covered |
| permission denied | N/A，本 milestone 不改权限卡 |
| long content | N/A，本 milestone 不改文本布局 |
| missing/nullable data | reducer null/unbound state and out-of-conversation stream event guard |
| mobile viewport | browser spot check covers basic chat route at mobile width if services run |
| desktop viewport | browser spot check covers conversation switch and scroll behavior |
| dark mode（如项目支持） | N/A，项目当前无 dark mode scope |

## 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| 会话切换时旧消息显示在新 heading 下 | integration regression + 浏览器 spot check | 是 |
| 外会话共享流事件污染当前 pane | integration regression | 是 |
| stale force-scroll flag 在发送失败后拉底 | component regression | 是 |
| anchor restore 后 near-bottom 状态过旧 | component regression | 是 |

## Roadpoints

### R1 — 会话切换与共享流隔离

- 状态: DONE
- 步骤:
  - C1: 为 delayed c2 history / old c1 message leak 与 out-of-conversation shared stream event 补红测。
  - C2: 让 MessagePane 只接收与 active conversation 匹配的 `streamState.messages`；共享 user stream 只 dispatch active conversation chat event。
  - C3: 记录根因、测试、回滚。
- 验证:
  - `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx`
  - `cd src/IM/frontend && npx tsc -b`

### R2 — 滚动状态 correctness 与门禁验收

- 状态: DONE
- 步骤:
  - C1: 为 send failure/no append stale force-scroll、anchor restore 后 live arrival 不拉底补红测。
  - C2: 调整 MessagePane force-scroll 生命周期与 restore anchor 后 near-bottom 计算；必要时稳定 `onLoadOlder` callback。
  - C3: 跑完整前端门禁和真浏览器 spot check，记录 evidence。
- 验证:
  - `cd src/IM/frontend && npm run test -- src/features/chat/v2/components/message-pane.test.tsx`
  - `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx`
  - `cd src/IM/frontend && npm run test`
  - `cd src/IM/frontend && npx tsc -b`
  - worktree ephemeral IM + Vite 真浏览器 spot check，结束清理 PID。
