# bugfix-536-M4 progress

## R1 — 2026-08-13: scope and baseline

- Pre-fix head: `62c2f24110b2f98cf7eb30aef6849bffd603c752`; local and remote
  `unit/bugfix-536` matched before the isolated M4 worktree was created.
- The Round 3 verifier identified exactly two full-repository formatter drifts:
  `src/personal_assistant/gateway/inbound_models.py` and
  `tests/contract/test_kernel_sdk_behavior_contract.py`. The pre-change
  `ruff format --check` on only those paths reported exactly those two files.
- `liveness.py` behaviour already covers tool, LLM, permission, and compaction
  windows. Its module and API docstrings were stale; this M4 change is wording
  only. No new regression test is appropriate for documentation and mechanical
  formatting.
- M3 already has the concurrency regression at its lowest observable owner;
  its task record lacks the required testing strategy and affected-test
  disposition. M4 documents that ownership without changing test behavior.

## R2 — in progress

- Pending exact formatter invocation, docstring/task-record updates, and
  focused validation.

## R3 — pending

- Pending mandatory full formatter gate, lint, focused tests, docs/diff checks,
  integration, push, and worker cleanup.
