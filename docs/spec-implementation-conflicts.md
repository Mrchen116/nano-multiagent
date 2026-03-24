# Spec 与现实现状冲突清单

本文档记录“当前代码实现”与最新 SPEC 之间的主要冲突点。

范围：
- `docs/需求.md`
- `docs/IM-SPEC.md`
- `docs/NodeGateway-SPEC.md`
- `docs/内核设计细化/系统提示词.md`

说明：
- 本文档只记录冲突/偏差，不给出实现方案。
- 以“新的 SPEC 设计”为准，不考虑后向兼容。

## 0. 状态更新（M301，2026-03-24）

以下冲突已由 M301 后端改造关闭，不再视为“当前冲突”：

- IM domain 已补 Actor-first 结构：
  - `Conversation.participants(actor[])`
  - `Message.sender(actor)`
  - `Conversation.direct_kind`（user-agent / agent-agent 等 direct 子语义）
  - 相关文件：`src/IM/domain/models.py`

- HTTP API 已提供 Actor-first 主语义并兼容旧字段输入：
  - 会话 API：新增 `participants`，并返回 `direct_kind`
  - 消息 API：新增 `sender`
  - 相关文件：`src/IM/api/routes/web_im.py`、`src/IM/api/routes/messages.py`

- Repository 边界已支持 actor 标识归一化：
  - participant 支持 `user:<id>` / `agent:<id>` 解析
  - sender 支持 agent actor id 解析并写回 sender(actor) 语义
  - 相关文件：`src/IM/infra/repositories.py`

- `send_message` 工具契约文案已对齐 `to=user_id/agent_id/conversation_id`：
  - 相关文件：`src/agent/products/personal_assistant/tools/send_message.py`

> 说明：本次仅更新后端职责范围。Gateway internal dispatch 的目标分类校验、前端语义与提示词相关冲突仍保留在下文。

## 1. IM 服务

- **Actor-first 模型未落地到核心 domain**
  - `src/IM/domain/models.py:95`
    - `Conversation` 仍使用 `participant_ids: list[str]`
  - `src/IM/domain/models.py:113`
    - `Message` 仍使用 `sender_user_id` + `sender_type`
  - 与 `docs/IM-SPEC.md` 的 Actor-first 和 `Message.sender(actor)` 冲突；当前 domain 仍以内置 `user_id` 为一等身份模型。

- **HTTP API 仍直接暴露内部 user-id 语义**
  - `src/IM/api/routes/web_im.py:15`
    - `CreateConversationRequest.participant_ids`
  - `src/IM/api/routes/web_im.py:31`
    - `ConversationResponse.participant_ids`
  - `src/IM/api/routes/messages.py:31`
    - `CreateMessageRequest.sender_user_id`
  - `src/IM/api/routes/messages.py:42`
    - `MessageResponse.sender_user_id`
  - 与 `docs/IM-SPEC.md:112` 中“对外接口以 Actor 语义建模，不暴露 IM 内部路由主键”冲突。

- **会话创建逻辑仍按“两个内部 user 就是 direct”处理**
  - `src/IM/infra/repositories.py:330`
    - `conversation_type = "direct" if len(normalized_participants) == 2 else "group"`
  - 当前只按参与者数量决定 `direct/group`，没有区分：
    - 用户-Agent 单聊
    - Agent-Agent 单聊
  - 与 `docs/IM-SPEC.md:159` 的 direct 语义区分不一致。

- **Agent-Agent 单聊的可见性/可发现性没有后端模型支撑**
  - `src/IM/infra/repositories.py:533`
    - `Conversation.participant_ids` 只返回参与者 user_id
  - `src/IM/application/web_im_service.py:48`
    - `list_conversations()` 只是全量列会话，没有“同一 owner 空间内对用户可发现、可查看”的专门规则
  - 与 `docs/需求.md:95`、`docs/IM-SPEC.md:35` 不一致。

- **前端仍靠派生/猜测会话语义，而不是后端提供一等语义**
  - `src/IM/frontend/src/features/chat/im-chat-api.ts:378`
    - 只有当前端 `conversationType === "agent-network"` 时才标成 `Agent-to-agent chat`
  - `src/IM/frontend/src/features/chat/im-chat-api.ts:815`
    - `participants` 只是从 `participant_ids` 映射 display name
  - 后端 `Conversation.type` 只有 `direct/group`，没有 Actor-typed participants 或 direct 子语义。

- **Gateway 处理 agent→agent 消息时仍完全依赖 IM user 映射**
  - `src/IM/ws/gateway_handler.py:471`
    - 通过 `username=f"agent:{source_agent_id}"` / `agent:{target_agent_id}` 找 IM user
  - `src/IM/ws/gateway_handler.py:479`
    - `_find_canonical_direct_conversation(left_user_id=..., right_user_id=...)`
  - `src/IM/ws/gateway_handler.py:485`
    - `participant_ids=[source_user.id, target_user.id]`
  - `src/IM/ws/gateway_handler.py:490`
    - `sender_user_id=source_user.id`
  - 与新 spec 中 `agent_id / user_id / conversation_id` 的稳定业务标识模型不一致。

- **Message API 与 spec 的 sender(actor) 设计不一致**
  - `src/IM/api/routes/messages.py:33`
    - `sender_type: str = "user"`
  - `src/IM/api/routes/messages.py:31`
    - `sender_user_id: str`
  - 仍是“类型 + 内部主键”双字段，不是 `sender = {type, id}` 的 actor-first 结构。

- **Conversation API 与 spec 的 participants(actor[]) 设计不一致**
  - `src/IM/api/routes/web_im.py:16`
    - `participant_ids: list[str]`
  - 当前无法表达每个 participant 的 actor 类型，也无法直接表达 `user_id / agent_id / display_name`。

- **用户可查看但非参与者的 agent-agent 单聊，目前只是副作用，不是正式权限/发现模型**
  - `src/IM/infra/repositories.py:327`
    - `owner_id = uuid4().hex if len(owner_ids) > 1 else next(iter(owner_ids))`
  - 当前更像“owner scope 下顺带可见”，不是“用户是查看者但非参与者”的正式语义模型。

## 2. Gateway / `send_message` / 上下文注入

- **`send_message` 工具契约仍过窄**
  - `src/agent/products/personal_assistant/tools/send_message.py`
    - `description = "Send a message to another agent or group via the gateway IM routing layer."`
    - `input_schema.properties.to.description = "Target agent id or group id."`
  - 与 `docs/NodeGateway-SPEC.md:209` 冲突：spec 要求 `to` 支持 `user_id / agent_id / conversation_id`。

- **Gateway 内部分发没有形成三类目标标识契约**
  - `src/personal_assistant/gateway/internal_dispatch.py`
    - 仅把 `to` 原样透传：`{"to": to.strip(), "text": text.strip()}`
  - 没有 `user_id / agent_id / conversation_id` 的分类或校验。

- **WebSocket 协议仍是裸 `to`**
  - `src/personal_assistant/ws/im_connection.py`
    - 上行 payload 只有 `to/text/from_session_id`
  - 没有 target kind 字段，也没有基于三种稳定标识的显式协议区分。

- **IM 上行入口目前只支持 agent→agent**
  - `src/IM/ws/gateway_handler.py:_handle_agent_message`
    - `target_agent_id = _require_text(payload.get("to"), field_name="to")`
    - 直接 `target_user = self._find_user_by_username(username=f"agent:{target_agent_id}")`
  - 说明当前实现只支持 `agent_id`，与 `docs/NodeGateway-SPEC.md:209-212` 直接冲突。

- **单聊落点只覆盖 agent-agent 一种 case**
  - `src/IM/ws/gateway_handler.py:_handle_agent_message`
    - `source_user = agent:{source_agent_id}`
    - `target_user = agent:{target_agent_id}`
    - `create_conversation(participant_ids=[source_user.id, target_user.id])`
  - 未实现 agent-user 单聊和 `conversation_id` 群聊落点。

- **direct 复用语义过粗**
  - `src/IM/ws/gateway_handler.py:_find_canonical_direct_conversation`
    - 复用规则是“任意两个 participant user_id 的 direct conversation”
  - 没有区分 user-agent direct 和 agent-agent direct 的业务语义。

- **群聊一期上下文注入少了 `user_id`**
  - `src/agent/products/personal_assistant/hooks/communication_context.py:_build_communication_context_block`
    - user 条目只有 `"{display} (user)"`，没有 `user_id`
    - agent 条目才输出 `agent_id`
  - 与 `docs/NodeGateway-SPEC.md:220` 冲突：一期要求当前群聊中的用户和 Agent 参与者标识，用户使用 `user_id`。

- **群聊 session metadata 未提供用户稳定标识**
  - `src/personal_assistant/gateway/inbound_pipeline.py:_build_session_metadata`
    - 只给 agent participant 补 `agent_id = display_name`
    - 对 user participant 没有规范化出 `user_id`
  - 与一期 spec 冲突。

- **模型提示未对齐新的目标标识规则**
  - `src/agent/products/personal_assistant/hooks/communication_context.py`
    - 仅强调对 agent 使用 `agent_id`
    - 没有对应说明对用户使用 `user_id`、对群聊使用 `conversation_id`
  - 与 `docs/NodeGateway-SPEC.md:209`、`docs/内核设计细化/系统提示词.md:84` 冲突。

- **群聊上下文来源仍偏 mention-driven**
  - `src/personal_assistant/gateway/inbound_pipeline.py:_build_session_metadata`
    - fallback 仍保留 `participant_agent_ids = mentioned_agent_ids`
  - 这意味着缺少 `participants` 时，模型只拿到“被提及的 agent IDs”，不是“当前群聊中的参与者标识”。

- **`task` 子 Agent 不具备 `send_message` 能力，目前主要靠外围约定**
  - `src/IM/ws/gateway_handler.py:_resolve_source_agent_id_from_session`
    - 发起方身份来自 session metadata 中的 `agent_id`
  - 没有链路内强校验，只是外围能力配置在限制。

## 3. Prompt / 前端语义

- **系统提示词文档内部仍有自相矛盾**
  - `docs/内核设计细化/系统提示词.md:104`
  - `docs/内核设计细化/系统提示词.md:105`
  - 表格仍写：
    - `群聊 @mention 门控 + NO_REPLY`
    - `send_message | 可选工具，跨 agent/群组通信`
  - 但正文已改成“按配置的群聊回复策略”“可发 users / agents / groups”。

- **前端 API 契约仍是旧的 `participant_ids` / `sender_user_id`**
  - `src/IM/frontend/src/features/chat/im-chat-api.ts:18`
    - `ImConversation.participant_ids`
  - `src/IM/frontend/src/features/chat/im-chat-api.ts:56`
    - `ImMessage.sender_user_id`
  - 与新 spec 的 Actor-first 模型不一致。

- **群聊语义仍只突出 agent，不完整覆盖 user participant identity**
  - `src/IM/frontend/src/features/chat/im-chat-api.ts:48`
    - `toMentionCandidates()` 只产出 agent mention 候选
  - 与一期 spec 强调“当前群聊中的用户与 Agent 参与者标识”不一致。

- **前端仍天然偏向 user-agent direct 模型**
  - `src/IM/frontend/src/features/chat/im-chat-api.ts:845`
    - `resolveDirectAgentId()` 非 group 会话里只尝试解析一个 agent participant
  - `src/IM/frontend/src/features/chat/im-chat-api.ts:942`
    - `createDirectConversation()` 仍硬编码 `[selfUserId, peer.id]`
  - `src/IM/frontend/src/features/chat/im-chat-api.ts:966`
    - `createFreshDirectConversation()` 同样是用户与 agent peer 的 fresh session
  - 与新 spec 下“user-agent direct / agent-agent direct 显式区分”不一致。

- **`agent-network` 仍是前端派生标签，不是正式一等语义**
  - `src/IM/frontend/src/features/chat/im-chat-api.ts:378`
    - `agent-network` 被作为前端 `conversationType` 分支处理
  - `src/IM/frontend/src/features/chat/im-chat-api.ts:401`
    - discoverability 仍依赖这个旧派生类型
  - 与新 spec 中 direct 语义显式区分的方向不一致。

- **会话列表的身份语义不足**
  - `src/IM/frontend/src/features/chat/im-chat-api.ts:815`
    - 会话列表里的 `participants` 直接映射成 `display_name`
  - 稳定身份 `user_id / agent_id` 没有保留到 UI 语义层。

- **Conversation list 文案仍偏 user-agent / group 心智**
  - `src/IM/frontend/src/features/chat/components/conversation-list.tsx:56`
    - “Open an agent chat or create a shared thread”
    - “Agent chats launched from Settings reopen each agent's stable direct thread here...”
  - 没体现 agent-agent 单聊对用户可发现的一等地位。

- **UI 没有明确承载 agent-agent 单聊的发现规则**
  - `src/IM/frontend/src/features/chat/components/conversation-list.tsx:82`
    - 当前只是“若被映射成 item 就显示”，没有专门的发现/分组逻辑。

- **前端把 agent-agent 单聊额外收窄成“只读协调线程”**
  - `src/IM/frontend/src/features/chat/im-chat-api.ts:309`
  - `src/IM/frontend/src/features/chat/im-chat-api.ts:316`
  - `AGENT_NETWORK_*` 文案包含：
    - `Agents only`
    - `This is a read-only coordination thread`
  - 新 spec 只要求“用户可查看但非参与者”，并未要求只读。

- **提示词对“何时 direct reply、何时 send_message”仍有边界模糊**
  - `src/agent/products/personal_assistant/prompts.py:58`
  - `docs/内核设计细化/系统提示词.md:88`
  - “Reply directly with text for conversations. Only use the send_message tool to reach a specific chat channel.”
  - 在已允许 `send_message(to=user_id)` 的前提下，仍未讲清楚：
    - 群聊里想找用户私聊时，应直接回复当前会话还是调用 `send_message(to=user_id)`。

## 4. 汇总结论

当前最新 spec 的主方向已经收敛为：
- Actor-first 身份模型
- `send_message(to)` 使用 `user_id / agent_id / conversation_id`
- `direct` 语义明确区分 user-agent 与 agent-agent
- agent-agent 单聊对用户可发现、可查看
- 一期群聊上下文注入只注入当前群聊中的用户与 Agent 参与者标识

而当前实现仍主要停留在：
- internal `user_id` first
- `participant_ids` / `sender_user_id` 风格接口
- `send_message(to=<agent_id>)` 主要只支持 agent-agent direct
- 前端大量靠派生标签和文案猜语义

冲突最集中的文件：
- `src/IM/domain/models.py`
- `src/IM/api/routes/web_im.py`
- `src/IM/api/routes/messages.py`
- `src/IM/infra/repositories.py`
- `src/IM/ws/gateway_handler.py`
- `src/personal_assistant/gateway/inbound_pipeline.py`
- `src/agent/products/personal_assistant/hooks/communication_context.py`
- `src/agent/products/personal_assistant/tools/send_message.py`
- `src/IM/frontend/src/features/chat/im-chat-api.ts`
- `src/IM/frontend/src/features/chat/components/conversation-list.tsx`
- `docs/内核设计细化/系统提示词.md`
