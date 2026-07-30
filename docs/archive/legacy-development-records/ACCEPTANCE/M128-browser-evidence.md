# M128 browser evidence summary

This milestone requires browser-visible proof that Web IM shows one consistent actionable failure experience for unbound, offline, and unavailable states.

## Browser automation availability
- No Playwright or dedicated browser automation harness exists in the canonical M128 worktree.
- Because of that, fresh evidence for M128 is captured through browser-visible frontend assertions plus a production build of the shipped Web IM assets.

## Fresh browser-visible assertions
Focused frontend tests now prove the shipped UI presents one product-grade failure pattern instead of splitting pre-send and on-send failures into unrelated messages:
- unbound state disables the composer before send, shows a `Chat unavailable` banner, explains that binding is required, and shows `Next: Open bind flow`;
- offline state also disables the composer before send, reuses the same `Chat unavailable` banner, explains that the bound Gateway is offline, and shows `Next: Bring Gateway online`;
- unavailable-on-send state preserves the draft, normalizes raw relay 503 failures into the same `Chat unavailable` framing, and tells the user to connect an online node and retry;
- route-level rendering assertions confirm the browser-visible placeholder and banner text match the same failure model on the real `/chat/:conversationId` route.

## Executed commands
```bash
npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M128/src/IM/frontend install
npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M128/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/components/message-pane.test.tsx src/features/chat/chat-workspace-page.test.ts src/features/chat/chat-routes.test.tsx
npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M128/src/IM/frontend run build
```

## Results
- Focused frontend failure-UX tests: `4 passed (20 tests)`
- Frontend production build: passed

## Supporting files
- `/Users/czj/Repos/nano-multiagent/.worktrees/M128/src/IM/frontend/src/features/chat/im-chat-api.ts`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M128/src/IM/frontend/src/features/chat/components/message-pane.tsx`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M128/src/IM/frontend/src/features/chat/im-chat-api.test.ts`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M128/src/IM/frontend/src/features/chat/components/message-pane.test.tsx`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M128/src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M128/src/IM/frontend/src/features/chat/chat-routes.test.tsx`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M128/README.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M128/docs/operator-runbook.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M128/src/IM/frontend/README.md`
