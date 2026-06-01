# feat-393-M1 Progress

## Status: DOING

##澄清记录

（开工前无疑问，设计意图清晰）

---

## Roadpoints

### R1 — IM turn_start to_user_id 分支

- Context: IM `_handle_streaming_delta` 的 `turn_start` 只支持 `conversation_id` 模式（必须非空），heartbeat 发 `to_user_id` 时直接抛 ValueError。
- Decision: 在 `turn_start` 块前增加 `to_user_id` 互斥分支；复用现有 `self._find_or_create_direct_conversation` 解析 canonical 直聊；ack 同时返回 `conversation_id` 和 `message_id`。
- Rationale: 复用服务端既有 canonical 解析逻辑，gateway 不预解析、不加额外 round-trip；与普通聊天 `conversation_id` 模式互斥，零风险交叉。
- Evidence:
  - Tests: `pytest tests/im_service/ -q` — 268 passed
  - Entry: N/A（纯后端协议扩展，由 R2 的 gateway 侧测试证明端到端可用）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（R3 跑全量）
  - Visual/Interaction: N/A
- Rollback: C1=b4211ed5, C2=66a3815b
- Commits: C1=b4211ed5, C2=66a3815b, C3=（本条记录）
- Next: R2 — gateway 侧 heartbeat observer 惰性 turn_start + 专属 :heartbeat session
