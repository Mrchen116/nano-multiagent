# M231 Progress: 群聊广播 relay 多 agent 广播 + gateway fan-out 撤销

## 概述

- Branch: milestone/M231
- Worktree: /Users/czj/Repos/nano-multiagent/.worktrees/M231
- Test command: `python -m pytest tests/unit/personal_assistant/ tests/unit/IM/ -x -q`

---

## R1: relay_service — 群聊多 agent broadcast

- Context: 原 enqueue_message_relay 为单 relay，群聊时 gateway 须自行 fan-out（已在 commit 3a43a47 中做）；需改为 IM 侧逐 agent 建 relay，gateway 不再 fan-out。
- Decision: 新增 enqueue_message_relay_all，群聊时调用 _resolve_participant_agent_ids 取出全部 participant agent，逐个以 {base}:{agent_id} 为 idempotency_key 调 enqueue_message_relay（_override_agent_id 强制 payload.agent_id）；直聊/unknown 走原单 relay 路径。
- Rationale: _override_agent_id 是内部参数，保持 enqueue_message_relay 签名稳定，避免改动所有现有调用方。
- Evidence:
  - Tests: `python -m pytest tests/unit/personal_assistant/ tests/unit/IM/ -x -q` → 106 passed
  - Entry: 群聊 2 个 participant agent → enqueue_message_relay_all 返回 2 条 relay，各自 payload.agent_id 不同；幂等重复调用返回 created=False。
- Rollback: 回退到 C1 commit 963cb90（含测试，无实现）
- Commits: C1=963cb90, C2=430b241, C3=（待写）
- Next: R2 — messages.py 路由层群聊 per-agent relay loop

---

## R2: messages.py — 群聊 per-agent relay loop

- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:

---

## R3: inbound_pipeline.py — 移除 gateway fan-out loop

- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:
