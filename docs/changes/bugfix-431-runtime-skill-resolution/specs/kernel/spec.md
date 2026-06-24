# kernel delta-spec — bugfix-431

## ADDED Requirement: runtime skill resolution 与 preview / list_skills 同源

### Scenario: 同一 agent 的 preview 与 runtime 技能集合一致

- **GIVEN** 消费者经 `build_kernel(skill_search_roots=..., workspace_config_dirname=...)` 装配 Kernel，并创建一个 session 且 `skills` 包含若干通过 `skill_search_roots` 或 workspace 配置目录暴露的技能名
- **WHEN** 调用 `Kernel.assemble_prompt_preview(..., skill_ids=..., workspace_root=...)` 与 `AgentRuntime` 真实执行该 session turn
- **THEN** 两者解析到的 `SkillMetadata` 集合相同，即真实 LLM 请求中的 `<available_skills>` 与 preview 中展示的技能一致

### Scenario: 子 agent 加载技能使用与父 runtime 同源的 resolver

- **GIVEN** 某 session 的 agent 调用 `agent` 工具创建子 agent，并传入 `load_skills`
- **WHEN** `agent` 工具校验 `load_skills` 是否存在
- **THEN** 校验使用的技能搜索根与 `Kernel.list_skills(workspace_root)` / `assemble_prompt_preview` 同源，即覆盖 `workspace_config_dirname` 下的 skills 目录与 `skill_search_roots`

### Scenario: 未提供 workspace_config_dirname 时无隐式默认 roots

- **GIVEN** 消费者经 `build_kernel()` 未传入 `workspace_config_dirname`
- **WHEN** `AgentRuntime` / `Kernel.list_skills` / `assemble_prompt_preview` 需要解析 skills
- **THEN** 返回空 skills 列表，不再隐式搜索 `~/.codex/skills` 或 `<workspace>/.codex/skills` 等 legacy 默认路径
