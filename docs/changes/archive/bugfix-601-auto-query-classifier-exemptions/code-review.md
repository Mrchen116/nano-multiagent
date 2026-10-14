# bugfix-601: Code Review

## Review scope

- Base / 审查时 HEAD：`290652ada2bf5fafbd4ac9f27a1514680ff78ca9`。
- Review mode：`full`。
- Reviewable tree：`codex/auto-query-exemptions` 的本次暂存/工作树 diff；尚未创建实施 commit。
- 产品文件：`packages/dsh-integration/src/policy/approval.ts`。
- 测试文件：`packages/dsh-integration/tests/approval.test.ts`。
- 文档文件：本 unit 的 `incident.md`、`design.md`、`specs/gateway/agent-capabilities.md` 及本记录。

## Round 1

- Reviewer：独立 `review_auto_queries`，`gpt-6.1-sol/high`，未参与实现，按 `change-code-review` 执行 full review。
- Findings：`[]`。9 种调用匹配、Nano/Auto 限定、downstream 拒绝优先、DSH 后置 guard 与原工具执行入口均已核对。
- Resolutions：无待修复项，无需 patch/closure 复审。
- validated_at：`290652ada2bf5fafbd4ac9f27a1514680ff78ca9` 加本次 6 文件暂存 diff（执行审查时尚未创建实施 commit）。
- executed_base：`290652ada2bf5fafbd4ac9f27a1514680ff78ca9`。
- effective_base：最终 fetch 后仍为 `290652ada2bf5fafbd4ac9f27a1514680ff78ca9`，无 main 增量。
- effective_through：本次审查的产品/测试内容；最终交付 commit 由 PR 记录。审查后仅追加 design 的实际测试结果与本审查记录，未改变代码、测试或需求，原审查结论保留。

## 验证与收尾状态

- 复用可信证据：先红 18 次审核请求、改后目标调用零审核；3 文件 14 项相关测试通过，Python non-E2E 56 项通过。
- Reviewer 独立执行暂存 diff 检查通过；主会话核对完整本地结果：build/typecheck、TypeScript 74 文件 273 项、docs、Ruff 均通过。
- 最终结论：Passed；无未解决 findings。

## 用户确认与归档收尾

2026-10-14，用户基于已展示的验证结果明确要求：“把 #351 和 #352 转正式合并”。据此确认交付并收尾，不补记未发生的真人亲手测试。

本轮仅归并已审查 delta、更新 canonical 入口计数、同步实际收尾状态及归档路径；产品和回归测试 blob 保持独立审查版本。主会话核对 canonical 与原 delta 一致，原 code review 和运行证据继续有效，不增加无实质变化的复审轮次。最终 effective_base/effective_through 由 PR 记录。

## 已合并更新能力的集成

合并前同步 main `d667bdb964c07e7d1ebe80bdbb0c5aaec0edb063`（PR #349）。唯一文本冲突为 Gateway 入口相邻两行计数；保留 Service Lifecycle 的更新/回退说明与 13 条 Requirement，同时保留本 unit 的 Agent Capabilities 24 条。

本 unit 的 approval.ts 与 approval.test.ts 保持独立审查 blob。main 的更新屏障/生命周期改动不改变本批 action 判定；沿用 downstream 拒绝优先和工具执行约束，集成后的相关回归及最终远端 CI 重新验证。最终 effective_base 更新为上述 main，实际结果及 head 见 PR。
