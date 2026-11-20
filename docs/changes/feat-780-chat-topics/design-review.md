# feat-780 · 独立设计审查

## Round 1

- reviewer: independent Gate 2 reviewer (subagent)，未参与本设计编写
- target: `754a8935a7a3ee7509c579efe8fbf2d61c9846b2` 上的 spec、design、六份 delta、`prototype.html`、`prototype-review/` 五张截图、M1 骨架。对照同一 commit 的 develop 代码。无 `deployment-prompt.md`。
- review_mode: full
- mode_reason: 首次 Gate 2，无既有 `design-review.md`。范围含话题存储、中继裁剪、未读、模型可见回复地址，以及 Web/iPhone 原型。
- started_at: 2026-11-20T15:37:42+00:00
- completed_at: 2026-11-20T15:46:43+00:00
- duration: 9m1s
- Verdict: **Issues Found · 1 CRITICAL / 4 WARNING**

### Coverage 与证据

- **现状断言。** `messages.reply_to_json` 由 `db.ts` 在执行 `schema.sql` 之后用可重复的 `ALTER TABLE` 补列。`messaging.ts` 的 `replyReference` 只拷贝本聊天一条已存在的 user/agent 消息；`deliveryFacts` 在私聊、@、引用到该 Agent 时把 `addressed_to_agent` 设为真；`enqueueRelays` 把成员 Agent 写入 `relay_tasks`。`message-records.ts` 的 `insert` 对除发送者外的参与者 `unread_count+1`，并更新 `last_message_preview`。已读接口按 `messages.rowid` 重算 `unread_count`。`classifyChatDelivery` 先处理 `owner_only && !ownerDirect → skip`，再把私聊、@、引用判为 `high`，其余为 `background`（`CHAT_BACKGROUND_DELAY_MS` = 10 分钟）。`single-thread.ts` 只把 `background` 放进 `bufferGroup`；高优走 `takeGroup` 和该聊天已有的 `chatBinding`。自动正文的 `turn_start` 只带 `conversation_id`。`inbox.acceptRelay` 的 target 是 `conversation_id`。Global 只有主 session。`send_message` 已有 `target` 与可选 `reply_to_message_id`，外部通道和内部子执行不能带引用。`ConversationView` 的消息菜单仍是复制和分支，不渲染 `reply_to`。这些与 design 的现状段一致。
- **另一条入箱并不经过 `enqueueRelays`。** Agent 完成的群消息由 `gateway.ts` 的 `groupReply` 转给其他全部 Agent，`chat-streaming.ts` 在 `message_completed` 时调用它。PA 观察由 `schema.sql` 的 `personal_observation_event` 在 `conversation_events` 插入后写入 `pa_source_events`，再由 `global-agent.ts` 的 `recoverPersonalObservations` 摄入。design 把未关注话题的裁剪写成「`enqueueRelays` 之前的同一刀」，见 R1-C1。
- **已收口且与代码相符的决定。** 话题回复与根消息同在 `messages`，用可空 `thread_root_id`，引用仍只用 `reply_to_json`。不按话题拆 session，也不按话题拆 Inbox target；`/new` 仍重开该聊天现有 session，Global 仍是一条主 session。仅限本人的群话题即使被中继，也会在 `classifyChatDelivery` 因缺少 `ownerDirect` 而 `skip`，不会进入十分钟批；创建者私聊仍是 high。私聊话题不按 `thread_follows` 过滤，未读和提示继续走现有私聊水位。人发的、会走 `enqueueRelays` 的未关注群话题，按设计在分类前丢掉，确实到不了 `bufferGroup` 和参与者 Inbox。多步任务由模型选择 `in_thread_of`，宿主在本轮已经写入该话题后不再向主时间线双写；一句且本轮没写过话题时留在主时间线。这个选择已写明，不另做句数分类器。无历史重写，不需要 `deployment-prompt.md`。
- **需求覆盖。** 一层话题、与 feat-730 引用分开、群关注/私聊不过滤、团队协作按关注叫醒、仅限本人、搜索打开话题、影子会话不建话题、分支仍是单聊，design 都有对应结果。iPhone 不补主时间线「回复」与当前菜单一致。feat-779 未进入本树。缺的是阅读位置、手机关注控件，以及写入副作用，见 R1-W1、R1-W3、R1-W4。
- **delta。** 三份 MODIFIED 都保留了 canonical 原有 Scenario，没有删条。时间线条目改为排除话题回复并让根消息带回复数；已读场景加上「打开主时间线不清尚未打开的群话题」；回执分母收成当时的关注者。后一条在 design 正文里没有机制，并入 R1-W1。ADDED 与 spec 的落点一致，但「正在看的人直接看到」没有保住向上翻阅时不拉动位置，见 R1-W3。`agent-capabilities.md` 不单列 delta 是说得通的：工具集合不变，`in_thread_of` 的可观察行为写在路由和 Global delta。
- **模型可见信息（设计审查，未跑模型）。** 话题轮次的样例有根 id、根摘录、更早回复和当前消息，并要求用 `in_thread_of` 指向该根、不要再贴主时间线。引用沿用 feat-730，并标明是引用而不是新指令。默认只带根和最近 20 条，更早的用带 `thread_root_message_id` 的 `conversations` 读取；不带该参数时读取和搜索仍是主时间线。Before/After 能区分一句、多步不双写，以及未中继时背景里没有这些消息。这只覆盖已经中继的那一轮。观察触发器和 `groupReply` 仍会把未关注话题送进十分钟输入，所以 After 对 PA 和其他 Agent 不成立，见 R1-C1。拼接方式见 R1-R1。本轮没有真实 provider 请求，不能把样例写成模型已经会调用。
- **前端。** 看过 `desktop-thread.png`、`desktop-closed.png`、`desktop-unfollowed.png`、`phone-timeline.png`、`phone-thread.png`。桌面同时留下主时间线和话题列，话题正文不进时间线，入口是条数加一行摘录；收起后只留入口；关注状态在话题顶栏，有「关注中 / 已取消关注」。390 宽推入一层，返回回到时间线，气泡上没有「回复」。这些 must-match 能对应 M1 的桌面、窄屏、iPhone 和话题内引用。手机层没有关注控件，气泡下的常驻按钮又和「加入菜单」不一致，见 R1-W4、R1-W5。原型未接后端；滚动、失败草稿和真实未读按 design 留在 M1，这次不把它们写成已通过。
- **架构。** 把话题放进现有 `messages`，比另建一套消息合适：附件、幂等、引用、搜索和实时事件继续在同一处。会话边界继续用 `chatBinding` 和 Global 主 session，Inbox target 继续是聊天，这是对的，不该按话题再开记忆。参与者中继的裁剪点放在分类之前也对，但不是唯一入箱点。fork 的复制查询在 `conversation-actions.ts`，不在 M1 文件表里，见 R1-W2。
- **里程碑。** 只有 M1，有 `[reviewer]` 和 `[worker]`，目录仅有 `.gitkeep`。reviewer 覆盖人和 Agent 的主要旅程，worker 覆盖根校验、游标、未读、中继裁剪、high、不入 buffer、`in_thread_of` 和自动正文不双写。原型 must-match 的桌面并排、窄屏、iPhone、关注和话题内引用都写进了 reviewer 或「符合 must-match 层级」加上 worker 的 1100/390/iPhone 对照。缺观察事件、`groupReply`、回执和 fork 复制。
- **证据边界。** 本轮只审文档和当前代码，没有启动服务、模拟器或模型。

### 历史问题闭环

首轮，无既有 issue。

### Issues

1. **R1-C1 · 未关注的群话题仍会进入十分钟批。** [design.md 关键决策](design.md#关键决策) 写 IM 在 `enqueueRelays` 之前丢掉未关注 Agent，使它们进不了 `group_background`，也进不了 Inbox 的十分钟批，并称 PA 观察使用同一刀。develop 上还有两条不经过 `enqueueRelays` 的入箱。

   `schema.sql` 的 `personal_observation_event` 在 `message.created` 和 `message.completed` 之后，给主人所在聊天的 PA 插入 `pa_source_events`。`global-agent.ts` 的 `recoverPersonalObservations` 再 `ingest`。未 @、未引用时，`personal-agent.ts` 的 `sourceFacts` 不会把 `addressed_to_agent` 设为真，`classifyChatDelivery` 得到 `background`，于是进入十分钟观察批。已关注但没有被点名的话题，这条路径也不会变成 high。这与 [personal-agent delta](specs/gateway/personal-agent.md) 的「不进入观察 Inbox，也不触发十分钟合并通知」以及「已关注则高优、不并进十分钟批」相反。有读权限时按话题根读取可以保留。

   `gateway.ts` 的 `groupReply` 把 Agent 已完成的群消息转给其他全部 Agent，走 `relayMessage`。`chat-streaming.ts` 在 `message_completed` 时调用它，`publishAgent` 也会调用。`deliveryFacts` 不会因话题关注把 `addressed_to_agent` 设为真。未关注的团队协作 Agent 因此收到 `background`，进入 `bufferGroup` 或 Inbox 的十分钟批。人发的话题回复才走 `enqueueRelays`。Agent 在话题里说话，或自动正文写进话题，都会绕过设计里的那一刀。spec 要求这些回复不混进大约十分钟才带上的普通群消息。

   仅限本人仍会在分类时因缺少 `ownerDirect` 而 `skip`，私聊不进 `groupReply`。这两条不能代替上面的裁剪。M1 列了 `schema.sql` 和 `gateway.ts`，没有 `personal-agent.ts`，正文也没有点名触发器和 `groupReply`。需要写明：未关注话题不写观察事件；`groupReply` 只发给仍关注的 Agent，并且这些中继按 high 进入该聊天现有 session。worker 要用一条 Agent 话题回复和一条 PA 观察断言十分钟批里没有它。

2. **R1-W1 · 群话题的未读、列表预览和回执没有按现有写入副作用收口。** `message-records.ts` 的 `insert` 给除发送者外的所有参与者 `unread_count+1`，并把正文写成 `conversations.last_message_preview`。`messaging.ts` 打开聊天时执行 `unread_count = COUNT(rowid > 水位)`，并把 `rowid <= 水位` 的回执标为已读。`discard` 也按这个水位重算。

   design 要求群话题只给 `following=1` 增加 `thread_follows.unread_count`，并加进列表总未读；打开主时间线的 SQL 不再把话题回复算进已读。按字面只改 COUNT，重算会清掉刚加进同一列的话题未读。水位之前插入的话题回复仍会被标成已读。未关注的人会在会话列表看到话题正文，这和「不提示、回复不进主列表」冲突。[conversations delta](specs/im/conversations-messages.md) 已把群话题回执的分母收成当时的关注者，design 和 M1 都没有回执。

   需要写明列表未读等于主时间线水位计数加上该用户各话题的 `thread_follows.unread_count`，重算和丢弃都加回后者；话题回复不改写全员预览；`message_receipts` 只包含当时该计未读的人。私聊继续用现有水位。

3. **R1-W2 · 分支复制会带走话题，而且不在 M1 文件里。** `conversation-actions.ts` 的 fork 执行 `SELECT * FROM messages WHERE conversation_id=? ORDER BY rowid`，再截到锚点。夹在中间的话题回复会进新单聊。design 写了只复制主时间线，M1 范围没有这个文件。按该范围实施，spec「新单聊只带主时间线历史，原话题留在原聊天」做不到。把这条查询纳入范围，worker 断言新单聊没有 `thread_root_id`。

4. **R1-W3 · 向上翻阅时，新回复不拉动阅读位置没有进入设计或验收。** spec「阅读和接上」要求正在看更早回复时，新回复出现但不把阅读位置拉走。design 只写正在看该话题时追加气泡。[conversations delta](specs/im/conversations-messages.md) 写成「正在看的人直接看到」，没有留下这一条，实现时可以做成滚到最新。M1 reviewer 也没有这条。客户端数据流、Web/iOS delta 和 reviewer 退出标准需要写明：人已经离开底部时保持当前位置，新回复仍加在末尾。

5. **R1-W4 · 窄屏话题层没有关注状态，iPhone 动作放在菜单还是气泡下也没定。** spec 要求 iPhone 能关注和取消。design 写话题顶栏有关注状态，must-match 单独要求「关注 / 已取消」。`phone-thread.png` 的顶栏只有「返回」和「话题」；两种状态只在桌面列和页面外的演示按钮上。按手机画面做，窄屏看不出也不会切换关注。

   同一处还有操作层级冲突。design 相关历史写把「在话题中回复」加进 `ConversationView` 菜单，与复制、分支以及 779 落地后的引用取并集。`phone-timeline.png` 画的是气泡下的常驻按钮。feat-779 的设计审查 Round 2 已是 Approved，其 M2 使用长按菜单，并且不在每条消息下常驻一行动作；本树的 `ConversationView` 仍只有复制和分支，779 没有实现。design 写「该设计尚未收口」和这份审查结论不符。要选定长按菜单或气泡下按钮，让 must-match 画面与选定结果一致，并写明与 779 并集时不删除对方的项、也不变成两套入口。390 宽的话题层还要有与桌面相同的关注状态，主时间线的每条消息上仍然没有这个开关。

### Recommendations

1. **R1-R1 ·** 话题块样例已经包含 Current message，正文又写「在现有消息前增加」。请规定它替换本条的默认 `messageContent`，还是只附根消息和更早回复，避免同一条回复出现两次。
2. **R1-R2 ·** `db.ts` 先执行整份 `schema.sql`，再 `ALTER` 补列。`(thread_root_id, created_at, id)` 若写在补列之前的 schema 里，旧库启动会因列不存在而失败。索引应在列已经存在之后创建。这仍然不需要 `deployment-prompt.md`。
3. **R1-R3 ·** 影子会话不能建话题已经写在约束和 reviewer 标准里。建议与根校验放在同一条：外部会话拒绝非空 `thread_root_id` 和 `in_thread_of`，避免只藏按钮。

### Author Resolutions

- R1-C1 accepted。关键决策写明 `enqueueRelays` 与 `groupReply` 使用同一谓词，未命中不调用 `relayMessage`；`personal_observation_event` 不为未关注且未被点名的话题回复写 `pa_source_events`，已写入的观察事件在 `recoverPersonalObservations` 标成 high。路由与 PA delta 的场景改成覆盖人和 Agent 的发送。M1 的 worker 标准包含观察事件和 `groupReply`。
- R1-W1 accepted。写入节规定列表未读等于主时间线水位计数加上 `thread_follows.unread_count`，重算和丢弃都加回后者；话题回复不改 `last_message_preview`；`message_receipts` 与未读对象相同。回执 delta 仍保留其余 Scenario。
- R1-W2 accepted。`conversation-actions.ts` 进入 M1，fork 只复制 `thread_root_id IS NULL`。
- R1-W3 accepted。实时事件、Web/iOS delta 和 reviewer 标准写明离开底部时不拉动阅读位置。
- R1-W4 accepted。窄屏和 iPhone 使用长按菜单，不在气泡下常驻按钮；话题顶栏在两端都有关注。原型 `phone-timeline.png` 与 `phone-thread.png` 已按此重拍。feat-779 Round 2 Approved 已写进相关历史，菜单取并集。
- R1-R1 accepted。话题块替换该条的默认 `messageContent`，当前消息只出现一次。
- R1-R2 accepted。索引在 `thread_root_id` 列存在之后创建，仍不需要 `deployment-prompt.md`。
- R1-R3 accepted。外部会话在根校验处拒绝非空 `thread_root_id` 与 `in_thread_of`。
