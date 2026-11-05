---
name: agent-context-review
description: "独立审查影响 LLM 可见信息或其选择、注入、加载、更新与恢复链路的设计或实现；覆盖 Prompt、动态提醒、Skill、工具、消息、Memory 和 History。由现有设计/代码审查角色按模式调用；纯 UI 样式或无 Context 影响的内部改动不触发完整审查。"
---

# Agent Context Review

站在 LLM 消费者视角审查接口及其生命周期。先读 [通用规范](../../../docs/development/agent-context-engineering.md)，按实际影响选择 Surface 与组合关系，不逐项制造全量 checklist。使用 caller 已指定的独立 reviewer 身份、范围和输出；不另派 Agent、不新增 Gate、不修改受审设计/实现或擅自修产品。

## Mode A — Design Review

用于实施前方案，由现有 design-reviewer 执行。沿 Consumer 的任务追踪来源/owner、选择/组装、交付时点、保留/失效与恢复：为什么常驻、动态、按需或通过工具获取？哪些输入可由模型可靠取得，哪些只能由宿主派生？核对与已有规则、Skills、Memory、工具的交互及多用户/多 Agent 的信任和权限边界。

结合必要的模型可见 Before/After 判断信息缺失、失败与状态更新能否支撑下一步；检查 Validation 能否证明实际交付及适用行为，并进入退出标准。没有真实实现或模型运行时只给方案判断，不伪造运行结论。结果并入原 `design-review.md`。

## Mode B — Implementation Review

用于已有实现，由现有 code reviewer 在 diff 及受影响消费链上执行。按 [观察实际 Context](../../../docs/development/llm-integration.md#观察实际-agent-context) 核对最终组装的 System Prompt、实际工具/Schema、序列化结果、注入消息和提醒，以及适用的 Skill 发现/加载、Memory 与多轮裁剪/换窗/恢复。组合后再判断，不止检查源码字段、内部 API、类型、UI 卡片或磁盘文件。

复用带版本与 locator 的可信证据；关键缺口才补捕获/任务。条件允许且与风险相关时，使用代表性真实模型任务观察选择工具、填写参数、理解状态与后续行动；隔离环境与数据，不改生产。区分装配预览、stub 请求、真实 provider 输入和实际行为，明确未验证条件；不要从一条成功 trace 外推全局可靠。结果并入 caller 的既有代码审查输出或报告，不强制新文件。

## 结论与问题

说明本次模式、版本/范围、触发理由、实际覆盖与未验证项。每个问题必须给：具体文件/设计位置、Context Surface、Agent 应知道/理解/执行的内容、实际设计或模型可见内容、失败场景或可成立机制、任务/用户影响、可执行建议、证据定位与限制。

严重度沿用当前 change 审查：CRITICAL 为缺失关键能力/违反边界等阻断问题，WARNING 为实质设计或实现缺陷，SUGGESTION 为可选改进；与证据状态分开。CONFIRMED 表示直接证据支持该声明（可确认确定性的接口缺陷而未运行模型）；PLAUSIBLE 表示机制有据但条件未证实；REFUTED 表示有反证，不作为存活 finding。不得把 PLAUSIBLE 描述成模型一定误解；缺少必要验收证据与已证实产品缺陷分别记录。

保持 caller 原输出格式：code review 的既有 JSON 字段不变，Context finding 另附 surface、expected、observed、impact、recommendation、severity、evidence；设计报告沿用现有 issue ID。无实际问题不凑 finding；空发现也说明证据范围与限制。完成相关覆盖后停止，只按真实 delta 复验。隐私原件按 [Evidence](../../../docs/development/evidence.md) 留本机，只引用脱敏摘要。
