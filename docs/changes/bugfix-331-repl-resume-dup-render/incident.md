# Incident: REPL resume 缺失历史 + 回答重复输出

## 现象

### 问题 1：REPL resume 后看不到历史

启动命令：

```bash
PYTHONPATH=src python3 -m coding_cli.main \
  --model volcanoArk:doubao-seed-2-0-code-preview-260215 \
  --resume sess_fbbb8459101d2090
```

resume 后 REPL 直接显示空白提示符：

```
[sess_fbbb8459101d2090]> hi
```

用户无法看到之前的对话内容，只能凭记忆继续。虽然 LLM 的 prompt tokens 高达 10908（说明历史已加载进模型上下文），但 CLI 界面没有向用户展示任何历史消息。

### 问题 2：回答不停重复

同一 assistant 回复被打印多次，且残留旧行：

```
> 我们刚才在聊 `nano-multiagent` 项目的 README。我给你总结了这个多智能体系统的核心启动流程、主要功能和 CLI 命令。
                                                                                                                 >
> 我们刚才在聊 `nano-multiagent` 项目的 README。我给你总结了这个多智能体系统的核心启动流程、主要功能和 CLI 命令。
                                                                                                                 >
                                                                                                                   > 具体来说：
```

- 第 1 行和第 2 行是**完全相同的整句**
- 第 3 行开始追加新内容
- 每行残留 `>` 和大量空格，终端渲染混乱

---

## 根因分析（RCA）

### 问题 1：REPL resume 不加载历史

**代码位置**：`src/coding_cli/commands.py:_run_repl()`

```python
def _run_repl(*, args: argparse.Namespace, ...):
    active_session_id = _resolve_initial_session_id(args)  # --resume 值
    # ... 直接进入输入循环，没有任何加载/打印历史的逻辑
```

resume 时 `_run_repl` 仅把 `active_session_id` 设为 CLI 状态，**没有**：
1. 向服务器请求该 session 的历史消息
2. 在 REPL 界面打印任何历史记录

用户只有手动输入 `/history` 才能看到之前的内容。LLM 侧虽然通过 `AgentRuntime._session_histories` 加载了完整历史（prompt=10908 证实），但产品层的 CLI 没有同步展示。

**与 CC 的差异**：Claude Code 启动时会自动渲染 session 的完整历史到终端，让用户立即回到上下文。

---

### 问题 2：回答重复输出

#### 根因链

**1. `AgentLoop` 发送完整文本而非增量 delta**

`src/agent/core/agent/loop.py:244-248`

```python
await self._dispatch_observe(
    "message_update",
    _with_optional_run_id({
        "message_id": assistant_message.message_id,
        "delta": assistant_message.content,   # <-- 完整文本，不是增量
    }, run_id=run_id),
    active_hook_ctx,
)
```

`message_update` hook 的 `delta` 字段是 `assistant_message.content`（生成完毕后的完整内容），而不是生成过程中的增量片段。

**2. `EventStreamHub` 每次 poll 返回 history 切片**

`src/agent/platform/http_api/sse.py:119`

```python
for event in history[-max_events:]:
    yield event
```

`/v1/sessions/{id}/events` 每次 poll 都返回最近 `max_events` 个历史事件。同一 text_delta 事件可能在多次 poll 中重复出现。

**3. `text_delta` 无 fallback dedupe**

`src/coding_cli/events/event_pipeline.py:11-17`

```python
_REPLAY_FALLBACK_DEDUPE_EVENTS = {
    "run_status",
    "tool_start",
    "tool_end",
    "tool_exec_started",
    "tool_exec_running",
    ...
}
# text_delta 不在此集合中
```

`text_delta` 不在 fallback dedupe 列表里。如果 SSE event_id 因传输/解析问题不可靠，客户端无法通过语义指纹去重。

**4. `emit_external_text` 多行清除不完整**

`src/coding_cli/input/repl_input.py:578-580`

```python
def _clear_interactive_line_locked(*, out: TextIO) -> None:
    out.write("\r\x1b[K")
    out.write("\x1b[J")
```

`\x1b[J`（Erase in Display）只清除**从当前行到屏幕底部**，不清除上方已输出的多行 assistant 回复。当 `emit_external_text` 被再次调用输出新的（或相同的）完整 delta 时，旧的多行文本残留在屏幕上方，形成"重复叠加"效果。

**5. `preview_writer(delta)` 输出完整文本而非增量**

`src/coding_cli/events/repl_events.py:236-241`

```python
if event_name == "text_delta":
    delta = data.get("delta")
    if isinstance(delta, str):
        updated_text = merge_text_delta(updated_text, delta)
        if emit_preview and delta:
            if preview_writer is not None:
                preview_writer(delta)   # <-- 传入完整 delta，不是增量
```

即使 delta 是完整文本，`preview_writer` 也直接输出完整内容。结合第 4 点的清除缺陷，多次输出相同完整文本就会在屏幕上留下多份残留。

#### 为什么看到"完全相同的整句重复"

综合以上因素，最可能的触发路径：

1. LLM 生成回复 → `AgentLoop` dispatch 一次 `message_update`（delta=完整文本）
2. `realtime_stream` publish 一个 `text_delta` 事件到 `EventStreamHub`
3. 客户端第 1 次 poll → 收到该 text_delta → `preview_writer` 输出完整句子
4. 客户端第 2 次 poll → `history[-max_events:]` 再次包含该 text_delta
   - event_id dedupe 理论上应跳过，但如果存在 event_id 解析/传输问题，或 hub 中确实存在多个内容相同但 event_id 不同的 text_delta（hook 被多次 dispatch），则会被重复处理
   - `emit_external_text` 的 `\x1b[J` 不清除上方已输出的多行内容，旧句子残留
5. 客户端第 3 次 poll → 收到新的 text_delta（内容=句子+新内容）→ 再次输出完整长文本

最终屏幕上呈现：旧句子残留 + 新句子覆盖下方，形成"重复"视觉。

---

## 影响范围

| 场景 | 影响 |
|------|------|
| `--resume` 启动 REPL | 用户面对空白提示符，无法回忆上下文 |
| 长回复（多行） | 重复输出严重，终端可读性极差 |
| 短回复（单行） | `\r` 回车行首可覆盖，重复不明显 |
| 非 TTY 输出（pipe/文件） | `_emit_plain_repl_block` 直接换行输出，重复同样严重 |

---

## 修复方向

### 修复 1：REPL resume 加载并打印历史

在 `_run_repl()` 中，当 `active_session_id` 不为空时：

```python
if active_session_id:
    # 拉取历史并打印
    history_payload = client.get_session_history(session_id=active_session_id, limit=20)
    _print_repl_history(out=out, messages=history_payload.get("messages", []))
```

- 需要新增 `GET /v1/sessions/{id}/history` HTTP API（或复用现有列表接口）
- 打印格式与 `/history` REPL 命令保持一致

### 修复 2：让 text_delta 携带增量内容

**方案 A（推荐）：AgentLoop 在生成过程中发送增量**

将 `AgentLoop.run()` 改为支持 streaming generate，在每次收到 token chunk 时 dispatch `message_update`，delta 为实际增量。

**方案 B（兜底）：服务端只保留最新 text_delta**

`EventStreamHub.publish()` 中对同一 `(run_id, message_id)` 的 text_delta 做覆盖，只保留最新一个。

**方案 C（客户端渲染修复）**：

在 `consume_async_run_events` 中计算增量再输出：

```python
previous_text = assistant_text
updated_text = merge_text_delta(updated_text, delta)
incremental = updated_text[len(previous_text):] if updated_text.startswith(previous_text) else delta
preview_writer(incremental)
```

### 修复 3：增强 TTY 多行清除

`emit_external_text` 在输出长文本前，使用终端滚动或保存/恢复光标位置，确保旧的多行内容被正确清除。

### 修复 4：text_delta 加入 fallback dedupe

```python
_REPLAY_FALLBACK_DEDUPE_EVENTS = {
    ...,
    "text_delta",   # 新增
}
```

语义指纹可基于 `(run_id, message_id, delta[:80])` 生成，防止同一内容被重复渲染。

---

## 验证建议

1. **resume 历史**：`--resume sess_xxx` 后应自动打印最近 10-20 条消息
2. **重复输出**：发送 "hello" 到长回复场景，终端不应出现相同整句多次
3. **event dedupe**：单元测试验证同一 event_id 的 text_delta 在多次 poll 中只被处理一次
4. **增量渲染**：如果实现方案 A，验证 preview_writer 每次只收到增量字符
