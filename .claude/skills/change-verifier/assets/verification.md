<!--
模板说明（定稿后删除本块）

验证实现是否匹配 spec / design / tasks。读代码核对，只读 + 报告，不修不改。
三维：Completeness（task 完成 + spec 覆盖）/ Correctness（实现 ↔ spec）/ Coherence（实现 ↔ design）。
问题分级：CRITICAL（严重阻塞）> WARNING（普通阻塞）> SUGGESTION（非阻塞）。
每条问题带可执行建议 + file:line。CRITICAL / WARNING 都为 0 才能建议提 PR。
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
  X critical issue(s), Y warning(s) found. Fix before PR.
-->

## Completeness

<!-- §2 -->
- Tasks: N/N complete（或 X/N，逐条列未完成项）
- Spec 覆盖：哪些 requirement 有实现 / 哪些缺失
- Prototype / Reference 覆盖：若 design.md 有前端原型，逐项说明 must-match 行是否有 milestone 投影、progress/acceptance 证据和 durable evidence；无原型写 N/A

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

### Prototype / Reference Contract

<!-- 仅 design.md 有前端原型 / reference 时填写；否则写 N/A。verifier 只核 explicit contract 与证据链，不做主观视觉评分。 -->

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| <must-match 行> | <退出标准 / tasks.md> | <file:line 或 missing> | <progress/acceptance 证据路径> | covered / warning / critical |

## Issues

<!-- 按 CRITICAL → WARNING → SUGGESTION 排。每条带可执行建议 + file:line。 -->

### CRITICAL（提 PR 前必须修）
- <问题 + file:line + 怎么改>

### WARNING（提 PR 前必须修）
- <问题 + file:line + 怎么改>

### SUGGESTION（可以修）
- <问题 + file:line + 怎么改>

<!-- 仅 verification_mode=corrected-delta 时填写；复验时更新本段，不追加 Attempt 历史。 -->

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| <path + Requirement / Scenario> | <file:line> | <test file:line or N/A> | aligned / delta-mismatch / implementation-mismatch |

### Uncovered Observable Behavior

None / <unit diff 中未被 delta 覆盖的行为及证据>

Outcome: aligned | delta-mismatch | implementation-mismatch
