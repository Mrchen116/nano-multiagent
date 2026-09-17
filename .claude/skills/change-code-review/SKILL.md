---
name: change-code-review
description: "用户要求审查代码 diff，或 change 流程进入独立 code-review 门禁时使用；不用于需求/设计文档评审或产品旅程验收。"
---

# Change Code Review

发现 maintainer 会处理的具体缺陷。由未参与受审实现的独立审查者执行，按派发的范围与模式给出结论。

## 范围与约束

- full 审指定完整 diff；patch 审 pre_fix_head..HEAD；closure 核 focus_findings 与 finding_origin_head..HEAD。未指定目标时确认合理 base，不能把空 upstream diff 当作无改动。
- 包含属于本任务的未提交改动，保留用户其他工作。patch/closure 不自行扩大到整条分支；发现影响扩大时报告需 full。
- 审查者关注正确性、被删除的不变量、实际调用方、复用/复杂度和运行代价，方法自主。候选需位置、具体触发场景与后果，不以数量凑 finding。
- 普通明确问题由独立审查者直接举证。高风险或存在争议、关键条件无法确认的候选，注明需要追加核验的原因与条件，交 caller 安排；只做审查，不修改被审对象。
- 审查者或追加核验者返回 CONFIRMED（直接证据）、PLAUSIBLE（机制有据但条件未证实）或 REFUTED（反证）。未确认的条件明确标出；不把假想边界或风格偏好报成缺陷。

## 输出

返回 JSON 数组，字段为 `file`、`line`、`summary`、`failure_scenario`、`review_mode`、`status`（CONFIRMED/PLAUSIBLE），按严重度排序；无存活问题返回 `[]`。closure 另说明各 focus finding 的 closed/still_open/superseded，未关闭项不能漏掉。

对派发的固定版本执行 patch/closure；复用可信且仍适用的测试证据，必要时独立复现关键条件。范围充分覆盖、问题有证据且适用的追加核验完成后结束，不为数量或推测反复审查。
