# M1 implementation and validation

## Authorization and scope

2026-09-09: user requested change-orchestrator-simple implementation, explicitly waived subsequent independent code-review/reviewer/verifier stages, and required self-run real-stack/model cases plus prompt iteration based on observations. We keep unit/integration checks, real browser/model evidence, canonical reconciliation, CI and PR delivery. No production deployment or PR merge authorized.

Branch: `codex/feat-544`; isolated worktree `.worktrees/unit-feat-544`; base `ce10d4d6d`. Main checkout remains untouched. One M1 delivered jointly: kernel worker owns `src/agent`, IM worker owns `src/IM`, parent owns PA wiring and end-to-end evaluation. No parallel writes to the same source files.

## Baseline

`PYTHONPATH=src .venv/bin/python -m pytest -q tests/unit/personal_assistant/test_steer_bubble_roll.py tests/unit/personal_assistant/test_send_message_tool.py tests/unit/personal_assistant/test_session_run_coordinator_steer_identity.py tests/im_service/unit/test_event_bridge.py`: **31 passed**, before changes.

Shared main .venv supplies dependencies only; PYTHONPATH and runtime scripts load this worktree's src. The implementation baseline preceded isolated service startup; final runtime evidence is recorded below.

## Test strategy

Keep current steer-bubble, send-message and recovery identity protections. Extend lowest relevant seams for exact consumption identity, same-group admission and held tool responses. Kernel SDK tests protect publish/accept ordering; IM persistence/frontend tests protect process-only history. Real-stack cases protect actual model behavior, cross-process wiring and browser perception; they are not replaced by mocks. Case inputs and scoring criteria are frozen before prompt trials, with every run outcome retained, including window misses/failures. Cases used to tune the prompt are open development cases, not an unbiased holdout KPI.

## Implementation and real validation

The kernel owns one accepted-input/output commit boundary, retained candidate states, and background inheritance. Gateway limits opt-in to native group runs, projects exact consumed source identities, reuses bubble rolling and the foreground lifecycle for background runs, and guards same-group send_message at its actual dispatch boundary. IM persists Process records across live/history views and fans out only real completed formal replies. Tool-held HTTP results remain a normal explicit held response.

The design and package delta specifications have been reconciled to the final implementation, including per-candidate durable status and actual-message fanout provenance. Independent implementation review, product reviewer and verifier were explicitly waived by the user; no such approval is claimed. Parent self-validation and real evidence remain required and are complete. All three fixed-code counting trials failed the exact criterion (duplicates 1, 1, 3; last numbers 17, 20, 18). One duplicate is conclusively traced to the approved pre-arrival concurrency boundary; other duplicates are retained without claiming a separately proven cause.

See [evaluation report](evaluation/report.md), [case results](evaluation/results.json), [prompt versions](evaluation/prompt-iterations.json), and [counting race evidence](evaluation/counting-race-evidence.json). The counting experiment exposes the agreed pre-arrival concurrency boundary and does not establish globally duplicate-free counting.

Final local CI-equivalent Python shards: **1,771 agent/PA passed** and **1,814 remaining passed**. Frontend: **71 files / 685 tests passed**, critical dependency audit passed (existing lower-severity advisories remain). Ruff check/format passed. Browser desktop/mobile full draft, continuation and source interactions were exercised against real services. All raw trials, including invalid setup, missed windows and failures, are retained locally with artifact hashes in the committed results.

No production deployment or PR merge is part of this delivery. Main checkout and unrelated work are preserved.

## Post-PR prompt clarification

On user request, output status messages now use the existing `<system-reminder>` envelope and refer to the immediately preceding assistant text. Candidate IDs are removed from model-visible status text and retained in structured metadata for durable linkage. Rewrote the existing request/reload regression rather than adding a parallel test: RED exposed the old ID in the model request; GREEN **4 output revalidation tests passed**, including distinct committed/withheld state after JSONL reload. Ruff and diff checks passed. This bounded prompt change does not alter admission, commit or fanout behavior. Historical real-model logs remain v3; the new wording is recorded separately as v4.

Worktree remains available at the user's explicit request; isolated services remain stopped. Cleanup awaits a subsequent user instruction.

The follow-up v4 real-model validation is complete: six targeted cases passed; actual proxy requests, candidate metadata and user-visible outcomes are recorded in [v4 real retest](evaluation/v4-real-retest.json). This supplements the earlier request-capture unit validation. Existing test sessions are preserved; the new isolated services are stopped after evidence collection, with the worktree retained as requested.

## Synchronization with main after PR #286

Merged main `6346c8374` (bugfix-545) into this branch. Resolved the Process renderer by retaining main's default-collapsed tools and adding the reply-process row; adapted the new draft/reference colors to main's shared light palette rather than restoring the old dark surface. Kept main's sidebar/mobile layout and updated the combined IM requirement counts. The existing held-send UI regression now explicitly expands the tool before checking its details.

Validation: full frontend **71 files / 689 tests passed**; documentation integrity, Ruff check/format and diff checks passed. Real merged-stack date correction `date-correction-1788923833.json` withheld the old draft and completed the September 19 final notice. Desktop/mobile draft expansion visually rechecked. Main changes touch frontend/docs only; the kernel/Gateway commit and revalidation code are unchanged from the six-case v4 real-model retest.
