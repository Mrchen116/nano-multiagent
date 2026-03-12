# M127 browser evidence summary

This milestone requires browser-visible proof for conversation discoverability and target selection clarity.

## Browser automation availability
- No Playwright or dedicated browser automation harness exists in the canonical M127 worktree.
- Because of that, fresh evidence for M127 is captured through browser-visible frontend assertions plus a production build of the shipped Web IM assets.

## Fresh browser-visible assertions
Focused frontend tests now prove that the normal `/chat` path visibly explains available chat targets instead of only showing a seeded starter demo:
- conversation list header explains that users can discover direct agent chats, shared group threads, and agent-to-agent coordination from one list;
- conversation list legend explains the semantics of `Direct agent chat`, `Agent-to-agent chat`, and `Group chat`;
- list rows show `kind_label`, `Target: ...`, and a short discoverability hint for each conversation;
- starter card explicitly tells users to use the conversation list for other direct agent chats, agent-to-agent threads, or group chats;
- conversation detail header shows the selected target type and target label so the current selection path stays clear after opening a thread.

## Executed commands
```bash
npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M127/src/IM/frontend test -- --run src/app/router.test.tsx src/features/chat/chat-layout.test.tsx src/features/chat/chat-workspace-page.test.ts
npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M127/src/IM/frontend run build
```

## Results
- Focused frontend discoverability tests: `3 passed (13 tests)`
- Frontend production build: passed

## Supporting files
- `/Users/czj/Repos/nano-multiagent/.worktrees/M127/src/IM/frontend/src/features/chat/components/conversation-list.tsx`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M127/src/IM/frontend/src/features/chat/components/message-pane.tsx`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M127/src/IM/frontend/src/features/chat/mock-chat-api.ts`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M127/src/IM/frontend/src/features/chat/chat-layout.test.tsx`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M127/src/IM/frontend/src/app/router.test.tsx`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M127/src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
