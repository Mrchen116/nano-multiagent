# 内核契约层增量 — bugfix-433

> 本 unit 对 `docs/specs/kernel/spec.md` 的增量。每条 Scenario 主语 = 经 `agent.sdk` 调用内核的消费者（`coding_cli` / `personal_assistant`）。收尾由 orchestrator 软对账并入 canonical。

## ADDED Requirements

### Requirement: 消息携带图片块时图片送达模型并随会话历史保留

消费者经 `agent.sdk` 提交（`submit`）或追加（`append_message`）一条携带图片部件（image part）的消息时，图片须送达底层模型，且随会话历史持久化——同一会话后续轮次重建历史时，该图片仍作为图片内容呈现给模型，而非被降级为纯文本占位符。两条入口（`submit` / `append_message`）在「能携带并保留图片」这一点上行为一致。

#### Scenario: 提交含图片的消息，当轮模型即可见
- **WHEN** 消费者 `submit` 一条 parts 含 image part 的用户消息
- **THEN** 该图片送达模型并被模型理解（模型据其内容作答），而非被降级为 `[image:placeholder]` 纯文本占位

#### Scenario: 单条消息含多张图片时全部送达
- **WHEN** 消费者 `submit` 一条 parts 含多个 image part 的用户消息
- **THEN** 所有图片都送达模型（不因多部件内部展开而丢失其中任一张）

#### Scenario: 含图片的消息跨轮重建后图片仍在
- **GIVEN** 某会话已持久化过一条含图片的用户消息
- **WHEN** 消费者在同一会话发起新的一轮、内核重建该会话历史
- **THEN** 重建出的历史里那条消息仍带有图片内容，发往模型的请求中图片可见

#### Scenario: append_message 追加的图片同样被保留
- **WHEN** 消费者用 `append_message` 追加一条 parts 含 image part 的消息
- **THEN** 该图片随会话历史持久化，后续轮重建历史时仍可见（与 `submit` 行为一致）

#### Scenario: 纯文本消息的持久化与回放不受影响
- **WHEN** 消费者提交一条不含图片的纯文本消息并在后续轮重建历史
- **THEN** 其持久化与回放结果与本变更前一致，无可观察差异

#### Scenario: 含图消息触发模型错误后，后续轮不再因该图重复失败
- **GIVEN** 某含图片的消息触发了一次模型调用错误
- **WHEN** 消费者在同一会话提交后续消息、内核重建历史
- **THEN** 历史中那张图不再发往模型，后续消息不会因它重复触发同一错误（该消息的文本保留；纯文本消息的既有错误处理不受影响）

> 失败契约（图片无法获取 / 超大 / 损坏）属 **gateway 入站职责**（见 `specs/gateway/spec.md` 的「异常图片本轮停下、明确告知用户、可重发」），不在内核重复——决策5 已把图片校验前移到 gateway `submit` 前，到达内核的 image part 恒为已校验的 data URL，内核不产出失败信号。
