# M140 NO_REPLY 固定字符串协议与群聊路由边界收口

## Goal
在真实 group-chat 主链路中产品化 `NO_REPLY` 固定字符串协议：命中 mention gate 并实际执行后的群聊轮次，若 kernel 最终输出精确 `NO_REPLY`，Gateway 不向群聊发送用户可见文本；同时保留 receipt/lifecycle 语义，不回退 mention gate 与多 Agent 路由。

## Scope
- Canonical worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M140`
- Branch: `milestone/M140`
- In scope:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M140/src/personal_assistant/gateway/inbound_pipeline.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M140/src/personal_assistant/main.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M140/tests/unit/personal_assistant/test_m103_gateway_im_integration.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M140/tests/im_service/integration/test_m136_group_chat_flow.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M140/tests/unit/personal_assistant/test_main.py`
- Out of scope:
  - direct chat 静默协议扩展
  - relay schema 大改
  - board / merge / worktree 清理，除非 milestone 全量完成并验收通过

## TDD record
### R1 红测
- Added focused unit red case: `test_group_message_with_mention_and_no_reply_token_stays_silent`
- Added focused integration red case: `test_group_message_with_mention_and_no_reply_token_stays_silent`
- Red intent: 证明“已命中 mention gate 且已执行”时，`NO_REPLY` 不应再作为普通文本回发到群聊。

### R2 最小实现
- Gateway 增加 group-only `NO_REPLY` 抑制判断：`text.strip() == "NO_REPLY"`
- 命中协议时：
  - 不调用 outbound router
  - 保留 `PipelineResult.reply_text == "NO_REPLY"`
  - `PipelineResult.outbound = None`
  - completed lifecycle 增加最小 detail：`suppressed_by=no_reply_token`
- relay callback 保持 completed receipt，但把 suppress 信息拼到 detail 中，便于 IM 侧观测。

### R3 边界
- mention gate 仍先于 `NO_REPLY` 生效；未命中 mention gate 的 group 消息仍直接忽略。
- direct chat 不启用静默协议。
- 多 Agent 显式 mention roundtrip 需继续保持绿。

## Verification
- `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M140/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M140/tests/unit/personal_assistant/test_m103_gateway_im_integration.py -k "no_reply or group_message"`
- `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M140/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M140/tests/im_service/integration/test_m136_group_chat_flow.py -k "no_reply or explicit_agent_mentions_roundtrip"`
- `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M140/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M140/tests/unit/personal_assistant/test_main.py -k "no_reply_suppression or relay_lifecycle"`
- `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M140/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M140/tests/unit/personal_assistant/test_m103_gateway_im_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M140/tests/im_service/integration/test_m136_group_chat_flow.py /Users/czj/Repos/nano-multiagent/.worktrees/M140/tests/unit/personal_assistant/test_main.py` → `10 passed in 0.53s`

## Status
- DONE

## Rollback
- Revert `/Users/czj/Repos/nano-multiagent/.worktrees/M140/src/personal_assistant/gateway/inbound_pipeline.py`
- Revert `/Users/czj/Repos/nano-multiagent/.worktrees/M140/src/personal_assistant/main.py`
- Remove the M140-focused tests listed above

## Next step
- None for M140 closure; any stronger receipt schema can be handled in a later milestone without reopening this scope.
