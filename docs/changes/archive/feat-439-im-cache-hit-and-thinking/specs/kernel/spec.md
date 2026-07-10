# kernel 契约层增量 — feat-439

> 本文件是 feat-439 对长青契约层 `docs/specs/kernel/spec.md` 的**增量草案**（delta-spec）。
> 收尾由 change-orchestrator 据实际 diff 校正后并入 canonical。视角=经 `agent.sdk` 的消费者。

## ADDED Requirements

### Requirement: 缓存使用量随 token 用量一并对外

#### Scenario: 一轮含多次模型调用
- **WHEN** 一次助手回复完成
- **THEN** 对外的 token 用量里，命中缓存的输入量、与可用于计算命中率的总输入量，都是这一轮所有模型调用的累计值
- **AND** 跨 provider 口径已归一，命中率 = 命中输入量 ÷ 总输入量，取值落在 0%–100%

#### Scenario: provider 不返回缓存信息
- **WHEN** 上游 provider 的用量里没有缓存字段
- **THEN** 对外的缓存输入量为 0（消费者据此得到 0% 命中率），不报错

### Requirement: 每次模型调用的思考内容随其回合对外

#### Scenario: 一轮含多次模型调用、各自有思考
- **WHEN** 一轮助手回复完成、其中多次模型调用各自产生了思考
- **THEN** 对外可观察到这一轮的多段思考，各段保留其相对于工具调用的先后次序

#### Scenario: 某次模型调用无思考
- **WHEN** 某次模型调用没有产生思考内容
- **THEN** 对外不为该次调用产出思考段
