# feat-447: 飞书 channel 支持 — 技术方案

> 对齐: spec.md
>
> Unit branch: `unit/feat-447` (will be created by orchestrator)

## Changelog

## 现状分析

### 涉及范围

- `src/personal_assistant/channels/base.py` — 定义 `ChannelAdapter` Protocol（name / start / send / stop）、`InboundMessage` / `OutboundMessage` / `ReplyContext`。飞书 adapter 直接实现此 Protocol。只读不改。
- `src/personal_assistant/channels/` — 新增 `feishu_adapter.py`（飞书消息收发 adapter）、`feishu_client.py`（飞书 SDK 封装）。
- `src/personal_assistant/gateway/channel_registry.py` — `ChannelRegistry`，飞书 adapter 通过它注册。只读不改。
- `src/personal_assistant/gateway/bootstrap.py` — `start_channels` / `stop_channels`，驱动 adapter 生命周期。只读不改。
- `src/personal_assistant/gateway/outbound_router.py` — `OutboundRouter.send_text()`，路由回复到 adapter。只读不改。
- `src/personal_assistant/gateway/inbound_pipeline.py` — 入站消息处理、agent 路由、群聊 mention 门控。只读不改。
- `src/personal_assistant/gateway/group_context_store.py` — 群上下文 buffer，飞书 adapter 复用。只读不改。
- `src/personal_assistant/config/local_store.py` — 扩展 `ChannelConfig` 支持飞书 accounts 配置结构。
- `src/personal_assistant/main.py` — 注册飞书 adapter。
- `skills/` — 新增飞书文档操作 skill（教 agent 调用 feishu-cli 命令操作云文档）。

### 既有约束

- Gateway 只经 `agent.sdk` 持有内核，禁止 import 内核内部
- 配置统一走 `~/.nano-assistant/config.yaml`
- channel adapter 是进程本地的，start/send/stop 是同步接口
- 回复通过 `OutboundRouter.send_text()` 路由，adapter 不直接调内核

### 可复用能力

- **`ChannelAdapter` Protocol**（`base.py`）— 飞书 adapter 直接实现，无需新建抽象。**用**。
- **`GroupContextStore`**（`group_context_store.py`）— 群上下文 buffer，飞书 adapter 未 @ 消息存入、@ 时取出。**用**。
- **`ChannelRegistry` + `bootstrap.py`** — adapter 注册和生命周期管理。**用**。
- **`OutboundRouter`** — 回复路由。**用**。
- **`InboundMessage` / `ReplyContext` 数据类** — 消息标准化。**用**。
- **feishu-cli**（飞书官方开源 CLI）— 封装全部飞书 API，内置 OAuth 流程，agent 通过 shell 调用即可操作云文档。**用**。不自建飞书 doc tools。

### 相关历史

无相关历史变更。这是第一个外部 IM channel adapter。

## 架构总览

**Before**: Gateway 只有一个 `WebRelayAdapter`，通过 IM WebSocket relay 收发消息。

**After**: Gateway 新增 `FeishuAdapter`，通过飞书 SDK 长连接直接收发消息。云文档操作通过 feishu-cli（外部 CLI 工具）实现，agent 通过 shell 调用，零自建代码。

```mermaid
graph TD
    subgraph "personal_assistant (Gateway)"
        REG[ChannelRegistry]
        PIPE[InboundPipeline]
        OUT[OutboundRouter]
        GCTX[GroupContextStore]
        MAIN[main.py]

        REG --> PIPE
        PIPE --> OUT
        GCTX --> PIPE
    end

    subgraph "channels/ (新增标★)"
        WRA[WebRelayAdapter]
        FA[★ FeishuAdapter]
        FC[★ FeishuClient]
    end

    subgraph "外部工具 (不改代码)"
        FCLI[feishu-cli<br/>飞书官方 CLI]
    end

    subgraph "外部"
        IM[IM Service<br/>WebSocket Relay]
        FS[飞书服务器<br/>长连接]
        FDOC[飞书云文档 API]
        BROWSER[用户浏览器]
    end

    WRA -->|relay.message| REG
    FA -->|InboundMessage| REG
    OUT -->|OutboundMessage| FA
    FA --> FC
    FC -->|WebSocket| FS
    FA -.->|未@消息存入| GCTX
    FA -.->|@时取出| GCTX
    WRA -->|relay| IM
    FA -->|mirror 入站+出站| IM
    PIPE -->|agent shell 调用| FCLI
    FCLI -->|OAuth| BROWSER
    FCLI -->|API 调用| FDOC
```

飞书消息收发通过 `FeishuAdapter`（自建）接入 gateway；云文档操作通过 `feishu-cli`（外部工具）实现。两层解耦，互不依赖。

## 关键决策

### 决策 1: 飞书事件连接方式

**选了 WebSocket 长连接模式作为默认**。

- **理由**: Gateway 跑在用户本机（NAT 后面），无公网 IP。WebSocket 由 Bot 主动连飞书服务器，零配置开箱即用。飞书 SDK（lark-oapi）内置 WSClient，自带自动重连。
- **拒绝**: Webhook 模式——需要公网 HTTPS 端点 + verificationToken + encryptKey，部署门槛高。
- **风险**: Gateway 重启时短暂断连，飞书 SDK 自动重连，断连窗口内消息有飞书重试机制兜底。

### 决策 2: 多 Bot 配置模型

**选了 config.yaml 的 `channels.feishu.accounts` 列表，每个 account 绑定一个 `agentId`**。

```yaml
channels:
  feishu:
    accounts:
      - name: plato-bot
        appId: cli_xxx
        appSecret: xxx
        agentId: plato
```

- **理由**: 跟 OpenClaw multi-account 模式一致。显式绑定 agentId，配置一目了然。
- **拒绝**: 靠 bot name 隐式匹配——不直观，改名断绑定。
- **风险**: 无。

### 决策 3: 云文档操作方案

**选了 feishu-cli（飞书官方开源 CLI）作为云文档操作的唯一路径，不自建飞书 doc tools**。

- **理由**: feishu-cli 封装了全部飞书 API（文档、知识库、电子表格、消息、日历、任务），内置 OAuth 用户授权流程（`feishu-cli auth login`），agent 有 shell 执行能力即可调用。零自建代码，维护成本为零。
- **拒绝**: 自建 feishu_doc_tools.py + OAuth 模块——重复造轮子，飞书官方已经做好了。
- **风险**: feishu-cli 是外部依赖，需确保安装。但它是飞书官方维护，npm 一键安装，稳定性有保障。

### 决策 4: Session 隔离 key 设计

**选了 `feishu:<agent_id>:dm/group:<id>` 格式**。

- **理由**: 用 `agent_id` 而非 `app_id`，可读性好，调试直观。跟 OpenClaw 的 `agent:<agentId>:feishu:...` 模式一致。一对一映射保证隔离。
- **拒绝**: 用 `app_id`（不可读）；不加标识（多 bot 碰撞）。
- **风险**: 无。改 agent_id 会断 session，但实际不会改。

### 决策 5: 群聊未 @ 消息的 history buffer

**选了直接复用现有 `GroupContextStore`**。

- **理由**: 代码已存在，gateway spec 已定义行为。飞书 adapter 只需在未 @ 时 push、@ 时 flush。
- **拒绝**: 自己实现 buffer——重复造轮子。
- **风险**: 无。纯复用。

### 决策 6: 飞书对话同步到内部 IM

**选了 mirror 模式：飞书消息/回复处理完后，回推到 IM 服务，内部 IM web UI 自然可见**。

- **理由**: 参考 Hermes 的 `mirror.py`——不搞跨渠道实时同步，而是让所有 channel 共享同一个 session store。我们的 IM 服务已有 WebSocket relay 机制，飞书 adapter 处理完消息后，通过同一套 relay 推一条到 IM 服务即可。内部 IM web UI 从 IM 服务读数据，自然能看到飞书对话。
- **拒绝**: 改 web UI 直接读 agent kernel session store——改动太大，且破坏现有 IM 服务的数据主权。
- **风险**: IM 服务离线时 mirror 失败，但不影响飞书主路径（mirror 错误全部吞掉，不阻塞回复）。

## 接口与数据流

### 飞书消息收发主流程

```mermaid
sequenceDiagram
    participant U as 飞书用户
    participant FS as 飞书服务器
    participant FC as FeishuClient
    participant FA as FeishuAdapter
    participant REG as ChannelRegistry
    participant PIPE as InboundPipeline
    participant K as Agent Kernel
    participant OUT as OutboundRouter

    participant IMS as IM 服务

    U->>FS: 发消息
    FS->>FC: WebSocket 事件推送
    FC->>FA: 解析消息事件
    FA->>FA: mention 检测（群聊）
    alt 群聊未 @Bot
        FA->>FA: push 到 GroupContextStore
    else 1:1 或群聊 @Bot
        FA->>FA: flush GroupContextStore（群聊）
        FA->>IMS: mirror 入站消息到 IM 服务
        FA->>REG: on_inbound(InboundMessage)
        REG->>PIPE: 路由到 agent
        PIPE->>K: 执行
        K->>PIPE: 回复
        PIPE->>OUT: send_text(reply_context)
        OUT->>FA: send(OutboundMessage)
        FA->>FC: 调飞书 API 发消息
        FC->>FS: 发送
        FS->>U: 显示回复
        FA->>IMS: mirror 出站回复到 IM 服务
    end
```

### 云文档操作流程（通过 feishu-cli）

```mermaid
sequenceDiagram
    participant U as 飞书用户
    participant A as Agent
    participant CLI as feishu-cli
    participant FS as 飞书 API

    U->>A: "帮我创建一篇飞书文档"
    A->>CLI: shell 调用 feishu-cli doc create --title "xxx"
    CLI->>FS: API 调用（user_access_token）
    FS->>CLI: 返回文档 URL
    CLI->>A: 输出结果
    A->>U: "文档已创建: <URL>"
```

OAuth 授权（一次性）:
1. 用户执行 `feishu-cli auth login`
2. 浏览器打开飞书授权页 → 用户点同意
3. feishu-cli 自动保存 token 到本地
4. 后续所有 `feishu-cli` 命令自动使用该 token

### FeishuAdapter 接口

```python
class FeishuAdapter:
    """实现 ChannelAdapter Protocol"""

    name: str                           # "feishu:<agent_id>"
    app_id: str                         # 飞书应用 ID
    agent_id: str                       # 绑定的 agent ID

    def start(self, on_inbound: InboundHandler) -> None:
        """启动飞书 WebSocket 长连接，注册入站回调"""

    def send(self, outbound: OutboundMessage) -> None:
        """通过飞书 API 发送消息"""

    def stop(self) -> None:
        """关闭 WebSocket 连接"""
```

### 关键数据结构

**InboundMessage 扩展**（通过 metadata 传递飞书特有字段）:
- `metadata["feishu_message_id"]` — 飞书消息 ID
- `metadata["feishu_chat_type"]` — p2p / group
- `metadata["feishu_mentions"]` — @ 列表

**ReplyContext 扩展**:
- `metadata["feishu_message_id"]` — 回复目标消息 ID（飞书回复语义）

## 契约层增量 (delta-spec)

- kernel: no spec delta
- im: no spec delta
- gateway: specs/gateway/spec.md — 新增飞书 channel 消息收发相关 Requirement（从 spec.md 验收标准投影）
- cli: no spec delta

## 风险与回退

| 风险 | 影响 | 应对 |
|---|---|---|
| 飞书 SDK 版本兼容 | lark-oapi API 变动可能破坏集成 | 锁定 SDK 版本，单测覆盖核心路径 |
| WebSocket 断连丢消息 | gateway 重启窗口内消息可能丢失 | 飞书 SDK 自带重连 + 消息重试；可后续加 webhook fallback |
| feishu-cli 未安装 | agent 无法操作云文档 | gateway 启动时检测，未安装则提示；或在 skill 里引导安装 |
| feishu-cli token 过期 | 云文档操作失败 | feishu-cli 内置 refresh 机制；refresh 也过期则提示用户重新 `feishu-cli auth login` |
| 三个 Bot 同时连飞书 | 资源占用 | 每个 Bot 独立 WebSocket 连接，飞书 SDK 轻量，无显著开销 |

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| Gateway (personal_assistant) | `PYTHONPATH=src python -m personal_assistant.main stop` | `PYTHONPATH=src python -m personal_assistant.main --config ~/.nano-assistant/config.yaml` | 检查进程存活 + 飞书 Bot 在线状态 |

**Review 驱动方式**: 端到端真栈;客户端面是飞书客户端——reviewer 需在飞书里实际发消息验证收发。云文档操作通过 feishu-cli shell 命令验证。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| feat-447-M1 | feishu-messaging | — | A | channels/feishu_adapter.py, channels/feishu_client.py, config/local_store.py, main.py | [reviewer] 1:1 私聊收发正常（覆盖 Scenario: 用户在 1:1 私聊中发消息）;群聊 @Bot 触发回复（覆盖 Scenario: 群聊中 @Bot 触发回复）;未 @ 不回复（覆盖 Scenario: 群聊中未 @Bot 不触发）;未 @ 消息作为上下文（覆盖 Scenario: 未 @ 消息作为上下文）;多 Bot 各自路由到对应 Agent（覆盖 Scenario: 不同 Bot 对应不同 Agent）;飞书对话同步到内部 IM（覆盖 Scenario: 飞书消息出现在内部 IM + 飞书群聊消息出现在内部 IM）;[worker] feishu_adapter 单测全绿;飞书 SDK 连接建立成功;config.yaml 解析正确;mirror 到 IM 服务单测覆盖 |
| feat-447-M2 | feishu-cli-integration | feat-447-M1 | B | skills/feishu-doc.md（飞书文档操作 skill） | [reviewer] 以用户身份创建文档（覆盖 Scenario: 以用户身份创建文档）;以用户身份编辑文档（覆盖 Scenario: 以用户身份编辑文档）;以用户身份读取文档（覆盖 Scenario: 以用户身份读取文档）;以用户身份创建文件夹（覆盖 Scenario: 以用户身份创建文件夹）;以用户身份移动文件（覆盖 Scenario: 以用户身份移动文件）;未授权时提示授权（覆盖 Scenario: 未授权时提示授权）;API 失败时反馈错误（覆盖 Scenario: 云文档 API 调用失败）;[worker] feishu-cli 安装验证;OAuth 授权流程验证;skill 文件格式正确 |
