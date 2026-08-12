# gateway (personal_assistant) - Relay Protocol Specification (delta for feat-517)

## ADDED Requirements

### Requirement: Gateway 在既有消息协议中保留后台返回归因

#### Scenario: idle parent 的后台回复透传 sidecar
- **GIVEN** BACKGROUND_TASK-origin run 的 user-visible assistant event 携带 subagent 或 Workflow 后台返回
- **WHEN** Gateway 以既有 `agent.message` 投递该回复
- **THEN** payload 在文本之外原样携带 `background_returns`
- **AND** 每项至少保留 task id/type、terminal status、原始 result 或 error，以及存在的 agent/run identity、usage、duration 和 artifact locator

#### Scenario: idle parent 正文为空时按 sidecar 可见
- **GIVEN** Gateway 要投递一条正文为空但 `background_returns` 非空的 idle 后台回复
- **WHEN** Gateway 通过既有 `agent.message` 协议发送 `text:""` 与完整 sidecar
- **THEN** IM 在原会话只创建一条终态消息；消息正文为空且持久保留完整 `background_returns`
- **AND** 在线用户立即收到同一条 `message.created`，刷新或重连后从历史恢复相同 sidecar
- **AND** 不出现占位文本或新增 wire event；`text` 与 `background_returns` 都空时 frame 被明确拒绝

#### Scenario: active parent 在气泡切点绑定 sidecar
- **GIVEN** active run 在 round boundary 消费一条或多条后台 notification
- **WHEN** Gateway 以既有 `injection_consumed` 语义关闭旧气泡并为后续回复打开新气泡
- **THEN** 该批 `background_returns` 按消费顺序进入新气泡的既有 `turn_start` payload
- **AND** 不按当前或最新 conversation message 猜测目标，不新建 Workflow 专属 wire event

#### Scenario: structured return 不进入外部 channel payload
- **WHEN** Gateway 把同一普通回复投递给不支持内部过程时间线的外部 channel
- **THEN** 外部 adapter 只收到既有文本和 reply metadata，不收到 Web IM 专用卡片协议
- **AND** 正文为空时不发送空消息，也不伪造占位文本或卡片
