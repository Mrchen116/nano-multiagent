# IM Agents and Nodes delta — refactor-460

> 对齐 canonical: `docs/specs/im/agents-nodes.md`。

## MODIFIED Requirements

### Requirement: 浏览器经用户维 WebSocket 收事件流,鉴权后只回放本租事件

浏览器经 `/im/ws/user` 建用户维事件流;身份取自 JWT(`?token=<jwt>` 查询串或 `Sec-WebSocket-Protocol:
bearer.<jwt>` 子协议),无 token / 非法 token 立即关闭;身份只认 JWT,单凭 `?user_id=` 不构成信任锚。
握手后发 `{op:"resume", after_event_id:N}` 即回放该用户 owner 范围内、`event_id > N` 的事件帧
(`op:"event"`),跨租事件不投递。`GET /im/v1/sync` 给出会话列表快照 + 全局 `max_event_id`,供前端在
`resync_required` 后对齐游标。浏览器短暂断网或登录凭证自动更新后,使用当前登录身份恢复连接和游标;
账号切换后不再接收前一账号事件。

#### Scenario: 无 token / 非法 token / 仅 user_id 的连接被拒
- **WHEN** 浏览器 `websocket_connect("/im/ws/user")`(无 token,或 `?token=not-a-jwt`,或仅 `?user_id=`)
- **THEN** 连接被服务端关闭(policy violation),收不到事件帧

#### Scenario: 合法 token 连接并 resume 回放本租事件
- **GIVEN** 已授权用户在自己会话里发过消息
- **WHEN** 浏览器以 `?token=<合法 jwt>` 连上后发 `{op:"resume", after_event_id:0}`
- **THEN** 收到 `op:"event"` 帧,含 `message.sent`、`message.delivered` 等 `event_type`;只含本 owner 事件

#### Scenario: sync 返回快照与全局游标
- **WHEN** 前端 `GET /im/v1/sync`
- **THEN** 200 含 `items`(会话列表)与 `max_event_id`(>0);前端据其对齐用户流游标

#### Scenario: 长时间登录后短暂断网自动恢复
- **GIVEN** 用户已在 Web IM 持续登录一段时间
- **WHEN** 浏览器网络短暂中断后恢复
- **THEN** 浏览器以当前登录身份恢复用户流,继续收到本账号的新事件,无需退出后重新登录

#### Scenario: 切换账号后只接收新账号事件
- **WHEN** 用户退出账号 A 并登录账号 B
- **THEN** 浏览器停止接收 A 的事件,后续用户流只交付 B 的 owner 范围事件
