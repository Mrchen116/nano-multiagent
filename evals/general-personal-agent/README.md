# General personal agent evaluation

This suite adapts the 58 synthetic scenarios from `nano-pa-general-v2` to actual
IM interactions. The source package supplied scenarios and a result summarizer;
it did not supply an executable runner. `scenarios.yaml` and
`fixtures.synthetic.json` preserve those source assets. `adapters.json` contains
an explicit ID-to-step mapping and evidence checks, with no title-based routing.

The executable entry is
[`tests/e2e/general_personal_agent`](../../tests/e2e/general_personal_agent/).
It reuses the critical-path `IMClient`, public IM APIs, and the existing daily
profile. It never imports product internals, invents tool results, or interprets
an assistant's claim of success as a behavior pass.

## Collection and execution

Use the repository Python environment (Python >=3.11 plus dev dependencies).
From the repository root:

```bash
python -m tests.e2e.general_personal_agent collect --cases all
python -m tests.e2e.general_personal_agent dry-run --cases smoke --output /tmp/pa-smoke-plan.json
python -m pytest tests/e2e/general_personal_agent/test_protocol.py -q
```

Collection validates all 58 mappings. A dry-run performs zero live actions and
writes `not_run` plan entries. Protocol tests prove the runner's evidence rules,
not PA behavior.

For each case and repetition, prepare a **fresh**, isolated daily profile using
[worktree-runtime](../../docs/development/worktree-runtime.md). The same model,
reasoning effort, approval rules and selected tools must be used on the old
baseline and candidate. Do not reuse a production or previously exercised PA.
The runner requires an empty owner PA timeline, a `wt-` node, loopback high port,
and a per-node claim file. One stack runs one case; this prevents previous
personal memory, schedules and attention from contaminating subsequent cases.
The caller owns stack startup, shutdown and removal of runtime resources.

```bash
export PA_EVAL_PASSWORD=nano1234  # isolated daily fixture only
python -m tests.e2e.general_personal_agent run \
  --case M01 --label candidate \
  --manifest /absolute/isolated-stack/.e2e-daily.json \
  --output /tmp/pa-eval/candidate-M01-1
```

The runner creates real distinct user identities and owner/PA, work, family and
shared conversations. Third-party text is actually sent by another user, never
embedded in an owner instruction pretending to be third party. Same-name people
have different real IDs. Only those conversations remain in the PA's source
scope. Cases with observation intervals enable the existing heartbeat at ten
minutes; no new scheduler or fake wake is introduced. `observe` waits real time
and records Work samples. A wall-clock wait alone does not prove a heartbeat
ran. Review must inspect its actual trace. Times in the source fixture are
nominal; live timestamps and relative dates are captured from the actual run.

`run` records `state.json`, per-step snapshots, complete `evidence.json`,
`rubric.json`, `result.json` and `actual-results.jsonl`. These contain synthetic
private conversations and belong outside Git. Credentials are read from the
named environment variable and are not written into evidence. Live output is
not stored under the suite directory.

## Execution adapters and explicit limits

Every case has concrete IM setup/action steps and an observable evidence rubric.
Steps are `send`, `observe`, `disable_memory`, `exclude_source` and `checkpoint`.
Ordinary sends settle against actual PA replies plus Work revision/idle state;
parallel scenarios deliberately send without waiting for settlement. All chat
and Work pages are captured, including real native child turns and tool detail.
Source IDs, session/turn IDs and resource references remain intact.

Some scenario preconditions cannot be manufactured through ordinary owner IM
messages. `checkpoint` stops execution with `not_run`, a named action and precise
required evidence. It **does not pretend to implement fault injection, native
restart, browser clicks, stale-source replay or runtime guard probes**. These
specialist fixtures must be performed against the same isolated run by the
reviewer or a separate test driver. The scenario remains incomplete until that
action is performed and its real evidence is supplied.

Typical checkpoints include concurrent maintenance M09, native failure W04,
late events W06, actual browser interactions U01–U03, and execution guard probes
S03/S04. Their exact per-case instructions are in `adapters.json`. This is an
executable collection/replay entry, **not a claim that all 58 complete journeys
are fully automated**.

To resume, provide a JSON object keyed by the pending checkpoint key:

```json
{
  "freeze-maintenance": {
    "run_id": "copy-from-state-json",
    "case_id": "M09",
    "performed_by": "independent-reviewer",
    "action": "Describe the actual isolated fixture action and native IDs",
    "files": [
      {"path": "/absolute/maintenance-read.json", "sha256": "actual-sha256"}
    ]
  }
}
```

Run the same command with `--checkpoints /absolute/checkpoints.json`. It resumes
from `state.json` after checking run identity and the adapter hash. File hashes
bind the receipt to real bytes; the external reviewer must still verify that the
bytes prove the requested action. Never use a synthetic assistant response as a
native event or an unsigned prose claim as a guard receipt.

## Evidence and verdicts

Raw behavior results use `passed`, `failed`, `blocked` or `not_run`.
Successful message execution remains `not_run` with
`evidence_needs_review: true`. HTTP errors/timeouts are visible `failed`
executions, not silently skipped. Missing specialist steps remain `not_run`;
unavailable external integrations are separately `blocked` live parts.

Work traces are **not final provider inputs**. `context_pointers` identify the
sessions/turns for locating actual provider request logs using the repository
[LLM integration guide](../../docs/development/llm-integration.md). Attach those
actual inputs for root and relevant children. Missing or incomplete child
capture prevents a full pass. Resource references also do not prove that a file
opens or has correct bytes; attach independent download/hash/browser evidence
when the assertion requires it. User-visible messages, tool receipts and
provider inputs must agree.

External adjudication covers every `expect`, `must_not` and adapter `review`
entry, indexed from zero. It names an independent reviewer, hashes the exact raw
result and all cited files, and gives precise locators/reasons for each verdict.
The evaluated PA cannot grade itself. Example shape (include **every** rubric
entry, not just the abbreviated example):

```json
{
  "run_id": "from-state",
  "result_sha256": "sha256-of-result-json",
  "method": "human",
  "reviewer": "reviewer-identity",
  "files": [
    {"path": "/absolute/provider-request.json", "sha256": "...", "kind": "model_input"},
    {"path": "/absolute/evidence.json", "sha256": "...", "kind": "tool_trace"},
    {"path": "/absolute/message-evidence.json", "sha256": "...", "kind": "user_result"}
  ],
  "assertions": [
    {"id": "expect:0", "verdict": "passed", "reason": "Observed source-linked record commit",
     "references": [{"path": "/absolute/evidence.json", "locator": "/tool_results/3/payload/detail"}]}
  ]
}
```

```bash
python -m tests.e2e.general_personal_agent adjudicate \
  --output /tmp/pa-eval/candidate-M01-1 --review /absolute/review.json
```

This writes a separate `adjudicated-result.json`; original observations stay
unchanged. An incomplete checkpoint, failed execution or missing provider input
cannot become a full pass. A review may also contain `parts`, each with `status`,
`reason` and hashed-file `references`, to separately grade an IM fallback while
the live calendar/email/booking part stays blocked. Required live parts for
D01/D02/D04 must be independently passed before the entire case can pass.
P11/D08 intentionally test honest behavior without external connections; their
unavailable live parts do not negate a verified IM fallback. The system never
claims to connect an external account on its own.

## Repetitions and baseline comparison

The smoke selection is M01/M02/M06/M09/P01–P04/I05/W01/W03/W04/W06/D08/U01/S03.
Run at least three independent fresh stacks for each selected case and condition,
then supply their output directories:

```bash
python -m tests.e2e.general_personal_agent compare \
  /tmp/pa-eval/baseline-M01-1 /tmp/pa-eval/baseline-M01-2 /tmp/pa-eval/baseline-M01-3 \
  /tmp/pa-eval/candidate-M01-1 /tmp/pa-eval/candidate-M01-2 /tmp/pa-eval/candidate-M01-3 \
  --output /tmp/pa-eval/comparison.json
```

Comparison rejects reused nodes/runs, fewer than three repetitions, unmatched
model/tool/Feature configurations and unadjudicated results as non-comparable,
with explicit reasons. New-only capabilities can still be reported separately;
they do not produce a fabricated old-versus-new percentage. Counters distinguish
observed Work turns/tool calls and reported token usage from unavailable model
call counts, incorrect-memory counts, duplicate notifications and response
blocking latency. Those remain null until measured from actual evidence; no
zero is invented. The report includes raw resource references and elapsed time.

No live behavior success is established by the suite's checked-in files.
