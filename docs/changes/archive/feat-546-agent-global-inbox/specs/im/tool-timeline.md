# im/tool-timeline Specification (delta for feat-546)

> 目标增量；实施校正后归并 current。原有 Scenario 完整保留，作用域由各 Requirement 开头的模式限定确定。

## MODIFIED Requirements

### Requirement: 内部 IM 把思考与工具调用展示为过程时间线、外部不展示

本条以下气泡内过程归属及 Scenario 适用于 `single_thread`。global 的相同真实思考/工具/后台信息展示在 [agent-work](agent-work.md) 的工作轮次，正式聊天不携带内部轨迹；共享工具详情、统计、授权与外部不展示内部过程的约束继续适用。

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
- **WHEN** 助手回复本轮无思考、工具调用、后台返回、未发送草稿、复核或片段交接记录
- **THEN** 不显示空的过程区域

#### Scenario: 外部 channel 不增加后台返回过程项
- **WHEN** 同一条含结构化后台来源的回复送达外部接入的 IM
- **THEN** 仍只显示正文，不增加 thinking、tool timeline 或后台返回卡片

#### Scenario: 正文为空但草稿或复核记录存在
- **WHEN** 内部群的一条 assistant message 没有正文，但含未发送草稿、复核或片段交接记录
- **THEN** 气泡与可展开的过程区域仍保留，新增记录与其他过程按真实顺序排列；刷新后仍可查看，不计为工具调用

### Requirement: 群聊 Process 保存真实未发送草稿与复核分段

以下当前群聊天气泡的草稿、复核、插话分段 Scenario 适用于 `single_thread`。global 的未发送草稿与目标复核归工作页对应发送工具详情，见 [agent-work](agent-work.md)；同伴只收到实际正式消息、来源不可用不误定位的规则继续适用于两种模式。

草稿和复核是明确标记的过程信息，不是正式正文、模型推理声明或工具计数。已写入历史的完整草稿可在刷新后回看。

#### Scenario: 旧段展开未发送全文
- **GIVEN** 当前群 Agent 因新消息保留了生成的旧草稿
- **WHEN** 用户展开旧消息块的 Process 和“原草稿 · 未发送”
- **THEN** 看见真实完整文本，默认折叠且明确未发送；不把它当正式发言转发给其他 Agent

#### Scenario: 新消息下方复核并继续工作
- **WHEN** Agent 实际采纳一批新消息开始复核
- **THEN** 旧块留在原位置并可定位后续块，新块位于本批最后一条采纳消息下方，展示来源引用和复核状态；后续新工具调用与正文属于新块
- **AND** 原有过程不复制，不把片段结束当整个任务完成；不存在草稿时不编造未发送记录

#### Scenario: 多条成批与多次更新
- **WHEN** 一次采纳多条消息，之后又采纳另一批
- **THEN** 每个采纳批次只建立一个后续段，不按每条通知建块；刷新和重连后顺序、归属及关联一致，没有重复项

#### Scenario: 静默或中断只保留实际过程
- **WHEN** Agent 按既有规则静默或运行被停止/失败
- **THEN** 保留实际发生的 Process 并收口运行状态，不新增正文占位回复，不展示协议静默 token，不伪造思考或发送成功

#### Scenario: 来源引用不可用
- **WHEN** 用户打开一个来源消息已不可定位的复核过程
- **THEN** 来源快照仍可辨认并说明不可用，不定位到其他消息

#### Scenario: 同群发送工具尚未提交或被保留
- **WHEN** 用户查看发送工具的过程，正文尚未提交或因新消息被保留
- **THEN** 待发送文字与未发送文字有明确状态；被保留的全文可在草稿项展开，不把它显示为已发送成功或无标记正式结论

#### Scenario: 同伴只收到实际正式回复
- **WHEN** 群 Agent 的非空正式回复完成落库
- **THEN** 按该真实消息 ID 向每个目标同伴转发一次，来源引用指向该回复；输入或 follower 完成回执不再生成同伴消息，重复回执或重放不重复转发
- **AND** 同伴任务失败不改变源正式消息的已完成状态；两条文本相同但 ID 不同的正式消息仍各自转发
