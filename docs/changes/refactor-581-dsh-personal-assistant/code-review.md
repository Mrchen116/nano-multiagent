# Code Review: refactor-581-dsh-personal-assistant

Round 1 · full · **Changes required**

Frozen implementation: `4915c44cb7f7b829414a19087877ad9b73d69ea1 → e89179da8956577b288ee374fe791c2ce82d5047`.

The machine-readable result is [code-review.json](code-review.json): **3 CONFIRMED findings**, no PLAUSIBLE findings. The two P1 defects concern execution liveness and the retained client usage schema; the P2 defect concerns public execution readiness after DSH recovery.

## Scope and interpretation

Reviewed the new semantic owners: product contracts; Node configuration, lifecycle, provider and device-binding/migration entrypoints; DSH public profile/RPC/session/preset/event/history/approval/fallback/capability integration; all five independent Feature lifecycles; Workflow host/guest controls, prefix state, catalog and accounting; knowledge maintenance; PA single-thread/global Inbox, session controls, delivery/outbox and channel ownership; Feishu parsing/transport/credentials; native IM identity, configuration operations, media, messages, gateway delivery, Work and task-graph projections; retained Web/Swift consumers; tests, CI and legacy-test disposition. Deleted Python implementation was examined through retained invariants and replacement owners rather than mechanically reviewing retired implementation lines.

Applied the approved migration decisions: stock DSH `0.2.1-alpha.1`, public interfaces, native tool names, native schedules to the parent conversation, no old-chat conversion, and retirement of the old Python kernel/Coding CLI. Canonical spec merge/archive is a later workflow step and is not reported as a source defect. Physical iOS acceptance is owned by the product reviewer, not this code review.

Only the frozen commit was reviewed. Parent-owned uncommitted repairs and documentation updates are excluded and require a precise patch/closure handoff.

## Independent confirmation

1. **Watchdog:** created an isolated native IM server and temporary database, shortened its own timeout to 0.05 seconds/interval to 0.01 seconds, inserted one quiet execution and one pending approval. Both became failed despite the fresh approval wait. The resulting content was `relay idle for 0.05s with no new event`. The actual timeout is 120 seconds. Source confirms no replacement runtime producer for `run_heartbeat`; node connection heartbeat is a different fact. Server and temporary data were removed.
2. **Usage:** transpiled and executed the frozen `presentation.ts` without loading the modified working-tree file. Native input=100/cache=50/output=20 projected `{prompt:150,completion:20,total:170,cache_read:50,cache_total_input:150,context_window:128000}`. The retained client calculation yielded NaN (JSON serializes it as null); accessing `usage.output.toLocaleString()` produced a TypeError.
3. **Readiness:** started a real isolated node with stock DSH and a private empty-agent config, killed only its owned runtime PID 33272, and observed replacement 33287. State still recorded `{ready:true,runtime_pid:33272}` and public status returned `RUNNING pid=33254 ready=true DSH=33272`. CLI stop completed and the private fixture was removed.
4. Independently reran `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest tests/contract/test_runtime_dependency_contract.py -q`: **8 passed**. The worktree-local `.venv` is absent; the shared repository interpreter was used. Other retained integration test results are mapped in [verification.md](verification.md), not represented as independently rerun here.

No source/test/configuration/design edits or shared-tree commit were made by this reviewer.
