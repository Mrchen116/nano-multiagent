# gateway Specification (delta for feat-447)

## ADDED Requirements

### Requirement: 飞书 channel 消息收发

Gateway 通过飞书 SDK WebSocket 长连接收发消息。1:1 私聊直接响应;群聊仅在用户 @Bot 时触发响应,未 @ 的群聊消息暂存为该群上下文,待下次 @Bot 时一并带入。Bot 收到待响应的消息后先在飞书消息上显示 THINKING 反应,回复发送后移除该反应。

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
- **AND** 当用户随后 @Bot 提问时,Bot 回复能引用之前未 @ 的群聊消息作为上下文

#### Scenario: @所有人 不算 @Bot
- **GIVEN** Gateway 配置的飞书 Bot 已加入某飞书群
- **WHEN** 用户在群里 @所有人 发消息,但没有单独 @Bot
- **THEN** Bot 不在群里回复
- **AND** 该消息按普通未 @ 群消息进入群上下文

#### Scenario: Bot 对即将响应的消息显示 THINKING 反应并在回复后移除
- **GIVEN** Gateway 配置的飞书 Bot 收到一条需要响应的消息
- **WHEN** Bot 开始处理并随后发出回复
- **THEN** 用户在飞书里看到该消息先出现 THINKING 反应,回复发出后该反应消失

### Requirement: 飞书多 Bot 路由

每个飞书 Bot 通过 channel name `feishu:<agent_id>` 绑定一个 Agent。用户与哪个 Bot 对话,消息就路由到对应的 Agent。一个 `agent_id` 只能对应一个飞书 Bot。

#### Scenario: 不同飞书 Bot 对应不同 Agent
- **GIVEN** Gateway 配置了分别绑定 plato、luban、hume 的三个飞书 Bot
- **WHEN** 用户与绑定 plato 的 Bot 对话
- **THEN** 回复来自 plato Agent,而非 luban 或 hume

### Requirement: 按触发源路由 agent 回复

agent 回复是否回写外部 channel 取决于触发该 run 的用户消息来源。由外部 channel 消息触发的回复回写原 channel 并同步到内部 IM;由内部 IM 影子会话消息触发的回复只留在内部 IM,不回写外部 channel。两种来源复用同一 kernel session,保证上下文连续。Gateway 的 kernel session identity 和外部 group buffer identity 均使用 `external_source + external_chat_id + agent_id`;IM conversation id 只作为 shadow conversation delivery 目标,不参与 session identity 或 group buffer identity。

#### Scenario: 在内部 IM 回复不会回写飞书
- **GIVEN** 内部 IM 已存在 `plato · feishu` 会话
- **WHEN** 用户在该会话中发送消息
- **THEN** plato 的回复只出现在内部 IM 会话,不出现在飞书原对话中

#### Scenario: 在内部 IM 群聊影子会话发消息自动触发 agent 回复
- **GIVEN** 内部 IM 已存在 `plato · 产品群 · feishu` group 影子会话
- **WHEN** 用户在该会话中发送消息（不 @plato）
- **THEN** Gateway 在群聊 mention gate 之前自动注入 `@plato` 或等效 mention metadata 后提交给 kernel
- **AND** plato 的回复只出现在内部 IM 会话,不回写飞书

#### Scenario: 同一 kernel session 跨入口上下文连续
- **GIVEN** 用户在飞书问了 plato-bot "我叫什么"
- **WHEN** 用户在内部 IM 的 `plato · feishu` 会话中回复 "你刚才不是知道吗"
- **THEN** plato 能引用前一条上下文,不会当成新会话

#### Scenario: IM shadow conversation id 不污染 kernel session
- **GIVEN** 飞书 chat id 为 `oc_xxx`,内部 IM shadow conversation id 为 `conv_yyy`
- **WHEN** 用户分别从飞书和内部 IM shadow 会话向 plato 发送消息
- **THEN** Gateway 两次都使用 `feishu:oc_xxx:plato` 对应的同一 kernel session,不会使用 `web_relay:conv_yyy:plato` 创建新 session

#### Scenario: 未 @ 群聊上下文可被 IM shadow group 入口使用
- **GIVEN** Alice 在飞书群「产品群」发了未 @plato 的消息“版本延期因为测试环境不可用”
- **WHEN** 用户随后在内部 IM 的 `plato · 产品群 · feishu` shadow group 中发送“总结刚才”
- **THEN** Gateway 使用同一外部 group buffer,plato 能引用 Alice 的延期原因
- **AND** plato 的回复只出现在内部 IM shadow group,不回写飞书

### Requirement: 外部 channel 可见回复镜像

外部 channel 消息触发 agent run 时,Gateway 必须把该 run 中每个用户可见 assistant 文本气泡镜像回原外部 channel。镜像边界是 assistant 气泡完成,不是 token delta;terminal 阶段不得把已经镜像过的最后气泡重复发送。由内部 IM shadow 会话触发的 run 仍只写 IM,不回写外部 channel。

#### Scenario: 飞书收到中间可见回复
- **GIVEN** 用户在飞书向 plato-bot 发送一个会让 agent 先回复“我查一下”再调用工具的问题
- **WHEN** 内部 IM shadow 会话中出现“我查一下”这一用户可见 assistant 气泡
- **THEN** 飞书原对话也收到对应的文本消息
- **AND** 后续最终答案也发送到同一飞书对话

#### Scenario: 最终气泡不重复发送
- **GIVEN** 外部 channel 触发的 run 产生了一个最终 assistant 文本气泡
- **WHEN** Gateway 已经按气泡完成边界把该文本镜像到飞书
- **THEN** run terminal 后不得再通过 terminal `reply_text` 把同一文本发送第二次

#### Scenario: IM 触发 run 不走外部镜像
- **GIVEN** 用户在内部 IM 的 `plato · feishu` shadow 会话中发送消息
- **WHEN** agent 产生中间回复和最终回复
- **THEN** 这些回复只出现在内部 IM
- **AND** 飞书原对话不收到任何对应消息

### Requirement: 飞书群聊背景上下文等价内部 IM 群聊

飞书群聊必须复用内部 IM 群聊的 group-context 语义:不 @Bot 的群消息也进入该 agent 的群背景上下文,后续 @Bot 或纯 @Bot 触发时,这些背景消息会作为 `[sender] text` 注入 LLM context。`@Bot` 既是用户可见正文的一部分,也是触发 drain 的结构化信号;Gateway 不得为了 mention gate 从 IM 展示或 LLM 输入中删除 @ 内容。

#### Scenario: 未 @ 背景被纯 @Bot 触发使用
- **GIVEN** 用户在飞书群里发送“你会数学吗”且没有 @nano
- **WHEN** 用户随后只发送 `@nano`
- **THEN** Gateway 将第一条未 @ 消息作为 group context 注入 nano 的本轮 LLM 输入
- **AND** nano 的回复能针对“你会数学吗”作答,而不是把 `@nano` 当成无上下文测试消息
- **AND** 两条用户消息都同步显示在内部 IM shadow group

#### Scenario: 飞书普通群消息投递能力缺失时验收失败
- **GIVEN** Gateway 配置了飞书群聊 channel
- **WHEN** 用户在飞书群发送不 @Bot 的 nonce 消息
- **THEN** Gateway 必须能收到该事件并写入 IM shadow group / GroupContextStore
- **AND** 如果飞书平台或 app 权限只投递 @Bot 事件,该配置不得被验收为支持飞书群聊背景上下文

#### Scenario: 纯 @Bot 保留为用户可见正文和 LLM 输入
- **GIVEN** 用户在飞书群里只发送 `@nano`
- **WHEN** FeishuClient 解析事件并交给 InboundPipeline
- **THEN** InboundMessage 的文本保留该 @ 行为（例如 IM mention wire 或 `@nano`）
- **AND** 结构化 mention metadata 同时标记 nano 被提及
- **AND** shadow sync 不会因为空文本被 IM 拒绝
- **AND** kernel 当前消息中仍能看到该 @ 内容,不是空字符串

#### Scenario: @Bot 加正文时正文不被删减
- **GIVEN** 用户在飞书群里发送 `@nano hi`
- **WHEN** Gateway 写入 IM shadow group 并提交给 kernel
- **THEN** IM 中该用户消息显示为 `@nano hi` 或等效 mention chip + `hi`
- **AND** kernel 当前消息包含 @nano 和 hi,而不是只剩 hi

### Requirement: 飞书原生工具权限审批

当飞书触发的 agent run 产生工具权限 `permission_request` 时,Gateway 必须在内部 IM shadow 会话保留现有审批卡,同时在飞书原对话发送原生 interactive approval card。飞书卡片点击产生的审批决策必须回到同一 kernel `request_id`,复用现有 `kernel.submit_permission_decision` 等待/恢复路径。内部 IM 和飞书两端审批 first-wins:任一端先完成决策后,另一端后续重复点击不得再次调用 kernel。

#### Scenario: 飞书触发的工具审批可在飞书中完成
- **GIVEN** 用户在飞书 1:1 对话中发送一条会触发受控工具的消息
- **WHEN** kernel 为本 run 发出 `permission_request`
- **THEN** 飞书原对话出现 interactive approval card
- **AND** 内部 IM shadow 会话也出现同一 `request_id` 的审批卡
- **WHEN** 用户在飞书 approval card 中点击允许
- **THEN** Gateway 将该决策提交给等待中的 kernel
- **AND** agent run 继续执行并把后续回复发回飞书

#### Scenario: 内部 IM 先审批后飞书卡片不得重复决策
- **GIVEN** 飞书触发的 run 已同时生成内部 IM 审批卡和飞书 approval card
- **WHEN** 用户先在内部 IM 中拒绝该 `request_id`
- **AND** 用户随后点击旧飞书 approval card 的允许按钮
- **THEN** Gateway 不得第二次调用 kernel permission decision
- **AND** 飞书卡片显示该请求已处理或已失效

#### Scenario: 非 owner 不能在飞书群里审批工具权限
- **GIVEN** 飞书群聊中 agent run 产生工具权限审批,且该 agent 已绑定 `ownerOpenId`
- **WHEN** 非 owner 群成员点击 approval card
- **THEN** Gateway 不提交该审批决策
- **AND** 该请求仍保持等待 owner 或内部 IM 审批

### Requirement: IM 离线时飞书对话不阻塞

Gateway 调用 IM HTTP API 同步外部 channel 用户消息时,必须是非阻塞的 best-effort 调用。IM 不可达不得影响飞书主路径,agent 仍需正常回复用户。

#### Scenario: IM 离线时飞书 1:1 对话仍正常
- **GIVEN** IM 服务当前不可达
- **WHEN** 用户在飞书与 plato-bot 1:1 对话
- **THEN** plato-bot 仍正常回复用户
- **AND** Gateway 记录同步失败日志,不阻塞飞书回复路径

#### Scenario: IM 离线时飞书群聊 @Bot 仍正常
- **GIVEN** IM 服务当前不可达
- **WHEN** 用户在飞书群「产品群」@plato-bot 并发消息
- **THEN** plato-bot 仍在群里正常回复
- **AND** 该消息暂不同步到内部 IM

### Requirement: 外部 channel 会话隔离

同一外部 channel 的同一聊天,如果绑定了多个 agent,内部 IM 中为每个 agent 生成独立的影子会话。

#### Scenario: 同一外部群绑定多个 agent 时生成多个独立会话
- **GIVEN** 飞书群「产品群」同时配置了 plato-bot 和 luban-bot
- **WHEN** 用户在群里分别 @plato-bot 和 @luban-bot
- **THEN** 内部 IM 中同时存在 `plato · 产品群 · feishu` 和 `luban · 产品群 · feishu` 两个独立的 group 会话,各自的内容互不混淆

### Requirement: 内置 skills 启动自举

Gateway 随包携带 PA 产品级内置 skills。启动时,Gateway 将包内 `builtin_skills/<skill-name>/SKILL.md`
按标准目录形态安装到用户全局 skill root `~/.nanoassistant/skills/<skill-name>/SKILL.md`;目标已存在时默认不覆盖用户本地版本。启用飞书 channel 的 agent 必须能发现 `feishu-doc` skill,使用户在飞书中要求云文档操作时,agent 能按该 skill 给出授权和文档操作路径。

#### Scenario: 新安装用户启动后获得 feishu-doc
- **GIVEN** 用户本机没有 `~/.nanoassistant/skills/feishu-doc/SKILL.md`
- **WHEN** Gateway 启动
- **THEN** Gateway 从包内内置资源安装 `feishu-doc` 到用户全局 skill root
- **AND** 后续 capabilities 查询和会话 prompt 均能解析到 `feishu-doc`

#### Scenario: 已存在的用户 skill 不被覆盖
- **GIVEN** 用户本机已存在自定义的 `~/.nanoassistant/skills/feishu-doc/SKILL.md`
- **WHEN** Gateway 启动
- **THEN** Gateway 保留用户已有文件,不以包内版本覆盖

#### Scenario: 飞书绑定 agent 自动启用 feishu-doc
- **GIVEN** Gateway 配置了 `feishu:plato` channel 且 plato agent 的 skills allowlist 未包含 `feishu-doc`
- **WHEN** Gateway 启动
- **THEN** Gateway 将 `feishu-doc` 加入 plato 的本地 skills 配置
- **AND** 用户从飞书向 plato-bot 请求云文档操作时,plato 的会话可见 `feishu-doc`

## MODIFIED Requirements

### Requirement: 飞书对话同步到内部 IM

原 MVP 条目声明「MVP 阶段仅同步 Agent 回复，用户原始消息不写入内部 IM」。本 unit 将其扩展为通用外部 channel 同步规则:Gateway 收到来自外部 channel（以飞书为首个实现）的用户消息后,调用 IM 服务创建或查找对应的影子会话,并将用户消息写入该会话;agent 回复亦同步到同一影子会话。1:1 私聊的影子会话名为 `agent名 · channel名`;群聊的影子会话名为 `agent名 · 群名 · channel名`。外部群聊消息携带原发送者显示名;IM owner 自己从外部 channel 发送的消息显示为「你」。未 @ 的群聊上下文消息、不 @ 也回的 agent 群聊消息均按同样规则同步。未 @ 且不应触发回复的群聊消息使用 `sync_only` 入站语义:同步到 IM 并写入 GroupContextStore,但不分配 kernel session、不进入 run queue、不发送 agent 回复。

#### Scenario: 外部 1:1 用户消息同步到内部 IM
- **GIVEN** 用户在飞书与 plato-bot 1:1 对话
- **WHEN** 用户发送一条消息
- **THEN** 内部 IM 中出现一个名为 `plato · feishu` 的独立会话,且该消息作为「你」的消息出现在该会话中

#### Scenario: 外部群聊消息同步到内部 IM 并显示发送者名字
- **GIVEN** plato-bot 已加入飞书群「产品群」,且 Alice 在群里发消息
- **WHEN** 该消息被同步到内部 IM
- **THEN** 内部 IM 中出现一个名为 `plato · 产品群 · feishu` 的独立 group 会话,Alice 的消息显示为 Alice 发送

#### Scenario: 未 @ 的群聊上下文消息同步到内部 IM
- **GIVEN** plato 的 group_reply_policy 为 MENTION,Alice 在飞书群「产品群」发了 2 条未 @plato 的消息
- **WHEN** 这些消息作为上下文被暂存
- **THEN** 它们作为普通用户消息同步到内部 IM 的 `plato · 产品群 · feishu` group 会话中,显示发送者名字

#### Scenario: 不 @ 也回的 agent 群聊消息全量同步
- **GIVEN** plato 的 group_reply_policy 为 ALWAYS
- **WHEN** 群成员在飞书群「产品群」发送任意消息
- **THEN** 每条消息都触发 plato 回复,并全部同步到内部 IM 的 `plato · 产品群 · feishu` group 会话中
