# M113 — IM 消息交付状态与 SSE 回执收口

## 1. 基线与最终验收
- 基线命令：
  - `cd /Users/czj/Repos/nano-multiagent && python -m pytest tests/im_service -q 2>&1 | tail -80`
- 基线结果：`9 failed, 45 passed`
- 最终验收命令：
  - `cd /Users/czj/Repos/nano-multiagent && python -m pytest tests/im_service -q 2>&1 | tail -80`
- 最终结果：`55 passed in 1.48s`

## 2. 最终结论
1. 非 relay 的 IM 写消息现在会在同一仓储事务内同步写入 `message.sent` 与 `message.delivered`，并把消息主记录收口为 `delivery_status=completed`。
2. `create_message`、`list_messages`、`/events`、SSE reconnect 现在对本地消息统一暴露 completed 口径，修复了 REST/SSE/历史回读不一致。
3. relay 路径不会被这次修复回退：`target_node_id` 存在时仍保留 `sent`，继续等待 `GatewayHandler` 的真实 receipt/report 把消息推进到 completed 或 failed。
4. worktree 内 `data/dev-tasks.json` 与 `data/locks` 已改为指向主仓共享副本，避免并行执行时状态分叉。

## 3. Roadpoint 记录

### R1 修复消息持久化后的 completed 口径
- Context:
  - 当前回归全部集中在 `tests/im_service/*`：本地写消息后主记录仍停留在 `sent`，同时缺失 `message.delivered` 事件，导致 REST/SSE/历史回读口径不一致。
  - 但 M109 已明确 relay 场景下 `message.delivered` 只能由真实 gateway receipt 触发，不能简单恢复成“所有消息创建即 delivered”。
- Decision:
  - 给 `MessageRepository.create_message` 增加 `auto_complete_delivery` 开关，默认 `True`，用于本地 IM 直写场景在事务内补写 `message.delivered` 并更新消息主记录为 `completed`。
  - `POST /im/v1/conversations/{id}/messages` 在 `target_node_id is None` 时保留默认自动收口；当请求走 relay 时显式传 `False`，继续由 gateway receipt 作为完成态单一真源。
  - delivered payload 复用 sent payload，并把 `progress_state` 收口到 `completed`，便于 SSE/history 共用同一消息元数据。
- Rationale:
  - 这样可以最小改动修复 M34 本地消息历史语义，同时不回退 M109 对真实回执边界的收敛。
  - 把口径切换放在消息创建入口而不是 SSE 渲染层，能够一次修复 REST 返回、历史回读和 SSE replay 三个出口。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M113 && python -m pytest tests/im_service -q` → `55 passed in 1.42s`
  - Entry: `tests/im_service/integration/test_messages_api.py::test_sse_events_roundtrip_for_sent_message` 现可同时读到 `message.sent` 与 `message.delivered`。
  - Entry: `tests/im_service/integration/test_chat_flow_integration.py::test_human_chat_roundtrip_with_history_and_conversation_list` 现断言列表接口返回 `delivery_status == ["completed", "completed"]`。
  - Entry: `tests/im_service/integration/test_gateway_websocket_api.py` 与 `tests/acceptance/test_im_gateway_real_acceptance.py` 额外回归通过，证明 relay 真实回执语义未回退。
- Rollback:
  - 若需重做本 Roadpoint，可回退到 `08e3ca9`（仅红测，尚未修改实现）；若只回退文档，可回退到 `da7c63e`。
- Commits: C1=`08e3ca9`, C2=`da7c63e`, C3=本提交
- Next:
  - 若后续需要继续区分“本地入库完成”和“前端历史可见完成”，应在协议层补正式语义说明，而不是在测试里继续隐式约定。
