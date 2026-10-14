# feat-604 Code Review

## Round 1 — full

- reviewer: `/root/static_review`, independent of implementation; skill `change-code-review`.
- branch: `codex/feat-604-account-policy-experience`.
- executed_base: `9ebe12f8553a593f6179784b0276849fb14e5358`.
- validated_at: `a2f3a66688e3bc1e17920f2976506bf1d222bc16`.
- diff_range: `9ebe12f8553a593f6179784b0276849fb14e5358...a2f3a66688e3bc1e17920f2976506bf1d222bc16`.
- scope: all 15 changed files, including both page implementations, extracted capacity panel, scoped CSS, i18n, three changed test files and implementation evidence. HEAD matched validated_at and the worktree was clean before report creation.
- verdict: **Changes requested — one CONFIRMED P2 finding.**

## JSON findings

```json
[
  {
    "file": "src/IM/frontend/src/features/settings/policies/policies-page.tsx",
    "line": 62,
    "summary": "[P2] Cancel an earlier background read before adopting the save response",
    "failure_scenario": "A background GET starts before PATCH and retains the old profile, PATCH succeeds first, and the earlier GET completes last. onSuccess writes the PATCH response but does not cancel the in-flight GET, then clears the draft. The late GET overwrites the cache, so the form reverts to the old saved values while still displaying Changes saved. AccountPage has the same mechanism at account-page.tsx:29-44; its AuthStore/menu additionally keeps the new name while the profile/form shows the old name. Reproduced on both actual page components with a deferred pre-PATCH GET. Cancel the same-key query before setting the successful response and clearing the draft, and extend the existing page tests to protect this ordering.",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

## Finding evidence

The implementation changed both success paths from query invalidation/refetch to `setQueryData` followed by `setDraft(null)`. A cache write does not cancel an existing fetch. With the draft cleared, AccountPage reads `profile.display_name` and PoliciesPage reads `baseline`, so a late pre-save response becomes visible again. The success flag remains true. This affects the expressly supported background-refresh/save path, rather than requiring a new API or unsupported input.

Independent reproduction used the locked frontend dependencies and the real exported AccountPage/PoliciesPage, QueryClientProvider, MemoryRouter, AuthStore and the existing test setup. Only HTTP was mocked: initial GET returns Original; a second GET is held with that same snapshot; edit to Saved; PATCH returns Saved; assert Saved and Changes saved; release the held GET; assert Original and Changes saved together. Both witness cases passed. Repository source/test/config files were not modified.

- temporary harness: `/tmp/nano-feat604/static-review/save-race.test.tsx` and `vitest.config.mts`.
- command, frontend cwd: `./node_modules/.bin/vitest run --config /private/tmp/nano-feat604/static-review/vitest.config.mts --maxWorkers=1`.
- result: 1 file / 2 witness tests passed, 2026-10-14 11:42:58 +08:00, 1.28s. These tests assert the faulty observation; this is reproduction evidence, not a green product regression gate.
- locations: `account/account-page.tsx:29-44` and `policies/policies-page.tsx:61-64`; the existing background-refresh tests stop before the save/late-read ordering (`account-page.test.tsx:184`, `policies-page.test.tsx:140`).
- limit: component-level controlled response ordering; no claim that this ordering was observed against the isolated or production HTTP server. The reproduction directly demonstrates the application behavior when an earlier response is delayed.

## PR validation input

Reused the frozen implementation evidence in [implementation-validation.md](M1-settings/evidence/implementation-validation.md), checked the corresponding local logs, and did not repeat its full suites:

- focused pages/access: 3 files / 19 tests passed; frontend full suite: 93 files / 877 tests passed; frontend build passed; critical audit: zero vulnerabilities.
- root build/typecheck passed. Initial unconstrained root suite had one existing usage-test timeout (79 files passed / 1 failed; 295 tests passed / 1 failed). Usage alone then passed 1/1 in 2.26s. Full root suite with unchanged 15s test timeout and `--maxWorkers=2` passed 80 files / 296 tests in 121.13s; no backend/test/timeout/skip changes. Locators: `/tmp/nano-feat604/backend-tests.log`, `backend-usage-retry.log`, `backend-tests-bounded.log`. Concurrency as the unique root cause is not established.
- Python helpers: 56 passed / 31 deselected; ruff check and format passed. Docs check was reported passed by the caller. Final diff/docs checks remain caller-owned after report integration.
- implementation screenshots are real isolated IM static-build self-checks for the recorded states. They do not constitute independent product acceptance, exhaustive role/language coverage, production deployment or native iOS acceptance.

The single confirmed finding prevents code-review approval at this snapshot. No additional speculative or style findings were retained. No product changes, commit, server process or browser session were created by this review.

## Author Resolution for Round 1

- W1 accepted. Both success callbacks now cancel the same-key in-flight query before adopting the PATCH response and clearing the draft. This keeps the existing API and local editor design.
- Durable tests extend the existing account/policies suites with the exact ordering: initial read → edit → hold an earlier refetch → PATCH succeeds → release old response → tab away from field → accepted value and saved feedback remain. Before the fix both tests failed (old name/model returned); after the fix the focused 3 files / 21 tests pass. Temporary red/green locators: `/tmp/nano-feat604/save-race-red.log`, `save-race-green.log`.
