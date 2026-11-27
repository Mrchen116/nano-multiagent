# Nano 开发流程

通用生命周期、实施方式、角色、门禁和收尾见 [dev-workflow-skills 的 Change Workflow](https://github.com/Mrchen116/dev-workflow-skills/blob/main/docs/development/change-workflow.md)。Nano 默认用 `change-orchestrator-simple` 实施已完成事前对齐的 Full/Bugfix lite。用户点名 `$change-orchestrator` 时使用原流程。快速开发由用户明确选择并经用户亲自验收后，用 `change-fast-close` 收尾。

## 什么时候不建 unit

小修与 change unit 的判据见 [通用流程](https://github.com/Mrchen116/dev-workflow-skills/blob/main/docs/development/change-workflow.md#什么时候不建-unit)。用户能够感知到错误行为时，建立 bugfix unit。

## 开发基线与 PR 目标

当前处于 skill 流程试验期：默认开发基线为最新 `origin/develop`，集成分支与 PR base 均为 `develop`，适用于首文档、设计、实施、快速开发收尾及后续任务，无需用户逐次重申。首文档与设计默认只提交本 unit 产物到 `develop`；实施分支从该基线建立，收尾同步该分支。创建 PR 时显式设置 base（CLI 使用 `--base develop`），不能依赖 GitHub 默认分支。

用户对具体任务另有明确基线或交付安排时优先遵循；暂不 PR 或尚待试验时保留相应边界。只有用户明确通知试验结束并要求恢复时，才统一将本规则及各入口的默认值改回 `main`；不因单个任务完成、CI 全绿或会话结束自动恢复。目标分支不构成自动合并或部署授权。

## 阶段 2：设计

从 [当前包契约](../specs/README.md) 核对行为并按 [Nano 契约约定](../specs/CONTRIBUTING.md) 组织 delta。界面和原型按 [Nano 前端体验与验收](frontend-experience.md) 对齐平台与资源。有一次性部署迁移时按 [Nano 迁移提示词](../changes/README.md#一次性部署提示词) 记录设计。

### 五端对齐矩阵

所有新建 Full unit 的 `design.md` 必须包含二级标题 `## 五端对齐矩阵`，逐行明确以下 5 个平台的处置方式与验证投影（由 `scripts/docs_check.py` 与 `scripts/check_platform_parity.py` 自动核验）：

| 平台名称（精确匹配） | 允许的 `处置方式` | 适用条件 |
|---|---|---|
| `Web` | `shared` \| `native-sync` \| `platform-exempt` | `src/IM/frontend` 浏览器端体验与协议消费 |
| `Desktop (macOS)` | `shared` \| `native-sync` \| `platform-exempt` | 主窗口 WebView 共享时填 `shared`；涉及原生宿主/通知/托盘/自动更新/本地 IPC 时填 `native-sync` |
| `Desktop (Windows)` | `shared` \| `native-sync` \| `platform-exempt` | 同上，涉及 Windows 命名管道、路径、安装器或自启动差异时填 `native-sync` |
| `iOS` | `shared` \| `native-sync` \| `platform-exempt` | 原生 SwiftUI 客户端非 WebView 复用，凡触及用户可见协议/状态/提醒须 `native-sync` 或给出明确 `platform-exempt` 边界理由 |
| `Node (macOS / Windows / Linux)` | `shared` \| `native-sync` \| `platform-exempt` | `apps/node` 跨三系统运行与 CLI 生命周期；Linux 沿用后台 Node + Web IM 边界 |

PR 触及共享契约（`packages/product-contracts`）、共享向量（`src/IM/shared`）、`apps/im-server` 客户端接口/事件或 `src/IM/frontend/src` 时，各受影响端须同步修改或由关联 unit 的《五端对齐矩阵》声明 `shared` / `platform-exempt`；符合“不建 unit”的小修或 Bugfix lite 若无需多端同步，须在提交说明或 PR 正文中声明 `Platform-Parity-Exempt: <具体理由>`。

## 阶段 4：selected validation gates

按 [通用审查阶段](https://github.com/Mrchen116/dev-workflow-skills/blob/main/docs/development/change-workflow.md#阶段-4selected-validation-gates) 和本次风险选择证据。涉及真实产品时遵循 [运行隔离和回收](worktree-runtime.md)。需要真实团队旅程时，复用 [固定日常验收模板](worktree-runtime.md#固定日常验收模板) 的 P/E/Q + PA 阵容，通过 `--profile daily` 按需求独立起栈。给审查者交接版本、`.e2e-daily.json` 和本次场景增量。

## 收尾

本地 CI 以 [当前 CI 工作流](../../.github/workflows/ci.yml) 为准，按实际 job 命令执行。PR 的独立 job `Change unit is archived` 与后端测试并行，检查符合 unit 分支格式的 change 已归档。CI 和 [文档检查](../../scripts/docs-check) 都在 Nano checkout 内运行。远端 CI 结束后交棒给人审查和合并。

### PR 合入后的 worktree 清理

本规则适用于常规实施、快速开发及后续合并/部署会话，以 PR 合入事件触发，不等待用户停止聊天：

- PR 已创建但未合入时，保留该任务的开发 worktree 供审查和修改；CI 全绿、unit 文档归档或本轮回复结束都不触发删除。验证结束按 [测试资源回收](worktree-runtime.md#测试资源回收) 回收临时资源；例外保留须记录 owner 和回收触发。资源回收不等于移除 worktree。milestone 临时现场仍按原流程在集成后由 worker 清理。
- 获授权执行 PR 合并的 Agent 在确认远端已合入后，接手该任务的开发 worktree 清理，在本轮结束前完成；后续会话处理同一任务时若发现 PR 已合入而目录仍在，也补做清理，包括此前归档失败的遗留现场。不因本规则自行合并 PR。
- 清理前核实具体路径与 PR 的对应关系、提交已保存且变更已合入、无其他未提交工作或活进程，并保留必要的本地测试证据。仅移除该任务的开发 worktree，保留生产 `prod-main`、研究基线和其他任务现场；运行数据与进程核对见 [worktree-runtime](worktree-runtime.md)。
- Codex 管理的 worktree 优先使用 `archive_worktree`；普通 Git worktree 使用 `git worktree remove`。随后核实目录与 Git worktree 登记确实已移除，不以调用工具成功或聊天归档代替。用户要求继续保留、检查不满足或清理失败时，报告路径、具体原因和下次清理触发；最终回复明确本任务 worktree 已清理或仍保留。
