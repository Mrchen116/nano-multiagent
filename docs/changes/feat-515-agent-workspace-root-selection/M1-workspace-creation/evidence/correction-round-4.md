# Round-4 Correction Evidence

## Review findings and corrected boundaries

| Finding | Corrected behavior | Durable regression owner |
|---|---|---|
| A generic first `node.register` marker did not prove an IM `agent.create`. | IM reserves an owner/node/agent/request-fingerprint operation before dispatch. Gateway persists and echoes its id; only that exact id can make a first registration claimable. | `tests/im_service/contract/test_agent_registration_seed_recovery.py` |
| Recovery could otherwise rewrite a normal/prehosted Agent. | Atomic claim requires operation, owner, node, persisted root/provenance, and display identity; normal PATCH clears pending state and completed operations cannot recover twice. | `tests/im_service/contract/test_agent_registration_seed_recovery.py`, `tests/im_service/unit/test_repositories_agent_profile.py` |
| Recursive thread scans could outlive logical cancellation and overload became “No transcript”. | Gateway derives the exact JSONL path from durable session binding, coalesces one cancellable task per conversation, and reports `ready`, `missing`, or `unavailable`. | `tests/unit/personal_assistant/test_gateway_session_log_resolution.py`, `tests/unit/personal_assistant/test_gateway_im_connection_behavior.py` |

## Red-green and focused regression record

- The new operation API and exact session-log provider tests were introduced before their production seams. The
  recovery suite initially failed until the IM reservation, Gateway persistence/advertisement, and atomic claim
  paths existed; session resolution initially failed until the provider/status contract existed.
- Focused cross-boundary command:

  ```text
  ../../.venv/bin/python -m pytest tests/unit/personal_assistant/test_gateway_session_log_resolution.py tests/unit/personal_assistant/test_gateway_im_connection_behavior.py tests/im_service/unit/test_gateway_handler.py tests/im_service/integration/test_users_conversations_api.py tests/im_service/contract/test_agent_registration_seed_recovery.py tests/im_service/unit/test_db_init.py tests/im_service/unit/test_repositories_agent_profile.py tests/unit/personal_assistant/test_gateway_workspace_creation_immutability.py -q
  90 passed, 2 warnings
  ```

- Recovery/migration/create expansion:

  ```text
  ../../.venv/bin/python -m pytest tests/im_service/unit/test_db_init.py tests/im_service/contract/test_agent_registration_seed_recovery.py tests/im_service/integration/test_gateway_im_registration.py tests/im_service/integration/test_agent_create_flow.py -q
  16 passed, 2 warnings
  ```

- The actual WebSocket lost-response regression disconnects after Gateway local persistence, reconnects with its
  persisted `agent_create_operations` map, then retries the exact HTTP create operation. The same owner succeeds
  once; arbitrary prehosted registration, wrong owner/root/provenance/display, profile PATCH, and repeated create
  all retain 409 without mutating the stored root/provenance pair.

## User-visible transcript state

- `ready` gives the picker an exact Gateway-local JSONL path.
- `missing` is the only state shown as “No transcript”.
- `unavailable` is distinct: the picker remains disabled and shows the localized temporary-unavailable message.
  This includes an unavailable provider or Gateway response, rather than making capacity pressure look like a
  permanent absence.

## Isolated browser acceptance

- Started the worktree-local IM/Gateway stack with `scripts/e2e-up.sh --wt ...` in a retained tmux session and a
  Vite dev server proxying to that isolated IM. The stack used IM port `49590`; it did not touch production `:8011`
  or user configuration.
- Signed in as the disposable E2E user in headed Chromium, created a real direct conversation with the bound E2E
  Agent, then stopped only that worktree Gateway. In the real UI, `Generate skill` showed the conversation checkbox
  disabled with **“Transcript temporarily unavailable”**. The “Distill to skill” button was disabled and no “No
  transcript” text appeared.
- Browser console contained zero errors after the final page reload. The browser, Vite tmux session, Gateway, and
  IM were stopped; the temporary frontend dependency link and Playwright cache were removed. Ignored E2E runtime
  data remains worktree-local and unstaged for the worktree lifecycle.

## Final gates

- Focused frontend distillation owners: `60 passed` (`conversation-sidebar` plus chat-workspace integration).
- Production frontend build completed with only the repository's existing Rollup chunk-size advisory.
- Full Python gate: `ulimit -n 65536; python -m pytest -m "not e2e" -q` — `3060 passed, 24 deselected,
  22 warnings in 135.63s`. The warnings are existing dependency/API deprecations.
- `ruff check .`, `scripts/docs-check` (`226` maintained Markdown sources / `66` required routes), and
  `git diff --check` passed before publication.
- The milestone was rebased against the current `origin/unit/feat-515` tip before publication; it was already up
  to date. All runtime used for browser validation is isolated to this worktree and is stopped before handoff.
