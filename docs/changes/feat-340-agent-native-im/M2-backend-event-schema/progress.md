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
