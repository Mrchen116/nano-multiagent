# M1 realtime runtime live-browser report

## Environment

- Production frontend build served by the worktree Web IM at `http://127.0.0.1:64722`.
- Real foreground Gateway node: `wt-refactor-460-M1-80957`.
- Browser: headed Chromium through the repository Playwright workflow; desktop `1440x900` and mobile `375x812`.
- Test account credentials and JWT values are intentionally omitted.

## User-visible results

| Scenario | Result | Evidence |
|---|---|---|
| Current chat receives a real Gateway/LLM response without refresh | PASS | `01-chat-initial.png`, `02-live-agent-reply.png`; reply `R460 LIVE OK` appeared with process/timing metadata. |
| Expired access token + still-valid refresh token | PASS | A correctly signed expired access JWT was installed while retaining the real refresh token. Reload produced one successful `/im/v1/auth/refresh`, concurrent authenticated requests retried successfully, the session stayed on the same chat, and a new live response `R460 REFRESH RECOVERY OK` arrived through the reconnected user stream. See `03-expired-token-recovery.png`. |
| Gateway status disconnect/reconnect | PASS | Stopping the real Gateway changed all four Agents to `offline`; restarting the same worktree Gateway returned them to `online` without reloading. See `04-status-offline.png` and `05-status-recovered.png`. |
| Mobile viewport | PASS | The recovered conversation and both real replies render at `375x812`; see `06-mobile-recovered-chat.png`. |
| Unopened conversation notification | PASS | A Plato reply arrived while default-agent was open. The sidebar preview updated and the application toast showed sender, body and `View message`; see `07-background-chat-toast.png`. |
| Browser transport interruption/recovery | PASS | Chromium network was toggled offline then online. A subsequent real Plato turn completed and appeared live; see `08-browser-network-recovered.png`. |
| Logout/account switch isolation | PASS | The same tab logged out user A and logged in a newly registered user B. The stale A conversation URL was not rendered (`oldTextCount=0`), the sidebar said `No conversations`, and the header showed user B; see `09-account-switch-isolated.png`. |

The desktop notification subscriber was also exercised by the committed integration regression with preference enabled, `document.visibilityState=hidden`, granted permission, a real subscriber callback sequence, and the `Notification` constructor assertion. The headed automation environment kept both Chromium pages `visible`, so no OS-level notification screenshot is claimed here; the application notification path above is the true-browser notification evidence.

## Runtime/transport observations

- At the final steady state, `lsof` showed exactly one established Chromium connection to Web IM plus the independent Gateway connection. The IM log showed user-stream connections as non-overlapping open/close generations across reload, token rotation, network recovery and account switch; it never showed two active browser user streams.
- During the expired-token run, the expected initial 401 responses were followed by one refresh 200 and successful authenticated retries. No token is copied into this report.
- The account-switch run produced an expected 404 for user B requesting user A's stale route before the canonical empty sidebar rendered. This is the authorization boundary working as intended, not cache leakage.

## Known unrelated environment issue

One initial messages request transiently returned 500, then its retry returned 200. The IM traceback points to concurrent use of the shared SQLite connection (`sqlite3.OperationalError: not an error`) in `repositories.py`; this is outside the frontend runtime milestone and is tracked separately as [#191](https://github.com/Mrchen116/nano-multiagent/issues/191).

