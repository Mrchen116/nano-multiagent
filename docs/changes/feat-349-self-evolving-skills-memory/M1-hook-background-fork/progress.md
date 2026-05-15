# feat-349-M1 Progress

## Overview

实现 hook 内核 background fork 基础设施。核心改动：
- `core/hooks/types.py`：`HookEventMode.BACKGROUND` + `HookRegistration.mode`
- `core/hooks/registry.py`：`on()` 支持 `mode` 参数
- `core/hooks/runner.py`：`dispatch_background()` fire-and-forget
- `core/hooks/context.py`：`fork_conversation` callable 注入
- `core/agent/context_fork.py`：`ForkConversationCallable` + `make_fork_conversation`
- `core/agent/loop.py`：turn_meta 暴露 `tool_iterations`
- `core/agent/runtime.py`：`_run_locked` 读 tool_iterations、dispatch background hook context

<!-- Roadpoints below -->

### R1 — HookEventMode.BACKGROUND + HookRegistration.mode + Registry support

- Context: hook 内核只有 observe/intercept 两种 mode，需增加第三种 fire-and-forget 模式支持 background hook。
- Decision: `HookEventMode.BACKGROUND` 枚举值；`HookRegistration.mode` 字段默认 OBSERVE；`HookRegistry.on()` 增 `mode` 参数；新增 `background_handlers_for()` 只返回 BACKGROUND 注册；`handlers_for()` 排除 BACKGROUND 注册（原有 observe/intercept 逻辑不变）。
- Rationale: 把 background 模式作为正交第三维度，而非复用 observe，便于 dispatch 时按 mode 路由。`handlers_for` 排除 background 保证现有 dispatch_observe/dispatch_intercept 行为不变。
- Evidence:
  - Tests: `test_hook_event_mode_has_background_value`, `test_hook_registration_has_mode_field`, `test_registry_on_accepts_background_mode`, `test_registry_background_handlers_for_returns_them` — all pass
  - Entry: N/A (pure type/registry change)
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: revert types.py + registry.py
- Commits: C1=cb8be496, C2=a82e9c1a, C3=(this)

### R2 — HookRunner.dispatch_background fire-and-forget

- Context: 需要 `dispatch_background()` fire-and-forget：不阻塞调用方、不受 timeout_ms 约束、异常隔离。
- Decision: `HookRunner.dispatch_background()` 遍历 `background_handlers_for()` 返回的注册，每个用 `asyncio.create_task()` 启动，异常在 task 内 `try/except` 吞掉并 warning log。
- Rationale: `create_task` 保证 fire-and-forget 语义；不包装 `asyncio.wait_for` 故无 timeout；异常隔离防止 background 错误污染主 turn。
- Evidence:
  - Tests: `test_dispatch_background_does_not_await_handler`, `test_dispatch_background_not_constrained_by_timeout_ms`, `test_dispatch_background_isolates_errors`, `test_dispatch_background_only_fires_background_handlers` — all pass
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: revert runner.py dispatch_background 段
- Commits: C1=cb8be496, C2=a82e9c1a, C3=(this)

### R3 — HookContext.fork_conversation + make_fork_conversation + anti-recursion

- Context: background hook 需要能 fork 当前对话跑 side-chain；同时必须防止 fork 内再次 fork（递归）；fork 必须命中 provider prefix cache（整个 background-fork 设计的核心动机）。
- Decision:
  1. `HookContext.fork_conversation: ForkConversation | None` 字段，默认 None。
  2. `dispatch_observe/dispatch_intercept` 用 `_strip_fork_conversation(ctx)` 确保 observe/intercept handler 永远收到 fork_conversation=None。
  3. `make_fork_conversation()` 在 `context_fork.py` 内，构建 async callable 封装 `AgentContextFork.execute()`。
  4. 防递归：fork side-chain 通过 `AgentContextFork` 运行，该实例没有 hook_runner 背景 hook，fork context 内不会注入 `fork_conversation`。
- Decision（验收修订 2026-05-14，决策 6 对齐）: **tool 收窄方式从"重塑 LLM tool 列表"改为"执行层拦截"**。
  - **system prompt + tools 参数逐字节继承父 turn**：`make_fork_conversation` 把完整的 `active_tools` 原样作为 `available_tools_override` 传给 fork（不再 `fork_tools = filter(...)`）；`rendered_system_prompt` 同样逐字节传。两者都是 provider prefix-cache key 的一部分，重塑任一个都会导致 cache miss。
  - **tool 收窄在执行层做**：`StreamingToolExecutor` 新增 `tool_execution_allowlist` 参数；`AgentLoop.run()` / `AgentContextFork.execute()` 增同名 kwarg 透传；`make_fork_conversation` 把 `tool_allowlist` 作为 `tool_execution_allowlist` 传下去。executor 在 `_execute_one` 里、调 `registry.execute()` **之前** 用 `_is_execution_denied()` 判断：不在 allowlist 的工具直接返回 synthetic error `ToolResult`，工具本体从不执行（无副作用）。
  - **挂点选择理由**：design 给了两个候选——`ToolRegistry.execute` 内置判断 vs 复用 hook `tool_call` intercept。**选 `StreamingToolExecutor`**（在 `ToolRegistry.execute` 之前的更外层）：① intercept hook 注册在 registry 上是全局的，无法只作用于 fork side-chain 而不影响主 agent；② `ToolRegistry` 是主 agent 和 fork 共享的同一实例，在它内部加 fork-only 状态会污染主路径；③ `StreamingToolExecutor` 是每次 `AgentLoop.run()` 新建的、天然 per-run 隔离，把 allowlist 作为构造参数透下去最干净——主 agent 的 loop 永远传 `None`，fork 的 loop 传具体 allowlist，互不影响。
- Rationale: prefix cache 命中是 background-fork 整个设计的核心动机，逐字节继承 system prompt + tools 是硬约束；执行层拦截让"LLM 看到全量工具"和"实际只能跑白名单"解耦，既保 cache 又保安全。observe/intercept 剥离 fork_conversation 是语义安全边界，防止非 background 代码意外调用 fork。
- Evidence:
  - Tests:
    - `test_fork_conversation_inherits_parent_system_prompt` — 断言 `system_prompt_override` 与父 turn `rendered_system_prompt` 字节一致
    - `test_fork_conversation_inherits_parent_active_tools_byte_for_byte` — 父 turn 有 4 个工具、allowlist 只放行 2 个；断言 `available_tools_override` == 完整 4 工具（不被收窄），且 `tool_execution_allowlist` == allowlist
    - `test_fork_executor_denies_unlisted_tool_at_execution_layer` — 真测：FakeLLM 第 1 轮同时调 `bash`（非白名单）+ `memory`（白名单），用真 `ToolRegistry` + 真 `RecordingTool`，断言 `memory` 真的执行了、`bash` 没被执行（执行层 deny）
    - `test_fork_conversation_none_in_fork_context`, `test_background_hook_receives_fork_conversation_in_context`, `test_hook_context_has_fork_conversation_field` — all pass
  - 反向验证: 临时把 `_is_execution_denied` 改成永远返回 False，`test_fork_executor_denies_unlisted_tool_at_execution_layer` 立即失败（`bash` 被执行），证明测试是真测不是假绿。
  - Entry: fork 路径用真 ToolRegistry + 真 FakeLLMClient 端到端跑通，工具执行/拒绝行为已验证
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: revert context.py + context_fork.py + tool_executor.py + loop.py（tool_execution_allowlist 透传段）
- Commits: C1=cb8be496, C2=a82e9c1a, C3=bd7129f5, fix=(this batch)

### R4 — loop.py turn_meta 暴露 tool_iterations + runtime agent_end 带计数

- Context: 决策2要求 runtime 持原始 `tool_iterations` 里程表（api_round_count），通过 turn_meta 传递给上层；`agent_end` payload 需携带 `tool_iterations` 和 `turn_count` 供 background hook 做 nudge 判断。
- Decision: 在 loop.py 所有 `turn_meta` yield 点加 `"tool_iterations": api_round_count`；runtime._run_locked 从 turn_meta message 提取 `tool_iterations`，加入 `agent_end` payload 同时加 `turn_count`。
- Rationale: `api_round_count` 就是本 turn 内的 LLM API 调用次数，即 hermes 的 `_iters_since_skill` 语义中的"本 turn 新增迭代数"；由 runtime 统计并暴露，hook 不需要自己计数，只需做里程表差值判断。
- Evidence:
  - Tests: `test_agent_loop_turn_meta_includes_tool_iterations`, `test_runtime_agent_end_payload_includes_tool_iterations` — both pass
  - Entry: Full runtime run (FakeLLMClient) executed, agent_end payload captured with tool_iterations field
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: revert loop.py turn_meta 段 + runtime.py agent_end 段
- Commits: C1=cb8be496, C2=a82e9c1a, C3=(this)

### R5 — runtime 构建 background dispatch + fork_conversation 注入

- Context: `agent_end` 之后需要 dispatch background hook 并传入 `fork_conversation`；需要用当前 session config 构建 `fork_conversation` callable。
- Decision: runtime._run_locked 在 observe dispatch `agent_end` 后，检查 hook_runner 是否有 background 注册；有则构建 `fork_system_prompt`（从 session config render）和 `fork_active_tools`，调用 `make_fork_conversation()` 构建 `fork_fn`，组装 `background_hook_ctx` 并调用 `dispatch_background()`。
- Rationale: 把 fork_conversation 的构建收在 runtime 里，hook 模块（future self_improvement.py）只需调用 ctx.fork_conversation()，不需要知道 context_fork 的存在；符合 core/platform 分层。
- Evidence:
  - Tests: `test_background_hook_receives_fork_conversation_in_context` — pass
  - Entry: Full runtime run tested in R4 test
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: revert runtime.py background dispatch 段
- Commits: C1=cb8be496, C2=a82e9c1a, C3=(this)

## Test Run Summary (final, post 验收修订)

```
tests/unit/test_background_hook_fork.py: 21 passed
tests/unit/test_hooks_runner.py: pass (no regression)
tests/unit/test_agent_runtime_hooks.py: pass (no regression)
tests/unit/test_agent_runtime.py: pass (no regression)
tests/unit/test_agent_loop.py: pass (no regression)
tests/unit/test_loop_compact.py / test_loop_retry.py: pass (no regression)
tests/unit/ -k "tool_executor or streaming or tool_allowlist or context_fork or fork_session or compact": 57 passed
```

验收修订（2026-05-14）：R3 tool 收窄方式从"重塑 LLM tool 列表"改为"执行层拦截"，
对齐 design 决策 6。新增 2 个真测替换原 1 个假测：
- `test_fork_conversation_inherits_parent_active_tools_byte_for_byte`（tools 字节一致）
- `test_fork_executor_denies_unlisted_tool_at_execution_layer`（执行层 deny 真测，已反向验证）
test 总数 20 → 21。

Pre-existing failures on unit/feat-349 branch (not introduced by M1):
- test_agent_runtime_m246, test_app_factory_with_profile, test_server_global_routes, test_cli_managed_server, test_run_cancel, test_task_tool_with_resolver
- tests/contract/test_hook_intercept_contract.py, tests/contract/test_hook_integration_contract.py (5 cases) — 已 stash 验证为 M1 之前就红

