# IM gateway-relay Specification (delta for bugfix-536)

## MODIFIED Requirements

### Requirement: 中继看门狗按 liveness 判存活,不误杀活着但安静的消息

中继看门狗判定某 `running` 消息是否失去进展时，依据其存活信号是否仍在刷新：agent run 在“活着但安静”窗口内产生的 liveness 心跳（执行静默长工具 / 等待主模型返回 / 自动整理上下文 / 等待用户权限决策，四类同源）必须推进该消息的存活判定（推进最近事件时间戳或刷新通用存活标记），使活跃 run 不被误判为卡死。看门狗对上述窗口不按类型分别豁免。只有在判定窗口内既无新事件也无 liveness 心跳的消息才被回收为 `failed`；维持存活信号的 Gateway/内核崩溃后心跳停止，存活信号 stale 超过回收阈值时，该消息仍被正常回收，不永久停留 running。

#### Scenario: 活跃长工具的消息不被误收
- **GIVEN** 某 running 消息对应的 run 正在执行静默长工具并周期产生 liveness 心跳
- **WHEN** 看门狗扫描
- **THEN** 该消息因存活信号持续刷新而不被判超时收尾

#### Scenario: 等待主模型返回的消息不被误收
- **GIVEN** 某 running 消息对应的 run 长时间等待主模型返回但连接活着并周期产生 liveness 心跳
- **WHEN** 看门狗扫描
- **THEN** 该消息不被判超时收尾

#### Scenario: 自动整理上下文的消息不被误收
- **GIVEN** 某 running 消息对应的 run 正在自动整理过长上下文，且持续产生 liveness 心跳
- **WHEN** 看门狗扫描
- **THEN** 该消息因存活信号持续刷新而不被判超时收尾
- **AND** 摘要完成后同一聊天的后续回复照常投递

#### Scenario: 等待权限的消息不被误收
- **GIVEN** 某 running 消息对应的 run parked 等待用户权限决策、Gateway 存活并周期产生 liveness 心跳
- **WHEN** 看门狗扫描
- **THEN** 该消息不被判超时收尾，无需 permission 专用豁免；用户决定后仍能继续

#### Scenario: 真静默消息仍被兜底收尾
- **GIVEN** 某 running 消息在判定窗口内无任何新事件（含心跳）、存活信号 stale 超过回收阈值
- **WHEN** 看门狗扫描
- **THEN** 该消息被翻为 `failed` 并推 `relay.failed`，徽标随之收口，不永久停留 running
