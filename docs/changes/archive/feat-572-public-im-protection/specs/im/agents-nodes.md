# IM agents-nodes Specification (delta for feat-572)

## MODIFIED Requirements

### Requirement: 设备绑定把节点归属到当前用户

Gateway 和其全部 Agent 由同一个有效公司成员管理；绑定与整体换绑要求本机持有设备身份的操作者明确确认及目标账号有效，不额外要求公司管理员批准。

#### Scenario: 首次绑定与同账号重试
- **WHEN** 本机发起绑定，active 用户在网页确认目标账号且本机明确接受
- **THEN** 节点及全部 Agent 归属该用户；响应可辨认操作、设备、接收人和当前状态，缺少必填信息明确失败。
- **AND** 同一操作重试幂等，不重建身份、配置或重复初始化渠道。

#### Scenario: 已绑定设备整体交接
- **WHEN** 有权操作本机的人将 Gateway 确认交给另一 active 成员
- **THEN** node、全部 Agent 及相关配置/渠道管理权一起转移，身份、工作记录和本机 workspace 保留；旧管理者及旧机器连接失去相应控制权。
- **AND** 新管理者不自动成为旧真人私聊的成员；其他成员只使用 Agent，不因此取得配置管理权。

#### Scenario: 旧管理者停用后仍可合法交接
- **WHEN** 旧 owner 已停用，但操作者可完成本机设备证明和新成员确认
- **THEN** 可以整体换绑，不要求先恢复旧 owner 或管理员额外批准；停用不会永久封禁物理设备。

#### Scenario: 抢绑、取消与中断
- **WHEN** 远端用户只知道 node_id，或重放旧操作/伪造本机确认
- **THEN** 不能绑定、换绑或替换该设备的登记身份。
- **WHEN** 确认前取消，或提交期间连接中断
- **THEN** 取消不改变归属；中断能核实并恢复同一提交结果，不出现部分 Agent 转移或旧账号继续控制的状态。

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
- **THEN** 200 含 `items`(会话列表)与 `max_event_id`(>0);前端据其对齐用户流游标

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

### Requirement: 登录用户可发现人和 Agent，管理配置保持个人归属

#### Scenario: 从目录直接发起聊天
- **WHEN** 已登录的有效公司成员按名字或稳定 ID 搜索联系人
- **THEN** 可辨认真人与 Agent 并直接私聊，不要求已有 Gateway、好友申请或管理者逐人授权；无匹配时显示空结果。

#### Scenario: 公开 Agent 资料与配置分开
- **GIVEN** Agent 由另一人管理
- **WHEN** 用户浏览该 Agent 资料
- **THEN** 能看到名字、管理者、设备名、在线状态及工作模式，能发消息，全局 Agent 可进入 Work；不能读取完整配置、凭据或保存管理修改。

#### Scenario: 一个人多 Gateway，单台离线
- **WHEN** 用户绑定多台 Gateway，其中一台离线
- **THEN** 可辨认各 Agent 所属设备与在线状态，其余设备和人际沟通正常；设备及其 Agent 仍只有原管理者管理。
