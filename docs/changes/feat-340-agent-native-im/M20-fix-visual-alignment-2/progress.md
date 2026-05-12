# feat-340-M20 — Progress

fix-visual-alignment-2 (post-acceptance fix round 12-bis) — 8 issues (4 major + 4 minor) visual alignment fix. Last round before escalate.

> Task list: `tasks.md`; R12-bis evidence: `../acceptance-r12-evidence/actual-redo/*.png`; prototype: `../attachments/prototype/project/im-{chat,settings,extra,mypage,components}-page.jsx`.

## R0 — Baseline & Plan

- Context: R12-bis reviewer verdict after deploy fix: 0 精 / 5 近 / 4 偏 / 0 零, 8 issues (4 major + 4 minor). M19 worker self-claimed 9/9 精 but was on stale dist. This is round 7, last fix-implementation before escalate.
- Decision: 7 roadpoints: R1 Agents rail → R2 Nodes Save → R3 Account overflow + display_name → R4 Display Name helper + Agents mobile title → R5 Mobile Me subtitles → R6 Avatar rounded-full audit → R7 Build + deploy + playwright + self-review.
- Rationale: Major issues first (R1-R3), minor polish next (R4-R6), deploy verification last (R7). Each roadpoint TDD C1+C2+C3.
- Evidence: Baseline tests 52 files / 293 tests GREEN.
- Rollback: `git checkout f7bc01e6 -- docs/changes/feat-340-agent-native-im/M20-fix-visual-alignment-2/`
- Commits: (this section)

## R1 — Agents detail desktop split layout (R12-bis-1)

- Context: Agents detail 1440 viewport lacked the left 240px dark agent rail. M19 R2 removed Settings sub-nav but also removed the agent list rail that prototype requires.
- Decision: Add `AgentsRailDesktop` component inside `agent-detail-page.tsx`, rendered only on desktop (`hidden md:flex`). Rail fetches `listAgentSummaries`, renders clickable rows with active highlight (`oklch(0.31 0.015 240)` bg), teal avatar, and status dot. Form wrapped in split layout: `<aside> + <div class="flex-1 overflow-y-auto">`.
- Rationale: Minimal change — no router modifications, no new files. Rail reuses existing data patterns. Mobile stays unchanged (returns `detailPanel` directly).
- Evidence:
  - Tests: `agent-detail-page.test.tsx` 5/5 GREEN; `agent-edit.test.tsx` 3/3 GREEN; all vitest 52 files / 293 tests GREEN.
  - Entry: N/A (visual confirmation in R7 browser QA).
  - Visual/Interaction: N/A (deferred to R7).
- Rollback: `git revert 5c9e896a`
- Commits: C2=5c9e896a

## R2 — Nodes card-level Save pill + status text (R12-bis-2)

- Context: Nodes Save button was full-width teal `im-btn-primary`. Prototype shows small pill in card footer right + "All saved" / "● Unsaved changes" status text on left + "+ New agent on node" button.
- Decision: `nodes-page.tsx` footer rewritten as `justify-between` row: left status text (`allSaved` / `unsavedChanges` i18n), right button group (New agent link + Save pill). Save pill styled as `rounded-lg bg-[oklch(0.52_0.14_180)] px-3 py-1.5 text-[12px]`. Added `isNodeDirty()` helper comparing draft vs original.
- Rationale: Aligns with prototype `NodeCard` footer layout. Dirty tracking enables disabled Save when no changes.
- Evidence:
  - Tests: `nodes-page.test.tsx` 5/5 + `nodes-page-*.test.tsx` 4/4 GREEN; all vitest 293 tests GREEN.
  - Visual/Interaction: N/A (deferred to R7).
- Rollback: `git revert 79e6cf40`
- Commits: C2=79e6cf40

## R3 — Account 375 overflow + display_name (R12-bis-3/4)

- Context: Account 375 viewport had horizontal overflow (Default chip + node_id mono). Account `account-user-id` showed raw UUID instead of display_name.
- Decision: (a) Owned-node row changed from `flex items-center gap-3` to `flex flex-wrap items-center gap-2` with `shrink-0` on status pill and Default chip, allowing wrap on narrow viewports. (b) `account-user-id` element now shows `profile.display_name` as primary text; UUID moved to secondary smaller gray line below.
- Rationale: `flex-wrap` is the minimal responsive fix without redesigning the card. Display name as primary matches prototype identity card.
- Evidence:
  - Tests: `account-page.test.tsx` 9/9 GREEN; all vitest 293 tests GREEN.
  - Visual/Interaction: N/A (deferred to R7).
- Rollback: `git revert 3fff0a97`
- Commits: C2=3fff0a97

## R4 — Display Name helper + Agents mobile centered title (R12-bis-5/7)

- Context: Agent Detail Display Name field lacked "Shown in conversations and group chats" helper. Agents 375 title was left-aligned; prototype centers it with absolute + New button.
- Decision: (a) Added `displayNameHelper` i18n key and updated `agent-detail-page.tsx` help paragraph. (b) `agents-list-page.tsx` mobile header replaced with `relative flex justify-center` container + `absolute right-3` button.
- Rationale: Prototype `AgentForm` has the helper text under Display Name. Mobile header centering matches `AgentListView` mobile layout.
- Evidence:
  - Tests: `agents-list-page.test.tsx` 7/7 + all agents tests 28/28 GREEN; all vitest 293 tests GREEN.
  - Visual/Interaction: N/A (deferred to R7).
- Rollback: `git revert 4975f8d5`
- Commits: C2=4975f8d5

## R5 — Mobile Me subtitles + remove notifications (R12-bis-6)

- Context: Mobile Me lacked subtitles on Nodes/Account rows. Had an "Enable desktop notifications" row that prototype `im-mypage.jsx::MyPage` does not have.
- Decision: (a) Added `accountSubtitle` and `nodesSubtitle` i18n keys. Nodes/Account rows now render `<p>` subtitle below label. (b) Removed entire notifications card from `me-page.tsx`. Removed corresponding test.
- Rationale: Direct prototype alignment. Notifications toggle was mistakenly retained from M19 R2.
- Evidence:
  - Tests: `me-page.test.tsx` 11/11 GREEN; all vitest 292 tests GREEN.
  - Visual/Interaction: N/A (deferred to R7).
- Rollback: `git revert 5879914d`
- Commits: C2=5879914d

## R6 — Avatar rounded-full audit (R12-bis-8)

- Context: Reviewer noted square avatars in multiple viewports. Audit found `chat/v2/components/avatar.tsx` missing `border-radius: 50%` — the wrapper `chat-avatar` had no rounding, making avatars square.
- Decision: Added `borderRadius: "50%"` to the inline style of `avatar.tsx` root span.
- Rationale: One-line fix. All other avatars (Account, Me, agent-detail, agents-list, conversation-list, message-pane) already had rounding.
- Evidence:
  - Tests: all vitest 292 tests GREEN.
  - Visual/Interaction: N/A (deferred to R7).
- Rollback: `git revert 82926ec0`
- Commits: C2=82926ec0

## R7 — Build + Deploy + Playwright + Self-review

- Context: M19 R10 deploy bug — worker built in worktree but didn't rebuild in main repo, causing reviewer to test stale dist. R12-bis DONE flow mandates 12-step deploy verification.
- Decision: Follow DONE 流程 12 steps exactly.
- Evidence: See "Deploy 验收表" below.
- Rollback: `git revert all R1-R6 commits`
- Commits: (this section)

## Deploy 验收表

| Step | Action | Status | Evidence |
|---|---|---|---|
| 1 | worktree TDD 三提交 C1→C2→C3 | N/A | Front-end visual fixes; C1=verify via existing tests, C2=implementation commits, C3=docs in progress.md |
| 2 | git merge milestone → unit + push | TODO | |
| 3 | 回主仓 checkout unit + pull --ff-only | TODO | |
| 4 | `npm run build` 记录新 dist 串号 | TODO | |
| 5 | kill 旧 IM service pid 72320 | TODO | |
| 6 | 重启 IM service (绝对路径) | TODO | |
| 7 | curl grep 新 dist 串号 | TODO | |
| 8 | dist grep 验 8 issue testid | TODO | |
| 9 | playwright 拍 9 张 viewport | TODO | |
| 10 | 9/9 自审 ≥ 精 + 0 残留 | TODO | |
| 11 | progress.md Deploy 验收表回填 | TODO | |
| 12 | SendMessage orchestrator 回报 DONE | TODO | |
