# refactor-460-M4 Evidence

## Real browser journeys

- `m4-baseline-natural-empty-{live,reload}.png`: before R1, a direct Web run with one real bash tool, one thinking segment, and a natural empty final left a process-only Agent row both live and after reload.
- `m4-r1-natural-empty-removed-{live,reload}.png`: after R1, the same controlled real-LLM journey leaves only the user row; REST history also contains no empty Agent message.
- `m4-r4-toast-unread-fixed.png`: two clean Chromium contexts use the same account. Browser B completes `M4_FINAL_NOTIFY_0713` in `plato`; browser A stays in `default-agent` and shows exactly one app toast, `plato` moved to the first row with the new preview/time, and local unread `1`.
- A third clean Chromium context logged in with cursor `0`: `/im/v1/sync` established cursor `79`; existing `M4_FINAL_NOTIFY_0713` appeared only as history preview, with `toastCount=0` and no local unread overlay.

## Automated gates

- Focused Gateway lifecycle/FK repository: 45 tests passed; real stack verified natural empty tombstone online/reload.
- Focused IM replay/repository/EventBridge: 100 tests passed.
- Focused browser runtime/mapper/workspace: 76 tests passed; production build passed.
- Focused accumulator/toast/notifier/workspace: 60 tests passed; production build passed.
- Full frontend: 64 files / 584 tests passed; `npm run build` passed.
- `ruff check src tests`: passed.
- `pytest -m "not e2e"`: 3512 passed, 1 skipped, 23 deselected.
- `e2e-critical`: 16 non-heartbeat paths passed in 356.45s. The heartbeat path is an existing strict xfail for #126; the default global 90s timeout preempted its own 180s wait, so it was rerun with `--timeout=210` and correctly reported `1 xfailed` in 187.74s.

## Contract notes

- No user-stream wire schema was expanded. Canonical `message.completed` owns the Agent reminder identity (`message_id` + `conversation_id`); direct-Web `relay.completed` is a receipt.
- The app toast and desktop notifier share the same canonical lifecycle accumulator. Only minimum pending sender identity is stored in user-scoped `sessionStorage` to bridge reload between created/completed.
- Same-account server read state remains authoritative. A tab that observed a live unseen completion overlays a minimum unread `1` only at render time; opening that conversation clears the tab-local feedback.
