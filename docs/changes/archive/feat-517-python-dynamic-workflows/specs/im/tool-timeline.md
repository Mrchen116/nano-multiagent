# IM - Tool Timeline Specification (delta for feat-517)

## MODIFIED Requirements

### Requirement: 内部 IM 把思考与工具调用展示为过程时间线、外部不展示

#### Scenario: 内部 Web IM 一轮含多段思考与工具调用
- **WHEN** 一轮带多段思考、多次工具调用的助手回复在内部 Web IM 展示
- **THEN** 气泡内有一个可折叠“过程”区域，把多段思考与工具调用按真实先后次序混排；每段思考可展开读完整内容、可收起；历史回看仍可展开

#### Scenario: 内部 Web IM 无思考
- **WHEN** 助手回复本轮无任何思考
- **THEN** 过程区域里不出现思考行（无思考不留空壳）

#### Scenario: 外部 channel
- **WHEN** 同一条回复送达外部接入的 IM
- **THEN** 只显示正文、不含任何思考

#### Scenario: 内部 Web IM 的过程时间线增加后台返回
- **WHEN** 一轮除思考/工具外还带一条或多条后台返回
- **THEN** 同一“过程”区域把 background-return 与已有 thinking/tool 按共享 `seq` 混排，历史回看仍可展开
- **AND** 工具数量、运行中工具与批准统计只计算真实工具；后台返回单独计数，不伪装成 ToolCall

#### Scenario: 后台返回可展开核对原始内容
- **GIVEN** 普通回复消费了 `Agent(run_in_background=true)` 或 Workflow 的 task notification
- **WHEN** 用户展开对应后台返回行
- **THEN** 可看到后台来源、terminal status、未经主 Agent 改写的 result/error、task/agent/run identity、usage、duration 与存在的 artifact locator
- **AND** 普通正文仍单独显示主 Agent 的综合结论

#### Scenario: 正文为空但后台返回存在
- **WHEN** 一条 assistant message 没有正文但含后台返回
- **THEN** 气泡仍保留并显示可展开过程项，不作为 empty completion 丢弃

#### Scenario: 内部 Web IM 无过程项
- **WHEN** 助手回复本轮无思考、工具调用或后台返回
- **THEN** 不显示空的过程区域

#### Scenario: 外部 channel 不增加后台返回过程项
- **WHEN** 同一条含结构化后台来源的回复送达外部接入的 IM
- **THEN** 仍只显示正文，不增加 thinking、tool timeline 或后台返回卡片
