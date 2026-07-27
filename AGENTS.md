# AGENTS.md

## 项目与架构红线

nano-multiagent 由四个顶层包组成：`agent` 是进程内内核库，`coding_cli` 和
`personal_assistant` 是两个产品，`IM` 是独立中心服务。跨包架构以 [`SPEC.md`](SPEC.md) 为准。

- `coding_cli` / `personal_assistant` 只能 import `agent.sdk`，不得 import `agent.core` /
  `agent.platform` 内部。
- `IM` 不调用 `agent`；`coding_cli`、`personal_assistant`、`IM` 三者之间不得相互 import。
- 内核依赖方向是 `platform → core`、`sdk → core + platform`；`core` 不依赖 `platform`。
- 内核是库，不恢复独立 HTTP server、旧 `--mode managed/remote` 或相关 HTTP CLI 子命令。

这些边界由 `tests/contract/` 自动验收；详细职责、部署拓扑和例外裁决只写在 `SPEC.md`。

## 调研与联调入口

LLM 交互日志：`/Users/czj/Repos/LLM_PROXY/logs/<session_id>/`

| 参考项目 | 本地路径 | 本仓主要参考面 |
|---|---|---|
| Claude Code | `~/Repos/opensource-hub/claude-code` | agent core、coding agent harness |
| openclaw | `~/Repos/opensource-hub/openclaw` | 多 channel 个人助手、heartbeat、cron、identity/soul |
| hermes-agent | `~/Repos/opensource-hub/self-evolution/hermes-agent` | 自进化、skills、子 agent、多终端 |
| opencode | `~/Repos/opensource-hub/opencode` | 多 provider/客户端、hook、共享 agent 内核 |
| codex-cli | `~/Repos/opensource-hub/codex` | coding agent core，与 Claude Code 对照 |

参考项目是调研材料，不是本仓 current 契约；结论必须回到本仓代码、`SPEC.md` 和 `docs/specs/` 核实。

## 工作红线

- 先按 [`docs/README.md`](docs/README.md) 定位任务对应的 canonical 文档。
- 需要 change unit 的工作按
  [`docs/development/change-workflow.md`](docs/development/change-workflow.md) 选择 Full 或
  Bugfix lite，并调用对应 `change-*` skills；符合“不建 unit”判据的小修可直接修改。
- 保持 diff 小而可审；代码修改后先跑最窄相关测试，再按风险扩大。
- public API 使用 Google 风格 docstring；注释写“为什么/约束”，不复述代码。完整规则见
  [`COMMENTING_GUIDE.md`](COMMENTING_GUIDE.md)。
- worktree 内启动服务必须使用隔离端口、隔离 Gateway config，并清理自己启动的进程。优先使用
  `./scripts/e2e-up.sh` / `./scripts/e2e-down.sh`；手工范式见
  [`docs/development/worktree-runtime.md`](docs/development/worktree-runtime.md)。
- `src/IM/frontend/dist/` 是本地构建产物，不提交；需要时在前端目录执行 `npm run build`。
- 不提交 secret 或本机生成的 config、日志、PID、数据库、截图缓存和 worktree runtime 文件。

环境安装、常用命令、提交格式与测试身份见
[`docs/development/local-development.md`](docs/development/local-development.md)。

## 高频文档路由

| 要回答的问题 | 权威位置 |
|---|---|
| 全仓文档地图与冲突裁决 | [`docs/README.md`](docs/README.md) |
| 跨包架构、依赖方向、部署拓扑 | [`SPEC.md`](SPEC.md) |
| 单包当前对外行为 | [`docs/specs/`](docs/specs/README.md) |
| 是否建 unit、Full/Bugfix lite 流程与门禁 | [`docs/development/change-workflow.md`](docs/development/change-workflow.md) |
| change unit 目录、产物与归档 | [`docs/changes/readme.md`](docs/changes/readme.md) |
| 本地开发环境、命令与提交约定 | [`docs/development/local-development.md`](docs/development/local-development.md) |
| worktree 内真实服务联调 | [`docs/development/worktree-runtime.md`](docs/development/worktree-runtime.md) |
| 测试分层与测试文档规范 | [`docs/TESTING_GUIDE.md`](docs/TESTING_GUIDE.md) |
| 启动、调试、恢复服务 | [`docs/operator-runbook.md`](docs/operator-runbook.md) |
| LLM provider 与代理联调 | [`docs/可用LLM_API与联调说明.md`](docs/可用LLM_API与联调说明.md) |
