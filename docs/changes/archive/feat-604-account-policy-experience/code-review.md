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

## Round 2 — closure

- reviewer: `/root/static_review`, same independent reviewer; skill `change-code-review`.
- review_mode: `closure`; focus: Round 1's single P2/W1.
- executed_base: `9ebe12f8553a593f6179784b0276849fb14e5358` (unchanged).
- finding_origin_head / pre_fix_head: `a2f3a66688e3bc1e17920f2976506bf1d222bc16`.
- validated_at: `49795346290faadb5039fb1b371db5f6d145562a`.
- closure diff: `a2f3a66688e3bc1e17920f2976506bf1d222bc16..49795346290faadb5039fb1b371db5f6d145562a`.
- scope reason: product changes are confined to both success callbacks and regression coverage in the existing page tests. Remaining changes integrate R1 reports/screenshots/runtime and prior validation. Spec/design/delta are unchanged; R1's unaffected conclusions remain valid. HEAD matched the new validated_at and the tree was clean before report edits.
- verdict: **Approved — W1 closed; no surviving findings.** This supersedes Round 1's code-review block for the new snapshot only.

### JSON findings

```json
[]
```

### Focus finding closure

| Finding | Result | Evidence |
|---|---|---|
| R1 P2 / verifier W1: earlier GET replaces successful save response | **closed** | Both `async onSuccess` callbacks await same-key `cancelQueries({ exact: true })` before `setQueryData`, AuthStore synchronization and draft clearing (`account/account-page.tsx:29`, `policies/policies-page.tsx:61`). This cancels the React Query result even when the underlying mocked HTTP promise resolves later. The mutation remains pending through this ordered completion. |

The two new tests drive the real page components with an independent QueryClient and controlled HTTP order: initial data → edit → held old GET → successful PATCH/status → release old GET → assert accepted value and success feedback. They observe form values rather than a cancellation-call count. Both fail on the old callbacks and pass with the fix, so the added coverage directly protects the reported regression without introducing a new framework or permanent test file.

- author red/green evidence inspected: `/tmp/nano-feat604/save-race-red.log` (2 failures), `save-race-green.log` (3 files / 21 passed).
- independent targeted rerun, frontend cwd: `./node_modules/.bin/vitest run src/features/settings/account/account-page.test.tsx src/features/settings/policies/policies-page.test.tsx -t 'keeps the accepted save when an earlier background read completes last' --maxWorkers=1`.
- independent result: 2 files / 2 selected tests passed, 9 unrelated tests skipped by name filter; 2026-10-14 11:57:20 +08:00, 2.24s. The first attempted invocation through the npm shell wrapper expanded the multiword filter and selected 17 files (35 passed / 235 skipped); the direct command above is the precise closure check.
- final frontend suite evidence inspected: `/tmp/nano-feat604/frontend-tests-final.log`, 93 files / 879 passed, 23.02s. Frontend build passed again per implementation handoff; dependencies did not change, so prior zero-vulnerability audit remains applicable. Root build/typecheck, bounded 296-test suite, Python 56 tests and ruff evidence remain unaffected.

No new confirmed or plausible defect was found in the closure delta; no full-review expansion is required. This is component/static closure, not the separate real-product S7 acceptance. Only code-review.md and verification.md were modified by this round; no commit or product/server/browser changes.

## Author Resolution for Round 1

- W1 accepted. Both success callbacks now cancel the same-key in-flight query before adopting the PATCH response and clearing the draft. This keeps the existing API and local editor design.
- Durable tests extend the existing account/policies suites with the exact ordering: initial read → edit → hold an earlier refetch → PATCH succeeds → release old response → tab away from field → accepted value and saved feedback remain. Before the fix both tests failed (old name/model returned); after the fix the focused 3 files / 21 tests pass. Temporary red/green locators: `/tmp/nano-feat604/save-race-red.log`, `save-race-green.log`.

## Round 3 — post-PR CI patch

本段归集独立审查者的返回事实，不覆盖 R1/R2 的历史。

- reviewer: `/root/pr357_ci_patch_review`，`gpt-6.1-sol/high`；未参与实现，使用 change-code-review。
- review_mode: `patch`；范围仅 `7e892cb6992411e0731797bdb653271594b90676..587ac7cd97280fea548237829f802fd22d0075c3`。
- patch_base: `7e892cb6992411e0731797bdb653271594b90676`；实际 main / executed_base: `20400dffb6b5877169d444377f573188e217485e`。
- validated_at: `587ac7cd97280fea548237829f802fd22d0075c3`；受审 worktree clean。
- reviewed_at: `2026-10-14T06:47:54Z`。
- verdict: pass；findings `[]`。

CI #38523384462 的既有登录冷却测试显示 Retry-After=30 时初始文案为31秒。一次 start 中两次 Date.now 相差1ms，经 Math.ceil 后成为31；既有真实 LoginPage 测试以每次时钟读取推进1ms稳定复现，未放宽30秒、凭据保留或重试禁用断言。修复只让 now/until 使用同一时间戳，原最短冷却、定时刷新与恢复语义保留。

审查者检查了唯一两个调用方 LoginPage/RegisterPage，独立运行 company-access 与 auth-form-experience 两文件，25/25通过，diff-check通过；核读红测、完整前端880/880通过和生产构建成功日志。未发现存活缺陷，无须扩展 full review。

独立一致性核对确认该补丁不改变 feat-604 的账号资料、空间资格、容量、策略权限、草稿或保存契约，不使归档 S1–S9 真实验收失效；本轮未执行或冒充新的真实浏览器验收。既有 Gate 2、corrected delta 及未受影响验收结论 retained。后续仅归集本报告和验证记录，最终 effective_through 在 PR body 记录。
