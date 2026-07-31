# M127 会话与可用 Agent 可发现性收口

## Milestone Goal
让普通用户在 Web IM 中看清楚除了默认 starter chat 之外还存在哪些聊天目标，并理解不同会话类型、选择路径与当前目标语义，不再把产品体验误解为只有单一 seeded demo。

## Roadpoints

### RP1. Baseline and discoverability gap confirmation
- Read `/Users/czj/Repos/nano-multiagent/.worktrees/M120-retest/docs/需求.md` §三.4 and the product review gap in `/Users/czj/Repos/nano-multiagent/.worktrees/M120-retest/ACCEPTANCE/IM-gateway-product-review.md` lines 69-121.
- Inspect the current Web IM list/detail/starter path inside `/Users/czj/Repos/nano-multiagent/.worktrees/M127/src/IM/frontend/src/features/chat`.
- Create fresh milestone TASKS/PROGRESS records in the canonical M127 worktree.

### RP2. Tight product-grade discoverability improvements
- Enrich conversation list semantics so users can distinguish direct agent chat, group chat, system feed, and agent-to-agent chat.
- Add clear target labels and short helper copy in list/detail views so users understand what each conversation represents.
- Keep the default starter path, but explicitly point users to the wider set of available targets instead of only the seeded chat.
- Keep implementation scope tight to discoverability and target-selection clarity.

### RP3. Focused validation and acceptance evidence
- Run focused frontend tests that prove browser-visible discoverability copy and selection semantics.
- Run frontend build to ensure shipped assets still compile.
- Produce fresh M127 acceptance evidence under `ACCEPTANCE/`; if no browser harness exists in this worktree, record the exact blocker and use the strongest browser-visible test evidence available.
- Update user-facing docs so product behavior and documentation stay aligned.

## Final checkpoint
- [ ] Canonical worktree only (`/Users/czj/Repos/nano-multiagent/.worktrees/M127`)
- [ ] M127 TASKS/PROGRESS created and updated
- [ ] Conversation discoverability semantics improved in product UI
- [ ] Focused tests added or updated and passing
- [ ] Fresh acceptance evidence written under `ACCEPTANCE/`
- [ ] User-facing docs aligned with behavior
- [ ] Milestone committed on `milestone/M127`
