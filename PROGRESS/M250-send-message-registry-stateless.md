# PROGRESS: M250 — 修复 send_message 工具不可用

## 现状说明

- 基线：`tests/unit` 640 passed，pre-existing failures 在 acceptance/contract/integration 中存在，不属于本 Milestone scope
- 主要问题：
  1. `bootstrap_product` 构建 tool_registry 仅用 `default_tool_ids`，`optional_tool_ids`（含 send_message）未包含，导致 tool_registry 中没有 send_message
  2. `_resolve_session_available_tools` 无 allowlist 时走 `_active_tool_specs()`（全量），有 allowlist 但 send_message 不在 registry 中时过滤结果为空
  3. `SendMessageTool` 有模块级 `TOOL` 单例和 `bind_dispatcher` 有状态反模式
  4. 无 `/internal/dispatch` 端点

---

## Roadpoint 记录

### R1 ResolvedProductConfig.default_tool_ids + bootstrap optional 合并 + runtime 双路过滤

- Context: base.py 的 ResolvedProductConfig 缺 default_tool_ids 字段；bootstrap 仅用 default_tool_ids 构建 registry；runtime 无 allowlist 时返回全量工具
- Decision: ResolvedProductConfig 增 default_tool_ids 字段；bootstrap 用 default+optional 并集构建 full registry，再存 default_tool_ids；runtime 无 allowlist 时按 default_tool_ids 过滤
- Rationale: optional 工具需在 registry 中（以便 allowlist 路径可找到），但默认不暴露给 LLM
- Evidence:
  - Tests: 8 passed (test_resolved_product_config_default_tool_ids.py + test_runtime_tool_allowlist_filtering.py)
  - Entry: tests/unit 648 passed
- Rollback: 0ef29ce (C1 test commit)
- Commits: C1=0ef29ce, C2=4f9df56, C3=<待填>
- Next: R2

### R2 SendMessageTool 无状态化

- Context: SendMessageTool 有 bind_dispatcher 有状态单例，需改为从 ctx.session_metadata 读 URL 做 HTTP POST
- Decision: 移除 TOOL 单例和 bind_dispatcher；ToolContext 增 session_metadata 字段；registry.execute 从 hook_context.metadata 注入；加 get_tool() 工厂供 loader 发现
- Rationale: 无状态工具便于测试和并发；tool loader 用 get_tool() 而非 TOOL 单例
- Evidence:
  - Tests: 6 passed (test_send_message_tool.py)，654 unit passed
  - Entry: tests/unit 654 passed
- Rollback: 8af52a3 (R1 C3)
- Commits: C1=00fc94f, C2=bad1ac2, C3=<待填>
- Next: R3

### R3 inbound_pipeline 注入 gateway_dispatch_url

- Context: session 创建时需注入 gateway_dispatch_url 以便 SendMessageTool 使用
- Decision: InboundPipeline 接收 gateway_internal_port（默认 8089），_build_session_metadata 注入 gateway_dispatch_url
- Rationale: 最小侵入方案，URL 在 session 创建时注入，不需要运行时查询
- Evidence:
  - Tests: 4 passed (test_gateway_dispatch_url_injection.py)，658 unit passed
  - Entry: tests/unit 658 passed
- Rollback: b4e0d0a (R2 C3)
- Commits: C1=1a3e912, C2=8427d5b, C3=<待填>
- Next: R4

### R4 Gateway /internal/dispatch 端点

- Context: send_message 需要 HTTP POST 到 gateway 端点进行消息投递
- Decision: GatewayRuntime 内嵌轻量 HTTP server 暴露 /internal/dispatch
- Rationale: 避免引入新进程，gateway 进程内直接服务
- Evidence:
  - Tests: <待填>
  - Entry: unit tests pass
- Rollback: R3 C3
- Commits: C1=<待填>, C2=<待填>, C3=<待填>
- Next: DONE
