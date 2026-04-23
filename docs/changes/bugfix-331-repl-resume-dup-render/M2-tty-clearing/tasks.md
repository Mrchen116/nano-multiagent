# M2: TTY Multi-Line Assistant Output Clearing

## 目标

修复 `emit_external_text` 在多行 assistant 回复场景下，旧内容残留在屏幕上方的问题。

## 根因

`_clear_interactive_line_locked` 使用 `\x1b[J`（Erase in Display from cursor to bottom），不清除光标上方的行。当 assistant 回复占多行时，再次输出相同/更新的完整 delta 会在上方留下残留。

## Roadpoints

### RP1: 跟踪上次输出行数

**文件**: `src/coding_cli/input/repl_input.py`

- 新增 module-level `_LAST_EXTERNAL_TEXT_LINES: int = 0`（受 `_RENDER_LOCK` 保护）
- 新增 `_count_terminal_lines(text: str, width: int) -> int`  helper

### RP2: 多行清除逻辑

**文件**: `src/coding_cli/input/repl_input.py`

- `emit_external_text`: 输出新文本前，若 `_LAST_EXTERNAL_TEXT_LINES > 0`
  - 发送 N 次 `\x1b[A\x1b[2K` 逐行上移清除
  - 行数基于 `os.get_terminal_size().columns` 和 `\r\n` 换行计算
  - 非 TTY 或取不到宽度时 fallback 到不清除
- 输出后更新 `_LAST_EXTERNAL_TEXT_LINES = new_lines`

**验收**:
- 5 行 assistant 回复再次 emit 时旧 5 行完全清除
- 非 TTY 环境行为不变
