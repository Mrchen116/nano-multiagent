# AGENTS.md

nano-multiagent 是使用 DSH 执行运行时的多节点个人助手项目。`apps/node` 管理用户节点，`packages/personal-assistant` 持有产品路由与交付，`apps/im-server` 提供独立中心服务，Web/原生 iOS 客户端保留在 `src/IM/`。产品入口见 [README.md](README.md)，跨包架构见 [SPEC.md](SPEC.md)。

## 架构红线

- 执行运行时仅由 `packages/dsh-integration` 通过已声明的 DSH 公开 exports 接入；浏览器查看器与本仓轨迹 UI 分叉的限定例外见 [SPEC.md](SPEC.md)。不得扩大为运行时 fork/patch 或 private import。
- `apps/node` 仅通过 `@nano/dsh-integration/client` 管理执行子进程；PA/Channels/IM 不 import DSH。
- PA 可依赖 Channels 与 product-contracts；Channels、IM 仅依赖 product-contracts；禁止跨包相对路径绕过边界。
- 不恢复旧 Python Kernel、Coding CLI 或第二套 Agent Loop。节点与 DSH 用 stdio 通信，不新增内核 HTTP 服务。

这些边界由 [runtime dependency contract](tests/contract/test_runtime_dependency_contract.py) 自动验收；职责、部署拓扑和例外裁决只写在 [SPEC.md](SPEC.md)。

## 开工路由

先从 [docs/README.md](docs/README.md) 判断任务属于哪类知识，再按需读取：

| 任务 | 入口 |
|---|---|
| 产品定位与稳定体验原则 | [docs/product/](docs/product/README.md) |
| 单包 current behavior | [docs/specs/](docs/specs/README.md) |
| 是否建立 change unit、选择生命周期或实施方式、查看门禁 | [docs/development/change-workflow.md](docs/development/change-workflow.md) |
| 开发环境、测试、注释、worktree E2E 与 LLM 联调 | [docs/development/](docs/development/README.md) |
| 模型可见信息及其选择、注入、加载、更新与恢复 | [Agent Context Engineering](docs/development/agent-context-engineering.md) |
| 启动、观察、排障和恢复 current 系统 | [docs/operations/](docs/operations/README.md) |
| change unit 目录、文件归属和归档 | [docs/changes/README.md](docs/changes/README.md) |
| Agent 评测集、物化方法和实验协议 | [evals/README.md](evals/README.md) |

当前任务涉及用户可观察行为时，先读对应 `docs/specs/<package>/`；active change 描述目标状态，完成归并前不能覆盖 current spec。需要 change unit 的工作按 `change-workflow.md` 调用相应 `change-*` skills；符合“不建 unit”判据的小修可以直接实施。Full 完成设计或 Bugfix lite 完成实施前首文档后，默认使用 `change-orchestrator-simple`；用户点名 `$change-orchestrator` 时改用原流程。用户明确选择快速开发模式时可以边对齐边实现，但交付前必须调用 `change-fast-close` 补齐 unit 并完成 code review。

## 工作红线

- 先确认 checkout、branch 和 `git status`；保留用户已有 dirty/untracked 内容，只提交本任务明确修改的文件。换机或建立开发环境时，先按 [本机开发配置](docs/development/local-development.md#本机开发配置) 运行 `python3 scripts/dev_host.py check`，不把历史机器路径当作当前事实。
- 主仓交付时不遗留本任务的未提交修改；未完成工作保存在独立分支/worktree，恢复位置明确。收尾与本地产物规则见 [提交与边界](docs/development/local-development.md#提交与边界)。
- PR 提交后保留开发 worktree；确认 PR 合入后，执行合并或接手同一任务后续工作的 Agent 须在本轮结束前按 [合入后清理规则](docs/development/change-workflow.md#pr-合入后的-worktree-清理)清理并核实结果，或报告具体保留原因；不等待用户停止聊天。
- 保持 diff 小而可审；代码修改后先跑最窄相关测试，再按风险扩大。测试规则见 [docs/development/testing.md](docs/development/testing.md)。
- public API 使用 Google 风格 docstring；注释写“为什么/约束”，不复述代码。完整规则见 [docs/development/coding-guidelines.md](docs/development/coding-guidelines.md)。
- worktree 内真实服务必须隔离端口、Gateway config、运行数据、workspace 和 node identity，并清理自己启动的进程。优先使用 `./scripts/e2e-up.sh` / `./scripts/e2e-down.sh`，完整契约见 [docs/development/worktree-runtime.md](docs/development/worktree-runtime.md)。
- `src/IM/frontend/dist/` 是本地构建产物，不提交。
- 不提交 secret、本机 config、日志、PID、数据库、截图缓存或 worktree runtime 文件。
- 同一项长期事实只在一个权威位置完整维护；其他文档只写必要摘要并链接过去。新增、移动或退役长期文档时，同步更新 [docs/README.md](docs/README.md) 和对应领域入口。

## LLM 联调入口

从 [本机开发配置](docs/development/local-development.md#本机开发配置) 的 `llm_logs` 定位日志；协议、session 定位和证据边界见 [LLM 联调](docs/development/llm-integration.md)。

## 调研参考项目

参考仓根目录由 [本机开发配置](docs/development/local-development.md#本机开发配置) 的 `reference_root` 指定；下表为根目录内的相对路径。

| 参考项目 | 相对路径 | 本仓主要参考面 |
|---|---|---|
| Claude Code | `claude-code` | agent core、coding agent harness |
| openclaw | `openclaw` | 多 channel 个人助手、heartbeat、cron、identity/soul |
| hermes-agent | `self-evolution/hermes-agent` | 自进化、skills、子 agent、多终端 |
| opencode | `opencode` | 多 provider/客户端、hook、共享 agent 内核 |
| codex-cli | `codex` | coding agent core，与 Claude Code 对照 |

参考项目是调研材料，不是本仓 current 契约；结论必须回到本仓代码、[SPEC.md](SPEC.md) 和 [docs/specs/](docs/specs/README.md) 核实。完整用途、基线记录规则和其他研究入口见 [docs/research/upstreams.md](docs/research/upstreams.md)。
