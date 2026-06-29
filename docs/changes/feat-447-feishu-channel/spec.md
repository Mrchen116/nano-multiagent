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

## 用户场景

用户在飞书上通过三个飞书 Bot（plato / luban / hume）分别与对应的 Agent 交互，体验与内部 IM 页面一致。

### 1:1 私聊

用户打开某个 Agent 对应的飞书 Bot 对话窗口，直接发消息。Bot 永远响应，无需 @。session 按用户维度隔离，每个用户跟每个 Bot 有独立的对话上下文。

### 群聊

用户在飞书群里 @Bot 发消息，Bot 响应。未 @ 的消息不会触发回复，但会被暂存为上下文——当用户下次 @Bot 时，agent 能看到之前未 @ 的群聊消息作为背景信息。群聊 session 默认按群维度隔离（整个群共用一个 session），可配置为按群+用户隔离。

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

### Requirement: 飞书对话同步到内部 IM

#### Scenario: 飞书消息出现在内部 IM
- **WHEN** 用户在飞书跟 Bot 对话，Bot 回复
- **THEN** 该对话（用户消息 + Bot 回复）同步出现在内部 IM 的对应 Agent 会话中

#### Scenario: 飞书群聊消息出现在内部 IM
- **WHEN** 用户在飞书群 @Bot 对话，Bot 回复
- **THEN** 该对话同步出现在内部 IM 的对应 Agent 会话中

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
  - 飞书对话同步到内部 IM（消息和回复 mirror 到 IM 服务，内部 IM web 可见）
  - 以用户身份操作飞书云文档（通过 feishu-cli，创建文档、读取、编辑/追加、创建文件夹、移动文件）
- 非目标：
  - 飞书 wiki（知识库）操作
  - 飞书 bitable（多维表格）操作
  - 飞书文档评论操作（list_comments / add_comment / reply_comment）
  - 飞书 drive 高级操作（权限管理等）
  - 流式卡片（streaming cards）富交互
  - 多飞书应用账号
  - 飞书群维度的精细权限配置（allowFrom / 黑名单等）
