# Local verification

Implementation branch: `codex/skill-denylist`, base `74bfff7f7118ed040f270491691f31f992393793`.

- A new SkillSourceSelector denylist test failed against the original component: a disabled item was rendered enabled. The same regression now passes.
- `pnpm build` and `pnpm typecheck`: passed for all runtime packages/apps.
- `pnpm exec vitest run --maxWorkers=4`: 71 files / 241 tests passed. The native DSH capabilities regression creates a session, copies a new Skill onto disk, loads its body with the real `skill` tool, verifies disabled loading fails, then restarts and verifies both states persist.
- Migration HTTP tests cover old default discovery, selected allowlist and empty allowlist; verify persisted mode/names, canonical fingerprint and idempotent retry.
- Web Vitest: 91 files / 856 tests passed. After adding the extra denylist preview case, the detail-page suite passed 21 tests. Create/edit/source selector/API/SlashPicker all use the new representation.
- Web Vite bundle: passed. Full Web TypeScript check reports the existing `message-pane.tsx:467` timer typing mismatch. The same compiler invocation on unchanged main reports the identical error; this change leaves that unrelated file untouched.
- iOS Simulator build: passed. `NanoIMTests/AgentContractsTests`: 7 tests passed, including disabled-name persistence, future-name default enablement and preview payload semantics. No physical-device acceptance claimed.
- Documentation integrity and `git diff --check`: passed.

## Delivery state

Local implementation only. No production configuration, service or deployment was changed. This side conversation prohibits subagents, so independent design/code/product gates have not run; no approval or PR-readiness is claimed. Keep the unit active for that review.

## Migration boundary

Old allowlists did not record the historical candidate set. Migration preserves the choice of every candidate present at migration time; it cannot infer whether an unselected candidate was added after the user's last edit. Once converted, future names default enabled and known disables survive restarts. Offline nodes retain legacy behavior until their authenticated IM migration completes.

## Separate finding

Ordinary background Skill review may modify F1 skills; automatic per-Skill batch review and inactivity archival are limited to F3/F4. This matches Hermes' distinction at the level discussed here; the new Hermes read-before-write enforcement is not part of this selection change. No evolution policy was changed.
