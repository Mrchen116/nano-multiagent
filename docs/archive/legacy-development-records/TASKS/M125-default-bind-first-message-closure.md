# M125 默认绑定后首条消息链路收口

## Milestone Goal
把 IM/Gateway 的默认用户路径真正收口成可用产品：用户按当前文档启动 IM 与 Gateway、完成绑定后，必须能在 Web IM 默认入口进入实际会话并成功发送至少一条真实消息；若发送条件不满足，UI 必须给出明确、可执行的产品级反馈，而不是停留在空壳/半连通状态。

## Roadpoints

### RP1. Baseline and gap confirmation
- Read `LOGBOOK.md` and `COMMENTING_GUIDE.md` before touching code.
- Read M120 acceptance retest artifact and confirm the blocking gap.
- Run `pytest -q` baseline in the canonical M125 worktree and record result.

### RP2. Port useful frontend closure work into canonical M125
- Port the validated parts of the previous worker patch into `/Users/czj/Repos/nano-multiagent/.worktrees/M125` only.
- Ensure bootstrap captures both bound-node identity and online/offline send readiness.
- Ensure composer disables send with actionable feedback for both unbound and offline states.
- Keep scope inside `src/IM/**`, `tests/acceptance/**`, `tests/im_service/**`, and milestone records.

### RP3. Validate real and automated acceptance evidence
- [x] Run targeted frontend/backend tests plus `pytest -q` after the port.
- [x] Execute the documented real path: start IM, start Gateway, bind through the real browser path, open Web IM, and verify first-message send or actionable blocker UI.
- [x] Save browser evidence under `ACCEPTANCE/` and record rollback point and outcomes in `PROGRESS/`.

## Final checkpoint
- [x] Canonical worktree verified and used as sole source of truth.
- [x] Remaining stale `4173` assertion updated to documented `8011` default path.
- [x] Targeted frontend regressions passed.
- [x] Targeted Python regressions passed.
- [x] Full `pytest -q` suite passed.
- [x] Real browser evidence captured for IM-hosted `/chat` -> default conversation -> first successful message.
- [x] `PROGRESS/` updated with evidence paths and final readiness.
