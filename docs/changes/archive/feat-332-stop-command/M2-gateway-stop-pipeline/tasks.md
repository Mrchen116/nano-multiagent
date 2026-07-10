# M2: Gateway Stop Pipeline

## 目标

在 Gateway `InboundPipeline` 中实现 `/stop` 命令的前置拦截、活跃 run 追踪和确认反馈，使用户能在 IM/聊天工具中随时终止当前 session 的 agent 操作。

## Roadpoints

### RP1: 活跃 run 追踪 (`_active_runs`)

**验收标准**：
- `InboundPipeline` 维护 `_active_runs: dict[str, str]`（`session_key -> run_id`）
- 注册时机：`_run()` coroutine 获得 `run_id` 后立即写入
- 注销时机：`_run()` 的 `finally` 块中清除（覆盖正常完成、异常、取消路径）
- 线程/协程安全：使用 `asyncio.Lock` 保护读写

**测试策略**：
- 单元测试：模拟 `_run()` 正常完成和异常路径，断言 `_active_runs` 状态正确

**依赖**：M1-RP2（`interrupt_session` 方法可用）

### RP2: `/stop` 前置拦截与 `_handle_stop_command()`

**验收标准**：
- `handle_inbound` 在 `_resolve_agent` 和 `_should_process` 之后、进入 `_run_queue.submit` 之前识别 `/stop`
- 群聊中支持 `@agent /stop` 和 `/stop @agent` 形式（去除 `@agent_id` 后匹配 `/stop`）
- `/stop` 本身不进入 `SessionRunQueue` 排队，直接走 `_handle_stop_command`
- `/stop` 不写入 group context buffer
- `_handle_stop_command` 逻辑：
  1. 查 `_active_runs.get(session_key)` → 有则继续，无则返回友好提示
  2. 调用 `self._kernel_client.interrupt_session(binding.kernel_session_id)`
  3. 调用 `self._kernel_client.append_message(...)` 注入用户中断消息（role="user", content="[Request interrupted by user for tool use]"），该调用仅写入历史，不触发新 run
  4. 返回 `PipelineResult` 带确认回复文本（"已停止当前操作"）

**测试策略**：
- 单元测试：mock kernel client，验证 `/stop` 识别、interrupt_session 调用、append_message 调用、返回结果
- 单元测试：验证无活跃 run 时返回友好提示
- 单元测试：验证 `@agent /stop` 被正确识别
- 单元测试：验证 `/stop` 不进入 group context buffer

**依赖**：RP1

### RP3: 集成与 E2E 测试

**验收标准**：
- `tests/integration/test_stop_command_integration.py`：Gateway + Kernel 真实链路，验证 `/stop` 能中断正在执行的工具批次
- `tests/e2e/test_stop_command_e2e.py`：
  - 启动一个执行慢工具（如 Sleep 5s）的 run
  - 发送 `/stop`
  - 断言 run 在 3 秒内终止，状态为 interrupted
  - 断言 session history 含用户中断消息
  - 断言 gateway 返回"已停止"确认
  - 断言同 session 后续消息能正常执行

**测试策略**：
- 集成测试：使用内存 kernel + 真实 Gateway pipeline
- E2E 测试：完整启动 kernel 进程 + gateway，通过 channel mock 发送消息

**依赖**：RP2

## 回滚方案

- 回滚 `inbound_pipeline.py` 修改
- `_active_runs` 是新增状态字段，回滚即删除
- 不影响正常消息处理路径
