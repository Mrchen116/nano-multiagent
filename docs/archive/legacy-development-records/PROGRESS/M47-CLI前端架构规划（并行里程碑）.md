# CLI前端架构规划（M47+）

更新时间：2026-03-04
范围约束：仅 `src/nano_multiagent/cli/**` 与 CLI 相关测试；不改内核 API。

## 目标
- 在不改变外部契约的前提下，控制 CLI 复杂度增长，支持并行开发。
- 通过二级目录分层，把输入、事件、渲染、运行控制解耦。
- 保持 `send-message` 非交互单 JSON 契约、REPL 交互可读性和门禁稳定。

## 目标目录形态（渐进迁移）
- `src/nano_multiagent/cli/app/`
  - 入口编排、命令路由、生命周期控制（managed/remote）。
- `src/nano_multiagent/cli/input/`
  - 键盘输入、历史回填、slash 菜单状态机、重绘请求。
- `src/nano_multiagent/cli/events/`
  - 事件归一化、去重、语义视图模型构建。
- `src/nano_multiagent/cli/render/`
  - 语义模型到文案渲染，preview/final 分层，TTY 输出策略。
- `src/nano_multiagent/cli/runtime/`
  - run queue、in-flight 管理、超时与收口策略。

说明：
- 迁移初期保留现有文件作为 facade，逐步转发到新子目录，避免一次性大改。
- 每个里程碑都要求“行为等价或更优 + 门禁全绿 + managed 实跑”。

## 并行里程碑 DAG
- `M47` CLI架构重整一期（二级目录骨架+兼容门面）
  - 产物：二级目录与最小 facade；不改行为。
- `M48` 输入子系统重构（状态机+重绘闸门）
  - 依赖：`M47`
- `M49` 事件语义管线重构（normalize/dedupe/view-model）
  - 依赖：`M47`
- `M50` 渲染层与阶段状态机（STREAMING/FINALIZING/FINALIZED）
  - 依赖：`M49`
- `M51` 工具时间线聚合与异常隔离（call_id/orphan）
  - 依赖：`M49`,`M50`
- `M52` 交互/脚本双通道契约固化（TTY/non-TTY）
  - 依赖：`M48`,`M50`
- `M53` CLI可靠性与性能门禁（长会话/高频事件）
  - 依赖：`M51`,`M52`
- `M54` 商业化收口（可观测+发布验收+文档）
  - 依赖：`M53`

并行策略：
- `M48` 与 `M49` 在 `M47` 完成后并行。
- `M51` 与 `M52` 可在上游依赖满足后并行。
- 每个 Milestone 独立 worktree，减少冲突与上下文污染。

## 防腐化规则
- 先测试后实现；每个 Roadpoint 严格 C1/C2/C3。
- 变更前先定义边界：允许改动文件列表 + 禁改目录。
- 尽量“移动+适配”而非重写；保留回滚点。
- 所有 UI 变化必须有 managed CLI 实跑片段，不只依赖单测。
