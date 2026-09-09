# Real-stack development evaluation

These are open development observations used to find defects and tune status wording. They are not a held-out benchmark, a sealed exact-model replay, or a causal measurement of the prompt change. Recipes were written before their respective trials; failed attempts and window misses remain in `results.json`. The Raft-inspired stress recipe uses three ALWAYS Agents without assigned turns, aiming for exactly 1–20. The source article does not disclose enough detail for an exact replication.

## Environment and evidence

Real isolated IM HTTP/WebSocket, Gateway, kernel, configured LLM providers, persistence, and Web IM were exercised. Ordinary cases used `deepseek:deepseek-v4-flash`; the image correction used `codexOAuth:gpt-5.6-sol`. The fixture config selected high reasoning; provider revision was not sealed. The runtime never used production IM or production Gateway state. Portable Python drivers next to this report use `IM_URL` and the repository E2E client. `run_special_cases.py image` additionally needs Pillow and the macOS fixture font.

Raw API transcripts, browser images and runtime diagnostics are retained locally under `/Users/Shared/feat544-evidence-20260909/raw` in the delivery evidence copy. They are not committed because repository policy excludes runtime logs, databases and screenshot caches. `results.json` records raw artifact hashes, formal replies, withheld draft hashes/lengths, tools and exact source IDs. `prompt-iterations.json` records the three status-wording versions and confounding instrumentation changes.

## Findings and fixes

- The initial repeated-update reply referred the user to a notice that was actually withheld. The status prompt now requires a complete current answer when the original rules still call for a reply, and prevents treating unrelated updates as cancellation. A subsequent run consumed two distinct updates in two segments and returned the final September 23 notice. The second-injection timing also changed, so this is not a prompt-only comparison.
- The first real sending-tool trial exposed the HTTP wrapper mapping a held result to 503. The wrapper now returns HTTP 200 with an explicit held result; a real rerun withheld the old tool payload and sent the corrected payload. Unit transport tests reproduce the original red result.
- A background continuation consumed a correction but left its follower input in `sent`. Background runs now share coordinator admission, observer, terminal follower and recovery lifecycle handling. A later actual background candidate was withheld and the corrected September 28 / Room D response completed its human input.
- Raft counting exposed completed receipts repeatedly generating peer messages, with the original input ID used as source. Fanout now comes from actual nonempty completed reply persistence, deduplicated per real message ID and target; follower receipts only settle tasks. Peer failure receipts cannot rewrite a completed source message. A real peer-correction rerun references the corrector's actual reply ID.
- Counting also exposed ambiguous model history around identical candidate texts. Each ordinary output candidate now persists its own local committed or withheld status and associated message IDs. Local commit is explicitly distinguished from remote delivery acknowledgment. The transcript reload regression protects earlier committed text when a later identical candidate is withheld.

## Behavioral coverage

The recorded cases cover no update, date correction, English three-point output, irrelevant update preserving the original request, repeated updates, same-group sending tool, background continuation, image correction, permitted silence, peer-origin correction, and unchanged direct/MENTION admission. A miss of the actual candidate-generation window is recorded as a miss, not a passing revalidation case. Invalid tool allowlists in early attempts remain setup/instrument failures.

The actual browser was used to expand full unsent draft text, follow the successor segment, expand revalidation, jump to the source message, reload persisted history, and inspect desktop and 390px mobile layouts. The initial light-theme contrast problem in the process card was fixed and visually rechecked. Process-only silence retains both the old draft block and completed new process without a visible NO_REPLY token. A 401 occurred after test login/session changes; normal reauthentication restored the page. Browser requests and console captures are retained with the local evidence rather than described as globally error-free.

## Counting boundary

All attempts retain their full visible sequences. A failed run is not upgraded to success merely because it reaches 20. The first fixed run's duplicate 3 is traced in `counting-race-evidence.json`: Agent C committed at 02:24:45.208 UTC, before IM created the competing peer relay at 02:24:45.395 UTC. The other input entered C's transcript at 02:24:45.418 UTC. The accepted-input guard cannot arbitrate this pre-arrival concurrency window. This implementation intentionally retains the approved local-input boundary and does not add a globally atomic room version or a turn-taking controller.

The initial diagnostic counting capture also includes stop acknowledgments; its separate before-stop snapshot is retained, and neither is promoted to a clean benchmark endpoint. Final per-trial counts and outcomes are in `results.json`; source and frozen recipe are in `raft-counting.json`. Concurrent ordinary rechecks also ran on the shared test provider during fixed counting trials; elapsed time therefore includes provider load and must not be interpreted as a latency benchmark.

## Fixed-code counting results

| Trial | Last number | Duplicate replies | Drafts / revalidations | Result |
|---|---:|---:|---:|---|
| 2 | 17 | 1 | 13 / 13 | Failed: duplicate and 240 s timeout |
| 3 | 20 | 1 | 9 / 9 | Failed: duplicate despite reaching 20 and settling |
| 4 | 18 | 3 | 14 / 14 | Failed: duplicate and 240 s timeout |

All three fixed-code trials fail the exact 1–20 criterion. The original broken-fanout diagnostic is an additional earlier attempt, not one of these three trials.

## v4 real-model retest

After the user requested direct evidence of model understanding, six fresh real IM/Gateway/kernel/DeepSeek cases ran on `ed925a8ab`: date correction, irrelevant update, repeated update, allowed silence, same-group tool sending, and background continuation. **All six passed with actual draft withholding and completed revalidation; no window misses.** The repeated-update case consumed two batches and produced the September 23 two-sentence final notice. The tool case returned held for the old send, successfully sent the corrected September 19 / Room B notice, and explicitly stated the old version had not been sent. Allowed silence kept empty formal bodies with durable Process. Background returned September 28 / Room D and completed the input lifecycle.

Each corresponding real LLM_PROXY request was checked for `<system-reminder>` wrapping, immediately preceding text reference, and absence of candidate IDs in model-visible text. JSONL still retains the candidate metadata. See [v4 real retest](v4-real-retest.json) for exact raw/session/proxy paths and hashes. These are targeted behavioral observations supporting correct use of the prompt in these cases, not a general guarantee of model comprehension or a new counting/reliability benchmark.
