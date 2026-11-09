# M1 · Implementation evidence

Baseline `56c508377`, branch `codex/perf-754`. The v2 transfer is additive and independent of Work catalog/turn item pagination. It uses a single reusable source worker, a single center verifier, 256 MiB of reserved staging capacity and 4 GiB of logical retained original bytes. Both clients read the same paged originals endpoint by execution and optional turn.

## Local evidence

- Node 24.22.1 built product-contracts, personal-assistant and im-server. The three targeted Vitest files passed 31 tests.
- `pnpm exec vitest run --maxWorkers=1 apps/im-server/tests/work-sync.test.ts packages/personal-assistant/tests/work-sync.test.ts` covers the existing v1 and old-capability behavior. The center cursor assertions include the advertised capability.
- `pnpm exec vitest run --maxWorkers=1 apps/im-server/tests/work-detail.test.ts` exercises the real center HTTP listener, durable Gateway journal and WorkSync. The four scenarios cover restart at a persisted offset, idempotent part replay, two originals of roughly 20 and 17 MiB for one tool, later Work from another root, SQLite online backup restore, exact streamed SHA-256 with browser session and Bearer, auth-session revocation, a synthetic beyond-limit manifest, deletion with a SQLite writer using the old state transition, quota deferral and same-revision completion after Gateway restart, and a private original whose full hash matches a misleading manifest.
- iOS source parse uses `swiftc -frontend -parse`. The iOS transport downloads to disk through the shared authenticated, cancellable session. The in-app excerpt reads up to 8 KiB.

## Scope still to validate

- The local frontend dependency overlay was missing the pinned MapLibre style-spec types, so the frontend typecheck stopped in the existing basemap module.
- The deletion check uses the old writer's SQLite operation. A complete mixed-version rollout, live Web and iOS interactions, and revocation or deletion during an actively stalled download are outside this local evidence.
- The fixtures establish the 17–20 MiB HTTP behavior. Upper-range 64 MiB resource measurements, production concurrency and storage peaks remain unmeasured. The worker processes one original at a time and caps its V8 old-generation heap. Arbitrary JSON shapes can have higher decode amplification than large text. Oversized legacy rows can require SQLite to scan the old JSON on the worker to extract a bounded result. Newly appended oversized rows save the bounded projection.
