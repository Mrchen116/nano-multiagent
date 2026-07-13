# refactor-462-M1 — Progress

## Baseline

- Context: M1 是一次性 session ownership cutover；必须先证明 main 基线稳定，避免把既有失败误归因到重构。
- Decision: 使用仓库共享 `.venv` 跑完整非 e2e 测试与 ruff 格式门禁。
- Rationale: 与项目 CI 的 Python job 一致，同时避免新建环境造成依赖漂移。
- Evidence:
  - Tests: `PATH=/Users/czj/Repos/nano-multiagent/.venv/bin:$PATH /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -m 'not e2e'` → `3496 passed, 1 skipped, 23 deselected`。
  - Entry: N/A（实现前基线）。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: N/A（实现前基线）。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: N/A（尚未修改产品代码）。
- Commits: plan commit 待提交。
- Next: R1 C1 为 Transcript/Directory/Prompt seed/lifecycle 写最终 interface 红测。

## R1 — Transcript、Directory 与核心 session 数据模型

- Status: DONE
- Context: 旧 JSONL store 同时拥有 raw I/O 与会话语义，Runtime 又另存 tail/history/context maps；PromptSlots 只在进程内保存，重启后无法重建。
- Decision: 引入绑定 `SessionRef` 的 private `JsonlTranscript`、raw `JsonlSessionFiles`、stable-identity `SessionDirectory` 与 core-owned request/seed/context types；writer 收窄为 raw enqueue + durability barrier，旧入口暂留到 R4 cutover。
- Rationale: tail、repair、materialize、idempotency 与持久化 prompt seed 只有一个 per-conversation owner；Directory 的短 guard 只负责 identity intern，不承载 I/O 或事务。
- Evidence:
  - Tests: `python -m pytest -q tests/unit/agent/session/test_jsonl_transcript.py tests/unit/agent/session/test_session_directory.py tests/unit/test_session_file_state.py tests/unit/test_agents_md_runtime_snapshot.py` → `28 passed`。
  - Entry: `JsonlTranscript.create/load/append_external/prepare_for_run` 与 `SessionDirectory.create/open/get/find_by_metadata/close_all` 的真实 temp-dir 测试。
  - Frontend State Matrix: N/A（纯内核重构）。
  - Browser QA: N/A（纯内核重构）。
  - E2E/Regression: baseline 非 e2e 套件已通过；最终真实入口签收在 R4。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 `15c9ee5e` 及其 C1 `01ee0172`；旧 manager/store/runtime 路径在 R4 前仍可工作。
- Commits: `01ee0172`（C1），`15c9ee5e`（C2）。
- Next: R2 以 `ConversationSession` interface 红测锁定 lifecycle permit、active external append、compact stale commit 与 fork snapshot。

## R2 — ConversationSession 接管 turn/compact/fork transaction

- Status: TODO

## R3 — KernelExecutor、RunsRegistry 与 subagent 控制面

- Status: TODO

## R4 — SDK composition cutover、旧 seam 删除与真实入口签收

- Status: TODO
