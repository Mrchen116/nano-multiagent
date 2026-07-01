# im Specification (delta for feat-447)

## ADDED Requirements

### Requirement: 外部 channel 影子会话

IM 支持创建带有 `external_source` 和 `external_chat_id` 标记的会话,用于镜像外部 channel 中的聊天。1:1 私聊映射为 `direct` 类型,群聊映射为 `group` 类型。会话按 `(external_source, external_chat_id, agent_id, owner_id)` 幂等创建或查找;实现上 `agent_id` 对应现有 conversation agent 配置维度,不得产生第二套 agent 身份来源。

#### Scenario: 外部 1:1 会话在内部 IM 有独立会话
- **GIVEN** Gateway 请求为 plato 的飞书 1:1 聊天创建影子会话
- **WHEN** IM 收到 `POST /im/v1/conversations/external/find-or-create`
- **THEN** 返回一个类型为 `direct`、标题为 `plato · feishu` 的会话;重复请求同一四元组时返回同一会话

#### Scenario: 外部群聊在内部 IM 有独立 group 会话
- **GIVEN** Gateway 请求为 plato 的飞书群「产品群」创建影子会话
- **WHEN** IM 收到 `POST /im/v1/conversations/external/find-or-create`
- **THEN** 返回一个类型为 `group`、标题为 `plato · 产品群 · feishu` 的会话,参与者为 IM owner 和 plato agent

#### Scenario: 同一外部群绑定多个 agent 时生成多个独立会话
- **GIVEN** 飞书群「产品群」同时配置了 plato 和 luban
- **WHEN** Gateway 分别为 plato 和 luban 请求创建影子会话
- **THEN** IM 生成两个独立的 group 会话,标题分别为 `plato · 产品群 · feishu` 和 `luban · 产品群 · feishu`

### Requirement: 外部 channel 消息写入

IM 支持将来自外部 channel 的用户消息写入影子会话。消息持久化发送者显示名 `sender_display_name`;外部群成员显示原名字,IM owner 自己从外部 channel 发送的消息显示为「你」。

#### Scenario: 外部 1:1 用户消息显示为「你」
- **GIVEN** Gateway 写入一条 IM owner 从飞书 1:1 发来的消息
- **WHEN** 用户通过 REST 或 WebSocket 查看该会话历史
- **THEN** 该消息显示为「你」发送

#### Scenario: 外部群聊消息显示原发送者名字
- **GIVEN** Gateway 写入一条 Alice 从飞书群发来的消息
- **WHEN** 用户通过 REST 或 WebSocket 查看该会话历史
- **THEN** 该消息显示为 Alice 发送

### Requirement: 外部 channel 会话元数据回环

IM 通过 WebSocket relay 把影子会话中的用户消息转发给 Gateway 时,必须携带该会话的外部 channel 元数据(`external_source`、`external_chat_id`、`agent_id`、`conversation_type`)以及触发来源标记(`trigger_source`),使 Gateway 能够复用同一 kernel session、识别影子 group,并按触发源决定回复去向。`external_chat_id` 指外部 channel 的 chat id,不是 IM conversation id。

#### Scenario: 内部 IM 消息被 Gateway 识别为 IM 来源
- **GIVEN** 内部 IM 中存在 `plato · feishu` 影子会话
- **WHEN** 用户在该会话中发送消息
- **THEN** Gateway 收到该消息后,将其识别为来自 IM 的触发,agent 回复只留在 IM,不回写飞书

#### Scenario: 影子群聊消息携带 conversation_type
- **GIVEN** 内部 IM 中存在 `plato · 产品群 · feishu` group 影子会话
- **WHEN** 用户在该会话中发送消息
- **THEN** relay payload 携带 `conversation_type="group"`、`external_source="feishu"`、飞书 `external_chat_id` 和 `agent_id="plato"`,Gateway 可按 group 路径触发 agent 回复

### Requirement: 现有 IM 行为不变

外部 channel 影子会话和消息的加入不影响 IM 现有 direct/group 会话、普通用户消息、agent 消息渲染、权限模型。

#### Scenario: 普通直连会话不受外部 channel 影响
- **GIVEN** 用户与 plato 有一个普通直连会话
- **WHEN** 用户在飞书与 plato-bot 对话
- **THEN** 飞书同步产生的 `plato · feishu` 会话与普通直连会话保持独立,互不合并
