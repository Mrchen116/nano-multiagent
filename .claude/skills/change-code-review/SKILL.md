---
name: change-code-review
description: "用户要求审查代码 diff，或 change 流程进入独立 code-review 门禁时使用；不用于需求/设计文档评审或产品旅程验收。"
---

# Change Code Review

发现 maintainer 会处理的具体缺陷。主会话组织独立 finder 和候选 verifier；模型/effort 沿用当前配置，按 diff 的实际风险选择有价值的角度与并行度，不固定七路或每条候选一个 agent。

## 范围与约束

- full 审指定完整 diff；patch 审 pre_fix_head..HEAD；closure 核 focus_findings 与 finding_origin_head..HEAD。未指定目标时确认合理 base，不能把空 upstream diff 当作无改动。
- 包含属于本任务的未提交改动，保留用户其他工作。patch/closure 不自行扩大到整条分支；发现影响扩大时报告需 full。
- finder 关注正确性、被删除的不变量、实际调用方、复用/复杂度和运行代价，方法自主。候选需位置、具体触发场景与后果，不以数量凑 finding。
- 候选去重后交独立 verifier，可按同一机制成批验证。只做审查，不修改被审对象。
- verifier 返回 CONFIRMED（直接证据）、PLAUSIBLE（机制有据但条件未证实）或 REFUTED（反证）。未确认的条件明确标出；不把假想边界或风格偏好报成缺陷。

## 输出

返回 JSON 数组，字段为 `file`、`line`、`summary`、`failure_scenario`、`review_mode`、`status`（CONFIRMED/PLAUSIBLE），按严重度排序；无存活问题返回 `[]`。closure 另说明各 focus finding 的 closed/still_open/superseded，未关闭项不能漏掉。

范围已经充分覆盖、候选已独立核实后结束，不为达到数量或追逐推测反复审查。
