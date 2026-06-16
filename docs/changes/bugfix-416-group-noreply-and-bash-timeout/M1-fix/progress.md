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

<!-- 每个 roadpoint 完成后追加。 -->
