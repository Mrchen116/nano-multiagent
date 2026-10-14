# bugfix-601: As-built Design

> 本文在实现后根据实际代码和回归结果整理。用户已基于验证结果明确确认交付并授权转正式合并；本 unit 完成契约归并与归档。

## 实现范围

- Base：`290652ada2bf5fafbd4ac9f27a1514680ff78ca9`（创建独立 managed worktree 前已 fetch 的 `origin/main`）。
- 分支：`codex/auto-query-exemptions`。
- 产品变更：`packages/dsh-integration/src/policy/approval.ts` 的既有 `safe_tool` 路由新增 4 行条件。
- 回归：扩展 `packages/dsh-integration/tests/approval.test.ts`。主 checkout 及其它工作树没有被修改。

## 实际调用链

DSH 工具管线先进入 Nano 的 `tools/pre-execute`。Nano 先调用 downstream；若得到 deny/ask/cancel，原样返回。仅 downstream allow 后，在 `rules:nano && policy.enabled` 下判断新增的固定工具/action 集，命中则记录原有 `safe_tool` 审计并 allow。之后仍经过 DSH owner guard 与原工具 execute、产品桥接/服务权限检查。

新增集合只包含：

| 工具 | action |
|---|---|
| skill_manage | list |
| task_graph | list、get |
| schedule_list、schedule_history | 全工具 |
| workflow | list、read |
| get_goal、todo_write | 全工具 |

其它 action 不匹配，继续既有分类路径。原 safeTools、alwaysAllowTools、绑定本人消息路由及 DSH 规则分支未改动。

## 决策与兼容边界

- 复用既有 `safe_tool` 路径，不新增策略服务、配置开关、工具注册或第二套审核链。
- 新集合由 `policy.enabled` 限定，防止“免 classifier”扩大为 Auto 关闭时免人工审批。既有 safeTools 的行为保持。
- 固定 action 按原值匹配，不将缺席 action 的默认 Workflow 启动归入查询。
- 不改变模型推理、2112/10240 预算、两阶段语义和无结论分流；剩余动作仍可能遇到已知审核故障。
- 无持久数据/schema 迁移。回退本提交即可恢复本批调用的原审批依赖。

## 测试策略与证据

最低有效 seam 是已经装配 NanoApproval 的真实锁定 DSH RuntimeClient，使用 fixture LLM 的审核请求日志、工具结果与公开审核台账观察行为。零审核调用是本次明确要求；不测试私有 review 方法或镜像匹配函数。

- 扩展既有 `approval.test.ts`，不新建平行测试文件；保留全部原审批/来源测试。
- 9 种目标调用在 Nano Auto 下实际完成，审核日志为零，审计均为 `safe_tool`。
- 20 种相邻写入/默认启动/生命周期/Bash/消息调用仍触发审核且被 fixture 拒绝，body 未执行。
- 同一 9 种调用在 DSH 规则下继续审核；Auto 关闭、downstream 明确拒绝及工具 allowlist 空集下均不执行。
- 保留 `task-graph-permission.test.ts` 对 Auto 关闭时人工审批的既有保护，以及 `workflow-approval.test.ts` 的 child 权限保护。
- 基线先红：9 种调用产生 18 条审核请求；新增路由后该回归通过。所有临时运行目录在测试 finally 清理；未调用真实 LLM。

复核命令：

```sh
pnpm --filter @nano/dsh-integration build
pnpm test packages/dsh-integration/tests/approval.test.ts packages/dsh-integration/tests/task-graph-permission.test.ts packages/dsh-integration/tests/workflow-approval.test.ts
```

本次本地检查结果：

- 上述聚焦回归：3 个文件、14 项测试通过。
- `pnpm build`、`pnpm typecheck`：通过。
- `pnpm test`：74 个文件、273 项测试通过。
- `python -m pytest -m 'not e2e' -q`：56 passed、31 deselected。
- `./scripts/docs-check`：246 maintained Markdown sources、64 required routes 通过。
- `ruff check .`、`ruff format --check .`：通过，82 个 Python 文件格式已符合要求。
- `git diff --cached --check`：通过。

Python/文档/Ruff 使用主 checkout 的现有 `.venv` 工具，在本 worktree 运行。未运行与本次变更无关的前端/iOS门禁。测试不代替真实用户旅程验收；独立审查由 [code review](code-review.md) 记录。

## Canonical 文档影响

[Gateway delta](specs/gateway/agent-capabilities.md) 描述本批消费者可观察行为，目标为 `docs/specs/gateway/agent-capabilities.md`。已按独立审查通过的 delta 归并 current spec，并更新 Gateway 入口 Requirement 计数；本 unit 随收尾归档。
