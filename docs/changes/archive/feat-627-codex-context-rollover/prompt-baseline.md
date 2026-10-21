# Codex prompt baseline and adaptations

固定基线：`openai/codex@464add49587a7cb6032d5ab04faa8a1585947853`。模型条目 `gpt-6-astra`，路径 `codex-rs/models-manager/models.json` → `models[0].model_messages.token_budget`。该条目 `enabled=false`、`use_history_notes_extension=false`；这里只取参考文本，不声称该配置在所有线上模型启用。

所有下列原文直接从固定源码提取；实现时英文原文和适配文本作为 golden fixtures。预算数值由 design 单独定义。

## guidance_message

### 原文

```text
For tasks that may span context windows, use `notes` to maintain a concise checkpoint of the goal, decisions, progress, learnings and next steps. Include the window ID and item ID for every relevant user request you are currently solving as well as important actions/tool calls. You can use `history` tool to look up details with the references later. Note that every non-assistant item, such as user, developer, tool response, has an item id `[id: ...]` that is immediately after its item content. Relative note paths belong to the current thread; absolute paths may read other threads' notes, but writes are limited to the current thread.

It is a good idea to take incremental notes while you work so that you do not miss any important info. You can also use `get_context_remaining` tool to find the remaining token budget for better planning. Once the token budget is exhausted, you will lose access to the current window and continue in a fresh context window and you can only recover through `notes` and `history` tools. So be careful not to over-run the context window without any documentation.

If Previous context window id is present in `<context_window>`, it means a context reset occurred and this is a new window. After a reset, read the checkpoint and use the read-only `history` tool to recover any missing details. When a window ID and item ID are known, prefer `read_item` directly; when they are missing or uncertain, use `list_items`, or `search_contents` to locate the item first.

Treat notes and history as internal bookkeeping. Do not mention them in user-facing messages.

```

### 适配文本

```text
For tasks that may span context windows, use `notes` to maintain a concise checkpoint of the goal, decisions, progress, learnings and next steps. Include the window ID and item ID for every relevant user request you are currently solving as well as important actions/tool calls. You can use `history` tool to look up details with the references later. Use the window and item IDs in <context_references>; entries identify persisted user messages, assistant tool calls, and tool results. Newly admitted messages appear in the next reference snapshot. Before saving a checkpoint, use `get_context_remaining` to obtain current references when needed. Pass returned IDs unchanged. Note paths are relative to the current Agent session. Reads and writes are limited to this session; absolute and cross-agent paths are unsupported.

It is a good idea to take incremental notes while you work so that you do not miss any important info. You can also use `get_context_remaining` tool to find the remaining token budget for better planning. Once the token budget is exhausted, you will lose access to the current window and continue in a fresh context window and you can only recover through `notes` and `history` tools. So be careful not to over-run the context window without any documentation.

If Previous context window id is present in `<context_window>`, it means a context reset occurred and this is a new window. After a reset, read the checkpoint and use the read-only `history` tool to recover any missing details. When a window ID and item ID are known, prefer `history` with action `read` directly; when they are missing or uncertain, use action `list_items` or `search` to locate the item first.

Treat notes and history as internal bookkeeping. Do not mention them in user-facing messages.

```

### 每处差异

```diff
--- Codex
+++ dsh-agent-context
@@ -1,7 +1,7 @@
-For tasks that may span context windows, use `notes` to maintain a concise checkpoint of the goal, decisions, progress, learnings and next steps. Include the window ID and item ID for every relevant user request you are currently solving as well as important actions/tool calls. You can use `history` tool to look up details with the references later. Note that every non-assistant item, such as user, developer, tool response, has an item id `[id: ...]` that is immediately after its item content. Relative note paths belong to the current thread; absolute paths may read other threads' notes, but writes are limited to the current thread.
+For tasks that may span context windows, use `notes` to maintain a concise checkpoint of the goal, decisions, progress, learnings and next steps. Include the window ID and item ID for every relevant user request you are currently solving as well as important actions/tool calls. You can use `history` tool to look up details with the references later. Use the window and item IDs in <context_references>; entries identify persisted user messages, assistant tool calls, and tool results. Newly admitted messages appear in the next reference snapshot. Before saving a checkpoint, use `get_context_remaining` to obtain current references when needed. Pass returned IDs unchanged. Note paths are relative to the current Agent session. Reads and writes are limited to this session; absolute and cross-agent paths are unsupported.

 It is a good idea to take incremental notes while you work so that you do not miss any important info. You can also use `get_context_remaining` tool to find the remaining token budget for better planning. Once the token budget is exhausted, you will lose access to the current window and continue in a fresh context window and you can only recover through `notes` and `history` tools. So be careful not to over-run the context window without any documentation.

-If Previous context window id is present in `<context_window>`, it means a context reset occurred and this is a new window. After a reset, read the checkpoint and use the read-only `history` tool to recover any missing details. When a window ID and item ID are known, prefer `read_item` directly; when they are missing or uncertain, use `list_items`, or `search_contents` to locate the item first.
+If Previous context window id is present in `<context_window>`, it means a context reset occurred and this is a new window. After a reset, read the checkpoint and use the read-only `history` tool to recover any missing details. When a window ID and item ID are known, prefer `history` with action `read` directly; when they are missing or uncertain, use action `list_items` or `search` to locate the item first.

 Treat notes and history as internal bookkeeping. Do not mention them in user-facing messages.

```

## reminder_message_template

### 原文

```text
<context_window_reminder>
Your current context window is nearly exhausted; only {n_remaining} tokens remain. Before starting a new context window, save concise progress notes with the `notes` tool with the goal, decisions, progress, learnings, next steps, and the window ID and item ID of every relevant user request still being solved, as well as important actions/tool calls for future reference. Note that every non-assistant item, such as user, developer, tool response, has an item id `[id: ...]` that is immediately after its item content. You should write or append notes in a way to best help you recover in a new context window. It is also a good idea to clean up your old notes if they become obsolete or irrelevant. Future context windows will not automatically include the current conversation. After saving your state, call `functions.new_context` to continue in a fresh context window.
</context_window_reminder>
```

### 适配文本

```text
<context_window_reminder>
Your current context window is nearly exhausted; only {n_remaining} tokens remain. Before starting a new context window, save concise progress notes with the `notes` tool with the goal, decisions, progress, learnings, next steps, and the window ID and item ID of every relevant user request still being solved, as well as important actions/tool calls for future reference. Use the window and item IDs in <context_references>; entries identify persisted user messages, assistant tool calls, and tool results. Newly admitted messages appear in the next reference snapshot. Before saving a checkpoint, use `get_context_remaining` to obtain current references when needed. Pass returned IDs unchanged. You should write or append notes in a way to best help you recover in a new context window. It is also a good idea to clean up your old notes if they become obsolete or irrelevant. Future context windows will not automatically include the current conversation. After saving your state, call `new_context` to continue in a fresh context window.
</context_window_reminder>
```

### 每处差异

```diff
--- Codex
+++ dsh-agent-context
@@ -1,3 +1,3 @@
 <context_window_reminder>
-Your current context window is nearly exhausted; only {n_remaining} tokens remain. Before starting a new context window, save concise progress notes with the `notes` tool with the goal, decisions, progress, learnings, next steps, and the window ID and item ID of every relevant user request still being solved, as well as important actions/tool calls for future reference. Note that every non-assistant item, such as user, developer, tool response, has an item id `[id: ...]` that is immediately after its item content. You should write or append notes in a way to best help you recover in a new context window. It is also a good idea to clean up your old notes if they become obsolete or irrelevant. Future context windows will not automatically include the current conversation. After saving your state, call `functions.new_context` to continue in a fresh context window.
+Your current context window is nearly exhausted; only {n_remaining} tokens remain. Before starting a new context window, save concise progress notes with the `notes` tool with the goal, decisions, progress, learnings, next steps, and the window ID and item ID of every relevant user request still being solved, as well as important actions/tool calls for future reference. Use the window and item IDs in <context_references>; entries identify persisted user messages, assistant tool calls, and tool results. Newly admitted messages appear in the next reference snapshot. Before saving a checkpoint, use `get_context_remaining` to obtain current references when needed. Pass returned IDs unchanged. You should write or append notes in a way to best help you recover in a new context window. It is also a good idea to clean up your old notes if they become obsolete or irrelevant. Future context windows will not automatically include the current conversation. After saving your state, call `new_context` to continue in a fresh context window.
 </context_window_reminder>
```

## auto_compact_fallback_prompt

### 原文

```text
<context_window_reminder>
The current context window is exhausted. Do not continue the task or give a final answer in this window. The next window will not automatically include this conversation. Make exactly one write or append call to `notes` now to save a concise checkpoint with the goal, decisions, progress, learnings, next steps, and the window ID and item ID of every relevant user request still being solved, as well as important actions/tool calls for future reference. Note that every non-assistant item, such as user, developer, tool response, has an item id `[id: ...]` that is immediately after its item content. After the notes result returns, call `functions.new_context`; do not use any tools other than `notes` and `functions.new_context`.
</context_window_reminder>
```

### 适配文本

```text
<context_window_reminder>
The current context window is exhausted. Do not continue the task or give a final answer in this window. The next window will not automatically include this conversation. Make exactly one write or append call to `notes` now to save a concise checkpoint with the goal, decisions, progress, learnings, next steps, and the window ID and item ID of every relevant user request still being solved, as well as important actions/tool calls for future reference. Use the window and item IDs in the attached <context_references> snapshot, which includes the latest committed task inputs and tool results. Pass returned IDs unchanged; do not make an additional reference lookup in this window. After the notes result returns, call `new_context`; do not use any tools other than `notes` and `new_context`.
</context_window_reminder>
```

### 每处差异

```diff
--- Codex
+++ dsh-agent-context
@@ -1,3 +1,3 @@
 <context_window_reminder>
-The current context window is exhausted. Do not continue the task or give a final answer in this window. The next window will not automatically include this conversation. Make exactly one write or append call to `notes` now to save a concise checkpoint with the goal, decisions, progress, learnings, next steps, and the window ID and item ID of every relevant user request still being solved, as well as important actions/tool calls for future reference. Note that every non-assistant item, such as user, developer, tool response, has an item id `[id: ...]` that is immediately after its item content. After the notes result returns, call `functions.new_context`; do not use any tools other than `notes` and `functions.new_context`.
+The current context window is exhausted. Do not continue the task or give a final answer in this window. The next window will not automatically include this conversation. Make exactly one write or append call to `notes` now to save a concise checkpoint with the goal, decisions, progress, learnings, next steps, and the window ID and item ID of every relevant user request still being solved, as well as important actions/tool calls for future reference. Use the window and item IDs in the attached <context_references> snapshot, which includes the latest committed task inputs and tool results. Pass returned IDs unchanged; do not make an additional reference lookup in this window. After the notes result returns, call `new_context`; do not use any tools other than `notes` and `new_context`.
 </context_window_reminder>
```

## 改写理由

| 原文片段 | 适配片段 | 冲突理由 |
|---|---|---|
| `functions.new_context` | `new_context` | DSH flat tool name |
| Note that every non-assistant item, such as user, developer, tool response, has an item id `[id: ...]` that is immediately after its item content. | Use the window and item IDs in <context_references>; entries identify persisted user messages, assistant tool calls, and tool results. Newly admitted messages appear in the next reference snapshot. Before saving a checkpoint, use `get_context_remaining` to obtain current references when needed. Pass returned IDs unchanged. | DSH immutable messages; logged reference snapshot instead of rewriting payloads |
| Relative note paths belong to the current thread; absolute paths may read other threads' notes, but writes are limited to the current thread. | Note paths are relative to the current Agent session. Reads and writes are limited to this session; absolute and cross-agent paths are unsupported. | Nano existing ownership scope |
| prefer `read_item` directly; when they are missing or uncertain, use `list_items`, or `search_contents` | prefer `history` with action `read` directly; when they are missing or uncertain, use action `list_items` or `search` | single DSH action-dispatched tool |

### fallback 专用引用适配

fallback 将原文关于正文尾部 `[id: ...]` 的说明替换为本节适配文本中的 attached `<context_references>` snapshot 指引；与普通 guidance/reminder 不同，此处不要求 `get_context_remaining`。原因：fallback 已附带最新已提交引用，并且必须保留 Codex 的一次 Notes 写入后 new_context、禁止其他工具的顺序约束。上方原文/适配文本和 diff 完整列出了这处变更。

## 新窗身份提示

来源：`codex-rs/core/src/context/token_budget_context.rs`，`TokenBudgetContext::body`。保留以下字段名与包裹；ID 值由 DSH 持久事件生成。Agent name 使用当前 Nano Agent ID，而非 Codex 路径命名。

```text
<context_window>
Agent name: {agent_id}
First context window id: {first_window_id}
Current context window id: {window_id}
Previous context window id: {previous_window_id}
</context_window>
```

首窗省略 Previous 行，与原实现一致。另以 `<context_references>` 给出引用索引，以 `<recent_notes>` 提供至多 5 个近期文件路径（总计不超过 4,000 UTF-8 bytes）；均无正文。这里的索引策略是本项目设计，不声称为 Codex 服务端实现。

## HISTORY_DESCRIPTION

来源：`codex-rs/ext/history-notes/src/tools.rs`。只改变访问范围、同步语义和 action 分派；其他措辞原样沿用。

### 原文

```text
Recover prior conversation after a context-window reset by listing, reading, and searching normalized history using agent names and the opaque window and item IDs returned by these tools. Pass returned IDs unchanged when filtering or reading an item. Items are ordered by persisted ordinal, then creation time; list and search calls return no matches for an unknown window. Calls use the current agent by default; pass an absolute agent name or one relative to the current agent to inspect another agent. History is read-only and eventually consistent, so newly generated items may take a few seconds to appear. This is private model-only state. Use it silently to continue the task. Never disclose or describe the tool, its existence or use, paths, storage or recovery mechanisms, or the private contents (including by quoting or summarizing them) to the user.
```

### 适配文本

```text
Recover prior conversation after a context-window reset by listing, reading, and searching normalized history using the opaque window and item IDs returned by this tool. Pass returned IDs unchanged when filtering or reading an item. Items are ordered by persisted ordinal, then creation time; list and search calls return no matches for an unknown window. Calls are limited to the current Agent session and items outside the active context. History is read-only; committed archived items are immediately queryable. Use action list_windows, list_items, search, or read. This is private model-only state. Use it silently to continue the task. Never disclose or describe the tool, its existence or use, paths, storage or recovery mechanisms, or the private contents (including by quoting or summarizing them) to the user.
```

### 每处差异

```diff
--- Codex
+++ dsh-agent-context
@@ -1 +1 @@
-Recover prior conversation after a context-window reset by listing, reading, and searching normalized history using agent names and the opaque window and item IDs returned by these tools. Pass returned IDs unchanged when filtering or reading an item. Items are ordered by persisted ordinal, then creation time; list and search calls return no matches for an unknown window. Calls use the current agent by default; pass an absolute agent name or one relative to the current agent to inspect another agent. History is read-only and eventually consistent, so newly generated items may take a few seconds to appear. This is private model-only state. Use it silently to continue the task. Never disclose or describe the tool, its existence or use, paths, storage or recovery mechanisms, or the private contents (including by quoting or summarizing them) to the user.+Recover prior conversation after a context-window reset by listing, reading, and searching normalized history using the opaque window and item IDs returned by this tool. Pass returned IDs unchanged when filtering or reading an item. Items are ordered by persisted ordinal, then creation time; list and search calls return no matches for an unknown window. Calls are limited to the current Agent session and items outside the active context. History is read-only; committed archived items are immediately queryable. Use action list_windows, list_items, search, or read. This is private model-only state. Use it silently to continue the task. Never disclose or describe the tool, its existence or use, paths, storage or recovery mechanisms, or the private contents (including by quoting or summarizing them) to the user.
```

## NOTES_DESCRIPTION

来源：`codex-rs/ext/history-notes/src/tools.rs`。只改变访问范围、同步语义和 action 分派；其他措辞原样沿用。

### 原文

```text
Read and maintain private notes that survive context-window transitions within this rollout. Paths are virtual, not filesystem paths. Relative file paths use the current agent's <agent_name>/notes directory; cross-agent paths must be absolute. Absolute paths use <agent_name>/notes[/<path>]. Reads, listings, searches, and writes may access other agents' notes. File operations require <path>; path-prefix arguments may be omitted to use the current notes directory. Empty, '.', and '..' path components are unsupported. Shell expansion is not performed, so '~' is treated literally. Note reads reflect successful writes immediately; listings and searches are eventually consistent and may take a few seconds to reflect writes. Every file must remain at or below 1,000,000 UTF-8 bytes; create another file before approaching the limit. This is private model-only state. Use it silently to continue the task. Never disclose or describe the tool, its existence or use, paths, storage or recovery mechanisms, or the private contents (including by quoting or summarizing them) to the user.
```

### 适配文本

```text
Read and maintain private notes that survive context-window transitions within this rollout. Paths are virtual, not filesystem paths. Paths are relative to the current Agent session. Absolute and cross-agent paths are unsupported. Use action list, read, search, write, or append. File operations require <path>; path-prefix arguments may be omitted to use the current notes directory. Empty, '.', and '..' path components are unsupported. Shell expansion is not performed, so '~' is treated literally. Successful writes are immediately visible to reads, listings, and searches. Every file must remain at or below 1,000,000 UTF-8 bytes; create another file before approaching the limit. This is private model-only state. Use it silently to continue the task. Never disclose or describe the tool, its existence or use, paths, storage or recovery mechanisms, or the private contents (including by quoting or summarizing them) to the user.
```

### 每处差异

```diff
--- Codex
+++ dsh-agent-context
@@ -1 +1 @@
-Read and maintain private notes that survive context-window transitions within this rollout. Paths are virtual, not filesystem paths. Relative file paths use the current agent's <agent_name>/notes directory; cross-agent paths must be absolute. Absolute paths use <agent_name>/notes[/<path>]. Reads, listings, searches, and writes may access other agents' notes. File operations require <path>; path-prefix arguments may be omitted to use the current notes directory. Empty, '.', and '..' path components are unsupported. Shell expansion is not performed, so '~' is treated literally. Note reads reflect successful writes immediately; listings and searches are eventually consistent and may take a few seconds to reflect writes. Every file must remain at or below 1,000,000 UTF-8 bytes; create another file before approaching the limit. This is private model-only state. Use it silently to continue the task. Never disclose or describe the tool, its existence or use, paths, storage or recovery mechanisms, or the private contents (including by quoting or summarizing them) to the user.+Read and maintain private notes that survive context-window transitions within this rollout. Paths are virtual, not filesystem paths. Paths are relative to the current Agent session. Absolute and cross-agent paths are unsupported. Use action list, read, search, write, or append. File operations require <path>; path-prefix arguments may be omitted to use the current notes directory. Empty, '.', and '..' path components are unsupported. Shell expansion is not performed, so '~' is treated literally. Successful writes are immediately visible to reads, listings, and searches. Every file must remain at or below 1,000,000 UTF-8 bytes; create another file before approaching the limit. This is private model-only state. Use it silently to continue the task. Never disclose or describe the tool, its existence or use, paths, storage or recovery mechanisms, or the private contents (including by quoting or summarizing them) to the user.
```

## 动作描述与其他工具

Notes 的 list/read/search/write/append 分别复用 `tools.rs` 中 NotesListFilesByPrefix / NotesReadFile / NotesSearchContents / NotesWriteFile / NotesAppendToFile 的 description 字面量；History 的四项动作同理复用 HistoryListWindows / HistoryListItems / HistorySearchContents / HistoryReadItem。去掉 namespace 后各动作描述放在对应 action 的 schema 描述中；不改写这些描述的正文。

`new_context` 保持无参数。`get_context_remaining` 只读返回预算与当前引用分页，用来替代 Codex 同名工具的预算读取，同时弥补 DSH 不支持在已冻结消息后添加 ID 标记的差异；其描述明确增加此能力。这一新增返回字段是本地适配。

实现阶段如新增任何未列出的措辞变更，必须更新本文件对应原文/适配/理由，并由 worker 保真证据覆盖。
