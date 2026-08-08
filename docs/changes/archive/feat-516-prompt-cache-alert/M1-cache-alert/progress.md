# M1: Per-call cache warning — Implementation Record

## Scope

- Added per-provider cache-data availability while preserving existing cache token relay and turn aggregation fields.
- Added the fixed Gateway-only warning at the per-call terminal usage boundary.
- Added deterministic Anthropic SSE fixture controls and a real IM + Gateway critical-path test.
- Merged the approved Gateway delta into the canonical service-lifecycle spec and registered the E2E journey.

## Decisions

- Anthropic streaming merges `message_start.message.usage` with `message_delta.usage`; input/cache data is therefore not lost when the terminal frame only reports output usage.
- `cache_usage_available` distinguishes an explicit cache miss (`0`) from omitted provider data. It is consumed before usage aggregation and is not relayed or persisted.
- The warning is scoped by the existing non-empty Gateway `agent_id` metadata; `HookContext` supplies the correlated `session_id`.
- Threshold comparison uses integer arithmetic (`input_tokens > 30_000` and `cache_read_tokens * 100 < input_tokens * 80`); the logged percentage is a one-decimal display value only.

## Evidence

- Meaningful red: the added loop test could not construct `TokenUsage(cache_usage_available=...)` before the implementation.
- Focused regression and real-process check passed:

  ```text
  PYTHONPATH=src .venv/bin/python -m pytest -q \
    tests/unit/test_llm_anthropic_client_streaming.py \
    tests/unit/test_llm_anthropic_mapper.py \
    tests/unit/test_openai_compat_client_streaming.py \
    tests/unit/test_llm_openai_compat_mapper.py \
    tests/unit/test_agent_loop.py \
    tests/e2e/critical_paths/test_prompt_cache_alert_critical_path.py
  73 passed
  ```

- The E2E starts a real IM and Gateway in an isolated temporary worktree. Its Anthropic fixture sends `input_tokens=30_001` and explicit `cache_read_input_tokens=0` in `message_start`, then output usage in `message_delta`; it verifies the Web IM reply, the warning fields and absence of prompt text, plus the `agent_id + session_id` JSONL path.
- `ruff check`, `git diff --check`, and `PYTHON=.venv/bin/python bash scripts/docs-check` passed.
- Independent code review found that a slow tool could delay the warning after its model call had already finished. The warning now runs immediately after the model stream, before tool-result waits; `test_loop_warns_before_waiting_for_a_tool_result` proves this ordering. Its closure review and targeted verifier/product revalidation passed.

## Design Deviation

None.

## Rollback

Revert this milestone's implementation commit; no configuration, migration, persisted schema, or relay protocol rollback is required.

## Commits

Pending delivery commit.
