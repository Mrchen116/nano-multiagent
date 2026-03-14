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
  - 待执行。
- Decision:
  - 待执行。
- Rationale:
  - 待执行。
- Evidence:
  - 待执行。
- Status: TODO

### R2 收口群聊 Gateway 多 Agent 路由与 NO_REPLY 语义
- Context:
  - 待执行。
- Decision:
  - 待执行。
- Rationale:
  - 待执行。
- Evidence:
  - 待执行。
- Status: TODO

### R3 验证、文档与收口
- Tests:
  - 待执行。
- Verification notes:
  - 待执行。
- Commits:
  - C1=`<pending>`
  - C2=`<pending>`
  - C3=`<pending>`
- Status: TODO

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
- 文档建档已完成；代码修复与验证待执行。
