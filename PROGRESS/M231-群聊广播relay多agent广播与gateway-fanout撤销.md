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

- Context: create_message 路由原来只调一次 enqueue_relay + push；需改为对每个 participant agent 各调一次，且单节点离线不阻断其他。
- Decision: 新增 WebIMService.enqueue_relay_all（委托 relay_service.enqueue_message_relay_all），路由改为遍历结果逐个 push，收集 any_dispatched；全部失败才抛 503，部分失败 record_relay_failure 继续。
- Rationale: any_dispatched 逻辑确保"至少一个 agent 收到"才算成功，符合群聊广播容错语义。
- Evidence:
  - Tests: `python -m pytest tests/unit/personal_assistant/ tests/unit/IM/ -x -q` → 109 passed
  - Entry: 群聊 2 agent，一个离线 → 200 返回；全部离线 → 503；两个均在线 → 两次 push 均被调用。
- Rollback: 回退到 C1 commit c5f8e0b
- Commits: C1=c5f8e0b, C2=b5b82bc, C3=（待写）
- Next: R3 — inbound_pipeline.py 移除 gateway fan-out loop

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
