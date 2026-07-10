# gateway delta-spec — bugfix-441

> 对齐: bugfix-441

本 unit 对 `docs/specs/gateway/spec.md` 的增量。

## ADDED Requirements

### Requirement: Gateway 中继工具调用时,执行中即转发参数侧展示

Gateway 把内核工具调用事件中继给 IM 时,工具**开始执行**(tool_start → `tool_call_upserted`)的中继帧携带 presenter 在该阶段产出的参数侧展示——`summary`(经 `output` 字段)与参数侧 `detail`;工具**执行结束**(tool_end → `tool_call_completed`)的中继帧携带含结果的完整 `detail`。Gateway 纯透传 presenter 产出的字段,不按工具语义增删。

#### Scenario: 工具执行中的中继帧携带参数侧展示
- **GIVEN** 一个其 presenter 在执行开始即产出 presentation 的工具被调用
- **WHEN** Gateway 中继该工具的 tool_start 事件给 IM
- **THEN** `tool_call_upserted` 帧携带 presenter 的 `summary`(写入 `output`)与参数侧 `detail`(presenter 在 format_start 产出的字段)
- **AND** presenter 在 format_start 未产 `detail` 的工具,该帧不含 `detail`(仅 `output`/已有的 `emoji`)

#### Scenario: 工具执行结束的中继帧携带完整展示
- **WHEN** Gateway 中继该工具的 tool_end 事件给 IM
- **THEN** `tool_call_completed` 帧携带 presenter 的 `summary`(写入 `output`)与含结果的完整 `detail`
