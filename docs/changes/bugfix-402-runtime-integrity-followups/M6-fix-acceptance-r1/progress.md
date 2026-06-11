# bugfix-402-M6: fix-acceptance-r1 — Progress

> 生成于 round-1 验收 fail 后的 fix milestone

## Commit

`a596ed44` `fix(bugfix-402/M6): round-1 acceptance fixes — 8 runtime integrity followups`
merged via `merge(bugfix-402/M6)` into `unit/bugfix-402`

## Fix 1 [blocking]: CronExecutionService 未为动态创建 agent 注册

**根因**：`handle_agent_create()` 将 agent 注册进 pipeline，但不创建 `CronExecutionService`；
同时 `_cron_tick_for_agent` 用 `pipeline._agents[agent_id].workspace_root`（可能含 `~` 未展开），
而 `GatewayCronDispatcher.register()` 用 `expanduser().resolve()` — key 不一致导致 resolve 失败。

**修法**：
- `_IMConfigSyncClient` 增加 `on_agent_created: Callable[[str, Path], None] | None` 属性
- `handle_agent_create()` 末尾调用 callback（try/except 隔离）
- `build_runtime` 提取 `_register_cron_service(agent_id, ws_root)` 内函数（幂等，`_resolve_service` 去重）
- 启动循环和 `on_agent_created` callback 均调用 `_register_cron_service`
- 代码路径：`src/personal_assistant/main.py:2310-2340`（`_register_cron_service`），`main.py:2215-2218`（callback wiring），`main.py:497-510`（callback invocation）

**e2e 验证（直接调用，绕过 LLM 层）**：
```
enqueue result: {'accepted': True, 'job_id': 'test-echo-job', ...}
PASS: dispatcher correctly routed to service via workspace_root
```
GatewayCronDispatcher.invoke() → `_resolve_service(str(WORKSPACE))` 成功命中注册的 service。

## Fix 2 [critical]: Kernel.aclose() 绕过 RunsRegistry 状态机

**根因**：`aclose()` 直接调用 `_drain_and_stop()` 而不设 DRAINING 状态，DRAINING 期间 `submit()` 不拒绝，可能 double-drain。

**修法**：`aclose()` 委托 `registry.shutdown()`（走 OPEN→DRAINING→CLOSED 状态机），在有 running loop 时用 `asyncio.to_thread` 避免阻塞。
- 代码路径：`src/agent/sdk/kernel.py:642-680`

**测试**：`tests/unit/test_cli_async_repl_sdk.py::test_kernel_aclose_uses_registry_shutdown_state_machine` — 验证 `shutdown()` 被调用而非 `_drain_and_stop`。

## Fix 3 [critical]: jsonl_store recovery 静默丢弃

**根因**：两层 `if not turns: return`；第二个 bare return 在 combined guard 之后，当 turns=[] 但 recovery_by_call_id 非空时静默丢弃恢复条目。

**修法**：保留 combined guard `if not turns and not recovery_by_call_id: return`；删去 bare return，改为 `return LoadResult(..., _inject_recovery_messages([], recovery_by_call_id))`。
- 代码路径：`src/agent/core/session/jsonl_store.py:224-252`

**测试**：`tests/unit/test_session_persistence_fidelity.py::TestRecoveryWithNoTurns::test_load_with_recovery_but_no_turns_does_not_silently_discard`

## Fix 4 [critical]: error_classifier billing text 优先级

**根因**：`classify_retryability` billing text 检查在 structured permanent type/code 之前；`provider_type=invalid_request_error` + body 含 "credit" 被误判为 retryable。同时 bare "credit" 匹配 "credit card required"（permanent，用户需换卡）。

**修法**：重排优先级（structured permanent type → code → billing text → HTTP status → text）；`_BILLING_QUOTA_FRAGMENTS` 中 bare "credit" 改为 "insufficient credit"/"credit balance"/"credit limit"/"credit expired"。
- 代码路径：`src/agent/core/llm/error_classifier.py`

**测试**（4 个新测）：
- `test_structured_permanent_type_overrides_billing_text`
- `test_structured_permanent_code_overrides_billing_text`
- `test_bare_credit_word_without_billing_context`
- `test_credit_balance_compound_still_retryable`

## Fix 5 [major]: e2e-down.sh grace 计时

**根因**：`while` 循环每次 `sleep 0.2` 但 `elapsed+=1`（+1 而非 +0.2），实际等待 = `GATEWAY_GRACE_SECONDS * 0.2s`（5s grace 只等 1s）。

**修法**：`elapsed_ticks=0`；`max_ticks=$(( GATEWAY_GRACE_SECONDS * 5 ))`；每次循环 `elapsed_ticks+=1`。
- 代码路径：`scripts/e2e-down.sh:37-47`

**e2e 验证**：`time bash scripts/e2e-down.sh` 输出：
```
gateway pid=5544 did not exit within 5s — force-killing
e2e stack stopped (...)
real   5.966s
```
脚本等满了 5s（`real 5.966s`），而非旧版的 ~1s。

## Fix 6 [W-1]: CronExecutionService drain

**根因**：`enqueue()` 用 `asyncio.ensure_future()` 调度 execute_fn 但不跟踪返回的 Task 句柄；Gateway 关闭时 IM 可能在 cron delivery 完成前关闭（违反 Decision 7）。

**修法**：
- `enqueue()` 用 `loop.create_task()` 并加入 `self._pending_tasks`；done callback 自动清理
- 新增 `drain(timeout)` 方法：`asyncio.wait_for(asyncio.gather(*pending))` + 超时 cancel
- `GatewayCronDispatcher.drain_all(timeout)` 遍历唯一 service（`id()` 去重）
- `GatewayRuntime._run_until_shutdown()` 在 `kernel.aclose()` 后、`im_connection_manager.close()` 前调用 `drain_all()`
- 代码路径：`src/personal_assistant/scheduler/cron_execution_service.py:390-460`，`src/personal_assistant/scheduler/gateway_cron_dispatcher.py:79-97`，`src/personal_assistant/main.py:1583-1590`

**e2e 验证**：
```python
# enqueue → execute → runs.jsonl lifecycle
enqueue accepted: request_id=2db729c69ac347868cf8477eeb846826
  executed job=test-echo-job req=2db729c69ac347868cf8477eeb846826
runs found: 4
  CronRunRecord(request_id='2db729c69ac347868cf8477eeb846826', job_id='test-echo-job',
    trigger='manual', status='completed', ..., result_summary='CRON_RUN_OK - e2e validation complete.')
PASS: runs.jsonl has completed record with CRON_RUN_OK

# drain_all deduplication
PASS: drain_all() called drain() exactly once (dedup ok)
```

**测试**（4 个新测）：
- `TestCronExecutionServiceDrain::test_drain_awaits_pending_tasks`
- `TestCronExecutionServiceDrain::test_drain_no_tasks_returns_immediately`
- `TestGatewayCronDispatcherDrainAll::test_drain_all_drains_all_services`
- `TestGatewayCronDispatcherDrainAll::test_drain_all_deduplicates_single_service_mode`

## Fix 7 [small]: tasks.md checkbox + RuntimeWarning

**修法**：M1/M2/M5 tasks.md 全部 `- [ ]` → `- [x]`；`test_dispatcher_invoke_enqueue_delegates_to_service` 改为 `async def`；execute_fn 改 `AsyncMock()`。

## Fix 8 [cleanup]: _extract_http_error_facts 去重

**修法**：从 `anthropic/client.py` 和 `openai_compat/client.py` 提取到 `common.py` 作为 `extract_http_error_facts(exc, *, provider)`；两个 provider import alias `_extract_http_error_facts`。
- 代码路径：`src/agent/platform/llm/providers/common.py`

## 全树测试结果

```
2667 passed, 1 skipped, 4 deselected, 16 warnings in 93.67s
ruff check: clean
ruff format: 20 files reformatted
```

## Gateway 日志验证

`.gateway.log` 全程无 "no CronExecutionService" / "cron_unavailable" 错误：
```
INFO node wt-unit-bugfix-402-7550 auto-bound to IM
  → NANO_MULTIAGENT_AUTO_BIND=1 confirmed bind for http://127.0.0.1:60622.
```
`grep -c "no CronExecutionService" .gateway.log` → 0

---

## Round-2 Fix: Dispatcher 路由 key 双源路径不一致

**Commit**: `15209b7e` `fix(bugfix-402/M6): route cron dispatcher by agent_id, fix drain_all parallelism and loop injection`

**根因**：round-1 在 `_register_cron_service` 用 `workspace_root` 做 dispatcher 注册 key，但 `reconcile_all_agents()` 从 IM 回读 agent 配置后会用 IM 存储的 workspace_root（原始 main config 路径）覆盖 pipeline 内存里的值。`_cron_tick_for_agent` 和 cron tool 的 `HostCapabilityContext.workspace_root` 均来自 pipeline（IM 同步后的值），与注册时用的本地 YAML 路径不同——lookup 必然失败，返回 `cron_unavailable`。

**修法（治本）**：
1. `HostCapabilityContext` 增加 `agent_id: str = ""` 字段（`agent.core.tools.host_capability`）
2. `cron.py` 从 `ctx.session_metadata["agent_id"]` 取值填入 `cap_ctx.agent_id`
3. `GatewayCronDispatcher` 注册/解析 key 改为 `agent_id`（`register(agent_id, service)` / `_resolve_service(agent_id)`）
4. `_cron_tick_for_agent` 改为 `_cron_dispatcher._resolve_service(agent_id)`
5. `_register_cron_service` 幂等检查和注册均用 `agent_id` key
6. **code-review 修 loop 注入**：`_register_cron_service` 接受显式 `gateway_loop` 参数，不在函数内调用 `get_running_loop()`；`_on_agent_created` 在 WS event loop 内捕获 loop 并显式传入
7. **code-review 修 drain_all 串行**：改为 `asyncio.gather` 并行所有 service 的 `drain()`，共享同一 wall-clock timeout

**Live e2e 验证（round-2，2026-06-11，全新 e2e 栈）**：

e2e 栈：IM port=49639，GW pid=41995，NODE_ID=wt-unit-bugfix-402-41935

先 PATCH default-agent features 开启 cron_scheduling：
```
PATCH /im/v1/agents/default-agent/config
{"features": {"cron_scheduling": true}, "tool_allowlist": ["cron"]}
→ profile_version=2, features: {"cron_scheduling": true}
```

用户发送消息到 conv `06452e3543204af2afb9c7425b641a98`：
```
[user]: Run cron job test-echo-job now
[agent/default-agent]: The job `test-echo-job` has been triggered. The result will appear in this chat when it completes.
```

cron job 执行并投递结果到 direct chat conv `46e0280aaf204deda3d173b3108ba30b`：
```
[agent/default-agent]: CRON_RUN_OK - e2e validation complete.
```

runs.jsonl 历史（latest record）：
```json
{
  "request_id": "0f2dc9cef7a544ebb99989b8f6a88106",
  "job_id": "test-echo-job",
  "trigger": "manual",
  "status": "completed",
  "accepted_at": "2026-06-11T01:26:41.374618+00:00",
  "started_at": "2026-06-11T01:26:41.375421+00:00",
  "finished_at": "2026-06-11T01:26:44.387294+00:00",
  "kernel_run_id": "run_bc6216128385a3e1",
  "result_summary": "CRON_RUN_OK - e2e validation complete."
}
```

`.gateway.log`（完整）：
```
INFO node wt-unit-bugfix-402-41935 auto-bound to IM
  → NANO_MULTIAGENT_AUTO_BIND=1 confirmed bind for http://127.0.0.1:49639.
cron: awareness inject failed: agent=default-agent job=test-echo-job session=sess_516e3375ad53fb4a
```

`grep -c "no CronExecutionService" .gateway.log` → **0**

注：`awareness inject failed` 是 session JSONL awareness 写入的非关键后处理警告（cron 结果已成功投递到 IM；awareness 仅为 follow-up 问答附加功能）。
