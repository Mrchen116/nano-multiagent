# gateway External Channels Specification (delta for bugfix-512)

## ADDED Requirements

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
