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

## R2 — node 级预览链路（決策 11）

**状态**: DONE

**根因**: IM 只有 `POST /im/v1/agents/{agent_id}/prompt-preview`，create 页用 `__preview__` 哨兵 → 404。

**修复**:
- `GatewayHandler`: 新增 `_node_prompt_preview_waiters` + `request_node_prompt_preview` + `_handle_node_prompt_preview`，处理 `node.prompt.preview` 消息类型
- `IM nodes.py`: 新增 `POST /im/v1/nodes/{node_id}/prompt-preview`，走 `request_node_prompt_preview`
- `PA im_connection.py`: 新增 `node.prompt.preview.request` 处理，复用 `prompt_preview_provider`（agent_id/workspace_root 传空串，provider 忽略）

**提交**: `05e852ed` — 3 files, 138 insertions

## R3 — 前端联动 + 删 effectiveToolIds + 移除 disabled（決策 12/14）

**状态**: DONE

**修复**:
- `im-agent-config-api.ts`: 新增 `nodePromptPreview(nodeId, body)` → `POST /im/v1/nodes/{nodeId}/prompt-preview`
- `agent-create-page.tsx`: 删 `effectiveToolIds`，改用 `nodePromptPreview`，移除 `disabled` 逻辑，新增联动（勾特性→加工具，移工具→取消特性）
- `agent-detail-page.tsx`: 删 `effectiveToolIds`，preview 直取 `draft.tool_allowlist`，移除 `disabled` 逻辑，新增联动
- 测试更新：M3-R1 改为验证 disabled=false；M8 测试改为 M9 行为（tool_ids 来自 allowlist）

**提交**: `c555d890` — 4 files, 93 insertions / 91 deletions
