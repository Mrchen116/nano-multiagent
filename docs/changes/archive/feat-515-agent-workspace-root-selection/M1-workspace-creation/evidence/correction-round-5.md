# Round-5 Correction Evidence

## Review findings and corrected boundaries

| Finding | Corrected behavior | Durable regression owner |
|---|---|---|
| Gateway accepted a same-root existing Agent when the incoming create operation was absent. | An existing Agent returns its create result only when the incoming non-empty operation id is exactly the persisted id; no-id legacy retries and different ids return the existing structured duplicate rejection. | `tests/unit/personal_assistant/test_gateway_workspace_creation_immutability.py` |
| An Agent-sourced conversation with an absent/unroutable profile omitted transcript status and UI classified it as permanently missing. | IM returns `source_jsonl_status="unavailable"` without a profile/node and the distill selector shows the temporary-unavailable state before considering source-node absence. | `tests/im_service/integration/test_users_conversations_api.py`, `src/IM/frontend/src/features/chat/components/conversation-sidebar.test.tsx` |
| Pending recovery had no permanent HTTP proof that invalid retries preserve the one valid operation. | A different effective request returns 409 before Gateway dispatch; a response with a wrong echoed operation returns 409 after dispatch. Both leave the durable operation and pending profile marker unchanged. | `tests/im_service/contract/test_agent_registration_seed_recovery.py` |

## Red-green and focused regression record

- Before implementation, the new Python owner tests failed on both no-id replay paths and both absent/null-node
  transcript projections (`4 failed, 9 passed`). The strengthened sidebar regression failed by rendering
  **No transcript** rather than **Transcript temporarily unavailable**.
- After the three constrained production changes, the direct owner command passed:

  ```text
  ../../.venv/bin/python -m pytest tests/unit/personal_assistant/test_gateway_workspace_creation_immutability.py tests/im_service/contract/test_agent_registration_seed_recovery.py tests/im_service/integration/test_users_conversations_api.py -q
  13 passed
  ```

- Expanded cross-boundary coverage passed:

  ```text
  ../../.venv/bin/python -m pytest tests/unit/personal_assistant/test_gateway_workspace_creation_immutability.py tests/unit/personal_assistant/test_gateway_session_log_resolution.py tests/unit/personal_assistant/test_gateway_im_connection_behavior.py tests/im_service/unit/test_gateway_handler.py tests/im_service/unit/test_db_init.py tests/im_service/unit/test_repositories_agent_profile.py tests/im_service/integration/test_users_conversations_api.py tests/im_service/integration/test_gateway_im_registration.py tests/im_service/integration/test_agent_create_flow.py tests/im_service/contract/test_agent_registration_seed_recovery.py -q
  97 passed, 2 warnings
  ```

- Sidebar owner coverage passed `12 tests` with Vitest. The warnings are the repository's existing Node
  localstorage-file warning and the Python dependency deprecations.

## Isolated browser acceptance and cleanup

- Used `scripts/e2e-up.sh --wt /Users/czj/Repos/nano-multiagent/.worktrees/feat-515-M1-fix5` in a retained tmux
  session, then launched Vite on a separate worktree-local port. The isolated IM ran on `127.0.0.1:57324` and Vite
  on `127.0.0.1:57374`; no production service or configuration was used.
- In headed Chromium, signed in as the disposable E2E user, created a real Agent conversation, stopped only that
  worktree Gateway, reloaded, and entered **Generate skill**. The conversation checkbox and action stayed disabled
  and displayed **Transcript temporarily unavailable**; **No transcript** did not appear.
- The final browser console reported `0` errors and `0` warnings. `e2e-down.sh`, both tmux sessions, the frontend
  dependency link, and the browser session were removed; the generated IM and Vite ports had no listeners.

## Final gates

- Full Python: `ulimit -n 65536; python -m pytest -m "not e2e" -q` — `3062 passed, 24 deselected, 22 warnings in
  262.99s`. The slower-than-usual run was sampled while active: it was progressing under host CPU contention, not
  blocked on an external service or test failure.
- Full frontend: `npm test -- --no-file-parallelism --maxWorkers=1` and `npm run build` both passed. The production
  build retained only the repository's existing Rollup chunk-size advisory.
- Static/documentation: `ruff check .`, `scripts/docs-check` (`227` maintained Markdown sources / `66` required
  routes), and `git diff --check` passed.
