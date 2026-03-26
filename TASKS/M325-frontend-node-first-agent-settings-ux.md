# M325 Frontend node-first agent settings UX

## Context
- Milestone: `M325`
- Goal: Update the IM frontend to make Nodes the only create-agent entry, add node-scoped create flow, show node ownership on agent settings, and drive runtime choices from node/agent capability endpoints.
- Scope: `src/IM/frontend/` only.

## Roadpoints

### R1.1 Node-first create flow and capability-backed settings
- Status: DONE
- Acceptance:
  - `/settings/agents` no longer exposes a global create-agent entry.
  - `/settings/nodes/:nodeId/agents/new` becomes the only create flow and rejects offline/unselected node creation in the UI.
  - New-agent runtime choices come from `/im/v1/nodes/{node_id}/capabilities` and agent edit/runtime choices come from `/im/v1/agents/{agent_id}/capabilities`.
  - Agent settings show owning node information and keep `workspace_root` read-only.
  - Router, settings shell, nodes page, create page, and edit page tests cover the new entry path.
- Tests Plan:
  - Extended `src/IM/frontend/src/features/settings/agents/agent-create.test.tsx` to prove the real settings entry starts from Nodes and that create submits to the node-scoped API with node capabilities.
  - Extended `src/IM/frontend/src/features/settings/agents/agent-edit.test.tsx` to prove agent capability loading and read-only workspace behavior on the real route.
  - Extended `src/IM/frontend/src/features/settings/nodes/nodes-page.test.tsx`, `src/IM/frontend/src/features/settings/settings-scroll-layout.test.tsx`, and `src/IM/frontend/src/app/router.test.tsx` to prove the new route and entry affordances.
- DoD:
  - C1/C2/C3 commits complete.
  - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M325/src/IM/frontend && npm test -- --runInBand agent-create agent-edit nodes-page settings-scroll-layout router` passes (19 tests passed).
  - TASKS/PROGRESS updated with evidence and rollback point.
