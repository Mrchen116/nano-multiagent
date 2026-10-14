# IM auth-tenancy Specification (delta for bugfix-608)

## ADDED Requirements

### Requirement: 用户时区由前台客户端自动报告并持久同步到所属 Gateway

浏览器和 iOS SHALL 在打开、回前台以及发送消息时读取系统时区，SHALL NOT 要求用户填写 timezone；后台不持续覆盖账号时区。IM SHALL 保存最近报告的合法时区，只有值变化时写入并通知所属节点；Gateway 重连能取得最新值并缓存供离线渠道和 Heartbeat 使用。

#### Scenario: 多设备切回原设备
- **GIVEN** 上海设备曾报告上海，另一设备随后报告东京
- **WHEN** 用户回到上海设备前台
- **THEN** 即使其系统时区未变化，也重新报告上海，IM 和所属 Gateway 使用上海
- **AND** 相同值再次报告不产生数据库更新或通知。

#### Scenario: 关闭客户端后继续工作
- **GIVEN** 用户系统时区已经成功同步
- **WHEN** 浏览器或 iOS 关闭，飞书输入或 Heartbeat 到达
- **THEN** Gateway 使用保存的用户时区，不以 Gateway 所在地代替。

#### Scenario: 消息时间快照
- **WHEN** 用户发送消息后改变时区或重试同一幂等发送
- **THEN** 原消息保留创建时的发生时间和时区，不因当前账号时区改变而重写。
