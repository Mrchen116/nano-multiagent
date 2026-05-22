# feat-379-M9: fix-feature-tool-coupling — progress

<!-- 每个 roadpoint 完成后补齐 -->

## R1 — 修 _build_tool_names（決策 13）

**状态**: DONE

**根因**: `_build_tool_names()` 以 `build_tool_registry(runtime=None, hook_runner=None)` 建 registry，
memory/skill_manage 需 bootstrap 路径注入才进 `list_specs()` 返回集合，导致即使它们在
`default_tool_ids` 中也被过滤掉。

**修复**: 直接取 `PERSONAL_ASSISTANT_PROFILE.default_tool_ids + optional_tool_ids`，
advertise 阶段只需工具名，无需实例化 registry。

**提交**:
- C1 `d060b912` — Red 测试（`test_build_tool_names_includes_memory_and_skill_manage` + `test_build_tool_names_contains_all_feature_registry_requires_tool`）
- C2 `5fe92641` — Green 实现（删 `build_tool_registry` 调用，直取 profile 工具名）
