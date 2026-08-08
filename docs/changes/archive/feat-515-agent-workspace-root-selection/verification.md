# feat-515 — Verification Scope

## Permanent risks covered by this unit

- Gateway-local default/custom workspace creation and its filesystem outcomes.
- Existing-directory confirmation and per-node root ownership.
- Immutable Workspace Root and opaque IM mirror/provenance.
- Operation-correlated recovery after a lost create response, including negative
  cases that must remain ordinary duplicates.
- The browser workflow for default/custom selection and typed error recovery.

## Required final checks

- Focused Gateway, IM create/recovery, and create-page tests.
- `ruff check` for changed Python paths and `git diff --check`.
- Frontend typecheck/build and the affected component tests.
- Documentation integrity check.

## Excluded from this verification

This unit does not verify session JSONL resolution, transcript status projection,
or cross-Gateway distillation selection. Those belong to the separate
Gateway-owned skill-distillation bugfix.
