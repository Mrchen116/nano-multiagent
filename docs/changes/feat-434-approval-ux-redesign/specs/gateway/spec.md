# Gateway 契约层增量 — feat-434

> 本文件是 feat-434 对 `docs/specs/gateway/spec.md` 的增量草案（design 期声明），收尾由 orchestrator 校正后并入 canonical。

## ADDED Requirements

### Requirement: Gateway 向 IM 中继的工具调用携带授权决策

Gateway 把内核工具执行事件中继到 IM 时，除既有的 reason 徽标 / emoji / presentation detail 外，一并透传「该工具调用是否经用户显式授权/拒绝」的标识；自动放行的调用不携带。

#### Scenario: 经用户授权的工具调用被中继

- **WHEN** 内核报出一次经用户允许的工具调用执行
- **THEN** Gateway 中继给 IM 的该工具调用数据携带「经用户授权允许」标识

#### Scenario: 经用户拒绝的工具调用被中继

- **WHEN** 内核报出一次经用户拒绝的工具调用
- **THEN** Gateway 中继的该工具调用数据携带「经用户拒绝」标识
