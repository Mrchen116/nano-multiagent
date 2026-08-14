# gateway (personal_assistant) - External Channels Specification

> 对齐: feat-523
> 上级: [gateway (personal_assistant) Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)。本目录只收 Gateway **对外可观察的行为**:消费者是在外部 IM / 内置 Web IM 上收发消息的终端用户、与 Gateway 双向通信的 IM 服务、敲启停命令的运维者。

## Purpose

飞书和其他外部 channel 的消息收发、IM 托管配置、多 Bot、回复镜像、控制投递、群聊上下文、权限审批、内部 IM 同步、离线自治和隔离契约。

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

### Requirement: 飞书富文本与图片在飞书、内部 IM 和模型输入间保持语义

Gateway 必须把 Agent Markdown 作为飞书可渲染富文本发送，并把飞书 text、Post 与 standalone image 入站还原为用户可读内容。内部 IM 展示投影与模型多模态输入分别构建：影子会话显示适合人阅读的正文和图片附件，模型输入保留飞书原始 text/image 顺序且不接收 UI 占位符。

#### Scenario: Agent Markdown 在飞书中按富文本渲染
- **WHEN** Agent 回复包含 Markdown 粗体、列表、链接或代码
- **THEN** 用户在飞书中看到平台原生富文本效果
- **AND** 气泡不把 `**` 等 Markdown 标记原样显示为普通文本

#### Scenario: Agent Markdown 图片在飞书中显示
- **WHEN** Agent 回复包含可获取的 Markdown 图片
- **THEN** Gateway 将图片上传为飞书消息资源并在同一富文本回复中显示

#### Scenario: 飞书 Post 入站不向用户或模型泄漏 wire JSON
- **WHEN** 用户从飞书发送包含样式、链接、代码或段落的 Post
- **THEN** 内部 IM 显示等价的可读 Markdown 文本，Agent 也基于该文本作答
- **AND** 两者都不把序列化 Post JSON 当作消息正文

#### Scenario: 飞书独立图片在 IM 直接显示并作为纯图片输入模型
- **WHEN** 用户从飞书发送一条 standalone image 消息
- **THEN** 内部 IM 的对应用户消息直接显示图片 attachment，不额外显示 `[图片]` 文本
- **AND** 模型收到一个 image part，不人为增加占位 text part

#### Scenario: 飞书 Post 内嵌图片分别生成展示投影和模型投影
- **WHEN** 用户从飞书发送内容顺序为“前文 → 图片 → 后文”的 Post
- **THEN** 内部 IM 显示 `前文[图片]后文` 或等价位置标记，并同时显示实际图片 attachment
- **AND** 模型按 `text("前文") → image → text("后文")` 的顺序收到多模态 parts
- **AND** 模型的 text parts 不包含 `[图片]` 占位符

#### Scenario: 飞书群历史中的纯图片消息可作为后续上下文
- **GIVEN** 飞书群中存在一条没有正文的 standalone image 消息
- **WHEN** 后续消息触发 Agent 处理群背景上下文
- **THEN** 该图片消息不会仅因正文为空而在历史采集阶段被丢弃

### Requirement: 飞书多 Bot 路由

每个飞书 Bot 通过 channel name `feishu:<agent_id>` 绑定一个 Agent。用户与哪个 Bot 对话，消息就路由到对应的 Agent。一个 `agent_id` 只能对应一个飞书 Bot。

#### Scenario: 不同飞书 Bot 对应不同 Agent
- **GIVEN** Gateway 配置了分别绑定 plato、luban、hume 的三个飞书 Bot
- **WHEN** 用户与绑定 plato 的 Bot 对话
- **THEN** 回复来自 plato Agent，而非 luban 或 hume

### Requirement: 外部 channel 触发源决定回复去向

Agent 回复是否回写外部 channel 取决于触发该 run 的用户消息来源。飞书消息触发的 run 回写原飞书 chat，并同步到内部 IM 影子会话；内部 IM 影子会话消息触发的 run 只留在内部 IM，不回写飞书。两种入口共享同一个外部会话身份，保证上下文连续。Agent 具有 Lark IM 操作能力不改变当前飞书 chat 的普通回复出口：该回复仍由 Gateway 统一投递和镜像；只有用户明确指定另一段 Lark chat 时，agent 才可对那段独立 chat 直接操作。

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

#### Scenario: 当前飞书 chat 的普通回复不走 Lark IM 直发
- **GIVEN** 用户在飞书向 plato-bot 发起一个会产生可见回复的请求
- **WHEN** plato 已获得 Lark IM 操作能力并生成普通助手回复
- **THEN** 回复仍由 Gateway 回写原飞书 chat 并同步到内部 IM 影子会话
- **AND** agent 不使用 Lark IM 向当前 chat 另发绕过 Gateway 的消息

#### Scenario: 用户明确指定另一段 Lark chat
- **GIVEN** 用户正在飞书与 plato-bot 对话
- **WHEN** 用户明确指定要查询、发送或管理另一段 Lark chat 的消息
- **THEN** plato 可使用 Lark IM 对该独立 chat 完成用户请求的操作
- **AND** plato 对操作结果的说明仍经当前飞书 chat 的 Gateway 回复链路返回

### Requirement: 外部 channel 可见回复镜像

飞书消息触发 agent run 时，Gateway 把该 run 中每个用户可见 assistant 文本气泡镜像回原飞书 chat。镜像边界是完整 assistant 气泡完成，不是 token delta；同一个最终气泡即使遇到重叠的投递机会也只能成功发送一次。较早的投递失败时，仍存活的兜底机会必须能够接管；已取消的旧 run 不得在取消后晚发该气泡。thinking、tool telemetry、token usage、debug/status 等运行态事件不作为普通飞书聊天消息外发。

#### Scenario: 飞书收到中间可见回复和最终回复
- **GIVEN** 用户在飞书向 plato-bot 发送一个会让 agent 先回复“我查一下”再继续处理的问题
- **WHEN** 内部 IM 影子会话中出现“我查一下”这一用户可见 assistant 气泡
- **THEN** 飞书原对话也收到对应文本消息
- **AND** 后续最终答案也发送到同一飞书对话

#### Scenario: 重叠投递机会只产生一条最终气泡
- **GIVEN** 外部 channel 触发的 run 产生了一个最终 assistant 文本气泡
- **WHEN** Gateway 的多个投递机会在首次发送完成前重叠
- **THEN** 飞书原对话最终只收到一条该文本消息
- **AND** 较早发送失败时，仍存活的兜底机会可以接管并发送一次
- **AND** 已取消的旧 run 不会在取消后晚发该文本

#### Scenario: IM 触发 run 不走外部镜像
- **GIVEN** 用户在内部 IM 的 `plato · feishu` 影子会话中发送消息
- **WHEN** agent 产生中间回复和最终回复
- **THEN** 这些回复只出现在内部 IM
- **AND** 飞书原对话不收到对应消息

### Requirement: 外部 channel 最终回复的可配置运行信息页脚

Gateway 默认不在外部 channel 回复中暴露运行信息。启用全局设置后，Gateway 在由外部用户消息触发的普通最终 assistant 回复正文下方附加本轮已解析模型与 context 占用百分比；特定外部 channel 可以覆盖全局开关。内部 Web IM 及其外部影子会话保持原正文。

#### Scenario: 全局启用后外部最终回复显示本轮运行信息
- **GIVEN** Gateway 已全局启用运行信息页脚，且本轮外部触发的普通最终回复具有已解析模型、prompt token 与 context window
- **WHEN** 用户在飞书或另一已接入的外部 channel 收到该最终回复
- **THEN** 用户在回复正文下方看到模型名与 context 占用百分比，例如 `gpt-5.4 · 42%`
- **AND** 该百分比基于本轮实际 prompt token 与该模型的 context window 计算

#### Scenario: 单一外部 channel 覆盖全局设置
- **GIVEN** Gateway 已全局启用运行信息页脚
- **WHEN** 飞书被单独配置为关闭该页脚并向用户发送普通最终回复
- **THEN** 飞书回复不显示运行信息页脚
- **AND** 未单独关闭的外部 channel 仍按全局设置显示页脚

#### Scenario: 单一外部 channel 可以独立启用页脚
- **GIVEN** Gateway 未全局启用运行信息页脚
- **WHEN** 飞书被单独配置为开启该页脚并向用户发送普通最终回复
- **THEN** 飞书回复显示运行信息页脚
- **AND** 未单独开启的外部 channel 保持不显示

#### Scenario: 非最终或内部消息不附加运行信息
- **GIVEN** 某外部 channel 的运行信息页脚已启用
- **WHEN** 同一 run 产生中间 assistant 文字、工具进度、审批卡、控制确认或内部 Web IM 影子回复
- **THEN** 这些消息都不显示运行信息页脚
- **AND** 只有普通最终外部 assistant 回复可以显示该页脚

#### Scenario: 运行信息缺失时静默省略
- **GIVEN** 某外部 channel 的运行信息页脚已启用
- **WHEN** 最终回复只具有模型或只具有有效 context 占用数据
- **THEN** 页脚只显示可取得的那一项，不显示未知占位符
- **WHEN** 两项都不可取得
- **THEN** Gateway 发送原最终回复，不增加空白页脚

### Requirement: 外部 channel 用户可见控制与后台文本投递

飞书触发或绑定的用户可见事件必须回到原飞书 chat，并同步到内部 IM 影子会话；内部 IM 影子会话触发的同类事件只留在内部 IM。用户可见事件包括 assistant 文本、`/stop`、`/new`、`/compact` 及 `/compact <关注点>` 的控制确认、预处理失败、后台 agent 文本、权限审批卡片和审批完成状态。含非空真实更新对象的 `self_evolution_review` system notice 遵守同一触发源规则：飞书触发时在原 chat 显示简短 Bot 更新通知并在 shadow IM 保留结构化 system notice，内部 IM 触发时不回写飞书。外部控制确认的 session/context outcome 与可恢复 delivery intent 必须先同次持久化；该 intent 幂等物化为 shadow output 后才向飞书发送，重放同一 provider message 复用首次控制结果，不重复改变会话或上下文。Gateway 启动和 IM reconnect 必须扫描未物化或未 hand-off 的 intent。若进程恰在 provider 已接受发送、但 hand-off 状态尚未来得及持久化时退出，飞书沿既有 at-least-once outbound 语义可能收到一次重复确认；本系统不伪造跨 provider exactly-once 保证，IM shadow 仍以同一 durable output 收敛。其他系统通知、thinking、工具遥测和调试状态不作为飞书普通聊天消息外发。

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

#### Scenario: 飞书 `/new` 或 `/compact` 同步到影子会话
- **GIVEN** 用户在飞书与 Bot 的私聊已有对应内部 IM shadow conversation
- **WHEN** 用户在飞书发送 `/new`、`/compact` 或 `/compact <关注点>`
- **THEN** Bot 在原飞书聊天返回该控制操作的结果
- **AND** IM shadow conversation 显示同一命令与结果，并继续映射该飞书聊天的后续 Agent 工作

#### Scenario: 群聊新控制命令要求明确 @Bot
- **GIVEN** 飞书群有该 Bot 的共同上下文，且其 group reply policy 为 MENTION
- **WHEN** 用户发送未明确指向 Bot 的 `/new` 或 `/compact`
- **THEN** Gateway 只按既有群背景/触发规则处理，不切换或压缩共同会话
- **WHEN** 用户发送 `@Bot /new` 或 `@Bot /compact <关注点>`
- **THEN** Bot 在同一群返回结果，且群对应 IM shadow conversation 同步命令与结果

#### Scenario: IM shadow 暂不可达不阻塞飞书控制确认
- **GIVEN** 飞书 Bot 可用但内部 IM 暂不可达
- **WHEN** 用户在飞书发送一个有效的文本会话控制命令
- **THEN** Gateway 仍在飞书原聊天返回命令结果
- **AND** 在 IM 恢复后，shadow 同步按既有恢复机制补齐同一命令和一条相同确认，不改变飞书控制命令的会话语义

#### Scenario: 飞书 provider 重放控制命令只复用首次结果
- **GIVEN** Gateway 已处理一个带同一 provider message id 的飞书 `/new` 或 `/compact <关注点>`
- **WHEN** provider 重放该消息，或 Gateway 在控制确认投递前后重启并恢复处理
- **THEN** Gateway 不再次切换会话或压缩上下文
- **AND** IM shadow 以同一 caller identity 收敛为一条控制确认；飞书重投沿既有出站去重/投递语义返回第一次的控制结果

#### Scenario: control outcome 提交后崩溃仍恢复确认
- **GIVEN** 飞书 `/new` 或 `/compact <关注点>` 的 session/context outcome 与其 external delivery intent 已提交
- **AND** Gateway 在 saga control output 写入前退出，且 provider 不重放该入站消息
- **WHEN** Gateway 重启并完成 external channel ready，或随后 IM reconnect
- **THEN** Gateway 从 pending delivery intent 幂等建立同一 saga control output，并向原飞书 chat 投递首次结果
- **AND** IM shadow 在可用后按既有 recovery 仅出现一条相同确认，不再次改变会话或上下文

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

#### Scenario: 飞书触发的 self-evolution review 通知回到原 chat

- **GIVEN** 用户从飞书发送消息，随后后台 review 确实成功写入 memory、skills 或两者
- **WHEN** `self_evolution_review` 通知产生
- **THEN** 原飞书 chat 收到一条简短、非第一人称的 Bot 通知，说明更新对象
- **AND** 内部 IM 影子会话保留同一结果的结构化 system notice
- **AND** 两端都不显示具体沉淀内容、review prompt 或工具过程

#### Scenario: 内部 IM 触发的 review 不回写飞书

- **GIVEN** 用户从内部 IM 或飞书影子会话发送消息，随后后台 review 确实成功写入 memory、skills 或两者
- **WHEN** `self_evolution_review` 通知产生
- **THEN** 通知只显示在当前内部 IM 对话
- **AND** 飞书原 chat 不收到对应消息

#### Scenario: 无成功写入的 review 不发送更新通知

- **GIVEN** self-evolution review 无需写入、只执行 list/read，或 mutating tool 执行失败
- **WHEN** 本轮后台 review 结束
- **THEN** 用户不收到 raw `Nothing to save.` 或工具过程
- **AND** 飞书与 shadow IM 均不产生 self-evolution update notice

#### Scenario: 其他内部运行态事件仍不外发

- **WHEN** Agent 产生 thinking、工具过程、token 使用量、debug/status 或其他未单独产品化的 system notice
- **THEN** 这些事件不作为普通消息发送到飞书

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

飞书触发的 agent run 产生工具权限审批时，Gateway 在内部 IM 影子会话保留现有审批卡，同时在飞书原对话发送原生 interactive approval card。飞书卡片用同一套通用字段布局展示工具输入，不按具体工具硬编码卡片：1:1 对话的短值在灰底分组中直接显示 label、物理行数与 value；长单行或多行值使用默认收起的飞书原生折叠面板，header 显示 label、总行数和最多两行紧凑摘要，原生展开后在同一面板显示完整值。默认卡片不得把 Markdown fence、`↵`、raw JSON 或整墙正文作为 values 的主要呈现。群聊保留字段名但统一隐藏 values，并提示到内部 IM 查看完整输入，避免全群读取 owner 的敏感工具参数。超出平台完整值预算时可以明确截断，但不得退化为只展示参数数量或整段难以扫描的 JSON。原生折叠交互不提交审批决策；内部 IM 与飞书两端审批 first-wins：任一端先完成决策后，另一端后续重复点击不得再次改变该请求。飞书群聊中，非 owner 成员不能代表 owner 审批工具权限。

#### Scenario: 飞书触发的工具审批可在飞书中完成
- **GIVEN** 用户在飞书 1:1 对话中发送一条会触发受控工具的消息
- **WHEN** agent 请求工具权限
- **THEN** 飞书原对话出现 interactive approval card
- **AND** 卡片逐字段显示本次工具调用的输入 label 与 value，用户无需切换到内部 IM 即可判断将执行的操作
- **AND** 短值直接显示在灰底分组中；长值默认只显示 label、总行数与有界摘要，用户可用原生折叠面板展开完整值并再次收起
- **AND** 展开或收起输入值不等于 Allow、Deny 或 Allow for session，也不改变待审批状态
- **AND** 内部 IM 影子会话也出现同一审批请求
- **WHEN** 用户在飞书 approval card 中点击允许
- **THEN** agent run 继续执行并把后续回复发回飞书

#### Scenario: 飞书群聊审批不向非 owner 暴露工具输入值
- **GIVEN** 飞书群聊中 agent run 产生工具权限审批，且 input 可能包含敏感值
- **WHEN** Gateway 在原群发送 approval card
- **THEN** 卡片使用与 1:1 相同的字段布局显示 input labels，但 values 统一标记为群内隐藏
- **AND** Request metadata 使用固定安全提示，不携带原 question 中的 path、reason 或 @ 等操作细节
- **AND** 卡片提示 owner 到内部 IM 审批查看完整输入
- **AND** 非 owner 群成员不能从卡片读取工具输入值

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

### Requirement: IM 托管的外部 channel 可热调和并离线自治

用户经 IM 通道页保存的完整 desired manifest 是托管 external channel 的权威配置。Gateway 在 register 成功后接收完整 manifest，由唯一 ChannelManager 幂等执行新增、替换、启停、重连和删除；不要求改本地 `config.yaml` 或重启 Gateway。Gateway 只在内存中解封节点公钥 envelope，并把同一密文 manifest 原子缓存到本机；因此 IM 暂时不可达或 Gateway 重启时，已应用 channel 仍可启动和收发。内置 `web_relay` 不进入该 managed manifest。旧 standalone YAML、历史 backup 或 legacy export 不属于本契约。

#### Scenario: 在线保存后热连接且凭据不落普通配置
- **GIVEN** 节点在线且 IM 下发一个有效飞书 desired item
- **WHEN** Gateway 调和该 manifest
- **THEN** ChannelManager 无需进程重启即启动 `feishu:<agent_id>` runtime，并上报 connecting 后的真实终态
- **AND** App Secret 不写入 `config.yaml`、日志、状态 payload 或 HTTP 响应

#### Scenario: 离线期间继续从密文 cache 启动
- **GIVEN** 某 managed channel 已成功应用并写入节点绑定的密文 cache
- **WHEN** Gateway 在 IM 不可达时重启
- **THEN** Gateway 从 cache 启动该 channel，外部消息主路径保持可用
- **AND** IM 恢复并下发更高 manifest 后，runtime 自动收敛到最新 desired state

#### Scenario: disable/delete 真实停止且删除不清历史
- **WHEN** manifest 停用或删除某 channel
- **THEN** Gateway 先从出站 registry 摘除该 runtime，再有界停止 worker；失败回报可重试原因，不伪造 applied
- **AND** 成功删除只清 runtime/cache identity，不删除 IM 影子会话或消息历史

#### Scenario: 重复和失败后的同 revision manifest 可安全重放
- **GIVEN** Gateway 已成功应用 manifest N，或上次应用 N 时发生可重试失败
- **WHEN** IM 再次下发 N
- **THEN** 已成功项不重复启动 listener，失败项继续重试未完成动作并回报真实 result
- **AND** 旧于当前已见 revision 的 manifest 不覆盖较新 runtime

#### Scenario: removal result 确认丢失后继续重放
- **GIVEN** Gateway 已实际停止 channel，但 IM 对 removal outcome 的 ACK 丢失
- **WHEN** Gateway 重连或继续处理更高 manifest
- **THEN** 未确认 token 的 outcome 仍从密文 cache outbox 重放，不被新 revision 覆盖
- **AND** IM 返回 accepted、already applied 或 applied-head 等价终态后才清除该 token

#### Scenario: managed 更新保持稳定 channel 身份与 Agent 能力
- **GIVEN** `feishu:<agent_id>` 已产生会话，且 Agent 使用显式非空 skill allowlist
- **WHEN** 用户经 IM 新建或更新该飞书 channel
- **THEN** 控制面 UUID 不改变 runtime channel name 或会话连续性，并幂等启用完整 Lark skill bundle
- **AND** 停用/删除不自动移除用户已有 skill

#### Scenario: 更换 App ID 后不继承旧应用身份
- **GIVEN** channel 已记录旧 App 的 Bot/owner metadata
- **WHEN** manifest 换为新 App ID
- **THEN** 旧 runtime 停止，旧 metadata 与迟到 patch 被拒；新 App 重新 probe Bot 并由首个合法 owner 消息绑定 owner

#### Scenario: 同节点多个 Bot 生命周期隔离
- **GIVEN** 同一 Gateway 上不同 Agent 各有一个 managed 飞书 Bot
- **WHEN** 其中一个 Bot 重连、停用、替换或失败
- **THEN** 其他 Bot 的收发与 listener 生命周期不受影响

### Requirement: 托管飞书 listener 不得脱离 Gateway 存活

Gateway 启动的每个托管飞书 listener 与创建它的 Gateway 共享退出生命周期。无论 Gateway 是否有机会执行正常关闭流程，Gateway 终止后都不得留下继续占用飞书长连接或接收消息的旧 listener；Gateway 重启只建立当前 listener。连接空闲本身不触发退出或重连。

#### Scenario: 正常停止或重启 Gateway 时回收旧 listener
- **GIVEN** Gateway 已连接一个托管飞书 channel
- **WHEN** 运维者正常停止或重启 Gateway
- **THEN** 旧 Gateway 的飞书 listener 随其退出
- **AND** 重启后只有当前 Gateway 的 listener 接管该 Bot

#### Scenario: Gateway 无法执行清理便异常终止
- **GIVEN** Gateway 已连接一个托管飞书 channel
- **WHEN** Gateway 因崩溃、强制终止或其他原因未执行正常关闭便消失
- **THEN** 从确认原 Gateway 进程身份消失起 3 秒内，该 Gateway 启动的飞书 listener 原进程身份也消失
- **AND** 旧 listener 不再占用飞书长连接或接收用户消息

#### Scenario: 异常退出后重启恢复稳定消息路径
- **GIVEN** 托管飞书 channel 所属 Gateway 曾异常终止且已重新启动
- **WHEN** channel 收敛为已连接，用户连续向 Bot 发送应触发回复的消息
- **THEN** 每条消息都由当前 Gateway 接收并按既有行为回复
- **AND** 用户消息与回复继续同步到内部 IM 影子会话，不因旧 listener 而随机缺失或重复

#### Scenario: 正常空闲不改变 listener 状态
- **GIVEN** Gateway 与托管飞书 channel 正常运行但暂时没有入站消息
- **WHEN** channel 保持空闲
- **THEN** listener 不会仅因没有入站消息而退出、降级或主动重连

### Requirement: 飞书权限诊断只依据可信租户授权并允许降级

飞书 runtime 启动后执行 provider-owned probe。权限项只有在开放平台返回已授权且为 tenant identity 时才算满足；每项 capability 可接受 current 或明确列出的 legacy 等价 scope set。完整 probe 证明所有等价集合都不满足时才标 missing；网络/API/解析失败、grant 字段缺失或只有 user identity 时标 unknown。基础链路可用但权限不完整不停止 channel，而以上报的 structured checks 让 IM 显示 limited、raw scope、影响和修复方向。

#### Scenario: tenant grant 满足 current 或 legacy 等价权限
- **WHEN** scope probe 对某 capability 返回任一 accepted set，且所需 scope 均为 tenant granted
- **THEN** 该 capability 标为 satisfied，不因另一个等价 scope 名缺失而误报 limited

#### Scenario: 确定缺普通群消息权限时仍保留基础连接
- **GIVEN** 私聊和 @Bot 基础链路可用，但完整 probe 证明普通群消息 accepted sets 均未授权
- **WHEN** runtime 上报诊断
- **THEN** connection 保持可用、diagnostics 标 limited，并指出群背景上下文不完整及应补的 scope

#### Scenario: 权限 probe 失败时返回 unknown
- **WHEN** 飞书权限接口失败、响应字段不足或只返回 user identity grant
- **THEN** diagnostics 标 unknown 并建议重试，不生成确定的 missing scope 列表

#### Scenario: 同一配置代次的状态保持因果顺序
- **GIVEN** 某 channel 当前 runtime incarnation 已上报较新 status sequence
- **WHEN** 旧 runtime、较小 sequence 或已被新 desired 淘汰的 cache barrier 迟到
- **THEN** Gateway/IM 以 terminal stale/removed 结果释放上行 owner，不让旧状态覆盖当前状态或阻塞后续 manifest/result
