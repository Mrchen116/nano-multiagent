# feat-519-M1 progress

## Status

- State: implementation complete; verifier round-one implementation fixes complete;
  independent gates pending.
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
- Static Feishu bundle reconciliation now persists `explicit_allowlist` when it
  actually appends names to a legacy non-empty allowlist. It leaves legacy/default
  zero-Skill selections and already-complete legacy allowlists unmigrated.
- Kernel session creation preserves the distinction between omitted Skills and an
  explicit empty allowlist. A real-session regression verifies both the stored
  runtime and model/tool boundary, including rejection of `skill_view` without
  exposing the discovered Skill body.
- Agent detail prompt preview projects the effective selection rather than the
  stored names alone: default discovery sends the current capability names, while
  explicit mode sends the exact allowlist, including empty.
- Lost-ACK recovery keeps explicit-empty Skill intent in the durable candidate,
  canonical fingerprint, Gateway apply payload, and committed IM profile. The
  existing CAS-loss compensation path now protects the same tri-state fields.

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
- Gate follow-up: `pytest -q tests/unit/personal_assistant/test_gateway_launch.py`
  → 10 passed, including the persisted YAML regression. The expanded Gateway
  reconciliation suite → 47 passed.
- Verifier round-one focused regressions:
  - `pytest -q tests/integration/test_empty_skill_allowlist_wiring.py` → 1 passed.
  - `pytest -q tests/im_service/integration/test_agent_config_operation_flow.py -k
    'explicit_empty or compensation'` → 2 passed.
  - `npm test -- --run
    src/features/settings/agents/agent-detail-page.test.tsx` → 18 passed; only
    pre-existing React `act(...)` warnings were emitted.
- Verifier round-one expanded regression suites:
  - `pytest -q tests/integration/test_empty_skill_allowlist_wiring.py
    tests/integration/test_empty_tool_allowlist_wiring.py
    tests/integration/test_session_run_coordinator_real_kernel.py
    tests/im_service/integration/test_agent_config_operation_flow.py
    tests/im_service/unit/test_agent_config_operations.py` → 16 passed.
  - `npm test -- --run
    src/features/settings/agents/agent-detail-page.test.tsx
    src/features/settings/agents/agent-edit.test.tsx
    src/features/settings/agents/im-agent-config-api.test.ts` → 39 passed; only
    pre-existing React `act(...)` and test-runtime warnings were emitted.
  - `npm run build` passed; Vite retained its existing large-chunk warning.
  - `ruff check src tests`, `ruff format --check src tests`, `git diff --check`,
    and `PYTHON=/Users/czj/miniforge3/bin/python ./scripts/docs-check` passed.

## Remaining gates

The orchestrator still owns real Coding CLI/PA/browser acceptance, independent
verifier/reviewer/code-review gates, canonical spec merge, archive, PR creation,
and remote CI. This worker intentionally did not run or mark those gates complete.

## Rollback

Revert the M1 implementation commit. The SQLite addition is nullable and Gateway
YAML omission remains readable, so rollback does not require destructive data
migration.
