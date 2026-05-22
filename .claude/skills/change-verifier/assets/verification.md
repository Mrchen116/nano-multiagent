<!--
模板说明（定稿后删除本块）

验证实现是否匹配 spec / design / tasks。读代码核对，只读 + 报告，不修不改。
三维：Completeness（task 完成 + spec 覆盖）/ Correctness（实现 ↔ spec）/ Coherence（实现 ↔ design）。
问题分级：CRITICAL（缺实现 / 未完成 task）> WARNING（偏离 spec/design / 缺测试）> SUGGESTION（模式不一致 / 小改进）。
每条问题带可执行建议 + file:line。有 CRITICAL 时不要建议提 PR。
-->

# Verification Report: <unit_id>

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | X/Y |
| Correctness | X/Y |
| Coherence | Followed / 有偏离 |

<!-- 结尾消息三选一：
  All checks passed. Ready for PR.
  X critical issue(s) found. Fix before PR.
  No critical issues. Y warning(s) to consider. Ready for PR (with noted improvements).
-->

## Completeness

<!-- §2 -->
- Tasks: N/N complete（或 X/N，逐条列未完成项）
- Spec 覆盖：哪些 requirement 有实现 / 哪些缺失

## Correctness

<!-- §3：逐 requirement / scenario 的实现映射 + 测试覆盖。 -->

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| <从 spec 复制> | <file:line 或 missing> | 有 / 无 | covered / 偏离 / 缺实现 |

## Coherence

<!-- §4：design 关键决策遵守情况 + 代码模式一致性。无 design.md 则注明跳过。 -->

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| <从 design 复制> | 是 / 否 |  |

## Issues

<!-- 按 CRITICAL → WARNING → SUGGESTION 排。每条带可执行建议 + file:line。 -->

### CRITICAL（提 PR 前必须修）
- <问题 + file:line + 怎么改>

### WARNING（应该修）
- <问题 + file:line + 怎么改>

### SUGGESTION（可以修）
- <问题 + file:line + 怎么改>
