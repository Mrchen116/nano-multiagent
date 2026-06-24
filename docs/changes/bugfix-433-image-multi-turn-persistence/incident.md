# bugfix-433: 内核跨轮丢失图片输入（历史只存文本占位符，content/parts 双轨且 parts 回放不被消费）

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

## 澄清记录

本 unit 在用户明确授权「0 交互自主完成」下推进。下列范围判断由 Agent 基于 issue #146 的代码级根因分析 + 现状 grounding 作出，记录决策与依据：

- Q1（范围）：只修「图片跨轮可见」，还是连带统一 content/parts 双轨？
  A(Agent 决策): 核心交付是**用户可观察的「图片跨轮无损保留」**；消除 content/parts 悬空双轨是达成它的必要手段（不统一就修不干净），一并纳入。依据：grounding 确认 `parts` 当前是写盘但回放不读的悬空字段，图片丢失正源于此。按纯架构最优推进，不为兼容降级。

- Q2（适用产品）：coding_cli 与 personal_assistant 都要支持图片跨轮吗？
  A(Agent 决策): 修复落在**内核层**（消息持久化/回放），两个产品自然受益；但用户可观察的图片输入路径目前**只有 personal_assistant**（IM 上传 `image/*` → attachment → 入站图片 part）。`coding_cli` 经 grounding 确认**无任何图片输入路径**，列为非目标。

- Q3（图片在历史里的存储形态）：base64 inline 进 JSONL（如 Claude Code）还是存引用？
  A(Agent 决策): 属实现层选型，**留给 design**。现状 grounding 提示本仓图片是 IM 托管 **URL 引用**（`image_url`）而非 base64，design 据此权衡，spec 不锁定。

- Q4（旧会话兼容）：修复前已存的、只含文本占位符的历史会话，要不要追溯恢复图片？
  A(Agent 决策): **不要求**。旧会话从未把图片落盘，无源可恢复；修复只对其生效后产生的消息负责。不做倒退式数据迁移。

- Q5（异常/超大图边界）：超大图、损坏图、单轮多图分别期望什么？
  A(Agent 决策): 单轮多图须全部跨轮可引用（正常路径）；异常/超大图**不得让整轮对话崩溃或中断**（优雅降级，用户可观察「对话仍能继续」）。具体降级手段（压缩/跳过/报错文案）留 design。

## 现象与复现

环境：personal_assistant（Node Gateway + IM），任一支持视觉的模型。

复现步骤：
1. 用户在 IM 对某 agent 发送一张图片 + 文字（例：「这张图里是什么？」）。
2. agent **当前轮能正确看到图片并回答**（如描述图片内容）。
3. 同一会话**下一轮**，用户只发文字追问刚才那张图（例：「图里左下角那个是什么颜色？」）。
4. **期望**：agent 仍能基于上一轮的图片回答。
   **实际**：agent 看不到原图，历史里该图只剩文本占位符 `[image:placeholder]`，agent 无法回答或答非所问。

即：图片输入是「单轮可见、跨轮丢失」。

## 影响范围

- **受影响用户**：所有在个人助手里发图、并期望 agent 在后续轮次记得这张图的用户。
- **严重度**：功能性缺陷。多轮视觉对话（看图追问、基于图持续讨论）实际不可用——这是视觉 agent 的核心场景之一。
- **数据损坏**：无。图片不进历史只是「未持久化」，已落盘数据无污染；但用户**误以为** agent 记得图，体验上是静默失败（agent 不会提示「我看不到上一张图了」）。
- **波及面**：纯文本多轮对话不受影响（content 路径正常）。

## 根因分析（RCA）

### 直接原因：图片只走「当前轮内存路径」，从不进入「持久化 + 回放」路径

图片有两条命运不同的链路（均已逐处核实源码）：

**A. 当前轮输入（工作正常）**
`Kernel.submit(parts=[{"type":"image","image_url":...}])`
→ `parse_input_parts`（`src/agent/core/agent/state.py:62-76`，解析出 `InputPart(type="image", image_url=...)`）
→ `_execute_loop(input_parts=effective_input_parts)`（`src/agent/core/agent/runtime.py:564`，内存对象直达 provider）。
当前轮图片确实进模型。

**B. 持久化 + 跨轮回放（丢图）**
1. **持久化只存渲染后的文本**：user turn 落盘走 `_message_to_entry`（`src/agent/core/agent/runtime.py:2121-2131`），只写 `content=msg.content`；而 `user_msg = Message(..., content=user_text)`（runtime.py:518-522），`user_text` 由 `render_user_text` 渲染，图片被替换成占位符 `[image:placeholder]`（`src/agent/core/agent/state.py:101-102`）。**`image_url` 根本不落盘。**
2. **`Message` 类型没有图片通道**：`src/agent/core/types.py` 的 `Message` 仅 `content: str`，无 `parts`/`image` 字段。
3. **回放只读 content 纯文本**：`build_chat_messages`（`src/agent/core/agent/prompting.py:76-88`）把历史 `Message` 转 `LLMMessage` 时 `content=message.content`，不还原任何 image block。

### content / parts 双轨缺陷（用户第 3 点）

`append_message` / `append_turn_message`（`src/agent/core/session/manager.py:178-193`）同时接受 `content`（str）与 `parts`（数组）并都落盘，但回放侧只认 content：
- `jsonl_store._to_message`（`src/agent/core/session/jsonl_store.py:754-765`）构造 `Message` 只读 `entry["content"]`，丢弃 `parts`；
- 另一条 loader `_build_turn_metadata`（`src/agent/core/session/manager.py:481-482`）虽把 `parts` 放进 `meta["parts"]`，但 `build_chat_messages` 不消费它。

结论：`parts` 是**写了不读的悬空字段**。这正是「content 和 parts 该不该互斥」疑问的根源——当前是双轨且不一致，图片丢失是这套双轨的直接后果。

### 为什么这种错能进来（机制层）

- **非回归**：这不是「曾经能用后来坏了」。多模态 `InputPart.image_url` 自 feat-330（JSONL storage）即存在，但**内核契约层 `docs/specs/kernel/spec.md` 从未定义图片的持久化/回放行为**（grep「image/图片/multimodal」为空）。即初始实现只闭合了「当前轮图片进模型」，「跨轮持久化」从设计上就是缺口，而非被改坏。
- **测试盲区**：现有单测覆盖「当前轮图片进 provider」，没有覆盖「发图 → 落盘 → 重建历史 → 下一轮仍含图」的端到端往返。占位符 `[image:placeholder]` 让纯文本断言全绿，掩盖了图片丢失。
- **抽象债**：`Message.content: str` 这一「消息内容即纯字符串」的假设贯穿持久化与回放两层，与「输入可为多模态 parts」的输入层假设不一致。两套假设在 `render_user_text`（多模态压成字符串）处对接，图片在此被有损降级。

### 原始设计意图与必须保住的不变量

图片输入能力的原意图（feat-330 + feat-340）：让 agent 能接收并理解用户发来的图片。**修复必须保住的不变量**：
1. 当前轮图片可见的现有行为不得回退。
2. 纯文本会话的持久化/回放行为逐字节不变（不得因引入结构化内容而扰动既有文本 session 的重建结果）。
3. 历史的 DAG/parentUuid 链、tool_use↔tool_result 配对、reasoning_content 往返等既有持久化契约不被破坏。

> 反面警示：最省事的「修法」是把图片在入口就丢弃以消除不一致——那是把功能阉割成残废，违背原意图，禁止。

## 修复方向（高层，行级实现留给 design + milestone）

1. **统一消息内容表示**：让历史持久化与回放支持结构化内容（含图片），消除 content/parts 悬空双轨——要么 parts 成为权威且回放消费它，要么 content 直接承载结构化 blocks。二选一，不得再「写了不读」。参照 Claude Code 的单一 content-blocks 模型（`MessageContent = string | ContentBlockParam[] | ContentBlock[]`），图片随历史无损往返。
2. **图片无损往返**：用户发的图（image_url 引用）随 user turn 落盘，重建历史时还原为图片块喂回 provider，使下一轮模型仍能看到。
3. **两条输入入口一致**：`submit` 与 `append_message` 携带图片的能力对齐，且都被持久化保留。
4. **保住不变量**：纯文本 session 持久化/回放零扰动；当前轮图片可见不回退；DAG/tool-pair/reasoning 等既有契约不破。
5. **补端到端往返测试**：覆盖「发图 → 落盘 → 重建 → 下一轮仍含图」，堵住占位符掩盖的盲区。

## 目标状态 / 验收标准

> 用户可观察的验收。reviewer 走 personal_assistant 真栈旅程逐条验。

### Requirement: 图片在多轮对话中跨轮保留

#### Scenario: 上一轮发图，下一轮仍可被追问
- **GIVEN** 用户在某 agent 的会话里发过一张图片并得到了基于该图的回复
- **WHEN** 用户在同一会话的下一轮**只发文字**，追问这张图的细节（不再重发图）
- **THEN** agent 能基于上一轮那张图的内容作答，而不是表示看不到图或答非所问

#### Scenario: 单轮多图，后续轮均可引用
- **GIVEN** 用户在一轮里发了多张图片并得到回复
- **WHEN** 用户在后续轮次追问其中任意一张
- **THEN** agent 能区分并基于对应图片作答

### Requirement: 当前轮图片可见不回退

#### Scenario: 单轮发图即问
- **WHEN** 用户在一条消息里同时发图片和问题
- **THEN** agent 当轮即能看到该图并正确作答（保持修复前已有的行为）

### Requirement: 纯文本会话行为不受影响

#### Scenario: 不含图片的多轮对话
- **WHEN** 用户进行一段完全不含图片的多轮文字对话
- **THEN** 对话的回复与持久化/重建行为与修复前一致，无可观察差异

### Requirement: 异常图片不致中断对话

#### Scenario: 发送异常或超大图片
- **WHEN** 用户发送一张异常（超大/损坏）图片
- **THEN** 对话不崩溃、不中断，agent 至少能就该轮给出可继续的回应（优雅降级，会话仍可继续）

## 范围与非目标

- 在范围：
  - 内核消息内容表示统一，消除 content/parts 悬空双轨。
  - 图片（image_url 引用）随会话历史无损持久化与回放。
  - personal_assistant 端到端：发图后跨轮仍可被 agent 引用。
  - 端到端往返测试覆盖。
- 非目标：
  - coding_cli 的图片输入（当前无此路径，不在本 unit 新建）。
  - 旧（修复前）会话的历史图片追溯恢复（本就未落盘，无源可恢复）。
  - 图片压缩/缩放/超大裁剪的具体策略选型（留 design 权衡，spec 只要求「不崩」）。
  - 视频/音频/文档等其它多模态类型（本 unit 只闭合 image）。
