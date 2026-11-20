# feat-780: 聊天内话题 — 技术方案

> 对齐: spec.md（`origin/develop` 上的 feat-780 首文档）

## Changelog

## 现状分析

### 涉及范围

话题要接进已经存在的一条消息链，而不是再做一套聊天。

- `apps/im-server/src/schema.sql` 与 `db.ts`：`messages` 现有 `reply_to_json`，没有话题根。启动时已用可重复的 `ALTER TABLE` 补列，不另做历史搬迁脚本。
- `apps/im-server/src/messaging.ts`：`replyReference` 只拷贝被点那一条；`deliveryFacts` 在私聊、@、引用到该 Agent 时把 `addressed_to_agent` 设为真。`enqueueRelays` 把群消息交给成员 Agent。
- `apps/im-server/src/message-records.ts`：新消息给除发送者外的参与者 `unread_count+1`。已读水位按 `messages.rowid` 重算，不区分主时间线和别的消息。
- `apps/im-server/src/message-search.ts`：按聊天搜正文，结果没有话题地址。
- `apps/im-server/src/gateway.ts`：中继元数据在引用对象是 Agent 时写入 `reply_to_agent_id`。
- `packages/product-contracts/src/collaboration.ts`：`classifyChatDelivery` 把私聊、@、引用判成 `high`，其余群消息判成 `background`（十分钟，`CHAT_BACKGROUND_DELAY_MS`）。`owner_only` 且不是创建者私聊则 `skip`。
- `packages/personal-assistant/src/single-thread.ts`：`background` 进 `store.bufferGroup`，高优才 `takeGroup` 并提交到该聊天已绑定的一个 session。自动正文用 `turn_start` 发回 `binding.conversationId`，没有话题地址。
- `packages/personal-assistant/src/global-agent.ts` 与 `inbox.ts`：同一条中继以 `high` 立即通知，或以十分钟写入 Inbox。Inbox 的 target 是聊天，不是某一条消息。Global 只有一条主 session。对外发言走 `send_message`。
- `packages/personal-assistant/src/attention.ts`：群里是否算被点名，直接采用 IM 给出的 `addressed_to_agent`。
- `packages/dsh-integration/src/message-arguments.ts`：`send_message` 已有 `target` 与可选 `reply_to_message_id`。外部通道和内部子执行不能带引用。
- `src/IM/frontend` 的消息面板：菜单有「回复」，输入区可取消引用，气泡用单层引用卡片定位原消息。
- `src/IM/ios` 的 `ConversationView`：菜单仍是复制和分支，不渲染 `reply_to`。补齐手机引用回复属于 feat-779，本 unit 不加这个动作。

### 既有约束

- 执行运行时只经 `packages/dsh-integration` 的公开出口。PA、Channels、IM 不 import DSH。节点与运行时仍走现有 stdio，不新增内核 HTTP。
- 不恢复第二套 Agent Loop，也不为话题新建一种 session 类型。`/new` 仍重开该聊天现有的 single_thread session；Global 仍是一条主 session。
- 引用回复保持 feat-730：单层快照、点击定位、不能跨聊天，不能引用系统行或未完成的 Agent 消息。本 unit 不改它的语义。
- 团队协作与仅限本人的收件边界保持 `classifyChatDelivery`。话题只改变「哪些群消息算被点名、哪些根本不入队」。
- 主时间线的普通群消息仍可积压约十分钟。未关注的话题回复不得进入这批积压。
- 飞书影子会话与外部投递第一版不能创建话题。

### 可复用能力

- 用：`messages` 表、`reply_to_json`、现有创建/幂等/附件/实时事件、`mentionedAgents`、`deliveryFacts`、`classifyChatDelivery`、`bufferGroup`、Inbox 的 high/background、`send_message` 的 `target` 与 `reply_to_message_id`、Web 引用卡片与定位。
- 改：主时间线查询排除话题回复；群未读与已读水位把话题回复分开；中继扇出按关注裁剪；自动正文和 `send_message` 能带话题根；模型看到的这一轮标明话题。
- 不用：每条话题一个 DSH session，或每个话题一个 Inbox target。现有绑定以聊天为单位，`/new` 和 Global 主 session 都靠这个边界。话题的隔离是「这条消息写到哪、谁会被叫醒」，不是再开一段记忆。

### 相关历史

- feat-730：Web 与服务端已有单层引用。本设计只增加话题地址，并允许话题里的新消息同时带这个引用。
- feat-774：协作范围取代了旧的「仅被提及 / 回复所有群消息」。话题门控必须建在 `high | background | skip` 上。
- feat-779：要求 iPhone 补齐引用回复和搜索，其 M2 打算在长按菜单里做引用。该设计尚未收口。本 unit 只在同一菜单增加「在话题中回复」，保留复制、分支，以及 779 落地后的引用。两边都改 `ConversationView` 时，菜单是并集，不互相删除。本 unit 不依赖 779 先合并。

## 架构总览

一条话题是主时间线上某条人或 Agent 消息的回复集合。根消息留在主时间线。回复行仍是 `messages` 里的普通消息，用话题根指向那一条。人和 Agent 的「关注」决定群里谁增加未读、哪个 Agent 收到中继。中继一旦发出，仍走现在的 high 路径，因此不会掉进十分钟积压。

```mermaid
flowchart LR
  subgraph im [IM]
    Timeline[主时间线查询]
    Messages[messages]
    Follows[thread_follows]
  end
  subgraph node [personal-assistant]
    Class[classifyChatDelivery]
    Buffer[group_background / Inbox 十分钟]
    High[该聊天的现有 session]
  end
  Web[Web / iOS] --> Messages
  Messages --> Timeline
  Messages --> Follows
  Follows -->|仅关注者或私聊| Class
  Class -->|high| High
  Class -->|background| Buffer
  High -->|自动正文或 send_message| Messages
```

这张图回答的是：话题不新开服务，未关注的群话题在进入 `classifyChatDelivery` 之前就被留下，所以既不会及时叫醒，也不会变成 background。

## 关键决策

**话题回复与根消息存在同一张 `messages` 表。** 新增可空 `thread_root_id`。空表示主时间线消息；非空表示这条回复属于该根。根必须是同一聊天里、自己的 `thread_root_id` 为空、且发送者是人或 Agent 的已可读消息。系统行、配置分界、未完成 Agent 消息、别的聊天、以及另一条话题回复都不能当根。这样附件、幂等、引用快照、搜索和实时事件都不用第二套消息。

**引用和话题是两个独立字段。** `reply_to_json` 继续只表示「卡片上引用哪一条」。`thread_root_id` 表示「这条消息出现在哪」。主时间线上的「回复」只写引用、不写话题根。话题里的普通发送只写话题根。话题里再引用某一条时两个都写，被引用的消息必须是该根或该话题里的消息。拒绝嵌套话题。

**群里谁收到话题，由 `thread_follows` 决定。** 一行是聊天、话题根、用户。第一条话题回复出现时，根消息的发送者和回复者成为关注者。之后在话题里发送、被 @、或被引用，都会重新关注。人可以取消关注。取消后，直到再次发送、被 @ 或被引用，不再计未读。Agent 不提供取消关注，避免做完就听不见纠正。仅限本人的 Agent 不会因群话题被写入关注，也不会收到群话题中继。私聊不使用这张表做过滤：对方仍按一条普通私聊新消息收到未读和中继。

**未关注的群话题不中继。** IM 在 `enqueueRelays` 之前丢掉这些 Agent。它们进不了 `group_background`，也进不了 Inbox 的十分钟批。被关注、被 @ 或被引用的 Agent 仍收到中继，并且 `addressed_to_agent` 为真，于是 `classifyChatDelivery` 得到 `high`。私聊话题保持现在的 direct/high。仅限本人在群里仍是 `skip`；创建者的私聊话题仍是 high。PA 的观察入箱使用同一刀：未关注的话题回复不写观察 Inbox，但聊天读取在有权限时仍能按话题根读到。

**不按话题拆 session，也不按话题拆 Inbox target。** single_thread 继续用 `chatBinding` 的一个聊天 session。Global 与 PA 继续用主 session，Inbox target 仍是 `conversation_id`。叫醒时的模型和自动回帖地址改到话题上。同一聊天里的话题和主时间线会留在同一段记忆里；这是现有聊天绑定的结果，不是把话题内容刷回主时间线。

**自动回帖的地址跟这一轮的话题走。** 从话题叫醒时，single_thread 的 `turn_start` 带上这个话题根，最终气泡写进话题，不写主时间线。从主时间线叫醒、且这一轮没有向该请求消息的话题发过言时，最终气泡仍在主时间线，用来保住「一句能答完」。这一轮只要已经用 `in_thread_of` 把话写进该请求的话题，随后的自动正文也进入同一话题，并且不在主时间线上再放一条。Global 没有自动气泡；它用 `send_message`。当前轮由某条话题叫醒、且目标就是这个聊天时，省略 `in_thread_of` 也写回该话题，避免默认落到主时间线。

**多步任务由模型选择 `in_thread_of`，宿主保证不双写。** 工具说明要求：需要先确认再交付时，第一条给人看的话就用 `in_thread_of` 指向用户那条请求；不要同时在主时间线再说话。宿主不另做「算不算多步」的分类器。脚本化运行可以证明地址；真实模型是否记得调用，由实现阶段的代表性任务核对，不能靠服务端猜一句还是多句。

**桌面话题在时间线旁边打开，窄屏和 iPhone 推入一层。** 依据是 Web IM「桌面可并排、手机单栏」的原则。主时间线只增加根消息上的话题入口，不把回复插进时间线。iPhone 不加「回复」按钮。

## 接口与数据流

### 数据

`messages.thread_root_id TEXT NULL`，引用 `messages.id`。索引 `(thread_root_id, created_at, id)`。启动时按 `db.ts` 现有方式补列和建表；旧行保持 NULL，未读数字不重算。

`thread_follows(conversation_id, root_message_id, user_id, following INTEGER, unread_count INTEGER, last_read_message_id TEXT)`，主键是三列身份。`following=0` 表示人已取消。Agent 行保持 `following=1`。

主时间线列表、游标和配置分界只扫描 `thread_root_id IS NULL`。话题列表只扫描该根。搜索仍扫全部可读消息，但结果带 `thread_root_id`；客户端据此打开话题而不是把它插进主时间线。fork 只复制主时间线消息；原聊天的话题不搬进新单聊，也不在新单聊里复活。

### 写入

创建消息增加可选 `thread_root_message_id`。校验失败沿用现在的 422/404，不创建半条消息。成功后在同一事务里：

1. 写入消息。群话题则更新关注：根发送者、当前发送者、正文里的 @、引用对象。仅限本人的 Agent 跳过。
2. 未读：私聊仍给其他参与者加聊天未读，并参与现有已读水位。群主时间线消息仍按现在加给所有其他人。群话题回复只给 `following=1` 且不是发送者的人增加 `thread_follows.unread_count`，并加到聊天列表使用的总未读。
3. 已读水位的 SQL 不再把群话题回复算进「打开主时间线就读完」。打开话题才清该根的 `unread_count` 并把 `last_read_message_id` 设为已看到的最后一条。私聊打开聊天仍按现在的水位清掉，包括话题回复。
4. 中继只发给仍应收到的 Agent。群话题的元数据包含 `thread_root_message_id`、根消息的发送者与正文摘录、以及这条之前有限条话题回复。`addressed_to_agent` 对这次中继为真。

实时 `message.created` 带 `thread_root_id`。主时间线客户端只更新根上的入口；正在看该话题时才追加气泡。

根消息的读取附带 `thread`：回复数、当前用户是否关注、最后一条回复的发送者和一行摘录。没有回复就不带 `thread`。

关注与取消是聊天成员对一个已存在话题根的显式操作。取消只影响自己。再次发送、被 @ 或被引用会把 `following` 设回 1。

### 模型可见信息

消费者是 single_thread 的该聊天 session、Global/PA 的主 session。生命周期只覆盖被中继的那一条：未关注的群话题没有 Inbox 行、没有 group buffer、没有模型输入。被叫醒时，这一轮在现有消息前增加一段来源明确的话题说明，而不是把话题回复伪装成主时间线新消息。

叫醒前，群里未点名的消息是「Background message」或 Inbox 背景。叫醒后，话题轮次的可见内容是：

```text
Thread on message "m-root" by 小李 in this conversation. Reply with in_thread_of "m-root" if the answer belongs in the thread. Do not also post it on the main timeline.
Root: 下周三要补哪三页？
Earlier in thread:
- m-2 小李: 先看第二页
Current message:
- m-3 小王: @Agent 第二页不用了
```

引用卡片仍用 feat-730 的投影，并标明它是引用、不是新的指令。摘录超过现有 1200 字时沿用省略，完整内容用消息 id 再读。话题说明默认带根和最近 20 条；更早的通过 `conversations` 读取，增加可选 `thread_root_message_id`。不带该参数时，读取和搜索的默认页仍是主时间线，避免把话题历史混进「这个聊天最近说了什么」。搜索命中话题回复时必须带根 id。

`send_message` 增加可选 `in_thread_of`。它是目标聊天里一条主时间线消息的 id，不能猜，不能和外部通道或内部子执行一起用。省略时：这一轮若由话题叫醒且 target 就是该聊天，宿主补上该根；否则写主时间线。`reply_to_message_id` 仍只做引用卡片。两者可同时存在。

Before：用户在主时间线说「用一句话回答」，single_thread 的最终正文回到主时间线。After：同一轮没有 `in_thread_of` 时仍是这样。Before：多句确认和结果会顺着自动正文堆在主时间线。After：模型把确认发到 `in_thread_of` 那条请求，宿主把本轮后续自动正文一并写入该话题。Before：无关群话题会在约十分钟后进入背景。After：没有中继，背景里没有这些消息。

交互约束：话题正文不能提高权限；引用和话题摘录都是聊天数据。仅限本人不会因为群里被 @ 就收到中继。PA 观察身份不变，未关注话题不构成新交办。`/new` 仍只重开该聊天的 session，不删除已有话题消息。

验证：用脚本化运行固定「一句」和「先 `in_thread_of` 再自动正文」两条路径，断言主时间线和话题里分别有什么。再取一条真实模型任务，核对实际请求里能看到根 id、`in_thread_of` 的工具说明，以及回帖落点。只看源码字段不算模型已消费。

### 主路径

```mermaid
sequenceDiagram
  participant User as 群成员
  participant IM as IM
  participant Node as personal-assistant
  participant Session as 该聊天或主 session
  User->>IM: 话题回复 thread_root_id
  IM->>IM: 更新关注与未读
  alt 群里该 Agent 未关注且没被点名
    IM-->>Node: 不中继
  else 私聊，或群里已关注、被 @、被引用
    IM->>Node: 中继 addressed_to_agent
    Node->>Session: high，附话题根与最近回复
    Session->>IM: 自动正文或 send_message 写回同一话题根
  end
```

### 客户端

Web 桌面在现有消息面板右侧打开话题，时间线留在原处。窄屏浏览器和 iPhone 把话题推成一层，带返回。根消息在两行动作里分清「回复」和「在话题中回复」；iPhone 只有后者，外加入口上的回复数。话题顶栏有关注状态。话题内引用沿用现有引用卡片，发送结果仍留在这一层。没有回复时不显示入口。发送失败保留草稿。

具体画面和必须对齐的层级见 `prototype.html`。色板和字号适配现有聊天样式，信息层级和操作结果不能改。

## 前端原型

要通过原型判断的设计决定：两个发送动作是否一眼能分开；话题回复是否不占据主时间线；桌面并排与手机推入是否各自能读完并继续回复；关注状态是否在话题里而不是在每一条消息上。

- 原型文件: [prototype.html](prototype.html)
- 用户目标与体验方案：从一条群消息把讨论收进话题，主时间线只留入口。桌面同时看见时间线和话题；窄屏与 iPhone 进入话题后再返回。已有「回复」只在 Web 主时间线出现。
- 用户需要判断的问题：无。版式沿用已确认的「桌面可并排、手机单栏」，不改变首文档里的落点和提醒规则。
- 呈现方式与覆盖范围：现有聊天页背景加上可切换的桌面、窄屏和话题内引用。不实现登录、搜索或设置。
- 交互边界：可切换「回复 / 在话题中回复」、打开话题、关注和取消。消息内容是演示数据。

### 现有 UX grounding

| 当前产品入口 | 画面与操作基线 | 沿用或改善的体验及原因 | 本次设计 |
|---|---|---|---|
| Web 消息面板 | 主列是时间线和底部输入；悬停或菜单有「回复」，输入区出现可取消的引用摘要 | 人已经知道「回复」会留在这条时间线上 | 旁边增加「在话题中回复」，不替换「回复」 |
| Web 桌面聊天 | 会话列表和当前聊天并排 | 原则允许桌面同时看上下文 | 话题作为聊天内的第二列，不新开路由 |
| 窄屏 Web 与 iPhone | 单栏进入聊天；iPhone 菜单是复制和分支 | 手机没有宽度再放一列；iPhone 引用回复另属 feat-779 | 话题整层推入，返回回时间线；iPhone 不画「回复」 |

### 原型对齐契约

| 原型区域 / 状态 | 对齐级别 | 产品入口 | 必验 viewport / 状态 | 下游验收投影 |
|---|---|---|---|---|
| 主时间线上两个动作，话题回复不插入时间线 | must-match | Web 消息菜单与时间线 | 桌面 1100 宽；已有一条话题入口 | M1 `[reviewer]` 两个动作和入口 |
| 桌面话题列与主时间线同时可读 | must-match | Web 聊天页 | 1100 宽，打开话题、继续回复 | M1 `[reviewer]` 桌面阅读 |
| 窄屏推入话题并可返回 | must-match | 窄屏 Web | 390 宽，打开、返回、失败草稿还在 | M1 `[reviewer]` 窄屏 |
| iPhone 只有话题动作和推入层 | must-match | iOS 聊天 | 390 宽的手机结构，无「回复」按钮 | M1 `[reviewer]` iPhone |
| 话题顶栏的关注 / 已取消 | must-match | 话题顶栏 | 两种状态 | M1 `[reviewer]` 关注 |
| 话题内单层引用仍留在话题 | must-match | 话题输入 | 引用一条话题消息后发送 | M1 `[reviewer]` 话题内引用 |
| 色板、圆角、精确间距 | may-adapt | 现有消息气泡样式 | 不单独验收像素 | N/A |
| 登录、搜索页、Agent 设置、飞书影子会话 | out-of-scope | 相应现有页面 | 不在原型中 | N/A |

### 原型走查

- 实际渲染与走查范围：用无头浏览器打开 `prototype.html` 的桌面、收起话题、取消关注、390 宽时间线和 390 宽话题。截图在 [prototype-review](prototype-review)。
- 当前产品对照及代表性截图：Web 现况是单列时间线加「回复」；iPhone 菜单没有「回复」。[desktop-thread.png](prototype-review/desktop-thread.png) 同时看见时间线和话题；[phone-timeline.png](prototype-review/phone-timeline.png) 只有「在话题中回复」；[phone-thread.png](prototype-review/phone-thread.png) 推入后主时间线不在这一层。
- 体验判断与修正：入口用回复数而不是把正文再贴进时间线，避免和「不做同时发到聊天」冲突。关注放在话题顶栏，避免每条消息一组开关。
- 未验证项：原型没有接后端。真实产品的滚动、失败保留和未读仍由 M1 验收。

## 本次审查安排

| 必须回答的问题 / 对应目标 | 能力与使用阶段 | 证据方法、范围与已有定位 |
|---|---|---|
| 话题地址、未读和中继是否让未关注的群话题既不出现在主时间线，也不进入十分钟积压 | 架构设计，设计审查 | 本文件的数据与时序；对照 `messaging.ts`、`message-records.ts`、`collaboration.ts`、`single-thread.ts`、`inbox.ts` |
| 模型能否分辨话题、引用和回复地址，并且一句与多步不会双写 | Agent Context，设计审查 | 本文「模型可见信息」的 Before/After；工具字段 `in_thread_of` |
| 两个动作和桌面/手机层级是否让人知道话会去哪 | 前端体验，设计审查 | `prototype.html` 与走查截图 |
| 里程碑能否一次交付 spec 里的人和 Agent 旅程 | 设计审查 | M1 的 reviewer / worker 标准 |

## 契约层增量 (delta-spec)

- IM 会话与消息: [specs/im/conversations-messages.md](specs/im/conversations-messages.md)
- Web 聊天: [specs/im/web-chat-ux.md](specs/im/web-chat-ux.md)
- iOS: [specs/im/ios-client.md](specs/im/ios-client.md)
- 路由与投递: [specs/gateway/routing-delivery.md](specs/gateway/routing-delivery.md)
- Global: [specs/gateway/global-agent.md](specs/gateway/global-agent.md)
- PA 观察: [specs/gateway/personal-agent.md](specs/gateway/personal-agent.md)
- `docs/specs/gateway/agent-capabilities.md`: no spec delta。固定工具集合不变；`in_thread_of` 的消费者行为写在路由与 Global 的 delta。

## 风险与回退

- 模型可能把多步任务只写成一条自动正文，从而留在主时间线。工具说明和宿主「一旦写过话题就不再双写」减少这个口子，但不能代替模型选择。实现时用脚本化路径守住宿主，并用一条真实模型任务看它是否调用 `in_thread_of`。
- 同一 session 仍记得这个聊天里其他话题。回帖地址由宿主按本轮话题根固定，不靠模型记得不要写错地方。
- 主时间线游标如果忘了排除 `thread_root_id`，话题回复会插回时间线或卡住翻页。这是 M1 的必须测试。
- 回退：停止接受非空 `thread_root_id` 与 `in_thread_of`，客户端隐藏入口。已写入的话题行留在库里，不删；隐藏后它们不再出现在主时间线。不需要数据回滚。

## 一次性部署迁移

无。新列为空、新表为空就表示没有话题。不重写旧消息、旧未读或旧 session。不新增 `deployment-prompt.md`。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 隔离的 IM 与 Gateway | `./scripts/e2e-down.sh --wt <绝对工作目录>` | `./scripts/e2e-up.sh --profile daily --wt <绝对工作目录>` | 脚本打印 `e2e stack ready`，且 `curl -sf http://127.0.0.1:$IM_PORT/health` |

**Review 驱动方式**: 人的话题、未读和界面用 daily 栈在 Web 走通。Agent 的一句、多步和未关注不入积压，先用脚本化中继与运行事件，再在同一 daily 栈取一条真实模型请求核对话题块和回帖位置。iPhone 用同一后端；模拟器不可用时界面层级以原型对照和 iOS 视图测试为证，不把缺失的模拟器写成产品失败。

**验收前置**: 无。账号、模型和审核沿用 `config/e2e/daily`，不另要生产凭据或飞书应用。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1 | 聊天内话题 | 无 | 无 | `apps/im-server/src/schema.sql`、`db.ts`、`messaging.ts`、`message-records.ts`、`message-search.ts`、`message-input.ts`、`gateway.ts`；`packages/product-contracts/src/chat.ts`；`packages/personal-assistant/src/single-thread.ts`、`global-agent.ts`、`attention.ts`；`packages/dsh-integration/src/message-arguments.ts` 及话题读取的 conversations 投影；`src/IM/frontend` 消息面板与话题层；`src/IM/ios` 话题层与菜单。不改 feat-730 的引用语义，不实现 feat-779 的手机「回复」。 | `[reviewer]` Web 与 iPhone 能把一条消息收成话题，主时间线不出现回复正文；Web 的「回复」仍留在主时间线；话题内引用不离开话题；群里只有关注者得到未读，私聊仍像新消息；取消关注后不再提醒，再回复或被 @ 会恢复；团队协作的 Agent 不被未关注话题及时叫醒，那些消息也不在约十分钟后冒出来；被 @、被引用或已经参与则会及时接上，确认和结果写在请求那条的话题里；一句回答仍在主时间线；仅限本人不会被群话题叫进来；搜索能打开话题里的原文；影子会话不能建话题；分支仍是另一段单聊。桌面并排、窄屏和 iPhone 推入符合原型 must-match 的层级，而不是只多一个按钮。 `[worker]` 覆盖根校验、游标排除、群/私聊未读、中继裁剪、`high` 与不入 buffer、`in_thread_of`、自动正文不双写、模型可见话题块的脚本断言；并留下 Web 1100 与 390、以及 iPhone 结构与原型的对照记录。 |
