# bugfix-416-M1 — Progress

## R1 — #107 群聊 fan-out NO_REPLY 抑制守卫泛化

- Context: 群聊有三条 agent 文本投递路径，NO_REPLY/HEARTBEAT_OK 抑制只落在主同步回复一条；流式 other-origin（`_on_other_event`）与 background 中继（`_relay_bg_run_output`）各自只判 `content.strip()` 非空就发，哨兵泄漏进气泡并落库。
- Decision: 按 fix.md 写死的修法决策——把 `_should_suppress_no_reply(message, *, reply_text)` 泛化为不依赖 message 的 `_should_suppress_no_reply(reply_text, *, in_group)`（内部仍 `in_group and _is_no_reply_token(reply_text)`），三条路径统一调用：主路径传 `in_group=message.is_group`，fan-out 两路传 `in_group=True`（agent-to-agent 隐含群聊）。docstring 写明「任何新增 agent 文本投递路径必须经此守卫」。
- Rationale: 抑制收敛在 pipeline 应用层单一判断点，不下沉 OutboundRouter.send_text（传输层不懂协议哨兵、且覆盖不到独立的 bg_reply_sender 出口），不在两处调用点各写 if（那是第三次打补丁，下次加第四条路径照样漏）。`in_group` 而非 message 是因为 bg 中继跨 SSE 循环手里没有原 InboundMessage。
- Evidence:
  - Tests: `tests/unit/personal_assistant/ -q` 565 passed 1 skipped；新增两个 fan-out 测试（NO_REPLY 抑制 + 非哨兵正常投递）。
  - Entry: pipeline.handle_inbound 是真实代码入口（非 mock），other-origin 事件经真实 `_await_terminal_run_async` → `_on_other_event` 分派；红测断言 `channel.sent` 只含 agent-a 正常回复，NO_REPLY 不在其中。
  - Frontend State Matrix: N/A（纯后端）
  - Browser QA: N/A
  - E2E/Regression: `tests/unit/personal_assistant/test_inbound_pipeline_session.py::test_group_fanout_other_origin_no_reply_token_is_suppressed` + `::test_group_fanout_other_origin_non_sentinel_still_delivered`，pytest 绿。
  - Visual/Interaction: N/A
- Rollback: revert C2（fix commit）回到泛化前。
- Commits: C1=test 红测, C2=fix 实现, C3=docs(本段)
- Next: R2 #111

## R2 — #111 超时 bash 保留 command/description

- Context: bash 超时被 watchdog 收口时，`run_terminal_reconcile` 只能从 `running_tool_calls` 拿到工具名（旧结构 `{call_id: name}`），硬塞 `input: {}`；前端 reducer `{...t, ...next}` 浅合并又让这条空 input 覆盖 tool_start 时已存的真实命令 → IM 只剩红 ×「bash Timed out」。
- Decision:
  - 后端（主修法）：`running_tool_calls[run_id][call_id]` 改存完整 `{"name", "input"}`（tool_start 时记入，main.py:3501）；reconcile 收口（main.py:3649）从中取原 input 重发，只改 status=failed + reason。兼容旧 bare-name 形态（跨部署在飞 call）。
  - 前端（兜底）：`upsertToolCall` 用新 `mergeToolCall`——incoming 字段为空（undefined/null/""/{}）且已存值非空时，保留已存 input/output，不被空字段覆盖。
- Rationale: 主修法在源头（后端收口）补回数据，前端兜底防「任何收口事件少带字段」同类问题复发（fix.md 不变量 3）。reconcile 止转圈行为不退化：在飞 call 仍收口 failed 并 pop（test_reconcile_still_closes_in_flight_call_as_failed 断言）。
- Evidence:
  - Tests: 后端 `tests/unit/personal_assistant/test_reconcile_preserves_tool_input.py` 2 passed；前端 `chat-stream-reducer` 15 passed。
  - Entry: 后端 observer = 真实代码入口（直接驱动 `_build_kernel_event_observer` 返回的 observer，喂真实 tool_start + run_terminal_reconcile 事件），断言下发的 `tool_call_completed` payload `input` 仍含 command/description。前端 reducer 是真实 WS 事件入口（`applyWsEvent`），断言 reconcile 空 input 不抹已有命令。
  - Frontend State Matrix: bug-regression；覆盖「reconcile 收口事件空 input/output」状态。N/A 其余 UI 态（无新 UI）。
  - Browser QA: 未起浏览器；reducer 纯函数经 vitest 真实事件序列验证（见 fix.md 验证段说明为何不强行起 Gateway e2e）。
  - E2E/Regression: 后端 test_reconcile_preserves_tool_input.py + 前端 chat-stream-reducer.test.ts「reconcile 空 input 不覆盖」，均落库回归。
  - Visual/Interaction: N/A
  - 全树回归：`pytest -m "not e2e"` 2644 passed 2 skipped；前端 `vitest run` 440 passed + `tsc --noEmit` 通过。
- Rollback: revert C2（fix commit）。
- Commits: C1=test 红测（后端+前端）, C2=fix 实现, C3=docs（本段）
- Next: milestone 完成

<!-- 每个 roadpoint 完成后追加。 -->
