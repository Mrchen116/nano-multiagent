# M1 Progress

## Scope delivered

- Gateway now assigns a stable `shadow_message_id` before every external-shadow
  `turn_start`, including normal, inline, multi-bubble and steer-roll paths.
- IM uses that identity as the conversation-scoped caller idempotency key. A repeated
  live start returns the same row without resetting rich or terminal state or adding
  unread count again.
- Live thinking/tool sequence and terminal elapsed can carry Gateway source facts;
  ordinary IM runs keep their existing IM-assigned behavior.

## Evidence

- `tests/unit/personal_assistant/test_gateway_shadow_sync.py`: online live delivery
  uses one identity and reconciles only after the terminal ACK barrier.
- `tests/im_service/unit/test_event_bridge.py`: repeated `turn_start` preserves the
  existing terminal row and source sequence/elapsed remain authoritative.
- `tests/im_service/integration/test_external_agent_messages_api.py`: a real
  `GatewayExecution.handle_streaming_delta` live row and the HTTP terminal reconcile
  resolve to one message id and keep its original `created_at`.

## Implementation note

New production writes no longer create legacy plain Agent outputs. Upgrade-era
legacy pending rows remain readable and recover through the existing protocol.
