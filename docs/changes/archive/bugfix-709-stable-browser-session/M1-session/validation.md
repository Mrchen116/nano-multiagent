# M1-session validation

Source snapshot 8ece8ad0ec7b38c97183e4cbd11a93c0bc201984, Node 24.22.1.

- Regression owner is apps/im-server/tests/identity.test.ts. Existing browser transport scenario was revised from once-only consumption to stable reuse, while native rotation scenarios were retained. Added repeatable legacy upgrade/lost response, existing database upgrade, concurrent stable renewal, rolling expiry, tampering, epoch and program-interface isolation coverage. Updated an existing positional session fixture to name its columns.
- Before implementation, identity suite had 2 failed / 11 passed. The browser Cookie reuse and upgrade-response-loss assertions reproduced the bug.
- After implementation, identity suite 13 passed (5.00 seconds). Command pnpm exec vitest run apps/im-server/tests/identity.test.ts.
- pnpm build and pnpm typecheck passed.
- pnpm check:ios-runtime passed.
- Frontend npm ci / npm run build passed. Full frontend npx vitest run --maxWorkers=2 passed 112 files / 1059 tests, 165.78 seconds.
- Python pytest -m 'not e2e' -q passed 129, deselected 28. Ruff check and format passed. Documentation integrity passed.
- Independent code review has no findings; implementation verification passed and corrected delta aligned.
- Independent product regression passed the real browser lost-response, explicit retry, page close/reopen, same-database service restart, and logout journeys. See ../regression.md for actual scope and local evidence.
- Disposable test proxy and backend listeners 18173/18174 were stopped by the main agent after reviewer handoff; reviewer closed its browser. No production state or service was changed.
- Existing already-consumed/invalid browser JWTs are not revived. An already stranded browser will need one login to obtain a stable Cookie after deployment.
- Full backend pnpm exec vitest run --maxWorkers=2 completed with 209 files passed / 1 failed, 1126 tests passed / 1 failed (581.92 seconds). The sole failure was packages/dsh-integration/tests/workspace-tools.test.ts with Capability inspection deadline exceeded, outside changed identity paths. No source or timeout was changed. Isolated rerun pnpm exec vitest run packages/dsh-integration/tests/workspace-tools.test.ts --maxWorkers=1 passed (39.92 seconds). The monolithic local run is not claimed green; its failed case has separate passing evidence.
- Retained review/product evidence applies to frozen source 8ece8ad0e. Subsequent changes only add reports, changelog and archive relocation, leaving implementation and canonical contract unchanged.
- Final documentation consistency correction updates prod-fleet.md: signing-key rotation invalidates JWTs, while upgraded stable browser sessions authenticate via database state; forced sign-out uses session revocation. Static reviewer verified this docs-only correction in the verification addendum. Source and canonical auth contract remain unchanged.
