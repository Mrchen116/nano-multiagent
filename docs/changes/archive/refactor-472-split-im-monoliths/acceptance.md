# refactor-472 — 验收报告

> 对齐: `motivation.md` 的用户侧验收标准。Round 1，2026-07-23。
>
> 口径澄清：team-lead 明确本 unit 未改前端、无原型或 must-match 契约；因此按 `design.md` 的 Runbook，以隔离真 IM/Gateway、公开 HTTP 和浏览器实际使用的 `/im/ws/user` 完成验收，不把缺失 `node_modules` 作为阻断理由。

## Verdict

**pass**

复验使用 Gateway 常规上报的 `status:"online"` heartbeat：替代旧连接后的新连接保持 online。此前无 `status` 的 heartbeat 会将节点显示 offline，是本次重构前后均存在的协议状态 drift，不影响本 unit 的行为保持验收。

- **Highest Required Action:** `pass`
- **Issues:** blocking 0 / major 0 / minor 0

## 用户旅程体验

### 1. 多 owner 数据、持久化与管理旅程

用 `scripts/e2e-up.sh` 建立隔离 IM/Gateway（IM `http://127.0.0.1:62029`，节点 `wt-unit-refactor-472-64261`）。`nano` 的节点显示 online，另注册 `reviewbob472`。

- `nano` 创建会话 `d4ff3b88763e402b99ebcc1e92f18524`，写入消息 `8e1f9990e3b049cb92a802c096c05d64` 后重新读取历史，仍只得到该完整消息。
- `reviewbob472` 读取或向上述会话写消息均获 404 `conversation_id not found`。
- Agent 配置从 profile version 1 更新到 2，重复旧 version 获 409 `profile_version conflict`；节点 alias、policy、metrics 均可读写，另一 owner 的 metrics 为 0 行。

### 2. Web IM 消息经 Gateway 获得真实回复并刷新

用浏览器同用的 `/im/ws/user` 建立用户事件流，创建 `nano` 与 `default-agent` 的会话，发送“只回复‘验收成功’”。用户消息先显示 `sent`；随后流中依次收到 agent running 气泡、thinking、`message.delta` 和 `message.completed`。终态正文为“验收成功”。刷新历史后读取到的顺序和终态为：

```text
user  | 只回复“验收成功”。 | completed
agent | 验收成功            | completed
```

### 3. 替代连接边界旅程

首次观察到两次不含 `status` 的手工 heartbeat 都将节点显示为 offline，复现步骤和原始 payload 均保留在下方 Side Finding。按 Gateway 正常 heartbeat 上报值重新验收：以 `Authorization: Bearer <nano JWT>` 建立两个真实 `/im/ws/gateway` 连接；连接 1、连接 2 均对随机节点 `reviewer-replacement-online-dc6f4d0b` 发送 `{"type":"node.register","payload":{"node_id":"<node>","agents":[]}}` 并各收到 register ACK；关闭连接 1 后节点仍为 online；连接 2 发送 `{"type":"node.heartbeat","payload":{"node_id":"<node>","status":"online"}}` 并收到 heartbeat ACK。

最终节点 payload 仍为 `{"node_id":"reviewer-replacement-online-dc6f4d0b","owner_id":"","node_name":"reviewer-replacement-online-dc6f4d0b","status":"online","last_heartbeat_at":"2026-07-23T03:34:36.341589Z","agent_count":0,"version":"","relay_enabled":true,"reporting_enabled":true,"alias":null,"last_error":null}`。因此替代旧连接的生产用户路径保持可用。

本轮所用隔离服务日志保留在 worktree 的 `.im.log` 与 `.gateway.log`；服务由 `scripts/e2e-down.sh` 停止。

### 5. 群聊、后台通知与外部 Channel 回流

按 `docs/e2e-critical-paths.md` 的真 IM + 真 Gateway 入口运行 `./scripts/e2e-critical.sh -m "not slow"`：17 条关键路径全通过（344.29 秒），包括真实后台 bash 完成后的跟进通知，以及群聊双向定向 @、未被 @ 的 Agent 不抢话。另按 Runbook 所指的已有 integration fixture 运行 group/Channel 覆盖，10 passed：覆盖群聊的实时 profile 同步与静默不重复、Channel 的跨 owner 隐藏/离线真实状态、绑定后 manifest bootstrap/reconcile 和在线保存后状态投影。外部 Feishu 真实凭据不是本 unit Runbook 前置；这些可复现 integration fixture 是 design 明定的替代验收入口。

### 4. 非法帧、在线控制与离线降级旅程

- 独立认证 Gateway 连接发送非 JSON，收到明确 `{"type":"error","payload":{"code":"invalid_message",...}}`；该连接按 unsupported-data 关闭，但隔离真栈中的原 Gateway 仍正常运行。
- 新独立连接发送 `{"type":"unknown.type","payload":{}}`，收到 `unsupported_message_type` 错误信封。
- 节点在线时，Agent/node capabilities、prompt preview、HEARTBEAT.md、cron、skill usage 的公开控制接口均返回 200。
- 单独停止本轮 Gateway、保留 IM 后，节点变为 offline；HEARTBEAT.md 返回 `{content:"", node_online:false}`，cron 返回 `[]`，skill usage 和创建 Agent 返回明确的 503 `target_node_id is not connected`。账号、历史和配置中心 API 仍可访问。

## Reference Artifacts Reviewed

N/A。`design.md` 未定义前端原型、reference screenshot 或 must-match 契约；本 unit 是严格后端行为不变重构。

## 问题清单

无本 unit 阻断问题。

## Side Findings

- 手工 Gateway heartbeat 省略 `status` 时，服务仍 ACK，却把节点显示为 offline。原始复现：`reviewer-replacement-node` 最终 payload 为 `{"node_id":"reviewer-replacement-node","owner_id":"","node_name":"reviewer-replacement-node","status":"offline","last_heartbeat_at":"2026-07-23T03:25:02.034921Z","agent_count":0,"version":"","relay_enabled":true,"reporting_enabled":true,"alias":null,"last_error":null}`；随机 node `reviewer-replacement-a77ebf69` 亦复现。常规 `status:"online"` heartbeat 的 replacement 复验保持 online。该无 status 行为在变更前已存在，且 `design.md` 明确纯重构不顺手修既有 drift；记为 out-of-unit、non-blocking，不立 issue。

## 验收标准覆盖

### Requirement: 账号、租户与持久化数据行为保持稳定 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户登录后访问自己的 IM 数据 | `motivation.md` L47-L50 | 旅程 1：两个真实登录 owner 访问会话、Agent、节点、policy、metrics；另一 owner 尝试读写会话。 | `reviewbob472` 对 `nano` 会话 GET/POST 均为 404；nano 的 node online、metrics 有 2 行，Bob metrics 0 行。 | pass | owner 隔离和正常数据面均可用。 |
| 用户刷新后继续看到完整会话历史 | `motivation.md` L52-L55 | 旅程 1、2：写入普通消息和真实 Agent 回复后重新读取会话历史。 | durable message `8e1f9990e3b049cb92a802c096c05d64` 重读存在；Agent 回复“验收成功”重读为 completed 且顺序正确。 | pass | 覆盖普通消息、Agent 回复和完成态；未触发附件/工具过程。 |
| 用户管理会话、Agent 与节点 | `motivation.md` L57-L59 | 旅程 1：创建会话、修改 Agent、修改 node alias、读写 policy；同时覆盖 profile conflict。 | config 1→2；旧 version 409；alias 保存；policy 30→31 后恢复。 | pass | 在线与跨 owner 权限边界均观察到。 |

### Requirement: Gateway 实时连接与消息中继行为保持稳定 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Gateway 注册后维持实时双向连接 | `motivation.md` L63-L66 | 旅程 2、4：隔离真 Gateway auto-bind/register，用户流接收真实 Agent 上行；在线 RPC 下行成功。 | `.gateway.log` 有 `auto-bound to IM`；node online；7 个在线 control RPC 全为 200；流中有真实 completed reply。 | pass | 心跳 replacement 边界已用常规 status 值复验。 |
| Web IM 消息经 Gateway 获得实时回复 | `motivation.md` L68-L71 | 旅程 2：浏览器同用 `/im/ws/user` 订阅，公开 messages API 发送真实 Agent 请求，再刷新历史。 | 事件依次含 agent `message.created`、`thinking.segment`、`message.delta`、`message.completed`；正文“验收成功”，刷新后仍为 completed。 | pass | 真实 Kimi route 完成一轮。 |
| Gateway 重连或旧连接迟到断开 | `motivation.md` L73-L76 | 旅程 3：同 node 两个真实 Gateway WS 依次 register，关闭旧 socket，再由新 socket heartbeat `status:"online"`。 | `reviewer-replacement-online-dc6f4d0b` 两次 register ACK；旧 socket close 后 online；新 socket heartbeat ACK 后仍为 online。 | pass | 原无 status heartbeat 行为见 Side Findings，为既有 drift。 |
| 非法或不支持的 Gateway 消息 | `motivation.md` L78-L80 | 旅程 4：独立 authenticated Gateway WS 分别发送非 JSON和 unknown type。 | 分别收到 `invalid_message` 与 `unsupported_message_type` 错误信封；原 Gateway 栈未崩溃。 | pass | 非 JSON 连接被协议关闭，符合明确错误且不影响其他连接。 |

### Requirement: Gateway 配置控制与后台事件行为保持稳定 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 在线节点响应配置与控制操作 | `motivation.md` L84-L87 | 旅程 1、4：配置更新、capabilities、prompt preview、heartbeat、cron、skill usage。 | Agent config 200 / conflict 409；7 个在线 Gateway RPC 均 200。 | pass | 覆盖成功和配置冲突。 |
| 外部 Channel 与后台事件实时回流 | `motivation.md` L89-L92 | 旅程 5：Runbook 指定的真 IM + 真 Gateway critical-path 入口，以及已有 group/Channel integration fixture。 | `./scripts/e2e-critical.sh -m "not slow"` 为 17 passed，覆盖后台通知、群聊双向 @ 与未被 @ 的 Agent 静默；group/Channel fixture 为 10 passed，覆盖实时群聊状态、幂等静默、Channel owner 隔离、bootstrap/reconcile/status。 | pass | Feishu 真凭据不是 Runbook 前置；按 design 的替代验收入口覆盖。 |
| Gateway 或目标节点离线 | `motivation.md` L93-L95 | 旅程 4：停止本轮 Gateway，保持 IM 在线并调用需在线操作。 | node offline；heartbeat `{content:"",node_online:false}`，cron `[]`，skills/create Agent 明确 503；账号、历史、policy 继续可用。 | pass | 用户获得离线/失败反馈而非服务崩溃。 |

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新。本 unit 的目标为内部模块重组，未改变顶层包职责或依赖方向。
- [x] `docs/specs/im/`、`docs/specs/gateway/`（长青行为契约层）：无需更新。设计声明 no spec delta；本轮发现是回归，应修复实现而非修改契约。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/SPEC_GUIDE.md`（文档规范）：无需更新。

## 清理结果

已在每次真栈旅程后执行 `./scripts/e2e-down.sh`。最终检查确认 unit worktree 不存在 `.im.pid`、`.gateway.pid`、`.e2e-ports.env`、`.e2e-jwt-secret`、`.gateway-config.yaml` 或 `.gateway-state.json`；仅保留 `.im.log` 与 `.gateway.log` 作为上述复现的服务日志证据。
