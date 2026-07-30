# SPEC.md — nano-multiagent 架构规约

> **版本** v1.5 | **日期** 2026-07-30 | **对齐** `docs/README.md`
> 本文档是 nano-multiagent 的**跨包顶点**架构权威文件（包 / 依赖方向 / 部署拓扑）。
> 单包"现在怎么表现"看长青行为契约层 `docs/specs/<包>/`；全仓文档地图和冲突处理见
> `docs/README.md`，长青 spec 写法见 `docs/SPEC_GUIDE.md`。在跨包架构范围内与其他设计文档冲突时，
> 以本文档为准。
>
> **v1.5 变更**：全仓文档索引、权威分工与生命周期移至 `docs/README.md`；本文 §6 只保留架构相关入口。
>
> **v1.4 变更（feat-392）**：§6 文档索引重定位到长青行为契约层 `docs/specs/`；四份混合高度子系统
> 设计 SPEC（内核设计 / IM / NodeGateway / CodingCLI）蒸馏进契约层后**全部退役**移入 `docs/archive/`，
> 对应契约改看 `docs/specs/<包>/`。
>
> **v1.3 变更（refactor-387）**：内核移除内置 HTTP API，改为纯库形态——对外只暴露
> `agent.sdk`（进程内 `build_kernel()` → `Kernel`）。两个产品由「spawn 内核 uvicorn 子进程
> + loopback HTTP」改为「import `agent.sdk` 进程内直调」。**内核与产品形态正交**：产品呈现为
> 终端软件、常驻 gateway 还是（未来的）云 API，是产品层决策，内核不内置任何形态偏好。

---

## 1. 愿景

nano-multiagent 是一个 Python 多模型 Agent 框架，由四个独立可部署的顶层包组成。

---

## 2. 架构总览

```
        ┌───────────┐     ┌──────────────────┐
        │  Browser   │     │   External IMs    │
        │  (Web IM)  │     │  飞书│QQ│TG│Slack │
        └─────┬─────┘     └────────┬─────────┘
              │ HTTPS/SSE           │ Bot SDK / Webhook
              ▼                     │
┌─────────────────────────────────┐ │
│  IM Service (src/IM/)           │ │
│  可选中心服务，多用户数据隔离   │ │
│                                 │ │
│  HTTP API  /im/v1/*             │ │
│    conversations│messages│SSE   │ │
│    agents config│nodes│bind│me  │ │
│                                 │ │
│  WebSocket Server               │ │
│    上行: register│hb│report     │ │
│    下行: relay│config│trigger   │ │
│                                 │ │
│  Domain: User│AgentProfile      │ │
│    Conversation│Message         │ │
│    NodeStatus│RelayTask         │ │
│                                 │ │
│  Frontend: React+TS+Vite       │ │
└──────────────┬──────────────────┘ │
               │ WebSocket              │
               │ (Gateway 主动发起)     │
               ▼                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                USER MACHINE (每台部署机器)                        │
│                                                                  │
│  两个产品平级、各自独立 import agent.sdk（互不依赖）：           │
│  ┌─ Node Gateway (personal_assistant/) ┐  ┌─ Coding CLI (coding_cli/) ─┐ │
│  │  Channels · Inbound Pipeline         │  │  async-native Terminal REPL │ │
│  │  Heartbeat · send_message · WS→IM    │  │                             │ │
│  │  持有 Kernel = import agent.sdk      │  │  持有 Kernel = import agent.sdk│ │
│  └─────────────────┬────────────────────┘  └──────────────┬──────────────┘ │
│                    │ await kernel.*（进程内）              │ await kernel.*  │
│                    └───────────────────┬───────────────────┘               │
│                                        ▼ （二者各自调用同一份内核库）       │
│  ┌─ Agent Kernel 库 (src/agent/) ──────────────────────────────┐ │
│  │  sdk      build_kernel() → Kernel  ← 唯一对外面（进程内）    │ │
│  │           create_session│submit│stream│interrupt│cancel│... │ │
│  │           权限 = 注入的 can_use_tool 回调                    │ │
│  │  core     SessionDirectory│ConversationSession × N          │ │
│  │           AgentEngine→AgentLoop│KernelExecutor│RunsRegistry │──→ LLM API
│  │           EventStreamHub│Tools│Hooks│Skills│Compaction      │ │
│  │           LLMClient (port，仅接口)                           │ │
│  │  platform LLMClientFactory(OpenAI-compat/Anthropic 具体实现)│ │
│  │           Built-in tools│Persistence(SQLite)│Safety          │ │
│  │  (refactor-406 决策1：products 层解散→消费者工厂)            │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─ Agent Workspaces ─────────────────────────────────────────┐  │
│  │  agent-A/                       agent-B/                    │  │
│  │  ├── MEMORY.md                  ├── MEMORY.md               │  │
│  │  ├── HEARTBEAT.md               ├── HEARTBEAT.md            │  │
│  │  └── .nano-assistant/           └── .nano-assistant/        │  │
│  │      tools/│hooks/│skills/          tools/│hooks/│skills/   │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

内核是**库**，不是服务：`agent.sdk.build_kernel()` 返回进程内的 `Kernel`，产品 import 后直调（async）。
内核不内置 HTTP API；未来若要云化，由独立产品包 import `agent.sdk` 按需包一层 API，而非内核内置。
IM Service 是唯一对外网络服务（多用户 / Web 前端 / 消息中继，HTTP+WS 名正言顺），不直接调内核。

---

## 3. 顶层结构

```text
src/
├── agent/                        # Agent 内核库（对外只暴露 agent.sdk，进程内调用）
│   ├── core/                     # 纯逻辑：runtime/loop/runs/tools/hooks/skills/session
│   ├── platform/                 # 集成层：LLM providers、persistence、safety
│   └── sdk/                      # 对外面：build_kernel() → Kernel
├── coding_cli/                   # 本地编码 CLI 应用（import agent.sdk 进程内直跑）
├── personal_assistant/           # 个人助手 Node Gateway（import agent.sdk 进程内持有 Kernel）
└── IM/                           # IM 前后端（独立网络服务）
    ├── app.py                   # 后端服务入口
    ├── api/                     # HTTP 路由
    ├── ws/                      # WebSocket 连接管理
    ├── application/             # 业务服务
    ├── domain/                  # 领域模型
    ├── infra/                   # 基础设施
    └── frontend/                # Web IM 前端
```

---

## 4. 各包职责与边界

### agent — 执行内核（库）

IM 无关、产品无关的 Agent 运行时。只负责"单 Agent 可运行 + 可扩展 + 可持久化 + 可观测"。

对外**只暴露 `agent.sdk`**（`build_kernel()` → 进程内 `Kernel`），禁止外部直接 import `agent.core` / `agent.platform` 内部模块。内核是库不是服务，**不内置任何对外网络 API**。

内部分三层（core / platform / sdk）：
- `core` 纯逻辑，不依赖 `platform`；只持 `LLMClient` 端口（接口）。
- `platform` 接环境（LLM provider 具体实现、持久化、安全），依赖 `core`。
- `sdk` 唯一对外装配面，依赖 `core` + `platform`，暴露 `build_kernel()` / `Kernel`。

> refactor-406（决策 1）：原 `products` 层（产品 profile / 默认工具 / hook / prompt / skill 策略）已解散——产品默认值下沉到各消费者包的工厂（`coding_cli.product` / `personal_assistant.product`），经 `build_kernel(tools=…, hooks=…, prompt=…)` 传入；内核眼里没有"产品"对象，两个一方产品与任意外部应用对 SDK 完全对等。

内核对外行为契约详见 [`docs/specs/kernel/`](docs/specs/kernel/spec.md)。

### coding_cli — 本地编码助手

终端 CLI 应用（async-native REPL）。`import agent.sdk` 在进程内持有 `Kernel`，用户输入 → `await kernel.*` → 渲染流式响应。

### personal_assistant — 个人助手 Node Gateway

常驻进程。`import agent.sdk` 在 gateway 进程内持有 `Kernel`。负责：
- Channel 接入外部 IM（QQ / Slack / Telegram 等）
- 本地 heartbeat 调度与执行
- 进程内调用 `Kernel`（`await kernel.*`）
- 与 IM 服务交互（配置同步、消息中继、状态上报）

### IM — 独立中心服务

提供内置 Web IM + 用户/Agent 配置中心 + 可选消息中继。

**不直接调用 agent 内核**，只与用户浏览器和各机器上的 `personal_assistant` 交互。IM 可离线，Node Gateway 仍可本地自治。

---

## 5. 依赖方向

```
用户 ──→ IM（Web IM）──WS──→ personal_assistant ──import agent.sdk（进程内）──→ agent
用户 ──→ coding_cli ──import agent.sdk（进程内）──→ agent
外部 IM ──→ personal_assistant ──import agent.sdk（进程内）──→ agent
```

**硬规则**：
- `coding_cli` 和 `personal_assistant` 通过 **`import agent.sdk` 进程内调用** agent；**只允许 import `agent.sdk`**，禁止 import `agent.core` / `agent.platform` 内部模块
- `IM` 不调用 agent，只与用户浏览器和各机器上的 `personal_assistant` 交互（HTTP/WS）
- 内核分层（refactor-406 决策1：products 层解散）：`core` 不依赖 `platform`；`platform → core`；`sdk → core + platform`（唯一对外面）
- `agent.sdk` 不被任何内核内部层反向依赖；`coding_cli` / `personal_assistant` / `IM` 三者之间无相互 import
- 验收口径：`src/coding_cli/`、`src/personal_assistant/` 只许 import `agent.sdk`，不得 import `agent.core` / `agent.platform`；`src/IM/` 不得 import `agent`；`src/agent/core/` 不得 import `agent.platform`。相关断言由 `tests/contract/test_cli_http_only_contract.py` 与 `test_core_no_platform_imports.py` 自动执行

---

## 6. 相关文档

本文只负责跨包架构。全仓文档地图、权威分工、生命周期和历史/研究材料入口见
[`docs/README.md`](docs/README.md)。

- 单包 current 行为：[`docs/specs/README.md`](docs/specs/README.md)
- 长青 spec 与 delta-spec 写法：[`docs/SPEC_GUIDE.md`](docs/SPEC_GUIDE.md)
- change unit 流程、目录与归档：[`docs/changes/readme.md`](docs/changes/readme.md)
