# IM - Conversations and Messages Specification

> 对齐: feat-447
> 上级: [IM Specification](spec.md)
>
> 写法纪律见 [`../../SPEC_GUIDE.md`](../../SPEC_GUIDE.md)。本目录只收 **IM 的消费者真正依赖的对外行为**:浏览器前端、Node Gateway、终端用户，以及 `tests/im_service/` 里的契约测试。

## Purpose

会话、消息、外部 channel 影子会话、消息顺序、群会话和 fork 的 IM 契约。

## Requirements

### Requirement: 会话与消息以 Actor 语义建模,响应字段稳定且分页

前端经 `/im/v1/conversations*` 创建/读取会话与消息;消息发送者是 Actor(人/Agent/system),响应暴露
稳定的 `delivery_status` / `sender_type` / `attachments` 等字段并以 `{items, next_before_message_id}`
信封分页。未知会话的消息/详情/更新接口保持稳定的 404 语义。

#### Scenario: 创建会话指定参与者 Actor
- **WHEN** 前端 `POST /im/v1/conversations {title, participant_ids:[...]}`
- **THEN** 201 返回含会话 `id`;后续以该 `conversation_id` 读写消息

#### Scenario: 创建消息回显投递状态与发送者类型
- **WHEN** 前端 `POST /im/v1/conversations/{id}/messages {sender_user_id, content, sender_type?, attachments?}`
- **THEN** 201 返回 `{id, conversation_id, delivery_status, sender_type, attachments, ...}`;
  `sender_type` 缺省为 `user`,可显式为 `agent`;`attachments` 为空时是 `[]`

#### Scenario: 列消息走 items+游标信封并暴露同样字段
- **WHEN** 前端 `GET /im/v1/conversations/{id}/messages?limit=N`
- **THEN** 200 返回恰含键 `["items","next_before_message_id"]`;每条携 `delivery_status`/`sender_type`/
  `attachments`;最后一页 `next_before_message_id` 为 `null`,有更多时为下一游标 message id

#### Scenario: 未知会话相关读写返回稳定 404
- **WHEN** 前端对不存在的 `conversation_id` 调 messages / 详情(GET) / 更新(PATCH)
- **THEN** 全部 404,`detail == "conversation_id not found"`

### Requirement: 外部 channel 影子会话按外部身份幂等创建

IM 支持为 Gateway 创建带 `external_source` 和 `external_chat_id` 标记的影子会话,用于镜像外部
channel 中的聊天。1:1 私聊映射为 `direct` 类型,群聊映射为 `group` 类型。会话按
`(external_source, external_chat_id, agent_id, owner_id)` 幂等创建或查找;`agent_id` 使用 IM 现有
conversation agent 配置维度,不引入第二套 agent 身份来源。

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

### Requirement: 外部 channel 用户消息可写入影子会话

IM 支持 Gateway 将来自外部 channel 的用户消息写入影子会话。消息持久化发送者显示名
`sender_display_name`;外部群成员显示原名字,IM owner 自己从外部 channel 发送的消息显示为「你」。
外部消息与普通 IM 消息共享读取、分页、权限和投递状态语义。

#### Scenario: 外部 1:1 用户消息显示为「你」
- **GIVEN** Gateway 写入一条 IM owner 从飞书 1:1 发来的消息
- **WHEN** 用户通过 REST 或 WebSocket 查看该会话历史
- **THEN** 该消息显示为「你」发送

#### Scenario: 外部群聊消息显示原发送者名字
- **GIVEN** Gateway 写入一条 Alice 从飞书群发来的消息
- **WHEN** 用户通过 REST 或 WebSocket 查看该会话历史
- **THEN** 该消息显示为 Alice 发送

### Requirement: 外部 channel 用户消息实时出现

IM 将外部 channel 用户消息写入影子会话后,必须通过浏览器 user-stream 发出足以直接插入当前会话
消息列表的 live 事件。打开中的影子会话不得依赖刷新历史才能看到飞书/Lark 用户刚发来的消息。
该 live 事件必须携带消息正文、附件、发送者类型、发送者显示名、delivery status 和创建时间。

#### Scenario: 打开的影子会话不刷新即可看到飞书用户消息
- **GIVEN** 用户已经在浏览器打开 `plato · feishu` 影子会话
- **WHEN** Gateway 写入一条 IM owner 从飞书 1:1 发来的新消息
- **THEN** 浏览器通过 user-stream 收到 canonical `message.created` 或等效完整新消息事件
- **AND** 当前消息列表立即追加该用户气泡,无需刷新页面或重新进入会话
- **AND** 该气泡显示为「你」

#### Scenario: 外部群成员 live 消息显示原发送者名
- **GIVEN** 用户已经在浏览器打开 `plato · 产品群 · feishu` shadow group
- **WHEN** Gateway 写入一条 Alice 从飞书群发来的新消息
- **THEN** 当前消息列表立即追加 Alice 的用户气泡
- **AND** live 显示名与刷新历史后的显示名一致

### Requirement: 外部 channel mention-only 消息可见

外部群聊中的 @Bot 是用户可见消息内容。IM 必须能持久化并实时显示 mention-only 和 mention+正文消息,
不得因为 Gateway 做 mention gate 而只保留去掉 @ 后的正文,也不得因为正文去除 mention 后为空而拒绝写入。
Gateway 写入时应提供规范化非空内容(例如 IM mention wire 或 `@nano`)或等效结构化展示字段。

#### Scenario: 纯 @Bot 消息写入 shadow group
- **GIVEN** 用户在飞书群里只发送 `@nano`
- **WHEN** Gateway 将该消息写入 `nano · <群名> · feishu` shadow group
- **THEN** IM 接受该写入,不会返回空消息错误
- **AND** 浏览器当前消息列表中出现一条内容为 `@nano` 或等效 mention 展示的用户气泡

#### Scenario: @Bot 加正文保留 mention 展示
- **GIVEN** 用户在飞书群里发送 `@nano hi`
- **WHEN** Gateway 将该消息写入 shadow group
- **THEN** 浏览器当前消息列表中出现 `@nano hi` 或等效 mention chip + `hi`
- **AND** 不会只显示 `hi`

### Requirement: 外部 channel 会话元数据回环

IM 通过 WebSocket relay 把影子会话中的用户消息转发给 Gateway 时,必须携带该会话的外部 channel
元数据(`external_source`、`external_chat_id`、`agent_id`、`conversation_type`)以及触发来源标记
(`trigger_source`),使 Gateway 能够复用同一 agent 会话、识别影子 group,并按触发源决定回复去向。
`external_chat_id` 指外部 channel 的 chat id,不是 IM conversation id。

#### Scenario: 内部 IM 消息被 Gateway 识别为 IM 来源
- **GIVEN** 内部 IM 中存在 `plato · feishu` 影子会话
- **WHEN** 用户在该会话中发送消息
- **THEN** Gateway 收到该消息后,将其识别为来自 IM 的触发
- **AND** agent 回复只留在 IM,不回写飞书

#### Scenario: 影子群聊消息携带 conversation_type
- **GIVEN** 内部 IM 中存在 `plato · 产品群 · feishu` group 影子会话
- **WHEN** 用户在该会话中发送消息
- **THEN** relay payload 携带 `conversation_type="group"`、`external_source="feishu"`、飞书 `external_chat_id` 和 `agent_id="plato"`
- **AND** Gateway 可按 group 路径触发 agent 回复

### Requirement: 外部 channel 影子会话不改变现有 IM 行为

外部 channel 影子会话和消息的加入不影响 IM 现有 direct/group 会话、普通用户消息、agent 消息渲染和权限模型。

#### Scenario: 普通直连会话不受外部 channel 影响
- **GIVEN** 用户与 plato 有一个普通直连会话
- **WHEN** 用户在飞书与 plato-bot 对话
- **THEN** 飞书同步产生的 `plato · feishu` 会话与普通直连会话保持独立,互不合并

### Requirement: 聊天流消息按时间顺序渲染，实时与刷新一致

聊天流中的消息按各自创建时刻先后渲染。该顺序在实时事件流到达时即生效，无需刷新，
且与刷新页面（走历史拉取）后的顺序一致。

#### Scenario: 实时到达的 agent 回复按时间排在用户消息之后
- **GIVEN** 用户在会话里发了一条消息，其后 agent 产生一条更晚的回复
- **WHEN** agent 回复经实时事件流到达前端（无需刷新）
- **THEN** 用户消息在上、agent 回复在下，与刷新页面后的顺序一致；
  不会出现「回复气泡短暂排在用户消息之前」的错位

#### Scenario: 实时事件到达顺序与时间顺序不一致时仍按时间渲染
- **GIVEN** 两条消息的时间先后已定（由各自创建时刻决定）
- **WHEN** 它们的实时事件以与时间相反的顺序先后到达前端
- **THEN** 聊天流仍按创建时刻先后渲染，到达先后不影响最终顺序；
  时刻相同的消息有稳定确定的相对次序，不抖动

### Requirement: 群会话支持成员增减、改名与解散（owner 隔离、解散限创建者）

前端经 `/im/v1/conversations/{id}*` 对一个已存在的群会话管理其成员与元数据：向群添加参与者（Actor）、
移除某个参与者、修改群名、解散整个群。所有操作按 owner 租户隔离（跨租户 404）；解散仅会话创建者可执行，
非创建者被拒。这些能力让用户在内置 Web IM 里完成基本群治理，无需重建群。

#### Scenario: 向已存在的群会话添加参与者
- **GIVEN** 终端用户在自己租户下有一个群会话，且账号下存在尚未加入该群的 agent
- **WHEN** 前端 `POST /im/v1/conversations/{id}/participants` 带一组 Actor（`{type:"agent", id:"<agent_id>"}`）
- **THEN** 200 返回该会话快照，其 `participants` 含新加入的 agent；此后该 agent 能收发该会话后续消息

#### Scenario: 重复添加已在群的参与者保持幂等
- **GIVEN** 某 agent 已是该群成员
- **WHEN** 前端再次 `POST /participants` 提交同一 agent
- **THEN** 成员不重复出现，会话快照参与者集合不变（不报 500）

#### Scenario: 添加请求为空或 agent 无法解析被拒
- **WHEN** 前端 `POST /participants` 提交空列表或无法解析为已知 agent 的 id
- **THEN** 400 拒绝，会话成员不变

#### Scenario: 跨租户添加参与者返回 404
- **WHEN** 用户对不属于自己租户的会话 `POST /participants`
- **THEN** 404，不泄漏该会话存在

#### Scenario: 修改群名生效，空名被拒
- **WHEN** 前端 `PATCH /im/v1/conversations/{id}` 提交非空 `title`
- **THEN** 200 返回更新后的会话，会话列表与详情显示新群名
- **AND** 提交空 `title` 时不接受为新名（会话名保持原值）

#### Scenario: 会话参与者带 user_id 供成员管理
- **WHEN** 前端读取会话（`GET /conversations` 或写操作返回的快照）
- **THEN** 每个 participant 带 `user_id`（agent participant 的 `id` 是 agent_id，`user_id` 是其稳定 IM 用户标识），前端据 `user_id` 调移除端点

#### Scenario: 移除参与者后该成员从群消失
- **GIVEN** 群里有多个 agent 成员
- **WHEN** 前端 `DELETE /im/v1/conversations/{id}/participants/{user_id}` 指定某 agent 的 `user_id`
- **THEN** 204；该会话快照参与者集合不再含该成员；可一直移除到群里只剩用户本人，群仍存在

#### Scenario: 仅创建者可解散群，非创建者被拒
- **WHEN** 会话创建者 `DELETE /im/v1/conversations/{id}`
- **THEN** 204，该会话及其消息被删除，列表不再返回它
- **AND** 非创建者发起同一请求时 403，会话不被删除

### Requirement: 用户可从单聊里某条已完成的 agent 回复 fork 出带历史的分支单聊

在「你 ↔ 单个 agent」的单聊里，用户可在一条已回复完成的 agent 消息上发起 fork，得到一个与同一 agent 的新单聊：新单聊带入从会话起点到该条回复（含）的全部消息，且 agent 在新单聊里带着这段历史的记忆继续对话。fork 入口只出现在单聊中已完成的 agent 消息上；用户自己的消息、生成中的 agent 消息、群聊中的消息均不提供 fork。新单聊作为普通 direct-agent 单聊出现在会话列表，名称为 agent 名。

#### Scenario: 在已完成的 agent 回复上 fork 得到带历史的新单聊
- **GIVEN** 用户在与某 agent 的单聊里，有一条已回复完成的 agent 消息 M，且该 agent 在线
- **WHEN** 用户在 M 上发起 fork
- **THEN** 系统新建一个与同一 agent 的单聊，带入从会话起点到 M（含 M）的全部消息（顺序与原会话一致、保留完整气泡形态），M 之后的消息不带入；用户被自动带入该新单聊并可立即发消息

#### Scenario: 分支单聊里 agent 记得到 fork 点为止的历史
- **GIVEN** 带入的历史里 agent 给过一条「分多点」的回复
- **WHEN** 用户在分支单聊里发「第二点再展开讲讲」（不重述第二点内容）
- **THEN** agent 的回复针对历史里那条回复的「第二点」展开，表明它带着历史上下文继续，而非从零开始

#### Scenario: 原会话不受 fork 影响、两线独立
- **GIVEN** 用户已从某会话 fork 出分支单聊并在其中继续对话
- **WHEN** 用户切回原会话
- **THEN** 原会话消息与对话状态完全不变，不出现分支单聊里的新消息；反之在原会话继续聊也不影响分支单聊

#### Scenario: fork 入口只在单聊已完成 agent 回复上出现
- **WHEN** 用户查看自己的消息、生成中的 agent 回复、或群聊中的任意消息
- **THEN** 这些消息上都不提供 fork 入口

### Requirement: agent 离线时 fork 不可用且给出明确提示

被 fork 的 agent 当前离线 / 不可用时，fork 操作不执行，用户得到明确反馈；系统不会建出一个 agent 不记得历史的空壳单聊（fork 过程中任一步失败均原子回滚，不留孤儿会话）。

#### Scenario: agent 离线时 fork 被拒并明确提示
- **GIVEN** 某 agent 当前离线
- **WHEN** 用户尝试在其历史回复上 fork
- **THEN** fork 不执行，用户看到「该 agent 当前不可用，暂时无法 fork」一类明确提示；会话列表里不新增任何单聊

#### Scenario: fork 中途失败不留孤儿会话
- **GIVEN** 校验通过、agent 在线、新会话已建并已委托内核侧 fork，但其后某一步（内核 fork 或展示历史复制）失败
- **WHEN** fork 流程结束
- **THEN** 已建的新会话被回滚删除，用户看到 fork 失败提示；不留下一个有历史显示但 agent 不记得的单聊
