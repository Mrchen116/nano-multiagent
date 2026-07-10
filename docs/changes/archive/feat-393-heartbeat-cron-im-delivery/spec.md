# feat-393: heartbeat/cron 结果真正回发到 IM 会话

## Relations

- Closes: #70
- Related: M138（主 Agent 与 Heartbeat 汇报链路产品化，commit 79eda8b2，立意但从未生效）
- Related: refactor-387（删除畸形 node.report heartbeat 桥 + 双侧健壮性加固，把"真正做对回发"单列出来 → 本 unit）

## 原始需求

> 用户在对话中的发起：
> https://github.com/Mrchen116/nano-multiagent/issues/70 这个问题，思考怎么设计，估计之前设计漏了，参考openclaw和hermes agent 代码

issue #70 原文（verbatim）：

> ## 背景
>
> M138（`feat(M138): productize main-agent heartbeat IM reporting`，commit 79eda8b2）立意是：
>
> > 让用户能在真实产品入口识别主 Agent，并看到 **Heartbeat 结果通过 IM 回流**，形成用户可见的产品闭环。
> > （R2 验收：Heartbeat 触发后…能形成 IM 可消费的 report 事件；若当前 agent 是主 Agent，则结果**直接面向用户会话**。）
>
> 但该实现从一开始就是坏的，**在真实 IM 上从未生效过**。
>
> ## 根因
>
> heartbeat 完成报告复用了 `node.report` 通道，但 `_build_heartbeat_product_reports()` 产出的 payload：
>
> 1. **缺 `node_id`** → IM `_handle_report` 第一行 `_require_text(payload.get("node_id"), ...)` 直接拒绝、返回 error frame。
> 2. 使用**合成** `conversation_id=f"heartbeat:{agent_id}"` / `message_id=run_id`，IM `messages` 表里不存在 → `_persist_report_event` 写 `events` 表时 `sqlite3.IntegrityError: FOREIGN KEY constraint failed`。
>
> 根本原因：heartbeat run 跑在自己新建的 kernel session、**不绑定任何真实 IM 会话**，所以没有真实 `conversation_id`/`message_id` 可用——无论怎么补字段都满足不了 events 表外键。M138 的集成测试 `heartbeat_report_into_conversation_events` 用的是不强制外键的测试桩，给了假绿信心。
>
> > 注：refactor-387 修好了 heartbeat 的 async 提交路径后，这条坏报告才真正被触发，会**打断 IM WebSocket 连接**。refactor-387 已按 parity 收口（删除畸形桥 + 双侧健壮性加固，heartbeat run 正常执行、连接健康），并把"真正做对回发"作为本 issue 单列。
>
> ## 期望（做对）
>
> 把 heartbeat run **绑定到主 agent 的真实 IM 会话**，并走真实 `message` 行的 report/streaming 路径，使 heartbeat 结果真正回发、在用户会话可见——满足 M138 R2 的原始意图。
>
> ## 参考
>
> - M138 TASKS 文档：`TASKS/M138-主-Agent与Heartbeat汇报链路产品化.md`（commit 79eda8b2）
> - refactor-387 parity 收口：`docs/changes/refactor-387-kernel-sdk-no-http-api/fix-heartbeat-im-report-progress.md`

## 澄清记录

前半部分（Q0 / Q0b）为本 spec 启动前、与用户的设计讨论回顾性记录（用户要求"前面我们沟通的，你也要回顾性记录"）。A 段为用户原话；调研结论与实现层细节不进 spec，留给 design.md。

- Q0（回顾·会话归属第一轮）: heartbeat 跑在/投递到哪个 IM 会话？我最初推荐"复用 owner 直聊会话"。
  A(原话): 有个问题，我现在一个agent可以在IM中产生一堆单聊。复用哪一个呢？以及其实是否适合有一堆单聊也可以讨论。我搞一堆单聊的初衷是希望每个聊天用同一个agent和我做不同的事情
  Agent 解读: 用户的"一堆单聊"是「同一 agent、不同任务线」的刻意模型，应保留；真正缺的是"agent 主动产出（heartbeat/cron）该有一个确定的家"，不该挤进某条任务单聊。经核实 IM 已有 canonical 直聊解析（`_find_canonical_direct_conversation` 取最旧那条 user-agent 直聊），agent 主动消息天然收敛到一条；正常任务往返回复各走自己窗口的 reply_context，互不干扰。

- Q0b（回顾·主直聊怎么确定）: agent 的"主直聊/替身入口"用显式专用会话，还是复用 IM 现有"最旧直聊"？
  A(原话): 复用 IM 现有"最旧直聊"
  Agent 解读: 不在 IM 加新的 primary 标记；heartbeat/cron 产出投递到 (owner, 该 agent) 之间最旧那条直聊。不存在时由 IM 自动创建一条。

- Q1: heartbeat 触发时若 owner 从没与该 agent 开过任何直聊，怎么办？
  A(原话): 自动新建直聊并汇报(推荐)
  Agent 解读: agent 主动来找你——没有现成直聊时自动新建一条 (owner, 该 agent) 直聊并把汇报发进去。配合"无事不报"，只有真有事才会弹。

- Q2: heartbeat 汇报在会话里怎么呈现——像正常 agent 回复一样实时流式，还是只出最终一条？
  A(原话): 同普通 agent 消息(推荐)
  Agent 解读: 开着会话就像平时聊天一样实时流式呈现，没开就是一条已完成消息躺在会话里；不为 heartbeat 单造展示逻辑。

- Q3: 汇报准备好那一刻 IM 断线，这条汇报怎么处理？
  A(原话): 平时的对话怎么样就是怎么样
  Agent 解读: heartbeat 投递不做任何专属处理，完全继承普通回复出站路径的送达/失败行为——不单造持久化重投/离线补投。这正是本 unit 的核心论点：heartbeat 是一次系统发起的消息，除"触发来源"外一律按普通 turn 对待。

## 用户场景

用户给某个 agent 写了 `HEARTBEAT.md`，声明一项定时意图——例如「每天早上看一眼我的日程，有冲突就提醒我」，或「每 10 分钟查一下 CI，挂了就告诉我」。到点后，agent 自己跑一轮。

- 如果这轮**发现有该说的事**，它就在「你和它的直聊」里发一条消息告诉你——就像替身主动来找你说话。你正开着那个窗口，就看着它像平时聊天一样实时打字、把话说完；你没开窗口，回头打开就看到一条它发来的汇报消息，和平时收到它的消息没有任何区别。
- 如果这轮**没什么可说的**，它就闭嘴，不发任何消息、不打扰你。
- 你可能和**同一个 agent 开了好几个单聊**，各做不同的事（不同任务线）。agent 的这种**主动汇报永远落到你俩最早建的那条直聊**——它的"家"——不会乱窜进你某条正在进行的任务单聊里。那些任务单聊照常只回你主动说的话。
- 如果你**压根还没和它开过任何直聊**，它第一次有事要报时会**主动建一条直聊**来找你，汇报就在那条新会话里。

对比之前（M138）：这套汇报链路从上线起就没在真实 IM 上生效过——heartbeat 跑完，结果发不出来（甚至会打断连接）。本 unit 让用户**第一次真正看到** agent 的主动汇报落进自己的会话。

## 验收标准

### Requirement: 定时 heartbeat 运行结果以 agent 消息形式出现在 owner 直聊

#### Scenario: 本轮有内容可汇报
- **GIVEN** owner 与该 agent 已有直聊
- **WHEN** `HEARTBEAT.md` 定时触发、且本轮 agent 判断有内容要汇报
- **THEN** owner 与该 agent 的直聊里出现一条该 agent 发出的汇报消息

#### Scenario: 会话开着时实时呈现
- **GIVEN** owner 正打开着该直聊
- **WHEN** heartbeat 汇报产生
- **THEN** 该汇报像普通 agent 回复一样实时（流式）呈现在会话里

#### Scenario: 会话没开时作为已完成消息留存
- **WHEN** heartbeat 汇报产生而 owner 未打开该会话
- **THEN** owner 之后打开该会话时能看到这条汇报消息，与平时收到 agent 消息一致

### Requirement: 本轮无内容可报时静默，不打扰用户

#### Scenario: 无可汇报内容
- **WHEN** heartbeat 定时触发、但本轮 agent 判断没有可汇报的内容
- **THEN** 直聊里不出现任何新消息

### Requirement: 汇报始终落到 canonical（最早建的）直聊，不污染其它任务单聊

#### Scenario: owner 与同一 agent 有多条单聊
- **GIVEN** owner 与该 agent 开了多条直聊（不同任务线）
- **WHEN** heartbeat 汇报产生
- **THEN** 汇报出现在其中最早创建的那条直聊
- **AND** 其它任务单聊里不出现该汇报

#### Scenario: 尚无任何直聊（首次/空态）
- **GIVEN** owner 从未与该 agent 开过任何直聊
- **WHEN** heartbeat 首次有内容要汇报
- **THEN** 自动出现一条 owner 与该 agent 的新直聊，其中包含该汇报消息

### Requirement: 用户只看到汇报内容，看不到驱动运行的内部触发指令

#### Scenario: 触发指令对用户不可见
- **WHEN** heartbeat 触发并产生汇报
- **THEN** 用户在会话里只看到 agent 的汇报内容
- **AND** 看不到驱动这轮运行的内部触发提示（例如 "Heartbeat scheduler trigger…" 之类的系统注入文本）

## 范围与非目标

在范围：
- 定时 heartbeat 机制（`HEARTBEAT.md` 的 interval / every / cron / at 全部调度模式）的运行结果，真正回发并出现在 owner 与该 agent 的 canonical（最早建）直聊里。
- 无现成直聊时自动新建。
- 本轮无内容可报时静默。
- 汇报的呈现与投递行为与普通 agent 消息完全一致。

非目标：
- **不**为 heartbeat 单造投递失败的持久化 / 离线补投 / 重试——投递走与普通回复完全相同的出站路径，失败行为与普通回复一致（用户原话："平时的对话怎么样就是怎么样"）。可靠通知是另一种语义，不压给周期心跳。
- **不**把 heartbeat 汇报投递到群聊（只投 owner 直聊）。
- **不**引入显式"主 Agent"标记或"先汇报给主 Agent 再转用户"的间接层——每个 agent 直接向 owner 的 canonical 直聊汇报，collapse 掉 M138 的主/非主区分。
- **不**改动 `HEARTBEAT.md` 的调度语义或解析（沿用现有 interval / every / cron / at）。
- M138 R1 的"主 Agent 入口在前端可识别"语义不在本 unit——本 unit 只解决 R2 的"结果真正回发、用户可见"。
