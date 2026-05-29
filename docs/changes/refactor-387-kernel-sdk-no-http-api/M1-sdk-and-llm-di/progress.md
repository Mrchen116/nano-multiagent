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
- Commits: C1=fac48e98, C2=b4e4b500, C3=7cfd0975
- Next: R2 完成

## R2 — 新增 agent/sdk/ (build_kernel + Kernel) + 删除旧 HTTP client

- Context: M1 第二件事：新增 `agent/sdk/` 作为唯一对外面（build_kernel + Kernel）；删除名不副实的 `agent/platform/sdk/client.py`（旧 HTTP client）。
- Decision:
  1. 新建 `src/agent/sdk/__init__.py` 暴露 `build_kernel` + `Kernel`
  2. `src/agent/sdk/kernel.py` 实现 Kernel 类（全 async-native 方法）+ `build_kernel()` 装配函数（镜像 create_app 去掉 FastAPI）
  3. can_use_tool 回调接线：在 `Kernel.__init__` 中构造一个 `permission_requester` 注入 `runtime._permission_requester`；broker park 机制保留（interrupt 路径），can_use_tool 与 broker Future 通过 asyncio.wait race（先返回者获胜）
  4. interrupt 调 `cancel_all_pending(run_id=None)` 取消所有 pending 权限请求（SDK 路径不按 run_id 范围 park）
  5. `agent/platform/sdk/__init__.py` 清空（旧 ServerClient 已删，保留空 __init__ 用于过渡）
  6. 删除 `tests/unit/test_platform_sdk_location.py` + `test_sdk_client.py`（测的是已删类）
  7. 更新 `test_no_legacy_homing_imports.py`（sdk 移出 REMOVED_ROOTS），`test_multi_product_architecture_acceptance.py`（删 platform/sdk/client.py，加 sdk/__init__.py），`test_apps_coding_cli_location.py`（agent.sdk 现在存在是预期的）
- Rationale: `build_kernel` 是 composition root，所有装配逻辑聚焦于此，产品只见 Kernel。can_use_tool 回调通过 permission_requester 接线比旧 event+HTTP resolve 更直接。
- Evidence:
  - Tests: `pytest tests/contract/test_agent_sdk_surface_contract.py` — 5 passed；`pytest tests/unit/ tests/contract/ -q` — 2080 passed, 2 failed (M4 预期红测), 1 xfailed
  - Entry: N/A（SDK 纯库，无 HTTP 入口；M2/M3 产品迁移后才有真实入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 5 个 SDK 表面契约测试覆盖：build_kernel smoke + 必要方法 + 跨 loop 流式 + can_use_tool 回调 + interrupt 取消权限等待
  - Visual/Interaction: N/A
- Rollback: `git revert 68c7b29f`
- Commits: C1=b7e9c137, C2=68c7b29f, C3=<待填>
- Next: R3 — 产品边界守卫 + 全量验证

