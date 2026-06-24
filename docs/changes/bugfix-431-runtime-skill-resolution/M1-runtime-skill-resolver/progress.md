# bugfix-431-M1 progress

## 开工澄清（§2.5 记录）

无歧义。范围与 design.md Milestone 表一致。

---

### R1 — core/skills 下沉 + AgentRuntime 参数 + sdk/kernel 改写 + platform agent 工具校验

(R1-R5 合并为单 roadpoint，5 件事内聚、单 commit 可 revert)

- Context: `_WorkspaceDirnameSkillResolver` 和内联 resolver 构造散落在 `agent.sdk.kernel`，若留在 sdk 层会让 `AgentRuntime`（core）只能向上 import sdk 违反边界；必须先下沉到 `agent.core.skills.discovery`，再让 AgentRuntime 同层调用。
- Decision:
  1. `_WorkspaceDirnameSkillResolver` + `make_skill_resolver` 移入 `agent.core.skills.discovery`；`__all__` 导出 `make_skill_resolver`
  2. `AgentRuntime.__init__` 移除 `config_resolver` / `ConfigResolverLike`，新增 `workspace_config_dirname: str | None` + `skill_search_roots: tuple[Path, ...]`；添加 `resolve_available_skills(workspace_root, include_names)` 方法
  3. `agent.sdk.kernel` 删内联 `_WorkspaceDirnameSkillResolver`；`Kernel.list_skills`、`assemble_prompt_preview`、`_build_kernel_base` 全改用 `from agent.core.skills import make_skill_resolver`（向下 import，合法）
  4. `agent.platform.tools.builtins.agent._validate_new_agent_args` 改用 `self._runtime.resolve_available_skills(...)`
  5. `default_skill_search_roots` 删隐式 Codex 回退根（决策 4）
- Rationale: 5 条 skill 发现路径（list_skills / preview / _resolve_session_available_skills / _from_config(compact) / agent 工具校验）全经同一个 `make_skill_resolver`，消除运行时与预览不同源的根因。
- Evidence:
  - Tests: `pytest tests/unit/ tests/integration/ tests/contract/ -m "not e2e"` → **2495 passed, 0 failed**
  - boundary contract: `test_agent_sdk_boundary_contract.py` 绿（core 无 `import agent.sdk`）
  - 归属断言: `test_make_skill_resolver_lives_in_core` 绿（`make_skill_resolver.__module__ == "agent.core.skills.discovery"`）
  - Entry: 纯逻辑改动，e2e runtime vs preview 同源验证留 [reviewer] 走真实 Gateway 会话
  - Frontend State Matrix: N/A（无前端变更）
  - Browser QA: N/A
  - E2E/Regression: N/A（e2e 属 [reviewer] 验收范围，见 tasks.md 测试策略）
  - Visual/Interaction: N/A
- Rollback: 回退到 `b6a5b324`（C1 红测试 commit）
- Commits: C1=b6a5b324, C2=ca27c760, C3=（本次）
- Next: 集成到 unit/bugfix-431 分支，清理 worktree，回报 orchestrator
