# Kernel Runs Specification (delta for bugfix-525)

## MODIFIED Requirements

### Requirement: self-evolution side-chain 只向 session stream 暴露明确业务结果

消费者经 `agent.sdk` 运行启用了 self-evolution 的会话时，后台 review 继承主会话能力并完成真实 memory/skill 更新，但其内部 assistant、tool 与 turn 过程不成为父 session 的普通 realtime events。需要驱动产品状态的业务事件继续可观察；只有返回结果中至少一条 mutating memory/skill tool call 被确认成功时才发布最终 structured `self_evolution_review` 更新事件，并携带非空真实更新对象与 originating run trace，供消费者选择正确投递路径。no-save、只有读取/列举或写操作失败时不发布该更新事件；若 fork 整体 `completed=False` 但此前已有确认成功的写入，仍发布对应真实更新对象。

#### Scenario: memory review 不产生第二条 assistant 输出

- **GIVEN** 消费者提交的一轮触发后台 memory review
- **WHEN** 消费者从该轮 start sequence 持续读取 session stream 直到后台 review 结束
- **THEN** stream 只含该前台轮次的 assistant/tool/turn realtime events，不含 review fork 的 prompt、tool 过程或完成确认
- **AND** 若 memory 持久更新成功，消费者收到携带 memory 更新对象与 originating run trace 的最终 `self_evolution_review`

#### Scenario: skill review 暴露可归属的创建事件

- **GIVEN** 消费者提交的一轮触发后台 skill review，且 review 成功创建 Skill
- **WHEN** 消费者持续读取同一 session stream
- **THEN** stream 不含 review fork 的普通 assistant/tool/turn realtime events
- **AND** 消费者收到一条保留创建结果并标明 self-evolution 来源的 `skill_created` 业务事件
- **AND** 消费者随后收到携带 skills 更新对象与 originating run trace 的最终 `self_evolution_review`

#### Scenario: no-save 或写操作失败不产生更新事件

- **GIVEN** self-evolution review 未执行 mutating tool、只执行读取/列举，或所有 mutating tool result 均失败
- **WHEN** 后台 review 结束
- **THEN** consumer 不收到 `self_evolution_review` 更新事件
- **AND** review fork 的 raw assistant/tool/turn 过程仍保持私有

#### Scenario: incomplete fork 已有成功写入时仍报告真实更新

- **GIVEN** self-evolution fork 返回 `completed=False`
- **AND** 返回结果中存在至少一个已确认成功的 mutating memory/skill tool result
- **WHEN** hook 汇总真实更新对象
- **THEN** consumer 收到只包含这些成功更新对象的 `self_evolution_review`
- **AND** 不把未成功或只被 review 的对象标记为已更新
