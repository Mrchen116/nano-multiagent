# M125 Progress — 默认绑定后首条消息链路收口

## Scope
- Milestone: M125
- Branch: `milestone/M125`
- Canonical worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M125`

## Baseline
- Read first: `LOGBOOK.md`, `COMMENTING_GUIDE.md`, `/Users/czj/Repos/nano-multiagent/.worktrees/M120-retest/ACCEPTANCE/M120-acceptance.md`
- Blocking gap confirmed from M120 retest: documented startup + bind could succeed while post-bind default chat still failed to prove a usable first-message path; UI also lacked a product-grade offline blocker state.
- Baseline command: `pytest -q`
- Baseline result: currently running in canonical M125 worktree; this baseline also serves as the post-port regression suite because milestone work started immediately after setup.

## Roadpoint Notes

### RP1. Baseline and gap confirmation
- Confirmed the canonical worktree exists and is on `milestone/M125`.
- Confirmed there were no existing `TASKS/M125-*.md` or `PROGRESS/M125-*.md` records, so created fresh milestone records.
- Verified the canonical worktree already contains the intended `tests/acceptance/test_im_gateway_real_acceptance.py` update at line 321 for the documented `8011` bind URL.

### RP2. Port useful frontend closure work into canonical M125
- Ported the useful patch from the prior nested agent worktree into the canonical M125 worktree only.
- Ported files:
  - `src/IM/frontend/src/features/chat/im-chat-api.ts`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.tsx`
  - `src/IM/frontend/src/features/chat/components/message-pane.tsx`
  - `src/IM/frontend/src/features/chat/im-chat-api.test.ts`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
  - `src/IM/frontend/src/features/chat/components/message-pane.test.tsx`
  - `src/IM/frontend/README.md`
  - `tests/acceptance/test_im_gateway_real_acceptance.py`
- Follow-up closure completed in the canonical worktree:
  - Updated the remaining stale `4173` bind assertion in `tests/e2e/test_m112_real_process_roundtrip_e2e.py:488` to `8011`.
- Design closure introduced by the port:
  - Bootstrap now tracks both `targetNodeId` and `targetNodeStatus`.
  - Send readiness is resolved centrally so UI can distinguish `unbound`, `offline`, and `ready` states.
  - Composer placeholder/helper text now gives actionable product feedback instead of exposing a half-connected send box.
  - Tests now cover the offline blocker copy as well as the explicit send-failure feedback path.

### RP3. Validate real and automated acceptance evidence
- Rollback point before M125 changes: `c139ae030c3766ab1414dcb4a9a480fc23c90be5`
- Targeted frontend regressions passed:
  - `npm test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/chat-workspace-page.test.ts src/features/chat/components/message-pane.test.tsx`
  - Result: `3` files, `17` tests passed.
- Targeted Python regressions passed:
  - `pytest -q tests/acceptance/test_im_gateway_real_acceptance.py tests/e2e/test_m112_real_process_roundtrip_e2e.py tests/unit/personal_assistant/test_main.py`
  - Result: `28` tests passed.
- Full suite passed in the canonical worktree:
  - `pytest -q`
  - Result: `761 passed, 4 skipped`.
- Real browser validation completed against the documented default path:
  - Started IM on `http://127.0.0.1:8011`.
  - Started Gateway with canonical `node-config.yaml` and observed node `my-macbook` online.
  - Opened the real IM-hosted Web IM at `/chat` in Chromium via Playwright.
  - Opened the default conversation from the starter card and sent `Hello from M125 browser acceptance`.
  - Browser-visible result showed the user message, relay node label `my-macbook`, and completed agent reply `Hello! Welcome—how can I help today?`.

## Evidence Log
- Acceptance context: `/Users/czj/Repos/nano-multiagent/.worktrees/M120-retest/ACCEPTANCE/M120-acceptance.md`
- Canonical rollback commit before edits: `c139ae030c3766ab1414dcb4a9a480fc23c90be5`
- Browser evidence files:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M125/ACCEPTANCE/m125-chat-home.png`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M125/ACCEPTANCE/m125-chat-opened-conversation.png`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M125/ACCEPTANCE/m125-chat-after-send.png`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M125/ACCEPTANCE/m125-browser-evidence.json`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M125/ACCEPTANCE/m125-im-api-evidence.json`
- Supplemental screenshot captured during early inspection:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M125/ACCEPTANCE/m125-root.png`

## Final Status
- Current status: Complete
- Ready for M120 re-acceptance: Yes
- Remaining blocker inside M125 scope: None recorded
