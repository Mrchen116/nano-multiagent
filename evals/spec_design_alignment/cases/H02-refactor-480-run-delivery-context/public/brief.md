# 需求：全仓重要架构问题盘点与重构组合

> 再看看当前代码仓中有多少巨石代码。
>
> 我希望你能明确当前所有的重要的架构问题；如果和 Claude Code 有类似的概念，则和它的源码架构做对比。然后用 change-spec-author、change-design-author skill，不需要跟我逐个进行对齐，帮我创建独立的几个 change unit。我要逐个进行重构、完善架构。我最终做一次确认后，再开始按可并行性做各个 unit 的实现。
>
> 中途你全程负责。我只做最终的确认。

对每个入选问题完成足够让我最终确认的 motivation/spec 与 design；同时给一个 portfolio index 汇总这些独立 unit、建议顺序和可并行关系。本阶段不实现代码。

运行环境提供了一个固定版本、只读的 Claude Code 源码镜像。只有确实存在可比概念时才做源码级对比并给出路径证据；没有等价概念时直接说明边界，不要为了“对比”而硬套。

原话里的具体 skill 名只表达“完成需求与设计阶段”的工作意图。本次运行以 runner 注入的唯一 arm bundle 为准；不要寻找或恢复 product snapshot 中已移除的旧 spec/design workflow。
