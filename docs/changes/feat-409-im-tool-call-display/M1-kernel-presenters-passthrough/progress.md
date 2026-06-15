# feat-409-M1 — Progress

## 体量上限复核（M1 grounding 项，决策 6）

256KB 内核 `_enforce_cap` 是唯一绑定约束，无更小隐藏上限：
- Gateway→IM：uvicorn `ws_max_size` 默认 16MB（IM 用 Starlette `websocket.receive_text()`，无自身上限）
- IM→浏览器：同上 uvicorn 16MB；浏览器 WebSocket API 无消息上限
- 持久化：`messages.tool_calls_json` 为 SQLite TEXT（实际上限 ~1GB）
- realtime_stream 已正确带 detail（`_presentation_dict` 含 detail 键），断点确在 Gateway，符合 design

结论：无需为本 unit 新增传输层裁剪。

## R1 — 内核 presenter 补齐/改人话 + task 收尾

（待补）

## R2 — Gateway tool_end 透传 detail

（待补）

## R3 — IM ToolCall.detail 贯穿 parse/serialize/persist

（待补）

## R4 — 文档收尾

（待补）
