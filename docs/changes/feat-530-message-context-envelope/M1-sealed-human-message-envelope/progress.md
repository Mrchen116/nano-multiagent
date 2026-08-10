# feat-530 M1 progress

## Baseline

- Branch: `unit/feat-530`
- Base: `origin/main@a3329c36ed17d6e2fa60797632baadecdcd5f0b0`
- Design seed: `3ed4a211d`
- Command: `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/unit/personal_assistant/test_inbound_dispatcher.py tests/unit/personal_assistant/test_chat_history_hook.py tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py tests/unit/personal_assistant/test_gateway_image_inbound.py tests/unit/personal_assistant/test_gateway_im_relay.py tests/unit/agent/test_kernel_list_capability_queries.py tests/contract/test_system_prompt_contract.py tests/integration/test_personal_assistant_prompt_integration.py`
- Result: PASS, 44 tests passed with two upstream `lark_oapi` deprecation warnings.
- Limit: baseline covers the directly affected current behavior, not the full suite or real services.

## Implementation log

- 2026-08-10: Admission accepted from approved Gate 2 Round 7. Created the isolated unit worktree from latest `origin/main`; dirty local `main` was not modified.
- 2026-08-10: Added source/receipt normalization, startup timezone snapshot, frozen PA model envelope, stable group-buffer metadata, exact readable-history projection, and the default-on Kernel runtime-footer policy. PA runtime and prompt preview explicitly disable the session-created datetime while Coding CLI/subagents inherit the unchanged default.
- 2026-08-10: Focused validation passed (132 tests, then 64-test regression rerun after updating two stale exact-feature expectations). Full non-E2E suite passed: `3218 passed, 28 warnings` in 124.96s with four workers.
- 2026-08-10: `/Users/czj/Repos/nano-multiagent/.venv/bin/ruff check .`, `git diff --check`, and `/Users/czj/Repos/nano-multiagent/.venv/bin/python scripts/docs_check.py` passed. The wrapper `./scripts/docs-check` first failed because the worktree has no local virtualenv and system Python lacks PyYAML; rerunning the same checker with the repository virtualenv passed.
- 2026-08-10: Real Web IM direct-chat validation passed at `acd6a6512`: Agent recognized `Web IM` and the provider occurrence minute; visible IM/readable history stayed raw; a header-shaped user body was preserved; two provider system prompts were byte-identical and timezone-only; Gateway-only restart preserved prior header bytes; active steer received the same envelope. Evidence: `evidence/web-im-real-stack.md`.
- 2026-08-10: Mandatory real Feishu validation is blocked before message delivery by existing cold-start/readiness budgets. Two isolated `--feishu` starts failed `FeishuWorkerRuntime.start()` with `feishu worker did not initialize`; a later warm attempt timed out the launcher's IM readiness before Gateway start even though IM subsequently reported healthy. No production/default profile was used, no Feishu message was sent, and all runtime resources were cleaned. This is recorded as inconclusive rather than passed.
