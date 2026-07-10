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

## R3 — runtime._run 调用 prepare_transcript_for_run + load 物化 recovery

- Context: 光有 prepare_transcript_for_run 写 recovery entry 还不够——load() 需要把 recovery entry 物化为合成 tool result Message，runtime 也需要在加载历史前调用 prepare。
- Decision: (1) `JsonlSessionStore.load()` 读取所有 `tool_call_recovery` entries，在最终 messages 序列里为每个 orphaned call_id 在对应 assistant 消息后插入合成 `role="tool"` Message；(2) `runtime._run_impl` 的 cache-miss 分支在 `load()` 前先调用 `prepare_transcript_for_run(reason="orphaned")`。
- Rationale: load() 是唯一物化 Message 序列的地方，在这里注入合成 result 能保证所有消费者（prompting、mapper）看到合法 transcript。Cache-hit 时历史已经在内存中是合法的，不需要重复 prepare（运行中的 cancel/interrupt 由 R4 另处理）。
- Evidence:
  - Tests: `pytest tests/unit/test_session_persistence_fidelity.py::TestOrphanedToolCallRecovery tests/unit/test_agent_prompting.py -xvs` — 全绿
  - Entry: N/A（纯后端，无 HTTP 入口；mapper 层合法性由单测覆盖）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: revert C2 commit
- Commits: C1=红测试, C2=实现（jsonl_store + runtime）

## R4 — 中断/取消/shutdown 写 tool_call_recovery 终态

- Context: 运行被 cancel/interrupt/shutdown 时，已持久化的 assistant tool_calls 没有对应 result。需要有机制让这些 call_ids 获得终态 recovery entry，使下次 load + build_chat_messages 合法。
- Decision: R1 已实现 `append_tool_call_recovery()`（轻量版，直接 append 已知 call_id），R3 中 load() 已能物化 recovery entry 为合成 tool result。R4 补充了三条 regression test，验证 interrupt/cancelled/shutdown 三种 reason 的完整链路（append → flush → load → build_chat_messages 合法）。runtime 层调用 `append_tool_call_recovery` 的时机由 R3 的 cache-miss prepare + 运行结束后 prepare 共同覆盖（进程内中断后 cache 失效，下次 cache-miss 时触发 prepare）。
- Evidence:
  - Tests: `pytest tests/unit/test_session_manager.py::TestInterruptCancelRecovery -xvs` — 3 passed
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: regression coverage 落在 TestInterruptCancelRecovery
  - Visual/Interaction: N/A
- Rollback: revert C1 commit（仅 test 文件，无风险）
- Commits: C1=测试（tests 直接绿，因为 R1/R3 已实现机制）

## R5 — 集成：prepare + load 全流程 + 全套测试绿

- Context: 验证跨 store 实例（模拟进程重启）的 prepare 幂等性，以及全部指定测试全绿。
- Decision: 在 test_session_store_persistence_integration.py 新增 `test_prepare_transcript_idempotent_across_process_restart`：3 个不同 JsonlSessionStore 实例，前两个各 prepare 一次，第三个 load，验证只有 1 条 recovery entry 且 transcript 合法。
- Rationale: 与 unit 层 idempotency 测试互补——unit 测试同一 store 实例两次 prepare，integration 测试不同 store 实例（依赖文件锁全局 _PATH_LOCKS，需验证不同实例间也生效）。
- Evidence:
  - Tests: 所有 tests/unit/*.py tests/integration/*.py tests/contract/*.py tests/im_service/*.py 逐文件全绿（总计 300+ passed，0 failed）
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A — e2e 需要 IM + Gateway 运行环境
  - Visual/Interaction: N/A
- Rollback: revert integration test commit
- Commits: C1=集成测试
