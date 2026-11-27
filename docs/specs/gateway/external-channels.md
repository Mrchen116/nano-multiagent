# gateway (personal_assistant) - External Channels Specification

> 对齐: feat-803
> 上级: [gateway (personal_assistant) Specification](spec.md)
>
> 写法纪律见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)。本目录只收 Gateway **对外可观察的行为**:消费者是在外部 IM / 内置 Web IM 上收发消息的终端用户、与 Gateway 双向通信的 IM 服务、敲启停命令的运维者。

## Purpose

飞书和其他外部 channel 的消息收发、IM 托管配置、多 Bot、回复镜像、控制投递、群聊上下文、权限审批、内部 IM 同步、离线自治和隔离契约。

## Requirements

### Requirement: 飞书 channel 消息收发

Gateway 通过飞书 SDK WebSocket 长连接收发消息。先依 Agent 协作范围决定收件；下述「团队公开」（`team`）场景中，私聊、实际 @Bot 或回复 Bot 的消息及时提醒，普通群动态按批次提供。普通 Global Agent 的 Bot 在应响应的消息持久入箱后添加「泣不成声」（`CRY`），完整读取后换成「了解」（`Get`）。其他模式的 Bot 使用待响应时添加、回复后移除的 THINKING 反应。

#### Scenario: 用户在飞书 1:1 私聊中发消息并收到回复
- **GIVEN** Gateway 配置了某个处于「团队公开」或已绑定该发送者为主人的 Agent 对应的飞书 Bot
- **WHEN** 用户在该飞书 Bot 的 1:1 对话窗口中发送一条文本消息
- **THEN** Bot 在合理时间内把 Agent 回复发回同一个 1:1 对话窗口

#### Scenario: 群聊中 @Bot 触发回复
- **GIVEN** Gateway 配置的飞书 Bot 已加入某飞书群且对应 Agent 处于「团队公开」
- **WHEN** 用户在群里 @Bot 并发送消息
- **THEN** Bot 在群里回复该消息

#### Scenario: 群聊中普通群消息先作为背景
- **GIVEN** Gateway 配置的飞书 Bot 已加入某飞书群且对应 Agent 处于「团队公开」
- **WHEN** 用户在群里发消息但未 @Bot
- **THEN** Bot 不因该条普通消息立即运行
- **AND** 当用户随后 @Bot 提问时，Bot 回复能引用之前未 @ 的群聊消息作为上下文

#### Scenario: @所有人 不算 @Bot
- **GIVEN** Gateway 配置的飞书 Bot 已加入某飞书群
- **WHEN** 用户在群里 @所有人 发消息，但没有单独 @Bot
- **THEN** Bot 不因该条普通消息立即运行
- **AND** 该消息按普通未 @ 群消息进入群背景上下文

#### Scenario: 普通消息持续十分钟合并提醒
- **GIVEN** Gateway 配置的飞书 Bot 已加入某飞书群，该 Agent 处于「团队公开」
- **WHEN** 用户在群里发送普通消息且没有 @Bot
- **THEN** 有新增积压时到期合并提醒，Agent 可以保持静默

#### Scenario: 其他模式的 Bot 对即将响应的消息显示 THINKING 反应并在回复后移除
- **GIVEN** Gateway 配置的非普通 Global Agent 飞书 Bot 收到一条需要响应的消息
- **WHEN** Bot 开始处理并随后发出回复
- **THEN** 用户在飞书里看到该消息先出现 THINKING 反应，回复发出后该反应消失

#### Scenario: 普通 Global Agent 的 Bot 展示收件和已读
- **WHEN** 应响应的消息持久入箱，然后由 Agent 完整读取
- **THEN** Bot 在原消息上的反应从「泣不成声」更新为「了解」
- **AND** 回执反馈可稍后更新，Agent 的读取和任务执行可独立推进

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

#### Scenario: JPEG 结束标记后存在附加数据
- **WHEN** 用户从飞书发送大小允许、可正常解码且结束标记后带附加数据的 JPEG 与文字
- **THEN** Agent 能基于图文继续回复，不因尾随数据误报图片损坏

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

Gateway 默认不在外部 channel 回复中暴露运行信息。启用全局设置后，Gateway 在由外部用户消息触发的普通最终 assistant 回复中呈现本轮已解析模型与 context 占用百分比；特定外部 channel 可以覆盖全局开关。飞书在有可呈现运行信息时，使用一张原生卡片承载原回复正文和紧凑运行信息区；其他已接入或未来外部 channel 以其支持的方式呈现同一信息。异常长的模型标识以最多 512 个字符加 `...` 的紧凑显示名呈现，避免挤占回复载荷。内部 Web IM 及其外部影子会话保持原正文。

#### Scenario: 全局启用后飞书最终回复使用原生卡片显示本轮运行信息
- **GIVEN** Gateway 已全局启用运行信息页脚，且本轮外部触发的普通最终回复具有已解析模型、prompt token 与 context window
- **WHEN** 用户在飞书收到该最终回复
- **THEN** 用户收到一张原生卡片，正文和模型名与 context 占用百分比在同一张卡片中，例如 `gpt-5.4 · ctx 42%`
- **AND** Gateway 不额外发送独立的运行信息消息，也不把运行信息作为普通 post 正文的附加文本
- **AND** 该百分比基于本轮实际 prompt token 与该模型的 context window 计算

#### Scenario: 全局启用后其他外部 channel 显示本轮运行信息
- **GIVEN** Gateway 已全局启用运行信息页脚，且本轮外部触发的普通最终回复具有已解析模型、prompt token 与 context window
- **WHEN** 用户在一个已接入的非飞书外部 channel 收到该最终回复
- **THEN** 用户以该 channel 支持的方式看到模型名与 context 占用百分比，例如 `gpt-5.4 · ctx 42%`
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

#### Scenario: 非最终或内部消息不呈现运行信息
- **GIVEN** 某外部 channel 的运行信息页脚已启用
- **WHEN** 同一 run 产生中间 assistant 文字、工具进度、审批卡、控制确认或内部 Web IM 影子回复
- **THEN** 这些消息都不显示运行信息
- **AND** 只有普通最终外部 assistant 回复可以显示该页脚

#### Scenario: 运行信息缺失时静默省略
- **GIVEN** 某外部 channel 的运行信息页脚已启用
- **WHEN** 最终回复只具有模型或只具有有效 context 占用数据
- **THEN** 运行信息只显示可取得的那一项，不显示未知占位符
- **WHEN** 两项都不可取得
- **THEN** Gateway 发送原最终回复，不增加空白运行信息区

#### Scenario: 异常长模型标识仍保留紧凑运行信息
- **GIVEN** 某外部 channel 的运行信息页脚已启用，且本轮已解析模型标识超过 512 个字符
- **WHEN** 用户收到普通最终 assistant 回复
- **THEN** 运行信息使用最多 512 个字符并以 `...` 结束的模型显示名
- **AND** 若本轮可取得 context 占用，该信息仍显示在同一运行信息区

#### Scenario: 飞书单卡大小超限时保留可读正文和运行信息
- **GIVEN** 飞书运行信息页脚已启用，且普通最终回复的正文在连同运行信息区编码后超出单张飞书卡片的可发送大小
- **WHEN** Gateway 向飞书发送该最终回复
- **THEN** 用户只收到一张原生飞书卡片，其正文保留开头的可读内容并以明确截断标记结束
- **AND** 同一张卡片保留本轮可取得的运行信息
- **AND** Gateway 不把剩余正文或运行信息拆成额外普通消息或额外卡片

### Requirement: 外部 channel 用户可见控制与后台文本投递

本条的渠道权限审批限定为原生工具。由外部 Worker 提出的提权及其终态仅投递该 Agent 的主人 Nano IM 私聊，即使派工由飞书触发也不投递到飞书或其影子会话。

聊天控制先通过协作范围检查。飞书触发或绑定的用户可见事件必须回到原飞书 chat，并同步到内部 IM 影子会话；内部 IM 影子会话触发的同类事件只留在内部 IM。用户可见事件包括 assistant 文本、`/stop`、`/new`、`/compact` 及 `/compact <关注点>` 的控制确认、因主模型不可用改用备用时的轻量说明、预处理失败、后台 agent 文本、权限审批卡片和审批完成状态。含非空真实更新对象的 `self_evolution_review` system notice 遵守同一触发源规则：飞书触发时在原 chat 显示简短 Bot 更新通知并在 shadow IM 保留结构化 system notice，内部 IM 触发时不回写飞书。外部控制确认的 session/context outcome 与可恢复 delivery intent 必须先同次持久化；该 intent 幂等物化为 shadow output 后才向飞书发送，重放同一 provider message 复用首次控制结果，不重复改变会话或上下文。Gateway 启动和 IM reconnect 必须扫描未物化或未 hand-off 的 intent。若进程恰在 provider 已接受发送、但 hand-off 状态尚未来得及持久化时退出，飞书沿既有 at-least-once outbound 语义可能收到一次重复确认；本系统不伪造跨 provider exactly-once 保证，IM shadow 仍以同一 durable output 收敛。其他系统通知、thinking、工具遥测和调试状态不作为飞书普通聊天消息外发。该轻量说明与压缩控制确认同一投递形态，不是运行信息页脚。

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
- **GIVEN** 飞书群有该 Bot 的共同上下文，且其协作范围为团队协作
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

#### Scenario: 飞书触发的模型备用切换说明回到原 chat
- **GIVEN** 用户从飞书发消息，本轮因主模型不可用改用了备用模型
- **WHEN** Gateway 投递切换说明
- **THEN** 原飞书 chat 收到与 Web IM 等价的一句 Bot 文本
- **AND** 内部 IM 影子会话出现同一说明

#### Scenario: 内部 IM 触发的模型备用切换说明不回写飞书
- **GIVEN** 用户从内部 Web IM 发消息导致改用备用
- **WHEN** Gateway 投递切换说明
- **THEN** 说明只出现在该内部 IM 对话
- **AND** 飞书原 chat 不收到对应消息

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

### Requirement: 飞书原生工具权限审批

需要人工审批的工具操作在原飞书对话与内部 IM 影子会话呈现同一请求。私聊可按字段检查实际输入，长值支持展开；超过平台预算时明确标出截断。群聊仅显示字段名和安全提示，完整输入由 owner 在内部 IM 查看。查看或展开参数不会批准操作。两端以第一个有效决定为准，重复点击不再改变结果；群成员不能代 owner 审批。

#### Scenario: 飞书触发的工具审批可在飞书中完成
- **GIVEN** 用户在飞书 1:1 对话中发送一条会触发受控工具的消息
- **WHEN** agent 请求工具权限
- **THEN** 飞书原对话出现 interactive approval card
- **AND** 卡片逐字段显示本次工具调用的输入 label 与 value，用户无需切换到内部 IM 即可判断将执行的操作
- **AND** 短值直接可读；长值先显示字段名、总行数和摘要，可展开查看平台可提供的内容并再次收起
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

### Requirement: IM 离线时飞书对话不阻塞

普通 Agent 延续离线执行与恢复镜像；正式 PA 需要中央身份和来源授权，不可用时持久保留输入待恢复。旧输出镜像失败不阻塞已可验证的新输入。

#### Scenario: IM 离线时飞书 1:1 对话仍正常
- **GIVEN** IM 服务当前不可达且 plato-bot 为普通 Agent
- **WHEN** 用户在飞书与 plato-bot 1:1 对话
- **THEN** plato-bot 仍正常回复用户
- **AND** 本次消息可暂不同步到内部 IM

#### Scenario: IM 离线时飞书群聊 @Bot 仍正常
- **GIVEN** IM 服务当前不可达且 plato-bot 为普通 Agent
- **WHEN** 用户在飞书群 @plato-bot 并发消息
- **THEN** plato-bot 仍在群里正常回复
- **AND** 本次消息可暂不同步到内部 IM

#### Scenario: PA 等待中央恢复
- **GIVEN** 正式 PA 的中央服务暂不可用
- **WHEN** 飞书消息到达后中央服务恢复
- **THEN** 输入在本地持久保留，授权可验证后单次接入同一个主会话

### Requirement: 外部 channel 会话隔离

同一外部 channel 的同一聊天如果绑定多个 agent，Gateway 与 IM 为每个 agent 保持独立的影子会话和 agent 会话上下文。

#### Scenario: 同一外部群绑定多个 agent 时生成多个独立会话
- **GIVEN** 飞书群同时配置了 plato-bot 和 luban-bot
- **WHEN** 用户在群里分别 @plato-bot 和 @luban-bot
- **THEN** 内部 IM 中同时存在 `plato · 群名 · feishu` 和 `luban · 群名 · feishu` 两个独立 group 会话
- **AND** 两个 agent 的上下文和回复互不混淆

### Requirement: IM 托管的外部 channel 可热调和并离线自治

用户经 IM 通道页保存的完整 desired manifest 是托管 external channel 的权威配置。Gateway 在 register 成功后接收完整 manifest，由唯一 ChannelManager 幂等执行新增、替换、启停、重连和删除；不要求改本地 `config.yaml` 或重启 Gateway。Gateway 只在内存中解封节点公钥 envelope，并把同一密文 manifest 原子缓存到本机；因此 IM 暂时不可达或 Gateway 重启时，已应用 channel 仍可启动和收发。同一 Agent 可按 provider 同时托管独立的 `feishu:<agent_id>` 与 `wechat:<agent_id>` 实例，每个实例严格维持单一活动长连接/长轮询（替换、重连、停用或删除时均异步等待在途旧轮询完全退出后再进入下一步，防止双轮询互抢消息）。当微信上游明确返回连接凭据已失效或已在别处重新绑定时，Gateway 立即停止该微信轮询、清理本地受保护会话游标与引用缓存，并上报可操作的失效重绑状态，不无限退避重试。内置 `web_relay` 不进入该 managed manifest。旧 standalone YAML、历史 backup 或 legacy export 不属于本契约。

#### Scenario: 在线保存后热连接且凭据不落普通配置
- **GIVEN** 节点在线且 IM 下发一个有效飞书或微信 desired item
- **WHEN** Gateway 调和该 manifest
- **THEN** ChannelManager 无需进程重启即启动对应 `<provider>:<agent_id>` runtime，并上报 connecting 后的真实终态
- **AND** App Secret 或微信连接令牌不写入 `config.yaml`、日志、状态 payload 或浏览器可读响应

#### Scenario: 离线期间继续从密文 cache 启动
- **GIVEN** 某 managed channel 已成功应用并写入节点绑定的密文 cache
- **WHEN** Gateway 在 IM 不可达时重启
- **THEN** Gateway 从 cache 启动该 channel，外部消息主路径保持可用
- **AND** IM 恢复并下发更高 manifest 后，runtime 自动收敛到最新 desired state

#### Scenario: disable/delete 真实停止且删除不清历史
- **WHEN** manifest 停用或删除某 channel（含先停用或失效后再删除）
- **THEN** Gateway 先从出站 registry 摘除该 runtime，再异步有界停止 worker/poller；失败回报可重试原因，不伪造 applied
- **AND** 成功删除彻底清理该通道的 runtime/cache identity 与本地动态游标及引用缓存，不影响同一 Agent 的其他 provider 通道，也不删除 IM 影子会话或消息历史

#### Scenario: 重复和失败后的同 revision manifest 可安全重放
- **GIVEN** Gateway 已成功应用 manifest N，或上次应用 N 时发生可重试失败
- **WHEN** IM 再次下发 N
- **THEN** 已成功项不重复启动 listener/poller，失败项继续重试未完成动作并回报真实 result
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

#### Scenario: 更换 App ID 或重新扫码更换微信绑定后不继承旧身份状态
- **GIVEN** channel 已记录旧飞书 App 的 Bot/owner metadata 或旧微信绑定的本地游标与引用缓存
- **WHEN** manifest 换为新飞书 App ID 或重新扫码后的新微信绑定身份
- **THEN** 旧 runtime 先异步完整停止，旧 metadata、旧上下文令牌与本地引用缓存清除且迟到 patch 被拒；新实例以全新绑定身份启动

#### Scenario: 微信凭据被撤销或异地重扫顶替时立即停止轮询并上报重绑提示
- **GIVEN** `wechat:<agent_id>` 正在运行长轮询
- **WHEN** 微信上游明确返回连接凭据已失效或已在别处重新绑定
- **THEN** Gateway 立即终止该通道轮询并清理本地上下文令牌与引用索引，向 IM 上报 `failed` 及需重新扫码绑定的明确状态信息，不在后台无限循环重试

#### Scenario: 同节点多个 Bot 与同一 Agent 多 provider 生命周期隔离
- **GIVEN** 同一 Gateway 上不同 Agent 各有外部 Bot，或同一 Agent 同时启用了飞书与微信两个外部通道
- **WHEN** 其中一个通道重连、停用、替换或失败
- **THEN** 其他 Agent 及同一 Agent 另一 provider 通道的收发与连接生命周期不受影响

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

### Requirement: 自动获取消息附件不访问任意网络目标

#### Scenario: 正常 Web 和渠道附件
- **WHEN** Web IM 发送受保护图片/文件，飞书发送原生图片/Post 附件，或微信发送受控加密 CDN 图片、语音、文件与视频媒体
- **THEN** Agent 仍可按既有图文与附件语义理解内容，IM 展示及正常渠道回复保持；自动获取仅使用受保护 IM 资源或经校验的官方渠道媒体源（如受控微信官方媒体域名，且禁止跨域重定向）。

#### Scenario: 伪造目标与越权资源
- **WHEN** 消息图片、分享卡片链接或自动转发引用非受控内网/loopback、任意外部网页 URL、跳转到非许可来源或未授权会话附件
- **THEN** 通道预处理与出站渲染均不自动抓取该外部网页或非许可目标，也不转发内部凭据；大小、类型与超时限制在实际流式读取时生效，不先无限下载再检查。
- **AND** 错误反馈能区分附件不可用且不泄漏令牌、内部地址细节或完整敏感 URL；普通网页链接与公众号文章链接保持为文本/卡片元数据交由 Agent 受控工具按需读取，不被通道层自动抓取。

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

### Requirement: 个人微信 channel 扫码连接、仅本人准入与富内容收发

Gateway 支持通过个人微信官方机器人通道（`wechat:<agent_id>`）收发 1:1 私聊消息，不要求用户在第三方开放平台预先手动创建应用。节点受控执行二维码获取、长轮询状态确认、受控官方域名切换与手机数字验证码校验；确认后仅接收扫码绑定者本人的私聊消息，非绑定微信账号发来的消息仅返回受频控拒绝提示，不进入内部 IM 影子会话、Agent 上下文或长期记忆。

微信入站消息自动同步至内部 IM 独立影子会话 `<agent名> · wechat`（沿用外部通道影子会话命名规则），遵循既有触发源决定回复去向、可见回复镜像、运行信息页脚（微信在开启运行信息页脚时以最终回复末尾的紧凑纯文本信息区呈现模型显示名与 context 占用百分比）及 `/new`、`/stop`、`/compact` 跨端会话控制契约。目标 Agent 为 Personal Agent 时，已绑定主人的微信私聊具有与主人内部 IM 私聊及飞书主人单聊相同的本人私聊身份、交办权限与定时提醒投递语义。

入站与出站内容保持如下可观察保证：
- **文章链接、分享卡片与合并聊天记录**：直接发送的链接及微信送达的分享卡片提取可读标题、摘要与来源链接；微信送达的合并转发聊天记录递归展开子消息的发送者、时间、正文及内嵌媒体/链接/嵌套记录说明，以明确的被转发引用结构呈现且不泄漏原始标记结构；遇到未携带可解析正文的特殊微信条目时，向微信与影子会话同步返回明确可读提示与替代发送建议，绝不静默丢弃。
- **双层语音、原图、通用文件、视频与引用还原**：语音在微信侧附带现成转写文本时直接呈现转写文本供日常对话理解，并在语音媒体存在时同步保留转码后的原声附件（`voice-raw.wav`/`voice-raw.mp3`）及按需下载说明，供需要处理原始音频文件的场景通过 `download_attachment` 取用（原声拉取异常不阻断已有转写文本）；缺失转写时自动下载解密并还原音频附件（`voice.wav`/`voice.mp3`）交给 Agent 处理（无法直接识别音频时给出明确可读反馈）；16 MiB 以内原图/截图经方向归一化与合规尺寸收敛后在影子会话直接展示为图片附件且不插入多余 `[图片]` 文本；合规通用文件与视频附件同步至影子会话并可供 Agent 在受控目录读取，超限或获取失败双向给出明确原因；全文引用与局部选中文字引用自动还原被引用原文片段或媒体摘要，本地引用索引仅限本机当前绑定可读且随解绑/删除一并清除。
- **正在输入状态、格式净化、长文切分与图片出站**：运行期间维持微信“正在输入…”状态并在完成、中止或报错后停止；出站文本清理微信不支持的排版标记，超长文本按单条上限安全分段且不截断代码块围栏；Agent 回复或显式发送附带的受控图片加密上传后作为原生微信图片消息发出，并在内部 IM 影子会话同步保留。

#### Scenario: 绑定者微信私聊同步影子会话并拦截非绑定者消息
- **GIVEN** Gateway 已连接绑定某微信主人的 `wechat:<agent_id>` 通道（普通 Agent 或 Personal Agent）
- **WHEN** 绑定者本人在微信发送消息并获得回复，同时另一非绑定微信用户向该机器人发送消息
- **THEN** 绑定者的消息与 Agent 回复同步呈现在微信原对话与内部 IM `<agent名> · wechat` 影子会话中（Personal Agent 按本人私聊身份处理）
- **AND** 非绑定用户的消息仅收到受频控提示，不进入内部 IM 影子会话或触发 Agent 执行

#### Scenario: 分享卡片、合并转发记录与不支持特殊卡片分别可读或明确提示
- **WHEN** 绑定者在微信发送公开文章链接/分享卡片、微信已送达记录负载的合并转发聊天记录，或无有效负载的表情包/特殊卡片
- **THEN** 分享卡片展示标题、摘要与链接并由 Agent 通过受控网页工具按需读取正文；合并转发记录展开各条子消息发言人、时间、文字与内嵌附件说明且与绑定者本轮直接指令分层区分；不支持的特殊条目在微信与影子会话均返回明确提示而不静默丢弃

#### Scenario: 语音双层兜底、原图/文件/视频入站、引用还原与图文分段出站
- **WHEN** 绑定者在微信发送带转写或无转写的语音、16 MiB 内原图、合规文档/视频附件，或对历史消息做全文/局部文字引用提问，且 Agent 生成含代码块的长回复与图片
- **THEN** 有转写语音日常直接按文本理解且同步保留原声附件供需要原音频的任务按需下载，无转写语音自动还原音频附件处理或给出明确说明；原图直接作为图片附件展示并进入多模态输入；文件/视频可在受控目录读取（超限明确报错）；引用上下文准确还原；长回复分段不破代码块且图片作为微信图片消息送达并在影子会话同步可见

### Requirement: 个人微信文本工具权限审批与内部 IM 互斥同步

由于个人微信官方机器人通道不提供交互式按钮卡片，当微信触发的单会话（`single_thread`）运行产生需要人工确认的工具权限请求时，Gateway 同时在内部 IM 影子会话呈现标准审批卡片，并在微信私聊发送包含工具名、原因、关键参数摘要及简短文本回复口令（允许 / 拒绝及可选拒绝原因）的可读提示；全局模式（`global`）与 Personal Agent 继续遵循各自的既有对话内确认语义，不额外生成审批卡片。微信纯文本审批口令与内部 IM 审批卡片共享同一权限请求状态机，以先到达的有效决定为准，后到达的重复回复或点击不再重复提交或篡改结果；运行被 `/stop`、`/new`、停用或异常终结时，未决外部审批提示同步失效，不拦截后续正常消息。

#### Scenario: 在微信通过文本回复完成工具审批并同步内部 IM 卡片
- **GIVEN** 绑定者在微信触发的单会话运行进入待人工审批状态，微信已收到文本审批指引且内部 IM 影子会话已显示审批卡片
- **WHEN** 绑定者在微信直接发送纯文本允许口令（或带原因的拒绝口令）
- **THEN** 该审批决定立即生效（拒绝原因同步传入 Agent），微信收到简短处理确认，且内部 IM 影子会话中的审批卡片同步更新为已处理状态

#### Scenario: 内部 IM 先完成审批或运行中止后微信消息不误触发审批
- **GIVEN** 微信触发的单会话运行同时在内部 IM 影子会话与微信私聊处于待审批状态
- **WHEN** 绑定者先在内部 IM 点击批准或拒绝，随后又在微信回复允许或拒绝口令
- **THEN** 内部 IM 的首次决定立即生效并向微信同步已完成提示；随后的微信重复审批口令仅提示该审批已处理，不第二次提交权限决策或误触发无关模型执行
- **WHEN** 待审批运行因 `/stop`、`/new` 或停用而提前结束，绑定者随后在微信发送包含“1”或“同意”的普通对话消息
- **THEN** 旧审批随运行结束一并失效，后续普通消息按正常对话处理而不报错吞消息
