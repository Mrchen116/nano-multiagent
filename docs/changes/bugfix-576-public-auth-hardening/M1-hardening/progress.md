# M1 hardening implementation and validation

## Implementation

- Company admission is retained around effects and rechecked after explicitly yielding for bcrypt/control results. Per-Agent lock waits use the same ownership boundary; duplicate create rechecks its profile under that resource lock.
- Two active password computations, persistent source/pair/one-second target budgets, and a separate SQLite limit connection. Cancellation does not free a running thread's capacity.
- Explicit browser session mode uses HttpOnly Cookie refresh and memory access, with Origin checks. Native JSON clients remain supported. Headers use the configured public origin.
- Browser Web Locks serialize Cookie mutations; versioned single-flight and credential-free login/logout notices coordinate tabs. Old localStorage credentials are discarded.

## Test strategy and evidence

- `test_auth_routes.py` and `test_auth_service.py`: keep native API, hash and durable rotation coverage.
- `test_browser_auth.py`: new HTTP transport risk owner, no prior Cookie coverage. Initial baseline run failed 2/2 on refresh in JSON and accepted foreign Origin; fixed run passes. Added actual served HTML/header coverage.
- `test_auth_concurrency.py`: new HTTP concurrency/abuse risk owner, controlled password worker blocking rather than absolute latency. Covers reads during real worker occupation, cancelled request retaining capacity, source failure isolation, fixed target expiry.
- `test_company_control_waits.py`: actual ASGI HTTP + WS control frames, same-Agent concurrent update, unrelated read, and logout during wait; final profile and response status prove revocation/recheck.
- `test_fork_edge_cleanups.py`: extend existing cleanup owner for revoked success/error/cancel outcomes; tests empty-scaffold removal under admission and original history preservation.
- `test_app_factory.py`: rewrite old any-loopback CORS expectation for explicit origins and credentials. Existing image header checks caught duplicate nosniff and are retained.
- Frontend auth-store/session/gate: rewrite-merge persistence expectations to memory/Cookie recovery, revision and network failure semantics; other fixtures remove obsolete refresh fields. Full frontend run: 85 files / 798 tests passed; one additional parameterized stale-401 case also passes in focused session run. Build passes.
- Initial broadened IM run: 526 passed / 3 failed; explicit CORS expectation, duplicate header, and concurrent-create recheck corrected. Relevant 31-test regression passes; fork/control/browser focused suite 11 passed. Full final suite recorded below when frozen.

## Evidence limits

No production mutations, real user accounts or user Chrome profile. Strict one-time refresh may require re-login if rotation commits and its response is lost; the temporary network retry guarantee does not create a token replay grace window. Product browser/TLS acceptance and independent static review remain separate gates.
