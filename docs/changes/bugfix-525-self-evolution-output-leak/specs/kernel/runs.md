# kernel Runs Specification (delta for bugfix-525)

## ADDED Requirements

### Requirement: self-evolution side-chain 只向 session stream 暴露明确业务结果

消费者经 `agent.sdk` 运行启用了 self-evolution 的会话时，后台 review 继承主会话能力并完成真实 memory/skill 更新，但其内部 assistant、tool 与 turn 过程不成为父 session 的普通 realtime events。需要驱动产品状态的业务事件与最终 structured review event 继续可观察，并带足够来源语义供消费者选择正确投递路径。

#### Scenario: memory review 不产生第二条 assistant 输出

- **GIVEN** 消费者提交的一轮触发后台 memory review
- **WHEN** 消费者从该轮 start sequence 持续读取 session stream 直到 structured review event
- **THEN** stream 只含该前台轮次的 assistant/tool/turn realtime events，不含 review fork 的 prompt、tool 过程或完成确认
- **AND** memory 持久更新仍完成，消费者收到最终 `self_evolution_review`

#### Scenario: skill review 暴露可归属的创建事件

- **GIVEN** 消费者提交的一轮触发后台 skill review，且 review 成功创建 Skill
- **WHEN** 消费者持续读取同一 session stream
- **THEN** stream 不含 review fork 的普通 assistant/tool/turn realtime events
- **AND** 消费者收到一条保留创建结果并标明 self-evolution 来源的 `skill_created` 业务事件
- **AND** 消费者随后收到最终 `self_evolution_review`
