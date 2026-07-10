# FIX-round-4-global-skill-enable Tasks

- [x] R1: Rename user-facing create scope from `pa` to `global` in docs, frontend prefill, built-in distiller guidance, and `skill_manage` schema.
- [x] R2: Make successful `skill_manage(create)` default-enable the created skill according to scope: `agent` for the executing agent, `global` for all agents.
- [x] R3: Preserve session and allowlist boundaries: no hot mutation of existing kernel prompts, no full allowlist materialization for unset skills, and empty `skills=[]` remains "no skills enabled".
- [x] R4: Align skill list/view runtime visibility with the session enabled-skill set.
- [x] R5: Verify backend, frontend, lint/build, and whitespace gates.

## Roadpoints

| Roadpoint | Status | Scope | Gate |
|---|---|---|---|
| R1 | DONE | public scope contract | `skill_manage` schema/tests + F2 frontend integration |
| R2 | DONE | Gateway config sync | `tests/unit/personal_assistant/test_gateway_im_config_sync.py` |
| R3 | DONE | session cache boundary | `tests/unit/personal_assistant/test_gateway_reconcile_on_connect.py` + sync tests |
| R4 | DONE | runtime skill visibility | `tests/unit/test_skill_manage_tool.py` + `tests/unit/test_skill_view.py` |
| R5 | DONE | local gates | focused pytest, frontend tests, ruff, build, `git diff --check` |
