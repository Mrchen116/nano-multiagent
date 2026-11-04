# refactor-710: 组织级 Agent 平台产品愿景 — 文档方案

> 对齐：[motivation.md](motivation.md)

## Changelog

## 现状分析

### 涉及范围

`docs/product/vision.md` 是产品定位与长期原则的唯一完整权威；README 是使用入口，SPEC 是架构权威，产品目录和文档地图负责导航，Web IM 原则负责界面长期取舍。本次修改这六份文档，不移动或复制总纲。

### 既有约束

产品方向与 current 行为契约分开。保留私人/公司权限、固定 PA 主人关系、Agent 配置 owner 及内部 subagent 的边界；不修改 DSH 执行架构和产品运行时提示词。产品文档可供开发者与开发 Agent 按需阅读，但没有进入已安装 Nano Agent Prompt/Skill 的装配链路，本次不改变运行产品的 Context 生命周期。

### 可复用能力

复用 [Global 跨聊天契约](../../specs/gateway/global-agent.md)、[PA 契约](../../specs/gateway/personal-agent.md)、[组织边界](../../specs/im/auth-tenancy.md)、[任务持续推进](../../specs/gateway/task-graphs.md)与 [Work](../../specs/im/agent-work.md)作为当前设计依据。PA 复用 Global 执行，故产品角色和执行模式分开说明，不构造两个互斥的技术类型。

### 相关历史

旧愿景由早期个人多 Agent 需求蒸馏，DSH 迁移只修订运行时内容。[feat-705](../feat-705-global-task-delegation/spec.md)仍为 active：只作为主从分工的后续设计入口，不将其未完成目标及暂缓 Task 联动加入 current 行为承诺。

## 架构总览

文档信息结构从“个人运行多个助手”改为“组织级平台 → IM 工作场所 → 真人、PA、专业数字员工 → 长期工作原则 → 当前契约入口”。不改变软件架构。

## 关键决策

1. **组织级定位由用户本轮明确决定。** 首段直接表达组织协作目标；个人使用仍可独立开始，不新增组织准入前置条件。
2. **IM 是工作主体。** 描述在聊天中提出需求、澄清、协同、反馈和交付，任务及 Work 为工作连续性与过程检查服务；Web、iPhone 和飞书保留各自入口地位，不把所有内部执行明细塞进聊天。
3. **按服务对象与责任定义角色。** PA 围绕一个人的目标与授权；专业 Global 数字员工围绕组织职能与成果、多来源请求和职责内主动工作。可举质量保障等岗位作为方向示例，明确不是已内置的岗位能力承诺。
4. **长期原则表达结果，不发明新机制。** 身份与职责连续、上下文和经验积累、工作可见可控、权限与个人/组织边界明确。数字员工职能不因请求者切换或一轮回复结束自动消失；不承诺无限自主、自动接收全部请求或现有配置 owner 变更。
5. **当前设计与目标分层。** 总纲明确愿景不等于所有场景已验收，链接 current specs 获取现状；不将 active change 当成 current，不扩大 feat-705 的范围。
6. **入口只写摘要。** README/SPEC 首段和两个索引链接到总纲；Web IM 原则首段与“对话优先”补明组织协作、任务与交付，其余已成立原则保留。

## 接口与数据流

无 API、存储、权限、配置及执行链变化。读者从 README 或文档地图进入 vision，再按领域链接查 current 契约。旧版留在 Git 历史；不额外维护新的产品总纲文件。

## 契约层增量 (delta-spec)

IM / Gateway：no spec delta。本次是产品方向文档修订，不以修改行为契约制造实现完成的假象。

## 风险与回退

主要风险为把“Global 执行模式”误当成“组织角色”，或把愿景写成已交付能力。通过显式说明 PA 也用 Global、保持 current 链接及方向/验收边界防止误读。回退只撤回本次文档 diff。

## 一次性部署迁移

无。

## Runbook for Reviewer

无常驻服务，无运行产品用户面变化，无外部验收前置。Review 驱动方式为静态文档一致性核对；不启动生产或测试服务。检查用户原话覆盖、现状依据、角色和权限边界、相对链接、修改范围，运行 `./scripts/docs-check` 与 `git diff --check`。不新增逐句文本测试，不运行与纯文档变更无关的产品回归；远端 CI 结果另行报告。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 文件范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-vision | 愿景与入口对齐 | 无 | 单项 | vision、README、SPEC、两份目录入口与 Web IM 原则 | [reviewer] 无运行产品用户旅程，跳过产品 reviewer；[worker] 三种角色、IM 主体、职能责任、共享执行及隐私边界准确；方向与 current 分开；六份文档一致，链接及 diff 检查通过；独立静态 code-review/verifier 核对 |
