# M15-fix-r5: progress

## R1 — Gateway 预创建 agent 占位消息 + run_context_store 注入正确 message_id

- Context: R5 验收发现 `message.created` 从不触发。根因：kernel `run_status=running` 在 SSE 客户端连接前就已发出，`kernel_event_observer` 注册在 SSE 流打开之后，永远捕获不到 `turn_start` 信号。旧实现在 observer 里监听 `run_status=running` 再发 `turn_start` frame——这在 SSE 有竞争的情况下必然丢失。
- Decision: 在 `_build_relay_lifecycle_callback` 的 `accepted` 阶段，通过 IM REST API（`POST /im/v1/conversations/{id}/messages`）同步预创建 agent 占位消息，将返回的 agent `message_id` 存入 `run_context_store`，覆盖原来的用户 `message_id`。`_build_kernel_event_observer` 中的 `run_status=running` 分支改为 `pass`（占位已在 accepted 阶段完成）。`im_http_client` 参数从 `im_config_sync_client._get_client()` 传入（复用已有认证 httpx.Client）。
- Rationale: accepted 阶段发生在 kernel 开始执行前（同步调用），此时 IM 连接稳定、agent_id 确认，不存在 SSE 竞态。预创建后 delta/completed 帧都用 agent message_id，用户消息内容不被污染。
- Evidence:
  - Tests: `pytest tests/unit/IM/test_streaming_chain.py tests/unit/test_inbound_pipeline_streaming.py` — 13 passed
  - Entry: 新增 `test_accepted_phase_calls_im_api_to_create_agent_message`、`test_accepted_phase_stores_agent_message_id_not_user_message_id`、`test_observer_does_not_send_turn_start_when_message_id_already_set`、`test_observer_uses_agent_message_id_for_delta` 4 项断言覆盖全路径
- Rollback: `git revert 99c9f352`
- Commits: C1=5ea0bba8, C2=99c9f352, C3=（本次）
- Next: 更新 tasks.md → R1/R2 DONE；e2e 验证待环境就绪后补充
