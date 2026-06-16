# IM Specification (delta for bugfix-417)

> 本 delta 对既有 canonical 做 diff。本 unit 把 relay 看门狗的 permission 专用豁免泛化为统一 liveness（故 REMOVED 旧 permission-特例 requirement + ADDED 新统一 liveness requirement），并修正工具徽标的失败原因映射（watchdog-reap 从「执行超时」改「已中断」、「执行超时」改归工具自身 deadline），故 MODIFIED 既有徽标 requirement。

## REMOVED Requirements

### Requirement: 等人工权限决策的消息不被中继看门狗误判为失败

（泛化为下方 ADDED 的统一 liveness 看门狗；等权限不再是专用特例，而是 liveness 心跳的三类窗口之一。）

## ADDED Requirements

### Requirement: 中继看门狗按 liveness 判存活，不误杀活着但安静的消息

中继看门狗判定某 `running` 消息是否失去进展时，依据其存活信号是否仍在刷新：agent run 在"活着但安静"窗口内产生的 liveness 心跳（执行静默长工具 / 等待 LLM / 等待用户权限决策，三类同源）必须推进该消息的存活判定（推进最近事件时间戳或刷新通用存活标记），使活跃 run 不被误判为卡死。看门狗对上述窗口不再按类型分别豁免（不再有 permission 专用特例）。只有在判定窗口内既无新事件也无 liveness 心跳的消息才被回收为 `failed`；维持存活信号的 Gateway/内核崩溃后心跳停止，存活信号 stale 超过回收阈值，该消息仍被正常回收，不永久停留 running。

#### Scenario: 活跃长工具的消息不被误收
- **GIVEN** 某 running 消息对应的 run 正在执行静默长工具并周期产生 liveness 心跳
- **WHEN** 看门狗扫描
- **THEN** 该消息因存活信号持续刷新而不被判超时收尾

#### Scenario: 等待 LLM 的消息不被误收
- **GIVEN** 某 running 消息对应的 run 长时间等待 LLM 返回但连接活着并周期产生 liveness 心跳
- **WHEN** 看门狗扫描
- **THEN** 该消息不被判超时收尾

#### Scenario: 等待权限的消息不被误收
- **GIVEN** 某 running 消息对应的 run parked 等待用户权限决策、Gateway 存活并周期产生 liveness 心跳
- **WHEN** 看门狗扫描
- **THEN** 该消息不被判超时收尾，无需 permission 专用豁免；用户决定后仍能继续

#### Scenario: 真静默消息仍被兜底收尾
- **GIVEN** 某 running 消息在判定窗口内无任何新事件（含心跳）、存活信号 stale 超过回收阈值
- **WHEN** 看门狗扫描
- **THEN** 该消息被翻为 `failed` 并推 `relay.failed`，徽标随之收口，不永久停留 running

## MODIFIED Requirements

### Requirement: 工具徽标按中断原因显示终态

run 异常终止、工具自身超时或工具被拒绝时,IM 工具徽标必须从「运行中」收口为一个**按原因区分**的非成功终态,不再停留在转圈状态。失败原因区分:工具因自身 deadline 到点被掐 → 「执行超时」(耗时过长);run 因看门狗 liveness 收尸或进程异常/中断 → 「已中断」(卡死/中断)。

#### Scenario: 在飞工具按原因收口
- **GIVEN** 一条消息里某工具已开始执行(徽标运行中)
- **WHEN** 终态下发到前端
- **THEN** 该工具徽标收口为对应文案:工具自身超时显示「执行超时」、看门狗 liveness 收尸或其他异常终止显示「已中断」

#### Scenario: 被拒绝的工具显示已拒绝
- **GIVEN** 一个工具被 auto_mode 分类器自动 block 或被用户在权限卡片上拒绝
- **WHEN** 该工具的终态渲染
- **THEN** 徽标显示「已拒绝」(区别于「执行超时」「已中断」)

#### Scenario: 权限未决期间显示等待批准
- **GIVEN** 一个工具正等待用户权限决策(未批未拒)
- **WHEN** 徽标渲染
- **THEN** 显示「等待批准」,既不收口为失败也不显示「已拒绝」

#### Scenario: 已完成工具徽标不被改写
- **GIVEN** 同一条消息里其他工具已正常完成
- **WHEN** 在飞工具收口
- **THEN** 已完成工具的徽标保持原终态不变
