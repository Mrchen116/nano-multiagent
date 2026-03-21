# TASKS: M250 — 修复 send_message 工具不可用

## Roadpoint 列表

### R1 — ResolvedProductConfig.default_tool_ids + bootstrap optional 合并 + runtime 双路过滤

**Acceptance:**
1. `ResolvedProductConfig` 有 `default_tool_ids: list[str] | None = None` 字段
2. `bootstrap_product` 构建 tool_registry 时使用 `default_tool_ids + optional_tool_ids` 的并集
3. `ResolvedProductConfig.default_tool_ids` 被赋值为 `profile.default_tool_ids`
4. `_resolve_session_available_tools` 无 tool_allowlist 时按 `default_tool_ids` 过滤
5. 有 tool_allowlist 时仍走 allowlist 过滤（覆盖 send_message 进入的路径）

**Tests Plan:**
- unit: `ResolvedProductConfig` 字段存在，bootstrap 结果有正确 tool_registry 及 default_tool_ids
- contract: runtime 双路过滤逻辑断言
- integration: bootstrap_personal_assistant 已有测试覆盖 send_message 不在默认集合

**Expected Tests:**
- `tests/unit/test_resolved_product_config_default_tool_ids.py`
- `tests/unit/test_runtime_tool_allowlist_filtering.py`

**DoD:** test_command 全绿 + C1/C2/C3

**Status:** TODO

---

### R2 — SendMessageTool 无状态化 + ToolContext.session_metadata 字段

**Acceptance:**
1. `ToolContext` 新增 `session_metadata: Mapping[str, Any]` 字段（默认空）
2. `ToolRegistry.execute()` 从 `hook_context.metadata` 注入 `session_metadata`
3. `SendMessageTool` 无模块级 `TOOL` 单例、无 `bind_dispatcher`
4. `SendMessageTool.run()` 从 `ctx.session_metadata["gateway_dispatch_url"]` 读取 URL，做 HTTP POST
5. `gateway_dispatch_url` 缺失时抛出明确错误

**Tests Plan:**
- unit: run() 正常分发 + 缺 URL 时错误信息
- contract: 无 TOOL 单例、无 bind_dispatcher 断言

**Expected Tests:**
- `tests/unit/personal_assistant/test_send_message_tool.py`（新建或扩展）

**DoD:** test_command 全绿 + C1/C2/C3

**Status:** TODO

---

### R3 — inbound_pipeline 注入 gateway_dispatch_url

**Acceptance:**
1. `_build_session_metadata` 注入 `gateway_dispatch_url` 字段
2. URL 指向 `http://127.0.0.1:<gateway_internal_port>/internal/dispatch`
3. `InboundPipeline` 接收 `gateway_internal_port` 参数（默认 8089）

**Tests Plan:**
- unit: `_build_session_metadata` 结果包含 `gateway_dispatch_url` 字段

**Expected Tests:**
- `tests/unit/personal_assistant/test_gateway_pipeline.py` 扩展

**DoD:** test_command 全绿 + C1/C2/C3

**Status:** TODO

---

### R4 — Gateway 暴露 POST /internal/dispatch 端点

**Acceptance:**
1. `GatewayRuntime` 或其 HTTP server 暴露 `POST /internal/dispatch`
2. 接受 `{text, to, from_session_id}`，通过 `OutboundRouter` 或 `IMConnectionManager` 投递
3. 返回 `{"ok": true}` 或错误描述
4. 端点测试：mock 请求可验证 ok 响应

**Tests Plan:**
- unit: 端点处理器单元测试
- integration: 通过 HTTP 请求验证端点

**Expected Tests:**
- `tests/unit/personal_assistant/test_internal_dispatch_endpoint.py`

**DoD:** test_command 全绿 + C1/C2/C3

**Status:** TODO
