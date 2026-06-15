# Verification Report: feat-409

Round 1 — 2026-06-15

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 7/8 tasks（M2 退出标准有一项 tasks.md 未更新为 [x]，但代码已实现） |
| Correctness | 14/14 scenarios covered |
| Coherence | Followed（1 个轻微偏离，见 WARNING） |

No critical issues. 1 warning(s) to consider. Ready for PR (with noted improvements).

---

## Completeness

### Tasks 完成状态

**M1（内核 presenter 补齐/改人话 + task 收尾 + 透传链打通）**: 8/8 完成（全部 `[x]`）

**M2（前端分工具渲染 + 长输出可控展开）**: 7/8 已完成，1 项 tasks.md 标记遗漏（见 WARNING）。

#### M2 tasks.md 未勾选项

- `- [ ] \`chat-types.ts\` ToolCall 增 \`detail?: ToolDetail\`（结构化 dict）`

**实际状态**：代码已实现。`ToolDetail` 类型已定义 (`src/IM/frontend/src/features/chat/v2/chat-types.ts:31-44`)，`ToolCall.detail?: ToolDetail` 已加 (L59-62)。任务实现完成，仅 tasks.md 漏打勾。

### Spec Requirement 覆盖

全 4 个 Requirement 均有实现：

1. **折叠态摘要有信息量且用真实工具名** — 已实现
2. **展开态按工具类型呈现详情** — 已实现
3. **长输出可控展开，不撑爆聊天流** — 已实现
4. **执行中状态不退化** — 已实现（沿用现有 `running` + pulse，代码未改动）

---

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| bash 带 description：折叠态显示 description | `presentation.py:293` `_summarize_bash` | `test_presentation.py:139` | covered |
| bash 未填 description：降级显示命令首段 | `presentation.py:720-721` | `test_presentation.py:152` | covered |
| 工具调用失败时折叠态标红 | `tool-calls-panel.tsx:97` `chat-tool-call-row--${call.status}` + `tool-presentation.ts:failTag` | `tool-calls-panel.test.tsx:88` | covered |
| 工具名显示真实注册名 | `tool-calls-panel.tsx:108` `{call.name}` | `tool-calls-panel.test.tsx:58` | covered |
| bash 展开看到命令与输出 | `tool-detail-renderers.tsx:BashCard` | `tool-calls-panel.test.tsx:123` | covered |
| edit 展开看到 diff | `tool-detail-renderers.tsx:DiffCard` | `tool-calls-panel.test.tsx:138` | covered |
| write 展开看到写入内容 | `tool-detail-renderers.tsx:WriteCard` | `tool-calls-panel.test.tsx:158` | covered |
| web_fetch 展开看到网页信息 | `tool-detail-renderers.tsx:WebCard` | `tool-calls-panel.test.tsx:172` | covered |
| agent 展开看到完整派发 prompt（排在结果前） | `tool-detail-renderers.tsx:AgentCard`；内核 `presentation.py:420-432`（prompt 键在 content 前，且不进 256KB 截断集合） | `test_presentation.py:208`（断言 `keys.index("prompt") < keys.index("content")` + 长 prompt 不截断）；`tool-calls-panel.test.tsx:187` | covered |
| memory / skill_manage / task_stop 有专属呈现 | `tool-detail-renderers.tsx:MemoryCard/SkillCard/TaskStopCard` | `tool-calls-panel.test.tsx:216/229/242` | covered |
| 长输出默认截断 + "展开全部" 入口 | `tool-detail-renderers.tsx:LongOutput`，阈值 50 行 | `tool-calls-panel.test.tsx:328` | covered |
| 展开全部后限高滚动 + 收起 | `tool-detail-renderers.tsx:LongOutput`（`chat-tool-long-output--expanded` CSS class）| `tool-calls-panel.test.tsx:350/370` | covered |
| 源头已截断的输出标注 | `tool-detail-renderers.tsx:LongOutput`，`truncatedAtSource → chat-tool-long-output-source-note` | `tool-calls-panel.test.tsx:388` | covered |
| 工具执行中状态不退化 | `tool-calls-panel.tsx:38` anyRunning pulse（沿用） | `tool-calls-panel.test.tsx:20` | covered |

### 补充核对

- **M1 数据链**：Gateway `tool_end` 透传 `detail` (`main.py:3518` `detail = pres.get("detail")` → L3530 `tool_call_payload["detail"] = detail`)；IM `ToolCall.detail` 贯穿 `domain/models.py:201`、`gateway_handler.py:2524`、`event_types.py:55-56`、`repositories.py:2718-2719/2783-2784`。
- **历史消息降级**：`tool-detail-renderers.tsx:ToolDetailBody` 末尾 fallback 到 `call.output` 字符串（L346-352）；`_decode_tool_calls` legacy 行 `detail → None` 有单测 `test_tool_call_detail.py:112`。
- **task.py 死代码 / `_TaskPresenter` 删除**：`task.py` 不存在于 `builtins/`，`presentation.py` 中无 `_TaskPresenter` / `TASK_PRESENTER` 引用。`_AgentPresenter` 已按 agent schema 重写。
- **4 个工具 presenter 属性挂载**：`agent.py:33`、`memory.py:46`、`skill_manage.py:47`（`TaskStopTool` 在 `task_stop.py:20`）均已挂 `presenter` 属性。
- **全测试树状态**：`pytest -m "not e2e"` → 2590 passed；contract → 127 passed；`npm test` → 398 passed；`npm run build` 绿。

---

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 决策 1：Gateway 整体透传 `detail`，不裁剪 | 是 | `main.py:3518/3529-3530`：`detail = pres.get("detail")` → `tool_call_payload["detail"] = detail` |
| 决策 2：IM `ToolCall` 增 `detail: dict \| None`，贯穿 parse/serialize/persist | 是 | `domain/models.py:201`、`gateway_handler.py:2524`、`event_types.py:55-56`、`repositories.py:2718-2719/2783-2784` |
| 决策 3：补 4 个 presenter，`_AgentPresenter` 重写（agent schema），完整 prompt 排结果前不截断 | 是 | `presentation.py:380-454`（`_AgentPresenter`）；`_enforce_cap` 截断集 `("stdout","stderr","diff","content")` 不含 `prompt`（L692） |
| 决策 4：折叠态文案由 presenter `summary` 产出，前端通用渲染 output，不按 name 派生 | 是 | `tool-presentation.ts:collapsedSummary` 直接返回 `call.output`；`tool-calls-panel.tsx:90` |
| 决策 5：前端两级展开，50 行阈值 + 限高滚动 + "收起" | 是 | `tool-detail-renderers.tsx:30/LONG_OUTPUT_LINE_THRESHOLD=50/LongOutput` |
| 决策 6：256KB cap 沿用 `_enforce_cap`，不新增传输层上限；prompt 不进截断集 | 是 | `presentation.py:686-707`；`_enforce_cap` 截断字段集不含 `prompt` |
| refactor-406 决策 12：presenter 随工具走（`getattr(tool,"presenter",None)`)，不用全局注册表 | 是 | `presentation.py:42`；各工具 `presenter = _XXX_PRESENTER` 类属性 |
| 模块边界：产品只 import `agent.sdk`，IM 不调 agent | 是 | contract 127 passed 包含边界验收 |

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

**W1：M2 tasks.md 中 `chat-types.ts ToolCall 增 detail` 任务标记遗漏**

- 文件：`docs/changes/feat-409-im-tool-call-display/M2-frontend-render-expand/tasks.md:11`
- 问题：`- [ ]` 未更新为 `[x]`，但代码已在 `chat-types.ts:59-62` 实现。
- 修复：将 `- [ ] \`chat-types.ts\` ToolCall 增 \`detail?: ToolDetail\`` 改为 `[x]`。

### SUGGESTION（可以修）

**S1：web_fetch 折叠态 summary 与 design 描述轻微差异**

- 文件：`presentation.py:349`
- 问题：design.md 第 103 行描述为 `web_fetch→title`（纯标题），但实现为 `status=200 (Example)`（含 HTTP 状态码）。包含状态码对用户辨别请求是否成功是有帮助的，且测试 `test_presentation.py:182` 已断言当前行为。如需严格对齐 design 的"纯 title"描述，可改为：若 title 存在则只显示 title，否则回退 status；但当前含 status 的实现信息量更高，用户体验可接受。
- 建议：可选择更新 design.md 第 103 行的措辞为 `web_fetch→status+title`，或保持现状（低优先级）。

---

# Round 2 — 2026-06-15

## 目标

复验 Round 1 中的 W1（tasks.md 漏打勾）和 S1（web_fetch summary 与 design 描述偏差）是否已闭合，同时核实 Round 1 修复引入的三处代码变更（registry.py `tool_result` 加 `arguments` 别名、REST `detail`/`input` 补齐、`_AgentPresenter` in-band error 规整为 str）未引入新偏离。

## W1 复验 — 已闭合

`docs/changes/feat-409-im-tool-call-display/M2-frontend-render-expand/tasks.md:11` 已更新为 `[x]`。全部 8/8 任务均已勾选。

## S1 复验 — 原报告误判，实际无问题

design.md 第 103 行原文为 `web_fetch→\`status=200 (title)\``，已包含 status + title 的组合格式，与实现完全一致。Round 1 报告的 S1 是误判——design.md 从未要求"纯 title"。该 SUGGESTION 关闭。

## Round 1 修复影响面核查

### Fix 1：REST 历史路径补 `detail` / `input`

- `src/IM/api/routes/messages.py:169` 已加 `detail=tc.detail`；`L166` 已加 `input=tc.input if isinstance(tc.input, dict) else {}`。
- `ToolCallPayload(BaseModel)` 在 `L82` 有 `input: dict = {}` 、`L88` 有 `detail: dict | None = None`。
- 新增专项测试 `tests/im_service/unit/test_messages_route_detail.py`（3 个测试）全部通过，覆盖 detail 传递 / input 保真 / 历史无 detail 降级为 None。
- 影响面仅限 `to_message_response` 序列化函数，不涉及任何写路径，无副作用风险。

### Fix 2：内核 `registry.py` `tool_result` 事件加 `arguments` 别名

- `src/agent/core/tools/registry.py:292` `tool_result_payload["arguments"] = normalized_args` 与已有 `"args": normalized_args` 并存（L288）。
- `realtime_stream.py` 的 `on_tool_result`（`L90`、`L100`）读 `event.get("arguments")`——fix 前此字段为 None，前端 `tool_end` 携带空 input，盖掉 `tool_start` 时写入的真实入参；fix 后 `arguments` 有值。
- 对 `tool_call` 事件（`L158`）的 `arguments` 无影响（该事件由 bugfix-367 早已补齐）。
- 对 hooks 合约无破坏：`tool_result` payload 新增字段是非破坏性扩展，现有 observe handler 读 `args` 的继续读 `args`（`L288` 未改）。
- 专项测试 `tests/unit/platform/hooks/test_realtime_stream_events.py::test_tool_result_emits_tool_end_with_presentation`（`L105-139`）断言 `evt["data"]["arguments"] == {"path": "src/app.py"}` 通过。bugfix-367 原有测试 `tests/unit/test_bugfix_367_tool_call_observe_timing.py::test_tool_result_event_carries_arguments_alias` 继续通过。

### Fix 3：`_AgentPresenter` in-band error 规整为 `str`

- `src/agent/platform/tools/presentation.py:433` `"error": str(output.get("error", ""))`——当 output 无 error 键时得到 `""`（空串），前端 AgentCard 渲染字符串时不会崩溃。
- `tests/unit/platform/tools/test_presentation.py::TestAgentPresenter::test_end_failed_error_is_plain_str` 断言 `isinstance(evt.detail["error"], str)` 且值为 `""` 通过。
- 影响范围仅 `_AgentPresenter.format_end` 的 Mapping 分支，其他 presenter 和 error 路径（`L411-416`，`result.error` 分支）未改动。

## 全量测试

- `pytest -m "not e2e"`: **2595 passed, 1 skipped** (含 Round 1 新增的 `test_messages_route_detail.py` 3 tests、`test_realtime_stream_events.py` 新增断言、`test_presentation.py` `TestAgentPresenter::test_end_failed_error_is_plain_str`)
- `npx vitest run`: **401 passed, 59 test files**（前端测试计数含新增测试）
- 全量绿，无新增失败。

## Round 2 Summary

| 维度 | 结果 |
|---|---|
| W1 闭合 | 是 — tasks.md 已全部勾选 |
| S1 闭合 | 是（实为误判，design.md 已含 `status=200 (title)`，无需改动） |
| Fix 1 副作用 | 无 |
| Fix 2 副作用 | 无，hooks 合约非破坏性扩展 |
| Fix 3 副作用 | 无 |
| 全量测试 | 2595 passed + 401 front-end passed |

**All checks passed. Ready for PR.**

---

# Round 3 — 2026-06-15

## 目标

轻量复核 Round-3 修复：memory/skill 失败态（`success=false`）现在正确显示失败 + 折叠态标红，`isCallFailed` 收敛 `status==failed || detail.success===false`；memory/skill 成功态补强（action·target·content 可见）。核查：与 spec/design 一致、未引入新偏离、vitest 新测试覆盖 success=false 路径。

## 变更范围

commit `a30f14a4`（fix）+ `fdd52545`（merge），涉及 5 个前端文件：

- `tool-presentation.ts` — 新增 `isCallFailed(call)` 函数
- `tool-calls-panel.tsx` — 折叠行改用 `isCallFailed(call)` 驱动红色 + 图标 + CSS modifier
- `tool-detail-renderers.tsx` — `MemoryCard`/`SkillCard` 增失败分支；MemoryCard 成功态补 meta+body
- `global.css` — 新增 `.chat-tool-detail-info--failed` 红头色 + `.chat-tool-detail-info-meta`
- `tool-calls-panel.test.tsx` — 新增 `describe("ToolCallsPanel · success-false failure (Round-3 fix)")` 6 个测试

## Spec 一致性核查

spec.md §84（「工具调用失败时折叠态标红」）：GIVEN 工具失败 → THEN 折叠行有可见失败标识（标红 + 失败提示）。

该 scenario 原本只考虑 `call.status === "failed"` 路径，但 memory/skill 从不抛错（失败返回 `{success:False, error}`），内核不产 `result.error`，所以 `call.status` 永远是 `"completed"`。`isCallFailed` 增加 `detail.success === false` 分支，使这两种工具的失败也触发标红——与 spec THEN 的用户可见标准完全一致，属于**正确对齐 spec 意图**，不是偏离。

spec.md §117（「memory / skill_manage / task_stop 有专属呈现」）：WHEN 展开 → THEN 看到结果卡片。`MemoryCard` 失败分支渲染 `✕ + message`，成功分支渲染 `✓ + action·target·content`；`SkillCard` 同理。满足条件。

## Design 一致性核查

design.md 决策 4（collapsed-row 文案来自 `output`，不由 name 派生）：`isCallFailed` 只影响行样式和图标，不改 `collapsedSummary` 逻辑，决策未受影响。

决策 1（Gateway 整体透传 detail）、决策 2（IM ToolCall 增 detail）：本 Round 均为纯前端改动，未触及后端路径，不影响这两条决策。

## 测试覆盖

`tool-calls-panel.test.tsx` 新增 `describe("ToolCallsPanel · success-false failure (Round-3 fix)")` 共 5 个测试：

| 用例 | 覆盖场景 |
|---|---|
| memory success=false → ✕ + 错误文本 + --failed 类 | detail.success===false 渲染失败态 |
| skill_manage success=false → ✕ + 错误文本 + --failed 类 | SkillCard 失败分支 |
| collapsed row 红 + fail-tag（call.status=completed，detail.success=false） | isCallFailed 来自 detail，非 status |
| memory success=true → ✓ + target + content | 成功态补强不误伤 |
| skill success=true → 显示 action + name | SkillCard 成功态头部 |

所有测试直接断言 DOM 结构（`.chat-tool-detail-info--failed`、`.chat-tool-call-row--failed`、`.chat-tool-call-fail-tag`），覆盖了两条失败分支和成功态，覆盖充分。

commit message 中报告：vitest 406 passed（新增 6 用例），`npm run build` 绿，`tsc` 绿。

## 架构自洽

纯前端修改，未新增跨包依赖，未触及后端接口，不破坏任何模块边界。

## Issues

### CRITICAL

无。

### WARNING

无。

### SUGGESTION

无。

## Round 3 Summary

| 维度 | 结果 |
|---|---|
| 与 spec 一致 | 是 — 折叠标红覆盖 detail.success===false，与 spec 失败标识要求完全对齐 |
| 与 design 一致 | 是 — 纯前端修复，所有 design 决策无受影响 |
| 新偏离 | 无 |
| vitest 覆盖 success=false | 是 — 5 个新测试覆盖全路径 |

**All checks passed. Ready for PR.**
