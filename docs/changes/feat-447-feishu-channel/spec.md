# feat-447: 飞书 channel 支持

## 原始需求

> 现在给我的gateway做一个重大需求，参考openclaw和hermes的方式，做飞书channel的支持。

## 澄清记录

- Q1: MVP 边界——先做"能对话"还是连飞书工具一起做?
  A(原话): 我们先从基础的开始构建，你得先跟我讲讲你要怎么去设计这个 channel。我先陈述一下我想达到的一个使用效果。首先我需要通过飞书，可以直接在飞书的消息平台上和我的这个 Agent 进行交互。并且我此页面上是有多个 Agent 的，即柏拉图、鲁班和 Humor。也就是说我在飞书上消息交互的方式要和当前内部im页面的交互方式是一样。同时需要满足在飞书空间使用用户权限，非只有bot权限去进行创建云空间、云文件夹、云具体云文件，并且进行编辑管理等。
  Agent 解读: 用户要两件事——(1) 飞书上多 Agent 对话，交互方式与内部 IM 一致；(2) 以用户身份操作飞书云文档（创建空间/文件夹/文件/编辑），非 bot 身份。先从基础构建，但云文档操作也要做。

- Q2: 飞书上多 Agent 选择——一个 Bot 对应一个 Agent，还是一个 Bot 命令切换?
  A(原话): 一个飞书 Bot 对应一个 Agent。
  Agent 解读: plato / luban / hume 各建一个飞书应用，用户跟哪个 Bot 聊天就是选哪个 agent。

- Q3: 群聊触发方式——@Bot 才响应还是每条消息都响应?
  A(原话): 可以，我支持这个方向。（指 @Bot 才响应 + 未 @ 消息存 history buffer 作为上下文）
  Agent 解读: 群聊默认 require_mention=true，@Bot 才触发；借鉴 OpenClaw 的 history buffer，未 @ 的消息暂存，下次 @ 时作为上下文前置。支持全局 + 每群覆盖配置。

- Q4: 飞书云文档操作——具体需要哪些能力?
  A(原话): 暂时只考虑上述文档相关的内容。
  Agent 解读: MVP 只做基础文档操作——创建文档、读取内容、编辑/追加、创建文件夹、移动文件。不做 wiki（知识库）、bitable（多维表格）、drive（云盘高级操作）。

- Q5: 文档评论操作要不要纳入本期?
  A(原话): 可以，文档评论暂时先不增加这个功能。
  Agent 解读: 文档评论（list_comments / add_comment / reply_comment）不纳入本期。

- Q6: 飞书对话是否同步到内部 IM?
  A(原话): 加到spec。
  Agent 解读: 飞书消息和回复 mirror 到 IM 服务，内部 IM web UI 可见。参考 OpenClaw/Hermes 的共享 session store 模式，方案 A：飞书消息处理完后回推到 IM 服务。

- Q7: 外部 channel（以飞书为首个实现）同步过来的消息，在内部 IM 里要作为一个独立的会话，还是合并进该 agent 的普通直连会话？
  A(原话): 独立会话，其他在内部IM的会话命名都是agent名，其他channel的应该设计成 agent名 · channel名。
  Agent 解读: 所有外部 channel 在内部 IM 都有独立会话，会话显示名为 `agent名 · channel名`（例如 `plato · feishu`）。这是跨 channel 的通用规则。

- Q2（通用规则）：对于任意外部 channel 在内部 IM 的同步会话，用户在该会话里回复，算「在原 channel 里接着聊」还是「只在内部 IM 里继续」？
  A(原话): 理解对的。后续再在飞书聊的话，agent还是能接上对应的上下文。
  Agent 解读: 外部 channel 在内部 IM 的同步会话是双向镜像：外部 channel 用户消息同步到内部 IM；agent 回复按触发源路由——飞书触发的回复回写飞书并同步到 IM，IM 触发的回复只留在 IM。无论用户从哪个入口说话，都复用同一个 kernel session，上下文连续。

- Q3（通用规则）：外部 channel 群聊里，未 @Bot、只进 history buffer 的消息，要同步到内部 IM 吗？
  A(原话): 可能是我之前说的不够明确，这个应该是复用我内部IM的逻辑吧，对于设置了@才回的agent，是未@暂存，@就回应。设置了不@也回的，则都回应。
  Agent 解读: 外部 channel 的 mention 门控逻辑与内部 IM 完全一致：@才回的 agent，未 @ 消息作为上下文暂存并同步到 IM；不 @ 也回的 agent，所有消息都触发回复并同步到 IM。

- Q4：外部 channel 的群聊，在内部 IM 里怎么表示？
  A(原话): A看起来合适
  Agent 解读: 外部 channel 群聊在内部 IM 映射为一个独立的 group 会话（影子 group），会话显示名为 `agent名 · channel名`，会话参与者为 IM owner + agent；外部群成员以带名字的用户消息形式出现在该 group 会话中。

- Q4-1：外部 channel 群聊消息在内部 IM 中是否显示原发送者名称？
  A(原话): A
  Agent 解读: 外部群聊的每条用户消息气泡旁显示该用户在原 channel 中的名字（如 Alice、Bob）。

- Q5：外部 channel 会话里，IM owner 自己从外部 channel 发的消息，在内部 IM 显示成「你」还是带原 channel 名字？
  A(原话): 对
  Agent 解读: IM owner 自己从外部 channel 发的消息，在内部 IM 显示为「你」，与内部 IM 其他会话中 owner 自己的消息显示一致。

- Q6：外部 channel 的群聊在内部 IM 里的会话名怎么定？
  A(原话): agent名 · 群名 · channel名。考虑一种情况，一个飞书群，有两个我们的agent，对于内部IM来说这也是两个不同的会话，不同的agent是主角。
  Agent 解读: 外部 channel 群聊在内部 IM 的会话名为 `agent名 · 群名 · channel名`（例如 `plato · 产品群 · feishu`）。同一外部群如果绑了多个 agent，内部 IM 会生成多个独立会话，每个 agent 各自一个。1:1 私聊保持 `agent名 · channel名`。

## 用户场景

用户在飞书上通过三个飞书 Bot（plato / luban / hume）分别与对应的 Agent 交互，体验与内部 IM 页面一致。飞书对话以独立会话的形式同步到内部 IM，用户可在内部 IM 继续同一会话的上下文；该规则同时作为所有外部 channel（以飞书为首个实现）的通用同步规范。

### 1:1 私聊

用户打开某个 Agent 对应的飞书 Bot 对话窗口，直接发消息。Bot 永远响应，无需 @。session 按用户维度隔离，每个用户跟每个 Bot 有独立的对话上下文。该对话在内部 IM 中以 `agent名 · channel名` 的独立会话呈现，与 agent 的普通直连会话区分。

### 群聊

用户在飞书群里 @Bot 发消息，Bot 响应。未 @ 的消息不会触发回复，但会被暂存为上下文——当用户下次 @Bot 时，agent 能看到之前未 @ 的群聊消息作为背景信息。群聊 session 默认按群维度隔离（整个群共用一个 session）。飞书群聊在内部 IM 中映射为一个独立的 group 会话，会话名为 `agent名 · 群名 · channel名`；外部群成员的消息以带原发送者名字的用户消息显示，IM owner 自己从飞书发的消息显示为「你」。如果同一飞书群绑了多个 agent，每个 agent 在内部 IM 都有各自的独立 group 会话。

### 飞书云文档操作（用户身份）

用户在对话中要求 agent 创建文档、编辑文档、创建文件夹等。agent 以**用户身份**（user_access_token）调用飞书 API，而非 bot 身份。用户首次使用前需要完成一次 OAuth 授权。操作结果在飞书云空间中可见，归属于用户本人。

## 验收标准

### Requirement: 飞书 1:1 私聊对话

#### Scenario: 用户在 1:1 私聊中发消息
- **WHEN** 用户在飞书 Bot 的 1:1 对话窗口中发送一条文本消息
- **THEN** Bot 在合理时间内回复，回复内容出现在同一个对话窗口中

#### Scenario: 私聊无需 @ 触发
- **WHEN** 用户在 1:1 对话窗口中发送消息（不带 @）
- **THEN** Bot 正常响应

#### Scenario: 私聊 session 隔离
- **GIVEN** 用户 A 和用户 B 分别与同一个 Bot 1:1 对话
- **WHEN** 用户 A 发送消息后，用户 B 发送消息
- **THEN** Bot 对用户 A 和用户 B 的回复互不影响，各自有独立的对话上下文

### Requirement: 飞书群聊 @Bot 触发

#### Scenario: 群聊中 @Bot 触发回复
- **GIVEN** Bot 已加入飞书群
- **WHEN** 用户在群里 @Bot 并发送消息
- **THEN** Bot 在群里回复该消息

#### Scenario: 群聊中未 @Bot 不触发
- **GIVEN** Bot 已加入飞书群
- **WHEN** 用户在群里发消息但未 @Bot
- **THEN** Bot 不回复

#### Scenario: 未 @ 消息作为上下文
- **GIVEN** 用户在群里发了 3 条未 @Bot 的消息讨论"项目延期原因"
- **WHEN** 用户第 4 条消息 @Bot 问"帮我总结一下刚才的讨论"
- **THEN** Bot 回复中包含前 3 条消息讨论的"项目延期原因"相关内容

#### Scenario: @所有人 不算 @Bot
- **WHEN** 用户在群里 @所有人 发消息，未单独 @Bot
- **THEN** Bot 不回复

### Requirement: 多 Agent 路由

#### Scenario: 不同 Bot 对应不同 Agent
- **GIVEN** 系统配置了三个飞书 Bot：plato-bot / luban-bot / hume-bot
- **WHEN** 用户与 plato-bot 对话
- **THEN** 回复来自 plato Agent，而非 luban 或 hume

### Requirement: 外部 channel 会话同步到内部 IM

#### Scenario: 外部 1:1 会话在内部 IM 有独立会话
- **GIVEN** 用户与 plato-bot 在飞书 1:1 对话
- **WHEN** 用户发送第一条消息
- **THEN** 内部 IM 中出现一个名为 `plato · feishu` 的独立会话，且不与 plato 的普通直连会话合并

#### Scenario: 外部 1:1 用户消息同步到内部 IM
- **GIVEN** 用户在飞书与 plato-bot 1:1 对话
- **WHEN** 用户发送一条消息
- **THEN** 该消息作为「你」的消息出现在内部 IM 的 `plato · feishu` 会话中

#### Scenario: 外部 1:1 agent 回复同步到内部 IM
- **GIVEN** 用户在飞书与 plato-bot 1:1 对话
- **WHEN** plato-bot 回复用户
- **THEN** 该回复出现在内部 IM 的 `plato · feishu` 会话中，包含完整 agent 输出（正文、tool call、thinking 等）

#### Scenario: 在内部 IM 回复不会回写飞书但上下文连续
- **GIVEN** 内部 IM 已存在 `plato · feishu` 会话
- **WHEN** 用户在该会话中发送消息
- **THEN** plato 的回复只出现在内部 IM 会话，不出现在飞书原对话中
- **AND** 下次用户在飞书原对话中发消息时，plato 能引用本次 IM 中的上下文

#### Scenario: 在内部 IM 群聊影子会话发消息自动触发 agent 回复
- **GIVEN** 内部 IM 已存在 `plato · 产品群 · feishu` group 影子会话
- **WHEN** 用户在该会话中发送消息（不 @plato）
- **THEN** plato 正常回复该消息
- **AND** 该回复只出现在内部 IM 会话，不回写飞书

#### Scenario: 同一 kernel session 跨入口上下文连续
- **GIVEN** 用户在飞书问了 plato-bot "我叫什么"
- **WHEN** 用户在内部 IM 的 `plato · feishu` 会话中回复 "你刚才不是知道吗"
- **THEN** plato 能引用前一条上下文，不会当成新会话

#### Scenario: 外部群聊在内部 IM 有独立 group 会话
- **GIVEN** plato-bot 已加入飞书群「产品群」
- **WHEN** 用户在群里 @plato-bot 并发消息
- **THEN** 内部 IM 中出现一个名为 `plato · 产品群 · feishu` 的独立 group 会话，会话参与者为 IM owner 和 plato

#### Scenario: 同一外部群绑定多个 agent 时生成多个独立会话
- **GIVEN** 飞书群「产品群」同时配置了 plato-bot 和 luban-bot
- **WHEN** 用户在群里分别 @plato-bot 和 @luban-bot
- **THEN** 内部 IM 中同时存在 `plato · 产品群 · feishu` 和 `luban · 产品群 · feishu` 两个独立的 group 会话，各自的内容互不混淆

#### Scenario: 外部群聊消息显示原发送者名字
- **GIVEN** 飞书群「产品群」中 Alice 发了消息
- **WHEN** 该消息同步到内部 IM
- **THEN** 内部 IM 中显示为 Alice 发送的用户消息（非匿名「用户」）

#### Scenario: 外部群聊中 IM owner 的消息显示为「你」
- **GIVEN** IM owner 在飞书群「产品群」中发了消息
- **WHEN** 该消息同步到内部 IM
- **THEN** 内部 IM 中该消息显示为「你」发送的消息

#### Scenario: 未 @ 的群聊上下文消息同步到内部 IM
- **GIVEN** plato 的 group_reply_policy 为 MENTION，Alice 在飞书群「产品群」发了 2 条未 @plato 的消息
- **WHEN** 这些消息作为上下文被暂存
- **THEN** 它们作为普通用户消息同步到内部 IM 的 `plato · 产品群 · feishu` group 会话中，显示发送者名字

#### Scenario: 不 @ 也回的 agent 群聊消息全量同步
- **GIVEN** plato 的 group_reply_policy 为 ALWAYS
- **WHEN** 群成员在飞书群「产品群」发送任意消息
- **THEN** 每条消息都触发 plato 回复，并全部同步到内部 IM 的 `plato · 产品群 · feishu` group 会话中

#### Scenario: IM 离线时飞书对话不中断
- **GIVEN** IM 服务当前不可达
- **WHEN** 用户在飞书与 plato-bot 1:1 对话
- **THEN** plato-bot 仍正常回复用户
- **AND** 该对话在 IM 恢复前暂不同步到内部 IM

### Requirement: 飞书云文档操作（用户身份）

#### Scenario: 以用户身份创建文档
- **WHEN** 用户要求 agent 创建一篇飞书文档
- **THEN** 文档在飞书云空间中创建，归属于用户本人（非 bot）

#### Scenario: 以用户身份编辑文档
- **GIVEN** 用户已有飞书文档
- **WHEN** 用户要求 agent 编辑该文档的内容
- **THEN** 文档内容被更新，变更归属于用户本人

#### Scenario: 未授权时提示授权
- **WHEN** 用户首次要求 agent 操作飞书云文档，但尚未完成 OAuth 授权
- **THEN** agent 提示用户进行授权，并提供授权链接或指引

#### Scenario: 以用户身份读取文档内容
- **GIVEN** 用户已有飞书文档
- **WHEN** 用户要求 agent 读取该文档的内容
- **THEN** agent 返回文档的文本内容

#### Scenario: 以用户身份创建文件夹
- **WHEN** 用户要求 agent 在飞书云空间中创建一个文件夹
- **THEN** 文件夹在飞书云空间中创建，归属于用户本人

#### Scenario: 以用户身份移动文件
- **GIVEN** 用户已有飞书文档和目标文件夹
- **WHEN** 用户要求 agent 将文档移动到目标文件夹
- **THEN** 文档出现在目标文件夹中，原位置不再显示

#### Scenario: 云文档 API 调用失败
- **WHEN** 用户要求 agent 操作飞书云文档，但飞书 API 返回错误
- **THEN** agent 向用户反馈操作失败及原因（如权限不足、文档不存在等）

## 范围与非目标

- 在范围：
  - 飞书 Bot 消息收发（1:1 私聊 + 群聊 @Bot 触发）
  - 多 Agent 路由（一个飞书 Bot 对应一个 Agent）
  - 群聊未 @ 消息的 history buffer 上下文
  - 外部 channel 会话同步到内部 IM（以飞书为首个实现）：
    - 每个外部 channel 在内部 IM 有独立会话；1:1 命名为 `agent名 · channel名`，群聊命名为 `agent名 · 群名 · channel名`
    - 用户消息、agent 回复、tool call、thinking 等完整同步到内部 IM
    - agent 回复按触发源路由：飞书触发的回复同时回写飞书和 IM；IM 触发的回复只留在 IM
    - 跨入口复用同一 kernel session，保证上下文连续
    - 群聊映射为独立 group 会话，外部成员消息显示原发送者名字
  - 以用户身份操作飞书云文档（通过 feishu-cli，创建文档、读取、编辑/追加、创建文件夹、移动文件）
- 非目标：
  - 飞书 wiki（知识库）操作
  - 飞书 bitable（多维表格）操作
  - 飞书文档评论操作（list_comments / add_comment / reply_comment）
  - 飞书 drive 高级操作（权限管理等）
  - 流式卡片（streaming cards）富交互
  - 多飞书应用账号
  - 飞书群维度的精细权限配置（allowFrom / 黑名单等）
  - 非 owner 外部成员在内部 IM 中创建真实用户账号或参与会话权限管理
  - 文件、图片、富文本等非文本消息从飞书同步到内部 IM（本期只同步文本）
  - 内部 IM 中编辑/删除消息同步回外部 channel（IM 现有功能不支持编辑删除，本期不新增）
