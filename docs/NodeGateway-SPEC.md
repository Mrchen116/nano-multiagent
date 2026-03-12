# Node Gateway SPEC — src/personal_assistant/

> **版本** v1.0 | **日期** 2026-03-11
> 本文档是 `src/personal_assistant/` 的设计权威文件，从属于顶层 `SPEC.md`。

---

## 1. 定位

`personal_assistant` 是每台机器上常驻运行的 Agent 节点网关（Node Gateway）。

**做什么**：接入外部 IM 通道、将入站消息路由到正确的 Agent、通过 HTTP 调用同机 agent 内核执行、将结果回发原通道、执行本地 heartbeat 定时任务、与可选的 IM 服务做配置同步和状态上报。

**不做什么**：不实现 Agent Loop，不直接调用 LLM，不管理会话持久化（由 agent 内核负责），不做全局用户/组织管理（由 IM 服务负责），不提供终端 CLI 交互（由 coding_cli 负责）。

**边界**：通过 HTTP 调用同机 `agent` 内核，禁止直接 import agent 内部模块。与 `IM` 服务通过 WebSocket 交互（可选，IM 离线时本地自治）。

**体验准则**：Node Gateway 的配置与运维体验应对标成熟商业 AI Agent Gateway（如 OpenClaw Gateway）的简洁性与自治能力；默认配置必须做到最小化手动干预，偏离时需有明确理由。

**用户体验硬要求**：
- 默认用户路径只要求用户“启动 Gateway”
- Gateway 默认以后台服务方式常驻，并在内部管理 agent 内核生命周期
- 若节点尚未绑定用户，Gateway 自动拉起浏览器进入登录/绑定流程
- 前台阻塞运行与内核相关覆盖项仅允许作为显式 debug/高级模式

---

## 2. 进程模型

Node Gateway 是一个常驻后台进程，承担控制平面角色：

```
聊天消息路径（统一走 Channel）：
  外部 IM（QQ/Telegram/Slack…）──→ Channel(嵌入式) ──→ Gateway ──HTTP──→ agent 内核
  内置 Web IM ──→ IM 服务 ──→ WebIM Channel(嵌入式) ──→ Gateway ──HTTP──→ agent 内核

Gateway 与 IM 服务的连接方向：
  Gateway ──主动连接──→ IM 服务（WebSocket 持久连接）
  │  上行：节点注册、心跳上报、执行结果、投递回执
  │  下行：Web IM 消息中继、配置同步通知、手动触发 heartbeat
  （Gateway 在用户机器上，可能在 NAT 后面，不可作为服务端被 IM 服务主动连接）

本地调度路径：
  heartbeat 调度器 ──→ Gateway ──HTTP──→ agent 内核
```

**关键区分**：
- 所有聊天消息（无论来自外部 IM 还是内置 Web IM）都统一经 Channel 适配器进入 Gateway，走相同的四步决策流水线
- Gateway 与 IM 服务之间，始终由 Gateway 主动发起连接（WebSocket），IM 服务通过该连接下推消息和指令。这和用户手机上的 IM 客户端是同一个模型——客户端在 NAT 后面，但仍能接收消息

### 启动

默认启动流程：

1. 加载本地配置（`node-config.yaml` 或等效）
2. 在内部启动/探活同机 agent 内核进程，轮询 `/v1/health` 确认就绪
3. 初始化 Channel 注册表，调用 `start_channels()` 启动所有已配置通道
4. 初始化 heartbeat 调度器
5. 如果配置了 IM 服务地址，主动建立 WebSocket 连接，注册节点并拉取最新配置
6. 若节点尚未绑定用户，自动打开浏览器进入登录/绑定流程，并在绑定完成后继续就绪
7. Gateway 转入后台常驻服务态；CLI/桌面入口应尽快返回

调试模式可显式选择前台阻塞运行，但不得成为默认启动路径。

### 关闭

1. 停止 heartbeat 调度器
2. 停止所有 Channel 适配器
3. 断开与 IM 服务的 WebSocket 连接（如有）
4. 关闭 agent 内核子进程（terminate → 宽限期 → kill）
5. 清理资源退出

---

## 3. Channels — 嵌入式通道适配器

### 进程内插件

Channels **不是**独立网络服务。每个 Channel 是嵌入在 Gateway 进程内的适配器插件，与 Gateway 通过进程内函数调用通信。

### 最小接口

```python
class ChannelAdapter(Protocol):
    name: str

    def start(self, on_inbound: Callable[[InboundMessage], None]) -> None: ...
    def send(self, outbound: OutboundMessage) -> None: ...
    def stop(self) -> None: ...
```

- `start()` 只做平台接入（webhook / polling / SDK callback），不做业务路由
- 适配器只负责"平台协议 ↔ nano 内部消息格式"转换
- 每个 Channel 独立启停，单通道故障不影响其他通道

### 计划支持的通道

| 通道 | 接入方式 | 优先级 |
|---|---|---|
| Web IM（内置） | IM 服务消息推送，与外部 IM 通道地位平等 | P0 |
| 飞书 | Bot SDK / webhook | P1 |
| QQ | Bot SDK / webhook | P2 |
| Telegram | Bot API polling | P2 |
| Slack | Bolt (Socket Mode) | P2 |

---

## 4. 入站消息处理 — 四步决策流水线

当任意通道收到入站消息时，Gateway 必须依次执行四个决策：

### 4.1 多 Agent 路由（交给哪个 Agent）

1. 消息显式带 `agent_id` → 直接命中
2. 查通道绑定规则（channel/chat → default_agent）
3. fallback 节点默认 Agent

绑定规则支持按通道、账号、群组/私聊精细匹配（参考 OpenClaw 的多级绑定模型），但 v1 从最小集开始。

### 4.2 会话键生成（用哪个会话）

- 群聊：`{channel}:{external_chat_id}:{agent_id}`
- 私聊：`{channel}:{external_user_id}:{agent_id}`
- 映射到 `kernel_session_id`，持久化在本地 `session_binding_store`

### 4.3 队列管理（是否有运行中 Agent）

- 每个 `session_key` 维护串行 FIFO 队列
- 同会话串行、跨会话并行
- 当前任务结束后自动消费下一条

### 4.4 出站路由（回复发回哪个通道）

- 入站时保存 `reply_context`（channel_name + target_chat_id + thread_id?）
- 执行完成后由 outbound router 选择原通道适配器回发
- 回发失败写失败回执并触发有限次重试

---

## 5. 群聊行为

- Agent 在群聊场景中需要判断"是否应该回复"
- 群聊消息需通过 @提及门控：只有被 @提及、回复 Agent 消息、或发出控制命令时才处理
- Agent 判断"无需回复"时输出约定字符串（如 `NO_REPLY`），不发言
- 群聊行为说明通过 workspace 级 hook 注入：hook 订阅 `before_agent_start`，检测群聊 session 后通过 `override_system_prompt` 追加行为说明，无需写死在产品级 system prompt 中

---

## 6. Heartbeat 调度

每个配置级 Agent 支持独立的 `HEARTBEAT.md`，定义周期巡检待办与执行规则。

### 调度模型

- Gateway 本地维护 heartbeat 调度器，按可配置周期触发
- 支持三种调度方式（参考 OpenClaw Cron 模型）：
  - **一次性**（`at`）：指定时间执行
  - **固定间隔**（`every`）：如每 30 分钟
  - **Cron 表达式**（`cron`）：如 `0 9 * * 1-5`（工作日早 9 点）

### 执行流程

1. 调度器 tick → 读取 `HEARTBEAT.md` 判断是否需要行动
2. 若需要行动，新建独立 session 执行任务（`POST /v1/sessions` + `POST /v1/sessions/{id}/messages:async`）
3. 若无有效任务，安静跳过，不打扰用户
4. 执行完成后汇报：普通 Agent 汇报给用户替身 Agent；替身 Agent 直接汇报给用户

### 硬规则

- IM 服务不触发 heartbeat，调度完全在本地
- `task` 临时子 Agent 不具备独立 heartbeat
- 进程重启后补跑错过的到期任务

---

## 7. 多 Agent 支持

所有 Agent 共用同一个 `personal_assistant` 产品 profile（产品级默认工具、hook、system prompt 统一）。各 Agent 的差异化完全来自各自独立的 workspace 目录：

```text
<agent_workspace>/
├── MEMORY.md              # 该 Agent 的长期记忆
├── HEARTBEAT.md           # 该 Agent 的周期巡检定义
└── .nano-assistant/       # 该 Agent 的 workspace 级扩展
    ├── tools/             # workspace 级自定义工具
    ├── hooks/             # workspace 级自定义 hook
    └── skills/            # workspace 级自定义 skill
```

Gateway 按 `agent_id` 隔离路由、会话、调度。创建 session 时通过 `POST /v1/sessions { workspace_root, product_id }` 指定，`workspace_root` 指向该 Agent 的 workspace 目录。

### 用户替身 Agent

- 用户可设定一个专属主 Agent 作为替身入口
- 替身 Agent 在 Agent Core 层与其他配置级 Agent 完全平等
- 核心职责：代表用户意图进行任务分解与团队指挥

### Agent 间通信

Agent 间协同完全通过 IM 消息路由实现，不引入专用内部消息总线。

**产品专属工具 `send_message`**：

`personal_assistant` 产品在 `products/personal_assistant/tools/` 下提供 `send_message` 工具：

```
send_message(text: str, to: str)
```

- `to` 为目标 Agent ID 或群聊 ID
- 工具执行时由 Gateway 将消息投递到目标会话（同机直接路由，跨机通过 IM 服务 WebSocket 中继）
- 同机器、跨机器通信逻辑完全一致，Agent 无感知部署环境

**上下文注入**：

每个 Agent 在 session 启动时，通过 `before_agent_start` hook 在系统提示词后追加通信上下文：

- 当前所在会话（session ID、会话类型、参与者）
- 可通信的 Agent 列表（同一用户归属的配置级 Agent，含 ID、名称、职责摘要）
- 可通信的群聊列表（该 Agent 已加入的群聊）

这样 Agent 知道"我能和谁说话"以及"我现在在哪个会话里"，可以自主决策发起协同。

**约束**：

- 仅同一用户归属的 Agent 支持相互发现和通信
- `task` 临时子 Agent 不具备 `send_message` 能力，不参与 Agent 间通信
- Agent 间通信仅依赖 IM 消息路由，不额外设计专有通信信道

---

## 8. 与 IM 服务的交互（可选）

IM 服务离线时，外部 IM 主路径（Channel → Gateway → agent 内核）完全可用。以下功能仅在 IM 服务在线时可用。

### 连接模型

Gateway 运行在用户个人机器上，通常在 NAT / 防火墙后面，**不可作为服务端被 IM 服务主动连接**。因此 Gateway 主动向 IM 服务发起 WebSocket 持久连接，所有双向通信复用该连接：

- **上行（Gateway → IM 服务）**：节点注册、周期心跳、执行结果汇报、投递回执
- **下行（IM 服务 → Gateway）**：Web IM 消息中继、配置同步通知、手动触发 heartbeat

### 上行消息（Gateway 发送）

| 消息类型 | 用途 |
|---|---|
| `node.register` | 节点注册（携带 node_id、agent 列表、能力声明） |
| `node.heartbeat` | 周期心跳（在线状态、Agent 运行态摘要） |
| `node.report` | 执行结果汇报 |
| `node.delivery_receipt` | 投递回执（sent / completed / failed） |

### 下行消息（IM 服务推送）

| 消息类型 | 用途 |
|---|---|
| `relay.message` | Web IM 消息中继（进入 WebIM Channel 适配器） |
| `config.sync` | 配置版本通知（Gateway 按需拉取最新配置） |
| `heartbeat.trigger` | 手动触发某个 Agent 的 heartbeat |

### 断线重连

- WebSocket 断开后自动重连（指数退避，上限 60s）
- 重连后重新发送 `node.register`，IM 服务刷新节点状态
- 断线期间外部 IM 主路径不受影响（本地自治）

---

## 9. 与 agent 内核的接口

Node Gateway 使用的 agent HTTP API 子集：

| 方法 | 端点 | 用途 |
|---|---|---|
| GET | `/v1/health` | 内核探活 |
| POST | `/v1/sessions` | 创建会话（传入 `workspace_root`、`product_id`） |
| POST | `/v1/sessions/{id}/messages:async` | 异步发送消息 |
| GET | `/v1/sessions/{id}/events` | SSE 事件流 |
| GET | `/v1/runs/{run_id}` | 查询运行状态 |
| POST | `/v1/runs/{run_id}/cancel` | 取消运行 |

---

## 10. 多媒体/文件处理

- IM 发来的音频、图片、文件由 Channel 适配器统一落盘
- 落盘后以标准文件路径形式传入 agent 内核
- Channel 层只负责接入、落盘、路径映射与元信息透传
- 不内置 ASR / OCR / 文件解析等业务逻辑，由 Agent 按已安装工具能力自主决策

---

## 11. 本地配置

Gateway 采用本地配置文件驱动（如 `~/.nano-assistant/config.yaml`），包含：

- 启用的通道列表及各通道凭证
- 节点 ID 与所属用户
- Agent 列表与绑定规则（无须用户初始化中配置，通过内部 IM 可配置）
- Heartbeat 调度配置
- IM 服务地址（可选）

**内部实现细节**：agent 内核地址、启动命令、生命周期策略默认由 Gateway 自动管理，不属于普通用户配置；仅显式 debug/高级模式允许覆盖。

配置变更通过编辑文件 + 重启生效（v1 不做热重载）。

---

## 12. 产品配置

所有 Agent 共用唯一的 `personal_assistant` 产品 profile，不存在每 Agent 各一套 profile：

| 配置项 | 值 |
|---|---|
| product_id | `personal_assistant` |
| config_namespace | `nano-assistant` |
| 全局配置目录 | `~/.nano-assistant/` |
| 默认工具 | `read` `write` `edit` `bash` `task` |
| 默认 hook | `default_status` `realtime_stream` `usage_metrics` |
| Session 存储 | `~/.nano-assistant/sessions.sqlite3` |
| System prompt | 个人助手（带 heartbeat 上下文） |

各 Agent 的个性化（记忆、heartbeat、自定义工具/hook/skill）通过各自 workspace 目录下的文件实现，遵循内核四层加载顺序：内核内置 → 产品默认 → 用户全局（`~/.nano-assistant/`） → workspace（`<agent_workspace>/.nano-assistant/`）。

---

## 13. 模块结构

```text
src/personal_assistant/
├── main.py                  # 进程入口
├── gateway/
│   ├── bootstrap.py         # start_channels() 与生命周期
│   ├── channel_registry.py  # 已配置通道注册表
│   ├── inbound_pipeline.py  # 入站四步决策流水线
│   ├── session_keys.py      # 会话键生成与映射
│   ├── run_queue.py         # 每会话串行队列
│   └── outbound_router.py   # 出站回发路由
├── channels/
│   ├── base.py              # ChannelAdapter Protocol
│   ├── qq_adapter.py        # QQ 通道
│   └── web_relay_adapter.py # Web IM 中继通道
├── scheduler/
│   ├── heartbeat_scheduler.py   # Heartbeat 调度引擎
│   └── memory_extract_scheduler.py  # 记忆抽取调度（可选）
├── client/
│   └── kernel_api_client.py # agent 内核 HTTP client
├── config/
│   ├── local_store.py       # 本地配置读取
│   └── sync_client.py       # IM 服务配置同步（可选）
├── reporter/
│   └── upstream_reporter.py # IM 服务上报（可选）
└── ws/
    └── im_connection.py     # IM 服务 WebSocket 连接管理（上行/下行消息处理）
```

### 模块职责边界

- `gateway/` 只做消息路由与队列编排，不做通道协议细节
- `channels/` 只做"平台协议 ↔ 内部消息"转换，不做业务决策
- `scheduler/` 只做定时调度，不做 Agent 执行
- `client/` 是唯一的 agent 内核 HTTP 出口
- `ws/` 管理与 IM 服务的 WebSocket 连接，处理上行/下行消息

---

## 14. 失效与降级

| 场景 | 影响 | 降级策略 |
|---|---|---|
| IM 服务离线 | Web IM 不可用，配置同步中断 | 外部 IM 主路径正常，使用本地最近稳定配置 |
| 单通道平台故障 | 该通道不可用 | 其他通道不受影响 |
| Agent 内核故障 | 所有 Agent 执行不可用 | 入站消息入队等待，内核恢复后自动消费 |
| 节点进程崩溃重启 | 短暂中断 | 补跑错过的 heartbeat，恢复会话映射 |

---

## 15. 硬约束

1. 禁止直接 import agent 内部模块，所有交互通过 HTTP
2. IM 服务离线时外部 IM 主路径必须可用（本地自治）
3. 同会话串行、跨会话并行，不可违反
4. Channel 适配器单通道故障不得影响其他通道
5. Heartbeat 调度完全在本地，IM 服务不做调度源
6. `task` 临时子 Agent 不拥有独立 heartbeat 和记忆
7. 出站回复必须回发原通道原目标，不可跨通道混发
8. 群聊中未被 @提及的消息不触发 Agent 执行
9. 配置驱动，新增通道不改 Gateway 核心代码，只增适配器
10. 默认用户路径必须满足 §1 的体验契约：后台常驻、内核内聚、自动浏览器绑定；前台阻塞与内核覆盖项仅允许显式 debug/高级模式

---

## 16. 验收标准

1. `start_channels()` 可加载并启动所有已配置通道
2. 任意通道入站消息能完成四步决策并执行
3. 同会话串行、跨会话并行策略生效
4. 回复能准确回发原通道目标
5. IM 服务离线时，外部 IM 主路径仍可用
6. Heartbeat 按配置周期触发，无有效任务时安静跳过
7. 进程重启后补跑错过的到期 heartbeat
8. 多 Agent 按绑定规则正确路由，互不干扰
9. 群聊 @提及门控正常工作，未提及时不回复
10. 多媒体文件通过 Channel 落盘后路径正确传入 agent
11. 默认启动命令成功后应尽快返回，Gateway 进入后台常驻服务态
12. 首次启动若节点未绑定，系统自动打开浏览器完成登录/绑定；绑定后用户可直接从浏览器或已接入通道发消息，无需手工调用 bind/message API
