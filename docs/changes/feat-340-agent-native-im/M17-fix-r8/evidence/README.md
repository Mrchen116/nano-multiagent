# M17-fix-r8 — Evidence

This worker shipped 6 issues' code-level fixes + tests + production bundle. Per §3.1
of `change-impl-worker`, the production bundle is `cd src/IM/frontend && npm run build`
verified to include the fix markers:

```
sendersById              → 1 occurrence in dist/assets/index-*.js
chat-v2","conversations → 2 occurrences (R7-4 invalidation key)
im-me-identity-card      → 1 (R8-4 mobile /me)
im-me-lang-pill          → 1 (R8-4 pill toggle)
chat-node-chip           → 1 (R7-5 header chip)
/settings/agents/        → 1 (R7-5 ⚙ Config target)
/im/v1/nodes             → ≥3 (R7-5 node fetch)
```

## Browser E2E status

Worker restarted IM service from this worktree's source (PYTHONPATH=src) on
`:8011` at 2026-05-12T15:46Z so the backend changes (AgentSummaryResponse
`user_id`, `_list_message_timeline` :relay: filter, `_parse_token_usage`
`total` field, persistence) are live. Personal-assistant gateway and LLM_PROXY
were not restarted (team-lead instructed LLM_PROXY stays up; gateway was
multi-process from prior session).

Full visual screenshots (single Alpha bubble / realtime label = "Alpha" /
header Node chip+⚙ / /me mobile layout / Token Chip real total / Open chat
success navigation) require driving a logged-in browser through one round trip
with a real agent on a connected node — that bundle was not produced in this
worker session and is deferred to **R9 acceptance reviewer**, who already
exercises this journey by contract (`change-reviewer` skill).

## Test evidence (in-tree)

- vitest: 248/248 passed (52 files) — `cd src/IM/frontend && npx vitest run`
- pytest IM scope: repositories.py +2 tests GREEN, gateway_handler.py +2
  GREEN, all repositories 16/16 GREEN. 6 pre-existing failures in
  `test_conversation_rename.py` / `test_messages_broadcast.py` are 401
  Unauthorized regressions inherited from base branch (verified by `git stash`
  on the base ref); they are out-of-unit for M17.
- Build: `vite build` succeeds (497 kB chunk, 152 kB gzip).
