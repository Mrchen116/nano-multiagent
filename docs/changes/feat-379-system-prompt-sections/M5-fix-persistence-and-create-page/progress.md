# M5 Progress

## 基线

- 测试基线: 7 failed (预存失败, 与本 M5 无关), 2297 passed, 22 skipped
- 基线失败列表: test_message_contract_fields_are_stable, test_dispatch_handler_build_aiohttp_handler_returns_callable, test_fork_conversation_inherits_parent_system_prompt, test_fork_conversation_inherits_parent_active_tools_byte_for_byte, test_fork_executor_denies_unlisted_tool_at_execution_layer, test_agent_loop_turn_meta_includes_tool_iterations, test_runtime_agent_end_payload_includes_tool_iterations

## R1/R2 — IM PATCH/GET 字段修复 + AgentConfigResponse 更新

**根因**: HTTP 路由层 `UpdateAgentConfigRequest` 缺 `features`/`custom_prompt` 字段, `AgentConfigResponse` 缺同字段, `update_agent_config()` 路由未传给 `ConfigService.update_profile()`。DB/仓库层 (M2 已做) 完全正常。

**修复**:
- `src/IM/api/routes/agents.py`: `UpdateAgentConfigRequest` 加字段、`AgentConfigResponse` 加字段、`to_agent_config_response()` 映射、`update_agent_config()` 传透到 service
- `src/IM/application/config_service.py`: `update_profile()` 加 `features`/`custom_prompt` 参数并透传
- `tests/im_service/contract/test_agent_config_contract.py`: 更新 shape 断言、新增 `test_patch_agent_config_persists_features_and_custom_prompt`
- `tests/im_service/contract/test_agent_create_contract.py`: 更新 shape 断言含新字段

**结果**: 250 IM 测试全通过 (含 1 新增 contract test), 0 新增失败。

## R3 — Gateway features 写回 config.yaml 验证

已有测试覆盖 (`test_gateway_im_config_sync.py`: `test_sync_agent_passes_through_features` 等 3 个)。
`sync_agent()` 在 `main.py:287-331` 已正确从 IM GET /config 读取 features/custom_prompt 并写进
`AgentWorkspaceConfig`。`test_local_store.py` 32 个测试全通过含 round-trip 验证。
**无需新增代码**，根因是测试覆盖缺口误报。

## R4 — ISSUE-3 features 门控验证

**根因**:`core_sections.py` 中 `_memory_guidance_enabled()` gate 已正确实现,缺少测试。
**修复**:在 `tests/unit/agent/test_core_sections_m4.py` 新增 6 个 `TestMemoryGuidanceFeatureGate` 测试:
  - `enabled_when_memory_tool_present_and_flag_default` / `_flag_true` — 正向
  - `disabled_when_memory_curation_false` — gate 抑制
  - `disabled_when_no_memory_tool_flag_true` — 工具缺失
  - `test_assemble_excludes/includes_memory_section_*` — 端到端汇编断言
6/6 通过。

## R5 — ISSUE-1 agent-create-page Behavior card 重构

**根因**:`agent-create-page.tsx` 未迁移,仍显示 system_prompt textarea 和 useEffect 预填。
**修复**:
- 新增 `CreateBehaviorCard` 组件(内联),与 `agent-detail-page.tsx BehaviorCard` 同款设计
- Custom Instructions textarea (optional, maps to custom_prompt)
- Features 开关组 (按 capabilities.features 渲染,unavailable → disabled + tooltip)
- Group Reply Policy select
- 折叠 Preview panel (aria-expanded + ▸/▾)
- 移除 `system_prompt` 预填 useEffect
- 更新 `EMPTY_DRAFT` 加 `custom_prompt: ""`、`features: {}`
- `normalizeDraft` 固定 `system_prompt: ""` + 透传 features/custom_prompt
- 更新 `agent-create.test.tsx`: 加 promptPreview mock、更新断言字段名
4/4 前端测试通过。

## R6 — ISSUE-4 default_system_prompt 处理

**根因**:`build_runtime_capabilities()` 发送含 `<RUNTIME_FILL:*>` 的原始模板字符串给 IM 前端。
**决定**:清空为空字符串(segments 体系接管 prompt 组装; R5 后前端不再使用该字段预填)。
**修复**:`src/personal_assistant/reporter/upstream_reporter.py`: `default_system_prompt=""` + 说明注释。
新增测试 `test_build_runtime_capabilities_default_system_prompt_has_no_runtime_fill_placeholders` 验证。
