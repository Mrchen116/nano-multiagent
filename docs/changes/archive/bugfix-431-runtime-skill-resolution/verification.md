# Verification Report: bugfix-431

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 5/5 tasks complete |
| Correctness | 3/3 scenarios covered |
| Coherence | Followed（4 决策全遵守） |

No critical issues. 2 warning(s) to consider. Ready for PR (with noted improvements).

---

## Completeness

### Tasks: 5/5 complete

tasks.md 中 R1–R5 全部标 DONE：

| Roadpoint | 状态 |
|---|---|
| R1: core/skills 下沉 (`_WorkspaceDirnameSkillResolver` + `make_skill_resolver`) | DONE |
| R2: core/skills `__init__` 导出 + 清理 `default_skill_search_roots` Codex 回退 | DONE |
| R3: AgentRuntime 新增 resolver 参数 + `resolve_available_skills` 方法 + 移除 `config_resolver` | DONE |
| R4: sdk/kernel 注入参数 + 改向下 import + 删内联 resolver | DONE |
| R5: platform/tools/builtins/agent 子 agent 校验改用 runtime 方法 | DONE |

### Spec 覆盖

delta-spec 三条 Requirement 全部有实现：

1. **runtime skill resolution 与 preview/list_skills 同源** — `make_skill_resolver` 住 `agent.core.skills.discovery`，5 条路径全经同一 helper
2. **子 agent 加载技能使用同源 resolver** — `agent.py:658` 改用 `runtime.resolve_available_skills`
3. **无隐式默认 roots（无 workspace_config_dirname 时返回空）** — `discovery.py:112` `config_resolver=None` 时返回空元组

---

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| Scenario 1: preview 与 runtime 技能集合一致 | `runtime.py:963-996`（`resolve_available_skills`）；`kernel.py:1128`（`list_skills`）；`kernel.py:1393`（`assemble_prompt_preview`）—— 三者均经 `make_skill_resolver` | `test_runtime_skill_resolution_same_source.py:61`（`test_runtime_sees_same_skills_as_list_skills`）、`test_runtime_resolves_workspace_skills_not_empty`、`test_extra_deployment_root_visible_through_both_paths`、`test_include_names_filter_consistent_across_paths` | covered |
| Scenario 2: 子 agent 加载技能使用同源 resolver | `agent.py:658`（`_validate_new_agent_args` 改用 `runtime.resolve_available_skills`）| 所有现有 `test_agent_tool.py` 用 `load_skills=[]`，不含非空 skill 名的校验路径测试 | **WARNING**: 缺测试（见 Issues） |
| Scenario 3: 无 workspace_config_dirname 时无隐式 Codex roots | `discovery.py:112`（`config_resolver=None` → 空元组）；`runtime.py:990`（`resolver is None` → 返回 `()`） | `test_core_skills_location.py:80`（`test_make_skill_resolver_returns_none_without_dirname`）；但缺 `AgentRuntime.resolve_available_skills` 层面的"无 dirname → 返回空元组"单元测试 | covered（部分）|

---

## Coherence

### design.md 关键决策遵守情况

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 决策 1: AgentRuntime 持有 `workspace_config_dirname` + `skill_search_roots`，内部按需构造 resolver | 是 | `runtime.py:115-116`（参数定义）；`runtime.py:147-148`（存储）；`runtime.py:985-995`（`resolve_available_skills` 方法用 `make_skill_resolver` 构造） |
| 决策 2: helper（`_WorkspaceDirnameSkillResolver` + `make_skill_resolver`）下沉 `agent.core.skills`，所有路径同源 | 是 | `discovery.py:18`（类定义）；`discovery.py:53`（helper 定义）；`kernel.py:1121`（sdk 向下 import core helper）；`agent.py:658`（platform 经 runtime 方法间接调用）；`runtime.py:985`（core 同层调用） |
| 决策 3: 移除 `AgentRuntime.config_resolver` property，新增 `resolve_available_skills` 方法 | 是 | `runtime.py` 全仓 grep `config_resolver` 只剩注释（第 111 行）和 `discovery.py` 的参数签名；`agent.py:658` 已改用 `runtime.resolve_available_skills` |
| 决策 4: 清理 `default_skill_search_roots` 的 Codex roots 默认回退 | 是 | `discovery.py:87-114`（`config_resolver=None` 时返回空元组；Codex 回退路径已删）；`build_kernel` 传入 workspace_config_dirname 默认 `".nano"` 确保有 resolver 兜底 |

### 架构自洽性核查（§4.3）

- **依赖方向** — `agent.core` 无 `import agent.sdk`（grep 全仓 core 目录，注释除外零违反）。`test_core_no_platform_imports.py` 守护 core 不 import platform/products/apps，通过。
- **helper 归属** — `_WorkspaceDirnameSkillResolver` 和 `make_skill_resolver` 只在 `agent.core.skills.discovery` 定义，`agent.sdk.kernel` 无内联副本（grep 确认）。
- **复用 vs 平行** — sdk 的 `list_skills` / `assemble_prompt_preview` 均经 `from agent.core.skills import make_skill_resolver`（`kernel.py:1121`、`kernel.py:1385-1386`），无平行实现。
- **5 条路径同源核实**：
  1. `Kernel.list_skills` → `make_skill_resolver` (`kernel.py:1128`)
  2. `Kernel.assemble_prompt_preview` → `make_skill_resolver` (`kernel.py:1393`)
  3. `AgentRuntime._resolve_session_available_skills` → `self.resolve_available_skills` → `make_skill_resolver` (`runtime.py:1340`)
  4. `AgentRuntime._resolve_session_available_skills_from_config`（含 compact 路径） → `self.resolve_available_skills` → `make_skill_resolver` (`runtime.py:1354`)
  5. `agent` 工具 `_validate_new_agent_args` → `runtime.resolve_available_skills` → `make_skill_resolver` (`agent.py:658`)

  所有路径均经同一 helper，无绕开路径。

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

**W1**: delta-spec Scenario 2（子 agent 加载技能使用同源 resolver）缺单元测试

- 问题：`_validate_new_agent_args` 已改用 `runtime.resolve_available_skills`（`agent.py:658`），但 `tests/unit/agent/tools/test_agent_tool.py` 中所有 `load_skills` 均为空列表 `[]`，从未测过非空 skill 名的校验路径。若 `load_skills=["some-skill"]` 且 skill 不存在时应抛 `ToolError("unknown skills requested")`，这条路径无回归测试。
- 建议：在 `tests/unit/agent/tools/test_agent_tool.py` 或新增的专项文件中添加：
  1. `load_skills=["nonexistent-skill"]` 时 `_validate_new_agent_args` 抛 `ToolError` 的 mock 测试
  2. `load_skills=["existing-skill"]` 时 `runtime.resolve_available_skills` 被正确调用（用 mock 确认 resolver 入参包含 workspace_root）

**W2**: `AgentRuntime.resolve_available_skills` 的 `workspace_config_dirname=None` 路径（Scenario 3 runtime 层）缺专项测试

- 问题：`test_make_skill_resolver_returns_none_without_dirname` 只测了 `make_skill_resolver` 层（resolver 返回 `None`）；没有从 `AgentRuntime` 整体层面断言"build_kernel 未传 workspace_config_dirname 时 `resolve_available_skills` 返回空元组"。`runtime.py:990-991` 的 `if resolver is None: return ()` 无测试。
- 建议：在 `test_runtime_skill_resolution_same_source.py` 补一条 `test_runtime_returns_empty_when_no_config_dirname`：构造无 `workspace_config_dirname` 的 `AgentRuntime`，断言 `runtime.resolve_available_skills(tmp_path)` 等于 `()`。

### SUGGESTION（可以修）

**S1**: `test_agent_sdk_boundary_contract.py` 未守护 `agent.core ↛ agent.sdk` 方向

- 问题：`test_core_no_platform_imports.py` 守护 core 不 import platform/products/apps，但 `FORBIDDEN_PREFIXES` 不含 `"agent.sdk"`。虽然当前 core 没有 import sdk，但这一方向无自动回归守护，未来有人误加不会被 CI 检测到。
- 建议：在 `test_core_no_platform_imports.py:19` 的 `FORBIDDEN_PREFIXES` 列表中追加 `"agent.sdk"`，或在 `test_agent_sdk_boundary_contract.py` 补一条测函数，遍历 `CORE_ROOT/*.py` 断言无 `"agent.sdk"` import。

**S2**: `test_include_names_filter_consistent_across_paths` 未覆盖 `session.skills` 的实际 runtime 执行路径

- 问题：该测试直接调用 `runtime.resolve_available_skills(workspace, include_names=[...])` 而非经 `_resolve_session_available_skills_from_config`，与真实 `runtime.run` 路径有一层间接。现有 `test_agent_runtime.py:157` 有补充覆盖，但两者关注点不同。
- 建议：不阻塞 PR，可下一次优化时合并两个测试的断言形式。

---

All checks passed. No critical issues. 2 warning(s) to consider. Ready for PR (with noted improvements).
