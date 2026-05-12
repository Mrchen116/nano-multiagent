<!--
模板说明（定稿后删除本块）

每个 roadpoint 完成后实时追加。一个 roadpoint 一段。
重点记"为什么这么决定"和"凭什么相信改对了"，不重复代码本身。

【硬约束：Pause-on-design-issue】
实现期发现 design 偏差时，禁止悄悄绕过。worker 必须：
1. 立即暂停编码
2. 在本文加一段 [Design 修订] R<n>: X → Y（现状 / 新方案 / 原因）
3. 同步改 ../../design.md 正文；若影响后续 milestone，再追加 design.md 顶部 Changelog
4. 通知人/orchestrator 确认后再继续

phase-locked 不重要，知识同步重要。
-->

# <milestone_id> — Progress

## R1 — <短描述>

- Context: <为什么做这一步>
- Decision: <做了什么>
- Rationale: <为什么这么做>
- Evidence:
  - Tests: <测试结果>
  - Entry: <真实入口验证结果>
  - Frontend State Matrix: <default/loading/empty/error/mobile/long-content 等覆盖情况;非前端写 N/A>
  - Browser QA: <打开的 URL / 用户路径 / console error 检查 / network failure 检查;非前端写 N/A>
  - E2E/Regression: <E2E 或 regression 用例路径 + 命令 + 结果;不适用写 N/A 和原因>
  - Visual/Interaction: <截图/录屏路径、viewport、reference 对照结论;非前端写 N/A>
- Rollback: <如何回退>
- Commits: <hash 或 PR>

## R2 — ...
