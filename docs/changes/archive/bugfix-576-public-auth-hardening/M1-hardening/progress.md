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

## Final gates and retained evidence

- Final runtime source: `c2d36427d`. Full Python: **4119 passed / 29 warnings / 92.65s**; full frontend: **804 passed / 85 files / 23.17s**. Build, Ruff check/format, docs-check and critical dependency audit pass. Dependencies were not changed.
- R1 findings were accepted and fixed in one batch: public HTTP/WS fork rejection now preserves waiting-period user content; timeout and copy-error also preserve it. Registration UTF-8 bounds now have local and server-projected field feedback. Existing tests were extended at their risk owners.
- Product R2 (`dccb875fc`) pass, static closure and corrected-delta (`035e48f2e`) pass with zero findings / CRITICAL / WARNING. R1 product evidence retains validity for unaffected Cookie, multi-tab, membership, network, attachment and WSS journeys; R2 directly verifies password field feedback and valid ASCII/Unicode boundaries.
- `validated_at`: product/static final `c2d36427d`; unaffected full-review evidence `9b9478ebe`. `executed_base` and final `effective_base`: `d357729af`. Final HTTPS fetch confirms origin/main has not advanced. No merge/rebase source delta exists.
- Remaining changes are mechanical canonical merge, complete unit archive and this delivery record; no source behavior changed after final validation. All gates are retained through the final PR head (recorded as `effective_through` in the PR body). Archive path correction changes only the relative current-spec link.
- Temporary acceptance scripts were kept outside the lint tree. Screenshots and sanitized CI logs are retained locally outside the worktree; credentials, databases, certificates and runtime files are not committed. The isolated server is stopped before delivery.
- Existing `infra/logging.py` is unchanged from main. The first isolated server exposed its pre-existing Uvicorn access-formatter incompatibility; targeted UI revalidation used `--no-access-log`, preserving authentication and browser behavior. No logging redesign is included.

## CI environment correction

- Initial GitHub CI passed both Python suites and Python checks, but the Node-environment Vite proxy test failed during shared setup: its Node version does not expose `navigator`. Browser tests passed (803 assertions).
- Scope the jsdom Web Locks substitute to `window.navigator` only when `window` exists. No runtime code changed; product, code-review and verification conclusions are retained.
- Explicitly disabling Node's global navigator locally passes the Node proxy test and all 11 browser auth-session tests (12 total); the same environment is used for the complete frontend rerun.
- Complete frontend rerun with `NODE_OPTIONS=--no-experimental-global-navigator`: **85 files / 804 passed / 15.90s**.
