# refactor-459-M1 — Progress

## 基线

- Context: M1 开始前确认现有 Web IM persistence 行为与格式门禁可用。
- Evidence: `pytest -q` 覆盖 conversation/event repository、messages API、group event enrichment、user WS auth/resume 与 events contract，结果 `43 passed, 1 skipped`；目标文件 `ruff check` 与 `ruff format --check` 全绿。

## R1 — Conversation intent interface

- 状态：DONE
- Context: WebIMService 先通过 repository private connection 查询是否存在，再调用 repository 写入，`created` 在并发竞态下可被误判；deps 还保留一套重复 ConversationRepository 子类。
- Decision: `ConversationRepository.find_or_create_external_conversation()` 返回 immutable `ExternalConversationWriteResult(conversation, created)`，由 repository 在 existing、successful insert、uniqueness race 三条路径给出准确结果；增加 `exists()`，WebIMService 纯委托，deps 统一构造 base repository。
- Rationale: created 判定与唯一约束恢复属于同一个 persistence invariant；把它留在 caller 会要求 caller 重复索引条件且无法准确解释竞态。
- Evidence:
  - Tests: `pytest -q tests/im_service/unit/test_conversation_repository_intents.py tests/im_service/unit/test_repositories_user_conversation.py tests/im_service/unit/test_relay_service_payload.py tests/im_service/integration/test_messages_api.py` → `34 passed, 1 skipped`。
  - Entry: 真实 FastAPI `POST /im/v1/conversations/external/find-or-create` 由既有 messages API integration 覆盖首次 201、重复 200 及持久化 identity 不变。
  - Frontend State Matrix: N/A（无前端变化）。
  - Browser QA: N/A（无前端变化）。
  - E2E/Regression: repository 使用真实 SQLite 覆盖首次/重复/竞争插入/exists；HTTP integration 覆盖 route/service/repository 接线。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退到 C1 `f406277a` 可移除实现并保留失败测试。
- Commits: C1=`f406277a`；C2=`1ae68a1e`；C3=本次 docs commit。
- Next: R2 收口 Event repository query interface。

## R2 — Event query interface

- 状态：DONE
- Context: user-stream 自己持有 recipient、global cursor、gap/window replay SQL；EventService 通过 `EventRepository._connection` 查询 relay identity 与 display name，导致 WS/application 同时知道 event schema。
- Decision: 在 infra 唯一定义 `EventReplayResult` 与 typed `RelayRunIdentity`；EventRepository 提供 recipient、global cursor、user resume、relay identity、agent display-name 五个 intent query。EventService 只做 payload enrichment，user-stream 只做 frame/connection lifecycle，`/sync` 通过 EventService 获取 cursor。
- Rationale: 每个 operation 都隐藏一条完整 query/invariant（owner-visible conversation、cursor resync reason、历史 identity mapping），没有新增假 adapter 或 pass-through facade。
- Evidence:
  - Tests: `pytest -q tests/im_service/unit/test_event_repository_queries.py tests/im_service/unit/test_event_repository.py tests/im_service/integration/test_group_chat_events.py tests/im_service/integration/test_user_stream_auth.py tests/im_service/contract/test_events_contract.py` → `17 passed`。
  - Entry: 真实 FastAPI user WebSocket resume、`GET /im/v1/sync` 与 group relay event enrichment integration 均通过，wire payload/status 不变。
  - Frontend State Matrix: N/A（无前端变化）。
  - Browser QA: N/A（无前端变化）。
  - E2E/Regression: 真实 SQLite interface 覆盖 recipient、global cursor、owner visibility、顺序、gap/window resync 与 typed enrichment maps；HTTP/WS integration 覆盖接线。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退到 C1 `5540ec88` 可移除实现并保留失败测试。
- Commits: C1=`5540ec88`；C2=`07689ba2`；C3=本次 docs commit。
- Next: R3 完成 profile dependency、静态 seam contract 与纵向门禁。按 orchestrator 明确的纵向迁移口径，`user_stream.py` 的 stale-node private SQL 是唯一精确临时例外，由 M2 的 `GatewayNodePersistence.stale_online_node_ids` 退出标准关闭；M1 不新增 NodeRepository pass-through，也不提前实现 M2 seam。

## R3 — Composition、routes 与 seam contract

- 状态：TODO
