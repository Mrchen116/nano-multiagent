# Code review — bugfix-706

- Reviewer: independent `review_web_dates` (`gpt-6.1-sol`, high), using `change-code-review`.
- `validated_at`: `ea359b4fdcff3ce1a4b37637fdf9cc8f67a01e8b` (full); closure at `a398b7d67570debb13f7a72c44a89215d99969de`.
- `executed_base`: `43cc90051cf9f037b58658fea86bb6e041681fac`.
- Scope: full unit diff, Web grouping/rendering and tests, iOS reference, current specification.
- Agent Context: presentation only; model inputs, history storage and delivery unchanged.

## Finding and resolution

P2: Web Chat UX now contains 32 Requirements but IM spec index still declared 31. Fixed in `a398b7d67`; closure independently confirmed count and summary match. The intermediate test fixture also gained required `permission_requests: []` in `5c22d341a`; closure found no behavioral impact.

Final closure returned `findings: []`; prior implementation review retained. Narrow test evidence reused (120 passed); independent documentation check passed (285 maintained Markdown sources, 68 required routes).

## Final synchronization

- `effective_base`: `43cc90051cf9f037b58658fea86bb6e041681fac` (origin/main unchanged at final fetch).
- `effective_through`: `a398b7d67570debb13f7a72c44a89215d99969de` for the implementation/specification tree; subsequent unit evidence and archive commits only move or record documents and retain this review.
- No main integration delta, runtime source changes, or unreviewed product changes. The corrected canonical Requirement and its index are covered by closure; lite requires no separate verifier.

## Prerequisite integration

- Final main base is now `6c072da43887ef8e144c0d1ef40ef3d7a2575fed`. Main only added the bugfix-707 first document since the prior review.
- Integrated `unit/bugfix-707` at `b4a3b4612de0a23a4adbb8e9439bc106c5274a69`; it adds a separately reviewed test-fixture lifecycle wait and its evidence/archive, with no production or frontend changes.
- Prior Web review and validation retained: frontend and product-contracts are unchanged from `a398b7d67570debb13f7a72c44a89215d99969de`; backend source/tests match the independently validated prerequisite branch. The original `validated_at`/`executed_base` remain execution facts; effective scope extends through this integration and subsequent unit-document/archive changes.

## Merge-time main synchronization (2026-11-04)

- PR #456 merged as `3da78a00a7cc8ace9d172c0b0d59c5d6e7881e0b`. Concurrent PR #458 had already advanced main to `5288d4d6e`; the new base therefore also contains feat-708 Skill defaults and its Node configuration tests.
- `b0bba8d47d1e85d589da1238919e5468910e5582` integrates that main. Web frontend and product-contracts have no delta relative to the approved date tree, so Web review, screenshot acceptance, and frontend validation remain applicable. No date grouping, rendering, or interface changes were introduced by the Skill integration.
- Effective base is `3da78a00a7cc8ace9d172c0b0d59c5d6e7881e0b`; original execution SHAs above remain historical facts. PR #457 now targets main. Backend validation is refreshed by the PR CI on the combined tree; this document-only record does not change the reviewed product scope.
