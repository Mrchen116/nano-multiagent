# gateway 契约层增量 — feat-439

> feat-439 对 `docs/specs/gateway/spec.md` 的增量草案（delta-spec）。
> 视角=Gateway 中继到 IM 的可观察结果。

## ADDED Requirements

### Requirement: 整轮多段思考按时序中继到 IM

#### Scenario: 含多段思考的一轮回复
- **WHEN** 一轮带多段思考的助手回复经 Gateway 中继（含只思考、不输出正文的回合）
- **THEN** IM 收到的该轮消息包含全部思考段，且每段带可还原其与工具调用时序的次序信息

#### Scenario: 只思考不输出正文的回合
- **WHEN** 某回合只产生思考、没有正文
- **THEN** 其思考作为该轮过程的一部分中继到 IM，且不因此产生一条空正文消息

#### Scenario: 既无正文也无思考的回合
- **WHEN** 某回合既无正文也无思考
- **THEN** 不向 IM 中继该回合（不产生空消息）
