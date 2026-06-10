# kernel Specification (delta for feat-394)

> 本单元对 canonical `docs/specs/kernel/spec.md` 的增量。收尾归并已合并进 canonical（§7.0）。
> 来源：M10 修复 cron awareness——`append_message` 带外写入此前会被丢弃/遮蔽（parent_uuid 链断 +
> 异步 writer 未 flush + 内存历史缓存陈旧三层叠加），修复使其对后续轮可见，并新增 `invalidate_session_cache`。

## ADDED Requirements

### Requirement: 经 append_message 带外写入的消息对后续轮次可见

消费者(如 Gateway)可在不触发模型运行的前提下,经 `append_message` 把一条消息持久化进会话;该消息进入会话
线性历史,对该会话此后任意一轮运行可见——既不被丢弃,也不被运行时的内存历史缓存遮蔽。内核另提供
`invalidate_session_cache`,供消费者在带外改动会话持久化后显式失效内存缓存。

#### Scenario: 带外追加的消息进入下一轮上下文
- **GIVEN** 一个已运行过至少一轮的会话
- **WHEN** 消费者经 `append_message` 向该会话追加一条消息,随后再提交一轮运行
- **THEN** 该追加消息出现在这一轮的模型上下文里(不被陈旧缓存或历史链断裂遮蔽)
