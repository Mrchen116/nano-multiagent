# feat-515-M1 round-1 correction evidence

Date: 2026-08-07 (Asia/Shanghai)

## Review lineage

| Source | Commit | Required correction |
|---|---|---|
| Verification round 1 | `015711133dbd10e9932e806ad1fb904178527b80` | Block duplicate root replacement, remove IM workspace dereference, and add permanent HTTP/UI path-error coverage. |
| Product acceptance round 1 | `e813c45f10fc11a33f0e75358c810e1a0fe1aa5e` | Real browser reproduced a successful second create for `review_default_515` that changed its fixed workspace root. |
| Code-review follow-up | current correction | Preserve same-root lost-response recovery, correlate invalid preview errors without disconnect, serialize concurrent local creates, and refresh ownerless provenance. |

## Corrected boundaries

| Boundary | Before | Correction | Permanent evidence |
|---|---|---|---|
| IM Agent create | Client owner text plus owner-sensitive precheck followed by profile upsert. | Authenticated owner, app-scoped serialized check/Gateway/insert, and insert-only SQLite uniqueness. | UI-shaped duplicate and concurrent HTTP contract tests; repository duplicate test. |
| Gateway Agent create | Same Agent ID could initialize and publish a different root. | Serialized local create; same root returns existing success for retry, divergent root rejects before filesystem effects. | Gateway immutability and concurrent-create tests. |
| Conversation transcript discovery | IM interpreted the mirrored root and scanned/opened local paths. | IM sends only Agent/conversation IDs; target Gateway discovers and reads session JSONL, then returns an opaque path. | Repository non-dereference, Gateway resolver, control correlation, and list/sync RPC tests. |
| Preview / provenance | Invalid custom preview raised through the receive loop; ownerless upsert preserved stale provenance. | Correlated 422 workspace error without disconnect; authoritative ownerless seed refresh. | Preview protocol/HTTP tests and registration integration test. |
| Workspace failures in UI | Mappings existed without full scenario coverage. | Four-code parameterized checks preserve all draft fields and render localized Workspace Root errors. | `agent-create-workspace.test.tsx`. |

## Commands and results

```text
python -m pytest -q <focused correction owners>
115 passed, 7 warnings in 10.36s

python -m pytest -q tests/im_service <affected Gateway owners>
442 passed, 22 warnings in 45.13s

git rebase origin/unit/feat-515
rebased cleanly onto e813c45f10fc11a33f0e75358c810e1a0fe1aa5e

python -m pytest -q <focused correction owners>
107 passed, 8 warnings in 10.16s

python -m pytest -m 'not e2e' -q
3049 passed, 24 deselected, 22 warnings in 126.90s

vitest run agent-create-workspace.test.tsx im-agent-config-api.test.ts
2 files passed, 22 tests passed

tsc -b && vite build
passed; existing chunk-size warning only

ruff check <changed Python files>
All checks passed

PYTHON=.venv/bin/python scripts/docs-check
documentation integrity passed

git diff --check
passed
```

## Isolation and cleanup

- All work ran in `.worktrees/feat-515-M1-fix1`; no production service or default runtime was started or modified.
- No persistent test process, socket, config, database, workspace, screenshot cache, or build output was retained.
- The temporary ignored frontend dependency link and generated `dist`/TypeScript build files were removed after validation.
