# M4 independent real-stack evidence

## Environment and scope

- Date: 2026-07-15 (Asia/Shanghai).
- Entry: isolated production IM frontend on `http://127.0.0.1:55401`, node `wt-feat-464-M4-99679`, real Gateway process and the configured live Feishu application.
- Browser: Playwright Chromium, desktop 1440×1000 and mobile 375×812; all mutations used the authenticated production HTTP routes.
- Provider calls used the official tenant-token, bot-info and long-connection endpoint flow. The mapping was checked against the [tenant access token documentation](https://open.feishu.cn/document/server-docs/authentication-management/access-token/tenant_access_token_internal?lang=zh-CN) and [generic error-code documentation](https://open.feishu.cn/document/server-docs/api-call-guide/generic-error-code?lang=zh-CN).

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
| Mobile layout and production provider registry | [connected 375×812](output/playwright/r6-mobile-connected-375x812.png), [provider picker](output/playwright/r6-mobile-provider-picker.png) | PASS; actions remained reachable and the production picker exposed exactly one Feishu descriptor. |

The online journey recorded five lifecycle `PATCH` responses at HTTP 200 and zero browser console errors; see [machine-readable result](output/playwright/r6-browser-result.json). The intentionally offline journeys recorded 2–3 console errors while Gateway-dependent capability requests were unavailable; the lifecycle mutations themselves returned HTTP 200 and converged after restart. Cache/stop failure and same-revision retry are re-proved by the permanent real store + HTTP/WS tests `test_cache_commit_failure_is_visible_and_same_revision_can_retry` and `test_connected_reconnect_and_failed_removal_retry_use_same_manifest_revision`; the existing product-state screenshot remains at `M2-offline-lifecycle/evidence/output/playwright/channel-deleting-failed-retry.png`.

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
