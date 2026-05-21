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

(待填)

## R4 — ISSUE-3 features 门控验证

(待填)

## R5 — ISSUE-1 agent-create-page Behavior card 重构

(待填)

## R6 — ISSUE-4 default_system_prompt 处理

(待填)
