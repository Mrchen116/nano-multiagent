# refactor-459-M5 — Progress

## Baseline

- Scope: round 2 behavior-preserving fix；不处理 ghost-register、shared-connection pending binding、replay-before-resolve、owner orphan、canonical-direct 全量 hydrate、waitpid。
- Initial gate: `pytest -m "not e2e"` → 3484 passed，2 skipped，23 deselected（102.19s）。
- Reviewer failure timeline: retained pytest-131 `.im.log` shows readiness GET `/nodes` at line 183, follow-up conversation POST 503 at line 187, replacement `/im/ws/gateway` accepted only at lines 190–191. The pre-restart heartbeat baseline was therefore satisfied before replacement registration.
- Root-cause hypothesis: old Gateway may emit a final heartbeat after the test samples its pre-restart timestamp but before `_terminate_process_group` completes; sampling the generation floor only after termination closes that window without sleep or weaker conversation assertions.

## R1 — replacement Gateway readiness

- Status: TODO

## R2 — direct enqueue-time route

- Status: TODO

## R3 — group bulk hydration 与 enqueue-time route

- Status: TODO

## R4 — offline failure sequencing 与 stale order

- Status: TODO

## R5 — 真栈与完整门禁

- Status: TODO
