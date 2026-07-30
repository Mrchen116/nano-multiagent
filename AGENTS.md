# AGENTS.md

## Project overview

整体架构：./SPEC.md

全仓文档地图：docs/README.md

开发变更流程：docs/development/change-workflow.md

本地开发：docs/development/local-development.md

开发文档地图：docs/development/README.md

注释规范：docs/development/commenting.md

测试规范：docs/development/testing.md

LLM交互日志：/Users/czj/Repos/LLM_PROXY/logs/<session_id>/

参考项目代码：
- Claude Code(CC) ~/Repos/opensource-hub/claude-code —— Anthropic 官方 Claude Code CLI （TypeScript/Bun），最优秀的商业coding agent harness。本项目agent core / coding agent主要参考实现。
- openclaw ~/Repos/opensource-hub/openclaw —— 开源个人 agent 助手，以 channel 形式接入各类 IM，本项目个人助手产品的整体架构主要参考它。他首创在agent个人助手设计中heartbeat、cron 自动化，agent identity、soul设定等特性。
- hermes agent ~/Repos/opensource-hub/self-evolution/hermes-agent —— 自进化个人 agent 助手，继openclaw 后的下一代技术演进，带闭环学习循环、自创建/自改进 skills、子 agent 并行、多 IM/多终端后端，本项目个人助手的自进化体系参考它。
- opencode ~/Repos/opensource-hub/opencode —— 多 provider / 多客户端架构的开源 AI Coding Agent，本项目 hook 事件设计、单一 agent 内核同时支撑两个产品的架构参考它。
- codex-cli ~/Repos/opensource-hub/codex —— OpenAI 官方coding agent harness（Rust + TypeScript），可参考其agent core / coding agent 设计，与CC对照。

## 服务启动

### 启动 IM 服务

```bash
PYTHONPATH=src python -m uvicorn IM.app:app --host 0.0.0.0 --port 8011
```

Web IM 入口：`http://127.0.0.1:8011/`

### 启动 Gateway（个人助手）

Gateway 默认读取 `~/.nano-assistant/config.yaml`。该文件是**持久化配置**：
- Gateway 启动时会将 config 中的 agents 同步到 IM
- 在 IM 前端新建 agent 时，Gateway 会自动把新 agent 写回该文件
- 因此服务重启后所有 agent 配置不会丢失

```bash
# 启动（后台，使用默认持久化配置）
PYTHONPATH=src python -m personal_assistant.main

# 或显式指定配置路径
PYTHONPATH=src python -m personal_assistant.main --config ~/.nano-assistant/config.yaml

# 显式指定远端 IM
PYTHONPATH=src python -m personal_assistant.main --im-service-url http://<im-host>:8011

# 停止 / 重启
PYTHONPATH=src python -m personal_assistant.main stop
PYTHONPATH=src python -m personal_assistant.main restart
```

## 架构总览

四个顶层包。内核（agent）是**库**，对外只暴露 `agent.sdk`；两个产品 import 它进程内直跑：

```
src/
├── agent/                # Agent 内核库（对外只暴露 agent.sdk，不内置 HTTP API）
│   ├── core/             # 纯逻辑：runtime/loop/runs/tools/hooks/skills/session；只持 LLMClient 端口
│   ├── platform/         # 集成层：LLM provider 具体实现、persistence、safety
│   └── sdk/              # 唯一对外面：build_kernel() 共享基座 + create_session() per-agent → Kernel
├── coding_cli/           # 本地编码 CLI（async-native REPL，import agent.sdk 进程内直跑）
├── personal_assistant/   # 个人助手 Node Gateway（常驻进程，import agent.sdk 进程内持有 Kernel）
└── IM/                   # IM 中心服务（Web IM + 配置中心 + 消息中继）
    └── frontend/         # React + TS + Vite
```

依赖方向硬规则（由 `tests/contract/` 自动验收）：
- `coding_cli` / `personal_assistant` → **只许 import `agent.sdk`**，禁止 import `agent.core` / `agent.platform` 内部
- `IM` 不调用 `agent`，只与用户和 `personal_assistant` 交互
- `coding_cli` / `personal_assistant` / `IM` 三者之间禁止相互 import

agent 内核三层（refactor-406 决策1：原 `products` 装配层解散，方案下沉为消费者工厂）：
`core`（纯逻辑）→ `platform`（接环境）→ `sdk`（对外面，两层装配：build_kernel 共享基座 + create_session per-agent）。
依赖方向：`platform → core`；`sdk → core + platform`（唯一对外面）；`core` 不依赖 `platform`。

## Worktree 运行隔离

内核是进程内库，不为它启动独立服务。在 worktree 内启动 IM、Gateway 或 Vite 时，监听服务必须使用空闲端口，Gateway config、运行数据和 workspace 必须隔离，并停止自己启动的全部进程；主实例的 `8011` 和常用 Vite 端口 `5173` 不用于分支验证。

优先使用仓库脚本：

```bash
./scripts/e2e-up.sh
source .e2e-ports.env
# 执行验证
./scripts/e2e-down.sh
```

脚本启动 IM + Gateway，不启动 Vite。端口、Gateway 生命周期、auto-bind、手工调试、运行证据和退出检查见 [`docs/development/worktree-runtime.md`](docs/development/worktree-runtime.md)。

## 关键文档索引

> 单包"现在怎么表现"看**长青行为契约层** `docs/specs/<包>/`（current 权威，收尾归并保持）；
> 每个包的 `spec.md` 是入口索引，同目录 area 文档承载具体 Requirement/Scenario；
> 文档体系怎么分层、契约层怎么写见 `docs/SPEC_GUIDE.md`；跨包架构看 `SPEC.md`。

| 文档 | 路径 | 内容 |
|---|---|---|
| 本地开发 | docs/development/local-development.md | Python 环境、测试命令、CLI/前端开发、测试身份与提交格式 |
| **文档规范** | docs/SPEC_GUIDE.md | 长青 spec 放什么/不放什么、判据、契约层骨架、收尾归并 + grounding checklist |
| **架构总览（顶点）** | SPEC.md | 四个包职责、依赖方向、部署图（跨包，不下钻单包行为） |
| **长青契约索引** | docs/specs/README.md | 长青行为契约层入口与 area 文档索引 |
| **内核契约层** | docs/specs/kernel/ | 内核经 `agent.sdk` 暴露的对外行为契约（入口 + area 文档） |
| IM 契约层 | docs/specs/im/ | IM 对外行为契约（入口 + area 文档） |
| Gateway 契约层 | docs/specs/gateway/ | Node Gateway 对外行为契约（入口 + area 文档） |
| CLI 契约层 | docs/specs/cli/spec.md | Coding CLI 对外行为契约（current） |
| 开发文档 | docs/development/README.md | 变更流程、环境、测试、注释、worktree E2E 与 LLM 联调 |
| 测试规范 | docs/development/testing.md | 测什么/不测什么、命名落层、临时验收 vs 回归、tasks.md 测试策略必填 |
| 运行与排障 | docs/operations/README.md | 主链路启动、Gateway 生命周期、外部通道与故障恢复 |
| LLM 联调 | docs/development/llm-integration.md | 本地代理、协议、交互日志与最近验证记录 |
| **关键路径 e2e 清单** | docs/development/e2e-critical-paths.md | 必保活的关键用户旅程 ↔ 守护 e2e 测试 ↔ 归属子系统 对账表（经真 Gateway 进程）；`scripts/e2e-critical.sh` 一键全跑；新增关键特性须登记一行 + 配 e2e |

> 四份混合高度子系统 SPEC（`内核设计SPEC` feat-392-M1、`IM-SPEC` feat-392-M2、
> `NodeGateway-SPEC` feat-392-M3、`CodingCLI-SPEC` feat-392-M4）已**全部退役**至
> `docs/archive/`，对应契约改看 `docs/specs/<包>/`。

## Agent workflow

- Read AGENTS.md / SPEC.md before making changes.
- Prefer small, reviewable diffs.
- After code changes, run the narrowest relevant test first, then broader checks if needed.
- Do not commit secrets or generated local files.
