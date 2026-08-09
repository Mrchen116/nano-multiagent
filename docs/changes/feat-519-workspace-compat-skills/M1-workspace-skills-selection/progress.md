# feat-519-M1 progress

## Status

- State: implementation complete; independent gates pending.
- Executed base: `1d0c2cb45`.
- Baseline: 27 focused Python tests and 37 focused frontend tests passed.

## Outcome

Implemented the complete workspace compatibility and truthful Skill selection
slice across kernel/SDK, PA/CLI product composition, Gateway/IM persistence and
runtime projection, and the Web IM create/detail/chat surfaces.

## Implementation decisions

- One core root-sequence builder now owns ordered workspace and shared Skill
  read roots. PA uses `.nanoassistant`, `.claude`, `.codex`; Coding CLI uses
  `.nanocode`, `.claude`, `.codex`. `skill_manage` keeps its native writer root.
- `Kernel.list_shared_skills()` supplies node-create candidates without deriving
  a fake repo workspace. Agent capabilities continue to resolve the real Agent
  workspace, and PA projects `source_group` as workspace/global/compatibility.
- `skills_selection_mode` uses `default_discovery` and `explicit_allowlist`.
  Legacy absent mode retains the prior empty/non-empty semantics; explicit empty
  survives IM SQLite, Gateway YAML and operations, live snapshots, sessions,
  SlashPicker, Feishu reconciliation, and `skill_created` transitions.
- The shared selector renders default discovery as effectively selected, converts
  the first edit to explicit intent, exposes accessible grouped tri-state actions,
  and preserves selected names absent from the current capability payload.

## Evidence

- Focused Python implementation/contract/Gateway suites:
  - `pytest -q tests/unit/test_core_skill_resolution.py tests/unit/test_skill_manage_tool.py tests/unit/agent/test_kernel_list_capability_queries.py tests/unit/personal_assistant/test_gateway_upstream_reporter.py tests/unit/personal_assistant/test_gateway_launch.py tests/unit/personal_assistant/test_gateway_im_config_sync.py tests/unit/personal_assistant/test_skill_selection_mode.py tests/im_service/contract/test_agent_config_contract.py tests/im_service/contract/test_agent_create_contract.py tests/im_service/unit/test_repositories_agent_profile.py` → 115 passed.
  - `pytest -q tests/unit/agent/test_runtime_skill_resolution_same_source.py tests/unit/test_skill_view.py tests/unit/personal_assistant/test_gateway_launch.py tests/unit/personal_assistant/test_gateway_im_config_sync.py` → 50 passed.
- Focused frontend selector/API/create/detail/SlashPicker suite → 48 passed;
  selector and legacy-payload follow-up → 20 passed.
- `pytest -q -m 'not e2e'` → 3140 passed, 25 deselected.
- `npm test -- --run` → 635 passed across 66 files; only the pre-existing React
  `act(...)` and test-runtime socket warnings were emitted.
- `npm run build` passed; Vite retained its existing large-chunk warning.
- `ruff check src tests`, `ruff format --check src tests`, `git diff --check`, and
  `PYTHON=/Users/czj/miniforge3/bin/python ./scripts/docs-check` passed.

## Remaining gates

The orchestrator still owns real Coding CLI/PA/browser acceptance, independent
verifier/reviewer/code-review gates, canonical spec merge, archive, PR creation,
and remote CI. This worker intentionally did not run or mark those gates complete.

## Rollback

Revert the M1 implementation commit. The SQLite addition is nullable and Gateway
YAML omission remains readable, so rollback does not require destructive data
migration.
