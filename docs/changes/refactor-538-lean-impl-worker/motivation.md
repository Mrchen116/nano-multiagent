# refactor-538: 精简 change-impl-worker

## 原始诉求

> 当前的 change-impl-worker 的 skill 流程有点过重了。很慢。你帮我去分析之前的 session，真正用到了 change-impl-worker subagent 的。帮我分析这些 subagent 是不是做了很多赘余操作导致很慢。具体是哪些没意义操作，从而指导我 skill 的改造、流程简化。

随后用户要求：在独立 worktree 中改一版，改完补 spec，把分析作为 Markdown 放进 unit，并提 PR。

## 动机

`change-impl-worker` 把不同复杂度的工作都当作完整 milestone：固定工件、反复状态检查、拆分提交、完整回归和 worktree 生命周期会附着在只需定向收尾的小变更上。历史 session 表明，这些流程成本在小闭环中经常超过实现本身；详细证据见 [analysis.md](analysis.md)。

这不是要降低实质性改动的验收强度。真实入口、跨进程链路、用户可观察行为或高风险边界仍需要独立验收；要移除的是与改动风险无关的固定流程税。

## 目标状态

- 调度者按当前任务判断独立 worker 是否能带来足够的 ownership、隔离或实现/验证收益；不能时直接闭环。
- 不用分类表或行数阈值决定是否派 worker。
- 文档、基线、调试、测试复跑按风险和证据缺口触发，而不是按固定清单触发。
- 保留 worker 创建并清理自己 milestone worktree 的既有所有权，同时以共享锁串行 unit 分支集成。

## 用户侧验收标准

### Requirement: 小闭环不再承受完整 milestone 流程

#### Scenario: 直接闭环更合适

- **WHEN** 范围和所需验证已经清楚，且独立 worker 不会提高交付可靠性
- **THEN** 调度者在 unit worktree 直接完成、验证差异并独立关闭
- **AND THEN** 不派发 worker，也不创建 milestone 的 `tasks.md`、`progress.md` 或 worktree

### Requirement: 实质性交付仍保留质量边界

#### Scenario: 独立 worker 能提高交付可靠性

- **WHEN** 独立 owner、隔离现场、实现/验证探索或协调能帮助可靠交付
- **THEN** 调度者派发完整 `change-impl-worker` milestone
- **AND THEN** worker 完成必要验证、串行集成到 unit 分支，并按适用风险做独立关闭

## 范围与非目标

范围是 change workflow 的 skill、模板、流程文档和对应契约测试。不会修改产品运行时代码、产品 current spec 或部署契约。

本次不通过行数阈值或穷举分类决定流程；模型结合上下文作出判断。也不改变 `feat-537` 已确立的 worker 创建/拥有/清理 milestone worktree 责任。

## 回滚

这是文档与工作流约束变更。回滚本 PR 即可恢复旧路由和模板，不影响任何已创建的产品运行数据。
