# M151 Progress — 修复真实群聊中 @Agent 路由与回执闭环

## Summary
- Canonical worktree used: `/Users/czj/Repos/nano-multiagent/.worktrees/M151`
- Branch confirmed: `milestone/M151`
- Root cause fixed in the IM relay payload construction layer rather than in browser setup: group relay snapshot selection ignored the addressed `@agent` and could bind the task to the wrong participant.

## What changed
### Code
- `/Users/czj/Repos/nano-multiagent/.worktrees/M151/src/IM/application/relay_service.py`
  - Added `_extract_mentioned_agent_ids()` to normalize `@agent` parsing from real message text.
  - Changed group relay snapshot resolution to collect participant agents first, then prefer the explicitly mentioned agent when building the relay payload.
  - Preserved the previous fallback to the first participant agent when no valid mention is present, limiting blast radius for direct chat and ambient behavior.

### Tests
- `/Users/czj/Repos/nano-multiagent/.worktrees/M151/tests/im_service/unit/test_relay_service.py`
  - Refactored fixture setup so agent profiles can be seeded explicitly.
  - Added regression coverage that a group relay payload addressed to `@agent-b` snapshots `agent-b` and its prompt/version into relay metadata.
- `/Users/czj/Repos/nano-multiagent/.worktrees/M151/tests/im_service/integration/test_m136_group_chat_flow.py`
  - Updated the fake kernel client to accept session metadata like the real gateway path.
  - Tightened the group mention roundtrip assertion so both session creations stay pinned to the addressed agent rather than drifting to the first participant.

## Real gap captured
- Prior live acceptance already proved the browser and IM API could create group threads containing multiple real agents.
- The remaining failure was product behavior: real group `@agent` messages did not yield an in-thread agent reply because the relay payload could snapshot the wrong agent before the Gateway even processed the task.
- This pass fixes that routing decision at the source of the payload.

## Evidence
### Gate command
- `cd /Users/czj/Repos/nano-multiagent/.worktrees/M151 && PYTHONPATH=src pytest -q tests/im_service/unit/test_relay_service.py tests/im_service/integration/test_m136_group_chat_flow.py tests/unit/personal_assistant/test_gateway_pipeline.py tests/unit/personal_assistant/test_main.py tests/unit/personal_assistant/test_m102_gateway_im_connection.py tests/im_service/integration/test_m103_im_gateway_e2e.py`

### Expected proof target
- Group mention regression green
- Existing gateway/direct-chat regressions still green
- Existing `NO_REPLY` product-path silence regressions still green

## Rollback point
- Minimal rollback is limited to:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M151/src/IM/application/relay_service.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M151/tests/im_service/unit/test_relay_service.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M151/tests/im_service/integration/test_m136_group_chat_flow.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M151/TASKS/M151-修复真实群聊中@Agent路由与回执闭环.md`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M151/PROGRESS/M151-修复真实群聊中@Agent路由与回执闭环.md`

## M141 re-validation note
- If the gate is green, M141 should be ready for real-browser re-validation of the addressed-agent path because the known routing bug is now covered at both unit and integration layers.
- Final confidence still depends on rerunning the true browser/live stack acceptance.
