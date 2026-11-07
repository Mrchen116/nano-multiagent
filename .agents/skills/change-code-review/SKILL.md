---
name: change-code-review
description: "审查实现 diff 的正确性、需求遗漏、设计一致性与维护风险；也用于校对最终 delta-spec。不替代专项 Context、体验或产品旅程判断。"
---

# Change Code Review

由未参与受审实现的独立审查者检查本次 diff 及相关调用方。输入为目标/要求、实际 base/head、范围、适用设计和契约、已有证据；普通无 unit 的 review 不强制补 change 文档。

## 范围与方法

- full 审指定完整 diff；patch 审 pre_fix_head..HEAD；closure 核指定 finding 及其来源到当前的变化。包含本任务明确的未提交改动，保留其他工作；不能把空 upstream diff 当作无改动。发现影响扩大时说明需补审的范围。
- 核对实现是否遗漏要求、违背关键设计/项目约束、删除不变量，检查真实调用方、失败恢复、授权和具体运行/维护代价。实现与设计一致不自动说明方案合理；设计问题交 owner，不建议改 spec 迎合错误实现。
- 有 unit 时将重要要求、设计决定和退出标准与实现及有效测试对应；材料已有充分映射就引用，不再写第二份逐项报告。缺实现、实质偏离或必要回归保护缺失均须明确报告。
- corrected-delta 只核最终校正的契约与实现/测试及遗漏的对外行为，给 aligned、delta-mismatch 或 implementation-mismatch；不符同时存在优先 implementation-mismatch。未变已审部分保留，无 delta 记录 no spec delta。
- 复用版本、命令、结果和定位明确的可信证据，关键条件未证实才独立补跑。不因角色交接重跑全量。
- 专项方法由 caller 按本次安排组合；发现未覆盖的 Context、前端或性能影响时明确交回补选，不能用本轮代码通过代替专项判断。只加载明确选择的能力，不默认内嵌全部专项。

## 结果与完成

返回受审版本/范围、需求与设计覆盖摘要、证据/限制、未验证项及 findings。finding 使用 file、line、summary、failure_scenario、severity、status；status 为 CONFIRMED 或 PLAUSIBLE，反证项标 REFUTED 并从存活列表移除。closure 给各指定问题的 closed/still_open/superseded 和依据。无存活问题返回空 findings，同时保留范围与证据摘要。

明确缺实现、违反边界或关键路径失败为阻塞；实质行为/契约偏离和必要回归缺失也须修复，可选维护改进不阻断。不把风格偏好或假想条件列为缺陷。高风险、有争议或关键条件无法确认时说明追加核验的具体问题，交 caller 安排，不能自行派发。

只审查，不修受审对象或自行提交报告。覆盖充分、实际问题和证据缺口已交代就结束，流程负责归集与交付。
