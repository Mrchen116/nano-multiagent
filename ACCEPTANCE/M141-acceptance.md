# M141 Acceptance

## Scope
- Milestone: M141 — 真实群聊创建与多 Agent 端到端验收
- Acceptance date: 2026-03-14
- Runtime used: `/Users/czj/Repos/nano-multiagent/.worktrees/M104/ACCEPTANCE/m104-runtime`
- Real product entry: `http://127.0.0.1:8031/chat`
- Runtime database: `/Users/czj/Repos/nano-multiagent/.worktrees/M104/ACCEPTANCE/m104-runtime/im.db`

## Materials Read
- `/Users/czj/Repos/nano-multiagent/docs/需求.md`
- `/Users/czj/Repos/nano-multiagent/docs/operator-runbook.md`
- `/Users/czj/Repos/nano-multiagent/src/IM/frontend/README.md`
- `/Users/czj/Repos/nano-multiagent/ACCEPTANCE/M136-group-chat-evidence.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M104/ACCEPTANCE/M104-acceptance.md`
- `/Users/czj/Repos/nano-multiagent/TASKS/M151-修复真实群聊中@Agent路由与回执闭环.md`
- `/Users/czj/Repos/nano-multiagent/PROGRESS/M151-修复真实群聊中@Agent路由与回执闭环.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M146/PROGRESS/M140-NO_REPLY-固定字符串协议与群聊路由边界收口.md`

## User Journeys Exercised
1. Opened the real IM-hosted browser at `http://127.0.0.1:8031/chat` in Google Chrome via Playwright using the shipped frontend, not mocks.
2. Opened `Create group chat` in the real browser and verified the live participant picker showed:
   - `Agent M104 Browser`
   - `Agent M141 Reviewer`
   - `Agent M146 Live`
   - `OpsBot`
3. In the real browser, selected `Agent M141 Reviewer` and `Agent M146 Live`, clicked `Create selected group chat`, and verified a new live group conversation was created.
4. Opened the newly created real group thread `6e174902fe9a4b74896b3e97b8a25794` (`Agent M141 Reviewer + Agent M146 Live`).
5. In that real browser thread, sent `@agent-m141-reviewer please handle this and answer exactly as configured.` and waited for a visible reply.
6. In the same real browser thread, sent `@agent-m146-live please handle this and answer exactly as configured.` and checked both browser-visible behavior and runtime DB relay state.
7. In the same real browser thread, used the browser mention picker by typing `@`, selecting `Agent M146 Live`, and sending the inserted text.
8. For a product-path NO_REPLY validation attempt, temporarily changed `agent-m141-reviewer` config via the real IM API to `When mentioned in a group chat, reply exactly with NO_REPLY.`, then sent another browser message in the same real group thread and observed browser-visible behavior plus DB evidence, then restored the original agent config.
9. As a control, opened the existing real direct conversation `41be7cb44d8845d3a74833ec99799394` and sent a browser message to `Agent M146 Live`, confirming that the live runtime could still return `LIVE_AGENT_V3` in a direct chat.

## Passes
1. **Real browser group creation now works end to end.**
   - The live browser no longer shows only a static placeholder.
   - The participant picker exposed selectable live entries and an enabled `Create selected group chat` action after two selections.
   - Runtime DB shows the newly created group conversation:
     - conversation id: `6e174902fe9a4b74896b3e97b8a25794`
     - title: `Agent M141 Reviewer + Agent M146 Live`
     - type: `group`

2. **At least one real browser-path @mention is effective.**
   - In conversation `6e174902fe9a4b74896b3e97b8a25794`, the browser-visible message `@agent-m141-reviewer please handle this and answer exactly as configured.` produced the visible reply `Reviewer ack from M141.`
   - Runtime DB evidence for message `9805688d73ea49ec9a8fedfd9bb6380c` / relay task `b9c72df1d56a4d43ad819586ab56b28c`:
     - `mentioned_agent_ids=["agent-m141-reviewer"]`
     - `agent_id="agent-m141-reviewer"`
     - `receipt_detail="Reviewer ack from M141."`
     - `conversation_events` advanced through `message.sent -> relay.accepted -> relay.completed -> message.delivered`

3. **The runtime itself was alive during acceptance.**
   - `http://127.0.0.1:8031/` and `/chat` returned 200.
   - `http://127.0.0.1:8030/v1/health` returned 200.
   - The existing direct chat with `Agent M146 Live` still produced a browser-visible `LIVE_AGENT_V3`, so the node/kernel path was not generally down.

## Issues
### 1. Same real group thread cannot reliably route the second mentioned agent
- Severity: Blocking
- Exact evidence:
  - In the same real group conversation `6e174902fe9a4b74896b3e97b8a25794`, the second browser-path message was `@agent-m146-live please handle this and answer exactly as configured.`
  - Browser result after waiting: no visible agent reply appeared.
  - Runtime DB row for message `ec72df54d074400f90cebd4d310884aa` shows:
    - `status='dispatched'`
    - `receipt_status=NULL`
    - `receipt_detail=NULL`
    - `mentioned_agent_ids=["agent-m146-live"]`
    - but `agent_id="agent-m141-reviewer"`
    - and `system_prompt="When mentioned in a group chat, reply exactly with: Reviewer ack from M141."`
  - This proves the second real mention in the same live group thread was not routed to the addressed agent.
- Impact:
  - Exit criterion 2 failed.
  - Exit criterion 3 failed for multi-agent browser-path mention routing, because only the first mentioned agent worked.

### 2. Browser mention picker inserts a token shape the backend does not resolve correctly
- Severity: Blocking
- Exact evidence:
  - In the live browser group thread, using the mention picker inserted `@agent:agent-m146-live ` into the composer.
  - The resulting sent message was `@agent:agent-m146-live  please answer via picker route.`
  - Runtime DB row for message `e7bd7cc5d31245a5b698d142d63eef93` shows:
    - `mentioned_agent_ids=["agent:agent-m146-live"]`
    - `agent_id="agent-m141-reviewer"`
    - `status='dispatched'`
    - no completion receipt
- Impact:
  - The real browser picker path does not produce a mention token that the real relay routing path handles correctly.
  - Exit criterion 3 failed on the browser-native @mention path.

### 3. NO_REPLY still does not pass product-path acceptance
- Severity: Blocking
- Exact evidence:
  - For a live validation attempt, `agent-m141-reviewer` was temporarily updated to system prompt `When mentioned in a group chat, reply exactly with NO_REPLY.` and later restored.
  - In the same real browser group thread, message `@agent-m141-reviewer please stay silent if the product path supports NO_REPLY.` was sent.
  - Browser-visible result was still a delivered visible reply `Reviewer ack from M141.`, not silence.
  - Runtime DB for message `97c94dd88d6f45f497a023e008a035f1` recorded relay metadata with:
    - `config_profile_version=2`
    - `system_prompt="When mentioned in a group chat, reply exactly with NO_REPLY."`
    - but `receipt_detail="Reviewer ack from M141."`
  - No browser-path evidence was obtained that NO_REPLY becomes silent behavior in this milestone run.
- Impact:
  - Exit criterion 4 failed.

## Retest Focus
1. Re-run on a fresh real group thread after fixing per-turn agent routing so that the second explicit mention in the same browser-created group reaches the addressed agent instead of the previous/first agent.
2. Re-run the real browser mention-picker path after normalizing picker output so that inserted mentions match backend-recognized agent ids.
3. Re-run NO_REPLY on a fresh real browser group thread and verify the product behavior is silent, with no leaked `NO_REPLY` string and no stale old-agent reply.
4. After the fix, capture the exact browser-visible outcomes and runtime DB receipts for both agents in the same group thread.

## Verdict
- Final verdict: FAIL
- Exit criterion mapping:
  1. Real browser can select participants and create a group chat: **PASS**
  2. At least two real agents can participate in one real group thread: **FAIL**
  3. Real browser-path @agent mention is effective: **FAIL**
  4. Real NO_REPLY is silent in product behavior: **FAIL**
  5. Acceptance report with revalidation conclusion: **PASS**

## Smallest Clear Follow-up Milestone Proposal
### M161 — 修复真实群聊浏览器 @mention 规范化与同线程多 Agent 路由
- Goal:
  - Make both typed mentions and picker mentions resolve to the addressed real agent in the same live group thread, then re-run real NO_REPLY acceptance on a fresh thread.
- Exit criteria:
  1. In one browser-created live group thread, `@agent-a` and `@agent-b` each route to the addressed real agent on separate turns.
  2. Browser mention picker inserts a token format that the relay path resolves to the same addressed agent id as manual typing.
  3. Fresh-thread NO_REPLY validation shows silence in browser-visible behavior, not a leaked token and not a stale reply from the wrong agent.
  4. Relay task rows, conversation events, and browser-visible outcomes agree for all above cases.
