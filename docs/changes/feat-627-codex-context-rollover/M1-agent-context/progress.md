# M1 implementation and validation

## Scope and baseline

- Nano unit worktree: `unit/feat-627`, base `d5ac9c4f9c371e53a7bcac542d551b1fdd303d28`.
- Plugin worktree: `codex/feat-627-agent-context`, base `d74876a90968bd5498b5af0bcc2f327c3131f007`, repository `Mrchen116/dsh-agent-context`.
- Gate 2: original Round 2 Approved; user then explicitly required all Agents to use this by default. R3 identified approval, allowlist contract and initial budget state gaps; the author accepted all three and R4 delta review Approved with 0 CRITICAL / 0 WARNING before default integration.
- Implementation split: independent first-pass plugin implementation; primary Agent owns Nano integration, real-stack validation, subsequent fixes and final delivery.

## Test ownership

Nano's `packages/dsh-integration/tests/workspace-tools.test.ts` already protects workspace plugin installation, peer resolution, session/tool scope, restart-required updates, idle activation, teardown and isolated compaction ownership/fallback. Keep it. The new agent-context-default integration test covers the newly added default migration, empty business selection, PA scope, persistent opt-out, and Auto-off child dispatch; these behaviors were absent from the prior lifecycle test. Plugin behavior tests belong to the independent plugin repository. A local packed bundle will additionally traverse Nano's real user entry for integration and long-task evidence; one-off acceptance scripts remain local rather than becoming permanent tests.

## Preflight

- `pnpm install --frozen-lockfile`: passed in the isolated Nano worktree.
- `pnpm build`: passed; installed DSH remains `0.2.1-alpha.1`.
- Web `npm ci && npm run build`: passed.
- `pnpm exec vitest run packages/dsh-integration/tests/workspace-tools.test.ts`: passed.
- Isolated stack started with `scripts/e2e-up.sh`; two separate workspaces, ephemeral IM port, unique node identity, no production channels. Test-only model window configured to 65,536 tokens; real provider reachable at the configured local proxy.

Preflight readiness is not acceptance. Package/long-task and independent gate evidence will be recorded after actual execution.

## Default scope red baseline

Before integration, `agent-context-default.test.ts` reproduced five failures: new/existing empty-selection Agents and PA lack all four context tools; all three approval rulesets reject internal Notes operations with `manual_required; return_to_agent` under Auto off. The fixture creates a real native child and retains a separate denied business operation. Captured locally in `/tmp/feat627-default-red-full.log` (not committed).

Pre-change baseline: backend 106 files / 476 tests, Web 100 files / 936 tests, Python 62 passed / 31 deselected; typecheck, ruff and formatting passed. Frontend audit passed its CI `critical` threshold, with pre-existing 5 low / 1 high advisories. No frontend dependency edits are part of this unit. These are baseline results, not post-integration acceptance.

## Integrated candidate

- Plugin source: `7f0a2b78ec530075edd48452c2cf5499548ca99c`; fixed [v0.3.0-rc.1 asset](https://github.com/Mrchen116/dsh-agent-context/releases/tag/v0.3.0-rc.1). Published download SHA-256 verified equal to local pack: `f8a26ca5c6558ef04a2ff2b7d93535993272f80cd05d138029c733aa391e4fb1`. Nano depends on the exact Release URL with lock integrity; no local dependency paths remain. Plugin 9 files / 22 tests, typecheck and pack build pass.
- Default migration preserves existing profile fields and explicit opt-out. New/old workspaces, no-workspace SDK, Global/Personal and native child cases are covered; internal context tools remain usable with empty business allowlists and Auto off without allowing business operations or overriding explicit downstream denial.
- Real IM smoke exposed DSH's valid omission of request maxTokens. Gate 2 R5 approved the bounded, labeled output-reserve policy; a new plugin regression reproduced the failed second turn before the repair. Real IM then returned `FEAT627_DEFAULT_OK` after get_context_remaining and notes write. This smoke does not replace long-task acceptance.
- Post-integration full backend run: 478 passed, 3 failed; failures were old assumptions about default LLM summaries, default tool lists, and the adapter's single-text cache-marker encoding. Updated tests preserve full system/tool equality and semantic inherited message content. Manual compaction now tests both the new default (zero summary calls) and explicit opt-out (one focused summary), including restart and selected Skill restoration. Readable history still verifies actual human body envelope removal while allowing source-reference previews. Focused repaired tests passed; final Release-based full run in progress.
- `pnpm install --frozen-lockfile` from the published candidate, build and typecheck pass. Python contract/helper suite: 62 passed / 31 deselected; docs-check: 250 maintained Markdown sources / 67 routes. Independent static and product gates pending.
