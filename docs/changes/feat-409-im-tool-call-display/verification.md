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
