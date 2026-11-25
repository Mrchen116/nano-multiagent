# perf-789 Design Review

## Round 1

### Metadata

- reviewer: `change-design-reviewer`（独立 Gate 2 设计审查子 Agent，并入 `agent-context-review` 设计模式与 `performance-review` 设计模式）
- reviewer target: `perf-789-pa-group-input-review`（worktree 分支 `unit/perf-789-pa-group-input-review`，含已提交 [motivation.md](motivation.md) 与暂存区 [design.md](design.md)、[specs/gateway/personal-agent.md](specs/gateway/personal-agent.md)、`M1-batch-input-review/.gitkeep`）
- review_mode: `full`
- mode_reason: 首次 Gate 2 独立设计审查；完整覆盖现状断言、跨包架构边界、准入与批次冲刷数据流、双通道幂等与恢复、模型可见 Context 设计、性能目标与不变量、delta-spec 及 M1 交付安排。
- started_at: 2026-11-25T18:49:41+09:00
- completed_at: 2026-11-25T19:04:00+09:00
- duration: 约 14 分钟

### Verdict

**Issues Found — 2 CRITICAL / 3 WARNING（另有 2 项可选 Recommendations）。**

整体方向紧扣原始痛点与用户确认的安全边界：不免除未 `@PA` 群消息的独立安全审核，而是复用零模型开销的 `pa.source.admit` 在抵达时完成身份与优先级分流，将无需立即唤醒的参与群非主人消息留在 `inbox` 待审并在唤醒/读取边界按会话合并送审、按单条消息独立结算，避免活跃群每条普通消息重复编码发送 20 条前序历史。职责划分符合 [SPEC.md](../../../SPEC.md)，无需新建外部调度器或一次性数据迁移脚本。

当前尚不能直接放行进入实施：主动历史读取与外发门禁存在绕过待审队列的安全与消重缺口（`R1-C1`），共同群双路投递（`pa.observations.available` + `relay.message`）及飞书观测入站存在待审落库、身份冲突与回执闭环断裂（`R1-C2`），且 `review_due_at` 的后台定时/恢复接线（`R1-W1`）、跨进程超窗拆批与不可访问收口契约（`R1-W2`）、以及批量审核模型的提示词/字段设计（`R1-W3`）需在实施前收口。

### Coverage 与证据

- **现状断言与真实生产组装入口核实**：
  - 独立读取 [apps/node/src/main.ts](../../../apps/node/src/main.ts)（`GlobalAgent`、`ExternalChannels`、`Heartbeat`、`ConfigurationOperations.apply/restrictToOwner`、`NodeUpdater.prepare` 忙碌探针及分区恢复接线），确认 Web IM `relay.message`（第 276–282 行）与 `pa.observations.available`（第 263 行）均汇入 `GlobalAgent`，飞书 PA 入站在 [packages/personal-assistant/src/external.ts](../../../packages/personal-assistant/src/external.ts)（第 181–185、453–478 行）先镜像为 IM `external-incoming` 事件（`suppress_relay: true`）再经观察事件流进入 `GlobalAgent`。
  - 独立读取 [packages/personal-assistant/src/global-agent.ts](../../../packages/personal-assistant/src/global-agent.ts)、[personal-assistant.ts](../../../packages/personal-assistant/src/personal-assistant.ts)、[inbox.ts](../../../packages/personal-assistant/src/inbox.ts)、[inbox-review.ts](../../../packages/personal-assistant/src/inbox-review.ts)、[attention.ts](../../../packages/personal-assistant/src/attention.ts)，核实现行 `ingestAdmitted -> personal.admit` 确实对所有 `personal_is_owner !== true && personal_delivery === 'participant'` 消息同步逐条调用 `pa.input.context` 与 `pa.review('input')`，先于 `chatDelivery` 高/背景优先级分流。
  - 独立读取 [apps/im-server/src/personal-input-context.ts](../../../apps/im-server/src/personal-input-context.ts)、[personal-agent.ts](../../../apps/im-server/src/personal-agent.ts)、[messaging.ts](../../../apps/im-server/src/messaging.ts)、[schema.sql](../../../apps/im-server/src/schema.sql)、[packages/product-contracts/src/runtime-rpc.ts](../../../packages/product-contracts/src/runtime-rpc.ts)、[packages/dsh-integration/src/personal-security.ts](../../../packages/dsh-integration/src/personal-security.ts) 与 [standalone-model-retry.ts](../../../packages/dsh-integration/src/standalone-model-retry.ts)，核实现行 20 条历史窗口、8,192 token 历史预算、`withStandaloneRetry` 重试边界及 `pa.incident.report` 累计 5 次自动拉黑闭环。

- **架构、职责方向与复用判断**：
  - 依赖方向严守架构红线：`apps/im-server` 仅负责 SQLite 权威消息与权限过滤的时间线投影；`packages/product-contracts` 持有 `pa.review` RPC 协议；`packages/personal-assistant` 持有节点侧待审生命周期、批次调度、范围清退与恢复，仅通过 `RuntimePort` 请求 `pa.review`；只有 `packages/dsh-integration` 调用 `@deepseek-ai/dsh-llm` 与 `@deepseek-ai/dsh-token-meter/estimate`。
  - 复用判断合理：复用 `pa.source.admit` 在抵达时零 LLM 成本鉴别主人控制命令（`/stop`、`/new`）、观察会话与高优寻址；复用既有 `InboxReviews` 状态机与 `restrict` / `revokeUnavailableSources` 清退机制，在 `inbox` 表增量添加可空 `review_due_at` 而将 `inbox_schedule` 保持为仅接纳 `admitted` 消息，从存储层杜绝未审文本混入通知摘要，无需引入新表或外部队列。

- **用户约束、迁移、原型边界与审查安排**：
  - 完整覆盖 [motivation.md](motivation.md) Q1–Q3 澄清要求：未 `@PA` 参与群消息不免审、按单条消息独立结算、被拒消息（无论是否 `@PA`）同样走主人私聊提醒 + 原群拒绝 + 5 次自动屏蔽闭环、审核前收紧协作范围或排除群聊立即清退待审积压且不调用审核模型。
  - 本变更纯属后端/运行时准入管线优化，无任何 Web/iOS 界面与交互变更，不生成 `prototype.html` 符合原型判断边界；SQLite 新增可空列且兼容旧状态机，无需 `deployment-prompt.md`。
  - 单一 Milestone `M1` 范围与跨包耦合面相称，无并行写冲突；`design.md` 已安排实施后 `change-code-review`、`agent-context-review`（实施模式）与 `performance-review`（实施模式），覆盖主要风险面。

- **Agent Context Review（设计模式）**：
  - **受影响消费者**：独立输入安全审核模型（`pa.review` 的 `kind='input'`，单轮无状态、无工具调用）；主 PA 的系统提示词、工具声明与出站披露审核 `pa.review('action')` 保持不变。
  - **生命周期与组装判断**：按时间顺序组织 `previous`（前序证据）→ `timeline`（含 `needs_decision` 标记的待审与穿插语境）及补充 `reply_targets`、配合全集 ID fail-closed 校验的方向正确，避免了“省略即放行”的漏判风险。但从审核模型当轮实际可见内容审查，存在三处需修正的 Context 缺陷（详见 `R1-W3`）：① 同一静态 `personalReviewPolicy('input')` 混装单条与批量两套互斥输入/输出协议；② 批量输出模板向入站审核开放 `needs_owner` 枚举，而宿主将该值静默结算为既不入 Inbox 也不告警的黑洞状态；③ 每条消息重复携带会话级样板字段并要求模型逐字回抄最多 20 个 36 位 UUID，易因单字符笔误触发整批重试或故障。此外，主 PA 侧若在未冲刷时调 `read_messages` / `search_messages`，会使未审外部原文绕过安全标记直接进入主 PA 上下文（详见 `R1-C1`）。
  - **实施后需观察的运行证据**：在实施阶段 `agent-context-review` 中须亲自读取真实组装捕获的 `pa.review('input')` 完整 `system` 与 `messages` 请求载荷（覆盖混合群务讨论 + 未 `@PA` 伪装系统指令 + 主人穿插消息 + 窗口外引用 + `omissions` 预算裁剪场景），核验无双模协议冲突、无多余内部样板字段、且模型逐条裁决与宿主结算准确对应。

- **Performance Review（设计模式）**：
  - **指标与核算**：基线 commit（`4ff83afda`）、样本构造与 `@deepseek-ai/dsh-token-meter/estimate` 分词口径明确。按基线单次策略 `1,432` tokens、21 条消息 `2,312` tokens（约 `110` tokens/条）推算，样本 A 合并为 1 次请求（20 条 `previous` + 20 条 `timeline`）输入约为 `6,000~6,400` tokens（满足 `≤ 8,000` 目标），样本 B 合并为 2 次请求累计输入约为 `10,500~11,500` tokens（满足 `≤ 15,000` 目标）；若同步采纳 `R1-W3` 去重会话级字段，输入与输出 token 还将进一步下降。
  - **不变量与退化路径检查**：发现两处与性能和行为不变量直接相关的风险：一是主动历史查询未冲刷会导致 `recordQueryRead` 消重失效、10 分钟后重复唤醒主模型（`R1-C1`）；二是若超窗拆批与普通模型故障未在 RPC 契约层严格区分，模型服务异常时 20 条批次二分拆批会退化为最多 39 次串行请求风暴（`R1-W2`）。跨会话并行冲刷与输出/延迟指标记录见 `R1-R1`。

- **Delta-spec 核查**：
  - [specs/gateway/personal-agent.md](specs/gateway/personal-agent.md) 正确锚定 canonical [docs/specs/gateway/personal-agent.md](../../specs/gateway/personal-agent.md) 的 `PA 输入审核以消息为独立准入单位` 与 `输入审核获得有界原始对话背景` 两条 Requirement，保留了交互卡片源码投影、单条故障隔离、显式重审与不越权读取后续消息等既有有效条款，与其余 17 条 Requirement（如观察聊天即时可读、累计五次自动屏蔽、来源控制与附件 fail-closed）无语义冲突；需随 `R1-C1` 补齐主 PA 主动读取该会话历史或外发前的待审冲刷条款。

### 历史问题闭环

首轮审查（Round 1），无历史遗留问题。

### Issues

#### R1-C1 — 主 PA 主动查询消息历史或向目标会话外发前未冲刷待审积压，导致未审消息直接暴露且已读消重失效

- **级别：CRITICAL；状态：open。**
- **位置**：[design.md](design.md) 第 133–137 行（`flushPendingReviews` 触发时机）、[specs/gateway/personal-agent.md](specs/gateway/personal-agent.md) 第 7–10 行；对照生产代码 [packages/personal-assistant/src/global-agent.ts](../../../packages/personal-assistant/src/global-agent.ts) 第 703–705、790–791 行，[packages/personal-assistant/src/inbox.ts](../../../packages/personal-assistant/src/inbox.ts) 第 605–608、802–830 行，[packages/personal-assistant/src/personal-assistant.ts](../../../packages/personal-assistant/src/personal-assistant.ts) 第 244、256 行，[packages/personal-assistant/src/heartbeat.ts](../../../packages/personal-assistant/src/heartbeat.ts) 第 110 行。
- **证据**：
  1. 现行实现在参与群消息抵达瞬间同步完成 `pa.review('input')`。当主 PA 因 `Heartbeat`（`heartbeat.ts:110` 直接调用 `runtime.request('session.submit')`，不经过 `GlobalAgent.wake`）、原生 `Cron` 调度、内部子任务回报唤醒，或在一个长轮次运行中途按系统提示词调用 `read_messages` / `search_messages` 读取群聊时，已到达的非主人群消息均已完成审核拦截与违章计数，且合法消息已处于 `review_state = 'admitted'`。
  2. 本设计第 133–137 行仅在 `backgroundDrain`、`wake`、`inbox(action="check" | "read")` 与满 20 条上限时冲刷待审队列，遗漏了 `GlobalAgent.execute` 中的 `read_messages` / `search_messages` 以及 `PersonalAssistant.send` 的发信前重验（`inbox.blocking` 在 `inbox.ts:606-607` 仅检查 `review_state = 'admitted'`）。
  3. 同时，`global-agent.ts:703-705` 在 `read_messages` 返回后调用 `inbox.recordQueryRead`（`inbox.ts:812-814`）同样只匹配 `review_state = 'admitted'` 的未读行以标记消费。
- **未修后果**：
  1. **安全边界突破**：主 PA 在上述时机调用 `read_messages` / `search_messages` 会从 IM 中心直接读到尚处于 `pending` 的未 `@PA` 伪装系统指令或套话原文，既无拦截与防备性事件提醒，也未计入 5 次自动拉黑（即使已是第 5 次攻击也不会先触发拉黑与 `actor_risk`），违背 [motivation.md](motivation.md) Q1 与目标状态的核心安全承诺。
  2. **重复唤醒回归**：主 PA 已通过 `read_messages` 完整读过的普通群消息因仍处 `pending` 无法被 `recordQueryRead` 消费，10 分钟到期冲刷后仍会作为“新未读”再次虚假唤醒主 PA。
  3. **发信门禁漏判**：主 PA 向群聊调用 `send_message` / `send_user_message` 时，若同群刚抵达正在排队或批审（`pending` / `reviewing`）的高优 `@PA` 消息，`inbox.blocking` 返回 `false`，无法触发 `held_for_revalidation`。
- **修正边界**：在主 PA 执行 `read_messages` / `search_messages` 前冲刷对应目标会话（未限定单会话 `target` 或按 `message_id` 查询时冲刷该 PA 全部待审会话），确保风险消息先完成拦截上报、合法消息先进入 `admitted` 供 `recordQueryRead` 正常消重；在 `PersonalAssistant.send` 校验 `inbox.blocking` 前先冲刷/等待目标会话在途与待审高优队列；同步在 delta-spec `参与群背景消息按唤醒批次合并送审` 条款补入主动历史读取与同会话外发前的送审边界。

#### R1-C2 — 飞书观测直入 `ingest` 与共同群双路投递（`pa.observations.available` + `relay.message`）下的待审落库、身份冲突与回执闭环断裂

- **级别：CRITICAL；状态：open。**
- **位置**：[design.md](design.md) 第 16、123–131、139–141 行；对照生产代码 [apps/im-server/src/messaging.ts](../../../apps/im-server/src/messaging.ts) 第 57、607–612、713 行，[apps/im-server/src/schema.sql](../../../apps/im-server/src/schema.sql) 第 566–590 行，[packages/personal-assistant/src/external.ts](../../../packages/personal-assistant/src/external.ts) 第 181–185、470–478 行，[packages/personal-assistant/src/global-agent.ts](../../../packages/personal-assistant/src/global-agent.ts) 第 166–188、631–665、1390–1401 行，[packages/personal-assistant/src/inbox.ts](../../../packages/personal-assistant/src/inbox.ts) 第 325–352、439–444 行。
- **证据**：
  1. **观测路径不经过 `acceptRelay`**：飞书 PA 群消息通过 `ExternalChannels.mirrorAdmitted`（`suppress_relay: true`）写入 IM 后，仅由 `GlobalAgent.recoverPersonalObservations` 直接调用 `this.ingest(obsInput, true)`（`global-agent.ts:631`），从不调用 `acceptRelay`。现行代码依赖 `PersonalAssistant.admit` 第 73 行 `if (!inbox.input(...)) inbox.receive(saved, false)` 补建 `inbox` 行；设计第 124、129 行假设 `acceptRelay` 已持久化原始输入而仅在 `stage` 更新认证元数据与 `review_due_at`。
  2. **共同群双路投递字段不对称**：在主人与 PA 共处的 Web IM 群（本变更最核心场景）中，`Messaging.send`（`messaging.ts:607-612`）在事务内先触发 `personal_observation_event` 并在 `publishEvent`（第 57 行）向节点推送 `pa.observations.available`，提交后再推送 `relay.message`。`recoverPersonalObservations` 组装的 `obsInput.message`（10 个投影字段，带 `metadata.pa_observation = true`，无 `agent_receipt`）与 `relay.message` 的完整 `ChatMessage`（含 `conversation_id`、`delivery_status`、`receipts_requested` 等）在 `inbox.acceptRelay`（`inbox.ts:327-331`）的 `sortedJsonAscii({agent, target, message})` 校验下不相等。
  3. **延迟结算回执短路**：`GlobalAgent.receipt`（`global-agent.ts:1391`）在 `input.metadata.pa_observation === true` 时直接走 `transmitReceipt`（对 Web IM 为空操作）并返回，不调用 `inbox.settleRelay`。
- **未修后果**：
  1. 若 `stage` 未原子补建缺失的 `inbox` 行，飞书参与群普通消息及先到的 Web 观测消息更新 0 行后即被 `recoverPersonalObservations` 第 647 行的 `pa.observations.ack(stage='processed')` 标记完成，消息永久静默丢失。
  2. 在主人与 PA 共处的 Web IM 群中，先到的 `obsInput` 写入 `inbox.payload` 后，紧随其后的 `relay.message` 在 `acceptRelay` 必现 `Relay input identity conflict` 异常并陷入 `scheduleAgentRecovery` 退避循环。
  3. 若 `inbox.payload` 保留了先到的 `obsInput` 或被后到的 `obsInput` 覆盖为 `pa_observation: true`，10 分钟后 `flushPendingReviews` 将消息结算为 `rejected` / `failed` 并调用 `this.receipt(input, 'completed')` 时会跳过 `inbox.settleRelay`，导致 Web IM 的 `relay_receipts` 永久滞留在 `accepted`（或丢失 `agent_receipt` 已读回执标记）。
- **修正边界**：在 `design.md` 明确：① `stage` 对尚未入 `inbox` 的观测输入原子建行；② 同一 `(agent_id, message_id)` 在 `pa_observation` 与 `relay.message` 双路先后到达时的身份归一化与元数据合并规则（避免 `Relay input identity conflict`，保留 `relay.message` 的 `agent_receipt` / 非观察投递属性且不推迟首次 `review_due_at`）；③ 批审终态按 `(agent_id, message_id)` 可靠结算 `relay_receipts` 与飞书回执；并在 M1 测试中覆盖「主人 + PA 共处同一 Web IM 群双路并发投递」与「飞书参与群镜像投递」。

#### R1-W1 — `armBackground`、`restoreRoot`、`wake` 与 `GlobalAgent.busy` 未解耦 `inbox_schedule` 依赖，导致纯待审队列定时器不挂载与恢复漏判

- **级别：WARNING；状态：open。**
- **位置**：[design.md](design.md) 第 79–82、134–136、144 行；对照生产代码 [packages/personal-assistant/src/global-agent.ts](../../../packages/personal-assistant/src/global-agent.ts) 第 134–137、355、378、438–458、551–564 行，[packages/personal-assistant/src/inbox.ts](../../../packages/personal-assistant/src/inbox.ts) 第 480–486、616–619 行。
- **证据**：
  1. 决策 2 规定未审消息只写 `inbox.review_due_at`、不入 `inbox_schedule`。但 `armBackground()`（`global-agent.ts:443`）仅从 `inbox.background(agentId)`（只查 `inbox_batch` 与 `inbox_schedule`）收集 `deadlines`：当 PA 仅有参与群 `pending` 消息而无观察会话 `admitted` 积压时，`deadlines` 为 `[]`，`backgroundTimer` 根本不会创建，第 134 行的 `backgroundDrain` 永远不会触发。
  2. `restoreRoot()`（`global-agent.ts:551-563`）在 `checkpoint && !obligations` 且 `check.rootSettled` 时提前返回，`obligations` 同样只看 `inbox.wakePending` / `inbox.background`；`wake()`（第 355 行）以 `while ((watermark = inbox.wakePending(agentId)) !== undefined)` 作为入口，若冲刷未置于读取 `watermark` 之前，则在无既有 `inbox_schedule` 时无法进入循环（如忙碌会话 `session.status === 'idle'` 回调），或在有既有 `inbox_schedule` 时因冲刷插入新 `ord` 触发第 378 行 `wakePending !== watermark` 造成重复 `checkInbox` / `describe`。
- **未修后果**：仅加入参与群而无观察会话未读的 PA 在收到普通群消息后 10 分钟永不触发批审与唤醒；重启恢复或会话由忙转闲时漏冲刷已到期批次；或在途批审因 `GlobalAgent.busy` 漏检被 `NodeUpdater` 中断。
- **修正边界**：明确 `InboxReviews` 暴露最早待审截止时间与到期判断（如 `nextDueAt(agentId)` / `duePending(agentId)`）：① `armBackground()` 取 `inbox.background(agentId)?.dueAt` 与 `reviews.nextDueAt(agentId)` 的最小值挂载定时器，`backgroundDrain` 对到期 PA 先 `refreshPersonalSources`、再 `flushPendingReviews`、最后在 `wakePending !== undefined` 时 `wake`；② `GlobalAgent.busy` 与 `restoreRoot` 的 `obligations` 同步纳入 `duePending` 及在途 `reviewBatches.size > 0`；③ `wake()` 在 `while ((watermark = inbox.wakePending(...)))` 循环前先完成全会话待审冲刷。

#### R1-W2 — 批量审核超窗拆批缺少跨进程错误分类契约，且 `pa.input.context` 单条失权收口与穿插附件规则不完整

- **级别：WARNING；状态：open。**
- **位置**：[design.md](design.md) 第 83–85、100–105、110–112、118、138–141 行；对照生产代码 [packages/dsh-integration/src/personal-security.ts](../../../packages/dsh-integration/src/personal-security.ts) 第 154–165、173–186 行，[packages/dsh-integration/src/standalone-model-retry.ts](../../../packages/dsh-integration/src/standalone-model-retry.ts) 第 75–79 行，[packages/product-contracts/src/runtime-rpc.ts](../../../packages/product-contracts/src/runtime-rpc.ts) 第 95–98 行，[packages/personal-assistant/src/global-agent.ts](../../../packages/personal-assistant/src/global-agent.ts) 第 299 行。
- **证据**：
  1. **超窗错误被吞没 vs 故障拆批风暴**：设计第 118 行写「若仅保留全部 `needs_decision: true` 条目仍超过 `available`，抛出超窗错误，由调用方二分拆批重试」。但 `pa.review` 在 DSH 子进程内由 `reviewPersonal`（`personal-security.ts:185`）捕获所有异常并统一转为 `{ decision: 'unavailable', reason: 'Independent review unavailable: ...' }`，且第 111 行的 `pa.review` RPC 结果未定义区分「窗口超限」与「模型超时/5xx/格式失败」的结构化字段。同时 `standalone-model-retry.ts:76-78` 校验窗口时额外计入每条消息 `+4` token 及 `JSON.stringify(options.tools ?? [])` 开销，与第 118 行 `contextWindow - cost(policy) - 4096 - 512` 存在边界差。
  2. **`targets` 全空越界与消息级不可访问误撤整群**：第 101 行规定仅当全部不可访问且 `!sourceAllowed` 时返回会话不可用错误；若会话本身仍可访问（`sourceAllowed === true`）但本批目标消息均因消息级条件进入 `unavailable_message_ids`（`targets = []`），第 102–103 行访问 `t_1.sequence` 将直接空指针报错。且第 138–141 行未定义 `unavailable_message_ids` 的结算方式——若沿用 `global-agent.ts:299` 对 `source_unavailable` 调用 `inbox.revokeSource`，单条不可访问消息会误清空整个有效群聊的全部未读；若不带 `error_code` 结为 `rejected` 则会误报 `prompt_injection` 违章。
  3. **穿插语境消息含附件与不可访问记录**：第 105 行将 `t_1..t_k` 间的主人发言或非目标消息作为 `needs_decision: false` 放入 `timeline`。若主人穿插发了图片或前序已前置 `failed` 的附件消息位于区间内，需明确仅对 `needs_decision: true` 条目执行附件 fail-closed，避免语境消息的 `attachments` 元数据阻断同批纯文本审核；区间内 `!messageAllowed` 的穿插消息亦应同 `previous` 一致记入 `omissions`（`history_unavailable`）。
- **未修后果**：若按泛化的 `unavailable` 触发二分拆批，模型服务故障时单群 20 条积压会退化为最多 39 次串行模型调用风暴；若不传递结构化超窗码，则二分拆批永远不生效，单条超长消息会连坐整批正常消息全部 `failed`；消息级不可访问会导致空数组异常或误删整群 Inbox。
- **修正边界**：在 `pa.review` 输出 schema 增加显式超窗原因码（如 `error_code?: 'context_overflow'`），仅在该错误码且批大小 `> 1` 时二分拆批，并将 `inputReviewEvidence` 的预算扣减与 `standalone-model-retry.ts` 严格对齐；明确 `targets.length === 0` 且会话仍有效时不访问 `t_1`、不调模型，将 `unavailable_message_ids` 单条结算为 `rejected`（`error_code: 'source_unavailable'`，不报 incident、不撤整群），仅在会话整体 `!sourceAllowed` 时调用 `revokeSource`；明确附件检查仅针对 `needs_decision: true` 条目。

#### R1-W3 — 批量输入审核的模型 Context 存在双协议指令冲突、`needs_owner` 静默丢消息陷阱及长 UUID 回抄脆弱性

- **级别：WARNING；状态：open。**
- **位置**：[design.md](design.md) 第 99–107、113–118 行；对照生产代码 [packages/dsh-integration/src/personal-security.ts](../../../packages/dsh-integration/src/personal-security.ts) 第 111–165 行，[packages/personal-assistant/src/personal-assistant.ts](../../../packages/personal-assistant/src/personal-assistant.ts) 第 94–100 行，[apps/im-server/src/personal-agent.ts](../../../apps/im-server/src/personal-agent.ts) 第 184–194 行。
- **证据**：
  1. **单条/批量双模提示词自相矛盾**：现行 `personalReviewPolicy('input')` 声明 `The current message is the only pending input... Return one JSON object only: {"decision":...}`；设计第 114 行拟在同一提示词内叠加「当输入包含 `timeline` 时……严格返回 `{"decisions":[...]}`」。同一 System Prompt 同时给出两套互斥输入假设与输出 JSON 结构，轻量审核模型在 `k=1` 批次或单条重审时易输出错误外壳。
  2. **`needs_owner` 在入站审核中会制造消息黑洞**：设计第 114 行要求批量提示词指示模型输出 `"decision":"allow|deny|needs_owner|unavailable"`。但核对 `personal-assistant.ts:96`、`inbox.ts:524` 与 `inbox-review.ts:48,54`，当入站审核返回 `decision: 'needs_owner'`（无 `incident`）时，消息被结算为 `review_state = 'rejected', review_error_code = 'needs_owner'`——**既不进入可读 Inbox，也不触发 `reportInputIncident` 告知主人，也不进入 `review_failures`**。群聊中常见的普通协作请求（如同事说「麻烦把上次排期表发群里」，本应作为不可信普通消息 `allow` 进 Inbox，由主 PA 与出站披露审核把关授权）一旦被入站模型按字面选为 `needs_owner`，就会无声丢失。
  3. **长 UUID 全集回抄与重复样板字段**：`messageEvidence`（`personal-agent.ts:184-194`）在每条消息上重复输出 `conversation_id`、`conversation_type`、`channel`、`delivery`、`owner_direct`、重复的顶层 `is_owner` 与空 `attachments: []`（且第 99–107 行未定义第 117 行顶层 `conversation` 字段的来源），并要求模型在单次 JSON 数组里精确回抄最多 20 个完整 36 位 UUID；结合决策 4 的全集精确匹配规则，单个十六进制字符笔误即导致整批 20 条消息重试或全部转 `unavailable`。
- **未修后果**：群成员合法请求因被误标 `needs_owner` 而静默蒸发（直接违背 [motivation.md](motivation.md)「正常群务消息正常准入可读」）；轻量分类模型因双协议冲突或长 UUID 抄写笔误频繁触发格式重试与整批 `review_unavailable`，同时浪费批量输入/输出 token。
- **修正边界**：按当次请求模式生成单一无歧义的输入审核提示词与输出 schema（或内部将单条与批量统一为同一 `timeline` 协议）；将模型侧入站判定枚举收窄为 `allow | deny`（明确普通未授权外部请求属于 `allow` 不可信数据而非 `needs_owner`，仅注入/伪装身份或系统指令/套取隐私判 `deny`；`unavailable` 由宿主在缺失证据或调用失败时生成）；明确顶层 `conversation` 元数据来源并剥离每条消息重复的会话级/空数组样板字段，在 `personal-security.ts` 内为 `needs_decision: true` 条目分配批内短标识（如 `"1".."20"`）并在解析后映射回真实 `message_id`。

### Recommendations

- **R1-R1 — 跨会话高优冲刷受控并行与性能观测指标补齐**：高优消息进入 `wake` 冲刷同一 PA 下多个不同 `conversation_id` 的待审队列时，各会话互不竞争单飞锁，建议采用 `Promise.all`（或有界并发）并行冲刷，避免多个活跃群的模型耗时串行叠加拖慢主人私聊响应；同时建议在 M1 实施期 `performance-review` 证据中除请求数与输入 token 外，一并记录输出/推理 token 及样本 B `@PA` 触发合并批审的单次耗时。
- **R1-R2 — 区分前序历史截断与批次内穿插截断的 `omissions` 标识**：[design.md](design.md) 第 102 行（`previous` 超 20 条）与第 105 行（`timeline` 穿插非目标消息超 20 条）使用了相同的 `{ reason: 'history_window', limit: 20 }`。建议将批次内穿插裁剪命名为独立 `reason`（如 `timeline_window`），便于审核模型准确获知缺失位置是在批次前还是两条待审消息之间。

### Author Resolutions

- **R1-C1 (`accepted`)**：核实 `global-agent.ts:703-705, 790-791`、`inbox.ts:605-608, 802-830`、`personal-assistant.ts:235, 247` 与 `heartbeat.ts:110` 属实。已在 [design.md](design.md)（§关键决策 3、§接口与数据流 3.3 全边界冲刷、§本次审查安排、§Milestones）与 [specs/gateway/personal-agent.md](specs/gateway/personal-agent.md) 补齐：主 PA 执行 `read_messages`/`search_messages` 前冲刷目标会话（无单会话 `target` 时并行冲刷全会话），使风险消息先拦截上报、合法消息先转为 `admitted` 供 `recordQueryRead` 消重；`PersonalAssistant.send` 在检查 `inbox.blocking` 前冲刷目标会话且 `inbox.blocking` 覆盖 `pending`/`reviewing`/`admitted` 高优行。
- **R1-C2 (`accepted`)**：核实 `messaging.ts:607-612, 713`、`external.ts:181-185`、`global-agent.ts:631-637, 1390-1401` 与 `inbox.ts:325-352` 属实。已在 [design.md](design.md)（§关键决策 1、§接口与数据流 3.1–3.3、§Milestones）补齐：`stage` 对缺失行原子调用 `inbox.receive` 建行；`acceptRelay` 与 `stage` 对同一 `(agent_id, message_id)` 的 `pa_observation` 与 `relay.message` 双路信封做核心不可变字段校验与归一化升级（保留完整 `relay.message` 信封、`agent_receipt`、已认证 `personal_*` 字段与首次 `review_due_at`，避免身份冲突及晚到观察覆盖）；批审终态按 `(agent_id, message_id)` 同时结清 `inbox.settleRelay` 与飞书 `transmitReceipt`。
- **R1-W1 (`accepted`)**：核实 `global-agent.ts:132-134, 355, 438-458, 551-563` 属实。已在 [design.md](design.md)（§关键决策 2、§接口与数据流 3.3–3.4）明确：`InboxReviews` 暴露 `nextDueAt`/`duePending`；`armBackground` 取 `inbox.background` 与 `reviews.nextDueAt` 的最小截止时刻并在 `backgroundDrain` 中先 `refreshPersonalSources` → `flushPendingReviews` → `wake`；`GlobalAgent.busy` 与 `restoreRoot.obligations` 接入 `duePending` 及在途批审锁；`wake` 在读取 `watermark` 循环前先完成待审冲刷。
- **R1-W2 (`accepted`)**：核实 `standalone-model-retry.ts:75-79` 与 `personal-security.ts:154-185` 属实。已在 [design.md](design.md)（§关键决策 4、§接口与数据流 1–3）与 [specs/gateway/personal-agent.md](specs/gateway/personal-agent.md) 修正：`inputReviewEvidence` 预算核算与 `standalone-model-retry.ts`（`+4`/消息及 `tools` JSON 开销）严格对齐，超窗返回结构化 `error_code: 'context_overflow'`，仅在该错误码且批大小 `> 1` 时二分拆批；`pa.input.context` 区分会话级 `source_allowed: false` 与消息级 `unavailable_message_ids`（`targets = []` 时安全返回空时间线，单条失权结为 `error_code: 'source_unavailable'` 不调 `revokeSource`、不报 incident）；附件前置 fail-closed 仅作用于 `needs_decision: true` 待审项，穿插语境消息保留轻量附件摘要。
- **R1-W3 (`accepted`)**：核实 `personal-security.ts:111-165` 与 `personal-assistant.ts:94-100` 属实。已在 [design.md](design.md)（§关键决策 5、§接口与数据流 1–2）修正：单条与批量分模态生成无歧义 System Prompt；模型侧入站判定枚举收窄为 `allow | deny`（明确普通未授权群务请求判 `allow` 交主 PA 与出站披露审核把关，消除 `needs_owner` 丢消息黑洞）；顶层提取一次 `conversation` 并剥离每条消息重复的会话级/空数组样板字段，批内使用短整数序号 `item: 1..k` 并在解析校验后映射回真实 `message.id`。
- **R1-R1 (`accepted`)**：已在 [design.md](design.md)（§接口与数据流 3.3、§本次审查安排、§Runbook）采纳跨会话 `Promise.all` 并行冲刷，并在实施期 `performance-review` 增加输出/推理 token 与高优合并批审耗时观测。
- **R1-R2 (`accepted`)**：已在 [design.md](design.md)（§接口与数据流 1）采纳，将 `timeline` 内非目标穿插消息超 20 条的裁剪原因区分命名为 `timeline_window`。


## Round 2

### Metadata

- reviewer: `change-design-reviewer`（独立 Gate 2 设计审查子 Agent，同一审查者续审，并入 `agent-context-review` 与 `performance-review` 设计模式）
- reviewer target: `perf-789-pa-group-input-review`（worktree 分支 `unit/perf-789-pa-group-input-review`，复审修订后的 [design.md](design.md)、[specs/gateway/personal-agent.md](specs/gateway/personal-agent.md) 及 Round 1 `Author Resolutions`）
- review_mode: `delta`
- retained_from: `Round 1`（[motivation.md](motivation.md) 原始需求、澄清记录与量化目标未变；跨包依赖方向、单 Milestone `M1` 切分、无一次性迁移脚本与无前端原型结论保持有效，沿用 Round 1 证据）
- mode_reason: 本轮修订聚焦关闭 Round 1 的 5 项问题与 2 项建议，涉及 `pa.input.context`、`pa.review`、节点双路投递合并及全读取/外发冲刷边界的有界接口与数据流更新，未改变用户需求与顶层架构。
- started_at: 2026-11-25T19:09:57+09:00
- completed_at: 2026-11-25T19:14:30+09:00
- duration: 约 5 分钟

### Verdict

**Approved — 0 CRITICAL / 0 WARNING（另有 1 项可选 Recommendation）。**

Round 1 提出的 `R1-C1`、`R1-C2`、`R1-W1`、`R1-W2`、`R1-W3` 及 `R1-R1`、`R1-R2` 已全部在 [design.md](design.md) 与 [specs/gateway/personal-agent.md](specs/gateway/personal-agent.md) 中准确闭合，未引入新的架构越界、状态死锁、安全漏放或性能退化风险，具备进入 M1 实施的条件。

### Coverage 与证据

- **不变范围沿用（`retained_from: Round 1`）**：`git diff HEAD -- docs/changes/perf-789-pa-group-input-review/motivation.md` 确认为空；用户侧不变性、量化指标（样本 A `1` 次 / `≤ 8,000` tokens，样本 B `2` 次 / `≤ 15,000` tokens）、跨包依赖红线、零部署迁移脚本及无需 UI 原型的判断沿用 Round 1 核实结论。
- **变更面与波及链路核实**：
  - **全可见/外发边界冲刷与 Dreaming 边界核对**：核对 `design.md` §接口与数据流 3.3（第 145–150 行）与生产代码 `global-agent.ts:697-706, 773-791`、`personal-assistant.ts:190, 244, 256`、`packages/dsh-integration/src/knowledge/dreaming-history.ts:116-130`。`read_messages` / `search_messages` 与 `PersonalAssistant.send` 前置冲刷覆盖了 `Heartbeat`、原生 `Cron`、子任务回报及运行中途主动查询/发信路径；同时确认后台 Dreaming 的 `memory.conversations` 只读已完成根轮次 `cutoff` 前的冻结历史且契约禁止消费 `pa_source_reads` / `inbox`（`apps/im-server/tests/e2e/memory-conversation-production-chain.test.ts:35-48`），设计未误触 `memory.conversations`，边界准确。
  - **双路投递幂等合并与终态回执**：核对 `design.md` §接口与数据流 3.1–3.3（第 131–159 行）与 `inbox.ts:325-352, 439-444`、`global-agent.ts:631-665, 1390-1401`、`external.ts:181-185, 236-239`。先到观察建行、后到 `relay.message` 按核心不可变事实校验升级信封、晚到观察不覆盖非观察 `payload`、以及终态按 `(agent_id, message_id)` 双路结清回执的规则，完整消除了共同群冲突异常、飞书丢消息和回执滞留。
  - **Agent Context Review（设计模式复核）**：核对 `design.md` §接口与数据流 1–2（第 98–127 行）。批量模式提取顶层 `conversation`、剥离单条重复样板字段、使用独立批量提示词、将模型侧判定收窄为 `allow | deny`（显式阐明普通未授权外部请求判 `allow` 交主 PA 与出站审核把关）、并以正整数 `item: 1..k` 替代 20 个 36 位 UUID 回抄，语义清晰、无双协议冲突、无消息黑洞。
  - **Performance Review（设计模式复核）**：核对 `design.md` 第 124 行 `totalRequestCost` 公式，与 `standalone-model-retry.ts:76-78`（单条 user 消息 `+4` 及 `JSON.stringify(options.tools ?? [])` 即 `'[]'` 分词开销、`maxTokens + 512` 预留）逐项一致；仅在 `error_code === 'context_overflow'` 且 `targets.length > 1` 时二分拆批，杜绝了模型超时/5xx 下的串行重试风暴；跨会话采用 `Promise.all` 并行冲刷，紧凑投影进一步扩大了样本 A/B 的输入与输出 token 余量，且实施期审查安排已纳入输出/推理 token 与高优批审耗时。
  - **Delta-spec 与 Milestone 复核**：[specs/gateway/personal-agent.md](specs/gateway/personal-agent.md) 已同步补入主动消息查询/搜索与外发前重验冲刷、单条不可访问不撤整群、`timeline` 穿插背景省略标明原因及待审项附件 fail-closed，与 canonical [docs/specs/gateway/personal-agent.md](../../specs/gateway/personal-agent.md) 其余条款兼容；`M1` 退出标准已完整覆盖新增边界测试与取证项。

### 历史问题闭环

- **R1-C1 — closed**：Author Resolution `accepted`。本轮核实 [design.md](design.md) 第 83–85、148–150、202 行与 [specs/gateway/personal-agent.md](specs/gateway/personal-agent.md) 第 9 行已补齐 `read_messages`、`search_messages` 及 `PersonalAssistant.send`（含本地附件上传前后两次门禁）的前置冲刷，并将 `inbox.blocking` 扩展至 `pending`/`reviewing`/`admitted` 高优未消费行，闭合了安全拦截、`recordQueryRead` 已读消重与发信重验门禁。
- **R1-C2 — closed**：Author Resolution `accepted`。本轮核实 [design.md](design.md) 第 76–78、131–134、158–159、202 行已明确 `stage` 缺失行原子建库、`acceptRelay` 与 `stage` 对 `pa_observation` / `relay.message` 双路信封的核心事实校验与非观察升级合并、以及批审终态按 `(agent_id, message_id)` 同时结清 `inbox.settleRelay` 与飞书回执，并纳入 M1 测试。
- **R1-W1 — closed**：Author Resolution `accepted`。本轮核实 [design.md](design.md) 第 80–82、146–147、152、163 行已明确 `InboxReviews` 暴露 `nextDueAt` / `duePending`，接入 `armBackground` 最小截止计算、`backgroundDrain`（`refreshPersonalSources` → `flushPendingReviews` → `wake`）、`wake` 循环前冲刷、`restoreRoot.obligations` 与 `GlobalAgent.busy`。
- **R1-W2 — closed**：Author Resolution `accepted`。本轮核实 [design.md](design.md) 第 86–88、100–101、115、121、124–126、154–155 行与 [specs/gateway/personal-agent.md](specs/gateway/personal-agent.md) 第 13–15、29–30 行已对齐 `standalone-model-retry.ts` 窗口开销公式、新增 `error_code: 'context_overflow'` 限定二分拆批条件、区分 `source_allowed: false` 与单条 `unavailable_message_ids`（`targets = []` 安全返回且不误调 `revokeSource`），并限定仅对 `needs_decision: true` 条目执行附件前置 fail-closed。
- **R1-W3 — closed**：Author Resolution `accepted`。本轮核实 [design.md](design.md) 第 89–90、103–109、117–122 行已拆分为单条/批量独立提示词、将模型侧入站判定枚举收窄为 `allow | deny`（消除 `needs_owner` 静默丢消息黑洞）、上提顶层 `conversation` 去重样板字段，并引入批内短整数 `item: 1..k` 映射与全集校验。
- **R1-R1 / R1-R2 — closed（已采纳）**：跨会话 `Promise.all` 并行冲刷、实施期输出/推理 token 与高优批审耗时记录，以及 `timeline_window` 独立省略原因均已落入 [design.md](design.md) 第 108、152、171、194 行。

### Issues

无（`0 CRITICAL / 0 WARNING`）。

### Recommendations

- **R2-R1 — 共享单条解析函数与 `context_only` 免调度守卫的实施防呆**：① `packages/dsh-integration/src/policy/codex.ts:59`（出站披露审核）与单测 `packages/dsh-integration/tests/codex-approval.test.ts:22` 直接复用了导出的 `parsePersonalDecision` 并校验 `allow | deny | needs_owner | unavailable` 四值，实施时建议保持导出 `parsePersonalDecision` 原四值解析兼容，为入站审核单独使用 `allow | deny` 校验器（如 `parseInputDecision` / `parseBatchInputDecisions`）；② [design.md](design.md) 第 157 行将 `admitted` 消息写入 `inbox_schedule` 时，建议直接复用 `inbox.schedule` 现有的 `input.metadata.context_only` 早退守卫（`inbox.ts:462`），避免第 140 行置为 `review_due_at = null` 的外部 `context_only` 背景消息在合批通过后因 `review_due_at` 为空而落入 `now + CHAT_BACKGROUND_DELAY_MS` 默认值触发空唤醒。

### Author Resolutions

- **R2-R1 (`accepted`)**：两条实施防呆细节均在 M1 代码落地时严格采用：① 保持导出的 `parsePersonalDecision` 四值解析不变以兼容 `codex.ts` 出站披露审核与现有单测，批量入站解析独立校验 `allow | deny`；② 合批准入写入 `inbox_schedule` 时统一复用 `inbox.schedule`（保留 `context_only`、`task_context` 等既有早退守卫），`review_due_at = null` 的 `context_only` 消息不生成定时唤醒。受审设计产物无需再做修改。
