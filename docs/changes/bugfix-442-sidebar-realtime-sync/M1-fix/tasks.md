# bugfix-442-M1 — 侧边栏会话列表实时同步

## 目标

修 fix.md 现象段的三个症状（同一根因）：收到 agent 新消息时侧边栏会话列表不刷新
（不标未读 / preview 与时间停在旧值 / 不重排），以及读消息后未读角标不清零。
根因见 fix.md：v2 用户维消息流只接 node/agent status 事件、不驱动会话列表刷新；
读消息也只刷新消息流、不刷新会话列表。

## 退出标准

- 收到 `message.sent` / `message_created` / `relay.completed` 事件时，侧边栏会话列表
  重新拉取，未读角标、preview、时间、排序随后端真值更新。
- 进入会话读消息后，该会话未读角标清零。
- 不破坏既有 toast、会话内气泡流（openChatStream）、node/agent 状态实时更新。
- 真实浏览器走一遍 fix.md 原始症状路径：修前能复现、修后不复现。

## 测试策略

- 类型：`bug-regression` + `critical-path`（实时消息 → 侧边栏，历史 bug）。
- 复用现有 `chat-workspace.integration.test.tsx` 框架（`capturedStatusHandler` 注入
  用户维流事件 + `fetchSpy.sent` 计数 GET）。
  - 测试 A：注入 `message.sent` 事件 → 断言 `/conversations` 被重新 GET（≥2 次）。
  - 测试 B：进入带消息的会话 → 断言读后 `/conversations` 被重新 GET（≥2 次）。
- 不为单个 bug 引入新 E2E 基础设施；用现有 integration 体系做 regression 保护。
- 真实浏览器验收（§6.0 fix.md 验证段）：真栈跑 fix.md 原始症状路径。

## UI 状态矩阵（会话列表侧边栏）

- default：有未读 / 无未读两态 — 覆盖
- 收到新消息（未打开该会话）：未读角标增加、preview/时间更新、重排 — 覆盖
- 收到新消息（正打开该会话）：preview 更新、不应残留未读（读态）— 覆盖
- empty / loading / error：本 fix 不改这些态，沿用现有 — N/A（不回归）
- mobile / desktop viewport：侧边栏布局本 fix 不改 — N/A
- dark mode：不涉及 — N/A

## 用户路径分类

`bug-regression`（历史 bug 修复）+ `critical-path`（实时消息进入会话列表）。

## 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| 收到新消息侧边栏不刷新 | integration 注入事件 + 断言重新拉取 | 是 |
| 读后未读不清零 | integration 进入会话 + 断言重新拉取 | 是 |
| 真实端到端实时表现 | 真栈浏览器走原始症状路径 | 否（fix.md 验证段记录） |

## Roadpoints

- R1（DONE）：v2 侧边栏消费消息流 + 读后刷新
  - C1：integration 红测（注入 message.sent → conversations 重拉；读会话 → 重拉）
  - C2：chat-workspace-page.tsx 加去抖刷新（流事件触发）+ 读后刷新 effect
  - C3：progress.md 证据 + 回填 fix.md 修复/验证段
