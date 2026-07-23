# refactor-472 — 验收报告

> 对齐: `motivation.md` 的用户侧验收标准。Round 1，2026-07-23。
>
> 口径澄清：team-lead 明确本 unit 未改前端、无原型或 must-match 契约；因此按 `design.md` 的 Runbook，以隔离真 IM/Gateway、公开 HTTP 和浏览器实际使用的 `/im/ws/user` 完成验收，不把缺失 `node_modules` 作为阻断理由。

## Verdict

**fail**

`Gateway` 替代旧连接后，旧连接结束虽然不会立刻使节点离线，但新连接随后发出已获 ACK 的 heartbeat 会把该节点显示为 `offline`。用户会在重连后看到节点离线，并失去在线节点依赖的操作能力。

- **Highest Required Action:** `fix-implementation`
- **Issues:** blocking 0 / major 1 / minor 0

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

同一 authenticated owner 以两个 Gateway WebSocket 先后注册随机节点 `reviewer-replacement-a77ebf69`。第二连接注册成功；关闭第一连接后节点仍为 online。但第二连接发送并收到 `node.heartbeat` ACK 后，节点列表将该节点显示为 offline。这会使重连后的用户无法继续把它当作在线节点使用。

### 4. 非法帧、在线控制与离线降级旅程

- 独立认证 Gateway 连接发送非 JSON，收到明确 `{"type":"error","payload":{"code":"invalid_message",...}}`；该连接按 unsupported-data 关闭，但隔离真栈中的原 Gateway 仍正常运行。
- 新独立连接发送 `{"type":"unknown.type","payload":{}}`，收到 `unsupported_message_type` 错误信封。
- 节点在线时，Agent/node capabilities、prompt preview、HEARTBEAT.md、cron、skill usage 的公开控制接口均返回 200。
- 单独停止本轮 Gateway、保留 IM 后，节点变为 offline；HEARTBEAT.md 返回 `{content:"", node_online:false}`，cron 返回 `[]`，skill usage 和创建 Agent 返回明确的 503 `target_node_id is not connected`。账号、历史和配置中心 API 仍可访问。

## Reference Artifacts Reviewed

N/A。`design.md` 未定义前端原型、reference screenshot 或 must-match 契约；本 unit 是严格后端行为不变重构。

## 问题清单

| # | 严重度 | 现象 | 处置 |
|---|---|---|---|
| 1 | major | 同一节点的新 Gateway 连接成功替代旧连接后，关闭旧连接不立刻影响节点；但新连接发送并获得 `node.heartbeat` ACK 后，节点板却显示 offline。用户会丢失已重连节点的在线状态和依赖它的控制/聊天入口。`reviewer-replacement-node` 与随机节点 `reviewer-replacement-a77ebf69` 均复现。 | **Regression Relation:** direct。**Recommended Action:** fix-implementation。**Action Rationale:** 直接违反 `motivation.md` “Gateway 重连或旧连接迟到断开” Scenario；首轮验收，按流程归实现修复。 |

## 验收标准覆盖

### Requirement: 账号、租户与持久化数据行为保持稳定 — 组内结论: pass

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 用户登录后访问自己的 IM 数据 | `motivation.md` L47-L50 | 旅程 1：两个真实登录 owner 访问会话、Agent、节点、policy、metrics；另一 owner 尝试读写会话。 | `reviewbob472` 对 `nano` 会话 GET/POST 均为 404；nano 的 node online、metrics 有 2 行，Bob metrics 0 行。 | pass | owner 隔离和正常数据面均可用。 |
| 用户刷新后继续看到完整会话历史 | `motivation.md` L52-L55 | 旅程 1、2：写入普通消息和真实 Agent 回复后重新读取会话历史。 | durable message `8e1f9990e3b049cb92a802c096c05d64` 重读存在；Agent 回复“验收成功”重读为 completed 且顺序正确。 | pass | 覆盖普通消息、Agent 回复和完成态；未触发附件/工具过程。 |
| 用户管理会话、Agent 与节点 | `motivation.md` L57-L59 | 旅程 1：创建会话、修改 Agent、修改 node alias、读写 policy；同时覆盖 profile conflict。 | config 1→2；旧 version 409；alias 保存；policy 30→31 后恢复。 | pass | 在线与跨 owner 权限边界均观察到。 |

### Requirement: Gateway 实时连接与消息中继行为保持稳定 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| Gateway 注册后维持实时双向连接 | `motivation.md` L63-L66 | 旅程 2、4：隔离真 Gateway auto-bind/register，用户流接收真实 Agent 上行；在线 RPC 下行成功。 | `.gateway.log` 有 `auto-bound to IM`；node online；7 个在线 control RPC 全为 200；流中有真实 completed reply。 | pass | heartbeat 的替代连接边界单列在下一行失败。 |
| Web IM 消息经 Gateway 获得实时回复 | `motivation.md` L68-L71 | 旅程 2：浏览器同用 `/im/ws/user` 订阅，公开 messages API 发送真实 Agent 请求，再刷新历史。 | 事件依次含 agent `message.created`、`thinking.segment`、`message.delta`、`message.completed`；正文“验收成功”，刷新后仍为 completed。 | pass | 真实 Kimi route 完成一轮。 |
| Gateway 重连或旧连接迟到断开 | `motivation.md` L73-L76 | 旅程 3：同 node 两个真实 Gateway WS 依次 register，关闭旧 socket，再由新 socket heartbeat。 | 两次 register ACK；旧 socket close 后 online；新 socket heartbeat ACK 后节点显示 offline。 | fail | 见问题 #1。 |
| 非法或不支持的 Gateway 消息 | `motivation.md` L78-L80 | 旅程 4：独立 authenticated Gateway WS 分别发送非 JSON和 unknown type。 | 分别收到 `invalid_message` 与 `unsupported_message_type` 错误信封；原 Gateway 栈未崩溃。 | pass | 非 JSON 连接被协议关闭，符合明确错误且不影响其他连接。 |

### Requirement: Gateway 配置控制与后台事件行为保持稳定 — 组内结论: fail

| Scenario | 期望来源 | 验证方式（覆盖它的旅程） | 证据 | 结果 | 备注 |
|---|---|---|---|---|---|
| 在线节点响应配置与控制操作 | `motivation.md` L84-L87 | 旅程 1、4：配置更新、capabilities、prompt preview、heartbeat、cron、skill usage。 | Agent config 200 / conflict 409；7 个在线 Gateway RPC 均 200。 | pass | 覆盖成功和配置冲突。 |
| 外部 Channel 与后台事件实时回流 | `motivation.md` L89-L92 | 尝试以本轮可用的真实 IM/Gateway 前置覆盖。 | 本轮没有外部 Channel 凭据；Runbook 明定不把 Feishu 真凭据作为前置，却未提供可由 reviewer 通过真实入口驱动的外部消息/群聊/后台通知替代旅程。 | inconclusive | 这是必验用户可观察 Scenario，不能用先前 integration fixture 或源码推断替代。未作为单独 issue：已有问题 #1 已使本 unit fail；修复轮应同时提供可运行的真实/等效验收入口或可复现证据。 |
| Gateway 或目标节点离线 | `motivation.md` L93-L95 | 旅程 4：停止本轮 Gateway，保持 IM 在线并调用需在线操作。 | node offline；heartbeat `{content:"",node_online:false}`，cron `[]`，skills/create Agent 明确 503；账号、历史、policy 继续可用。 | pass | 用户获得离线/失败反馈而非服务崩溃。 |

## 上层文档同步

- [x] `SPEC.md`（跨包顶点架构）：无需更新。本 unit 的目标为内部模块重组，未改变顶层包职责或依赖方向。
- [x] `docs/specs/im/`、`docs/specs/gateway/`（长青行为契约层）：无需更新。设计声明 no spec delta；本轮发现是回归，应修复实现而非修改契约。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/SPEC_GUIDE.md`（文档规范）：无需更新。
