# feat-332-stop-command 进度

## 状态：M1 完成，M2 完成

---

## M1: Kernel Interrupt API

### RP1: HTTP API 端点 `POST /v1/sessions/{session_id}/interrupt`
- **状态**: 完成
- **修改**:
  - `src/agent/core/runs/registry.py`: `interrupt()` 返回类型从 `bool` 改为 `str | None`（返回被中断的 run_id）
  - `src/agent/platform/http_api/routes/session.py`: 新增 `InterruptSessionResponse` model 和 `interrupt_session` 路由处理函数
- **验收**: 契约测试通过

### RP2: `KernelApiClient.interrupt_session()`
- **状态**: 完成
- **修改**:
  - `src/personal_assistant/client/kernel_api_client.py`: 新增 `interrupt_session(session_id)` 方法
- **验收**: 单元测试通过

### RP3: 契约测试
- **状态**: 完成
- **文件**: `tests/contract/test_session_interrupt_contract.py`
- **覆盖**: 活跃 run 中断、空闲 session 中断、session 不存在 404

---

## M2: Gateway Stop Pipeline

### RP1: 活跃 run 追踪 (`_active_runs`)
- **状态**: 完成
- **修改**:
  - `src/personal_assistant/gateway/inbound_pipeline.py`:
    - `__init__` 中添加 `self._active_runs: dict[str, str]` 和 `self._active_runs_lock: asyncio.Lock`
    - `_run()` 中获取 `run_id` 后立即注册活跃 run
    - `_run()` 的 `finally` 块中清除活跃 run（覆盖正常完成、异常、取消路径）
- **验收**: `test_active_run_tracking_registers_and_unregisters` 通过

### RP2: `/stop` 前置拦截与 `_handle_stop_command()`
- **状态**: 完成
- **修改**:
  - `handle_inbound` 在 `_should_process` 之后、进入 `_run_queue.submit` 之前识别 `/stop`
  - 群聊支持 `@agent /stop` 和 `/stop @agent` 形式
  - `/stop` 跳过 `SessionRunQueue` 排队，直接走 `_handle_stop_command`
  - `/stop` 不写入 group context buffer
  - `_handle_stop_command` 逻辑:
    1. 查 `_active_runs.get(session_key)` → 有则中断，无则返回"当前没有正在执行的操作。"
    2. 调用 `self._kernel_client.interrupt_session(binding.kernel_session_id)`
    3. 调用 `self._kernel_client.append_message(...)` 注入用户中断消息
    4. 返回 `PipelineResult` 带确认回复文本（"已停止当前操作。"）
- **验收**:
  - `test_stop_command_with_no_active_run_returns_friendly_message` 通过
  - `test_stop_command_interrupts_active_run_and_appends_message` 通过
  - `test_stop_command_in_group_chat_with_mention_is_recognized` 通过
  - `test_stop_command_with_agent_after_slash_is_recognized` 通过
  - `test_stop_command_does_not_enter_group_context_buffer` 通过

### RP3: 集成与 E2E 测试
- **状态**: 完成
- **文件**:
  - `tests/integration/test_stop_command_integration.py`: 2 个测试（活跃 run 中断、空闲 session）
  - `tests/e2e/test_stop_command_e2e.py`: 1 个测试（async submit → running → interrupt 完整链路）
- **验收**: 全部通过

---

## 测试汇总

| 测试文件 | 数量 | 状态 |
|---------|------|------|
| `tests/contract/test_session_interrupt_contract.py` | 3 | 通过 |
| `tests/unit/personal_assistant/test_gateway_stop_command.py` | 6 | 通过 |
| `tests/integration/test_stop_command_integration.py` | 2 | 通过 |
| `tests/e2e/test_stop_command_e2e.py` | 1 | 通过 |
| `tests/unit/personal_assistant/test_gateway_pipeline.py` | 29 | 通过（回归） |
| `tests/unit/personal_assistant/test_kernel_api_client.py` | 8 | 通过（回归） |

**总计**: 49 个测试通过
