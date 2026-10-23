# Task continuation delta

## ADDED Requirements

### Requirement: Task 自动推进 SHALL 以当前事实与可验证结果为准

#### Scenario: 阻塞前与等待复查
- **WHEN** Agent 推进 doing 任务或到期检查 waiting
- **THEN** 检查当前状态与工具结果，尝试授权内替代途径及独立部分，重新判断原阻塞是否必要；完成须有可验证结果。
- **AND** Schedule 唤醒不提供新授权，不重开 paused/closed/done/in_review。

### Requirement: Task waiting 的下次复查 SHALL 在未来一小时以内

#### Scenario: 新增与续期
- **WHEN** 提交新增或变更 waiting 关联
- **THEN** 校验原生 Schedule 的真实下一执行时间在未来一小时以内；超限拒绝且任务保持原状，无统一默认等待间隔。
- **AND** 通用 Schedule 可使用更长时间。

### Requirement: Task 等待与结果反馈 SHALL 交付到固定所属聊天

#### Scenario: 跨聊天与 Agent 派发
- **WHEN** Task 成功进入 waiting 或提交结果
- **THEN** 反馈回到 Task 固定所属聊天；等待说明包含实际进展、阻塞、尝试、所需协作与下次检查；Global 以 send_message 实际交付。
- **AND** 相同已确认反馈不重复发送；发送失败/未知不伪造送达、不改变真实 waiting，其他独立工作继续。

#### Scenario: SingleThread 已确认显式交付
- **WHEN** SingleThread 本轮 send_message 已确认送达本轮绑定聊天，模型以 NO_REPLY 收尾
- **THEN** 不公开哨兵；其他聊天、未确认发送或可见审批不被该交付标记吞掉。

#### Scenario: 停止优先于旧排队输入
- **WHEN** 真人 /stop 已暂停 Task，但原生 inbox 仍有停止前收到的答复或定时输入
- **THEN** 解除停止隔离前将受信停止事实持久化，并保证首次后续模型步可见；模型与独立审批均区分原消息时序，旧输入不能被视为停止后的恢复授权。
- **AND** 停止后新的明确真人恢复仍可作用于对应 Task；通知持久化失败保持 stop pending，不伪报完成。

### Requirement: 自动失败屏障 SHALL 与 Task 业务状态分离

#### Scenario: 故障与修复
- **WHEN** 读取、持久化或模型故障发生
- **THEN** 停止受影响的无效自动重复，不伪造业务状态；相关运行恢复后可重新评估。普通参数与版本错误允许模型修正。

#### Scenario: 拒绝与新输入
- **WHEN** 审批拒绝后出现无关通知、心跳或不同动作的同名工具成功
- **THEN** 不自动解除原拒绝动作的重试屏障；新输入与合法独立工作仍可处理，实际动作仍通过原审批链。
