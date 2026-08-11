# Gateway Routing and Delivery Specification (delta for bugfix-525)

## MODIFIED Requirements

### Requirement: self-evolution 维护过程不作为 Agent 聊天文本投递

Gateway 只把含非空真实更新对象的 self-evolution structured result 作为既有 system notification 投递；飞书触发时，该产品化更新通知按普通消息的触发源路由在原 chat 显示一行等价 Bot 文本。review side-chain 的 prompt、工具过程、完成确认、无更新说明与失败文本均属于后台维护信息，不形成内部 IM 或外部 channel 的普通 Agent 消息。该隔离不改变普通后台 Agent 明确面向用户产生结果的投递语义。

#### Scenario: memory review 完成后只显示 structured notice

- **GIVEN** 用户的一轮正常聊天触发后台 memory review
- **WHEN** review 保存 memory 并生成完成确认
- **THEN** 用户只收到正常 Agent 回答与既有 memory-updated system notification；飞书触发时原 chat 收到同一结果的一行 Bot 通知
- **AND** 不收到 review prompt、工具状态或完成确认的普通聊天气泡

#### Scenario: 无更新或失败的 review 保持私有

- **WHEN** self-evolution review 得出无需更新或执行失败
- **THEN** 用户不收到 `Nothing to save.`、错误文本或其他 side-chain 回复
- **AND** 该后台结果不改变前台回答的完成状态
- **AND** 没有成功的 memory/skills 写操作时不产生 system notification

#### Scenario: 普通后台 Agent 结果继续投递

- **WHEN** 非 self-evolution 的后台 Agent 按既有语义产生用户可见文本
- **THEN** Gateway 继续把该文本投递到原内部 IM 或外部 channel
