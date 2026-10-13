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

- Backend build/typecheck passed; full runtime regressions: 59 files / 167 tests passed (75.13 s).
- Frontend production build passed; 87 files / 826 tests passed; npm audit: 0 vulnerabilities.
- Python helper/architecture: 54 passed, 31 E2E deselected; Ruff check/format passed.
- Docs integrity: 235 maintained sources, 64 routes passed before archive.
- iOS CI-equivalent `build.sh test` and `build.sh archive` passed using Xcode.app and iOS 26.4 iPhone 17 Pro simulator; logs `/tmp/nano-ios-bugfix585-test.log` and `/tmp/nano-ios-bugfix585-archive.log`. No iOS source change; this is simulator/build evidence, not physical-device acceptance.

## Test ownership

Kept existing Relay delivery/ACK/revocation tests and extended their diagnostic observations. New `apps/im-server/tests/node-connection.test.ts` owns the previously untested cross-boundary IM guard chain. Existing frontend loading-shell test owns live server-cache refresh versus editing lifecycle. Real LLM/browser validation is separate product evidence, not substituted by these tests.

## Isolated product stack

Built this worktree before starting its `.runtime-585` via design runbook. Initial URL `http://127.0.0.1:49936`, Node PID 27259, identity `wt-.runtime-585-27082`, owner `u_2sajrkra`; runtime secrets and full logs remain excluded in `.runtime-585/`. Reviewer must verify current PID/version before use. This is not production deployment or physical device acceptance.

## Product review repair

Round 1 found a real shutdown ordering defect: @fastify/websocket's preClose closed clients before the Gateway could send 1001/server_shutdown. A new real createServer/app.close + public Relay regression failed on the reviewed snapshot, then passed after moving the Gateway hook before plugin registration (commit 684122882). Focused IM/Channels: 13 passed; build/typecheck passed. This follows the existing approved shutdown contract and changes no design or scope.

The first real Agent reply failed because the local DeepSeek proxy returned Zstandard bytes without Content-Encoding under text/event-stream; direct synthetic HTTP probe reproduced it independently of Node/IM and decompressed to complete SSE with end_turn. Reviewer selected the already configured codexOAuth:gpt-5.6-sol through the isolated Agent UI and observed a real reply. No proxy, production config or upstream code was changed.

The temporary reviewer admin was promoted in the disposable test DB for the real suspension API journey. This fixture does not alter product authorization code. Existing IM queued-message recovery was observed and attributed to unchanged persistence/re-registration code; the unit does not add offline submission or transport replay.

Final backend suite on 684122882: 59 files / 168 tests passed (24.05 s), log `/tmp/nano-bugfix585-final-backend.log`. Frontend, Python/Ruff and iOS evidence above is retained: the only subsequent product change is IM shutdown hook ordering, and the new integration regression plus backend suite exercise its affected lifecycle.

## Resume presence gap

The second real IM restart left the untouched Nodes tab offline while API and Chat were online. Nodes had no edits. The user-stream recovery fetches state before the WebSocket resume; node/Agent status events are transient, so a registration in that gap is not replayed. A deterministic real WebSocket test registers the Node after browser connect but before resume; it failed with no status frame (684122882). The scoped design addition sends current owner node/Agent presence at resume completion using the same events; it adds no polling, queue or chat cursor semantics.

Gate2 R5 approved the resume addition (0 critical / warning). Commit 8e453ab96 adds the current owner snapshot after resume. Focused IM/Channels: 14 passed, including the formerly failing timing window and owner isolation; build/typecheck passed. No frontend change was needed, so the prior frontend/draft and iOS checks remain applicable.

Final backend regression on 8e453ab96: 59 files / 169 tests passed (24.62 s), log `/tmp/nano-bugfix585-resume-backend.log`. Final main fetch remains 6bb37a069 (already ancestor); there is no main increment to integrate. Code review/corrected delta target the latest implementation; design R5 includes resume recovery. Canonical merge and archive will only change documentation paths/text, preserving those source/test conclusions.

## Final product result and cleanup

Independent Round 3 passed R1–R4 on 8e453ab96, including the untouched stale Nodes tab recovering without reload, another IM restart, a real new Agent answer, and 78 seconds without reconnection after real account suspension. Reports retain both discovered defects and their closure evidence.

Owned runtime cleanup completed with e2e-down. Reviewer IM restart had left the original process-birth marker; cleanup first refused safely. Caller verified PID35709 command, birth, cwd and listener against the exact isolated stack, refreshed that test marker and reran cleanup. IM35709, Node27259 and DSH27322 are gone; port49936 is closed. Reviewer tabs and caller preflight tab were closed. No production service was changed.

## Delivery documentation checks

Reviewed deltas were merged into canonical gateway lifecycle/relay and IM node specs; the relay index now declares 22 requirements. Final docs-check passes after that count update. The whole unit is archived without dropping history. Because desktop branch naming is codex/bugfix-585 and CI's archive selector only matches unit/, the archive checker was explicitly run with `--head-ref unit/bugfix-585` to validate this exact unit; PASS (unique archive, no active/retired duplicate). Final product tree remains 8e453ab96; the delivery commit adds only canonical/documentation/archive changes.
