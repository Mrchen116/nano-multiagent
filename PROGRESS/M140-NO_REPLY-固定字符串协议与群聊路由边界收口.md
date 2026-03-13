# M140 Progress — NO_REPLY 固定字符串协议与群聊路由边界收口

## Summary
- Canonical worktree used: `/Users/czj/Repos/nano-multiagent/.worktrees/M140`
- Branch confirmed: `milestone/M140`
- Read handoff/requirement docs from main repo before coding.
- Landed TDD-first minimal closure for group-chat `NO_REPLY` on the real Gateway/IM path.

## What changed
### Code
- `/Users/czj/Repos/nano-multiagent/.worktrees/M140/src/personal_assistant/gateway/inbound_pipeline.py`
  - Added group-only `NO_REPLY` detection via `text.strip() == "NO_REPLY"`
  - Suppresses outbound send when group reply is exactly `NO_REPLY`
  - Preserves lifecycle completion and observability through `reply_text` plus `detail={"suppressed_by": "no_reply_token"}`
  - Allows `PipelineResult.outbound` to be `None` when suppressed
- `/Users/czj/Repos/nano-multiagent/.worktrees/M140/src/personal_assistant/main.py`
  - Keeps completed relay receipt semantics and appends suppress marker into receipt detail string

### Tests
- `/Users/czj/Repos/nano-multiagent/.worktrees/M140/tests/unit/personal_assistant/test_m103_gateway_im_integration.py`
  - Added group mention + `NO_REPLY` silent-path regression
- `/Users/czj/Repos/nano-multiagent/.worktrees/M140/tests/im_service/integration/test_m136_group_chat_flow.py`
  - Added real relay path regression asserting no outbound group message while receipts still complete
- `/Users/czj/Repos/nano-multiagent/.worktrees/M140/tests/unit/personal_assistant/test_main.py`
  - Added callback regression for completed receipt detail on suppressed reply

## Red → Green evidence
### Red intent locked
- Wanted failure mode: mentioned group message enters kernel, kernel returns `NO_REPLY`, Gateway wrongly sends visible text.
- New tests encode that behavior boundary directly.

### Green result
- Focused unit suite passed.
- Focused integration suite passed.
- Focused relay lifecycle suite passed.
- Combined targeted suite passed: `10 passed in 0.53s`.

## Final verification result
- Command: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M140/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M140/tests/unit/personal_assistant/test_m103_gateway_im_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M140/tests/im_service/integration/test_m136_group_chat_flow.py /Users/czj/Repos/nano-multiagent/.worktrees/M140/tests/unit/personal_assistant/test_main.py`
- Result: `10 passed in 0.53s`

## Commands run
- `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M140/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M140/tests/unit/personal_assistant/test_m103_gateway_im_integration.py -k "no_reply or group_message"`
- `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M140/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M140/tests/im_service/integration/test_m136_group_chat_flow.py -k "no_reply or explicit_agent_mentions_roundtrip"`
- `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M140/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M140/tests/unit/personal_assistant/test_main.py -k "no_reply_suppression or relay_lifecycle"`
- `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M140/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M140/tests/unit/personal_assistant/test_m103_gateway_im_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M140/tests/im_service/integration/test_m136_group_chat_flow.py /Users/czj/Repos/nano-multiagent/.worktrees/M140/tests/unit/personal_assistant/test_main.py`

## Boundary check
- mention gate preserved
- multi-agent explicit mention routing preserved by existing M136 roundtrip test
- direct chat remains visible and unchanged

## Risk / rollback
- Main risk is receipt detail string formatting being an interim observability contract rather than structured schema.
- Minimal rollback: revert the two production files and three M140 tests.

## Merge / board state
- Not merged into `main` in this pass.
- `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json` not touched.
- Canonical M140 worktree kept for handoff/further validation.

## Next step
- Milestone closure is ready: mark TASKS/PROGRESS done, commit on `milestone/M140`, and hand back residual risk notes only.
