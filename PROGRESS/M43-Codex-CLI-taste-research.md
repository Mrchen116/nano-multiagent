# M43 Codex CLI Taste 研究落盘（进行中）

更新时间：2026-03-04
来源：explorer `019cb6b3-2bba-7241-9410-1c98cbbf94e7`、`019cb6b8-b2d4-7de3-bd25-2256128dc01b`

## 已确认设计原则（可直接指导 nano CLI）

1. 事件不要直出：先做 `protocol event -> semantic view model`，再渲染人类文案。
2. 默认静默低价值高频事件：只保留关键阶段（开始/完成/错误/告警/关键工具进度）。
3. 工具输出默认截断：使用 `head + ellipsis + tail`，避免长输出刷屏。
4. 多工具事件先聚合后输出：按 `call_id` 或工具名聚合，完成时再 flush，避免碎片行。
5. 人类模式和机读模式分通道：human 输出与 JSON 输出契约不能互相污染。
6. 进度展示走“可覆写单行状态”而不是每个原始事件一行。

## 关键代码锚点（codex）

### 人类输出与事件转译
- `codex-rs/exec/src/event_processor_with_human_output.rs:207` `process_event`：事件 `match` 后输出自然语言。
- `codex-rs/exec/src/event_processor_with_human_output.rs:893` `is_silent_event`：低价值事件静默策略。
- `codex-rs/exec/src/event_processor_with_jsonl_output.rs:847`：JSONL 机读输出路径。
- `codex-rs/exec/src/lib.rs:1`：stdout 契约注释（human 与 json 分离）。

### 状态线和工具输出示例
- `codex-rs/exec/src/event_processor_with_human_output.rs:244`：`McpStartupUpdate` -> `mcp: ... starting|ready|failed`。
- `codex-rs/exec/src/event_processor_with_human_output.rs:368`：`ExecCommandEnd` -> 成功/失败 + 耗时 + 输出片段。
- `codex-rs/exec/src/event_processor_with_human_output.rs:1037`：任务进度行格式化（含 completed/running/pending/eta）。

### 截断、聚合、节流（TUI）
- `codex-rs/tui/src/exec_cell/render.rs:99`：输出行截断策略。
- `codex-rs/tui/src/exec_cell/render.rs:530`：按屏幕行中段截断。
- `codex-rs/tui/src/exec_cell/render.rs:273`：连续 read 聚合与去重。
- `codex-rs/tui/src/exec_cell/model.rs:67`：ExecCell 聚合模型。
- `codex-rs/tui/src/chatwidget.rs:2428`：active cell 分组边界，避免 orphan end 误合并。
- `codex-rs/tui/src/streaming/commit_tick.rs:69`：commit tick 节流策略。

### 事件到界面的分层边界
- `codex-rs/tui/src/chatwidget.rs:4273` `dispatch_event_msg`：事件分发到语义 handler。
- `codex-rs/tui/src/chatwidget.rs:2380` `handle_streaming_delta`：流式增量合并。
- `codex-rs/tui/src/app.rs:2917` `handle_codex_event_now`：顶层事件转 UI cell 插入。
- `codex-rs/tui/src/history_cell.rs:582`：历史 cell 的人类文案展示（不暴露协议术语）。

## 对 M43 的直接落地要求（已注入 worker）

1. 重构 REPL 默认输出为“语义化状态线”，禁用 `[status]/[tool]/[usage]` 原样标签暴露。
2. 工具过程采用聚合摘要（开始/关键进度/结束），不逐条事件刷屏。
3. 引入默认截断策略，防止工具 chunk 大量噪声。
4. 保持 `send-message` 单 JSON stdout 契约不变。
5. 保持 run_id 过滤与 event_id 去重，不破坏已有正确性。

## 待继续追问（进行中）

1. 输入层在“用户编辑中 + 后台输出到来”时的光标恢复策略细节。
2. slash 菜单出现/消失策略，如何避免每次按键触发整屏重绘。
3. 最小改动前提下，把输入层抖动降到可发布水平的具体实现路径。

## 第四轮补充（输入层，已确认）

来源：explorer `019cb6b8-b2d4-7de3-bd25-2256128dc01b`

### A) 后台输出到来时如何避免光标错位

1. 后台事件只更新历史/状态，不直接写输入框文本。
2. 历史输出先进队列，统一在 draw 周期 flush，而非任意时刻立刻刷终端。
3. 插入历史时保持“光标中立”，flush 后恢复光标位置。
4. 每帧绘制结束再设置一次光标位置做兜底。

关键锚点：
- `codex-rs/tui/src/chatwidget.rs:1962`
- `codex-rs/tui/src/chatwidget.rs:2027`
- `codex-rs/tui/src/tui.rs:443`
- `codex-rs/tui/src/tui.rs:468`
- `codex-rs/tui/src/tui.rs:498`
- `codex-rs/tui/src/insert_history.rs:122`
- `codex-rs/tui/src/insert_history.rs:171`
- `codex-rs/tui/src/app.rs:1687`

### B) slash 菜单如何避免刷屏

1. 每次按键后统一调用 `sync_popups()`，菜单状态收口在一个状态机里。
2. 用 `needs_redraw` 决定是否请求下一帧，避免无效重绘。
3. `Esc` 只关闭 popup 不改输入内容，交互可预测。
4. 帧调度器做 coalesce + 限频，合并高频 redraw 请求。

关键锚点：
- `codex-rs/tui/src/bottom_pane/chat_composer.rs:1227`
- `codex-rs/tui/src/bottom_pane/chat_composer.rs:1277`
- `codex-rs/tui/src/bottom_pane/chat_composer.rs:1331`
- `codex-rs/tui/src/bottom_pane/chat_composer.rs:3176`
- `codex-rs/tui/src/bottom_pane/chat_composer.rs:3399`
- `codex-rs/tui/src/bottom_pane/mod.rs:409`
- `codex-rs/tui/src/tui/frame_requester.rs:6`
- `codex-rs/tui/src/tui/frame_requester.rs:92`
- `codex-rs/tui/src/tui/frame_requester.rs:113`

### C) 对 nano CLI 的 3 条最小落地策略

1. 增加 `pending_output_queue`：后台输出只入队，主渲染循环统一 flush + 光标恢复。
2. 输入处理函数返回 `needs_redraw`，只有需要时才触发重绘。
3. slash 菜单集中状态机管理：仅在首 token `/` 场景启用，`Esc` 关闭菜单不改文本。

## 第五轮补充（输入层并发细节）

来源：explorer `019cb6b3-2bba-7241-9410-1c98cbbf94e7`

新增确认点：

1. 输入与输出的“布局层”必须解耦：菜单和输入框属于 bottom pane，历史/事件属于 history pane，不能混写同一文本流。
2. slash 交互需集中状态机：`ActivePopup` 单一入口，按键后统一 `sync_popups()`，而不是多处临时开关。
3. 后台事件只触发 `request_redraw`，不要在异步回调直接 print；重绘由调度器合帧限频处理。
4. 绘制后总是显式恢复 composer 光标位置，作为并发输出后的兜底。
5. 运行中输入采用“可编辑 + 可排队（FIFO）”，并对不允许并发的命令单独拦截。

补充锚点：
- `codex-rs/tui/src/bottom_pane/chat_composer.rs:408`
- `codex-rs/tui/src/bottom_pane/chat_composer.rs:1227`
- `codex-rs/tui/src/bottom_pane/chat_composer.rs:3176`
- `codex-rs/tui/src/bottom_pane/chat_composer.rs:3399`
- `codex-rs/tui/src/bottom_pane/mod.rs:409`
- `codex-rs/tui/src/chatwidget.rs:3390`
- `codex-rs/tui/src/chatwidget.rs:4580`
- `codex-rs/tui/src/chatwidget.rs:4618`
- `codex-rs/tui/src/tui/frame_requester.rs:96`
