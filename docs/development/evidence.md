# Evidence

一次验证只有在“要证明的声明、验证方法、运行结果、保存位置和能力边界”能够连起来时，才可供下一位 Agent 复查。不同证据回答不同问题，交付结论通常需要把其中几类串成证据链。

## 证据类型与能力边界

| 类型 | 能证明什么 | 不能单独证明什么 | 执行或观察入口 | 保存位置 |
|---|---|---|---|---|
| unit / integration / contract 测试 | 指定代码行为和边界可重复通过 | 真进程装配、浏览器体验、外部系统可用 | [`local-development.md`](local-development.md) 与 [`testing.md`](testing.md) | `tests/`；结果摘要写 unit `progress.md` |
| 前端测试与 build | 组件行为、静态构建可完成 | 真实后端、浏览器布局和完整用户旅程 | `src/IM/frontend` 的 `npm run test` / `npm run build` | 测试代码；结果摘要写 `progress.md` |
| 关键路径 E2E | 真 IM + Gateway 进程上的指定用户旅程 | 清单之外的产品完整性、所有浏览器状态 | [`e2e-critical-paths.md`](e2e-critical-paths.md) | 长期脚本和 `tests/e2e/`；当次结果写 `progress.md` |
| 手工真栈 / 浏览器验收 | 某个 commit、环境和 viewport 下的真实体验 | 未来回归、其他环境或未走到的场景 | [`worktree-runtime.md`](worktree-runtime.md) + unit reviewer runbook | `<unit>/M*/evidence/` 与 acceptance/regression 报告 |
| verifier / reviewer 报告 | 对 spec/design 或用户旅程的独立判定 | 报告未覆盖的行为；原始运行本身 | [`change-workflow.md`](change-workflow.md) | unit 根部的 verification/acceptance/regression 报告 |
| code review 结果 | 对指定 diff range 的 correctness 与维护风险判定 | 产品旅程或未进入该 diff 的代码 | `change-code-review`，由 orchestrator 执行和判真 | Full/lite 写 PR Validation Summary；快速开发另写 unit `code-review.md` |
| 本地 runtime state 与服务日志 | 某次运行的进程、连接、事件和错误 | 长期规范或其他时间点的系统状态 | [`../operations/`](../operations/README.md) | gitignored state/log/DB；unit 中记录定位信息和必要摘要 |
| LLM 交互日志 | 实际发给 provider 的请求和返回链路 | 应用已正确消费、消息已送达用户 | [`llm-integration.md`](llm-integration.md) | `LLM_PROXY/logs/session/*_<session_id>/`，仓内只记录 locator |
| GitHub CI | PR head 在 CI 环境通过仓库定义的 jobs | 未进入 CI 的 E2E、外部凭据和人工体验 | `.github/workflows/ci.yml`、`gh pr checks` | GitHub check/run URL 与 PR Validation Summary |

测试选择、持久化位置和产品门禁各有自己的 owner；本页负责解释它们如何组成证据链，不复制完整流程和命令。

## 反馈层与交付门禁

一次改动通常会经过多层反馈，但各层解决的问题不同：

| 层次 | 何时使用 | 权威入口 | 结果如何记录 |
|---|---|---|---|
| 最窄开发反馈 | 每个 roadpoint 修改后，先验证直接受影响的行为 | [`testing.md`](testing.md) 与现有测试/包脚本 | 命令和结果摘要写当前 `progress.md` |
| 风险扩展验证 | 跨模块、架构边界、前端静态构建或真实进程受到影响时 | [`local-development.md`](local-development.md)、[`worktree-runtime.md`](worktree-runtime.md) | 记录选择依据、命令、结果和未覆盖面 |
| selected validation gates | unit 的所有 milestone 合入后，按 unit 类型做独立 verifier、reviewer 和 code review | [`change-workflow.md`](change-workflow.md#阶段-4selected-validation-gates) | verifier/reviewer 写 unit 报告；code review 写 PR Validation Summary，快速开发另写 `code-review.md` |
| 本地 CI 等价检查 | 归档和提 PR 前 | 当前 [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) 中每个 job 的实际命令 | PR Validation Summary 写通过的 job |
| 远端 CI | PR head 已推送后 | GitHub check/run | 记录 PR head SHA、check URL 和最终状态 |

本地 CI 的命令不在多份文档里复制维护；工作流文件是当前 job 的执行权威。当前远端 CI 也不自动代表前端 build、真实进程 E2E、真实 LLM 或人工用户旅程已经通过，这些验证按改动风险和 selected gates 另行执行并记录。

## 一条可复查记录需要什么

在 `progress.md`、验收报告、`code-review.md` 或 PR Validation Summary 引用证据时，至少写清：

1. **Claim**：这次要证明的具体行为或退出标准。
2. **Baseline**：branch、commit SHA，以及会影响结果的配置/环境。
3. **Method**：可重复命令，或真实用户路径、viewport、账号角色等操作条件。
4. **Result**：pass/fail/inconclusive 与关键观察；不能只写“已验证”。
5. **Locator**：测试名、CI URL、unit evidence 相对路径、日志 session id 或本机 runtime 路径。
6. **Limit**：本证据没有覆盖的环境、状态或行为。

截图、JSON 和日志只有与 Claim、Baseline、Method 建立链接后才有解释力。证据目录中的文件名使用场景和状态命名，避免只写 `final.png`、`result2.json`。

## 保存与引用

- 小型、可审查且不含 secret 的截图、录屏、请求摘要和对照表放在对应 `<unit>/M*/evidence/`。
- verifier/reviewer 的 unit 级结论写在 `verification.md`、`acceptance.md` 或 `regression.md` 并链接原始 evidence；code review 结果进入 PR Validation Summary，快速开发同时保留在 unit `code-review.md`。
- PID、完整服务日志、数据库、临时 config、浏览器缓存和原始 LLM 对话保留在 gitignored/仓外位置；unit 记录时间、session id、路径和必要的脱敏摘要。
- evidence 含 token、cookie、个人数据、完整 prompt 或第三方内容时，不提交原件；保存可复现定位信息和脱敏结论。
- `/tmp` 或浏览器临时会话只适合当场调查。交付依赖它时，先把必要结果转存到 unit evidence 或可重复测试。

## 从一次证据进入长期保护

change 收尾时逐项判断：

| 证据揭示的长期事实 | 归并位置 |
|---|---|
| 每次修改都应自动守住的回归 | `tests/`、CI 或稳定脚本 |
| 用户或外部消费者当前应观察到的行为 | `docs/specs/` |
| 跨包职责、依赖方向和架构不变量 | `SPEC.md`，高后果边界再加 contract test |
| 可重复的开发、测试和隔离运行方法 | `docs/development/` |
| 启动、观察、恢复和排障方法 | `docs/operations/` |
| 只解释本次选择或只对当时环境成立 | 保留在归档 change unit |

归并完成后，长期 owner 承担 future truth；原始 evidence 继续留在 change history，说明结论从哪里来。
