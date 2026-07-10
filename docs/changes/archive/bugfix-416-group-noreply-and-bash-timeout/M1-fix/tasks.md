# bugfix-416-M1: 群聊 NO_REPLY 泄漏 + 超时 bash 丢字段 — Tasks

> 对齐: ../fix.md（lite，无 design.md）

## 目标

外部可观察变化：
1. #107 群聊 fan-out 路径（流式 other-origin / background 中继）里 agent 输出 `NO_REPLY` / `HEARTBEAT_OK` 哨兵时，与主路径一致被静默抑制——不投递、不落库、不进气泡。
2. #111 bash 超时被 watchdog 收口后，IM 气泡仍展示其 command / description（与正常态一致，只是状态 failed + reason），不再只剩红 ×「bash Timed out」。

## 退出标准

- [ ] `_should_suppress_no_reply` 泛化为 `(reply_text, *, in_group)`，三条投递路径统一调用；docstring 写明「新增 agent 文本投递路径必须经此守卫」。
- [ ] 群聊 fan-out other-origin + background 中继两路输出哨兵 → 不 `send_text` / 不 `bg_reply_sender`。
- [ ] `running_tool_calls` 存完整 tool_call（name + input/arguments）；reconcile 收口重发原 input/description（仅改 status=failed + reason）。
- [ ] reconcile 止转圈行为不退化（在飞 call 仍收口为 failed）。
- [ ] 前端 reducer 兜底：tool_call 合并时空 input/output 不覆盖已有非空值。

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

- 被测行为：
  - #107：群聊 fan-out other-origin 路径输出 `NO_REPLY` → 不投递。
  - #107：background 中继路径输出 `NO_REPLY` → 不 `bg_reply_sender`。
  - #107：fan-out 非哨兵内容仍正常投递（不误杀）。
  - #111：reconcile 收口后 tool_call payload 仍带原 input（command/description）。
  - #111：前端 reducer 收到空 input/output 的合并事件不覆盖已存非空值。
- 已有测试在：
  - #107：`tests/unit/personal_assistant/test_inbound_pipeline_session.py`（主路径抑制已有，扩展 fan-out 两路）。
  - #111 后端：`tests/unit/personal_assistant/test_tool_end_detail_passthrough.py` 同款 observer 驱动 helper，新建 `tests/unit/personal_assistant/test_reconcile_preserves_tool_input.py`（reconcile 专项，与 tool_end 关注点不同）。
  - #111 前端：`src/IM/frontend/src/features/chat/v2/chat-stream-reducer.test.ts`（扩展）。
- 落层/目录/marker：tests/unit/personal_assistant/（无 marker）；前端 vitest。
- 可选依赖 importorskip：无。
- 一次性验收证据：Gateway 进程内 e2e 走真实 fan-out 群聊较重；后端 observer/pipeline 入口测试 = 真实代码路径（非 mock 入口，直接驱动 pipeline.handle_inbound / observer(event)），作为回归保护。fix.md 验证段记录真实复现路径推演。

前端用户路径分类：bug-regression（reducer 纯逻辑兜底）。
UI 状态矩阵：N/A（无新 UI；reducer 是纯函数，覆盖「收口事件空字段」状态即可，由 vitest 断言）。

## Roadpoints

### R1 — #107 群聊 fan-out NO_REPLY 抑制守卫泛化 [DONE]

- 步骤:
  1. C1 红测：扩展 test_inbound_pipeline_session.py，构造群聊 fan-out other-origin assistant_message=NO_REPLY，断言不 send_text；构造非哨兵内容断言正常投递。
  2. C2 实现：`_should_suppress_no_reply(reply_text, *, in_group)` 泛化 + docstring 约束；三条路径统一调用。
  3. C3 文档：progress.md + tasks 状态。
- 验证: 后端 pipeline 测试全绿；fan-out 哨兵不投递、非哨兵正常。

### R2 — #111 超时 bash 保留 command/description [DONE]

- 步骤:
  1. C1 红测：新建 test_reconcile_preserves_tool_input.py（tool_start 记 input → reconcile 收口断言 payload 仍带 command/description）；前端 reducer 测试加空字段不覆盖 case。
  2. C2 实现：running_tool_calls 存完整 payload；reconcile 重发原 input；前端 upsertToolCall 兜底。
  3. C3 文档：progress.md + tasks 状态 + 回填 fix.md。
- 验证: 后端 + 前端测试全绿；reconcile payload 带原命令；前端空字段不抹已有值。
