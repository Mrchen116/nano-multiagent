#!/usr/bin/env bash
set -uo pipefail

# E2E test for REPL resume + no duplicate output (Bugfix-331)
# Two-phase: create session + turn, then resume and verify history + no dupes

REPO="/Users/czj/Repos/nano-multiagent"
SOCK="/tmp/coding-cli-test.sock"
export PATH="$HOME/.cargo/bin:$PATH"

# Cleanup previous runs
rm -f "$SOCK"

# Helper
 tw() {
  termwright exec --socket "$SOCK" --method "$1" --params "${2:-null}"
}

echo "=== PHASE 1: Start fresh REPL, create session, send message ==="
termwright daemon \
  --socket "$SOCK" \
  --cols 120 \
  --rows 40 \
  -- \
  bash -c "cd $REPO && PYTHONPATH=$REPO/src NANO_MULTIAGENT_REPO_ROOT=$REPO python3 -m coding_cli.main --mode managed" &
daemon_pid=$!

for i in $(seq 1 100); do
  if [ -S "$SOCK" ]; then break; fi
  sleep 0.05
done
if [ ! -S "$SOCK" ]; then
  echo "Daemon failed to start"
  exit 1
fi

echo "=== Waiting for prompt ==="
tw wait_for_idle '{"idle_ms":1500,"timeout_ms":20000}' > /dev/null

echo "=== Creating new session ==="
B64=$(python3 -c "import base64; print(base64.b64encode(b'/new\n').decode())")
tw raw "{\"bytes_base64\":\"$B64\"}" > /dev/null
tw wait_for_idle '{"idle_ms":1500,"timeout_ms":20000}' > /dev/null

# Capture session ID from screen
tw screen '{"format":"text"}' | jq -r '.result' > /tmp/phase1_after_new.txt
SESSION_ID=$(grep -oE 'sess_[a-f0-9]+' /tmp/phase1_after_new.txt | tail -1)
if [ -z "$SESSION_ID" ]; then
  echo "FAIL: Could not extract session ID"
  cat /tmp/phase1_after_new.txt
  tw close > /dev/null || true
  wait $daemon_pid 2>/dev/null || true
  rm -f "$SOCK"
  exit 1
fi
echo "Created session: $SESSION_ID"

echo "=== Sending first message ==="
MSG1="say hi"
B64=$(python3 -c "import base64; print(base64.b64encode(b'${MSG1}\n').decode())")
tw raw "{\"bytes_base64\":\"$B64\"}" > /dev/null

echo "=== Waiting for assistant reply (up to 60s) ==="
tw wait_for_idle '{"idle_ms":4000,"timeout_ms":90000}' > /dev/null

echo "=== Capturing screen after first turn ==="
tw screen '{"format":"text"}' | jq -r '.result' > /tmp/phase1_after_turn1.txt
cat /tmp/phase1_after_turn1.txt

echo ""
echo "=== Checking first turn for duplicate output ==="
# Count lines containing "say hi" - should appear exactly once (the user message)
USER_COUNT=$(grep -c "say hi" /tmp/phase1_after_turn1.txt || true)
if [ "$USER_COUNT" -eq 1 ]; then
  echo "PASS: First turn user message not duplicated (count=$USER_COUNT)"
else
  echo "WARN: First turn user message count=$USER_COUNT"
fi

echo "=== Exiting REPL ==="
B64=$(python3 -c "import base64; print(base64.b64encode(b'/exit\n').decode())")
tw raw "{\"bytes_base64\":\"$B64\"}" > /dev/null
sleep 1
tw close > /dev/null || true
wait $daemon_pid 2>/dev/null || true
rm -f "$SOCK"

echo ""
echo "=== PHASE 2: Resume session and verify history ==="
termwright daemon \
  --socket "$SOCK" \
  --cols 120 \
  --rows 40 \
  -- \
  bash -c "cd $REPO && PYTHONPATH=$REPO/src NANO_MULTIAGENT_REPO_ROOT=$REPO python3 -m coding_cli.main --mode managed --resume $SESSION_ID" &
daemon_pid=$!

for i in $(seq 1 100); do
  if [ -S "$SOCK" ]; then break; fi
  sleep 0.05
done
if [ ! -S "$SOCK" ]; then
  echo "Daemon failed to start in phase 2"
  exit 1
fi

echo "=== Waiting for resume prompt ==="
tw wait_for_idle '{"idle_ms":2000,"timeout_ms":20000}' > /dev/null

echo "=== Capturing screen after resume ==="
tw screen '{"format":"text"}' | jq -r '.result' > /tmp/phase2_resume.txt
cat /tmp/phase2_resume.txt

echo ""
echo "=== Checking resume history ==="
if grep -q "say hi" /tmp/phase2_resume.txt; then
  echo "PASS: Resume shows previous user message 'say hi'"
else
  echo "FAIL: Resume missing previous user message 'say hi'"
fi

python3 - <<'PY'
from pathlib import Path

text = Path("/tmp/phase2_resume.txt").read_text(encoding="utf-8")
lines = [line.rstrip() for line in text.splitlines()]
assistant_lines = []
for line in lines:
    stripped = line.strip()
    if not stripped:
        continue
    if stripped == "> say hi":
        continue
    if stripped.startswith("[sess_") and stripped.endswith("]>"):
        continue
    if stripped.startswith("[sess_") and "]> " in stripped:
        continue
    assistant_lines.append(stripped)

if assistant_lines:
    print("PASS: Resume shows assistant/history lines:")
    for line in assistant_lines[:3]:
        print(f"  {line}")
else:
    print("FAIL: Resume screen did not show any assistant/history lines")
    raise SystemExit(1)
PY

echo ""
echo "=== Sending second message ==="
MSG2="say hello again"
B64=$(python3 -c "import base64; print(base64.b64encode(b'${MSG2}\n').decode())")
tw raw "{\"bytes_base64\":\"$B64\"}" > /dev/null

echo "=== Waiting for assistant reply (up to 60s) ==="
tw wait_for_idle '{"idle_ms":4000,"timeout_ms":90000}' > /dev/null

echo "=== Capturing screen after second turn ==="
tw screen '{"format":"text"}' | jq -r '.result' > /tmp/phase2_after_turn2.txt
cat /tmp/phase2_after_turn2.txt

echo ""
echo "=== Checking second turn for duplicate output ==="
USER_COUNT2=$(grep -c "say hello again" /tmp/phase2_after_turn2.txt || true)
if [ "$USER_COUNT2" -eq 1 ]; then
  echo "PASS: Second turn user message not duplicated (count=$USER_COUNT2)"
else
  echo "FAIL: Second turn user message duplicated (count=$USER_COUNT2)"
fi

python3 - <<'PY'
from pathlib import Path

lines = [line.rstrip() for line in Path("/tmp/phase2_after_turn2.txt").read_text(encoding="utf-8").splitlines()]
filtered = []
for line in lines:
    stripped = line.strip()
    if not stripped:
        continue
    if stripped.startswith("[sess_") and "]>" in stripped:
        continue
    filtered.append(stripped)

duplicates = []
for prev, curr in zip(filtered, filtered[1:]):
    if prev == curr:
        duplicates.append(curr)

if duplicates:
    print("FAIL: Found consecutive duplicate rendered lines:")
    for line in duplicates[:5]:
        print(f"  {line}")
    raise SystemExit(1)

print("PASS: No consecutive duplicate rendered lines detected")
PY

echo ""
echo "=== Cleanup ==="
tw close > /dev/null || true
wait $daemon_pid 2>/dev/null || true
rm -f "$SOCK"

echo "=== E2E test complete ==="
