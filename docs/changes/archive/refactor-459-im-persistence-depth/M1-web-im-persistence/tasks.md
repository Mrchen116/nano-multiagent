# refactor-459-M1: Web IM persistence seam — Tasks

> 对齐: ../design.md v1

## 目标

把 shadow conversation 的 created 语义，以及浏览器事件的 recipient、resume/cursor、relay enrichment 查询收回 concrete SQLite repository；Web IM application、route 与 user-stream 只表达业务意图，保持现有 HTTP/WS 行为不变。

## 退出标准

- [x] Conversation interface 覆盖 created/竞态恢复/exists，Event interface 覆盖 recipient、cursor gap/window、relay identity 与 agent display-name enrichment。
- [x] `EventReplayResult` 唯一定义在 `IM.infra.repositories`，infra 不 import WS。
- [x] M1 event/application/route 路径无 repository private connection、直接业务 SQL 或 commit；deps 不定义 ConversationRepository 子类。`user_stream.py` 仅枚举保留 M2 stale-node SQL 这一处精确临时例外。
- [x] owner 隔离、direct/group、shadow conversation、过程事件与 user-stream resume/sync 对外结果不变。
- [x] 最窄 IM tests、完整 IM non-e2e 与 `ruff check` / `ruff format --check` 全绿。

## 测试策略

- 被测行为（来自退出标准）：external find-or-create 首次 `created=True`、重复及竞态恢复 `created=False`；conversation exists；recipient 顺序；global cursor；resume gap/window；relay run identity 与 agent display-name enrichment；HTTP shadow status、sync cursor 与 user WS resume 行为不变；静态 seam 约束。
- 已有测试在：`tests/im_service/unit/test_repositories_user_conversation.py`（只迁移既有结果断言；文件已超过软上限）；新建 `tests/im_service/unit/test_conversation_repository_intents.py`，理由：created/race/exists 是新的 intent interface，旧文件已超 400 行；`tests/im_service/unit/test_event_repository.py`（扩展）；`tests/im_service/integration/test_messages_api.py`、`test_group_chat_events.py`、`test_user_stream_auth.py`、`tests/im_service/contract/test_events_contract.py`（复用/扩展）。新建 `tests/contract/test_im_persistence_seam_contract.py`，理由：跨模块 import/SQL/private-state 边界属于静态架构契约，现有 contract 文件无对应 seam。
- 落层/目录/marker：`tests/im_service/unit/`、`tests/im_service/integration/`、`tests/im_service/contract/`、`tests/contract/`，marker：无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：真实 FastAPI HTTP + user WebSocket integration 命令输出记录在 progress；无临时脚本。
- 前端 UI：N/A（无前端或视觉变化）。
- Prototype / Reference Contract：N/A。

## Roadpoints

### R1 — Conversation intent interface

- 状态：DONE
- 步骤：为 external find-or-create 引入 typed `ExternalConversationWriteResult`，让 repository 单次调用返回 conversation/created（含竞态恢复）；增加 `exists`；WebIMService 只委托；deps 删除重复子类并改用 base repository。
- 验证：repository created/duplicate/race/exists 红转绿；shadow HTTP 201→200 行为保持；最窄 conversation/API tests 通过。

### R2 — Event query interface

- 状态：DONE
- 步骤：把 `EventReplayResult`、recipient、resume/window/gap、global cursor、relay identities 与 display-name 查询收进 EventRepository；EventService 与 user_stream 改为纯 interface 调用。
- 验证：真实 SQLite event interface tests 红转绿；event enrichment、user WS resume 与 sync integration tests 通过。

### R3 — Composition、routes 与 seam contract

- 状态：DONE
- 步骤：app 显式注入 EventRepository 到 user-stream；route 通过公开 dependencies/service 获取 profile 与 cursor；新增静态 persistence seam contract，清除目标调用方 private connection/SQL。
- 验证：seam contract 红转绿；M1 最窄测试、相关 IM suite、ruff check/format 全绿；真实 FastAPI HTTP/WS 入口覆盖 Scenario 1–3、7 的既有结果。
