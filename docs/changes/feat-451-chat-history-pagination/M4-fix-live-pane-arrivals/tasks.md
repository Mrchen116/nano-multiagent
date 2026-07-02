# feat-451-M4: fix-live-pane-arrivals — Tasks

> 对齐: ../design.md Changelog 2026-07-02 / Milestones feat-451-M4

## 目标

关闭 round 3 blocking：打开聊天页时，同会话 live message 到达后 active message pane 必须渲染该消息，sidebar preview 与 open thread 保持一致；同时关闭 verifier W1：切换会话且新会话 history 尚未返回时，同会话 live event 不丢失，外会话 event 不污染当前 pane。

## 退出标准

- [ ] `[reviewer]` 开着聊天页时，同会话 live message 到达后 active message pane 渲染该消息，sidebar preview 与 open thread 保持一致。
- [ ] `[reviewer]` 用户正在历史位置时，同会话 live arrival 不跳到底部；用户在底部时跟底。
- [ ] `[worker]` 从 c1 切到 c2 且 c2 history 尚未绑定 reducer 时，c2 `message.created` 先到不丢失。
- [ ] `[worker]` 外会话 shared user stream event 仍不污染 active pane。
- [ ] `[worker]` 保持 M3 行为：切换会话时 history 未回来前不显示旧会话消息；发送失败、历史 anchor、near-bottom 行为不回退。
- [ ] `[worker]` 补充对应回归测试。
- [ ] `[worker]` `npm run test` 与 `npx tsc -b` 在 `src/IM/frontend` 通过。
- [ ] `[worker]` 使用隔离端口跑真浏览器 live-arrival evidence，并记录 bottom / off-bottom 行为、console/network 观察。

## 测试策略

- 被测行为（来自退出标准）：
  - 同会话 live message event 触发 conversations refetch 后，active pane 也必须包含该消息，防止 sidebar preview 更新但 pane 不更新。
  - c1 切到 c2、c2 history response 延迟时，c2 `message.created` 先于 history 到达也应出现在 c2 pane；之后 history resolve 不丢 live message、不显示 c1。
  - 外会话 event 在 reducer 未绑定或绑定其他会话时仍不得进入当前 pane。
  - MessagePane 既有 off-bottom / bottom-follow 策略继续由组件测试和真浏览器入口验证。
- 已有测试在：
  - `src/IM/frontend/src/features/chat/v2/chat-workspace.integration.test.tsx`（扩展 active pane live/refetch 与 conversation-switch live-before-history 回归）。
  - `src/IM/frontend/src/features/chat/v2/components/message-pane.test.tsx`（滚动策略已有覆盖；如真浏览器发现缺口再补）。
- 落层/目录/marker：Vitest component/integration（`src/IM/frontend/src/features/chat/v2/**`），marker：无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：worktree ephemeral IM + Vite + Playwright 真浏览器 live-arrival 运行记录；临时脚本/截图只记录路径或结论，不提交。

## 前端 UI 状态矩阵

用户路径分类：`critical-path` + `bug-regression`。

| 状态 | 覆盖计划 |
|---|---|
| default | active conversation live message render regression |
| loading | delayed c2 history response while c2 live event arrives |
| empty | c2 history pending/empty state must accept c2 live event without showing c1 |
| error | N/A，本 milestone 不改错误 UI；send failure 滚动 flag 用既有 M3 regression 保持 |
| disabled | N/A，本 milestone 不改 controls |
| submitting | N/A，本 milestone 不改 send mutation；既有 MessagePane tests 保持 |
| permission denied | N/A，本 milestone 不改权限卡 |
| long content | N/A，本 milestone 不改文本布局 |
| missing/nullable data | reducer conversation binding null/mismatch state covered |
| mobile viewport | 真浏览器 spot check 至少打开移动 viewport 确认 active pane可见 |
| desktop viewport | 真浏览器 off-bottom/bottom live-arrival evidence |
| dark mode（如项目支持） | N/A，项目当前无 dark mode scope |

## 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| sidebar preview 更新但 active pane 不更新 | integration regression + 真浏览器 live-arrival | 是 |
| 切换期间 active conversation live event 先于 history 到达被丢 | integration regression | 是 |
| 外会话 event 污染 active pane | 既有 M3 regression 保持 + targeted rerun | 是 |
| bottom/off-bottom 滚动策略回退 | 既有 MessagePane regression + 真浏览器 evidence | 是 + 临时证据 |

## Roadpoints

### R1 — Active conversation live event 不丢

- 状态: TODO
- 步骤:
  - C1: 补 round 3 blocking 与 verifier W1 红测。
  - C2: 在 workspace active conversation 状态边界修复 reducer 绑定 / live 合并 / history 合并。
  - C3: 记录根因、测试、真浏览器 evidence 和回滚。
- 验证:
  - `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx`
  - `cd src/IM/frontend && npm run test`
  - `cd src/IM/frontend && npx tsc -b`
  - isolated IM + Vite 真浏览器 live-arrival QA。
