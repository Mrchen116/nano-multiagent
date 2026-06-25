# 内核契约层增量 — feat-434

> 本文件是 feat-434 对 `docs/specs/kernel/spec.md` 的增量草案（design 期声明），收尾由 orchestrator 校正后并入 canonical。

## ADDED Requirements

### Requirement: 工具执行事件携带用户授权决策标识

内核经 `agent.sdk` 向消费者发出的工具执行事件，在原有「非成功终态分类」（denied / 超时 / 中断）之外，新增一个**授权决策标识**：当某次工具调用是经用户在权限卡上显式决策放行或拒绝时，事件携带该决策；自动放行的调用不携带。

#### Scenario: 用户显式允许的工具调用

- **GIVEN** 一次工具调用进入权限确认（auto_mode_gate ask）
- **WHEN** 用户显式允许后该工具执行
- **THEN** 消费者从该工具调用的执行事件可观察到「经用户授权允许」的标识

#### Scenario: 用户显式拒绝的工具调用

- **WHEN** 用户显式拒绝该工具调用
- **THEN** 消费者可观察到「经用户拒绝」的标识

#### Scenario: 自动放行的工具调用

- **WHEN** 一次工具调用未触发用户确认、被自动放行
- **THEN** 该工具调用的执行事件不携带授权决策标识
