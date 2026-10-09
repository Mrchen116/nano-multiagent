# M2 implementation evidence

Status: in progress. These checks do not complete M2 or authorize deployment.

## Working paths

- Global mode now uses one native DSH Session per product Agent, a node-owned durable Inbox, and explicit `send_message` delivery. Work events are replayable from native Session history into the existing IM journal protocol.
- Real-model isolated IM checks passed for a direct-chat project code, recall from a second group conversation, and an uploaded image (red square and blue circle). The image check confirmed durable Inbox read and image preparation receipts.
- Task Graphs is a separately disposable runtime Feature using the existing IM command contract. Its data stays in IM.
- Each Agent's Cron owner has isolated native JSON/domain storage and a native ScheduleService. A disabled owner has no ScheduleService timer. Disabling and re-enabling preserves tasks.
- Native schedule inputs retain their original message ID in the node projection. They are never submitted again, and automatic single-thread output returns to the bound conversation without inventing a relay receipt.
- A real model created a 3-second native reminder using `schedule_create`, acknowledged it, and then delivered `NATIVE_CRON_DELIVERY_OK` in the same conversation. Native schedule ID: `schedule-78d7cae0-c763-4120-ba70-3e582cae3231`; final IM message: `26718252cb8b4325a3f42df73825e63e`.

## Runtime and recovery checks

- Two-Agent native-profile test verifies schedule tools on/off/on, A/B isolation, stopped A versus firing B, disabled cold restart, one catch-up receipt after enabling, and retained native history.
- The same test verifies Task Graphs tool and prompt removal/reinstatement without duplicate registration, and updating a persona/Feature configuration while retaining the existing Session binding.
- A native storage-domain nested injection in alpha.1 cannot resolve isolated storage at its inner mount. Nano assembles the public DomainFacility with both native storage dependencies in one Cordis fiber. The native storage and schedule implementations are unchanged.
- Configuration operation receipts persist before file mutation, survive a runtime failure after persistence, reconcile once after restart, and reject stale fingerprints or reused operation IDs. Canonical JSON is checked against the existing Python fingerprint, including Unicode and the `{}` heartbeat clearing rule.

## Remaining M2 scope

IM configuration and management end-to-end integration is being validated. Heartbeat policy and silent delivery, complete group revalidation, native child identity/Work projection, Feishu and channel configuration, manual schedule runs and execution history attribution, and the remaining M2 scenarios are not yet accepted. M3–M5 and final independent gates remain open.

## Additional product checks

- IM HTTP creation and full configuration update passed for `e2e-config-1791548562`; Task Graphs/Cron off→on advanced profile revisions 1→2→3 and persisted the node configuration. The initial legacy fixture correctly rejected a stale mirror fingerprint; a missing `node_id` in the new config-read response was fixed before the successful run.
- Heartbeat real-model check passed for `e2e-heartbeat-1791549003` in `c_7o1wah6n`: the proactive reply recalled `HARBOR_925` from the prior user turn. Three native heartbeat input records were observed; the silent phase created zero IM messages. Cadence, multiple task rhythms, active hours, disabled subscription, and uncertain admission recovery have focused tests.

## Group and external transport increment

- Full suite before this increment: 11 files / 26 tests passed. The reconnect test now waits for the observable second registration within its deadline instead of assuming a 65 ms scheduler window.
- Single-thread group input parks in durable node storage without creating a DSH Session. A mention or reply transfers the buffer into native `inject` inputs before the actual `followup`. Stable input IDs survive redelivery; group text is held until the completed reply can be checked for silent tokens.
- Real HTTP/LLM group check passed: background `QUARTZ_217` was stored with zero Session bindings, the later mention recalled it, and `NO_REPLY` produced no final IM message. Evidence: ignored `.dsh-runtime/group-smoke-evidence.json`.
- Official Feishu Node SDK 1.74.0 receives text/post/images and sends native Markdown. The node persists external inputs and separate platform/IM delivery facts. IM projection is asynchronous and replayable; external-trigger and internal-shadow-trigger outputs retain different destinations.
- Dedicated `--feishu` test profile and its single-listener lock were used. The verified `e2e-feishu-testagent` user sent a nonce to the dedicated test Bot. DSH replied through the real platform; the exact returned platform message ID was read back with the matching nonce. IM received one user anchor and one output, and all 13 projected frames were acknowledged. Evidence: ignored `.dsh-runtime/feishu-smoke-evidence.json`.
- Focused transport tests cover duplicate external admission, confirmed-send replay, internal-only replies, and reconnect projection using the same Session through its shadow alias. Rich post parsing preserves text/image order and distinguishes the Bot's open ID from @all.

Remaining: hosted channel configuration/reconciliation, full Feishu media/control/approval and real offline acceptance, native child identity/Work projection, remaining Task Graphs and native schedule fault-boundary checks, then M3–M5 and independent final gates. These are not yet a completed M2.
- Real offline acceptance passed after stopping only the isolated IM process: Feishu replied with the new nonce and the preceding Session's code while projection remained pending. Restarting the same IM database drained the pending projection to zero. The reply used the configured native runtime-footer card. Evidence: ignored `.dsh-runtime/feishu-offline-evidence.json`.
