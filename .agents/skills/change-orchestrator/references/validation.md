# 审查输入、复验与收口

按 [能力组合](../../../../docs/development/skill-composition.md) 选问题和执行者。冻结本次受审版本，提供目标/要求、unit 与 worktree、branch、`validated_at`（实际受审 tree）、`executed_base`（与目标集成分支的 merge-base）、本次问题/能力及必要证据、授权和输出位置。独立普通 diff review 可含明确列出的 dirty 范围；unit 交付审查使用冻结提交。

复验附实际 delta、历史问题与原证据。full 覆盖本次全部所选问题；patch/delta 检查新增影响；closure 定向关闭；corrected-delta 校对最终契约。只有证据不足或影响无法界定时扩大，不以新提交号机械重审。

## 统一结果

使用 [review 模板](../assets/review.md)，删除不适用占位；各能力返回自身判断，owner 串行归集并保留执行者和原结论。只有被派发独占报告范围时 reviewer 才直接写；不要求审查者提交、rebase 或 push 报告，不让并行任务争抢同一文件。

每个问题有版本/范围、判断、决定性证据及限制。一个缺陷只维护一个 ID，其他能力引用；修复者追加 resolution，独立复验者提供关闭依据。聚合输出不得把未验证改成通过，或把作者自检改成独立审查。

- pending：该检查仍在运行，流程等待结果，不另派人对账。
- inconclusive：必要观察无法取得，明确缺口，相关目标不能通过。
- fail：实际缺陷或结果不满足目标，交 owner 判真与修复。
- pass：本问题在声明范围内有充分证据。
- retained：沿用旧结论，给 prior locator、原版本及未失效理由；不是重新执行。

记录 confirmed / plausible 等证据状态与严重度，二者不能混用。缺实现、关键路径失败、违反边界、实质契约/设计偏离以及妨碍目标的体验问题阻塞交付；可选改进不阻断。未知条件写明，不把假设直接报 confirmed。范围外发现保留关联与因果未知，不自动扩大需求；需要外部 issue 或操作时仍遵循当前授权。

## 修复与版本有效性

主 Agent 判真并合并同因问题，记录 pre_fix_head 后集中修复，不新派或唤醒修复 worker。独立复验只检查实际变化与必要关联；若反馈说明原判据或整体体验有误，重新检查受影响判断，不能只清掉旧 findings。

可信测试/构建/运行证据可共享，必要关键条件仍独立观察。记录版本、方法、结果与 locator。代码未变只能证明对象未变，不能把从未观察的体验变成 pass。格式、报告或无关集成增量不触发唤醒；owner 记录 retained 依据。

需求/关键设计变化交回 author；权限、持久化、迁移、协议、跨进程、共享运行时或并发变化可能使整条链失效，按影响扩大。final sync 和冲突解决同样判断范围；保留原 `executed_base` / `validated_at`，另记最终 `effective_base` / `effective_through`。

收口时核目标和关键设计覆盖、阻塞问题关闭、必要证据充分、最终版本有效。最终 delta 与实现/测试由独立代码审查核对；未改已审部分保留，无 delta 不空跑。所有适用问题完成后才能交付；不另开 verifier 汇总一遍。

同一 issue 经 5 个有效修复轮或 unit 经 7 个有效验收轮仍未收口，保留现场交人；上限不是目标，不为可选润色循环。历史报告按 [接手规则](../../../../docs/development/skill-composition.md#其他流程与历史接手) 保留。
