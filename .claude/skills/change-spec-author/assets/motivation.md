<!--
模板说明（定稿后删除本块）

用于 refactor / perf。回答：为什么改 / 改成什么样 / 不改的后果。
- perf：必须有当前 benchmark 数据 + 目标值。
- refactor：必须有迁移策略 + 行为不变保证。

填写顺序：先粘原始诉求 → 交互澄清 → 才能写痛点/目标。

镜头：refactor / perf 是面向内部的变更，【用户侧验收标准】用"回归基线"镜头写——
"现在用户是这样用的，变更后要保持一致"，写的是既有行为快照 + 不变性，不是新东西。
结构：按 ### Requirement 分组、每组挂 ≥1 个 #### Scenario（WHEN 走既有行为 / THEN 与变更前一致）。
这一段会被 change-reviewer 当作回归清单逐 Scenario 走，只写用户可观察的；
实现层目标（新结构 / benchmark 内部指标 / 迁移正确性）归 design.md，不进这里。
-->

# <type-id>: <短描述>

## Relations

- Depends on:
- Blocks:
- Related:

## 原始诉求

<!-- 提出人的原话，原样保留。 -->

## 澄清记录

- Q1:
  A:

## 现状痛点

<!-- 可证据化。perf 必须给 benchmark 数据。 -->

## 目标状态

## 用户侧验收标准（不变性）

<!-- 回归基线 + 不变性。先用自由叙事写"现在用户是这样用的"（既有行为快照、回归面），
     再用 Requirement / Scenario 结构列不变性：每个 #### Scenario 的 WHEN 走一条既有行为，
     THEN 写"与变更前一致"。只写用户可观察的；reviewer 照此逐 Scenario 走回归。
     每个 Requirement 至少一个 Scenario。若确实无用户可观察表面，显式写"无"并举证。 -->

### Requirement: <既有能力描述>

#### Scenario: <既有行为名>
- **WHEN** <用户走既有操作 X>
- **THEN** <结果与变更前一致（描述用户可观察的那个结果）>

## 影响范围

<!-- 哪些模块/接口/调用方/数据会变。 -->

## 迁移与回滚策略

<!-- refactor: 行为不变如何保证；perf: 降级路径与回滚条件。 -->
