# AGENTS.md

## 项目与架构红线

nano-multiagent 由四个顶层包组成：`agent` 是进程内内核库，`coding_cli` 和 `personal_assistant` 是两个产品，`IM` 是独立中心服务。跨包架构以 [`SPEC.md`](SPEC.md) 为准。

- `coding_cli` / `personal_assistant` 只能 import `agent.sdk`，不得 import `agent.core` / `agent.platform` 内部。
- `IM` 不调用 `agent`；`coding_cli`、`personal_assistant`、`IM` 三者之间不得相互 import。
- 内核依赖方向是 `platform → core`、`sdk → core + platform`；`core` 不依赖 `platform`。
- 内核是库，不恢复独立 HTTP server、旧 `--mode managed/remote` 或相关 HTTP CLI 子命令。

这些边界由 `tests/contract/` 自动验收；详细职责、部署拓扑和例外裁决只写在 [`SPEC.md`](SPEC.md)。

## 开工路由

先从 [`docs/README.md`](docs/README.md) 判断任务属于哪类知识，再按需读取：

| 任务 | 入口 |
|---|---|
| 产品介绍与最短可用路径 | [`README.md`](README.md) |
| 单包 current behavior | [`docs/specs/`](docs/specs/README.md) |
| 是否建立 change unit、Full/Bugfix lite 与门禁 | [`docs/development/change-workflow.md`](docs/development/change-workflow.md) |
| 开发环境、测试、注释、worktree E2E 与 LLM 联调 | [`docs/development/`](docs/development/README.md) |
| 启动、观察、排障和恢复 current 系统 | [`docs/operations/`](docs/operations/README.md) |
| change unit 目录、文件归属和归档 | [`docs/changes/readme.md`](docs/changes/readme.md) |

当前任务涉及用户可观察行为时，先读对应 `docs/specs/<package>/`；active change 描述目标状态，完成归并前不能覆盖 current spec。需要 change unit 的工作按 `change-workflow.md` 调用相应 `change-*` skills；符合“不建 unit”判据的小修可以直接实施。

## 工作红线

- 先确认 checkout、branch 和 `git status`；保留用户已有 dirty/untracked 内容，只提交本任务明确修改的文件。
- 保持 diff 小而可审；代码修改后先跑最窄相关测试，再按风险扩大。测试规则见 [`docs/development/testing.md`](docs/development/testing.md)。
- public API 使用 Google 风格 docstring；注释写“为什么/约束”，不复述代码。完整规则见 [`docs/development/commenting.md`](docs/development/commenting.md)。
- worktree 内真实服务必须隔离端口、Gateway config、运行数据、workspace 和 node identity，并清理自己启动的进程。优先使用 `./scripts/e2e-up.sh` / `./scripts/e2e-down.sh`，完整契约见 [`docs/development/worktree-runtime.md`](docs/development/worktree-runtime.md)。
- `src/IM/frontend/dist/` 是本地构建产物，不提交。
- 不提交 secret、本机 config、日志、PID、数据库、截图缓存或 worktree runtime 文件。
- 同一事实只在 canonical owner 写全；新增、移动或退役长期文档时同步维护 [`docs/README.md`](docs/README.md) 和对应领域入口。

## 调研与联调入口

LLM 交互日志：`/Users/czj/Repos/LLM_PROXY/logs/<session_id>/`

| 参考项目 | 本地路径 | 本仓主要参考面 |
|---|---|---|
| Claude Code | `~/Repos/opensource-hub/claude-code` | agent core、coding agent harness |
| openclaw | `~/Repos/opensource-hub/openclaw` | 多 channel 个人助手、heartbeat、cron、identity/soul |
| hermes-agent | `~/Repos/opensource-hub/self-evolution/hermes-agent` | 自进化、skills、子 agent、多终端 |
| opencode | `~/Repos/opensource-hub/opencode` | 多 provider/客户端、hook、共享 agent 内核 |
| codex-cli | `~/Repos/opensource-hub/codex` | coding agent core，与 Claude Code 对照 |

参考项目是调研材料，不是本仓 current 契约；结论必须回到本仓代码、[`SPEC.md`](SPEC.md) 和 [`docs/specs/`](docs/specs/README.md) 核实。
