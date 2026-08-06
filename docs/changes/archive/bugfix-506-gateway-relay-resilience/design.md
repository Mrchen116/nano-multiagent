# bugfix-506: Gateway 重连后的中继可靠性 As-built Design

> 本文在实现完成后根据实际代码、diff 与已确认决定整理，描述最终落地设计。

## 实现范围

- Base: `0e79d9b4a264703807c25f25ec121a8b000c5f11`
- Head: 本 unit 提交前的工作区实现
- Commits: 本 unit 实现先于文档完成；提交时一并形成可审查 diff
- Included dirty files: IM schema、流式协议/EventBridge/event repository，Gateway connection-ready、profile reconciliation、runtime observer、IM connection，以及对应回归测试
- 受影响模块：`personal_assistant` Gateway 与 `IM` WebSocket relay

## 最终结构

### 组件与职责

- `ConnectionReadyCoordinator`：注册完成后将节点绑定与 Agent profile reconciliation 调度为后台任务；业务 outbox 与影子恢复不等待这些控制面工作。
- `IMAgentConfigSync`：在拉取后、发布前重新读取已通知的 profile version；重连中的 reconciliation 单飞并在有更新 generation 时补跑。
- `IMConnectionConfig`：将远端 IM 业务 ACK 的默认等待上限设为 10 秒。
- Gateway runtime delivery observer：为每个 kernel `assistant_message` 生成稳定 delta 幂等键，并随全部 `message_delta` 投递。
- IM gateway protocol/execution/EventBridge：解析该键；同一 SQLite 事务内写入幂等 marker、追加正文与持久 delta event，重复键只确认，不重复更新消息或发布事件。

### 调用链与数据流

`kernel assistant_message` → Gateway observer（`run_id + source event identity`）→ `node.streaming_delta(message_delta, idempotency_key)` → IM protocol/execution → EventBridge → `conversation_events` 与用户事件流。

在注册 ACK 后，`ConnectionReadyCoordinator.on_connected` 立即调度业务 outbox；节点绑定与 Agent profile reconciliation 作为独立 task 运行。对账任务在重连重叠时合并为最新一轮，并在发布前检查当前 profile version。其异常被记录，不能占住 Gateway 的收发路径。

### 状态、数据与兼容性

幂等键保存在 IM 的 `message_delta_idempotency` 持久表和 delta event payload 中，因此跨 Gateway 重连仍可识别已追加的正文；已有 event payload 会在首次创建该表时回填。旧 Gateway 不带键时维持原有追加语义，避免改变既有协议调用者。ACK 上限只改变默认值，显式配置仍可覆盖。

## 关键决策

| 决策 | 原因与约束 | 代码定位 |
|---|---|---|
| 配置收敛与业务收发解耦 | profile HTTP 不是注册完成后继续中继的前置条件 | `gateway/connection_ready.py` |
| 对账在发布前复核最新版本 | 后台任务不能以启动时的旧快照覆盖已到达的 `config.sync` | `gateway/agent_config_sync.py` |
| 以 kernel 事件身份作为 delta 幂等身份 | 重连补发需要跨连接稳定，不能由随机 WS frame id 决定 | `gateway/runtime_delivery/observer.py` |
| IM 原子持久化 delta | 仅 Gateway 侧去重无法覆盖 ACK 丢失后的再投递；正文、marker 与 event 不能留下半提交 | `IM/application/event_bridge.py`、`IM/infra/repositories/events.py`、`IM/infra/db.py` |
| 默认 ACK 上限与远端部署相容 | 1 秒不足以覆盖跨机 RTT、调度与 durable ACK | `ws/im_connection.py` |

## 失败路径、风险与回滚

- 节点绑定或 profile reconciliation 失败仍记录 warning，后续连接会再次尝试；业务 relay 不因此断开。
- 重复 delta 键只跳过重复追加；不同键的连续文本仍按原顺序追加。event 写入失败时事务回滚正文与 marker，重传可安全重试。
- 10 秒内未收到 ACK 的业务帧仍走既有断线、补发和有界重连逻辑。
- 如需回滚，可恢复原 ACK 默认和同步 reconciliation；IM 已持久的幂等键对旧代码无害。

## 与初始意图的差异

无。实现直接对应实验中确认的三项稳定性问题；未纳入无关的 LLM_Bridge OAuth 修复或本地 WebSocket 代理配置改动。

## 验证定位

- 用户验收：真实 IM 群聊实验的修复后消息未重复，用户确认继续按一个 PR 交付。
- 自动化测试：聚焦回归 95 passed；扩大 `tests/im_service/unit tests/unit/personal_assistant` 为 1092 passed。覆盖 EventBridge 原子重传、IM 协议透传、慢 bootstrap、对账单飞与版本新鲜度、远端 ACK 上限和 shadow bubble payload。
- 运行证据：修复后 MacBook Gateway 持续在线超过二十分钟；新回复仅产生一条 `message.delta`。

## Canonical 文档影响

- Delta-spec：`specs/gateway/service-lifecycle.md`、`specs/im/gateway-relay.md`
- 归并目标：`docs/specs/gateway/service-lifecycle.md`、`docs/specs/im/gateway-relay.md`
