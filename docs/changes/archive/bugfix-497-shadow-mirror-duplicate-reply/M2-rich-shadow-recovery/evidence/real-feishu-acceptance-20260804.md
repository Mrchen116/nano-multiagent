# Real Feishu Acceptance — 2026-08-04

## Boundary

- The journeys used the isolated `unit/bugfix-497` Gateway, IM database, runtime
  ports, node identity and workspace.
- A dedicated test Feishu app was connected only to that isolated IM runtime. Its
  credentials are local, ignored configuration; no credential, runtime database,
  log or screenshot is included in this change.
- The Web IM observations used the isolated Vite client as the `nano` test user.
  Terminal Web IM assertions were repeated after a page reload.

## Results

| Journey | Feishu nonce | User message id | Agent message id | IM / history result |
|---|---|---|---|---|
| Online | `BUGFIX497-ONLINE-20260804-1720` | `13dbb0c7c10b4f12880c341e560af0ae` | `99a7c423d381438fbf19778eeaf63668` | Exactly one rich Agent bubble: 1 thinking item, 2,637 total tokens and 1,011 ms; reload preserved the same single bubble. |
| IM fully offline, then Gateway restart | `BUGFIX497-OFFLINE-20260804-1721` | `531b473d377d43e5b67c1ba7091bb798` | `ccda088bc8734fe199dec2967787163d` | Feishu received the terminal reply while IM was down. Gateway was then restarted while IM remained down; restoring IM reconciled exactly one rich Agent bubble with 1 thinking item, 2,765 total tokens and 1,004 ms. Reload preserved it. |
| IM disconnect during run | `BUGFIX497-MIDRUN-DISCONNECT-20260804-1730` | `d824e3d3fbb64fd9b5a82d61595051d0` | `bb5a17a60b2b45aab8abe08edd95e09c` | IM was stopped four seconds after submission while Gateway stayed online. The 26,031 ms Feishu run completed, then IM recovery showed one rich Agent bubble with 1 thinking item and 5,907 total tokens. Reload did not add a plain duplicate. |

For each nonce, the IM history API contained exactly one matching User row and one
matching Agent row. The Agent row was terminal `completed`, retained the rich
thinking/token/elapsed projection above, and used its single durable external-shadow
message identity through live delivery or recovery.

## Tool coverage boundary

The isolated `plato` test agent had an explicit empty tool allowlist during these
real-channel runs. Under the current Gateway capability contract that means no tool
was available, so these rows cannot honestly claim a real structured tool event. One
model response rendered tool-call-looking text as ordinary final content; it was not
counted as a tool invocation. The permanent Gateway/IM regressions recorded in
`../progress.md` cover ordered structured thinking/tool snapshots and their recovery;
these three original rows are preliminary channel/restart/reload evidence only.

## Closure runs

The test profile was then explicitly granted its isolated `read` and `bash` tools. This
was a runtime-only test setting and was not saved to source configuration.

| Journey | Feishu nonce(s) | Result |
|---|---|---|
| Fully offline + Gateway restart with a structured tool | `BUGFIX497-OFFLINE-TOOL-RESTART-20260804-1811` | IM was stopped before the Feishu message was sent. Feishu showed the terminal reply before IM was restored; the reply confirms the command's start/end markers. Gateway was stopped and restarted while IM was still unavailable, then the same IM database and port were restored. Recovery created exactly one Agent row `f0a5b160bd50493a9470182b91f67b25` for User row `3e64d95cd5004e8788d0a67b6c477b1f`: terminal `completed`, one thinking item, one completed `bash` tool at `seq = 1` (12,170 ms, exit 0 and both markers), 3,504 total tokens, 15,026 ms and kernel id `msg_18d0de01d4dbee81`. The Web IM page opened directly to that terminal rich bubble (no running replay); its Process disclosure showed the same tool output and a page reload retained the one bubble. |
| Partial live row, IM outage and same-row recovery | `BUGFIX497-MIDRUN-PARTIAL-PASS-20260804-1808` | Before outage, the open Web IM page contained running Agent row `098717ccdade45a68f1b90cb069ebfc2`. IM was stopped while Gateway stayed online; Feishu received the terminal reply before IM was restored. After restoration on the same port/database, the already-open page automatically converged that **same** row to one rich terminal bubble: 1 thinking item, 16,126 total tokens, 27,037 ms, `completed`, kernel id `msg_daba1196ad809592`. A fresh login/page reload retained the same one bubble. |

The history API was used only to cross-check exact ids and persisted fields. Actual
pass/fail observations came from the real Feishu chat and the Web IM page.

## Cleanup

After the observations, the isolated Gateway, IM and Vite processes were stopped. Their
generated runtime configuration and credentials were removed; generated databases, logs
and workspace data were moved out of the worktree to the local Trash for recoverable
cleanup. No test-channel configuration remains in the worktree.
