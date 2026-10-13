# IM agents/nodes delta for bugfix-585

## MODIFIED Requirements

### Requirement: 节点上线/心跳/超时实时反映到 owner 的浏览器看板

注册和心跳更新在线状态；注册上线及连接离线转换向节点 owner 广播 node.status_changed。当前连接关闭、超时或撤权时持久化 offline 并向 owner 广播；超时标记 last_error=heartbeat_timeout，且不撤销凭据。已打开页面实时反映状态；离线发送沿用明确失败语义。重连注册后恢复 online，旧连接的延迟关闭不覆盖新连接。关联 Agent 的已有状态消费者同步收到 agent.status_changed。Nodes、Chat 和 Agent detail 均显示真实状态，状态更新不覆盖未保存配置输入。广播严格按 owner 隔离。

#### Scenario: 节点注册广播 online 给本租浏览器
- **WHEN** 节点注册成功
- **THEN** owner 的浏览器收到 online 事件，其他 owner 不收到。

#### Scenario: 心跳超时翻 offline 并广播
- **WHEN** IM 检测到当前节点心跳过期
- **THEN** 数据库/API/owner 页面变为 offline，广播包含 heartbeat_timeout；重复清理不重复广播。

#### Scenario: 断开与恢复一致
- **WHEN** 当前连接断开后重新注册
- **THEN** 页面先离线后在线，恢复后正常收发；旧连接关闭不导致假离线。

#### Scenario: 编辑中收到状态变化
- **WHEN** 用户在 Agent detail 尚未保存编辑时节点离线或恢复
- **THEN** 状态标识实时更新，未保存输入仍保留。

#### Scenario: 浏览器恢复订阅时补齐错过的状态
- **GIVEN** 节点状态在浏览器 HTTP 刷新后、实时订阅恢复前改变
- **WHEN** 浏览器重新订阅
- **THEN** owner 的已打开页面收敛到节点及关联 Agent 当前状态，无需人工刷新；其他 owner 不收到这些状态。
