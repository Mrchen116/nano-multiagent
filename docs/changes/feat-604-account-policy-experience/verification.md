# Verification Report: feat-604

> Validation snapshot: `9ebe12f8553a593f6179784b0276849fb14e5358 → a2f3a66688e3bc1e17920f2976506bf1d222bc16`

## Round 1

- verifier: `/root/static_review`, independent of implementation; skill `change-verifier`.
- verification_mode: `full`, including all corrected-delta reconciliation.
- branch: `codex/feat-604-account-policy-experience`.
- unit_dir: `docs/changes/feat-604-account-policy-experience`.
- executed_base: `9ebe12f8553a593f6179784b0276849fb14e5358`.
- validated_at: `a2f3a66688e3bc1e17920f2976506bf1d222bc16`.
- requires_full_verification: `false` (this report already covers the full assigned scope).
- verdict: **FAIL — 0 CRITICAL / 1 WARNING / 0 SUGGESTION.**

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 implementation present; W1 representative evidence present; W2 tests and gates present; save/refresh ordering needs correction. R1–R3 product verdict belongs to the separately dispatched reviewer. |
| Correctness | S1–S9 mapped; one confirmed mismatch affects S1/S7 and the editable-state delta. |
| Coherence | Frontend scope, authority and reuse followed; successful-save/background-query synchronization is incomplete. |

## Completeness

- The single M1 implementation exists: two reorganized settings pages, shared scoped CSS and translations, independent actual-capacity panel, local drafts, recoverable initial-load/save failures and read-only presentation.
- Simplified implementation has no mandatory worker tasks/progress files. [Implementation validation](M1-settings/evidence/implementation-validation.md) records the affected-test rewrite/merge strategy and actual results; no new permanent test files were introduced.
- M1-W1 has real client representative captures and prototype references for the three must-match rows. This verifier inspected the actual account desktop, policy desktop, policy mobile failure and account/policy prototype pixels. The explicit grouping and failure/footer relationships are visible; partial screenshots do not establish off-screen content or all roles/states.
- M1-W2 extends existing page/access tests for summary navigation, validation, failures, refresh protection and independent query errors. The late-read-after-success case is missing and has a reproducible defect, recorded as W1 below.
- Existing valid validation was reused: 19 focused tests; frontend 93 files / 877 tests, build and zero critical-audit vulnerabilities; root build/typecheck; Python 56 passed / 31 deselected and ruff check/format. Root suite initially had one usage-test timeout, then isolated usage 1/1 and unchanged-timeout bounded full suite 80 files / 296 tests passed. Logs were checked at `/tmp/nano-feat604/`; the original failure remains recorded in [code-review.md](code-review.md). No full suite was rerun by this verifier.
- M1-R1–R3 include real product interaction and visual judgment. Their independently dispatched reviewer must supply that verdict; component/build evidence and this report do not replace it. This report does not treat the worker's unvisited English/role/fault states as already accepted.

## Correctness

| Requirement / Scenario | 实现位置 | 测试与直接证据 | 状态 |
|---|---|---|---|
| S1 身份与资料编辑 | `account/account-page.tsx:24`, `:29`, `:89`, `:101`, `:141` | `account-page.test.tsx:107`; real save/menu/refresh self-check; deferred-read witness described in code review | Main path covered; W1 affects late GET after success |
| S2 电脑管理与空状态 | `account/account-page.tsx:53`, `:289` | summary/link and absence of repeated device rows at `account-page.test.tsx:107`; count/zero branch directly inspected | Covered statically; full visual role/state judgment remains reviewer-owned |
| S3 团队资格 | `account/account-page.tsx:45`, `:225`, `:266` | none/pending/suspended/member/admin branches, separate personal flag and membership return path inspected; current admission coverage `company-access.test.tsx:45`, `:54`, `:63` | Covered implementation/current permission boundary; no claim these tests exercise every new account badge |
| S4 容量与预设分层 | `policies/policies-page.tsx:97`, `:102`, `:130`; `attachment-capacity-panel.tsx:39`, `:97`, `:133` | `policies-page.test.tsx:74`; `company-access.test.tsx:104`; policy desktop capture; server service/owner limits and visibility inspected | Covered: used + reserved, remaining, server limit, optional owners and unenforced presets |
| S5 只读成员 | `policies/policies-page.tsx:48`, `:97`, `:198`, `:228` | `company-access.test.tsx:92`; inactive redirect and admin-only panel/render/write guard inspected | Covered; no capacity request/save controls for ordinary members |
| S6 放弃与合法输入 | `account/account-page.tsx:25`, `:79`, `:177`; `policies/policies-page.tsx:34`, `:116`, `:255` | account `:144`, `:160`; policies `:106`; trim/required/min/step/submit guards inspected against server validation | Covered |
| S7 保存失败与后台刷新 | account `:20`, `:29`, `:163`; policies `:57`, `:61`, `:229` | account `:160`, `:184`; policies `:106`, `:140`; real mobile failure/retry self-check; independent deferred-GET witness on both real components | WARNING W1: earlier GET can overwrite accepted save response |
| S8 加载与容量故障 | account `:207`; policies `:278`; capacity `:76` | account `:210`; policies `:106`, `:158`; failed capacity hides meter instead of claiming zero; queries are independent | Covered initial-load/error/retry seam |
| S9 桌面、手机与语言 | `settings-surfaces.css:1`, `:234`, `:383`; both pages' labels/status/alert; en/zh resources | actual desktop and 320/390px self-check captures; responsive CSS and i18n keys inspected | Explicit structure covered; full English/keyboard/visual journey verdict remains independent product review |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 账号只编辑显示名，详情下沉，电脑只保留摘要 | 是 | `account/account-page.tsx:89`, `:141`, `:289`; no `listNodes` dependency |
| 空间资格独立，延续现有 membership/成员路由 | 是 | account `:225`, `:269`, `:282`; existing MembershipPage consumes `state.from` |
| 真容量优先，未接入执行的六项预设诚实分组 | 是 | policies `:16`, `:97`, `:106`; capacity reads its own API; no backend/runtime change |
| 本地草稿保护，成功响应成为最新已存状态 | 部分；W1 | account `:20`, `:29`; policies `:57`, `:61`; late pre-save GET remains able to replace the successful response |
| 只读成员读值，局部故障不阻断无关区域 | 是 | policies `:198`, `:278`; capacity `:76`; account related sections outside profile loading branch |
| 手机单栏、保存反馈与底栏不冲突，中英完整 | 显式契约已实现；产品裁决待独立 reviewer | shared CSS media block, status/alert in save footer, real mobile-failure screenshot |

The diff stays in Web client code/tests/evidence, uses existing APIs and AuthStore/React Query, and introduces no global form/draft framework, backend permission change, private DSH import, cross-package dependency or second runtime. Current authority remains `docs/specs/im/auth-tenancy.md:114` for six stable policy fields/permissions and `:155` for team/personal admission; IM retains server-side authorization. Canonical current specs have not been prematurely overwritten.

### Prototype / Reference Contract

| Reference contract | Milestone projection | Implementation evidence | Durable evidence | Status |
|---|---|---|---|---|
| 身份、空间与关联管理 | M1-R1/W1 | account identity form, details, separate spaces and linked management | `account-desktop.png`, `account-mobile-320.png`, prototype account reference; implementation-validation path/limits | Explicit responsibility split covered; broader role observations belong to product reviewer |
| 容量与分组预设 | M1-R2/W1 | capacity precedes notices/grouped presets; owners in details; ordinary members read text | `policies-desktop.png`, prototype policies narrow; component tests for capacity/read-only/error | Explicit structure covered; remaining real state/viewport observations belong to reviewer |
| 编辑反馈与恢复 | M1-R3/W2 | draft ownership; alert/status in footer; validation and pending locks | `policies-mobile-failure.png`, recorded real retry, page tests and independent race reproduction | WARNING W1 for save/refresh ordering; failure feedback location is covered |

These captures prove the documented isolated static-build states. Capacity fixture bytes are database samples, not actual uploads of those sizes. The screenshots do not establish production, native iOS, future regression protection or unvisited roles/languages. No subjective visual-quality verdict is issued here.

## Issues

### CRITICAL

None.

### WARNING

#### W1 — A pre-save background GET can undo the visible successful save

- Contract: spec S1/S7 (`spec.md:27`, `:58`), design decision 4 (`design.md:37`) and editable-state delta (`specs/im/auth-tenancy.md:24`). Success must make the accepted response the saved baseline and provide truthful visible feedback during supported background refresh.
- Locations: `src/IM/frontend/src/features/settings/account/account-page.tsx:29` and `src/IM/frontend/src/features/settings/policies/policies-page.tsx:61`.
- Evidence: both success callbacks call setQueryData without canceling an in-flight same-key GET, then clear the draft. A deferred read started before PATCH was released after the successful response. Both actual components reverted Saved → Original while Changes saved remained visible; the account AuthStore retained Saved. Independent witness run: 1 file / 2 cases passed at 11:42:58 +08:00. Method, exact command and local harness locator are in [code-review.md](code-review.md#finding-evidence).
- Existing tests cover refetch while editing, but stop before this save/read ordering. Add this ordering to the existing page tests, cancel the same-key fetch before adopting the response/clearing the draft, and rerun the narrow affected tests. Do not change the spec to accept stale success feedback. No full-suite repetition is needed solely to reproduce this case.

### SUGGESTION

None.

## Corrected Delta Reconciliation

No post-review delta correction exists at this frozen snapshot. All three current added delta requirements and the full implementation diff were reconciled, rather than treating an empty correction as a reason to skip behavior coverage.

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `specs/im/auth-tenancy.md:5` — Web 账号设置分清个人资料、空间资格与关联管理 | account identity/details, separate membership and computer summary/zero state | account summary/save/discard tests; existing admission tests; recorded real account self-check | aligned |
| `specs/im/auth-tenancy.md:14` — Web 策略设置区别实际容量与未接入执行的预设 | capacity panel uses server limit and used + reserved; policies groups/not-applied notice/read-only controls | policies capacity/read-failure tests and ordinary-member access tests | aligned |
| `specs/im/auth-tenancy.md:24` — Web 账号与策略编辑反馈清楚且保留未提交内容 | regular failure/dirty/validation paths implemented; late pre-save GET can replace successful baseline and leave incorrect success feedback | regular paths covered; independent deferred-GET witness proves W1 on both pages | implementation-mismatch |

### Uncovered Observable Behavior

None requiring an additional delta requirement. The unit's changed responsibilities, navigation, actual-capacity/preset distinction, local editing states and responsive presentation fall under the three existing delta requirements and S1–S9. W1 is an implementation defect against the agreed behavior, not a reason to weaken the delta.

Outcome: **implementation-mismatch**.

No self-created service/browser environment needs cleanup. Temporary component reproduction files are outside the repository under `/tmp/nano-feat604/static-review/`; only this report and code-review.md were added, with no commit. Fix W1 before PR approval and retain the separately required product-review verdict.

## Round 2 — Targeted Closure

- verifier: `/root/static_review`; verification_mode: `targeted-closure`, including corrected-delta closure for the prior implementation-mismatch.
- executed_base: `9ebe12f8553a593f6179784b0276849fb14e5358` (unchanged).
- finding_origin_head / pre_fix_head: `a2f3a66688e3bc1e17920f2976506bf1d222bc16`.
- validated_at: `49795346290faadb5039fb1b371db5f6d145562a`.
- fix_delta_range: `a2f3a66688e3bc1e17920f2976506bf1d222bc16..49795346290faadb5039fb1b371db5f6d145562a`.
- prior_verification_path: this report, Round 1; focus_issues: `W1`.
- requires_full_verification: `false`.
- verdict: **PASS — W1 closed; 0 CRITICAL / 0 WARNING / 0 SUGGESTION.** This supersedes Round 1's implementation block at the new snapshot. Real-product S7 acceptance remains a separate reviewer obligation.

### Coverage and retained conclusions

The full closure diff was inspected. Only the two page success callbacks and the existing page regression tests change product behavior; other delta files integrate previously completed reports, real-product screenshots, runtime and validation evidence. Spec/design/delta have no changes. Round 1's unrelated requirement/design/current-authority/must-match checks remain valid; new product screenshots do not enlarge this verifier's visual-acceptance claims.

| Focus / contract | Implementation evidence | Direct validation | Conclusion |
|---|---|---|---|
| W1; S1/S7; design decision 4; editable-state delta | `account/account-page.tsx:29` and `policies/policies-page.tsx:61` await exact same-key cancellation before adopting accepted response and clearing draft | Existing page tests now hold pre-save GET until after PATCH; assert accepted value and success status after releasing it | **closed** |
| Test protection at the lowest relevant seam | New cases in `account-page.test.tsx:237` and `policies-page.test.tsx:178` exercise actual components, QueryClient and API response ordering | Red log: 2 failures before fix; green: 3 files / 21 pass. Independent direct Vitest rerun: both selected cases passed at 11:57:20 +08:00, 2.24s | covered |
| No new authority/architecture behavior | No API, permission, backend, runtime, dependency or global-state change | Full fix delta and unchanged spec/design/delta inspected | retained |

The cancellation removes the earlier query result's ability to replace the successful baseline even if the underlying HTTP promise finishes later. Awaiting it before the cache write also preserves mutation-pending locks until the response and draft state have been reconciled. No additional state machinery is required.

Validation locators and exact independent command are recorded in [code-review.md](code-review.md#round-2--closure). The completed final frontend log was inspected: 93 files / 879 tests passed; build passed again. Prior root build/typecheck, bounded root 80 files / 296 tests, Python 56 tests, ruff and unchanged-dependency audit evidence remain applicable. The initial root timeout remains in the historical record without claiming a proven unique cause. No full suite was intentionally repeated by this verifier.

### Corrected-delta closure

This closes the prior Corrected Delta Reconciliation's implementation-mismatch; the original Round 1 result above is preserved as history. The delta text is unchanged because W1 required implementation correction, not contract relaxation.

| Delta item | Latest reconciliation | Outcome |
|---|---|---|
| `specs/im/auth-tenancy.md:5` — account responsibilities | Fix only orders successful-save completion; identity/space/computer responsibilities and unaffected evidence retained | aligned |
| `specs/im/auth-tenancy.md:14` — actual capacity and unenforced presets | No change to capacity, groups, visibility, limits or read-only semantics; previous evidence retained | aligned |
| `specs/im/auth-tenancy.md:24` — recoverable and truthful edit/save feedback | Same-key in-flight GET canceled before accepted response becomes baseline; actual component regression tests prove old response cannot restore old visible value | aligned |

Uncovered Observable Behavior: **None.** The fix adds no behavior outside the existing edit/save contract.

Latest corrected-delta outcome: **aligned**.

The scope remains targeted; no new shared-boundary impact requires full verification. This static/consistency pass does not close product reviewer R1-G1 by itself: independently observing the controlled refresh/save path in the rebuilt real client remains that reviewer's gate. Only the two assigned reports were appended, no commit was created, and no review-owned runtime needs cleanup.
