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
