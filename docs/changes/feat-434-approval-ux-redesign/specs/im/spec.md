# IM 契约层增量 — feat-434

> 本文件是 feat-434 对 `docs/specs/im/spec.md` 的增量草案（design 期声明），收尾由 orchestrator 校正后并入 canonical。

## MODIFIED Requirements

### Requirement: 工具调用的授权决策随消息持久化与下发

IM 持久化并下发的工具调用数据，在原有字段（status / reason / detail / emoji / duration）之外，携带「该工具调用是否经用户显式授权/拒绝」的标识。该标识在实时下发（WebSocket）与历史加载（REST）两条路径上一致，页面刷新后不丢失；无标识的历史工具调用保持兼容（不携带该字段）。

#### Scenario: 经用户授权的工具调用在历史加载中保留标识

- **GIVEN** 一条已落库的 agent 消息，其中某工具调用经用户授权允许
- **WHEN** 客户端重新加载该会话历史
- **THEN** 该工具调用数据携带「经用户授权允许」标识

#### Scenario: 旧工具调用无标识仍可加载

- **GIVEN** 一条历史消息的工具调用是在本能力上线前落库的、无授权标识
- **WHEN** 客户端加载该会话
- **THEN** 该工具调用正常加载，不携带授权标识、不报错
