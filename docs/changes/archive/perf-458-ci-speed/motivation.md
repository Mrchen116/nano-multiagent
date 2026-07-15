# perf-458: CI 提速

## Relations

- 无

## 原始诉求

> 我发现本仓的CI非常慢，我希望压缩到1分钟以内。你帮我分析下

> [$change-spec-author](/Users/czj/Repos/nano-multiagent/.claude/skills/change-spec-author/SKILL.md) 开始。不用说特别严格。只要把简单合理的方案做上。大幅提升了就行。难的，增加复杂度的方案不需要。

## 澄清记录

- Q1: 性能目标是否定义为“常规代码 PR 的 CI 从约 3分30秒降到 90 秒以内，尽量接近 1 分钟，但不作为硬 SLA；GitHub 排队时间不计入”？
  A(原话): 对
  Agent 解读: 以不含 GitHub 排队时间的常规成功 CI 执行时长为口径；90 秒是验收上限，1 分钟是优化方向而非硬性承诺。
- Q2: 剩余成功标准、范围边界与非目标是否由 Agent 按推荐直接收口？
  A(原话): 不用问我了，直接自己推进，推到design完成。
  Agent 解读: 后续不再逐项打断用户；按“简单、合理、显著提速、不增加复杂度”的原始边界自主完成 motivation 与 design。

## 现状痛点

仓库贡献者每次提交代码或更新 PR 后，都要等待 Python 与 Frontend 两组 required checks。两组检查并行，但总反馈时间由较慢的 Python 检查决定。

2026-07-10 对近期成功 GitHub Actions run 的测量结果：

| 检查 | 当前耗时 | 主要耗时 |
|---|---:|---:|
| Python checks | 3分31秒–3分52秒 | pytest 3分03秒–3分20秒；依赖安装 18–25 秒 |
| Frontend checks | 1分02秒–1分11秒 | vitest 48–52 秒 |
| 完整 required checks | 3分34秒–3分55秒 | 由 Python checks 决定 |

代表性基线：[GitHub Actions run 29086182596](https://github.com/Mrchen116/nano-multiagent/actions/runs/29086182596)，完整 required checks 为 3分34秒。

本地同一套非 e2e Python 测试包含约 3,445 个用例：串行执行 141.61 秒；以 4 个 worker 执行为 52.73 秒，以 8 个 worker 执行为 42.35 秒，两次并行基准均通过。duration profile 同时发现少数测试将生产超时、固定等待或大规模重复 I/O 直接计入每次 CI，贡献了约 44 秒可避免的串行等待。

当前反馈周期已经长到会打断开发节奏；即使只是确认一个小改动，贡献者也通常要等待三分半以上。继续随测试数量自然增长，会让每次改动的验证成本进一步上升。

## 目标状态

- 常规代码 PR 的一次成功 CI，从 runner 开始执行到全部 required checks 完成为止，不超过 90 秒，并尽量接近 1 分钟。
- 相比当前 3分34秒–3分55秒基线取得大幅、稳定且可复测的改善。
- 保留现有 required checks 所提供的质量信号；不能通过删除有效测试、忽略失败或降低门禁范围换取速度。
- 优先采用简单、易理解、易维护的优化；达到目标后即停止，不为追求更低数字引入复杂基础设施或复杂调度体系。
- GitHub 托管 runner 的外部排队时间不计入目标，也不承诺包含排队时间的硬 SLA。

## 用户侧验收标准（不变性）

仓库贡献者仍按现有方式提交代码和查看 PR checks；本次优化只缩短等待，不改变产品功能、提交方式或 CI 成败语义。

### Requirement: 常规代码 PR 获得显著更快的完整反馈

#### Scenario: 合法代码变更通过全部门禁

- **GIVEN** GitHub 托管 runner 已开始执行 CI，且变更能够通过现有 required checks
- **WHEN** 贡献者提交常规代码 PR 并等待检查完成
- **THEN** 全部 required checks 在 90 秒内完成
- **AND** 贡献者仍能看到 Python 与 Frontend 检查的最终成功结果

### Requirement: CI 质量信号保持不变

#### Scenario: 代码违反现有检查要求

- **WHEN** 贡献者提交会触发现有格式、静态检查或测试失败的变更
- **THEN** CI 仍显示失败并阻止该变更被当作通过
- **AND** 贡献者仍能从检查结果判断失败属于哪一类门禁

#### Scenario: 产品既有行为回归

- **WHEN** 优化后的 CI 验证现有产品代码
- **THEN** 用户在 IM、Gateway、Coding CLI 与 agent 内核中的既有可观察行为与优化前一致

### Requirement: 优化后的门禁不增加日常运维负担

#### Scenario: 贡献者重跑 CI

- **WHEN** 贡献者在普通 GitHub 托管 runner 上重新运行检查
- **THEN** 检查无需人工准备专用机器或额外服务即可完成
- **AND** 使用方式与当前 PR checks 一致

## 影响范围

- 直接影响仓库贡献者和维护者等待 PR checks 的时间。
- 影响仓库 CI 门禁及其执行的现有测试，但不引入新的产品功能。
- 不改变 IM、Gateway、Coding CLI、agent 内核的用户行为和对外契约。

## 范围与非目标

本期范围：

- 优化当前 required checks 的执行时间。
- 清理现有测试中简单、明确、可避免的固定等待或重复重负载。
- 在不降低质量信号的前提下使用低复杂度的并行或缓存能力。
- 用同一套现有门禁对优化前后进行 benchmark 对比。

非目标：

- 不保证包含 GitHub runner 排队时间在内的 60 秒硬 SLA。
- 不采购或维护 self-hosted runner、付费大规格 runner 等专用基础设施。
- 不引入复杂的跨机器调度、动态测试选择平台或长期维护成本高的 CI 系统。
- 不通过删除仍有价值的测试、跳过失败、降低覆盖范围或放宽检查规则换取速度。
- 不在本 unit 内优化当前 required checks 未运行的 e2e 套件。

## 迁移与回滚策略

- 优化按可独立测量的小步推进，每一步都对比完整 required checks 的通过情况和耗时。
- 若某项优化引入 flaky、遗漏现有失败信号、需要额外人工运维，或没有带来可观测收益，则撤回该项并保留其他已证明有效的简单优化。
- 回滚后仍可恢复到当前 Python 与 Frontend 两组 required checks 的既有执行方式，不影响产品运行时。
