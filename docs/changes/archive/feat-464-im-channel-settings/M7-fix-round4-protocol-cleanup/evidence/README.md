# M7 evidence

## Production browser — removal retry response lost → empty

- Runtime: isolated production frontend bundle + IM + Gateway on an ephemeral port.
- Setup: production `ChannelControlStore` staged one failed removal receipt without sending it to Gateway before page load.
- Action: the browser retried through the real IM HTTP endpoint. The route allowed the request and Gateway deletion to complete, then aborted only the browser response to reproduce response loss.
- Convergence: subsequent unmodified channel polling returned no resources. Final DOM counters were `empty=1`, `alerts=0`, `waiting=0`, `retryButtons=0`; Web IM was not shown.
- Console/network: the deliberately aborted retry produced one expected `net::ERR_FAILED`; there were no React render errors, and the following channel GET completed with 200.
- Safety: runtime config contained neither the test App ID nor App Secret after the flow. Trace, request dump, browser profile, credentials, database, logs and PID files were removed; only the sanitized screenshot is retained.

- Screenshot: [m7-removal-response-lost-auto-empty.png](output/playwright/m7-removal-response-lost-auto-empty.png)
- Viewport: 1440×1000
- SHA-256: `3ad0e8443826bbaa80f4e5ba17a430cdc068498ee6d3766e4888357d74f13061`

## Aggregate gates

| Gate | Result |
|---|---|
| Backend `pytest -q -m "not e2e"` | PASS — 3473 passed, 1 skipped, 20 deselected |
| Frontend `npm test` | PASS — 68 files, 627 tests |
| Frontend `npm run build` | PASS |
| Ruff `src tests` | PASS |
| Test naming/size contract | PASS in full backend; largest touched protocol file is 396 lines |
| Secret scan / `git diff --check` / isolated process cleanup | PASS |
