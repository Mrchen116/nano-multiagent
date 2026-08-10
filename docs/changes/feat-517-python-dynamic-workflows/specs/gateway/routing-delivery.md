# gateway (personal_assistant) - Routing and Delivery Specification (delta for feat-517)

## MODIFIED Requirements

### Requirement: 后台任务完成后 Gateway 把 Agent 回复中继回原 IM 对话

用户让 Agent 后台执行长任务后，主轮先回复已启动；任务结束时，Gateway 把消费该 `<task-notification>` 后产生的普通 Agent 回复投递回原 IM 对话。既有 background Bash 继续以第二条文本回复送达。对内置 Web IM 的后台 subagent / Workflow，回复还携带与 notification 同源的结构化后台返回，让用户核对原始 result 或 error 与来源；对不提供内部过程时间线的外部 IM，继续只投递普通文本。重复投递经稳定 identity 去重，不产生重复消息或重复后台返回。

#### Scenario: 后台 Bash 完成后用户在 IM 对话收到包含结果的第二条回复
- **GIVEN** 用户经 IM 直聊让 Agent 后台执行一个命令（如 `run_in_background: sleep 30 && echo X`）
- **WHEN** 主轮返回“已启动”，任务在后台完成
- **THEN** 用户在同一 IM 对话收到第二条 Agent 回复，内含后台任务输出（如“X”）
- **AND** 本 unit 不要求该 Bash 回复增加结构化后台返回过程项

#### Scenario: 后台 Agent 完成后 Web IM 收到正文与可归因返回
- **GIVEN** 用户经 Web IM 让 Agent 以 `run_in_background=true` 派发一个 subagent
- **WHEN** 主轮已返回“已启动”，subagent 稍后完成并由 parent 生成综合回复
- **THEN** 用户在同一对话收到第二条普通 Agent 回复
- **AND** 该回复同时携带 subagent 的 task/agent identity、status、未经主 Agent 改写的 result/error、usage、duration 与 output artifact

#### Scenario: 后台 Workflow 使用相同投递通路
- **GIVEN** 用户经 Web IM 启动一个 Workflow
- **WHEN** Workflow completed、failed 或 stopped，parent 生成综合回复
- **THEN** Gateway 用相同消息 sidecar 携带 Workflow task/run identity、terminal value、usage、diagnostics 与 resume hint
- **AND** 不把 terminal 当作 launch ToolCall 的后续更新

#### Scenario: 外部 IM 保持普通文本回复
- **WHEN** 同一后台返回来自飞书等外部 channel
- **THEN** Gateway 仍把主 Agent 的普通文本回复发回原聊天
- **AND** 不新增外部卡片、raw XML 或 Web 专用过程字段

#### Scenario: Gateway 重启不产生重复的后台回复
- **GIVEN** 某后台任务回复及其结构化返回已投递到 IM 对话
- **WHEN** Gateway 重启后同一 task 的事件被重放
- **THEN** 该对话中不出现重复的第二条回复，同一消息中也不出现重复后台返回
