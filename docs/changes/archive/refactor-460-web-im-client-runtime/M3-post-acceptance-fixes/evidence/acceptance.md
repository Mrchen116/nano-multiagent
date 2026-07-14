# refactor-460-M3 acceptance evidence

Date: 2026-07-13

## Real-stack user journeys

The acceptance stack used the milestone worktree's real IM and Gateway processes, the configured `kimiCoding:K2.6` provider through the local proxy, the public REST/WebSocket surfaces, and a headed Playwright browser.

### Direct Web IM `NO_REPLY`

- A direct conversation produced a real Gateway terminal event `message.discarded` with reason `no_reply_token` and the original provisional message id.
- While the run was active, the browser rendered the provisional Agent bubble. The live tombstone then removed it without navigation.
- REST history after completion contained one user row, zero Agent rows, and zero literal `NO_REPLY` rows.
- Reloading the browser preserved the same result: only user messages remained. See [no-reply-after-reload.png](no-reply-after-reload.png).
- The focused repository test additionally proves repeated discard is idempotent and publishes the tombstone callback exactly once; wire/replay tests prove nullable tombstone FK retains the payload id while an ordinary non-null FK still overrides stale payload data.

### Online non-current Agent reply

- The browser remained on conversation A while a real reply completed in conversation B.
- The live toast contained sender `default-agent`, preview `ONLINE_M3_MARKER`, and a `View message` link to conversation B.
- The sidebar independently showed B first with the same preview and `1 unread`; the current conversation did not change and did not receive a duplicate toast. See [background-agent-toast.png](background-agent-toast.png).

### Agent detail Open chat

- From `/settings/agents/default-agent`, `Open chat` navigated to a newly created `/chat/<conversation_id>` route.
- The destination was an empty direct Agent conversation titled `default-agent`, with the expected Agent metadata and composer.

## Automated gates

| Gate | Result |
|---|---|
| Agent detail focused Vitest | 27 passed |
| IM event bridge, user stream, Gateway lifecycle, external-visible and heartbeat delivery | 66 passed |
| Full frontend Vitest | 62 files, 581 passed |
| Frontend production build | passed |
| `ruff check src tests` | passed |
| `pytest -q -m "not e2e"` | 3505 passed, 1 skipped, 23 deselected |
| `e2e-critical.sh -m "not slow" -q` | 15 passed, 2 deselected |

The first unfiltered critical-path run completed seven paths before the existing slow heartbeat wait reached pytest's global timeout. The supported `not slow` profile was then run to completion; all non-time-driven critical paths passed.
