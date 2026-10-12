# M1 implementation and validation evidence

- Implemented and validated tree: `7e22a91d28fff92d07980845cfbabb9821cd1316` (2026-10-12).
- Executed base / effective base: `origin/main` at `9e4b0a8a0`; merged before final validation. Its incremental changes concern feat-573 design workflow documentation, not this runtime, so the approved design gate remains valid. The implementation also depends on the TypeScript migration PR #329.
- Actual product evidence and verdict are maintained in the independent acceptance report; static findings and corrected-delta reconciliation are maintained in the independent code review / verification reports. This file records commands and cross-process observations without replacing those gates.

## Implementation

Work embeds the original published DSH 0.2.1-alpha.1 trajectory modules in a separate React 18 iframe. The official session controller owns history and live projection. IM holds credentials and authorizes exact Work sessions; a separate transient Node connection carries read-only requests. No native events are stored in IM. Reading an existing cold session does not activate an Agent. Chat images require original media access; successful workspace reads require trusted source and native session-reference proof.

## Automated validation

| Command / scope | Result |
|---|---|
| `pnpm build`, `pnpm typecheck` | Passed for all runtime packages and native viewer |
| `pnpm test` | 58 files / 162 tests passed on final implementation |
| Frontend `npm run test` | 87 files / 825 tests passed; subsequent bookmark/empty-state changes additionally verified through real browser acceptance and Work's 17-test regression |
| Frontend `npm run build` | Passed, including final bookmark implementation |
| Frontend `npm audit --audit-level=critical` | 0 vulnerabilities |
| `pytest -m 'not e2e' -q` | 54 passed / 31 deselected, including browser-only dependency boundary |
| `ruff check .`, `ruff format --check .` | Passed |

Local command logs are under `output/feat-583-runtime/` (`final-build.log`, `final-typecheck.log`, `final-backend-tests.log`, `frontend-tests.log`, `frontend-build.log`, `final-python-tests.log`). Logs, runtime configuration, databases and screenshot caches are not committed.

The native cold-session test first failed at the absent `trajectory.prepare` method before implementation. Its green version restarts the actual locked DSH runtime, reads persisted history and image provenance, confirms no new Agent creation, rejects unauthorized access and detects a subsequent business activation. Additional tests cover provenance-write failure followed by ordinary input, bounded native streams, IM source-media permissions, ticket reuse and viewer transport cancellation without cancelling a task.

## Full-stack observation

The isolated service uses actual IM → Node → DSH processes and the configured local LLM proxy, with a real global Agent, native child, reads, images, failed tool, compaction and cancelled task. It is not a replacement renderer or preconstructed trajectory fixture.

On 2026-10-12 at 05:39:17 UTC an actual browser-protocol observer stopped pulling its native follow stream for 6.1 seconds. Its next pull failed with `trajectory_slow_consumer`, while ordinary chat input `a2e70b96c3a14895a4f214ab91c41ca2` completed through the same live Node and reply `2e2e9a14cf274b6086855e3eb3555782` was delivered. Node remained online. Reproduction and raw result: `output/feat-583-runtime/slow-reader.mjs` and `slow-reader-result.json`.

The service is intentionally retained at `http://127.0.0.1:51650` for the user's requested review, using isolated runtime `.dsh-runtime/feat-583-review`. It can be stopped with the worktree's E2E cleanup after the user finishes. This is local product acceptance, not production deployment.

## Remaining acceptance boundary

Independent acceptance closed the empty-state and reading-bookmark defects, but the required timeline range drag/zoom is still inconclusive. Both reviewer and root attempted actual CUA input; the browser rejected iframe dragging with `Cannot safely inspect fractional iframe input coordinates`. The alternate native Codex application surface is explicitly unavailable to computer use and was not bypassed. No implementation defect is inferred from that tool limitation, and no successful drag is claimed.

The unit remains active. Canonical delta merge, archive and Ready PR are withheld until this specific real interaction can be verified. All other completed evidence is retained; further work should target only this missing interaction unless new findings invalidate it. The earlier probe servers on ports 43831 and 52183 have been stopped; the final IM/Node service on 51650 remains running.

### Subsequent native interaction evidence

Re-reading R3.4 confirmed that the requirement is native interval focus and zoom, not one prescribed pointer gesture. The official timeline also supports clicking blank track space to select a centered interval. On the unchanged final service, this real click selected 43.75%–56.25% of the child timeline and visibly dimmed records outside it; Escape removed the range and restored all records. Read-only DOM inspection confirmed selection width `12.5%` before Escape and no selection afterward. Actual screenshots are `output/feat-583-acceptance/range-click-before.jpg` and `range-reset-after.jpg`.

Zoom remains unverified: coordinate-based and fresh accessibility-target scrolling moved the outer page, with native timeline domain width unchanged at `100%`. Current computer-use inventory reports the Mac locked and Chrome unavailable. The user has been asked to unlock the Mac and keep Chrome open so a supported real input path can finish this bounded check. No source change, synthetic event injection or relaxation of the product requirement was made.

Screenshot capture boundary: full-page capture reset the iframe layout and could capture a loading state in this IAB. The two evidence images above and `deliverable-native-trajectory.jpg` were replaced using the current viewport screenshot API and visually verified after saving; stale loading-state images are not used as passing evidence.
