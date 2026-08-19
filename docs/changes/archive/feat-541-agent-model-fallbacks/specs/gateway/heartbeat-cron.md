# gateway - Heartbeat and Cron Specification — feat-541 delta

> 落点: `docs/specs/gateway/heartbeat-cron.md`
> 投影自: feat-541 spec.md Requirement「心跳与定时任务走同一条备用链」

## ADDED Requirements

### Requirement: 心跳与 cron 走该 Agent 同一条模型备用链

Heartbeat tick 与 cron 执行使用与人工聊天相同的主模型 + 有序备用链及粘性规则。复用已有 Kernel session（含心跳优先使用的 canonical 直聊）时，第一次 admit 与随后经 `submit_message` 打进内核的 model 都必须是该 session 的 `candidates[0]`（有粘性就是备用）；不得省略、也不得再把保存的主模型当 explicit 打进去。主模型因可用性失败且该 run 尚未投出真实正文或工具时间线时，先投下带模型名的失败提示（若该路径对用户可见），再按备用链改用能用的模型并完成本次 tick/任务。成功切换且向用户发出可见内容时，内容前带与聊天相同的轻量切换说明。没配备用或整链耗尽时，每个失败候选留下带模型名的失败提示，没有伪装成功。

#### Scenario: 心跳在主模型不可用时仍能完成 tick
- **GIVEN** Agent 配备用列表
- **WHEN** 一次心跳 tick 时主模型因可用性失败，且尚未投出真实正文或工具时间线
- **THEN** 用户若能看见该次失败，失败提示带该模型名
- **AND** 该 tick 按备用链改用能用的模型并完成
- **AND** 若这次心跳向用户发出了成功可见内容，内容旁带与聊天相同的轻量切换说明

#### Scenario: 心跳复用已粘备用的直聊时仍用备用
- **GIVEN** 某 Agent 的 canonical 直聊已粘在备用模型 B
- **WHEN** 下一次心跳 tick 复用该 Kernel session
- **THEN** 该 tick 第一次就用 B，入队显式传入 B，不因传入保存的主模型或省略 model 而被内核拒
- **AND** 不先再撞已经失败的主模型

#### Scenario: 定时任务在主模型不可用时仍能跑完
- **GIVEN** Agent 配备用列表
- **WHEN** 一次 cron 任务执行时主模型因可用性失败，且尚未投出真实正文或工具时间线
- **THEN** 用户若能看见该次失败，失败提示带该模型名
- **AND** 该次执行按备用链改用能用的模型并完成
- **AND** 若这次任务向用户发出了成功可见内容，内容旁带与聊天相同的轻量切换说明

## MODIFIED Requirements

## REMOVED Requirements
