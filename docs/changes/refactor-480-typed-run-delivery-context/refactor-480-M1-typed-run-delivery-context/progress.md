# refactor-480-M1 implementation record

## Completed implementation

- Removed the legacy context mirror, mapping facade, dict fallback paths, and string-encoded boolean state.
- Made the typed store the only live run representation; relay cleanup uses idempotent `discard()` and owner-direct streams use atomic `take()`.
- Replaced mutable terminal context output with the frozen `RunDeliveryTerminalProjection` consumed by heartbeat only.
- Moved observer mutations behind typed domain actions for turn-start acknowledgements, bubble replacement, visibility/silence, shadow state, and external text.
- Migrated behavior fixtures to a test-only typed-store factory; production accepts no legacy dict representation.

## Local evidence

- Baseline before the implementation: 132 focused tests passed.
- After the cutover: `ruff check` on all changed source and tests passed; the targeted Gateway, observer, scheduler, and stream suite passed (`150 passed`).
- Worktree IM + Gateway started with isolated ports/config and passed OpenAPI plus live-PID health checks; it was kept separate from the main checkout.
- `tests/e2e/critical_paths/test_agent_config_context_continuity_critical_path.py` passed against a real IM + Gateway stack and recording LLM fixture (`1 passed`).
- Remaining gates: independent verifier/reviewer/code review, sync against current `origin/main`, archive, and PR CI.
