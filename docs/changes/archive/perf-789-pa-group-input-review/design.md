# perf-789: 按唤醒批次合并 PA 参与群的输入安全审核 — 技术方案

> 对齐: motivation.md v1

## Changelog

## 现状分析

### 涉及范围

- `packages/personal-assistant/src/global-agent.ts`：`ingestAdmitted` 在消息入 Inbox 调度前逐条同步等待 `personal.admit`；`wake`、`armBackground`、`restoreRoot`/`restorePersonalInputs`、`recoverPersonalObservations`、`receipt` 以及 `inbox`/`read_messages`/`search_messages`/`send_message` 工具分发负责跨会话提醒、双路投递合并、到期扫描、主动读取消重（`recordQueryRead`）与发信门禁。
- `packages/personal-assistant/src/personal-assistant.ts`：`source` 向中心调用 `pa.source.admit` 获取可信身份与参与关系；`admit` 对所有 `personal_is_owner !== true && personal_delivery === 'participant'` 消息逐条拉取 `pa.input.context` 并请求 `pa.review('input')`；`send` 在外发前通过 `inbox.blocking` 执行 `held_for_revalidation` 门禁。
- `packages/personal-assistant/src/inbox-review.ts` 与 `inbox.ts`：在同一 SQLite `inbox` 表维护 `review_state`（`pending`/`reviewing`/`admitted`/`rejected`/`failed`）、`review_generation`、故障事件投递、`acceptRelay` 身份校验、`relay_receipts`、`inbox_schedule` 十分钟截止、`recordQueryRead` 已读消重以及 `restrict`/`revokeSource` 清退。
- `apps/im-server/src/personal-input-context.ts`、`personal-agent.ts` 与 `messaging.ts`：Web IM 共同群在 `Messaging.send` 同时产生 `pa_source_events`（推送 `pa.observations.available`）与 `relay_tasks`（推送 `relay.message`），飞书 PA 入站经 `ExternalChannels.mirrorAdmitted`（`suppress_relay: true`）仅走 `pa_source_events` 观察流；`pa.input.context` 提供原始会话历史与直接回复证据。
- `packages/product-contracts/src/runtime-rpc.ts`、`packages/dsh-integration/src/personal-security.ts` 与 `standalone-model-retry.ts`：定义 `pa.review` RPC schema，组装独立输入审核提示词、执行窗口与 8,192 token 历史预算裁剪、经 `withStandaloneRetry` 调用审核模型并解析 JSON 判定。
- `apps/node/src/main.ts`：组装 `GlobalAgent`、`ExternalChannels`、`Heartbeat`、`ConfigurationOperations`（含 `restrictToOwner`）与 `NodeUpdater` 忙碌探针。

### 既有约束

- 遵守 [SPEC.md](../../../SPEC.md) 与 [AGENTS.md](../../../AGENTS.md)：`packages/personal-assistant` 不直接依赖 DSH，仅通过 `RuntimePort` 调用 `pa.review`；只有 `packages/dsh-integration` 使用公开 DSH exports 调用模型与分词估算。
- 遵守 [Gateway PA 契约](../../specs/gateway/personal-agent.md)：
  - 非主人 `participant` 消息未通过独立审核前不得进入主 PA 可见面（含 Inbox 通知、`inbox` 读取以及 `read_messages`/`search_messages` 主动历史查询），不得借异常或省略默许放行；
  - 输入审核以单条消息为独立准入单位，单条拒绝、消息级不可访问或技术故障不阻塞同会话其他合法消息，也不误清空仍可访问的整个会话；
  - 被拒消息（未满第 5 次自动屏蔽时）继续走 `pa.incident.report` → 主 PA 私聊提醒主人 + 原会话拒绝回复 + `prompt_injection` 累计 5 次自动屏蔽；普通未授权外部协作请求应作为不可信数据 `allow` 进入 Inbox 由主 PA 与出站披露审核把关，不得落入无提醒黑洞；
  - 带附件的非主人待审消息保持既有输入审核 fail-closed 边界，但不连坐同批纯文本消息；
  - 背景等待期间 `GlobalAgent.busy` 保持 `false`（不阻塞节点更新探针），到期或批审在途时为 `true`；重启不重置已确定的十分钟期限，已失败记录不在重启或 `inbox check/read` 时自动重放模型调用。

### 可复用能力

- **复用** `pa.source.admit`：纯服务端 SQLite 校验，无模型开销，可在消息抵达时立即鉴别主人身份、`participant`/`observer`、`addressed_to_agent`、`addressed_to_owner`、话题关注与来源可达性。
- **复用** `InboxReviews` 状态机（`pending` → `reviewing` → `admitted`/`rejected`/`failed`）与 `inbox_schedule`、`restrict`、`revokeUnavailableSources`：仅在 `inbox` 表增量补充可空列 `review_due_at INTEGER` 记录延迟待审消息的原始到期时刻，并暴露 `nextDueAt`/`duePending` 供 `armBackground`、`restoreRoot` 与 `busy` 接入。
- **扩展** `pa.input.context`、`pa.review('input')` 与 `personal-security.ts`：在保留单条调用兼容的同时，支持同会话最多 20 条待审消息的时间线紧凑投影、单模态无歧义批量提示词、批内短整数标识映射、显式 `context_overflow` 错误码二分拆批与逐条判定输出。

### 相关历史

- `feat-774`（统一协作范围与十分钟合并提醒）：建立了 `chatDelivery`（`skip`/`high`/`background`）、`inbox_schedule` 首个积压十分钟截止与 `restrictToOwner` 清退机制，并将 PA 入站审核成本单列为 [#533](https://github.com/Mrchen116/nano-multiagent/issues/533)。
- `bugfix-678`（PA 权限边界与累计五次自动屏蔽）：确立了消息级准入状态机、未完成中断转 `failed`、显式单条重审及 `pa.incident.report` 风险处置闭环。
- `feat-780` / `feat-786`（群话题、`read_messages` 消重与通用附件）：引入话题目标 `joinThreadTarget`/`splitThreadTarget`、`recordQueryRead` 主动查询已读消重及非主人入站附件 fail-closed 约束。

## 架构总览

改动将 PA 参与群的准入拆成「**抵达时轻量鉴权与双路幂等落库**」与「**全可见/外发边界按会话批量审核**」两步：

```mermaid
sequenceDiagram
    participant IM as IM Server
    participant GA as GlobalAgent / PersonalAssistant
    participant DB as InboxStore (SQLite)
    participant DSH as dsh-integration (pa.review)

    IM->>GA: relay.message 与/或 pa.observations.read
    GA->>DB: 原子建行或幂等合并双路信封 (保留非观察 relay 与首次 review_due_at)
    GA->>IM: pa.source.admit (轻量鉴权，0 LLM)
    alt 主人消息 或 observer 会话
        GA->>DB: settle admitted + inbox_schedule
    else 非主人 participant 普通群背景 (!high && 同群 pending < 20)
        GA->>DB: 存认证元数据，保持 review_state=pending，写 review_due_at=now+10m
    else 高优消息 或 同群 pending >= 20
        GA->>DB: 存待审行并立即触发 flushPendingReviews(conversation_id)
    end

    Note over GA,DSH: 10m 到期 / wake 循环前 / inbox check·read 前 / read_messages·search_messages 前 / send 前
    GA->>DB: 按 conversation_id 并行冲刷 (单会话单飞锁，附件前置单条 failed，纯文本 ≤20 条/批)
    GA->>IM: pa.input.context (conversation_id, source_message_ids)
    IM-->>GA: source_allowed + unavailable_message_ids + conversation + previous + timeline + reply_targets + omissions
    GA->>DSH: pa.review(kind='input', 紧凑时间线 + 短序号 item=1..k)
    DSH-->>GA: decisions[{id, decision: allow|deny, reason, incident?}] 或 error_code=context_overflow
    GA->>DB: 超窗且批>1则二分拆批；否则逐条结算 admitted / rejected / failed 并结清双路回执
```

- **Before**：每条非主人 `participant` 群消息在 `ingestAdmitted` 内同步调 `pa.input.context` + `pa.review('input')`，20 条普通群聊触发 20 次独立模型调用，前 20 条历史被重复编码发送 20 次。
- **After**：抵达时仅执行 `pa.source.admit` 并在 `inbox` 原子保存待审行与 `review_due_at = arrival + 10min`；在主 PA 任何可能观察或受其影响的边界（十分钟到期、高优 `wake`、`inbox` `check`/`read`、`read_messages`/`search_messages`、外发 `send` 前重验或同群攒满 20 条）按 `conversation_id` 合并送审一次，再按 `message_id` 独立结算。

## 关键决策

1. **抵达时照常执行 `pa.source.admit`，原子持久化待审行并幂等合并 `pa_observation` 与 `relay.message` 双路投递。**
   - 理由：飞书 PA 消息仅经 `recoverPersonalObservations -> ingest` 进入（不经过 `acceptRelay`），而主人与 PA 共处的 Web IM 群同时送达 `pa_observation`（10 字段投影）与 `relay.message`（完整 `ChatMessage` + `agent_receipt`）。抵达时原子建行与信封合并可保证观测路径消息不丢失、双路先后到达不抛 `Relay input identity conflict`、保留 `relay.message` 的 `agent_receipt` 与非观察回执义务且不推迟首次 `review_due_at`。
   - 拒绝备选：仅依赖 `acceptRelay` 建行或保留原全字段字节相等校验——会导致飞书参与群消息静默丢失、Web 共同群双路投递冲突死循环，或批审拒绝后 Web `relay_receipts` 卡死在 `accepted`。

2. **待审期限存放在 `inbox.review_due_at`，`armBackground`、`restoreRoot`、`wake` 与 `GlobalAgent.busy` 统一接入 `InboxReviews` 期限查询。**
   - 理由：未审消息不进 `inbox_schedule`，从存储层杜绝未审文本混入通知摘要；`InboxReviews` 提供 `nextDueAt(agentId)` 与 `duePending(agentId)`，使仅有参与群待审积压的 PA 也能准时挂载 10 分钟定时器、重启恢复不漏冲刷、因满 20 条提前批审的消息继承原 `review_due_at` 不提前唤醒主 PA，且等待期 `busy === false`、到期或在途批审期 `busy === true`。

3. **覆盖主 PA 全部读取与外发入口（含 `read_messages`/`search_messages` 与 `PersonalAssistant.send`）执行前置冲刷，跨会话并行、同会话串行。**
   - 理由：主 PA 可由 `Heartbeat`、原生 `Cron` 或子任务唤醒并在未经过 `GlobalAgent.wake` 时直接调用 `read_messages`/`search_messages` 或向群聊 `send_message`。在这些入口前冲刷目标会话（无单会话 `target` 时并行冲刷该 PA 全部待审会话），既防止未审注入借历史查询绕过拦截与违章计数，又让合法消息先转为 `admitted` 使 `inbox.recordQueryRead` 正常标记已读（避免 10 分钟后重复唤醒），同时配合 `inbox.blocking` 覆盖 `pending`/`reviewing` 高优行确保在途 `@PA` 可靠触发 `held_for_revalidation`。

4. **显式 `context_overflow` 错误码驱动二分拆批，附件与消息级不可访问前置单条隔离。**
   - 理由：将 `inputReviewEvidence` 的窗口核算与 `standalone-model-retry.ts`（每条 `messages` 额外 `+4` tokens 及 `JSON.stringify(tools ?? [])` 开销）严格对齐，超窗时返回结构化 `error_code: 'context_overflow'`；仅在 `error_code === 'context_overflow'` 且批大小 `> 1` 时二分拆批，避免模型超时/5xx 故障退化为串行重试风暴。带附件的 `needs_decision: true` 待审项前置单条结为 `failed`（不影响穿插语境消息中的附件元数据），`pa.input.context` 返回的单条 `unavailable_message_ids` 单条结为 `rejected`（`error_code: 'source_unavailable'`，不报 incident、不调用 `revokeSource` 误删整群）。

5. **按单条/批量分模态生成提示词，模型侧入站判定收窄为 `allow | deny`，批内使用短序号 `1..k` 全集校验。**
   - 理由：消除单条与批量输出 schema 混装冲突；避免模型对普通未授权群务请求输出 `needs_owner` 造成静默丢消息黑洞；剥离每条消息重复的会话级样板字段并将 36 位长 UUID 映射为批内短整数 `item: 1..k`，降低 token 开销与回抄笔误率，同时保持缺项/重项/越界序号 fail-closed。

## 接口与数据流

### 1. IM 批量上下文接口 `pa.input.context`

`apps/im-server/src/personal-input-context.ts` 新增 `personalInputBatchContext`（保留单条 `{ source_message_id }` 分支向后兼容）：

- **请求参数**：`{ conversation_id: string, source_message_ids: string[] }`（`1 <= source_message_ids.length <= 20`）。
- **会话与消息级校验**：
  1. 先校验会话级 `sourceAllowed(b, conversation_id)` 及会话存在性：若会话本身不可访问，返回 `{ source_allowed: false }`（由节点调用一次 `inbox.revokeSource` 清退该会话）。
  2. 会话可访问时，在 `conversation_id` 内查询各请求消息并逐条检查 `messageAllowed(b, msg)`：缺失或消息级不可访问的 ID 放入 `unavailable_message_ids: string[]`；若可访问目标为空（`targets.length === 0`），直接返回 `{ source_allowed: true, unavailable_message_ids, conversation, previous: [], timeline: [], reply_targets: [], omissions: [] }`，不访问空下标、不发起模型调用。
- **紧凑证据投影**：
  - 顶层 `conversation` 一次输出 `{ id: chat.id, type: chat.type, delivery: participant ? 'participant' : 'observer', channel: chat.external_source ?? 'web' }`。
  - 单条紧凑消息投影（用于 `previous`、`timeline`、`reply_targets`）仅保留消息自身事实：`{ id, sender: { id, name, type, is_owner, ...(source_id ? { source_id } : {}) }, ...(pa_agent_id ? { pa_agent_id } : {}), addressed_to_agent, ...(addressed_to_owner ? { addressed_to_owner: true } : {}), ...(explicit_mentioned_agent_ids.length ? { explicit_mentioned_agent_ids } : {}), content, created_at, ...(attachments.length ? { attachments: attachments.map(a => ({ content_type: a.content_type, file_name: a.file_name })) } : {}), ...(reply_to ? { reply_to: { message_id: reply_to.message_id } } : {}), ...(interaction_reply ? { interaction_reply } : {}), ...(interactive ? { interactive } : {}) }`，剥离重复的会话级字段与空 `attachments: []`。
  - **`previous`**：取 `t_1.sequence` 之前最近 21 条同会话消息，超出 20 条记 `{ reason: 'history_window', limit: 20 }`；不可访问项记 `{ reason: 'history_unavailable', message_id }`，保留最多 20 条。
  - **`timeline`**：取 `t_1.sequence .. t_k.sequence` 之间的同会话消息：
    - 属于 `targets` 的消息标 `needs_decision: true`（若存在服务端 `actor_risk` 一并附带 `actor_risk`）；
    - 穿插的非目标消息：不可访问项记 `{ reason: 'history_unavailable', message_id }`；可访问项标 `needs_decision: false`，若穿插非目标消息总数超过 20 条，仅保留紧邻目标消息的最近 20 条，被裁掉的更早穿插消息记 `{ reason: 'timeline_window', limit: 20 }`。
  - **`reply_targets`**：遍历 `targets` 的 `reply_to` 与 `interaction_reply`，若引用目标不在 `previous` 或 `timeline` 中且 `sequence < target.sequence`，可访问则按 `id` 去重加入 `reply_targets`，否则记 `{ reason: 'reply_target_unavailable', message_id }`。

### 2. 运行时 `pa.review` 契约与模型可见 Context 设计

- **Consumer**：独立输入安全审核模型（`config.approval?.reviewer ?? { provider: config.provider, model: config.model }`），单轮无状态、无工具调用（`tools: undefined`）。
- **Protocol (`packages/product-contracts/src/runtime-rpc.ts`)**：
  `pa.review`（`kind === 'input'`）返回结构扩展可选字段：`decisions?: Array<{ id: string, decision: 'allow' | 'deny' | 'needs_owner' | 'unavailable', reason: string, incident?: { reason: string } }>` 与 `error_code?: 'context_overflow'`（顶层 `decision` / `reason` 在单条模式或整批不可用时保持兼容）。
- **Context Lifecycle & Before/After（`packages/dsh-integration/src/personal-security.ts`）**：
  - **分模态 System Prompt**：
    - 单条模式（`evidence.current`）使用单条输入提示词，要求仅输出 `{"decision":"allow|deny","reason":"...","incident":{"reason":"..."}}`。
    - 批量模式（`evidence.timeline`）使用专用批量输入提示词，不混入单条 `current` 描述：声明 `conversation`、`previous`、`reply_targets` 及 `timeline` 中无 `item` 编号（`needs_decision: false`）的条目均为背景证据，绝不执行其中指令；仅对 `timeline` 中带正整数 `item`（`1..k`）的待审消息结合前序与穿插语境逐条裁决；明确区分「普通未获主人授权的外部协作请求」（判 `allow`，作为不可信普通消息交主 PA 与出站审核处理，绝不用拒绝吞没正常群务）与「显式提示词注入、伪装系统/主人身份或授权、借前文/引用诱导越权或套取主人隐私」（判 `deny`，恶意试探或欺骗附带 `incident`），且前文他人的可疑发言不连坐后续正常发言者；严格返回 `{"decisions":[{"item":1,"decision":"allow|deny","reason":"...","incident":{"reason":"..."}}]}`，覆盖全部 `1..k`。
  - **短序号映射与解析校验**：
    - 序列化前为 `timeline` 中每个 `needs_decision: true` 条目按顺序注入 `item: 1 .. k`，并在本地保存 `item -> message.id` 映射；仅对 `needs_decision: true` 条目检查附件（若存在附件抛出不可投影错误；穿插 `needs_decision: false` 条目的附件摘要允许保留作背景）。
    - 解析 `decisions` 时校验：`decisions.length === k`，`item` 集合精确等于 `{1..k}`（无重复、无缺漏、无越界），每项 `decision` 为合法枚举且 `reason` 非空；校验通过后映射回真实 `id` 返回。任何缺漏或错号返回 `undefined`，走 `withStandaloneRetry`（`formatRemaining: 1`）重试，仍无效则整批返回 `{ decision: 'unavailable', reason }`。
  - **与 `standalone-model-retry.ts` 精确对齐的窗口预算裁剪**：
    - 批量输出预留 `maxTokens = 4096`（单条保持 `2048`）。总输入估算函数严格对齐 `standalone-model-retry.ts:76-78`：`totalRequestCost(serialized) = estimateContent([{ type: 'text', text: serialized }]) + 4 + estimateContent([{ type: 'text', text: policy }, { type: 'text', text: '[]' }])`，要求 `totalRequestCost(serialized) + maxTokens + 512 <= contextWindow`。
    - 先校验仅含全部 `needs_decision: true` 条目（`previous = []`、无 `needs_decision: false` 穿插项、无 `reply_targets`）时的最小必需请求开销：若仍超出窗口，抛出专用 `InputReviewContextOverflowError`，由 `reviewPersonal` 捕获并返回 `{ decision: 'unavailable', error_code: 'context_overflow', reason }`。
    - 若最小必需集可装入窗口，而完整上下文超出窗口或上下文辅助部分（`previous` + `needs_decision: false` 穿插项 + `reply_targets`）超过 `8,192` tokens，依次整条移除最旧 `previous`（记 `history_budget`）、最旧 `needs_decision: false` 穿插项（记 `history_budget`）、最后逐条移除 `reply_targets`（记 `reply_target_budget`）。
- **Interactions**：主 PA 的系统提示词、工具 schema、出站披露审核 `pa.review('action')` 与安全事件提交通道 `personal-state` 完全不变。

### 3. 节点准入、双路合并、全边界冲刷与恢复流程

1. **双路信封幂等合并（`InboxStore.acceptRelay` & `PersonalAssistant.stage`）**：
   - 当 `acceptRelay` 收到 `relay.message` 而 `inbox` 已存在同一 `(agent_id, message_id)` 行时：若既有行带 `metadata.pa_observation === true`（先到的观察事件），按不可变核心消息事实（`agent_id`、`conversation_id`、`message.id`、`sender_type`、`content`）校验一致性后，将 `payload` 升级为完整 `relay.message` 信封（补齐 `agent_receipt`、`participants`、`interaction_contexts`、清除 `pa_observation`），同时保留已写入的认证 `personal_*` 字段、`review_state` 与首次 `review_due_at`；两个非观察 `relay.message` 之间仍保持原全字段一致性校验。
   - 当 `recoverPersonalObservations -> ingest` 晚于 `relay.message` 到达时：若 `inbox` 已有非观察信封，不将 `pa_observation: true` 覆盖回 `inbox.payload`，且若已进入终态或已排入 `pending` 队列则幂等返回现有状态。
   - 若 `inbox` 尚无该行（如飞书 PA 镜像观察或先到的 Web 观察），`stage` 原子调用 `inbox.receive(saved, false)` 建行，确保 `pa.observations.ack('processed')` 后消息持久在库。
2. **抵达阶段（`PersonalAssistant.stage` / `GlobalAgent.ingestAdmitted`）**：
   - 对尚带 `personal_unclassified === true` 的消息执行 `personal.source(config, input)`：
     - 不可访问：同现状结算 `source_unavailable`（仅在 `!input.metadata.scope_skipped` 且会话失权时清退）或 `scope_skipped`，并结清关联回执。
     - `is_owner === true` 或 `delivery !== 'participant'`：直接结算 `review_state = 'admitted'`，写入 `store.receive`、`inbox.classify(input, attention, high)`；若 `high && !deferWake`，先并行冲刷该 PA 全部待审会话再 `wake`。
     - 非主人 `participant` 消息：
       - 原子写入认证后的 `input`、`attention`（清除 `personal_unclassified`，保持 `review_state = 'pending'`），并在 `review_due_at IS NULL` 时写入初始截止时间 `context_only ? null : (high ? 0 : now + CHAT_BACKGROUND_DELAY_MS)`。
       - 若存在附件（`input.message.attachments.length > 0`）：前置直接将该条结算为 `failed`（`error_code: 'review_unavailable'`，原因保留 `Input review attachment projection is unavailable`），结清该条回执并触发 `deliverReviewFailures(config)`，不进入文本批审队列。
       - 若 `high === true` 或同 `conversation_id` 当前 `pending` 纯文本数达到 `20`：立即调用 `flushPendingReviews(config, binding, input.conversation_id)`；若 `high && !deferWake`，再并行冲刷该 PA 其余会话待审队列后进入 `wake`。
       - 否则（普通参与群背景纯文本）：Web `relay` 保持 `accepted` 回执，调用 `armBackground()` 挂载最早定时器后返回，**0 次 `pa.input.context` / `pa.review` 调用**。
3. **全边界冲刷（`flushPendingReviews(config, binding, conversationId?)`）**：
   - **全部触发入口**：
     1. `backgroundDrain` 到期扫描（`inbox.wakePending(agentId) !== undefined || inbox.reviews.duePending(agentId)`）：先 `refreshPersonalSources`，再并行冲刷该 PA 全部待审会话，最后若 `inbox.wakePending(agentId) !== undefined` 调用 `wake`；
     2. `wake(config, binding)` 在进入 `while ((watermark = inbox.wakePending(config.agentId)) !== undefined)` 循环前（及循环内若检测到新到到期/高优待审时）并行冲刷该 PA 全部待审会话；
     3. `GlobalAgent.execute` 中主 PA 调用 `inbox(action="check")` 前并行冲刷全会话，调用 `inbox(action="read", target)` 前冲刷 `splitThreadTarget(target).base`；
     4. `GlobalAgent.execute` 中主 PA 调用 `read_messages` 或 `search_messages` 前：若指定了单会话 `target`（且非跨会话搜索）则冲刷对应的已解析 `conversation_id`，否则并行冲刷该 PA 全部待审会话，保证未审风险消息先被拦截上报、合法消息先转为 `admitted` 供紧随其后的 `inbox.recordQueryRead` 标记消费；
     5. `PersonalAssistant.send` 在检查 `inbox.blocking(config.agentId, conversation)` 前（含本地附件准备前后两次检查）冲刷/等待目标 `conversation` 的待审与在途审核，且 `inbox.blocking` 同步覆盖 `consumed = 0 AND attention = 1 AND review_state IN ('pending', 'reviewing', 'admitted')`。
   - **并发与拆批执行**：
     - 跨会话使用 `Promise.all` 并行冲刷；同一 `${agentId}:${conversationId}` 通过单飞锁串行化（在途锁纳入 `PersonalAssistant.busy` 与 `GlobalAgent.busy`）。
     - 每批按 `seq ASC` 取最多 20 条 `consumed = 0 AND review_state = 'pending' AND personal_unclassified = 0` 的消息并原子 `beginBatch`（递增各自 `review_generation` 置为 `reviewing`）。
     - 调 `pa.input.context`：若 `source_allowed === false`，调 `inbox.revokeSource(agentId, conversationId)` 并结清回执；对 `unavailable_message_ids` 逐条结算 `state: 'rejected', error_code: 'source_unavailable'` 并结清该条回执（不调 `reportInputIncident`、不调 `revokeSource`）。
     - 若剩余可审目标非空，执行 `reviewChunk(targets)`：若返回 `error_code === 'context_overflow'` 且 `targets.length > 1`，按 `Math.ceil(targets.length / 2)` 二分拆成两个子切片顺序执行，直至单条超窗（仅该单条结为 `failed`）或正常返回 `decisions`。
     - 逐条结算终态：
       - `allow`：结算 `admitted`、`store.receive`、按原 `review_due_at`（无则 `now + CHAT_BACKGROUND_DELAY_MS`）写入 `inbox_schedule`；
       - `deny`（或兼容单条 `needs_owner`）：结算 `rejected`，无 `error_code` 时调用 `reportInputIncident` 并触发 `recoverPersonalObservations()`，同时按 `(agent_id, message_id)` 结清 `inbox.settleRelay(..., 'completed')` 与飞书 `transmitReceipt`；
       - `unavailable`：结算 `failed`（`error_code: 'review_unavailable'`），按 `(agent_id, message_id)` 结清回执并调用 `deliverReviewFailures(config)`。
4. **范围收紧、来源撤销、显式重审与重启恢复**：
   - `restrictToOwner` 与 `revokeUnavailableSources`/`revokeSource` 直接将 `pending` 行标为 `scope_cancelled`/`consumed = 1` 或移除，后续冲刷跳过，0 次模型调用。
   - `inbox(action="review", message_id)` 仅对指定 `failed` 消息执行单条重审，绝不混入常规 `pending` 扫描，常规冲刷也绝不重审 `failed` 消息。
   - 重启时：`reviewing` 行转为 `interrupted` 失败；`pending` 行中 `personal_unclassified === true` 的补跑 `ingest(input, true)`，已鉴权的保留原 `review_due_at`，在 `restoreRoot`（`obligations` 含 `duePending`）或 `armBackground` 中按原截止时刻恢复。

## 本次审查安排

| 必须回答的问题 / 对应目标 | 能力与使用阶段 | 证据方法、范围与已有定位 |
|---|---|---|
| 合批时间线、双路投递合并、全读取/外发冲刷、超窗二分拆批、范围清退与故障恢复是否正确闭合且不破坏安全边界 | `change-code-review`（实施后独立审查） | 审查 `apps/im-server`、`packages/product-contracts`、`packages/personal-assistant`、`packages/dsh-integration` diff 与新增单元/集成测试，校对最终 delta-spec |
| 批量输入审核模型实际收到的单模态 `system`、紧凑 `timeline`（短序号 `1..k`、`omissions` 区分 `history_window`/`timeline_window`）是否语义清晰、无 `needs_owner` 丢消息陷阱或跨发言者误伤，且 `read_messages` 前置冲刷阻止未审原文暴露给主 PA | `agent-context-review`（设计模式 + 实施模式独立审查） | 亲自读取真实组装入口捕获的 `pa.review('input')` 完整 `system` 与 `messages` 请求载荷（含混合群务、未 `@PA` 伪装系统指令、主人穿插带图消息、窗口外引用、预算裁剪）及解析结算行为 |
| 参与群连续普通消息与混合消息场景下，审核请求数与输入/输出 token、高优批审耗时是否达标且保持准入/消重/唤醒不变量 | `performance-review`（设计模式 + 实施模式独立审查） | 在相同群历史、消息样本与 `@deepseek-ai/dsh-token-meter/estimate` 口径下对照基线（`4ff83afda`）与候选实现的请求次数、输入/输出 token、耗时、准入结果及唤醒次数 |

## 契约层增量 (delta-spec)

- Gateway Personal Agent: [`specs/gateway/personal-agent.md`](specs/gateway/personal-agent.md)（对应 canonical [`docs/specs/gateway/personal-agent.md`](../../specs/gateway/personal-agent.md)，修改 `PA 输入审核以消息为独立准入单位` 与 `输入审核获得有界原始对话背景` 两条 Requirement，明确参与群非高优消息按唤醒及主动读取/外发边界合并送审、范围收紧清退、消息级失权隔离及批量时间线有界上下文语义；Requirement 总数保持 19 不变）。

## 风险与回退

- **风险 1：批量请求中模型漏判、错填短序号或输出格式偏移**。通过 `1..k` 整数序号全集校验 + `withStandaloneRetry` 格式重试拦截，失败转 `review_unavailable` 提醒主 PA，绝不静默当 `allow`；禁用入站 `needs_owner` 枚举杜绝正常群务消息无声丢失。
- **风险 2：同批混入带附件消息、单条不可访问消息或超长单条消息连累正常消息**。待审附件前置单条 `failed`、消息级不可访问单条结算 `source_unavailable` 不撤整群、精确 `context_overflow` 错误码驱动二分拆批，防止连坐与故障重试风暴。
- **风险 3：双路投递（观察流 + Web Relay）或主动查询（`read_messages`）绕过/卡死状态机**。通过双路信封归一化合并、终态双路回执结清及 `read_messages`/`search_messages`/`send` 前置冲刷闭合。
- **回退方案**：数据库仅在 `inbox` 表新增可空列 `review_due_at`，兼容旧版表结构；回退代码重启后，未开始的 `pending` 消息按旧版逐条准入，无数据迁移负担。

## 一次性部署迁移

无。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 无常驻服务（库级与跨包集成测试直接驱动真实 SQLite、IM handler、PA GlobalAgent 与 DSH integration） | 无 | 无 | `pnpm build && pnpm typecheck && pnpm test` 通过 |

**Review 驱动方式**: 运行窄测试（`pnpm vitest run apps/im-server/tests/personal-input-context.test.ts packages/personal-assistant/tests/input-admission.test.ts packages/personal-assistant/tests/personal-attention.test.ts packages/dsh-integration/tests/personal-security.test.ts`）验证跨模块契约、双路投递、主动查询前置冲刷、真实请求组装证据与恢复不变量；运行可复现基准脚本核对样本 A/B 前后请求数、输入/输出 token 与耗时；不需要启动 Web/iOS 客户端常驻进程。

**验收前置**: 无。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1 | 实现并验证参与群按唤醒批次合并输入审核 | 无 | 单组 | `apps/im-server`、`packages/{product-contracts,personal-assistant,dsh-integration}`、测试与证据 | **[reviewer]** 参与群连续普通发言到期、遇高优唤醒或主 PA 主动查询历史时均先完成安全准入且合法消息完整可读、不重复唤醒；同批混入未 `@PA` 伪装指令或越界索取时单独拦截并触发主人私聊提醒、原群拒绝与累计五次自动屏蔽，不牵连同批正常消息；故障中断可恢复且支持单条显式重审；到期前排除来源或切换「仅限本人」立即清退待审积压不发起模型审核；样本 A 审核请求数降至 `1`（输入 tokens `≤ 8,000`）、样本 B 审核请求数降至 `2`（输入 tokens `≤ 15,000`）。**[worker]** 完成 IM 紧凑批量上下文投影（含 `source_allowed` 与 `unavailable_message_ids` 隔离）、`pa.review` 批量分模态提示词（仅 `allow|deny` + 短序号 `1..k`）与对齐 `standalone-model-retry` 的 `context_overflow` 二分拆批、PA 双路投递幂等合并、`review_due_at` 后台定时/恢复接线及全冲刷入口（到期、`wake`、`inbox check/read`、`read_messages`/`search_messages`、`send` 门禁、满 20 条上限）；覆盖共同群双路并发投递、飞书参与群镜像投递、`read_messages` 前置拦截与 `recordQueryRead` 消重、穿插带图主人消息、单条超窗拆批、模型超时不拆批风暴、漏判序号 fail-closed、重启保留剩余期限、范围清退及第 5 次自动拉黑测试；产出模型实际可见请求原件样本与前后同口径性能对比证据；通过窄测试、`pnpm build && pnpm typecheck`、`./scripts/docs-check` 及运行时依赖契约测试。 |
