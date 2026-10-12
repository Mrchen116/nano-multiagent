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

Native child identity/Work projection, remaining Task Graphs and native schedule fault-boundary checks, and full channel control/media combinations remain open. Built-in commands and complete history/configuration capabilities will be integrated with M3. M3–M5 and final independent gates remain open.

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

The remaining scope above still prevents declaring M2 complete.
- Real offline acceptance passed after stopping only the isolated IM process: Feishu replied with the new nonce and the preceding Session's code while projection remained pending. Restarting the same IM database drained the pending projection to zero. The reply used the configured native runtime-footer card. Evidence: ignored `.dsh-runtime/feishu-offline-evidence.json`.

## Hosted channels and delivery boundaries

- Node reuses the enrolled `channel-credentials-v1.pem` identity. Envelopes use the existing X25519/HKDF/AES-GCM wire format and authenticated owner/node/Agent/channel/revision scope. One-time Node↔Python encryption interoperability passed in both directions; secret material remains in ignored fixtures.
- `ManagedChannels` persists encrypted full desired state and FIFO control receipts. It validates all envelopes before any listener switch, ignores stale manifests, avoids restarting unchanged successful generations, retries failed starts on replay, preserves removal receipts, and starts cached listeners while IM is unavailable. Status incarnation/sequence and provider metadata are generation-scoped.
- Real HTTP acceptance against the isolated IM passed bootstrap, enabled→disabled (observed stopped), disabled→enabled (observed connected), and reconnect dispatch. The same enrolled device key was retained. Evidence: ignored `.dsh-runtime/channel-control-evidence.json`.
- Real native Feishu approval was clicked and the allowed tool ran. A later stale click returned a closed card without another execution. Group field values and reasons are hidden; only the bound owner and actual card identity can answer, with first-wins behavior. Evidence: ignored `.dsh-runtime/feishu-approval-evidence.json` and `feishu-approval-completed.png`.
- External completion enters the IM outbox only after platform confirmation. A lost platform result records `unknown`, projects an explicit failure notice, and never automatically resends after restart. Node delivery history preserves that uncertainty. Focused tests observe the pending-send boundary and cold replay.
- Internal single-thread group drafts are retained in Process when a newer accepted input has not been incorporated. The next native turn receives a system note that the prior draft was not sent. External groups and MENTION-only background do not acquire a new wake rule. The regression first failed by publishing Thursday before the correction, then passed by retaining Thursday as a draft and publishing Friday.
- Feishu input enrichment uses platform sender/chat names and group history including pure images. Data-URL Markdown images upload as platform resources; remote links and code examples remain inert. Real media acceptance is in progress.
- Latest validation: `pnpm build` passed; `pnpm test` passed 16 files / 35 tests. Two registration/heartbeat tests were made event-driven after full-suite CPU scheduling exposed fixed-sleep assumptions; transport code was unchanged for those test fixes.

## Native child and proactive accounting increment

- The actual global Agent started native continuable child `5642440e-8250-4018-bacb-0d2ffac2f50e`, then used native `send_message(agent_id, message)` to continue that same child. The second child turn retained the first code and added the second. Work shows the real parent/child IDs and child drafts; only the parent's explicit final send reached the public conversation. Evidence: ignored `child-smoke-evidence.json`.
- The global product sender preserves the native internal-child branch. Descendant Work projection reads public native catalog/session observations, releases observation leases, and deduplicates replay by stable journal identity; it does not resume an inactive child to inspect it.
- Native schedule crash test holds a public flush participant while native persistence writes the input, then kills the actual runtime before ScheduleService commits its receipt. Cold recovery with Cron disabled finds the original accepted message/schedule identity although native receipt history is still empty. Admission evidence and timer receipts are deliberately distinct; the native schedule engine remains unchanged.
- Actual Task Graph creation, child addition and dependency updates passed through the native tool and IM. Graph `tg_e4f96afa` revision 3 contains two todo children and the A→B dependency. This fixture required the existing IM `task_graph` allowlist. Initial permission denial led to stopping the test Agent; no tracked files were changed by that test. Full effective-tool selection remains M3 work.
- That test also exposed cross-Agent configuration blocking. Configuration apply is now serialized per Agent, while writes to the one node configuration file stay globally serialized. A regression first observed B blocked by A's active turn, then passed with B applied while A still waits.
- Real Feishu group image readback passed: an unmentioned background message and pure image did not wake a reply; the later mention correctly identified red on the left and blue on the right and recalled the background code. Platform reply `om_x100b63baf43100acddc1e31d9be3084` was read back. Evidence: ignored `feishu-group-image-evidence.json`.
- Validation: full suite 16 files / 36 tests passed before the two new regressions; focused Cron 2 tests and configuration 3 tests passed after them; build passed.
- First Heartbeat before any human input produced `FIRST_HEARTBEAT_OK_581` in owner conversation `c_5qijjti6`; the fixture was disabled afterward. The initial probe queried Agent ID as a synthetic user ID; correcting that query confirmed the already-delivered messages. Evidence: ignored `heartbeat-first-evidence.json`.
- Outgoing data-URL image passed the real Feishu SDK upload/send/readback path; the platform message contains an `img_` resource and no original data URL. Evidence: ignored `feishu-output-image-evidence.json`.
