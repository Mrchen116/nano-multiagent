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

## R2 — A 面决策2:消双写,apply() 降纯结果构造 + 内存断言

- Context: `_compact_session` 存在双写——直写路径(经已解析 path 写 compact_boundary+summary)+ `apply()→append_compaction`(第二写,workspace_root=None)。第二写在生产 data_dir=None 模式抛 SessionNotFoundError → overflow 恢复崩在落盘(已吐部分输出后)。直写路径含 load-bearing 内存重置 `_session_histories[session_id]=[summary_msg]`(下一轮 cache-first 消费),不能丢。
- Decision: 保留直写(含内存重置);`CompactionApplier.apply` 去 `append_compaction` 持久化副作用、改纯结果构造,新增 `summary_uuid` 形参,`entry_id` 对齐直写 `summary_msg.message_id`(消写/观测漂移)。summary_msg 上移到 `if path` 守卫之前生成,使 result entry_id 在 path 缺省时仍一致。`CompactionApplier()` 不再依赖 session_manager。
- Rationale: 决策2——要删的「冗余写」是 apply() 的持久化副作用,而非直写;按「删直写留 append_compaction」收敛会丢内存重置(WARNING-1),且磁盘重放测试照不到该内存回归。`append_compaction` 在 manager 保留(test_session_manager / contract / integration 直接调它作 API),只是不再被 apply() 调用。
- Evidence:
  - Tests: 新增 `test_overflow_compaction_workspace_aware_does_not_crash`(data_dir=None overflow,修前红崩在 append_compaction)、`test_compaction_single_write_and_memory_reset`(单写=磁盘恰一对 boundary+summary、boundary 先于 summary、entry_id==summary_uuid、内存 `_session_histories` 仅含 summary 轮);compaction+loop+contract+manager 区 37 passed。
  - Entry: data_dir=None 生产模式 overflow 恢复 retry 成功出 "retry-ok"、不失忆;manual compact 后磁盘单写 + 内存重置经断言核实。
  - Frontend State Matrix / Browser QA / Visual: N/A
  - E2E/Regression: 上述两条集成回归用例;内存断言直读 `runtime._session_histories`(决策2 退出标准明确要求的内部不变量守护,磁盘重放照不到)。
- Rollback: revert C2(决策2)回到双写 + data_dir=None 落盘崩溃态。
- Commits: C1=test 红测, C2=fix 消双写, C3=本段

## R3 — B 面决策3:失败 message 级即时反馈

- Context: `main.py` `_build_relay_lifecycle_callback` 的 `failed` 分支只发 relay-task 级 `delivery_receipt`,不像 `completed` 分支同时发 message 级 `node.report`。占位气泡靠 message 级 report 翻态,缺它 → 气泡卡 running 直到 IM 120s idle watchdog 兜底,且兜底文案掩盖真因。
- Decision: failed 分支镜像 completed,从 `message.metadata` 取 `message_id`,补发 `send_report(status="failed", agent_id, session_key, conversation_id, message_id, summary=update.error)` → `node.report`,保留既有 `delivery_receipt(failed, detail=update.error)`。真因经 `summary` 承载(send_report 无 error 形参;IM failed 气泡文案读 summary)。watchdog 退为「节点真死」最后兜底。
- Rationale: 决策3——`_run_turn` 已 emit phase=failed 带真因,缺的就是这条 message 级 report;镜像 completed 不另造路径,IM 已支持 failed 翻消息,IM 不改。
- Evidence:
  - Tests: 新增 `test_relay_lifecycle_callback_failed_sends_message_level_report_with_real_cause` 修前红(只发 delivery_receipt)、修后绿;relay lifecycle 区 12 passed。
  - Entry: callback 单元经真 `UpstreamReporter` + `_FakeIMManager` 驱动,断言 failed → 先 node.report(status=failed, message_id=msg-1, summary=真因) 再 node.delivery_receipt(failed)。
  - Frontend State Matrix / Browser QA / Visual: N/A(gateway callback,无 UI 改动;气泡翻态是 IM 既有 failed report 路径,本 unit 不改 IM/前端)
  - E2E/Regression: 上述单元回归用例;端到端真栈气泡验收留给 reviewer(design Runbook)。
- Rollback: revert C2(B 面)回到 failed 只发 delivery_receipt。
- Commits: C1=test 红测, C2=fix failed report, C3=本段
