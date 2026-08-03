# refactor-488: As-built Design

> 本文在实现完成后根据实际 diff 与对话中的确认决定整理，描述最终落地设计。

## 实现范围

- Base: `26d05224c90424100199645aadbfea2215af5aa5` (`origin/main`)
- Head: 本 unit 的提交 head；以 PR 的已 push head 为准。
- Included dirty files: `.claude/skills/change-orchestrator/SKILL.md`、`.claude/skills/change-orchestrator/references/codex-execution-notes.md`、`tests/contract/test_change_skill_archive_contract.py`、`tests/contract/test_change_workflow_documentation_contract.py`。
- 受影响模块：change orchestration prompt contract 与 Codex subagent dispatch mapping。

## 最终结构

### 组件与职责

- `change-orchestrator/SKILL.md`：保留 unit 准入、专属 worktree、worker 边界、独立 gate、finding 裁决、选择性复验、final sync、归档和 PR/CI；删除重复解释、固定轮询、小抄和与当前阶段无关的强制读取。
- `references/codex-execution-notes.md`：保留 Codex 工具映射、稳定 task identity 与显式模型/推理强度；移除不受当前 spawn 接口支持的 `agent_type`，并指定 code-review finder=Luna、verifier=Terra。
- workflow contract tests：只验证 PR 模板的固定 blob 链接，以及 lifecycle 文档中的 selected-gate matrix；不把 agent 行为提示或已退役文件名视为接口。
- `docs/changes/refactor-488-change-orchestrator-skill/`：记录快速开发路径中真实发生的需求与 as-built design，不补造 milestone、design review、verifier、产品验收或 code-review 报告。

### 调用链与数据流

1. orchestrator 启动时只读取首文档、design、最新 design review、Runbook/reference contract 和实时 Git/PR 状态；完整 artifact 由实际消费阶段读取。
2. worker 使用已有的明确派发包；reviewer/verifier/code-review 使用主 skill 内的最小 handoff schema，绑定 `validated_at`、`executed_base`、worktree、模式和精确 diff range。
3. fix 前冻结 `pre_fix_head`；code-review 对新源码 delta 使用 `patch`，只有 verifier 使用 `delta`。
4. delta 校正、canonical spec 归并、promotion 与 archive 都先 commit/push，再让独立 worktree 或 PR 消费该 head。

### 状态、数据与兼容性

- 不新增生命周期快照、活动清单或运行时状态文件；调度状态仍只存在当前会话和已有 unit 产物中。
- 不改变 Full、零用户面 Full、Bugfix lite 的 selected-gate 矩阵。
- archive 仍是完整 unit 目录的 `git mv`，而非复制或压缩历史。

## 关键决策

| 决策 | 原因与约束 | 代码定位 |
|---|---|---|
| 将主 skill 压缩到 500 行以下 | 强模型不需要重复 rationale、shell 小抄或固定轮询；非显然的交付边界必须保留。 | `.claude/skills/change-orchestrator/SKILL.md` |
| 只保留阶段性 reference | `worktree-runtime`、spec 归并规则、PR 模板和 Codex 映射各自承载不可猜测的阶段接口；不再引用生命周期总览或 child skill。 | `SKILL.md` 的“读取范围” |
| 在 parent 保留 gate handoff | mode、snapshot、range 与 worktree 由 orchestrator 决定，不能交由 child skill 自行猜测。 | `SKILL.md` 的“选择门禁” |
| 删除 skill 文本断言 | agent 行为约束由 skill 与实际 unit 验收承担；字符串断言会阻碍等价的 prompt 重构。 | `tests/contract/test_change_skill_archive_contract.py` |
| 显式远端可见性边界 | corrected-delta verifier 与 PR 只能读取已 push 的 unit head。 | `SKILL.md` 的“收尾与 PR” |
| Finder=Luna、verifier=Terra | 按用户指定的 Codex code-review 模型映射执行。 | `references/codex-execution-notes.md` |

## 失败路径、风险与回滚

- 若 Codex runtime 未暴露 `gpt-5.6-luna`，finder 派发会被 runtime 拒绝；恢复为可用模型前不应静默降级。
- 若精简后发现 gate handoff 缺字段、final sync 无法说明 gate 有效性或独立 gate 产生报告外写入，unit 保持 active 并回到修复/复验。
- 回滚是还原本 unit 对两个 skill 文件及其 archive 文档的提交；不涉及产品数据或运行时迁移。

## 与初始意图的差异

无。实现遵循“流程大体不变、删除重复和无用描述”的范围；review 中确认的 handoff、远端可见性和 diff 检查缺口被补回，因为它们是可执行接口而非冗余说明。

## 验证定位

- 用户验收：用户逐轮审阅精简方向、引用边界、子 agent 边界和 Finder/Verifier 模型映射，并明确要求补齐本次文档记录。
- 自动化测试：CI 同款 `pytest -m "not e2e" -n 4 --dist worksteal`、`ruff check .`、`ruff format --check .`、`scripts/docs_check.py` 与 `git diff --check`。
- 运行证据：对 Gate 2 拒绝路径和 fix→revalidation→corrected-delta→archive→PR 的只读前向演练。
- 独立 code review：用户明确要求不执行。归档与 PR 基于这一显式豁免；PR 不得声称 code review 已通过。

## Canonical 文档影响

- Delta-spec：无。
- 归并目标：无。
- 若无变更，原因：本次只改变 agent skill 的内部执行提示，不改变产品或 SDK 的 current behavior；`docs/development/change-workflow.md` 仍是生命周期权威，不复制 role 内部步骤。
