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
- delta 锚定正确 canonical target，MODIFIED 保留未改变的 Scenario，消费者视角正确；前端 must-match 与验收前置已落实。
- 前端设计按 [共同体验标准](../change-design-author/references/prototype-and-runbook.md#共同判断标准)，先看实际渲染的画面、走相关路径并对照现有产品，形成自己的体验判断，再核作者的清单与契约。检查每个受影响平台是否已有足以指导实施的内容关系和交互方案；用“原生适配”代替尚未作出的设计决定属于缺口。证据不足明确未验证，不提前要求真实后端实现。
- 独立检查职责、依赖方向、抽象与已有能力复用。说明职责应由哪个模块承担，对比复用既有能力与新增机制，不只检查依赖是否合法。只报能说明实际维护/运行代价的复杂度，不追求假想“架构最优”。

体验问题按具体用户代价判断，不因功能可用或符合原型就降为审美建议；方案本身有问题也需修订。纯风格偏好不阻断，视觉变化按实际影响复查，不因“纯样式”自动豁免。

完成条件是覆盖有证据、无会让下游实质走偏的未解决问题。`Approved` 仅用于 `0 CRITICAL / 0 WARNING`；可选建议放 Recommendations，不阻断。

## 报告

每轮向同一个 `docs/changes/<unit>/design-review.md` 追加完整 Round，保留历史并记录本轮 reviewer 身份；更换 reviewer 按 workflow 交接证据，不能仅据旧 Approved 放行。格式与模式证据见 [report](references/report.md)。author 只追加 resolutions；后续 reviewer 核实闭环，不回写旧结论。返回轮次、模式/理由、结论、问题数和报告位置。
