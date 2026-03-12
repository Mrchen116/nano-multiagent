# M127 Progress — 会话与可用 Agent 可发现性收口

## Scope
- Milestone: M127
- Branch: `milestone/M127`
- Canonical worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M127`

## Baseline
- Requirement anchor: `/Users/czj/Repos/nano-multiagent/.worktrees/M120-retest/docs/需求.md` §三.4
- Review gap anchor: `/Users/czj/Repos/nano-multiagent/.worktrees/M120-retest/ACCEPTANCE/IM-gateway-product-review.md` lines 69-121
- Baseline finding: current Web IM keeps a default starter chat, but discoverability for additional targets is too implicit and reads like a single seeded demo.

## Roadpoint Notes

### RP1. Baseline and discoverability gap confirmation
- Confirmed canonical M127 worktree exists and is the only worktree used.
- Read current frontend list/detail/starter implementation in:
  - `src/IM/frontend/src/features/chat/components/conversation-list.tsx`
  - `src/IM/frontend/src/features/chat/components/message-pane.tsx`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.tsx`
  - `src/IM/frontend/src/features/chat/mock-chat-api.ts`
- Confirmed the main discoverability gap is not transport or send readiness, but that the list/detail UI does not explain what conversation types exist or how to interpret them.

### RP2. Tight product-grade discoverability improvements
- Implemented discoverability metadata in the chat model layer:
  - enriched `ConversationSummary` / `ConversationDetail` with `kind_label`, `target_label`, and `discoverability_hint`;
  - kept the change scoped to the Web IM chat frontend.
- Updated mock data so the product now visibly includes more than one kind of target:
  - direct agent chat;
  - group chat;
  - system feed;
  - agent-to-agent chat.
- Updated the list/detail/starter UI so users can understand:
  - what kinds of conversations exist;
  - which target a row represents;
  - how the default starter relates to the wider set of available chat targets.

### RP3. Validation and acceptance evidence
- Executed validation:
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M127/src/IM/frontend test -- --run src/app/router.test.tsx src/features/chat/chat-layout.test.tsx src/features/chat/chat-workspace-page.test.ts`
  - result: `3` files passed, `13` tests passed.
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M127/src/IM/frontend run build`
  - result: passed.
- Browser automation check:
  - confirmed no Playwright or dedicated browser automation harness exists in the canonical M127 worktree.
  - recorded the blocker plus browser-visible assertions in `/Users/czj/Repos/nano-multiagent/.worktrees/M127/ACCEPTANCE/M127-browser-evidence.md`.
- User-facing doc alignment:
  - updated `/Users/czj/Repos/nano-multiagent/.worktrees/M127/src/IM/frontend/README.md` so docs now describe the conversation-type semantics visible in the UI.

## Current status
- Status: complete, pending commit
- Remaining blocker: no local browser automation harness in canonical M127; strongest available evidence has been recorded via browser-visible frontend tests plus production build.

## Evidence
- `/Users/czj/Repos/nano-multiagent/.worktrees/M127/ACCEPTANCE/M127-browser-evidence.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M127/src/IM/frontend/src/features/chat/chat-layout.test.tsx`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M127/src/IM/frontend/src/app/router.test.tsx`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M127/src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M127/src/IM/frontend/src/features/chat/components/conversation-list.tsx`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M127/src/IM/frontend/src/features/chat/components/message-pane.tsx`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M127/src/IM/frontend/src/features/chat/mock-chat-api.ts`

## Conclusion
- M127 discoverability slice is landed in the canonical worktree with fresh evidence, focused tests, and doc alignment.
- `data/dev-tasks.json` was not updated because milestone completion state has not yet been recorded through the requested final commit step.
