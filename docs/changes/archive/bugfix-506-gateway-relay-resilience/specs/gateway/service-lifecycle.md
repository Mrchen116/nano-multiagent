# gateway Service Lifecycle Specification (delta for bugfix-506)

## MODIFIED Requirements

### Requirement: 断线后自动重连并补发未确认帧,期间外部 IM 主路径不受影响

WebSocket 断开后 Gateway 自动重连(指数退避,有上限),重连后重发 `node.register`;断开前未收到 ack 的上行帧在重连后补发,不丢消息。注册 ACK 后的节点绑定和 Agent 配置收敛在后台运行,不得占住业务收发路径;控制面工作失败仅保留诊断,不使已连接 Gateway 失去中继能力。业务帧等待远端 IM ACK 使用 10 秒默认上限,不得因正常的跨机往返延迟而主动断线。断线期间外部 IM 主路径(通道 → Gateway → 内核)仍可用。

#### Scenario: 重连后补发断线前未确认的帧
- **GIVEN** 一帧 `node.report` 已发出但 socket 在收到 ack 前断开
- **WHEN** Gateway 重连成功
- **THEN** 新连接上先发 `node.register`、再补发那帧 `node.report`,原 payload 不变

#### Scenario: 慢控制面收敛不阻塞已恢复的业务中继
- **GIVEN** Gateway 已收到 `node.register` ACK，但节点绑定或 IM 上的 Agent 配置读取缓慢或暂时失败
- **WHEN** 用户随后经 Web IM 发送消息，或 Gateway 上行一条业务帧
- **THEN** 该消息与业务帧仍在既有连接上继续中继
- **AND** 控制面收敛在后台继续；失败只留下可诊断日志，不关闭该连接

#### Scenario: 正常远端 ACK 延迟不触发重连
- **GIVEN** Gateway 已向远端 IM 发送一条业务帧
- **WHEN** IM 在超过 1 秒、但未超过默认 10 秒业务 ACK 上限时确认该帧
- **THEN** Gateway 接受该 ACK 并维持当前连接，不把这次延迟当作断线重连

#### Scenario: 重连采用指数退避并封顶
- **WHEN** IM 服务持续不可达,Gateway 反复重连
- **THEN** 重连间隔按指数退避增长直到上限(不无限激增、不放弃)

#### Scenario: control rejection 与普通断线使用同一退避
- **WHEN** IM 以 protocol error 拒绝 `node.register` 或 `node.heartbeat`
- **THEN** Gateway 断开当前 socket，保留未受影响的业务队列，并在下一次连接前执行既有指数退避
- **AND** backoff 只在新连接的 register ACK 后重置，不能因 transport connect 成功但注册失败而形成热循环

#### Scenario: send yield 内到达的匹配响应不会丢失
- **GIVEN** 一帧已经取得唯一 wire owner 并对 transport 可见，但本地 `send()` coroutine 尚未返回
- **WHEN** IM 在该窗口返回匹配 ACK、channel result 或 generic error
- **THEN** Gateway 把响应结算给同一 owner且只结算一次；wrong type/request 不释放 owner，后继 FIFO 不会永久阻塞

#### Scenario: IM 离线时外部 IM 主路径仍可用
- **GIVEN** IM 服务不可达
- **WHEN** 外部通道来一条入站消息
- **THEN** 该消息照常走通道 → Gateway → 内核 → 回发,Agent 执行不受 IM 离线影响(本地自治)
