# bugfix-527-M1 — Progress

## 当前状态

- R1、R2、R3 已完成并合入 `unit/bugfix-527`；Reviewer fix1 的 R4 与扩展门禁已完成，等待 rebase 与重新集成。
- 基线: `73 passed`（self-improvement、background fork、skill_manage、usage、skill_view）。

## R1 — 建立来源链红测并最小贯通 F3

- Context: 自动 Skill Review 创建链已有 source 消费端，但 Review 入口未声明 F3，导致真实 `.usage.json` 稳定落为默认 F1。
- Decision: `fork_conversation` 新增可选 `metadata_overrides`，与父 metadata 合并后仍强制后台 `run_origin` 并去掉陈旧 `tool_call_id`；Skill-only / Combined Review 只对本次 fork 注入 `skill_creation_source=F3`。
- Rationale: 来源意图由 self-improvement 生产者声明，通用 fork 只负责隔离地传递；不修改 `skill_manage` 的既有默认，也不触碰 Allowlist。
- Evidence:
  - Tests: 红测 `2 failed`，两种 Review 均显示实际 `F1 != F3`；最小实现后同命令 `2 passed`。
  - Entry: `tests/integration/test_self_improvement_skill_source.py` 从 Kernel SDK 公共入口 `build_kernel/create_session/submit` 进入，经过生产 `agent_end` 后台 hook、fork wrapper、真实 `skill_manage(create)` 与 usage sidecar 落盘，Skill-only / Combined 均读回 `source=F3`。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/integration/test_self_improvement_skill_source.py` → `2 passed`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert 本 roadpoint commit，恢复 fork 不接受 metadata override 的旧行为。
- Commits: `674d571b9`。
- Next: R2 证明 memory-only、普通 fork、普通用户 create 均不被污染，并跑扩展回归。

## R2 — 锁定不污染边界并扩大回归

- Context: F3 只能属于自动 Skill Review 的创建行为，不能借通用 fork 扩散到 memory-only、普通 fork 或用户手工创建；F4 batch/蒸馏等已有来源语义也必须保持。
- Decision: 在既有 owner 测试中补窄断言：Skill-only / Combined producer 显式传 F3，memory-only 传 `None`；普通 fork metadata 不凭空出现来源；真实普通 `skill_manage(create)` sidecar 仍为 F1。
- Rationale: 跨边界 integration 测试保护正向链，既有最低层 owner 分别保护三个负向边界，避免再造重复的高层路径。
- Evidence:
  - Tests: `81 passed`，覆盖新增 integration、self-improvement、background fork、skill_manage、usage、skill_view 与 skill batch review。
  - Entry: 普通 create 通过真实 `SkillManageTool.run` 写入临时 `.usage.json` 并读回 `F1`；自动 Review 的入口证据同 R1。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/integration/test_self_improvement_skill_source.py tests/unit/test_self_improvement_hook.py tests/unit/test_background_hook_fork.py tests/unit/test_skill_manage_tool.py tests/unit/test_usage.py tests/unit/test_skill_view.py tests/unit/test_skill_batch_review.py` → `81 passed`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert 本 roadpoint commit；R1 的正向 F3 修复仍可独立保留。
- Commits: `38d114ece`。
- Next: R3 回填 fix.md、跑扩展门禁、rebase 并合入 unit 分支。

## R3 — 回填 lite 证据并完成集成

- Context: lite 单必须用原始症状的真实入口闭环，并在合入 unit 前完成风险扩展门禁与可复查文档。
- Decision: 把 R1 的内部 handler 回归提升为真实 Kernel SDK session；使用 pytest 临时 `.nanoassistant` 配置将阈值设为 1，主轮先执行只读 Skill list，再由后台 Review 创建 Skill并检查 sidecar。生产数据与 Allowlist 完全隔离。
- Rationale: SDK session 是本缺陷可达的真实内核入口，能同时覆盖 builtin hook 加载、agent_end 后台 dispatch、fork metadata、工具执行与持久化接线；临时 Workspace 让验证可重复且不污染本机状态。
- Evidence:
  - Tests: 聚焦 `81 passed`；扩展 `tests/unit tests/integration` 为 `2637 passed, 2 warnings in 143.47s`。
  - Entry: `tests/integration/test_self_improvement_skill_source.py` 的 Skill-only / Combined 两例均从 SDK submit 进入并在临时 `.usage.json` 读回 F3；修前同一断言为 `F1 != F3`。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/integration/test_self_improvement_skill_source.py` → `2 passed`；全量 unit + integration → `2637 passed`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `2b9a99d91` 恢复较低层回归；revert `674d571b9` 恢复修复前行为。
- Commits: `2b9a99d91`、`e5f1c6724`；unit merge `7a47f80f0`。
- Next: milestone 已完成，等待 unit reviewer / verifier。

## R4 — Reviewer fix1：收窄 creation provenance 消费

- Context: change-code-review 在冻结 HEAD `599d42d3c` 发现 fork-wide `skill_creation_source=F3` 同时进入 `skill_view`；若它首次查看无 usage 记录的手工/遗留 Skill，`bump_skill_usage` 会误建 F3 记录并使其进入自动生命周期。
- Decision: `SkillViewTool` 首次建立 usage record 时固定使用既有默认 F1，不再从当前 session 的 creation provenance 推断被查看 Skill 的历史来源；`SkillManageTool._create` 仍是 `skill_creation_source` 的唯一消费方。已有 usage record 继续由 `setdefault` 保留其 F3/F4。
- Rationale: creation provenance 描述“本次 create 动作”，不是整个 fork 内所有 Skill 的来源；在 read owner 收窄消费能保留 fork metadata 与 create 正向链，同时避免改动 usage 通用原语或 Allowlist。
- Evidence:
  - Tests: 红测 Skill-only / Combined 两例均显示无记录手工 Skill `F3 != F1`；修复后入口 + SkillView owner `14 passed`，聚焦保护矩阵 `82 passed`，changed-file Ruff 全绿；扩展 unit + integration `2638 passed, 2 warnings in 497.18s`。
  - Entry: Kernel SDK `build_kernel → create_session → submit → agent_end Review` 同轮先 `skill_view(manual-skill)` 再 `skill_manage(create auto-review-skill)`；最终 sidecar 分别为 F1 / F3。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/integration/test_self_improvement_skill_source.py` 覆盖 Skill-only / Combined；`tests/unit/test_skill_view.py` 覆盖无记录 Skill 与已有 F3/F4。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `65d0cc0bc` 回到 reviewer finding 的冻结实现。
- Commits: `65d0cc0bc`；docs 证据提交待完成。
- Next: rebase `origin/unit/bugfix-527`，复验后获取 unit 锁并合入。

## Promotion Candidates

None.
