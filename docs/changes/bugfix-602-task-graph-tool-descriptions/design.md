# bugfix-602: As-built Design

> 本文在实现及首轮真实验证后形成，描述实际落地；不代表已事前走设计门禁。

## 实现范围

- Base：`290652ada2bf5fafbd4ac9f27a1514680ff78ca9`（创建 worktree 时的 origin/main）。
- Branch：`codex/task-graph-descriptions`。
- 产品代码：`packages/dsh-integration/src/features/task-graphs.ts`、`task-graph-schema.ts`，仅七处 description。
- 不修改 systemPrompt.section、JSON schema 结构、PA 路由、IM 服务、运行时或审批策略。

## 最终结构与调用链

工具级描述负责动作选择与 create→apply 顺序；action 字段负责五动作参数矩阵；change_note、operations 与引用字段负责就近调用细节。现有 system prompt 继续负责授权、归属、记录不等于执行及协作状态行为。

注册后的工具沿现有 DSH 公开工具接口进入模型请求。PA 解析真实 target 并路由到 IM；IM 的动作字段表、权限、revision、原子 operations 和回执保持权威。描述只改善生成引导，不新增或代替形式校验。

## 采用决定

| 决定 | 原因与边界 |
|---|---|
| 改七处工具/字段描述 | 对应实玩中三类参数拒绝与依赖方向误解，不增加新抽象。 |
| 保留系统提示词 | 现有行为规则无矛盾；参数语法放在实际调用接口。实发请求逐例验证原文未变。 |
| 不加根 oneOf/if，不拆工具 | 当前非 strict Anthropic request builder 丢弃根组合约束；拆工具会扩大配置/工具名/权限影响面。 |
| 第一版通过后停止改写 | 三个独立自然任务都零参数拒绝；没有继续追逐猜测边界。 |

## 状态、失败与回滚

既有保存、访问、变更说明、幂等及冲突语义不变；旧错误参数仍由服务端拒绝。回滚只恢复七处描述。文案无法保证所有模型永不犯错；本次证据限于所列同模型 fresh case 与一次后续更新。

## 验证定位

真实栈、隔离方式、实际调用和持久图见 [M1-fix/progress.md](M1-fix/progress.md)。独立 [code review](code-review.md) 已通过，用户尚未亲测。

## Canonical 影响

[最窄 delta](specs/gateway/task-graphs.md)记录工具公布动作与引用契约；尚未覆盖 current spec。raw prompt、日志、配置、数据库和脚本均仅在本地 output/runtime，不提交。
