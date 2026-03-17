# M228 - 运行态生效链修复：从Gateway本地配置驱动session

## Roadpoints

### R1: _build_session_metadata reads from local AgentWorkspaceConfig
- **Acceptance**:
  1. `_build_session_metadata` uses `self._agents[agent_id]` for system_prompt/skills/tool_allowlist
  2. No longer a @staticmethod (becomes instance method)
  3. message.metadata system_prompt/skills/tool_allowlist are ignored
  4. conversation_id/config_profile_version still come from message.metadata
  5. Existing tests updated to match new behavior
- **Tests Plan**: unit (primary); integration not needed as this is a pure logic change
- **Expected Tests**:
  - `tests/unit/personal_assistant/test_gateway_pipeline.py::test_build_session_metadata_reads_system_prompt_from_local_agent_config`
  - `tests/unit/personal_assistant/test_gateway_pipeline.py::test_build_session_metadata_reads_skills_and_tool_allowlist_from_local_agent_config`
  - `tests/unit/personal_assistant/test_gateway_pipeline.py::test_build_session_metadata_ignores_message_metadata_for_prompt_fields`
  - `tests/unit/personal_assistant/test_gateway_pipeline.py::test_build_session_metadata_still_reads_conversation_id_from_message_metadata`
- **DoD**: `test_command` all green + C1/C2/C3
- **Status**: TODO
