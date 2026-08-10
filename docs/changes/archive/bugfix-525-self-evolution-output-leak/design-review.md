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
