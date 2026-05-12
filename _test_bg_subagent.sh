#!/bin/bash
set -e

REPO="/Users/czj/Repos/nano-multiagent"
SOCK="/tmp/coding-cli-bg-test.sock"
rm -f "$SOCK"

# Start daemon
export PATH="$HOME/.cargo/bin:$PATH"
termwright daemon \
  --socket "$SOCK" \
  --cols 120 \
  --rows 40 \
  -- \
  bash -c "PYTHONPATH=$REPO/src python3 -m coding_cli.main --mode managed --model volcanoArk:doubao-seed-2-0-code-preview-260215 2>&1" &
daemon_pid=$!

# Wait for socket
for i in $(seq 1 100); do
  if [ -S "$SOCK" ]; then break; fi
  sleep 0.05
done

tw() {
  termwright exec --socket "$SOCK" --method "$1" --params "${2:-null}"
}

# Wait for first prompt - wait for nano> to appear
echo "=== WAITING FOR PROMPT ==="
tw wait_for_text '{"text":"nano>","timeout_ms":30000}' >/dev/null
sleep 2

echo "=== SCREEN AFTER STARTUP ==="
tw screen '{"format":"text"}' | jq -r '.result'

# Turn 1: launch background subagent
# Use raw for atomic text+enter
MESSAGE='启动一个后台agent，description是test-bg，prompt是echo hello from subagent，subagent_type是explore，load_skills是空数组，run_in_background是true'
B64=$(python3 -c "import base64; print(base64.b64encode('$MESSAGE'.encode()).decode())")
tw raw "{\"bytes_base64\":\"$B64\"}" >/dev/null

echo "=== WAITING FOR MAIN AGENT RESPONSE ==="
tw wait_for_idle '{"idle_ms":5000,"timeout_ms":60000}' >/dev/null

echo "=== SCREEN AFTER MAIN AGENT RESPONSE ==="
tw screen '{"format":"text"}' | jq -r '.result'

# Wait for subagent to complete and notification to arrive
echo "=== WAITING 40s FOR BACKGROUND SUBAGENT ==="
sleep 40

tw wait_for_idle '{"idle_ms":3000,"timeout_ms":15000}' >/dev/null

echo "=== SCREEN AFTER BACKGROUND COMPLETION ==="
tw screen '{"format":"text"}' | jq -r '.result'

# Cleanup
tw close >/dev/null 2>&1 || true
wait $daemon_pid 2>/dev/null || true
rm -f "$SOCK"

echo "=== DONE ==="
