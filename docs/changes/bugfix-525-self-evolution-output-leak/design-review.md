# Design Review: bugfix-525

## Round 1

### Metadata

- reviewer: `/root/bugfix_525_design_reviewer`
- review_mode: `full`
- mode_reason: `R1 requires a full independent review of every frozen artifact and its production/code grounding.`
- started_at: `2026-08-10T12:09:00+08:00`
- completed_at: `2026-08-10T12:22:15+08:00`
- duration: `13m 15s`

### Verdict

Issues Found — 1 CRITICAL / 0 WARNING

### Coverage

- Frozen inputs: `incident.md`, `design.md`, all three delta-specs, and the empty `M1-lifecycle-routing/.gitkeep` skeleton.
- Canonical contracts: `docs/specs/CONTRIBUTING.md`; kernel `runs.md`; Gateway `routing-delivery.md`, `agent-capabilities.md`, `external-channels.md`, and `relay-protocol.md`; IM `gateway-relay.md` and `web-chat-ux.md`.
- Production paths: fork construction and inherited hook publisher, realtime `skill_created` projection, foreground observer, terminal-to-persistent handoff, persistent event filter/replay, composition wiring, and `AgentConfigSync.handle_skill_created()`.
- Operational grounding: the Runbook commands match `scripts/e2e-up.sh` / `e2e-down.sh` and the checked-in secret-free `config/e2e/gateway.yaml`.

### 核实台账

#### 现状断言

| 原子 | 本轮核实 | 结论与证据 |
|---|---|---|
| `context_fork.py` 是 raw side-chain 进入父 stream 前的 seam | 从 `AgentRuntime` 的 background-hook wiring 追到 fork 的 inherited `HookContext` 和 publisher replacement。 | **不成立为“仅 self-evolution seam”**：`AgentContextFork` 是通用 fork（`src/agent/core/agent/context_fork.py:57-62`），而 runtime 为所有 `agent_end` background handlers 建造同一个 `fork_conversation`（`src/agent/core/agent/runtime.py:871-920`）。见 R1-C1。 |
| 成功 `skill_manage(create)` 已有窄业务事件 | 追 realtime hook 的 tool-result projection。 | 成立：仅成功 create 且 payload 完整时发布 `skill_created`，`src/agent/platform/hooks/builtins/realtime_stream.py:116-118,220-253`。 |
| 前台 observer 依赖 live run context，当前拥有普通 `skill_created` | 从 coordinator 的 per-run stream 追到 observer 的 handler branch。 | 成立：前台 stream 仅在 matching `run_id` 时进入 observer（`src/personal_assistant/gateway/session_run_coordinator.py:1472-1531`），observer 在 live context 中调用 handler（`src/personal_assistant/gateway/runtime_delivery/observer.py:516-529`）。 |
| persistent subscriber 有 session 生命周期、replay 与 reconnect，但当前只消费 notice | 追 manager ensure-once 到 subscriber event filter 与 cursor 更新。 | 成立：每 session 一个 subscriber（`src/personal_assistant/gateway/background_subscriptions.py:77-93,218-237`）；默认 filter 仅含 `self_evolution_review`（`background_session_events.py:25-30`），并在 callback 前推进 reconnect cursor（`background_session_events.py:173-227`）。 |
| `AgentConfigSync` 已承载 mode-aware skill 变更 | 追生产 composition 注入和 handler 对 agent/global/default/explicit 的分支。 | 成立：observer 已注入该 handler（`composition.py:466-504`）；handler 校验 root、按 scope 处理、保持 default/explicit selection mode（`agent_config_sync.py:1006-1099`）。 |
| Kernel sequence 能作为跨 terminal 的 replay anchor | 追 `RunInfo.start_sequence`、EventHub 和 coordinator 的 subscription request。 | 成立：submit start anchor 的语义明确（`src/agent/core/runs/registry.py:81-87`），stream 只 replay `sequence_num > after_sequence` 且持续 live（`src/agent/core/events/hub.py:178-239`），terminal 后 manager 从该 anchor 建立订阅（`session_run_coordinator.py:911-930`）。 |

#### 决策

| 决策 | 本轮核实 | 结论 |
|---|---|---|
| D1，fork publisher 按 source 分类 | 与通用 fork 的真实调用方和 incident 的非目标逐一对照。 | **不通过**：分类源没有由 self-evolution caller 声明，会污染所有 background-fork caller；见 R1-C1。 |
| D2，self-evolution `skill_created` 由 persistent manager 唯一拥有 | 对照现有 terminal 后 replay、live subscriber、per-run observer 的职责。 | 条件成立：source-specific observer skip + manager route 能避免 terminal 边界的双 owner，且不需要重建 subscriber。依赖 D1 的 caller-specific provenance 修正。 |
| D3，复用现有 config-sync handler | 对照 handler 的 root/mode/session-refresh 职责与 composition。 | 成立：复用避免复制 IM/YAML 写回状态机；`AgentConfigSync` 是自然 owner。 |
| D4，cursor + 单 owner + 既有收敛语义处理重放 | 对照 EventHub cursor、subscriber reconnect 与 IM notice idempotency。 | 成立：不新增 durable inbox/outbox 与当前同进程 Kernel/Gateway 故障模型相称；`self_evolution_review` 仍有 delivery-incarnation key（`runtime_delivery/background.py:76-148`）。 |
| D5，回归穿过 Kernel→Gateway→config-sync seam | 对照已存在的 Kernel-only integration proof 和本次缺口。 | 成立：现有 test 只证明 raw output 隔离并保留 stream `skill_created`（`tests/integration/test_self_evolution_output_visibility.py:126-335`），设计要求补真实 Gateway route，正击中 RCA。 |

#### 首文档约束

| 原子 | 覆盖核实 | 结论 |
|---|---|---|
| Q1 的“只保留既有结构化通知、不要另一种后台结果” | D1/D2、事件表和 Gateway routing delta 都将 raw output 与 structured notice 分开。 | 覆盖；但 D1 的通用 fork scope 必须收窄。 |
| memory 成功、无内容/失败时 raw output 私有且正常回答不受影响 | D1、事件表、routing delta 的三种 Scenario 均覆盖；既有 notice callback 不参与 raw relay。 | 覆盖。 |
| skill 在 terminal 前后、reconnect、下一轮生效且不重复 | D2-D4、主时序、capabilities delta 和 M1 worker exits 均覆盖 fast/slow/replay/reconnect。 | 覆盖，前提是 R1-C1 修正后 source 真正可信。 |
| 普通后台 Agent 的用户可见结果不回归 | 设计保留 background-output route，current route 会对 `origin=background_task` assistant text 调 callback（`background_session_events.py:190-212`）。 | **被 D1 破坏**：generic background fork 也会被 self-evolution filter 吞掉；见 R1-C1。 |
| RCA 不变量：真实 memory/skill 写入、unattended fork、`skill_created` activation、structured notice | D1-D3 保留 hook context/allowlist/业务事件，D3 复用写回，D4 保持 notice 路径。 | 覆盖，除 provenance owner 缺口外自洽。 |
| 非目标：不全局改变 `BACKGROUND_TASK` 投递语义或扩大为 feat-524 UI | 方案没有改 IM schema/UI，也没有采用 origin/string global filter。 | UI 范围成立；通用 fork policy 仍会实质改变一类 `BACKGROUND_TASK` delivery，见 R1-C1。 |

#### Delta-spec

| 条目 | 锚 canonical / 可观察性核实 | 结论 |
|---|---|---|
| kernel `runs.md` ADDED：side-chain 的 observable stream boundary | 面向 `agent.sdk` consumer，THEN 描述 stream、持久更新和 structured event，而非内部类/函数；与 `runs.md:22-29` 的 stream contract 相容。 | 成立。 |
| Gateway `routing-delivery.md` ADDED：raw maintenance text 不投递 | 与 `external-channels.md:125-148` 的可见 assistant / 非可见 telemetry 边界一致；同时明确普通 background Agent 不变，不是替换现有长任务 relay requirement。 | 成立，受 R1-C1 影响。 |
| Gateway `agent-capabilities.md` ADDED：terminal 后 skill 调和 | 是对现有“Gateway 已处理 `skill_created`”行为（`agent-capabilities.md:349-358`）新增 session-lifetime delivery guarantee；Scenario 保持用户可观察的 mode/result 描述。 | 成立，受 R1-C1 影响。 |
| IM / CLI 无 delta | structured IM notice 的 transport、idempotency、展示已由 `relay-protocol.md:247-274`、`gateway-relay.md:178-204`、`web-chat-ux.md:335-367` 覆盖，方案不改其 schema/UI；CLI 没有专属交互增量。 | 成立。 |

#### Milestone

| 原子 | 本轮核实 | 结论 |
|---|---|---|
| `bugfix-525-M1 lifecycle-routing` | 单一垂直切片；Kernel classification、Gateway owner/wiring 与 regression 不能独立交付，目录只有 `.gitkeep`，符合 Full design skeleton 规则。退出标准同时列 `[reviewer]` 旅程与 `[worker]` seam/quality proof。 | 成立；范围不与并行 milestone 相交。 |

### 整体判断

上层总览、事件表和两张图可以让 reviewer 直接看到“raw 私有、business event 续投、notice 保持原路径”的主线；接口从 `source` 到 persistent manager 再到既有 config-sync 也已闭合。风险、回退和隔离真栈 Runbook 都是可操作的：脚本支持 `--wt`，并生成隔离 config、workspace、PID 与 ports（`scripts/e2e-up.sh:12-24,103-105,301-366`）。

### 架构进攻

| 角度 | 主动检验 | 结论 |
|---|---|---|
| 归属 | source/visibility policy 是否由知道 side-chain 身份的层拥有 | **失败**：generic core fork 并不知道是哪个 background handler 调它，却被要求产生 `self_evolution` source。见 R1-C1。 |
| 该不该存在 | 新增 durable queue、第二套 config mutation 或 terminal-watermark lock 是否必要 | 不需要：现有 session subscriber + `AgentConfigSync` 已是深模块；删除新增队列/同步服务只会避免复制状态机。 |
| 深度 | manager 新增 handler dependency 是否只是浅包装 | 可接受：它将 replay/reconnect/owner selection 隐藏在已存在的 session-lifetime module，而 handler 仍集中配置语义。 |
| 治本 | 是否在 adapter/string/output 侧补丁 | 可接受：publisher edge 的隔离是正确的最低稳定 seam；但该 edge 必须由 caller-specific policy 驱动，不能把 generic fork 当作 self-evolution。 |

### Issues

- [R1-C1][CRITICAL] [现状分析“context-fork publisher seam” / 决策 1 / Kernel session-event 契约] 方案把 `source="self_evolution"` 和 raw-event suppression 固定在通用 `make_fork_conversation()` 上，却没有让调用 fork 的 hook 声明其 side-chain 身份或可见性策略。`AgentContextFork` 明确服务 compaction、memory extraction、speculative reasoning 等通用 fork（`src/agent/core/agent/context_fork.py:57-62`）；runtime 又把同一个 fork callable 注入所有 `agent_end` background handlers（`src/agent/core/agent/runtime.py:871-920`）。因此任一现有或随后注册的非 self-evolution background hook 只要使用正常 fork API，就会被错误地静默化，并把其 `skill_created` 错投给 self-evolution persistent owner；而 Gateway 当前确实把 `origin=background_task` assistant result 作为普通后台结果投递（`src/personal_assistant/gateway/background_session_events.py:190-212`）。不改会直接违反 incident “普通后台 Agent 结果继续投递”和“不改所有 `RunOrigin.BACKGROUND_TASK` 通用投递语义”的边界，worker 也无法从 source 值可靠判断该事件是否应由 persistent manager 接管。

### Recommendations

- [R1-R1] 让 self-evolution hook（或它唯一可识别的 fork invocation）显式选择 private side-chain event policy / provenance；通用 fork 的默认 event policy 必须保留既有语义，其他 background hook 只能按自己明确的 policy 被过滤或标记。补一条非-self-evolution fork 的可见输出不回归测试，以及 source-owner 交接的 Gateway seam regression。
- [R1-R2] 作者修订冻结产物并追加 `Author Resolutions` 后，唤醒同一 reviewer 做 R2；本轮有 CRITICAL，尚不可进入 `change-orchestrator`。

### Author Resolutions

- **R1-C1 — accepted and resolved.** 生产调用面确认 `make_fork_conversation()` 是注入所有 background handlers 的通用 callable，不能携带隐式 self-evolution 语义。`design.md` 决策 1、架构图、interface、风险与 M1 范围/退出标准已改为：通用 callable 的 `event_policy` 默认 `inherit`；只有 `self_improvement` caller 显式选择 `self_evolution` policy 时才隔离 raw events 并添加 source。M1 同时要求非 self-evolution fork 默认可见性回归，避免普通 background hook 被静默化。

## Round 2

### Metadata

- reviewer: `/root/bugfix_525_design_reviewer`
- review_mode: `delta`
- mode_reason: `Author resolved only R1-C1 with a bounded caller-specific event-policy change. Rechecked its changed atoms and direct Kernel-to-Gateway ownership/data-flow effects; all other full-review evidence is retained from Round 1.`
- started_at: `2026-08-10T12:26:40+08:00`
- completed_at: `2026-08-10T12:28:00+08:00`
- duration: `1m 20s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### Coverage

- Rechecked changed atoms: `design.md` involved-range table, reusable seam, architecture graph, Decision 1, `fork_conversation` interface, sequence diagram, risk/rollback, and M1 scope/exit criteria.
- Rechecked direct production constraints: shared background-hook callable construction and dispatch (`src/agent/core/agent/runtime.py:871-920`; `src/agent/core/hooks/runner.py:173-211`), the self-improvement fork invocation (`src/agent/platform/hooks/builtins/self_improvement.py:205-255`), generic HookContext capability (`src/agent/core/hooks/context.py:54-62,160-163`), and preserved ordinary background output route (`src/personal_assistant/gateway/background_session_events.py:190-212`).
- retained_from: Round 1 — incident constraints other than R1-C1, all three delta-specs and their canonical anchors, Decisions 2-5, Runbook, the single-milestone split, and the four architecture attack angles remain semantically unchanged by this bounded correction.

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | Generic callable defaults to `event_policy="inherit"`; only `self_improvement` explicitly selects `self_evolution`; M1 adds a non-self-evolution regression. | Runtime creates one callable and dispatches it to every background handler, so the revised default preserves that shared capability. The hook that actually knows review identity is `self_improvement`; `design.md:85-91,127-143` now makes it the explicit policy selector. The graph/timing table route only marked `skill_created` to the persistent owner (`design.md:55-81,145-210`), while M1 requires default-inherit visibility proof (`design.md:219-243`). | closed |

### 本轮重查台账

| Changed atom / affected path | Recheck | Conclusion |
|---|---|---|
| Current-state framing and reusable seam | The design now calls `context_fork.py` a generic background-hook seam and names `self_improvement.py` as the caller that knows review identity (`design.md:12-21,39-45`). This matches the shared callable and fan-out in production. | Correct. |
| Decision 1 and callable interface | `inherit` keeps the parent publisher and adds no source; `self_evolution` is opt-in, isolates raw events and marks its business event; unknown policy rejects (`design.md:85-91,127-143`). | Closed without a global `BACKGROUND_TASK` filter or a second delivery mechanism. |
| Ownership/data flow | Only the explicit policy creates the `source=self_evolution` discriminator. Per-run observer keeps ordinary events, while the persistent manager owns just marked business events (`design.md:55-81,145-210`). | One owner per event class; terminal replay/reconnect reasoning from R1 remains valid. |
| Incident target and delta contracts | The Kernel delta remains scoped to sessions that enabled self-evolution; Gateway routing delta still preserves ordinary background text; capability delta still describes only marked self-evolution `skill_created`. | No delta-spec change is required; all remain consumer-observable and non-conflicting. |
| Risk and milestone exits | Risk explicitly includes generic-fork drift, and M1 now scopes `self_improvement.py` plus a default-inherit/non-self-evolution regression in addition to fast/slow/replay/config-sync proof (`design.md:219-225,237-243`). | The previously missing guard is now a testable worker exit, not an aspiration. |

### 架构进攻

| 角度 | 本轮结论 |
|---|---|
| 归属 | Pass: the platform hook that knows its semantics declares the private policy; generic core fork execution no longer guesses caller identity. |
| 该不该存在 | Pass: one two-state, default-preserving policy is smaller than moving publisher construction into Gateway or adding an independent side-chain service. |
| 深度 | Pass: the callable exposes one semantic control and keeps policy mechanics at the existing publisher seam; `BackgroundSubscriptionManager` and `AgentConfigSync` retain their deep existing responsibilities. |
| 治本 | Pass: self-evolution still blocks raw events before the parent stream, while ordinary background output keeps its existing route; this fixes the classification root cause rather than filtering text downstream. |

### Issues

- None.

### Recommendations

- [R2-R1] Gate 2 is clear. Proceed to `change-orchestrator` after confirming no reviewed artifact changes occur after this Round.

## Round 3

### Metadata

- reviewer: `/root/bugfix_525_design_review_failover`
- review_mode: `full`
- mode_reason: `Reviewer failover after the original reviewer became unavailable, followed by a post-PR requirement correction that changes external-channel behavior, cross-module delivery provenance, delta-spec semantics, and the milestone inventory. Per the reviewer contract, no Round 1 inventory was inherited without revalidation.`
- started_at: `2026-08-10T17:23:52+08:00`
- completed_at: `2026-08-10T17:30:36+08:00`
- duration: `6m 44s`

### Verdict

Issues Found — 3 CRITICAL / 0 WARNING

### Coverage

- Frozen inputs: current `incident.md`, `design.md`, all four delta-spec files present in the reopened unit, the completed M1/M2 records needed to interpret the current milestone inventory, and the empty `M3-external-system-notice/.gitkeep` skeleton.
- Historical review: Round 1, its Author Resolution, and Round 2 were read only as issue history. Round 2's approval is invalidated by the later incident/design/delta/milestone changes and is not used as current Gate 2 evidence.
- Canonical contracts: `docs/specs/CONTRIBUTING.md`; Gateway `routing-delivery.md`, `external-channels.md`, `relay-protocol.md`, and `agent-capabilities.md`; kernel `runs.md`; IM `gateway-relay.md` and `web-chat-ux.md`.
- Production path: Feishu and Web IM ingress identity → shared external session key → binding refresh → foreground run delivery context → terminal subscriber admission → long-lived subscriber callback → structured IM notice and `OutboundRouter`. Kernel event publication and the actual `self_evolution_review` payload were independently traced from the foreground hook.
- Operational path: repository `e2e-up.sh --feishu`, dedicated profile/identity guard, probe, listener lock, and `e2e-down.sh` cleanup contract.

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | Generic fork defaults to `inherit`; only `self_improvement` selects `self_evolution`. | Current code still makes the callable generic and default-preserving (`src/agent/core/agent/context_fork.py:154-210,231-280`), while the self-improvement caller explicitly opts in (`src/agent/platform/hooks/builtins/self_improvement.py:219-228`). Ordinary background output remains a separate subscriber route (`src/personal_assistant/gateway/background_subscriptions.py:186-213`). | closed |
| R2-R1 | Gate 2 was clear only if no reviewed artifact changed after Round 2. | Incident v2, Decisions 6-7, external delivery data flow, two delta-specs, and M3 were added after Round 2. | superseded by this full review |

### 核实台账

#### 现状断言

| 原子 | 本轮核实动作 | 结论与证据 |
|---|---|---|
| 通用 context fork 是最早 raw-event seam，且默认行为必须保持 | 从 runtime 的 shared fork callable 追到 caller policy 与 publisher replacement。 | 成立：generic fork serves multiple use cases and defaults to `inherit`; only explicit self-evolution policy installs the business-event allowlist (`context_fork.py:57-62,154-210,249-280`). |
| `self_improvement` 是知道 review 身份的 caller | 追真实 hook invocation。 | 成立：它显式传 `event_policy="self_evolution"`，没有让 core 猜 caller (`self_improvement.py:219-228`). |
| `skill_created` 是窄业务事件 | 追 realtime projection 的成功条件。 | 成立：只有成功的 `skill_manage(create)` 且 payload 完整才发布，包含 fork run id (`realtime_stream.py:220-253`). |
| 前台 observer 依赖 run-scoped delivery context，并让出 self-evolution skill event | 追 observer branch 和 run context lifecycle。 | 成立：source-marked skill event被 persistent owner 消费 (`runtime_delivery/observer.py:524-538`); ordinary external trigger source lives in per-run `RunDeliveryContext` (`runtime_delivery/context.py:351-405`) and is discarded at terminal (`runtime_delivery/lifecycle.py:29-45,157-164`). |
| persistent subscriber 是 session-lifetime unique owner | 追 manager admission、request capture、reconnect loop。 | 成立，但它保留的是**首次 admission 的** `reply_context`: active session causes later `ensure` to return without refresh (`background_subscriptions.py:82-97`), and the subscriber closure captures that request (`background_subscriptions.py:172-184`). 这直接触发 R3-C1。 |
| Feishu 与其 shadow IM 共用 Kernel session，binding 每轮刷新 reply target | 从入口 identity 追 session key 和 binder。 | 成立：两入口都由 `external_source + external_chat_id + agent_id` 得到同一 key (`session_keys.py:1614-1643`), while `GatewaySessionBinder.resolve()` persists the current turn's reply context on reuse (`session_binder.py:274-295`). The long-lived subscriber does not consume that refresh. |
| `self_evolution_review` 当前携带足够触发源事实 | 追 hook payload和 EventHub publisher。 | **不成立**：event carries only session id, reviewed flags, tool names, and completion (`self_improvement.py:246-259`); the publisher adds only session id (`agent/sdk/kernel.py:2330-2344`). It contains neither originating run id nor trigger source. 见 R3-C1。 |
| structured IM notice callback 已有 stable identity 与 best-effort failure boundary | 追 current callback。 | 成立：current internal path requires a valid sequence, builds an incarnation/session/sequence key, waits for business ACK, and catches delivery failure (`runtime_delivery/background.py:43-148`). |
| ordinary-message metadata helper 可选择 Feishu vs IM | 直接核 helper 对 event-specific `ReplyContext` 的行为。 | 条件成立：for one specific inbound context it suppresses Web IM / `trigger_source=im` and retains external chat/thread metadata (`runtime_delivery/background.py:241-268`). Design wrongly assumes the persistent callback receives the triggering turn's context; 见 R3-C1。 |
| composition 已有唯一 external sender / router | 从 composition 追到 `OutboundRouter`. | 成立：`_send_external_reply()` reconstructs the channel target and delegates to the one router (`composition.py:299-317`); router owns process-local reply dedupe (`outbound_router.py:14-56,65-81`). |
| current canonical excludes all system notifications from Feishu | 核 canonical current requirement。 | 成立且需 delta：current contract excludes system notifications with telemetry (`docs/specs/gateway/external-channels.md:146-205`); the proposed narrow exception therefore belongs in a MODIFIED requirement. |
| current canonical already contains M1 kernel/routing/capability requirements | 对比 canonical titles 与 active delta headings。 | 成立：the same requirements already exist at `docs/specs/kernel/runs.md:261-278`, `docs/specs/gateway/routing-delivery.md:308-328`, and `docs/specs/gateway/agent-capabilities.md:366-382`; active ADDED deltas are no longer a valid merge inventory. 见 R3-C2。 |
| no-save review does not publish a product notice | 追 hook event condition并核已验收真实旅程。 | **不成立**：after any successful fork the hook publishes `self_evolution_review`, even without a write (`self_improvement.py:236-259`); completed M2 evidence explicitly observed one structured memory notice on controlled no-save (`M2-acceptance-closure/progress.md:12-23`; `regression.md:303-313`). 见 R3-C3。 |

#### 决策

| 决策 | 四问核实 | 结论 |
|---|---|---|
| D1 caller-selected fork event policy | Default, opt-in owner, rejection and non-goals are explicit; production caller matches. | 通过。 |
| D2 self-evolution `skill_created` belongs to persistent manager | One owner covers fast/slow/replay and does not conflict with ordinary observer. | 通过。 |
| D3 reuse `AgentConfigSync` | Existing handler concentrates scope/root/mode/config publication; no duplicate state machine. | 通过。 |
| D4 cursor + one owner + existing convergence | Fits current in-process fault model and does not promise durable cross-process handoff. | 通过。 |
| D5 regression must cross Kernel→Gateway→config sync | Directly driven by the historical escape seam and has a concrete integration exit. | 通过。 |
| D6 productized notice follows ordinary trigger-source routing | Required outcome is explicit, but the design does not carry event-specific trigger provenance into the session-lifetime callback. | **不通过**；见 R3-C1。 |
| D7 reuse external sender and notice identity | Reusing sender/dedupe is sound, but the proposed input context is stale for a session that alternates Feishu and shadow IM; two independent workers cannot implement correct routing from this interface. | **不通过**；见 R3-C1。 |

#### 首文档约束

| 原子 | 设计覆盖核实 | 结论 |
|---|---|---|
| Q1：raw review completion 不成为另一条 Agent output | D1、event table、routing delta keep raw assistant/tool/turn private. | 覆盖。 |
| Q2：Feishu trigger → Feishu + shadow；IM trigger → IM only | D6/D7 and external delta state the target, but the interface cannot distinguish the triggering turn after the first subscriber admission. | **未可实现覆盖**；见 R3-C1。 |
| Q3：Feishu one-line, non-first-person Bot text, no specific distilled content | D6, callback contract, external delta, M3 reviewer exit all require it. | 覆盖。 |
| Q4：only `self_evolution_review` opt-in; thinking/tool/token/debug and future notices stay private | D6, risk section, external delta and M3 exits all use an explicit one-event allowlist. | 覆盖。 |
| memory update succeeds; raw prompt/tool/`Saved:` stays private; structured notice remains | D1 plus existing structured callback preserve this. | 覆盖。 |
| no-save or failure does not expose raw reply/error and does not alter foreground completion | Private publisher and failure isolation cover raw output; failure emits no review event. | 覆盖 for raw privacy; product-notice semantics are contradictory for no-save, 见 R3-C3。 |
| skill creation before/after terminal activates under current selection mode | D2-D5 and M1/M2 evidence cover agent/global, default/explicit, replay and later sessions. | 覆盖。 |
| terminal handoff/reconnect produces no duplicate activation/notice | One subscriber/cursor/config convergence plus stable internal notice key cover the current path. | 覆盖；external per-trigger provenance remains blocked by R3-C1。 |
| ordinary background Agent user-visible result remains unchanged | Generic fork defaults to inherit; background subscriber has separate `origin=background_task` route. | 覆盖。 |
| Feishu-triggered successful review reaches both destinations | Target is specified, but the first subscriber context may instead be IM or a previous Feishu thread. | **未覆盖**；见 R3-C1。 |
| shadow-IM-triggered successful review never writes back to Feishu | Same session key and a stale first Feishu context make this scenario fail in production. | **未覆盖**；见 R3-C1。 |
| other runtime events and future system notices remain non-external | Explicit event-name branch and delta non-goal preserve this. | 覆盖。 |
| 非目标：不改 feat-524 background UI | No IM/frontend UI or background display redesign is introduced. | 不越界。 |
| 非目标：不改 self-evolution thresholds/prompts/formats/permissions | D1-D7 do not change those semantics. | 不越界，except R3-C3 must resolve notice meaning without silently redefining review/write behavior. |
| 非目标：不改 runtime footer / all BACKGROUND_TASK delivery | Generic default and ordinary route remain. | 不越界。 |
| 非目标：future notices remain opt-in | Explicit `self_evolution_review` whitelist is stated in decision, risk and delta. | 不越界。 |

#### Delta-spec

| 条目 | 锚 canonical / 用法 / THEN 可观察核实 | 结论 |
|---|---|---|
| kernel `runs.md` ADDED self-evolution stream boundary | Consumer perspective and observable stream results are valid, but the same title/content is already canonical on this reopened branch (`docs/specs/kernel/runs.md:261-278`). | Historical delta is already applied; leaving it in the active merge inventory is invalid，见 R3-C2。 |
| Gateway `agent-capabilities.md` ADDED cross-terminal skill reconciliation | Observable Gateway result is valid, but the same requirement is already canonical (`docs/specs/gateway/agent-capabilities.md:366-382`). | Historical delta is already applied; active merge status is ambiguous，见 R3-C2。 |
| Gateway `routing-delivery.md` ADDED raw-maintenance privacy | The current canonical already has this exact requirement (`docs/specs/gateway/routing-delivery.md:308-328`), while the delta changes its notice behavior (`specs/gateway/routing-delivery.md:3-25`). | Must be MODIFIED with the complete current requirement, not ADDED；见 R3-C2。 |
| Gateway `external-channels.md` MODIFIED external control/background delivery | Exact canonical title is targeted; all nine existing Scenarios are retained and three consumer-visible notice Scenarios are appended. THEN clauses contain no implementation symbols. | 用法正确；behavior still depends on resolving R3-C1/R3-C3。 |
| IM / CLI no delta | Internal structured schema/UI and CLI behavior do not change. | 成立。 |

#### Milestone

| 原子 | 垂直性 / 举证 / 范围 / 两轨退出核实 | 结论 |
|---|---|---|
| M1 lifecycle-routing | Completed vertical Kernel→Gateway→config-sync slice with reviewer and worker exits; not parallel with later milestones. | 历史切片成立。 |
| M2 acceptance-closure | Completed post-acceptance remediation that added deterministic real-entry validation, not a pending implementation-vs-test split for the current orchestrator. Its records explain why the no-save and reconnect journeys are trustworthy. | As completed history it does not create a current dispatch collision; its no-save evidence exposes R3-C3. |
| M3 external-system-notice | Sequential post-PR vertical user behavior slice with code, contract, unit proof and dedicated Feishu journey; external acceptance authorization and isolation preconditions are explicit. | Split is justified by the later user correction, but scope/exit cannot satisfy per-trigger routing without a provenance seam outside the listed callback/composition changes (R3-C1), and no-save exit conflicts with current behavior (R3-C3). |

### 整体判断

The top-level summary, graph, decisions, event table and Feishu runbook make the intended direction easy to understand. Naming is consistent; there are no TBD/template remnants. The dedicated Feishu commands match the checked-in `--feishu` launcher, identity probe and listener-lock/cleanup contract (`scripts/e2e-up.sh:12-16,103-128,158-167`; `scripts/e2e-feishu-probe.py:22-94`; `scripts/e2e-down.sh:83-101`).

The data flow is not closed at its new load-bearing point: the notice is produced by a run-triggered background hook, but M3 routes it using a session subscriber's first reply context. A session may alternate Feishu and shadow IM while remaining the same Kernel session, and the event carries no run/trigger identity. The document therefore states the correct UX while giving the worker an interface that cannot produce it reliably.

### 架构进攻

| 角度 | 主动检验 | 结论 |
|---|---|---|
| 归属 | Trigger source belongs to the foreground run/inbound message; does the session-lifetime subscriber own that fact? | **失败**：subscriber is the correct event-consumption owner but not the natural owner of per-run trigger provenance. Reusing its first `ReplyContext` crosses lifetime boundaries and causes external write-back from IM-triggered turns or missed Feishu notices. R3-C1. |
| 该不该存在 | Is a new Feishu adapter/outbox/sender abstraction necessary? | Pass: the existing external sender and router should be reused. The missing thing is a real event-to-trigger provenance seam, not another channel service. |
| 深还是浅 | Does `reply_context_external_delivery_metadata()` hide the relevant complexity? | Conditional fail: the helper is deep for a specific inbound reply context, but applying it to a stale session-level context only hides the provenance loss. Long-term cost is a deceptively correct helper call that silently misroutes whenever entry source changes. R3-C1. |
| 治本还是补丁 | Does the proposal fix source routing at the fact owner, or infer it downstream? | **失败**：the proposal infers a run-specific decision from session state after the run context was discarded. It also leaves “reviewed target” versus “actual update/no-save” unresolved, so Feishu text may be fabricated or inconsistently suppressed. R3-C1/R3-C3. |

### Issues

- [R3-C1][CRITICAL] [现状分析“复用 reply context helper” / 决策 6-7 / 接口与数据流 / M3] 方案没有把**触发本次 review 的那条消息来源**带到 notice callback，却要求 callback 从 `BackgroundSubscriptionManager` 保存的 `reply_context` 判断是否外发。生产中 Feishu 和 shadow IM 通过同一 external identity 共享 Kernel session (`session_keys.py:1614-1643`)，每轮 binding 虽会刷新当前 reply target (`session_binder.py:274-295`)，但 manager 对已存在 session 直接返回并保留首次 request (`background_subscriptions.py:82-97,172-184`)。同时 `self_evolution_review` payload 与 EventHub publisher 都不含 originating run/trigger source (`self_improvement.py:246-259`; `agent/sdk/kernel.py:2330-2344`)。因此会话先从 Feishu 建立 subscriber、后来从 shadow IM 触发 review 时，通知仍会按旧 Feishu context 回写；反向顺序则会漏发 Feishu，thread 也可能错。若后台 review 与下一轮交叠，读取“最新 binding”同样不能可靠替代 event-specific provenance。**不改会直接让两条核心用户 Scenario 在真实共享会话上互相打架，worker 也无法只靠 M3 当前列出的 callback/composition interface 实现正确行为。** 设计必须拍死 run/event-specific trigger provenance 的来源、生命周期和消费接口，并把所需模块纳入 M3 scope；不能用 subscriber 首次或最新 session context 猜。
- [R3-C2][CRITICAL] [delta-spec inventory / `specs/gateway/routing-delivery.md`] reopened unit 的 delta inventory 没有对齐当前 canonical：kernel runs、Gateway agent-capabilities 与 Gateway routing 三条 `ADDED` Requirement 已经由本 unit 原 M1 收尾归入 canonical (`docs/specs/kernel/runs.md:261-278`; `docs/specs/gateway/agent-capabilities.md:366-382`; `docs/specs/gateway/routing-delivery.md:308-328`)。其中 routing delta 现在又修改了同名现有 requirement，却仍写在 `## ADDED Requirements` (`specs/gateway/routing-delivery.md:3-25`)。**不改时收尾按 delta 归并会在 canonical 追加同名新旧两条，造成“system notice 不外发”和“该 notice 外发”并存；orchestrator 也无法判断另外两份历史 delta 是否要再次应用。** 将本轮真实变化重建成相对 current canonical 的 inventory：routing 必须是完整 `MODIFIED`，external-channels 保持 `MODIFIED`，已经归并且本轮未变的历史 delta 必须明确退出 active merge set，而不是继续以 `ADDED` 参与收尾。
- [R3-C3][CRITICAL] [incident no-save Scenario / 决策 6 / M3 exit] no-save notice 语义在冻结产物内部矛盾。当前 hook 在 fork 成功后无论是否发生写入都会发布 `self_evolution_review`; payload 的 `reviewed_memory/reviewed_skills` 表示被 review 的目标，不是写入成功 (`self_improvement.py:236-259`)。M2 的真实 no-save 旅程也明确验收为“raw `Nothing to save.` 为 0，但保留一条 structured memory notice” (`M2-acceptance-closure/progress.md:12-23`; `regression.md:303-313`)。incident 的 no-save Scenario 只禁止 raw reply/error (`incident.md:80-84`)，D6 又说当前产品化 `self_evolution_review` 一律按 trigger source 路由；但 M3 reviewer exit 突然要求 `no-save/failure 仍两端静默` (`design.md:289`)。**不改时 worker 必须在“照现有 event 外发”“只保留 internal notice”“两端都 suppress”三种互斥行为中猜一个，并可能静默改掉已经验收的产品行为或向飞书发送虚假的 updated 文案。** 先明确 notice 的语义是“review 完成”还是“真实产生更新”，再统一 incident、event payload/判定、D6、两个 delta 和 M3 exits；failure 无 event 可继续静默，但 no-save 不能同时被写成保留 productized event 和两端静默。

### Recommendations

- [R3-R1] For R3-C1, preserve the trigger fact at the originating run/review boundary and make the persistent callback consume that exact fact. Add a two-direction alternating-entry regression on one shared Kernel session (Feishu→shadow-trigger and shadow→Feishu-trigger), plus an overlap case so “latest binding” cannot accidentally pass.
- [R3-R2] For R3-C2, treat the reopened branch's canonical specs as current. Keep only the two actual M3 MODIFIED deltas in the active merge plan, while preserving already-applied M1 deltas as history without making the final merger reapply them.
- [R3-R3] For R3-C3, record one explicit no-save decision before implementation and make the dedicated Feishu journey assert that choice separately from raw side-chain privacy.

### Author Resolutions

- **R3-C1 — accepted and resolved.** `design.md` 不再让 persistent subscriber 使用首次或最新 binding 猜本轮来源。coordinator 在 public `Kernel.submit()` 前生成 trace 并注册不可变 `trace_id -> ReplyContext`；既有 run trace 穿过 `RunRecord -> TurnRequest -> HookContext`，`self_improvement` 把它作为 `originating_trace_id` 放进 review event。manager 只以该 event-specific trace 解析 route，缺失时 fail-closed，最多保留 4096 项并 oldest-first 淘汰；M3 加入同 session 双向交替与 overlap regression。
- **R3-C2 — accepted and resolved.** 已归并 current canonical 的历史 `specs/kernel/runs.md` 与 `specs/gateway/agent-capabilities.md` 已从 active delta set 删除；`specs/gateway/routing-delivery.md` 改为完整 `MODIFIED`，`external-channels.md` 保持完整 `MODIFIED`。`design.md` 的 active delta inventory 同步只列本轮两条 Gateway 修改。
- **R3-C3 — accepted and resolved.** notice 明确定义为“review 正常完成及其整理范围”，不是实际写入回执。正常完成但 no-save 继续产生既有 structured notice，并按本轮触发源路由到对应出口；raw `Nothing to save.` 仍私有；fork failure 不产生完成 event。incident、D7、两个 delta 与 M3 reviewer/worker exits 已统一。

## Round 4

### Metadata

- reviewer: `/root/bugfix_525_design_review_failover`
- review_mode: `full`
- mode_reason: `The same stable failover reviewer continues because the original reviewer remains unavailable. Round 3 resolutions add cross-module Kernel trace propagation, a new run-route registry, event provenance, changed notice semantics, a rebuilt active delta inventory, and revised M3 scope/exits; these are core data-flow and shared-contract changes, so closure/delta evidence is insufficient.`
- started_at: `2026-08-10T17:44:20+08:00`
- completed_at: `2026-08-10T17:50:11+08:00`
- duration: `5m 51s`

### Verdict

Issues Found — 2 CRITICAL / 0 WARNING

### Coverage

- Frozen inputs: current `incident.md`, `design.md`, the two active Gateway delta-specs, the M3 skeleton and current three-row milestone table, plus Round 3 and its Author Resolutions. Completed M1/M2 records were reread where they constrain no-save and replay semantics.
- Canonical contracts: kernel `runs.md`; Gateway `routing-delivery.md`, `external-channels.md`, `relay-protocol.md`, and `agent-capabilities.md`; IM `gateway-relay.md` and `web-chat-ux.md`; their package spec indexes and delta-writing rules.
- Production path: public `Kernel.submit(trace_id=...)` → `RunRecord` → `TurnRequest` → `AgentRuntime` HookContext → self-improvement review event; Gateway queued admission / `try_steer`, persistent subscriber, proposed trace route, structured IM callback, external metadata helper and `OutboundRouter`.
- Presentation path: IM `SystemNotice.updated_targets` validation and the localized Web IM renderer, including the actual Chinese/English “updated” copy used for live and replayed notices.
- Operational path: dedicated Feishu E2E startup, identity guard/probe, isolated config/workspace and cleanup contract remain available and consistent with the M3 reviewer journey.

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R3-C1 | Generate and register an immutable `trace_id -> ReplyContext` before submit; propagate the same trace through `TurnRequest`/HookContext and publish it as `originating_trace_id`; missing route fails closed; bounded oldest-first retention; add alternating/overlap exits. | Public Kernel already accepts caller-supplied trace (`src/agent/sdk/kernel.py:1481-1543`) and `RunsRegistry` freezes it on the new run (`src/agent/core/runs/registry.py:210-245`). The missing production seam is exactly `TurnRequest` and `_run_locked` metadata (`src/agent/core/session/types.py:141-150`; `src/agent/core/agent/runtime.py:285-300,405-424`), so the proposed propagation is implementable without crossing the `agent.sdk` boundary. Gateway creates new runs at the coordinator fact owner (`session_run_coordinator.py:870-893`), and the route table eliminates the first/latest-binding inference identified in R3. Current `try_steer` intentionally retains the existing run identity (`session_run_coordinator.py:220-259`), so it does not create a second trace contract for this M3. | closed |
| R3-C2 | Keep only full MODIFIED Gateway routing/external deltas; remove already-canonical Kernel/capability deltas and update inventory. | Active inventory now contains only the two intended files, both under `MODIFIED Requirements`; routing faithfully retains its three canonical Scenarios. The external replacement, however, weakens one unrelated canonical Scenario instead of preserving it verbatim; see R4-C1. | partially closed |
| R3-C3 | Define the notice as successful review completion/scope, not a write receipt; no-save retains notice and raw output stays private; fork failure is silent; align incident/design/deltas/M3. | No-save-versus-failure routing is now aligned in the two deltas and M3. The claimed semantic alignment is not true across the frozen incident, canonical IM contract, live schema/UI, and the returned-but-incomplete fork path; see R4-C2. | open |

### 核实台账

#### 现状断言

| 原子 | 本轮核实 | 结论与证据 |
|---|---|---|
| Generic self-evolution fork policy and persistent Skill owner remain the M1 production path | Rechecked the caller-selected policy, event allowlist, foreground skip and persistent config-sync path. | 成立：only `self_improvement` opts into the private policy; raw events remain inside the fork while source-marked `skill_created` is handled by the persistent owner (`context_fork.py:21-35,249-304`; `self_improvement.py:219-259`; `runtime_delivery/observer.py:516-529`; `background_subscriptions.py:184-213`). |
| Kernel already owns an opaque run trace but does not put it in the active turn HookContext | Traced the public SDK argument into `RunRecord`, then into `TurnRequest` and runtime metadata. | 成立：`Kernel.submit(trace_id=...)` forwards to the registry; the registry stores the trace but currently builds `TurnRequest` without it, and runtime only writes `run_id` (`kernel.py:1481-1543`; `runs/registry.py:210-245`; `session/types.py:141-150`; `agent/runtime.py:405-424`). |
| Coordinator owns the immutable message route before new-run submit | Traced binding admission and synchronous submit under the transition lock. | 成立：binding/reply context is resolved before the synchronous submit and active marker publication (`session_run_coordinator.py:840-893`). This is the correct fact owner for R3-C1's route registration. |
| Persistent subscriber currently captures its first request context and therefore needs event-specific routing | Rechecked ensure-once and callback closure. | 成立：an already-active session returns unchanged, while `_build_subscriber` closes over `request.reply_context` (`background_subscriptions.py:82-97,154-184`). The trace table removes this stale-session inference. |
| Existing structured IM notice is already a completion/scope message whose schema/UI can remain unchanged | Traced Gateway payload through IM validation and renderer rather than relying on design wording. | **不成立**：Gateway sends `updated_targets` and “updated” text (`runtime_delivery/background.py:63-131`); IM validates and persists an `updated_targets` schema (`src/IM/ws/gateway/relay.py:431-469`; `src/IM/domain/models.py:280-305`); Web IM renders “技能/记忆已更新” / “skills/memory updated” (`src/IM/frontend/src/i18n/zh.json:549-558`; `en.json:552-561`). See R4-C2. |
| A failed review emits no completion event | Traced exception and non-exception incomplete returns. | 只对抛异常成立：the hook catches exceptions and returns, but after any returned `ForkResult` it publishes `self_evolution_review` including `completed` (`self_improvement.py:229-259`). `max_turns_reached` returns `completed=False` rather than raising (`context_fork.py:294-304`; `agent/loop.py:322-340`). The design does not state whether that event is suppressed or routed. See R4-C2. |
| Dedicated Feishu verification can use a non-production identity and isolated runtime | Rechecked the runbook against repository scripts and M3 scope. | 成立：the `--feishu` startup, profile/identity guard, probe and `e2e-down` cleanup remain concrete; the design explicitly forbids production Bot/chat/config use. |

#### 决策

| 决策 | 本轮核实 | 结论 |
|---|---|---|
| D1：self-evolution caller explicitly selects the private event policy | Compared with the shared background-hook callable and existing caller. | 成立；generic default remains `inherit`, so ordinary background hooks are not silently changed. |
| D2：source-marked self-evolution `skill_created` has one persistent owner | Rechecked foreground skip, subscriber filter/replay and config-sync injection. | 成立；M3 does not reopen this completed M1 ownership. |
| D3：reuse `AgentConfigSync`, no second config mutation or durable queue | Rechecked handler responsibility and same-process fault model. | 成立；scope/root/mode/session refresh stay centralized. |
| D4：cursor + one owner + existing idempotency handle replay | Rechecked cursor timing, stable notice identity and M2 replay evidence. | 成立 for the documented same-process semantics; no speculative durable outbox is needed. |
| D5：regression crosses public Kernel to production Gateway seam | Compared M3 tests/exits with the original Kernel-only blind spot. | 成立；alternating source and overlap proof now target the newly load-bearing provenance seam. |
| D6：only `self_evolution_review` opts into ordinary trigger-source external delivery | Compared Q2-Q4, delta allowlist and external sender reuse. | 成立；unknown/future notices and thinking/tool/token/debug remain private by default. |
| D7：originating trace selects the exact run route | Traced the trace source, propagation gap, registration timing, lookup and failure policy. | 成立 for the current per-run trigger-source contract: one caller-generated trace is frozen before submit, propagated opaquely, and missing lookup fails closed. The 4096 oldest-first bound is an explicit privacy-over-delivery tradeoff, not an unbounded cache. |
| Notice means successful review completion/scope, not write receipt | Compared the stated decision with incident, canonical IM semantics, actual UI and incomplete returns. | **不通过**：documents and runtime still encode mutually exclusive “updated” and “review completed” meanings, and `completed=False` handling is not decided. See R4-C2. |

#### 首文档约束

| 原子 | 覆盖核实 | 结论 |
|---|---|---|
| Q1 / raw privacy：no review prompt, tool progress, `Saved:` / `Nothing to save.` or failure text becomes chat output | D1-D4, routing delta and M1/M2 evidence retain the private fork boundary. | 覆盖。 |
| Q2：Feishu trigger sends original Feishu chat + shadow IM; internal/shadow trigger sends internal only | D6-D7, trace data flow, external delta and M3 alternating/overlap exits cover the route. | 覆盖。 |
| Q3：Feishu uses one-line, short, non-first-person Bot text without distilled details | D6, callback contract, external delta and dedicated Feishu exit all require it. | 覆盖。 |
| Q4：only the productized review notice opts in; other telemetry/future notices remain external-off | Explicit event allowlist appears in D6, risks, delta and M3. | 覆盖。 |
| no-save keeps the completion notice; review failure is silent; foreground completion is unaffected | The two Gateway deltas and M3 now state the same route result. | **行为目标覆盖，但 completion/failure 判定与用户可见语义未闭合**；见 R4-C2。 |
| successful Skill update survives terminal/reconnect and ordinary background Agent output remains unchanged | Completed M1/M2 ownership, config-sync and regression contracts remain in design and canonical specs. | 覆盖；M3 does not alter them. |
| non-goals：no default/threshold/prompt/permission changes; no global background suppression; no arbitrary system-notice export | Rechecked D1/D6 and milestone scope. | 覆盖，且没有夹带新的 runtime feature. |

#### Delta-spec

| 条目 | 锚 canonical / 可观察性核实 | 结论 |
|---|---|---|
| Gateway `routing-delivery.md` MODIFIED | Exact title matches canonical; all three original Scenarios remain, with external review routing and no-save/failure outcomes added as user-observable results. | 成立；`MODIFIED` 用法与内容完整。 |
| Gateway `external-channels.md` MODIFIED | Exact title matches canonical and the new review scenarios are in the narrow existing trigger-source requirement. | **不完整**：the original group `/stop` Scenario's `WHEN` required a real in-group mention; the active replacement weakens it to textual `@Bot /stop`. See R4-C1. |
| Kernel / Gateway capability historical deltas removed | Compared active set with current canonical `kernel/runs.md` and `gateway/agent-capabilities.md`. | 成立：M1 behavior is already canonical; trace propagation is internal support for the canonical “enough source semantics” event guarantee, so no duplicate active delta is needed. |
| IM no active delta | Compared design's “schema/UI unchanged” claim with the new completion/scope semantics. | **不成立 under R3-C3 as written**：if scope/completion is the intended durable meaning, current IM schema/canonical/UI say update and must be reconciled or the decision must be narrowed. See R4-C2. |

#### Milestone

| 原子 | 本轮核实 | 结论 |
|---|---|---|
| M1 lifecycle-routing | Completed vertical repair for raw privacy and post-terminal Skill business events. | 历史切片完整；不与当前 M3 重派。 |
| M2 acceptance-closure | Completed deterministic real-entry proof for no-save and Skill/replay behavior. | 历史验收收口；its observed no-save notice remains a binding semantic fact. |
| M3 external-system-notice | Sequential post-PR vertical slice spanning provenance, Gateway route, external delivery, deltas, tests and dedicated Feishu acceptance. | Split remains justified by the later user correction and has both reviewer/worker exits. Scope is incomplete only if the chosen completion/scope semantics require IM schema/copy work; see R4-C2. |

### 整体判断

R3-C1's revised trace design fixes the original session-state inference at the correct fact owner and is implementable through an already-public opaque Kernel correlation field. The architecture remains small: one bounded route registry in the existing lifecycle owner, one event field, and reuse of the existing external sender. The document is readable and the dedicated Feishu runbook is actionable.

Gate 2 is still blocked because the merge contract and the notice meaning are not actually frozen. One unrelated canonical `/stop` guarantee would be weakened by the MODIFIED replacement, while the same no-save event is simultaneously described as “review completed” and rendered/persisted as “updated”; returned `completed=False` forks add a third undecided outcome. Those are worker-visible forks in behavior, not editorial polish.

### 架构进攻

| 角度 | 主动检验 | 结论 |
|---|---|---|
| 归属 | Should channel payloads enter Kernel, or should Kernel carry only correlation while Gateway owns routes? | Pass: opaque trace stays in Kernel; `ReplyContext` remains in Gateway's coordinator/manager, preserving `personal_assistant -> agent.sdk` and no reverse product dependency. |
| 该不该存在 | Delete-test the new route registry and event provenance. | They are necessary: without event-specific correlation the long-lived subscriber can only guess first/latest session state. Housing the bounded table in the existing subscription owner is smaller than a new service or durable outbox. |
| 深度 | Does the registry hide meaningful lifecycle complexity, and are existing send/schema abstractions reused? | Mostly pass: it centralizes retention, lookup, failure policy and subscriber delivery. The semantic claim that IM needs no change fails because the reused `updated_targets` abstraction exposes a different meaning to every IM consumer (R4-C2). |
| 治本还是补丁 | Does trace fix source routing at the fact owner, and does wording merely mask missing outcome facts? | Trace is root-cause level. The no-save wording is not: relabeling `reviewed_*` as scope while preserving an “updated” durable schema/UI makes false write claims recur across live, replay and localized views; R4-C2. |

### Issues

- [R4-C1][CRITICAL] [active `specs/gateway/external-channels.md` MODIFIED requirement / R3-C2] The rebuilt delta inventory has the right files and operation type, but the full replacement does not faithfully preserve an unrelated canonical Scenario. Current canonical requires the user to send a **real mention in the group** for `@Bot /stop` (`docs/specs/gateway/external-channels.md:157-161`); the active delta changes that `WHEN` to plain “用户发送 `@Bot /stop`” (`specs/gateway/external-channels.md:16-20`). Under the delta merge model this replacement becomes authoritative and silently drops the real-mention constraint that prevents textual `@Bot` from being confused with provider mention metadata. **If unchanged, final merge can regress a pre-existing group control contract outside bugfix-525 even though the author declared this a complete MODIFIED copy.** Restore the canonical Scenario exactly and add only the self-evolution changes.

- [R4-C2][CRITICAL] [incident target/no-save Scenario / design grounding + notice interface + delta inventory / M3] R3-C3 has not actually frozen one notice meaning or one success boundary. The author resolution says the notice means “review completed and scope, not a write receipt,” but the incident still promises “memory/skills 已更新” in its target and success Scenarios (`incident.md:60-62,72-78,89-95`). More importantly, design claims the IM schema/UI stay unchanged (`design.md:43,211,277`), while production and canonical contracts persist `updated_targets` and render “技能/记忆已更新” / “skills/memory updated” (`runtime_delivery/background.py:63-131`; `docs/specs/gateway/relay-protocol.md:247-260`; `docs/specs/im/gateway-relay.md:178-191`; `docs/specs/im/web-chat-ux.md:345-358`; `src/IM/frontend/src/i18n/{zh,en}.json`). A no-save review therefore still tells shadow IM that an update occurred, contradicting the new completion-only semantics and the external “整理完成” text. The failure boundary is also ambiguous: exceptions emit no event, but a fork can return `completed=False` (for example `max_turns_reached`) and current hook still publishes the event; the event table retains `completed` without saying whether subscriber or publisher rejects it (`self_improvement.py:229-259`; `context_fork.py:294-304`; `agent/loop.py:322-340`). **If unchanged, independent workers can legitimately implement three incompatible products: leave a false “updated” IM notice, change IM schema/copy outside M3 and without deltas, or suppress a no-save/incomplete event contrary to the frozen exits.** Decide the exact publish gate for `completed=False`, then either (a) keep true update-receipt semantics and supply a real write outcome, or (b) consistently change incident, Gateway/IM canonical + delta inventory, schema naming/presentation and M3 scope/exits to completion/scope semantics. No-save and failure must remain separately testable.

### Recommendations

- [R4-R1] Return to `change-design-author` for the two bounded corrections above. R3-C1's trace architecture does not need redesign; preserve it while closing the MODIFIED copy and notice semantic boundary.
- [R4-R2] After author appends resolutions, wake the same stable failover reviewer. The next mode can be `delta` only if changes are limited to the canonical Scenario restoration plus an enumerated notice-semantic choice/inventory update; any new IM schema or milestone restructuring should remain `full`.

### Author Resolutions

- **R4-C1 — accepted and resolved.** `specs/gateway/external-channels.md` 已恢复 canonical 原句“用户在群里发送真实 mention 形式的 `@Bot /stop`”；完整 MODIFIED 不再弱化任何无关 group-control 契约。
- **R4-C2 — accepted and resolved.** 选择 true update-receipt 语义，不修改 IM schema/UI：hook 以 call id 关联 `TurnResult.tool_calls` 与 `tool_results`，只认可 memory `add/replace/remove` 和 skill_manage `create/edit/patch/write_file/remove_file` 的成功结果，形成非空 `updated_targets`；event 的 legacy `reviewed_*` 同步投影这些真实更新对象。no-save、只有 list/read、所有写操作失败均不发布 event；`completed=False` 若已有成功写入仍发布真实更新回执，若无成功写入则静默。incident、D6、event table/interface、M3 exits 与两个 Gateway delta 已统一；新增完整 Kernel MODIFIED delta 保留 M1 raw/business boundary，并明确 structured update event 的 publish gate/originating trace。现有 IM `updated_targets` schema、本地化“已更新”文案与 canonical relay/UI 因而继续真实，无需 IM delta。

## Round 5

### Metadata

- reviewer: `/root/bugfix_525_design_review_failover`
- review_mode: `full`
- mode_reason: `Round 4 resolutions replace a globally visible Kernel event's publish gate and payload meaning, add a full Kernel MODIFIED delta, and change M3 outcome exits. Those changes affect a shared SDK contract and every consumer, so their impact cannot be closed by checking only the two historical issues; this round re-runs all five atom classes and all four architecture attacks.`
- started_at: `2026-08-10T17:58:17+08:00`
- completed_at: `2026-08-10T18:02:42+08:00`
- duration: `4m 25s`

### Verdict

Issues Found — 1 CRITICAL / 0 WARNING

### Coverage

- Frozen inputs: current `incident.md`, `design.md`, all three active delta-specs (`kernel/runs.md`, Gateway `routing-delivery.md` and `external-channels.md`), the M1/M2 completed records, M3 skeleton, and the complete Round 1–4 review/resolution history.
- Canonical contracts: Kernel `runs.md`; Gateway `routing-delivery.md`, `external-channels.md`, `relay-protocol.md` and `agent-capabilities.md`; IM `gateway-relay.md` and `web-chat-ux.md`; CLI package index plus `interactive-repl.md` and `product-integration.md`.
- Production path: public `Kernel.submit(trace_id=...)` → `RunRecord` → `TurnRequest` → `AgentRuntime` HookContext → self-improvement fork/result → Kernel session event → persistent Gateway manager → exact route → shadow IM/external sender.
- Outcome path: `AgentLoop` aggregation and incomplete return, `TurnResult.tool_calls/tool_results`, memory/skill tool result shapes, existing `skill_created` success test, IM `updated_targets` rendering, and Coding CLI's session-level review renderer.
- Operational/document path: dedicated Feishu identity guard/runbook, `PYTHON=/Users/czj/Repos/nano-multiagent/.venv/bin/python ./scripts/docs-check` (`241` sources / `67` routes), and `git diff --check` all pass before this append.

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R4-C1 | Restore the canonical real-mention wording in the full external-channels MODIFIED replacement. | The active replacement now contains the exact canonical `WHEN` “用户在群里发送真实 mention 形式的 `@Bot /stop`” and retains every unrelated original Scenario (`specs/gateway/external-channels.md:9-64`; canonical `docs/specs/gateway/external-channels.md:150-205`). | closed |
| R4-C2 | Choose a true update receipt derived from successful mutating tool results; suppress no-save/read/failure; preserve successful writes on `completed=False`; align incident/design/M3 and add a full Kernel delta. | `TurnResult` exposes call id/name/arguments and raw structured outcome (`src/agent/core/types.py:67-107`; `agent/runtime.py:2308-2368`). Memory and SkillManage return explicit `success: true` only after the relevant writes (`memory.py:188-213,241-287`; `skill_manage.py:339-356,414-524`), so the named action set and call-id correlation are implementable. Incident, D6/event interface, M3 exits, Kernel/Gateway deltas and existing IM “updated” schema now share one meaning; incomplete turns retain earlier tool results (`agent/loop.py:301-340`; `agent/runtime.py:2331-2368`). | closed |

### 核实台账

#### 现状断言

| 原子 | 本轮核实 | 结论与证据 |
|---|---|---|
| Caller-selected private fork policy is the production raw-output boundary | Traced the self-improvement caller into the generic fork publisher. | 成立：generic default remains `inherit`; only the explicit `self_evolution` policy filters raw events and preserves marked business events (`context_fork.py:24-35,198-304`; `self_improvement.py:219-228`). |
| Persistent manager remains the one owner for late self-evolution business events | Rechecked subscriber filter/owner and foreground skip. | 成立：source-marked `skill_created` is excluded from the per-run observer and consumed through the session-lifetime path; M3 does not introduce a second handler (`runtime_delivery/observer.py:516-529`; `background_subscriptions.py:154-213`). |
| Public Kernel already has an opaque trace, with one missing propagation seam | Traced submit through registry, request and runtime HookContext. | 成立：the SDK accepts `trace_id` and `RunRecord` stores it, while current `TurnRequest` and HookContext omit it (`agent/sdk/kernel.py:1481-1546`; `agent/core/runs/registry.py:210-245`; `agent/core/session/types.py:141-150`; `agent/core/agent/runtime.py:401-429`). The proposed opaque pass-through is on the real production path. |
| Coordinator owns the immutable route before new-run admission; persistent subscriber's captured request is session-stale | Rechecked submit timing and ensure-once subscriber closure. | 成立：the coordinator has this message's `ReplyContext` at admission, whereas an existing subscriber keeps its first request; event-specific trace lookup is necessary to avoid first/latest binding inference (`session_run_coordinator.py:840-893`; `background_subscriptions.py:82-97,154-184`). |
| Returned fork outcome can distinguish actual update targets, including before an incomplete terminal | Followed tool calls/results from loop messages into `TurnResult` and checked tool output contracts. | 成立：`build_turn_result` aggregates all body tool calls/results before applying the final `completed` flag (`agent/runtime.py:2308-2368`); mutating memory/skill actions return structured success only after write completion. Call-id matching supplies the action because reconstructed `ToolResult` does not carry arguments. |
| Existing IM schema/UI already expresses true updates | Traced Gateway fields through IM validation and localized rendering. | 成立 under the revised decision：Gateway/IM use non-empty `updated_targets`, and live/replay UI says memory/skills “updated” (`runtime_delivery/background.py:63-131`; `src/IM/ws/gateway/relay.py:431-469`; `src/IM/frontend/src/i18n/zh.json:549-558`; `en.json:552-561`). No IM delta is required once no-write events are suppressed. |
| Coding CLI is also a live consumer of this global event | Traced default product features into the background event renderer. | 成立, but omitted by the design inventory：CLI enables both self-evolution features by default and immediately renders every `self_evolution_review` as “... updated” (`src/coding_cli/product.py:75-77`; `src/coding_cli/events/background_runs.py:16-23,70-96`). Changing the Kernel publish gate therefore changes terminal-visible behavior. See R5-C1. |
| Dedicated Feishu validation remains isolated and executable | Rechecked runbook commands, non-default identity guard and cleanup boundary. | 成立：M3 still specifies a dedicated test Bot/chat, worktree-local runtime/config/workspace, probe and `e2e-down` cleanup rather than production identities. |

#### 决策

| 决策 | 本轮核实 | 结论 |
|---|---|---|
| D1：caller explicitly selects the private event policy | Compared shared default and the only self-evolution caller. | 成立；ordinary forks and background Agent output keep existing visibility. |
| D2：self-evolution `skill_created` has one persistent owner | Rechecked ownership, terminal timing and reconnect path. | 成立；no duplicate/zero-owner fork is introduced. |
| D3：reuse `AgentConfigSync`, no second config mutation or durable queue | Rechecked scope/root/mode responsibility. | 成立；the proposed manager dependency delegates to the existing state machine. |
| D4：cursor + one owner + current idempotency handle the documented replay model | Rechecked same-process lifecycle and stable notice identity. | 成立；a new durable outbox would be speculative for the stated fault model. |
| D5：regression crosses public Kernel and production Gateway seams | Compared the original blind spot with M3 overlap/alternating routes. | 成立 for PA/Feishu; the outcome change's second production consumer, Coding CLI, is absent from M3 coverage (R5-C1). |
| D6：publish a true update receipt and externally opt in only this notice | Checked success predicate against current tool shapes, event payload, incident and all three deltas. | 成立：successful named writes produce non-empty targets; no-save/read/write-failure is silent; `completed=False` preserves already-committed writes; telemetry/future notices remain external-off. |
| D7：originating trace selects the exact immutable reply route | Traced fact owner, registration-before-submit, propagation, lookup and eviction. | 成立：opaque trace stays in Kernel, channel context stays in Gateway, missing route fails closed, and bounded oldest-first retention is explicit. |

#### 首文档约束

| 原子 | 覆盖核实 | 结论 |
|---|---|---|
| Raw review prompt/tool/completion/error text remains private | D1-D4, routing delta and M1/M2 evidence retain the side-chain boundary. | 覆盖。 |
| A true memory/skill update produces a structured update notice; no successful write produces none | Incident target/success/no-save Scenarios now agree with D6 and Kernel/Gateway deltas. | 覆盖；the old M1/M2 no-save observation is historical and explicitly superseded by the later Round 4 decision/M3 exit. |
| Feishu trigger sends original chat + shadow IM; internal/shadow trigger stays internal | D6-D7, trace route and external delta cover both directions and overlap. | 覆盖。 |
| Feishu text is one-line, short, non-first-person and reveals no distilled content | D6, callback contract, M3 reviewer exit and external delta all retain it. | 覆盖。 |
| Only this productized notice opts in; thinking/tool/token/debug and future notices stay external-off | Checked event allowlist in decisions, risks, milestone and delta. | 覆盖。 |
| Skill activation survives terminal/reconnect; ordinary background Agent output stays unchanged | Completed M1/M2 owner/config-sync contracts remain intact. | 覆盖。 |
| Scope/non-goals do not silently change other products | The shared event gate also changes Coding CLI no-save/update notification behavior, while design says there is no CLI interaction change. | **不成立**；见 R5-C1。 |

#### Delta-spec

| 条目 | 锚 canonical / 可观察性核实 | 结论 |
|---|---|---|
| Kernel `runs.md` MODIFIED | Exact canonical title; both original M1 Scenarios retained; publish gate, true targets, trace, no-save/failure and incomplete-success behavior added. | 成立；replacement is complete, SDK-consumer-facing, and its THEN clauses are observable stream results. |
| Gateway `routing-delivery.md` MODIFIED | Exact canonical title and all three original Scenarios retained with true-update routing. | 成立；no unrelated behavior is removed. |
| Gateway `external-channels.md` MODIFIED | Exact canonical title, every existing Scenario retained, real mention restored, and only the narrow review-notice exception added. | 成立；R4-C1 closed. |
| IM no delta | Compared true receipt with existing `updated_targets` schema/UI. | 成立；the revised gate makes the existing update presentation truthful. |
| CLI no delta | Compared design inventory with CLI package ownership and production renderer. | **不成立**：the Kernel change suppresses the terminal notification on no-save/read/failure and makes successful categories outcome-derived. CLI canonical explicitly owns terminal-user-observable output, not Kernel internals (`docs/specs/cli/spec.md:5,25-29`). See R5-C1. |
| Historical Gateway capability delta removed | Compared active inventory with current canonical capability contract. | 成立；Skill config-sync behavior is already canonical and unchanged by M3. |

#### Milestone

| 原子 | 本轮核实 | 结论 |
|---|---|---|
| M1 lifecycle-routing | Rechecked completed privacy/Skill-owner vertical slice. | 历史切片完整；not reopened. |
| M2 acceptance-closure | Rechecked deterministic no-save/failure and Skill/replay harness value. | 历史切片完整；M3 intentionally changes only the false no-save receipt observed there, not the raw-privacy proof. |
| M3 external-system-notice | Checked vertical scope, sequential dependency, reviewer/worker tracks, route/outcome exits and dedicated Feishu evidence. | PA/Feishu slice is coherent and verifiable, but scope/exits omit the user-visible Coding CLI consequence and its regression/delta even though D6 changes the shared event source. See R5-C1. |

### 整体判断

The two Round 4 blockers are genuinely resolved. The revised outcome is not a wording workaround: current tool results provide enough structured evidence to emit a truthful update receipt, preserve a successful write before an incomplete terminal, and keep no-write/failure silent without changing IM schema or UI. The full Kernel replacement now preserves M1's raw/business boundary, and the restored external replacement no longer weakens `/stop` mention handling. Trace-based route ownership and the dedicated Feishu runbook also remain sound.

Gate 2 is still blocked by one cross-product contract omission. `self_evolution_review` is a shared Kernel event, and Coding CLI enables and renders it in production. Suppressing no-save events therefore changes what a terminal user sees even though the design declares “无 CLI 专属交互变化.” The implementation could otherwise ship with PA tests green while the CLI behavior has neither a durable product contract nor an M3 regression.

### 架构进攻

| 角度 | 主动检验 | 结论 |
|---|---|---|
| 归属 | Should update truth and channel routing live together, or should Kernel own outcome while products own presentation/routes? | Pass：outcome truth belongs at the hook/Kernel result boundary shared by all consumers; `ReplyContext` and channel choice remain in Gateway. No reverse dependency or channel payload enters `agent`. The missing CLI delta is documentation/test ownership, not a reason to move the gate into PA. |
| 该不该存在 | Delete-test the route registry, trace propagation and outcome correlation. | All three are necessary: deleting trace routing restores session-state guessing; deleting outcome correlation makes the “updated” notice false; deleting the bounded registry loses the only race-safe association. They reuse existing owner/interfaces instead of creating a service or durable queue. |
| 深度 | Does the proposal hide complexity behind meaningful existing seams and reuse presentation schemas? | Pass except inventory coverage：`TurnResult` already centralizes call/result outcome, the manager centralizes subscriber lifecycle/routes, and IM/external senders retain presentation ownership. The shared Kernel seam naturally reaches CLI too, which is precisely why R5-C1 must be recorded at the CLI contract/test boundary. |
| 治本还是补丁 | Does true receipt fix the false-update semantic cause, and does trace fix source routing at its fact owner? | Pass：both changes replace inference with source facts. Filtering the no-save notice only inside Gateway would be the patch; central Kernel gating is the deeper design, provided every observable consumer is explicitly covered. |

### Issues

- [R5-C1][CRITICAL] [design §契约层增量 `cli: no spec delta` / D5-D6 / M3] The new true-update publish gate is global Kernel behavior, not a PA-only delivery detail. Coding CLI enables memory and skill self-evolution by default (`src/coding_cli/product.py:75-77`), subscribes to session-level `self_evolution_review`, and renders each event immediately as “background self-evolution review: ... updated” (`src/coding_cli/events/background_runs.py:16-23,70-96`). R4-C2 therefore changes terminal-visible behavior: no-save/list/read/write-failure no longer prints a review notification, while successful notices now name only actually updated targets. Yet design says CLI has “无 CLI 专属交互变化” and supplies no CLI delta or M3 CLI outcome regression (`design.md:275-280,303-311`). The CLI canonical layer explicitly owns terminal-user-observable output (`docs/specs/cli/spec.md:5,25-29`), so the Kernel delta cannot substitute for it. **If unchanged, the unit can merge a cross-product UX change with PA/Feishu tests green while CLI's durable contract remains silent and future work can reintroduce a false no-save “updated” line without violating this unit's M3 exits.** Accept this shared consequence explicitly, add the narrow CLI delta (at the terminal presentation area) and include successful-update/no-write CLI regression coverage in M3; alternatively redesign the event contract to genuinely preserve existing CLI behavior, but do not claim no change while using the global gate.

### Recommendations

- [R5-R1] Return to `change-design-author` for the bounded inventory correction only: keep the now-sound true-receipt and trace architecture, add the CLI observable contract/regression to delta inventory and M3, then wake this same stable reviewer for closure.

### Author Resolutions

- **R5-C1 — accepted and resolved.** shared Kernel true-receipt gate 的 Coding CLI 后果已显式纳入本 unit：新增 `specs/cli/interactive-repl.md` ADDED Requirement，规定真实 memory/skills 更新才显示既有 updated system line，no-save/read/list/write-failure 不显示误导提示；`design.md` D5、delta inventory 与 M3 scope/exits 已加入 CLI consumer。M3 要求 `tests/unit/test_cli_background_runs.py` 覆盖 memory/skills/both 的真实更新对象与 no-write 无更新行；收尾归并时同步把 CLI `spec.md` 的 Interactive REPL Requirement 计数从 7 更新为 8。true-receipt gate、trace route 与 PA/Feishu 行为不变。

## Round 6

### Metadata

- reviewer: `/root/bugfix_525_design_review_failover`
- review_mode: `delta`
- mode_reason: `Round 5 resolution adds one bounded CLI consumer contract plus its explicitly enumerated D5/inventory/M3 coverage. Kernel true-receipt semantics, trace routing, Gateway/IM/Feishu data flow, and milestone structure are unchanged, so the affected atoms and ownership/depth attacks can be closed without re-running the full Round 5 inventory.`
- started_at: `2026-08-10T18:07:04+08:00`
- completed_at: `2026-08-10T18:08:17+08:00`
- duration: `1m 13s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### Coverage

- `retained_from: Round 5` — the full production-path, incident, Kernel/Gateway/IM delta, true-update outcome, trace-route, M1/M2 and four-angle architecture evidence remains valid because none of those artifacts or decisions changed.
- Changed inputs: R5-C1 Author Resolution; new `specs/cli/interactive-repl.md`; design changelog/current scope, D5, delta inventory, and M3 scope/exits.
- Rechecked production consumer: Kernel session stream → REPL background queue → `BackgroundRunEventProcessor` → terminal system line, plus the existing category test seam.
- Rechecked canonical placement/merge: CLI package ownership, all seven existing Interactive REPL Requirements, new ADDED semantics, and the documented package-index count update from 7 to 8.
- Validation: `PYTHON=/Users/czj/Repos/nano-multiagent/.venv/bin/python ./scripts/docs-check` passes with `242` maintained sources / `67` routes; both worktree and cached `git diff --check` pass before this append.

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R5-C1 | Add a narrow CLI Interactive REPL delta; include CLI as a shared-event consumer in D5/inventory/M3; cover true memory/skills/both and no-write terminal outcomes; update canonical index count at merge. | Production REPL continuously reads the Kernel session stream into its background queue and renders each event through `BackgroundRunEventProcessor` (`src/coding_cli/commands.py:539-595,693-699`); the processor's existing self-evolution seam renders the three real target combinations (`src/coding_cli/events/background_runs.py:16-23,70-96`; `tests/unit/test_cli_background_runs.py:98-121`). The new delta now owns both the positive line and no-success silence, while M3 couples renderer coverage with the upstream update-outcome tests that prove no-write emits no event. | closed |

### 本轮重查台账

| Changed atom | 核实动作 | 结论与证据 |
|---|---|---|
| CLI production premise | Traced the interactive product entry from the long-lived Kernel stream through queue flush and formatter. | 成立：this is a real REPL path, not a test-only renderer (`commands.py:539-595,693-699`), and default CLI self-evolution remains enabled (`product.py:75-77`). |
| CLI delta canonical target and operation | Compared the new requirement with all current `docs/specs/cli/interactive-repl.md` headings and package ownership rules. | 成立：background self-evolution receipt/silence is a parallel terminal behavior not already specified by startup, session, slash command, foreground streaming, steer, error or non-TTY Requirements. `ADDED` is correct; both Scenario THEN clauses are terminal-user-observable. The stated count change 7→8 matches the canonical index. |
| Success/no-success semantic completeness | Compared the delta prose/Scenarios with Kernel true-receipt and the CLI renderer's accepted fields. | 成立：memory, skills and both map to the existing non-first-person “updated” line; no-save/read/list/all-write-failure produce no Kernel event and therefore no line. M3 also retains raw prompt/tool/error privacy, so the delta does not reopen leakage. |
| D5 regression boundary | Checked whether the revised test decision proves both the shared source and the product presentation instead of duplicating Kernel logic in CLI. | 成立：M3 keeps update-outcome unit/integration coverage at the hook/Kernel source and adds `tests/unit/test_cli_background_runs.py` only for the terminal projection. This is the correct split; CLI does not infer tool success itself. |
| M3 scope and exits | Checked worker/reviewer tracks and file scope against R5-C1. | 成立：scope names the existing CLI test seam; reviewer exit covers no-success silence and target-accurate success; worker exit enumerates memory/skills/both/no-write. No new production module or milestone split is introduced. |

### 架构进攻（受影响角度）

| 角度 | 主动检验 | 结论 |
|---|---|---|
| 归属 | Could the CLI delta make the product infer write success separately from Kernel? | Pass：the Kernel remains the sole owner of update truth; CLI owns only terminal presentation. The delta explicitly keys positive output to the shared structured event and silence to its absence, avoiding a second outcome classifier. |
| 深度 / 治本 | Does adding a renderer regression merely paper over the shared-event issue? | Pass：the M3 pair covers the deep source gate with update-outcome tests and the actual terminal projection with the existing processor test. No wrapper, adapter or CLI-specific event is introduced, so there is no new maintenance layer or divergence path. |

### 整体判断

R5-C1 is fully closed. The new ADDED Requirement sits at the canonical owner of terminal-visible behavior without replacing any existing REPL contract, and its merge bookkeeping is explicit. D5 and M3 now cover both halves of the shared event: Kernel decides whether a truthful update exists; Coding CLI renders only its real targets. The correction does not expand implementation architecture or reopen the approved PA/Feishu route.

### Issues

None.

### Recommendations

- [R6-R1] Gate 2 is clear; proceed to `change-orchestrator` for M3 implementation, preserving the documented CLI canonical count update during delta merge.
