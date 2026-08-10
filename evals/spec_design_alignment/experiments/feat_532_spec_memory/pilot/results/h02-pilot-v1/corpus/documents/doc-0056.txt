# bugfix-365: IM 失败 bubble 合并 relay.failed 原因，消除幽灵 "Agent" 行

## Relations

- Related: bugfix-361-im-running-watchdog（watchdog 引入）, bugfix-362-im-ghost-agent-reconcile（幽灵 agent 行另一来源）

## 原始报告

> 为啥会有这个出现，没有一个群成员叫这个名字。http://127.0.0.1:8011/chat/bd4b7e7f9d49471db63bdf28898bf4a1
> （截图：群聊里出现两条失败 bubble，第一条 "Q 14:45 失败"（content 空），第二条 "Agent 14:51 失败 / relay timed out after 300s with no completion event"）

> 上一条不是已经看到Q失败了吗，为啥还要搞这个

> 我觉得好的体验应该是把"relay timed out after 300s with no completion event"填充到"失败"那个bubble里

复现路径：`http://127.0.0.1:8011/chat/bd4b7e7f9d49471db63bdf28898bf4a1`，message_id=`327efabb1c494c3786b837a4c61fb233`。

## 澄清记录

- Q1: 失败 bubble 的"超时原因"文案放哪、什么样式？
  A(原话): 对
  Agent 解读: 采用推荐方案——文案作为 bubble 主内容渲染，沿用现有 failed 消息样式（"失败"红色 label 在下方），文案保留 `relay.failed` payload 里 `detail` 原文（如 "relay timed out after 300s with no completion event"，英文与日志一致便于排查）。若真实消息行已有部分流式 content（agent 吐了一半就挂），watchdog 文案作为副文本接在已产出内容之后，用一行空行分隔，前缀 `[error] `。

- Q2: 已存在的幽灵 "Agent" bubble 要不要回溯消失？
  A(原话): 不用管，开发态
  Agent 解读: 不需要数据回填或迁移脚本；前端读路径修好后，老会话刷新一次就干净，旧 `relay.failed` 事件行可保留在 DB 不动。

- Q3: 修复范围只处理 watchdog 超时还是所有 `relay.failed` 都合并？
  A(原话): 你来定，后面都你来思考定。我离开了
  Agent 解读: 采用推荐方案 —— 所有 `relay.failed` 都合并进真实失败 bubble，不区分失败子类型。理由：根因是 `_message_from_visible_event_row` 对任何 `relay.failed` 都会生成独立合成行，只修 watchdog 是治标。gateway 主动报错路径若 `detail` 缺失，由 worker 在实现阶段决定兜底文案（"消息发送失败" 之类）。

## 现象 / 复现

群聊会话里每出现一次 agent 消息失败（无论触发源是 watchdog 5 分钟超时、gateway 主动报错、还是 LLM 返回错误），都会出现**两条 bubble**：

1. **真实失败 bubble**：以 agent 自己的 display_name（例如 "Q"）作为发送者，content 通常为空，下方红色 "失败" label。
2. **幽灵失败 bubble**：发送者匿名兜底为 "Agent"（avatar 显示 "AG"），content 是 `relay.failed` 事件 payload 里的 `detail` 文本（例如 "relay timed out after 300s with no completion event"），下方红色 "失败" label。

复现步骤：
1. 在群聊里 `@` 一个 agent 发起消息。
2. 让 gateway 在该消息开始处理后挂掉（kill gateway 进程 / 网络断 / LLM 卡住超过 300s 不返回）。
3. IM 服务端 `relay_watchdog` 5 分钟扫一次，把 `running` 超时的消息翻成 `failed` 并写一条 `relay.failed` 事件。
4. 在前端 chat 历史里观察到两条失败 bubble（同一逻辑消息）。

实际样本：
- 会话 ID：`bd4b7e7f9d49471db63bdf28898bf4a1`
- 真实消息 ID：`327efabb1c494c3786b837a4c61fb233`（sender_user_id=`f29e2b531a3c415bb3087b3892f07551` / agent `ArchA` / display_name="Q"）
- 事件流：`message.sent` → `message.created` → (gateway 中断，无 `relay.processing`) → 5 分钟后 watchdog 写 `relay.failed`

## 根因

两个独立组件叠加导致一条消息渲染两次：

1. **IM 后端"合成消息"机制无去重**（`src/IM/infra/repositories.py` `_message_from_visible_event_row` + `_synthetic_message_id_from_event_payload`）：任何 `relay.failed` / `relay.completed` 事件都会被独立翻译成一条 "synthetic message"，id 形如 `{message_id}:agent`，与真实 `messages` 表行的 id 不冲突 → 两条都被加入会话消息流。这套机制原本是为"消息行 content 为空、文本只在事件 payload 里"的 `relay.completed` 流式场景设计的，但没考虑同 `message_id` 的真实消息行可能已经写好且处于终态——失败路径上这两条总会同时存在。

2. **`relay_watchdog._build_failed_payload` 在 `relay.processing` 缺失时丢失 agent 身份**（`src/IM/application/relay_watchdog.py`）：watchdog 通过查 `relay.processing` 事件继承 `agent_id` / `sender_display_name`。本 bug 复现路径里 gateway 在写 `relay.processing` *之前* 就挂了，事件链只有 `message.sent` + `message.created`。watchdog 兜底 payload 只含 `message_id` / `detail` / `reason`，**没有 `agent_id`**。

   进而触发 `_actor_from_event_payload`（`repositories.py:1257`）的兜底分支：`agent_id` 为 None 时返回 `Actor(type="agent", display_name=None, user_id="agent:Agent")`，前端 `getGroupMessageSenderLabel`（`message-pane.tsx:258`）对 `sender_display_name=undefined && sender_type=agent` 兜底显示 "Agent"。

**为什么这种错能进来**：
- bugfix-361 引入 watchdog 时，把"补发 `relay.failed` 事件"和"翻转真实消息行状态"做成了两件事，意图是让前端通过 WebSocket 监听 `relay.failed` 即时更新状态。但同期合成消息机制（更早期为 `relay.completed` 设计）没收紧"真实消息行已存在时跳过合成"，两条路径在失败场景下叠加。
- `_build_failed_payload` 默认假定每次 `relay.failed` 之前都至少有一条 `relay.processing`（正常 gateway 路径确实如此），未覆盖 gateway 在 `processing` 之前就崩溃的边缘场景。
- 缺乏一条直接断言"同一个 message_id 在历史里不应产生超过一条 bubble"的契约/测试。

## 修复

三处改动（commits `f5a9100a` 红测 / `cf7af8d0` 实现）：

1. **后端合成行去重**（`src/IM/infra/repositories.py` `_message_from_visible_event_row`）：把 `relay.completed` / `relay.failed` 事件翻译成合成消息前，先查 `messages` 表里是否已存在 `id == payload.message_id` 的真实行。当真实行的 `sender_type='agent'` 且 `delivery_status ∈ {failed, completed}` 时直接返回 None，跳过合成。`sender_type='agent'` 的限定是关键：保留了"一条用户消息扇出多条 agent 合成回复"这条遗留路径(用户消息 row 是 `sender_type='user'`，不触发去重)。

2. **失败 bubble 内容回填**（`src/IM/application/relay_watchdog.py` `_backfill_failure_detail_into_message_content`）：watchdog 在翻转消息为 `failed` 后，把 `detail` 文本写到 `messages.content`。空 content 直接写入；已有部分流式 content 时，追加一个空行 + `[error] <detail>` 后缀，保留 agent 在崩溃前已吐出的文字。

3. **watchdog 兜底身份补全**（`src/IM/application/relay_watchdog.py` `_build_failed_payload`）：当 `relay.processing` 事件缺失时，回退查 `messages.sender_user_id` → `users.username = agent:<id>` 链路，把 `agent_id` 和 `sender_display_name` 写回 `relay.failed` payload。即使未来去重逻辑漏了，匿名 "Agent" 兜底也不会再出现。

## 验证

**单元测试**（`pytest tests/im_service/unit/test_relay_watchdog.py tests/im_service/unit/test_repositories.py`，24 passed）：

- `test_list_messages_dedups_relay_failed_when_real_terminal_row_exists`：真实 failed agent row 存在时 `relay.failed` 合成行被抑制，最终只有一条 failed bubble。
- `test_scan_writes_detail_into_empty_message_content`：watchdog 翻转空 content 消息后，content 变为 "relay timed out after 300s with no completion event"。
- `test_scan_appends_error_note_to_partial_streamed_content`：watchdog 保留 partial content 且追加 `[error] ...` 后缀。
- `test_scan_recovers_agent_identity_when_relay_processing_missing`：无 `relay.processing` 时仍能从 `messages` 表补全 `agent_id` + `sender_display_name`。
- 原 4 个 watchdog 行为测试 + 既有 17 个 repositories 测试全部继续通过，无回归。

**关联 IM 套件回归**：`pytest tests/im_service/ tests/unit/IM/ -m "not e2e"` —— 修改前后失败列表对照(28 个失败均与本次无关：401 auth / 既有 broadcast / conversation_rename 等，与本 unit 涉及文件无交集)，引入零回归。

**生产数据现状**：会话 `bd4b7e7f9d49471db63bdf28898bf4a1` 的 message `327efabb...` 历史上的 `relay.failed` 事件保留在 DB 不动；前端读路径修复后该事件不再生成合成行，幽灵 "Agent" bubble 自动消失。真实 "Q 失败" bubble 的 content 仍是空（旧 watchdog 没回填）—— 开发态，按 Q2 的决定不做数据迁移，新一次失败会带 detail 文本。
