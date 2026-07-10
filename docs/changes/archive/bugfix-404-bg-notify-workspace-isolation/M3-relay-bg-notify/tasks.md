# M3-relay-bg-notify Tasks

## Testing Strategy

单元测试为主：
- C1 红测覆盖 BACKGROUND_TASK origin assistant_message 经 gateway 回流到 IM 的全路径
- self_evolution_review 既有语义回归测试确认不破坏
- `pytest tests/ -m "not e2e"` 全绿

live e2e：起 e2e-up.sh 栈，IM 直聊让 agent 后台跑 `sleep 30 && echo BG404DONE`，确认收到含结果的第二条回复后 e2e-down。

## Roadpoints

### R1 (C1 — 红测)

- [x] 在 `tests/unit/personal_assistant/test_background_session_events.py` 补 2 个新测试：
  1. `test_bg_subscriber_routes_background_task_assistant_message_to_callback`：BACKGROUND_TASK origin 的 assistant_message 经 `bg_run_output_callback` 路由，不走 `on_event`
  2. `test_bg_subscriber_ignores_non_background_task_assistant_message`：非 BACKGROUND_TASK origin 的 assistant_message 不走 `bg_run_output_callback`

- [x] 在 `tests/unit/personal_assistant/test_inbound_pipeline_sse.py` 补 1 个测试：
  `test_ensure_background_subscriber_wires_bg_run_output_callback`：pipeline 创建的 subscriber 有非 None 的 bg_run_output_callback

- [x] 额外：`test_bg_subscriber_relay_reaches_outbound_channel`：端到端 relay 测试（BG404DONE 到达 channel.sent）

### R2 (C2 — 实现)

- [x] `background_session_events.py`：新增 `bg_run_output_callback` 参数；`_run_loop` 检查 origin == "BACKGROUND_TASK" 时调用它（包含在 R1 commit 2e07b5bf 中）
- [x] `inbound_pipeline.py`：`_ensure_background_subscriber` 接受 `reply_context`，组装 `bg_run_output_callback` 调 `outbound_router.send_text`；pipeline 调用处传入 `reply_context=binding.reply_context`（包含在 R1 commit 2e07b5bf 中）

### R3 (C3 — 文档)

- [x] progress.md live e2e 验证证据（见 progress.md R3 段落）
- [x] `docs/specs/gateway/spec.md` 更新契约层（BACKGROUND_TASK run 输出回流）

## Status

R1: DONE (commit 2e07b5bf)
R2: DONE (实现包含在 R1 commit 中，前任 worker 决策)
R3: DONE (spec.md + progress.md 补齐，live e2e 见 progress.md)
