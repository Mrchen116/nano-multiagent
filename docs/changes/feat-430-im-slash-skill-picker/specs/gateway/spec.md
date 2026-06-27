# feat-430 delta-spec: gateway

> 对齐 canonical: [`docs/specs/gateway/spec.md`](../../../../specs/gateway/spec.md)
> 本文件只列 feat-430 对 Gateway 对外可观察行为的增量。草案——收尾由 orchestrator 据实际 diff 校正并软对账并入 canonical。

## MODIFIED Requirements

### Requirement: /stop 控制命令中断当前运行

在 canonical 同名 Requirement 基础上，补齐群聊场景：picker 补入的提及形式 `/stop` 被识别；裸 `/stop` 不受群聊 @ 提及门控限制（消解 canonical `Requirement: 群聊只在被 @提及 / 回复 Agent / 控制命令时触发 Agent` 已声明"控制命令触发"但代码丢弃群聊裸 `/stop` 的 drift）。

#### Scenario: 群聊里 picker 补入的提及形式 /stop 被识别
- **GIVEN** 群聊里某 Agent 正在运行
- **WHEN** 用户用 slash picker 发出指向该 Agent 的 `/stop`（picker 补入的提及形式）
- **THEN** 该 `/stop` 被识别为控制命令，中断该 Agent 当前运行，用户收到「已停止当前操作。」

#### Scenario: 群聊裸 /stop 不受 @ 提及门控限制
- **GIVEN** 群里某 Agent `group_reply_policy=MENTION` 且正在运行
- **WHEN** 用户发裸 `/stop`（不 @ 任何 Agent）
- **THEN** 该 `/stop` 仍送达群内 Agent 并中断正在运行的那个；当前无运行的 Agent 不受影响（幂等，无报错）
