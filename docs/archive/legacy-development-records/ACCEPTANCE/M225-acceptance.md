# M225 Acceptance

## Scope
- Milestone: M225 — 重做新增 Agent 页面信息架构与视觉收口
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M225`
- Branch: `milestone/M225`
- Date: 2026-03-17

## Verdict
- Verdict: pass
- Focus: create/detail/list/allowlist 页面信息架构、workspace 语义统一、真实页面证据

## Runtime used for this acceptance
- App URL: `http://127.0.0.1:8013/settings/agents`
- Runtime DB: `/Users/czj/Repos/nano-multiagent/.worktrees/M225/ACCEPTANCE/m225-runtime/im_service.sqlite3`
- Frontend dist: `/Users/czj/Repos/nano-multiagent/.worktrees/M225/src/IM/frontend/dist`
- Seeded agents:
  - `agent-m225-default`
  - `agent-m225-custom`

## Automated gate
- Frontend:
  - `npx pnpm --dir src/IM/frontend test -- --run agent-create agent-detail agents-list-mobile allowlist-selector router`
  - Result: `20 passed, 93 passed`
- Backend:
  - `PYTHONPATH=src pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py`
  - Result: `9 passed in 0.45s`

## Real page evidence
- Agents list screenshot: `/Users/czj/Repos/nano-multiagent/.worktrees/M225/ACCEPTANCE/m225-runtime/m225-agents-list.png`
- Create page screenshot: `/Users/czj/Repos/nano-multiagent/.worktrees/M225/ACCEPTANCE/m225-runtime/m225-agent-create.png`
- Detail page screenshot: `/Users/czj/Repos/nano-multiagent/.worktrees/M225/ACCEPTANCE/m225-runtime/m225-agent-detail-custom.png`
- Observations JSON: `/Users/czj/Repos/nano-multiagent/.worktrees/M225/ACCEPTANCE/m225-runtime/m225-ui-observations.json`

## Product acceptance notes

### 1. Create page is now focused on creation decisions
- Real page heading is `Create Agent`.
- The old right-rail checklist is gone; there is no `Before you create` section in the real page.
- The create flow is organized as `Identity`, `Behavior`, `Access & model`, and `Runtime`, keeping nonessential guidance out of the first screen.
- Runtime copy now separates:
  - `Workspace setting`
  - `Directory from current setting`
  - `Managed default directory`
  - `Current runtime directory appears after the agent is created.`

### 2. Workspace semantics are no longer misleading
- Create page no longer presents `Workspace preview` as if it were the live runtime path.
- Detail page shows `Current runtime directory`, `Managed default directory`, and editable `Workspace setting` together, with distinct explanatory copy.
- For the seeded custom agent, the real detail page shows:
  - live runtime: `/private/tmp/m225-custom-workspace`
  - managed default: `~/nano-assistant/workspace/agent-m225-custom`
- This closes the earlier ambiguity between saved setting, managed default, and real runtime directory.

### 3. Allowlist noise is reduced on the real pages
- The create page no longer shows `Selected N` badges or `Show advanced options` expanders.
- The detail page keeps already-saved non-standard items visible under `Needs review` instead of mixing them into the main path.
- Real detail evidence shows:
  - `tdd-execution-worker` remains visible under `Needs review`
  - unavailable saved skill `plan` is labeled `Unavailable now`
  - saved advanced tool `bash` stays visible under review without reintroducing the old noisy affordances

### 4. List/create/detail wording is aligned
- List page subtitle is `Review each agent's role, access, and runtime placement before opening settings.`
- List cards use `Runtime` and `Access` instead of the older `Workspace` and `Routing` split.
- Create and detail pages both use the same `Runtime` terminology and the same workspace distinctions.
- The misleading `Read-only runtime path` wording is no longer present on the detail page.

### 5. Delta vs M224
- M224 fixed the underlying runtime/workspace semantics.
- M225 closes the remaining product-layer IA issues:
  - create page first-screen overload
  - right-rail noise
  - allowlist chip/badge/advanced-expander clutter
  - inconsistent wording between list/create/detail
  - confusing workspace copy that looked like a live pwd preview

## Acceptance conclusion
M225 meets its exit criteria. The real settings pages now present a smaller and more consistent decision surface, workspace language is explicitly separated into saved/default/live concepts, and allowlist UI no longer exposes the prior high-noise structure on the main path.
