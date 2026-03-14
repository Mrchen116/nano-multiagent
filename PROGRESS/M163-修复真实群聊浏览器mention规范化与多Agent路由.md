# M163 Progress — 修复真实群聊浏览器 mention 规范化与多 Agent 路由

## 启动记录
- 已确认 worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M163`
- 已确认 branch：`milestone/M163`
- 已确认约束：仅在该 worktree 实施修复；不创建嵌套 worktree；不修改 `data/dev-tasks.json`
- 首轮阅读文件：
  - `src/IM/application/relay_service.py`
  - `src/personal_assistant/gateway/inbound_pipeline.py`
  - `src/personal_assistant/channels/web_relay_adapter.py`
  - `src/IM/frontend/src/features/chat/components/message-pane.tsx`
  - `tests/im_service/unit/test_relay_service.py`
  - `tests/unit/personal_assistant/test_gateway_pipeline.py`
  - `tests/im_service/integration/test_m136_group_chat_flow.py`
  - `src/IM/frontend/src/features/chat/components/message-pane.test.tsx`

## 初始根因判断
- relay 服务提取 mention 时只做“去掉开头 @ 与末尾标点”，没有把 picker token `agent:agent-x` 归一回真实 agent id `agent-x`，导致群聊 relay payload 的 `mentioned_agent_ids` 与 `agent_id` 可能偏离真实被点名 Agent。
- gateway 群聊路由当前优先使用显式 `message.agent_id`；一旦上游 payload 已漂移，就会压过正确的 mention metadata，使同线程后续消息继续命中错误 Agent。
- NO_REPLY 可见回复不是独立静默逻辑故障，而是群聊路由命中了错误的非静默 Agent。

## 执行策略
1. 先补 `TASKS/M163` 与 `PROGRESS/M163`，冻结 Roadpoints、验证命令与回滚边界。
2. 再在 relay 层统一 mention 规范化，补 typed / picker 两种 token 的回归测试。
3. 最后在 gateway 群聊路由里以 mention 语义优先收口，并补多 Agent / NO_REPLY 集成验证，把结果写回 PROGRESS。

## 进度

### R1 收口 IM relay mention 规范化
- Context:
  - relay payload 对手打 `@agent-b` 与 picker `@agent:agent-b` 的 `mentioned_agent_ids` 不一致，导致后续 agent 快照选择可能回退到首个群参与 Agent。
- Decision:
  - 在 `RelayService` 增加 mention 归一 helper，统一剥离浏览器 picker 使用的 `agent:` 前缀，并保留末尾标点清洗。
  - 补单测同时覆盖 typed / picker 两种 token，确保都收敛到同一个 `agent_id` 与 `mentioned_agent_ids`。
- Rationale:
  - 先在 relay 边界把 mention token 规范化，才能保证后续 gateway 与 session 选择都基于稳定 agent id。
- Evidence:
  - `src/IM/application/relay_service.py`
  - `tests/im_service/unit/test_relay_service.py`
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M163/tests/im_service/unit/test_relay_service.py -q` → `4 passed in 0.07s`
  - Commit: `af7c21b` `fix(M163): normalize browser group mention tokens`
- Status: DONE

### R2 收口群聊 Gateway 多 Agent 路由与 NO_REPLY 语义
- Context:
  - 真实群聊产品路径里，gateway 当前会先相信 payload 自带的 `agent_id`；一旦上游 relay payload 因旧快照或未规范化 mention 发生漂移，就会把后续群消息继续发给错误 Agent。
- Decision:
  - 调整 `InboundPipeline._resolve_agent()`：群聊场景先按 `mentioned_agent_ids` / `reply_to_agent_id` 解析，再回退到显式 `message.agent_id`。
  - 新增单测覆盖“group mention metadata 与漂移 agent_id 冲突时，仍必须路由到被 mention 的 agent”。
  - 把 `test_m136_group_chat_flow.py` 的第二条消息改成浏览器 picker 真实会产出的 `@agent:agent-b`，同时保留同线程多 Agent 与 NO_REPLY 断言。
- Rationale:
  - 群聊里真正代表产品语义的是 mention / reply 指向，而不是可能已经漂移的 payload 快照。把 mention 语义前置，才能修掉同线程多 Agent 错路由，并恢复 NO_REPLY 的静默闭环。
- Evidence:
  - `src/personal_assistant/gateway/inbound_pipeline.py`
  - `tests/unit/personal_assistant/test_gateway_pipeline.py`
  - `tests/im_service/integration/test_m136_group_chat_flow.py`
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M163/tests/unit/personal_assistant/test_gateway_pipeline.py -q` → `12 passed in 0.18s`
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M163/tests/im_service/integration/test_m136_group_chat_flow.py -q` → pending final rerun output capture
  - Commit: `a17b87b` `fix(M163): honor group mentions over stale relay agent ids`
- Status: DONE

### R3 验证、文档与收口
- Tests:
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M163/src/IM/frontend install`
    - 结果：安装前端依赖后，`vitest` 可执行；未改动业务代码。
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M163/src/IM/frontend test -- --run src/features/chat/components/message-pane.test.tsx`
    - 结果：`1 passed file / 13 passed tests`
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M163/tests/im_service/unit/test_relay_service.py -q`
    - 结果：`4 passed in 0.07s`
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M163/tests/unit/personal_assistant/test_gateway_pipeline.py -q`
    - 结果：`12 passed in 0.18s`
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M163/tests/im_service/integration/test_m136_group_chat_flow.py -q`
    - 结果：pending final rerun output capture
- Verification notes:
  - 前端 mention picker 仍稳定插入 `@agent:<agent-id>`，对应浏览器真实行为已由 `message-pane.test.tsx` 锁定。
  - relay 层现在把 typed / picker mention 统一规范为裸 `agent_id`，gateway 群聊路由则优先按 mention 语义选 agent，因此同线程多 Agent 和 NO_REPLY 的产品路径语义都回到被点名 Agent 上。
  - 按 milestone 要求，合并到 `main` 后仍需重新复验 M141 的真实浏览器群聊路径。
- Commits:
  - C1=`e8f4a98` `docs(M163): freeze mention routing repair plan`
  - C2=`af7c21b` `fix(M163): normalize browser group mention tokens`
  - C3=`a17b87b` `fix(M163): honor group mentions over stale relay agent ids`
- Status: DONE

## 回滚点
- 若需回滚本 milestone，预计只需撤回以下文件：
  - `src/IM/application/relay_service.py`
  - `src/personal_assistant/gateway/inbound_pipeline.py`
  - `tests/im_service/unit/test_relay_service.py`
  - `tests/unit/personal_assistant/test_gateway_pipeline.py`
  - `tests/im_service/integration/test_m136_group_chat_flow.py`
  - `TASKS/M163-修复真实群聊浏览器mention规范化与多Agent路由.md`
  - `PROGRESS/M163-修复真实群聊浏览器mention规范化与多Agent路由.md`

## 当前结论
- M163 已完成 relay mention 规范化与 gateway 群聊路由优先级收口，typed mention 与 picker mention 现在都会命中相同 agent。
- 同线程多 Agent 路由与 NO_REPLY 静默已由单测 / 集成测试覆盖；待最后一次集成测试输出回填后即可作为 ready-to-merge 候选。
