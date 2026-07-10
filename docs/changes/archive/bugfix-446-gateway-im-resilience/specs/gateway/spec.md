# gateway delta-spec — bugfix-446

> 对齐: bugfix-446
>
> 本文件是 bugfix-446 对长青契约层 `docs/specs/gateway/spec.md` 的**增量草案**。
> 只写变更的 Requirement。收尾由 orchestrator 据实际 diff 校正后并入 canonical。
> 消费者视角：与 Gateway 双向通信的 IM 服务、在 IM 看板上观察节点状态的运维者 / 终端用户。

## MODIFIED Requirements

### Requirement: 断线后自动重连并补发未确认帧,期间外部 IM 主路径不受影响

WebSocket 断开后 Gateway 自动重连(指数退避,有上限),重连后重发 `node.register`;断开前未收到 ack 的
上行帧在重连后补发,不丢消息。断线期间外部 IM 主路径(通道 → Gateway → 内核)仍可用。

**自动重连对宿主级瞬态故障同样成立**：无论断连源于套接字断开、Gateway 所在机器休眠/唤醒、网络中断后
恢复、还是 IM 服务重启，Gateway 都持续按退避重试，故障消除后节点自动恢复 online，无需人工重启进程。

#### Scenario: 重连后补发断线前未确认的帧
- **GIVEN** 一帧 `node.report` 已发出但 socket 在收到 ack 前断开
- **WHEN** Gateway 重连成功
- **THEN** 新连接上先发 `node.register`、再补发那帧 `node.report`,原 payload 不变

#### Scenario: 重连采用指数退避并封顶
- **WHEN** IM 服务持续不可达,Gateway 反复重连
- **THEN** 重连间隔按指数退避增长直到上限(不无限激增、不放弃)

#### Scenario: IM 离线时外部 IM 主路径仍可用
- **GIVEN** IM 服务不可达
- **WHEN** 外部通道来一条入站消息
- **THEN** 该消息照常走通道 → Gateway → 内核 → 回发,Agent 执行不受 IM 离线影响(本地自治)

#### Scenario: Gateway 所在机器休眠唤醒后节点自动恢复
- **GIVEN** 节点处于 online，Gateway 与 IM 在不同机器
- **WHEN** Gateway 所在机器休眠一段时间后唤醒
- **THEN** 无需人工重启，节点在有限时间内自动恢复 online，该节点下的 agent 重新能正常收发消息

#### Scenario: 网络中断恢复后节点自动恢复
- **GIVEN** 节点处于 online
- **WHEN** Gateway 所在机器网络中断一段时间后恢复
- **THEN** 中断期间该节点在 IM 显示离线，网络恢复后节点自动回 online，全程无需人工干预

#### Scenario: IM 服务重启后节点自动重新注册
- **GIVEN** 节点处于 online
- **WHEN** IM 服务重启（短暂不可达后恢复）
- **THEN** IM 恢复后节点自动重新注册并回 online，agent 重新可用

## ADDED Requirements

### Requirement: Gateway 启动顺序对 IM 可用性不敏感

Gateway 启动不依赖 IM 服务当时是否可达；IM 不可达时 Gateway 正常起、进入连接重试，IM 就绪后自动连上。

#### Scenario: Gateway 先于 IM 启动 / 启动时 IM 不可达
- **WHEN** 在 IM 尚未就绪时启动 Gateway
- **THEN** Gateway 正常完成启动、不崩溃、不卡死，本地通道主路径立即可用；IM 一就绪即自动连上、节点变 online

### Requirement: 连接维护故障永不致 Gateway 不可恢复

维持 IM 连接过程中的任何瞬态故障都不会让 Gateway 停在"既不重连也不退出"的不可恢复状态。

#### Scenario: 出现超出已知范围的连接故障
- **GIVEN** 节点运行中
- **WHEN** 维持 IM 连接的过程中发生任意瞬态故障（含未预料到的故障）
- **THEN** Gateway 不会停在既不重连也不退出的状态——最终自动恢复 online，用户无需手动重启进程
