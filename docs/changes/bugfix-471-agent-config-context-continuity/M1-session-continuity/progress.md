# bugfix-471-M1 — Progress

## 启动记录

- 已读 `incident.md`、`design.md`、项目规则、`docs/TESTING_GUIDE.md`、现有 Kernel/Gateway/session/scheduler 实现与测试。
- 基线：`PYTHONPATH=src pytest -m 'not e2e'` — 3628 passed，1 skipped，20 deselected（2026-07-21）。
- 本 milestone 不修改前端、IM timeline 或 divider；M2 负责这些可见缓存边界。

### R1 — Kernel runtime replacement

- Context: 配置变更不能创建第二份 session 或 transcript，且 model 与 capabilities 必须同一原子配置。
- Decision: 增加 SDK `SessionRuntimeConfig` 及 identity/state/result DTO；创建和 replacement 都在 transcript 持久化完整 raw runtime。`ConversationSession` 经既有 turn gate 执行 replacement，`Kernel.submit()` 从会话 runtime 获取 model 并拒绝冲突的 per-run override。
- Rationale: session 自己拥有 transcript、payload 与 turn 串行；把 replacement 放入该事务边界，防止 active turn 中途混用配置，并在重启后可由 transcript 还原。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/agent/session tests/integration/test_session_run_coordinator_real_kernel.py` — 24 passed；`PYTHONPATH=src ruff check src/agent/sdk src/agent/core/session src/agent/core/runs/executor.py tests/integration/test_session_run_coordinator_real_kernel.py` — passed。
  - Entry: integration 用真实 `build_kernel()`、会话、run 和 fake LLM 验证 replacement 后同一 session 以新 model 发起请求且请求历史保留前一轮用户内容。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/integration/test_session_run_coordinator_real_kernel.py::test_kernel_reconfigures_one_session_without_losing_transcript`，见 Tests。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A（M2）。
- Rollback: 回退 `469c4eeb0`，恢复 per-run model 语义与无 replacement 的 session API。
- Commits: C1=c2e46af7f，C2=469c4eeb0，C3=待提交。
- Next: R2 在 Gateway admission 内惰性比较 desired/applied runtime，并保留已有 binding。
