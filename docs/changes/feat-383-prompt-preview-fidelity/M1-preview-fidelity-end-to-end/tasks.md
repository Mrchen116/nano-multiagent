# feat-383-M1: preview-fidelity-end-to-end — Tasks

> 对齐: ../design.md v1

## 目标

预览链路端到端返回真实工具描述 / 真实 skill 条目 / 真实 workspace 路径，运行时 volatile 字段（时间）用明确占位符呈现；agent-create 页补传 `agent_id_hint` 和 `skill_ids`，IM 端 derive workspace_root 后透传给 gateway。

## 退出标准

- [ ] `pytest tests/unit/test_global_routes_prompt_preview.py tests/contract/test_prompt_preview_runtime_parity.py tests/integration/test_prompt_sections_golden.py` 全绿
- [ ] `pytest -m "not e2e"` 全绿（无回归）
- [ ] `(cd src/IM/frontend && npm run test)` 全绿
- [ ] Contract test 断言：preview HTTP 输出中占位符替换后与 runtime `build_system_prompt` 同 ctx 逐字相等
- [ ] IM 单测覆盖 `agent_id_hint → managed_workspace_root` derive 路径
- [ ] 前端单测覆盖 `draft.skills` 透传到 `promptPreview` / `nodePromptPreview` 调用 payload
- [ ] 浏览器验收：agent-detail 和 agent-create 两个入口的工具/skill/cwd/时间四类字段所见即所得

## 测试策略

- 被测行为：
  1. `/v1/prompt-preview` 用 ToolRegistry 取真实工具描述，静默跳过未注册工具
  2. `/v1/prompt-preview` 用 `resolve_available_skills` 解析真实 skills
  3. `current_datetime` 恒填占位符 `<运行时注入：当前时间>`
  4. `cwd` 填真实 workspace_root，为空时填占位符 `<运行时注入：workspace 路径>`
  5. `kernel_api_client.prompt_preview()` 透传 `workspace_root` + `skill_ids`
  6. Gateway `request_node_prompt_preview` 支持 `workspace_root` + `skill_ids`
  7. IM `/im/v1/agents/{id}/prompt-preview` 透传 `skill_ids`
  8. IM `/im/v1/nodes/{id}/prompt-preview` 透传 `skill_ids`，用 `agent_id_hint` derive `workspace_root`
  9. 前端 `promptPreview` / `nodePromptPreview` 传 `skill_ids` / `agent_id_hint`
  10. preview HTTP 端输出占位符替换后 ≡ runtime `build_system_prompt`

- 已有测试在：
  - `tests/unit/test_prompt_preview_endpoint.py`（扩展：新增 workspace_root/skill_ids/datetime/cwd 相关用例）
  - `tests/contract/test_prompt_preview_runtime_parity.py`（新建，硬要求）
  - `tests/im_service/unit/test_nodes_prompt_preview.py`（新建，IM derive 路径）
  - `src/IM/frontend/src/features/settings/agents/__tests__/`（扩展或新建前端单测）

- 落层/目录/marker：
  - `tests/unit/` — 后端单元测试，无 marker
  - `tests/contract/` — 契约测试，无 marker
  - `tests/integration/` — 集成测试（golden test 已存在）

- 可选依赖 importorskip：无

- 一次性验收证据：浏览器截图（agent-detail + agent-create 两入口），收尾记入 progress.md

## 用户路径分类

- `normal-ui`：Tool/skill/cwd/time 四类字段真实呈现 — 必须真实浏览器验收，截图记录

## UI 状态矩阵

| 状态 | 覆盖计划 |
|---|---|
| default | 已有 tool 勾选 → 预览展示真实描述 |
| loading | 600ms debounce 期间显示 loading（既有行为，不变） |
| empty | 无 tool 勾选 → Available Tools 段为空；无 Agent ID → cwd 显示占位 |
| error | N/A（不改错误路径） |
| disabled | N/A |
| submitting | N/A |
| permission denied | N/A |
| long content | 工具描述完整展示不截断（浏览器验证） |
| missing/nullable data | agent-create 未填 Agent ID → cwd 占位符 |
| mobile viewport | N/A（不改布局） |
| desktop viewport | 浏览器主要在 desktop 验收 |
| dark mode | N/A（不改样式） |

## 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| 工具描述真实显示（非空） | 单测 + 浏览器截图 | 是（单测） |
| datetime 占位符 | 单测 + 浏览器截图 | 是（单测） |
| cwd 真实路径 / 占位符 | 单测 + 浏览器截图 | 是（单测） |
| skill 真实描述 | 单测 + 浏览器 | 是（单测） |
| preview ≡ runtime（替换占位后） | contract test | 是 |
| IM node derive workspace_root | IM 单测 | 是 |
| 前端 skill_ids/agent_id_hint 透传 | 前端单测 | 是 |

## Roadpoints

### R1 — kernel `/v1/prompt-preview` 真实化（工具描述+skill+datetime/cwd 占位）

- 状态: DONE
- 步骤: 扩展 `PromptPreviewRequest`（加 `workspace_root`/`skill_ids`），在处理函数注入 `ToolRegistry`，用 `registry.get(tid)` 取真实工具，用 `resolve_available_skills` 解析 skills，datetime/cwd 占位
- 验证: 扩展 `tests/unit/test_prompt_preview_endpoint.py`，新增 contract test `tests/contract/test_prompt_preview_runtime_parity.py`

### R2 — kernel_api_client + Gateway WS 透传 workspace_root/skill_ids

- 状态: DONE
- 步骤: 扩展 `kernel_api_client.prompt_preview()` 签名，扩展 Gateway `request_node_prompt_preview` payload，`im_connection.py` 读取 `skill_ids`/`workspace_root`
- 验证: 现有 `test_personal_assistant_kernel_client_contract.py` 相关部分 + 新单测

### R3 — IM HTTP 路由透传 skill_ids + node 端 derive workspace_root

- 状态: DONE
- 步骤: 扩展 `PromptPreviewRequest`（agents.py） + 扩展 `NodePromptPreviewRequest`（nodes.py）加 `agent_id_hint`，服务端 derive workspace_root
- 验证: 新建 IM 单测

### R4 — 前端 API 客户端 + 调用点补字段

- 状态: DONE
- 步骤: 扩展 `promptPreview`/`nodePromptPreview` 签名，`agent-detail-page.tsx` 加 `skill_ids`，`agent-create-page.tsx` 加 `skill_ids`/`agent_id_hint`
- 验证: 前端单测 + 浏览器验收截图
