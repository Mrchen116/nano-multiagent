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
