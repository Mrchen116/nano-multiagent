# TASKS/M76 多产品架构重构三期：抽出 local_coding 产品默认能力

## 目标
把 coding prompt、默认 tools/hooks 从共享层抽离到 local_coding 产品定义中，让 core/shared 层不再持有产品专属默认值，同时保持 coding CLI 主链路兼容。

---

## Roadpoints

### R76.1 中和 DEFAULT_SYSTEM_PROMPT，将 coding prompt 迁至 local_coding（C1=0b9cb69 C2=b271e4e）

**状态**: DONE

**Acceptance**:
1. `agent/prompting.py` 中 `DEFAULT_SYSTEM_PROMPT` 不再是 coding 专属文案（改为通用空字符串或通用 fallback）
2. `CODING_SYSTEM_PROMPT` 在 `agent/prompting.py` 中定义并导出（backward-compat alias）
3. `LOCAL_CODING_PROFILE.default_system_prompt` 等于原 coding 文案（`CODING_SYSTEM_PROMPT`）
4. `agent/loop.py` 使用通用 fallback，不再绑定 coding 专属默认值
5. `bootstrap.py` 不再 fallback 到 `DEFAULT_SYSTEM_PROMPT` 当 profile 有 prompt 时

**Tests Plan**:
- unit: 测试 `DEFAULT_SYSTEM_PROMPT` 为通用 fallback（空字符串或 "You are a helpful assistant."）
- unit: 测试 `CODING_SYSTEM_PROMPT` 包含原来的 coding 文案
- unit: 测试 `LOCAL_CODING_PROFILE.default_system_prompt == CODING_SYSTEM_PROMPT`
- unit: 测试 `AgentLoop(system_prompt=...)` 使用注入值，不默认 coding 专属文案
- contract: 不选（暂无新协议结构）
- integration: 不选（prompt 渲染已有 integration 覆盖）
- e2e: 不选（主链路行为不变，现有 e2e 即可回归）

**Expected Tests**:
- `tests/unit/test_agent_prompting.py::test_default_system_prompt_is_generic_fallback`
- `tests/unit/test_agent_prompting.py::test_coding_system_prompt_contains_coding_content`
- `tests/unit/test_local_coding_profile.py` — 更新 `test_local_coding_profile_system_prompt_matches_default` 测试

**DoD**: pytest -q 全绿（512 passed） + C1/C2/C3 齐全 + PROGRESS 写清

---

### R76.2 local_coding 明确列出 default_tool_ids 与 default_hook_modules（C1=f499448 C2=21e4f8b）

**状态**: DONE

**Acceptance**:
1. `LOCAL_CODING_PROFILE.default_tool_ids` = `["read", "write", "edit", "bash", "task"]`
2. `LOCAL_CODING_PROFILE.default_hook_modules` 列出内置 hook 模块名称列表（4 个内置模块）
3. `bootstrap.py` 当 `profile.default_tool_ids` 非 None 时，只注册指定 tool ids
4. `bootstrap.py` 当 `profile.default_hook_modules` 非 None 时，只加载指定 hook 模块
5. 现有主链路行为不变（local_coding 列出的就是当前所有内置）

**Tests Plan**:
- unit: 测试 `LOCAL_CODING_PROFILE.default_tool_ids` 包含 5 个指定 tool ids
- unit: 测试 `LOCAL_CODING_PROFILE.default_hook_modules` 非 None 且包含内置 hook 模块
- unit: 测试 `bootstrap_product` 当 `default_tool_ids` 非 None 时只注册指定工具
- integration: 测试 `bootstrap_product(local_coding)` 返回 registry 中有且仅有预期 tools
- contract: 不选（ProductProfile 结构已验证）
- e2e: 不选（主链路行为不变）

**Expected Tests**:
- `tests/unit/test_local_coding_profile.py::test_local_coding_profile_default_tool_ids`
- `tests/unit/test_local_coding_profile.py::test_local_coding_profile_default_hook_modules`
- `tests/unit/test_platform_bootstrap.py::test_bootstrap_respects_default_tool_ids`
- `tests/integration/test_bootstrap_integration.py::test_bootstrap_local_coding_tool_ids`

**DoD**: pytest -q 全绿（512 passed） + C1/C2/C3 齐全 + PROGRESS 写清

---

### R76.3 server/app.py 通过 ResolvedProductConfig 注入 system_prompt

**状态**: DONE

**Acceptance**:
1. 当 `product_profile` 提供时，`create_app` 通过 `bootstrap_product` 得到 `resolved_system_prompt`
2. `AgentRuntime` 接受 `system_prompt` 参数（当通过 profile 构建时）
3. `AgentLoop` 注入来自 ResolvedProductConfig 的 system_prompt，不走 coding 默认
4. 无 profile 时向后兼容（`create_app()` 无变化）
5. loop/runtime 代码中无 `DEFAULT_SYSTEM_PROMPT` 直接引用（已迁移）

**Tests Plan**:
- unit: 测试 `create_app(product_profile=profile)` 用 profile 的 resolved_system_prompt
- unit: 测试 `AgentRuntime` 接受 `system_prompt` 参数并传给 AgentLoop
- integration: 测试 profile 注入后实际 prompt 渲染包含 profile 的 system_prompt 内容
- contract: 不选
- e2e: 不选（现有 e2e 覆盖主链路不变）

**Expected Tests**:
- `tests/unit/test_app_factory_with_profile.py::test_create_app_with_profile_uses_resolved_system_prompt`
- `tests/unit/test_agent_runtime.py::test_agent_runtime_accepts_system_prompt`
- `tests/integration/test_bootstrap_integration.py::test_bootstrap_local_coding_system_prompt_injected`

**DoD**: pytest -q 全绿（512 passed） + C1/C2/C3 齐全 + PROGRESS 写清
