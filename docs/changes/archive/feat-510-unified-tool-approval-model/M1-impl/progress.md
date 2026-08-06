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

### Independent gates and fix closure

- Product acceptance Round 1: `pass`, 0 blocking / 0 major / 0 minor at
  `89197f46323803d413a012f83418d5dad03049ce`; report commit `38dfd6b47`.
- Verification Round 1 identified two permanent-test evidence gaps: the SDK routing test used one
  override client, and the Agent-derived origin used the nonexistent `subagent` value.
- Fix commit `7f0d4be1e` routes the contract test through distinct provider-a/provider-c clients, uses
  the real `background_task` origin, closes two full-unit regressions found by code review, and adds
  the public SDK `Raises` contract.
- Complete `tests/unit`: 2441 passed. Focused auto-gate and SDK contract set: 78 passed.
- Verification Round 2: `pass`, 0 critical / 0 warning / 0 suggestion at `7f0d4be1e`; report commit
  `0aece52d0`. Independent evidence included 134 related unit/contract tests and 4 real-stack E2E
  cases.
- Code-review findings were independently confirmed and closed. The acceptance evidence wording was
  corrected to the production origin `background_task（Agent 派生运行）` in `ea96d9d5a`.
- Corrected-delta verification: `aligned`, no issues; report commit `7840195ef`.

### Delivery closure

- Canonical specs were merged and the complete unit was archived in `a65c1ba59`.
- Local CI matched `.github/workflows/ci.yml`: docs-check, ruff check/format, 2959 non-E2E
  Python tests, critical-level npm audit, and 574 frontend tests all passed.
- PR [#248](https://github.com/Mrchen116/nano-multiagent/pull/248) was opened against `main`.
- GitHub Actions run `31096022607` passed both required jobs: Frontend checks in 1m16s and
  Python checks in 2m2s. This record-only commit does not alter implementation or contract behavior.

## Design deviations

None.

## Rollback

Revert the feat-510 commits. Older PA parsers ignore the extra YAML key, and no runtime fallback or migration state is introduced.

## Commits

- `89197f463` — implementation, permanent tests, deterministic fixture, runbook, and milestone evidence.
- `38dfd6b47` — product acceptance Round 1 (`pass`).
- `b93d0d8ce` — implementation verification Round 1 (`fail`, two warnings).
- `7f0d4be1e` — close verification and code-review findings.
- `0aece52d0` — implementation verification Round 2 (`pass`).
- `ea96d9d5a` — correct final acceptance origin evidence.
- `7840195ef` — corrected-delta verification (`aligned`).
