# M5 validation evidence

## Automated gates

| Gate | Result |
|---|---|
| Focused Python continuity / Gateway / IM tests | 66 passed, 1 skipped |
| Ruff (`src tests`) | passed |
| Backend non-e2e (`pytest -m "not e2e" -q`) | 3513 passed, 1 skipped, 23 deselected |
| Frontend full Vitest | 64 files, 589 tests passed |
| Frontend production build | passed |
| Critical e2e (`scripts/e2e-critical.sh -q -m "not slow" --timeout=240`) | 15 passed, 2 deselected |
| Patch whitespace (`git diff --check`) | passed |

The e2e timeout override reconciles the repository's 90-second global pytest timeout with cases that intentionally wait 120/180 seconds. Slow heartbeat coverage remains a strict xfail tracked by #126 and was not reclassified as a product pass.

## Isolated live-stack browser check

- Stack: worktree-local IM + Gateway + Vite on ephemeral ports; persistent user config was copied into the worktree-isolated e2e config by the project script.
- Browser: Codex in-app browser only. Chrome, Computer Use, browser profiles, notification permissions, and macOS System Settings were not touched.
- Finding: a new external conversation's first canonical `message.created` could precede the conversations cache and be suppressed as self-authored.
- Fix proof: with the authoritative conversation lookup in place, a newly created external conversation displayed a toast with sender `Visible External Sender` and preview `VISIBLE_TOAST_M5`, while its sidebar row displayed `1 unread`.
- Cleanup proof: temporary instrumentation was removed, the 4-second toast dismissal restored, the app reloaded normally with no debug dataset, both ephemeral ports were released, and the worktree dependency symlink was removed.
