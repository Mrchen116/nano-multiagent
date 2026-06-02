# IM 浏览器用户流（WSS）迁移计划

> **状态**：**已实现**（约 2026-03）；下文保留目标与当时设计记录，便于对照代码与排障。
>
> **目标**：用「每用户一条 WebSocket」替代「每会话 SSE + 前十路 cap」，对齐商用 IM 的多会话实时与可扩展性；**多标签页默认允许多连接**；**一次性切换**（不长期双轨）。
>
> **规模假设**：≈200 用户，单机 IM；Gateway WebSocket（`/im/ws/gateway`）保持不变。
>
> **Replay**：见 §4（实现侧默认参数可环境变量覆盖）。

---

## 1. 迁移前摘要（归档）

| 区域 | 迁移前 |
|------|--------|
| 会话事件持久化 | `conversation_events.event_id` 为表级 `AUTOINCREMENT`，**全局单调**；`EventRepository.append_event` 写库即得 `event_id`。 |
| 按会话 SSE | `GET /im/v1/conversations/{id}/events`（`messages.py`）等；**已删除**，见 `docs/specs/im/spec.md`。 |
| 前端 | 曾用 `EventSource` 按会话拉流；现改为共享 **`/im/ws/user`** + `sessionStorage` 全局 `event_id` 游标 + `GET /im/v1/sync` 对齐。 |
| Gateway | `app.py`：`/im/ws/gateway`，与浏览器用户流 **独立**。 |
| 会话成员 | `conversation_participants(conversation_id, user_id)`；广播收件人与参与者一致（见 `user_stream.resolve_recipient_user_ids`）。 |
| HTTP API | 列表/会话 **当前无 OAuth 级鉴权**；前端靠 bootstrap/`/im/v1/me` 认出 `selfUserId`。用户流握手 query `user_id` 与之对齐（见 §3）。 |

---

## 2. 目标架构

```
浏览器 ──WSS /im/ws/user──► IM（内存 fan-out）◄── 写路径 append_event 后广播
         ▲                    │
         │                    └── 现有 REST / Gateway WS 不变
         └── JSON 帧：统一 envelope（conversation_id + event_id + type + payload）
```

- **下行**：所有原 SSE `event_type` 与 payload 形态 **尽量保持不变**，外包一层 `conversation_id` + `event_id`（与表中一致），减少前端 reducer 重写范围。
- **上行（首版最小）**：`ping` / `resume`（可选）；业务操作仍走 HTTP（发消息、已读等），避免首版在 WS 上复制 REST 语义。
- **Fan-out**：在 **每次 `append_event` 成功后**（`gateway_handler`、HTTP 发消息路径等所有写点），解析「应接收该事件的 `user_id` 集合」，投递到该用户下 **当前已连接的所有 WS**（多标签 = 多条连接；重复投递可接受，客户端按 `event_id`+`conversation_id` 去重）。

---

## 3. 用户识别与握手

- **原则**：与现有 Web IM 一致——从 **_QUERY / Header（与现有前端 `requestJson` 同源）** 或会话 Cookie（若后续加了）解析 `user_id`；握手未完成前不进入 `receive` 循环。
- **实现落点**：新建 `IM/ws/user_handler.py`（或 `user_stream.py`）+ `app.py` 注册 `@app.websocket("/im/ws/user")`（路径以最终实现为准，建议与 gateway 并列、前缀 `/im/ws/`）。
- **鉴权对齐**：若短期仍无强鉴权，也应在握手携带 **显式 `user_id`/`device` 与现网风险一致**；计划在文档中记「与 `/im/v1/me` 同一信任域」，后续可收紧为 token。

---

## 4. 重连与 Replay（定案）

**游标**：客户端持久化 **已处理的最大 `conversation_events.event_id`（全局）**（单字段即可，因 PK 全局单调）。

**连接后**：

1. 客户端发送 `{"op":"resume","after_event_id":N}`（或在 URL `?after_event_id=`，二选一，实现时统一一处）。
2. 服务端查询（伪 SQL）：

   `conversation_events` 与「该用户有权访问的 `conversation_id`」做交集（与列表/详情可见性一致；至少 `conversation_participants` + 产品对 owner/旁听会话的规则），`WHERE event_id > N ORDER BY event_id LIMIT K`。

**默认参数（商用可接受、实现可调）**：

- `K = 500`（单帧批量上限，防一次读爆）。
- **时间窗**：仅回放 **最近 15 分钟内** 的事件；更旧的记录仍可通过 HTTP 拉历史（与现有 `list_messages` / 会话维度的 cursor 一致）。若 `after_event_id` 过旧，服务端回复 `{"op":"resync_required","reason":"cursor_stale"}`，客户端用 **§5 增量接口** 对齐。
- **超限**：若 `event_id`  gap 超过 **2000**（可调），同样 `resync_required`，避免恶意或 bug 导致超大 scan。

**心跳**：服务端每 **25s** 发 `ping` 帧（或 JSON `{"op":"ping"}`），客户端 `pong`；配合 Nginx `proxy_read_timeout` ≥ 60s。

**多标签**：各连接独立 `resume`；同一事件可能到两 tab，UI 去重即可。

---

## 5. Inbox / 增量对齐（兜底）

新增轻量 **`GET /im/v1/sync`**（或 `inbox/sync`）：

- **Query**：`after_event_id`（可选）、`limit`。
- **响应**：`next_after_event_id` + `conversations touched` 摘要列表（`conversation_id`、`last_message_preview`、`last_message_at`、`unread_count` 等 **已有列表 API 已返回字段**），避免重复发明模型。

**客户端策略**：收到 `resync_required`、冷启动、或 WS 断连超过阈值 → 调一次 `/im/v1/sync`，更新 React Query `["chat","conversations"]`，再继续 `resume`。

**目录重拉**：`agents`/`nodes`/`users` **不要**绑在 3s 通知环上；保持「进设置 / 显式 refetch / 较长 stale」。

---

## 6. 后端实现任务（有序）

1. **`UserConnectionRegistry`**（进程内）：`register(user_id, ws)`、`broadcast(user_ids, text)`、`disconnect`；200 用户可纯内存 `dict[str, set[WebSocket]]`。
2. **`resolve_event_recipient_user_ids(conversation_id) -> set[str]`**：复用仓储层与 `list_conversations`/参与者解析一致；Agent 当人时仍映射到 **应接收通知的人类用户**（owner、群成员用户别名等）；**写单测覆盖边界**（仅 Agent 会话、群、单聊）。
3. **在 `EventRepository.append_event` 返回后广播**（推荐：**单一出口**——新增薄封装 `append_event_and_publish` 或在 repository 注入 notifier，避免漏改 `gateway_handler` / `messages` 某一路）。
4. **`WebSocket` 路由**：握手鉴权 → `resume` 回放循环 → 长连接 `receive` 处理 ping/pong；异常断开清理 registry。
5. **`GET /im/v1/sync`**：SQL 聚合「用户相关会话 + `event_id > cursor` 的变更」或直接基于现有表字段-diff（实现选简单且正确者优先）。
6. **删除或废弃**：`GET .../events` SSE 路由（一次性切换可删；若有外部依赖则先 grep 全仓后再删）。
7. **`docs/specs/im/spec.md` / `IM前端蓝图.md`**：追认 WSS 与 `/sync` 为 P0 行为；Gateway 章节不动。

---

## 7. 前端实现任务（有序）

1. **`userStream.ts`**：`WebSocket` 连接、自动重连（指数退避 + jitter）、`resume`、心跳、解析 JSON 行协议；持久化 `last_event_id` 于 `sessionStorage`（每 tab 独立即可）。
2. **统一事件分发器**：根据 `conversation_id` 分发给「当前会话 reducer」与「全局会话列表 / toast」；**删除** `use-global-message-toast` 内 **3s 全量 list + 多 EventSource**；toast 仅消费用户流事件。
3. **`chat-workspace-page`**：**移除**对 `streamConversationEvents` 的依赖；合并为同一 `userStream` 订阅。
4. **`im-chat-api.ts`**：删除或内联 `streamConversationEvents` / 多路 `EventSource`；保留 HTTP API。
5. **`AppProviders` / `chat` 根**：在壳层挂载单一 `UserStreamProvider`（或等价），确保 `/settings` 与 `/chat` 共享连接（若希望 settings 页也能收 toast）。
6. **Resync**：处理 `resync_required` → 调 `/im/v1/sync` → `queryClient.setQueryData`。
7. **测试**：单测 mock WS；关键集成：**多会话事件顺序**、**重连 replay**、**两 tab 重复事件去重**。

---

## 8. 测试与验收

- **集成测试**：`append_event` 后指定用户 WS 收到帧；非成员收不到。
- **Replay**：`after_event_id` 在中间、大批量、过旧 cursor → `resync_required`。
- **压测（可选）**：200 连接、每用户 3 tab，内存与 FD 在单进程预算内。

---

## 9. 风险与备注

- **SQLite 单写**：高并发写事件时仍是单连接；200 用户通常足够；若 relay 突发极高再考虑 WAL/队列。
- **可见性**：`resolve_event_recipient_user_ids` 必须与 **「谁能看到该会话」** 完全一致，否则漏推或多推；实现时对照 `WebIMService.get_conversation` / 列表过滤逻辑（若后续加了 owner 维度过滤一并复用）。
- **代理**：内网访问公网 WSS 用 443；文档提醒企业代理需放行长连接。
- **CORS**：WS 不受 CORS 同源限制同 REST，但 cookie 方案需注意 SameSite；当前若以 query/header 传用户身份，迁移期与现网一致。

---

## 10. 建议实施顺序（里程碑）

| 阶段 | 内容 |
|------|------|
| M1 | Registry + `append_event` 广播 + 最小 WS（无 replay）+ 前端只订阅打印日志 |
| M2 | `resume` + 时间窗 + `resync_required` + `GET /im/v1/sync` |
| M3 | 前端替换 SSE / 删除 toast 轮询；E2E 手动验收 |
| M4 | 删 SSE 路由与死代码；更新 SPEC；补集成测试 |

---

**文档版本**：2026-03-27；依据仓库路径 `src/IM/` 与前端 `src/IM/frontend/` 当前结构整理。
