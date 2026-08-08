# Round-8 Critical Correction Evidence

## Corrected boundary

| Finding | Corrected behavior | Durable regression owner |
|---|---|---|
| `GatewaySessionBinder.bind_conversation()` committed a fork/new-conversation binding but bypassed the canonical copy-on-write projection publisher. | After the durable bind succeeds, the binder publishes it through `_record_provenance(..., persist_binding=True)`, updating all provenance maps and the session-log projection together. | `tests/unit/personal_assistant/test_session_fork_handler.py` |

## Red-green record

- Before the correction, `test_fork_handler_locates_source_forks_and_binds_new` persisted `ksess-src-fork` but the
  immediate production session-log provider returned `None` for `conv-new`.
- After the correction, the same fork path immediately returns
  `<workspace>/.nanoassistant/sessions/ksess-src-fork.jsonl` from the lock-free projection.
- Focused owner command:
  `python -m pytest tests/unit/personal_assistant/test_session_fork_handler.py tests/unit/personal_assistant/test_gateway_session_binder.py tests/unit/personal_assistant/test_gateway_im_connection_behavior.py tests/unit/personal_assistant/test_gateway_session_log_resolution.py -q`
  — `46 passed, 7 warnings`.
- Final Python gate: `python -m pytest -m 'not e2e' -q` — `3063 passed, 24 deselected, 20 warnings in 137.89s`.
- Final static gates: `ruff check .`, `PYTHON=.venv/bin/python scripts/docs-check` (`230` maintained Markdown sources,
  `66` required routes), and `git diff --check` passed.
