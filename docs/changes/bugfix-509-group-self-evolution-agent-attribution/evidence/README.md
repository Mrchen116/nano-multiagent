# Real-stack acceptance evidence

## Environment

- Date: 2026-08-06
- Isolated branch/worktree: `unit/bugfix-509`, `.worktrees/unit-bugfix-509`
- IM: `http://127.0.0.1:64502`
- Web IM: `http://127.0.0.1:64635`
- Gateway node: `wt-unit-bugfix-509-51646`
- Agents: `e2e` (`E2E Agent`) and `e2e-peer` (`E2E Peer Agent`)

The stack used repository E2E configuration with isolated ports, data and Gateway workspaces. The command runner reaped detached children after shell exit, so the same startup commands were hosted in named tmux sessions for the duration of the browser journey.

## Observations

### Group attribution and locale switching

Conversation `435a96ea4e7f4b2ea96d735d2d33d1ab` included both Agents. A real mention-picker turn asked both to invoke `skill_view`; each completed and emitted one self-evolution review notice.

- Persisted notice 1: source `e2e-peer`, display-name snapshot `E2E Peer Agent`, targets `skills`.
- Persisted notice 2: source `e2e`, display-name snapshot `E2E Agent`, targets `skills`.
- Chinese rendered rows: `· E2E Peer Agent · 后台自进化：技能已更新` and `· E2E Agent · 后台自进化：技能已更新`.
- English rendered rows: `· E2E Peer Agent · Background self-evolution: skills updated` and `· E2E Agent · Background self-evolution: skills updated`.
- Reload/re-entry loaded the same two records from history. SQLite notice count was 2 before and after reload.

Screenshots:

- [`group-zh-desktop.png`](group-zh-desktop.png)
- [`group-en-desktop.png`](group-en-desktop.png)
- [`group-en-mobile.png`](group-en-mobile.png)

### Direct conversation, combined targets and fork

Conversation `067b49d96d5842abad5fe14a796741b8` produced one skills-only notice and one canonical `skills,memory` notice. Direct conversation `995e4427df0044a193545a109d115ded` was forked from the second reply and preserved the earlier notice sidecar and source snapshot. Its Chinese row was `· 后台自进化：技能已更新`, without the redundant Agent name.

Screenshot:

- [`direct-fork-zh-mobile.png`](direct-fork-zh-mobile.png)

### Browser diagnostics

- Viewports checked: desktop and 390×844 mobile.
- Browser console: 0 errors, 0 warnings; only the React development-mode informational message.
- Observed API requests returned successful 2xx responses.
- Message rows stayed on the existing low-emphasis centered system style with no avatar, sender header or message actions.

Protocol-level duplicate replay and ACK-loss recovery are covered by the focused Gateway/IM tests; the real browser reload additionally verified that history projection does not duplicate stored notices.
