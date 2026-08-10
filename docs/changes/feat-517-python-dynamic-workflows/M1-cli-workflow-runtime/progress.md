# feat-517-M1 — Progress

## Baseline / Coordination

- Context: M1 在 unit shared worktree 实施；M2 同时修改 IM/PA 范围。
- Decision: 仅修改并按路径提交 agent core/platform/sdk、coding_cli、M1 tests/docs；不暂存任何 M2 dirty 文件。
- Evidence:
  - Tests: 实施前 M1 targeted baseline `276 passed`；随后全量 `pytest -m 'not e2e' tests/ -q` 因并行 M2 Red tests 缺 `IM.domain.models.BackgroundReturn` 在 collection 阶段出现 3 errors，已通知 orchestrator，待 M2 变绿后补跑。
  - Entry: N/A（尚未实现）。
  - Frontend State Matrix: N/A（M1 无前端）。
  - Browser QA: N/A（M1 无前端）。
  - E2E/Regression: Luna 一 Agent lifecycle 归 reviewer；worker 不做规模实验。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A；Web must-match 状态归 M2，M1 只稳定数据契约。
- Rollback: 所有 M1 commit 均只含 M1 paths，可逐 commit revert；不影响并行 M2 dirty。
- Commits: pending

## R1 — 稳定共享公开契约与后台 carrier

- Context: pending
- Decision: pending
- Rationale: pending
- Evidence: pending
- Rollback: pending
- Commits: pending

## R2 — 实现受限 Python compiler、primitives 与 resume 状态

- Context: pending
- Decision: pending
- Rationale: pending
- Evidence: pending
- Rollback: pending
- Commits: pending

## R3 — 接入 platform manager、Workflow 工具与持久化

- Context: pending
- Decision: pending
- Rationale: pending
- Evidence: pending
- Rollback: pending
- Commits: pending

## R4 — 接入 turn activation、provider golden 与 SDK 管理方法

- Context: pending
- Decision: pending
- Rationale: pending
- Evidence: pending
- Rollback: pending
- Commits: pending

## R5 — 完成 coding_cli 产品旅程

- Context: pending
- Decision: pending
- Rationale: pending
- Evidence: pending
- Rollback: pending
- Commits: pending

## R6 — M1 回归、静态门禁与交付记录

- Context: pending
- Decision: pending
- Rationale: pending
- Evidence: pending
- Rollback: pending
- Commits: pending

## Promotion Candidates

None.
