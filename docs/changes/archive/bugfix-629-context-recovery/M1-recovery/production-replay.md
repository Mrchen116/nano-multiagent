# Original production todo request replay

Date: 2026-10-21. User requested restoring a test copy to before the first new-style compaction and testing the actual production todo failure. This report covers that original input; it does not supersede the R5 forced-reset Notes-selection failure in [regression.md](regression.md).

## Result

**PASS for the original production request on the fixed runtime.** The real model acquired the original 14:12:07 Inbox message, “今天有什么todo吗”, read actual journal files, and delivered one substantive todo answer to the isolated delivery sink. It did not terminate with the previous midday greeting's completion. This was not a production deployment or a real Feishu receipt test.

The final answer identifies the evening interview and the already-rescheduled interview, lists four older pending items, and explicitly distinguishes their unconfirmed completion status from today's confirmed arrangements. The native turn ends as completed only after the answer's captured `send_message` result. Acknowledgement and substantive answer are counted separately.

## Reconstructed boundary

- Production source: Mini native session `8d36509c-91d0-423d-97d4-2f6419162253`; read-only download of the complete V4 log, 7,047 events through seq 7046.
- The first new-style compaction starts at seq 6843, 14:10:55, during scheduled turn 179. Todo input is subsequently read at original seq 6874, message `daf538d32fce47fa98e259ea0605262c`, in turn 180. The original failing todo turn resets again at seq 6888 after reading the vault instructions.
- The accepted replay cut is seq **6822**, the standalone tail after completed turn 178 and immediately before the scheduled wake at seq 6823. All 6,823 prefix event payloads remain unchanged; the physical header's cwd points to the isolated workspace. Native preset identity is retained through the ordinary trusted binding.
- The original schedule message from seq 6828 is submitted with its original `schedule` source through public Agent `followup`. Only after that turn finishes is the original Inbox wake submitted. The product boundary returns the original Inbox message object, retaining its sender, owner flag, channel, timestamp, ID and content. It is never relabelled as a direct model user message.
- No Notes existed at this prefix: the original first Notes write occurs at seq 6840. The replay starts with an empty session Notes namespace and does not copy future Notes or the failing future turns.

An earlier setup probe cut at seq 6842 and delivered the todo wake before the interrupted scheduled turn had finished. That probe's message ordering differs from production and is excluded from the verdict. Its files remain in `setup-boundary-probe/`; the accepted replay uses the closed-turn boundary and original ordering described above.

## Runtime and isolation

Nano executable source is `839880856ca9b8d9717fe0045bbc34a7b479de5c` (reports through `7d0ea705a`); locked plugin is `dsh-agent-context@0.3.0-rc.5`, source `823a202`. Model remains `anthropic/codexOAuth:gpt-6-astra`, reasoning medium, context 258,400, output cap 32,768, and plugin default reserve/reminder budgets. No context hint, answer template, manual reset or budget reduction is supplied.

The copy uses its own DSH home, storage, Notes and workspace under `/tmp/bugfix629-prod-replay`. Production workspace Skills/Memory and global Nano Skills were copied; compatibility Skill roots and external plugin paths were not connected. Automatic memory/skill maintenance intervals were moved beyond this short replay, while their prompt features remained enabled. No production scheduler state was imported. The original execution tool selection was retained; the test boundary prohibits external mutation/delegation and captures public sends locally. None of those prohibited operations was attempted. Native `read` reads the actual local iCloud journal; the two files used by the model match Mini's production files by SHA256.

The public message tool's real model-chosen payload is accepted by a local test sink, not transmitted to production. Consequently this validates model task continuation and the explicit delivery call, not IM persistence, provider receipt or live user visibility. Inbox responses are replay data, not a live production subscription. No production configuration, session, process or file was changed.

## Evidence

| Observation | Accepted replay |
|---|---|
| Scheduled turn | 2 requests; one captured midday greeting, then private close |
| Todo turn | 8 requests; Inbox check/read, acknowledgement, two journal reads, one substantive answer, private close |
| Journal reads | `4.0 Journal/2026-10-16.md`, `4.0 Journal/2026-10-21.md`; both byte-identical to production |
| Model input across both turns | 173,612 → 175,942 tokens, including cache; growth 2,330 |
| Runtime snapshots per request | 5 in all 10 requests; inherited copies stay constant |
| Original todo message | Present in all 5 model requests after its Inbox read |
| Compaction/reset during replay | 0; pressure never requires a reset |
| Tool errors | 0 |
| Terminal state | Todo turn 180 completed, acceptedSeq 6841, consumedSeq 6845 |
| Cleanup | Runtime shut down normally; recorded PID 10195 is absent |

This supports the specific causal repair: previously each ordinary step appended another large runtime snapshot and rapidly forced a reset; the fixed runtime keeps that count stable and completes the todo task within the existing window. It does **not** demonstrate correct task selection after an unavoidable forced reset, nor negate R5's real-model counterexample.

Local private evidence (not committed): `/tmp/bugfix629-prod-replay/{manifest.json,evidence-summary.json,requests.jsonl,events.jsonl,tool-attempts.jsonl,product-calls.jsonl,deliveries.jsonl,terminal.json,file-comparison.json}`. The `source/` directory preserves the downloaded session, configuration snapshot, Skill archives and production journal hashes. Scripts `prepare.py`, `observe.mjs` and `run.mjs` document exact setup and isolation.
