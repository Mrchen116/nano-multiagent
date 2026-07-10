# feat-394-M8: fix-round6 Progress

## R1 — 红测试 + CRITICAL-1 合约白名单行号

- Context: R6-1 的 ceil bug 导致 elapsed=interval+overhead 时 next_due 比 now 晚→不触发。CRITICAL-1 白名单行号 703 因 M7 插入 `_UNATTENDED_ORIGINS` 偏移到 707。
- Decision: 写红测试覆盖"连续两拍触发"和"大gap只触发一次"两个场景；同步更新白名单。
- Rationale: 红测试锁定 bug 行为，防止修复后回归。合约测试是 CI 门禁。
- Evidence:
  - Tests: `test_interval_triggers_on_second_tick_with_lll_overhead` + `test_heartbeat_interval_triggers_on_second_tick_with_overhead` → 红（修复前 0 runs）
  - `test_large_gap_triggers_only_once` / `test_heartbeat_large_gap_triggers_only_once` → 绿（大gap语义已正确）
  - `pytest tests/contract/test_no_hardcoded_workspace_dirname.py` → 绿（703→707）
- Commits: C1=3f2d6a5（测试+合约白名单）

## R2 — floor 实现修复 + awareness 注入改进

- Context: heartbeat_scheduler.py 和 cron_scheduler.py 各有一个 `_IntervalSchedule.due_times_up_to`，都用了 ceil。awareness 在 main.py 里调用 `_resolve_canonical_session_id() or ""` 时，如果返回 None，会用空字符串导致 JSONL 找不到。
- Decision: 两个文件的 `_IntervalSchedule.due_times_up_to` 统一改为 `steps = max(1, elapsed_secs // interval_secs)`（floor 语义）。更新了原来基于 ceil 语义写的 `test_interval_no_backfill_after_restart`（现在语义是"大gap触发一次最近时隙，而非等待绝对未来时隙"）。awareness 注入：优先从 `_canonical_session_store[agent_id]` 取（heartbeat 在 tick 时已填充），作为 `_resolve_canonical_session_id()` 的前置 fallback。失败日志级别从 debug 升级为 warning 以便诊断。
- Rationale: floor 确保 elapsed=interval+ε 时能触发（去掉 LLM overhead 对节律的影响）。大gap时 floor(N.X/1)=N，steps=N，next_due=last+N*interval≤now → 只触发一次（不补跑洪流）。canonical_session_store 是 heartbeat 维护的最可靠 session 源，比 SQLite session_bindings（只有用户发过消息才有）更早可用。
- Evidence:
  - Tests: `pytest tests/unit/personal_assistant/test_cron_scheduler.py tests/unit/personal_assistant/test_heartbeat_scheduler.py tests/contract/` → 52 passed
  - 全量 `pytest -m "not e2e"` → 2513 passed，2 failed（预先存在的 /tmp macOS 路径问题）
- Commits: C2=fix commit（ceil→floor + awareness）

## R3 — Live 验证 + 文档

- Context: 核心收口要求验证 recurring，历史轮次均漏了第二拍。
- Decision: 起 IM+Gateway（ephemeral port 55613）验证连续触发。
- Evidence:
  - **heartbeat 连续触发（≥3次）**：
    - 04:48:15 — 第一次
    - 04:48:45 — 第二次（差 30s）
    - 04:49:30 — 第三次（差 45s，含 LLM 耗时）
  - **cron 连续触发（≥3次，直聊消息）**：
    - `[2026-06-04T04:48:25] agent: Current time: 04:48:20 UTC`
    - `[2026-06-04T04:49:10] agent: Current time: 04:49:06 UTC`（差 ≈45s）
    - `[2026-06-04T04:49:47] agent: Current time: 04:49:42 UTC`（差 ≈37s）
  - **S5.1 不补跑**：cron-state.json 中 last_due_at 每次只推进一步（04:48:00 → 04:49:00 → 04:49:30）
  - heartbeat-state.json 更新序列证明两两间隔约30s，无跳跃洪流
  - pytest -m "not e2e" 全量 2513 passed
  - pytest tests/contract/ 102 passed
  - tsc -b 通过（no errors）
  - vitest（unit-feat-394 worktree）: PASS (361) FAIL (0)
- Rollback: git revert 到 C1 commit hash
- Commits: C1=red tests, C2=impl fix, C3=docs
- Next: 合入 unit/feat-394 → 触发 reviewer

## 设计修订说明

R6-1 修复改变了 `test_interval_no_backfill_after_restart` 的语义：
- 旧（ceil）：restart 后大gap → 等待下一个绝对未来时隙（不触发任何东西）
- 新（floor）：restart 后大gap → 触发最近一次错过的时隙（恰好一次），然后等待下一个完整周期

这个语义变更符合 "不刷屏" 的核心设计意图（一次 tick 最多触发一次，不补跑 N 次），且更符合 agent 的实际使用体验（重启后立即汇报一次，而不是静默等待）。
