# kernel runs Specification (delta for bugfix-536)

## ADDED Requirements

### Requirement: 自动恢复向 SDK 消费者提供可结算的 pending 交接

消费者经 `try_steer()` 成功注入一条消息时，返回的 `RunInfo` 带一个 Kernel-owned opaque `pending_id`。若该消息在消费前因非用户终态转交后续 run，消费者可从后续 run 的 queued `run_status` event 读取完整 continuation descriptor（含 `recovery_id`、直接 `predecessor_run_id`、batch index、origin 和该 batch 的 `pending_ids`）；内核随后在同一 session stream 恰好发布一次 recovery settlement，明确所有 batch 已 scheduled、没有 batch，或无法恢复。

#### Scenario: 消费者按 pending identity 关联恢复 batch
- **GIVEN** 消费者已成功 steer 多条消息到活跃 run，并保留各自 `pending_id`
- **WHEN** 该 run 因非用户原因在消费前终止，内核将未消费消息分成一个或多个后续 batch
- **THEN** 每个后续 batch 的 queued status 都携带直接前序 run、batch identity 和该 batch 的完整 `pending_ids`
- **AND** 消费者可不依赖时间相邻、session 当前 active id 或 origin 猜测，将每条已接受消息关联到唯一 batch

#### Scenario: recovery settlement 可靠收口
- **GIVEN** 一个非用户终态有尚未消费的 pending 消息
- **WHEN** 内核完成该批消息的恢复调度判定
- **THEN** stream 恰好产生一次带相同 `recovery_id` 的 settlement，声明 `scheduled`、`none` 或 `unavailable`，并在 `scheduled` 时列出全部 successor run id
- **AND** 用户主动 interrupt 的 held pending、正常同-run steer 和无 pending 的终态不产生 recovery descriptor 或 settlement

## MODIFIED Requirements

### Requirement: alive-but-quiet 窗口经 stream 持续发出 liveness 事件

当一条 run 处于“活着但暂无业务输出”的窗口（执行静默长工具、等待主模型或自动压缩摘要模型返回、parked 等待用户权限决策）时，内核必须经 `kernel.stream` 周期性发出 liveness 事件（携带 run_id），间隔显著小于消费者侧的存活判定窗口。该事件仅表征“该 run 仍存活”，消费者可据其判定存活而不误判为卡死。四类窗口走同一事件通路，消费者无需按窗口类型分别豁免。

#### Scenario: 执行静默长工具期间 stream 仍有事件
- **GIVEN** 某 run 正在执行一个长时间无标准输出的工具（如长命令）
- **WHEN** 消费者消费 `kernel.stream(session_id)`
- **THEN** 在工具执行全程内，stream 周期性产出携带该 run_id 的 liveness 事件（不必等工具结束才出现）

#### Scenario: 等待主模型返回期间 stream 仍有事件
- **GIVEN** 某 run 正在等待主模型返回且长时间未产出业务事件
- **WHEN** 消费者消费 `kernel.stream(session_id)`
- **THEN** 等待期间 stream 周期性产出携带该 run_id 的 liveness 事件

#### Scenario: 自动压缩等待期间 stream 仍有事件
- **GIVEN** 某 run 正在自动整理过长上下文，内部摘要尚未产生用户可见业务输出
- **WHEN** 消费者消费 `kernel.stream(session_id)`
- **THEN** 摘要等待期间 stream 周期性产出携带该父 run id 的 liveness 事件
- **AND** 摘要的内部内容、工具和权限过程不作为父 run 的业务事件泄漏

#### Scenario: parked 等待权限决策期间 stream 仍有事件
- **GIVEN** 某 run parked 在等待用户权限决策、长时间未产出业务事件
- **WHEN** 消费者消费 `kernel.stream(session_id)`
- **THEN** 等待期间 stream 周期性产出携带该 run_id 的 liveness 事件（与工具/主模型/自动压缩等待同一事件通路），消费者据此判存活，无需 permission 专用豁免
