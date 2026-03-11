# SPEC.md — nano-multiagent 架构规约

> **版本** v1.2 | **日期** 2026-03-10 | **对齐** M84
> 本文档是 nano-multiagent 的唯一架构权威文件。
> 若与其他设计文档冲突，以本文档为准。

---

## 1. 愿景

nano-multiagent 是一个 Python 多模型 Agent 框架，由四个独立可部署的顶层包组成。

---

## 2. 顶层结构

```text
src/
├── agent/                        # Agent 内核（对外只暴露 HTTP API）
├── coding_cli/                   # 本地编码 CLI 应用
├── personal_assistant/           # 个人助手 Node Gateway
└── IM/                           # IM 前后端（独立服务）
    ├── service/
    └── frontend/
```

---

## 3. 各包职责与边界

### agent — 执行内核

IM 无关、产品无关的 Agent 运行时。只负责"单 Agent 可运行 + 可扩展 + 可持久化 + 可观测"。

对外**只暴露 HTTP API**，禁止外部直接 import 内部模块。

内部分三层（core / platform / products），详见 [`docs/内核设计SPEC.md`](docs/内核设计SPEC.md)。

### coding_cli — 本地编码助手

终端 CLI 应用。用户输入 → HTTP 调同机 agent → 渲染流式响应。

### personal_assistant — 个人助手 Node Gateway

常驻进程。负责：
- Channel 接入外部 IM（QQ / Slack / Telegram 等）
- 本地 heartbeat 调度与执行
- 通过 HTTP 调用同机 agent 内核
- 与 IM 服务交互（配置同步、消息中继、状态上报）

### IM — 独立中心服务

提供内置 Web IM + 用户/Agent 配置中心 + 可选消息中继。

**不直接调用 agent 内核**，只与用户浏览器和各机器上的 `personal_assistant` 交互。IM 可离线，Node Gateway 仍可本地自治。

---

## 4. 依赖方向

```
用户 ──→ IM（Web IM）──→ personal_assistant ──HTTP──→ agent
用户 ──→ coding_cli ──HTTP──→ agent
外部 IM ──→ personal_assistant ──HTTP──→ agent
```

**硬规则**：
- `coding_cli` 和 `personal_assistant` 通过 HTTP 调用同机 agent，禁止直接 import
- `IM` 不直接调用 agent，只与用户和 `personal_assistant` 交互
- 四个包之间无 Python import 依赖，各自独立部署

---

## 5. 文档索引

### 内核（agent）

| 文档 | 路径 | 内容 |
|---|---|---|
| **内核设计 SPEC** | `docs/内核设计SPEC.md` | agent 包三层架构、模块归属、Runtime API、HTTP API、工具/Hook/Skill/Session/LLM 契约、硬约束、验收标准 |
| 工具设计细化 | `docs/内核设计细化/工具设计细化.md` | 5 工具参数、返回值、安全策略 |
| Hook 体系细化 | `docs/内核设计细化/Hook体系设计细化.md` | 19 事件清单、拦截/观察契约、闭包模型 |
| Skill 体系细化 | `docs/内核设计细化/Skill体系设计细化.md` | 自动/显式 skill 机制 |
| 系统提示词模板 | `docs/内核设计细化/系统提示词.md` | Runtime 填充的 prompt 模板 |

### 应用与服务

| 文档 | 路径 | 内容 |
|---|---|---|
| **Coding CLI SPEC** | `docs/CodingCLI-SPEC.md` | coding_cli 运行模式、REPL 交互、模块结构、硬约束、验收标准 |
| **Node Gateway SPEC** | `docs/NodeGateway-SPEC.md` | personal_assistant 进程模型、Channel、入站四步决策、Heartbeat、多 Agent 路由、硬约束、验收标准 |
| **IM 服务 SPEC** | `docs/IM-SPEC.md` | IM 服务 Web IM、配置中心、设备绑定、节点管理、消息中继、前端、硬约束、验收标准 |
| IM 前端蓝图 | `docs/IM前端蓝图.md` | 前端信息架构、响应式设计 |

### 综合

| 文档 | 路径 | 内容 |
|---|---|---|
| 需求文档 | `docs/需求.md` | 内核 vs 助手产品需求定义 |
| LLM API 联调 | `docs/可用LLM_API与联调说明.md` | 可用模型、本地代理地址、验证 curl |

### 归档（历史参考，已被 SPEC 覆盖）

| 文档 | 路径 |
|---|---|
| 内核设计蓝图 | `docs/archive/内核设计蓝图.md` |
| 多产品架构调整建议 | `docs/archive/多产品架构调整建议.md` |
| Agent 助手蓝图 | `docs/archive/Agent 助手（基于 SDK 的上层应用）蓝图.md` |
| Agent 节点蓝图 | `docs/archive/Agent节点蓝图.md` |
| IM 服务蓝图 | `docs/archive/IM服务蓝图.md` |
| CLI 时序图 | `docs/archive/CLI到工具调用时序图.md` |
