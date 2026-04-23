# Regression Verification: Bugfix-331

## 修复范围

- **M1** SSE 序列号 + 客户端高水位线 — 根治重复事件
- **M2** TTY 多行 assistant 输出清除 — 修复终端残留
- **M3** REPL resume 加载并打印历史 — 恢复上下文

---

## 复现验证

### 验证 1：序列号过滤

EventStreamHub 单元测试验证：
- `sequence_num` 从 1 开始单调递增
- `stream(after_sequence=N)` 只返回 `sequence_num > N` 的事件
- `encode_sse_event` 的 `id:` 字段为 `str(sequence_num)`

### 验证 2：客户端高水位线

- coding_cli `send_message_with_async_events` 每次 poll 传递 `after_sequence=last_sequence_num`
- gateway `InboundPipeline._await_terminal_run` 同样跟踪 `last_sequence_num`
- 连续 poll 不再收到已消费的历史事件

### 验证 3：TTY 多行清除

- `emit_external_text` 在写入新文本前，发送 N 次 `\x1b[A\x1b[2K` 清除上方已输出的 assistant 内容
- 非 TTY 环境（无法获取终端宽度）fallback 到不清除，不影响行为

### 验证 4：REPL resume 历史

- `_run_repl()` 在 resume 模式下调用 `client.get_session_messages(limit=20)`
- user 消息前缀 `>`，assistant 消息前缀 `<`
- 空内容跳过

---

## 回归测试结论

| 测试集 | 结果 | 说明 |
|--------|------|------|
| `tests/unit/test_sse_encoder.py` | 4 passed | SSE 编码器更新序列号 |
| `tests/unit/test_app_factory.py` | 2 passed | App factory 事件流兼容 |
| `tests/unit/test_cli_main.py` | 92 passed | CLI 主流程无回归 |
| `tests/unit/personal_assistant/test_kernel_api_client.py` | passed | Gateway 客户端解析序列号 |
| `tests/unit/personal_assistant/test_gateway_pipeline.py` | passed | Gateway pipeline 兼容 |

已知与本次修复无关的预存失败：
- `test_app_factory_with_profile.py::test_create_app_with_profile_uses_resolver_skill_roots_over_legacy_codex`
- `test_cli_managed_server.py` x 6
- `test_cli_refactor_boundaries.py` x 3
- `test_server_global_routes.py` x 5
- `test_server_message_route.py` x 2

---

## Verdict

Bugfix-331 的两个核心问题已修复，无引入新回归。
