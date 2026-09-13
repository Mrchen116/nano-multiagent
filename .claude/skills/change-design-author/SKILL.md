---
name: change-design-author
description: "Full unit 首文档已定稿，需要对齐技术方案、delta-spec 和 milestone 时使用；Bugfix lite、直接实施和事后补文档不触发。"
---

# Change Design Author

把已确认需求落成可供人审查、下游无歧义实施的设计。只修改 unit 内的设计产物，不写产品代码、不创建实施分支。

## 约束与产物

- 首文档未收口时先完成需求对齐；需求、验收或范围变化交回 spec-author。Bugfix lite 直接进入实施。
- 方案建立在受影响路径的 current specs、实际生产接线和可复用机制上；证据沿用仍有效的调查，发现漂移明确记录。
- 关键架构决定和 milestone 拆分逐项与用户对齐，一次一个问题；已有决定不重问，授权范围内的实施细节自主处理。
- 使用 [design 模板](assets/design.md)：上层写整体思路、关键取舍，下层写接口、数据流、退出标准。图只用于解释难懂的结构/交互，选型可查 [diagrams](references/diagrams.md)。设计期 Changelog 留空。
- 默认单 M1。只有可独立交付、真实无冲突并行或分阶段验证/容量需要时拆分；不按数据层/API/UI/测试横切，不用固定行数、文件数或小时数决定。
- milestone 表包含 ID、依赖、并行组、文件范围和两轨退出标准：`[reviewer]` 用户可观察结果，`[worker]` 实现与验证证据。骨架只放 `.gitkeep`，不预填 tasks/progress。
- 有前端变化时按 [原型与验收前置](references/prototype-and-runbook.md) 形成 `prototype.html` 与 must-match 契约；无前端变化不生成。
- 有对外行为增量时按 [specs/CONTRIBUTING](../../../docs/specs/CONTRIBUTING.md) 写最窄 target 的 delta-spec；纯内部变化注明 `no spec delta`，不提前覆盖 current spec。

模块接口、职责或测试边界需要设计时可用 [codebase-design](../codebase-design/SKILL.md)；普通配置、文案或局部实现不必调用。

## Gate 2 与交付

Gate 2 只创建一个独立 `change-design-reviewer`，后续复用同一 reviewer；审查期间冻结首文档、design、delta-spec、prototype 和骨架。具体派发、恢复和追加报告契约见 [设计审查闭环](references/review-loop.md)。

完成条件：需求与设计覆盖一致、接口和依赖闭合、适用验收资源已落实，最后完整 Round 为 `Approved` 且 `0 CRITICAL / 0 WARNING`，author 判真后无实质问题，受审产物此后未变化。常规修订自主完成；只有推翻用户决定才重新对齐。

在 `main` 只提交并推送本 unit 产物，交给默认 `change-orchestrator` 或用户点名的 simple 流程。
