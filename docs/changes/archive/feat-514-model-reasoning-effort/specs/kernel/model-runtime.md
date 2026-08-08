# kernel (agent) - Model Runtime Specification (delta for feat-514)

## ADDED Requirements

### Requirement: 完整 session runtime 可携带未来模型请求的 provider-neutral 推理强度

消费者可在 `SessionRuntimeConfig` 为一个 session 的未来正常模型请求提供可选的
`reasoning_effort`。该值与 model、prompt、skills、tools、features 同属 complete runtime：创建、
读取、fork、runtime identity 和 durable reconfigure 保持其语义。Kernel 不把它解释为某个产品的
配置；它只在随后开始的普通模型请求中传给已选 provider adapter，由 adapter 使用其协议字段。

#### Scenario: 消费者创建 session 后读取完整 runtime
- **WHEN** 消费者以带 `reasoning_effort` 的 `SessionRuntimeConfig` 创建 session，随后读取 runtime
- **THEN** 读取结果保留等价的推理强度和 runtime identity

#### Scenario: consumer reconfigure 仅影响之后开始的模型请求
- **GIVEN** 一个 session 已有开始执行的 run
- **WHEN** 消费者 durable reconfigure 该 session 的 `reasoning_effort`
- **THEN** 已开始的 run 使用开始时的完整 runtime
- **AND** 后续开始的正常模型请求使用新的推理强度

#### Scenario: fork 保留 future runtime 语义
- **WHEN** 消费者 fork 一个带 `reasoning_effort` 的 session
- **THEN** fork 得到的 session 在未被再次 reconfigure 前保留等价的 future runtime

#### Scenario: 传入 provider 的正常模型请求携带 runtime 推理强度
- **WHEN** 消费者以带 `reasoning_effort` 的 complete runtime 开始一轮正常对话
- **THEN** 该轮的 provider adapter 以其协议形式发送该推理强度
- **AND** Kernel 不将其用于独立 hook/审批模型调用
