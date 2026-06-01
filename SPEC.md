# SPEC.md — nano-multiagent 架构规约

> **版本** v1.4 | **日期** 2026-06-01 | **对齐** feat-392
> 本文档是 nano-multiagent 的**跨包顶点**架构权威文件（包 / 依赖方向 / 部署拓扑）。
> 单包"现在怎么表现"看长青行为契约层 `docs/specs/<包>/spec.md`（§6）；文档体系怎么分层见
> `docs/SPEC_GUIDE.md`。若与其他设计文档冲突，以本文档为准。
>
> **v1.4 变更（feat-392）**：§6 文档索引重定位到长青行为契约层 `docs/specs/`；内核设计 SPEC 退役
> 移入 `docs/archive/`，内核契约改看 `docs/specs/kernel/spec.md`。
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
│  │  core     AgentRuntime→AgentLoop·RunsRegistry·EventStreamHub │ │
│  │           ToolRegistry│HookRunner│SkillRegistry│Compaction  │──→ LLM API
│  │           SessionManager│LLMClient (port，仅接口)           │ │
│  │  platform LLMClientFactory(OpenAI-compat/Anthropic 具体实现)│ │
│  │           Built-in tools│Persistence(SQLite)│Safety│Bootstrap│ │
│  │  products local_coding│personal_assistant (ProductProfile)  │ │
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
│   ├── platform/                 # 集成层：LLM providers、persistence、safety、bootstrap
│   ├── products/                 # 产品 profile：local_coding、personal_assistant
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

内部分四层（core / platform / products / sdk）：
- `core` 纯逻辑，不依赖 `platform` / `products`；只持 `LLMClient` 端口（接口）。
- `platform` 接环境（LLM provider 具体实现、持久化、安全、bootstrap），依赖 `core` + `products`。
- `products` 产品 profile（默认工具 / hook / prompt / skill 策略）。
- `sdk` 唯一对外装配面，依赖 `core` + `platform` + `products`，暴露 `build_kernel()` / `Kernel`。

内核对外行为契约详见 [`docs/specs/kernel/spec.md`](docs/specs/kernel/spec.md)。

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
- 内核分层：`core` 不依赖 `platform` / `products`；`platform → core + products`；`sdk → core + platform + products`（唯一对外面）
- `agent.sdk` 不被任何内核内部层反向依赖；`coding_cli` / `personal_assistant` / `IM` 三者之间无相互 import
- 验收口径：`src/coding_cli/`、`src/personal_assistant/` 只许 import `agent.sdk`，不得 import `agent.core` / `agent.platform`；`src/IM/` 不得 import `agent`；`src/agent/core/` 不得 import `agent.platform` / `agent.products`。相关断言由 `tests/contract/test_cli_http_only_contract.py` 与 `test_core_no_platform_imports.py` 自动执行

---

## 6. 文档索引

本节是顶点索引。**单包的"系统现在怎么表现"看长青行为契约层** `docs/specs/<包>/spec.md`(收尾归并保持
current);本 `SPEC.md` 只讲跨包架构,不与契约层重复。文档体系怎么分层、契约层怎么写,见
[`docs/SPEC_GUIDE.md`](docs/SPEC_GUIDE.md)。

### 长青行为契约层（current，单一权威）

| 包 | 路径 | 内容 |
|---|---|---|
| **kernel (agent)** | [`docs/specs/kernel/spec.md`](docs/specs/kernel/spec.md) | 内核经 `agent.sdk` 暴露的对外行为契约：装配/会话/运行/许可/压缩/工具/Hook/Skill/持久化 |
| **im** | `docs/specs/im/spec.md` | IM 服务对外行为契约（feat-392-M2 建立） |
| **gateway** | `docs/specs/gateway/spec.md` | Node Gateway 对外行为契约（feat-392-M3 建立） |
| **cli** | `docs/specs/cli/spec.md` | Coding CLI 对外行为契约（feat-392-M4 建立） |

### 文档规范与约定

| 文档 | 路径 | 内容 |
|---|---|---|
| **文档规范 SPEC_GUIDE** | [`docs/SPEC_GUIDE.md`](docs/SPEC_GUIDE.md) | 长青 spec 放什么/不放什么、判据、契约层骨架、收尾归并与 grounding checklist |
| 测试规范 | `docs/TESTING_GUIDE.md` | 测什么/不测什么、命名落层、临时验收 vs 回归 |
| 注释规范 | `COMMENTING_GUIDE.md` | docstring 风格、注释写"为什么/约束" |
| 操作手册 | `docs/operator-runbook.md` | 启动、调试、常见问题 |
| LLM API 联调 | `docs/可用LLM_API与联调说明.md` | 可用模型、本地代理地址、验证 curl |

### 内核实现细化（实现叙事，非契约层）

> 这些是实现层细化文档，不是对外契约。"内核现在怎么表现"以 `docs/specs/kernel/spec.md` 为准；下面几份
> 描述内部参数/事件清单等实现细节，作实现参考。

| 文档 | 路径 | 内容 |
|---|---|---|
| 工具设计细化 | `docs/内核设计细化/工具设计细化.md` | 5 工具参数、返回值、安全策略 |
| Hook 体系细化 | `docs/内核设计细化/Hook体系设计细化.md` | 事件清单、拦截/观察契约、闭包模型 |
| Skill 体系细化 | `docs/内核设计细化/Skill体系设计细化.md` | 自动/显式 skill 机制 |
| 系统提示词模板 | `docs/内核设计细化/系统提示词.md` | Runtime 填充的 prompt 模板 |

### 旧子系统 SPEC（迁移退役中）

> 旧的混合高度子系统设计文档，正被长青契约层取代。`内核设计SPEC` 已随 feat-392-M1 退役、
> `NodeGateway-SPEC` 已随 feat-392-M3 退役（均移入 `docs/archive/`，对应契约改看
> `docs/specs/<包>/spec.md`）；IM / Coding CLI 两份由 feat-392-M2/M4 蒸馏进 `docs/specs/<包>/` 后退役。
> 在各自迁移完成前仅作历史参考，可能已陈旧。

| 文档 | 路径 | 状态 |
|---|---|---|
| Coding CLI SPEC | `docs/CodingCLI-SPEC.md` | 待 M4 迁移退役 |
| IM 服务 SPEC | `docs/IM-SPEC.md` | 待 M2 迁移退役 |
| IM 前端蓝图 | `docs/IM前端蓝图.md` | 前端信息架构、响应式设计 |
| 需求文档 | `docs/需求.md` | 内核 vs 助手产品需求定义 |

### 归档（历史参考，已被 SPEC 覆盖）

| 文档 | 路径 |
|---|---|
| 内核设计蓝图 | `docs/archive/内核设计蓝图.md` |
| 多产品架构调整建议 | `docs/archive/多产品架构调整建议.md` |
| Agent 助手蓝图 | `docs/archive/Agent 助手（基于 SDK 的上层应用）蓝图.md` |
| Agent 节点蓝图 | `docs/archive/Agent节点蓝图.md` |
| IM 服务蓝图 | `docs/archive/IM服务蓝图.md` |
| CLI 时序图 | `docs/archive/CLI到工具调用时序图.md` |
