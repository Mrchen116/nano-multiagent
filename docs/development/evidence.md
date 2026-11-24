# Nano Evidence

可复查记录的字段、通用证据限制与如何转化为长期保护见 [Evidence](https://github.com/Mrchen116/dev-workflow-skills/blob/main/docs/development/evidence.md)。面向 Nano 的运行入口、实际 CI 和保存约束见下文。

## 证据类型与能力边界

| 类型 | 能证明什么 | 不能单独证明什么 | 执行或观察入口 | 保存位置 |
|---|---|---|---|---|
| unit / integration / contract 测试 | 指定代码行为和边界可重复通过 | 真进程装配、浏览器体验、外部系统可用 | [`local-development.md`](local-development.md) 与 [`testing.md`](testing.md) | `tests/`；结果摘要写实际实施记录、DONE 回报或 PR Validation Summary |
| 前端测试与 build | 组件行为、静态构建可完成 | 真实后端、浏览器布局和完整用户旅程 | `src/IM/frontend` 的 `npm run test` / `npm run build` | 测试代码；结果摘要写实际实施记录、DONE 回报或 PR Validation Summary |
| 关键路径 E2E | 真 IM + Gateway 进程上的指定用户旅程 | 清单之外的产品完整性、所有浏览器状态 | [`e2e-critical-paths.md`](e2e-critical-paths.md) | 长期脚本和 `tests/e2e/`；当次结果写实际实施记录或验收报告 |
| 手工真栈 / 浏览器验收 | 某个 commit、环境和 viewport 下的真实体验 | 未来回归、其他环境或未走到的场景 | [`worktree-runtime.md`](worktree-runtime.md) + unit reviewer runbook | `<unit>/M*/evidence/` 与 review.md |
| 能力审查结果 | 对 spec/design 或用户旅程的独立判定 | 报告未覆盖的行为；原始运行本身 | [`change-workflow.md`](change-workflow.md) | unit 根部的 review.md，保留能力与执行者归属 |
| code review 结果 | 对指定 diff range 的 correctness 与维护风险判定 | 产品旅程或未进入该 diff 的代码 | `change-code-review`，由 orchestrator 执行和判真 | unit `review.md`；PR 引用摘要 |
| 本地 runtime state 与服务日志 | 某次运行的进程、连接、事件和错误 | 长期规范或其他时间点的系统状态 | [`../operations/`](../operations/README.md) | gitignored state/log/DB；unit 中记录定位信息和必要摘要 |
| LLM 交互日志 | 实际发给 provider 的请求和返回链路 | 应用已正确消费、消息已送达用户 | [`llm-integration.md`](llm-integration.md) | `LLM_PROXY/logs/session/*_<session_id>/`，仓内只记录 locator |
| GitHub CI | PR head 在 CI 环境通过仓库定义的 jobs | 未进入 CI 的 E2E、外部凭据和人工体验 | `.github/workflows/ci.yml`、`gh pr checks` | GitHub check/run URL 与 PR Validation Summary |

## 反馈层与交付门禁

一次改动通常会经过多层反馈，但各层解决的问题不同：

| 层次 | 何时使用 | 权威入口 | 结果如何记录 |
|---|---|---|---|
| 最窄开发反馈 | 一个 coherent change 完成后，先验证直接受影响的行为 | [`testing.md`](testing.md) 与现有测试/包脚本 | 命令和结果摘要写实际实施记录或 DONE 回报 |
| 风险扩展验证 | 跨模块、架构边界、前端静态构建或真实进程受到影响时 | [`local-development.md`](local-development.md)、[`worktree-runtime.md`](worktree-runtime.md) | 记录选择依据、命令、结果和未覆盖面 |
| selected validation gates | unit 的所有 milestone 合入后，按本次问题组合独立代码审查与必要能力 | [`change-workflow.md`](change-workflow.md#阶段-4selected-validation-gates) | owner 串行归集 unit `review.md`，保留独立结论与证据限制 |
| 本地 CI 等价检查 | 归档和提 PR 前 | 当前 [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) 中每个 job 的实际命令 | PR Validation Summary 写通过的 job |
| 远端 CI | PR head 已推送后 | GitHub check/run | 记录 PR head SHA、check URL 和最终状态 |

本地 CI 的命令不在多份文档里复制维护；工作流文件是当前 job 的执行权威。当前远端 CI 也不自动代表前端 build、真实进程 E2E、真实 LLM 或人工用户旅程已经通过，这些验证按改动风险和 selected gates 另行执行并记录。

## 保存与引用

- 截图、录屏保存在 gitignored 或仓外目录。`<unit>/M*/evidence/` 保存文字结论、场景/尺寸、可复现定位、小型脱敏请求摘要和对照表。
- PID、完整服务日志、数据库、临时 config、浏览器缓存及原始 LLM 对话只在 gitignored 或仓外按需暂存。unit 记录时间、session ID 和脱敏摘要，取证结束按 [测试资源回收](worktree-runtime.md#测试资源回收) 处理。路径被回收后记录该状态。
- 涉及凭据、个人数据、完整 prompt 或第三方内容时，仅提交脱敏结论和合适的定位信息。

## 从一次证据进入长期保护

可重复回归归测试或 CI。单包行为归 [当前契约](../specs/README.md)，跨包约束归 [SPEC.md](../../SPEC.md)。可复用开发和操作方法分别归 [开发文档](README.md) 与 [操作手册](../operations/README.md)。只解释本次工作或当时环境的证据随 unit 归档。
