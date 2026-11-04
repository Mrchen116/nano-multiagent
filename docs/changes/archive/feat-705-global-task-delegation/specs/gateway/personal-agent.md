# gateway personal-agent Specification (delta for feat-705)

> 目标：`docs/specs/gateway/personal-agent.md`。

## MODIFIED Requirements

### Requirement: PA 复用完整 Global 执行能力

#### Scenario: 主人请求与普通工具
- **WHEN** 主人交办工作或查询历史
- **THEN** 直接进入 Global 主上下文，复用普通工具、Skills、插件、任务、子 Agent 与调度；不增加主人输入审核或 PA 目标引擎。
- **AND** 日常直接处理、完整独立事项的单一内部执行责任、原执行者接续及主 Agent 唯一沟通交付均遵循 [Global 契约](global-agent.md)，不另设 PA 执行模型。

### Requirement: 默认服务指导复用普通配置和 Skill

默认服务指导将 PA 定位为长期辅助主人履行职责、追求目标并兼顾工作与生活的助手，结合相关目标、偏好、关系、承诺和新事实判断有帮助的下一步；共享 Global 指引提供内部委派与对外交付分工，不将 PA 固定为只处理新请求的接单者。实际信息范围和行动权限仍沿用当前契约。

#### Scenario: 用户调整服务方式
- **WHEN** 主人修改或清空 PA 的 custom_prompt
- **THEN** 沿用普通 Agent 的配置和 Persona 加载机制，运行时不暗中补回默认服务文案；固定主人身份、来源、权限及对外披露规则仍有效。

#### Scenario: 跨轮次持续工作
- **WHEN** Global 或 PA 接续已接受的持续事项
- **THEN** 可按普通 Skill 发现、选择和加载机制使用随包 nano-ongoing-work，复用已有工作记录、任务、子 Agent、Heartbeat 和 schedule；不新增 PA 账本服务或调度器，不覆盖用户已有 ongoing-work Skill，也不绕过用户禁用选择。

#### Scenario: 重要观察后的私人准备
- **GIVEN** PA 使用默认服务指导，相关来源已获准访问且对应 Skill 未被禁用
- **WHEN** 观察到与主人有关的重要变化或承诺
- **THEN** 可按需使用 nano-proactive-care，核对原话和后续状态，在现有权限内准备有实际内容的私人草稿或材料；不把观察到的承诺当作对外发送授权，不增加新的关注项服务或调度器。
- **AND** 已处理或没有新帮助价值时保持安静；可读取的信息不足时保留不确定性，不声称已完整核实。

#### Scenario: 已交办事项中的权限阻塞
- **WHEN** 内部执行者报告权限阻塞
- **THEN** 主 Agent 核对具体动作、拒绝理由、原始要求和有效限制，继续允许的独立部分；已有授权覆盖的事项不因内部委派或跨轮次就要求用户重新批准。
- **AND** 父级只能澄清自己的交办限制，不能新增人类授权或推翻用户限制；必要的新权限问题须具体，答复交回原执行者，实际动作仍走正常权限检查，不换介质重复被拒动作。
