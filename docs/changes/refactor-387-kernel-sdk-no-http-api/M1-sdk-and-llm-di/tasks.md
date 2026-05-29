# refactor-387-M1: sdk-and-llm-di — Tasks

> 对齐: ../design.md v1

## 目标

1. 新增 `agent/sdk/`：`build_kernel()` 装配函数 + `Kernel` 类，封装 `create_app` 函数体中去掉 FastAPI/routes/middleware 后的装配逻辑（复用 bootstrap_product / AgentRuntime / RunsRegistry / EventStreamHub / PermissionBroker / wire_background_tasks / build_tool_registry / build_hook_registry）。
2. 删除名不副实的 `agent/platform/sdk/client.py`（旧 HTTP client）。
3. #40 DI 重构：`core/llm/factory.py` 端口化（只留 `LLMClient` 接口 + `LLMFactoryConfig` dataclass），具体 provider factory 移到 `agent/platform/llm/factory.py`，注入 `AgentRuntime`（构造 + `reconfigure_llm`）。

## 退出标准

- [x] 新增 `agent/sdk` 表面契约测试 green（含跨 loop 流式 + can_use_tool 权限回调 + 等权限时 interrupt 能取消）
- [x] `tests/contract/test_core_no_platform_imports.py` 去掉 xfail 后 green（core 零 platform import）
- [x] 新增「产品只能 import `agent.sdk`」边界守卫雏形（contract 测试）

## 测试策略

- 被测行为（来自退出标准）：
  1. `agent.sdk.build_kernel()` 能构建可用 Kernel
  2. 跨 loop 流式：RunsRegistry 后台 loop 跑 turn，消费方 loop 迭代 EventStreamHub async iterator 能收到事件
  3. can_use_tool 权限回调：内核工具确认流程调用注入的 can_use_tool 回调
  4. 等权限时 interrupt 能取消该 turn
  5. core 包零 platform import（去 xfail 绿测试）
  6. 产品只能 import agent.sdk（边界守卫）
- 已有测试在：`tests/contract/test_core_no_platform_imports.py`（去 xfail，修完即绿）；无合适已有文件覆盖 sdk 表面，新建 `tests/contract/test_agent_sdk_surface_contract.py`，理由：M1 专属新模块行为，无现有覆盖；产品边界守卫新建 `tests/contract/test_agent_sdk_boundary_contract.py`，理由：新边界规则无现有覆盖
- 落层/目录/marker：`tests/contract/` ，marker：无（非 e2e，不需要真实 LLM 或长驻进程）
- 可选依赖 importorskip：无
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无

## Roadpoints

### R1 — DI 重构：core/llm/factory.py 端口化 + platform factory

- 步骤：
  1. 新建 `agent/platform/llm/factory.py`：把 `_PROVIDER_CLIENTS` / `_resolve_client_class` / `create_llm_client` 移入，重命名为 `create_platform_llm_client`（或保留 `create_llm_client`，让 platform 模块负责具体实例化）
  2. `agent/core/llm/factory.py` 删掉 platform import + `_PROVIDER_CLIENTS` + `_resolve_client_class` + `create_llm_client`，只保留 `LLMFactoryConfig` dataclass
  3. `AgentRuntime` 构造函数增加 `llm_client_factory` 参数（callable `LLMFactoryConfig -> LLMClient`），构造和 `reconfigure_llm` 都经注入的 factory 建 client；`create_llm_client` 调用替换为 `self._llm_client_factory(config)`
  4. 更新 `AgentRuntime` 内 from-env fallback：若未注入 factory，使用 platform factory（为 HTTP API 路径后向兼容）
- 验证：`test_core_no_platform_imports.py` 去 xfail 后 green；现有 `test_llm_config_contract.py` 和 `test_llm_provider_contract.py` 仍绿

### R2 — 新增 agent/sdk/ 模块（build_kernel + Kernel）

- 步骤：
  1. 新建 `agent/sdk/__init__.py` 暴露 `build_kernel` + `Kernel`
  2. `build_kernel(*, product_profile, llm_config, can_use_tool, repo_root=None) -> Kernel`：从 `create_app` 函数体复制装配逻辑，去掉 FastAPI/routes/middleware；注入 platform factory 进 runtime（#40 产物）；can_use_tool 接线到 PermissionBroker（详见 R3）
  3. `Kernel` 类实现 design 接口段所有方法（委托给 AgentRuntime / RunsRegistry / EventStreamHub）
  4. 删除 `agent/platform/sdk/client.py`（旧 HTTP client），更新 `agent/platform/sdk/__init__.py`
- 验证：新建 `tests/contract/test_agent_sdk_surface_contract.py`，覆盖 build_kernel 能创建 Kernel 实例 + 基本方法可调用

### R3 — can_use_tool 回调接线到 PermissionBroker

- 步骤：
  1. 分析 auto_mode_gate hook park 流程（`PermissionBroker.register_request`），在 `agent/sdk/kernel.py` 中实现一个内部桥接：监听 permission_request 事件，在 broker park future 挂起时 await can_use_tool 回调，将返回值 resolve broker future
  2. 确保等权限期间 interrupt 能 cancel_all_pending 中止等待
- 验证：`test_agent_sdk_surface_contract.py` 中的 can_use_tool 回调测试 + 等权限时 interrupt 测试 green

### R4 — 契约测试（去 xfail + 边界守卫）+ 收尾

- 步骤：
  1. 去掉 `test_core_no_platform_imports.py` 中的 `@pytest.mark.xfail`
  2. 新建 `tests/contract/test_agent_sdk_boundary_contract.py`：断言 `coding_cli` 和 `personal_assistant` import 的 `agent.*` 只能是 `agent.sdk.*`（雏形守卫，M4 才全量，M1 只做守卫框架 + 基本断言）
  3. 全量跑 `pytest tests/contract/ tests/unit/` 确保全绿
- 验证：全量测试 green，无 xfail 残留在 M1 范围内的代码
