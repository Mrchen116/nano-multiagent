# refactor-538: 精简 change-impl-worker

## 原始诉求

> 当前的 change-impl-worker 的 skill 流程有点过重了。很慢。你帮我去分析之前的 session，真正用到了 change-impl-worker subagent 的。帮我分析这些 subagent 是不是做了很多赘余操作导致很慢。具体是哪些没意义操作，从而指导我 skill 的改造、流程简化。

随后用户要求：在独立 worktree 中改一版，改完补 spec，把分析作为 Markdown 放进 unit，并提 PR。

## 动机

这套流程原本让 orchestrator 保持全局调度、集成和门禁注意力，把 design 拆出的独立实现面交给 worker 专注完成并提高并行度。问题不在独立 owner 本身，而在 worker 内冗长的过程台账、反复状态检查、拆分提交和无信息的测试复跑；它们会让交接成本超过实现收益。详细证据见 [analysis.md](analysis.md)。

这不是要降低实质性改动的验收强度。真实入口、跨进程链路、用户可观察行为或高风险边界仍需要独立验收；要移除的是与改动风险无关的固定流程税。

## 目标状态

- design 已拆出的独立 milestone 交给 worker；未形成 milestone 的自包含小闭环才由调度者判断是否直接完成。
- 不用分类表或行数阈值决定是否派 worker。
- worker 固定留下极简 `tasks.md` / `progress.md`；文档内容、基线、调试和测试复跑仍按风险和证据缺口决定。
- 保留 worker 创建并清理自己 milestone worktree 的既有所有权，同时以共享锁串行 unit 分支集成。

## 用户侧验收标准

### Requirement: 小闭环不再承受完整 milestone 流程

#### Scenario: 直接闭环更合适

- **WHEN** 一个自包含闭环不属于已设计 milestone，且独立 worker 不会提高交付可靠性
- **THEN** 调度者在 unit worktree 直接完成、验证差异并独立关闭
- **AND THEN** 不派发 worker，也不创建 milestone 的 `tasks.md`、`progress.md` 或 worktree

### Requirement: 实质性交付仍保留质量边界

#### Scenario: 独立 worker 能提高交付可靠性

- **WHEN** 独立 owner、隔离现场、实现/验证探索或协调能帮助可靠交付
- **THEN** 调度者派发完整 `change-impl-worker` milestone
- **AND THEN** worker 创建两份短记录、完成必要验证、串行集成到 unit 分支，并按适用风险做独立关闭

## 范围与非目标

范围是 change workflow 的 skill、模板、流程文档和对应契约测试。不会修改产品运行时代码、产品 current spec 或部署契约。

本次不通过行数阈值或穷举分类决定流程；模型结合上下文作出判断。也不改变 `feat-537` 已确立的 worker 创建/拥有/清理 milestone worktree 责任。

## 回滚

这是文档与工作流约束变更。回滚本 PR 即可恢复旧路由和模板，不影响任何已创建的产品运行数据。
