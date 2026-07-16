# M4 independent real-stack evidence

## Environment and scope

- Date: 2026-07-15 (Asia/Shanghai).
- Entry: isolated production IM frontend on `http://127.0.0.1:55401`, node `wt-feat-464-M4-99679`, real Gateway process and the configured live Feishu application.
- Browser: Playwright Chromium, desktop 1440×1000 and mobile 375×812; all mutations used the authenticated production HTTP routes.
- Provider calls used the official tenant-token, bot-info and long-connection endpoint flow. The mapping was checked against the [tenant access token documentation](https://open.feishu.cn/document/server-docs/authentication-management/access-token/tenant_access_token_internal?lang=zh-CN) and [generic error-code documentation](https://open.feishu.cn/document/server-docs/api-call-guide/generic-error-code?lang=zh-CN).

The final sign-off supplement was run from production baseline `6bc146c3cd4abc2c626589bb8ceb78f27e23c05f` on a second isolated IM/Gateway stack. It used the production SQLite stores, authenticated HTTP routes, Gateway reconcile path, built frontend, and Playwright Chromium. A gated acceptance fixture failed exactly the first Gateway cache commit containing a removal; the channel was disabled and the isolated config contained no enabled external provider, so this journey made no Feishu request and started no Feishu worker.

## Live Feishu findings closed during R6

The first real run exposed three gaps that mocks had not represented. Each now has a permanent regression:

1. Live `/bot/v3/info` returns the bot object at top level (`bot`), while the previous parser only accepted the nested mock shape. The parser now accepts both; `test_preflight_accepts_official_top_level_bot_identity_shape` guards it.
2. The live tenant-token endpoint returned code `10014` with message `app secret invalid` for an invalid secret. Message-aware normalization now reports `feishu_invalid_credentials`; other `10014` authorization-disabled responses remain `feishu_app_disabled`. No secret is copied into status or logs.
3. A cached provider startup failure previously aborted Gateway before it could reconnect to IM and report the failure. Cached desired state is now retained, the failure is reported, and manual reconnect can recover; `test_cached_provider_failure_allows_gateway_connect_and_manual_recovery` guards this path.

## Browser journeys

| Journey | Evidence | Result |
|---|---|---|
| Real configured application reaches Connected | [connected](output/playwright/r6-real-connected.png) | PASS; runtime status synchronized and diagnostics reached `complete`. |
| Connected → Disable → Disabled | [disabled](output/playwright/r6-real-disabled.png) | PASS in 2.357s, under the 90s bound; the old Feishu worker PID was gone. |
| Re-enable without entering a secret | [re-enabled](output/playwright/r6-real-reenabled.png) | PASS in 2.822s and returned to the live connection. |
| Replace with a genuinely invalid secret | [provider failure](output/playwright/r6-real-invalid-credential.png) | PASS; card displayed “Feishu rejected the App ID or App Secret”, not a generic runtime crash. |
| Restore the valid secret | [credential recovered](output/playwright/r6-real-credential-recovered.png) | PASS; no Gateway restart or config edit was required. |
| Offline create and update | [created pending](output/playwright/r6-offline-created.png), [updated pending](output/playwright/r6-offline-updated.png) | PASS; desired state remained “Waiting for node” and applied automatically after restart. |
| Offline disable and restart | [disabling](output/playwright/r6-offline-disabling.png), [restart disabled](output/playwright/r6-restart-disabled.png) | PASS; UI did not claim Disabled until the node applied it. |
| Offline re-enable and restart | [re-enable pending](output/playwright/r6-offline-reenabled-pending.png), [converged](output/playwright/r6-offline-changes-converged.png) | PASS; no secret re-entry and final state Connected. |
| Delete and preserve an external shadow conversation | [empty after applied removal](output/playwright/r6-removal-applied.png), [history after removal](output/playwright/r6-history-after-removal.png) | PASS; `DELETE ...?channel_revision=4` returned 200, channel resources became empty, and the existing message remained readable through the production conversation/messages APIs and UI. |
| Current-HEAD cache commit failure → reload → same-revision retry | [failed](output/playwright/r6-current-head-cache-failure.png), [failed after reload](output/playwright/r6-current-head-cache-failure-reloaded.png), [empty after retry](output/playwright/r6-current-head-cache-retry-applied.png) | PASS; the UI retained “Deletion incomplete”, the deterministic cache error and `Retry apply` across reload, never projected empty early, then `POST .../actions/retry` returned 200 and converged to empty. |
| Mobile layout and production provider registry | [connected 375×812](output/playwright/r6-mobile-connected-375x812.png), [provider picker](output/playwright/r6-mobile-provider-picker.png) | PASS; actions remained reachable and the production picker exposed exactly one Feishu descriptor. |

The online journey recorded five lifecycle `PATCH` responses at HTTP 200 and zero browser console errors; see [machine-readable result](output/playwright/r6-browser-result.json). The intentionally offline journeys recorded 2–3 console errors while Gateway-dependent capability requests were unavailable; the lifecycle mutations themselves returned HTTP 200 and converged after restart.

The current-HEAD failure journey is independently machine-readable in [browser failure](output/playwright/r6-current-head-cache-failure-browser.json), [browser retry](output/playwright/r6-current-head-cache-retry-browser.json), and [store/runtime assertions](output/runtime/r6-current-head-cache-failure.json). Before retry, IM returned one failed removal at deletion manifest revision 3, manifest head was `3/2` desired/applied, and the Gateway cache remained revision 2 with the old channel. The browser reload still showed the failed removal and no empty state. The real retry endpoint replayed revision 3 (HTTP 200); afterward the durable receipt was applied, IM head was `3/3`, Gateway cache was revision 3 with zero channels and one removal receipt, and the browser showed the empty state. No new manifest revision was allocated.

## Security and lifecycle audit

- The live key, encrypted manifest cache, and derived Gateway config were all mode `0600` before cleanup.
- Exact configured-secret scan: zero hits in worktree text/evidence/logs, zero hits in SQLite strings, and zero access-key/ticket/token patterns in durable evidence.
- Wrong-owner Gateway authentication, atomic cross-owner bind, credential re-entry, partial start, registry failure, non-cooperative backpressure, bounded restart, metadata replay, activation retry, and the injected second-provider path all have permanent regressions.
- Full deletion left no Feishu worker process. `scripts/e2e-down.sh` then removed IM/Gateway PID files, JWT/config copies, credential key and manifest cache; no worktree service or worker process remained.

## Final gates

- `ruff check src tests` → PASS.
- Frontend `npm run test -- --run` → 67 files / 620 tests passed.
- Frontend `npm run build` → PASS, 444 modules transformed.
- Backend `pytest -q -m "not e2e"` → 3447 passed, 1 skipped, 20 deselected.
- Gateway handler-focused suite → 70 passed; every test file opening `/im/ws/gateway` → 71 passed.
- `git diff --check`, test naming/size contract, secret scan, file-mode audit, screenshot inspection and process cleanup → PASS.
- Current-HEAD cache-failure supplement: focused real-store/HTTP/WS regressions 2 passed; test naming/size contract 2 passed; fixture Ruff check PASS; frontend production build PASS (444 modules); secret scan, screenshot inspection, and isolated-process cleanup PASS.
