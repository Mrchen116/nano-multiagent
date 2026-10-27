# Gateway Personal Agent Specification (delta for feat-667)

## MODIFIED Requirements

### Requirement: 默认服务指导复用普通配置和 Skill

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
