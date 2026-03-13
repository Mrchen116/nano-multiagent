# M144 Acceptance Report

## Scope
- Milestone: M144 — Settings Center 真实 API 收口
- Review target: `/Users/czj/Repos/nano-multiagent/.worktrees/M144`
- Review date: 2026-03-13
- Goal: confirm `/settings/nodes`、`/settings/account`、`/settings/policies` have converged from page-level mocks onto real IM APIs, persist edits through the live backend, and remain usable from the IM-hosted frontend.

## Acceptance Basis
### 1. Required test gate
Executed milestone gate:
- `PYTHONPATH=src pytest -q tests/im_service/contract/test_account_binding_contract.py tests/im_service/contract/test_settings_policies_contract.py tests/im_service/integration/test_account_binding_api.py tests/im_service/integration/test_settings_policies_api.py tests/im_service/integration/test_nodes_metrics_api.py::test_nodes_list_and_config_update && npm --prefix src/IM/frontend test -- src/features/settings/nodes/nodes-page.test.tsx src/features/settings/account/account-page.test.tsx src/features/settings/policies/policies-page.test.tsx`

Result:
- Python: `8 passed in 0.37s`
- Frontend: `3 passed`

Additional build gate:
- `npm --prefix src/IM/frontend run build`
- Result: production bundle rebuilt successfully for the IM host.

### 2. Real browser and real API evidence
Reviewed live evidence captured against the real IM host at `http://127.0.0.1:8011` using Google Chrome via DevTools Protocol:
- `/Users/czj/Repos/nano-multiagent/.worktrees/M144/ACCEPTANCE/M144-settings-browser-evidence.json`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M144/ACCEPTANCE/M144-settings-nodes.png`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M144/ACCEPTANCE/M144-settings-account.png`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M144/ACCEPTANCE/M144-settings-policies.png`

Confirmed from evidence:
- `/settings/nodes` loads from the IM host and reads live node data, including status, heartbeat, and owned-node alias.
- Editing node alias persisted from `m135-node-baseline` to `m135-node-m144-final`, and the saved alias survived page reload plus `GET /im/v1/nodes` re-check.
- `/settings/account` loads the live `me` profile, including `user_id`, `owned_node_ids`, and `default_entry_node_id`.
- Editing account display name persisted from `You Baseline` to `You Ops M144 Final`, and the saved values survived page reload plus `GET /im/v1/me` re-check.
- `/settings/policies` loads from live `GET /im/v1/policies` rather than local mock state.
- Editing policies persisted from `baseline-model/basic/55` to `gpt-5.4-settings-final/strict/111`, and the saved values survived page reload plus `GET /im/v1/policies` re-check.

### 3. Runtime compatibility regression closure
The live browser run exposed one runtime-only failure in older DB states: `PATCH /im/v1/policies` could return 500 if the singleton `settings_policies` row was missing.

This was closed with:
- regression test: `/Users/czj/Repos/nano-multiagent/.worktrees/M144/tests/im_service/integration/test_settings_policies_api.py::test_policies_reseed_missing_singleton_row`
- repository auto-reseed fix in `/Users/czj/Repos/nano-multiagent/.worktrees/M144/src/IM/infra/repositories.py`

## Acceptance Decision
- Final verdict: Acceptable
- Blocking issues: 0 for the milestone scope
- Major issues: 0
- Minor issues: 1

Reasoning:
- The three settings pages now use real IM APIs instead of page-level mocks.
- The live browser evidence proves edits are not just accepted by the UI; they round-trip through the real backend and remain after reload.
- The late runtime singleton-row bug discovered during real verification was converted into a regression test and fixed before acceptance.

## Remaining Issue
### Minor 1: main-branch merge was not safe to execute from the canonical repo state
- `git -C /Users/czj/Repos/nano-multiagent status --short` showed unrelated dirty files in the canonical main worktree.
- To avoid polluting unrelated user state, this milestone records the merge blocker instead of forcing a merge.
- Milestone acceptance is still valid because the feature scope, tests, and live evidence are complete inside `/Users/czj/Repos/nano-multiagent/.worktrees/M144`.

## Merge Status
- Milestone branch: `milestone/M144`
- Merge to canonical `main`: not executed
- Blocker: unrelated dirty working tree in `/Users/czj/Repos/nano-multiagent`
- Safe next step: clean the canonical main worktree first, then perform the merge from the main repository.
