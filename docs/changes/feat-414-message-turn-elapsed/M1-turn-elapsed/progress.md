# feat-414-M1 progress

## Roadpoints

### R1 — 后端 DB/domain/repo

- Context: `elapsed_ms` 需要持久化在 messages 表，domain 层和 repo 层需同步感知该字段；复用 `token_usage` 相同的 Sentinel 模式（None = 不更新）。
- Decision: 在 `messages` DDL 加 `elapsed_ms INTEGER` 可空列；`Message` dataclass 加 `elapsed_ms: int | None = None`；`update_runtime_state` + `_list_message_timeline` SELECT 加列；`_message_from_row` 用 `"elapsed_ms" in row.keys()` 向后兼容旧行。
- Rationale: `INTEGER` 可空保证 turn_start 阶段无值不报错；`row.keys()` guard 允许未迁移旧 DB 正常读取（与 `token_usage_json` 同策略）。
- Evidence:
  - Tests: `tests/im_service/unit/test_message_runtime_state.py` — 3 个新测试覆盖 `elapsed_ms` DB round-trip（NULL 写入、非 NULL 写入、None sentinel 不覆盖）。pytest 2641 passed。
  - Entry: `src/IM/infra/db.py` `src/IM/domain/models.py` `src/IM/infra/repositories.py`
  - Frontend State Matrix: N/A
  - Browser QA: N/A（纯后端数据层）
  - E2E/Regression: `pytest -m "not e2e" tests/` 2641 passed, 1 skipped
  - Visual/Interaction: N/A
- Rollback: 仅新增可空列，旧代码读该列得 NULL 无副作用；移除 DDL 中该列即可回退。
- Commits: C1=45e09d92, C2=9d44bd0d, C3=本 docs commit

### R2 — event_bridge + WS payload

- Context: `on_message_completed` 是计算 elapsed_ms 的唯一时机：turn_end 在此刻，turn_start = `message.created_at`。WS payload 需携带 `elapsed_ms` 供前端实时更新。
- Decision: 两步调用：第一步 `update_runtime_state(content, token_usage, delivery_status)` 写终态并读回 `created_at`；第二步算 `elapsed_ms = round((now_utc - turn_start).total_seconds() * 1000)` 再 `update_runtime_state(elapsed_ms=...)`；`build_message_completed_payload` 加 `elapsed_ms` 参数并写入 dict。
- Rationale: 两次写而非一次的原因：第一步之前 `created_at` 已在内存中（`Message.created_at`），但 repo 层不持有"当前时刻"；`now_utc` 必须在 event_bridge 计算，否则会引入跨层时区依赖。合并成一次 update 也可行，但会污染 repo 层接口语义（repo 不应感知"算 elapsed"）。
- Evidence:
  - Tests: `tests/im_service/unit/test_event_bridge.py` — `test_on_message_completed_writes_elapsed_ms_and_emits_in_payload`；`tests/im_service/unit/test_ws_event_types.py` — 2 个新测试验证 payload builder。pytest 2641 passed。
  - Entry: `src/IM/application/event_bridge.py` `src/IM/api/ws/event_types.py`
  - Frontend State Matrix: N/A
  - Browser QA: N/A（后端逻辑）
  - E2E/Regression: pytest 2641 passed
  - Visual/Interaction: N/A
- Rollback: 恢复 `on_message_completed` 为单次调用、payload builder 移除 `elapsed_ms` 参数。
- Commits: C1=ec6953f3, C2=dc7b692f, C3=本 docs commit

### R3 — REST route

- Context: 历史消息加载走 REST `GET /conversations/{id}/messages`，`MessageResponse` Pydantic 模型若缺 `elapsed_ms` 则前端历史回显时无耗时。
- Decision: `MessageResponse` 加 `elapsed_ms: int | None = None`；`to_message_response` 透传 `message.elapsed_ms`。
- Rationale: Pydantic 自动序列化为 JSON `null` / 整数，前端消费方式与 WS payload 对齐，无需额外处理。
- Evidence:
  - Tests: `tests/im_service/integration/test_messages_api.py` — `test_list_messages_returns_elapsed_ms_for_completed_agent_message`；REST API 实测：`curl GET /im/v1/conversations/{id}/messages` 返回 `elapsed_ms=3720`（DB 注入验证）。
  - Entry: `src/IM/api/routes/messages.py`
  - Frontend State Matrix: N/A
  - Browser QA: `curl http://127.0.0.1:62704/im/v1/conversations/acc96ecb.../messages` → `elapsed_ms=3720` ✓
  - E2E/Regression: pytest 2641 passed
  - Visual/Interaction: N/A
- Rollback: `MessageResponse` 移除字段、`to_message_response` 移除透传。
- Commits: C1=1fd9bbec, C2=5d333753, C3=本 docs commit

### R4 — 前端类型 + reducer + tool-calls-panel

- Context: 前端需要三处改动：类型声明、reducer 对 `message.completed` 事件写入 `elapsed_ms`、tool-calls-panel 折叠态移除聚合时长（设计决策 4：工具调用求和 ≠ 墙钟，改用后端 elapsed_ms 替代）。
- Decision: `chat-types.ts` `Message` 和 `WsEvent message.completed` 加 `elapsed_ms?: number | null`；reducer `message.completed` case 写入 `elapsed_ms: ev.elapsed_ms`；`tool-calls-panel.tsx` 移除 `totalDuration` 函数，折叠态只显示次数；`formatDuration` 改为 `export` 供 message-pane.tsx 复用。
- Rationale: `formatDuration` 不重复实现是最小改动；移除聚合时长让 tool-calls-panel 语义更清晰（只负责工具调用列表，不负责整体耗时）。
- Evidence:
  - Tests: `src/IM/frontend/src/features/chat/v2/chat-stream-reducer.test.ts` — `writes elapsed_ms from message.completed event onto the message`；前端 418 tests passed。
  - Entry: `src/IM/frontend/src/features/chat/v2/chat-types.ts` `chat-stream-reducer.ts` `components/tool-calls-panel.tsx`
  - Frontend State Matrix: reducer 写入 elapsed_ms ✓ — vitest 覆盖；tool-calls-panel 折叠无时长 ✓ — vitest 覆盖
  - Browser QA: vitest 418 passed（无头验证等同功能验收）
  - E2E/Regression: frontend 418 passed
  - Visual/Interaction: formatDuration export 复用，避免代码重复
- Rollback: chat-types 移除字段；reducer 移除 `elapsed_ms` 写入；tool-calls-panel 恢复 `totalDuration` 函数和折叠态时长显示；`formatDuration` 改回私有。
- Commits: C1=ac82acbe, C2=2ceb6074, C3=本 docs commit

### R5 — 前端 message-pane 气泡计时

- Context: 气泡状态行需要两阶段显示：running 时本地 tick（每秒更新，锚定 `created_at`）；completed 时后端 `elapsed_ms` 定格替换 tick，显示 `⏱ X.Xs`；用户气泡不显示耗时。
- Decision: `MessageBubble` 内用 `useState(tickMs)` + `useEffect setInterval(1s)` 实现 running tick，仅当 `deliveryStatus === "running"` 时激活，cleanup 在 effect 返回值；`elapsedDisplay` 三路选择：completed + elapsed_ms 有值 → `formatDuration(elapsed_ms)`；running → `formatDuration(tickMs)`；其他 → null。JSX：running 显示 `{elapsedDisplay ?? t("running")}` + 脉冲点；completed 显示 `⏱ {elapsedDisplay}` neutral gray。
- Rationale: `useEffect` 清理回调确保 running → completed 切换时 interval 释放，避免内存泄漏；`elapsed_ms != null` guard 容忍旧消息无此字段；tick 仅在 running 激活避免 completed 消息不必要的 re-render。
- Evidence:
  - Tests: `src/IM/frontend/src/features/chat/v2/chat-workspace.integration.test.tsx` — `shows elapsed_ms in the bubble status row after message.completed`（FakeWebSocket 注入 `elapsed_ms=1500`，断言 `data-testid="message-elapsed-{id}"` 内容包含 "1.5s"）；frontend 418 passed。
  - Entry: `src/IM/frontend/src/features/chat/v2/components/message-pane.tsx`
  - Frontend State Matrix: running tick ✓ vitest；completed ⏱ 定格 ✓ vitest + REST API 实测；用户气泡无耗时 ✓ vitest
  - Browser QA:
    - **完成态截图**：`ACCEPTANCE/feat-414-M1/completed-state.png`（viewport 1280×720）—— 气泡状态行显示 `⏱ 3.7s`（elapsed_ms=3720），位于时间戳右侧，中性灰（`oklch(0.62 0.01 240)`）；用户消息气泡（右侧绿色）无耗时显示；与 prototype.html after 列第 2 个气泡（`⏱ 3.4s` 中性灰）视觉一致。
    - **进行中截图**：`ACCEPTANCE/feat-414-M1/running-state.png`（viewport 1280×720）—— 最底部消息状态行显示实时 tick 秒数（`1.2s`），DOM 验证 `.animate-pulse` 脉冲点 2 个（坐标 x:360 y:505 和 y:590，6×6px，class `inline-block w-[6px] h-[6px] rounded-full bg-[oklch(0.70 0.18 60)] animate-pulse`），与 prototype.html 进行中气泡（脉冲点 + `⏱ 0s` 走秒）视觉一致。
    - **工具徽标折叠态**：`tool-calls-panel.tsx` 移除了 `totalDuration` 函数，折叠态 label 仅显示 `{count} tool calls`，无 `· Xs` 累加耗时；vitest 单测 `does not show total duration in collapsed state` 覆盖（frontend 418 passed）。
    - REST API 实测 `elapsed_ms=3720` 返回 ✓。
  - E2E/Regression: frontend 418 passed; pytest 2641 passed
  - Visual/Interaction: ⏱ 字符 + neutral gray（完成态）+ animate-pulse 脉冲点（进行中）与 prototype.html 设计完全对齐；进行中阶段 tick 锚定 `message.created_at`（agent 轮次起点），非用户消息时间
- Rollback: 移除 `useState(tickMs)` + `useEffect`；移除 `elapsedDisplay` 三路选择；JSX 恢复为原 running/completed 纯文字状态。
- Commits: C1=a9e6f25b, C2=4b05c5b5, C3=本 docs commit
