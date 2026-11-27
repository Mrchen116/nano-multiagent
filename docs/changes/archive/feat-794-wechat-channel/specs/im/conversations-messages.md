# im/conversations-messages.md (delta for feat-794)

## MODIFIED Requirements

### Requirement: 外部 channel 影子会话按外部身份幂等创建

IM 支持为 Gateway 创建带 `external_source` 和 `external_chat_id` 标记的影子会话,用于镜像外部 channel 中的聊天。1:1 私聊映射为 `direct` 类型,群聊映射为 `group` 类型。会话按 `(external_source, external_chat_id, agent_id, owner_id)` 幂等创建或查找;`agent_id` 使用 IM 现有 conversation agent 配置维度,不引入第二套 agent 身份来源。未手动改名的影子会话标题前缀优先使用目标 Agent 当前公开显示名（无显示名时回退 `agent_id`），在 Agent 或 Personal Agent 更新显示名时同步刷新未手动改名的影子会话标题。

#### Scenario: 外部 1:1 会话在内部 IM 有独立会话
- **GIVEN** Gateway 请求为 plato 的飞书 1:1 聊天创建影子会话
- **WHEN** IM 收到 `POST /im/v1/conversations/external/find-or-create`
- **THEN** 返回一个类型为 `direct`、标题为 `plato · feishu` 的会话
- **AND** 重复请求同一四元组时返回同一会话

#### Scenario: 外部群聊在内部 IM 有独立 group 会话
- **GIVEN** Gateway 请求为 plato 的飞书群「产品群」创建影子会话
- **WHEN** IM 收到 `POST /im/v1/conversations/external/find-or-create`
- **THEN** 返回一个类型为 `group`、标题为 `plato · 产品群 · feishu` 的会话
- **AND** 参与者包含 IM owner 和 plato agent

#### Scenario: 同一外部群绑定多个 agent 时生成多个独立会话
- **GIVEN** 飞书群「产品群」同时配置了 plato 和 luban
- **WHEN** Gateway 分别为 plato 和 luban 请求创建影子会话
- **THEN** IM 生成两个独立的 group 会话,标题分别为 `plato · 产品群 · feishu` 和 `luban · 产品群 · feishu`

#### Scenario: 影子会话默认标题使用 Agent 当前显示名并在 Agent 改名时同步
- **GIVEN** 目标 Personal Agent 或普通 Agent 的内部标识为自动生成 ID（如 `pa_...`），公开显示名为 `小助`
- **WHEN** Gateway 为其微信或飞书会话创建/同步影子会话，或主人随后修改该 Agent 的公开显示名
- **THEN** 未手动改名的影子会话标题显示 `<公开显示名> · wechat` / `<公开显示名> · feishu`（群聊保留中间群名），不直接把内部 `pa_...` 标识暴露为默认标题前缀；用户已手动改名的影子会话保留自定义标题

### Requirement: 真人发送的普通聊天消息提供逐人回执

#### Scenario: 聚合展示私聊与群聊回执
- **WHEN** 真人在 Nano 私聊向真人或 Global Agent 发送消息，或在群聊中发送普通消息
- **THEN** 消息发送者可辨认待送达、已送达和已读，并按收件人查看状态
- **AND** 群聊主时间线以发送时其他有收件资格的成员为范围；群话题回复只把当时关注该话题的人计入范围。因 Agent 协作范围排除的目标不占分母，全部计入范围内的人送达后才显示已送达，全部已读后才显示已读

#### Scenario: 外部 1:1 影子会话同步主人向 Global Agent 或 PA 的逐人回执
- **WHEN** 已绑定外部私聊通道（飞书或个人微信）的主人在外部 1:1 私聊向 Global Agent 或 Personal Agent 发送普通消息并镜像至内部 IM 影子会话，或直接在内部 IM 该 1:1 影子会话中发送消息
- **THEN** 内部 IM 影子会话中的主人消息同样提供逐人回执，按收件 Agent 的模型提醒送达与 `inbox` 实际读取事实依次从待送达推进至已送达与已读，并实时通知在线客户端刷新
- **AND** 外部群聊影子会话、非主人外部私聊消息、被协作范围或审批拦截跳过的消息以及 SingleThread 会话不生成逐人回执；Personal Agent 观察其他群聊或会话仍不改变原有已读状态

#### Scenario: 各收件人的状态独立推进
- **WHEN** 部分收件人确认收件或已读
- **THEN** 发送者可以查看这些人的最新状态，其他收件人维持最近一次已确认状态
- **AND** 对 Global Agent，已送达以本条消息的 Inbox 提醒实际进入模型请求、且该请求返回有效模型内容为准；仅持久入箱、进入调度队列或开始请求不能推进已送达。已读以模型调用 Inbox read 成功取得完整消息且读取事实已持久化为准

#### Scenario: Agent 忙碌或离线时不提前显示送达
- **GIVEN** 新消息已持久进入 Agent Inbox，但其提醒仍排队、请求未发出，或请求未返回有效模型内容
- **THEN** 该 Agent 的回执保持待送达；节点在线或传输确认不改变这一状态
- **WHEN** 包含该条消息提醒的模型请求返回有效内容
- **THEN** 仅推进该提醒实际覆盖的消息，不把稍后到达或按范围取消的消息一起标记已送达；重试与恢复重复证据不重复推进
- **AND** Inbox check、读取失败或只取得部分内容不产生已读回执
