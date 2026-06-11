# M4: unified-cron-run — Progress

## 总览

branch: milestone/bugfix-402-M4
worktree: /Users/czj/Repos/nano-multiagent/.worktrees/bugfix-402-M4

---

### R1 — HostCapabilityDispatcher 类型定义 + sdk re-export + build_kernel 注入

- Context: agent.core.tools 是 ToolContext 所在层；类型必须落在 core 而非 sdk，否则 sdk→core 依赖倒置。
- Decision: 新建 `agent/core/tools/host_capability.py`，定义 `HostCapabilityContext`（frozen dataclass）和 `HostCapabilityDispatcher`（ABC）；`agent.core.tools.__init__` re-export；`agent.sdk.__init__` re-export 作为公开面；`build_kernel()` 新增 `host_capabilities` 可选参数，通过 `_inject_host_capabilities` 写入 registry 的 base ToolContext；`ToolContext.with_session` 和 `_resolve_execution_context` 均传播 `host_capabilities`。
- Rationale: Kernel 公共面保持产品无关；dispatcher 由 composition root 正向注入，不反向 import personal_assistant。
- Evidence:
  - Tests: `pytest tests/contract/test_agent_sdk_surface_contract.py tests/unit/personal_assistant/test_cron_tool_openclaw.py tests/unit/personal_assistant/test_cron_delivery_chain.py tests/unit/personal_assistant/test_cron_runner_awareness.py tests/unit/personal_assistant/test_cron_scheduler_tick.py tests/contract/test_cron_coding_cli_isolation.py` — 49 passed
  - Entry: N/A（纯类型定义 + 注入，无产品入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: C1 hash
- Commits: C1=test(bugfix-402/M4/R1), C2=feat(bugfix-402/M4/R1), C3=docs(bugfix-402/M4/R1)
- Next: R2 DONE → R3

### R2 — cron tool run 动作改用 host capability dispatch

- Context: 旧 `_action_run` 从 session_metadata 读取 `gateway_cron_url` 并用 httpx 发 POST，但该 URL 从未注入且内核无 HTTP 服务器，导致 run action 永久不可用。
- Decision: 改为读 `ctx.host_capabilities`，调用 `"personal_assistant.cron.enqueue"`；无 dispatcher 时返回 ok=False 带说明文字；dispatcher 返回 accepted=False 时映射 error_code 为可读错误；保留 `LookupError` 对未知 job。
- Rationale: 彻底断开 HTTP loopback，让 cron tool run 和 Gateway CronExecutionService 直接通信，符合 bugfix-402 Decision 1。
- Evidence:
  - Tests: 21 passed (test_cron_tool_openclaw.py 含新增 TestCronToolRunHostCapability 5 用例)；全 M4 suite 54 passed
  - Entry: N/A（单元测试已覆盖关键路径）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: C1 hash (test(bugfix-402/M4/R2))
- Commits: C1=test(R2), C2=fix(R2), C3=docs(R2)
- Next: R3 DONE → R4

### R3 — CronExecutionService + runs.jsonl 三阶段历史

- Context: 旧 `_cron_tick_for_agent` 是内联闭包，手动/定时路径有各自的执行逻辑，`_action_runs` 只读旧的 state.json（仅 last_due_at）。需要统一入口和结构化运行历史。
- Decision: 新建 `personal_assistant/scheduler/cron_execution_service.py`，包含：`CronRunRecord` dataclass（七个字段）、`CronRunsStore`（append-only runs.jsonl，materialize-on-read，update_status，list_by_job，converge_stale_on_restart）、`CronExecutionService`（enqueue() 同步返回 ack，validate+persist accepted+schedule execute_fn）。
- Rationale: accepted→running→terminal 三阶段历史让两条触发路径共用同一数据源；converge_stale_on_restart 确保重启后没有永久进行中的记录。
- Evidence:
  - Tests: 64 passed (含新增 TestCronRunsStore 5 用例 + TestCronExecutionServiceEnqueue 5 用例)
  - Entry: N/A（单元）
  - Frontend State Matrix: N/A; Browser QA: N/A; E2E: N/A; Visual: N/A
- Rollback: C1 hash (test(bugfix-402/M4/R3))
- Commits: C1=test(R3), C2=feat(R3), C3=docs(R3)
- Next: R4 DONE → R5

### R4 — Gateway composition 改用 CronExecutionService (scheduled+manual 共用 enqueue)

- Context: 旧 `_cron_tick_for_agent` 为每个 tick 内联创建 CronRunner + submit_fn 闭包，与 manual cron tool 路径完全割裂，无共享历史。
- Decision: 新建 `GatewayCronDispatcher(HostCapabilityDispatcher)` — 按 workspace_root 路由到 per-agent `CronExecutionService`；`build_runtime()` 在 `build_kernel()` 前创建空 dispatcher 并注入 `host_capabilities=_cron_dispatcher`；为每个 `config.agents` 创建 `CronExecutionService(execute_fn=...)` 并注册；`_cron_tick_for_agent` 改为 `_service.enqueue(trigger="scheduled")`；execute_fn 封装完整执行链(submit→stream→deliver→awareness)。
- Rationale: scheduled/manual 触发共用同一 execute_fn，保证历史一致性；GatewayCronDispatcher 延迟注册（build_kernel 前创建空 dispatcher，kernel_shim 创建后注册 services），无需分两个阶段。
- Evidence:
  - Tests: 69 passed (含新增 TestGatewayCronDispatcher 5 用例)
  - Entry: N/A（单元）
  - Frontend State Matrix: N/A; Browser QA: N/A; E2E: N/A; Visual: N/A
- Rollback: C1 hash (test(bugfix-402/M4/R4))
- Commits: C1=test(R4), C2=feat(R4), C3=docs(R4)
- Next: R5 DONE → Milestone 完成

### R5 — 启动遗留记录收敛 + cron runs 从 runs.jsonl 返回最新 records

- Context: 旧 `_action_runs` 只能返回 `state.json` 中的 `last_due_at`，无结构化历史；Gateway 重启后 accepted/running 记录永久留在非终态。
- Decision: `_action_runs()` 改为 inline 读取 `workspace/.nanoassistant/cron/runs.jsonl` 并 materialize-on-read（添加 `_read_runs_for_job()` helper，不 import personal_assistant，遵守模块边界）；`build_runtime()` 在注册每个 agent CronExecutionService 后调用 `runs_store.converge_stale_on_restart()`。
- Rationale: 两个修改共同满足 M4 退出标准：runs 查询返回最新结构化 records；重启后无永久进行中状态。
- Evidence:
  - Tests: 74 passed (含新增 TestCronRunsActionFromJsonl 4 用例 + TestGatewayStartupConvergence 1 用例)
  - Entry: N/A（单元）
  - Frontend State Matrix: N/A; Browser QA: N/A; E2E: N/A; Visual: N/A
- Rollback: C1 hash (test(bugfix-402/M4/R5))
- Commits: C1=test(R5), C2=fix(R5), C3=docs(R5)
- Next: milestone 全部 roadpoints DONE → rebase + merge + spec delta

---

## Live E2E 验证证据

**Date**: 2026-06-10

**Stack**: `scripts/e2e-up.sh --wt .worktrees/bugfix-402-M4`
- IM port: 59086
- Gateway node: `wt-bugfix-402-M4-50035` (online)
- LLM upstream: local proxy http://127.0.0.1:4000

**Test setup**:
1. `default-agent` workspace: `/Users/czj/nano-assistant/workspace/default-agent`
2. Cron job `test-echo-job` created in `.nanoassistant/cron/jobs.json` with `instruction: "Reply with exactly this text: CRON_RUN_OK - e2e validation complete."`
3. `features.cron_scheduling=true` set via `PATCH /im/v1/agents/default-agent/config`
4. **Fix applied**: Gateway loop injection (`GatewayCronDispatcher.set_gateway_loop()`) so `enqueue()` called from `asyncio.to_thread` (tool.run) schedules `execute_fn` on the Gateway loop instead of silently dropping.
5. **Fix applied**: `_execute` now writes `running`→`completed`/`failed` state transitions to `runs.jsonl`.

**Evidence 1 — Immediate ack on run**:
User message: "Run test-echo-job now using cron tool: action=run jobId=test-echo-job..."
Agent response (from cron tool):
```
requestId: b56a964222a9409aa8f8e3a97b49521f — accepted successfully
```

**Evidence 2 — runs.jsonl three-phase transitions**:
```
status=accepted  trigger=manual  request_id=b56a964222a9409a  started=None    finished=None   run_id=None
status=running   trigger=manual  request_id=b56a964222a9409a  started=13:40:39 finished=None  run_id=None
status=running   trigger=manual  request_id=b56a964222a9409a  started=13:40:39 finished=None  run_id=run_72efe4882e4a4b9b
status=completed trigger=manual  request_id=b56a964222a9409a  started=13:40:39 finished=13:40:42 run_id=run_72efe4882e4a4b9b
```
Total elapsed: 3 seconds (accepted → completed).

**Evidence 3 — Kernel run executed, result in target conversation**:
IM conversation `bee3e40fb18046d1873f1b43d57e297e` received agent reply:
```
CRON_RUN_OK - e2e validation complete.
```
This is the exact `instruction` text from the cron job, delivered to the same conversation the user sent the trigger from.

**Evidence 4 — cron runs history (agent reply)**:
Agent `action=runs` reply:
```
1 run record found.
Status: running  (materializer read mid-execution, before completed record written)
Trigger: manual
Accepted: 13:40:39 UTC
Started: 13:40:39 UTC
kernel_run_id: run_72efe4882e4a4b9b
```

**Test count**: 2656 passed (unit + contract, non-e2e) after all M4 fixes including gateway loop injection + state tracking.
