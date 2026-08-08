# Round-3 Correction Evidence

## Review targets and corrections

| Review target | Correction boundary | Durable regression owner |
|---|---|---|
| R3-1 | A first `node.register` projection is marked as a registration seed regardless of whether its node has already been bound. A recovery claim atomically matches owner, node, Gateway canonical root and provenance, validates the requested display identity against Gateway's persisted result, and clears the marker. | `tests/im_service/contract/test_agent_registration_seed_recovery.py` and `test_agent_create_immutability_contract.py` |
| R3-2 | IM no longer compares raw browser root text after Gateway response. Gateway canonical root is the proof for `~`, `..`, and symlink aliases; changed canonical root or immutable display identity remains a conflict. | `tests/im_service/contract/test_agent_registration_seed_recovery.py` and `test_agent_create_immutability_contract.py` |
| R3-4 | Gateway session-log resolution uses four bounded worker slots, one physical scan per conversation key, 4.5-second logical expiry, and immediate null resolution when no safe slot is available. | `tests/unit/personal_assistant/test_gateway_session_log_resolution.py` |
| R3-5 | An Agent-create draft cannot supply a local-root classifier; only a stored canonical profile root can do so. | `src/IM/frontend/src/features/settings/agents/agent-create-workspace.test.tsx` |

R3-3 was refuted during verification; it has no code or documentation change.

## Red-green record

- Before the correction, an owner-bound registration seed retry returned 409, an overloaded third scan waited without a response, and a target-Gateway draft root could label a source as local.
- Focused Python correction matrix:

  ```text
  43 passed, 7 warnings in 6.23s
  ```

- Targeted frontend Workspace suite:

  ```text
  11 passed
  ```

## Documentation and runtime isolation

- The design and delta now state that Browser and IM forward a nonblank custom target value opaquely; only Gateway interprets its target-host path syntax.
- The second-Gateway Runbook stores its config, PID, log, workspace base, and config-adjacent runtime state in `.gateway-node-2-runtime`, preventing a `node_id` state collision with the primary Gateway.
- Isolated Chromium acceptance opened the online bound node's create page, selected Custom path, and entered `/gateway/staging/../draft`. The rendered skill groups remained `Global` and `Compatibility (Claude/Codex)` with no `Local` group; console output contained only the React development informational message. The temporary screenshot was captured under `output/playwright/` and removed with the isolated runtime.
- Final broad gates:

  ```text
  pytest -m "not e2e" -q: 3054 passed, 24 deselected, 22 warnings in 133.59s
  frontend Vitest (single worker): 64 files passed, 618 tests passed
  ```

- `npm run build` completed (`tsc -b && vite build`); it emitted only the existing Rollup chunk-size advisory. Full-repository Ruff, `scripts/docs-check` (225 maintained Markdown sources / 66 required routes), and `git diff --check` passed.
