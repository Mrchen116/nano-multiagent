# Gateway Agent Capabilities Specification (delta for bugfix-601)

## ADDED Requirements

### Requirement: Nano Auto 的指定查询与会话计划记录不依赖分类审核

#### Scenario: 查询已有工作与记录当前会话计划
- **GIVEN** Agent 使用已开启的 Nano Auto，且工具自身权限与作用域允许调用
- **WHEN** 用户要求查看已有 Skill 列表、任务图、提醒及其执行历史、Workflow 定义或运行记录、当前 goal，或者记录当前会话计划
- **THEN** `skill_manage list`、`task_graph list/get`、`schedule_list`、`schedule_history`、`workflow list/read`、`get_goal` 与 `todo_write` 不请求分类模型，并按原工具语义执行
- **AND** 工具可用性、确定性拒绝、作用域、ACL 与参数/执行约束保持有效；记录计划不会自动启动工作

#### Scenario: 相邻动作继续审核
- **GIVEN** Agent 使用已开启的 Nano Auto，且没有其它既有显式放行
- **WHEN** Agent 发起上述工具的其它写入、调度、编排或 goal 生命周期动作，或者执行 Bash/公开消息发送
- **THEN** 不因该工具具有查询功能而获得本批豁免，继续既有审批路径
- **AND** 缺席 action 的 Workflow 默认启动不属于查询

#### Scenario: Auto 关闭与 DSH 规则保持原路径
- **WHEN** 运维者关闭 Auto，或者选择 DSH 规则
- **THEN** 上述调用不继承本批新增豁免；Auto 关闭时保持原人工审批路径，DSH 规则下保持原审核路径
