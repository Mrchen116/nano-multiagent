# gateway/external-channels.md (delta for feat-803)

## MODIFIED Requirements

### Requirement: 飞书群聊背景上下文等价内部 IM 群聊

「团队公开」（`team`）下，飞书群动态纳入对应 Agent 的批次。Global 的任一聊天有高优消息时，同时列出积压；单会话仅在同一聊天遇到高优时带入该聊天背景。均受十分钟截止约束。「项目级」（`project`）与「私有」（`owner_only`）时照常镜像，Agent 不接收该飞书群背景。`@Bot` 既是用户可见消息内容，也是触发信号；Gateway 不得为了 mention gate 从 IM 展示或模型输入中删除 @ 内容。

#### Scenario: 未 @ 背景被纯 @Bot 触发使用
- **GIVEN** 「团队公开」下，用户在飞书群里发送“你会数学吗”且没有 @nano
- **WHEN** 用户随后只发送 `@nano`
- **THEN** nano 的回复能针对“你会数学吗”作答，而不是把 `@nano` 当成无上下文测试消息
- **AND** 两条用户消息都同步显示在内部 IM 影子群聊

#### Scenario: 普通群消息投递能力缺失时不能验收为支持背景上下文
- **GIVEN** Gateway 为「团队公开」Agent 配置了飞书群聊 channel
- **WHEN** 用户在飞书群发送不 @Bot 的消息
- **THEN** Gateway 必须能收到该事件并写入 IM 影子群聊和群背景上下文
- **AND** 如果飞书平台或 app 权限只投递 @Bot 事件，该配置不得被验收为支持飞书群聊背景上下文

#### Scenario: mention-only 和 mention+正文都保留用户可见内容
- **GIVEN** 用户在飞书群里发送 `@nano` 或 `@nano hi`
- **WHEN** Gateway 写入 IM 影子群聊并提交给 agent
- **THEN** IM 中该用户消息保留 `@nano` 或等效 mention 展示
- **AND** agent 本轮输入也能看到该 @ 内容，不会只剩空字符串或只剩去掉 @ 的正文

### Requirement: 飞书对话同步到内部 IM

Gateway 收到来自飞书的用户消息后，尽力在内部 IM 创建或查找对应影子会话，并将用户消息写入该会话；agent 回复和用户可见控制/后台文本同步到同一影子会话。1:1 私聊的影子会话名为 `agent名 · feishu`；群聊影子会话名为 `agent名 · 群名 · feishu`。外部群聊消息携带原发送者显示名；IM owner 自己从外部 channel 发送的消息显示为「你」。普通群消息继续镜像；Agent 是否接收及何时提醒遵循协作范围与工作模式。「项目级」（`project`）与「私有」（`owner_only`）时不进入该 Agent 的收件箱或待处理上下文（已绑定主人本人的飞书单聊除外）。

#### Scenario: 飞书私聊用户消息和回复出现在内部 IM
- **GIVEN** 用户在飞书与某 Bot 1:1 对话
- **WHEN** 用户发送消息且 Bot 回复用户
- **THEN** 内部 IM 中出现一个名为 `agent名 · feishu` 的独立会话
- **AND** 用户消息显示为「你」，Bot 回复也出现在同一会话中

#### Scenario: 飞书群聊用户消息和回复出现在内部 IM
- **GIVEN** 用户在飞书群 @Bot 对话
- **WHEN** 用户消息和 Bot 回复被同步到内部 IM
- **THEN** 内部 IM 中出现一个名为 `agent名 · 群名 · feishu` 的独立 group 会话
- **AND** 群成员消息显示原发送者名字，Bot 回复也出现在同一会话中

#### Scenario: 未 @ 的群聊上下文消息同步到内部 IM
- **GIVEN** plato 采用「团队公开」，Alice 在飞书群发了未 @plato 的消息
- **WHEN** Gateway 收到该消息
- **THEN** 该消息作为普通用户消息同步到内部 IM 的 `plato · 群名 · feishu` group 会话中
- **AND** Gateway 不因这条普通消息立即启动 Agent，后续按批次处理

### Requirement: PA 飞书主人私聊身份与交付

飞书在各协作范围下都以该渠道首个实时发送者为主人并保存其 `open_id`；个人微信以扫码绑定确认的微信用户标识作为唯一主人。「项目级」（`project`）与「私有」（`owner_only`）时仅递送已绑定主人与 Agent 的外部私聊，跳过群消息和其他私聊。已绑定主人与 PA 的飞书单聊及微信单聊均具有与 Web 主人私聊相同的交办权限；主人回复和定时提醒送到对应外部单聊并同步至内部 IM 影子会话。群聊与其他私聊不取得主人豁免。普通工具权限保持有效。

#### Scenario: 主人单聊收发和提醒
- **WHEN** 已绑定主人通过飞书单聊或微信单聊向 PA 交办并安排提醒
- **THEN** PA 在原外部单聊回复并在到时向该单聊发送提醒，依据平台回执确认送达，同时同步至对应内部 IM 影子会话

#### Scenario: 非团队公开档位下向非主人外部渠道会话主动发消息被前置拦截
- **GIVEN** PA 处于「私有」（`owner_only`），或普通/全局 Agent 处于「私有」（`owner_only`）或「项目级」（`project`）
- **WHEN** 该助手通过产品工具（如 `send_message` 或 `send_user_message`）尝试向飞书群聊或非绑定主人的外部单聊发送消息
- **THEN** Gateway 在向外部渠道实际发信及写入内部 IM 影子占位消息之前拒绝该请求，外部渠道与影子会话均不产生对外消息，并向模型返回明确的协作范围限制说明

#### Scenario: 失败输出与新输入隔离
- **GIVEN** 旧输出投影失败
- **WHEN** 新飞书或微信消息到达
- **THEN** 新输入继续持久化和接入，重放不造成重复执行
