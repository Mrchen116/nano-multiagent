# M1 implementation evidence

Base: `5665af409426f22eec86d03d68e6ffbb1c935d00`. Implementation is isolated in the attached `unit/feat-630` worktree; production and dirty main are untouched.

## Regression ownership

- Keep PA Inbox, controls, personal admission, correction/revalidation and single-thread coverage. Update existing fixtures to supply distinct relay identities for distinct inputs, acknowledge the new small scope request, and retain original behavioral assertions.
- Extend channels coverage at its real WebSocket seam. `realtime-window.test.ts` owns the newly concurrent transport window, lost/late ACK isolation and reserved control slots; existing lifecycle/redaction tests remain.
- Work HTTP cursor/parts and its client recovery have separate protocol owners. Dedicated tests cover bounded bodies, machine-only auth, atomic projection, restart, hashes, quotas and cancellation.
- Ordinary Web sending owns IndexedDB attempt persistence and normal Composer interaction. Existing optimistic history/echo tests are retained; assertions wait for the durable completion boundary.
- Existing private background retry test changes from accepting a mutated key to requiring 409, retaining the frozen relay background assertion.
- Real center reconnect/window recovery is protected at the existing process E2E seam. The manual `tests/e2e/reliability/im-load.mts` load harness creates only isolated test identities and exercises real HTTP/WS and SQLite admission.

## Meaningful RED

- Channels: lost business ACK blocked the subsequent receipt; window overflow had no bounded rejection. Both new real-WS cases failed before implementation (2026-10-21 20:46 CST).
- PA: unavailable runtime caused input to be missing from Inbox; duplicate receipt obligation API was absent. Both cases failed before implementation (20:48 CST, after required workspace package build).
- Work: valid offline runtime token GET cursor returned 401 instead of 200 (20:45 CST).
- Web: three response-loss API cases and four ordinary Composer identity/reload cases failed before implementation; implementation slice reports are retained in task history.

## Integrated validation

Executed implementation base: `5665af409426f22eec86d03d68e6ffbb1c935d00`; effective main base: `536d5a29fd449de5da7ef8c29030c1868d91567a` (fetched again after final integration; unchanged). Product source frozen at `a1b5b15e2982382539e8e5498d1cdd033cbda00e`. Later changes contain fixtures, evidence, corrected delta/canonical docs and archive paths only.

| Check | Actual command / result |
|---|---|
| Build | `pnpm build` — passed, source a1b, installer fingerprint `fc088dbfb592` |
| Typecheck | `pnpm typecheck` — all packages passed |
| Complete backend | `pnpm exec vitest run --maxWorkers=2` — 114 files, 531/531 passed, 247.02 s |
| Complete Web | `npm test -- --maxWorkers=2` — 102 files, 949/949 passed, 75.62 s |
| Web dependency gate | `npm audit --audit-level=critical` — passed (no critical advisories) |
| Python helpers/architecture | `.venv/bin/python -m pytest -m 'not e2e' -q` — 62 passed, 31 E2E deselected |
| Python lint/format | `ruff check .`; `ruff format --check .` — passed, 83 files formatted |
| Browser bundle | `npm exec vite build` — passed; the built frontend was used for final a1b reviewer follow-up |
| Documentation | `python scripts/docs_check.py` with repository venv — passed after canonical merge (260 maintained sources/67 routes) and after archive (249 maintained sources/67 routes); unit/feat-630 archive gate passed |

The earlier fully parallel local suites contended for this development machine and exposed timing-only failures; bounded two-worker runs above are the complete suites, not a selected subset. No product fix was made for unrelated timing. This evidence is reusable; only new source changes, actual failures or invalidated scope justify further complete runs.

## Real acceptance and repairs

See [technical-acceptance.md](../technical-acceptance.md) for V1–V8 data, public-boundary process fixtures, event hashes, original/recovery native identities, six actual input redeliveries, capacity profile and failed attempts. See [acceptance.md](../acceptance.md) for independent real desktop/narrow-browser journeys and [verification.md](../verification.md) / [code-review.md](../code-review.md) for independent gates.

Confirmed independent/runtime findings were fixed by the main agent: control self-wait and PA source classification; complete-part finalization after crash; permission business ID vs transport request ID; revoked receipt drain; external permission consumer; immediate publication confirmation; three-Agent fairness and Retry-After; cold interrupted wake and partial-consumption boundary; status-only committed publication recovery; bounded relay indexes and constant pending-upload commit lookup. Native DSH/public exports, authorization/read barriers and truthful interrupted-turn state are preserved.

`536d5a29` main integration affects the consumed-background wake and PA review naming only. Related PA tests and complete suites pass; the independent reviewer retained unchanged chat journeys and rechecked the final a1b stack. Design Gate 2 remains applicable: original requirements, architecture, single M1 and UI non-expansion are unchanged. Corrected delta is independently aligned before canonical merge.

Final V7 passed: 12,000/12,000/12,000 messages, no loss/duplicates, save/receive p99 254.07/253.86 ms and increments 198.56/200.15 ms. M1 is complete: independent Round 7 code review and full verification passed with no open findings, corrected delta is aligned, and independent product acceptance passed all 13 scenarios. The complete unit is ready for archive and PR delivery.

Final sync retained `536d5a29fd449de5da7ef8c29030c1868d91567a`; no newer main delta exists. The gate `validated_at` remains product source `a1b5b15e2982382539e8e5498d1cdd033cbda00e`. Subsequent report, aggregate evidence, canonical-spec merge and archive-relative-link changes do not alter that product tree, so all gates are retained; the PR records the final archive commit as `effective_through`.

No production services were modified. Owned isolated stacks, providers, proxies and browsers have been stopped. Selected raw logs, native counts, hashes and browser evidence are preserved outside Git under `/Users/czj/.codex/visualizations/2026/10/21/01a15e22-3769-76d3-9b08-c4f2c1f8b84b/feat-630-evidence/`; the portable load aggregate is committed in `evidence/load-summary.json`. Runtime/config/database artifacts are not committed.
