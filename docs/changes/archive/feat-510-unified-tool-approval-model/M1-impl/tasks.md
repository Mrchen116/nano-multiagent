# M1 Implementation Tasks

## Scope

- Parse, validate, preserve, and compose optional PA `llm.tool_approval_model`.
- Add the public Kernel build choice between an explicit classifier model and the current run model.
- Route both auto-mode classifier stages through the Kernel-scoped choice without changing normal Agent turns or fallback policy.
- Add deterministic tests at config, hook, SDK contract, composition, and real PA/Gateway critical-path layers.
- Update the Gateway runbook, then complete independent product, implementation, and code-review gates.

## Test strategy

| Behavior | Existing coverage | Change |
|---|---|---|
| PA LLM parse/save/reload | `tests/unit/personal_assistant/config/test_parse_llm.py` | Extend for explicit, omitted, blank, and unregistered approval model. |
| Gateway composition | `tests/unit/personal_assistant/test_gateway_build_runtime.py` | Add focused propagation assertion through `build_pa_kernel`. |
| Auto gate stages and failure | `tests/unit/test_auto_mode_gate_hook.py` | Extend existing hook harness; assert stage 1/stage 2 model and no alternate-model retry. |
| Public Kernel contract | `tests/contract/test_sdk_kernel_wiring.py` | Add explicit/implicit build validation and normal-classifier-normal request sequence. |
| PA user journey | No existing approval-model routing E2E | Add `test_tool_approval_model_critical_path.py` using real IM/Gateway and a deterministic recording Anthropic fixture. |

## Roadpoints

- [x] Record clean worktree and focused pre-change baseline.
- [x] Add failing tests for PA config and composition.
- [x] Add failing tests for Kernel-scoped dependency and auto gate routing.
- [x] Implement the smallest config/SDK/platform changes that make them pass.
- [x] Add and pass the deterministic real-stack critical path.
- [x] Update operations documentation and record all evidence in `progress.md`.
- [x] Complete independent product, implementation, code-review, and corrected-delta gates.
- [x] Merge the final delta into canonical specs and archive the unit.
- [ ] Complete local CI, PR creation, and required remote CI.

## Exit criteria

The M1 exit criteria in `design.md` are all covered by reproducible commands or independent gate reports, with no changes to Coding CLI behavior, permission policy, or runtime fallback semantics.
