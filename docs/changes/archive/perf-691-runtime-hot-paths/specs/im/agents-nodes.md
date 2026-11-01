# IM agents-nodes Specification (delta for perf-691)

## MODIFIED Requirements

### Requirement: 浏览器经用户维 WebSocket 接收和重放当前成员事件

浏览器以当前 active 账号的 Bearer access 调 `POST /im/v1/auth/ws-ticket` 取得短时一次性票据，再经 `/im/ws/user?ticket=...` 建用户事件流。缺失、非法、过期、已消费的票据或不匹配的 Origin 被拒绝；不能使用旧 JWT 查询串/子协议或 user_id 绕过。票据绑定当前 session 和资格，登出/停用后不能继续使用；长期 JWT 不进入 WS URL。
握手后发 `{op:"resume", after_event_id:N}` 即回放该用户当前参与聊天范围内、`event_id > N` 的事件帧
(`op:"event"`),非成员聊天事件不投递；个人节点／配置事件仍只向 owner 发送。`GET /im/v1/sync` 给出会话列表快照 + 全局 `max_event_id`,供前端在
`resync_required` 后对齐游标。浏览器短暂断网或登录凭证自动更新后,使用当前登录身份恢复连接和游标;
账号切换后不再接收前一账号事件。

#### Scenario: 无效票据与旧认证方式被拒
- **WHEN** 浏览器连接缺少有效 ticket，票据过期/重复消费，或仅提供旧 token/user_id
- **THEN** 连接被服务端关闭(policy violation),收不到事件帧

#### Scenario: 合法票据连接并 resume 回放成员事件
- **GIVEN** 已授权用户在自己会话里发过消息
- **WHEN** 浏览器以当前会话新领的一次性 ticket 连上后发 `{op:"resume", after_event_id:0}`
- **THEN** 收到 `op:"event"` 帧,含 `message.sent`、`message.delivered` 等 `event_type`;仅包含当前身份可访问的事件

#### Scenario: sync 返回快照与全局游标
- **WHEN** 前端 `GET /im/v1/sync`
- **THEN** 200 含 `items`(会话列表)与 `max_event_id`(无事件时为 0)。Web 建连或重新同步时使用 `?view=cursor`，经相同账号资格检查后只返回同一个 `max_event_id`。

#### Scenario: 长时间登录后短暂断网自动恢复
- **GIVEN** 用户已在 Web IM 持续登录一段时间
- **WHEN** 浏览器网络短暂中断后恢复
- **THEN** 浏览器以当前有效登录身份新领 ticket 后恢复用户流,继续收到本账号的新事件,无需退出后重新登录

#### Scenario: 切换账号后只接收新账号事件
- **WHEN** 用户退出账号 A 并登录账号 B
- **THEN** 浏览器停止接收 A 的事件,后续用户流只交付 B 当前成员范围内的聊天事件及其个人事件

#### Scenario: 票据签发失败与资格撤销
- **WHEN** 浏览器票据请求被拒、限流或当前成员停用
- **THEN** 显示可行动的重新登录/等待/成员状态反馈，不重试长期 JWT 旁路，不无限快速重连；停用或退出后旧连接停止投递。
