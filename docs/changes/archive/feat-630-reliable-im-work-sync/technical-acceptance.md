# Technical acceptance — feat-630

## Version and boundaries

Implementation base: `5665af409426f22eec86d03d68e6ffbb1c935d00`; integrated main: `536d5a29fd449de5da7ef8c29030c1868d91567a` (bugfix-631 consumed-background wake and bugfix-632 PA review title). Final product source: `a1b5b15e2982382539e8e5498d1cdd033cbda00e`; it includes the recovery corrections at `432400f08` and the final constant pending-upload lookup used by V7. Later fixture/test/document commits do not change the product. Official DSH: `0.2.1-alpha.1`. All services, accounts, node identities and workspaces below are isolated test fixtures. No production change or deployment.

Reproducible drivers: [crash-host](../../../../tests/e2e/reliability/crash-host.mts), [fault proxy](../../../../tests/e2e/reliability/fault-proxy.mts), [model provider](../../../../tests/e2e/reliability/model-provider.mts), [sustained load](../../../../tests/e2e/reliability/im-load.mts). The crash host instantiates production GlobalAgent/Inbox/NodeStore and the declared public DSH client; it freezes at public request/response boundaries with SIGSTOP. The controller reads persisted facts, SIGKILLs only that host and its official DSH process, then starts the normal Node CLI with the unchanged config and data. It never advances a cursor, marks an input consumed, or inserts a successful delivery fact.

## V1: Work outage and complete recovery

Root center `127.0.0.1:54957`, test node `wt-nano-multiagent-37676`, fixture Global Agent `e2e-fixture`, session `c96ca378-d0ab-4339-8e69-cd3975af59bf`, chat `c_52e69qwg`. The HTTP/WS proxy rejected only Work HTTP with 503 from approximately 13:32 to 14:10 UTC on 2026-10-21. Ordinary WS, receipts and publication remained available. Actual DSH tools produced over 9 MB of Work history before a subsequent ordinary query and formal `FIXTURE630_OK` reply. The independent reviewer separately exercised query, stop (133 ms) and a real permission decision during an outage exceeding seven minutes.

A separate real-model baseline used `deepseek:deepseek-v4-flash`: normal UI input in chat `c_hs75ssto` produced one formal `FEAT630_REAL_OK` reply at 13:24 UTC. Thus the integration is also connected to an actual permitted model, beyond deterministic provider behavior.

The deterministic run wrote 48 real workspace files including a 106 KiB argument. A later `write four630.txt` carried 4,194,304 `F` bytes and returned successfully. The raw Work tool_start/tool_end events at journal seq 267/268 were 12,583,671 / 12,583,832 UTF-8 bytes because the native presentation also retains the complete arguments. These are actual tool events below the 16 MiB envelope limit, rather than arbitrary large transport-only fields.

After restoring HTTP, local and remote journals each contained 292 events at the comparison snapshot, with **zero** differences in sequence, event_id, root_agent_id, session_id, turn_id, type, observed_at or complete payload. SHA-256 of ordered, canonical JSON events joined by newline:

`c0389cde56aa06e74a6c92a5202928d9af6fdc6b6b8457a85cad4815b4aa4c3f`

The 4 MiB file SHA-256:

`b14138a3ca83b79cc5b448a07ab8d1dd9e1220652bc0ca1b248c15c12b9e5a68`

The center retained exactly one `FOUR630_DONE` (`fc54610bd6d54589bbc805f70fd836f8`). Dropped publication/receipt ACKs were reconciled; the local publication became confirmed. The independent reviewer opened the actual Work tool entry: the rendered PRE contained all 4,194,304 `F`s (4,194,306 total characters including the existing `+ ` prefix), without truncation. Root data digest snapshot: ignored `.e2e-work-hash.json`; independent visual evidence is listed in acceptance.md.

Fixture corrections are excluded from product claims: the first deterministic BULK run hit its initially undersized model context; reused fixture call IDs were replaced with UUIDs before FOUR630B. An invalid PNG had an incorrect IDAT CRC; the reviewer reran with a real valid screenshot. Neither is counted as a transport regression or as passing evidence. An initial bash side-effect fixture was denied by the configured reviewer; crash effect evidence below uses successfully executed `write`, without changing product authorization policy.

## V2: exact process crash windows

All rows use actual UI sends and the same retained Inbox/DSH/node identity. At each boundary, the host was physically SIGKILLed, with the DSH child also ended. Restart command: `node apps/node/lib/cli.js start --config .gateway-config.yaml`. The final repair uses public lookup/submit and stable recovery notice IDs; user cancellation is not resumed, and consumed work does not get a new wake.

| Window | Durable identity and observation before kill | Observation after normal restart |
|---|---|---|
| Inbox commit, before DSH submit | seq 8, message `c7aba7cf556446ad82ec25c7489a0f20`, relay `10358c6489f4471a96c2dd1f39f7a032`; consumed=0, local wake=7; `inbox-wake:e2e-fixture:8` had not been submitted | Same one input consumed; wake=8; local/center receipt completed and confirmed; formal reply count 2→3; one successful native write call at event 409/turn 8 |
| DSH durable ACK, before local wake commit | seq 9, message `ded53676a3c64866956e8a0bd0562aa8`, relay `eacb9e5ccb9349aead858b81aab8d478`; input `inbox-wake:e2e-fixture:9` returned acceptedSeq=422, turn=9, durable=true; local wake remained 8 | Recovery notice `:9:recovery:422` acceptedSeq=434/turn=10 was **also** killed before local commit. Final restart used stable `:9:recovery:434`, then consumed the same input, wake=9, completed/confirmed receipt, one successful write and formal reply count 3→4 |
| Center applied receipt, before local confirmation | seq 10, message `9d7deff43d8a4838994b13ea26154940`, relay `2a0e1bf665f245ec9c29965b33aa9af6`; actual `node.delivery_receipt` ACK received; center receipt=sent, local confirmed=0, wake=9 | Same input consumed, wake=10; receipt completed/confirmed; one write, formal reply count 4→5 |
| Center publication commit, before local confirmation | seq 11, operation `c96ca378-d0ab-4339-8e69-cd3975af59bf:fixture-39cc2868-915b-4550-9d86-966a9aa64f68`; actual ACK message `976859e774de44c2ad8178562bc65877`; local publication=sending | Formal reply remains one (aggregate count remains 6), write remains one. Status-only recovery confirms the original message and appends its Work publication fact, without resending or starting a model turn. The native interrupted turn/failed execution receipt remains truthful; publication confirmation does not invent a completed model turn |

The initial after-submit run on `2f057ba8e` exposed a real failure: `inbox-wake:e2e-fixture:7` was durable at acceptedSeq=350/turn=6, but a cold DSH resume closed that turn as interrupted; retrying its accepted ID did not wake it. `67ee7b547` added the stable recovery-notice chain; the original failing retained input subsequently completed with one write and one formal reply. `883efa4c3` retained the actual merged wake boundary when only part of a batch was consumed, and recovered committed publications by status; `432400f08` keeps publication recovery independent of input/wake work.

Native export accounting (not just effect-file existence): every original/recovery notification ID above has exactly one `user/message`. For seq 9 the three distinct IDs occur once at events 426, 438 and 450. The successful write callIds for the repaired checkpoints are:

| Case | Native callId | turn / event seq | Successful executions |
|---|---|---|---|
| Original retained after-submit | `fixture-11a97cc9-1845-4a72-83b3-0b13876c2abe` | 7 / 379 | 1 |
| Before-submit-fixed | `fixture-f1010529-f3e7-4f4c-8a3d-4d9dae7353e0` | 8 / 409 | 1 |
| Repeated after-submit recovery | `fixture-bfce60db-2b79-41a2-b75f-e6b32668ec1f` | 11 / 463 | 1 |
| After receipt | `fixture-5bbdf57f-8e4e-48a5-beaa-2976f6ac2eab` | 12 / 493 | 1 |
| After publication | `fixture-defaafb7-d61b-47f6-ace3-7607fa6fbf7d` | 13 / 523 | 1 |

The actual written effect files prove workspace effects exist; native tool/call plus successful tool/result proves they were each executed once. Raw local-only snapshots: `.e2e-crash-evidence.jsonl`, `.e2e-crash-native-counts.json`. They are excluded from Git alongside PIDs, configs and databases; essential facts are retained in this report.

Runtime unavailable with Node still alive was tested separately: SIGSTOP the owned DSH process, then send through the ordinary UI. At 14:38:47 UTC seq 12/message `fa562e0622ee433d82d9da2d1f7ea6b3` was durable, consumed=0, wake=11, center receipt=sent while the runtime remained paused. SIGKILL only the runtime; the existing supervisor restarted it automatically. Same input consumed, one successful write (`fixture-3568302d-396e-4f67-9804-abc128f300f8`, turn 14/event 550), formal reply count 6→7. No user resend or manual database edit.

## V3–V6 and V8 evidence ownership

- Work server tests cover complete 106 KiB chunk reassembly across server restart, duplicate/out-of-order parts, corrupt per-part/full hashes, identity conflicts, stale epoch/credential, quota/TTL, oversized envelope and atomic cursor/projection. Child tool scope/complete arguments/parent projection are covered by the dedicated child-tool test. Client real-HTTP tests cover a 4 MiB UTF-8 event, missing-parts resume after a lost response, all-parts-durable/finalize crash, cursor rollback/gap rejection, >16 MiB pause and abort on shutdown. Actual 12.58 MB tool events plus UI full text above cover the real tool path.
- Native child lineage projection remains covered by `projects durable native child lineage and drafts into Work without a public send` in PA global-agent tests. The real 4 MiB run was a main-session tool, not a fabricated subagent run; the parent-scope regression and native-child contract provide the separate child ownership coverage.
- Real-WS Channels tests cover same-type late ACK isolation, bounded 6+2/256+2 capacity, heartbeat opportunity and three-Agent rotation using real publication scopes. Center replay regression rotates A/B/C through a 32-item window. The independent verifier additionally ran reverse-order same-type ACK and new-node/old-center upgrade-required probes; their results belong to verification.md. Legacy raw protocol compatibility is exercised by existing process E2E, not claimed as a historical Node binary run.
- Real process relay-recovery tests cover 40-message bounded reconnect replay, offline saved-message recovery, terminal receipt monotonicity and small current scope registration independent of historical upload.
- Independent browser acceptance owns Web response loss, reload and attachment identity; edit-after-unknown draft retention; account/conversation isolation; offline recovery; permission and stop; revocation before reconnect; correction before publication; desktop/narrow view and no new internal UI. Details and versions are in acceptance.md.
- Existing PA admission, observer/owner isolation, source revocation, busy Inbox, read commitment, correction and external adapter tests remain part of the full regression run. Neither Work nor this fixture changes approval or disclosure policy.

## V7: sustained load

Hardware: Apple M3, 8 CPUs, 24 GiB RAM, macOS, Node 25.8.2. One real isolated center process, 100 real WS connections and 100 separate durable Inbox databases. Twenty clients continuously replenish batches of 100 Work events (~1.56 MB, including a 106 KiB field); the other 80 nodes receive a combined 20 ordinary messages/s. Work-only HTTP proxy has a fixed 96 KiB/s per-node profile (aggregate maximum 1.875 MiB/s); chat HTTP/WS are unthrottled. This is an explicitly bounded profile, not an unlimited-throughput or total-user-capacity claim.

The unchanged no-Work transport/control code's ten-minute baseline at integrated `2f057ba8e`: 12,000 sent/stored/durably received, zero duplicate deliveries/errors, save p99=55.51 ms, durable receive p99=53.71 ms. Retained for the final profile: the later PA recovery helpers are not instantiated by the load clients; the only center change affects Work-only commit triggers, which are inactive in this baseline. The HTTP/WS wiring and machine are unchanged.

Failed/interrupted attempts are retained as failures:

1. Missing relay replay/publication indexes: even without Work, p99 grew to 8.5 s at five minutes. Added exact node-pending, message-relay and message-event indexes; independent EXPLAIN confirms indexed replay.
2. Unbounded Work-rate attempt ran out of local disk because old owned test data had not been cleaned. Only this task's five temporary load directories were deleted; user/production files were untouched. This run is not passing evidence.
3. Initial fixed-network-profile run: 12,000/12,000/12,000, zero duplicate/error, save p99=736.44 ms and receive p99=736.21 ms; failed the unchanged +500 ms baseline-increment requirement. The cursor trigger rewrote all already-committed hash receipts on each advance. `432400f08` restricts the trigger to committed=0 (at most the one pending event per node); its 1,000-retained-receipts regression proves advancing a cursor does not rewrite history.

Final same-profile ten-minute run is recorded below when complete. Thresholds remain save p99≤1 s, receive p99≤2 s, and each p99 increment≤500 ms, with no message loss/duplicates and bounded windows. No acceptance threshold was relaxed.

### Actual input redelivery (V2 / Scenario 5)

The fault proxy also held outbound `node.delivery_receipt` frames themselves, not merely their returning ACKs. The center therefore actually retransmitted relay `b9705a44063246c7a6cb17b16df79f81` **six times over WS**. The receiver retained only one Inbox row (seq 13, message `ad581d52227342aab4ef6b58a63f3e68`, consumed=1), one native input notification, one successful `write crash630-effect-relay-repeat.txt`, and one formal `CRASH630_DONE` (aggregate replies 7→8, effect files 6→7). After releasing the held receipt frames, center and local receipt became completed/confirmed. Ignored `.e2e-relay-replay.json` records the actual observed relay-frame count; this is distinct from the earlier center-applied/ACK-lost case.

### Bounded lookup refinement

The first committed=0 trigger correction prevented historical writes, but EXPLAIN on the running load database still chose the `(node_id,journal_id,seq)` range and read retained history. `a1b5b15e2` resolves the single pending upload ID by `(node_id,committed=0)` first, then updates that primary key after journal/seq checks. This uses the existing unique pending-node index and does not add another queue or index. The interrupted run after the first correction is not the final V7 result. The final product source is now `a1b5b15e2982382539e8e5498d1cdd033cbda00e`; later test/fixture/evidence changes are non-product.

### Final V7 result: Pass

Product source `a1b5b15e2`, after complete local CI. Both active phases lasted 600 seconds; the Work phase including settlement lasted 601.441 s. Twenty Work clients continuously replenished their backlogs and advanced in the minute snapshots. Steady 100-event batches were 1,562,844 UTF-8 bytes (first metadata batch 1,548,122); largest event 108,732 bytes, including the exact 106 KiB field.

| Metric | No Work | Twenty Work streams | Limit |
|---|---:|---:|---:|
| Messages sent / stored / durably received | 12,000 / 12,000 / 12,000 | 12,000 / 12,000 / 12,000 | Equal |
| Save p99 | 55.51 ms | 254.07 ms | <=1,000 ms |
| Durable receive p99 | 53.71 ms | 253.86 ms | <=2,000 ms |
| Save / receive p99 increment | - | 198.56 / 200.15 ms | Each <=500 ms |
| Duplicate deliveries / message errors | 0 / 0 | 0 / 0 | 0 |

Twenty uploaders committed 65,330 events and uploaded 1,047,824,074 accepted HTTP body bytes. Each uploader made sustained progress; the per-node totals are in [load-summary.json](M1-reliable-im/evidence/load-summary.json). The center issued 329 expected Work-only 429 busy responses, retried with Retry-After; no message errors resulted. This verifies the stated 96 KiB/s-per-Work-node profile, without claiming unlimited ingress or production capacity.

The JSON is aggregate evidence, not a raw log, runtime database or credential file. Final command: `IM_LOAD_BASELINE=.e2e-load-baseline.json IM_LOAD_OUTPUT=.e2e-load-result-final-pass.json node --import tsx tests/e2e/reliability/im-load.mts`. Raw observations: `.e2e-load-final-pass.log`. The retained no-Work baseline scope is documented above.
