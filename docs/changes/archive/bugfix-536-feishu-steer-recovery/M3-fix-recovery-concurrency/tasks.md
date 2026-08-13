# bugfix-536-M3: recovery successor closure race

> Align: `../incident.md`, approved `../design.md`, `../design-review.md`, and the
> three approved delta-specs. This targeted fix changes no public contract.

## Goal

Close the failed-adopted-successor race reported after M2. A normal message
accepted immediately before failed-successor cleanup must either enter a valid
re-handoff or receive one terminal lifecycle; it must never be removed from the
follower ledger without settlement.

## Exit criteria

- [x] Linearize the unconsumed-suffix decision and terminal successor close under
  the session transition owner.
- [x] Preserve re-handoff when an unconsumed suffix already exists; preserve
  normal same-run steering and explicit control/shutdown fences.
- [x] Add a deterministic regression that holds dispatch preparation inside the
  transition lock, accepts a concurrent follower, and proves exactly-one
  terminal lifecycle, released busy state, and a following normal reply.
- [x] Run focused recovery tests, the M1/M2 aggregate, static/doc checks, and a
  relevant isolated Gateway/Web IM public-path smoke.

## 测试策略

- 保护的回归风险与可观察 seam: accepted follower 在 failed successor cleanup
  之前赢得 admission 后必须由同一 recovery owner 结算；lifecycle、busy state 与
  subsequent reply 是可观察结果。
- 已有保护与处置:
  `tests/unit/personal_assistant/test_recovery_handoff_concurrency.py` (keep) 是
  该锁交错的最低 owner；它不复制无 suffix、normal same-run 或 control 的既有风险。
- 落层/目录/marker: `tests/unit/personal_assistant/`, marker: 无；受控 Kernel 与
  coordinator transition lock 在此层才能确定性暴露该竞态。
- 文件归属: 保留
  `test_recovery_handoff_concurrency.py`; 它按行为命名并只承载这个并发交错。
- 可选依赖 importorskip: 无。
- 本 milestone 产生的一次性验收证据(收尾删除,不进套件): 无；隔离 Web IM smoke
  的结果仅记录在 `progress.md`。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| admission-wins follower 的 nested re-handoff | `test_recovery_handoff_concurrency.py::test_lock_held_accepted_follower_is_terminalized_at_failed_successor_close` | keep | 这是唯一确定性持锁交错：follower 只完成一次、busy 释放且后续普通消息回复。 | M3 focused recovery command |
| failed successor 没有新 suffix 的 terminal closure | `test_recovery_handoff_coordinator.py::test_failed_adopted_successor_without_suffix_releases_session` | keep | 保留失败 terminal、active/busy 释放与后续普通消息；不与 admission-wins re-handoff 重复。 | M3 focused recovery command |
| normal same-run steering 与 `/stop`、`/new`、shutdown fences | `test_recovery_handoff_coordinator.py::{test_new_message_during_adopted_successor_stays_same_run,test_control_after_adoption_fences_recovery_output,test_shutdown_during_recovery_fails_each_accepted_message_once}` | keep | 各自保护成功 successor admission 与三种 control/shutdown 收口，不由并发测试重复断言。 | M3 focused recovery command |

## Plan

| Step | Status | Evidence |
|---|---|---|
| R1 — establish baseline and lock ownership | done | `progress.md` R1 |
| R2 — implement owner-level atomic closure and regression | done | `progress.md` R2 |
| R3 — validate, integrate, and clean isolated runtime/worktree | done | `progress.md` R3 |
