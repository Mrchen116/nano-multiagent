# M1 evidence — gateway runtime footer

## Automated checks

- `pytest tests/unit/personal_assistant/test_runtime_footer.py tests/unit/personal_assistant/test_local_store.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_session_run_coordinator_terminal.py`
- `pytest tests/unit/personal_assistant`
- `ruff check src/personal_assistant tests/unit/personal_assistant`
- `python scripts/docs_check.py`
- `git diff --check`

The full personal-assistant unit suite passed with `1085 passed`.

## Isolated Feishu round trip

On 2026-08-14, the dedicated non-production Feishu test profile completed
`scripts/e2e-feishu-probe.py` against the isolated gateway in 2.55 seconds.
The delivered final reply visibly ended with:

```text
deepseek:deepseek-v4-flash · 2%
```

The corresponding isolated Web IM shadow message stored only the original
assistant text; it did not contain the footer. The E2E stack was then stopped
and its local runtime files were removed from this worktree.
