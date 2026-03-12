# M126 browser evidence summary

This milestone requires browser-visible proof, but no Playwright/browser automation harness exists in the canonical M126 worktree.

Fresh evidence captured for M126 therefore consists of:
- frontend test assertions proving browser-visible ownership/route summary and send-blocker copy,
- API acceptance artifact proving bind -> owned node -> send -> visible assistant reply roundtrip.

## Browser-visible assertions covered by frontend tests
- Conversation detail header shows ownership summary: `Using OpsBot on node-app-01 (online)`
- Starter card labels the route as `Current route`
- Offline bound node disables composer with placeholder `Bring the Gateway online to enable chat`
- Offline helper text is `The current bound node is offline. Bring the Gateway online or bind an online node, then retry.`
- Send failure preserves draft and shows retryable feedback

## Executed command
```bash
cd /Users/czj/Repos/nano-multiagent/.worktrees/M126/src/IM/frontend && npm test
```

Result: `15 passed (38 tests)`

## Supporting files
- `/Users/czj/Repos/nano-multiagent/.worktrees/M126/src/IM/frontend/src/features/chat/chat-layout.test.tsx`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M126/src/IM/frontend/src/features/chat/chat-routes.test.tsx`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M126/src/IM/frontend/src/features/chat/components/message-pane.test.tsx`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M126/src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M126/ACCEPTANCE/M126-api-roundtrip.json`
