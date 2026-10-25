# M1 implementation and validation

## Delivered implementation

`6a78d0253` restores the ordinary shared host and existing PA binding/epoch homes, retains public DSH root handles, scopes cancellation and durable recovery to the product Agent, and removes the split-home migration/control host. Web/iOS, center authorization, persistent lifecycle intent and Task suspension remain unchanged. `5ca2abaa4` installs ordinary-host delivery consumers with their original idempotency identities. `60514ca8f` permits retry of pre-disposal cleanup deadlines while preserving unknown scope-cleanup outcomes. `2c88684b4` retains management startup for an empty node while its center is unreachable; populated nodes reconcile lifecycle intent before executing. `f10168318` keeps the last execution host identity in disabled reports after a Node restart, so the center can validate the original stop request while local proof still checks prior cleanup and the new shared host. `6769c89cb` collects persisted cold root/descendant stop history through read-only public queries, closing Work projection gaps after offline disable without activating an Agent.

No DSH dependency version or runtime source was patched. No production service, data migration, deployment or package release was performed.

## Local checks

Evidence root: `/Users/czj/.codex/reports/bugfix-660/` (local runtime logs and synthetic records, not committed).

| Check | Result | Evidence |
|---|---|---|
| Build and package candidate | pass; candidate not published | `shared-build.log` plus scoped DSH/Node rebuilds after fixes |
| Final TypeScript typecheck | pass at `2c88684b4` | `shared-typecheck-final.log` |
| Packaged iOS interactive runtime check | pass; no native UI diff | `shared-ios-runtime.log` |
| Backend suite, 2 workers | 732/733 pass; remaining empty-node CLI startup regression fixed and verified below | `shared-backend-two-workers.log` |
| Cold stopped Work projection | cold root is never activated; final cancellation and historical events reach Work | `shared-cold-stop-red.log`, `shared-cold-stop-green.log` (16 pass) |
| Offline stop/reconnect lifecycle | 2 new cases reproduce the stale-process rejection before the fix; all 12 Node/IM lifecycle cases pass after it | `shared-reconnect-red.log`, `shared-reconnect-green.log` |
| Real empty-node CLI start/status/crash-recovery/stop/PID ownership | pass after final 3-line empty-node startup fix | `shared-empty-node.log`, 1 pass |
| Shared A/B owner cleanup | real child/grandchild/continuable subtree + Bash/PTY; A stops, B continues; same PID; fresh A enable passes | `shared-native-isolation.log` and full backend suite |
| Retry + unknown cleanup | slow native job settles after first deadline; second retry confirms without restart; scope cleanup error remains unconfirmed | `shared-retry.log`, 2 pass |
| Cold reads/fork/selective durable recovery | pass in complete backend suite | `trajectory.test.ts`, `history.test.ts`, `agent-disable-native.test.ts` |
| Frontend suite | 108 files / 1,028 tests pass | `shared-frontend.log` |
| Frontend production build | tsc + Vite pass; used by independent Web reviewer | `shared-web-build.log` |
| Frontend critical dependency audit | pass at configured critical threshold | `shared-audit.log` |
| Python architecture/tooling | 70 pass / 32 e2e deselected | `shared-python.log` |
| Ruff checks and format | pass | `shared-ruff.log` |
| Documentation integrity | pass before archive; repeated on final archived tree | `shared-docs.log` |

The initial default-concurrency backend attempt overloaded the local machine (load average 40) and was stopped after timing failures. The complete 2-worker run is the accepted full-suite evidence. Its only deterministic failure exposed the empty-node startup case. All other 732 results are retained because the final change executes solely when the configured Agent list is empty; the affected real CLI case was rerun successfully. The later report-identity fix affects only Node stop publication and was verified by all 12 Node/IM lifecycle tests plus independent product revalidation. The final cold-history delta was checked by all 16 affected native/PA stop and cold-trajectory tests. Remote CI runs the final integrated tree normally.

## Real Context evidence

At `60514ca8f`, daily P used the actual `codexOAuth:gpt-6.1-sol` high model in root `a943501a-fbf1-4434-960f-53d6b082e7bd`. A synthetic human message supplied a code; P used Inbox and send_message to reply. Normal lifecycle requests disabled revision2 and enabled revision3 with the same shared host identity. A new message asked for the previous code without supplying it; P correctly replied with that code.

The actual upstream Responses payload before and after resume preserves identical system content and the same 24 selected tool schemas. Original human source metadata, Inbox result, sent receipt and the new human question appear in their original order. This verifies create/dispose/resume history and preset delivery through the changed owner path, with actual model consumption and product delivery. Raw requests remain local; report and precise locators: `context-evidence.md`, `context-wire-summary.json`, `context-lifecycle.json`, `context-messages.json` in the evidence root.

This probe does not claim all-model/all-tool coverage. Native tests cover child/Job/PTY ownership and public fork seed preservation; independent Web acceptance covers lifecycle/Task/offline management journeys. The final empty-node-only startup change cannot affect this populated daily environment.

## Linux CI terminal shutdown correction

The first remote run, `40208579485` at `6b1245bc7`, passed the frontend and 735/736 backend tests. The same-host native A/B stop case failed on Linux: cancelling an in-flight PTY send Job could race an exited foreground group; native terminal interruption retained the resulting `ESRCH` as a transport failure, so later scope cleanup correctly refused to confirm the stop.

`2f9765d3f` closes each owned terminal through the public terminal service before cancelling and awaiting remaining owned Jobs. It retains the existing narrow `ESRCH` handling for explicit foreground signalling and propagates terminal close failures. It does not suppress cleanup errors, change DSH source, or touch B's terminals. The rebuilt DSH package and all seven native disable tests pass locally (`shared-pty-order-build.log`, `shared-pty-order.log`); Linux confirmation belongs to the subsequent remote CI run. The prior Web journeys, model Context evidence and unrelated checks retain their scope; this patch changes only the shutdown ordering exercised by the native Bash/PTY test.
