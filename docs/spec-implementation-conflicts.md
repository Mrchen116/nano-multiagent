# Spec 与现实现状冲突清单

本文档记录“当前代码实现”与最新 SPEC 之间的主要冲突点。

范围：
- `docs/需求.md`
- `docs/specs/im/spec.md`
- `docs/specs/gateway/spec.md`
- `docs/内核设计细化/系统提示词.md`

说明：
- 本文档只记录冲突/偏差，不给出实现方案。
- 以“新的 SPEC 设计”为准，不考虑后向兼容。

## 0. 状态更新（2026-03-24）

以下冲突已由本轮里程碑关闭，不再视为“当前冲突”：

### M301：后端 Actor-first 契约收敛
- IM domain 已补 Actor-first 结构：`Conversation.participants(actor[])`、`Message.sender(actor)`、`Conversation.direct_kind`
- HTTP API 已提供 Actor-first 主语义并兼容旧字段输入：会话 API 返回 `participants` / `direct_kind`，消息 API 返回 `sender`
- Repository 边界已支持 actor 标识归一化：participant 支持 `user:<id>` / `agent:<id>`，sender 支持 agent actor id 解析
- `send_message` 工具契约文案已对齐 `to=user_id/agent_id/conversation_id`

### M302：上下文注入 / 提示词收敛
- 群聊 session metadata 已改为 actor-first 规范化：relay `participants` 规范为 `participants[{type,user_id|agent_id,display_name}]`
- `participant_agent_ids` 改为由结构化 participants 派生；无结构化数据时回退为当前 `agent_id`，不再使用 mention 列表
- communication context hook 已优先展示 `user_id` / `agent_id`
- personal_assistant 提示词与系统提示词文档已同步到新的目标标识规则

### M303：前端 actor-first / direct 语义收敛
- 前端 API 主路径已切到 Actor-first：`Conversation.participants(actor[])`、`Message.sender(actor)`
- `participant_ids` / `sender_user_id` 仅保留兼容回退
- direct 语义已在前端显式区分，agent-agent direct 保持用户可发现
- 会话列表与发现文案已去除“只读协调线程 / Agents only”导向

### M304：Gateway send_message 目标分类与落点收敛
- 已新增显式目标分类与落点解析：`conversation_id / agent_id / user_id`
- 为 `agent_id` / `user_id` 目标补齐 direct 会话落点（缺失时自动创建）
- direct 复用已按 `direct_kind` 语义区分 `agent-agent` 与 `user-agent`
- 已补充对应 gateway handler 测试

### M305：前端发现与 mention 收敛
- mention 候选已增强为稳定标识展示：候选 label 显式包含 `agent_id`，并保持排序/去重
- group / agent-network 场景下，discoverability hint 已附带 `user_id` / `agent_id` 摘要
- Conversation list 已加入显式分组：`Agent-to-agent direct` / `Group chats` / `Direct chats` / `Other`
- agent-agent direct 的发现规则从“仅列表映射”提升为一等可见分区

### M306：通信边界提示词收敛
- 已明确“当前会话直回 vs 跨会话 send_message”硬边界：
  - 当前会话回复：直接输出文本，不调用 `send_message`
  - 跨会话投递：仅用 `send_message(to=user_id|agent_id|conversation_id)`
  - 需要“会话内可见 + 会话外投递”时：先会话内回复，再调用 `send_message`
- 上述边界已同步到运行时 prompt、communication context hook、系统提示词文档

### M307：`/internal/dispatch` 端到端接线收敛
- IM Gateway 已支持 `agent.message` 入站处理，按 `to=user_id|agent_id|conversation_id` 分类落点并持久化消息
- `send_message` 工具发送时优先透传 `agent_id` 到 `from_session_id`，使 dispatch 链路可稳定识别发起 agent
- 相关测试已覆盖 `agent.message` 的 user/direct 落点与无效来源错误路径

### M308：前端完整身份可见性收敛（discoverability）
- 会话参与者摘要在 `group` / `agent-network` 场景改为显示完整身份：`display_name + user_id/agent_id`
- 会话 discoverability hint 显式展示用户与 agent 身份摘要，不再只偏向 agent 语义
- 会话列表卡片新增 discoverability hint 展示，身份语义对用户可见
- mention 候选已具备稳定身份展示能力，并为后续 mention 目标扩展打通前端语义基础

### M309：群聊 mention 全参与者目标收敛
- 群聊 mention 候选从 agent-only 扩展为 user+agent 全参与者可选（排除当前用户）
- group discoverability hint 已与实现一致：mentions 支持 participant IDs（`user_id` / `agent_id`）
- 对应提示词已明确“群聊 mention 可使用 `user_id` / `agent_id` 稳定标识”

### M312：`send_message` 去重与反馈一致性收敛
- Gateway `agent.message` 入站新增 dispatch 请求幂等日志：同一 `tool_call` 请求重放时复用首次落点，不再重复写入 agent-agent direct 消息
- `send_message` 工具发送时附带稳定 `tool_call` 请求标识，并在 Gateway 端解析为 source + dispatch key，实现同请求单次投递
- `send_message` 工具改为以 Gateway JSON 回包作为成功判定（`ok=true`），并移除读超时上限，避免“实际已路由成功但工具侧误报 timeout”
- personal_assistant 提示词已补充：群聊内对 `send_message` 状态反馈必须严格基于工具返回结果

### M313：agent-to-agent DM 列表预览刷新收敛
- 前端会话摘要层新增“最新消息预览快照”缓存，统一记录每个会话最近一次可见预览内容与时间
- `getConversation` / `listConversations` / `sendMessage` 会同步更新预览快照，避免左栏摘要停留在旧 DM 文案
- ConversationList 渲染时优先使用最新快照，确保 agent-to-agent direct 会话在 DM 送达后与详情页最后一条内容保持一致

## 1. 当前剩余冲突

- M311 浏览器验收发现的两项问题已进入修复并合并；当前待以真实浏览器重新验收确认已关闭。

## 2. 汇总结论

当前最新 spec 的主方向已经明显收敛为：
- Actor-first 身份模型
- `send_message(to)` 使用 `user_id / agent_id / conversation_id`
- `direct` 语义明确区分 user-agent 与 agent-agent
- agent-agent 单聊对用户可发现、可查看
- 一期群聊上下文注入应注入当前群聊中的用户与 Agent 参与者标识

经过本轮 M301–M313 改造后，已完成的部分包括：
- 后端 domain / repository / API 的 actor-first 主语义
- send_message 工具契约文案对齐
- Gateway → session metadata → prompt context 的 actor-first 参与者注入
- 前端 conversation / message 的 actor-first 主路径与 direct 语义收敛
- Gateway 侧 send_message 目标分类与 direct 落点能力
- `/internal/dispatch` 到 Gateway 目标分类落点的端到端接线
- 前端 discoverability / mention 的完整 actor 目标收敛
- prompt 中 direct reply 与 cross-conversation `send_message` 的边界澄清
- 前端 `group` / `agent-network` 的完整身份可见性增强（display + user_id/agent_id）
- send_message 的幂等去重与真实反馈一致性
- agent-to-agent direct 列表预览与详情页一致性刷新
