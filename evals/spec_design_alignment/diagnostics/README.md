# Diagnostic-only assets

This directory records evaluation material that is intentionally outside the formal main suite. Entries in `registry.json` are not sealed main cases or main source roots and must not be counted by `dataset.json`, `source-roots.json`, or `suite-seal.json`.

The registry also records explicit owner dispositions. In particular, H06 is intentionally unused after `bugfix-520-compaction-context-loss` was rejected for the formal suite; future extensions must preserve that lineage instead of silently reassigning the number.

- `cases/H02-refactor-480-run-delivery-context` is retained as an unsealed, non-main diagnostic case after the formal H02 slot moved to `H02-feat-510-tool-approval-model`.
- `claude-code-h02-0991eac5` is retained as a diagnostic-only external source record. It is not exposed to any formal main case.

Paths in the registry are relative to the evaluation root unless a source record explicitly contains an absolute control path.
