# M44 Codex CLI 研究补充（输入历史 / 事件折叠 / 去重策略）

日期：2026-03-04
范围：
- 上游参考仓：`/Users/czj/Repos/opencode-hub/codex`
- 本仓落地目标：`src/nano_multiagent/cli/**`（仅提出可迁移规则与建议实现锚点）

## 1) 输入编辑与历史回填交互模型（Codex）

关键结论：
- 输入框不是“字符串拼接器”，而是“带原子 element 的编辑状态机”。光标会被强制钳制到字符/element 边界，避免中途切断 placeholder/mention。
- 历史回填不是纯文本：本地会话历史保留 `text_elements/local_images/mentions/pending_pastes`，可完整回填；持久历史按需拉取文本并合并导航。
- Up/Down 历史导航有严格闸门：非空输入时，只有“当前文本等于上次回填文本 + 光标在行首/行尾”才接管导航，避免破坏多行内编辑。
- 回填后显式 `move_cursor_to_end()`，保证 shell-like 连续 Up/Down 体验。

代码锚点：
- `TextArea` 原子编辑与边界：
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/bottom_pane/textarea.rs:179`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/bottom_pane/textarea.rs:261`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/bottom_pane/textarea.rs:593`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/bottom_pane/textarea.rs:887`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/bottom_pane/textarea.rs:1069`
- 历史导航状态机：
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/bottom_pane/chat_composer_history.rs:87`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/bottom_pane/chat_composer_history.rs:173`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/bottom_pane/chat_composer_history.rs:195`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/bottom_pane/chat_composer_history.rs:212`
- 组合器接线（回填、提交、弹窗闸门）：
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/bottom_pane/chat_composer.rs:1043`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/bottom_pane/chat_composer.rs:2658`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/bottom_pane/chat_composer.rs:3176`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/bottom_pane/chat_composer.rs:1817`

## 2) 事件折叠与渲染分层（Codex）

关键结论：
- 分层清晰：
  - 事件路由/聚合在 `ChatWidget`（active cell、打断队列、begin/end 对齐、orphan 处理）。
  - 数据折叠在 `ExecCell`（exploring 组、按 `call_id` 完成、输出累积）。
  - 视觉压缩在 render 层（前缀树、行数截断、中间省略、wrap 后再截断）。
- 折叠策略不是“全隐藏”，而是“关键节点 + 可读摘要”：`Running/Ran/Exploring/Explored`、exit 状态、有限输出窗口、省略计数。
- orphan end（活跃组不含该 call_id）不会错误并入当前组，而是落成单独历史项，防止跨工具串味。

代码锚点：
- 统一历史 cell 协议与 transcript/live-tail：
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/history_cell.rs:94`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/history_cell.rs:151`
- ExecCell 折叠模型：
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/exec_cell/model.rs:36`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/exec_cell/model.rs:67`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/exec_cell/model.rs:82`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/exec_cell/model.rs:154`
- Exec 渲染压缩：
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/exec_cell/render.rs:29`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/exec_cell/render.rs:252`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/exec_cell/render.rs:356`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/exec_cell/render.rs:530`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/exec_cell/render.rs:682`
- ChatWidget 事件路由/错配隔离：
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:2360`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:2436`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:2626`

## 3) “缺失 event_id 的重复事件去重”研究结论（Codex）

关键观察：
- Codex `Event.id` 是“提交关联 id（sub_id）”，不是全局唯一事件流水号；同一 turn 多事件可共享同一 `id`，因此不能拿它做通用去重键。
- TUI 分发层基本不使用 `id` 做通用幂等；去重/幂等主要依赖“业务键 + 状态机”（`call_id`、payload key、phase）。

代码锚点：
- 协议层 `Event` 定义（关联 submission id）：
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/protocol/src/protocol.rs:931`
- 核心发送事件时普遍 `id: sub_id`：
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/core/src/codex.rs:2070`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/core/src/codex.rs:4321`
- TUI 分发层不做通用 event-id 幂等：
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:4255`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:4273`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:1913`
- 现有“业务键幂等”样式：
  - 重复 wait 抑制：`last_unified_wait + suppressed_exec_calls`
    - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:2644`
    - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:2655`
  - Realtime 用户消息去重：`last_rendered_user_message_event`
    - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget/realtime.rs:47`
    - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget/realtime.rs:80`
  - pending map 覆盖告警（按 call_id/sub_id）：
    - `/Users/czj/Repos/opencode-hub/codex/codex-rs/core/src/codex.rs:2636`
    - `/Users/czj/Repos/opencode-hub/codex/codex-rs/core/src/codex.rs:2642`
    - `/Users/czj/Repos/opencode-hub/codex/codex-rs/core/src/codex.rs:2734`
    - `/Users/czj/Repos/opencode-hub/codex/codex-rs/core/src/codex.rs:2740`
    - `/Users/czj/Repos/opencode-hub/codex/codex-rs/core/src/tools/handlers/dynamic.rs:94`
    - `/Users/czj/Repos/opencode-hub/codex/codex-rs/core/src/tools/handlers/dynamic.rs:100`

可落地策略（给 nano CLI）：
- 键设计（优先级）
  1. `event_id` 存在：`dedupe_key = event_id`
  2. `event_id` 缺失：`dedupe_key = run_id + event_name + semantic_key`
  3. `semantic_key` 建议：
     - `tool_*`: `tool_call_id`（或 `group_key`）+ `phase(start|chunk|exit|end)` + `stream(stdout|stderr)` + `seq`
     - `run_status`: `run_id + status + attempt + retry_count`
     - `text_delta`: `run_id + delta_hash + local_seq_bucket`
- 窗口策略
  - 每个 `run_id` 维护 LRU/TTL 去重窗口（例：最多 2048 key，TTL 10 分钟）。
  - 终态事件（`run_status=completed|failed|canceled`、`tool_exec_exit`）可延长 TTL，防止重放污染。
- 风险与缓解
  - 误杀（false positive）：fallback key 太粗会吞真实进度。缓解：按事件类型细分 key 字段，不做跨类型复用。
  - 漏杀（false negative）：fallback key 太细会放过重放。缓解：对 chunk 增加“短时间相同内容 hash + seq 缺失”二级判重。
  - 内存增长：长会话 key 膨胀。缓解：按 `run_id` 分桶 + LRU 上限 + turn 完成后清桶。

与 nano 现状对应锚点：
- 当前只在 `event_id` 存在时去重：
  - `/Users/czj/Repos/nano-multiagent/src/nano_multiagent/cli/repl_events.py:133`
  - `/Users/czj/Repos/nano-multiagent/src/nano_multiagent/cli/repl_events.py:134`
- SSE 解析对缺失 id 写空串：
  - `/Users/czj/Repos/nano-multiagent/src/nano_multiagent/cli/http_client.py:306`
  - `/Users/czj/Repos/nano-multiagent/src/nano_multiagent/cli/http_client.py:330`

## 4) Human 流式预览与最终摘要如何避免重复（Codex）

关键结论：
- 有“阶段切换”，也有“已播报集合/状态位”，但不是单一全局集合。
- 文本主通道：若已存在 stream controller，最终 `AgentMessage` 不再重复注入（避免“流式 + 最终消息”双写）。
- Plan 通道：优先 finalize 已流式块；只有无流式块时才写最终文本，避免双份 plan。
- Reasoning 通道：delta 只用于状态/缓冲，不直接落历史；仅在 final 时落“summary block”，随后清空缓冲。
- 状态行与流式输出分离：流式 commit 时隐藏状态行，commentary 完成后等待队列空闲再恢复，避免双重“进行中”提示。

代码锚点：
- 最终消息去重（stream 已存在则不重复）：
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:1269`
- Plan finalize 优先，fallback 次之：
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:1311`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:1327`
- Reasoning “delta 不落盘，final 汇总落盘”：
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:1346`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:1367`
- 阶段门控恢复状态行（commentary vs final）：
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:2290`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:2321`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:2338`
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget.rs:913`
- Realtime 已播报集合（避免重复 user message）：
  - `/Users/czj/Repos/opencode-hub/codex/codex-rs/tui/src/chatwidget/realtime.rs:80`

## 5) 可直接迁移到 nano CLI 的 UX 规则

规则清单：
- 规则 A：Preview 与 Summary 分层
  - Preview 只显示关键状态和关键节点（start / exit / error / chunk 计数），不输出原始 chunk 文本。
  - Summary 在 turn 末尾统一收口，避免把 Preview 原样再输出一遍。
- 规则 B：每类事件单独幂等键
  - 不做“全局字符串去重”；按事件类型构造语义键，避免吞真实事件。
- 规则 C：阶段状态机
  - `STREAMING -> FINALIZING -> FINALIZED`；进入 `FINALIZING` 后禁止再发 preview。
- 规则 D：容错优先
  - 对 orphan end（无 begin）单独落条目，不并入当前活动工具组。
- 规则 E：可观测性
  - 每个 run 输出去重统计：`dedup_dropped`, `fallback_key_used`, `orphan_events`。

建议实现锚点（nano）：
- 事件归一化/去重入口：
  - `/Users/czj/Repos/nano-multiagent/src/nano_multiagent/cli/repl_events.py:100`
  - `/Users/czj/Repos/nano-multiagent/src/nano_multiagent/cli/repl_events.py:112`
- 工具聚合视图（start/exit/error/progress）：
  - `/Users/czj/Repos/nano-multiagent/src/nano_multiagent/cli/repl_events.py:190`
- 预览文案层：
  - `/Users/czj/Repos/nano-multiagent/src/nano_multiagent/cli/repl_events.py:304`
- SSE 解析层（补 fallback key 输入字段）：
  - `/Users/czj/Repos/nano-multiagent/src/nano_multiagent/cli/http_client.py:294`

