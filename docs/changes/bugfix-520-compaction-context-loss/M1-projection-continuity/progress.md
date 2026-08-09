# bugfix-520-M1 — Progress

## Baseline

- Context: unit 分支与远端同步，milestone worktree 从 `origin/unit/bugfix-520` 创建；M1/M2 范围无交叉。
- Evidence:
  - `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/test_session_persistence_fidelity.py` → 20 passed。
  - `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/e2e/critical_paths/test_agent_config_context_continuity_critical_path.py tests/e2e/critical_paths/test_prompt_cache_alert_critical_path.py` → 2 passed。

## R1 — canonical recoverable projection 与字段对称

- Context: `load()` 已按 latest boundary、active branch 和 recovery 物化消息；compaction event path 却逐 raw turn 投影，既包含废弃分支/旧 boundary 前历史，又丢失 parent/tool/group/reasoning，且没有合成 recovery result。
- Decision: 让两条读取路径共用 `_project_recoverable_messages()`；event path 先保留 compaction audit/control entries，再把 canonical Messages 对称适配为 turn events。`new_turn_appended_entry()` 与 `message_from_turn_entry()` 对称承载当前 durable Message 字段。
- Rationale: active/recovery 规则仍只有 transcript 一个 owner，planner 与 provider 不需要理解 raw JSONL schema，也不增加第三套 DTO。
- Evidence:
  - Tests: 红测在旧代码稳定显示 projected 首项仍是 `pre-user`、而 `load()` 首项是 `compact-summary`；修复后相关 persistence/transcript/planner/audit/manual compact 共 37 passed。
  - Entry: N/A；本 roadpoint 修复最低层投影 seam，真实 IM/Gateway 入口由 R2 覆盖。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/unit/test_session_persistence_fidelity.py::test_compaction_projection_matches_latest_recoverable_transcript` 同时比较双路径语义、排除 abandoned branch，并把 normal/recovery tool pair 送入 Anthropic mapper。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退到 `a9b1a1885`。
- Commits: 本 roadpoint commit。
- Next: R2 recording fixture 与真进程 compaction/restart journey。

## Promotion Candidates

None.
