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
- Next: R2 — cron tool run 动作改用 host capability dispatch，删除 gateway_cron_url
