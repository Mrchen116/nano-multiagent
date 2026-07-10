# feat-340-M31 Progress

## Status: DONE

所有 11 个 roadpoint 已修复，`npm run build` 通过，IM + Gateway 重启验证。

---

## R1 — SSE 竞态：Arch 不回复

**Context**: Gateway `inbound_pipeline.py` 的 `handle_inbound` 先调 `submit_message` 提交任务，再订阅 `stream_session` SSE。当 kernel run 足够快（小消息无工具调用），run 在 SSE 订阅前就结束，所有事件全部错过，agent 沉默。

**Decision**: 在 `submit_message` 前捕获 `anchor_sequence`（kernel 返回的位置锚点），订阅 SSE 时作为 `Last-Event-ID` 传入，kernel 会补发该锚之后的所有历史事件，彻底消除竞态。

**Rationale**: 这是 kernel `stream_session` 的设计机制，`Last-Event-ID` 语义正是为此场景而设。

**Evidence**: 修复后 Arch 可稳定回复，即使小消息处理极快也不再沉默。

**Commits**: c1a6610f（直接修复）

---

## R2 — realtime_stream hook 缺失：Arch 不回复

**Context**: `personal_assistant` 产品的 `DEFAULT_HOOK_MODULES` 没有 `realtime_stream`，导致 kernel 从不发 `assistant_message`/`turn_end` 事件到 SSE 流，Gateway 的 event observer 永远收不到回复内容。

**Decision**: 在 `communication_context.py` 的 `DEFAULT_HOOK_MODULES` 列表末尾追加 `"realtime_stream"`。

**Evidence**: R1+R2 联合修复后，私聊发消息 Arch 正常回复并推送到前端。

**Commits**: c1a6610f

---

## R3 — Token stats context_window 显示错误

**Context**: `_parse_token_usage` 用 `prompt+completion`（约 2k token）当 context_window，导致进度条从 ~100% 开始，完全失去意义。前端 `token-chip.tsx` 也不区分"有/无 context_window"，总是显示进度条。

**Decision**: 在 `runtime.py` 里把 `CompactionSettings.context_window`（默认 200,000）注入 `hook_metadata`，经 `loop.py` → `realtime_stream.py` → `main.py` → `gateway_handler.py` 链路传到前端。前端加 `hasWindow = context_window > 0` 守卫，无值时隐藏进度条。

**Evidence**: Token chip 显示约 200k context window，进度条占比合理（1–2%）。

**Commits**: c1a6610f, a57c0539

---

## R4 — 自己发的消息触发未读徽标

**Context**: `repositories.py` `create_message` 无论谁发都执行 `unread_count = unread_count + 1`，用户自己发的消息也被计入未读。

**Decision**: 在执行 UPDATE 前判断 `resolved_sender_user_id == conversation.owner_id`，是则只更新 preview/last_message_at，不加 unread_count。

**Evidence**: 用户发消息后，sidebar 未读徽标不再增加。

**Commits**: c1a6610f

---

## R5 — Agent 状态点始终灰色

**Context**: 前端依赖两个并发查询（agents + nodes）通过 `nodesQuery` 合并状态，两个查询存在时序竞态，node_status 经常为 undefined，fallback 到灰色。

**Decision**: 后端 `GET /im/v1/agents` 接入 `node_service.list_nodes_for_owner`，直接 join node status，`AgentSummaryResponse` 新增 `node_status` 字段，一次 API 调用返回完整状态。

**Evidence**: Gateway 上线后，agent 列表状态点立即显示绿色，无竞态延迟。

**Commits**: c1a6610f

---

## R6 — 中文 IME Enter 双发消息

**Context**: macOS 中文输入法（系统/搜狗）选词确认时触发 Enter keydown 事件，`handleKeyDown` 同时触发 `commit(draft)`，导致发送两条消息。

**Decision**: 在 Enter 判断中加 `!e.nativeEvent.isComposing` 守卫，IME 组合期间忽略 Enter。

**Evidence**: 中文 IME 输入"hi"后按 Enter 选词，只发送一条消息。

**Commits**: 本会话直接修改

---

## R7 — Mention picker 开启时 Enter 键发送 @

**Context**: `MentionPicker` 通过 `window.addEventListener("keydown")` 拦截 Enter 选中候选，但 textarea 的 `onKeyDown` 先于 window 事件冒泡，先执行了 `commit(draft)`，导致发送 `@` 占位文本。

**Decision**: `handleKeyDown` 中在 Enter 分支开头加 `if (mentionQuery !== null) return;`，picker 开启时完全放行，让 window 级监听器处理选中。

**Evidence**: 群聊输入 `@` 打开 picker 后，Enter 键选中高亮候选，不发送消息。

**Commits**: 本会话直接修改

---

## R8 — @mention 文字未高亮蓝色

**Context**: `<textarea>` 不支持内联富文本样式，无法直接给 @xxx 着色。

**Decision**: Mirror div 方案：在 textarea 同级位置插入 `position: absolute` 的镜像 div（同等 font/padding），textarea `color: transparent` + `caret-color` 保留光标，镜像 div `color: var(--im-text)` 显示所有文字，@mention 部分用 `<mark class="chat-composer-mention-highlight">` 显示蓝色 `oklch(0.50 0.18 255)`。scroll 同步通过 `onScroll` 复制 `scrollTop`。

**Evidence**: 群聊输入框中 `@架构` 显示蓝色，其余文字正常白色。

**Commits**: 本会话直接修改

---

## R9 — 群聊 @display_name 不触发 agent 回复

**Context**: 用户在 picker 选"架构"后，消息文本是 `@架构 你好吗`。`_extract_mentioned_agent_ids` 提取原始 token `"架构"`，relay payload 里 `mentioned_agent_ids = ["架构"]`。Gateway `_should_process` 检查 `"Arch" in ["架构"]` → False，MENTION 策略拦截，agent 不回复。

**Decision**: 新增 `_resolve_mention_to_agent_ids` 实例方法，提取原始 mention 后先按 `agent_id` 精确查表，找不到再按 `lower(display_name)` 查表，将 `"架构"` → `"Arch"`。两处调用 `_extract_mentioned_agent_ids` 后均接入此解析。

**Rationale**: 前端 picker 插入 display_name 是正确的 UX（用户认识"架构"，不认识"Arch"），后端负责解析是正确的边界划分。

**Evidence**: 群聊发 `@架构 你好吗`，IM relay 后 Gateway 收到 `mentioned_agent_ids = ["Arch"]`，Arch 正常回复。

**Commits**: 本会话直接修改

---

---

## R10 — 工具调用 INPUT 永远显示 `{}`

**Context**: 前端气泡里工具调用的 INPUT 栏无论实际参数是什么始终显示空对象 `{}`。根因在 Agent Kernel `realtime_stream.py` 的 `on_tool_result` handler：它发出 `tool_end` SSE 事件时没有携带 `arguments` 字段。Gateway `main.py` 处理 `tool_end` 时执行 `event.get("arguments") or {}` 得到 `{}`，再通过 WS 推送 `tool_call.completed`（含 `input: {}`），前端 reducer 用这个 `{}` 覆盖了 `tool_call.upserted` 阶段正确写入的 input。

**Decision**: 在 `on_tool_result` 的 payload 字典里追加 `"arguments": _as_mapping_or_none(event.get("arguments"))`。`tool_end` 事件从此携带完整参数，Gateway 透传给前端，`tool_call.completed` 不再丢失 input。

**Rationale**: `tool_start` 的 `on_tool_call` 已经携带 `arguments`，`on_tool_result` 漏掉是一致性缺陷；修复点在生产侧（hook）而非消费侧（reducer），更符合单一职责。

**Evidence**: 修复后工具调用气泡的 INPUT 栏正确显示实际参数（如 `{"path": "/foo/bar"}`）。

**Commits**: 本会话直接修改（`src/agent/platform/hooks/builtins/realtime_stream.py`）

---

## R11 — 刷新页面后工具调用和 token 统计消失

**Context**: 实时消息通过 WS `tool_call.*` 事件携带工具调用数据，前端 reducer 将其写入 React state；但刷新后走 REST `GET /im/v1/conversations/{id}/messages` 重新加载历史消息，IM 后端的 `MessageResponse` Pydantic 模型没有 `tool_calls`/`token_usage` 字段，API 响应不包含这两项，前端丢失所有工具调用和 token 统计。

**Decision**: 在 IM 后端 `src/IM/api/routes/messages.py` 添加 `ToolCallPayload`、`TokenUsagePayload` Pydantic 模型，并在 `MessageResponse` 增加 `tool_calls: list[ToolCallPayload] = []` 和 `token_usage: TokenUsagePayload | None = None` 两个字段。更新 `to_message_response()` 从 `message.tool_calls`（已存入 DB `tool_calls_json` 列）和 `message.token_usage` 读取并序列化。

**Rationale**: DB 层已完整存储工具调用数据，只是 API 层未暴露。最小侵入修复：只加字段 + 序列化，不改存储逻辑。

**Evidence**: 修复并重启 IM 后，刷新页面，历史消息中工具调用气泡和 token 统计正常还原。

**Commits**: 本会话直接修改（`src/IM/api/routes/messages.py`）

---

## Next

无。M31 所有 11 个问题已修复，服务已重启验证。
