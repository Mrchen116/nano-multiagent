# M5-http-api-transition: HTTP API 过渡适配

## Goal
Sync endpoint (`POST /messages`) 内部走流式执行，组装完整结果后返回，保持现有响应格式 100% 兼容。

## Roadpoints

### R5.1 send_message() 内部流式化
- `send_message()` 中调用 `runtime.run()` 获得 async iterator
- 手动消费 async iterator，收集所有 yield 的 `Message`
- 从收集的 Message 中组装 `SendMessageResponse`
- 保留现有 `SendMessageResponse` 格式（过渡方案）
- **文件**: `src/agent/platform/http_api/routes/session.py`
- **验收**: `test_sync_endpoint_assembly` 通过

### R5.2 RunsRegistry 适配（如有需要）
- `_run_worker()` 中 `asyncio.run(runtime.run(...))` 保持不动（因为 runtime.run 仍返回 async iterator，只是消费方式从 `await` 改为 `async for`）
- 确认 `_run_worker` 正确消费 streaming generator
- **文件**: `src/agent/core/runs/registry.py`
- **验收**: async 提交路径端到端测试通过

## 验收标准
1. `POST /messages` 返回的 JSON 与 335 前完全一致
2. 内部确实走了流式（可通过日志/调试确认 `StreamingToolExecutor.add_tool()` 被调用）
3. `:async` 端点 + RunsRegistry + EventStreamHub 路径无回归
