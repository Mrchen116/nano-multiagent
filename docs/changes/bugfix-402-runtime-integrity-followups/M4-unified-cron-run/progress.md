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
- Next: R3 — CronExecutionService + runs.jsonl 三阶段历史
