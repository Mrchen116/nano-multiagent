# Gateway 契约层增量 — bugfix-433

> 本 unit 对 `docs/specs/gateway/spec.md` 的增量。每条 Scenario 主语 = 经 IM 与 agent 交互的用户。收尾由 orchestrator 软对账并入 canonical。

## ADDED Requirements

### Requirement: 用户经 IM 发送的图片被 Agent 看到，且在后续轮次仍可追问

用户在 IM 会话里给 agent 发送图片时，agent 当轮即能基于图片内容作答；在同一会话的后续轮次，用户即便只发文字追问那张图，agent 仍能据其作答。异常图片不致中断会话。

#### Scenario: 发图即问，当轮可答
- **WHEN** 用户在一条消息里同时发送一张图片和关于该图的问题
- **THEN** agent 当轮基于图片内容作答，而非表示看不到图

#### Scenario: 上一轮发图，下一轮只发文字仍可追问
- **GIVEN** 用户上一轮发过图片并得到基于该图的回复
- **WHEN** 用户在同一会话下一轮只发文字追问这张图
- **THEN** agent 仍能基于上一轮那张图作答

#### Scenario: 异常图片不中断会话
- **WHEN** 用户发送一张异常（超大 / 损坏 / 无法获取）的图片
- **THEN** 会话不崩溃，agent 至少能就该轮给出可继续的回应
