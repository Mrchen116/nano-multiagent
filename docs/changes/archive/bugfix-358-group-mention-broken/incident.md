# bugfix-358: 群聊 @-mention 处理不对

## Relations

- Refs: #21

## 原始报告

> http://127.0.0.1:8011/chat/358879bdd812442db936145521c7fc15 你看下聊天记录，agent@的处理有问题

证据来自该会话的实际消息（节选）：

- 用户：`@架构`
- agent `Arch`（display "架构"）回复：`@f29e2b531a3c415bb3087b3892f07551 要不我们从认识论聊起？...`
- 用户希望两个 agent 互相 @ 对方继续聊，但 Arch 输出的 `@f29e2b53...` 既不被前端渲染成 mention chip（呈现为一串 UUID），也没有触发被 @ 的那个 agent（`ArchA`，display "Q"）回复。

同会话上下文里的另一条同源现象（更早的对话沉淀，本 unit 一并视为复现证据）：

- 用户在另一个群里 `@Q 你说呢`，`Q` 是 `ArchA` 的 display_name；IM 解析后却把 mention 落成字面 `"Q"`，匹配到一条挂在 offline node 上的孤儿 `agent_id='Q'`，导致 `ArchA` 未被触发。该孤儿已临时清理，但 resolver 仍然依赖 display_name 做路由这一点没改。

## 澄清记录

- Q1: 这个 bug 的修复方向——是给 IM mention parser 加 UUID 容错（如果 agent 输出 synth user UUID 也能反查回 agent_id），还是从 ID 设计层面重新分清"路由用的 ID"和"界面呈现的 ID"？
  A(原话): 容错没必要。思考清楚给模型去@的应该是什么 ID？以及在界面上应该呈现什么 ID，这个应该是相对明确的。这两者是可以不一样的，我们只需要做一个转换就可以了。关键就是去思考合理性。
  Agent 解读: 用户明确否决"加 UUID 容错"那种补丁式修法；要求从设计层把"agent 用的 wire ID"和"界面呈现的 display ID"两层分开，由 IM 做一次单向转换。

- Q2: 那合理性是不是这样——wire 层（agent 输出 / IM 路由 / 落库）用 `agent_id`（稳定、唯一、不可变的 PK）；display 层（前端 chip / picker）用 `display_name`（可读、可改、不强唯一）；IM 在 agent→前端 和 前端→agent 两个方向上各做一次转换？
  A(原话): 也避免了display name重名的问题对吧
  Agent 解读: 用户认可方向，并主动指出连带效益——按这套分层后，display_name 重名（fuck/Q 那种历史踩坑）不再是路由问题，可以放弃"display_name 必须唯一"的约束。

- Q3: 这事立成什么单元？要不要先把 system prompt 里的 group participants 块格式定下来？
  A(原话): 开始当作bugfix。前面几轮交互作为问答。你继续和我问答。你的推荐格式我不太认同。不过可以在design阶段继续讨论
  Agent 解读: 用户要立 bugfix 单元；participants 块的具体格式属于实现层，推迟到 design 阶段；先把前面的 Q&A 沉淀进 spec。

- Q4: 修复覆盖面——(a) 只修 agent→agent 这一个症状；(b) 整条 mention 链路四个方向（agent→agent / agent→user / user→agent / user→user）都改成"wire=ID、display=display_name、IM 转换"，删掉 display_name 兜底查表？
  A(原话): b
  Agent 解读: 整条链路一次性改到位；display_name 兜底查表那一支删除；user→agent 的 picker 也要发 wire ID 而非 display_name；mention parser 只认 wire ID。

- Q5: 历史消息里已经落库的 `@<UUID>` token（如本会话里 Arch 那条 `@f29e2b53...`）是否回填成 `@<agent_id>`？
  A(原话): 现在是开发态，不计过往。
  Agent 解读: 不做任何数据迁移；旧消息保持原样；本 bugfix 的覆盖面只对修复点之后产生的新消息负责。

- Q6: 是否主动放开 "display_name 必须唯一" 的约束，让用户可以创建/改名出两个同名 agent？
  A(原话): 对
  Agent 解读: display_name 唯一性约束完全放开（DB 不强制、UI 创建/改名不拦截）。前端 picker 在出现重名时必须让用户能区分并独立选中（具体呈现交给 design），写进验收标准。

- Q7: 跟 issue #21 的关系——Close 还是 Refs？
  A(原话): 对
  Agent 解读: 取推荐——Relations 写 Refs: #21（消除了 #21 评论中的 resolver 子缺陷），不 Close；#21 主诉（IM↔Gateway agent 表对账）留给单独 unit。

- Q8: lite 还是升 full？跨 5+ 模块、4 个 mention 方向，且 Q3 明确说 participants 格式留给 design 阶段对齐。
  A(原话): full
  Agent 解读: 升 bugfix full；首文档为 incident.md，进入 design 阶段对齐 participants payload schema、prompt 中 participants 块格式、mention token 文本承载格式、picker 重名消歧 UX；reviewer 阶段补 regression.md。

## 现象与复现

### 期望 vs 实际

期望：在群聊里，任何方向的 mention（agent↔agent、user↔agent、user↔user）发出后——

- 前端把消息里的 mention 渲染成可点击 chip，显示目标对象的当前 display_name；
- 被 @ 的目标对象（agent 或 user）正确收到通知/触发响应；
- display_name 是否唯一、是否被改过、是否撞到孤儿 agent，都不影响路由结果。

实际：上述三条全部不成立。详见下文复现步骤。

### 复现 A：agent → agent 互相 @ 失败（主复现）

环境：本地 demo-node + IM 服务 + Gateway，conversation `358879bdd812442db936145521c7fc15`。

步骤：

1. 创建群聊，参与方：user `Test User` + agent `Arch`（display "架构"）+ agent `ArchA`（display "Q"）。
2. user 发送 `@架构` → Arch 收到并回复（OK，因为 "架构" 在本群 display_name 唯一）。
3. user 发送 `你们相互@对方聊` → 两个 agent 均收到（无 @，按 MENTION 策略 buffer，不立即回复，OK）。
4. user 再次发送 `@架构` → Arch 触发，回复内容里包含对 ArchA 的 @：`@f29e2b531a3c415bb3087b3892f07551 要不我们从认识论聊起？...`
5. 观察：
   - 前端：Arch 这条消息里 `@f29e2b53...` 被当作字面文本展示，不是 mention chip。
   - 路由：IM mention parser 解析这条消息时 `mentioned_agent_ids` 不包含 `ArchA`；ArchA 被 Gateway MENTION 策略静默 buffer，不响应。
   - 用户看到的最终现象：Arch 说了"@<一串 UUID>"，然后没有下文。

### 复现 B：user @ display_name 撞库失败（同源历史现象）

步骤：

1. IM 表里有孤儿 `agent_id='Q'` 挂在 offline 节点（本会话已临时清理，但当时存在）。
2. user 在另一个群里发送 `@Q 你说呢`，本意 @ 当前群里的 `ArchA`（display "Q"）。
3. IM mention parser 在 `_resolve_mention_to_agent_ids` 里先按 `agent_id='Q'` 精确匹配 → 命中孤儿；display_name 兜底查表那一支因为前一支已命中而被跳过。
4. 解析结果 `mentioned_agent_ids=['Q']`，下发给 Gateway 的 ArchA relay 里 ArchA 不在 mentioned 列表，被静默 buffer。
5. 用户看到的最终现象：@ 了 Q，没有任何回复，没有任何错误反馈。

### 共同特征

两条复现路径的可观察终态都是"用户发出 mention 后没有得到应有的响应或者得到无法解读的字符串"，**且不会触发任何用户可见的错误反馈**——这是本 bug 最坏的一面：静默失败。

## 影响范围

- **受影响产品**：IM 群聊功能（个人助手产品的核心交互之一）；@-mention 是多 agent 协作的基础。
- **受影响用户**：所有在群聊里使用 @ mention 的用户和 agent。一对一对话不受影响。
- **严重程度**：可观察故障。agent → agent 方向几乎"完全坏了"（输出 UUID 字面、对方不响应）；user → agent 方向在 display_name 撞库时"静默失败"。两条都不报错，用户无法 self-debug。
- **数据损坏**：无。落库的消息文本里的 UUID / display_name token 都是合法字符串，DB 完整性未受破坏。仅"视觉与路由"两个面失败。
- **历史数据处理**：开发态，不回填、不迁移已落库的旧消息（Q5 约定）。

## 根因分析（RCA）

### 直接根因（"哪行错了"）

`src/IM/application/relay_service.py:_resolve_all_participants:500` 给 kernel / agent 的 participants 列表里，agent 项的 `id` 字段填的是 synth user UUID（合成出来的 IM 内部 user_id），不是 agent_id：

```python
result.append({"id": user_id, "display_name": display_name, "type": "agent"})
```

Agent 按 system prompt 指引使用"稳定 ID" @ 别人时，能取到的只有这串 UUID，于是产生 `@<UUID>`。

### 同源根因

`src/IM/application/relay_service.py:_resolve_mention_to_agent_ids:300` 既支持 agent_id 精确匹配（第一支），也回退到 display_name 兜底查表（第二支）。display_name 没有唯一约束，撞到其他节点的孤儿 agent 时，第一支会先命中孤儿、第二支不再运行，路由结果偏离用户意图。

### 设计层根因（"为什么这种错能进来"）

把"路由用的 wire ID"和"界面呈现的 display ID"两层混在了同一个字段里：

- 同一个 `id` 字段既暴露给 agent 当 @ token，又作为前端展示的查表起点。两层互相牵制——
  - 路由侧不得不容忍 display_name 兜底（防 agent 写了 display_name），就要吃 display_name 撞库的歧义；
  - 展示侧不得不接受 UUID 当字面文本（因为消息里有），就出现 chip 渲染失败。
- agent system prompt 中的措辞"prefer stable IDs (user_id / agent_id) when mentioning participants" 是层级混淆的另一面证据——把 user_id 和 agent_id 当作可互换的"稳定 ID"，没区分谁是 wire、谁是内部实现。

### 测试 / Review 漏过这个层级混淆的原因

日常单 agent 群聊里 display_name 通常唯一、agent 也通常不主动 @ 别人；表面 bug 看不出来。多 agent + display_name 撞库 + agent 主动互相 @ 这三种条件同时成立，才一次性把所有失败模式触发。集成测试套件没有覆盖"agent 在自己回复里 @ 另一个 agent"这条路径，也没有 display_name 重名场景。

## 用户场景（修好之后的目标状态）

群聊里有多个 agent，比如"架构"和"Q"。

- **user → agent**：用户敲 `@`，前端弹出 picker，挑"架构"，发送的消息里这一段被渲染成可点击 chip，显示"@架构"。Arch 收到并回复。
- **agent → agent**：Arch 在自己回复里想点名 Q——它输出的 wire token 是稳定 ID，IM 在投递到前端前把这段翻译成 mention chip，前端展示"@Q"。Q 收到通知，接着说话。
- **改名**：用户后来把"Q"改名叫"测试员"。再翻聊天记录或继续发新消息，所有指向这个 agent 的 chip 都自动按"测试员"渲染。
- **重名**：用户起了两个都叫"助手"的 agent，picker 在该群里列出二者时让用户能区分并选中其中一个；选中哪一个就 @ 哪一个，互不串。
- **撞孤儿**：IM 表里残留一个跟当前群某 agent display_name 同名的孤儿 agent（来自 offline 节点）。用户在群里 @ 那个名字，路由仍然落到当前群里的真实 agent，不被孤儿截胡。
- **agent → user**：agent 在回复里 @ 群里的 user（当前架构下群内仅有一个 user），前端渲染成 display_name chip，被 @ 的用户收到通知。

整个过程中用户看到的每个 mention 都是清晰可读的当前 display_name，可点击；底层路由不依赖名字字面。

## 验收标准

1. 群聊中 user 通过 picker 选中一个 agent 发送 mention 后，该 agent 收到该消息并触发响应（不被 MENTION 策略静默 buffer）；前端把该 mention 渲染成 chip，显示目标 agent 的当前 display_name。
2. 群聊中一个 agent 在自己回复里 @ 另一个 agent，被 @ 的 agent 收到并响应；该 mention 在前端渲染为 chip，显示当前 display_name，**不出现 UUID / agent_id 等内部字符**作为字面文本。
3. user 把某 agent 的 display_name 改名后，本次修复生效之后产生的新消息中针对该 agent 的 chip 自动按新 display_name 渲染。
4. 系统允许多个 agent 使用相同 display_name（创建或改名时不被拒绝）；群里出现重名时，picker 让用户能区分并独立选中其中任一；被选中的 agent 被 @ 后，**只有它**响应，同名其他 agent 不被打扰。
5. 当 IM 中存在残留 / 离线节点上的孤儿 agent（其 display_name 与当前群中某真实 agent 相同），user 或 agent 在群里发出针对该名字的 mention 后，目标 agent 仍正确被触发，孤儿不截胡。
6. agent → user mention（agent 在群里 @ 当前 user），前端渲染成对应 display_name chip，被 @ 的用户收到通知。

## 范围与非目标

### In scope

- IM relay payload `participants[]` schema 改造：agent 项暴露 `agent_id` 作为 wire ID，user 项暴露 `user_id` 作为 wire ID；不再以 synth user UUID 混充 agent 的 ID。
- IM mention parser 改造：只认 wire ID 精确匹配，**删除** display_name 兜底查表分支。
- Agent system prompt 模板：group participants 块重设计，明确 wire ID 与 display_name 的分工、@ 规则；删除"prefer stable IDs (user_id / agent_id)"这类层级模糊措辞。
- 前端 picker：选中后插入的 wire token 改为 `@<wire_id>`；列表项以 display_name 为主；同群出现重名时呈现消歧。
- 前端 mention chip 渲染：把消息文本里的 `@<wire_id>` 翻译成 chip，显示当前 display_name。
- DB / API：放开 display_name 唯一性约束（如有 UNIQUE 索引则删除；IM 创建 / 改名 API 不再拦截重名）。
- 覆盖 user→agent、agent→agent、agent→user **三个方向**的 mention（user→user 不在本 unit 范围，见 Non-goal）。

### Non-goal

- **不回填**历史消息中已落库的 `@<UUID>` 或 `@<display_name>` token（Q5：开发态、不计过往）。
- **不做** IM↔Gateway agent 表对账机制（issue #21 主诉）；该缺陷留给单独 unit。
- **不动** `users.username` 字段语义；不引入新的 ID 类型；沿用已有的 `agent_id` 和 `user_id`。
- **不调整** group_reply_policy（如 MENTION）的语义。
- **不处理**其他与 mention 相邻但不在本主问题路径上的功能（如 @everyone、silent mention、mention 通知偏好等，如果存在）。
- **不支持** user → user mention（群内多 user 是未来能力，当前架构每个群仅一个 user，本 unit 不为该未来场景预设规则）。

## 修复方向（高层）

按 Q1–Q2 定下的"两层分开 + IM 单向转换"原则：

- **wire 层**（agent 输出 / IM 路由 / 落库）：`agent_id`（agent）/ `user_id`（user）。稳定、不可改、PK 唯一。
- **display 层**（前端 chip / picker 显示）：`display_name`。可读、可改、可重名。
- **IM 是转换层**：
  - agent → 前端方向：消息文本里的 `@<wire_id>` 被前端按当前 display_name 渲染成 chip。
  - 前端 → agent 方向：picker 选中目标后插入 `@<wire_id>`；mention parser 只认 wire ID。

详细 schema、token 在文本中的承载格式（结构化 markdown 还是普通 `@<id>` 加上下文表）、prompt 中 participants 块的具体形式、picker 重名消歧的视觉呈现，全部在 `design.md` 中讨论（Q3、Q8 已经把这些明确推迟到 design）。
