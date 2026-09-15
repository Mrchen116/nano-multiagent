# M1-fix Progress

## Test strategy

- Regression seam: PA kernel wiring, node capability payload metadata, and Gateway shared-root usage response.
- Existing coverage: extend `test_product_workspace_layout.py`, `test_gateway_upstream_reporter.py`, `test_gateway_im_connection_behavior.py`, and the capability payload contract; no parallel test file.
- Layer: unit plus existing capability contract; these are the lowest stable product/protocol seams for the two declarations.
- Optional dependencies: none.
- One-off evidence: none.

## Progress

- Red: five focused tests failed before production changes because `~/.agents/skills` was absent from kernel discovery and Gateway usage reporting.
- Green: the same five tests passed after adding the user-global root to both declarations.
- Expanded: 52 relevant unit/contract tests passed; the isolated PA unit suite passed 1304 tests after raising the shell file-descriptor limit and clearing the host SearXNG override.
- Quality: `git diff --check`, focused Ruff checks, and documentation integrity checks passed.
- Current contract: updated `docs/specs/gateway/agent-capabilities.md`; generic kernel policy and archived feat-519 docs remain unchanged.
- Independent code review: Approved, 0 critical / 0 warning; the existing duplicate root declarations remain covered by wiring and usage tests.
- Final sync: rebased onto `origin/main` at `e63857a46`; the main delta did not alter the reviewed behavior, and final-tree CI preserved the review conclusion.
- Local CI: docs/ruff/format passed; Python shards passed 1882 + 1977 tests; frontend critical audit gate and 759 Vitest tests passed.
- Complete: ready for archive and PR.
