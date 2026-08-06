# IM Gateway Relay Specification (delta for bugfix-497)

> Target canonical: `docs/specs/im/gateway-relay.md`

## ADDED Requirements

### Requirement: 外部 shadow live frame 携带稳定消息身份与源时间线事实

Gateway 为 external shadow Agent 气泡上行 live frame 时，可在 `turn_start` 提供稳定来源消息身份，在思考/工具 frame 提供共享过程序号，在 terminal frame 提供 source elapsed。IM 以该身份幂等建立消息，并按来源顺序和耗时持久化；没有这些字段的普通 Gateway run 保持既有序号与耗时语义。

#### Scenario: turn_start 重试返回同一消息
- **GIVEN** IM 已按某 external shadow 来源身份建立 Agent 气泡
- **WHEN** Gateway 因 ACK 丢失重发相同 `turn_start`
- **THEN** IM 返回原 message id，不新增消息、不重复增加未读
- **AND** 已有正文、过程或 terminal 状态不被重置

#### Scenario: external shadow 过程顺序实时与恢复一致
- **WHEN** Gateway 上行带来源过程序号的思考与工具 frame
- **THEN** IM 按该序号持久化并实时下发过程项
- **AND** 随后的 terminal snapshot 与历史读取保持相同过程顺序

#### Scenario: external shadow terminal 使用 source elapsed
- **WHEN** Gateway 为 external shadow Agent 气泡上行带 source elapsed 的 terminal frame
- **THEN** IM 持久化并下发该耗时，live 完成与离线恢复口径一致
