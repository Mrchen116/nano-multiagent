# gateway (personal_assistant) - External Channels Specification

> 对齐: feat-447
> 上级: [gateway (personal_assistant) Specification](spec.md)
>
> 写法纪律见 [`../../SPEC_GUIDE.md`](../../SPEC_GUIDE.md)。本目录只收 Gateway **对外可观察的行为**:消费者是在外部 IM / 内置 Web IM 上收发消息的终端用户、与 Gateway 双向通信的 IM 服务、敲启停命令的运维者。

## Purpose

飞书和其他外部 channel 的消息收发、多 Bot、回复镜像、控制投递、群聊上下文、权限审批、内部 IM 同步、离线自治和隔离契约。

## Requirements

### Requirement: 飞书 channel 消息收发

Gateway 通过飞书 SDK WebSocket 长连接收发消息。1:1 私聊直接响应；群聊按 agent 的群聊回复策略决定是否响应。MENTION 策略下仅真实 @Bot 触发响应，未 @ 的群聊消息进入该 agent 的群背景上下文，待后续触发时一并带入；ALWAYS 策略下普通群消息也触发响应。Bot 收到待响应的消息后先在飞书消息上显示 THINKING 反应，回复发送后移除该反应。

#### Scenario: 用户在飞书 1:1 私聊中发消息并收到回复
- **GIVEN** Gateway 配置了某个 Agent 对应的飞书 Bot
- **WHEN** 用户在该飞书 Bot 的 1:1 对话窗口中发送一条文本消息
- **THEN** Bot 在合理时间内把 Agent 回复发回同一个 1:1 对话窗口

#### Scenario: 群聊中 @Bot 触发回复
- **GIVEN** Gateway 配置的飞书 Bot 已加入某飞书群
- **WHEN** 用户在群里 @Bot 并发送消息
- **THEN** Bot 在群里回复该消息

#### Scenario: 群聊中未 @Bot 的消息不触发回复但作为上下文
- **GIVEN** Gateway 配置的飞书 Bot 已加入某飞书群
- **WHEN** 用户在群里发消息但未 @Bot
- **THEN** Bot 不在群里回复
- **AND** 当用户随后 @Bot 提问时，Bot 回复能引用之前未 @ 的群聊消息作为上下文

#### Scenario: @所有人 不算 @Bot
- **GIVEN** Gateway 配置的飞书 Bot 已加入某飞书群
- **WHEN** 用户在群里 @所有人 发消息，但没有单独 @Bot
- **THEN** Bot 不在群里回复
- **AND** 该消息按普通未 @ 群消息进入群背景上下文

#### Scenario: ALWAYS 策略下普通群消息也触发回复
- **GIVEN** Gateway 配置的飞书 Bot 已加入某飞书群，且该 agent 的群聊回复策略为 ALWAYS
- **WHEN** 用户在群里发送普通消息且没有 @Bot
- **THEN** Bot 也在该群里回复该消息

#### Scenario: Bot 对即将响应的消息显示 THINKING 反应并在回复后移除
- **GIVEN** Gateway 配置的飞书 Bot 收到一条需要响应的消息
- **WHEN** Bot 开始处理并随后发出回复
- **THEN** 用户在飞书里看到该消息先出现 THINKING 反应，回复发出后该反应消失

### Requirement: 飞书多 Bot 路由

每个飞书 Bot 通过 channel name `feishu:<agent_id>` 绑定一个 Agent。用户与哪个 Bot 对话，消息就路由到对应的 Agent。一个 `agent_id` 只能对应一个飞书 Bot。

#### Scenario: 不同飞书 Bot 对应不同 Agent
- **GIVEN** Gateway 配置了分别绑定 plato、luban、hume 的三个飞书 Bot
- **WHEN** 用户与绑定 plato 的 Bot 对话
- **THEN** 回复来自 plato Agent，而非 luban 或 hume

### Requirement: 外部 channel 触发源决定回复去向

Agent 回复是否回写外部 channel 取决于触发该 run 的用户消息来源。飞书消息触发的 run 回写原飞书 chat，并同步到内部 IM 影子会话；内部 IM 影子会话消息触发的 run 只留在内部 IM，不回写飞书。两种入口共享同一个外部会话身份，保证上下文连续。

#### Scenario: 在内部 IM 影子会话回复不会回写飞书
- **GIVEN** 内部 IM 已存在 `plato · feishu` 影子会话
- **WHEN** 用户在该会话中发送消息
- **THEN** plato 的回复只出现在内部 IM 会话，不出现在飞书原对话中

#### Scenario: 同一外部会话跨入口上下文连续
- **GIVEN** 用户在飞书问了 plato-bot 一个带上下文的问题
- **WHEN** 用户随后在内部 IM 的 `plato · feishu` 影子会话中追问
- **THEN** plato 能引用飞书入口的前文，不会当成新会话

#### Scenario: 影子群聊入口可使用外部群背景上下文
- **GIVEN** 飞书群里已有未 @plato 的背景消息
- **WHEN** 用户在内部 IM 的 `plato · <群名> · feishu` 影子群聊中发送“总结刚才”
- **THEN** plato 能引用该飞书群的背景消息
- **AND** plato 的回复只出现在内部 IM 影子群聊，不回写飞书

### Requirement: 外部 channel 可见回复镜像

飞书消息触发 agent run 时，Gateway 把该 run 中每个用户可见 assistant 文本气泡镜像回原飞书 chat。镜像边界是完整 assistant 气泡完成，不是 token delta；同一个最终气泡不得在 run terminal 阶段重复发送。thinking、tool telemetry、token usage、debug/status 等运行态事件不作为普通飞书聊天消息外发。

#### Scenario: 飞书收到中间可见回复和最终回复
- **GIVEN** 用户在飞书向 plato-bot 发送一个会让 agent 先回复“我查一下”再继续处理的问题
- **WHEN** 内部 IM 影子会话中出现“我查一下”这一用户可见 assistant 气泡
- **THEN** 飞书原对话也收到对应文本消息
- **AND** 后续最终答案也发送到同一飞书对话

#### Scenario: 最终气泡不重复发送
- **GIVEN** 外部 channel 触发的 run 产生了一个最终 assistant 文本气泡
- **WHEN** Gateway 已经按气泡完成边界把该文本镜像到飞书
- **THEN** run terminal 后不得再把同一文本发送第二次

#### Scenario: IM 触发 run 不走外部镜像
- **GIVEN** 用户在内部 IM 的 `plato · feishu` 影子会话中发送消息
- **WHEN** agent 产生中间回复和最终回复
- **THEN** 这些回复只出现在内部 IM
- **AND** 飞书原对话不收到对应消息

### Requirement: 外部 channel 用户可见控制与后台文本投递

飞书触发或绑定的用户可见事件必须回到原飞书 chat，并同步到内部 IM 影子会话；内部 IM 影子会话触发的同类事件只留在内部 IM。用户可见事件包括 assistant 文本、控制确认、预处理失败、后台 agent 文本、权限审批卡片和审批完成状态。系统通知、thinking、工具遥测和调试状态不作为飞书普通聊天消息外发。

#### Scenario: 飞书 /stop 成功后用户在飞书看到确认
- **GIVEN** 用户在飞书 1:1 对话中触发了一个正在运行的 agent run
- **WHEN** 用户随后在同一飞书对话发送 `/stop`
- **THEN** Gateway 中断对应 run
- **AND** 飞书原对话收到停止确认
- **AND** 内部 IM 影子会话也出现同一确认消息

#### Scenario: 群聊 @Bot /stop 按控制命令处理
- **GIVEN** Gateway 配置的飞书 Bot 已加入某飞书群，且该群中存在正在运行的该 agent run
- **WHEN** 用户在群里发送真实 mention 形式的 `@Bot /stop`
- **THEN** Gateway 将该消息识别为发给该 Bot 的 `/stop` 命令
- **AND** 停止确认发送回同一飞书群并同步到内部 IM 影子群聊

#### Scenario: 飞书预处理失败反馈回原对话
- **GIVEN** 用户在飞书发送 Gateway 当前不支持或处理失败的图片/附件消息
- **WHEN** Gateway 在提交 agent run 前判定该消息无法处理
- **THEN** 失败原因发送到飞书原对话
- **AND** 同一失败原因同步到内部 IM 影子会话

#### Scenario: 飞书绑定后台 agent 文本回到飞书
- **GIVEN** 某个后台任务或 delayed run 绑定到飞书触发的影子会话
- **WHEN** 该后台任务产生 agent 自己的用户可见文本输出
- **THEN** 该文本发送到原飞书 chat
- **AND** 该文本同步到内部 IM 影子会话

### Requirement: 飞书群聊背景上下文等价内部 IM 群聊

飞书群聊复用内部 IM 群聊的 group-context 语义：未触发回复的普通群消息也进入对应 agent 的群背景上下文；后续 @Bot、纯 @Bot 或 ALWAYS 策略触发时，这些背景消息进入本轮模型上下文。`@Bot` 既是用户可见消息内容，也是触发信号；Gateway 不得为了 mention gate 从 IM 展示或模型输入中删除 @ 内容。

#### Scenario: 未 @ 背景被纯 @Bot 触发使用
- **GIVEN** 用户在飞书群里发送“你会数学吗”且没有 @nano
- **WHEN** 用户随后只发送 `@nano`
- **THEN** nano 的回复能针对“你会数学吗”作答，而不是把 `@nano` 当成无上下文测试消息
- **AND** 两条用户消息都同步显示在内部 IM 影子群聊

#### Scenario: 普通群消息投递能力缺失时不能验收为支持背景上下文
- **GIVEN** Gateway 配置了飞书群聊 channel
- **WHEN** 用户在飞书群发送不 @Bot 的消息
- **THEN** Gateway 必须能收到该事件并写入 IM 影子群聊和群背景上下文
- **AND** 如果飞书平台或 app 权限只投递 @Bot 事件，该配置不得被验收为支持飞书群聊背景上下文

#### Scenario: mention-only 和 mention+正文都保留用户可见内容
- **GIVEN** 用户在飞书群里发送 `@nano` 或 `@nano hi`
- **WHEN** Gateway 写入 IM 影子群聊并提交给 agent
- **THEN** IM 中该用户消息保留 `@nano` 或等效 mention 展示
- **AND** agent 本轮输入也能看到该 @ 内容，不会只剩空字符串或只剩去掉 @ 的正文

### Requirement: 飞书原生工具权限审批

飞书触发的 agent run 产生工具权限审批时，Gateway 在内部 IM 影子会话保留现有审批卡，同时在飞书原对话发送原生 interactive approval card。内部 IM 与飞书两端审批 first-wins：任一端先完成决策后，另一端后续重复点击不得再次改变该请求。飞书群聊中，非 owner 成员不能代表 owner 审批工具权限。

#### Scenario: 飞书触发的工具审批可在飞书中完成
- **GIVEN** 用户在飞书 1:1 对话中发送一条会触发受控工具的消息
- **WHEN** agent 请求工具权限
- **THEN** 飞书原对话出现 interactive approval card
- **AND** 内部 IM 影子会话也出现同一审批请求
- **WHEN** 用户在飞书 approval card 中点击允许
- **THEN** agent run 继续执行并把后续回复发回飞书

#### Scenario: 飞书中拒绝工具审批时可填写拒绝原因
- **GIVEN** 用户在飞书 1:1 对话中触发了一个工具权限审批
- **WHEN** 用户在飞书 approval card 中点击拒绝，填写拒绝原因并提交
- **THEN** agent run 按现有权限拒绝路径恢复，且可看到该拒绝原因
- **AND** 飞书 approval card 紧凑显示已拒绝和拒绝原因，不展示 `open_id` 等平台内部操作者标识

#### Scenario: 内部 IM 先审批后飞书卡片不得重复决策
- **GIVEN** 飞书触发的 run 已同时生成内部 IM 审批卡和飞书 approval card
- **WHEN** 用户先在内部 IM 中拒绝该请求
- **AND** 用户随后点击旧飞书 approval card 的允许按钮
- **THEN** Gateway 不得第二次提交审批决策
- **AND** 飞书卡片显示该请求已处理或已失效

#### Scenario: 非 owner 不能在飞书群里审批工具权限
- **GIVEN** 飞书群聊中 agent run 产生工具权限审批，且该 agent 已绑定 owner
- **WHEN** 非 owner 群成员点击 approval card
- **THEN** Gateway 不提交该审批决策
- **AND** 该请求仍保持等待 owner 或内部 IM 审批

### Requirement: 飞书对话同步到内部 IM

Gateway 收到来自飞书的用户消息后，尽力在内部 IM 创建或查找对应影子会话，并将用户消息写入该会话；agent 回复和用户可见控制/后台文本同步到同一影子会话。1:1 私聊的影子会话名为 `agent名 · feishu`；群聊影子会话名为 `agent名 · 群名 · feishu`。外部群聊消息携带原发送者显示名；IM owner 自己从外部 channel 发送的消息显示为「你」。未 @ 且不应触发回复的群聊消息也同步到 IM 并写入群背景上下文，但不分配新 run、不发送 agent 回复。

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
- **GIVEN** plato 的群聊回复策略为 MENTION，Alice 在飞书群发了未 @plato 的消息
- **WHEN** Gateway 收到该消息
- **THEN** 该消息作为普通用户消息同步到内部 IM 的 `plato · 群名 · feishu` group 会话中
- **AND** Gateway 不因此启动 agent run 或发送 agent 回复

### Requirement: IM 离线时飞书对话不阻塞

Gateway 对内部 IM 的外部 channel 同步是 best-effort：IM 不可达不得影响飞书主路径，agent 仍需正常回复用户；恢复 IM 后，后续飞书消息继续按影子会话规则同步。

#### Scenario: IM 离线时飞书 1:1 对话仍正常
- **GIVEN** IM 服务当前不可达
- **WHEN** 用户在飞书与 plato-bot 1:1 对话
- **THEN** plato-bot 仍正常回复用户
- **AND** 本次消息可暂不同步到内部 IM

#### Scenario: IM 离线时飞书群聊 @Bot 仍正常
- **GIVEN** IM 服务当前不可达
- **WHEN** 用户在飞书群 @plato-bot 并发消息
- **THEN** plato-bot 仍在群里正常回复
- **AND** 本次消息可暂不同步到内部 IM

### Requirement: 外部 channel 会话隔离

同一外部 channel 的同一聊天如果绑定多个 agent，Gateway 与 IM 为每个 agent 保持独立的影子会话和 agent 会话上下文。

#### Scenario: 同一外部群绑定多个 agent 时生成多个独立会话
- **GIVEN** 飞书群同时配置了 plato-bot 和 luban-bot
- **WHEN** 用户在群里分别 @plato-bot 和 @luban-bot
- **THEN** 内部 IM 中同时存在 `plato · 群名 · feishu` 和 `luban · 群名 · feishu` 两个独立 group 会话
- **AND** 两个 agent 的上下文和回复互不混淆
