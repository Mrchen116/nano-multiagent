# Verification Report: feat-383

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 7/7 tasks complete，spec 5 requirement 全部有实现 |
| Correctness | 13/13 scenario 有实现，11/13 有测试覆盖，2 scenario 测试弱覆盖 |
| Coherence | 6/6 design 关键决策遵守 |

No critical issues. 2 warning(s) to consider. Ready for PR (with noted improvements).

## Completeness

### Task 完成情况

Tasks: 7/7 complete（tasks.md 退出标准全部勾选 `[x]`）

### Spec Requirement 覆盖

- R1（预览忠实反映 UI 配置）：有实现 — `global_routes.py:322-355`、前端 `agent-detail-page.tsx:137-141`、`agent-create-page.tsx:126-131`
- R2（工具列表显示真实描述，不截断）：有实现 — `global_routes.py:322-326`（ToolRegistry 注入）
- R3（工作目录显示真实路径或占位）：有实现 — `global_routes.py:344`、`nodes.py:178`
- R4（运行时字段用占位符）：有实现 — `global_routes.py:341`（恒填 `<运行时注入：当前时间>`）
- R5（Skills 段反映勾选集合）：有实现 — `global_routes.py:331-336`（`resolve_available_skills`）

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| R1-S1: 用户切换 Tool Allowlist 勾选 | `global_routes.py:322-326`；前端 `agent-detail-page.tsx:139` | 单测 `test_prompt_preview_endpoint.py:326`；前端 `agent-detail-page.test.tsx:650` | covered |
| R1-S2: 用户切换 Skill 勾选 | `global_routes.py:331-336`；前端 `agent-detail-page.tsx:141` | 前端 `agent-detail-page.test.tsx:650`（仅验证字段存在）；无端到端 skill 解析单测 | **弱覆盖** |
| R1-S3: 用户修改 Custom Instructions | `global_routes.py:258`（custom_prompt 透传）；前端 `agent-detail-page.tsx:138` | 单测 `test_prompt_preview_endpoint.py:99` | covered |
| R2-S1: 已勾选工具显示真实说明文本 | `global_routes.py:324`（`registry.get(tid)`） | 单测 `test_prompt_preview_endpoint.py:326-358` | covered |
| R2-S2: 用户未勾选任何工具 | `global_routes.py:322-326`（空 tool_ids → 空 available_tools） | 单测（通过 `test_prompt_preview_no_sections_returns_empty` 间接） | covered |
| R2-S3: 配置中存在未注册工具 id | `global_routes.py:324-326`（`None` 静默跳过） | 单测 `test_prompt_preview_endpoint.py:360-388` | covered |
| R3-S1: 已存在 agent 预览显示真实路径 | `agents.py:439`（`workspace_root_for_profile`）；`global_routes.py:344` | IM 契约测试 `test_agent_config_contract.py:410-471`（skill_ids 覆盖；workspace_root 已有）；单测 `test_prompt_preview_endpoint.py:273-299` | covered |
| R3-S2: agent-create 已填 Agent ID | `nodes.py:178`（`managed_workspace_root(agent_id_hint)`）；前端 `agent-create-page.tsx:131` | IM 契约测试 `test_agent_config_contract.py:475-528` | covered |
| R3-S3: agent-create 未填 Agent ID | `nodes.py:178`（`if payload.agent_id_hint else ""`）；`global_routes.py:344` | IM 契约测试 `test_agent_config_contract.py:535-581` | covered |
| R4-S1: 时间字段显示占位符 | `global_routes.py:341`（`"<运行时注入：当前时间>"`） | 单测 `test_prompt_preview_endpoint.py:249-271` | covered |
| R5-S1: 勾选了若干技能 | `global_routes.py:331-336`（`resolve_available_skills`） | 无专项测试（见 WARNING-1） | **弱覆盖** |
| R5-S2: 未勾选任何技能 | `global_routes.py:331-336`（`include_names=[]` → 空集合）；`test_prompt_preview_accepts_workspace_root_and_skill_ids` 只验证 HTTP 200 | 单测 `test_prompt_preview_endpoint.py:231`（仅验证字段接受） | covered（间接） |
| R5-S3: workspace 下解析不到的 skill id | `global_routes.py:331-336`（`resolve_available_skills` 内部静默跳过） | 无专项测试（见 WARNING-1） | **弱覆盖** |

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 决策 1: workspace_root 由 IM 服务端 derive | 是 | `nodes.py:178`（`managed_workspace_root(agent_id_hint)`）；前端不拼路径（`agent-create-page.tsx:43,82` workspace_root=null） |
| 决策 2: skill_ids 由前端传，kernel 端解析 | 是 | 全链路：`agent-create-page.tsx:130` → `nodes.py:186` → `gateway_handler.py:451` → `im_connection.py:427-428` → `global_routes.py:331-336` |
| 决策 3: ToolRegistry 注入 + 静默跳过 | 是 | `global_routes.py:297`（`Depends(get_tool_registry)`）；`global_routes.py:324-326`（filter None） |
| 决策 4: datetime 占位，cwd 占位仅在 workspace 不可知时 | 是 | `global_routes.py:341`（恒占位）；`global_routes.py:344`（workspace_root or 占位） |
| 决策 5: 两层防线（golden test + contract test） | 是 | 既有 `tests/integration/test_prompt_sections_golden.py`；新增 `tests/contract/test_prompt_preview_runtime_parity.py`（验证占位符替换后逐字相等） |
| 决策 6: 静默跳过逻辑在 preview 端，不污染 core 渲染 | 是 | `core_sections.py` 无改动（git diff 空）；过滤逻辑仅在 `global_routes.py:324-326` |

## Issues

### CRITICAL（提 PR 前必须修）

无

### WARNING（应该修）

- **WARNING-1**: Spec R5 有 3 个 Scenario（已勾技能 / 未勾 / 解析失败静默跳过），但 `test_prompt_preview_endpoint.py` 中无一专项测试覆盖「skill_ids → resolve_available_skills → ctx.available_skills」路径；`test_prompt_preview_accepts_workspace_root_and_skill_ids`（`:231`）仅验证 HTTP 200，不检查 ctx.available_skills 内容。若 `resolve_available_skills` 调用方式出错（如参数顺序），单测无法发现。
  - 建议：在 `tests/unit/test_prompt_preview_endpoint.py` 补 2 个测试：(a) 提供真实 workspace + skill 文件，验证 `available_skills` 中出现对应 skill 条目；(b) skill_ids 中含 workspace 下不存在的 id，验证对应 id 不出现在 ctx.available_skills（镜像工具静默跳过逻辑）。可用 `tmp_path` + 写入假 skill YAML 文件来构造测试用例。

- **WARNING-2**: 前端测试 `agent-create.test.tsx` 的 `describe("agent create page — preview fidelity")`（`:308-364`）仅验证 `skill_ids` 字段存在，未验证 `agent_id_hint` 的传递行为。tasks.md 退出标准（`:16`）要求「前端单测覆盖 `draft.skills` 透传到 `promptPreview` / `nodePromptPreview` 调用 payload」——`agent_id_hint` 的透传是 agent-create 场景的关键字段（驱动 IM 端 derive workspace），但无测试断言。
  - 建议：在 `agent-create.test.tsx` 的 preview fidelity describe 块中补一个 test case：在表单填入 Agent ID 字段后触发预览，断言 `nodePromptPreviewMock` 收到的调用包含 `agent_id_hint` 且值等于填入的 Agent ID。

### SUGGESTION（可以修）

- **SUGGESTION-1**: tasks.md（`:37`）原计划新建 `tests/im_service/unit/test_nodes_prompt_preview.py`，实际 IM node derive 路径的测试落在了 `tests/im_service/contract/test_agent_config_contract.py`（`:475-581`）。测试内容覆盖充分，仅文件落层与计划不符。可将 node prompt preview 相关 test 函数提取到独立文件，使测试分布更清晰，但不影响当前覆盖质量。
