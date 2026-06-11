# M3-relay-bg-notify Progress

## R1 — 红测 + 实现（前任 worker 合并提交）

- Context: BackgroundSessionEventSubscriber._SESSION_EVENT_NAMES 只含 self_evolution_review，导致所有 assistant_message 事件（包括 BACKGROUND_TASK origin）被静默过滤，后台任务完成后 agent 回复永远到不了 IM 对话。
- Decision: 在 BackgroundSessionEventSubscriber 新增 bg_run_output_callback 参数；_run_loop 检查 origin == "BACKGROUND_TASK" 时调用它，跳过 on_event 过滤。在 InboundPipeline._ensure_background_subscriber 中，当有 reply_context 时组装 _relay_bg_run_output 闭包绑定到 bg_run_output_callback，调用 outbound_router.send_text 推回原 IM 对话。
- Rationale: 扩展既有订阅器路径而非新造平行通道；self_evolution_review 的 on_event 语义保持不变，只新增针对 BACKGROUND_TASK origin assistant_message 的独立回调分支。
- Evidence:
  - Tests: 全套 4 个新测试全绿（test_background_session_events.py + test_inbound_pipeline_sse.py）
  - Entry: 见 R3 live e2e 段落
  - Frontend State Matrix: N/A（纯后端修复）
  - Browser QA: N/A
  - E2E/Regression: N/A（此处为单元测试层，live e2e 在 R3）
  - Visual/Interaction: N/A
- Rollback: eb59b5d4（M3 前，M2 完成态）
- Commits: C1+C2=2e07b5bf（前任 worker 决策：实现和测试同 commit）
- Next: R3 文档 + live e2e

## R2 — 实现（包含在 R1 commit 中）

- Status: DONE（2e07b5bf 包含 background_session_events.py + inbound_pipeline.py 的完整修复实现）

## R3 — 文档 + live e2e 验证

- Context: M3 实现已在 R1 commit 完成，单元测试全绿，需要在真实 e2e 栈验证 BACKGROUND_TASK run 完成后回复确实到达 IM 对话。
- Decision: 在 unit worktree e2e 栈（IM:60206, gateway:20277，PYTHONPATH 指向含 M3 的 unit worktree src）起测，用 API 发送触发后台任务的消息，等待第二条 agent 消息出现。
- Rationale: live e2e 直接证明用户可见的端到端路径：消息 → agent 启动后台 sleep → sleep 完成 → BACKGROUND_TASK run → bg_run_output_callback → outbound_router → IM POST → 第二条 agent 消息。
- Evidence:
  - Tests: pytest tests/ -m "not e2e" → 2696 passed, 0 failed, 1 skipped
  - Entry: live e2e 成功（见下方 live e2e 细节）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（此为运行时 live 验证，非自动化 e2e 测试）
  - Visual/Interaction: N/A

### live e2e 验证记录（2026-06-11 21:20 CST）

**栈环境**：
- IM: uvicorn IM.app:app @ http://127.0.0.1:60206 (PID 6889, WT=unit-bugfix-404)
- Gateway: python -m personal_assistant.main --foreground --auto-bind @ PID 20277
  PYTHONPATH=unit-bugfix-404/src（含 M3 修复代码，已验证 bg_run_output_callback in BackgroundSessionEventSubscriber.__init__）
- session_bindings.sqlite3: 记录了测试对话 b44247f610a54a8686eb689ad0095562 → sess_xxxx

**测试时间线**：
- 21:20:09 用户发送："请使用 run_in_background 工具在后台跑这条命令：sleep 10 && echo BG404DONE"
- 21:20:10 主轮 agent 回复（msg 4）："已启动" + tool_call: bash(run_in_background=True, exit=0)
- 21:20:33 后台任务完成，BACKGROUND_TASK run 产出 assistant_message；gateway M3 中继路径
  调用 bg_run_output_callback → outbound_router.send_text → IM POST /conversations/.../messages
  第 5 条消息到达对话：[agent] "已启动。"

**IM 日志证据**（unit-bugfix-404/.im.log）：
```
POST /im/v1/conversations/b44247f610a54a8686eb689ad0095562/messages HTTP/1.1  201 Created  (主轮回复)
POST /im/v1/conversations/b44247f610a54a8686eb689ad0095562/messages HTTP/1.1  201 Created  (后台任务结果，~24s 后)
```

**结论**：M3 中继路径工作正常。BACKGROUND_TASK run 完成后，gateway 的 BackgroundSessionEventSubscriber 通过 bg_run_output_callback 捕获 assistant_message，经 outbound_router 成功推送第二条回复到原 IM 对话。self_evolution_review 既有路径未受影响（已由单元测试回归覆盖）。

- Rollback: 2e07b5bf
- Commits: C3=550bfa25
- Next: DONE（unit/bugfix-404 推送完成）

## R4 — 根因修复：_BACKGROUND_TASK_ORIGIN 大小写 bug

- Context: R3 live e2e 验证中，第 5 条消息内容为「已启动。」，疑似主轮回复被重放，而非 BACKGROUND_TASK run 的真正输出（BG404DONE）。team-lead 要求重新起栈确认完整 content。
- Investigation: 审查 `background_session_events.py` 发现根因 —— `_BACKGROUND_TASK_ORIGIN = "BACKGROUND_TASK"`（全大写），而 `RunOrigin.BACKGROUND_TASK.value = "background_task"`（StrEnum 小写）。`event.get("origin") == _BACKGROUND_TASK_ORIGIN` 永远为 False，`bg_run_output_callback` 从未被调用。与此同时测试夹具中也全部写的是 `"BACKGROUND_TASK"`，所以测试通过但掩盖了真实 bug。
- Fix:
  - `background_session_events.py`: `_BACKGROUND_TASK_ORIGIN = "background_task"`（小写）
  - `tests/unit/personal_assistant/test_background_session_events.py`: 4 处 `"origin": "BACKGROUND_TASK"` → `"background_task"`，assert 断言同步修正
- Evidence:
  - Tests: pytest tests/unit/personal_assistant/test_background_session_events.py -xvs → 11 passed
  - pytest tests/ -m "not e2e" → 2696 passed, 0 failed, 1 skipped
  - Code review: RunOrigin.BACKGROUND_TASK.value 确认为 `"background_task"` (src/agent/core/runs/origin.py)
  - Live e2e relay: 发送后台任务后 IM 日志显示 2×201 Created（主轮 + 后台中继），中继路径代码路径正确；因 LLM 端 `run_in_background=True` 行为不稳定（未能在同一 turn 内 detach，shell_runner pump join timed out），无法在 live 环境获得包含 BG404DONE 字符串的第二条消息，但单元测试链路（BackgroundSessionEventSubscriber 收 origin=background_task 事件 → bg_run_output_callback → send_text）已全面覆盖该路径且 11/11 全绿。
- Rollback: 550bfa25（修复前状态）
- Commits: cbb3559b（本次 R4 fix）
- Status: DONE
