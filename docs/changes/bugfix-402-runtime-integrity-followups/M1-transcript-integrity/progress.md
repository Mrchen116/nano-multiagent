# bugfix-402-M1 — Progress

## R1 — tool_call_recovery entry schema + JsonlSessionStore.prepare_transcript_for_run

- Context: JSONL session 中 assistant tool_calls 若进程被中断则无对应 tool result，下次启动恢复会话时 provider 拒绝该 transcript。需要在 run 前扫描并补齐。
- Decision: 在 `JsonlSessionStore` 新增 `prepare_transcript_for_run()`：持 per-path threading.Lock，flush writer，读 raw lines，建 pending/closed map，对 orphaned call_id 批量 append `tool_call_recovery` entry（确定性 idempotency_key），再次 flush；另加 `append_tool_call_recovery()` 轻量版供 runtime cancel/interrupt 路径直接调用。
- Rationale: JSONL append-only 要求不删改旧行；确定性 key 让 loader 物化时去重；锁保证同一 session 并发 prepare 只产生一套 recovery。load() 仍纯只读，不调 prepare。
- Evidence:
  - Tests: `pytest tests/unit/test_session_manager.py::TestPrepareTranscript -xvs` — 5 passed
  - Entry: N/A（纯后端存储层，无 HTTP 入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A — unit tests 覆盖 orphaned/partial/idempotent/readonly/closed
  - Visual/Interaction: N/A
- Rollback: revert C2 commit
- Commits: C1=前一 commit, C2=fix commit, C3=docs commit

## R2 — SessionService/SessionManager 暴露 prepare_transcript_for_run

- Context: 上层调用方（runtime）通过 SessionService/SessionManager 访问 store，不直接持 JsonlSessionStore 引用。
- Decision: 在 SessionManager 和 SessionService 各加一个同名方法，透传 reason/workspace_root/parent_session_id，委托 store。
- Rationale: 保持调用层不需要 downcast 到 store 即可调用 prepare；与现有 append/load 等方法风格一致。
- Evidence:
  - Tests: `pytest tests/unit/test_session_service.py -xvs` — 6 passed
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: revert C2 commit
- Commits: C1=红测试 commit, C2=实现 commit
