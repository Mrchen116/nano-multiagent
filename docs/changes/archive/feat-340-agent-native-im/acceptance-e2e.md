# feat-340 Agent-Native IM — End-to-End Acceptance Report

**Date**: 2026-05-11  
**Tester**: e2e-verification worker (Claude Sonnet 4.6)  
**Verdict**: FAIL — streaming event chain not implemented

---

## Context

Previous 4 rounds of change-reviewer only validated layout/API 200 responses against a mock stack. This report covers the first real end-to-end run with live LLM calls, gateway, kernel, and WebSocket capture.

---

## Stack Health

| Service | Address | Status |
|---------|---------|--------|
| LLM proxy (moonshot:kimi-k2.5) | http://127.0.0.1:4000 | `{"ok":true}` |
| Agent kernel | http://127.0.0.1:8000 | responds to `/v1/sessions` |
| IM service | http://127.0.0.1:8011 | responds to `/im/v1/conversations` |
| Gateway (e2e-test-node) | http://127.0.0.1:8089 | registered, online, bound to root user |

Gateway node registration confirmed via IM admin:
```
node_id: e2e-test-node
owner_id: ba20c2bfc39f466cb878481cf12730eb (root)
status: online
```

Kernel session created for Alpha with `config_profile_version: 2`:
```json
{
  "session_id": "sess_9305f698135cac12",
  "status": "active",
  "metadata": {
    "agent_id": "Alpha",
    "conversation_type": "direct",
    "gateway_dispatch_url": "http://127.0.0.1:8089/internal/dispatch"
  }
}
```

---

## J-A: Direct Chat — Real LLM Round-Trip

**Setup**: Root user → direct conversation with Alpha (participant `2e4593e9e95b49f689e7d9a2a62d061b`)  
**Message sent**: "What is 2+2? Give a single number answer."  
**LLM model**: `moonshot:kimi-k2.5`

**Result**: PASS (basic delivery), FAIL (streaming)

Alpha replied "4" correctly. The full WS event log captured to `/tmp/ws_events4.log`:

```
message.sent      → event_id 1644
relay.accepted    → event_id 1645  (run_id=run_4a8e10c93a9deb4a)
relay.processing  → event_id 1646  (summary="4", status=running)
relay.report      → event_id 1647  (summary="4", status=completed)
relay.completed   → event_id 1648
message.delivered → event_id 1649
```

**Missing events** — zero occurrences across all 4 WS captures:
- `message.created` — never seen
- `message.delta` — never seen  
- `message.completed` — never seen
- `tool_call.upserted` — never seen
- `tool_call.completed` — never seen

The spec (feat-340 design.md) requires the gateway to emit this streaming chain as the LLM produces tokens. The chain is entirely absent. The agent's reply appears as a single complete bubble with no streaming animation.

**Token Chip**: Not rendered. The `relay.report` event carries `summary="4"` (plain text) with no `token_usage` field. No token counts are ever surfaced in the UI.

---

## Root Cause Analysis

### 1. EventBridge is dead code

`src/IM/application/event_bridge.py` defines:
- `on_turn_start()` → would emit `message.created`
- `on_message_delta(chunk)` → would emit `message.delta`
- `on_message_completed(...)` → would emit `message.completed`
- `on_tool_call_upserted(...)` → would emit `tool_call.upserted`
- `on_tool_call_completed(...)` → would emit `tool_call.completed`

**Nobody instantiates or calls this class.** Grep across entire `src/` finds zero usages outside the class definition itself.

### 2. kernel_event_observer never wired

`src/personal_assistant/gateway/inbound_pipeline.py:107`:
```python
def __init__(self, ..., kernel_event_observer=None, ...):
```

`_await_terminal_run_async()` at line 535 streams kernel SSE events and calls:
```python
if self._kernel_event_observer:
    self._kernel_event_observer(event)
```

`src/personal_assistant/main.py` never passes `kernel_event_observer` when constructing `InboundPipeline`. It is always `None`. The hook exists in the pipeline code but is never connected.

### 3. Gateway report handler skips streaming chain

`src/IM/ws/gateway_handler.py:_persist_report_event()` (line ~1220) maps `node.report` status → either `relay.processing` or `relay.report` IM events. It never emits `message.created / delta / completed`. The entire streaming translation path is absent from the gateway WS handler.

---

## J-B through J-E: Blocked

These journeys require streaming to be functional as a prerequisite:

| Journey | Requirement | Status |
|---------|-------------|--------|
| J-B: Group chat @mention | streaming agent reply + mention picker | BLOCKED — streaming absent |
| J-C: Cross-tenant isolation | WS frames scoped to correct user | Cannot verify streaming isolation without streaming |
| J-D: Notification | notification triggered by message.completed | BLOCKED — event never fires |
| J-E: Attachment | image/PDF chip in agent context | Not tested (orthogonal, could pass, but out of scope for this run) |

---

## Evidence Summary

| Artifact | Path | Content |
|----------|------|---------|
| WS capture (direct chat, 2 messages) | `/tmp/ws_events4.log` | Shows relay.* chain only, zero message.delta |
| Browser screenshot (post-reply) | `/tmp/im-direct-chat.png` | Complete bubble, no streaming animation |
| Stream attempt screenshots x5 | `/tmp/im-stream-{1-5}.png` | All show same completed state, no incremental render |
| Previous WS captures | `/tmp/ws_events{1-3}.log` | Consistent — no message.delta in any session |

---

## What Previous Reviewers Missed

All 4 prior reviews validated:
- Page layout renders correctly
- API endpoints return 200
- Conversation creation works
- Message list populates

None verified:
- Real LLM call via kernel (kernel was never started in earlier reviews)
- WS event types beyond `message.sent` / `message.delivered`
- Whether `message.delta` / `message.created` / `message.completed` exist at all in the WS stream
- Whether Token Chip displays real `token_usage` values

---

## Required Implementation Work

To pass J-A streaming:

1. **Wire kernel_event_observer**: In `src/personal_assistant/main.py`, pass a callback to `InboundPipeline` that forwards kernel SSE `TextChunk` / `ToolCallEvent` events via the gateway WS to IM.

2. **Implement EventBridge invocations**: In `src/IM/ws/gateway_handler.py`, when a `node.streaming_delta` frame arrives from the gateway, call `EventBridge.on_message_delta()` to fan-out `message.delta` to subscribed user WS connections.

3. **Add token_usage to relay.report**: The gateway should include `token_usage: {prompt: N, completion: M}` in the `node.report` frame so IM can render Token Chip.

4. **Frontend**: Token Chip component and streaming text rendering are presumably already designed per spec — they need the above WS events to activate.
