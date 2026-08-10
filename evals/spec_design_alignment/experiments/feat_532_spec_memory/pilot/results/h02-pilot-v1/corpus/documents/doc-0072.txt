# bugfix-512: 飞书富文本与图片消息语义丢失

## Relations

- Related: [飞书发送消息](https://open.feishu.cn/document/server-docs/im-v1/message/create?lang=zh-CN)
- Related: [飞书接收消息内容结构](https://open.feishu.cn/document/server-docs/im-v1/message-content-description/message_content)
- Related: [飞书获取消息中的资源文件](https://open.feishu.cn/document/server-docs/im-v1/message/get-2?lang=zh-CN)
- Related: [飞书上传图片](https://open.feishu.cn/document/server-docs/im-v1/image/create)

## 原始报告

用户在飞书中观察到两类直接问题：

1. Agent 回复中的 Markdown（例如 `**bold**`、列表）按原始标记显示，没有渲染为飞书富文本。
2. 用户从飞书发送富文本后，Agent 收到的是飞书 Post JSON，而不是用户在飞书中看到的文本内容。

用户要求查看当前代码、核对飞书官方文档和同类产品做法，在专用 worktree 中直接修复；实施期间先不补 spec，待真实飞书与内部 IM 视图确认满意后再补齐。

## 澄清记录

- Q1: 普通文本和带图片的消息是否都需要覆盖？
  A: 需要；每个场景都要同时查看飞书视图与内部 IM 视图。
- Q2: Post 内嵌图片在内部 IM 显示 `[图片]` 是否也代表 LLM 输入？
  A: 不是。内部 IM 展示与 LLM 实际输入必须分开：内部 IM 可在原位置显示 `[图片]`，并把图片作为 attachment 展示；LLM 应按飞书原始顺序收到 text/image parts，不接收占位符。
- Q3: 独立图片消息在内部 IM 是否显示 `[图片]` 加 attachment？
  A: 不显示占位符；内部 IM 直接展示图片 attachment，LLM 只收到 image part。
- Q4: 最终效果是否满足预期？
  A: 用户查看真实飞书与内部 IM 视图后回复 “ok”，并授权补 spec、提交 PR。

## 现象与复现

### Agent Markdown 出站

1. 在飞书中向 Agent 提问，使回复包含 Markdown 粗体、列表、链接或代码。
2. 原实现以 `msg_type=text` 发送完整 Markdown 字符串。
3. 飞书气泡显示 `**...**` 等原始标记，而不是富文本样式。

### 飞书 Post 入站

1. 用户在飞书输入带序号、样式或图片的富文本消息。
2. 飞书事件提供 `msg_type=post`，`content` 是序列化的 Post 结构。
3. 原解析器只识别 `{"text":"..."}`；无法命中时把原始 JSON 当正文交给 Agent。

### 飞书图片入站

1. 用户发送独立图片，或发送内容顺序为“前文 → 图片 → 后文”的 Post。
2. 原历史读取只接纳 text，adapter 不下载消息图片资源，也不向 shadow IM 或 Kernel 传附件。
3. 内部 IM 和模型都无法得到实际图片；如果把所有图片统一降级成文本占位符，又会破坏 LLM 的多模态输入。

## 影响范围

- 影响绑定飞书 channel 的 1:1 与群聊用户。
- Markdown 出站可读性下降；Post 入站会把 provider wire JSON 泄漏为用户内容；图片入站无法完成视觉理解。
- 内部 IM 影子会话与飞书实际消息不一致，无法作为可信的审阅视图。
- 不涉及消息删除、权限越界或持久数据损坏；问题集中在消息表示、资源下载与投递。

## 根因分析（RCA）

1. `FeishuClient.send_message()` 把 Agent Markdown 固定封装成飞书 text 消息。飞书 text 与 post 是不同消息类型，text 不承担 Markdown 富文本渲染。
2. Feishu 入站模型只有一个扁平 `text` 字段，解析器只覆盖 text payload；Post 的节点类型、样式和 text/image 顺序在进入 adapter 前已被折叠或泄漏为 JSON。
3. 图片的 `image_key` 没有通过消息资源 API 下载成 Gateway 共享 attachment，shadow sync 与 Kernel 入站因此没有可消费的二进制资源。
4. Gateway 原多图逻辑默认“正文后追加所有图片”，不能表达 Post 内部的 text/image 交错顺序，也无法分别满足内部 IM 展示与 LLM 输入两种用途。
5. Web IM 已能渲染图片 attachment，但收到的预览使用固定小尺寸裁剪，不适合作为外部消息的可读镜像。

## 修复方向

- Agent 普通回复统一用飞书 Post 的 `md` 节点发送；Markdown 图片先上传为飞书 `image_key` 再嵌入。
- 将 text、Post、standalone image 解析为有序的 text/image 内容部件；Post 文本节点投影成 Markdown，而不是暴露 JSON。
- adapter 通过 `message_id + image_key` 下载图片，生成 Gateway attachment，并保留图片在 provider 内容中的索引。
- shadow IM 使用展示投影：独立图片正文为空并直接展示 attachment；Post 在原位置显示 `[图片]`，同时展示 attachment。
- Kernel 使用模型投影：按原顺序构建 text/image parts，不把内部 IM 的 `[图片]` 占位符送给模型。
- 图片预览保持原始宽高比，并在聊天气泡内提供可辨认尺寸。
