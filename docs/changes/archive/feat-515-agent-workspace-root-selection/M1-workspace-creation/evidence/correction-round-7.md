# Round-7 Critical Correction Evidence

## Corrected boundary

| Finding | Corrected behavior | Durable regression owner |
|---|---|---|
| The production transcript provider acquired `GatewaySessionBinder`'s `threading.Lock` and queried the shared SQLite binding store on the Gateway event loop. | The binder hydrates committed bindings before IM receive and replaces a copy-on-write projection after each durable update. The provider reads only that immutable projection. | `tests/unit/personal_assistant/test_gateway_im_connection_behavior.py` |

## Red-green record

- Baseline non-E2E Python: `3063 passed, 24 deselected, 20 warnings`.
- Before the correction, the new production-composition regression held a real `PersistentSessionBindingStore.get()`
  inside `GatewaySessionBinder.capture_binding_provenance()` and failed because the IM receive worker could not
  process its heartbeat before the held lookup was released.
- After the correction, the same regression proves heartbeat and `IMConnectionManager.close()` complete while the
  held persistent lookup remains blocked, and the response still returns the exact binding-derived JSONL path with
  `status="ready"`.
- Focused owner command:
  `python -m pytest tests/unit/personal_assistant/test_gateway_im_connection_behavior.py tests/unit/personal_assistant/test_gateway_session_log_resolution.py tests/unit/personal_assistant/test_gateway_session_binder_concurrency.py -q`
  — `35 passed, 7 warnings`.
- Final Python gate: `python -m pytest -m 'not e2e' -q` — `3063 passed, 24 deselected, 20 warnings in 134.19s`.
- Final static gates: `ruff check .`, `PYTHON=.venv/bin/python scripts/docs-check` (`229` maintained Markdown sources,
  `66` required routes), and `git diff --check` passed.
- Frontend/browser/build: N/A for this backend-only correction; it changes neither frontend sources nor its user-visible
  contract. The persistent-store/Binder/IM-control composition regression is the lowest production seam that can
  hold the offending lock and prove the receive/close behavior.
