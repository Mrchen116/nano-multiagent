# M226 Progress

## Situation
- Milestone: M226 — Gateway本地配置模型扩展与YAML持久化
- execution_mode: serial, worktree: .worktrees/M226, branch: milestone/M226
- test_command: `python -m pytest tests/ -x -q 2>&1 | tail -30`
- Baseline: unit tests pass; pre-existing NameError in runtime.py (forbidden scope) blocks full suite
- Scoped test: `python -m pytest tests/unit/personal_assistant/test_local_store.py -x -q`

### R1 扩展 AgentWorkspaceConfig 字段并解析
- Context: AgentWorkspaceConfig 缺少 system_prompt/group_reply_policy/default_model 字段；_parse_agents 不解析 skills/tool_allowlist
- Decision: 在 dataclass 添加5个可选字段（skills/tool_allowlist 默认空 tuple，其余默认 None），_parse_agents 全部解析，新增 _parse_string_list 辅助函数
- Rationale: 向后兼容，旧 YAML 无新字段时用默认值
- Evidence:
  - Tests: 14 passed (12 existing + 2 new)
  - Entry: load_local_config 正确加载含/不含扩展字段的 YAML
- Rollback: C1 = 2e7b479
- Commits: C1=2e7b479, C2=e15cb5f, C3=pending
- Next: R2 save_local_config
