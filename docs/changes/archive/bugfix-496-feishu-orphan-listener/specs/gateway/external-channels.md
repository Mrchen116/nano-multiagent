# gateway external-channels Specification (delta for bugfix-496)

## ADDED Requirements

### Requirement: 托管飞书 listener 不得脱离 Gateway 存活

Gateway 启动的每个托管飞书 listener 与创建它的 Gateway 共享退出生命周期。无论 Gateway 是否有机会执行正常关闭流程，Gateway 终止后都不得留下继续占用飞书长连接或接收消息的旧 listener；Gateway 重启只建立当前 listener。连接空闲本身不触发退出或重连。

#### Scenario: 正常停止或重启 Gateway 时回收旧 listener
- **GIVEN** Gateway 已连接一个托管飞书 channel
- **WHEN** 运维者正常停止或重启 Gateway
- **THEN** 旧 Gateway 的飞书 listener 随其退出
- **AND** 重启后只有当前 Gateway 的 listener 接管该 Bot

#### Scenario: Gateway 无法执行清理便异常终止
- **GIVEN** Gateway 已连接一个托管飞书 channel
- **WHEN** Gateway 因崩溃、强制终止或其他原因未执行正常关闭便消失
- **THEN** 从确认原 Gateway 进程身份消失起 3 秒内，该 Gateway 启动的飞书 listener 原进程身份也消失
- **AND** 旧 listener 不再占用飞书长连接或接收用户消息

#### Scenario: 异常退出后重启恢复稳定消息路径
- **GIVEN** 托管飞书 channel 所属 Gateway 曾异常终止且已重新启动
- **WHEN** channel 收敛为已连接，用户连续向 Bot 发送应触发回复的消息
- **THEN** 每条消息都由当前 Gateway 接收并按既有行为回复
- **AND** 用户消息与回复继续同步到内部 IM 影子会话，不因旧 listener 而随机缺失或重复

#### Scenario: 正常空闲不改变 listener 状态
- **GIVEN** Gateway 与托管飞书 channel 正常运行但暂时没有入站消息
- **WHEN** channel 保持空闲
- **THEN** listener 不会仅因没有入站消息而退出、降级或主动重连
