# Evidence

一次验证只有在“要证明的声明、验证方法、运行结果、保存位置和能力边界”能够连起来时，才可供下一位 Agent
复查。不同证据回答不同问题，交付结论通常需要把其中几类串成证据链。

## 证据类型与能力边界

| 类型 | 能证明什么 | 不能单独证明什么 | 执行或观察入口 | 保存位置 |
|---|---|---|---|---|
| unit / integration / contract 测试 | 指定代码行为和边界可重复通过 | 真进程装配、浏览器体验、外部系统可用 | [`local-development.md`](local-development.md) 与 [`testing.md`](testing.md) | `tests/`；结果摘要写 unit `progress.md` |
| 前端测试与 build | 组件行为、静态构建可完成 | 真实后端、浏览器布局和完整用户旅程 | `src/IM/frontend` 的 `npm run test` / `npm run build` | 测试代码；结果摘要写 `progress.md` |
| 关键路径 E2E | 真 IM + Gateway 进程上的指定用户旅程 | 清单之外的产品完整性、所有浏览器状态 | [`e2e-critical-paths.md`](e2e-critical-paths.md) | 长期脚本和 `tests/e2e/`；当次结果写 `progress.md` |
| 手工真栈 / 浏览器验收 | 某个 commit、环境和 viewport 下的真实体验 | 未来回归、其他环境或未走到的场景 | [`worktree-runtime.md`](worktree-runtime.md) + unit reviewer runbook | `<unit>/M*/evidence/` 与 acceptance/regression 报告 |
| verifier / reviewer / code review 报告 | 对 spec/design、用户旅程或 diff 的独立判定 | 报告未覆盖的行为；原始运行本身 | [`change-workflow.md`](change-workflow.md) | unit 根部的 verification/acceptance/regression/review 记录 |
| 本地 runtime state 与服务日志 | 某次运行的进程、连接、事件和错误 | 长期规范或其他时间点的系统状态 | [`../operations/`](../operations/README.md) | gitignored state/log/DB；unit 中记录定位信息和必要摘要 |
| LLM 交互日志 | 实际发给 provider 的请求和返回链路 | 应用已正确消费、消息已送达用户 | [`llm-integration.md`](llm-integration.md) | `LLM_PROXY/logs/session/*_<session_id>/`，仓内只记录 locator |
| GitHub CI | PR head 在 CI 环境通过仓库定义的 jobs | 未进入 CI 的 E2E、外部凭据和人工体验 | `.github/workflows/ci.yml`、`gh pr checks` | GitHub check/run URL；PR 和 unit 状态页记录链接 |

测试选择、持久化位置和产品门禁各有自己的 owner；本页负责解释它们如何组成证据链，不复制完整流程和命令。

## 一条可复查记录需要什么

在 `progress.md`、验收报告或 `status.md` 引用证据时，至少写清：

1. **Claim**：这次要证明的具体行为或退出标准。
2. **Baseline**：branch、commit SHA，以及会影响结果的配置/环境。
3. **Method**：可重复命令，或真实用户路径、viewport、账号角色等操作条件。
4. **Result**：pass/fail/inconclusive 与关键观察；不能只写“已验证”。
5. **Locator**：测试名、CI URL、unit evidence 相对路径、日志 session id 或本机 runtime 路径。
6. **Limit**：本证据没有覆盖的环境、状态或行为。

截图、JSON 和日志只有与 Claim、Baseline、Method 建立链接后才有解释力。证据目录中的文件名使用场景和状态命名，
避免只写 `final.png`、`result2.json`。

## 保存与引用

- 小型、可审查且不含 secret 的截图、录屏、请求摘要和对照表放在对应 `<unit>/M*/evidence/`。
- unit 级结论写在 `verification.md`、`acceptance.md`、`regression.md` 或 code review 记录中，并链接原始 evidence。
- PID、完整服务日志、数据库、临时 config、浏览器缓存和原始 LLM 对话保留在 gitignored/仓外位置；unit 记录
  时间、session id、路径和必要的脱敏摘要。
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
