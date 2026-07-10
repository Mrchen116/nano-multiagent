# M1: Kernel Interrupt API

## 目标

暴露 Kernel 已有的 `RunsRegistry.interrupt(session_id)` 能力为 HTTP API，使 Gateway 能以 session 为粒度强制中断正在执行的 agent run。

## Roadpoints

### RP1: HTTP API 端点 `POST /v1/sessions/{session_id}/interrupt`

**验收标准**：
- 端点接受空 body，返回 `{"session_id": str, "interrupted": bool, "run_id": str | None}`
- 当 session 存在且有 RUNNING 的活跃 run 时，`interrupted=true`，`run_id` 为被中断的 run id
- 当 session 存在但无活跃 run 时，`interrupted=false`，`run_id=null`
- 当 session 不存在时返回 404 `session_not_found`
- 鉴权走现有 bearer token 机制

**测试策略**：
- 单元测试：`session.py` 路由中 mock `RunsRegistry.interrupt()`，验证响应格式和状态码
- 契约测试：验证端点合约稳定（响应字段、类型、HTTP 状态码）

**依赖**：无

### RP2: `KernelApiClient.interrupt_session()`

**验收标准**：
- 新增 `interrupt_session(session_id: str) -> dict[str, Any]` 方法
- 内部调用 `POST /v1/sessions/{session_id}/interrupt`
- 正确传递 auth header 和 request id
- 对 404/401/5xx 错误抛出 RuntimeError（与现有 `_request` 错误处理一致）

**测试策略**：
- 单元测试：mock httpx client，验证请求路径、方法和响应解析

**依赖**：RP1

### RP3: 契约测试

**验收标准**：
- `tests/contract/test_session_interrupt_contract.py` 覆盖：
  - 正常 interrupt（session 有活跃 run）
  - 空 interrupt（session 无活跃 run）
  - session 不存在 404

**测试策略**：
- 使用 TestClient 调用端点，assert 响应 schema

**依赖**：RP1

## 回滚方案

- 删除 `session.py` 中新增端点
- 删除 `kernel_api_client.py` 中新增方法
- 不影响现有 `cancel_run` 和 `send_message_async` 行为
