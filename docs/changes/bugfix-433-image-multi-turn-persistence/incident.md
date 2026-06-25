# bugfix-433: 用户图片输入端到端从未送达模型（当前轮被换成占位符、跨轮更无从恢复，content/parts 双轨悬空）

## Relations

- Closes: #146
- Related: feat-330（引入 JSONL session storage 与多模态 `InputPart.image_url`）
- Related: feat-340（个人助手 IM 图片上传 → attachment → 入站图片 part）

## 原始报告

来源：GitHub issue #146（https://github.com/Mrchen116/nano-multiagent/issues/146），由本仓 PR #145 review 过程中追问暴露。用户原话（对话中）：

> 这绝对是个bug啊。下一轮图片怎么能没了。你参考下CC的源码。而且不管submit还是append_message，我理解能输入的东西应该一样的。而且content和parts是不是应该互斥的啊？

报告核心三点：
1. 多轮对话中，上一轮发的图片到下一轮模型看不到了——这是 bug。
2. `submit` 与 `append_message` 两条输入入口，能携带的内容应当一致。
3. `content`（字符串）与 `parts`（结构化数组）的双轨设计可疑，二者关系不清。

> **立项时的认知修正（design 阶段 grounding 追到底后纠正）**：issue #146 与立项初稿都假设「图片当前轮可见、只是跨轮丢失」。深入核实送达链路后发现这是**错的**——用户图片输入**当前轮就没送达模型**（在 `render_user_text` 处被换成 `[image:placeholder]`，image_url 当场丢弃）。即整条「用户 image 输入 → LLM provider」的路从未打通，比 issue 描述的更严重。本文按核实后的真相重写。

## 澄清记录

本 unit 在用户明确授权「0 交互自主完成」下推进。下列范围判断由 Agent 基于代码级根因分析 + 现状 grounding 作出，记录决策与依据：

- Q1（范围）：只修「图片跨轮可见」，还是连带打通当前轮 + 统一 content/parts 双轨？
  A(Agent 决策): grounding 暴露当前轮也不通，故范围是**打通用户图片输入端到端送达模型（当前轮）+ 跨轮持久化回放**这一整条链路；消除 content/parts 悬空双轨是其必要手段。按纯架构最优推进，不为兼容降级。

- Q2（适用产品）：coding_cli 与 personal_assistant 都要支持吗？
  A(Agent 决策): 修复落在**内核层**（消息内容表示 / 回放 / provider mapper），两个产品自然受益；但用户可观察的图片输入路径目前**只有 personal_assistant**（IM 上传 `image/*` → attachment → 入站图片 part）。`coding_cli` 经 grounding 确认**无任何图片输入路径**，列为非目标。

- Q3（图片在历史里的存储形态 + 如何送达 provider）：URL 引用还是 base64？
  A(Agent 决策): 属实现层选型，**留给 design**。现状：图片是 IM 托管 **HTTP URL 引用**（`image_url`）；而当前 Anthropic mapper 的 `_to_anthropic_image_part` 只认 `data:` base64 URL、对 HTTP URL 返回 `None`。design 须决策「HTTP URL → Anthropic url-source / 下载转 base64」，spec 不锁定。

- Q4（旧会话兼容）：修复前已存的、只含文本占位符的历史会话，要不要追溯恢复图片？
  A(Agent 决策): **不要求**。旧会话从未把图片落盘，无源可恢复；修复只对其生效后产生的消息负责。不做倒退式数据迁移。

- Q5（异常/超大图边界）：超大图、损坏图、单轮多图分别期望什么？
  A(Agent 决策): 单轮多图须全部送达且跨轮可引用（正常路径）；异常/超大图**不得让整轮对话崩溃或中断**。

- Q6（异常图片该静默降级还是明确告知用户）：用户原话——
  > 决策1：全世界都用CC，他的做法当然可接受 决策4：先按现在的。我的新问题：#### Scenario: 异常图片不中断会话 - **WHEN** 用户发送一张异常（超大 / 损坏 / 无法获取）的图片 - **THEN** 会话不崩溃，agent 至少能就该轮给出可继续的回应 这不就隐藏了错误吗，用户不知道是否图片给了llm？你这个跟CC学的？
  A(核实后修正): 用户指出原 Q5「静默降级为占位文本」隐藏了「图片是否送达 LLM」，是坏设计。**亲自核实 CC 源码**：CC 对图片处理失败是 `throw new ImageResizeError(...)`（`src/utils/imageResizer.ts:438,586`），带用户可见可操作文案（"The image exceeds the 5MB API limit and compression failed. Please use a smaller image."；`getImageTooLargeErrorMessage()` `src/services/api/errors.ts:186`），**绝不静默占位**。故修正：异常图片须**对用户明确可见地告知「这张图未送达模型 + 原因 + 可操作建议」**，不把假占位喂给模型让 agent 假装看到。会话仍不崩（给出明确错误本身即「不崩」），但「图片是否进了 LLM」对用户始终透明。决策5 与对应验收 Scenario 据此重写。

## 现象与复现

环境：personal_assistant（Node Gateway + IM），任一支持视觉的模型。

复现步骤：
1. 用户在 IM 对某 agent 发送一张图片 + 文字（例：「这张图里是什么？」）。
2. **当前轮**：agent **看不到图片**——它收到的只是文本 `[image:placeholder]`，于是答非所问或表示没看到图。
3. **下一轮**：用户只发文字追问刚才那张图。agent 同样看不到（历史里那张图也只剩占位符）。

即：用户图片输入**当前轮就不可见**，跨轮更无从恢复。整条链路是断的。

> 对照参考实现 Claude Code：用户消息 content 直接是 Anthropic API 的 blocks 数组（`[{type:text}, {type:image, source:{...}}]`），图片随消息无损落盘、resume 原样回放喂回 API（见 issue #146 内的 CC 源码定位）。本仓缺这条往返通道。

## 影响范围

- **受影响用户**：所有在个人助手里给 agent 发图、期望 agent 看懂并（在本轮或后续轮）讨论它的用户。
- **严重度**：功能性缺陷，且范围比初判更大——视觉对话（无论单轮看图还是多轮追问）实际不可用。这是视觉 agent 的核心能力之一。
- **静默失败**：agent 不会提示「我看不到图」，用户误以为它看到了图却得到错误回答。
- **数据损坏**：无。图片只是未送达 / 未持久化，已落盘数据无污染。
- **不受影响面**：纯文本对话正常（content 文本路径完好）；工具结果里的 base64 图片可正常送达 Anthropic（既有 tool-result image 路径，见 RCA）。

## 根因分析（RCA）

图片在「用户输入 → 模型」与「持久化 → 回放」两条链路上都断了，三处断点（均已逐处核实源码）：

### 断点 1：用户输入渲染时丢弃图片（当前轮断）

`render_user_text`（`src/agent/core/agent/state.py:97-103`）把 `InputPart(type="image")` 一律渲染成字面量 `"[image:placeholder]"`，**image_url 当场丢弃**。`_execute_loop` 调用 `build_chat_messages(history_messages=..., user_text=state.user_text)`（`src/agent/core/agent/loop.py:230-234`）——**只传 `user_text`（已是占位符），根本不传 `input_parts`**。`input_parts` 在 runtime 里仅用于 hook 的 `input.images` 事件（`_extract_input_images`，runtime.py:2044），不进 provider 请求。

→ 当前轮用户图片从未到达 provider。

### 断点 2：持久化只存渲染后的文本（跨轮断）

user turn 落盘走 `_message_to_entry`（`src/agent/core/agent/runtime.py:2121-2131`），只写 `content=msg.content`；而 `user_msg = Message(..., content=user_text)`（runtime.py:518-522），`user_text` 已是占位符。`Message` 类型（`src/agent/core/types.py`）仅 `content: str`，无图片通道。回放 `build_chat_messages`（`src/agent/core/agent/prompting.py:76-88`）`content=message.content` 纯字符串，不还原图片。

→ 即便断点 1 修好让当前轮可见，不修这里，图片仍只是单轮可见、跨轮丢失。

### 断点 3：provider mapper 的 user 分支不发图片，且 HTTP URL 发不出

`LLMMessage.content` 类型签名已是 `str | list[dict]`（`src/agent/core/llm/interfaces.py`，已支持结构化），但：
- Anthropic mapper user 分支（`src/agent/platform/llm/providers/anthropic/mapper.py:147-151`）硬编码 `content=[{"type":"text","text":message.content}]`，不处理 list 形式的图片块。
- `_to_anthropic_image_part`（同文件 :231）对**非 `data:` 前缀**的 image_url 直接返回 `None`——IM 的 HTTP URL 即便走到也发不出，只支持 base64 data URL。
- OpenAI-compat mapper user 分支（`src/agent/platform/llm/providers/openai_compat/mapper.py:104-105`）原样透传 content，但同样从未收到图片块。

→ 这是为什么图片送达必须连 provider mapper 一起修，且要决策 HTTP URL 怎么送（url-source 还是下载转 base64）。

### content / parts 双轨缺陷（用户第 3 点）

`append_message` / `append_turn_message`（`src/agent/core/session/manager.py:178-193`）同时接受并落盘 `content`（str）与 `parts`（数组），但回放只认 content：`jsonl_store._to_message`（`src/agent/core/session/jsonl_store.py:754-765`）只读 `entry["content"]` 丢弃 parts。`parts` 是**写了不读的悬空字段**——这正是「content 和 parts 该不该互斥」的根源：当前双轨且不一致。

### 为什么这种错能进来

- **非回归**：多模态 `InputPart.image_url` 自 feat-330 即存在，但内核契约层 `docs/specs/kernel/spec.md` **从未定义图片送达/持久化行为**（grep「image/图片/multimodal」为空）。初始实现只把图片解析进了 `InputPart`，「送达 provider」与「跨轮持久化」从设计上就没闭合，而非被改坏。
- **测试盲区**：现有测试只覆盖「`InputPart` 解析」「IM attachment 传到 inbound」「tool-result image 送 Anthropic」，**没有任何测试覆盖「用户 image 输入送达 provider」或「图片持久化/回放」**。占位符 `[image:placeholder]` 让纯文本断言全绿，掩盖了整条断链。
- **抽象债**：`Message.content: str` 与 `render_user_text`（把多模态压成字符串）这两处「消息内容即纯文本」假设，与「输入可为多模态 parts」的输入层假设不一致，图片在交界处被有损降级。

### 原始设计意图与必须保住的不变量

图片输入能力的原意图（feat-330 + feat-340）：让 agent 能接收并理解用户发来的图片。**修复必须保住的不变量**：
1. 纯文本会话的持久化/回放行为逐字节不变（不得因引入结构化内容扰动既有文本 session 的重建结果）。
2. 既有的 tool-result image 送达路径（base64 → Anthropic）不被破坏。
3. 历史 DAG/parentUuid 链、tool_use↔tool_result 配对、reasoning_content 往返等既有持久化契约不破。

> 反面警示：最省事的「修法」是把图片在入口直接丢弃以消除不一致——那是把功能阉割成残废，违背原意图，禁止。

## 修复方向（高层，行级实现留给 design + milestone）

1. **打通用户图片输入送达 provider（当前轮）**：让用户输入的图片块随当前 user 消息构造成结构化 content（`LLMMessage.content: list[dict]`），喂给 provider mapper。
2. **provider mapper 支持 user 图片块 + HTTP URL 送达**：Anthropic / OpenAI-compat 的 user 分支能输出 image block；解决 IM HTTP URL 的送达（url-source 或下载转 base64，design 决策）。
3. **图片随历史无损往返（跨轮）**：图片随 user turn 持久化、重建历史时还原为图片块，使后续轮模型仍可见。
4. **统一消息内容表示**：消除 content/parts 悬空双轨——要么 parts 成权威且回放消费它，要么 content 直接承载结构化 blocks。二选一，不得再「写了不读」。参照 Claude Code 单一 content-blocks 模型。
5. **保住不变量**：纯文本 session 零扰动；tool-result image 路径不破；DAG/tool-pair/reasoning 契约不破。
6. **补端到端往返测试**：覆盖「发图 → 送达 provider → 落盘 → 重建 → 下一轮仍含图」，堵住占位符掩盖的盲区。

## 目标状态 / 验收标准

> 用户可观察的验收。reviewer 走 personal_assistant 真栈旅程逐条验。

### Requirement: 用户发的图片当前轮即可被 agent 看到

#### Scenario: 单轮发图即问
- **WHEN** 用户在一条消息里同时发一张图片和关于该图的问题
- **THEN** agent 当轮即能基于图片内容作答（而不是表示看不到图或答非所问）

#### Scenario: 单轮发多张图
- **WHEN** 用户在一条消息里发多张图片并提问
- **THEN** agent 能看到全部图片并据此作答

### Requirement: 图片在多轮对话中跨轮保留

#### Scenario: 上一轮发图，下一轮仍可被追问
- **GIVEN** 用户上一轮发过一张图片并得到了基于该图的回复
- **WHEN** 用户在同一会话下一轮**只发文字**追问这张图的细节（不再重发图）
- **THEN** agent 能基于上一轮那张图作答

### Requirement: 纯文本会话行为不受影响

#### Scenario: 不含图片的多轮对话
- **WHEN** 用户进行一段完全不含图片的多轮文字对话
- **THEN** 回复与持久化/重建行为与修复前一致，无可观察差异

### Requirement: 异常图片明确告知用户，不静默隐藏

#### Scenario: 发送异常或超大图片
- **WHEN** 用户发送一张异常（超大/损坏/无法获取）图片
- **THEN** 用户收到明确提示，说明这张图片**未能送达模型**及原因（如太大/无法加载）和可操作建议（如换小图重发）
- **AND** 对话不崩溃、不中断
- **AND** agent 不会对着这张未送达的图片编造内容（即不把伪造的占位图当成用户真发了图来作答）

## 范围与非目标

- 在范围：
  - 打通用户图片输入端到端送达 LLM provider（当前轮可见）。
  - provider mapper（Anthropic + OpenAI-compat）的 user 分支支持图片块；解决 IM HTTP URL 送达。
  - 图片随会话历史无损持久化与回放（跨轮可见）。
  - 消除 content/parts 悬空双轨。
  - personal_assistant 端到端验证 + 内核往返测试覆盖。
- 非目标：
  - coding_cli 的图片输入（当前无此路径，不在本 unit 新建）。
  - 旧（修复前）会话的历史图片追溯恢复（本就未落盘，无源可恢复）。
  - 图片压缩/缩放/超大裁剪的具体策略选型（留 design 权衡，spec 只要求「不崩」）。
  - 视频/音频/文档等其它多模态类型（本 unit 只闭合 image）。
