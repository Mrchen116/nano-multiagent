# M251 — 修复 LLM 重试时用户消息重复追加（retry 逻辑下沉到 loop）

## 目标

将瞬态 ModelError retry 逻辑从 `_run_worker`（registry.py）移入 `loop.py`，
使 retry 只包裹 `LLMClient.generate()` 调用，不再重新执行 `runtime.run()`，
从而避免每次 retry 都重新追加 user message 到 session history。

## Roadpoints

### R1 — 新增测试：验证 loop 内部 retry 后 session 中 user message 仅一条

**Acceptance**
- 模拟 N 次 retryable ModelError 后成功，断言 loop 未抛出异常
- 检查模型调用次数 = N + 1（N 次失败 + 1 次成功）
- 断言 session history 中 user message 仅出现 1 次（需通过 runtime.run 的集成场景）
- 退避参数与预期一致（delays 循环使用、第5次后额外30s cooldown）
- max_retries 超出上限后抛出 non-retryable ModelError

**Tests Plan**
- unit：直接测试 AgentLoop.run() 中的 generate 重试逻辑
- integration：通过 AgentRuntime.run() 模拟 retryable 失败后成功，验证 session history 中 user message 仅一条
- contract：不需要（无新协议字段）
- e2e：不需要（loop/registry 属于内核层，用 unit+integration 已足够）

**Expected Tests**
- `tests/unit/test_loop_retry.py`
  - `test_loop_retries_generate_on_retryable_error_and_succeeds`
  - `test_loop_max_retries_raises_non_retryable_model_error`
  - `test_loop_non_retryable_error_propagates_immediately`
- `tests/unit/test_runtime_retry_no_duplicate_user_message.py`
  - `test_runtime_run_retryable_model_error_user_message_appears_once`

**DoD**: test_command 全绿 + C1/C2/C3

**状态**: DONE

---

### R2 — 实现：loop.py 中包裹 generate() 做退避重试

**Acceptance**
- `AgentLoop.run()` 中 `_llm_client.generate()` 外层包裹 retry 逻辑
- 退避策略：delays=(0.5, 1.0, 2.0)，每5次失败后额外30s cooldown
- max_retries=20 超出后抛 non-retryable ModelError
- 只包裹 generate()，不包裹 tool 执行或任何 session 写操作
- retry 过程中不调用任何 session_manager 写操作

**Tests Plan**
- unit：同 R1 测试（R1 写测试后 R2 让其绿）
- integration：同 R1 集成测试

**DoD**: test_command 全绿 + C1/C2/C3

**状态**: DONE

---

### R3 — 实现：registry.py 中移除 ModelError retry 循环

**Acceptance**
- `_run_worker` 不含 `ModelError` retryable 捕获和 `while True` retry 循环
- ModelError 像其他异常一样冒泡到 `_mark_failed`
- `while True` 循环替换为单次调用
- TimeoutError 和其他异常处理不变
- 现有 `test_cancel_stops_retry_loop_without_transitioning_to_failed` 仍通过（因为 loop 内部 retry 上限后会抛 non-retryable ModelError，registry 将其标为 failed，不再是无限循环；cancel 功能只需在 loop 内部 retry 间隙处检查）

**注意**: 原有 test_cancel_stops_retry_loop... 测试中的 _AlwaysRetryableFailureRuntime 仍会触发 registry 捕获 ModelError 并 mark_failed，因为 loop 内部重试最终会抛 non-retryable。该测试需适配。

**Tests Plan**
- unit：测试 registry 不再无限重试，ModelError(retryable=True) 被 mark_failed

**DoD**: test_command 全绿 + C1/C2/C3

**状态**: DONE
