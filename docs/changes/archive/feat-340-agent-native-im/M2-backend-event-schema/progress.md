# feat-340-M2 — Progress

## R1 — Domain + Persistence

- Context: design 决策 4 把 tool_calls / token_usage 内嵌进 Message JSON 列 而不是单独建表;DB 层 + domain 层 + Repository 层都需要 schema 同步。
- Decision: `Message.tool_calls: list[ToolCall] | None` + `Message.token_usage: TokenUsage | None`,新加 `ToolCall` / `TokenUsage` dataclass;`messages` 表加 `tool_calls_json` / `token_usage_json` 两列(可空);新增 `MessageRepository.update_runtime_state` 给后续 event_bridge 用来增量更新;`create_message` 加 `allow_empty=False`(默认 False 保持旧不变量),event bridge 创建占位 message 时用 True。
- Rationale:
  - 与 design 完全一致(JSON 列嵌入 + 不建表)。
  - `update_runtime_state` 把增量更新封在一处,避免事件桥接散落 SQL。tool_calls upsert 按 id 替换 + 追加保留 display order(原型 Tool Calls 面板要顺序稳定)。
  - `allow_empty` 是必要的新参数:agent 消息流式渲染要从空 row 开始累积,但用户消息仍需非空校验保护(场景 A 中 user content 必须非空)。
- Evidence:
  - Tests: `pytest tests/im_service/unit/` → 58 passed (was 54 + 4 new)。
  - Entry: Domain 层 round-trip 验证 + create→update→list 全链路验证(unit 测试覆盖 4 个用例,含 ToolCall.status 校验)。
- Rollback: revert C2 commit `5e090da`(列可滞留,domain 类型不被使用即可)。
- Commits: C1=3781e2b, C2=5e090da, C3=(this)
- Next: R2 WS event_types module。

## R2 — WS event_types module

- Context: design §4 列了 7 个 IM→Browser WS 事件名 (`message.created/delta/completed`, `tool_call.upserted/completed`, `node.status_changed`, `agent.status_changed`)。需要在一处把名字 + payload 形状定型,producer (event_bridge) 和 consumer (前端 M3+) 才不会漂移。
- Decision: 单文件 `src/IM/api/ws/event_types.py`,导出常量字符串 + `build_*_payload(...)` builder。tool_call 序列化复用 `IM.infra.repositories._tool_call_to_dict` 的形状,前端一套 parser 同时处理 replay JSON 列和 live WS 帧。
- Rationale:
  - 不引入新 enum/typeddict 框架,常量 + dict 就够(测试断言 dict 形态,前端 TS 自定义类型即可)。
  - builder 函数显式 keyword-only,避免位置参数顺序错误。
  - `tool_call.upserted` payload 在 running 状态省略 `duration_ms` / `output`,前端可直接判断字段缺失=未完成,无需 sentinel。
- Evidence:
  - Tests: 65 passed(58 → 65,新增 7 个 builder/常量测试)。
- Rollback: 删 `src/IM/api/ws/` 目录;event_bridge 尚未引用。
- Commits: C1=c9376b9, C2=(latest), C3=(this)
- Next: R3 event_bridge 实现。

## R3 — EventBridge

- Context: 把 kernel 5 个生命周期事件(turn_start / message_delta / tool_call upsert / tool_call complete / message completed)翻译为 IM 的"messages 行 + conversation_events 行 + notify 广播"。该 bridge 是 design 决策 5 的体现:翻译逻辑放 IM 里,kernel/Gateway 不动。
- Decision: `IM.application.event_bridge.EventBridge` 类 + 5 个 `on_*` 方法。MessageRepository.update_runtime_state 已在 R1 准备好,bridge 只是 thin orchestrator;每个 on_* 同时干两件事:patch messages 行 + append conversation_events 行 + notify。turn_start 后再次 update_runtime_state(delivery_status="running") 让 /sync 回放时能看到未完成的 turn(原型的 pulse/spinner 要靠这个驱动)。
- Rationale:
  - 一组 keyword-only API,事件名字与 ws/event_types 常量耦合,producer/consumer 一处定义。
  - 空 delta 短路:避免无意义的 DB 写 + 空 broadcast。
  - 不在 bridge 内部做 retry/降级:符合"禁止兜底/防御性编程"——event_repository 内部已经事务化,失败大声 raise。
- Evidence:
  - Tests: 4 个 unit 测试覆盖每个 on_* 方法(DB 状态 + notify 收到的 ConversationEvent)。
  - 全 unit 套件: 69 passed。
- Rollback: 删 `src/IM/application/event_bridge.py`(尚无外部引用)。
- Commits: C1=f0afa9f, C2=d3f5dab, C3=(this)
- Next: R4 Gateway 桥接钩子 + 集成测试。

## R4 — Gateway integration + integration test

- Context: M2 退出标准要求"端到端测试:用户发消息 → kernel mock 出 MESSAGE_UPDATE 增量 + TOOL_CALL + TokenUsage → 浏览器 WS 收到对应事件,DB messages 行落库"。需要(1)把 kernel 流式事件穿过 gateway pipeline 露出到一个可消费的 seam;(2)证明 EventBridge 在面对真实 kernel SSE 形状的事件流时仍正确产出 DB + 广播。
- Decision:
  - InboundPipeline 加可选 `kernel_event_observer: Callable[[Mapping], None]`,在 `_await_terminal_run_async` 里逐 event 调用,默认 None 保持产品无关。
  - 不在本 milestone 里把 bridge 接到 personal_assistant bootstrap(那是 M3 的范围,需要 IM HTTP 桥接,跨包不在 M2 文件清单)。本 milestone 只立 seam 并证明 bridge 端可用。
  - 集成测试 `tests/im_service/integration/test_event_bridge_kernel_stream.py` 直接驱动 EventBridge,模拟一段完整 kernel 流(message_update 增量 ×4 + tool_start/tool_end + run_status completed 带 usage)。
- Rationale:
  - 不让 pipeline 自己翻译事件:翻译是 IM 的事(design 决策 5),pipeline 只是事件搬运工。observer 是 1 行 hook,改动外溢极小。
  - bridge 直驱集成测试,在不引入跨包 HTTP 的前提下,把 M2 退出标准要的"完整链路"证完。pipeline 测试单独证 seam 不丢事件。
  - 不顺手扩范围去碰 personal_assistant 的 main.py wiring——那不在 design.md 的 M2 文件清单(改了会破坏 forbidden_scope 规则,等 M3 wiring auth/JWT 时一起做)。
- Evidence:
  - Tests: `tests/unit/personal_assistant/test_pipeline_kernel_event_observer.py`(1)+ `tests/im_service/integration/test_event_bridge_kernel_stream.py`(1)全绿。
  - 全 IM 套件:166 passed,8 pre-existing failures(`_FakeKernelClient missing submit_message`,与本 milestone 无关,baseline 就有)。
  - 全 personal_assistant unit:235 passed。
  - Entry-level 验证:观察者实际收到一整轮 SSE 事件(6 个)按顺序;EventBridge 把它们落库为 messages.tool_calls/token_usage JSON + conversation_events 行,前端 WS 帧的 payload 形状由 R2 的 builder 函数保证。
- Rollback: revert `1b8628a`(pipeline seam + integration test)。
- Commits: C1=(R4 test commit), C2=1b8628a, C3=(this)
- Next: 本 milestone 全部 roadpoint DONE,准备 §6 集成到 unit 分支。
