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

## Evidence — 真实浏览器验证（2026-05-22）

服务环境：Playwright headless Chromium；IM port 54238、Vite port 54239；Gateway node `wt-m9-verify`（ephemeral worktree 隔离实例）。

### 场景 a — 新建页 preview 加载，无 404

- 路由：`/settings/agents/new`
- 操作：展开「Preview full system prompt」
- 结果：按钮变为 `[expanded]`，preview 区显示完整 system prompt（含 `# Nano Personal Assistant`、`## Runtime`、`# System` 等各段），无报错
- 截图：`ACCEPTANCE/feat-379-M9/create-page-preview-expanded.png`
- Network：`POST /im/v1/nodes/wt-m9-verify/prompt-preview` → 200 OK

**请求体（request #88）**：
```json
{"features":{"memory_curation":true,"skill_creation":true},"custom_prompt":"","tool_ids":[],"scenario":"direct"}
```

### 场景 b — 勾「记忆自进化」→ memory 工具即时变绿

- 操作：在 create 页勾 Memory Curation checkbox（已默认 checked，先 uncheck 再 check）
- 结果：重新勾选后，Tool Allowlist 中 `memory` 按钮状态变为 `[pressed]`（绿色），即时生效
- 截图：`ACCEPTANCE/feat-379-M9/create-memory-checked-allowlist-green.png`
- Network：`POST /im/v1/nodes/wt-m9-verify/prompt-preview` → 200 OK

**请求体（request #91，勾选后触发）**：
```json
{"features":{"memory_curation":true,"skill_creation":true},"custom_prompt":"","tool_ids":["memory"],"scenario":"direct"}
```
`tool_ids` 包含 `"memory"`，确认联动正确。

### 场景 c — 从 allowlist 移除 memory → 「记忆自进化」即时取消勾选；取消特性 → 工具保留

**移除工具方向**：点击 Tool Allowlist 中 `memory` 按钮（取消 pressed）→ Memory Curation checkbox 即时失去 `[checked]` 状态

**取消特性方向**：重新把 memory 加入 allowlist，再 uncheck Memory Curation → `memory` 按钮仍为 `[pressed]`（工具保留，決策 14 单向删除规则）

- 截图：`ACCEPTANCE/feat-379-M9/create-memory-removed-feature-unchecked.png`

### 场景 d — 所有 feature checkbox 无 disabled/灰态

- 快照中 Memory Curation 和 Skill Creation 两个 checkbox 均无 `[disabled]` 标注，`cursor=pointer` 可点击
- 截图：`ACCEPTANCE/feat-379-M9/create-page-initial.png`

### 场景 e — agent detail 页 preview 表现一致

- 路由：`/settings/agents/test-m9-agent`（allowlist 含 read/write/edit/bash/memory/skill_manage）
- 操作：展开「Preview full system prompt」
- 结果：`[expanded]` + 完整 system prompt，`## Available Tools` 段包含 memory 和 skill_manage
- 截图：`ACCEPTANCE/feat-379-M9/detail-page-preview-expanded.png`
- Network：`POST /im/v1/agents/test-m9-agent/prompt-preview` → 200 OK

**请求体（request #91）**：
```json
{"features":{},"custom_prompt":"","tool_ids":["read","write","edit","bash","memory","skill_manage"],"scenario":"direct"}
```

### 汇总

| 场景 | 结论 |
|---|---|
| a. 新建页 preview 加载 | PASS — 200 OK，无 404 |
| b. 勾特性 → memory 即时变绿 | PASS — `[pressed]`，request body 含 memory |
| c. 移工具 → 特性取消；取消特性 → 工具保留 | PASS — 双向联动均正确 |
| d. 无 disabled 灰态 | PASS — 所有 checkbox 无 `[disabled]` |
| e. detail 页 preview 一致 | PASS — 200 OK，工具列表匹配 allowlist |
