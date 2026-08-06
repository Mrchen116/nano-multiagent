# M1 Progress

## Context

- Branch: `unit/feat-510`
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-510`
- Baseline: `eaaed4c3ec91c5359044ca6b47d3834e8388063f` (`origin/main` at implementation start)
- Gate 2: `Approved — 0 CRITICAL / 0 WARNING` in design review Round 3.

## Decisions

- Implement the current-main registry-state bridge described by design decision 3; refactor-476's trusted dependency bundle is not present in this baseline.
- Keep the model id in PA-owned config and pass it as an independent public SDK build parameter.
- Preserve current failure handling: an explicit classifier model is never replaced by the Agent model after an error.
- The deterministic fixture uses the normal Anthropic protocol and drives a real `write` call; model selection is asserted from recorded upstream request bodies, while successful execution is asserted from the isolated workspace file.

## Evidence

### Pre-change baseline

- `test_parse_llm.py`: 7 passed.
- `test_auto_mode_gate_hook.py`: 18 passed.
- `test_sdk_kernel_wiring.py`: 14 passed.
- `test_gateway_build_runtime.py`: 9 passed (two dependency deprecation warnings).

All commands used `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q` from the isolated worktree.

### TDD and focused implementation

- Red: config tests failed on the absent payload field/validation; gate tests failed because classifier calls had no `model`; SDK tests failed because `build_kernel` rejected the new argument.
- Green: 62 focused unit/contract tests passed across PA parse/save, Gateway composition, both classifier stages, failure/no-fallback, run origins, public Kernel routing, and the only-production-consumer invariant.
- `ruff check` passed on all changed Python files.
- `ruff format --check` passed after formatting the five reported files.
- `git diff --check` passed.
- `PYTHON=.../.venv/bin/python ./scripts/docs-check` passed: 235 maintained Markdown sources and 66 required routes.

### Real PA/Gateway critical path

Command: `PYTHONPATH=src .../.venv/bin/python -m pytest -xvs tests/e2e/critical_paths/test_tool_approval_model_critical_path.py`

- 4 passed in 51.20s.
- Explicit C: recorded `model-a → model-c → model-a` and `model-b → model-c → model-b`; approved writes created files in the isolated Gateway workspaces.
- Config changed C→D without restart: the next turn still recorded C; after the same node reconnected from a Gateway restart, the next turn recorded D.
- Omitted field: recorded `model-a → model-a → model-a` and `model-b → model-b → model-b`.
- `approval-fail`: the attended journey emitted `permission.request`; the only classifier request used `approval-fail`, with no Agent-model classifier retry.
- `missing-model`: the real PA foreground entry rejected startup and named `llm.tool_approval_model` plus the invalid value.
- Teardown removed every test PID and generated Gateway config; no fixture or Gateway process remained.

## Design deviations

None.

## Rollback

Revert the feat-510 commits. Older PA parsers ignore the extra YAML key, and no runtime fallback or migration state is introduced.

## Commits

Pending.
