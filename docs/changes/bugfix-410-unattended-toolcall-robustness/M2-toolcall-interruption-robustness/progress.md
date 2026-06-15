# bugfix-410-M2 — Progress

## 启动澄清记录

- 范围确认（与 orchestrator）：design Milestone 表 M2 行 = runtime.py / core/session/ / core/tools/{registry,base}.py / gateway/inbound_pipeline.py / personal_assistant/main.py / IM/application/relay_watchdog.py / IM tool_call 持久化 / 前端 tool-calls-panel.tsx。不碰 auto_mode_gate（M1）。
- reason_code 链端到端 6 跳已核实（见开工信）。整条链单一 owner = M2。

## R1 — #82 恢复式 finally 覆盖 CancelledError

- Context: bugfix-402 的 eager-recovery 在 try 体末尾、靠 turn_meta.stop_reason 触发。外部 cancel()（gateway run-idle 看门狗）在工具/LLM 的 await 点打断 run 时，CancelledError 穿透、run 回不到迭代边界、不写 turn_meta → `_run_stop_reason=None` 不匹配 `in ("aborted","cancelled")` → 漏补悬空 tool_call + 脏内存缓存留存 → 下条消息 cache-hit 复用脏历史 → 砖化到进程重启（#82 reopen）。
- Decision: 把 recovery 抽成 `_recover_orphaned_tool_calls`，从 try 体移入 stop_reason-**独立**的 `finally`。新增 `except asyncio.CancelledError` 仅置 `_run_cancelled=True` 并 re-raise（保留 cancel 语义）。finally 无条件扫 `all_messages` 未闭合 tool_call。
- Rationale:
  - 无条件扫描不误伤正常完成 run——其 tool_call 都有对应 tool result，orphan 集天然为空、return no-op。
  - 两步保护级别不对等（按 design 必读陷阱）：`invalidate_session_cache` 是 load-bearing 自愈（同步原子 dict pop、无 await），放 finally 最前、任何 I/O await 之前，cancel 传播中也必跑完、无需 shield；`append_tool_call_recovery`+flush 是 out-of-band 加速、做 I/O，cancel 路径走 `asyncio.shield` best-effort，失败由下次 `prepare_transcript_for_run` 兜底。
  - reason 不依赖 turn_meta：cooperative abort→interrupted / cancel→cancelled；无 turn_meta（CancelledError 穿透）合成 interrupted。
- Evidence:
  - Tests: `tests/unit/test_agent_runtime.py -k "recovery or cancellederror"` 6 passed（2 新 CancelledError + 4 既有 abort/cancel/cache-hit/completed 无回归）。broader runtime+session+loop+executor+streaming 424 passed。ruff check + format 通过。
  - Entry: 后端内部恢复路径，真实入口=regression 测 `test_runtime_recovery_on_cancellederror_visible_to_next_run`——复现 #82 reopen 砖块：同进程内 cancelled run 后第二个 run 的 history 含 `is_recovery=True` 的 synthetic tool result（修前 assert False，修后通过）。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: `tests/unit/test_agent_runtime.py::test_runtime_recovery_on_cancellederror_passthrough` + `::..._visible_to_next_run`（落库回归）
  - Visual/Interaction: N/A
- Rollback: revert C2 commit（finally 重构）→ 回 R1 C1 红测态
- Commits: C1=plan 后第 1 个 test commit, C2=fix(...R1) finally 重构, C3=本段 docs

## R2 — #98 看门狗豁免

（待补）

## R3 — #97 终态在飞 tool_call reconcile

（待补）

## R4 — reason_code 全链 + 前端文案

（待补）
