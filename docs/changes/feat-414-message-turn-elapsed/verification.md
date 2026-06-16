# Verification Report: feat-414

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 5/5 tasks complete；6/6 requirements covered |
| Correctness | 6/6 scenarios 有实现；3/6 scenarios 缺部分测试覆盖 |
| Coherence | 4/4 design 决策已遵守 |

No critical issues. 3 warning(s) to consider. Ready for PR (with noted improvements).

---

## Completeness

**Tasks: 5/5 complete**（R1/R2/R3/R4/R5 均标 DONE）

**Spec 覆盖：**
- Requirement: agent 回复气泡显示本轮墙钟耗时 → **已实现**
- Requirement: 工具徽标不再用累加耗时冒充总耗时 → **已实现**

所有 6 个 Scenario 均有对应实现（见 Correctness 节）。

---

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 含多轮工具与思考的慢任务（正常路径） | `event_bridge.py:238-250`（elapsed_ms 计算）；`message-pane.tsx:383-388`（completed 定格） | `test_event_bridge.py:223`；`chat-workspace.integration.test.tsx:265` | covered |
| 纯文本回复、零工具调用也显示耗时 | `message-pane.tsx:382-389`（`isAgent` 路径，不依赖 tool_calls） | `chat-workspace.integration.test.tsx:265`（无 tool_calls 的 message.completed） | covered |
| 这一轮仍在进行中：实时计时增长 + 答完后定格 | `message-pane.tsx:371-388`（useState tickMs + useEffect setInterval 1s） | `chat-workspace.integration.test.tsx:265`（仅覆盖 completed 定格；running tick 无 fake-timer 断言） | **WARNING：见 W1** |
| 用户自己发的消息气泡不显示耗时 | `message-pane.tsx:383`（`isAgent` guard：用户气泡 `elapsedDisplay` 永远 null） | 无 vitest 断言 | **WARNING：见 W2** |
| 折叠态工具徽标只显示次数，无 `· Xs` | `tool-calls-panel.tsx:59-60`（移除 totalDuration，折叠态纯次数字符串） | 无明确"不含时长"断言 | **WARNING：见 W3** |
| 展开后单工具耗时仍在 | `tool-calls-panel.tsx:130`（`formatDuration(call.duration_ms)` 保留在展开行） | `tool-calls-panel.test.tsx`（多处 expand + duration 断言） | covered |

---

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 决策 1: elapsed 在 IM `on_message_completed` 算，起点用 `message.created_at` | 是 | `event_bridge.py:238-247`：`now_utc = datetime.now(timezone.utc)`；`turn_start = datetime.fromisoformat(current.created_at)`；`elapsed_ms = round((now_utc - turn_start)...)`；未动 agent core / gateway |
| 决策 2: 进行中实时 tick 由前端本地 tick，锚 `created_at`；completed 后用权威 `elapsed_ms` 定格 | 是 | `message-pane.tsx:371-388`：`useEffect setInterval 1s`；`elapsedDisplay` 三路选择（running→tickMs，completed→elapsed_ms，其他→null） |
| 决策 3: `elapsed_ms` 持久化为 messages 表新列，无后向兼容 | 是 | `db.py:127`（`elapsed_ms INTEGER`）；`repositories.py:1437-1438`（`row.keys()` guard 容忍旧行） |
| 决策 4: 工具徽标只删折叠态求和，保留展开行单工具耗时 | 是 | `tool-calls-panel.tsx:59-60`（折叠态纯次数）；`tool-calls-panel.tsx:130`（展开行 `formatDuration(call.duration_ms)` 保留） |

**架构自洽性**：本 unit 全部改动在 IM 包内，未破坏任何依赖方向（`IM` 包不调用 `agent`，不向外暴露新的跨包接口）。`formatDuration` 由 `tool-calls-panel.tsx` export 供 `message-pane.tsx` 复用，属于同包内复用，合规。

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

**W1: 进行中实时计时（running tick）场景无 vitest 断言**

tasks.md UI 状态矩阵写明 "running（进行中，实时 tick）: vitest integration test"，但 `chat-workspace.integration.test.tsx` 中仅有 completed 定格测试，无任何使用 `vi.useFakeTimers()` / `vi.advanceTimersByTime()` 验证 running 态 tick 数字出现在 DOM 的断言。

修复建议：在 `src/IM/frontend/src/features/chat/v2/chat-workspace.integration.test.tsx` 中，在"shows elapsed_ms..."测试之后或独立 describe 中，用 `vi.useFakeTimers()` 推进时钟，断言 running 态气泡的脉冲行显示秒数文本（如 `"5s"` 或任意 `\d+s` 匹配）。参考 `in-app-toast.test.tsx:40`（`vi.advanceTimersByTime`）的已有写法。

**W2: 用户气泡不显示耗时场景无 vitest 断言**

tasks.md UI 状态矩阵写明 "用户气泡（不显示耗时）: vitest 状态断言"，但测试套件中找不到任何断言：当消息 `sender.type === "user"` 时，`data-testid="message-elapsed-*"` 元素不存在或不渲染。

修复建议：在 `src/IM/frontend/src/features/chat/v2/components/message-pane.test.tsx` 或 `chat-workspace.integration.test.tsx` 中，构造一条 `delivery_status: "completed"`、`elapsed_ms: 1234` 但 `sender_type: "user"` 的消息，断言 `queryByTestId("message-elapsed-<id>")` 为 null。实现已正确（`message-pane.tsx:383` `isAgent` guard），测试仅是遗漏。

**W3: 折叠态工具徽标"无累加时长"场景无明确 vitest 断言**

tasks.md 标注 "工具徽标折叠（无总时长）: vitest" 覆盖，但 `tool-calls-panel.test.tsx` 里的折叠态测试（`getByRole("button", { name: /tool call/i })`）只验证 expand 行为，未断言 toggle 按钮文本中不含 `· Xs` 或 `· \d` 时长后缀。

修复建议：在 `src/IM/frontend/src/features/chat/v2/components/tool-calls-panel.test.tsx` 中，构造含 `duration_ms` 的 ToolCall 列表，render 后取 toggle button 的 `textContent`，断言 `not.toMatch(/·\s*\d/)` 或 `not.toContain("s")`（仅匹配时长后缀部分，不误杀工具 summary 文本）。

### SUGGESTION（可以修）

无。
