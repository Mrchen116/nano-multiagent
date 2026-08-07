# Verification Report: refactor-513-pa-workspace-layout

> Validation snapshot: `f54e008b1 → e0e61f779`

## Summary

Mode: full  
Delta range: `f54e008b1..e0e61f779`  
Focus issues: N/A  
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 2/3 milestones verifiable; M1 has one mandatory, unproven scope-isolation exit criterion |
| Correctness | Core/default, PA, CLI, IM and migration contracts are substantially implemented; 3 behavior/design deviations remain |
| Coherence | Product/SDK/IM dependency boundaries are followed; D4 and PA's residual default persistence path diverge from the frozen design |

## Completeness

- M1: code delivers the planned `WorkspaceLayout`, cached scope resolver, selected tools/hooks/policy/output roots and per-turn `ContextVar` propagation (`src/agent/core/workspace/layout.py:15-115`, `src/agent/sdk/kernel.py:514-592`, `src/agent/core/agent/runtime.py:273-350`, `src/agent/core/agent/loop.py:238-247`).  However, its frozen concurrent pre-tool-chain and nested-path exit criterion is not demonstrated by durable tests; see C1.
- M2: PA/IM final paths, explicit external-workspace handling, chat history, heartbeat/RPC paths, manual deployment prompt and terminal runtime behavior are implemented (`src/personal_assistant/config/local_store.py:70-138,1095-1108`, `src/personal_assistant/product.py:373-431`, `src/personal_assistant/hooks/chat_history.py:94-119`, `src/personal_assistant/scheduler/heartbeat_scheduler.py:349-350`, `src/IM/domain/models.py:8-41`, `docs/operations/pa-workspace-layout-migration.md:35-106`).  The remaining residual PA default is W3.
- M3: CLI passes `.nanocode` both as its workspace configuration dirname and global auto-mode root (`src/coding_cli/product.py:121-155`), while PA-only chat/heartbeat remain absent from CLI.  Its selected-root policy behavior has a real integration test (`tests/integration/test_bash_engine.py:190-214`).
- No frontend prototype/reference contract is declared in `design.md`; N/A.

## Correctness

| Requirement / Scenario | Implementation evidence | Durable regression evidence | Status |
|---|---|---|---|
| Unspecified SDK consumers retain `.nano` | `WorkspaceLayout.config_dirname` defaults to `.nano` and `build_kernel` supplies the same default (`src/agent/core/workspace/layout.py:15-34`, `src/agent/sdk/kernel.py:304-318`) | `tests/unit/agent/test_workspace_execution_scope.py:106-117` | covered |
| Session-local custom tools/hooks, policy, background output and optional global auto-mode config | Scope construction selects `layout.{tools,hooks,policy,background_tasks,tool_results}` and an optional global root (`src/agent/sdk/kernel.py:539-592`); Bash consumes scope metadata (`src/agent/platform/tools/builtins/bash.py:689-697`) | `tests/unit/agent/test_workspace_execution_scope.py:83-173`; `tests/integration/test_bash_engine.py:190-214` | partial — C1, W1 |
| PA workspace files belong below `.nanoassistant` and readable history remains a non-transcript copy | PA factory selects `.nanoassistant`; hook appends `ts`/`role`/`content` below selected config root; scheduler and RPC select its `HEARTBEAT.md` | `src/personal_assistant/product.py:413-431`; `src/personal_assistant/hooks/chat_history.py:94-119`; `src/personal_assistant/scheduler/heartbeat_scheduler.py:349-350`; `src/personal_assistant/ws/im_connection.py:1228-1250` | `tests/unit/personal_assistant/test_chat_history_hook.py:104-175`; affected heartbeat/RPC suite in the command below | covered |
| PA global home/default workspace and IM-owned managed-default classification | PA config/default workspace derives `~/.nanoassistant/workspaces`; IM independently uses the same path without product imports | `src/personal_assistant/config/local_store.py:70-71,1095-1108`; `src/personal_assistant/gateway/agent_config_sync.py:691-704`; `src/IM/domain/models.py:8-41` | `tests/unit/personal_assistant/test_local_store.py:56-122`; IM contract/integration tests | partial — W3 |
| CLI workspace state uses `.nanocode`, without PA history/heartbeat | CLI passes `.nanocode` and `~/.nanocode`; PA hook is registered only by PA | `src/coding_cli/product.py:121-180`; `src/personal_assistant/product.py:413-431` | `tests/unit/test_cli_product_workspace_layout.py:11-30`; `tests/contract/test_cron_coding_cli_isolation.py:7-39` | covered |
| Migration is manual, conflict-safe and preserves source/relative legacy data | No product startup migration branch is added; the maintained runbook preflights conflicts, preserves external workspace legacy data, and validates source/target secret equality and mode before shutdown | `docs/operations/pa-workspace-layout-migration.md:22-31,35-106` | Operations procedure is a manual artifact; source scan found no runtime legacy migration/sync path | covered |
| Product-selected policy must win over legacy `.nano/policy.toml` | Scope loads `layout.policy`; Bash reads only injected overrides | `src/agent/sdk/kernel.py:580-589`; `src/agent/platform/tools/builtins/bash.py:217-269` | `tests/integration/test_bash_engine.py:190-214` | covered |
| Kernel `list_session_tools` returns a session's selected tool set | Scope registry is selected before the method returns | `src/agent/sdk/kernel.py:1702-1712` | Existing tests cover only an unknown/no-allowlist session (`tests/contract/test_kernel_sdk_behavior_contract.py:500-509`) | deviates — W1 |

### Delta-spec reconciliation within this full review

All final delta areas have canonical carriers and match the intended implementation shape: kernel SDK boundary/background/tools-hooks (`docs/specs/kernel/sdk-boundary.md`, `docs/specs/kernel/background-tasks.md`, `docs/specs/kernel/tools-hooks.md`); PA Gateway routing/lifecycle/heartbeat (`docs/specs/gateway/routing-delivery.md`, `docs/specs/gateway/service-lifecycle.md`, `docs/specs/gateway/heartbeat-cron.md`); IM managed default (`docs/specs/im/agents-nodes.md`); and CLI integration (`docs/specs/cli/product-integration.md`).  W1 is also a direct mismatch with the kernel tools-hooks `list_session_tools` scenario.  No additional changed external behavior was found without a delta/canonical carrier.

The following verification command was executed at the validation snapshot:

```text
PYTHONPATH=src .venv/bin/python -m pytest -q [M1/M2/M3 affected suites + SDK/product/core boundary contracts]
306 passed, 1 failed
```

The sole failure was `tests/unit/agent/background_tasks/test_platform_adapters.py::test_shell_runner_runs_in_dedicated_process_group`: this macOS sandbox refuses `/bin/ps` (`zsh: operation not permitted: /bin/ps` when invoked directly), so the child process emits an empty PGID. It is an environment limitation, not a refactor-513 behavior failure. `PYTHON=/Users/czj/Repos/nano-multiagent/.venv/bin/python scripts/docs-check`, focused `ruff check`, and `git diff --check f54e008b1..e0e61f779` all passed.

## Coherence

| Design decision | Result | Evidence |
|---|---|---|
| D1: pure core `WorkspaceLayout` | followed | Frozen path-only dataclass (`src/agent/core/workspace/layout.py:15-82`) has no platform/product import. |
| D2: first-use cached workspace extension scopes | followed | SDK clones the base registrations and loads only selected workspace paths (`src/agent/sdk/kernel.py:539-592`, `src/agent/core/tools/registry.py:84-96`, `src/agent/core/hooks/registry.py:123-140`). |
| D3: immutable per-turn scope, no mutable shared Engine switching | followed in implementation; mandatory concurrent proof absent | Scope is held in `ContextVar`s and metadata is immutable (`src/agent/core/agent/runtime.py:273-350,1494-1513`, `src/agent/core/agent/loop.py:238-247,687-689`); C1 covers the absent proof. |
| D4: every selected runtime artifact and the four-directory safety set | not followed | The new path selection is wired, but the declared `.nano`, `.nanoassistant`, `.nanocode`, `.nano-assistant` safety set is not (`design.md:85-89`; `src/agent/platform/tools/dangerous_paths.py:46-55`); see W2. |
| D5: PA single home and IM independence | followed except residual public default | Production composition puts binding state below `config.source_path.parent` (`src/personal_assistant/gateway/composition.py:221-247`); IM remains standalone (`src/IM/domain/models.py:1-41`); W3 remains. |
| D6/D7: terminal runtime paths; manual, no-rotation migration | followed | The maintained operations prompt performs secret preflight before stopping IM and retains the old source until both Gateways are online (`docs/operations/pa-workspace-layout-migration.md:47-61,85-106`). |

Architecture contracts were re-run: product-to-SDK and product-sibling import boundaries passed (`tests/contract/test_agent_sdk_boundary_contract.py`, `tests/contract/test_cli_sdk_only_contract.py`, `tests/contract/test_core_no_platform_imports.py`). No product→`agent.core`/`agent.platform`, product-to-product, or IM-to-agent import was introduced.

## Issues

### CRITICAL（提 PR 前必须修）

- **C1 — M1's mandatory concurrency and scope-propagation exit criterion is not proved.** `design.md:212` explicitly requires two *concurrent* workspaces with conflicting tools/hooks/auto-mode/policy through the real `auto_mode_gate` pre-tool chain, plus main run, subagent, slash skill, fork/compaction and `list_session_tools` scope coverage. The new scope suite only inspects registries and runs workspace A then B serially (`tests/unit/agent/test_workspace_execution_scope.py:83-173`); its only actual pre-tool test is a single workspace policy (`tests/integration/test_bash_engine.py:190-214`). Add durable integration-level tests that run both sessions via `asyncio.gather`, assert conflicting hook/tool/auto-mode/policy results and output roots do not cross, then exercise the named nested execution paths with workspace-specific extensions. Do not mark M1 complete until those frozen exit conditions are evidenced.

### WARNING（提 PR 前必须修）

- **W1 — `Kernel.list_session_tools` crashes for every existing session with an explicit enabled-tool allowlist.** `ToolRegistry.list_specs()` returns a tuple (`src/agent/core/tools/registry.py:122-141`), but the new filtering branch calls `specs.items()` (`src/agent/sdk/kernel.py:1707-1712`). A direct SDK reproduction — create a `.consumer` session with `enabled_tools=['read']`, then call `list_session_tools` — raises `AttributeError: 'tuple' object has no attribute 'items'`. Filter by `spec.name` and return the public shape expected by CLI, then add a custom-directory, explicit-allowlist regression test; current coverage at `tests/contract/test_kernel_sdk_behavior_contract.py:500-509` never creates such a session.

- **W2 — D4's declared safety boundary omits both the default `.nano` and retained legacy `.nano-assistant` directories.** The frozen design requires all four `.nano`, `.nanoassistant`, `.nanocode`, `.nano-assistant` directories to be sensitive (`docs/changes/refactor-513-pa-workspace-layout/design.md:85-89`), while `DANGEROUS_DIRECTORIES` contains only the new two (`src/agent/platform/tools/dangerous_paths.py:46-55`) and its changed test freezes that incomplete set (`tests/unit/agent/platform/tools/test_dangerous_paths.py:38-47,78-95`). Add both missing names and path-level tests. Keeping the legacy directory in the safety guard is not a runtime fallback or synchronization path.

- **W3 — the PA binding-store default still creates persistent data under the retired global home.** `PersistentSessionBindingStore()` without an override says and constructs `~/.nano-assistant/session_bindings.sqlite3` (`src/personal_assistant/gateway/session_keys.py:624-640`), contradicting the single-home D5 contract (`docs/changes/refactor-513-pa-workspace-layout/design.md:91-95`) and terminal-runtime requirement. Production composition currently passes the new config-parent path (`src/personal_assistant/gateway/composition.py:221-247`), but this remaining product default is still reachable and will silently recreate the legacy root. Change the default to `~/.nanoassistant/session_bindings.sqlite3` (or require an explicit path) and add a HOME-isolated regression test.

### SUGGESTION（可以修）

- The public SDK docstrings still describe workspace tools/hooks as literal `<repo_root>/.nano/...` (`src/agent/sdk/kernel.py:283-289,487-499`), and development worktree guidance still names the retired default config path (`docs/development/worktree-runtime.md:14-20`). Update these explanations to say “the selected workspace configuration directory” and `~/.nanoassistant/config.yaml`, respectively, so operator/developer guidance matches the new terminal layout.

1 critical issue(s), 3 warning(s) found. Fix before PR.

# Round 2

> Targeted-closure snapshot: `e0e61f779 -> 533082563`

## Summary

Mode: targeted-closure

Focus: Round 1 C1, W1, W2, W3.

Verdict: **fail**. W1, W2, and W3 are closed. C1 remains a release-blocking
coverage gap because the newly added real concurrent chain does not exercise all
of the frozen M1 execution boundaries.

requires_full_verification: false. The fix is narrowly scoped to the reported
closure items and does not change the architecture reviewed in Round 1.

## Validated closure items

| Prior issue | Result | Evidence |
|---|---|---|
| W1: `list_session_tools` public result and explicit allowlist | closed | `Kernel.list_session_tools` filters the tuple returned by the registry on `spec.name` and builds the dict payload consumed by CLI (`src/agent/sdk/kernel.py:1713-1728`). A real `.nanocode` session created with `enabled_tools=['read']` returned only `read`, and `coding_cli.commands._print_tools_summary` rendered it as `Tools for session <id> (1):`. Contract and CLI REPL coverage passed. |
| W2: four protected config directory names | closed | `DANGEROUS_DIRECTORIES` now contains `.nano`, `.nano-assistant`, `.nanocode`, and `.nanoassistant` (`src/agent/platform/tools/dangerous_paths.py:50-58`), with exact-set and path-level regression cases (`tests/unit/agent/platform/tools/test_dangerous_paths.py:38-109,164-169`). |
| W3: PA binding-store implicit home | closed | The default and docstring now select `~/.nanoassistant/session_bindings.sqlite3` (`src/personal_assistant/gateway/session_keys.py:624-640`); a HOME-isolated test verifies it neither creates nor reads the retired path (`tests/unit/personal_assistant/test_persistent_session_binding_store.py:153-166`). |
| C1: concurrent scope isolation | partial; still critical | The new test uses `asyncio.gather` for two real runs and proves workspace tool/hook selection, `auto_mode_gate` permission passage, bash policy passage, selected background-output roots, forked-run scope, and `list_session_tools` (`tests/unit/agent/test_workspace_execution_scope.py:277-339`). It is materially stronger than Round 1, but does not execute the frozen M1 `subagent`, slash-skill, or compaction paths. |

## Remaining issue

### CRITICAL

- **C1 — M1 still lacks execution evidence for three explicitly required scope boundaries.** The frozen exit criterion requires main run, subagent, slash skill, fork/compaction, and `list_session_tools` to use the same workspace scope (`design.md:212`). The added concurrent test executes main runs, a forked follow-up, and `list_session_tools` (`tests/unit/agent/test_workspace_execution_scope.py:294-315`), but it never creates a subagent, invokes a slash skill, or calls `Kernel.compact`. Static inspection shows scope is seeded for compaction (`src/agent/core/agent/runtime.py:309-326`) and the current registry is used by slash-skill dispatch (`src/agent/core/agent/runtime.py:558-568,1603-1613`), but that is not the required executable evidence and does not cover a real subagent path. Add durable workspace-specific extension tests for those three paths (using conflicting A/B workspace markers) before calling M1 complete.

### SUGGESTION

- W1 is functionally closed, but its new durable tests cover the payload shape and CLI renderer separately, not an explicit enabled-tool allowlist through the real CLI command. Preserve the direct verification above with a small regression test so a future return to an unfiltered tuple or incompatible item shape is caught automatically.

# Round 3

> Targeted-closure snapshot: `e3913749d -> 3f0147b1c`

## Summary

Mode: targeted-closure

Focus: Round 2's remaining C1 only.

Verdict: **pass**. The frozen M1 scope-propagation exit criterion now has
executable evidence for every previously missing side-entry boundary. Splitting
the regression suite for the 400-line contract retains that evidence unchanged.

requires_full_verification: false. This delta only restructures the targeted
regression coverage; it leaves the reviewed runtime architecture unchanged.

## C1 closure evidence

| Required boundary | Executable evidence | Result |
|---|---|---|
| Concurrent slash skills | Two sessions in distinct `.consumer` workspaces run `/skill:scope-a` and `/skill:scope-b` with `asyncio.gather`; each reaches the real `skill_view` tool and each transcript contains only its own workspace SKILL.md content (`tests/unit/agent/test_workspace_scope_side_entry_points.py:119-183`). | covered |
| Real `AgentTool` subagent execution | A parent turn calls the registered `agent` tool, which creates a child session and drives that child through the workspace-only `scope_probe_child` extension. The test observes the parent `agent` tool end, the child's actual tool result, and the child workspace hook transform (`tests/unit/agent/test_workspace_scope_side_entry_points.py:132-191`). | covered |
| Compaction skill reinjection | The test manually compacts the first slash-skill session through `Kernel.compact`; full compaction replaces its transcript, and the retained `<system-reminder>` has only the session's own skill content (`tests/unit/agent/test_workspace_scope_side_entry_points.py:136-183`). This exercises runtime's current-scope compaction path and its post-compact skill reloader (`src/agent/core/agent/runtime.py:309-326,1975-2017,2035-2114`). | covered |

The companion main-run regression still supplies the complementary concurrent
pre-tool proof: conflicting workspace tools/hooks, auto-mode configuration,
bash policy, background-output roots, fork follow-up, and `list_session_tools`
(`tests/unit/agent/test_workspace_execution_scope.py:190-247`). Together, the
two executable paths satisfy M1's full scope list in `design.md:212`.

## Checks run

```text
Round 2:
PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q \
  tests/unit/agent/test_workspace_execution_scope.py \
  tests/unit/agent/test_kernel_nano_tools_override.py \
  tests/unit/agent/platform/tools/test_dangerous_paths.py \
  tests/unit/personal_assistant/test_persistent_session_binding_store.py \
  tests/contract/test_kernel_sdk_behavior_contract.py \
  tests/unit/test_cli_repl_commands.py
120 passed

PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q \
  tests/integration/test_bash_engine.py \
  tests/unit/personal_assistant/test_local_store.py \
  tests/unit/personal_assistant/test_product_workspace_layout.py \
  tests/unit/test_cli_product_workspace_layout.py \
  tests/contract/test_agent_sdk_boundary_contract.py \
  tests/contract/test_cli_sdk_only_contract.py \
  tests/contract/test_core_no_platform_imports.py \
  tests/contract/test_kernel_sdk_behavior_contract.py
84 passed

Round 3:
PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q \
  tests/unit/agent/test_workspace_execution_scope.py \
  tests/unit/agent/test_workspace_scope_side_entry_points.py \
  tests/contract/test_test_naming_and_size_contract.py \
  tests/unit/agent/test_kernel_nano_tools_override.py \
  tests/integration/test_bash_engine.py \
  tests/contract/test_kernel_sdk_behavior_contract.py \
  tests/contract/test_agent_sdk_boundary_contract.py \
  tests/contract/test_cli_sdk_only_contract.py \
  tests/contract/test_core_no_platform_imports.py
47 passed

PYTHON=/Users/czj/Repos/nano-multiagent/.venv/bin/python scripts/docs-check
documentation integrity passed: 217 maintained Markdown sources, 67 required routes

ruff check [Round 2 closure source and tests]
All checks passed

ruff check tests/unit/agent/_workspace_scope_support.py \
  tests/unit/agent/test_workspace_execution_scope.py \
  tests/unit/agent/test_workspace_scope_side_entry_points.py
All checks passed

git diff --check 5feb761de..533082563
git diff --check e3913749d..3f0147b1c
passed
```
