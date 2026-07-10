# 实现记录

## RP1: 实时事件回调

**改动**: `src/coding_cli/session_stream.py`

```python
def drain_run(
    self, run_id: str, *,
    timeout: float = 0.5,
    terminal_timeout: float = 120.0,
    on_other: Callable[[dict[str, Any]], None] | None = None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
```

`on_event` 在匹配到目标 `run_id` 的事件时立即调用，早于 `events.append(evt)`。这使得 `_send_message_via_sse` 可以在事件到达的第一时间就将其渲染到终端，而不是等 `drain_run` 返回完整列表后再批量处理。

**验证**: 集成测试模拟 3-turn agent loop，确认每个 `assistant_message` 和 `tool_start`/`tool_end` 都在对应的事件到达时立即输出。

## RP2: ANSI 顺序打印替代 Rich Live

**改动**: `src/coding_cli/commands.py` — `_send_message_via_sse` TTY 分支

原始方案（Rich Live）:
```python
renderer = ReplLiveRenderer(out)
with renderer:
    events = reader.drain_run(...)
    for event in events:
        if event_name == "assistant_message":
            renderer.on_text_delta(event.get("content", ""))
        elif event_name in ("tool_start", "tool_end"):
            renderer.on_tool_event(mapped_name, event)
```

新方案（ANSI 顺序打印）:
```python
_thinking_shown = [True]
print("⠋ Thinking...", end="\r", file=out, flush=True)

def _erase_thinking():
    if _thinking_shown[0]:
        print("\r\033[K", end="", file=out, flush=True)
        _thinking_shown[0] = False

def _on_run_event_tty(event):
    _erase_thinking()
    event_name = event.get("event")
    if event_name == "assistant_message":
        ...  # 逐行打印 > content
    elif event_name == "tool_start":
        print(format_tool_running(name), end="\r", file=out, flush=True)
    elif event_name == "tool_end":
        print(f"\r\033[K{format_tool_done(name, duration_ms)}", file=out, flush=True)

events = reader.drain_run(..., on_event=_on_run_event_tty)
```

关键决策：
- 不用 `rich.live.Live`：它的 in-place update 模型无法支持"文本和工具按真实时序穿插"。文字一旦进入 live area 就会和工具行分离。
- 不用 `console.print()` above live：已验证 `console.print()` 可以在 live active 时打印到上方，但工具行仍固定在底部 live area，无法穿插。
- ANSI `\r\033[K` 是最简方案：`` 回车到行首，`\033[K` (EL0) 擦除到行尾，然后直接 print。没有 cursor tracking 问题，没有高度限制。

**中间探索（已保留代码但 TTY 路径未使用）**:
- `ReplLiveRenderer.print_above_live()`: 使用 `console.print()` 在 live active 时打印到上方，然后 `live.refresh()`。
- `ReplLiveRenderer.on_assistant_message()`: replace 语义（非 merge），用于在 live area 内替换整段文本。
- 这些方法留在 `repl_live.py` 中，因为 `ReplLiveRenderer` 仍被 import，且未来非 TTY 或 block-based 渲染可能用到。

**验证**:
- termwright 真实 TTY 验证：两轮对话确认文字与工具标记严格穿插。
- Python 模拟 TTY 验证：7 条断言确认 3-turn 场景下时序正确、消息不丢失。

## RP3: 尾部空行过滤

**改动**: `src/coding_cli/commands.py` — `_on_run_event_tty`

```python
lines = content.split("\n")
while lines and lines[-1] == "":
    lines.pop()
for line in lines:
    print(f"> {line}", file=out)
```

**决策**: 只去掉尾部空字符串（由 LLM 尾部 `\n` 产生），保留中间空字符串（LLM 故意的段落分隔 `\n\n`）。

**验证**:
- `"hello\n\nworld\n"` → `["hello", "", "world"]` → 保留中间空行
- `"hello\n"` → `["hello"]` → 去掉尾部空行
- `"hello\n\n"` → `["hello"]` → 去掉多个尾部空行

## 清理：删除 repl_live.py 中未使用的中间代码

**RP4**: 删除 `ReplLiveRenderer.on_assistant_message()`、`print_above_live()` 和 `ReplBlockRenderer.on_assistant_message()`。这些方法是探索 Rich Live 混合方案时的中间产物，最终 TTY 路径完全未使用。

**验证**: 删除后 `tests/unit/test_repl_live.py` 9 个用例全部通过，无破坏。

## 回归测试

```bash
pytest -xvs tests/unit/test_repl_live.py tests/unit/test_session_stream.py
# 17 passed
```

## 相关 Commit

- `commands.py`: ANSI 顺序打印 + 空行过滤
- `session_stream.py`: `drain_run` 新增 `on_event` 回调
- `repl_live.py`: 删除未使用的 `on_assistant_message` / `print_above_live`
