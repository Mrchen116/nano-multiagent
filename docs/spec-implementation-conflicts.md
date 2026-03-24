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

### M304：Gateway send_message 目标分类与落点收敛（部分）
- 已新增显式目标分类与落点解析：`conversation_id / agent_id / user_id`
- 为 `agent_id` / `user_id` 目标补齐 direct 会话落点（缺失时自动创建）
- direct 复用已按 `direct_kind` 语义区分 `agent-agent` 与 `user-agent`
- 已补充对应 gateway handler 测试
- 仍未闭环部分：`personal_assistant` 侧 `/internal/dispatch` 尚未接入该解析入口，因此“工具调用到网关落点”的端到端链路仍待后续里程碑接线

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

## 1. 当前剩余冲突

- **`send_message(to=...)` 的 Gateway internal dispatch 链路仍未完全端到端闭环**
  - IM 侧已具备目标分类和会话落点解析能力；但 `personal_assistant` 的 `/internal/dispatch` 入口尚未接线到该能力，仍待后续里程碑完成全链路收敛。

- **前端群聊 mention 候选仍偏 agent，不是完整 user+agent identity 视图**
  - 当前 mention 候选已增强 `agent_id` 标识，但仍主要围绕 agent 候选，而不是完整覆盖群聊中的 user/agent 参与者标识视图。

- **UI 的 agent-agent direct 发现规则仍可继续增强**
  - 当前已完成显式分组展示；若要做到更强 discoverability（置顶/过滤/独立入口），仍需后续产品化细化。

## 2. 汇总结论

当前最新 spec 的主方向已经明显收敛为：
- Actor-first 身份模型
- `send_message(to)` 使用 `user_id / agent_id / conversation_id`
- `direct` 语义明确区分 user-agent 与 agent-agent
- agent-agent 单聊对用户可发现、可查看
- 一期群聊上下文注入应注入当前群聊中的用户与 Agent 参与者标识

经过本轮 M301–M306 改造后，已完成的部分包括：
- 后端 domain / repository / API 的 actor-first 主语义
- send_message 工具契约文案对齐
- Gateway → session metadata → prompt context 的 actor-first 参与者注入
- 前端 conversation / message 的 actor-first 主路径与 direct 语义收敛
- Gateway 侧 send_message 目标分类与 direct 落点能力
- 前端 discoverability / mention 的一轮增强
- prompt 中 direct reply 与 cross-conversation `send_message` 的边界澄清

当前剩余冲突主要集中在：
- `/internal/dispatch` 到 Gateway 新目标解析入口的端到端接线
- 群聊 mention 候选是否要升级为完整 user+agent identity 视图
- agent-agent direct 是否需要更强产品化发现入口
