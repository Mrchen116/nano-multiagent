# feat-716 设计审查（Gate 2）

## Round 1

- **reviewer**：独立 `change-design-reviewer`（本 unit 的 Gate 2 审查角色，不参与本 unit 的 spec/design 撰写）
- **review target**：`docs/changes/feat-716-interactive-background-one-shot/` @ `487724de5`（worktree `feat-715-integrated-bg`，branch `unit/feat-716`）
- **review_mode**：`full`（R1；无历史 Round）
- **mode_reason**：首次审查，需完整覆盖现状断言、决定、用户约束、delta、prototype 与 milestone；关键现状断言已在同一 tree 上逐条回核代码。
- **started_at**：2026-11-05T16:28:00+08:00 ／ **completed_at**：2026-11-05T17:05:00+08:00 ／ **duration**：约 37 分钟
- **Verdict**：**Changes requested**（Issues Found）—— **CRITICAL 1 ／ WARNING 6**

### 覆盖与证据

已核对并形成独立判断的范围：

| 覆盖面 | 证据 |
|---|---|
| 首文档 6 Requirements / 18 Scenarios、范围校准、非目标 | `spec.md` 全文（Requirement 头 6 处、Scenario 18 条，计数与 design 头部一致） |
| 决定 D1–D7、D9（D8 已撤销）与决策点 1–6 对应 | `design.md:99-171` |
| 中心派生谓词的**实际可写性** | 直接读 `apps/im-server/src/{messaging,interactions,message-attempts,message-records,personal-actions,schema.sql,conversation-actions,evaluation,context}.ts` 回核；`messages.sender_source_id`（`schema.sql:156`）、`pa_delegated_messages.representation_operation_id`（`:516-520`）、`interaction_drafts.updated_at/submission_message_id`（`:574-582`）、`message_interactive.read_only/superseded_by`（`:563-573`）、`conversations.dissolved_at`（`:51`）均存在 |
| 六类 owner-attributed 写点的排除方式 | `personal-actions.ts:243-244`+`message-records.ts:190-193`（代发必落 `representation_operation_id`）、`messaging.ts:396`（外部镜像带 `sender_source_id`）、`external.ts:352-353`（影子会话代发同带）、`task-context-access.ts:139`（`sender_type='system'`）、`conversation-actions.ts:315-336`+`interactions.ts:156-157`（fork 逐列复制、目标卡 `read_only=1`、草稿不复制、代发标记一并复制）、`evaluation.ts:39-62`（自建 `options.path` 隔离库） |
| 客户端的四条 iOS 登记点与 Web 两处 | `InteractiveRuntime.swift:71/82/100/286`（`select()` 唯一写点四处，实测）、`interactive-card.tsx:89`、`:199-202`、`:207-208`（`onParseResult` 无条件 `select`）——D6「原前提有误」成立 |
| 只渲染是否会写草稿 | `interactive-card.tsx:204-212`：`touched` 为假时 `select()` 后 `return`，不置 `dirty`、不 `save()`；`InteractiveRuntime.swift:98-100` 只在 `touched==true` 时 `changed()` → 「只渲染、不改动」在机制上可达 |
| 幂等/冻结与 attempt 顺序 | `messaging.ts:509-510`（attempt 命中在 `contexts()` 之前）、`:520-527`（`insertMessage`+`saveAttempt`+`enqueueRelays` 同一 `transaction`）、`message-attempts.ts:15-34` |
| 显式提交不与派生重复注入 | `sendInteraction` 只 `enqueueRelays(m,key)`，不派生；`interactions.ts:146-151` 提交时**不动** `updated_at`、`writeDraft` 置空 `submission_message_id`（`:107`）——派生侧 `submission_message_id IS NULL` + `updated_at > floor` 双判据自洽 |
| 四个 delta 文件的锚点与条目完整性 | `docs/specs/im/conversations-messages.md:549/571/581`、`docs/specs/im/ios-client.md:82`、`docs/specs/im/web-chat-ux.md:627`、`docs/specs/gateway/agent-capabilities.md:794` 全部存在；每条 MODIFIED 保留了 canonical 全部未改 Scenario（4/5/5/5 逐条比对） |
| delta 计数、索引、`agent-work.md` | 4 个文件均为「`## MODIFIED Requirements`」且合计 4 条 MODIFIED、0 ADDED、0 REMOVED，与 `design.md:381-388` 的声明逐行一致；`docs/specs/im/agent-work.md` 无 delta 文件、正文未改；Requirement 头未增删，`docs/specs/im/spec.md:22` 的 `32` 无需变 |
| 呈现侧是否有回潮 | 全文 grep `Work 详情/折叠/标签/trajectory/viewer/查看器/呈现`：命中项全部是「不改／按现状／预期行为」，**未发现**任何重新引入呈现改动的 Requirement、Scenario、决定或 milestone（D8 已撤销并明确 `packages/trajectory-ui` 不在范围） |
| 原型 | 实读 `prototype.html` 的 7 个状态与 `evidence/screens/{normal,blocked,saved,unconfirmed,narrow,both,ios}.png`；走查记录的「事实 → 判断 → 修正」与截图一致，未夸大（明确写了「未接后端」「未验证 409/真实失败」） |
| 文档完整性 | `../../.venv/bin/python scripts/docs_check.py` 通过（223 sources / 68 routes） |

现状断言的复核结论：`spec.md`「现状与依据」1–9 条与 `design.md`「涉及范围」「可复用能力」引用的行号、行为、写点数量**均与当前 tree 一致**（含 `message-pane.tsx:287/296-304/752-759/1259`、`interactive-card.tsx:89/199-202/114/118/226`、`InteractiveRuntime.swift:71/82/100/286/153/275-279`、`message-attempts.ts:15/32` 等）；仅两处细节偏差已单列入 Recommendations（`§D8 退出说明` 与「模型输入不变」是不存在的交叉引用；`wireContent` 统一 `trimmed` 是未写进契约的行为变化）。

### spec ↔ design ↔ delta ↔ milestone 追踪

| spec Requirement / Scenario | design 机制 | delta 落点 | milestone 判据 |
|---|---|---|---|
| R1 改动一张卡后发消息 | D1 中心派生 + D2 边界 + 谓词 `LIMIT 1` | conv-msg「改动一次只携带一次」 | M1-R① |
| R1 连续改动两张卡 | `ORDER BY d.updated_at DESC, m.rowid DESC LIMIT 1` | conv-msg「连续改动两张卡」 | M1-R② |
| R1 只渲染、不改动 | D6 删两端全部登记点 + `d.updated_at IS NOT NULL` | conv-msg「只渲染不改动」、ios「只打开、滚动…不产生背景」 | M1-W①、M2-R② |
| R1 同一张卡再改一次 | 单行草稿覆盖（无第二个写点） | 仅由「本人最近一次真实改动」措辞覆盖，**未单列 Scenario** | 无专属判据（R1-R6） |
| R2 连续两条消息 | `floor = max(本人最后一条消息, 水位)` | conv-msg「改动一次只携带一次」+「发问后继续操作与网络重试」 | M1-R① |
| R2 改动后刷新或重开 | D3（状态即草稿行） | conv-msg「刷新、重载与换设备后仍只携带一次」 | **无判据**（R1-W4） |
| R2 换设备继续 | D3 + 服务端为权威 | 同上 | M2-R⑥（受 R1-W1 水位语义影响） |
| R3 被更新版本取代 | `i.superseded_by IS NULL` | conv-msg「失效条件只清除这次携带」 | M1-R④、M1-W① |
| R3 变为只读 | `i.read_only = 0` | 同上 | M1-R④、M1-W① |
| R3 改动后切换会话 | D4 `discard(through)` 水位 | 同上（WHEN 含"用户离开该会话"） | M2-R③（iOS 侧受 R1-W2 影响） |
| R3 群聊永不携带 | 会话闸门 `type='direct'` + 既有 422 | conv-msg「私聊背景与群聊隔离」、gateway「群聊不读取私人操作」 | M1-R⑥ |
| R3 私聊背景不跨会话 | 谓词按 `cid` 隔离 | 同上 | M2-R③（部分覆盖） |
| R4 卡片内明确提交 | D5：提交消息推进 floor；`submission_message_id` 置位 | conv-msg 条目正文「明确提交…消费此前尚未发出的卡片改动」 | M1-R⑤ |
| R4 提交与另一张卡的改动 | 同上（floor 前移，不区分卡） | 同上 | M1-R⑤ |
| R5 结果未知后重试 | D7：attempt 命中在派生之前，派生冻结进 relay payload | conv-msg「发问后继续操作与网络重试」「同一发送身份携带不同快照」 | M1-W④、M2-W⑥ |
| R5 重试成功后继续对话 | 同上（冻结 + 单调 floor） | 同上 | M1-W④ |
| R5 改动后立刻发送 | D9 发送前 flush，失败不发 | web-chat-ux / ios-client「发送前卡片改动尚未保存」 | M2-R④ **仅失败分支**（R1-W4） |
| R6 同一旅程两端同结果 | D6 两端同删缓存 | ios-client 条目正文「客户端 SHALL NOT 自行选择、缓存或上报背景」 | M2-R①③⑥ |
| 不得回归 1–3（作者路由/群聊/幂等） | 路由不变、422 保留、指纹收敛但保留正文/附件 409 | conv-msg「同一发送身份携带不同快照」+AND | M1-R⑥、M1-W②④ |

结论：需求→机制→契约三段闭合，缺口集中在**失败与多端时序**（C1、W1–W3、W6）和**判据可验证性**（W4、W5）。

### Issues

#### R1-C1（CRITICAL）409 冲突下的拦截提示只有「重试保存」，该动作在实现上永远失败，输入区被卡住

`design.md:165`：

> 任一卡片仍有未保存改动或遇 409 冲突 → **不发送**，在输入框附近给出可操作提示（Web：`role="alert"` 行内条 + 「重试保存」；iOS：会话级 `ErrorNotice` + 重试）

但 409 的成因决定了「重试保存」不可能成功：`interactive-card.tsx:114` 只在保存**成功**时推进 `revision.current`，`:84` 只有 `load()` 会重新取服务端 revision；`:118` 遇 409 只把 `error` 置为 `'conflict'`，本地 `revision.current` 仍是服务端已拒绝的旧值。因此 `save()` 重试会带同一个 `expected_draft_revision` → 又一次 409。卡片自己为冲突准备的出口是 `:226`「读取最新」→ `load()`（会用服务端状态覆盖本地改动），而 D9 把这条失败搬到输入区后，输入区只有「重试保存」，且明确写着卡片内错误「不再承担拦截职责」（`design.md:357`）。

未修后果：本 unit 自己把 409 写成了常态场景（`spec.md:112-116` 换设备、`conversations-messages.md` 的「两台设备同时修改」），于是**用户在另一台设备改过同一张卡之后，这台设备的输入区永久发不出消息**：唯一给出的动作重复同一失败，「改动尚未保存 / 这次不会带上」的文案也没说明是"另一台设备赢了"，用户既无法发送也无法得知该怎么脱困（只能手刷页面并丢掉这次改动）。这属于「给出的补救路径不可实现」，且原型与 milestone 都没有覆盖（`evidence/prototype-walkthrough.md` 把 409 列为未验证；`design.md:436` 无对应判据）。

必须补：拦截态按失败原因分流——网络/5xx →「重试保存」；409 → 走既有 `load()`（「读取最新并继续」，可明确提示将放弃本机这次改动）或提供等价的显式放弃；并把 409 状态加进 `prototype.html` 与 M2 `[reviewer]` 第 4 条，补一条 worker 用例（stale revision → 提示 + 不发送 + 走通恢复）。

#### R1-W1（WARNING）discard 水位的取值与持久化没有定义到可实现的精度，多端语义会与「换设备继续」打架

`design.md:138`：

> body `{through?: string}`（ISO-8601，取该客户端**最后一次**草稿保存响应里的 `updated_at`）

`:144`：

> `through` 缺失（另一端编辑、本端无本地水位）按 `now()` 全清——与"切换会话即清除"的产品语义一致。

三点需要收口：

1. **取值不是「最后一次响应」而是「每会话当前最大值」。** 防抖保存下两张卡可能同时在飞（`interactive-card.tsx:204-212`），响应乱序到达时「最后一次」可能是较旧的时间戳；届时 `discard(through=较旧)` 只清掉旧的那次，用户刚改的另一张卡仍 `> 水位`，回到会话再发消息就会带上它——直接违反 `spec.md:129-131`「改动后切换会话」。`design.md:329` 的 `noteDraftSaved(cid, updatedAt)` 已按会话维度设计，应明确写「按会话取 `max`」。
2. **水位只存在内存里。** Web 侧未写持久化，刷新即丢；此后该会话任何一次 `discard` 都落入「`through` 缺失 → `now()` 全清」，D4 承诺的「迟到的 discard 只清 ≤ 那次改动、不会清掉用户回到该会话后的新改动」在刷新后不再成立。
3. **两条 Scenario 的优先级没有裁决。** `spec.md:112-116`（甲改、乙发 → 乙这条携带）与 `spec.md:129-131`（切走再回来 → 不携带）在"乙在新设备上打开→切走→回来→发送"这条正常路径上给出相反结论；当前设计用 `now()` 全清选了后者，却没有在任何一处说明这个取舍，也没说明是否要为「本端从未保存过的会话」禁用全清。负责人锁定的规则 4 只写"切换会话清除"，未写"任一端切换即清除全网"。

未修后果：worker 可以按任一读法实现，两端/多端行为不一致，且 verifier 无法从 spec 判断哪一结果算通过。

#### R1-W2（WARNING）iOS 切走时 `leave()` 的 flush 与 discard 的先后顺序未定义，会把「改动后切换会话」变成静默失效

`design.md:340`：

> 会话切换：`ChatStore.selectedID` 变更处（`ConversationView.swift:124`/`:146` 调用侧）对**离开的**会话调用 discard（带本地水位）

但 iOS 现成的离开钩子会**先写一次草稿**：`InteractiveRuntime.swift:275-279`

```swift
func leave() {
    saveTimer?.cancel(); queryTask?.cancel(); queryPoll?.cancel()
    // Finish the latest private edit; Session's generation still fences logout.
    Task { await flush() }
}
```

若 discard 在 flush 的 PUT 落地之前发出，`through` 必然早于这次新保存的 `updated_at`，派生得到 `draft.updated_at > 水位` → 背景在切走之后**存活**；用户回来一发消息就带上了本该被清除的改动。Web 侧相反（卸载即 `clearTimeout`、不保存），两端行为正好分叉。设计需要写明顺序（`await flush` → 记录水位 → `discard`），并落一条 iOS worker 用例；这与 D4「迟到 discard 不回退」是两个不同的窗口，不能互相替代。

#### R1-W3（WARNING）「不发送」的实际范围是整条会话，不是这一条消息，文案与代价没有对齐

`design.md:166` 只写「网络断时**这条消息**发不出去」。但 D9 的实现点是在 `commit()`/`ChatStore.send` 前 flush 所有已挂载卡片，因此只要该会话里有任意一张卡处于 dirty，「不发送」拦住的是这条会话的**所有**发送（包括与卡片毫无关系的追问），而 spec 非目标又禁止「是否仍要发送」的二选一（`spec.md:202`）。离线状态下「重试保存」也永远不会成功，用户只能等网络恢复。

未修后果：真实用户会遇到"我改了张卡、地铁里没信号，于是我连一句话都发不出去"，而设计文档的措辞让人以为只影响那一条。需要把范围写清（会话级）、把原型文案与之一致（当前 `blocked.png` 的标题是"这条消息没有发布"，与实现范围不完全一致），并在 Risks 表里显式承认这条代价（`design.md:392-401` 无此行）。

#### R1-W4（WARNING）三条验收没有可执行判据，M2 判据无法证明「刷新后仍携带」与「刚改完立刻发也携带」

`design.md:435-436` 的判据缺口：

- `spec.md:106-110`「改动后刷新或重开 → 携带」**无任何 `[reviewer]`/`[worker]` 条目**。M2-R② 只覆盖"刷新后不带"（没改动的情形），M2-R① 是"改→发→发"，M2-R⑥ 是换设备。而"刷新后仍携带"恰恰是"服务端派生、客户端不再持有状态"的最直接证据，缺了它，客户端残留内存状态也能让 M2-R① 通过。
- `spec.md:168-170`「改动后立刻发送」只被 M2-R④ 覆盖**失败**分支；`THEN 该消息仍然携带这次改动` 的成功路径没有判据。这条能"假通过"：flush 写旧值（保存失败但提示未触发）时，用户看到的仍是"发出去了、带了背景"，只是内容不是最后一次改动。
- `spec.md:95-97`「同一张卡再改一次 → 携带最后一次改动的完整状态」无判据；M1-R② 只验两张不同的卡。

建议：M2-R 补「改卡 → 刷新页面 → 发送：携带且内容为刷新前最后状态」，M2-R 补「改卡后 <500ms 内立刻发送：Work 里的注入内容是新状态而非上一次保存值」，M1-W 补「同一卡连续两次改动只产生一条背景、state 为合并后最终值」。

#### R1-W5（WARNING）派生候选 SQL 取不到第 4、5 步要用的字段，`agent_id`/`fields` 无法产出

`design.md:234-246` 的候选查询只 `SELECT d.source_message_id, d.updated_at, d.state_json, m.content`，但第 4 步要求「用既有 `interactionState`（`interactive-source.ts`）按**已保存 source** 校验 `state_json` 并取 `fields`」，第 5 步要求 `agent_id = 卡片执行 Agent`。`source`、`registry_json`、`executor_agent_id` 都在 `message_interactive` 与 `Interactions.source()` 里（`interactions.ts:15-23`，该方法是 public，seam 存在），当前 SQL 一行都没取。

未修后果：worker 要么补一条二次查询，要么另写一套 source 解析——后者正是设计明确要避免的"第四份判定"。请把查询扩到 `i.source, i.registry_json, i.executor_agent_id`（或直接调用 `interactions.source(id,cid)` 并说明用哪个），让「与现状 `interactions.ts:67` 完全一致」有落点。

#### R1-W6（WARNING）跨设备时序：另一端的防抖保存可能落在本条消息之后，把"已发送"的改动重新武装到**下一条**消息上

派生只读 `draft.updated_at` 与本人消息时间。当甲在 500ms 防抖窗口内改卡（`interactive-card.tsx:204-212`）、乙在这半秒内发出消息时：

1. 乙的消息到达 → `floor` 前移到 `T_msg`；
2. 甲的保存随后落地 → `draft.updated_at = T_save > T_msg`；
3. 这条消息**不带**背景（与 `spec.md:112-116` 期望相反），而且该改动在此后**仍然待发**——乙的下一条消息会带上一段用户认为"已经发过了"的旧状态。

这正是本 unit 要消灭的症状，但 `design.md:392-401` 的风险表没有这一行，`D3` 还把它说成"D1 的直接结果、不需要任何客户端状态"。不要求消灭这个窗口（跨端无锁无法消灭），但必须：把它写进风险表并说明可接受窗口（防抖 + 一次 RTT）、说明"迟到的保存会让改动落到下一条消息"是已知代价，并让 M2-R⑥（换设备）的验收口径包含"先等甲保存完成"。

### Recommendations

- **R1-R1**：`design.md:28` 的「见 §D8 退出说明与「模型输入不变」」是失效交叉引用——D8 已是"（已撤销）"，全文也没有名为「模型输入不变」的小节。建议改为指向 §Context 影响 的「组装：不变」与 D8 段。
- **R1-R2**：新增表 `interaction_background_discards` 未写外键/级联。ER 图已画 `conversations ||--o{ …`，建议补 `FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE`，并说明会话删除/解散后水位行的去向（`conversations.dissolved_at` 已在谓词里闸门，但行会残留）。
- **R1-R3**：`design.md:328` 把 `wireContent` 统一改成 `trimmed` 说成"删掉 contexts 后行为更一致的副作用"。这是唯一的剩余分支，写测试固定没问题，但它确实改变了"带背景那条消息"的正文首尾空白（`message-pane.tsx:761` 现状是 `contexts.length ? text : trimmed`）。要么在 delta 里不提（属于不可观察的极小差异），要么一句话说明取舍，不要用"副作用"带过。
- **R1-R4**：`design.md:220` 的派生入口只写 `pending(user, cid)`，未说明调用点只对人类发送生效。`messaging.ts:481` 的 `send()` 同时服务 gateway 身份（`p.kind==='gateway'`），建议显式写「仅 `p.kind !== 'gateway'` 时派生」，否则 worker 会用一个非人类身份去查 `sender_user_id`。
- **R1-R5**：`design.md:287-288` 的 `discard` 表格自相矛盾：非 direct 会话返回 `204 空操作`，但响应行写 `{discarded_through: string}`。请统一（建议非 direct 也返回当前水位或统一 204+空 body），并说明客户端把「会员资格 404」也并入"旧服务端静默忽略"是否有意。
- **R1-R6**：delta 侧建议补一条「同一张卡再改一次」的 Scenario（当前只有措辞覆盖），并在此处显式记录：spec 的 5 条失效 Scenario 在 delta 中合并为 1 条「失效条件只清除这次携带」——合并是有意的，避免归并后丢失逐条件的可核对粒度。

### 必须在实施前修改

1. **R1-C1**：409 拦截态必须有能成功的出口（走 `load()` 或显式放弃），并补原型状态、M2 `[reviewer]` 与 worker 用例。
2. **R1-W1**：写清 discard 水位 = 每会话 `max`、是否持久化、`through` 缺失时的行为，并裁决 `spec.md:112-116` 与 `:129-131` 在多端切换路径上的优先级。
3. **R1-W2**：写清 iOS 切走的顺序（flush → 记录水位 → discard）并落测试。
4. **R1-W5**：补全派生候选查询（source/registry/executor 或改用 `Interactions.source()`）。
5. **R1-W3、R1-W4、R1-W6**：可在同一轮修订中一并处理（范围措辞、三条判据、风险表新增一行）。

以上第 1–4 项属实质设计变化，修订后需要一轮复审（建议 `delta` 模式，核对上述四处与判据补全）。

## Author Resolutions

- **responder**：本 unit 设计作者（`change-design-author`，未参与 Round 1 审查）
- **响应目标**：Round 1 的 1 CRITICAL / 6 WARNING / 6 Recommendations（`487724de5` → 本轮修订，同 worktree `feat-715-integrated-bg`、同 branch `unit/feat-716`）
- **修订性质**：只改文档与原型（`design.md`、`spec.md`、3 个 im delta、`evidence/prototype-walkthrough.md`、`prototype.html`）；无实现代码改动、无 push。Round 1 原文保留在上面，未改写。
- **结论**：C1、W1–W6、R1–R6 全部处理；其中 R1-R3 按建议的第二个选项（写明取舍、用测试固定，不写进 delta 契约）。**无一条以“不修”收口**；仍存在的代价（会话级拦截、409 放弃本机改动、跨设备防抖窗口）都是显式写进 §风险与回退 的已知取舍，不是遗漏。
- **校对**：`../../.venv/bin/python scripts/docs_check.py` → `documentation integrity passed: 224 maintained Markdown sources, 68 required routes`（224 = Round 1 记录的 223 + Round 1 之后新增的 `design-review.md` 本身；本轮未新增文档）。

### 逐条响应

| 编号 | 状态 | 落点 |
|---|---|---|
| R1-C1 | **CLOSED** | §D9「按失败原因分流」+ conflict 两动作；§前端原型（新增 409 状态与对齐契约行）；`prototype.html`（`conflict` / `conflict-diff` / `conflict-adopted` / `iosconflict` / `iosconflict-diff`）；M2 `[reviewer]` ④(b)、`[worker]` ② |
| R1-W1 | **CLOSED** | §D4 全节重写（水位 = 每会话 `max` + 持久化 + 缺失 no-op + 跨设备优先级表）；`spec.md:129-131` 补一条 AND；M2 `[reviewer]` ⑥、`[worker]` ④ |
| R1-W2 | **CLOSED** | §客户端改动要点 iOS 第 3 条（`await flush` → 水位 → discard，串行，10s 超时按失败）；`specs/im/ios-client.md`；M2 `[worker]` ⑤ |
| R1-W3 | **CLOSED** | §D9 第 1 条（范围：会话级）+ 两端文案；§风险与回退 新增「会话级拦截的代价」行；`prototype.html` 标题改为“这个会话暂时不能发送”、正文补会话范围；`specs/im/web-chat-ux.md`、`specs/im/ios-client.md` |
| R1-W4 | **CLOSED** | M2 `[reviewer]` ⑦（刷新后仍携带且为刷新前最后状态）、⑧（<500ms 立刻发送的成功路径）、⑨（同一张卡改两次）；M1 `[worker]` ⑥ |
| R1-W5 | **CLOSED** | §派生谓词 第 4 步改为 public 缝 `Interactions.background(user, cid, sourceMessageId, stateJson)`，缝内复用 `source(id, cid)` + `interactionState`（不再二次查询、不写第四份判定）；M1 `[worker]` ⑦ |
| R1-W6 | **CLOSED** | §风险与回退 新增「跨设备时序」行（可接受窗口 = 500ms 防抖 + 一次 RTT，写明“迟到保存会落到下一条消息”）；M2 `[reviewer]` ⑥ 口径改为“先等甲的未保存提示消失” |
| R1-R1 | **CLOSED** | `design.md:28` 交叉引用改为 §Context 影响 的「组装：不变」+ §D8（已撤销） |
| R1-R2 | **CLOSED** | §持久化形态：`FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE`、`user_id` 同样级联；说明解散（`dissolved_at`）不清行、真删除/fork 源删除由级联清；ER 图同步 |
| R1-R3 | **CLOSED**（按建议选项二） | §客户端改动要点 Web 第 1 条：明写 `wireContent` 统一 `trimmed` 是**可见但极小**的差异，不作为契约写进 delta，M2 用测试固定；M2 `[worker]` ③ |
| R1-R4 | **CLOSED** | §派生谓词 第 0 步：只在该 `p.kind === 'user'` 的普通文字发送中调用，gateway/agent 凭据（含 PA 代发、外部镜像、`external.ts:353`）不派生；M1 `[worker]` ⑧ |
| R1-R5 | **CLOSED** | §`discard` 路由表重写：direct → `200 {discarded_through: string \| null}`、非 direct → `204` 空 body、`through` 缺失/非法 → `204` no-op（不写水位）、404/501 一律静默忽略（并说明会员资格 404 同属“旧服务端/不可写”而不弹错、不本地标记已清除）；客户端水位只由保存成功响应推进 |
| R1-R6 | **CLOSED** | `specs/im/conversations-messages.md` 新增 Scenario「同一张卡再改一次」；§契约层增量 记录“5 条失效 Scenario 合并为 1 条是有意的”；M2 `[reviewer]` ⑨、M1 `[worker]` ⑥ |

### 关键改动的实际写法（供复审直接对照）

**D4 水位语义**：`through` = 该客户端在该会话内**所有草稿保存成功响应中 `updated_at` 的最大值**（每会话单调不回退，不是“最后一次响应”）；持久化在按账号隔离的 IndexedDB（键 `(accountId, conversationId)`，最多 128 条，登出/切服务清除）；`through` 缺失 → 客户端不发、服务端 no-op（**不再** `now()` 全清）。跨设备优先级裁决（原 `spec.md:112-116` 与 `:129-131` 的冲突）落成四行表：甲改未发 → 乙新设备打开直接发 = 携带；乙打开又切走 = 仍携带；甲自己切走 = 不携带；甲乙都改、乙保存后乙切走 = 不携带（覆盖甲的更早改动）。清除权限归“做过这次改动的那一端”，`spec.md` 只加一条 AND，Requirement/Scenario 数不变。

**D9 冲突分支的最终文案**（Web 与 iOS 同义，容器各自沿用）：

- transient 标题：「卡片改动尚未保存，这个会话暂时不能发送」
- transient 正文：「先保存「会议安排」的改动再发送，否则这条不会带上你刚改的周四和参会人；同一会话的其他消息也要等它保存好。」+ 离线追加「当前网络不可用，恢复后会自动放行。」
- conflict 标题：「另一台设备更新了这张卡片，这条消息没有发出」
- conflict 正文：「「会议安排」的草稿在另一台设备上改过；本机这次改动还没保存，所以这条不会带上它。」
- conflict 动作：「查看最新改动」→ 展开「字段 / 另一台设备 / 我这台」只读对比 → 出现「改用最新草稿（会放弃本机这次改动）」→ 调既有 `load()`
- 两类同时存在 → 冲突优先；冲突解决后 transient 卡片仍走「重试保存」

冲突态**不提供**「重试保存」（旧 `expected_draft_revision` 必然再 409），也**不自动合并**（服务端草稿是整份 state，缺逐字段因果，合并结果无法解释也无法验收）；点「改用最新草稿」之前本机编辑、输入正文与提示都保留。

### 作者主动补充（不在 Round 1 条目内）

- `prototype.html` 的留证画面从 7 张扩到 13 张：状态机新增三个（离线、409 冲突、iOS 409），另用 `?state=conflict&diff=1`、`?state=saved&card=other&note=adopted`、`?state=iosconflict&diff=1` 复现“展开只读对比”与“改用最新草稿之后”（`&card=other` 让卡片显示另一台设备已保存的版本）。「查看最新改动 → 改用最新草稿」是可点的两步。iOS 的采用按钮标签同样补全为「改用最新草稿（放弃本机这次改动）」，对比表 caption 写“不会自动合并”，避免 `may-adapt` 变成丢掉“明确放弃”这条语义。
- `design.md §前端原型` 同步：状态清单、交互边界、原型对齐契约新增 409 一行（must-match，Web 1280）、原型走查范围改为“十个状态 + iOS 三态”。
- `evidence/prototype-walkthrough.md` 重写：截图表 13 行（路径仍只用反引号，不建图片链接）、新增“409 只有不可成功的出口”“文案把会话级说成单条”“离线不假装能重试”“放弃必须显式”“iOS 也不能省掉放弃语义”五条“事实 → 判断 → 修正”，`未验证` 改为“409 已按状态开关演示，但仍无真实请求、无旧 revision、无两步之间的服务端变化”。

### 复审建议

按 Round 1 的建议走 `delta` 模式，重点四处：①§D9 冲突分支与 §前端原型/原型的对应（C1）；②§D4 水位取值、持久化、缺失 no-op 与四行优先级表（W1）；③iOS `leave()` 顺序（W2）；④`Interactions.background()` 缝与 §派生谓词 第 0/4 步（W5）。判据侧只需核对 M1 `[worker]` ⑥⑦⑧、M2 `[reviewer]` ④(b)⑥⑦⑧⑨ 与 M2 `[worker]` ②④⑤ 是否真的能证伪对应结论。

## Round 2

- **reviewer**：同一独立 `change-design-reviewer`（继续持有 Round 1 证据，不参与本 unit 撰写）
- **review target**：`7c7dda7c7`（`15cecd531` → `7c7dda7c7`，改动仅文档与原型：`design.md`、`spec.md`、3 个 im delta、`prototype.html`、`evidence/prototype-walkthrough.md`、本报告追加）
- **review_mode**：`delta`
- **mode_reason**：作者只修订 Round 1 点名的位置（C1、W1–W6、R1–R6），未改需求、未改派生核心边界、未改 milestone 结构；本题按派发要求只核四处修订（C1／W1／W2／W5）+ 判据可证伪性 + 残留代价表述，其余项引用 R1 证据。范围扩大处：核对 §派生谓词 第 0 步（W5 修订引入的新内容）与四处修订是否引入新矛盾。
- **started_at**：2026-11-05T17:06:00+08:00 ／ **completed_at**：2026-11-05T17:30:00+08:00 ／ **duration**：约 24 分钟
- **Verdict**：**Changes requested**（Issues Found）—— **CRITICAL 1 ／ WARNING 2**

### 覆盖与证据

| 核对面 | 结论与证据 |
|---|---|
| C1 契约与原型一致 | **一致**。`design.md:177-187`（分流 + 两动作 + 文案）、`specs/im/web-chat-ux.md`「发送前草稿在多端冲突」、`specs/im/ios-client.md`「发送前草稿在多端冲突」三处逐句对应；`prototype.html:302-326`（Web 两段 alert、`web-adopt` 默认 `hidden`）、`:375-390`（iOS 同构）与实读截图 `conflict.png`（只有「查看最新改动」、无「重试保存」）、`conflict-diff.png`（字段／另一台设备／我这台 三列 + 采用按钮此时才出现）一致；`conflict-adopted.png` 存在 |
| C1 旧 revision 必然再 409 是否被真正堵死 | **是**。冲突分支不再提供「重试保存」（`design.md:180`），唯一出口是 `load()`（`:182` → `interactive-card.tsx:84` 取回服务端 revision），与 `interactive-card.tsx:114`（只在成功时推进 revision）的现状机制相容；iOS 侧本来就有 `InteractiveRuntime.retryContent()`（`:280-282` 冲突时 `load()`）可复用 |
| C1 冲突态保留正文与卡片状态 | **是**。`design.md:184` + 两个 delta 的「在用户明确放弃本机改动之前，正文、卡片状态与提示都保留」；原型 `conflict-diff.png` 里输入框正文与卡片「周四 14:00」仍在，采用按钮标签写明“会放弃本机这次改动” |
| W1 水位取值/持久化/no-op | **成立**。`design.md:138-156`：`max` 而非“最后一次响应”、IndexedDB `(accountId, conversationId)` 持久化 + 128 上限 + 登出清除、`through` 缺失 → 客户端不发且服务端 204 no-op；`discard` 路由表（`:307-318`）与 D4 不再互相矛盾（direct `200 {discarded_through: string|null}` / 非 direct `204` / 缺失 `204`） |
| W1 no-op 是否可观测 | **是**。它被写成可核对行为（“另一台设备切走不清除”→ 该会话下一条消息仍携带），并由 `spec.md:132` 新增 AND + `specs/im/conversations-messages.md` 失效 Scenario 的 AND + M2 `[reviewer]` ⑥ 口径共同承载，不是静默 |
| W1 优先级表是否真能由机制落地 | **能**。同一账号多端共用一行 `interaction_drafts`（PK `(source_message_id, user_id)`，`schema.sql:574-582`），四行结论与 `floor = max(本人最后一条消息, 水位)` 推导一致；行 2（乙无水位切走 → 仍携带）由“无水位不发请求”直接得到，行 3/4 由 `through` 单调 MAX 得到 |
| W2 顺序与超时语义 | **顺序成立**（`design.md:376-380`：`await flush()` → 水位 `max` → 有水位才 `discard`；`selectedID` 切换不等待任务）。**超时语义有漏洞**，见 R2-W2 |
| W2 iOS worker 用例能否证伪 | `src/IM/ios/Tests` + `NanoIMTests` target 存在（`ChatStateTests.swift`、`SendRecoveryTests.swift` 等），M2 `[worker]` ⑤ 的“`leave()` 顺序 = flush → 水位 → discard”可用 spy 断言，**可证伪**；但它只能证伪顺序，不能证伪 R2-W2 的迟到落库 |
| W5 是否只复用 public 缝 | **是**。`Interactions.source(id,cid)` 是 public 且 `SELECT i.*`（含 `source`／`registry_json`）+ `COALESCE(...) executor_agent_id`（`interactions.ts:15-23`），`interactionState()` 是模块级导出；`background()` 不新增状态源、不二次查询，与现状 `contexts()`（`:59-70`）同一套字段与 160 字符截断 |
| W5 派生第 0 步（新增内容） | **有致命错误**，见 R2-C1 |
| 判据可证伪性（M1 W⑥⑦⑧、M2 R④(b)⑥⑦⑧⑨、M2 W②④⑤） | M1 W⑥⑦、M2 R④(b)⑥⑦⑧⑨、M2 W②③④⑤ 逐条都能落成“会失败的测试/SQL 断言/真栈观察”；**M1 W⑧ 会把错误谓词固化成测试**（R2-C1）；M2 W② 缺客户端缝（R2-W1） |
| Risks 三条残留代价是否写清 | **写清了**（`design.md:445-447`）：会话级拦截（含“离线时一句话也发不出去”）、409 需放弃本机那版、跨设备防抖窗口（含“迟到保存会落到下一条消息”）；与之配套的文案（“这个会话暂时不能发送”“会放弃本机这次改动”）在原型里能看到，不再停留在机制描述 |
| 契约卫生 | `spec.md` 仍 6 Requirement / 18 Scenario（新增的是 AND）；4 个 delta 仍 0 ADDED / 4 MODIFIED / 0 REMOVED，`conversations-messages` 3 条（17 Scenario，含新增「同一张卡再改一次」）、`ios-client` 1 条（7）、`web-chat-ux` 1 条（6）、`agent-capabilities` 1 条（3），与 `design.md:427-431` 的声明一致；`im/agent-work.md` 仍无 delta；`im/spec.md` 计数不变 |
| 呈现侧零改动 | 新增内容全部在 composer 拦截提示与客户端水位，未出现任何 Work 详情/折叠/标签/trajectory/viewer 的改动项；`packages/trajectory-ui` 仍在范围外 |
| 文档完整性 | `../../.venv/bin/python scripts/docs_check.py` → `documentation integrity passed: 224 maintained Markdown sources, 68 required routes` |

### 历史问题闭环

| 原编号 | Author Resolution | 本轮证据 | 状态 |
|---|---|---|---|
| R1-C1 | 409 分流 + 两动作 + 原型/M2 判据 | 见上表 C1 三行；契约/原型/判据三处一致 | **closed**（残余：客户端缝 → R2-W1；冲突文案仍写“这条消息”→ R2-R1） |
| R1-W1 | 水位 `max` + 持久化 + 缺失 no-op + 四行表 + `spec.md` AND | `design.md:135-156`、`spec.md:132`、delta AND、M2 R⑥（“等甲的未保存提示消失”） | **closed**（残余限制见「已知且接受的限制」第 4 条） |
| R1-W2 | iOS 串行 flush → 水位 → discard + 10s 超时 | `design.md:376-380`；`InteractiveRuntime.swift:275-279` 与 `:265-266`（`conflict` 区分）确为所引用写点 | **保留（部分）** → R2-W2：顺序对，超时分支的理由不成立 |
| R1-W3 | 会话级范围写入 D9/文案/两个 delta/Risks | `design.md:176`、`:187`、`:446`；`blocked.png` 标题 | **closed**（残余：conflict 文案仍是单条口径 → R2-R1） |
| R1-W4 | 新增 M2 R⑦（刷新）⑧（<500ms 成功路径）⑨（同卡改两次）+ M1 W⑥ | `design.md:483`；三条都能用“Work 轨迹内容 vs 期望状态”证伪 | **closed** |
| R1-W5 | public 缝 `Interactions.background()` + 第 4 步改写 | `design.md:247-273`、`interactions.ts:15-23` | **closed** |
| R1-W6 | 跨设备时序写入 Risks + M2 R⑥ 口径 | `design.md:445`、`:483` R⑥ | **closed** |
| R1-R1 | 交叉引用改为 §Context 影响「组装：不变」+ §D8 | `design.md:28` | **closed** |
| R1-R2 | 新表 FK + 级联 + 解散说明 | `design.md:194`（FK 级联说明）、ER 图 `:212-216`、M1 W③ | **closed** |
| R1-R3 | `trimmed` 明写为可见极小差异 + M2 W③ 固定 | `design.md:355` | **closed** |
| R1-R4 | 「只人类发送派生」 | **应用错误**：写成 `p.kind === 'user'`（R1 建议原文是 `p.kind !== 'gateway'`），见 R2-C1 | **still open** → R2-C1 |
| R1-R5 | 路由表重写（200/204/no-op/404 静默） | `design.md:307-320` | **closed** |
| R1-R6 | delta 新增「同一张卡再改一次」+ 合并说明 | `conversations-messages.md:43-47`、`design.md:421` | **closed** |

### Issues

#### R2-C1（CRITICAL）派生入口写成 `p.kind === 'user'`，实现后所有真实人类发送都不会派生——功能整体静默失效

`design.md:247`：

> 0. **调用点**：只在 `messaging.send()` 里、`p.kind === 'user'`（人类 JWT）的**普通文字发送**中调用

同一错误被写进判据 `design.md:482`（M1 `[worker]` ⑧「派生入口只在 `p.kind === 'user'` 生效」）。

事实：人类 JWT 主体的 `kind` 是 **`undefined`**，不是 `'user'`。`messaging.ts:86-90` 的 `principal()` 只给 gateway 补 `kind: "gateway"`，人类走 `identity.authenticateRequest()` → `identity.ts:345-356` 返回 `users` 行（`id/username/display_name/owner_id/created_at/membership_status`，无 `kind`）；`sendMessage`（`messaging.ts:473-479`）只做 `sendPrincipal(actor)` 的类型收敛（`message-input.ts:5` 的联合类型是 `{kind?:'user';…}`，因此 `p.kind === 'user'` 在 TS 里合法、编译期不会报错）。`send()` 自身识别人类用的正是 `p.kind !== 'gateway'`（`messaging.ts:482`、`:484`）。

后果：按设计原文实现，`pending()` 对每一次真实发送都提前返回 `null` → R1「改动一张卡后发消息」、R2「携带一次即消费」、R6「两端同结果」全部变成“永不携带”，而服务端测试可以照样全绿：M1 W⑧ 会照着设计构造一个 `{kind:'user'}` 的合成 fixture 并断言“派生已发生”，这个断言的通过恰好掩盖了生产里 `kind` 为 `undefined` 的事实。这正是“判据能通过而用户可见行为是错的”。

必须改成与既有代码同一谓词：`p.kind !== 'gateway' && !p.username?.startsWith('agent:')`（`contexts()`／`writeDraft` 的现有写法，`interactions.ts:60`、`:100`），并让 M1 W⑧ 用**真实形状**的两类主体断言（`principal()` 产出的无 `kind` 用户行 → 派生；gateway 行 → 不派生），或直接把人类判定抽成一个被 `contexts()` 与派生共用的 helper。

#### R2-W1（WARNING）Web 冲突分支缺客户端缝：composer 拿不到“我这台”的本地状态，也没有触发卡片 `load()` 的入口

`design.md:361` 列出的注册表 API 只有 `registerDraftFlusher/unregister`、`flushInteractionDrafts`、`noteDraftSaved`、`discardOnLeave`、`awaitPendingDiscard`、`pendingDraftFailure`；而 `:181` 要求「与本机编辑做**字段级**对比」、`:368` 要求「调卡片 `load()`」。`state.current`、`revision.current` 都是 `interactive-card.tsx` 组件内部状态（`:83-84`、`:114`），`load()` 也是组件内函数（`:86-96`）；`pendingDraftFailure(cid)` 只给 `{reason, 卡片 id}`。iOS 侧不同（`InteractiveRuntime` 是对象，`retryContent()`/`load()` 可直接调，`:280-282`），所以这个缺口只落在 Web。

后果：M2 `[worker]` ② 要求“渲染三列对比、点「改用最新草稿」调用 `load()` 并清提示”，但没有缝就无法按设计写这条测试；worker 要么把 `readInteractionDraft` 的结果当成“我这台”（错，那是另一台），要么临时发明一条未记录的通路，两种都会让“显示本机那版”失真——而“先看清将放弃什么”正是 C1 修订的全部意义。

建议一行补全：注册表条目从 `flush` 扩展为 `{flush, describeConflict(): {localState, revision} | null, adoptRemote(): Promise<void>}`（后者内部调既有 `load()`），并让 M2 W② 断言这两点由注册表提供。

#### R2-W2（WARNING）iOS 超时分支的理由不成立：flush 超时后草稿仍可能落库，切走时背景会存活

`design.md:380`：

> 4. flush 超时（例如 10s）按失败处理，仍用上次水位发 discard（服务端草稿的 `updated_at` = 上次水位，`updated_at > 水位` 不成立，仍会被清除——这是有意的：切走即清除本端草稿）。

括号里的前提只在“PUT 从未到达服务端”时成立。超时是**客户端**放弃等待，请求可能已被服务端执行（`writeDraft` 是独立事务，`interactions.ts:105-112`）；此时服务端 `updated_at = T_new > 水位`，而 discard 已用旧水位发出 → 派生 `draft.updated_at > floor` 成立，**背景在切走后存活**，用户回来发消息就会带上——与 R1-W2 完全同一类用户可见后果，只是窗口更窄（10s 超时 + 响应丢失）。

M2 `[worker]` ⑤ 只断言“顺序 = flush → 水位 → discard、超时同失败”，会**通过**而掩盖这一条，属于“判据通过但行为错”。

建议（与已选语义自洽、也最省）：把“晚到的保存成功”纳入 D4 的迟到处理——该端在离开后如果收到某张卡的保存成功（前台重试、重连后补齐），用新的 `updated_at` **补发一次 `discard(through=新水位)`**（做过这次改动的仍是这一端）；或至少按 R1-W6 的方式在 Risks 表显式记这条窗口，并让 M2 W⑤ 覆盖“超时后迟到成功 → 补发 discard”。

### Recommendations

- **R2-R1**：`design.md:187` 与 `prototype.html` 的冲突标题仍是「这条消息没有发出」，但冲突同样拦住该会话全部发送（D9 已确定会话级）。建议与 transient 对齐为“这个会话暂时不能发送”，否则用户点第二条消息时又会被同一句“这条消息没有发出”困住。
- **R2-R2**：`design.md:447` 说 409 风险由「M2 `[reviewer]` ⑦ 覆盖」，但 ⑦ 现在是“改卡→刷新页面→发送”，409 的判据是 ④(b)。改掉这处编号漂移，避免验收时按错误条目取证。
- **R2-R3**：`evidence/prototype-walkthrough.md` 的 `conflict.png` 里卡片底部仍画成「草稿暂未保存。重试」；真实产品在该状态是 `error='conflict'`，卡片内动作是「读取最新」（`interactive-card.tsx:226`）。原型作为“现状底色”可以保留，但建议在走查里加一行说明，免得下游 reviewer 以为冲突态下卡片内也有一个会再次 409 的重试入口。
- **R2-R4**：`design.md:375` 引「`conflict` 已在 `:269` 区分」，实际区分在 `InteractiveRuntime.swift:266`。顺手校正，避免 worker 按行号找不到写点。

### 已知且接受的限制（本轮确认，非阻断）

1. **会话级拦截**：任一卡片改动未保存成功，该会话所有发送被拦；离线时一句话也发不出去，直到保存成功。已写入 D9、Risks、两个 delta 与原型文案。
2. **409 需显式放弃本机那版**：不自动合并，需要本机版本的用户要在卡片上重改一次；放弃前正文与卡片状态保留。
3. **跨设备防抖窗口**：可接受窗口 = 500ms 防抖 + 一次 RTT；迟到保存会落到该端下一条消息（Risks 已记，M2 R⑥ 口径为“等甲的未保存提示消失”）。
4. **水位 128 条上限**：被淘汰会话的“切走清除”退化为“该端没有水位 → 不清除”。实际影响极小（用户刚落过改动的会话总会被刷新成新行），但 `spec.md:129-131` 在该会话不再有绝对保证。
5. **`through` 缺失 → no-op**：把“另一台设备的切走不清除”固化为产品语义（`spec.md:132` 的 AND）。这属于对“谁来清除”这一未指定跨设备情形的澄清，不改规则 4 在单设备路径上的结论，因此不算重开已锁定规则。
6. **`wireContent` 统一 `trimmed`**：可见但极小的正文首尾空白差异，已写明并由 M2 W③ 固定。
7. **原型保真度**：卡片内错误行在 409 状态仍按 `save` 文案绘制（见 R2-R3）；原型不产生真实请求，不证明携带/清除语义。

### 必须在实施前修改

1. **R2-C1**：`design.md:247`（第 0 步）与 `design.md:482`（M1 W⑧）改为既有的人类判定谓词，并用真实主体形状断言。
2. **R2-W1**：`design.md:361`／`:368` 补全 Web 注册表的冲突缝（`describeConflict` + `adoptRemote`），M2 W② 同步。
3. **R2-W2**：`design.md:380` 改正超时前提，并给出迟到保存成功的补发 discard 路径（或按 R1-W6 记入 Risks + M2 W⑤ 覆盖）。

以上三项都是可在一轮内收口的小改动，不改变本 unit 的需求、派生核心边界与 milestone 结构；修订后建议再走一轮 `closure` 复审。

## Round 3 (closure)

- **reviewer**：同一独立 `change-design-reviewer`（继续持有 Round 1/2 证据，不参与本 unit 撰写）
- **review target**：`6cd674b5b`（`c30a3f22a` → `6cd674b5b`，改动仅 `design.md`、`prototype.html`、`evidence/prototype-walkthrough.md`，3 文件 +59/−30；本报告此前未动）
- **review_mode**：`closure`
- **mode_reason**：作者只修订 Round 2 点名的三条必改与四条 minor，未改需求、派生核心边界、delta 与 milestone 结构。本轮只核三条必改、四处 minor、以及修订本身引入的新矛盾。新增共享契约字段按派发要求单独判定（是否必须、是否破坏边界、默认关闭是否真能保证模型输入不变），不因它落在既有 milestone 内就默认放行。
- **started_at**：2026-11-05T17:46:00+08:00 ／ **completed_at**：2026-11-05T18:03:00+08:00 ／ **duration**：约 17 分钟
- **Verdict**：**Changes requested**（Issues Found）—— **CRITICAL 1 ／ WARNING 3**

### 覆盖与证据

| 核对面 | 结论与证据 |
|---|---|
| R2-C1 判据 | **成立**。`design.md:258` 改为 `p.kind !== 'gateway' && !p.username?.startsWith('agent:')`，与 `interactions.ts:60`、`:92`、`:100`、`:117` 四处“人类查看者”闸门逐字同款 |
| R2-C1 理由逐条核实 | **成立**。`SendPrincipal` 人类分支是 `{kind?:'user';id;username}`（`message-input.ts:5`，`kind` 只是可选字面量）；`principal()` 只在 gateway 分支补 `kind`（`messaging.ts:53-57`，`:56` 为 `{...gateway, kind:"gateway"}`，另一分支直接返回 `identity.authenticateRequest()`）；`identity.ts:345` 返回 `users` 行，`User` 类型（`identity.ts:27-33`）无 `kind` 字段；`sendPrincipal()` 的键选择在 `message-input.ts:48`（只有 gateway 分支要求 `node_id/owner_id`）。因此 `p.kind === 'user'` 对真实人类发送恒为假，Round 2 的判断与修法都正确 |
| R2-C1 判据可证伪性（M1 W⑧） | **成立**。`design.md:510` M1 W⑧ 用“真实人类 principal 形状（`{id, username}`，没有 `kind`）断言派生发生”，另用 gateway 与 `agent:` 断言不派生。仓库已有同形状先例（`tests/chat-contracts.test.ts:19` 的 `{id:'user',username:'alice',membership_status:'active'}`），且 HTTP 路径主体本来就取自 `users` 行（`tests/messaging.test.ts:56` 经 `sendMessage({headers:{"x-user":"u2"}})`），不存在只能造合成 fixture 的障碍 |
| R2-W1 注册表缝 | **成立**。`design.md:368-378`：`registerDraftHandle(cid, messageId, handle)` 幂等、`DraftHandle{flush, describeConflict, adoptRemote}`（`:371-377`）；`:384` 的 `useDraftFailures(cid)` 用 `useSyncExternalStore`，条目由卡片推进（保存成功或 `adoptRemote()` 清除），composer 不倒推；`:385` 明确三个方法闭包复用组件内 `save()`／`load()`／`state.current`／`revision.current`。仓库有 `useSyncExternalStore` 先例（`features/notifications/local-unread-feedback.ts:1`、`:46`），React 19.1（`src/IM/frontend/package.json:32`）；`load()` 的既有写点与冲突分支的「读取最新」也能对上（`interactive-card.tsx:84`、`:226`） |
| 新契约字段是否必须 | **是必要代价，非 must-fix**。列标签与可读值确实没有客户端等价能力：Web `renderer-library.ts` 与 iOS `src/IM/ios/Runtime/interactive-runtime.ts:24`（只有 `create`）都不返回字段投影，客户端要自己再实现一遍 label/options 求值。字段只读、可选、独立于 `InteractionSnapshot['fields']`（`interactive-types.ts:24`、`:29-31`），`InteractionDraft` 只被 `chat-api.ts`、卡片与测试消费，不在任何模型输入路径上 |
| 默认关闭能否保证模型输入不变 | **能**。`interactionState()`（`interactive-source.ts:125`）本来就算 `options`（`:153`）但只用于 `display_value`（`:155-156`）；开关默认 false、只有 `readDraft()` 传 true 时，`prepare()`／`contexts()`／`background()` 的产物逐字节不变。M1 W⑦ 已把这一点写成断言（含 `withInteractionContext` 字节快照） |
| 契约边界“无改动”旧口径 | **已正确替换**。旧句“`packages/product-contracts`：**无改动**”不再出现；`design.md:23`、`:29` 与 M1 范围（`:510`）一致地描述为一个只读可选字段。`docs/specs/` 不描述 `interaction-state` 的线形状（grep `draft_revision`／`interaction-state` 无命中），不需要额外 delta |
| R2-W2 收尾 (a) | **成立**。`design.md:403-404`：超时不 abort、先用已有水位发基线 discard |
| R2-W2 收尾 (b) | **成立**。`design.md:405`：迟到成功用 `T'` 推进水位并补发 `discard(through: T')`；`through` 单调，他端更新的 `T_B > T'` 不会被清，与 D4 自洽 |
| R2-W2 收尾 (c) | **不成立，且引入新的数据丢失路径**，见 R3-C1 |
| R2-W2 判据（M2 W⑤） | (a)(b) 可证伪；(b) 的最终判据在 iOS 单测里不可执行，见 R3-W3 |
| 四处 minor | **全部改对**。①标题：`design.md:198`、`prototype.html:311`（Web）、`:508-509`（iOS 动态文案）；②409 覆盖引用：`design.md:475` → M2 `[reviewer]` ④(b)；③iOS 判定：`InteractiveRuntime.swift:266`（`conflict = (error as? APIError)?.status == 409`）；④走查新增 `prototype-walkthrough.md:45`，并在 `prototype.html:456` 的 conflict note 里同步解释“卡片内仍画重试”是有意对照物 |
| 新引入矛盾 | 三处：观测无法归属（R3-C1）、iOS 类型生成路径写错（R3-W1）、`options` 类型未规定归一化（R3-W2） |
| 文档完整性 | `../../.venv/bin/python scripts/docs_check.py` → `documentation integrity passed: 224 maintained Markdown sources, 68 required routes`（exit 0） |

### 历史问题闭环

| 原编号 | Author Resolution | 本轮证据 | 状态 |
|---|---|---|---|
| R2-C1 | 改用既有“人类查看者”谓词 + W⑧ 用真实主体形状 | `design.md:258`、`:510`；`interactions.ts:60/92/100/117`、`message-input.ts:5/48`、`messaging.ts:56`、`identity.ts:27-33/345` | **closed** |
| R2-W1 | `DraftHandle` + `useDraftFailures` + 注册表键 `(cid,messageId)` | `design.md:368-378`、`:384-385`；M2 W② 改为从 composer 侧驱动并断言三列/条目消失（`:511`） | **closed**（契约字段的 `options` 类型另见 R3-W2，不重开本项） |
| R2-W2 | 三种收尾（不 abort／基线 discard／迟到补发／永久观测不到） | (a)(b) 见 `design.md:403-405`；(c) `:406` | **保留（部分）** → R3-C1 |
| R2-R1 | 冲突标题改“这个会话暂时不能发送” | `design.md:198`、`prototype.html:311/508` | **closed** |
| R2-R2 | 409 覆盖引用改为 ④(b) | `design.md:475` | **closed** |
| R2-R3 | 走查写明卡片内“重试”是现状对照物 | `prototype-walkthrough.md:45`、`prototype.html:456` | **closed** |
| R2-R4 | iOS 行号改 `:266` | `design.md:398` 引 `InteractiveRuntime.swift:266`；代码 `:266` 一致 | **closed** |

### Issues

#### R3-C1（CRITICAL）“永久观测不到”的补发无法归属观测，会清掉另一台设备已保存未发送的改动——违反本 unit 自己的跨设备保证

`design.md:406` 的触发条件只有三个：`updated_at > 本端水位`、这张卡此刻不 dirty、不在保存中。这三条都无法区分“本端那次未知保存”和“另一台设备更晚的一次保存”，而 `through` 抬高的服务端水位是按用户共享的：

- `interaction_drafts` 是 `(source_message_id, user_id)` 单行（`schema.sql:574-582`，PK 在 `:581`），同一账号的多台设备、多个标签页共用这一行；
- `discard` 写入的 `interaction_background_discards` 也是 `(conversation_id, user_id)`（ER 图 `design.md:212-216`），派生用 `floor = max(coalesce(localHumanAt,''), coalesce(discarded_through,''))`。所以 `through` 一旦取了他端的 `T_B`，`floor` 就抬到 `T_B`，他端已保存但未发送的改动**永远不会再被携带**。

具体路径（两端即可复现，不需要异常设备）：A 改卡、PUT 响应丢失（或 10s 超时）→ A 切走会话，注册表记下“结果未知的保存”→ B（或同账号另一个标签页）改同一张卡并保存成功得到 `T_B` > A 的水位 → A 回到该会话：卡片挂载即 `load()`（`interactive-card.tsx:92` 的 `useEffect(() => { void load() }, [message.id])`），观测到 `T_B > 水位` 且卡片不 dirty、不在保存中 → A 用 `T_B` 补发 `discard` → 服务端 `floor = T_B` → B 侧界面仍显示“已保存”，但 B 那次改动此后不会被任何消息携带，也没有任何提示。

这正是 delta `conversations-messages.md:57` 的 AND 被违反：**“清除由做过这次改动的那一端执行：另一台设备在同一会话打开又切走，不清除这台设备上尚未发送的改动。”** `design.md:406` 末尾“`through` 只清 ≤ 水位的那一次，语义自洽”只在单设备成立——`through` 是服务端按用户共享的水位，不带端信息。

同段还有三处必须一起收口的含糊：①标记只在“注册表”（内存）里，页面刷新即失，而 Risks（`design.md:468`）只承认“用户从此不再打开这张卡”这一种残余窗口；②本端从未成功保存过（无水位）时该判据如何取值没有定义；③这条恢复只写在 iOS 第 4 步，Risks（`:468`）却把“下次成功观测到 `updated_at > 水位` 再补一次”写成两端承诺，而 `:408` 又只让 Web 补“迟到成功”一次——Web 若照 Risks 实现会踩同一路径，若不实现则该承诺是空的。

建议（不新增机制，且与已接受语义一致）：**删掉这条无法归属的补发**，改为两条已存在或可证明的收尾——(i) `design.md:405` 的迟到成功补发（能证明是本端写入，且 `through = T'` 不会清掉更大的 `T_B`）；(ii) 本端下次在该会话任意卡片保存成功时水位自然越过 `T'`，之后正常切走发出的 `discard(through: 新水位)` 就会把它清掉。把“用户不再打开该会话/不再保存”的残余窗口如实写回 Risks（现有 `:468` 的括号一句可保留，但不要再用“下一次成功观测到 `updated_at > 水位` 再补一次”承诺它）。若作者坚持保留观测式恢复，则必须给出可归属的判据（例如只能在收到本端那次 PUT 的迟到响应时补发），否则不能以 `updated_at` 大小作为清除依据。

#### R3-W1（WARNING）iOS 类型“重生成”不成立，M1 W⑦ 的退出标准不可执行

`design.md:23` 与 M1 范围（`:510`）都写“Web/iOS 类型由 `scripts/generate-interactive-ui.ts`、`scripts/generate-ios-interactive.ts` 重生成”，M1 W⑦（`:510`）要求“重生成 Web/iOS 交互类型后 `git diff` 为空（两个脚本幂等）”。事实：`generate-interactive-ui.ts` 只把 `packages/product-contracts/src/interactive-types.ts` 逐字复制成 Web 的 `features/chat/interactive/types.ts`（脚本 `outputs` 第一项），与 iOS 无关；`generate-ios-interactive.ts` 只把 `src/IM/ios/Runtime/interactive-runtime.ts` 打包成 `Resources/InteractiveRuntime.js` 与 license 文件，不产出任何 Swift 类型。iOS 的 `struct InteractionDraft` 是手写 Codable（`InteractiveModels.swift:26-34`，`interactionDraft` 在 `:37`）。

后果：实现 M2 的 `describeConflict()` 时，Swift 侧不会自动多出 `fields`，解码结果为 `nil`，三列对比退化为空；而 M1 W⑦ 的“重生成后 diff 为空”在 iOS 侧是空跑通过，会把一个真实缺失变成绿灯。

修法：把 `:23`／`:510` 改成“Web 类型由脚本逐字生成；iOS 为手写 Codable，需同步新增可选 `fields`”；M1 W⑦ 换成两条可执行断言——Web 生成文件与 `product-contracts/src/interactive-types.ts` 逐字节一致；iOS 用一段含 `fields` 的 JSON 做解码测试并通过编译。

#### R3-W2（WARNING）新契约的 `options` 类型没写归一化，实际选项可能是字符串，iOS 会整份解码失败

`design.md:31-36` 声明 `options?: {label: string; value: string}[]`，但 `interactionState()` 的 `options` 直接来自 `evaluate(node.args[1], ctx)`（`interactive-source.ts:153`），而 catalog 的选项是 union：`z.union([z.string(), z.object({ value: z.string(), label: z.string() })])`（`open-intelligent-ui/components/style.ts:42`，`toOption` 在 `:44` 才做归一化）。按现在写法，字符串形式的选项会被原样放进 `options`，违反声明的类型。

后果：iOS `InteractionDraft` 解码是整份 Codable，一个字符串元素就会让解码抛错——而卡片挂载时的 `load()` 也走同一个方法（`InteractiveModels.swift:37`），于是卡片草稿读取与 409 对比路径一起失败；Web 侧对字符串项取 `option.label` 会得到 `undefined`，三列里出现空标签。

修法：在 `design.md` 写明 `options` 归一化为 `{label, value}`（字符串展开为 `{label: s, value: s}`，与 `toOption` 同义），并在 M1 W⑦ 加一条“字符串形式选项 → 返回对象、两端可解码/渲染”的用例。

#### R3-W3（WARNING）M2 W⑤(b) 的最终判据 `pending()` 在 iOS 单测里不可执行

`design.md:511` M2 `[worker]` ⑤(b) 要求“底层 task 迟到成功 → 补发第二次 discard（新水位），最终 `pending()` 不含该草稿（只断言顺序的测试必须在这里失败）”。`pending()` 是服务端派生 SQL（`design.md:255` 的伪代码），iOS 单测环境里没有它；照写只能造一个假实现，测试变成自证。

修法：iOS 单测断言两个可观测点——(1) 迟到成功后发出第二次 `discard` 且 `through = T'`（**未补发则此断言失败**，这正是“只断言顺序会红”的判别式）；(2) 重复发幂等。把“`pending()` 不含该草稿”留在 M1 W③ 的服务端用例（那里能真跑 SQL）。同时按 R3-C1 把 ⑤(c) 删掉或改成“下一次该会话保存成功后水位越过 `T'`”。

### Recommendations

- **R3-R1**：原型标题与正文已改，但 `evidence/screens/conflict*.png` 是改文案前的本地旧像素（截图按 `.gitignore` 不入库）。重新截一次，或在走查的截图表里标注“截图为改文案前”，免得下游拿旧像素核对文案。
- **R3-R2**：delta 的 409 Scenario（`specs/im/web-chat-ux.md:23-28`、`specs/im/ios-client.md:33-39`）仍只写“这条消息不发出”，没有 transient Scenario 那句“拦截范围是会话级”的 AND；D9 已确定冲突同样拦整个会话（`design.md:188`），建议补一条 AND，避免验收时按“只影响这一条”取证。
- **R3-R3**：`readDraft()` 现在同时是 GET 与 PUT 的响应体（`writeDraft` 在 `interactions.ts:111` 返回它）。加 `fields` 后 PUT 响应也变大，新增/既有测试对响应体请用“包含字段”断言而不是整对象相等，否则纯增量契约会变成假红。

### 已知且接受的限制

沿用 Round 2 的 7 条（本轮无新增接受项）：会话级拦截、409 需显式放弃本机那版、跨设备防抖窗口、水位 128 条上限、`through` 缺失 no-op、`wireContent` 统一 `trimmed`、原型保真度（卡片内 409 态仍画重试，已在走查里说明为对照物）。若 R3-C1 按“删掉观测式补发”收口，需在 Risks 里把相应残余窗口改写为“直到该会话下一次保存成功或该端再次切走”，与本轮前一致地承认它。

### 必须在实施前修改

1. **R3-C1**：`design.md:406` 删除观测式补发或给出可归属判据；同步 `:468` Risks 与 M2 W⑤(c)（`:511`）。
2. **R3-W1**：纠正 `design.md:23`／`:510` 的类型生成路径，M1 W⑦ 换成 Web 逐字节 + iOS 解码两条可执行断言。
3. **R3-W2**：`design.md:31-36` 写明 `options` 归一化，M1 W⑦ 增加字符串选项用例。
4. **R3-W3**：M2 W⑤(b) 的 `pending()` 判据换成 iOS 可观测的断言，`pending()` 留在 M1 W③。

以上四项仍是一个轮次内的修订：不改需求、派生核心边界、delta 结构与 milestone 划分；其中 R3-C1 是必须堵住的数据丢失路径，其余三项是让判据真的能证伪。修订后再走一轮 `closure` 应可 Approved。

### 本轮执行结果

- 只改本文件（`design-review.md` 追加本节），未改设计、原型、走查或任何代码。
- `../../.venv/bin/python scripts/docs_check.py` → `documentation integrity passed: 224 maintained Markdown sources, 68 required routes`（exit 0）。
- 工作树在提交后应为干净；未 push。

## Round 4 (closure)

- **reviewer**：同一独立 `change-design-reviewer`（继续持有 Round 1–3 证据，不参与本 unit 撰写）
- **review target**：`5b449a105`（`6cd674b5b` → `5b449a105`；作者改动为 `design.md` +11/−10、`evidence/prototype-walkthrough.md` +1、`specs/im/web-chat-ux.md` +1、`specs/im/ios-client.md` +1，另重渲染 5 张本地截图；本报告上一轮 commit 也在区间内）
- **review_mode**：`closure`
- **mode_reason**：作者只修订 Round 3 的四条必改与三条顺带项，未改需求、派生核心边界、delta 结构与 milestone 划分。本轮只核这四项、两处顺带项与修订引入的新矛盾，其余引用 Round 1–3 证据。
- **started_at**：2026-11-05T17:58:00+08:00 ／ **completed_at**：2026-11-05T18:12:00+08:00 ／ **duration**：约 14 分钟
- **Verdict**：**Approved**（0 CRITICAL ／ 0 WARNING）—— 允许进入实施

### 覆盖与证据

| 核对面 | 结论与证据 |
|---|---|
| R3-C1 只留两种可归属收尾 | **成立**。`design.md:405-407`：超时不 abort；基线 discard 用已有水位；迟到成功用本端收到的 `T'` 补发 `discard(through: T')`，并说明“归属明确，不会清掉他端更大的 `T_B`（D4 单调）”。观测式补发被整段删除，内存里的“结果未知的保存”标记随之消失（全文再无 `结果未知`／观测式恢复的残留，只剩 `:408` 的解释段） |
| R3-C1 拒绝理由是否写清 | **成立且与我上轮判定一致**。`:408` 明确写出 `interaction_drafts` 是 `(source_message_id,user_id)` 单行、discard 水位按 `(cid,user)` 共享，所以 `updated_at > 水位` 无法归属；拿他端 `T_B` 当 `through` 会让那台设备“已保存但未发送”的改动永不再携带，直接违反 delta `conversations-messages.md:57` 的「清除由做过这次改动的那一端执行」 |
| R3-C1 残余窗口措辞 | **如实、不会被读成已解决**。Risks（`:469`）写的是“**残余窗口**（不做观测式补发…）：这次 PUT 的响应若永远收不到，该改动仍待发——直到本端在该会话下一次任意保存成功使水位越过 `T'`、之后正常切走的 discard 才清掉；在此之前下一次发送会带上它（单会话、一次、可在 Work 核查视图看到），且**不会**影响另一台设备已保存的改动”。机制段（`:408`）也写“宁可留一个写明的残余窗口” |
| R3-C1 “他端更晚保存 → 本端 load() 后不得发 discard”是否可断言 | **是**，双层覆盖。客户端：M2 W⑤(c)（`:512`）构造“他端更晚保存 + 本端水位较低”，断言 `load()` 之后**没有**发出任何 discard，且要等到本端下次保存成功使水位越过 `T'`、随后切走才发 `discard(新水位)`。服务端：M1 W③（`:511`）用 `pending()` 断言“迟到补发 `T'` 后该草稿不再待发，而他端更晚保存（`T_B > T'`）的草稿**仍待发**”——两条正好互为对照，任一侧写成观测式补发都会红 |
| R3-C1 两端统一 | **成立**。`:409` 明确“两端同一规则：Web 的 `discardOnLeave` + `awaitPendingDiscard` 同样只做这两种收尾（迟到成功补发一次），不做观测式补发”。Web 侧的具体断言缺口见「实施时顺手修」第 3 条（不影响设计正确性） |
| R3-W1 类型生成路径 | **改对**。`design.md:23` 改为“Web 类型由 `scripts/generate-interactive-ui.ts` 从本文件**逐字**生成，iOS 的 `struct InteractionDraft` 是手写 `Codable`（`InteractiveModels.swift:26-34`），需同步手写可选 `fields`”；M1 范围（`:511`）把 iOS `InteractiveModels.swift` 的可选 `fields` 纳入，并注明“契约可解码性跟着契约走，只加字段”；M2 范围改为“消费 M1 的 `fields`”。与 `generate-interactive-ui.ts` 的 `outputs` 第一项（逐字复制 contract）和 `generate-ios-interactive.ts`（只打包 `src/IM/ios/Runtime/interactive-runtime.ts` 成 `Resources/InteractiveRuntime.js` + license）一致 |
| R3-W1 两条断言能否跑 | **内容断言成立，命令形态需一处小修（见「实施时顺手修」第 1 条）**。脚本支持 `--check` 且逐字比较；`--check` 的语义与 `src/IM/frontend/package.json` 的 `check:interactive-assets`（`tsx ../../../scripts/generate-interactive-ui.ts --check`，并挂在 `pretest`）完全相同。但设计写的 `pnpm exec tsx scripts/generate-interactive-ui.ts --check` 从仓根跑不通：`src/IM/frontend` 不在 pnpm workspace（`pnpm-workspace.yaml` 只有 `apps/*`、`packages/*`），`@openuidev/react-lang` 不会被链接；本轮实测（先 `pnpm install` 成功，再跑该命令）报 `ERR_MODULE_NOT_FOUND: Cannot find package '@openuidev/react-lang'`（exit 1）。官方入口见 `docs/development/local-development.md:12` 的 `npm --prefix src/IM/frontend ci` |
| R3-W1 能否抓到 Swift 缺字段 | **能，但前提是断言到取值**。Swift `Codable` 默认忽略未知键，只断言“含 `fields` 的 JSON 解码成功”抓不到结构体缺属性；若测试引用并断言 `draft.fields?.count`／取值，缺属性会直接编译失败。设计写的是“用手写的可选 `fields` + 一段含 `fields` 的 JSON 做解码测试并通过编译”，方向正确，落实形态见「实施时顺手修」第 2 条；即便 M1 写松，M2 W②（iOS 侧渲染三列、标签来自服务端 `fields`）会兜住 |
| R3-W2 归一化位置与一致性 | **正确**。`design.md:39`（新增段）：`options` 由服务端归一化后再返回，`interactionState` 在 `withOptions` 分支里逐个展开成 `{label, value}`（字符串 → `{label:s, value:s}`，与 `toOption` 同义），并引 `style.ts:42` 的 union 与 `:44` 的 `toOption`。位置在服务端开关分支，客户端只渲染，符合“默认产物逐字节不变”的既有约定 |
| R3-W2 用例 | **成立**。M1 W⑦（`:511`）新增“`options` 的字符串形式（`['wed','thu']` 之类）返回 `{label,value}` 对象，两端都能解码/渲染”，并补了“用‘包含字段与取值’而不是整对象相等（`readDraft()` 同时是 GET 与 PUT 的响应体，`interactions.ts:111`）”——我上轮 R3-R3 的提醒已被采纳 |
| R3-W3 M2 W⑤(b) | **成立**。`:512`：断言发出**第二次** discard 且 `through == T'`（未补发则红）、重复发送幂等、水位不倒退。判据从“服务端 `pending()`”换成客户端可观测行为，iOS 单测能真跑 |
| R3-W3 M2 W⑤(c) 与 `pending()` 归位 | **成立**。`:512` (c) 改为“不做观测式补发”的构造性场景（见上）；并明写“`pending()` 是服务端 SQL，不在 iOS 单测断言，见 M1 `[worker]` ③”。M1 W③ 已承接（`pending()` 双向断言） |
| 顺带：5 张截图与走查一致 | **自洽**。走查新增“像素与文案同步”一行（`prototype-walkthrough.md:14`），点名 `conflict.png`／`conflict-diff.png`／`conflict-adopted.png`／`iosconflict.png`／`iosconflict-diff.png` 五张，并说“下表截图的文案与当前 HTML 一致”；本轮核对本地 PNG 的 mtime：这五张为 18:00–18:01，其余八张仍是 17:10，与“只重渲染受影响五张”一致。截图表里冲突态三行（`:22-24`）的 must-match 描述与新文案不冲突（都不引用旧标题） |
| 顺带：delta 409 的会话级 AND | **两处都补了**。`specs/im/web-chat-ux.md:26` 与 `specs/im/ios-client.md:37` 各新增一条 AND：“拦截范围与未保存失败一致，也是会话级：同一会话的其他消息同样要等这次冲突处理完，不只是这一条不发出”，与 D9（`design.md:188`）及 transient Scenario 的 AND 同义 |
| 契约卫生 | 只加 AND，计数不变：`spec.md` 仍 6 Requirement／18 Scenario；delta 仍 17／7／6／3 Scenario（`conversations-messages`／`ios-client`／`web-chat-ux`／`agent-capabilities`），0 ADDED／4 MODIFIED／0 REMOVED |
| 新引入矛盾 | **未发现**。全文已无“重生成 iOS 类型”“观测式补发”“结果未知的保存”等旧口径；“两种收尾”（`:405`）与 Risks 的“覆盖三种形状”（`:469`，指 (a)(b)(c) 三个测试情形）是措辞可优化、不是语义冲突（见顺手修第 4 条） |
| 文档完整性 | `../../.venv/bin/python scripts/docs_check.py` → `documentation integrity passed: 224 maintained Markdown sources, 68 required routes`（exit 0） |

### 历史问题闭环

| 原编号 | Author Resolution | 本轮证据 | 状态 |
|---|---|---|---|
| R3-C1 | 删掉观测式补发与内存标记，只留基线 + 迟到成功两种可归属收尾，两端统一 | `design.md:405-409`；Risks `:469`；M2 W⑤(b)(c) `:512`；M1 W③ `:511` | **closed** |
| R3-W1 | 明写 Web 逐字生成、iOS 手写 Codable；M1 范围纳入 `InteractiveModels.swift`；断言改为 `--check` 逐字节 + iOS 解码 | `design.md:23`、`:511`、`:512` | **closed**（命令形态 → 顺手修第 1 条） |
| R3-W2 | 服务端 `withOptions` 分支归一化字符串选项；M1 W⑦ 加用例 | `design.md:39`、`:511` | **closed** |
| R3-W3 | M2 W⑤(b) 改客户端可观测断言（`through == T'` + 幂等 + 水位不倒退）；(c) 改为“不做观测式补发”；`pending()` 移回 M1 W③ | `design.md:511-512` | **closed** |
| R3-R1 | 重渲染受影响截图并在走查里注明 | `prototype-walkthrough.md:14` + 本地 PNG mtime | **closed** |
| R3-R2 | delta 409 Scenario 补会话级 AND（Web 与 iOS） | `web-chat-ux.md:26`、`ios-client.md:37` | **closed** |
| R3-R3 | M1 W⑦ 明写“包含字段与取值”而非整对象相等 | `design.md:511` | **closed** |

### 已接受限制清单（随本次放行）

1. **会话级拦截**：任一卡片改动未保存成功或处于 409 冲突，该会话所有发送被拦，直到保存成功或明确采用最新；离线时一句话也发不出去。已写入 D9、Risks、两个 delta 与原型文案。
2. **409 需显式放弃本机那版**：不自动合并；放弃前正文与卡片状态保留。
3. **跨设备防抖窗口**：可接受窗口 = 500ms 防抖 + 一次 RTT；迟到保存会落到该端下一条消息（M2 R⑥ 口径为“等甲的未保存提示消失”）。
4. **水位 128 条上限**：被淘汰会话的“切走清除”退化为“该端没有水位 → 不清除”。
5. **`through` 缺失 → no-op**：把“另一台设备的切走不清除”固化为产品语义（delta `conversations-messages.md:57`）。
6. **`wireContent` 统一 `trimmed`**：可见但极小的正文首尾空白差异，由 M2 W③ 固定。
7. **原型保真度**：卡片内错误行在 409 态仍按现状绘制，走查已写明为“卡片内提示不够、所以要搬到发送处”的对照物；原型不产生真实请求。
8. **响应永久丢失的残余窗口（本轮新增接受）**：flush 超时且响应永远收不到时，该次改动仍待发，直到本端在该会话下一次任意保存成功使水位越过 `T'`、之后正常切走才清掉；期间下一次发送会带上它（单会话、一次，可在 Work 核查视图看到），且不会影响另一台设备已保存的改动（Risks `:469`）。

### 实施时顺手修（不阻断，不另开 Round）

1. **M1 W⑦ 的 Web 命令换成可跑形态**：`npm --prefix src/IM/frontend ci` 后 `npm --prefix src/IM/frontend run check:interactive-assets`（`pretest` 已自动执行）。不要从仓根写 `pnpm exec tsx scripts/generate-interactive-ui.ts --check`：`src/IM/frontend` 不在 pnpm workspace，本轮实测根安装后该命令 `ERR_MODULE_NOT_FOUND: @openuidev/react-lang`（exit 1）。
2. **iOS 解码断言断言到取值**：例如 `XCTAssertEqual(draft.fields?.count, N)` 或逐项比较；只断言“解码成功”抓不到结构体缺 `fields`（`Codable` 忽略未知键）。
3. **M2 W④（Web）补一条与 iOS ⑤(b)(c) 对称的用例**：迟到成功补发一次 `discard(through: T')`；`load()` 之后不发观测式 discard。设计已写“两端同一规则”（`design.md:409`），但 Web 侧目前没有对应断言。
4. **两处措辞**：M2 `[reviewer]` ③ 可限定“正常（非响应丢失）路径”，以免与 Risks 的残余窗口字面冲突；Risks `:469` 的“覆盖三种形状”可写成“覆盖 (a)(b)(c) 三个情形”，避免被读成三种收尾。

### 本轮执行结果

- 只改本文件（`design-review.md` 追加本节）；未改设计、原型、走查、delta 或代码。
- `../../.venv/bin/python scripts/docs_check.py` → `documentation integrity passed: 224 maintained Markdown sources, 68 required routes`（exit 0）。
- 为核实“断言是否能跑”，本轮在 worktree 执行过一次 `pnpm install` 与一次 `pnpm exec tsx scripts/generate-interactive-ui.ts --check`（返回 1，原因见顺手修第 1 条）；`git status` 仍干净，tracked 文件未被改动。
- 提交后工作树应为干净；未 push。
