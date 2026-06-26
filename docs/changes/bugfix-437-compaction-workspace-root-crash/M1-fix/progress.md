# bugfix-437-M1 — Progress

<!-- 每个 roadpoint 完成后实时追加。 -->

## R1 — A 面决策1:workspace_root 显式贯穿压缩读取点

- Context: 生产 `data_dir=None`(workspace-aware)模式下,threshold 预压缩 `loop._maybe_compact → list_entries(session_id)` 漏传 workspace_root → store 抛 SessionNotFoundError → run 死在读取(JSONL 0 条 compact_boundary,正是 plato 崩点)。overflow 恢复分支 `list_turn_messages(session_id)` 同样漏传,内部吞异常返回空 → 静默失忆。
- Decision: `loop.run`/`_execute_loop` 新增显式 `workspace_root` 参数(与 `current_working_directory_override` 语义分离——后者缺省回退全局 cwd,拿来定位会话存储会指向错误根),穿到 `_maybe_compact` → `list_entries(workspace_root=...)`;runtime 两处 `_execute_loop` 调用点传 `session_workspace_root`(= config.workspace_root);overflow `list_turn_messages` 带同根。
- Rationale: 决策1——从 runtime→loop 入口源头贯穿,而非逐点 hack(下一个还会再忘)。不弱化 store stateless 契约(补根到调用点,不退回猜路径)。
- Evidence:
  - Tests: `tests/integration/test_compaction_runtime_integration.py::test_threshold_compaction_workspace_aware_does_not_crash` 修前红(SessionNotFoundError@loop.py:871)、修后绿;compaction+loop 区 35 passed。
  - Entry: data_dir=None 真实生产模式 runtime.run 两轮触发 threshold 压缩,run 完成出 "ack"、落盘 CompactionEntry、可 list_turn_messages 重放含 summary。
  - Frontend State Matrix / Browser QA / Visual: N/A(内核改动)
  - E2E/Regression: 同上集成回归用例(workspace-aware 模式);_FakeSessionManager.list_entries 测试 fake 同步加 workspace_root 形参。
- Rollback: revert C2 (workspace_root 贯穿) 回到漏传崩溃态。
- Commits: C1=test 红测, C2=fix 贯穿, C3=本段
