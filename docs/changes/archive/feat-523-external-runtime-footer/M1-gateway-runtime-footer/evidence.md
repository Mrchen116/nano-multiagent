# M1 evidence — Feishu runtime card

## Automated checks

- Focused runtime projection, Feishu adapter, Feishu probe, relay-lifecycle,
  and terminal-fallback tests.
- Full personal-assistant plus Feishu suite: `1116 passed`.
- `ruff check`, `python scripts/docs_check.py`, and `git diff --check`.

## Isolated Feishu round trip

On 2026-08-15, the dedicated non-production Feishu test profile completed
`scripts/e2e-feishu-probe.py` against the isolated gateway. Its final reply
was one native `interactive` card: the answer body occupied the main section,
and the note section visibly displayed:

```text
deepseek:deepseek-v4-flash · ctx 2%
```

The corresponding isolated Web IM shadow message stored only the original
assistant text; it did not contain the card-only runtime metadata. The E2E
stack was stopped after capture and its local runtime files were removed from
this worktree.
