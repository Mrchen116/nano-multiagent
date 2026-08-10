# bugfix-527-M1 — Progress

## 当前状态

- R1 已完成；R2 正在锁定不污染边界并扩大回归。
- 基线: `73 passed`（self-improvement、background fork、skill_manage、usage、skill_view）。

## R1 — 建立来源链红测并最小贯通 F3

- Context: 自动 Skill Review 创建链已有 source 消费端，但 Review 入口未声明 F3，导致真实 `.usage.json` 稳定落为默认 F1。
- Decision: `fork_conversation` 新增可选 `metadata_overrides`，与父 metadata 合并后仍强制后台 `run_origin` 并去掉陈旧 `tool_call_id`；Skill-only / Combined Review 只对本次 fork 注入 `skill_creation_source=F3`。
- Rationale: 来源意图由 self-improvement 生产者声明，通用 fork 只负责隔离地传递；不修改 `skill_manage` 的既有默认，也不触碰 Allowlist。
- Evidence:
  - Tests: 红测 `2 failed`，两种 Review 均显示实际 `F1 != F3`；最小实现后同命令 `2 passed`。
  - Entry: `tests/integration/test_self_improvement_skill_source.py` 从生产 `agent_end` hook handler 进入，执行实际 fork wrapper、真实 `skill_manage(create)` 与 usage sidecar 落盘，Skill-only / Combined 均读回 `source=F3`。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/integration/test_self_improvement_skill_source.py` → `2 passed`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert 本 roadpoint commit，恢复 fork 不接受 metadata override 的旧行为。
- Commits: 本提交（R3 回填 hash）。
- Next: R2 证明 memory-only、普通 fork、普通用户 create 均不被污染，并跑扩展回归。

## Promotion Candidates

None.
