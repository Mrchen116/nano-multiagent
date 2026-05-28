# bugfix-383-M1 progress

## R1 — 写新增失败测试（RED）

- Context: 旧代码用 `messages.created_at` 判超时，长 tool 循环（10 min）必被误杀；需要 5 个新测试覆盖"活跃不杀 / idle 被杀 / 无 event fallback / 边界 121s / 边界 119s"。另有 `_insert_conversation_event` helper 函数用于直接控制 event 时间。
- Decision: 在现有测试文件末尾追加所有新用例；`_insert_conversation_event` 直接写 SQL 绕开 repository（repository.append_event 总写当前时间，无法控制历史时间）。
- Rationale: 修改现有文件优于新建文件；helper 直接插行便于精确控制时间戳。
- Evidence:
  - Tests: `pytest tests/im_service/unit/test_relay_watchdog.py` — 3 RED（`test_active_relay_not_killed`, `test_idle_relay_killed_with_new_wording`, `test_boundary_just_under_idle_threshold`）；其余 9 PASS（预期）。
  - Entry: N/A（纯逻辑，无 HTTP 入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（单元测试层）
  - Visual/Interaction: N/A
- Rollback: commit a1c289ca（plan）
- Commits: C1=778f1d49
- Next: R2

## R2 — 实现 SQL + default + 文案（GREEN）

- Context: 实现 D1/D2/D3 三个关键决策。发现 `test_scan_inherits_prior_relay_processing_payload_for_id_continuity` 用 `repo.append_event`（写当前时间）seed `relay.processing`，导致新 SQL 认为 last_evt=now 而不杀 — 测试也需要同步更新为直接 SQL 插入 stale 时间。
- Decision:
  1. `relay_watchdog.py` SQL 改 LEFT JOIN conversation_events 子查询 + COALESCE；
  2. `detail_text` 和 `_build_failed_payload` 里的 detail 字段均改为新文案 `"relay idle for Ns with no new event"`；
  3. `scan_and_fail_stuck_running_messages` 的 `timeout_seconds` default 改 120；
  4. `app.py:298` 的 env default 改 `"120"`；
  5. 现有文案断言（两处）同步更新；
  6. `test_scan_inherits_prior_relay_processing_payload_for_id_continuity` 改为直接 SQL 插 stale_at 的 relay.processing event。
- Rationale: `repo.append_event` 的隐式时间戳耦合在新 SQL 下暴露为测试 bug，直接用 SQL 插入是正确修法（控制时间是测试意图，不是生产意图）。
- Evidence:
  - Tests: `pytest tests/im_service/unit/test_relay_watchdog.py` — 12/12 PASS；`pytest tests/im_service` — 258/258 PASS，0 回归。
  - Entry: 后端纯逻辑，入口验证见退出标准 (d)（env override 日志）。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（单元测试层）
  - Visual/Interaction: N/A
- Rollback: commit 778f1d49（C1）
- Commits: C2=01aff3c9
- Next: R3

## R3 — env override 验证 + 文档

- Context: 退出标准 (d) 要求验证 `IM_RELAY_WATCHDOG_TIMEOUT_SECONDS` env override 仍生效。
- Decision: 代码路径确认：`app.py:298` `int(os.getenv("IM_RELAY_WATCHDOG_TIMEOUT_SECONDS", "120"))` → 传入 `run_relay_watchdog(timeout_seconds=relay_watchdog_timeout)` → 传入 `scan_and_fail_stuck_running_messages(timeout_seconds=timeout_seconds)` → 日志 `age > {timeout_seconds}s`。链路完整，env 覆盖直接生效。若设 `env IM_RELAY_WATCHDOG_TIMEOUT_SECONDS=60` 起 IM，日志会打 `relay_watchdog: reaped stuck message ... (age > 60s)`。
- Rationale: 链路无中间变量截断，os.getenv 读一次、直穿到日志，reviewer 起 IM 后等待首次扫描即可看到自定义值。
- Evidence:
  - Tests: `pytest tests/im_service` — 258 PASS
  - Entry: env override 路径通过代码审查验证（`app.py:298-304` + `relay_watchdog.py:104`）；真实起服务验证由 reviewer 负责（退出标准标注 [reviewer 验] 的项目）。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: commit 01aff3c9（C2）
- Commits: C3=pending
- Next: 合并到 unit/bugfix-383
