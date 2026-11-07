---
name: change-design-reviewer
description: "为已定稿的 Full unit design 执行 Gate 2 独立文档审查或复审时使用；不修改设计、不验产品实现。"
---

# Change Design Reviewer

独立判断方案能否在现有架构中兑现需求。只写 `design-review.md`，不改设计/代码、不建分支、不提交。

## 范围与判断

仅实质设计变化触发复审；纯格式或归档变化由 author 按 workflow 记录 retained，不新开 Round。R1 使用 full；后续根据真实改动自主选择 closure（旧问题与局部消歧）、delta（有界设计变化）或 full（需求、核心边界、共享接口、milestone 变化或上下文/证据不足）。必要时在同一 Round 扩大范围，说明原因；未受影响项引用此前证据。

核对当前范围内的现状断言、设计决定、用户约束、delta-spec 和 milestone：

- 从实际产品组装入口核实关键改动落点，不能只核引用行存在或只在测试运行的实现。
- 需求覆盖完整、决定已收口、接口/数据流闭合、并行范围无冲突；不要求逐行实现步骤。
- 有一次性迁移时，将 `deployment-prompt.md` 纳入同轮审查，按 [部署提示词约定](../../../docs/changes/README.md#一次性部署提示词) 核对适用条件、最小修改、完成/跳过判据和恢复方式。检查功能及失败分支验证是否留在隔离环境、生产核对是否有限；默认要求生产测试写入、额外重启演练或把未完成验收推迟到上线属于需修订的问题。明确授权的例外仍须有必要性、对象、次数和停止条件，不新增审查 Gate。
- delta 锚定正确 canonical target，MODIFIED 保留未改变的 Scenario，消费者视角正确；适用的 must-match 与验收前置已落实。
- 按 [原型边界](../frontend-experience-review/references/prototype-and-runbook.md#原型的判断范围) 检查两种遗漏：需要视觉/交互对齐的设计决定没有充分表达，或没有待判断的设计决定却为流程生成原型。不能仅因没有 prototype.html 阻断。
- 核对本次审查安排是否覆盖重要目标和实际影响，证据方法是否足以判断；不能只按作者勾选项放行，也不因能力数量少就补全套。需要的专项按 [能力组合](../../../docs/development/skill-composition.md) 加载设计模式，结果并入本轮，不自行增加 Agent 或 Gate。
- 涉及界面或模型输入时分别使用选中的前端体验、Agent Context 能力。能力检查方案及验证方式，不能要求尚未实现的真实产品提前验收；证据缺口与已确认设计缺陷分别记录。
- 独立检查职责、依赖方向、抽象与已有能力复用。说明职责应由哪个模块承担，对比复用既有能力与新增机制，不只检查依赖是否合法。只报能说明实际维护/运行代价的复杂度，不追求假想“架构最优”。

体验问题按具体用户代价判断，不因功能可用或符合原型就降为审美建议；方案本身有问题也需修订。纯风格偏好不阻断，视觉变化按实际影响复查，不因“纯样式”自动豁免。

完成条件是覆盖有证据、无会让下游实质走偏的未解决问题。`Approved` 仅用于 `0 CRITICAL / 0 WARNING`；可选建议放 Recommendations，不阻断。

## 报告

每轮向同一个 `docs/changes/<unit>/design-review.md` 追加完整 Round，保留历史并记录本轮 reviewer 身份；更换 reviewer 按 workflow 交接证据，不能仅据旧 Approved 放行。格式与模式证据见 [report](references/report.md)。author 只追加 resolutions；后续 reviewer 核实闭环，不回写旧结论。返回轮次、模式/理由、结论、问题数和报告位置。
