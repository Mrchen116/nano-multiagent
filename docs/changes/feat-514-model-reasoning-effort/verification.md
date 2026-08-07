# Verification Report: feat-514

> Validation snapshot: `f54e008b1 → 6e8413635`

## Summary

Mode: full
Delta range: N/A
Focus issues: N/A
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 4/5 M1 roadpoints demonstrably complete; R5 evidence and production delivery remain incomplete |
| Correctness | 10/10 requirements and 40/40 scenarios have implementation and permanent-test coverage |
| Coherence | Followed for the approved architecture and design decisions |

Validation run on this snapshot: 114 focused Python/contract tests passed; `ruff check` on the changed production and test surfaces, `scripts/docs-check`, and `git diff --check` passed. The implementation session also reported 611 frontend tests plus `npm run build` passed and an isolated browser journey completed. Its attempted full pytest run reached 1717 passed / 18 skipped before local file-descriptor exhaustion; the follow-up `--lf` run passed 108 tests. That host-resource interruption is not classified as a code finding.

## Completeness

- Tasks: R1--R4 are implemented and their permanent tests exist. R5 has a three-state isolated Gateway catalog in [config/e2e/gateway.yaml](../../../config/e2e/gateway.yaml), and the final runbook now identifies the bound isolated-browser account in [docs/development/worktree-runtime.md](../../development/worktree-runtime.md). However, the unit contains no durable 1440px/375px screenshot-and-comparison evidence, and no non-secret record that both production Gateway configurations were changed, restarted, and checked. See the CRITICAL findings below.
- Spec coverage: all four product requirements and all six delta requirements map to code and tests below.
- Prototype / Reference coverage: implementation reflects the five explicit prototype states, but the required durable proof is absent. The reported browser result alone is not a reviewable artifact under the prototype contract.

## Correctness

### Product spec requirements

| Requirement / Scenario | Implementation evidence | Permanent test evidence | Status |
|---|---|---|---|
| Selectable model shows only declared levels and its default | `src/IM/frontend/src/features/settings/agents/model-reasoning-field.tsx:112` | `model-reasoning-field.test.tsx:37`; create/edit form tests | covered |
| Platform-default model cannot carry standalone effort | `model-reasoning-field.tsx:82`; `model_reasoning.py:108` | `model-reasoning-field.test.tsx:62`; `test_parse_llm.py:219` | covered |
| Stale catalog keeps draft, blocks save, and asks for refresh | `model-reasoning-field.tsx:47`; `agent-create-page.tsx:521`; `agents.py:586` | `model-reasoning-field.test.tsx:101`; `agent-edit.test.tsx:366` | covered |
| Fixed model is informational only; switching clears effort | `model-reasoning-field.tsx:92`; `model-reasoning-field.tsx:25` | `model-reasoning-field.test.tsx:62`; `model-reasoning-field.test.tsx:116` | covered |
| Create saves model and effort for the first run | `agent_config_operations.py:94`; `session_composition.py:39` | `test_agent_create_contract.py:13`; `test_session_run_coordinator_real_kernel.py:141` | covered |
| Existing conversation adopts the pair only on its next run and retains history | `session_run_coordinator.py:1193`; `session_composition.py:58` | `test_session_run_coordinator_real_kernel.py:141` | covered |
| Failed or unknown save preserves an understandable draft | `agent_config_operations.py:67`; `agent-detail-page.tsx:1520` | `test_agent_config_operation_flow.py:50`; `agent-edit.test.tsx:438` | covered |
| Per-node configuration, not IM model-name logic, supplies options | `model_reasoning.py:79`; `upstream_reporter.py:75` | `test_parse_llm.py:180`; `test_gateway_upstream_reporter.py:163` | covered |
| Existing model level changes reach the form without a frontend release | `upstream_reporter.py:95`; `nodes.py:156` | `test_gateway_upstream_reporter.py:163`; frontend descriptor normalization tests | covered |
| New configured model remains node-scoped | `upstream_reporter.py:75`; `nodes.py:173` | `test_gateway_upstream_reporter.py:151`; `test_agent_config_contract.py:148` | covered |

### Delta-spec requirements and scenarios

| Requirement / Scenario set | Implementation evidence | Permanent test evidence | Status |
|---|---|---|---|
| Kernel complete runtime: create/read, reconfigure-next-run, fork, normal requests; hooks/approval remain independent | `src/agent/sdk/runtime.py:30`, `src/agent/core/agent/loop.py:378`, `src/agent/platform/llm/providers/{anthropic,openai_compat}/mapper.py` | `test_llm_reasoning_request_body.py:16`; `test_session_run_coordinator_real_kernel.py:141`; `test_session_run_coordinator_real_kernel.py:284` | covered |
| Gateway current model/effort applies to direct, retained-session, active-run, default-model, heartbeat, and cron admissions | `session_composition.py:39`; `session_run_coordinator.py:1198` | `test_parse_llm.py:196`; `test_session_run_coordinator_real_kernel.py:141` | covered |
| Gateway publishes safe selectable/fixed/absent capability descriptors and rejects invalid pairings before persistence | `model_reasoning.py:35`; `upstream_reporter.py:75`; `agent_config_sync.py:495` | `test_parse_llm.py:180`; `test_gateway_upstream_reporter.py:163`; `test_gateway_config_operation_validation.py:31` | covered |
| Gateway create/apply receipt protocol handles replay, ACK loss/status, all four crash cuts, operation-id reuse, and stale values | `agent_config_sync.py:345`; `config_apply_receipts.py:62` | `test_gateway_config_operations.py:32`; `test_gateway_config_operation_validation.py:31` | covered |
| IM profile/API exposes nullable effort, Gateway-first apply, 409 rejection, 503 pending, profile CAS compensation, and lost-create recovery | `agent_config_operations.py:67`; `agents.py:461`; `nodes.py:237` | `test_agent_config_contract.py:17`; `test_agent_config_operation_flow.py:50`; `test_agent_config_operation_flow.py:276`; `test_agent_config_operation_flow.py:351` | covered |
| IM capability endpoints and form consume only provider/name/reasoning descriptors and render selectable/fixed/default/absent/pending states | `agents.py:533`; `model-reasoning-field.tsx:67` | `test_agent_create_contract.py:13`; `model-reasoning-field.test.tsx:37`; `agent-create.test.tsx:514`; `agent-edit.test.tsx:438` | covered |

The regression tests use stable external seams: configuration parsing, Gateway RPC/receipt state, HTTP responses, provider packets, durable runtime identity, and rendered form behavior. The final split keeps both new Gateway operation test files below the repository's 400-line limit.

## Coherence

| Design decision | Followed? | Code evidence |
|---|---|---|
| D1: deployer declares absent/fixed/selectable levels; invalid schema rejects startup | Yes | `model_reasoning.py:35`; `local_store.py:1083` |
| D2: one PA-owned catalog resolves, validates, and projects the capability | Yes | `model_reasoning.py:79`; `composition.py:197`; `upstream_reporter.py:95` |
| D3: provider-neutral runtime field, static-body merge at provider client, adapter-specific last-hop rendering | Yes | `session_composition.py:58`; `request_body.py:11`; `anthropic/mapper.py:88`; `openai_compat/mapper.py:42` |
| D4: nullable profile/config persistence and Gateway-side validation | Yes | `IM/domain/models.py:109`; `IM/infra/db.py:727`; `agent_config_sync.py:501` |
| D5: write-ahead prepared intent, workspace-before-config, CAS, live convergence, terminal receipt, IM recovery/compensation | Yes | `agent_config_sync.py:410`; `agent_config_sync.py:495`; `agent_config_operations.py:129`; `config_apply_receipts.py:62` |
| D6: model and effort are adjacent dependent fields with fixed/default/stale/pending truthfulness | Yes | `agent-create-page.tsx:765`; `agent-detail-page.tsx:1849`; `model-reasoning-field.tsx:81` |
| Cross-package and process boundaries | Yes | `tests/contract/test_cli_sdk_only_contract.py` and `test_core_no_platform_imports.py` passed; IM communicates with Gateway via its existing WS control protocol and does not import `agent` |

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| Create/detail model then reasoning order, fixed, default, stale, and pending states at 1440px and 375px | `design.md:323-326`, M1 exit criterion | `agent-create-page.tsx:765`; `agent-detail-page.tsx:1849`; `model-reasoning-field.tsx:81` | No screenshot/comparison or unit acceptance artifact is present | critical |

## Issues

### CRITICAL（提 PR 前必须修）

- **[V1] The prototype must-match contract has no reviewable browser evidence.** `docs/changes/feat-514-model-reasoning-effort/design.md:323-326` requires real create/detail checks at both 1440px and 375px and specifically projects a worker screenshot-to-prototype comparison. The final branch has no `evidence/`, acceptance record, screenshots, or comparison locator. The reported isolated browser journey establishes useful context, but without an in-repo/unit artifact it cannot prove all five must-match states. Run and record the desktop/mobile create and detail checks, store redacted screenshots plus a brief state-by-state comparison under this unit, and link the exact paths from the M1 record.

- **[V2] The required two-node production configuration and verification are not evidenced.** `docs/changes/feat-514-model-reasoning-effort/design.md:438-441` and the M1 exit criterion at `design.md:451` require mac-mini and macbook-air Gateway configuration, restart, lifecycle/node-identity/capability checks, and a real message. No non-secret rollout record exists in the unit and `config/e2e/gateway.yaml:41-57` is only an isolated test catalog. Execute the documented per-host stop/edit/start/verify sequence, then add a redacted unit evidence record with time, node identity, model descriptors, lifecycle outcome, and real-message outcome; do not commit configs, credentials, logs, or secrets.

### WARNING（提 PR 前必须修）

- None.

### SUGGESTION（可以修）

- None.

2 critical issue(s), 0 warning(s) found. Fix before PR.
