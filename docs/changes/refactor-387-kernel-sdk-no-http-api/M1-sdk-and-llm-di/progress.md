# refactor-387-M1 — Progress

> 注：`test_cli_http_only_contract.py::test_spec_declares_zero_import_acceptance_rules` 和
> `test_multi_product_architecture_acceptance.py::test_architecture_docs_describe_zero_residue_target_state`
> 在 unit 分支内是预期红测（SPEC.md 已更新为目标态，旧 snippet 不存在）。这两个测试的改写属 M4，
> M1 不负责，见 dispatch 包说明。

## R1 — DI 重构：core/llm/factory.py 端口化 + platform factory

- Context: `agent.core.llm.factory` 直接 import `agent.platform.llm.providers.*` 违反 core 不依赖 platform 的架构规则（#40）。同时 `agent.core.hooks.context` 有一个 lazy import `agent.platform.permissions.broker.PermissionResponse`，也是违例。
- Decision:
  1. 新建 `agent/platform/llm/factory.py`，接收 `_PROVIDER_CLIENTS` + `create_llm_client`（要求 `config` keyword-only 参数）
  2. `agent/core/llm/factory.py` 删除所有 platform imports，只保留 `LLMFactoryConfig` dataclass
  3. `agent/core/llm/__init__.py` 移除 `create_llm_client` 导出
  4. `AgentRuntime` 新增 `llm_client_factory: Callable[[LLMFactoryConfig], LLMClient] | None = None` 参数；构造时 `llm_client` 优先，其次 factory，否则 raise；`reconfigure_llm` 要求 factory
  5. `platform/http_api/app.py` 注入 lambda 适配器
  6. `agent/core/hooks/context.py` fail-closed 路径改用 `types.SimpleNamespace` 替代 lazy platform import
  7. 更新受影响测试：`test_core_llm_location.py`、`test_runs_registry_transport_lifecycle.py`、`test_memory_snapshot.py`、whitelist 行号
- Rationale: DI 是唯一干净方案——core 零 platform 依赖，composition root（build_kernel/create_app）是唯一同时认识两层的装配点。单测路径（`llm_client=FakeLLMClient()`）不受影响。
- Evidence:
  - Tests: `pytest tests/contract/test_core_no_platform_imports.py` — 1 passed（去 xfail 后绿）；`pytest tests/unit/ tests/contract/ -q` — 2081 passed, 135 warnings（排除 M4 预期红测）
  - Entry: N/A（纯架构重构，无用户入口变化）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A — 不涉及用户可观察行为变化；contract/unit 全绿
  - Visual/Interaction: N/A
- Rollback: `git revert b4e4b500`
- Commits: C1=fac48e98, C2=b4e4b500, C3=<待填>
- Next: R2 — 新增 agent/sdk/ 模块（build_kernel + Kernel）

