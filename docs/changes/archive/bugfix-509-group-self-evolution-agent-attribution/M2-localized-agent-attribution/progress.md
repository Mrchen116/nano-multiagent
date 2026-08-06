# M2 progress

## Context

- Depends on M1's stable `system_notice` Message contract.
- Final user contract: all IM self-evolution notices follow current zh/en UI language; group rows show the stored source Agent name, direct rows do not.

## Decisions / deviations

- No design deviation at start.

## Evidence / commits

- Red/Green: reducer, formatter and focused MessagePane tests failed before the optional notice and complete locale-key matrix existed, then passed after implementation.
- Green: all 579 frontend tests passed; existing suites still emit their pre-existing React `act()` and mocked user-stream diagnostics. `npm run build` passed with the pre-existing chunk-size warning.
- Real group: both distinct source Agent snapshots rendered in the existing centered row. Runtime locale switching changed the complete rows between Chinese and English without a new message.
- Real direct/fork: the same structured notice rendered in Chinese without repeating the Agent name. The row has no avatar, sender header or message actions.
- Desktop and 390×844 mobile screenshots are indexed in [`../evidence/README.md`](../evidence/README.md). Browser console reported 0 errors and 0 warnings; all observed API requests completed successfully.

## Round 1 gate fixes

- Formatter and MessagePane component tests now cover all 12 group/direct × zh/en ×
  skills/memory/both combinations. The current participant name intentionally differs
  from the stored notice snapshot in the component matrix.
- Malformed live and persisted sidecars now fall back to stored content without throwing
  or coercing non-string identity fields.
- Independent real-stack evidence for all target variants, both locales, both chat kinds,
  two group Agents, long-name wrapping, refresh, and CLI compatibility is retained in
  [`../evidence/round1-review/`](../evidence/round1-review/).
- The independent reviewer found fork-copy timestamps collapsing at browser millisecond
  precision. Fork now assigns source-ordered millisecond timestamps ending at copy time;
  a focused mixed user/Agent/system regression proves the browser-visible order.
- All 603 Web IM tests and the production build passed after the round-1 fixes.
