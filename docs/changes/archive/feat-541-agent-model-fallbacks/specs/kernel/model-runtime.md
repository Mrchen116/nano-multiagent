# kernel - Model Runtime Specification — feat-541 delta

> 落点: `docs/specs/kernel/model-runtime.md`
> 投影自: feat-541 spec.md Q9 + design.md 决策 1、2、6

## ADDED Requirements

### Requirement: 模型调用失败对消费者可见时必须带上该 run 的模型 id

消费者经 `stream` 收到的 provider 失败 assistant 文案必须包含本次 run 实际使用的模型 id，使同一会话连续失败时能区分是哪一个模型挂了。内核仍按既有 `is_provider_error` 语义把该条从下一轮模型上下文中滤掉。

#### Scenario: 失败文案含模型 id
- **GIVEN** 消费者已为某 session 配置 runtime 模型 M
- **WHEN** 该 run 因 provider 可用性失败而结束
- **THEN** 消费者收到的失败 assistant 文案含 M 的模型 id
- **AND** 下一轮普通模型请求的上下文不含该失败 assistant

### Requirement: run 失败终态向消费者暴露可判定的错误种类

当 run 因模型/provider 错误失败时，`run_status.error` 除 `code` / `message` 外携带稳定 `kind`，供产品层决定是否换另一个模型。`kind` 至少区分额度/欠费、过载、超时、限流、认证、上下文过长与其它。消费者只经 `agent.sdk` 读取该字段，不依赖内核内部异常类型。上下文过长与 compaction 失败仍走既有压缩/失败路径，不要求产品把它当成可换模型的种类。

#### Scenario: 可用性失败带 kind
- **WHEN** 某 run 因额度、过载、超时、限流或认证失败到达 `failed`
- **THEN** 消费者从该 run 的 `run_status.error` 读到对应 `kind`，不需要解析失败气泡正文

#### Scenario: 上下文过长带独立 kind
- **WHEN** 某 run 因上下文过长失败
- **THEN** `kind` 标识上下文过长，与额度/认证等可换模型种类不同

## MODIFIED Requirements

## REMOVED Requirements
