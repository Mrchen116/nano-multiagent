# feat-519-M1 progress

## Status

- State: delivery complete; verifier, acceptance, code review, corrected-delta,
  canonical merge, and local CI-equivalent gates passed.
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
- IM and Gateway now hash the same canonical `skills_selection_mode` field.
  Gateway validates it through the existing selection-mode helper, while its
  local previous-state projection retains the persisted raw mode so legacy
  absence remains hashable without eager migration.
- Config operations use one current canonical fingerprint, including the effective
  selection intent, through initial submit, resubmit, status recovery,
  compensation, and terminal idempotency. They do not negotiate a schema or retain
  mixed-version fallback, receipt replay, or operation migration paths.
- Distillation readiness now honors the effective selection mode on both Gateway
  and Web IM: explicit mode must actually include `conversation-skill-distiller`,
  including rejecting explicit empty before any prompt is generated.
- A successful Agent detail save invalidates the shared
  `['chat', 'slash-skills']` query prefix, so returning to an existing conversation
  cannot reuse the prior 60-second candidate set.
- `source=mirror` preserves raw legacy `skills_selection_mode=None`; live/default
  reads and write responses remain effective. Frontend normalization retains the
  effective UI contract, while reconnect reconciliation no longer rewrites legacy
  empty or non-empty YAML merely because the mirror was read.

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
- Acceptance round-one fingerprint follow-up:
  - TDD red: five IM/Gateway parity cases (`legacy absent`, `legacy null`,
    `default_discovery`, explicit non-empty, explicit empty) all produced unequal
    fingerprints, and a real explicit-empty `handle_agent_config_operation()`
    apply returned `rejected`.
  - Root cause: IM's canonical fingerprint schema included
    `skills_selection_mode`, but Gateway omitted it; additionally, Gateway's
    local previous-state projection converted persisted legacy absence to an
    effective mode, which would conflict after adding the missing canonical key.
  - `pytest -q tests/unit/personal_assistant/test_gateway_config_operation_validation.py
    tests/unit/personal_assistant/test_gateway_config_operations.py
    tests/unit/personal_assistant/test_gateway_im_config_sync.py` → 42 passed.
  - `pytest -q tests/im_service/unit/test_agent_config_operations.py
    tests/im_service/integration/test_agent_config_operation_flow.py` → 15 passed.
  - The combined related suite passed 57 tests; `ruff check src tests`,
    `ruff format --check src tests`, `git diff --check`, and
    `PYTHON=/Users/czj/miniforge3/bin/python ./scripts/docs-check` also passed.
- Code-review fix round:
  - TDD red: backend schema tests could not import the absent v1/v2 protocol API;
    the explicit-empty frontend distill journey generated a prompt; and Agent
    detail save invalidated only the settings cache. Mirror contract tests also
    observed effective modes instead of raw `None`.
  - Rolling protocol and recovery suites, including old/new Gateway WS paths,
    legacy receipt replay, SQLite migration, compensation, distill, mirror
    reconciliation, and config validation → 132 passed. The consolidated related
    IM/Gateway/DB suite → 109 passed.
  - Frontend chat integration, chat API, SlashPicker, Agent detail, and config API
    suites → 112 passed. `npm run build` passed with the existing Vite large-chunk
    warning.
  - `pytest -q -m 'not e2e'` → 3169 passed, 25 deselected; only existing dependency,
    deprecation, and test-key warnings were emitted.

- Final delivery gates:
  - Change-code-review closure returned `[]`; all four confirmed findings closed.
  - Verification round 4 passed with no issue; corrected-delta verification found
    no delta or implementation mismatch.
  - Product acceptance round 4 passed with no blocking, major, or minor issue on
    a fresh IM/Gateway/browser stack.
  - Final local CI-equivalent run: Ruff check/format passed; Python non-E2E
    `3169 passed`; frontend critical audit passed and Vitest `640 passed` across
    66 files; canonical requirement merge comparison and docs-check passed.

## Delivery status

The implementation and local delivery gates are complete. The orchestrator archives
this unit before opening the Ready PR; branch and remote CI status remain live GitHub
state and are intentionally not copied into this progress snapshot.

### User-directed R5 scope correction

The user explicitly rejected v1/v2 fingerprint-schema negotiation as redundant
backward compatibility. The follow-up removes the mixed-version protocol, old
operation/receipt recovery and schema persistence while retaining current-version
operation retry, lost-ACK recovery, compensation, and legacy profile-mode reads.

- Focused protocol suite: 54 passed.
- Expanded IM/Gateway/contract suite: 115 passed.
- Frontend Agent-config/chat suite: 86 passed across 3 files.
- Ruff, Python compile, `git diff --check`, and docs-check passed.
- Patch-mode change-code-review found no actionable issue; an independent verifier
  rechecked the deleted protocol surface and same-version recovery coverage.

## Rollback

Revert the M1 implementation commits. The Skill-selection SQLite addition is
nullable and Gateway YAML omission remains readable, so rollback requires no
destructive data migration.
