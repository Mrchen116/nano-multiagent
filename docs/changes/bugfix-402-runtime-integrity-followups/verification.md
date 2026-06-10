# Verification Report: bugfix-402

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 实现全部完成，5/5 milestone；M1/M2/M5 tasks.md checkboxes 未更新（文档问题，非实现缺失） |
| Correctness | 所有 requirement / scenario 有实现和测试覆盖；2657 个测试全绿 |
| Coherence | 基本遵守；1 条 design 偏离（CronExecutionService drain 未实现） |

No critical issues. 1 warning to consider. Ready for PR (with noted improvements).

---

## Completeness

### Tasks 完成度

| Milestone | tasks.md 状态 | progress.md / roadpoints | 实现验证 |
|---|---|---|---|
| M1 transcript-integrity | 全 `- [ ]`（未勾选） | 4 roadpoints 全 DONE | 代码存在，测试绿 |
| M2 model-error-semantics | 全 `- [ ]`（未勾选） | 5 roadpoints 全 DONE | 代码存在，测试绿 |
| M3 owned-run-shutdown | 全 `- [x]`（已勾选） | ✓ | 代码存在，测试绿 |
| M4 unified-cron-run | Roadpoints 格式（全 DONE） | ✓ | 代码存在，测试绿 |
| M5 actor-first-web-im | 全 `- [ ]`（未勾选） | roadpoints 隐含完成 | 代码存在，前端测试绿 |

M1/M2/M5 的 tasks.md checkboxes 均未从 `- [ ]` 更新为 `- [x]`，但通过 progress.md roadpoints 和实际代码 + 测试验证，所有工作已完成。这是纯文档遗漏，不影响 PR。

### Spec 覆盖

**Kernel delta-spec（specs/kernel/spec.md）**

所有 Added / Modified requirements 均有对应实现：

1. **持久化 transcript 在进入模型前保持 tool call 闭合**
   - `prepare_transcript_for_run()` 实现于 `src/agent/core/session/jsonl_store.py:395`
   - `append_tool_call_recovery()` 实现于 `src/agent/core/session/jsonl_store.py:483`
   - `runtime._run` 调用 prepare 于 `src/agent/core/agent/runtime.py:295`
   - 恢复 entry 写于中断/取消路径 `runtime.py:574`

2. **模型错误按统一可恢复语义重试**
   - `ProviderErrorFacts` + `classify_retryability()` 实现于 `src/agent/core/llm/error_classifier.py`
   - `RetryingLLMClient` 部分内容保护实现于 `src/agent/core/llm/retry.py:55-56`

3. **Kernel 关闭收拢所有 owned runs**
   - `RunsRegistry._owned_tasks` + `_drain_and_stop()` 实现于 `src/agent/core/runs/registry.py`
   - `Kernel.aclose()` 实现于 `src/agent/sdk/kernel.py:642`

4. **build_kernel 支持 host_capabilities（Modified）**
   - `HostCapabilityDispatcher` / `HostCapabilityContext` 实现于 `src/agent/core/tools/host_capability.py`
   - `build_kernel()` 新增可选参数，SDK re-export

**Gateway delta-spec（specs/gateway/spec.md）**

所有 Modified requirements 均有对应实现：

1. **stop/restart 收拢活动运行** — Gateway 关闭序列见 `main.py:1559-1567`，kernel.aclose() 在 channels/heartbeat 停止后、IM 关闭前调用
2. **Heartbeat 与 Cron 统一执行语义** — `CronExecutionService.enqueue()` 实现于 `src/personal_assistant/scheduler/cron_execution_service.py:319`，scheduled/manual 共用同一方法
3. **运行历史区分 trigger** — `CronRunRecord` 含 trigger 字段，accepted→running→terminal 三阶段追加
4. **手动运行未知任务明确拒绝** — `cron.py:506-518` 在创建 session 前拒绝

---

## Correctness

### Kernel delta-spec：逐 Scenario 核对

| Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 中断权限等待后继续同一会话 | `runtime.py:545-574`（interrupt 写 recovery），`jsonl_store.py:395`（prepare on next run） | `test_session_manager.py::TestInterruptCancelRecovery` | covered |
| 重启后恢复悬空 tool call | `runtime.py:295`（prepare before load），`jsonl_store.py:800`（物化 recovery 为合成 tool result） | `test_session_persistence_fidelity.py::TestOrphanedToolCallRecovery` | covered |
| 重复准备恢复保持幂等 | `jsonl_store.py:476`（确定性 idempotency_key），loader 去重 | `test_session_manager.py` idempotency tests；`test_session_store_persistence_integration.py::test_prepare_transcript_idempotent_across_process_restart` | covered |
| 只读加载没有修复副作用 | `load()` 纯读，不调 prepare，见 `jsonl_store.py` load 方法 | `test_session_manager.py` readonly load tests | covered |
| 语义不明或可能恢复的 4xx 继续重试 | `error_classifier.py:142-162`（默认 retryable=True） | `test_llm_provider_contract.py`（quota/billing/429 fixtures） | covered |
| 明确永久错误快速失败 | `error_classifier.py:146-159`（permanent types/codes/HTTP statuses） | `test_llm_provider_contract.py`（credentials/invalid_request/404 fixtures） | covered |
| 已产出内容后的中途故障不重复输出 | `retry.py:55-56`（`if yielded_content: raise`） | `test_runtime_retry_no_duplicate_user_message.py` | covered |
| 重试耗尽返回最后真实错误 | `retry.py:58-68`（保留 `exc.message`/code/type，只追加 retry 元数据） | `test_loop_retry.py` exhaustion tests | covered |
| 有活动运行时关闭 | `registry.py:149-220`（OPEN→DRAINING→CLOSED 状态机，await owned tasks） | `test_runs_registry.py` shutdown tests | covered |
| 异步关闭不阻塞消费者 loop | `kernel.py:658-665`（drain_future via `asyncio.wrap_future`，Registry 在自己 loop 跑） | `test_runs_registry_transport_lifecycle.py` | covered |
| 关闭期间拒绝新提交 | `registry.py:158`（DRAINING 后拒绝 submit） | `test_runs_registry.py` | covered |
| 重复关闭 | `kernel.py:649-651`（`_closed` guard）；`close()` 同理 | `test_runs_registry.py` | covered |
| 用产品 profile + LLM 配置装配 Kernel | `sdk/kernel.py` `build_kernel()` 接受 `host_capabilities` 可选参数 | `test_agent_sdk_surface_contract.py::TestBuildKernelHostCapabilities` | covered |
| 宿主注入能力 | `host_capability.py:39-77`（ABC 定义），cron tool `cron.py:509-553` | `test_cron_tool_openclaw.py::TestCronToolRunHostCapability` | covered |
| 宿主未提供能力 | `cron.py:510-518`（dispatcher is None 时返回明确错误） | `test_cron_tool_openclaw.py` | covered |

### Gateway delta-spec：逐 Scenario 核对

| Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 手动运行已有 cron 任务立即入队 | `cron_execution_service.py:319`（enqueue 同步返回 ack），`cron.py:528-553` | `test_cron_tool_openclaw.py::TestCronToolRunHostCapability` | covered |
| 手动 cron 与定时 cron 使用同一执行语义 | `gateway_cron_dispatcher.py:91-126`（shared execute_fn），`cron_scheduler.py` tick 调 `_service.enqueue()` | `test_cron_scheduler_tick.py::TestGatewayCronDispatcher` | covered |
| 查询 cron 运行历史 | `cron.py:556`（`_action_runs` 读 runs.jsonl）；`CronRunsStore.list_by_job()` | `test_cron_delivery_chain.py` runs history tests | covered |
| 手动运行未知或不可运行任务 | `cron_execution_service.py:342-356`（job_not_found / job_disabled 在 Kernel session 创建前拒绝） | `test_cron_tool_openclaw.py` | covered |
| 未启用的 Agent 两套机制都不跑 | cron prompt section 通过 `ctx.flags.get("cron_scheduling", False)` 控制（`prompt_sections.py:105`）；dispatcher 未注册时返回 `cron_unavailable` | `test_agent_features_cron_json.py` | covered |
| Cron 汇报后用户追问 Agent 记得汇报内容 | `cron_runner.py` canonical session awareness 写回；`CronExecutionService.execute_fn` 完整执行链 | `test_cron_runner_awareness.py` | covered |
| stop 收拢活动运行后终止 Gateway | `main.py:1558-1565`（aclose() 在 channels 停后、IM 关前调用） | `test_gateway_stop_command.py` | covered |
| 真实故障在关闭后仍是主要错误 | `main.py:1549-1553`（cleanup 失败只 warning，不覆盖原始错误） | `test_gateway_stop_command.py` | covered |

---

## Coherence

### Design 决策遵守情况

| 决策 | 遵守? | 代码证据 |
|---|---|---|
| 决策 1：通用 SDK 只提供宿主能力 dispatcher，类型定义于 core | ✓ | `agent/core/tools/host_capability.py:20-77`；sdk re-export 于 `agent/sdk/__init__.py`；无 cron 类型进入 sdk/core |
| 决策 2：Gateway 只有一个 cron execution service；enqueue 前从可信 context 解析 agent | ✓（部分）| `CronExecutionService` 存在，scheduled/manual 共用；**但 drain 未实现，见 WARNING** |
| 决策 3：transcript 完整性由显式、原子的 session 准备步骤保证 | ✓ | `jsonl_store.py:395-481`（per-path lock + flush/replay/check/append/flush）；确定性 idempotency_key |
| 决策 4：统一错误事实，默认重试，永久错误用否定清单 | ✓ | `error_classifier.py`（provider-neutral，无 provider-name 分支） |
| 决策 5：重试耗尽不替换真实上游错误 | ✓ | `retry.py:58-68`（保留 `exc.message`，追加 retry_exhausted/attempts 元数据） |
| 决策 6：RunsRegistry 对 Task 生命周期负全责，`Kernel.aclose()` async-native | ✓ | `registry.py:124-220`（`_owned_tasks`，OPEN→DRAINING→CLOSED）；`kernel.py:642-678` |
| 决策 7：Gateway 按生产者到消费者顺序关闭；先等 kernel aclose 再断 IM | ✓ | `main.py:1544-1573`；`e2e-down.sh`（先 SIGTERM Gateway 等待，再停 IM） |
| 决策 8：Web IM 只使用 Actor-first 数据源 | ✓ | `im-chat-api.ts:839-851`（`ensureSelfUser` 从 auth store 读）；`/im/v1/users` 字符串已从调用路径删除 |

### 架构边界（§4.3）

- 模块边界无违反：`coding_cli` / `personal_assistant` 均只 import `agent.sdk`；`cron.py` 的 `HostCapabilityContext` import 路径为 `agent.core.tools.host_capability`（core 层，合法）
- `CronTool` 不 import `personal_assistant`：dispatcher 由 composition root 注入，core 内不含产品专属类型
- `CronExecutionService._action_runs` 通过 `_read_runs_for_job()` inline 读取 runs.jsonl，不 import `personal_assistant`（`cron.py:556-620`）
- 跨进程边界：无假设 Gateway/IM 同机直接文件访问；IM 只通过 WebSocket/HTTP 交互

---

## Delta-Spec 对账（附加任务）

### 契约与实现一致

**kernel/spec.md**
- R1 "持久化 transcript 工具调用闭合"：全部 4 个 scenario 实现 + 测试一致
- R2 "统一可恢复语义重试"：全部 4 个 scenario 实现 + 测试一致；`error_classifier.py` 不含 provider-name 分支，与 spec 要求的 provider-neutral 一致
- R3 "Kernel 关闭收拢 owned runs"：全部 4 个 scenario 实现 + 测试一致
- Modified R "build_kernel host_capabilities"：全部 4 个 scenario 一致

**gateway/spec.md**
- "手动运行已有任务立即入队"：实现与 spec 一致，工具立即返回 accepted，不等待执行
- "手动 cron 与定时 cron 使用同一执行语义"：`execute_fn` 共用，触发路径无差别
- "查询 cron 运行历史"：`_action_runs` 从 runs.jsonl 读取，含 trigger/status/timestamps，与 spec 要求一致
- "手动运行未知或不可运行任务"：在 Kernel session 创建前拒绝，明确 error_code

### 契约声明的行为代码已背离

无——所有 spec 条目均在代码中有对应实现。

### 本 unit 新增代码产生了 delta 未覆盖的对外行为

1. **`CronExecutionService.enqueue()` 的"无 event loop"静默警告路径**（`cron_execution_service.py:398-405`）：当 enqueue 被调用时既没有 running loop 也没有 gateway_loop，execute_fn 被静默 drop，只写 WARNING 日志。spec 只声明了 accepted 确认语义，对"已接受但从未执行"没有明确处理。这是一个在极端情况下可能导致 accepted 记录永远不更新为 terminal 的行为，与 converge_stale_on_restart 会在下次重启时覆盖，但 spec 没有声明此场景。

2. **`_COOLDOWN_EVERY` / `_COOLDOWN_SECONDS` 额外冷却**（`retry.py:13-15`）：每 5 次失败后插入额外 30 秒冷却，spec 只声明"在既定预算内重试"和"重试耗尽"，未声明冷却语义。这是一个实现细节，对外行为是用户等待时间可能超出预期，但没有测试覆盖冷却路径的时序行为。

---

## Issues

### WARNING（应该修）

**W-1：design.md 决策 2 / M4 任务清单要求 "Gateway 关闭时先等 CronExecutionService drain 完成"，但实现缺失**

- `CronExecutionService` 和 `GatewayCronDispatcher` 均无 `drain()` / `close()` 方法
- `main.py` 关闭序列（`_run_until_shutdown` finally 块）在 `await self._kernel.aclose()` 之后直接关 IM，未等待 cron execute_fn coroutines 完成
- 实际风险：`enqueue()` 派发的 `execute_fn` coroutine 跑在 Gateway loop 上；`kernel.aclose()` 收拢的是 Registry 内的 run Tasks，但 `execute_fn` 里的流消费、IM 投递和 awareness 写回是 Gateway loop 上的 Task，`kernel.aclose()` 返回后这些 Task 可能还在运行，IM 连接随即被关闭
- 修复方向：在 `CronExecutionService` 或 `GatewayCronDispatcher` 增加 `pending_tasks` 跟踪（`create_task` 返回值），并在 `main.py` 关闭序列 `kernel.aclose()` 之后、`im_connection_manager.close()` 之前，`await asyncio.gather(*pending_tasks, return_exceptions=True)`
- 相关位置：`src/personal_assistant/scheduler/cron_execution_service.py:385-397`（enqueue 调度），`src/personal_assistant/main.py:1558-1567`（关闭序列）

### SUGGESTION（可以修）

**S-1：M1/M2/M5 tasks.md checkboxes 未从 `- [ ]` 更新为 `- [x]`**

- `docs/changes/bugfix-402-runtime-integrity-followups/M1-transcript-integrity/tasks.md`
- `docs/changes/bugfix-402-runtime-integrity-followups/M2-model-error-semantics/tasks.md`
- `docs/changes/bugfix-402-runtime-integrity-followups/M5-actor-first-web-im/tasks.md`
- 所有实现已完成，progress.md 和代码一致，但 checkboxes 未更新。将所有 `- [ ]` 改为 `- [x]` 即可

**S-2：`test_cron_scheduler_tick.py::TestGatewayCronDispatcher` 产生 `RuntimeWarning: coroutine was never awaited`**

- `tests/unit/personal_assistant/test_cron_scheduler_tick.py:289`
- `_noop_execute` 被定义为 async 但测试中 mock 返回了 coroutine 未 await。不影响测试通过，但会产生 warning。修复：将 `_noop_execute` 改为返回已完成的 coroutine 或直接 `AsyncMock`

**S-3：`retry.py` 的 `_COOLDOWN_EVERY` / `_COOLDOWN_SECONDS` 冷却行为 spec 中无说明**

- `src/agent/core/llm/retry.py:13-15`
- 每 5 次失败插入 30 秒额外冷却，超出 spec 声明范围。建议在 kernel spec.md 的重试 requirement 下补一句：重试含指数冷却策略（每 N 次失败后额外暂停），或在代码注释中更明确地注明这是实现细节

---

No critical issues. 1 warning to consider. Ready for PR (with noted improvements).

---

# Round 2

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 8/8 M6 fixes 全部完成；M6 tasks.md 全 `[x]`；全量测试 2667 passed |
| Correctness | Round 1 W-1 已修复；8 个 fix 均有代码证据和测试覆盖 |
| Coherence | 所有 8 条 design 决策遵守（含 W-1 修复后的决策 7）；无新偏离 |

All checks passed. Ready for PR.

---

## Round 1 W-1 修复核对

**W-1：CronExecutionService execute_fn tasks not drained on Gateway shutdown**

修复状态：**已解决**

修复由 Fix 6 实现，分三层：

1. `CronExecutionService.enqueue()` 改用 `loop.create_task()`，并通过 done callback 跟踪 `_pending_tasks` 列表（`src/personal_assistant/scheduler/cron_execution_service.py:396-416`）

2. `CronExecutionService.drain(timeout)` 新增方法，用 `asyncio.wait_for(asyncio.gather(...))` 等待 pending tasks，超时后 cancel（`cron_execution_service.py:434-472`）

3. `GatewayCronDispatcher.drain_all()` 新增方法，对 unique services 调用 `drain()`，正确去重 single-service 模式下的重复注册（`gateway_cron_dispatcher.py:79-97`）

Gateway 关闭序列：`main.py:1583-1591` 在 `kernel.aclose()` 之后、`im_connection_manager.close()` 之前调用 `await self._cron_dispatcher.drain_all()`，与 design 决策 7 完全一致。

测试覆盖：
- `TestCronExecutionServiceDrain::test_drain_awaits_pending_tasks` — 验证 drain 等待 pending tasks
- `TestCronExecutionServiceDrain::test_drain_no_tasks_returns_immediately` — 空 pending 场景
- `TestGatewayCronDispatcherDrainAll::test_drain_all_drains_all_services` — 多 service drain
- `TestGatewayCronDispatcherDrainAll::test_drain_all_deduplicates_single_service_mode` — 去重路径

---

## M6 Fix 逐项核对

| Fix | 描述 | 代码证据 | 测试覆盖 | 状态 |
|---|---|---|---|---|
| Fix 1 | 动态创建 agent 的 CronExecutionService 注册 | `main.py:2310-2325`（`_register_cron_service` 提取），`main.py:2215-2218`（`on_agent_created` 回调） | `test_cron_delivery_chain.py::TestGatewayStartupConvergence` | resolved |
| Fix 2 | `Kernel.aclose()` 委托 `RunsRegistry.shutdown()` 状态机 | `kernel.py:660-669`（`asyncio.to_thread(registry.shutdown)`，不再绕过 DRAINING 状态） | `test_runs_registry.py`，`test_cli_async_repl_sdk.py` | resolved |
| Fix 3 | jsonl_store turns=empty 时不丢弃 recovery entries | `jsonl_store.py:224-239`（combined guard + explicit `_inject_recovery_messages([], recovery_by_call_id)`） | `test_session_persistence_fidelity.py` 新增 empty-turns recovery 测试 | resolved |
| Fix 4 | `classify_retryability` 结构化 permanent 信号优先于 billing 文本 | `error_classifier.py:163-171`（priority 1/2 在 billing text 之前）；`_BILLING_QUOTA_FRAGMENTS` 删 bare "credit"，改精确 compound phrases | `test_llm_error_classifier.py::test_structured_permanent_type_overrides_billing_text`，`test_bare_credit_word_without_billing_context` | resolved |
| Fix 5 | e2e-down.sh grace 计时：tick-based 计数修复 | `e2e-down.sh:41-50`（`max_ticks=$(( GRACE * 5 ))`，`elapsed_ticks+=1` per 0.2s） | `bash -n` 语法验证 | resolved |
| Fix 6 | CronExecutionService drain（W-1 主体修复） | 见上节 W-1 详细核对 | `TestCronExecutionServiceDrain`，`TestGatewayCronDispatcherDrainAll` | resolved |
| Fix 7 | M1/M2/M5 tasks.md checkboxes；test RuntimeWarning | 全三个 tasks.md 均已全 `[x]`；`test_cron_scheduler_tick.py:254` 改为 `async def` + `AsyncMock`，RuntimeWarning 消除 | 全量测试无 RuntimeWarning | resolved |
| Fix 8 | `_extract_http_error_facts` 去重到 `common.py` | `platform/llm/providers/common.py:40`（`extract_http_error_facts` 定义）；两 provider 均 import alias | `test_llm_provider_contract.py` 全绿 | resolved |

---

## Round 1 Delta 未覆盖行为 — M6 后状态（advisory）

**行为 1：`CronExecutionService.enqueue()` 无 event loop 时静默 drop（`cron_execution_service.py:418-425`）**

M6 后状态：该路径**仍存在**，但 context 已弱化。Fix 1 确保所有 agent（静态 + 动态创建）在 cron tick 前均已注册并注入 `gateway_loop`，因此 Context B（tool.run 线程）在正常 Gateway 运行时总有 `gateway_loop` 可用。无 loop 的 warning 路径只在 Gateway 构建不完整（测试 mock 或进程异常）时触发。

**delta spec 是否需要补条目（advisory）**：不需要。spec 要求"enqueue 立即返回 accepted 确认"，隐含"scheduler 已初始化"的 precondition；warning drop 是防御性降级，不是被告知消费者的契约语义。建议在代码注释处补充"此路径仅在 Gateway 未完成初始化时触发"以明示场景，但不需要进入 spec。

**行为 2：`retry.py` 的 `_COOLDOWN_EVERY`/`_COOLDOWN_SECONDS` 冷却语义**

M6 后状态：**未改变**，冷却逻辑仍存在（`retry.py:10-15`）。

**delta spec 是否需要补条目（advisory）**：建议在 kernel spec.md 的"模型错误按统一可恢复语义重试并保留原始原因"requirement 下补一句"重试策略含指数退避，连续失败可能触发额外冷却等待"——这是消费者（Gateway 运维者）在调优 grace timeout 时需要知道的行为边界。属于 advisory，不阻塞 PR。

---

All checks passed. Ready for PR.
