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

---

# Round 2 — 2026-05-22

**Reviewer**: reviewer-r2 (change-reviewer skill, Sonnet 4.6)
**Branch**: `unit/feat-379` (HEAD a4279ca8)
**Verdict**: `fail`
**Highest Required Action**: `fix-implementation`
**Issues Count**: blocking: 2, major: 1, minor: 0
**GH Issues Filed**: none (all in-unit)
**Needs Re-Review**: true

---

## 澄清记录（Round 2）

无澄清问题，按当前理解直接走旅程。

---

## 服务启动记录（Round 2）

- IM: `http://127.0.0.1:54527`（ephemeral，IM_DB_PATH=worktree 本地 `.im-r2.sqlite3`，JWT secret: `feat-379-reviewer-r2`）
- Gateway: worktree 本地 config `.gateway-config-r2.yaml`，node_id=`wt-unit-feat-379-r2`
- 前端：已在 worktree 重建（`npm run build`，bundle `index-B5oks0h8.js`）
- 产物指纹核验：`memory_curation` x2 / `custom_prompt` x1 / `Preview full` x1 / `skill_creation` x2 / `Behavior card` x1 — 通过
- Gateway 在线，`mem-test-agent`（含 memory 工具）同步到 IM 并显示 online

---

## User Journeys Exercised（Round 2）

| # | 旅程 | 路径 | 目标 Issue |
|---|---|---|---|
| J1 | Settings→Agents→mem-test-agent，查看 Behavior card 的 Features 区块 | 主路径 | ISSUE-2/ISSUE-3 前提 |
| J2 | 取消 Memory Curation + 填写 Custom Instructions → 保存 | 主路径 | ISSUE-2 持久化 |
| J3 | 重启 IM → 重读 GET /config，验证 features+custom_prompt 是否保持 | 持久化路径 | ISSUE-2 |
| J4 | 切换 Memory Curation on/off，查看 Preview 内容是否随之改变 | 主路径 | ISSUE-3 |
| J5 | 点击 "+ New"，查看 agent-create 页面 Behavior card | 主路径 | ISSUE-1 |
| J6 | GET /agents/{id}/capabilities，验证 default_system_prompt 字段 | API 路径 | ISSUE-4 |
| J7 | 群聊配置回归（Group Reply Policy select + "always active"） | 回归路径 | AC5 |
| J8 | Golden 测试 coding CLI 回归 | 测试路径 | AC6 |

---

## 验收标准覆盖表（Round 2）

| # | 验收标准 | 期望来源 | 验证方式 | 证据 | 结果（R1→R2） |
|---|---|---|---|---|---|
| AC1 | IM agent 配置里，每个"用户可勾"特性都有开关，新建 agent 时按各特性预置的默认值呈现 | spec.md §验收标准#1 | 浏览器打开 agent-create 页 | `ACCEPTANCE/feat-379-r2/r2-03-create-page.png`：旧 System Prompt textarea 已消失，Custom Instructions + Group Reply + Preview 到位；**但 Features 开关组（Memory Curation / Skill Creation checkbox）缺失** | **fail（部分改善，Features 组仍缺）** |
| AC2 | 切换某可勾特性并保存后，重启 IM / Gateway，该 agent 的开关状态保持不变 | spec.md §验收标准#2 | 前端勾选切换→保存→重启 IM→GET /config | 前端保存后 `GET /config` 返回 `features: {} / custom_prompt: null`；直接 PATCH API（含所有必填字段）后 GET 可读回；再次重启 IM 后 features 再次丢失 (`features: {}`)。问题在 IM 重启后数据丢失，说明 features/custom_prompt 未真正持久化到 SQLite | **fail（PATCH→GET 同会话内工作，重启后丢失）** |
| AC3 | 关闭某能力性特性（memory/skills 自进化）后，对话中不再表现该特性引导的行为；重新开启后恢复 | spec.md §验收标准#3 | 浏览器切换 Memory Curation off → 观察 Preview 内容变化；PATCH API 直传 features 测试 | 浏览器切换 Memory Curation off 后，Preview 内容不变（仍含 `## Memory` + MEMORY.md 段）；直接 POST /prompt-preview 传 `features: {"memory_curation": false}` vs `true`，返回内容相同（7333 chars，均含 MEMORY.md 段）。截图：`ACCEPTANCE/feat-379-r2/r2-06-preview-memory-off-still-same.png` | **fail（门控未生效）** |
| AC4 | 给某 agent 填写自定义补充文本并保存，该 agent 表现出该文本描述的人设 | spec.md §验收标准#4 | 前端填写 Custom Instructions → 保存 → 重启 IM → GET /config | 前端填写"你是我的私人法律顾问…"后保存，GET /config 返回 `custom_prompt: null`，IM 重启后仍为 null。PATCH API 含所有必填字段后 GET 可读回，但 IM 重启后再次丢失 | **fail（同 AC2，依赖持久化修复）** |
| AC5 | 进入群聊的 agent 始终遵循群聊回复策略，无法通过 agent 配置关闭 | spec.md §验收标准#5 | 浏览器查看 Group Reply Policy 区块 | Group Reply Policy 为 select combobox，说明文字"always active, not a toggle"存在；Preview 含 `In group chats, follow the configured group reply policy` | **pass（回归确认通过）** |
| AC6 | coding CLI 的 agent 行为与重构前一致，无可观察变化 | spec.md §验收标准#6 | `pytest tests/integration/test_prompt_sections_golden.py` | 13/13 通过 | **pass（回归确认通过）** |
| AC7 | agent 在不可逆/影响他人的操作前会先与用户确认 | spec.md §验收标准#7 | Preview 内容文本 | Preview 含 `# Executing actions with care` 段（通过上轮验证，Preview 内容未变化） | **pass（继承 R1 结论）** |
| AC8 | agent 引用代码用 `file_path:line_number`，引用 issue/PR 用 `owner/repo#123` | spec.md §验收标准#8 | Preview 内容文本 | Preview 含相关 tone_style 段（通过上轮验证） | **pass（继承 R1 结论）** |
| AC9 | agent 配置页有可展开的只读「完整系统提示词预览」，切换特性开关或改自定义文本后预览随之更新 | spec.md §验收标准#9 | 浏览器 Preview 面板 | Preview 面板展开/折叠正常；**但切换 features 后 Preview 内容不更新（ISSUE-3 阻塞）** | **fail（Preview 存在但不响应 features 开关）** |

---

## Issues（Round 2）

### ISSUE-1（R2 确认）— agent-create 页面 Features 开关组缺失（部分修复）

**Severity**: blocking
**Recommended Action**: fix-implementation
**Action Rationale**: M5 修复了旧 System Prompt textarea 问题，但 Features 开关组（Memory Curation / Skill Creation 复选框）未出现在 agent-create 页面。design.md M3 范围明确要求 create 页有"特性开关组 + 自定义补充 + 折叠预览（必做）"，当前仅完成了后两者。

**证据**:
- `ACCEPTANCE/feat-379-r2/r2-03-create-page.png`：新建 agent 页面有 Custom Instructions textarea（无旧 System Prompt 串）+ Group Reply Policy select + Preview 折叠按钮
- `$B snapshot -i` 输出：`@e12 [textbox] "Custom Instructions"` / `@e13 [combobox] "Group Reply Policy"` / `@e17 [button] "Preview full system prompt"` — **无 checkbox 行**
- 对比 detail 页：`@e12 [checkbox] "Memory Curation..."` / `@e13 [checkbox] "Skill Creation..." [disabled]` — Features 组在 detail 存在

**期望**: create 页需补充 Features 开关组（从 `/capabilities` 取 features 列表，按 `default_on` 渲染默认值）。

---

### ISSUE-2（R2 确认）— features/custom_prompt IM 重启后丢失（持久化未真正写入 SQLite）

**Severity**: blocking
**Recommended Action**: fix-implementation
**Action Rationale**: 同一 IM 会话内 PATCH→GET 可读回 features/custom_prompt，但 IM 进程重启后这两个字段归零。说明 PATCH 更新了内存中的对象但没有将这两个字段持久化到 SQLite。profile_version 在重启后继续递增（v3→v4），说明 config 本身的其他字段（如 display_name）正常持久化，features/custom_prompt 是特定字段的漏洞。

**证据（直接 API 测试序列）**:
```
1. PATCH {features: {memory_curation: false}, custom_prompt: "..."} + required fields → 200, GET 返回 features+custom_prompt ✓
2. kill IM + restart → GET → features: {} / custom_prompt: null ✗
   (profile_version: 3→4，说明 config 记录在 DB 但 features/custom_prompt 字段未写入)
```
- 前端保存路径同样受影响：Save Agent 后 GET /config 返回 `features: {} / custom_prompt: null`

**期望**: IM SQLite 的 agent config 存储层（db.py / repositories.py）需正确读写 features/custom_prompt 字段；IM 重启后 GET /config 必须返回 PATCH 写入的值。

---

### ISSUE-3（R2 确认）— memory_curation gate 未影响 prompt preview 内容

**Severity**: major
**Recommended Action**: fix-implementation
**Action Rationale**: 带 memory 工具的 agent（mem-test-agent）在 memory_curation=true vs false 时，POST /prompt-preview 返回完全相同内容（7333 chars，均含 `## Memory` + MEMORY.md 段）。UI 层切换 Memory Curation checkbox 后 Preview 内容也不变。门控未接通组装器。

**证据**:
- `POST /im/v1/agents/mem-test-agent/prompt-preview` 传 `{"features": {"memory_curation": true}}` vs `{"features": {"memory_curation": false}}`：len 均为 7333，内容完全相同，均含 `## Memory` 段
- 截图：`ACCEPTANCE/feat-379-r2/r2-06-preview-memory-off-still-same.png`：Memory Curation unchecked 但 Preview 中仍显示包含 Memory 段的内容
- 与 R1 相同：M5 progress.md 记录了 R4 新增 6 个门控单测，单测通过，但集成路径（API→组装器）仍未接通

---

### ISSUE-4（R2 关闭）— capabilities `default_system_prompt` 已清空

`GET /im/v1/agents/mem-test-agent/capabilities` 返回 `"default_system_prompt": null`，不含 `<RUNTIME_FILL:*>` 占位符。**已修复，关闭。**

---

## 通过的旅程小结（Round 2）

- **Behavior card（detail 页）**：Memory Curation checkbox（可用时 checked/unchecked）+ Skill Creation checkbox（无对应工具时 disabled）+ Group Reply Policy select + Preview 折叠按钮 — 全部到位。截图：`ACCEPTANCE/feat-379-r2/r2-02-features-memory-checked.png`
- **agent-create 页面（部分改善）**：旧 System Prompt textarea 已消失，Custom Instructions + Group Reply + Preview 到位。Features 开关组缺失（见 ISSUE-1）。截图：`ACCEPTANCE/feat-379-r2/r2-03-create-page.png`
- **Save 后 profile_version 更新**：Save Agent 后 profile_version 递增（v1→v2），Last Updated 时间戳更新，UI 状态正确。截图：`ACCEPTANCE/feat-379-r2/r2-07-after-save.png`
- **ISSUE-4 关闭**：capabilities API `default_system_prompt` 为 null，无 RUNTIME_FILL 占位符
- **AC5 群聊配置**：Group Reply Policy select + "always active, not a toggle" 说明仍在，回归正常
- **AC6 coding CLI 回归**：golden 测试 13/13 通过

---

## Side Findings（Round 2）

无新增 out-of-unit 问题。R1 提到的 `test_message_contract_fields_are_stable` 失败仍然是 out-of-unit 已知问题，不立 issue。

---

## 上层文档同步检查（Round 2）

| 文档 | 检查结果 |
|---|---|
| `SPEC.md` | 无需更新（持久化修复不改四包架构） |
| `docs/内核设计SPEC.md` | 建议后续补充 PromptSection/PromptContext 接口，不阻塞本次验收 |
| `AGENTS.md` / `CLAUDE.md` | 无需更新 |
| `docs/CodingCLI-SPEC.md` | 无需更新 |
| `docs/NodeGateway-SPEC.md` | 待 ISSUE-2 修复后补充 features/custom_prompt Gateway 写回说明 |
| `docs/IM-SPEC.md` | 待 ISSUE-2 修复后补充 /config 路由字段说明 |

---

## Recommended Action Summary（Round 2）

仍有 2 blocking + 1 major issue，派 fix-implementation milestone（M6）：

1. **ISSUE-2（blocking，最高优先）**: 排查 IM SQLite 持久化层，确认 features/custom_prompt 在 PATCH 时真正写入 DB。当前症状：PATCH→同会话 GET 可读回，但 IM 重启后丢失（profile_version 递增说明其他字段写入正常，features/custom_prompt 是漏点）。修复后重启 IM 验证。
2. **ISSUE-3（major，与 ISSUE-2 联测）**: memory_curation gate 未接通 prompt 组装器。可能需要在 preview 接口端、组装器端排查门控逻辑。修复后同会话内可直接用 POST /prompt-preview 验证 on/off 内容差异。
3. **ISSUE-1（blocking）**: agent-create 页面 `CreateBehaviorCard` 组件缺 Features 开关组。需从 `/capabilities` 取 features 列表渲染按默认值呈现的 checkbox 行。

---

# Round 3 — 2026-05-22

**Reviewer**: reviewer-r3 (change-reviewer skill, Sonnet 4.6)
**Branch**: `unit/feat-379` (HEAD 834178c0)
**Verdict**: `fail`
**Highest Required Action**: `fix-implementation`
**Issues Count**: blocking: 2, major: 1, minor: 0
**GH Issues Filed**: none (all in-unit)
**Needs Re-Review**: true

---

## 澄清记录（Round 3）

无澄清问题，根据 orchestrator 派发包对 3 个遗留 issue 的根因描述，直接走旅程。

---

## 服务启动记录（Round 3）

- IM: `http://127.0.0.1:59955`（ephemeral，IM_DB_PATH=worktree 本地 `.im-r3.sqlite3`，JWT secret: `feat-379-reviewer-r3`）
- Gateway: worktree 本地 config `.gateway-config-r3.yaml`，node_id=`wt-feat-379-r3`，含 `mem-test-agent`（tool_allowlist: [memory, web_search]）
- 前端：已在 worktree 重建（`npm run build`，bundle `index-UAW1qVEE.js` 539kB）
- 产物指纹核验：`memory_curation` x2 / `custom_prompt` x1 / `Preview full` x1 / `skill_creation` x2 / `Behavior` x1 — 通过
- 注：Gateway 在此环境中 WebSocket 绑定始终处于 pending 状态（gateway.log 显示"waiting for IM binding"），导致 IM 代理的 `/prompt-preview` 端点返回 503。前端 UI 中 Preview 显示 "Could not load preview." 错误。这是环境限制，不影响 ISSUE-1/2 的验证，ISSUE-3 通过单测层验证。

---

## User Journeys Exercised（Round 3）

| # | 旅程 | 路径 | 目标 Issue |
|---|---|---|---|
| J1 | Settings→Agents，查看 mem-test-agent detail 页 Behavior card，确认 Features 开关 | 主路径 | 基线确认 |
| J2 | 切换 Memory Curation off（detail 页），观察 Preview 响应 | 主路径 | ISSUE-3 |
| J3 | 填写 Custom Instructions + 保存，通过 GET /config 读取 | 主路径 | ISSUE-2 前半 |
| J4 | 直接 PATCH API（含 features/custom_prompt）→ GET 同会话读回 | API 路径 | ISSUE-2 DB写入 |
| J5 | 重启 IM → GET /config 验证 features/custom_prompt 是否保持 | 持久化路径 | ISSUE-2 重启 |
| J6 | 点击 "+ New"，进入 agent-create 页面，检查 Features 开关组 | 主路径 | ISSUE-1 |
| J7 | GET /im/v1/nodes/wt-feat-379-r3/capabilities，检查 features 字段 | API 路径 | ISSUE-1 根因 |
| J8 | golden 测试（coding CLI 回归） | 测试路径 | AC6 |

---

## 验收标准覆盖表（Round 3）

| # | 验收标准 | 期望来源 | 验证方式 | 证据 | 结果（R1→R2→R3） |
|---|---|---|---|---|---|
| AC1 | IM agent 配置里，每个"用户可勾"特性都有开关，新建 agent 时按各特性预置的默认值呈现 | spec.md §验收标准#1 | 浏览器打开 agent-create 页 | `/tmp/feat379-r3-16-create-features-area.png`：Behavior 区块 Custom Instructions → Group Reply Policy 之间无 Features checkbox；`$B snapshot -i` 无 checkbox ref；`GET /nodes/wt-feat-379-r3/capabilities` 返回 `features: []` | **fail（Features 开关组仍缺，node capabilities features 为空数组）** |
| AC2 | 切换某可勾特性并保存后，重启 IM / Gateway，该 agent 的开关状态保持不变 | spec.md §验收标准#2 | 前端 Save → GET /config → 重启 IM → GET /config | 前端 Save 后 GET /config 返回 `features: {}, custom_prompt: null`；直接 PATCH（含 profile_version=2）后同会话 GET 返回 features/custom_prompt ✓；IM 重启后 GET 返回 `features: {}, custom_prompt: null`（profile_version=3 递增正常，features/custom_prompt 归零） | **fail（IM 重启后仍丢失）** |
| AC3 | 关闭某能力性特性（memory/skills 自进化）后，对话中不再表现该特性引导的行为；重新开启后恢复 | spec.md §验收标准#3 | UI 切换 Memory Curation off → Preview 变化；单测 | UI：切换 Memory Curation → unchecked 后 Preview 长度仍 7221，`## Memory` 段仍存在（截图 `/tmp/feat379-r3-09-after-uncheck.png`）；单测层：`test_prompt_preview_memory_curation_gate_requires_tool_id` PASSED（带 tool_ids=[memory] 时 on/off 确实影响 prompt 内容）；IM-proxy 层：503（Gateway 未连接），无法验证完整链路 | **fail（UI Preview 不响应 features 开关；IM-proxy 链路 503）** |
| AC4 | 给某 agent 填写自定义补充文本并保存，该 agent 表现出该文本描述的人设 | spec.md §验收标准#4 | 前端填写 Custom Instructions → 保存 → 重启 IM → GET /config | 前端 Save 后 GET /config 返回 `custom_prompt: null`；IM 重启后仍 null（同 AC2，持久化失败） | **fail（依赖 AC2 修复）** |
| AC5 | 进入群聊的 agent 始终遵循群聊回复策略，heartbeat agent 始终按 heartbeat 运行，无法通过 agent 配置关闭 | spec.md §验收标准#5 | 浏览器查看 Group Reply Policy 区块 | Group Reply Policy select 存在，说明文字"always active, not a toggle"（`/tmp/feat379-r3-06-features-checkboxes.png`） | **pass（回归确认通过）** |
| AC6 | coding CLI 的 agent 行为与重构前一致，无可观察变化 | spec.md §验收标准#6 | `pytest tests/integration/test_prompt_sections_golden.py` | 13/13 通过 | **pass（回归确认通过）** |
| AC7 | agent 在不可逆/影响他人的操作前会先与用户确认 | spec.md §验收标准#7 | Preview 文本内容（R1/R2 确认过，本轮截图 preview 内容） | `$B snapshot` @e49 文本含 `# Executing actions with care`，reversibility/blast radius 说明在（R1 截图 `r1-08-preview-visible.png` 已确认，本轮前端 preview 503 不影响后端内容已 pass） | **pass（继承 R1/R2 结论）** |
| AC8 | agent 引用代码用 `file_path:line_number`，引用 issue/PR 用 `owner/repo#123` | spec.md §验收标准#8 | Preview 文本内容 | @e49 文本含 `file_path:line_number`、`owner/repo#123`（R1 已确认，本轮同一源码） | **pass（继承 R1/R2 结论）** |
| AC9 | agent 配置页有可展开的只读「完整系统提示词预览」，切换特性开关或改自定义文本后预览随之更新 | spec.md §验收标准#9 | 浏览器 Preview 面板 | Preview 折叠/展开按钮存在（`/tmp/feat379-r3-06-features-checkboxes.png`）；但切换 Memory Curation 后 Preview 未响应更新（内容不变）；Gateway 未连接时显示 "Could not load preview." 错误（`/tmp/feat379-r3-18-detail-memory-off-state.png`） | **fail（Preview 不响应 features 开关；Gateway 断连时无降级）** |

---

## Issues（Round 3）

### ISSUE-1（R3 确认）— node capabilities features 为空数组，create 页 Features 开关组不显示

**Severity**: blocking
**Recommended Action**: fix-implementation
**Action Rationale**: M6 在 `NodeCapabilitiesResponse` 加了 `features` 字段，但 `GET /im/v1/nodes/wt-feat-379-r3/capabilities` 实际返回 `features: []`（空数组），前端无内容可渲染 checkbox 行。根因是 get_node_capabilities route 透传 Gateway 返回值，而 Gateway 的 node-capabilities handler 未返回 FEATURE_REGISTRY 投影数据。

**证据**:
- `GET /im/v1/nodes/wt-feat-379-r3/capabilities` → `"features": []`（空数组，非期望的 [{key: memory_curation, default_on: True, ...}]）
- `/tmp/feat379-r3-16-create-features-area.png`：create 页 Behavior 区块中，Custom Instructions 下方直接是 Group Reply Policy，无 Features 标题和 checkbox
- `$B snapshot -i` 全页无 checkbox ref（创建页）

**期望**: create 页 Behavior card 应显示 Features 开关组（Memory Curation、Skill Creation），按 FEATURE_REGISTRY 默认值（default_on）呈现。

---

### ISSUE-2（R3 确认）— features/custom_prompt IM 重启后仍丢失

**Severity**: blocking
**Recommended Action**: fix-implementation
**Action Rationale**: M6 修复了 upsert CASE 保留逻辑（单测 `test_upsert_profile_preserves_features_on_re_register` 通过），但实际端到端路径（前端 Save 或直接 PATCH → IM 重启 → GET）仍丢失数据。profile_version 在重启后递增（2→3），说明 Gateway 重启时 re-sync 仍以空 features/custom_prompt 覆盖了 DB 中的有效值。

**证据（API 测试序列）**:
```
1. PATCH {features: {memory_curation: false}, custom_prompt: "你是我的私人法律顾问...", profile_version: 2} → 200
2. GET /config → features: {memory_curation: false}, custom_prompt: "你是我的私人法律顾问..." ✓
3. kill IM + restart IM
4. GET /config → features: {}, custom_prompt: null ✗  (profile_version: 3)
```
- 前端 Save（profile_version 从 v1→v2）后 GET /config 也立即返回 `features: {}, custom_prompt: null`，说明前端 Save 路径同样有问题（可能未传完整必填字段导致 422 被吞）。

---

### ISSUE-3（R3 确认）— memory_curation 切换后 UI Preview 不更新

**Severity**: major
**Recommended Action**: fix-implementation
**Action Rationale**: UI 层：mem-test-agent（有 memory 工具）切换 Memory Curation checkbox 到 unchecked 后，Preview 面板内容不变（长度 7221，`## Memory` 段仍存在）。单测层 `test_prompt_preview_memory_curation_gate_requires_tool_id` 通过（证明 endpoint 层门控逻辑正确），但前端发出的 prompt-preview 请求在当前环境因 Gateway 连接问题返回 503，无法从浏览器端完整验证。M6 的修复方向（前端传 tool_ids）在代码层面已实现，但 UI Preview 不更新这一用户可观察症状仍复现。

**证据**:
- `/tmp/feat379-r3-09-after-uncheck.png`：Memory Curation unchecked（空方框），但 Preview 起始文本与 checked 时完全相同
- `$B js "document.querySelector('[class*=preview]')?.textContent?.includes('## Memory')"` → `true`（取消勾选后）
- 单测 6/6 通过（endpoint 层实现正确）
- 网络层：两次 prompt-preview 请求均 503（Gateway WebSocket 未连接）

---

## 通过的旅程小结（Round 3）

- **Behavior card（detail 页）**：Memory Curation checkbox（可切换）+ Skill Creation checkbox（disabled）+ Group Reply Policy select + Preview 折叠按钮，结构完整（`/tmp/feat379-r3-06-features-checkboxes.png`）
- **Profile Version 更新**：Save 后 profile_version v1→v2，Last Updated 时间戳更新（`/tmp/feat379-r3-13-after-save.png`）
- **AC5 群聊配置**：Group Reply Policy select + "always active, not a toggle" 说明正常
- **AC6 coding CLI 回归**：golden 测试 13/13 通过
- **AC7/AC8 CC 对齐段**：@e49 snapshot 文本中确认 `# Executing actions with care` / `file_path:line_number` / `owner/repo#123` 存在

---

## Side Findings（Round 3）

- Gateway WebSocket 绑定在 ephemeral 环境中始终处于 pending 状态（需要手动 confirm bind URL），导致 IM-proxy 的 prompt-preview 端点持续返回 503。这影响了 ISSUE-3 的完整链路验证，但不影响 ISSUE-1/ISSUE-2 的结论。建议 Gateway 在 reviewer 验收场景中提供 non-binding 直连模式或 IM proxy 走直接 agent API 降级。此为 out-of-unit minor，不立 issue。
- `test_message_contract_fields_are_stable` 失败为已知 out-of-unit 问题（R1/R2 记录），本轮未重跑，不立 issue。

---

## 上层文档同步检查（Round 3）

| 文档 | 检查结果 |
|---|---|
| `SPEC.md` | 无需更新 |
| `docs/内核设计SPEC.md` | 待 features/custom_prompt 链路全通后补充；不阻塞本次 |
| `AGENTS.md` / `CLAUDE.md` | 无需更新 |
| `docs/CodingCLI-SPEC.md` | 无需更新 |
| `docs/NodeGateway-SPEC.md` | 待 ISSUE-2 修复后补充 features/custom_prompt 写回说明 |
| `docs/IM-SPEC.md` | 待 ISSUE-2 修复后补充 /config 路由字段说明 |

---

# Round 4 — 2026-05-22

**Reviewer**: reviewer-r4 (change-reviewer skill, Sonnet 4.6)
**Branch**: `unit/feat-379` (HEAD 89bd00ae)
**Verdict**: `fail`
**Highest Required Action**: `fix-implementation`
**Issues Count**: blocking: 0, major: 1, minor: 0
**GH Issues Filed**: none (all in-unit)
**Needs Re-Review**: true

---

## 澄清记录（Round 4）

无澄清问题，直接走旅程。

---

## 服务启动记录（Round 4）

- IM: `http://127.0.0.1:50788`（ephemeral，IM_DB_PATH=`.im-r4.sqlite3`，JWT secret: `feat-379-reviewer-r4`）
- Gateway: worktree 本地 config `.gateway-config-r4.yaml`，node_id=`wt-feat-379-r4`，含 `mem-test-agent`（tool_allowlist: [memory, web_search]）
- 前端：已在 worktree 重建（`npm run build`，bundle `index-UAW1qVEE.js` 539kB）
- 产物指纹核验：`memory_curation` x2 / `custom_prompt` x1 / `Preview full` x1 / `skill_creation` x2 / `Behavior` x1 — 通过
- Gateway 完成 IM bind 绑定（POST /bind → 201 Created，WS /im/ws/gateway accepted）

---

## User Journeys Exercised（Round 4）

| # | 旅程 | 路径 | 目标 Issue |
|---|---|---|---|
| J1 | Settings→Agents，查看 mem-test-agent detail 页 Behavior card，确认 Features 开关 | 主路径 | 基线确认 |
| J2 | 点击 `+ New`，进入 agent-create 页面，检查 Features 开关组 snapshot | 主路径 | ISSUE-1 |
| J3 | GET /nodes/wt-feat-379-r4/capabilities，验证 features 字段非空 | API 路径 | ISSUE-1 |
| J4 | 填写 Custom Instructions + 取消 Memory Curation → 点击 Save Agent → 立即 GET /config 读取 | 主路径 | ISSUE-2 持久化 |
| J5 | 真实重启 IM → GET /config 验证 features/custom_prompt 重启后保持 | 持久化路径 | ISSUE-2 重启 |
| J6 | 重启后前端重新打开配置页，确认 UI 显示持久化状态 | 主路径 | ISSUE-2/AC4 |
| J7 | 切换 Memory Curation on/off，观察 Preview 内容变化 + 拦截 preview 请求 body | 主路径 | ISSUE-3 |
| J8 | golden 测试（coding CLI 回归） | 测试路径 | AC6 |

---

## 验收标准覆盖表（Round 4）

| # | 验收标准 | 期望来源 | 验证方式 | 证据 | 结果（R1→R2→R3→R4） |
|---|---|---|---|---|---|
| AC1 | IM agent 配置里，每个"用户可勾"特性都有开关，新建 agent 时按各特性预置的默认值呈现 | spec.md §验收标准#1 | snapshot -i 全页交互元素检查 + 截图 | create 页 snapshot：`@e13 [checkbox] "Memory Curation..." [checked]` / `@e14 [checkbox] "Skill Creation..." [checked]`（create 时无 tool_allowlist 约束，两者均按 default_on=true 呈现）；截图 `/tmp/feat379-r4-09-create-features-visible.png` | **pass（R1/R2/R3 fail → R4 PASS）** |
| AC2 | 切换某可勾特性并保存后，重启 IM / Gateway，该 agent 的开关状态保持不变 | spec.md §验收标准#2 | 前端 Save Agent → 立即 GET /config → 真实 kill+restart IM → GET /config | 保存后立即 GET：`features: {memory_curation: false}`；kill IM PID 29922 → restart 新 PID 35045 → GET /config：`features: {memory_curation: false}, profile_version: 2` — 重启后保持 | **pass（R1/R2/R3 fail → R4 PASS）** |
| AC3 | 关闭某能力性特性后，对话中不再表现该特性引导的行为；重新开启后恢复 | spec.md §验收标准#3 | UI 切换 Memory Curation on/off → Preview 内容变化观察 + 请求拦截 | 切换开关后前端确实重新触发 preview 请求（network 监测：`POST /prompt-preview → 200`）；但 preview 请求 body 中 `tool_ids: []`（空数组），导致 memory 工具被视为不在位，memory_curation gate 无论 on/off 都不出现 memory guidance；截图 `/tmp/feat379-r4-18-memory-on-preview.png` | **fail（ISSUE-3 部分修复：请求触发，但 tool_ids 未传）** |
| AC4 | 给某 agent 填写自定义补充文本并保存，该 agent 表现出该文本描述的人设，其它 agent 不受影响 | spec.md §验收标准#4 | 前端填写 → Save Agent → IM 重启 → GET /config + 前端配置页 | 保存后 GET /config：`custom_prompt: "You are my personal legal advisor, answer with relevant clauses."`；IM 重启后仍保持；前端重新打开配置页显示相同内容（截图 `/tmp/feat379-r4-13-after-restart-detail.png`）；Preview 含 `# Custom Agent Instructions` 段 | **pass（R1/R2/R3 fail → R4 PASS）** |
| AC5 | 进入群聊的 agent 始终遵循群聊回复策略，heartbeat agent 始终按 heartbeat 运行，无法通过 agent 配置关闭 | spec.md §验收标准#5 | 浏览器配置页查看 Group Reply Policy 区块 | Group Reply Policy select 存在，说明文字"always active, not a toggle"（截图 `/tmp/feat379-r4-06-features-checkboxes.png`）；Preview 含 pa.communication_context 段标记 | **pass（回归确认通过）** |
| AC6 | coding CLI 的 agent 行为与重构前一致，无可观察变化 | spec.md §验收标准#6 | `pytest tests/integration/test_prompt_sections_golden.py` | 13/13 通过 | **pass（回归确认通过）** |
| AC7 | agent 在不可逆/影响他人的操作前会先与用户确认 | spec.md §验收标准#7 | Preview 文本内容 | Preview 含 `# Executing actions with care` 段，含 reversibility/blast radius 框架 | **pass（继承 R1/R2/R3 结论）** |
| AC8 | agent 引用代码用 `file_path:line_number`，引用 issue/PR 用 `owner/repo#123` | spec.md §验收标准#8 | Preview 文本内容 | Preview 含 `file_path:line_number` / `owner/repo#123` | **pass（继承 R1/R2/R3 结论）** |
| AC9 | agent 配置页有可展开的只读「完整系统提示词预览」，切换特性开关或改自定义文本后预览随之更新 | spec.md §验收标准#9 | 浏览器 Preview 面板 + 网络请求监测 | Preview 面板展开正常；**切换 features 后前端确实重新触发 preview 请求（network 监测：POST /prompt-preview → 200）**；但 preview 内容不更新（tool_ids 为空导致门控段不出现），用户可观察到开关切换不影响 preview 显示内容 | **fail（请求已触发，但内容不更新，ISSUE-3 遗留）** |

---

## Issues（Round 4）

### ISSUE-1（R4 PASS — 已修复并验证）

**关闭**：Round 4 验证通过。

**验证证据**：
- `GET /im/v1/nodes/wt-feat-379-r4/capabilities` 返回：
  ```
  features: [
    {key: "memory_curation", available: true, default_on: true, requires_tool: "memory"},
    {key: "skill_creation",  available: true, default_on: true, requires_tool: "skill_manage"}
  ]
  ```
- create 页 snapshot：`@e13 [checkbox] "Memory Curation..." [checked]` / `@e14 [checkbox] "Skill Creation..." [checked]`
- 截图：`/tmp/feat379-r4-09-create-features-visible.png`

---

### ISSUE-2（R4 PASS — 已修复并验证）

**关闭**：Round 4 真实多服务链路验证通过。

**验证证据（真实 kill+restart IM）**：
```
1. 前端 Save Agent → 立即 GET /config：
   features: {memory_curation: false}
   custom_prompt: "You are my personal legal advisor, answer with relevant clauses."
   profile_version: 2

2. kill IM (PID 29922) → restart IM (PID 35045, 同 DB、同 JWT secret)

3. GET /config（重启后）：
   features: {memory_curation: false}  ← 保持
   custom_prompt: "You are my personal legal advisor, answer with relevant clauses."  ← 保持
   profile_version: 2  ← 未重置
   source: live (Gateway 重连后 source=live 路径不再覆盖)
```
- 前端 UI（重启后重新打开）显示持久化状态（截图：`/tmp/feat379-r4-13-after-restart-detail.png` / `/tmp/feat379-r4-14-after-restart-features.png`）

---

### ISSUE-3（R4 确认仍 fail — 部分修复，剩余问题：tool_ids 未传入）

**Severity**: major
**Recommended Action**: fix-implementation
**Action Rationale**: 前端切换 features 后确实触发了 preview 请求（`POST /prompt-preview → 200`），说明 useEffect 依赖已修复（ISSUE-3 的一个子问题已解决）。但 preview 请求 body 中 `tool_ids: []`（空数组），导致 memory_curation gate 的 `requires_tool="memory"` 检查失败（memory 工具被视为不在位），memory guidance 段无论 memory_curation=true 还是 false 都不出现。用户可观察症状：Memory Curation 勾选/取消后 preview 内容始终不变。

**证据**：
- 拦截前端 preview 请求 body：`{"features":{"memory_curation":true,"skill_creation":true},"custom_prompt":"...","tool_ids":[],"scenario":"direct"}`
- Preview 文本 7315 字节，切换 Memory Curation 前后内容相同
- 单测层：`tests/unit/test_prompt_preview_endpoint.py` 6/6 通过（端点层门控逻辑正确，传入 tool_ids=["memory"] 时 on/off 确实不同）
- IM proxy 层：browser 的 preview 请求成功（200），但因 tool_ids=[] 门控未生效

**期望**：前端 detail 页发 preview 请求时，应将当前 agent 的 tool_allowlist（`["memory", "web_search"]`）传入 tool_ids 字段，使 requires_tool 门控能正确判断工具在位。

---

## 通过的旅程小结（Round 4）

- **ISSUE-1 已修复**：node capabilities 含 FEATURE_REGISTRY 投影，create 页 Features 开关组按 default_on 呈现（截图：`/tmp/feat379-r4-09-create-features-visible.png`）
- **ISSUE-2 已修复**：真实 kill+restart IM 后 features/custom_prompt 持久化保持（API 证据 + UI 截图）
- **AC5 群聊配置**：Group Reply Policy select + "always active, not a toggle" 正常
- **AC6 coding CLI 回归**：golden 测试 13/13 通过
- **AC7/AC8 CC 对齐段**：Preview 含 `# Executing actions with care` / `file_path:line_number` / `owner/repo#123`
- **AC4 custom_prompt 持久化**：重启后 UI 正确显示 "You are my personal legal advisor..."

---

## Side Findings（Round 4）

- Gateway 绑定 URL 尾部有多余文本（`token=xxx to finish binding this node.` 而非仅 `token=xxx`），导致手动构建 bind URL 时容易出错。此为 ephemeral 验收环境问题，out-of-unit minor，不立 issue。
- `test_message_contract_fields_are_stable` 已知失败（R1/R2/R3 记录），本轮未重跑，不立 issue。

---

## 上层文档同步检查（Round 4）

| 文档 | 检查结果 |
|---|---|
| `SPEC.md` | 无需更新 |
| `docs/内核设计SPEC.md` | 待 ISSUE-3 修复后补充 PromptContext.flags / tool_ids 传入路径说明 |
| `AGENTS.md` / `CLAUDE.md` | 无需更新 |
| `docs/CodingCLI-SPEC.md` | 无需更新 |
| `docs/NodeGateway-SPEC.md` | ISSUE-2 已修复，可以补充 features/custom_prompt Gateway 写回说明（不阻塞本次验收） |
| `docs/IM-SPEC.md` | ISSUE-2 已修复，可以补充 /config 路由字段说明（不阻塞本次验收） |

---

## Recommended Action Summary（Round 4）

ISSUE-1 和 ISSUE-2 已修复关闭。**ISSUE-3 剩余子问题**（前端 preview 请求未传 tool_ids）仍为 major，需修复：

**ISSUE-3 修复目标**：前端 detail 页（`agent-detail-page.tsx` / `CreateBehaviorCard`）在构建 prompt-preview 请求时，应从 agent capabilities 或 agent config 取到当前 tool_allowlist，并填入请求的 `tool_ids` 字段。修复后，勾选/取消 Memory Curation 时 preview 中 memory guidance 段应随之进出（len 差约 +583 bytes，对应 M7 live chain 证据）。

---

## Recommended Action Summary（Round 3）

仍有 2 blocking + 1 major issue，需再派 fix-implementation milestone（M7）：

1. **ISSUE-2（blocking，最高优先）**: IM 重启后 features/custom_prompt 归零。两条路径均失效：① 前端 Save 路径（Save 后立即 GET 就丢失，可能是 Save 请求体缺少 tool_allowlist 等字段被 422 拒绝而前端没有报错）；② 直接 PATCH（含所有字段）→ 同会话可读，但重启后丢失（Gateway re-sync 以空值覆盖）。需同时排查前端 Save 构建的 PATCH 请求体完整性，以及 Gateway 启动时 sync payload 是否携带 features/custom_prompt。

2. **ISSUE-1（blocking）**: node capabilities `features: []`。`GET /im/v1/nodes/{node_id}/capabilities` 返回空数组，而非 FEATURE_REGISTRY 投影。M6 的修复路径是 IM route 层从 Gateway 回传值，但实际 Gateway 没有返回 features 列表。需检查 Gateway 的 node-capabilities handler 是否正确返回 FEATURE_REGISTRY 投影数据。

3. **ISSUE-3（major）**: UI Preview 切换 features 后不更新。前端请求 Gateway 的 prompt-preview 因 WebSocket 未绑定而 503，且即使在 Gateway 连接正常时（R2 round 中），切换 features 后 Preview 内容也未变化。需排查前端在 features 开关变化时是否重新触发 preview 请求，以及 IM proxy 是否正确转发 tool_ids 至 Gateway。
