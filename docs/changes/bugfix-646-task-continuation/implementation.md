# M1 implementation evidence

Baseline: e7f8249d26287dbaccde298365323c70e3cd5fc8, isolated unit/bugfix-646 worktree.

- Task driver reuses native lifecycle and inbox; denial records track action + affected node version and exclude shared graph revision. Successful new input recovers runtime errors but cannot grant denied actions. Source/flush failure preserves business state.
- IM enforces one-hour waiting association at preparation and commit. Successful mutation receipt contains the fixed-conversation feedback projection; integration defers a real-delivery reminder after the confirmed tool result.
- Shared interactive guidance and generated assets distinguish Global private closing from SingleThread silence.
- Existing Task execution tests retained and expanded at their risk owners. New task-feedback tests cover the distinct native tool-result/deferContext seam; task-recovery tests cover native source/flush failure, separate from authorization denial. They run in the normal Vitest gate.
- Red: native unrelated-input denial tests expected 4 requests but saw 6; confirmed child apply had no feedback. Native source/flush fixture startup race was isolated and corrected by establishing initial quiescence, without a product workaround.
- Green: `pnpm exec vitest run` for IM Task, PA Task, native Task execution/feedback/recovery, Task graph permission and native communication: 7 files / 34 tests, 2026-10-23 23:17 +08. Build and typecheck passed. Local temporary logs: /tmp/nano-646-red-confirmed.log and /tmp/nano-646-narrow-final.log.
- Real stack prerequisite found: default DeepSeek reviewer supports high/max, while tool approval hard-coded low; the request failed before any verdict. Same-model supported effort selection now matches the existing disclosure path. Red 2 failed / 6 passed, then green 8 passed in codex-approval-lifecycle; reviewer identity, full evidence and verdict rules retained. This is request compatibility, not a classifier-policy exemption. Initial real smoke is NOT acceptance evidence.

Real acceptance and full CI results are recorded by their respective gates. No production configuration or service changed.
