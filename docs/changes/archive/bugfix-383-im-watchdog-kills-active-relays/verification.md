# Verification Report: bugfix-383

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 5/5 tasks complete |
| Correctness | 5/5 requirements covered |
| Coherence | Followed（1 minor inconsistency, see WARNING） |

No critical issues. 1 warning to consider. Ready for PR (with noted improvements).

---

## Completeness

**Tasks: 5/5 complete**

M1 所有 roadpoints 已标记 DONE：
- R1（写失败测试 RED）: DONE — `778f1d49`
- R2（实现 SQL + default + 文案 GREEN）: DONE — `01aff3c9`
- R3（env override 验证 + 文档）: DONE — `pending commit → 已合并`

**Spec 覆盖**（incident.md 修复方向 + design.md 测试策略）：

| requirement | 有实现 |
|---|---|
| SQL 改为 LEFT JOIN + COALESCE 判活 | ✓ |
| 阈值 300s → 120s（env default + 函数 default） | ✓（env default，见 WARNING） |
| 失败文案改为 "relay idle for Ns with no new event" | ✓ |
| bugfix-365 行为保留（backfill + identity 恢复） | ✓ |
| 5 个新测试用例 | ✓ |

---

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| D1: SQL 改 LEFT JOIN + COALESCE（最近 event 时间判活） | `relay_watchdog.py:48-61` | `test_active_relay_not_killed`、`test_idle_relay_killed_with_new_wording`、`test_no_event_fallback_to_created_at` | covered |
| D2: env default 300 → 120 (`app.py:298`) | `app.py:298` | 无需测试（env 读取链路透明） | covered |
| D3: 文案改 "relay idle for Ns with no new event" | `relay_watchdog.py:66`、`relay_watchdog.py:127` | `test_idle_relay_killed_with_new_wording`（断言 content 含新文案） | covered |
| D4: `_build_failed_payload` 保留 | `relay_watchdog.py:112-171` 未修改 | `test_scan_inherits_prior_relay_processing_payload_for_id_continuity`、`test_scan_recovers_agent_identity_when_relay_processing_missing` | covered |
| D4: `_backfill_failure_detail_into_message_content` 保留 | `relay_watchdog.py:201-226` 未修改 | `test_scan_writes_detail_into_empty_message_content`、`test_scan_appends_error_note_to_partial_streamed_content` | covered |
| 边界：last_evt 121s 前 → 被杀 | `relay_watchdog.py:42`（cutoff 计算） | `test_boundary_just_over_idle_threshold` | covered |
| 边界：last_evt 119s 前 → 不被杀 | 同上 | `test_boundary_just_under_idle_threshold` | covered |
| 活跃 relay 不被杀（核心回归场景） | SQL COALESCE 路径 | `test_active_relay_not_killed` — msg 10min 前创建，event 30s 前推进，返回 0 且 status=running | covered |

**测试结果验证**：
- `pytest tests/im_service/unit/test_relay_watchdog.py`: **12/12 passed**
- `pytest tests/im_service`: **258/258 passed，0 回归**

---

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| D1: LEFT JOIN + COALESCE SQL | 是 | `relay_watchdog.py:48-61`，与 design.md 中 SQL 完全一致 |
| D2: `app.py:298` env default → "120" | 是 | `app.py:298`: `os.getenv("IM_RELAY_WATCHDOG_TIMEOUT_SECONDS", "120")` |
| D3: 文案 "relay idle for {N}s with no new event" | 是 | `relay_watchdog.py:66`（detail_text）、`relay_watchdog.py:127`（payload detail 字段） |
| D4: 保留 `_build_failed_payload` / `_backfill_failure_detail_into_message_content` | 是 | 函数体完整保留，无修改 |
| watchdog interval 30s 不变 | 是 | `run_relay_watchdog` 的 `interval_seconds=30` 未动 |
| `scan_and_fail_stuck_running_messages` default 改 120 | 是 | `relay_watchdog.py:26`: `timeout_seconds: int = 120` |

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

- **`run_relay_watchdog` 的 `timeout_seconds` 默认值未同步为 120**：`relay_watchdog.py:234` 仍为 `timeout_seconds: int = 300`，而 `scan_and_fail_stuck_running_messages` 已改为 `120`（line 26）。在实际部署路径下无影响（`app.py` 总是从 env 读值并显式传入），但若有测试或第三方代码直接调用 `run_relay_watchdog()` 不传 `timeout_seconds`，会得到 300s 旧行为，与 D2 设计意图矛盾。
  - 建议：将 `relay_watchdog.py:234` 的 `timeout_seconds: int = 300` 改为 `timeout_seconds: int = 120`，与 `scan_and_fail_stuck_running_messages` 的 default 保持一致。

### SUGGESTION（可以修）

无。
