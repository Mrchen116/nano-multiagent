---
name: termwright
description: Drive interactive TUI applications (especially coding_cli REPL) via termwright daemon for automated testing and acceptance. Handles PTY race conditions, base64 raw input, screen capture, and idle waiting.
license: MIT
compatibility: Requires termwright CLI, Rust 1.85+, macOS/Linux.
metadata:
  author: claude
  version: "1.0"
---

Use termwright to automate interactive terminal applications (like coding_cli REPL) in a headless PTY. This skill encapsulates hard-won best practices around PTY race conditions, input synchronization, and screen capture.

---

## Installation

```bash
cargo install termwright
brew install socat jq    # recommended for shell scripting
```

Verify:
```bash
termwright --help
termwright run -- ls -la
```

---

## Daemon lifecycle

### Start daemon
```bash
SOCK="/tmp/coding-cli.sock"
rm -f "$SOCK"

termwright daemon \
  --socket "$SOCK" \
  --cols 120 \
  --rows 40 \
  -- \
  bash -c 'PYTHONPATH=/absolute/path/to/repo/src python3 -m coding_cli.main --mode managed --model volcanoArk:doubao-seed-2-0-code-preview-260215 2>&1' &

daemon_pid=$!

# Wait for socket
for i in $(seq 1 100); do
  if [ -S "$SOCK" ]; then break; fi
  sleep 0.05
done
```

**Important**: Use absolute `PYTHONPATH` because daemon working dir may not be the repo root. If using managed mode with `--model`, always add explicit `--mode managed`.

### Stop daemon
```bash
termwright exec --socket "$SOCK" --method close
wait $daemon_pid 2>/dev/null
rm -f "$SOCK"
```

---

## Input strategy: choose the right method for the scene

termwright exposes `type`, `press`, `hotkey`, and `raw`. They are **not** interchangeable for every scene.

### Text submission (chat / REPL prompt)

**Risk**: because `type` and `press` are separate RPCs, under certain daemon initialization timings the `\r` (Enter) can be processed before the preceding text, causing an empty submission that gets ignored. This is a PTY-level scheduling race between two independent socket writes.

**Recommended**: use `raw` to send text + newline in a **single atomic write**:
```bash
python3 -c "import base64; print(base64.b64encode(b'hi\n').decode())"
# -> aGkK

termwright exec --socket "$SOCK" --method raw --params '{"bytes_base64":"aGkK"}'
```

If you **must** use `type` + `press Enter` (e.g. you need to watch partial typing on screen), add synchronization between the two calls:
- either `wait_for_text '{"text":"hi","timeout_ms":3000}'` after `type`
- or a generous `sleep 0.5` (not guaranteed, but usually enough once the daemon is warm)

### Menu / selection navigation

Arrow keys, Tab, Escape, and other control keys **must** use `press` or `hotkey`. This is unaffected by the race above because there is no preceding `type` payload that needs to arrive before the control key.

```bash
# Move up in a list
tw press '{"key":"Up"}'
# Confirm selection
tw press '{"key":"Enter"}'

# Cancel with Ctrl+C
tw hotkey '{"ctrl":true,"ch":"c"}'
```

### Quick reference by intent

| Intent | Method | Why |
|--------|--------|-----|
| Send a full chat message | `raw` with `\n` | Single atomic write; avoids PTY race |
| Type without submitting | `type` | To observe incremental screen changes |
| Press Enter / arrows / Tab | `press` | Native escape-sequence injection |
| Ctrl/Alt combos | `hotkey` | Accurate modifier encoding |

---

## Helper function

Define this once per session:
```bash
tw() {
  termwright exec --socket "$SOCK" --method "$1" --params "${2:-null}"
}
```

---

## Common interaction loop

```bash
# 1. Send text + newline atomically
MESSAGE="hello"
B64=$(python3 -c "import base64; print(base64.b64encode(b'${MESSAGE}\n').decode())")
tw raw "{\"bytes_base64\":\"$B64\"}"

# 2. Wait for output to stabilize
tw wait_for_idle '{"idle_ms":3000,"timeout_ms":45000}'

# 3. Capture current screen
tw screen '{"format":"text"}' | jq -r '.result'
```

Repeat 1-3 for each turn of conversation.

---

## Full multi-turn example

```bash
export PATH="$HOME/.cargo/bin:$PATH"
SOCK="/tmp/coding-cli.sock"
rm -f "$SOCK"

termwright daemon \
  --socket "$SOCK" \
  --cols 120 \
  --rows 40 \
  -- \
  bash -c 'PYTHONPATH=/Users/czj/Repos/nano-multiagent/src python3 -m coding_cli.main --mode managed --model volcanoArk:doubao-seed-2-0-code-preview-260215 2>&1' &
daemon_pid=$!

for i in $(seq 1 100); do
  if [ -S "$SOCK" ]; then break; fi
  sleep 0.05
done

tw() { termwright exec --socket "$SOCK" --method "$1" --params "${2:-null}"; }

# Wait for first prompt
tw wait_for_idle '{"idle_ms":800,"timeout_ms":15000}' >/dev/null

# Turn 1
tw raw '{"bytes_base64":"aGkK"}' >/dev/null
tw wait_for_idle '{"idle_ms":3000,"timeout_ms":45000}' >/dev/null
tw screen '{"format":"text"}' | jq -r '.result'

# Turn 2
tw raw '{"bytes_base64":"6K+36L6T5YWl5L2g55So5L2g55qE5L2g55So5ZCN44CCCg=="}' >/dev/null
tw wait_for_idle '{"idle_ms":3000,"timeout_ms":45000}' >/dev/null
tw screen '{"format":"text"}' | jq -r '.result'

# Cleanup
tw close
wait $daemon_pid 2>/dev/null
rm -f "$SOCK"
```

---

## Key methods reference

| Method | Purpose | Example params |
|--------|---------|----------------|
| `status` | Check if child process exited | `null` |
| `screen` | Get current terminal content | `'{"format":"text"}'` |
| `raw` | Send raw bytes (best for text+enter) | `'{"bytes_base64":"aGkK"}'` |
| `type` | Type text without newline | `'{"text":"hello"}'` |
| `press` | Press a single key | `'{"key":"Enter"}'` |
| `hotkey` | Press a key combo | `'{"ctrl":true,"ch":"c"}'` |
| `wait_for_idle` | Wait until screen stops changing | `'{"idle_ms":3000,"timeout_ms":45000}'` |
| `wait_for_text` | Wait until text appears on screen | `'{"text":"Assistant:","timeout_ms":30000}'` |
| `close` | Kill daemon and child process | `null` |

---

## Troubleshooting

### 1. Missing LLM reply / "Queued message #1" but no Assistant text
- Check if port 8000 is already in use by another coding_cli instance.
- Switch managed API to a different port with `--base-url http://127.0.0.1:<free_port>`.

### 2. `type` + `press Enter` loses the typed text
- This is a PTY-level race between two independent socket writes. The `\r` may occasionally be read by the application before the preceding characters, resulting in an empty submission.
- **Fix for chat/REPL**: use `raw` to send text + newline atomically.
- **Fix for menus/selections**: `press` for arrows and `press` for Enter is fine, because there is no preceding `type` payload that needs ordering protection.

### 3. Chinese characters show spaces between them on screen
- This is a vt100 display-width rendering quirk inside termwright. The actual bytes sent/received are correct.

### 4. "managed startup LLM options require --mode managed"
- Add explicit `--mode managed` to the coding_cli command line.

### 5. "No module named 'coding_cli'"
- Use absolute `PYTHONPATH=/Users/.../src` instead of relative `PYTHONPATH=src`.
