# bugfix-713: 丢弃 Agent 占位消息后恢复会话投影

## Relations

- Related: #468

本 unit 原按「iOS 聊天本地先行」立项，含 5 项范围。用户已确认瘦身：只保留第 5 项——`message_discarded` 时恢复会话的 `unread_count` / preview / `last_message_at`。其余四项（会话列表本地快照与冷启动首绘、发送期间输入区不锁死、发送乐观气泡、已读明确触发与读边界单调）属于更大范围的目标态工作，已按 issue #468 拆入 U1/U2/U3，不在本 unit 内。

## 原始报告

报告人：Test User，在 iPhone 上日常使用原生客户端。来源是 iOS 体验审计（32 条问题，P0 8 / P1 16 / P2 8）及其修复路线第①步。当时记录的用户原话：

> 1. 启动后首屏长时间只有一个加载/“正在连接”，列表要等网络往返完成才出现。
> 2. 未读数点进会话后不清零 / 会“复活”。
> 3. 网络慢时发出的消息卡在输入框一段时间才进列表（输入区锁死、没有气泡）。

Agent 解读：这三条症状已随瘦身移交 U1（本地库与冷启动首绘）、U3（已读单调与多端）、U2（发送内核）；本 unit 只处理审计中同一路线第①步里「被丢弃的 Agent 占位消息在列表留下幽灵未读与空白预览」这一项。第 5 项在原立项中由 `gateway-relay.md` 的既有 Requirement 直接判定，不是新增产品决策。

证据边界：本文的现象与根因来自对当前 `main` 上 `apps/im-server/src/` 与 `docs/specs/im/` 的静态核对，以及该功能的引入/迁移提交；未运行服务、未做运行时复现，也未有设备上的观测记录。「多算 1 条」是代码路径推导出的必然后果，不是测量值。本文不能替代实施后的回归验证。

## 现象 / 复现

环境：IM 服务端 `apps/im-server`（Gateway 经 `/gateway` 流式事实写入）与原生 iOS 客户端。

复现步骤（静态可推导，未做运行时复现）：

1. 让一个 Agent 走一次「先建运行中占位消息、再判定不需要保留这条回复」的轮次。真实使用中常见的四种触发：PA 单线程的 NO_REPLY 静默、heartbeat 与自动轮次、模型失败、显式回复优先（前一条占位被随后的显式回复取代）。
2. 回到会话列表，观察该会话的未读数、预览与时间；再进入会话看消息气泡。
3. 断线重连、下拉刷新历史、让同一条消息被重复丢弃，再回列表观察。

用户可见的实际结果：

- 会话里的占位气泡不再出现——客户端按 `message.discarded` 事件移除了它，刷新历史也不会复活。
- 列表却仍按「这条消息存在」显示：未读比真实情况多 1（发送者自己除外），预览可能是被丢弃的正文、也可能是一片空白，时间停在那条已经不存在的消息上。
- 以上三点不会自愈：重复丢弃、断线重连、刷新历史都只保证「消息不复活」，列表投影仍是那条消息留下的值。用户无法通过任何界面操作把它纠正回来；只有该会话之后又来了新消息、把投影覆盖掉，才看起来"好了"。
- 未读是容易被误读的一项：用户会以为漏看了一条消息，点进去却什么都没有。预览为空时，会话在列表里像一条没有内容的条目。

## 根因

**写入侧：占位消息在创建时就改了列表投影。**
`apps/im-server/src/message-records.ts` 的 `MessageRecords.insert()` 在插入消息行的同一个方法里写了会话投影：`conversations.last_message_preview` / `last_message_at` 取自这条消息，`conversation_participants.unread_count` 对除发送者外的参与者加一。`apps/im-server/src/chat-streaming.ts` 的 `turn_start` 分支正是用这个 `insert()` 建 `running` 占位消息，所以占位从诞生那一刻起就已经是「会话里的最后一条消息」。

**丢弃侧：只删了消息行。**
同一文件 `apply()` 的 `message_discarded` 分支（`apps/im-server/src/chat-streaming.ts:64-65`）只有两步：`records.discard(m.id)` 与广播 `message.discarded`。`MessageRecords.discard()`（`apps/im-server/src/message-records.ts:98`）是一条 `DELETE FROM messages WHERE id=?`，没有回滚投影，也没有事务包裹——`gateway.ts` 的 `streaming()` 直接调用 `ChatStreaming.receive()`，整条路径不开事务（`insert()` 只在 interactive / personal_source 场景自行开事务）。因此删除消息行与写 tombstone 事件是两个独立的自动提交写。

**读取侧：缺的投影没有重算机会，只有回落。**
`apps/im-server/src/messaging.ts` 的 `conversation()` 用 `conversations.last_message_at` 去 `messages` 里找 `created_at` 相同的最新一条；消息行被删后这条查询为空，`preview` 于是回落到存储的 `last_message_preview` 原值，`last_message_at` 与 `unread_count` 根本不参与重算。所以「幽灵投影」不是暂时不一致，而是没有任何读取路径会把它修正——这解释了为什么刷新和重连都不自愈。

**为什么这种错能进来。**
该契约由 `8e90de7cb fix(im): discard NO_REPLY provisional messages` 引入。当时的 Python 实现在同一个事务里做完了四件事：删除 `running` 占位、按剩余最新消息重算 preview 与 `last_message_at`、把 `unread_count` 回滚（`MAX(unread_count-1, 0)`，并注释说明这是为了兼容「run 期间用户已经读过」）、写入无外键的 tombstone。TS 迁移（`ebd3411e4`，`gateway.ts` 中的旧 `message_discarded` 分支）只搬了「删除消息行 + 广播事件」两半，投影恢复留在被退役的 Python 实现里；后续 `39f159d9f` 把这段分支收进 `chat-streaming.ts` 时，形状照搬，缺的部分也没有被补回来。

迁移没有把这个缺口变成红灯，因为迁移前后都没有 IM 侧的回归断言：`8e90de7cb` 自带的测试只断言 Gateway 侧行为（发出 `message_discarded` 帧、静默回复不产生 peer relay），没有断言 IM 的会话投影；今天在 `apps/im-server/tests` 里 grep `discard` 只命中 3 处无关语义（`work-sync` 的未确认字节丢弃、`interactive-messages` 的保留既有结果、`onboarding` 的嵌套 api key），全仓没有 `message_discarded` 的服务端测试。契约只写在 `docs/specs/im/gateway-relay.md:157-165` 的 Requirement 与 Scenario 里，实现和用例两边都只覆盖了「气泡消失」这半边，而界面上恰好只看得出这半边——所以缺口在迁移中静默通过。

**修复必须保住的不变量（比"删了就减 1"更严）。**
契约要求投影恢复到这条消息出现前的状态，因此：

- `unread_count` 不能无脑减一：占位消息可能已被用户读掉（未读已是 0），也可能期间又来了其他真实消息。回滚只能针对这条消息自己贡献的那一份，且不能把其他消息造成的未读一起抹掉。
- preview 与 `last_message_at` 要按该会话剩余的最新真实消息重算；没有剩余消息时才回到空预览与该消息出现前的状态，不能重新覆盖成旧值。
- 其他参与者、其他会话的未读与预览不受影响；重复丢弃不得重复回滚（契约要求幂等）。现状第二次丢弃在消息查找处就会失败（消息行已不存在），这一半不在本 unit 范围，但补投影时不能把重复丢弃变成二次回滚。
- 既有丢弃语义不能削弱：仍然删除消息行、仍然广播 `message.discarded` 让在线客户端撤泡、刷新历史仍不复活。

**本 unit 边界。** 只改投影恢复，不改丢弃事件的形状、不改客户端撤泡逻辑、不重做消息与已读模型（那属于 issue #468 的 U3）。契约里同一句还要求「同一事务内留下可重放 tombstone、删除该消息的 message-scoped 过程事件」；现状是 tombstone 以 `message_id=null` 的事件写入（可重放），消息行删除后其过程事件仍留在 `conversation_events` 中。这与投影缺口同源（同样是迁移只搬了一半），但本 unit 不做扩展；实施时如发现残留事件会改变用户可见历史，回报后再决定是否单独立项。

## 修复

改动范围（4 个源文件 + 1 个新测试文件）：

- `apps/im-server/src/message-records.ts`：`discard()` 从「一条 DELETE」变为「删除消息行 + 恢复会话投影 + 回滚未读」。恢复前先读出被删消息的 `rowid` / `conversation_id` / `sender_user_id`；preview 与 `last_message_at` 按 `rowid DESC` 取**最后插入**的剩余消息——`insert()` 写投影用的就是它刚插入的那一行，而 ingress / 事件重放会用 `extra.created_at` 回填更早的时间，所以「这条消息出现前」是插入顺序而不是时间戳顺序（按 `created_at` 取最大值会把投影跳到一条已被后续插入覆盖过的旧行，且与该行的时间戳不符）。preview 沿用 `insert()` 的公式（`content.trim().slice(0,120)`，空正文回落到首个附件名），没有剩余消息时两项写 `NULL`（不是空串）。
- `apps/im-server/src/chat-streaming.ts`：`message_discarded` 分支把「删行 + 写 tombstone」包进一个 `transaction()`；tombstone 以 `publish=false` 写入，提交后再广播。
- `apps/im-server/src/messaging.ts`：新增 `publishCommitted(frame)`，只广播已提交帧、不重跑 wake 策略（wake 已在事务内的 `event()` 跑过一次）。
- `apps/im-server/src/gateway.ts`：把 `publishCommitted` 接进 `ChatStreaming` 的 ports。
- `apps/im-server/tests/discarded-message-projection.test.ts`：新增服务端回归测试（此前 `apps/im-server/tests` 无 `message_discarded` 覆盖）。

**`unread_count` 回滚方案与取舍。** 当前读模型不是计数器：`insert()` 对除发送者外的每个参与者 `+1`，而 `POST /read` 用 `COUNT(rowid > last_read_message_id AND sender != user)` 整体重算。因此无脑减一既会抹掉其他真实消息造成的未读，也会把已读过的减成负数。采用的规则用既有的已读水位，分两种参与者：

- 有可用水位（`last_read_message_id` 指向存在的最新已读消息，或就是被丢弃的这条）：按读模型同一公式重算 `COUNT(rowid > 水位 AND sender != user)`。对读过的人这是精确值，也能顺带修掉此前的漂移。
- 无可用水位（从未读过，或水位指向已不存在的消息）：`MAX(unread_count-1, 0)`，即历史实现的口径。对从未读过的人这是精确的，因为 `+1` 插入是他们的唯一来源。

取舍：真正「只回滚自己那一份」的精确实现需要记录「创建时给谁加过未读」的每消息账本（新表 + 与读模型重算同步），属于改消息/已读模型，超出本 unit。残余不精确只出现在一种窄场景：某参与者在占位消息创建之后才被拉进会话、此后未读过来、期间又有真实消息——该参与者的 `unread_count` 会被多减 1（下限 0）。历史实现同样如此，本 unit 不放宽也不扩大。

**事务边界。** 删除消息行、写 tombstone、恢复 preview/`last_message_at`/`unread_count` 都在 `chat-streaming.ts` 的同一个 `transaction()` 内（`gateway.streaming()` 本身不开事务，与 `insert()` 只在 interactive / personal_source 自开事务的现状一致）。广播刻意移到提交之后：回滚的丢弃不会先被播给在线客户端。tombstone 仍以 `message_id=null` 写入 `conversation_events`，因此断线重放照样可重放（`gateway.ts` 按 `event_id` 重放）。

**与既有丢弃幂等语义的关系。** 调用方仍在 `records.message(p.message_id)` 处对已删除消息失败（404），这一边界未改；`discard()` 内部再对「行已不存在」提前返回，确保即使将来有别的调用方重放，也只删一次、只回滚一次。

**无 spec delta。** `docs/specs/im/gateway-relay.md` 第 157-165 行的 Requirement/Scenario 已经写了同一事务内恢复三项投影，本 unit 只把实现补到契约上，不改 current spec。

**未做（照原边界回报）。** message-scoped 过程事件（`message.delta` / `thinking.segment` / `tool_call.*`）在消息行删除后仍留在 `conversation_events`，本 unit 不动。核对结论：历史接口从 `messages` 表读，tombstone 在事件流里位于这些事件之后且可重放，因此不会让气泡复活，也不改变用户可见历史；是否单独立项按原计划另议。

## 验证

先写测试并确认修前红灯（`npx vitest run apps/im-server/tests/discarded-message-projection.test.ts`，修前 4 条用例 3 failed / 1 passed；第 5 条插入顺序用例在实现过程中补入）：

1. 「丢弃后恢复到剩余消息」失败在 `unread_count` 1→期望 0、`last_message_preview` `""`→期望 `earlier real reply`、`last_message_at` 停在占位消息。
2. 「占位是唯一消息」失败在 `last_message_preview` `""`/`last_message_at` 非空，期望均为 `NULL`。
3. 「重复丢弃不回滚两次」失败在第二次丢弃后 `u2` 未读仍是 2（修前从未回滚，故也没被减）。
4. 「已读水位之后又来真实消息」修前即通过——它是防「无脑减一」改法的守卫，不是本 bug 的红灯。
5. 「时间戳非单调时回到上一次插入写下的投影」用于钉住 `rowid` 顺序：把实现临时换成 `created_at DESC` 后该用例失败（得到 `arrived first` / `2026-01-01`，期望 `backdated ingress` / `2025-12-01`），证明它确实在守这个选择。

修后同一命令 5 passed。测试驱动真实 `Gateway.handle('node.streaming_delta')` 与真实 Fastify 路由（`GET /im/v1/conversations/:id`、`POST .../read`、`GET .../messages`），断言 HTTP 投影、参与者未读、消息行与历史、`message.discarded` 广播帧，以及另一会话不受影响。

实跑命令与结果：

- `npx vitest run apps/im-server/tests/discarded-message-projection.test.ts` → 5 passed。
- 相关面扩查 `npx vitest run apps/im-server/tests/{discarded-message-projection,messaging,message-attempts,relay-delivery,watchdog,chat-contracts,conversation-query-hot-path,personal-disclosure,task-context-live,task-context-revocations,task-context-migration}.test.ts` → 11 files / 69 tests passed。
- 真实入口 e2e `npx vitest run apps/im-server/tests/e2e/{chat-boundaries,server,control-work}.test.ts` → 3 files / 9 tests passed。
- 全量 `npx vitest run apps/im-server/tests` → 380 passed / 20 failed；失败集中在 `interactive-messages`、`interactive-source`、`personal-representation`、`personal-sources`、`tenancy`、`e2e/trajectory` 六个文件，全部在改动面之外。用 `git stash` 只回退本次 4 个源文件后复跑同一批文件，得到相同失败（`interactive-messages` 14/14、`interactive-source` 2、`personal-representation` 1、`personal-sources` 1、`tenancy` 1），确认为本机环境既有红灯（interactive catalog 校验与未构建的工作区包），与本 unit 无关。
- 类型检查 `npx tsc -p apps/im-server/tsconfig.json --noEmit` 与 `-p tsconfig.contracts.json` 均只报一条既有错误 `src/trajectory.ts(109,46): Property 'initialBatch' does not exist`（依赖包 `lib/` 未构建的产物，非本次文件）。

既有丢弃语义回归：新测试同时断言消息行确实被删除、历史接口不再返回该消息、`message.discarded` 帧仍广播（含 `message_id` 与 `reason`）。
