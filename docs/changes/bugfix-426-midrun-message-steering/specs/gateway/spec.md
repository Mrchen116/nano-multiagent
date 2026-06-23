# gateway spec delta — bugfix-426

> 本 unit 对长青契约层 `docs/specs/gateway/spec.md` 的增量。主语 = IM 用户。

## ADDED Requirements

### Requirement: 运行中的入站消息 steer 进当前 run 而非排队等其结束

Agent 正在执行一个 run 时收到同会话的新入站用户消息，Gateway 将其注入当前 run 的下一轮，而不是排到队尾等当前 run 整体结束。

#### Scenario: 工具循环中途发消息，当前 run 下一轮即消费
- **GIVEN** 某会话的 Agent 正在连续执行多轮工具调用
- **WHEN** 用户在该 run 仍在执行时发送一条新消息
- **THEN** 该消息在当前 run 的下一次模型调用前被带入上下文，Agent 后续回应据其调整
- **AND** 不另起新 run、也不等当前 run 整体结束才理睬

#### Scenario: 当前轮工具不被掐断
- **GIVEN** 当前轮有工具正在执行（含慢工具 / 超时重试）
- **WHEN** 用户在此期间发消息
- **THEN** 正在执行的工具批次照常跑完，消息在该批次结束后的下一轮注入

#### Scenario: 空闲时发消息仍新建 run
- **GIVEN** 该会话当前无活跃 run
- **WHEN** 用户发消息
- **THEN** 照常作为新 run 处理，行为与既有一致

#### Scenario: 群聊运行中 steer 保留发言人与缓冲上下文
- **GIVEN** 一个群聊会话的 Agent 正在执行 run
- **WHEN** 群成员在运行中发消息触发 steer
- **THEN** 注入的消息保留发言人前缀与该 Agent 的群聊缓冲上下文，与一次普通群聊 turn 一致（群聊行为不变）
