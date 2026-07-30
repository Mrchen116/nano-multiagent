# PROGRESS (Milestone: M34)

- Title: 独立IM服务人和人聊天链路与SSE事件流
- Goal: 在 `src/IM` 完成人和人聊天完整链路：发送消息、历史查询、SSE 实时事件流、送达状态与基础错误处理。
- Exit Criteria:
  - `POST /im/v1/conversations/{id}/messages` 可持久化并生成事件。
  - `GET /im/v1/conversations` 与 `messages/events` 可用。
  - SSE 事件流稳定（重连不崩）。
  - 完成 contract + integration + e2e 入口验证。
  - 不改动 `src/nano_multiagent/*`。
- Test command: `PYTHONPATH=src pytest -q tests/im_service`
- Branch: `milestone/M34`

### Baseline
- Context:
  - execution_mode=`parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M34`，branch=`milestone/M34`。
  - 已读取 `COMMENTING_GUIDE.md`、`LOGBOOK.md`、`IM前端蓝图.md`、`IM服务蓝图.md`、`Agent 助手（基于 SDK 的上层应用）蓝图.md`。
  - prevention_rules：仅做人和人聊天后端与聊天 SSE；不做 Agent 助手/节点接口；保持独立服务边界。
- Decision:
  - 先同步 `origin/main`（含 M33 基础），再在同一分支拆分 `R34.1/R34.2/R34.3` 按 C1/C2/C3 执行。
- Rationale:
  - 避免与 M33 已合并能力重复建设，降低冲突与返工。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/im_service`（rebase 后 baseline `10 passed`）。
  - Entry: 当前已有 users/conversations/messages 基础 API，尚缺事件持久化与 SSE 接口。
- Rollback:
  - plan commit
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
  - 提交 Plan 后进入 `R34.1` Red。

### R34.1 消息送达状态与事件持久化
- Context:
  - 既有 M33 只有 `messages` 表与消息增查接口，尚未提供送达状态字段与事件持久化能力。
  - 本 Roadpoint 目标是先固化“消息写入即产出可回放事件”的数据约束，为 SSE 重连游标打基础。
- Decision:
  - 在 `messages` 表新增 `delivery_status` 字段，并在 `create_message` 内完成 `sent -> completed` 状态收口。
  - 新增 `conversation_events` 表（`event_id` 自增主键）作为事件持久化日志。
  - 消息写入事务内同步落两条事件：`message.sent`、`message.delivered`，并新增 `EventRepository.list_events` 游标读取接口。
  - API `MessageResponse` 与 `GET messages` 返回 `delivery_status`，契约可被前端消费。
- Rationale:
  - 用数据库自增 `event_id` 作为 SSE 重连游标最稳定，避免时间戳去重误差。
  - 在仓储层原子写入消息与事件，可避免“消息写入成功但无事件”造成链路断层。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/im_service`（`14 passed`）
  - Entry: `POST /im/v1/conversations/{id}/messages` 返回 `delivery_status=completed`，事件仓储可按 `after_event_id` 增量读取。
- Rollback:
  - `661f940`（R34.1 C1，仅红测）
- Commits: C1=`661f940`, C2=`f890075`, C3=`4777c85`
- Next:
  - 进入 `R34.2` Red：新增 SSE 事件流接口、重连游标与心跳流测试。

### R34.2 SSE 事件流接口与重连稳定性
- Context:
  - R34.1 已具备事件持久化，但仍缺 HTTP SSE 入口与断线重连游标语义。
  - 验收要求“重连不崩”，需在空闲连接场景下提供稳定 keepalive。
- Decision:
  - 新增 `src/IM/sse.py` 统一 SSE 帧编码（事件帧 + 心跳帧）。
  - 在 `GET /im/v1/conversations/{id}/events` 接入轮询式流读取：支持 `after_event_id` 与 `Last-Event-ID`。
  - 读取游标统一由 `_parse_event_cursor` 解析，非法值返回 `400 after_event_id must be an integer`。
  - 流路径增加会话存在性校验，不存在会话返回 `404 conversation_id not found`。
- Rationale:
  - 轮询 + 心跳实现最小可靠，不引入额外 broker 就能满足“可回放 + 可重连”。
  - 将游标逻辑集中在单函数可避免 query/header 分散解析导致语义不一致。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/im_service`（`19 passed`）
  - Entry: `/im/v1/conversations/{id}/events` 返回 `text/event-stream`，支持 `Last-Event-ID` 增量读取且空闲时输出 `: keepalive`。
- Rollback:
  - `030d46d`（R34.2 C1，仅红测）
- Commits: C1=`030d46d`, C2=`804a48d`, C3=`81f9f78`
- Next:
  - 进入 `R34.3` Red：补 e2e 入口链路与错误处理收口验证。

### R34.3 人和人聊天链路入口验证与错误处理收口
- Context:
  - R34.2 已具备 SSE 与重连，但入口层还缺“未知会话 messages 返回 404”语义，错误路径不一致。
  - Milestone 要求 contract + integration + e2e 都有入口验证，需补齐完整链路测试组。
- Decision:
  - 新增三层验证：
    - contract：未知会话下 `messages/events` 均返回 `404 conversation_id not found`；
    - integration：用户/会话/消息/历史/会话列表主链路；
    - e2e：完整人聊链路 + `after_event_id` 增量重连。
  - 在 `list_messages` 接口前增加会话存在性检查；
  - 在 `create_message` 错误映射中把 `conversation_id not found`、`sender_user_id not found` 收敛到 404。
- Rationale:
  - 错误分层一致可减少前端兜底分支，404 也更符合资源语义。
  - 入口三层同时覆盖可防止“单测通过但真实请求链路偏差”。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/im_service`（`22 passed`）
  - Entry: create users/conversation -> post messages -> list messages -> SSE replay/reconnect 全链路可运行；未知会话 messages/events 统一 404。
- Rollback:
  - `1e8790e`（R34.3 C1，仅红测）
- Commits: C1=`1e8790e`, C2=`a1af04e`, C3=`<pending>`
- Next:
  - 执行 Milestone 最终集成：rebase main、全绿、合并到 main、更新 dev-tasks 状态。
