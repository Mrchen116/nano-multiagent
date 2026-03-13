# M151 Task — 修复真实群聊中 @Agent 路由与回执闭环

## 背景
- 真实验收已证明问题不是环境缺失，而是产品缺陷：真实 Web IM -> IM API -> Gateway 的群聊链路中，用户在共享线程里发送 `@agent-x ...` 后，消息只作为用户消息停留在线程内，没有得到被点名 Agent 的线程内回复。
- M141 需要基于真实浏览器复验多 Agent 群聊、`@agent` 路由以及 `NO_REPLY` 静默语义，因此必须先补上真实产品路径中的群聊点名闭环。

## 目标
1. 群聊 relay payload 必须优先绑定到被点名的 agent，而不是错误地回退到首个参与者；
2. 真实群聊路径中，被点名 agent 回复、未点名 agent 保持静默；
3. `NO_REPLY` 仍然在产品路径表现为静默，不向 UI 泄漏固定字符串；
4. 不破坏直聊与既有动态同步行为。

## 设计
- 在 `src/IM/application/relay_service.py` 中：
  - 抽出更稳健的 mention 解析逻辑，支持从消息正文中提取并清洗 `@agent-id`；
  - 在会话参与者快照中先收集群聊内可用 agent，再按 `mentioned_agent_ids` 优先选择目标 agent；
  - 仅当没有任何可匹配 mention 时，才维持原有回退策略。
- 在测试中补齐：
  - IM relay service 单测：锁定“群聊中显式提及 agent-b 时，payload 必须快照到 agent-b”；
  - M136 集成测试：锁定真实群聊 roundtrip 中显式 mention 始终落到被点名 agent，且 `NO_REPLY` 静默边界不回退。

## 验收门禁
- `PYTHONPATH=src pytest -q tests/im_service/unit/test_relay_service.py tests/im_service/integration/test_m136_group_chat_flow.py tests/unit/personal_assistant/test_gateway_pipeline.py tests/unit/personal_assistant/test_main.py tests/unit/personal_assistant/test_m102_gateway_im_connection.py tests/im_service/integration/test_m103_im_gateway_e2e.py`

## 回滚点
- 若需要回滚，只需撤回：
  - `src/IM/application/relay_service.py`
  - `tests/im_service/unit/test_relay_service.py`
  - `tests/im_service/integration/test_m136_group_chat_flow.py`
