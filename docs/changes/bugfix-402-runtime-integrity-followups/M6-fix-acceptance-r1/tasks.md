# bugfix-402-M6: fix-acceptance-r1 — Tasks

> 对齐: ../design.md（8 项来自 round-1 验收 fail 清单）

## 目标

修复 round-1 验收发现的 8 项问题，涵盖：CronExecutionService 动态注册缺失、
Kernel.aclose() 状态机绕过、jsonl_store recovery 静默丢弃、error_classifier 优先级、
e2e-down.sh 计时 bug、CronExecutionService drain 缺失、tasks.md checkbox、provider 重复代码。

## 退出标准

- [x] Fix 1 [blocking]: CronExecutionService 为动态创建的 agent 正确注册
- [x] Fix 2 [critical]: Kernel.aclose() 委托 RunsRegistry.shutdown() 状态机
- [x] Fix 3 [critical]: jsonl_store recovery entries 在 turns=empty 时不再丢弃
- [x] Fix 4 [critical]: classify_retryability 结构化 permanent 信号优先于 billing 文本
- [x] Fix 5 [major]: e2e-down.sh grace 等待实际 5s（tick-based 计数）
- [x] Fix 6 [W-1]: CronExecutionService execute_fn tasks drain before IM close
- [x] Fix 7 [small]: M1/M2/M5 tasks.md checkbox 勾选；RuntimeWarning 消除
- [x] Fix 8 [cleanup]: _extract_http_error_facts 去重到 common.py
- [x] 全树 `-m "not e2e"` 绿 + ruff clean
- [x] Live e2e 复验：cron manual run 完整链路（agent reply → enqueue ack → job execute → result deliver → runs 历史可见）
- [x] `.gateway.log` 全程无 "no CronExecutionService" 错误

## 测试策略

- Fix 1 测试：`tests/unit/personal_assistant/test_cron_delivery_chain.py`（`on_agent_created` callback 路径）
- Fix 2 测试：`tests/unit/test_cli_async_repl_sdk.py::test_kernel_aclose_uses_registry_shutdown_state_machine`
- Fix 3 测试：`tests/unit/test_session_persistence_fidelity.py::TestRecoveryWithNoTurns::test_load_with_recovery_but_no_turns_does_not_silently_discard`
- Fix 4 测试：`tests/unit/test_llm_error_classifier.py`（4 个新用例）
- Fix 5：`bash -n scripts/e2e-down.sh` + live e2e-down 实测等满 5s
- Fix 6 测试：`tests/unit/personal_assistant/test_cron_scheduler_tick.py::TestCronExecutionServiceDrain`（2 用例）+ `TestGatewayCronDispatcherDrainAll`（2 用例）
- Fix 7：tasks.md checkbox；AsyncMock 替换同步 execute_fn
- Fix 8：`tests/contract/test_agent_sdk_surface_contract.py`（import 检查）

落层：`tests/unit/`；无 e2e marker。

## Roadpoints

### R1 — Fix 1: CronExecutionService 动态注册

- 步骤：
  - `_IMConfigSyncClient` 增加 `on_agent_created: Callable[[str, Path], None] | None` 属性
  - `handle_agent_create` 末尾调用 callback（try/except 隔离）
  - `build_runtime` 提取 `_register_cron_service(agent_id, ws_root)` 内函数（幂等检查 + `_resolve_service`）
  - 启动循环和 `on_agent_created` callback 均调用 `_register_cron_service`
- 验证：`pytest -xvs tests/unit/personal_assistant/test_cron_delivery_chain.py`

### R2 — Fix 2: Kernel.aclose() 状态机

- 步骤：
  - `aclose()` 改为委托 `registry.shutdown()`，在有 running loop 时用 `asyncio.to_thread` 执行
  - 移除直接调用 `_drain_and_stop`
- 验证：`pytest -xvs tests/unit/test_cli_async_repl_sdk.py::test_kernel_aclose_uses_registry_shutdown_state_machine`

### R3 — Fix 3: jsonl_store recovery 修复

- 步骤：
  - 删去 bare `if not turns: return`（在 combined guard 之后）
  - 改为 `if not turns: return LoadResult(... _inject_recovery_messages([], recovery_by_call_id))`
- 验证：`pytest -xvs tests/unit/test_session_persistence_fidelity.py::TestRecoveryWithNoTurns`

### R4 — Fix 4: error_classifier 优先级

- 步骤：
  - `classify_retryability` 重排：structured permanent type → code → billing text → HTTP status → text
  - `_BILLING_QUOTA_FRAGMENTS` 收窄：bare "credit" 改为 "insufficient credit"/"credit balance"/"credit limit"/"credit expired"
- 验证：`pytest -xvs tests/unit/test_llm_error_classifier.py`

### R5 — Fix 5: e2e-down.sh grace 计时

- 步骤：
  - `elapsed_ticks=0`；`max_ticks=$(( GATEWAY_GRACE_SECONDS * 5 ))`；每次 `sleep 0.2` 后 `elapsed_ticks+=1`
- 验证：`bash -n scripts/e2e-down.sh`；live e2e-down 等满 5s

### R6 — Fix 6: CronExecutionService drain

- 步骤：
  - `enqueue()` 使用 `create_task` 并将句柄加入 `_pending_tasks`；done callback 自动清理
  - 新增 `drain(timeout)` 方法：`asyncio.wait_for(asyncio.gather(*pending))` + timeout cancel
  - `GatewayCronDispatcher.drain_all(timeout)` 遍历唯一 service（id() 去重）
  - `GatewayRuntime._run_until_shutdown()` 在 `kernel.aclose()` 后、`im_connection_manager.close()` 前调用 `drain_all()`
- 验证：`pytest -xvs tests/unit/personal_assistant/test_cron_scheduler_tick.py::TestCronExecutionServiceDrain tests/unit/personal_assistant/test_cron_scheduler_tick.py::TestGatewayCronDispatcherDrainAll`

### R7 — Fix 7: tasks.md + RuntimeWarning

- 步骤：
  - M1/M2/M5 tasks.md `- [ ]` → `- [x]`
  - `test_dispatcher_invoke_enqueue_delegates_to_service` 改为 `async def`；execute_fn 改 `AsyncMock()`
- 验证：`pytest -xvs tests/unit/personal_assistant/test_cron_scheduler_tick.py` 无 RuntimeWarning

### R8 — Fix 8: _extract_http_error_facts 去重

- 步骤：
  - 移动到 `agent/platform/llm/providers/common.py` 作为公开函数 `extract_http_error_facts(exc, *, provider)`
  - `anthropic/client.py` 和 `openai_compat/client.py` 均 import alias 为 `_extract_http_error_facts`
- 验证：`pytest -xvs tests/contract/`；ruff clean
