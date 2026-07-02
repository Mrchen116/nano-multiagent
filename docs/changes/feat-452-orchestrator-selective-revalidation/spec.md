# feat-452: orchestrator selective revalidation

## Relations

- Related: refactor-403

## 原始需求

> change-orchestrator skill，每一轮都重新跑三道闸，有点受不了，太慢了，而且太消耗token了。这个问题我问了gpt 5.5 pro。他的分析如我粘贴的。你根据当前几个/Users/czj/Repos/nano-multiagent/.claude/skills中相关skill分析下他的说的，有问题再跟我对齐

> 好，开始改。

> ok，这次本身也是一个需求，帮我补一个spec，把我的需求和gpt pro的分析补进去。然后和你的修改一并commit

GPT Pro 分析原文见:

> /Users/czj/.codex/attachments/5f2646f5-9b03-4ad3-8490-66b7ac59b266/pasted-text.txt

GPT Pro 分析中的关键建议:

- 初验全量;fix 后按风险选择性复验;PR 前做收口确认。
- 验证结论可以继承,但必须有失效规则和 retained 依据。
- worker DONE 签收不能弱化,尤其 live-critical 必须先由 worker 自证到用户可见结果。
- reviewer 已有 Fast-lane,应成为 reviewer-fix 的默认轻量路径,而不是被 orchestrator 的全量复验规则架空。
- verifier 需要 targeted-closure / delta 模式;code review 需要 full / patch / closure 模式。
- 高风险 delta 必须升级 full 三闸,包括共享基础设施、协议、schema、持久化、并发、跨进程、build/deploy/runbook 等范围。
- PR body 应透明记录哪些闸是新验的、哪些结论是 retained 继承的。

## 澄清记录

- Q1: 这次是否按「四个 skill 都改、ledger 做轻量版、保留高风险 full 三闸」推进?
  A(原话): 好，开始改。
  Agent 解读: 用户认可按 GPT Pro 的方向调整,但不要引入重型持久化 ledger;以 orchestrator 运行态记录和 PR body 验证摘要承载 retained 依据。

- Q2: 这次是否需要补首文档并与 skill 修改一起提交?
  A(原话): ok，这次本身也是一个需求，帮我补一个spec，把我的需求和gpt pro的分析补进去。然后和你的修改一并commit
  Agent 解读: 本次 skill 调整需要作为独立变更单元留档,并和已完成的 skill 契约修改在同一个 commit 里提交。

## 用户场景

`change-orchestrator` 的使用者在跑一个 unit 时,常会遇到这样的循环:首轮 reviewer / verifier / code review 发现少量问题,fix worker 只改一处小范围代码,但下一轮仍重新跑完整 reviewer、完整 verifier、完整 code review。这个默认策略虽然保守,但对常见小修过重,会显著拉长交付时间并消耗大量 token。

使用者希望 orchestrator 更像一个技术负责人:首轮把三道闸跑全,之后每次 fix 先判断这次 delta 是否会推翻旧结论。未被影响的结论可以继承;被影响的闸才按 targeted / patch / closure / full 重新验证。这样小修能快速收敛,高风险改动仍会回到完整三闸。

使用者也需要保留信任边界:fix worker 不能自我验收;worker DONE / live-critical 签收不能被省;reviewer / verifier 越界写代码仍要作废;如果 orchestrator 无法解释为什么某道闸可以 retained,就必须升级完整复验。

最终,PR reviewer 应能从 PR body 看出本 unit 的验证状态:哪些闸 full 跑过,哪些闸 targeted / patch / closure 复验过,哪些闸 retained 继承,以及 retained 的依据是什么。

## 验收标准

### Requirement: 首轮验收仍保持完整三道闸

#### Scenario: 普通 full unit 首次进入验收
- **WHEN** 一个 full unit 的所有实现型 milestone 都已完成并进入首轮验收
- **THEN** orchestrator 仍派发 reviewer full、verifier full,并执行 code review full
- **AND** reviewer / verifier / code review 的职责边界与变更前一致

#### Scenario: lite 或零用户面 unit 首次进入验收
- **WHEN** 一个 lite unit 或明确无用户可观察变化的 unit 进入首轮验收
- **THEN** orchestrator 仍按 unit 类型跳过不适用的闸
- **AND** 不因为新增选择性复验机制而强行派发不适用的 reviewer 或 verifier

### Requirement: fix 后按失效范围选择性复验

#### Scenario: reviewer 用户面小修
- **GIVEN** 上一轮 reviewer 报告了用户可观察问题
- **WHEN** fix worker 完成的是小范围 UI、CLI、文案或状态修复
- **THEN** orchestrator 默认只要求 reviewer targeted/Fast-lane 复验相关 Scenario 或 issue
- **AND** 若 fix 产生源码 delta,code review 只审本次 patch
- **AND** 未被 delta 影响的 verifier 结论可以 retained,但必须记录继承依据

#### Scenario: verifier issue closure
- **GIVEN** 上一轮 verifier 报告 CRITICAL 或 WARNING
- **WHEN** fix worker 提交修复
- **THEN** orchestrator 可以要求 verifier targeted-closure 只验证上一轮问题是否关闭
- **AND** 若 fix 改变用户可观察行为,orchestrator 还会加派 reviewer targeted

#### Scenario: code review finding closure
- **GIVEN** 上一轮 code review 报告阻塞 finding
- **WHEN** fix worker 提交修复
- **THEN** orchestrator 可以只要求 code review closure 验证上一轮 finding 是否关闭
- **AND** 若修复 patch 非平凡,orchestrator 还会加跑 patch code review

### Requirement: 高风险 delta 强制完整复验

#### Scenario: fix 触及高风险范围
- **WHEN** fix delta 触及权限、持久化、schema、协议、跨进程、共享 runtime、事件总线、队列、并发、build、deployment 或 runbook 等高风险范围
- **THEN** orchestrator 升级为 full 三闸复验
- **AND** 不允许仅靠 retained 结论放行

#### Scenario: targeted 复验发现新副作用
- **WHEN** reviewer targeted/Fast-lane、verifier targeted-closure/delta 或 code review patch/closure 发现新的副作用、CRITICAL 或阻塞 finding
- **THEN** 本轮按有效失败处理
- **AND** 下一轮由 orchestrator 重新按 delta 风险选择复验范围,必要时升级 full 三闸或 escalate

#### Scenario: retained 依据无法说明
- **WHEN** orchestrator 无法说明某道闸的上一轮结论为什么未被当前 delta invalidate
- **THEN** 该闸不能 retained
- **AND** orchestrator 必须选择 targeted、delta、patch 或 full 复验

### Requirement: worker 签收和验收独立性不削弱

#### Scenario: worker DONE 证据不足
- **WHEN** fix worker 报 DONE 但缺少 issue-to-commit 对应、必要测试证据或 live-critical 用户可见证据
- **THEN** orchestrator 不进入 reviewer/verifier/code-review 复验
- **AND** 直接打回 worker 补齐证据

#### Scenario: reviewer 或 verifier 越界写代码
- **WHEN** reviewer 或 verifier 在验收轮中写了源码、测试或配置改动
- **THEN** orchestrator 仍作废该轮 verdict 并回滚越界改动
- **AND** 不因为选择性复验机制而接受验收 agent 顺手修出的代码

### Requirement: PR body 透明呈现验证状态

#### Scenario: 有 retained 闸的 PR
- **WHEN** unit 最终提 PR 且某些闸在末轮为 retained
- **THEN** PR body 包含 Validation Summary
- **AND** 每道闸列出最近一次有效模式、证据、validated head 或 diff range
- **AND** retained 闸写明继承依据,让 PR reviewer 能区分"已验且未失效"和"漏验"

#### Scenario: lite unit PR
- **WHEN** lite unit 提 PR
- **THEN** PR body 的 Validation Summary 明确 reviewer/verifier skipped 的原因
- **AND** code review 的最近一次有效模式和证据仍可见

## 范围与非目标

- 在范围:
  - 更新 `change-orchestrator` 的失败循环和复验选择规则。
  - 更新 `change-reviewer` 的 Fast-lane 触发契约。
  - 更新 `change-verifier` 的 `full / targeted-closure / delta` 模式契约。
  - 更新 `change-code-review` 的 `full / patch / closure` 模式契约。
  - 更新 orchestrator PR body 模板,加入 Validation Summary。
  - 保留 worker DONE 签收、live-critical 证据、reviewer/verifier 零写入、issue 指纹和轮次 cap。

- 非目标:
  - 不实现持久化数据库式 validation ledger。
  - 不改产品代码、agent runtime 或多 agent 调度工具。
  - 不改变 reviewer / verifier / code review 的职责边界。
  - 不降低高风险变更的验收强度。
