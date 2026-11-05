# M1-session Code Review

## Snapshot and result

- Independent reviewer: `/root/review_stable_session`; did not author the implementation.
- Mode: `full`.
- Reviewed source: `0287088bec1b646ac397b20ae3365d5e6962388e → 8ece8ad0ec7b38c97183e4cbd11a93c0bc201984`.
- Whole-unit context: `90efdd3dc → 8ece8ad0ec7b38c97183e4cbd11a93c0bc201984`.
- Checkout: `unit/bugfix-709`, source HEAD matched the frozen commit; clean at review start.
- Scope: all changed source/test files, incident, approved design, unit delta and merged canonical auth contract; actual server, Web and native callers inspected.
- Result: **pass; no confirmed or plausible actionable defects**.

```json
[]
```

## Review evidence

1. **Stable credential and rolling expiry.** `identity.ts:406-437` verifies a two-part credential against a live session, the browser marker and stored SHA-256; renewal changes only `browser_session` and `expires_at`. It neither replaces the secret nor consumes its hash. `identity-routes.ts:34-43,132-136` renews Cookie Max-Age and omits the credential from response JSON. `identity.ts:119,400-404` retains 30-day session and 15-minute access lifetimes. Repeated and simultaneous requests preserve the same Cookie; lost Set-Cookie cannot invalidate its old value.
2. **Legacy JWT upgrade and native isolation.** `identity.ts:295-335,409-413` retains signature, token type, JWT expiry, current session/epoch and current hash validation while allowing repeat browser upgrade. The unchanged `sid` and `jti` generate the same opaque value. Only the browser upgrade path bypasses the new browser-mode restriction; the regular JSON refresh and logout decoders reject upgraded sessions. An already consumed legacy JWT is still rejected by its hash. Stable two-part values cannot pass the JWT decoder. `identity-routes.ts:45-56` still separates Cookie-only browser requests from explicit native JSON credentials. Native `Session.swift:125-160` remains compatible with the unchanged pair contract.
3. **Revocation and transport security.** `identity.ts:288-335,445-461` applies the existing durable session revocation, epoch and expiry gates to both access and browser credentials, and shares the transaction that deletes outstanding WebSocket tickets. `identity-routes.ts:138-147` calls the real Gateway closeSession path and clears the browser Cookie. Existing origin checks at `identity-routes.ts:82-100`, host-only/HttpOnly/SameSite/Secure attributes at `34-35`, and server no-store/CORS assembly at `server.ts:123-141` remain intact. Web `auth-api.ts:24-30,58-64` uses the browser marker and included Cookie; `auth-session.ts:50-78` preserves retry versus signed-out handling.
4. **Persistence and schema upgrade.** `schema.sql:318-328` defines the default-zero browser marker for new databases. `db.ts:31-38` upgrades old tables within the existing migration transaction, checks the column before adding it, and persists a migration marker. Existing rows retain their credential hashes and default unupgraded mode. All repository `auth_sessions` inserts were checked; the affected positional fixture was changed to explicit columns, while existing explicit-column inserts remain valid.
5. **Test ownership and evidence.** `identity.test.ts` remains the existing authentication regression owner. The former browser replay-rejection assertion is replaced with stable-cookie replay success, two focused cases cover loss-safe migration, restart/rolling expiry, tampering, expiry, consumed-token rejection and epoch revocation, and native/revocation tests are retained. No parallel milestone-named test suite was added. The direct HTTP seam exercises the actual registered routes rather than reproducing their logic.
6. **Architecture and Context.** All production changes stay inside IM identity/transport/database responsibilities. No PA/Channels/Node/DSH dependency changes, second session store, alternate revocation mechanism or model-visible Context changes were introduced. Agent Context Review is not applicable. No frontend visual changes or prototype contract apply.

## Validation reused

The main agent ran these commands with Node `24.22.1`; this reviewer directly read the logs and verified the frozen source snapshot. No full-suite rerun was launched by the reviewer.

| Command / baseline | Result | Locator |
|---|---|---|
| `pnpm exec vitest run apps/im-server/tests/identity.test.ts`, pre-fix source with regression tests | 2 failed / 11 passed; repeated browser Cookie and discarded legacy-upgrade response returned 401 | `/tmp/im-stable-red.log` |
| Same command, final source | 13 passed, 5.00 seconds | `/tmp/im-stable-identity.log` |
| `pnpm build`, final source | Passed | `/tmp/im-stable-build.log` |
| `pnpm typecheck`, final source | Passed | `/tmp/im-stable-typecheck.log` |

These are implementation/HTTP evidence, not real browser product acceptance. The independent product reviewer owns the isolated Chrome lost-response, `/login` recovery, restart and explicit logout journeys. Root/other suites were still running when this review was written and are not claimed here. No production requests, source changes, commits or reviewer-owned services were made.
