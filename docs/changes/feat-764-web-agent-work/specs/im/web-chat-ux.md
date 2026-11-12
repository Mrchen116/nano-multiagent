# IM Web Chat UX Specification (delta for feat-764)

## ADDED Requirements

### Requirement: Web 聊天可从 Agent 头像查看工作状态

#### Scenario: 私聊和群聊查看同一个 Agent
- **GIVEN** 用户可以查看该 Agent 的 Work
- **WHEN** 在私聊或群聊点击 Agent 头像
- **THEN** 在头像旁查看主 Agent 状态、正在执行的主轮次最近工具，以及正在运行、待授权的子 Agent 数量；关闭后原聊天位置和草稿仍可继续使用。
- **AND** 可以展开一、二级等活跃子执行并打开相应 Work，配置入口仅在具备编辑资格时显示。

#### Scenario: 执行状态暂不能确认
- **WHEN** 工作记录正在补齐、节点离线或活跃状态不能确认
- **THEN** 显示对应同步或不确定状态，不把尚未确认的执行数显示为零。
