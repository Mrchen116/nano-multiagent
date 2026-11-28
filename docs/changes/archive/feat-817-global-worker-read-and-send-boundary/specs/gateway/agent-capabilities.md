# gateway/agent-capabilities.md (delta for feat-817)

## MODIFIED Requirements

### Requirement: 全局主 Agent 保留默认工具并具备固定基础能力

#### Scenario: 新建全局 Agent 时保留正常执行能力
- **WHEN** 用户新建全局 Agent
- **THEN** 除读取收件箱、查阅聊天、显式发言、委派及 Worker 只读观测的固定基础工具外，仍默认拥有现有创建流程提供的工具
- **AND** 不因选择全局模式变成只能统筹、不能正常查询或执行的空工具 Agent

#### Scenario: 固定基础工具与可配置工具区分
- **GIVEN** 用户创建或编辑全局 Agent
- **WHEN** 查看和调整工具配置
- **THEN** `inbox`、`conversations`、`read_messages`、`search_messages`、`threads`、`send_message`、`download_attachment`、`delegate_worker`、`read_worker` 作为固定基础工具，不可关闭
- **AND** Personal Global 另外固定 `personal_sources` 与 `send_user_message`；Global / PA 根主 Agent 运行时隐藏原生 `subagent`、`list_agents` 与 `interrupt_agent`；其他工具继续按默认选择及依赖规则配置，`single_thread` 和子 Agent 不继承 Global 根会话固定项
