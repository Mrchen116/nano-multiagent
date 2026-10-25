# Validation 与交付记录

## 被测版本与方法

实现 `93d1c3b01a8e3b39dbff84546482761b4d1e8a5d`；补充真实试点及 wire 操作说明后的独立审查版本 `572d336a5b721c221a844bf20e7841d785295a89`。两者产品代码相同。本地使用 Node 24.22.1、pnpm 11.7.0 和主仓 `.venv` 的 Python 工具。方法/Skill 改动不新增产品测试；复用现有回归，实际方法试用见 [context-pilots](context-pilots.md) 及独立 code-review/verification。

日志原件留在 `/Users/czj/.codex/reports/nano-context-engineering-20261025/validation/`，不提交日志与运行配置。

| 检查 | 命令与结果 | 证据 |
|---|---|---|
| 依赖与构建 | `pnpm install --frozen-lockfile`、`pnpm build` 通过 | install 当场输出；`nano-659-build.log` |
| TS 与原生资源 | `pnpm typecheck`、`pnpm check:ios-runtime` 通过 | `nano-659-backend-ci.log` 前段 |
| 相关窄回归 | `pnpm exec vitest run` 指定 llm-attribution、task-feedback、communication-native、capabilities、native-human-source、agent-context-default、knowledge、PA inbox/global-agent/tool-references；10 files / 86 tests 通过 | `nano-659-narrow.log` |
| 后端全量 | `pnpm exec vitest run --maxWorkers=2`；132 files / 704 tests 通过 | `nano-659-backend-bounded.log` |
| Python/架构与格式 | `pytest -m "not e2e" -q`：70 passed / 32 deselected；`ruff check .`、`ruff format --check .` 通过 | 同上 |
| 前端准备 | `npm ci`、shared product-contracts `npx tsc`、`npm audit --audit-level=critical` 通过 | `nano-659-frontend-ci.log` 前段 |
| 前端全量 | `npm run test -- --maxWorkers=2`（含 interactive assets 检查）；107 files / 1022 tests 通过 | `nano-659-frontend-bounded.log` |
| 文档与 Skill | `./scripts/docs-check`：292 maintained / 68 routed 通过；skill-creator 的 `quick_validate.py .claude/skills/agent-context-review` 通过；`git diff --check` 通过 | 实施当场输出；归档后再核完整路径 |

## 首次全量运行与复验边界

首次同时启动前后端默认并发，本机另有其他任务全量测试，观察到 load 66.99。前端出现 agent-edit 与 chat-workspace 的两个超时（105 files / 1020 tests 已通过）；后端出现 workspace-tools、providers 超时和 knowledge-policy partial-read limit 失败，随后仅中断本任务的 Vitest。原始失败日志保留。

按 systematic-debugging 缩小环境变量：未改测试或产品代码，仅将本任务前后端分开并限制 `maxWorkers=2`。前后端全套通过。该结果支持资源竞争解释，但不是对每个初始失败根因的独立证明；不将首次失败隐去，也不以本次文档变更名义修改无关 runtime。远端 CI 使用原配置的默认并发，创建 PR 后核对。

## 现场清理

真实 daily 栈已通过 `scripts/e2e-down.sh` 停止，IM 64516 无监听；受控 unknown 的 RuntimeClient 已 shutdown。另核实并停止首次中断 workspace-tools 测试遗留的孤儿 DSH（cwd 为该测试临时目录）。一次性试点驱动脚本已删除；合成请求、运行数据和小型证据原件保留在仓外/ignored 路径。开发 worktree 随开放 PR 保留。
