# kernel - Runs Specification — feat-541 delta

> 落点: `docs/specs/kernel/runs.md`
> 投影自: feat-541 design.md 决策 1 replay-last-user 缝

## ADDED Requirements

### Requirement: 消费者可在模型失败后复用上一条用户消息换模型再跑

消费者在某 run 以模型可用性失败终态结束后，可为同一 session 换成另一个 runtime 模型，再发起不携带新 user parts 的下一 run。内核复用 transcript 里最近一条用户消息；不向消费者再投一条 user 消息。若该失败 run 已向消费者产出过非 provider-error 的 assistant 正文或工具事件，内核拒绝此次 replay，不原位重放。该入口不读取产品层备用列表，也不在一次 run 内切换模型。产品层以 `run_status.error.kind` 决定是否调用本入口，不以 assistant 正文是否为空或失败气泡文案为准。

#### Scenario: replay 不复制用户消息
- **GIVEN** 某 session 最近一轮因模型可用性失败结束，transcript 含用户消息与 provider-error assistant
- **WHEN** 消费者将该 session runtime 换成模型 B 并发起 replay-last-user
- **THEN** 新 run 以模型 B 请求 LLM，上下文含那条用户消息（失败 assistant 仍按既有规则过滤）
- **AND** 消费者不再收到一条新的 user 消息

#### Scenario: 仅 provider-error 气泡不阻止 replay
- **GIVEN** 某 run 只向消费者产出了 provider-error 失败 assistant，没有其它正文或工具事件
- **WHEN** 消费者将该 session runtime 换成模型 B 并发起 replay-last-user
- **THEN** 内核接受此次 replay

#### Scenario: 已有真实输出则不可 replay 原位重放
- **GIVEN** 某 run 已向消费者产出非 provider-error 的 assistant 正文或工具事件
- **WHEN** 该 run 随后失败
- **THEN** 消费者不能用 replay-last-user 原位重放该请求

## MODIFIED Requirements

## REMOVED Requirements
