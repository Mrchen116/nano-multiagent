# AGENTS.md

## Project overview

整体架构：./SPEC.md

开发规范：COMMENTING_GUIDE.md

LLM交互日志：/Users/czj/Repos/LLM_PROXY/logs/<session_id>/

参考项目代码：
- Claude Code(CC) ~/Repos/opensource-hub/claude-code —— Anthropic 官方 Claude Code CLI （TypeScript/Bun），最优秀的商业coding agent harness。本项目agent core / coding agent主要参考实现。
- openclaw ~/Repos/opensource-hub/openclaw —— 开源个人 agent 助手，以 channel 形式接入各类 IM，本项目个人助手产品的整体架构主要参考它。他首创在agent个人助手设计中heartbeat、cron 自动化，agent identity、soul设定等特性。
- hermes agent ~/Repos/opensource-hub/self-evolution/hermes-agent —— 自进化个人 agent 助手，继openclaw 后的下一代技术演进，带闭环学习循环、自创建/自改进 skills、子 agent 并行、多 IM/多终端后端，本项目个人助手的自进化体系参考它。
- opencode ~/Repos/opensource-hub/opencode —— 多 provider / 多客户端架构的开源 AI Coding Agent，本项目 hook 事件设计、单一 agent 内核同时支撑两个产品的架构参考它。
- codex-cli ~/Repos/opensource-hub/codex —— OpenAI 官方coding agent harness（Rust + TypeScript），可参考其agent core / coding agent 设计，与CC对照。

## 常用命令

### 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 运行测试

```bash
# 全部测试
pytest

# 单个测试文件
pytest -xvs tests/unit/test_xxx.py

# 跳过 e2e（不需要本地运行时依赖）
pytest -m "not e2e"
```

### 启动 IM 服务

```bash
PYTHONPATH=src python -m uvicorn IM.app:app --host 0.0.0.0 --port 8011
```

Web IM 入口：`http://127.0.0.1:8011/`

### 启动 Gateway（个人助手）

```bash
# 启动（后台）
PYTHONPATH=src python -m personal_assistant.main

# 显式指定远端 IM
PYTHONPATH=src python -m personal_assistant.main --im-service-url http://<im-host>:8011

# 停止 / 重启
PYTHONPATH=src python -m personal_assistant.main stop
PYTHONPATH=src python -m personal_assistant.main restart
```

### 启动 Coding CLI

```bash
# Managed 模式（自动起本地 API）
PYTHONPATH=src python3 -m coding_cli.main \
  --mode managed \
  --base-url http://127.0.0.1:8000

# 或指定模型
PYTHONPATH=src python3 -m coding_cli.main --model volcanoArk:doubao-seed-2-0-code-preview-260215
```

### 前端开发（IM）

```bash
cd src/IM/frontend
npm install
npm run dev        # Vite dev server
npm run build      # 生产构建（tsc + vite build）
npm run test       # vitest
```

## 测试账号

```yaml
username:   nano
password:   nano1234
display_name: Test User
im_url:     http://127.0.0.1:8011
```

注册：`curl -X POST $im_url/im/v1/auth/register -H "Content-Type: application/json" -d '{"username":"nano","password":"nano1234","display_name":"Test User"}'`

IM 启动必须带固定 secret，否则 token 随重启失效：
`IM_JWT_SECRET="demo-jwt-secret-for-feat340-testing" PYTHONPATH=src python -m uvicorn IM.app:app --host 0.0.0.0 --port 8011`

**Gateway 固定 config**：`/tmp/demo-gateway-config.yaml`（已含 token，开箱即用）

启动：`PYTHONPATH=src python -m personal_assistant.main --config /tmp/demo-gateway-config.yaml`

### 非交互式 CLI 命令

```bash
PYTHONPATH=src python3 -m coding_cli.main --mode remote --base-url http://127.0.0.1:8000 health
PYTHONPATH=src python3 -m coding_cli.main --mode remote --base-url http://127.0.0.1:8000 create-session --title "demo"
PYTHONPATH=src python3 -m coding_cli.main --mode remote --base-url http://127.0.0.1:8000 send-message --session-id <id> --text "hello"
```

## 架构总览

四个独立顶层包，无 Python import 依赖，各自独立部署：

```
src/
├── agent/                # Agent 执行内核（HTTP API  only）
│   ├── core/             # 纯逻辑：runtime, loop, tools, hooks, skills, session
│   ├── platform/         # 集成层：HTTP API, LLM providers, persistence, safety
│   └── products/         # 产品 profile：local_coding, personal_assistant
├── coding_cli/           # 本地编码 CLI（终端 REPL）
├── personal_assistant/   # 个人助手 Node Gateway（常驻进程，Channel + Heartbeat）
└── IM/                   # IM 中心服务（Web IM + 配置中心 + 消息中继）
    └── frontend/         # React + TS + Vite
```

依赖方向硬规则（由 `tests/contract/` 自动验收）：
- `coding_cli` → `agent`（HTTP only，禁止直接 import）
- `personal_assistant` → `agent`（HTTP only，禁止直接 import）
- `IM` 不直接调用 `agent`，只与用户和 `personal_assistant` 交互
- 四个包之间禁止相互 import

agent 内核三层：`core`（纯逻辑）→ `platform`（接环境）→ `products`（装配方案）。
依赖方向：`platform → products + core`，禁止反向。`core` 不依赖 `platform` / `products`。

## 开发约定

- **注释规范**：见 COMMENTING_GUIDE.md。public API 必须写 Google 风格 docstring；注释写"为什么/约束"而非"做什么"。
- **TODO/FIXME 格式**：`TODO(<issue-id>): <改进> — <删除条件>` / `FIXME(<issue-id>): <缺陷> — <影响/风险>`
- **模块边界**：CLI 只能通过 `ServerClient` 访问 API；不要在 `commands.py` 里重新导出内部实现。
- **单测优先**：修改后先跑最窄的单元测试，再跑集成/contract。
- **前端产物**：`src/IM/frontend/dist/` 是构建产物，不提交；需要时在前端目录执行 `npm run build`。

## 关键文档索引

| 文档 | 路径 | 内容 |
|---|---|---|
| 架构总览 | SPEC.md | 四个包职责、依赖方向、部署图 |
| 内核设计 | docs/内核设计SPEC.md | agent 三层架构、模块归属、HTTP API、工具/Hook/Skill/Session 契约 |
| Coding CLI | docs/CodingCLI-SPEC.md | CLI 运行模式、REPL 交互、模块结构、硬约束 |
| Node Gateway | docs/NodeGateway-SPEC.md | Gateway 进程模型、Channel、入站四步决策、Heartbeat |
| IM 服务 | docs/IM-SPEC.md | IM Web IM、配置中心、设备绑定、节点管理、前端 |
| 操作手册 | docs/operator-runbook.md | 启动、调试、常见问题 |
| LLM 联调 | docs/可用LLM_API与联调说明.md | 可用模型、本地代理地址、验证 curl |

## Agent workflow

- Read AGENTS.md / SPEC.md before making changes.
- Prefer small, reviewable diffs.
- After code changes, run the narrowest relevant test first, then broader checks if needed.
- Do not commit secrets or generated local files.
