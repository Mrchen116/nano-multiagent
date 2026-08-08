# Round-6 Correction Evidence

## Corrected boundaries

| Finding | Corrected behavior | Durable regression owner |
|---|---|---|
| Production binding lookup synchronously probed a custom workspace before yielding. | Gateway projects the durable binding address without `Path.is_file()` or `Path.resolve()`; no binding is `missing`, while provider/binding failure is `unavailable`. | `tests/unit/personal_assistant/test_gateway_im_connection_behavior.py` |
| An ineligible selected source remained hidden in state and could later switch the selected node after availability/order changed. | The chat page purges selected ids once they become ineligible; a later refresh preserves the explicit B selection rather than restoring A. | `src/IM/frontend/src/features/chat/chat-workspace.integration.test.tsx` |
| Pending retry negatives only compared selected durable fields. | The HTTP recovery contract snapshots complete profile and operation rows before and after both rejection paths. | `tests/im_service/contract/test_agent_registration_seed_recovery.py` |

## Red-green record

- Baseline owner suite before the new cases: `34 passed, 2 warnings`.
- The new production binding projection failed before the code change: a durable binding whose JSONL file had not
  been probed returned `missing` instead of `ready`.
- The selection regression failed before the code change: after A became unavailable, B was selected, and A became
  ready at the top of the list, the UI silently selected A and disabled B.
- Focused post-change command:
  `python -m pytest tests/unit/personal_assistant/test_gateway_session_log_resolution.py tests/unit/personal_assistant/test_gateway_im_connection_behavior.py tests/im_service/contract/test_agent_registration_seed_recovery.py -q`
  — `35 passed, 2 warnings`.
- Targeted frontend owner:
  `chat-workspace.integration.test.tsx` — `49 passed`; its unavailable-A / select-B / A-ready-and-reordered
  regression proves B stays selected and A is not silently restored. The existing same-node test preserves
  one-node selection behavior.
- Full regression: `pytest -m 'not e2e' -q` — `3063 passed, 24 deselected, 22 warnings in 173.40s`.
  `npm --prefix src/IM/frontend test -- --no-file-parallelism --maxWorkers=1` and
  `npm --prefix src/IM/frontend run build` both passed; the build emitted only Vite's chunk-size advisory.
- Browser acceptance: an isolated worktree IM, Gateway, Vite, and Chromium stack created an `e2e` conversation.
  Opening **Generate skill** rendered its transcript-less source disabled as **No transcript**; browser console
  reported `0` errors and `0` warnings. The stack, browser, ports, temporary `node_modules` link, and generated
  runtime were stopped or removed after capture; no production service was touched.
- Final static gates: `ruff check .`, `PYTHON=.venv/bin/python scripts/docs-check` (`228` maintained Markdown
  sources, `66` required routes), and `git diff --check` all passed.
