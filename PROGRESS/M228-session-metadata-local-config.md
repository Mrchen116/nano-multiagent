# M228 Progress - 运行态生效链修复：从Gateway本地配置驱动session

## Baseline
- 20 tests pass in test_gateway_pipeline.py
- Pre-existing ToolSpec import error in agent/core (forbidden scope, not M228 concern)

### R1: _build_session_metadata reads from local AgentWorkspaceConfig
- Context: `_build_session_metadata` was a @staticmethod reading system_prompt/skills/tool_allowlist from relay-pushed `message.metadata`. This caused stale or missing config when relay was out of sync.
- Decision: Changed to instance method reading from `self._agents[agent_id]` (local AgentWorkspaceConfig). Routing fields (conversation_id, config_profile_version) still from message.metadata.
- Rationale: Local config is the single source of truth after M226; relay metadata should not override it.
- Evidence:
  - Tests: 24 passed (4 new + 20 existing, 3 existing updated)
  - Entry: `_build_session_metadata` now reads agent.system_prompt/skills/tool_allowlist; message.metadata prompt fields are ignored.
- Rollback: ec70e2a (C1)
- Commits: C1=ec70e2a, C2=bae64b4, C3=pending
- Next: Merge to main
