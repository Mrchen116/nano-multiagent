# Acceptance: M310 — SPEC Alignment (M301–M309)

Date: 2026-03-25 (Asia/Shanghai)

## 1) Scope

Product acceptance review for the shipped M301–M309 work, focusing on the default user path:

- Start IM → start Gateway → open Web IM.
- Actor-first identity semantics (users/agents/conversations) are coherent and visible.
- `send_message(to=user_id|agent_id|conversation_id)` semantics are consistent with routing behavior.
- Group chat mention/discoverability is usable.

Out of scope:
- Fixing issues found.
- Deep code review.

## 2) Materials relied on (user-facing first)

- `README.md`
- `docs/operator-runbook.md`
- `docs/NodeGateway-SPEC.md`
- `docs/内核设计细化/系统提示词.md`
- `docs/spec-implementation-conflicts.md`

## 3) Environment & Preconditions

### Port bind self-test

I validated the environment can listen on localhost:

- `python socket.bind(('127.0.0.1', 0))` → `OK ('127.0.0.1', <ephemeral_port>)`

### Services started (real process)

- IM: `PYTHONPATH=src python -m uvicorn IM.app:app --host 127.0.0.1 --port 8011`
- Gateway: `PYTHONPATH=src python -m personal_assistant.main --config ./node-config.yaml --foreground`

Observed:
- Web IM shell served at `http://127.0.0.1:8011/` and `/chat`.
- Gateway printed the bind confirmation URL (per runbook).

## 4) Journeys executed

### Journey A — Start IM and confirm Web IM entrypoint

- `GET http://127.0.0.1:8011/` returns the Web IM HTML shell.
- `GET http://127.0.0.1:8011/chat` returns the same shell.

Result: **Pass** (entrypoint served by IM host as documented).

### Journey B — Start Gateway and bind the node

- Gateway reports “waiting for IM binding” and provides `.../bind/confirm?token=...`.

Because this is a terminal-only environment (no interactive browser automation available), I used the documented operator API path from the runbook appendix:

- `POST /im/v1/bind {action:start,node_id}`
- `POST /im/v1/users` (create a user)
- `POST /im/v1/bind {action:confirm,bind_id,user_id}`

Result: **Pass** (binding works; `GET /im/v1/nodes` shows `status=online` and `owner_id` set).

### Journey C — Actor-first identity semantics are coherent

Evidence via IM APIs:

- `GET /im/v1/conversations` includes:
  - `participants` as an actor list with `type` (`user|agent`) and stable ids (`user_id` / `agent_id`).
  - `direct_kind` for direct conversations (e.g. `user-agent`).

Result: **Pass**.

### Journey D — Group chat mention & routing behavior

I created a group conversation including:
- a human user (`Acceptance`)
- another human user (`You`)
- an agent participant (`Alpha`)

Then sent messages:

1) Without an agent mention:
- Message persists to IM (`message.sent`) but does not proceed to gateway execution.

2) With a stable agent mention token:
- Sent content: `@agent:Alpha ...`
- SSE events show the full relay lifecycle:
  - `relay.accepted` (with `mentioned_agent_ids=["Alpha"]`)
  - `relay.processing`
  - `relay.completed`
  - `message.delivered`

Result: **Pass** (group mention gating behaves coherently and is observable).

## 5) Findings

### Blocking

None.

### Major

None.

### Minor

1) I could not click through the bind confirmation UI in a real browser in this terminal-only session; binding was validated via the runbook’s documented operator API path instead.

## 6) Verdict

Verdict: **pass**

## 7) Issue counts

- blocking: 0
- major: 0
- minor: 1

## 8) Top issue (one sentence)

The documented bind-confirmation UI flow couldn’t be interacted with directly here, so binding was validated via the runbook’s API appendix instead.

## 9) Re-review required?

No.
