# M1 recovery evidence

## Implementation

IM now separates heartbeat expiry (recoverable 1012) from authority revocation (terminal 1008), persists offline before closing and fences old connection cleanup. Registration clears last_error and publishes node/Agent status. Agent detail keeps unsaved inputs when only presence changes. Channels emits bounded lifecycle diagnostics to the Node's existing gateway.log sink; uncertain business frames are still not replayed.

Test-only IM dependency on the public Channels package supports the real server guard + Relay regression without cross-package source imports. Runtime dependencies remain unchanged.

## Baseline and red reproduction

Base `6bb37a069` (product baseline `649e80311`), dedicated managed worktree `/Users/czj/.codex/worktrees/bugfix-585/nano-multiagent`, branch `codex/bugfix-585`. Main's unrelated dirty work preserved. Managed worktree location/branch follows desktop tooling; all unit implementation stays isolated there.

- `pnpm exec vitest run apps/im-server/tests/node-connection.test.ts`: before fix, heartbeat guard closed with 1008 instead of 1012; account suspension left DB online. Replacement-fencing baseline passed.
- `pnpm exec vitest run packages/channels/tests/web-relay.test.ts`: before fix, 3 diagnostic assertions failed because no lifecycle events were emitted.
- frontend `agent-detail-loading-shell.test.tsx`: before fix, presence transition replaced `Unsaved name` with `Agent Two`.

## Focused green results

- Channels + IM node-connection: 12 tests pass, including real 5-second IM guard, persistent/API offline, owner-scoped node/Agent events, re-registration, new HTTP message delivery, real account suspension, old connection replacement, refusal/ACK timeout/remote close diagnostics and credential redaction. Fault injection changes lastSeen only; cleanup/reconnect paths remain real.
- Frontend loading-shell + status consumer: 13 tests pass, including preservation of edited input across offline/online.

## Broader validation

- Backend build/typecheck passed; full runtime regressions pending completion.
- Frontend production build passed; 87 files / 826 tests passed; npm audit: 0 vulnerabilities.
- Python helper/architecture: 54 passed, 31 E2E deselected; Ruff check/format passed.
- Docs integrity: 235 maintained sources, 64 routes passed before archive.
- iOS CI-equivalent test/archive running separately; no iOS source change.

## Test ownership

Kept existing Relay delivery/ACK/revocation tests and extended their diagnostic observations. New `apps/im-server/tests/node-connection.test.ts` owns the previously untested cross-boundary IM guard chain. Existing frontend loading-shell test owns live server-cache refresh versus editing lifecycle. Real LLM/browser validation is separate product evidence, not substituted by these tests.

## Isolated product stack

Built this worktree before starting its `.runtime-585` via design runbook. Initial URL `http://127.0.0.1:49936`, Node PID 27259, identity `wt-.runtime-585-27082`, owner `u_2sajrkra`; runtime secrets and full logs remain excluded in `.runtime-585/`. Reviewer must verify current PID/version before use. This is not production deployment or physical device acceptance.
