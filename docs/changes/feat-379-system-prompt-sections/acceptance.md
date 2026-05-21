# feat-379: System Prompt 段式体系构建 — 验收报告

## Round 1 — 2026-05-22

**Reviewer**: reviewer-r1 (change-reviewer skill, Sonnet 4.6)
**Branch**: `unit/feat-379` (HEAD 0615c9eb)
**Verdict**: `fail`
**Highest Required Action**: `fix-implementation`
**Issues Count**: blocking: 2, major: 0, minor: 2
**GH Issues Filed**: none (all in-unit)
**Needs Re-Review**: true

---

## 澄清记录

无澄清问题，按当前理解直接走旅程。

---

## 服务启动记录

- IM: `http://127.0.0.1:65434` (ephemeral, JWT secret: `feat-379-reviewer-r1`)
- Gateway: worktree 本地 config `$WT_ROOT/.gateway-config.yaml`，node_id=`wt-unit-feat-379-reviewer`
- 前端：已在 worktree 重建 (`npm run build`，bundle `index-sdNcRXC1.js` 535kB)
- 产物指纹核验：`memory_curation` x2 / `skill_creation` x2 / `custom_prompt` x13 / `Preview full` x1 — 通过

---

## User Journeys Exercised

| # | 旅程 | 路径 |
|---|---|---|
| J1 | 进入 Settings → Agents，查看 agent 配置页 Behavior card | 主路径 |
| J2 | 填写 Custom Instructions，点击 Save | 主路径 |
| J3 | 展开 "Preview full system prompt"，验证内容更新 | 主路径 |
| J4 | 点击 "+ New" 进入新建 agent 页面，检查默认值 | 主路径 |
| J5 | 通过 API 验证 features/custom_prompt 持久化 | 持久化路径 |
| J6 | 通过 prompt-preview API 验证段式内容（M4 CC 对齐段） | 内核验证 |

---

## 验收标准覆盖表

| # | 验收标准（spec.md） | 期望来源 | 验证方式 | 证据 | 结果 |
|---|---|---|---|---|---|
| AC1 | IM agent 配置里，每个"用户可勾"特性都有开关，新建 agent 时按各特性预置的默认值呈现 | spec.md §验收标准#1 | 浏览器打开 agent-detail 和 agent-create 页面 | **detail 页**: `ACCEPTANCE/feat-379-r1/r1-04-agent-detail.png` — Memory Curation + Skill Creation 开关存在，disabled 态（无依赖工具）；**create 页**: `ACCEPTANCE/feat-379-r1/r1-16-new-agent.png` — 仍显示旧整串 System Prompt textarea，无特性开关 | **fail** |
| AC2 | 切换某可勾特性并保存后，重启 IM / Gateway，该 agent 的开关状态保持不变 | spec.md §验收标准#2 | PATCH `/im/v1/agents/{id}/config` + 重读 `/config` | PATCH 返回 200 但响应不含 `features`；GET `/config` 不含 `features` 字段；gateway config.yaml 未写入 `features` | **fail** |
| AC3 | 关闭某能力性特性（如 memory/skills 自进化）后，对话中不再表现该特性引导的行为；重新开启后恢复 | spec.md §验收标准#3 | 因 AC2 fail（不持久化），此条无法在重启场景验证；preview-API 测试：`memory_curation=false` vs `true` section_count 均=18，内容无差异（features 未传入组装器） | **fail** |
| AC4 | 给某 agent 填写自定义补充文本并保存，该 agent 表现出该文本描述的人设，其它 agent 不受影响 | spec.md §验收标准#4 | 前端 Custom Instructions 填写后 prompt-preview 实时更新包含 `# Custom Agent Instructions`+内容 (`ACCEPTANCE/feat-379-r1/r1-15-preview-bottom.png`)；但 PATCH 保存后 GET `/config` 不含 `custom_prompt`，持久化失败 | **fail** |
| AC5 | 进入群聊的 agent 始终遵循群聊回复策略，heartbeat agent 始终按 heartbeat 运行，无法通过 agent 配置关闭 | spec.md §验收标准#5 | Group Reply Policy 在配置页以 select（非 toggle）形式存在，说明文字"always active, not a toggle"；`pa.communication_context` 段为 `cache_safe=False order=900` 场景必加；`pa.heartbeat` 段固定存在 | **pass** |
| AC6 | coding CLI 的 agent 行为与重构前一致，无可观察变化 | spec.md §验收标准#6 | golden 测试 13/13 通过（`tests/integration/test_prompt_sections_golden.py`）；LC 产品段（lc.identity/lc.guidelines/lc.tools_footer）存在；unit + integration 551 passed | **pass** |
| AC7 | agent 在不可逆/影响他人的操作前会先与用户确认（对齐 CC「谨慎执行操作」规范） | spec.md §验收标准#7 | prompt-preview 中 `core.actions_care` 段内容含：reversibility/blast radius 框架、confirm before risky、`--no-verify` 明确禁止 | **pass** |
| AC8 | agent 引用代码用 `file_path:line_number`，引用 issue/PR 用 `owner/repo#123`，非用户要求不滥用 emoji | spec.md §验收标准#8 | prompt-preview 中 `core.tone_style` 段含：`file_path:line_number`、`owner/repo#123`、emoji only on request、no colon before tool calls | **pass** |
| AC9 | agent 配置页有可展开的只读「完整系统提示词预览」，切换特性开关或改自定义文本后预览随之更新 | spec.md §验收标准#9 + design.md §前端Behavior card | 折叠按钮存在（`▸ Preview full system prompt`），点击展开显示完整段式 prompt；填入 custom_prompt 后 preview 立即包含 `# Custom Agent Instructions` 和内容（`ACCEPTANCE/feat-379-r1/r1-15-preview-bottom.png`）；预览底部注明"Group chat and memory runtime segments are excluded from this preview." | **pass** |

---

## Issues

### ISSUE-1 — agent-create 页面未重构：新建 agent 无特性开关，仍显示旧整串 System Prompt textarea

**Severity**: blocking
**Recommended Action**: fix-implementation
**Action Rationale**: AC1 的一半失败：`agent-create-page.tsx` 未同步迁移到新 Behavior card（Custom Instructions + Features 开关）。

**证据**:
- `ACCEPTANCE/feat-379-r1/r1-16-new-agent.png`：新建 agent 页面显示 "System Prompt *" 整串 textarea，有预填默认串，**无 Memory Curation / Skill Creation 开关**。
- design.md M3 范围明确包含 `agent-create-page.tsx`："重构为「特性开关组 + 自定义补充 + 折叠预览(必做)」"。
- 对比 `agent-detail-page.tsx`（已重构，`ACCEPTANCE/feat-379-r1/r1-04-agent-detail.png`）可知 detail 已完成，create 漏实现。

**期望**: 新建 agent 时 Behavior card 应与 detail 页一致——Custom Instructions textarea（空）+ Features 开关组（按 `capabilities.features[*].default_on` 渲染默认值）+ Group Reply Policy select + Preview。

---

### ISSUE-2 — features 和 custom_prompt 未在 IM DB 持久化：保存后重读/重启丢失

**Severity**: blocking
**Recommended Action**: fix-implementation
**Action Rationale**: AC2/AC3/AC4 的持久化路径全部失败。IM `PATCH /im/v1/agents/{id}/config` 返回 200 但响应中没有 `features` / `custom_prompt` 字段；`GET /config` 也不含这两个字段；gateway config.yaml 未写入。

**证据**:
- PATCH 请求 body `{"features":{"memory_curation":false}, "custom_prompt":"你是我的私人法律顾问..."}` → 响应 body 无这两字段，re-read GET 无这两字段。
- IM log 确认 PATCH 200 OK，但字段被 IM schema 忽略。
- gateway config.yaml 内容仅含 `node_id`/`agents[]`/`channels`/`im_service`，无 `features`/`custom_prompt`。

**期望**:
1. IM DB + `/config` 路由应支持读写 `features: dict[str,bool]` 和 `custom_prompt: str`；
2. Gateway 收到 IM 的 agent-update 通知后应将 `features` + `custom_prompt` 写回 config.yaml；
3. 保存后 re-read `/config` 必须能读回这两个字段。

---

### ISSUE-3 — features 门控未接通组装器：memory_curation on/off 时 preview 内容相同

**Severity**: major
**Recommended Action**: fix-implementation
**Action Rationale**: 即使通过 prompt-preview API 直传 `features: {"memory_curation": true/false}`，section_count 均为 18 且 prompt 内容无差异（memory guidance 段本应随 flag 进出）。

**证据**:
- `preview_mem_true.json` (memory_curation=true): section_count=18，无独立 memory guidance 段加入。
- `preview_mem_false.json` (memory_curation=false): section_count=18，内容与 true 相同。
- 分析：`reviewer-test-agent` 没有 `memory` 工具（tool_allowlist 无 memory），`requires_tool` 门控可能让两者都不出现；但即使如此，有工具时的开关路径应仍被验证。需要带 memory 工具的 agent 测试 on/off 差异。
- 无法完成此路径的真实对话验证（测试环境无 LLM），且持久化本身失败阻碍了保存-重启-验证链路。

**注**: 这个 issue 可能被 ISSUE-2 连带遮蔽（features 不持久化 → 无法真实测 on/off 行为差异）。worker 修复 ISSUE-2 后一并验证此条。

---

### ISSUE-4 — capabilities API `default_system_prompt` 仍为旧格式串（含 `<RUNTIME_FILL:*>` 占位符）

**Severity**: minor
**Recommended Action**: fix-implementation
**Action Rationale**: `GET /im/v1/agents/{id}/capabilities` 返回的 `default_system_prompt` 字段仍是旧 f-string 格式（带 4 个 `<RUNTIME_FILL:*>` 标记），未更新为段式组装结果。虽然此字段不在新 Behavior card 的关键路径上（prompt-preview 接口已独立），但若有消费方依赖此字段会取到旧格式串。

---

## 通过的旅程小结

- **Behavior card 结构**（detail 页）：Custom Instructions textarea + Features 开关组（两个 disabled 态 checkbox）+ Group Reply Policy select（含"always active, not a toggle"说明）+ Preview 折叠按钮 — 全部到位。截图：`r1-04-agent-detail.png`、`r1-08-preview-visible.png`。
- **Preview 折叠/展开**：`▸/▾` 按钮正确，展开后显示完整段式 prompt，底部注明群聊/记忆段排除。截图：`r1-09-preview-expanded.png`、`r1-15-preview-bottom.png`。
- **Preview 实时更新**：填写 custom_prompt 后 preview 立即包含 `# Custom Agent Instructions` + 内容（browser 内存状态，非持久化）。
- **M4 CC 对齐段全部到位**：`core.actions_care`（reversibility/--no-verify/confirm）、`core.tone_style`（file_path:line_number / owner/repo#123 / emoji policy / no colon）、`core.system`（system-reminder / prompt injection / auto-compress）、`core.tool_rules`（专用工具优先 / 并行调用）— 全部在 prompt-preview 中确认。
- **群聊场景必加段**：`pa.communication_context` 为 `order=900 cache_safe=False`，`pa.heartbeat` 固定存在；Group Reply Policy 说明明确"not a toggle"。
- **coding CLI 回归**：golden 测试 13/13，unit + integration 551 passed。

---

## Side Findings

- `tests/contract/test_core_types_contract.py::test_message_contract_fields_are_stable` 失败（`Message` 新增了 `reasoning_content` 等字段，contract 测试未更新）。此失败与本 unit 无关，属 out-of-unit minor，不立 issue。

---

## 上层文档同步检查

| 文档 | 检查结果 |
|---|---|
| `SPEC.md` | 无需更新（段式体系是内部实现改动，四包架构/依赖方向不变） |
| `docs/内核设计SPEC.md` | 建议后续补充 PromptSection/PromptContext/assemble_system_prompt 的接口描述，但不阻塞本次验收 |
| `AGENTS.md` / `CLAUDE.md` | 无需更新 |
| `docs/CodingCLI-SPEC.md` | 无需更新（coding CLI 行为不变） |
| `docs/NodeGateway-SPEC.md` | 建议后续补充 features/custom_prompt 字段的 Gateway 写回说明，待 ISSUE-2 修复后一并更新 |
| `docs/IM-SPEC.md` | 建议后续补充 `/config` 路由的 features/custom_prompt 字段说明 |

---

## Recommended Action Summary

修复两个 blocking issue 后再派 re-review：

1. **ISSUE-1**: 按 design.md M3 的 Behavior card 设计，重构 `agent-create-page.tsx` — Custom Instructions + Features 开关组（从 `capabilities.features` 取默认值）+ Preview。
2. **ISSUE-2**: IM DB + `/config` PATCH/GET 路由支持 `features`/`custom_prompt` 字段；Gateway 收 agent-update 后将这两个字段写回 config.yaml 对应 agent 条目。修复后一并验证 ISSUE-3（features 门控是否真正影响 prompt 组装）。
