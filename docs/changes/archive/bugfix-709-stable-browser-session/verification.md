# Verification Report: bugfix-709

> Validation snapshot: `0287088bec1b646ac397b20ae3365d5e6962388e → 8ece8ad0ec7b38c97183e4cbd11a93c0bc201984`

## Summary

| Dimension | Result |
|---|---|
| Completeness | M1 implementation and worker exit criteria covered; separate product review is not asserted by this report |
| Correctness | All changed authentication scenarios aligned; no blocking implementation issue |
| Coherence | Approved design followed; IM-only responsibility boundary preserved |
| Full implementation verification | **pass — 0 CRITICAL / 0 WARNING / 0 SUGGESTION** |
| Corrected delta | **aligned** |
| requires_full_verification | `false` |

Independent verifier: `/root/review_stable_session`. The same independent reviewer also completed [full code review](M1-session/code-review.md); the implementation author did not perform this verification. HEAD matched the frozen snapshot and the checkout was clean before review. Source/test/config/design were not changed. Reports are handed back uncommitted for the main agent to integrate.

## Completeness

- M1-session is the only milestone. All changed files are within its declared identity, route, schema, persistence, test and auth-contract scope (`design.md:23-27`). Worker exit criteria have implementation and passing regression evidence.
- All 13 scenarios in the modified auth Requirement have an existing or changed implementation path. The three added scenarios and the changed browser/native semantics are mapped below; unchanged registration, invalid-login, reserved-name, personal-space and login-history protections remain present in `identity.ts:219-281` and `identity.test.ts:85-203,263-326`.
- Product-review exit criteria in `design.md:25` remain a separate gate. This report verifies their implementation seams and does not claim the real Chrome lost-response, restart, `/login → /chat`, or logout journey was performed by this verifier.
- Prototype / reference must-match: N/A; no visual changes or prototype in the approved design.
- Agent Context: N/A; human authentication state only, no model-visible Context/lifecycle change.

## Correctness

| Requirement / Scenario | Implementation evidence | Regression / validation evidence | Status |
|---|---|---|---|
| Browser response loss, retry and same-origin concurrent renewal | `identity.ts:406-437`; `identity-routes.ts:34-43,132-136` retain the verified secret and extend expiry | `identity.test.ts:177-188,205-237` discards an upgrade response, retries the same Cookie and concurrently renews the stable Cookie; final 13/13 pass | covered |
| Thirty-day rolling session/Cookie expiry; short access unchanged | `identity.ts:119,400-404,430-437`; `identity-routes.ts:34-43` | `identity.test.ts:113-135,179,228-240` checks TTL, day-later extension and expiry rejection | covered |
| Legacy browser JWT safely and repeatedly upgrades | `identity.ts:295-335,406-435` checks signed unexpired JWT/current hash and preserves `sid/jti` | `identity.test.ts:214-225,247-260` retries original JWT, verifies same Cookie and rejects consumed legacy JWT | covered |
| Native one-time rotation, restart durability and mode isolation | `identity.ts:332,363-398,448-450`; `identity-routes.ts:45-56,132-136` | `identity.test.ts:85-110,224-225`; existing native rotation retained and upgraded JWT/stable Cookie rejected by JSON refresh | covered |
| Browser logout, account epoch, tampering, expiry and revoked access | `identity.ts:288-335,418-420,445-461,568-576`; `identity-routes.ts:138-147`; `gateway.ts:141-145` | `identity.test.ts:189-202,238-260,302-325`; browser logout, tamper/expiry rejection, epoch invalidation and existing suspension protection | covered |
| Browser Origin, Cookie-only transport, no page-persistent credential, secure headers | `identity-routes.ts:34-56,82-100`; `server.ts:123-141`; Web `auth-api.ts:24-30`; `auth-store.ts:53-55` | `identity.test.ts:138-179` retains Origin, JSON omission, Cookie security and transport separation coverage; unchanged frontend only holds access/user in memory | covered |
| Schema upgrade and repeat opening preserve session state | `db.ts:31-38`; `schema.sql:318-328` default-zero marker and atomic idempotent add-column migration | `identity.test.ts:205-237` starts from old auth table, opens it, creates/upgrades a session, reopens and successfully renews | covered |
| Login-page recovery and retry semantics | Web `auth-session.ts:50-78`; browser API shape unchanged at `identity-routes.ts:43` | Existing recovery code inspected; real-browser product acceptance delegated separately | implementation aligned; product evidence external |

The frozen diff was checked against the server's actual `openDatabase → createIdentity → registerIdentityRoutes` assembly (`server.ts:70-91,173`) and native/Web callers. The change does not rely on an unused test-only path.

## Coherence

| Approved design decision | Followed? | Evidence |
|---|---|---|
| Stable `session_id.secret`, hashed server credential, shared auth_sessions | Yes | `identity.ts:406-437`; no refresh hash update in browser renewal |
| Upgrade keeps original JWT jti/hash; old invalid JWT is not resurrected | Yes | `identity.ts:295-335,409-413`; `identity.test.ts:214-225,247-260` |
| Browser mode marker blocks native consumption | Yes | `identity.ts:332,418-432`; native JSON path retains ordinary decoder |
| Shared expiry/epoch/revocation/ticket mechanism | Yes | `identity.ts:288-335,445-484`; no duplicate revocation state |
| New schema and existing-database startup are both supported | Yes | `schema.sql:323`; `db.ts:34-38`; old-schema/reopen regression |
| Preserve transport security and frontend/native response contracts | Yes | `identity-routes.ts:34-56,82-100`; existing Web/native callers |
| No Agent services/model calls/production writes required | Yes | Reviewer only read code/logs and wrote reports; no runtime created |

### Prototype / Reference Contract

N/A.

## Issues

### CRITICAL

None.

### WARNING

None.

### SUGGESTION

None.

## Corrected Delta Reconciliation

Canonical target: `docs/specs/im/auth-tenancy.md`. The unit delta's complete Requirement was compared with the merged canonical Requirement and matches exactly. Its unchanged scenario text was retained; the same-name merge anchor approved in design-review Round 3 is preserved.

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| Requirement body and program refresh/rotation/concurrency distinction (`specs/im/auth-tenancy.md:5-31`) | `identity.ts:332,363-398,448-454`; transport split at `identity-routes.ts:45-56,136` | `identity.test.ts:85-110,224-225` | aligned |
| Browser storage/recovery and thirty-day renewal (`specs/im/auth-tenancy.md:33-45`) | `identity.ts:119,400-437`; `identity-routes.ts:34-43`; unchanged Web recovery | `identity.test.ts:138-244`; separate Chrome acceptance is not replaced by this evidence | aligned |
| Origin/native boundary (`specs/im/auth-tenancy.md:47-49`) | `identity-routes.ts:45-56,82-100`; browser marker guard in decoder | `identity.test.ts:138-179,224-225` | aligned |
| Added lost-response behavior (`specs/im/auth-tenancy.md:51-53`) | `identity.ts:430-437` only extends expiry | `identity.test.ts:205-237`; red 401 failure then final pass | aligned |
| Added restart/failure boundaries (`specs/im/auth-tenancy.md:55-57`) | Shared persistent `validSession`, epoch and revokeSession paths | `identity.test.ts:226-260,302-325` | aligned |
| Added repeatable legacy upgrade and native isolation (`specs/im/auth-tenancy.md:59-62`) | `identity.ts:295-335,406-435` | `identity.test.ts:214-225,247-260` | aligned |

### Uncovered Observable Behavior

None. The new database marker is an internal migration detail supporting the declared client behavior. No other auth endpoint, client response shape, UI behavior or cross-package contract is changed by the unit diff.

Outcome: **aligned**.

## Validation provenance and limits

Node `24.22.1`; exact commands and readable logs were supplied by the main agent and directly inspected by this verifier:

| Command / snapshot | Result | Locator |
|---|---|---|
| `pnpm exec vitest run apps/im-server/tests/identity.test.ts`, pre-fix source plus new regression assertions | 2 failed / 11 passed, repeated-cookie/lost-upgrade-response 401 | `/tmp/im-stable-red.log` |
| Same command, frozen final source | 13 passed in 5.00 seconds | `/tmp/im-stable-identity.log` |
| `pnpm build`, final source tree | Passed | `/tmp/im-stable-build.log` |
| `pnpm typecheck`, final source tree | Passed | `/tmp/im-stable-typecheck.log` |

Build/test commands ran immediately before the final source commit; the main agent attested the reviewed source was unchanged. No duplicate full-suite execution was started. Broader root/frontend/Python checks were still running when this report was written and are not claimed. No production acceptance or physical iOS acceptance is implied. No reviewer-owned service or worktree needs cleanup.

Implementation verification passed. The independent product-review gate remains separate.

## Retained-evidence addendum — operations documentation

Targeted review at `9d687892fddf53f959e781cd243f6b3e3a61e59a` plus the single uncommitted change to `docs/operations/prod-fleet.md:136`: **pass; findings `[]`**. The corrected key-rotation guidance matches the implementation: `identity.ts:295-335` verifies access/legacy refresh JWT signatures with the signing key, while the upgraded two-part Cookie path at `406-437` verifies the durable session and secret hash without that key. Valid stable sessions can therefore restore a newly signed access token after a key change; forcing logout requires revoking the corresponding session (`445-461`). Gateway runtime identity remains a separate boundary. Comparing the frozen implementation `8ece8ad0e` with this HEAD shows no source or identity-test changes. Original code-review/full-verification evidence and corrected-delta outcome **aligned** remain applicable; no code/test rerun or broader review was needed.

Final validation evidence is now recorded in [M1-session/validation.md](M1-session/validation.md): root backend run retained **1126 passed / 1 failed**, with the sole unchanged Agent capability-inspection timeout passing its isolated rerun in 39.92 seconds; the original full run is not reported green. Frontend passed 112 files / 1059 tests. The independent [product regression](regression.md) passed real Chromium response-loss/retry, page reopen, same-database service restart and logout journeys, resolving the separately pending product evidence in the original report. Those reports are reused here; this addendum performs no new runtime or production action. **0 CRITICAL / 0 WARNING; requires_full_verification: false.**
