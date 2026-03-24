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

## 0. 状态更新（2026-03-24）

以下冲突已由本轮里程碑关闭，不再视为“当前冲突”：

### M301：后端 Actor-first 契约收敛

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

### M302：上下文注入 / 提示词收敛

> 本小节仅标注「上下文注入 / 提示词」范围的落地状态；不覆盖 IM domain、前端或 send_message 全链路改造。

- 群聊 session metadata 已改为 actor-first 规范化：
  - relay `participants` 会被规范为 `participants[{type,user_id|agent_id,display_name}]`
  - `participant_agent_ids` 由结构化 participants 派生；无结构化数据时回退为当前 `agent_id`，不再使用 mention 列表
  - 相关文件：`src/personal_assistant/gateway/inbound_pipeline.py`

- communication context hook 已优先展示稳定标识：
  - user 显示 `user_id`
  - agent 显示 `agent_id`
  - `send_message` 目标格式明确为 `user_id / agent_id / conversation_id`
  - 相关文件：`src/agent/products/personal_assistant/hooks/communication_context.py`

- personal_assistant 提示词与系统提示词文档已同步：
  - 群聊按配置回复策略
  - `send_message(to=...)` 的目标标识规则
  - 当前会话直接回复 vs 跨会话发送的边界
  - 相关文件：`src/agent/products/personal_assistant/prompts.py`、`docs/内核设计细化/系统提示词.md`

### M303：前端 actor-first / direct 语义收敛

- 前端 API 主路径已切到 Actor-first：
  - `Conversation.participants(actor[])`
  - `Message.sender(actor)`
  - `participant_ids` / `sender_user_id` 仅保留兼容回退
  - 相关文件：`src/IM/frontend/src/features/chat/im-chat-api.ts`

- direct 语义已在前端显式区分：
  - 区分 user-agent direct、agent-agent direct 等 direct 语义
  - agent-agent direct 保持用户可发现
  - 相关文件：`src/IM/frontend/src/features/chat/im-chat-api.ts`

- 会话列表与发现文案已去除“只读协调线程 / Agents only”导向：
  - 改为 direct/shared thread 的统一发现语义
  - 相关文件：`src/IM/frontend/src/features/chat/components/conversation-list.tsx`

- 仍待后续里程碑继续细化：
  - 群聊 mention 候选仍偏 agent-oriented，尚未扩展为完整 user+agent 标识视图
  - UI 侧尚未新增单独的 agent-agent direct 分组/发现交互

### M304：Gateway send_message 目标分类与落点收敛（部分）

- 已新增显式目标分类与落点解析：
  - 分类 `conversation_id / agent_id / user_id`
  - 为 `agent_id` / `user_id` 目标落到 direct 会话（缺失时自动创建）
  - direct 复用按 `direct_kind` 语义区分（`agent-agent` vs `user-agent`）
  - 相关文件：`src/IM/ws/gateway_handler.py`、`tests/im_service/unit/test_gateway_handler.py`

- 当前仍未闭环的部分：
  - `personal_assistant` 侧 `/internal/dispatch` 尚未接入该解析入口，因此“工具调用到网关落点”的端到端链路仍待后续里程碑接线。

## 1. 核心数据模型 / 路由语义

- **`send_message(to=...)` 的 Gateway internal dispatch 链路仍未完全端到端闭环**
  - IM 侧已具备目标分类和会话落点解析能力；但 `personal_assistant` 的 `/internal/dispatch` 入口尚未接线到该能力，仍待后续里程碑完成全链路收敛。

- **单聊落点能力已补齐，但尚未接入 dispatch 入口**
  - `src/IM/ws/gateway_handler.py:resolve_send_message_target`
    - `agent_id` 目标：落到 `agent-agent` direct
    - `user_id` 目标：落到 `user-agent` direct
    - `conversation_id` 目标：直接落到指定群聊
  - 仍需把该能力接入实际 `/internal/dispatch` 调用链。

- **direct 复用语义已收敛**
  - `src/IM/ws/gateway_handler.py:_find_canonical_direct_conversation`
    - 已按 `expected_direct_kind` 区分并优先复用 `user-agent` / `agent-agent` 语义一致的 direct 会话。

- **`task` 子 Agent 不具备 `send_message` 能力，目前主要靠外围约定**
  - `src/IM/ws/gateway_handler.py:_resolve_source_agent_id_from_session`
    - 发起方身份来自 session metadata 中的 `agent_id`
  - 没有链路内强校验，只是外围能力配置在限制。

## 2. Prompt / 前端语义

- **前端群聊 mention 候选仍主要突出 agent，不完整覆盖 user participant identity**
  - `src/IM/frontend/src/features/chat/im-chat-api.ts`
    - `toMentionCandidates()` 仍主要返回 agent mention 候选
  - 与一期 spec 强调“当前群聊中的用户与 Agent 参与者标识”仍有差距。

- **UI 没有明确承载 agent-agent 单聊的发现规则**
  - `src/IM/frontend/src/features/chat/components/conversation-list.tsx`
    - 当前仍以列表映射显示为主，没有专门的发现/分组逻辑。

- **提示词对“何时 direct reply、何时 send_message”仍可能存在边界模糊**
  - `src/agent/products/personal_assistant/prompts.py`
  - `docs/内核设计细化/系统提示词.md`
  - 尽管已补充 `send_message(to=user_id)` 语义，但复杂场景下的策略边界仍值得继续细化。

## 3. 汇总结论

当前最新 spec 的主方向已经明显收敛为：
- Actor-first 身份模型
- `send_message(to)` 使用 `user_id / agent_id / conversation_id`
- `direct` 语义明确区分 user-agent 与 agent-agent
- agent-agent 单聊对用户可发现、可查看
- 一期群聊上下文注入应注入当前群聊中的用户与 Agent 参与者标识

经过本轮 M301 / M302 / M303 改造后，已完成的部分包括：
- 后端 domain / repository / API 的 actor-first 主语义
- send_message 工具契约文案对齐
- Gateway → session metadata → prompt context 的 actor-first 参与者注入
- 前端 conversation / message 的 actor-first 主路径与 direct 语义收敛

当前剩余冲突主要集中在：
- Gateway internal dispatch 的目标类型与落点完整闭环
- 一些前端发现逻辑与 mention 语义的进一步细化
- prompt 中复杂通信策略边界的继续收敛
