# bugfix-431-M1: runtime-skill-resolver

## 目标

让 `AgentRuntime` runtime skill resolution 与 `Kernel.list_skills` / `assemble_prompt_preview` 完全同源，消除两套独立 resolver 实现导致的行为不一致。

## 退出标准

- `[worker]` `pytest tests/unit/ tests/integration/ tests/contract/ -m "not e2e"` 全绿
- `[worker]` `tests/contract/test_agent_sdk_boundary_contract.py` 绿（core 无 `import agent.sdk` 反向依赖）
- `[worker]` `test_core_skills_location.py` 断言 `make_skill_resolver` 住 core
- `[worker]` 新增/更新单元测试覆盖 runtime skill resolution 与 preview 同源

## 测试策略

纯后端逻辑改动（无前端）。

- R1 红测试：为 `make_skill_resolver` 在 `test_core_skills_location.py` 添加模块归属断言（住 core 非 sdk），以及为 `AgentRuntime.resolve_available_skills` 行为写单元测试，确认先红再绿。
- R2-R4 行为测试：`resolve_available_skills` 是核心行为方法，在 `tests/unit/` 补覆盖它的单元测试。
- 不做前端验收（无 UI 变更）。
- entry test: 本次 bug 的最终症状（runtime vs preview 同源）属于 e2e 场景（真 Gateway 进程 + LLM proxy），超出 `tests/unit/ -m "not e2e"` 范围，按退出标准只需 worker 级单测全绿 + `[reviewer]` 走真实会话验收。

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | core/skills 下沉：`_WorkspaceDirnameSkillResolver` + `make_skill_resolver` | DONE |
| R2 | core/skills `__init__` 导出 + 清理 `default_skill_search_roots` Codex 回退 | DONE |
| R3 | AgentRuntime：新增 resolver 参数 + `resolve_available_skills` 方法 + 移除 `config_resolver` | DONE |
| R4 | sdk/kernel：注入参数 + 改向下 import + 删内联 resolver | DONE |
| R5 | platform/tools/builtins/agent：子 agent 校验改用 runtime 方法 | DONE |
