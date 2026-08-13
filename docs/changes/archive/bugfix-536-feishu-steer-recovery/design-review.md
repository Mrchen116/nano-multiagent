# Design Review: bugfix-536-feishu-steer-recovery

## Round 1

### Metadata

- reviewer: `/root/bugfix_536_design_reviewer`
- target: `docs/changes/bugfix-536-feishu-steer-recovery/design.md` and its three delta-specs
- review_mode: `full`
- mode_reason: `R1` has no previous review inventory; the unit changes the Kernel SDK seam, Gateway ownership, and user-visible multi-channel delivery.
- started_at: `2026-08-13T14:50:00+08:00`
- completed_at: `2026-08-13T15:00:14+08:00`
- duration: `10m 14s`

### Verdict

Changes requested — 2 CRITICAL / 0 WARNING

The compaction-liveness decision is well grounded and the overall direction (Kernel owns recovery facts; Gateway owns presentation) is the right architecture.  The recovery handoff is not yet a closed consumer contract, however, and the liveness delta-specs use the wrong delta operation.  Either defect lets an implementer produce a green local path while still dropping, misrouting, duplicating, or permanently waiting on an accepted message.

### Historical issues

None — first review round.

### Coverage

Reviewed in full:

- First document: `incident.md`, including all four clarification records, three requirements, four scenarios, scope, and non-goals.
- Design: all current-state claims, four decisions, interfaces/data flows, risks, runbook, and M1.
- Delta-specs: `specs/kernel/runs.md`, `specs/gateway/routing-delivery.md`, and `specs/im/gateway-relay.md`.
- Canonical targets: `docs/specs/kernel/runs.md`, `docs/specs/gateway/routing-delivery.md`, and `docs/specs/im/gateway-relay.md`; delta-spec writing rules in `docs/specs/CONTRIBUTING.md`.
- Production paths and focused tests: `AgentLoop`/`CompactionSummarizer`/liveness, `RunsRegistry`, SDK DTO and stream boundary, `SessionRunCoordinator`, runtime-delivery lifecycle/context/observer, and the coordinator, pending-origin, and liveness test suites.

### 核实台账

#### 现状断言

| ID | 断言 | 核实结论与实际证据 |
|---|---|---|
| A1 | 自动压缩在下一次主模型调用前、同 run pending drain 前发生 | 成立。`loop.py:362-386` 先 await `_maybe_compact()`，之后才 `drain_pending()`。 |
| A2 | summarizer sidechain 不应把摘要过程投进父会话 | 成立。`summarizer.py:72-97` 将 `session_event_publisher` 置为 no-op，且移除 permission requester。 |
| A3 | 当前 compaction await 没有父 run liveness | 成立。`loop.py:1054-1064` 直接 await `summarize()`；相对地，主 LLM stream 在 `loop.py:443-455` 被 `_with_liveness_heartbeat()` 包住。 |
| A4 | await-bound ticker 可复用，并且不掩盖真卡死 | 成立。`liveness.py:76-110` 在 body 离开时取消 ticker；`liveness.py:178-197` 已用于迭代式 await，事件格式在 `liveness.py:60-70`。 |
| A5 | 非用户终态会保留未消费 pending 并重提 | 成立。`registry.py:565-629` drain 后按 contiguous origin batch 重提；用户 interrupt 单独进入 held pending。 |
| A6 | 当前 Kernel 事件没有 predecessor 关联 | 成立。`RunRecord` 仅有 run/session/origin/model 等字段（`registry.py:54-89`），`_publish_run_status_event()` 也只发布该 record 的自身字段（`registry.py:857-887`）。 |
| A7 | Gateway 只能经 SDK 接触 Kernel | 成立。`SPEC.md:151-161` 与 `session_run_coordinator.py:15-21` 均显示 PA 使用 SDK surface；没有 core import。 |
| A8 | coordinator 对 accepted steer 有 own/follower 状态，但旧 run 收尾即整体弹出 | 成立。`session_run_coordinator.py:301-329` 记录 accepted follower；`1372-1384` 会同时删除 active marker、consumed count 和全部 followers。 |
| A9 | Gateway 当前不消费 user-origin 的其他 run | 成立。`session_run_coordinator.py:1401-1424` 在 `origin in {user, None, ""}` 时直接返回。 |
| A10 | old run 的 stream consumer 当前在旧 terminal 后停止，idle 时立即 cancel/reconcile/raise | 成立。`session_run_coordinator.py:1889-1904` timeout 后 cancel 并 raise；`1931-1955` 在 old terminal status 处 break/failed。 |
| A11 | 多条 follower 的消费与 shadow 锚定已按 `injection_consumed` 计数 | 成立。`session_run_coordinator.py:1958-2000` 以 consumed count 从 follower 列表取得最后一个 shadow；现有 batch/non-user 回归在 `test_session_run_coordinator_admission.py:905-1031`。 |
| A12 | runtime delivery 以 run id 为 context 键，accepted/terminal lifecycle 分别 seed/discard | 成立。`runtime_delivery/context.py:253-357` 是 per-run store；`runtime_delivery/lifecycle.py:31-48` 在 accepted seed、completed/failed discard。 |
| A13 | current lifecycle 没有 recovery 形态，accepted 还会产生外部 ACK/receipt | 成立。`inbound_models.py:196-213` 只允许 accepted/running/completed/failed；`runtime_delivery/lifecycle.py:31-64` 的 accepted 分支同时 ack external inbound 并发 receipt。 |
| A14 | explicit `/stop` 与 `/new` 是必须保持的硬边界 | 成立。`session_run_coordinator.py:737-792` 将 stop 标为 user interruption；current kernel 将 user interruption 的 pending 放 held buffer（`registry.py:600-609`）。 |
| A15 | live-but-quiet 现行 code/tests 已覆盖 tool/LLM/permission，但没有 compaction call-site 覆盖 | 成立。liveness unit test 只覆盖 ticker/LLM/permission adapter（`test_liveness_ticker.py:36-110`）；当前 loop 的 compaction path 如 A3 所示没有 ticker。 |

Production path was traced from inbound admission (`session_run_coordinator.py:260-333`) through SDK `try_steer()` (`kernel.py:1670-1702`), registry admission (`registry.py:387-427`), event stream (`kernel.py:1816-1840`), and runtime-delivery context/lifecycle.  The design's named components are production paths, not test-only stand-ins.

#### 决策

| ID | 决策 | 核实 |
|---|---|---|
| D1 | 父 run 包住 compaction await 发 `run_heartbeat(source=compaction)`，sidechain 继续静默 | 成立且是最小修复。它复用 A4 的 await-bound primitive，满足 incident 的「不延长/关闭 watchdog」非目标，也不违反 A2。 |
| D2 | Registry 向 SDK 发显式 predecessor link | 方向正确，但不足以构成可消费的 recovery handoff；见 R1-C1。 |
| D3 | Gateway 保持未消费 followers，等待关联 recovery run | 覆盖 incident 的核心结果，但在 old terminal→successor 的实际顺序、多个 pending batch、无 successor 的收口上尚未拍死；见 R1-C1。 |
| D4 | 走既有 lifecycle/context，不造 channel-specific recovery adapter | 归属正确且避免飞书特例；但需把 recovery lifecycle 的 typed shape 与 no-ACK/no-receipt 语义写死，作为 R1-C1 的闭环内容。 |

#### 首文档约束

| ID | incident 约束 | design 落点与结论 |
|---|---|---|
| S1 | Q1：正常推进的压缩不得被误报失败；真停止才接住后发消息 | D1 和 D3 分别覆盖两种分支；D3 仍受 R1-C1 阻断。 |
| S2 | Q2：恢复保留原上下文，补充消息不是孤立新问题 | D2/D3 复用同一 session 的 Kernel continuation；成立，前提是 handoff 关联可确定。 |
| S3 | Q3：飞书、Web IM 和同 Gateway channel 一致 | D4 明确不设飞书分支，M1 包含两入口；成立，前提是 recovery context 能准确取得每条 follower 的原路由（R1-C1）。 |
| S4 | Q4：仅精确 `/stop`、`/new` 是控制边界 | D2/D3、风险表和 M1 都保留此边界；与 A14 一致。 |
| S5 | 自动压缩期间追加消息：旧消息不误失败，补充消息连上下文继续 | D1、主流程和 M1 对应完整；成立。 |
| S6 | 真中断前已接受补充：无需重发、无 timeout/重复 | D2-D4 有落点，但 exact-once handoff 仍未封闭；R1-C1。 |
| S7 | 恢复收口后下一条普通消息仍正常工作 | D3 风险/回退和 M1 保住 session release；成立，但 R1-C1 的 fallback protocol 必须避免无限 busy。 |
| S8 | 所有 Gateway 聊天入口的一致体验 | D4、delta gateway 和 M1 对应；成立，受 R1-C1 的 per-follower routing 限制。 |
| S9 | 范围：Gateway 普通聊天；非目标：不改变 `/stop`/`/new`、不把自然语言当控制、不放宽 watchdog | D1/D3/D4 没有越界；没有发现飞书专用、前端或 IM 网络帧扩张。 |

#### Delta-spec 条目

| ID | 条目 | 核实 |
|---|---|---|
| DS-K1 | kernel ADDED: recovery run 向 SDK 标明前序 run | 消费者视角正确，但仅 predecessor id 不能唯一关联恢复 batch 或决定无 successor 的结束；R1-C1。 |
| DS-K2 | kernel ADDED: compaction wait 保持 parent liveness | 对外可观察、场景正确；但它扩展的是 existing liveness Requirement，不能只 ADDED；R1-C2。 |
| DS-G1 | gateway ADDED: accepted normal message 的 recovery delivery | 用户视角正确；依赖 R1-C1 对 lifecycle/batch 关联的闭环。 |
| DS-G2 | gateway ADDED: compaction 插话不被 idle 误收 | 对外可观察、场景正确；但修改 existing routing+liveness Requirement，R1-C2。 |
| DS-I1 | im ADDED: compaction liveness 延续 relay message | 用户可观察、没有实现名泄漏；但修改 existing watchdog Requirement，R1-C2。 |

#### Milestone

| ID | 核实 |
|---|---|
| M1 | 单一垂直切片成立：heartbeat、SDK seam、coordinator handoff、delivery 与回归缺任一均不能交付用户结果。范围没有并行组重叠问题；reviewer/worker 两轨退出也可验。M1 的 “无链接/重复/迟到/shutdown” 回归应在 author 修正 R1-C1 后扩展为 batch correlation 和 deterministic no-successor 收口。 |

### 架构进攻

| 角度 | 结论与证据 |
|---|---|
| 归属 | 通过。Registry 是 pending re-submit 的事实 owner（`registry.py:565-629`），SDK 是产品唯一合法 seam（`SPEC.md:157-161`），Gateway 是外部可见 delivery owner（`session_run_coordinator.py:1268-1324`）。设计没有把 Registry 细节泄漏到 channel 或 IM。 |
| 该不该存在 | 通过。删除 predecessor seam 会迫使 Gateway 按时间/active id 猜 successor；A5/A6 证明它无法得到这个事实。该 field 不是假想多态抽象。 |
| 深还是浅 | 发现 R1-C1。只给 predecessor id 把内部 recovery 的一个事实暴露出来，却仍迫使 Gateway 猜 batch 归属和“没有 successor”何时成立；这不是足够深的 consumer contract。 |
| 治本还是补丁 | 通过。D1 修父 run 的真实静默窗口而非延长 watchdog；D2-D4 尝试让 input preservation 和 visible delivery 同一条链路闭合，而非加飞书特例。 |

### Issues

- [R1-C1][CRITICAL] [决策 2-4 / 接口与数据流 / M1] Recovery handoff only promises `continuation_of_run_id`; it does not define a closed, correlated handoff protocol.  This is not enough for the actual producer/consumer sequence: Gateway publishes cancel on idle (`session_run_coordinator.py:1898-1904`), the old terminal status then makes the current consumer stop (`1931-1955`), while Registry only drains/re-submits after target completion and can submit multiple contiguous-origin batches (`registry.py:565-629`).  The current follower list is also deliberately removed together with its consumed count at old-run close (`1372-1384`).  Therefore an implementer has no specified answer to all of these material cases: which of several successor runs owns which unconsumed follower batch; when a linked successor is no longer expected and failure must be emitted; how the active marker and stream stay owned across old terminal; and which typed lifecycle update seeds the new context without entering the existing accepted branch that ACKs external inbound and sends a receipt (`inbound_models.py:196-213`, `runtime_delivery/lifecycle.py:31-64`).  The current diagram says “wait” but does not resolve those decisions.  Without a concrete protocol, one valid-looking implementation will fail immediately and drop the successor, another can wait forever and wedge the session, and another can bind the wrong route/re-ACK/duplicate a reply.  This directly violates the incident's no-timeout/no-duplicate and all-channel requirements.

- [R1-C2][CRITICAL] [delta-specs kernel/gateway/im — compaction liveness] The three liveness delta-specs use `ADDED`, although this change extends existing canonical liveness Requirements rather than creating parallel behavior.  The current kernel Requirement explicitly names exactly three windows and says they share one path (`docs/specs/kernel/runs.md:219-236`); the IM Requirement likewise defines three sources (`docs/specs/im/gateway-relay.md:159-176`); Gateway's existing routing Requirement defines its own liveness/watchdog rule (`docs/specs/gateway/routing-delivery.md:69-102`).  The proposed delta files contain only `## ADDED Requirements` (kernel `specs/kernel/runs.md:3-23`, IM `specs/im/gateway-relay.md:3-13`, Gateway `specs/gateway/routing-delivery.md:3-23`).  Under `docs/specs/CONTRIBUTING.md`'s merge rule, ADDED appends rather than replaces, leaving the old “three window” canonical statements beside a fourth special case.  Workers and later maintainers then have conflicting sources for the same watchdog semantics, and the stated “same event path, no source-specific exception” invariant is no longer canonical.  The change must supply full `MODIFIED` versions of the existing liveness Requirements (preserving their existing scenarios) and reserve ADDED for genuinely new recovery behavior.

### Recommendations

- [R1-R1] Resolve R1-C1 in the design, not in worker tasks: specify an SDK-visible recovery descriptor that correlates each continuation batch to the accepted, unconsumed Gateway follower range (not merely its predecessor), and define the terminal signal or bounded/authoritative condition by which Gateway knows no recovery will arrive.  Specify the coordinator state transition across old terminal → linked successor(s), including active-marker/session-queue ownership, `injection_consumed` prefix versus unconsumed suffix, old-event suppression, and `/stop`/`/new`/shutdown precedence.
- [R1-R2] Name and type the coordinator→runtime-delivery recovery lifecycle operation in `RelayLifecycleUpdate` (or an equally explicit typed companion), identify its old/new run ids and follower route, and state that it seeds only the new delivery context.  Its callback must not execute the current `accepted` external ACK/relay receipt behavior; terminal status must be emitted exactly once for the accepted follower.
- [R1-R3] Resolve R1-C2 by adding MODIFIED canonical liveness Requirements to kernel, Gateway, and IM delta-specs.  Keep the new SDK continuation Requirement and Gateway visible-recovery Requirement as ADDED only if they remain genuinely new after the design correction.
- [R1-R4] Make M1 validation explicitly exercise: old terminal precedes successor publication; more than one pending origin batch (including interleaved non-user pending work); one or more already-consumed followers plus an unconsumed suffix; absent/corrupt link; duplicate/late successor event; and recovery raced by `/stop`, `/new`, and shutdown.  Assert both external ACK/receipt count and one visible final delivery, not only Kernel output.

### Author Resolutions

- [R1-C1] accepted — `RunsRegistry` 确实先 publish old terminal，再在 `_settle_terminal_pending()` 里按 origin batch 重提；仅 predecessor id 无法让 Gateway 区分 batch 或判定没有 successor。已将设计改为 Kernel-owned `pending_id`、per-batch continuation descriptor 和一次 recovery settlement，并在 `RecoveryHandoffLedger` 状态机中明确 old terminal→successor、已消费前缀/未消费后缀、active marker/FIFO、mismatch/no-successor、重复/迟到 event 与 `/stop`/`/new`/shutdown 优先级。`recovery_adopted` lifecycle 也明确为 no-ACK/no-receipt，位置见 `design.md` 决策 2-4、接口表、时序图、风险表和 M1；对应新 SDK/Gateway delta 条目同步更新。
- [R1-C2] accepted — canonical kernel、Gateway、IM 的 liveness 条款都是现有同一规则，不能并列新增第四种。已将三份 liveness delta 改为 `MODIFIED Requirements`，保留每个现有 scenario 并加入自动压缩 scenario；仅可结算的 recovery handoff 保持 `ADDED`，位置见 `specs/kernel/runs.md`、`specs/gateway/routing-delivery.md` 和 `specs/im/gateway-relay.md`。

## Round 2

### Metadata

- reviewer: `/root/bugfix_536_design_reviewer`
- target: Round 1 resolutions plus `design.md` and the Kernel/Gateway/IM delta-specs in `docs/changes/bugfix-536-feishu-steer-recovery/`
- review_mode: `full`
- mode_reason: Decisions 2–4 revise a cross-module Kernel SDK event contract, Gateway logical-run ownership, and delivery lifecycle semantics.  This is a high-risk shared seam, so a closure-only review would not be sufficient.
- started_at: `2026-08-13T15:09:29+08:00`
- completed_at: `2026-08-13T15:12:34+08:00`
- duration: `3m 05s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

Both prior blockers are substantively closed.  The revised design makes the recovery handoff a complete SDK-visible protocol rather than an inferred successor relationship, and the liveness deltas now replace the relevant canonical Requirements rather than append competing ones.  This is a design-only verdict: implementation and its tests still need the M1 acceptance evidence.

### Historical issues

| ID | Author resolution | Re-review result and evidence |
|---|---|---|
| R1-C1 | accepted | **Closed.** `design.md:71-79` assigns Kernel ownership of a returned opaque `pending_id`, per-batch descriptor, and exactly-one `recovery_settled` closure.  `design.md:81-105` specifies the old-terminal → settlement → successor state machine, unconsumed-suffix ownership, FIFO marker, mismatch/late-event behavior, and control precedence.  `design.md:107-124` gives the delivery handoff a typed `recovery_adopted` shape with no ACK/receipt side effect.  This directly covers the failure sequence in current code, where terminal settlement later drains and submits origin batches (`registry.py:550-629`), and where the old coordinator would otherwise tear down all followers. |
| R1-C2 | accepted | **Closed.** Kernel, Gateway, and IM liveness changes are each under `## MODIFIED Requirements` (`specs/kernel/runs.md:21-46`, `specs/gateway/routing-delivery.md:27-68`, `specs/im/gateway-relay.md:3-33`).  They reproduce the existing requirement and its scenarios while adding the compaction scenario.  The only `ADDED` items are genuinely new recovery contracts (`kernel:5-19`; `gateway:5-25`), which is consistent with the `ADDED`-append / `MODIFIED`-replace rule in `docs/specs/CONTRIBUTING.md:150-164`. |

### Coverage

Inputs re-read in full: `incident.md`; revised `design.md`; all three delta-specs; canonical Kernel, Gateway, and IM specs; delta merge rules; current SDK/registry/coordinator/runtime-delivery/liveness paths; and focused liveness, registry, and coordinator tests.  No implementation was changed or executed in this design review.

#### 现状断言台账

| ID | 断言 / 约束 | 核实结论与证据 |
|---|---|---|
| A1 | 自动压缩在同 run pending drain 前发生，且当前没有父 run heartbeat | 成立。`loop.py:362-386` 先 `_maybe_compact()` 再 drain；`loop.py:1054-1064` 直接 await summarizer，而主 LLM stream 已在 `443-455` 受 liveness wrapper 保护。 |
| A2 | 摘要 sidechain 必须保持静默 | 成立。`summarizer.py:72-97` 使用 no-op session-event publisher 且不挂 permission requester；D1 只在父 run 边界补 heartbeat，符合这条隔离。 |
| A3 | 当前 continuation 的事实与发布顺序由 Registry 掌握 | 成立。non-user terminal 在 `_finish()` 的 terminal 处理之后才进入 `finally` 的 `_settle_terminal_pending()`；后者按 contiguous origin batch 提交 successor（`registry.py:550-629`）。这正是 D2 不让 Gateway 猜测的必要依据。 |
| A4 | 现有 SDK seam 足以承载新事实，不需要 Gateway 触及 core | 成立。PA 只能使用 SDK（`SPEC.md:151-161`）；`try_steer()` 是 inject-only seam（`kernel.py:1670-1702`），而 `submit(steer=True)` 已直接复用它（`1756-1759`），故 `pending_id` 可由同一 `RunInfo` 自然传播。 |
| A5 | 当前 coordinator 的 old-run 收尾会丢失 recovery delivery owner | 成立。admission 保存 follower（`session_run_coordinator.py:260-333`），但 close 路径清除 active/follower state（`1372-1384`），且 old terminal 使当前 stream consumer 结束（`1876-1955`）。D3 逐项取代这些不适用于恢复 suffix 的动作。 |
| A6 | 已消费前缀和未消费 suffix 必须区别处理 | 成立。当前映射以 `injection_consumed` 计数选择 follower shadow（`session_run_coordinator.py:1958-2000`）。D3 仅保留未消费 suffix，避免已进入旧 run 的消息被错误宣称为恢复成功。 |
| A7 | lifecycle 的 accepted 分支不能复用于 recovery | 成立。当前 phase 仅有 accepted/running/terminal（`inbound_models.py:196-213`）；accepted 同时 ACK 外部入站、seed context、发 relay receipt（`runtime_delivery/lifecycle.py:31-64`）。D4 的 explicit no-ACK `recovery_adopted` 是必要且足够窄的 seam。 |
| A8 | typed recovery lifecycle 仍可复用按-run context 和 terminal delivery | 成立。context store 按 run id 管理（`runtime_delivery/context.py:253-357`），terminal lifecycle 已执行 report/receipt（`runtime_delivery/lifecycle.py:82-139`）。D4 只增加新 run context 的种子路径，不新设 channel adapter。 |
| A9 | `/stop`、`/new` 和 shutdown 是恢复链的硬终结条件 | 成立。用户中断的 pending 进入 held buffer 而非 auto-continuation（`registry.py:600-609`）；D2/D3 明确排除 held pending，并把控制竞争置于 ledger 优先级之上。 |
| A10 | existing liveness policy 的 compaction 缺口是本 unit 的最窄变化 | 成立。current liveness tests 覆盖 ticker/LLM/permission，没有 compaction call site（`tests/unit/test_liveness_ticker.py:36-110`）。D1 与三份 MODIFIED requirement 都只加这第四个静默窗口。 |
| A11 | Gateway permission exemption 与 Kernel/IM permission heartbeat 是既有分层语义，不是本轮新引入的差异 | 成立。canonical Gateway routing requirement 仍规定 permission window 不依赖 heartbeat；canonical Kernel/IM 条款仍规定它能产生/消费 liveness。修订后的 Gateway delta 保留其 exemption（`specs/gateway/routing-delivery.md:27-68`），Kernel/IM delta 只在各自既有条款中加入 compaction，因此没有把 baseline policy drift 误归为本 unit 的新要求。 |

#### 决策、首文档与 delta-spec 台账

| ID | 覆盖项 | 结论 |
|---|---|---|
| D1 | 父 run compaction heartbeat、sidechain 不泄漏、watchdog 仍回收真卡死 | 通过。`design.md:63-69` 复用 await-bound ticker，且没有延长或关闭 watchdog。 |
| D2 | pending identity、batch correlation、successor 集合和确定失败收口 | 通过。`design.md:71-79` 与 Kernel ADDED requirement/scenarios（`specs/kernel/runs.md:5-19`）完整定义 producer/consumer contract，不再把 batch/order/absence 推给 Gateway 推断。 |
| D3 | old terminal 之后的 logical owner、prefix/suffix、FIFO、duplicates 和 control race | 通过。状态图和规则（`design.md:81-105`）覆盖 R1 所列 old terminal first、多 batch、none/unavailable、late event、`/stop`/`/new`/shutdown；M1 将这些化为测试退出标准。 |
| D4 | 新 delivery context、no ACK/receipt、per-follower terminal 和一次外部文本 | 通过。`design.md:107-124`、恢复时序图（`147-168`）及风险表（`183-187`）一致，且没有产生飞书专用路径或 IM 网络帧变更。 |
| S1 | 正常压缩不得被误报失败；真停止才接住后发消息 | 通过。D1 和 D2/D3 明确分开 alive-but-quiet 与 non-user terminal 两条路径。 |
| S2 | 恢复必须保留原上下文，补充消息不是孤立新问题 | 通过。D2 保留同一 session 的 Registry continuation；D3 将 accepted suffix 交给关联 successor，而非创建 Gateway fallback turn。 |
| S3/S8 | 飞书、Web IM 和其他 Gateway 入口一致 | 通过。D4 复用 common delivery adapter；Gateway ADDED requirement (`specs/gateway/routing-delivery.md:5-25`) 将“原聊天、一次可见结果”写为 channel-neutral contract。 |
| S4/S9 | 仅精确 `/stop`、`/new` 是控制；不得放宽 watchdog 或扩大范围 | 通过。D1 拒绝 watchdog 绕开；D2 排除 user-held pending；D3/D4 维持 control precedence，M1 未加入前端、IM protocol 或 Feishu-specific 代码。 |
| S5 | 压缩期间追加普通消息连续完成 | 通过。Kernel/Gateway/IM MODIFIED requirements 都新增 compaction scenario；Gateway scenario 还明确后续普通消息和既有上下文继续。 |
| S6 | 真中断前已接收消息无需重发、无 timeout/duplicate | 通过。pending-id/descriptor/settlement 和 `recovery_adopted` 对应此验收；Gateway ADDED scenarios 覆盖 successful、no-successor/mismatch 两种可见结果。 |
| S7 | 恢复收口后下一条普通消息可正常开始 | 通过。D3 在 successful terminal、settlement failure、fallback expiry、explicit controls 后释放 marker/FIFO；D2 不允许无限等待。 |
| DS-K1 | SDK recovery handoff 是新的、消费者可验证的能力 | 通过。`ADDED` Kernel requirement 给出 identity、descriptor 和 exactly-once settlement，符合 SDK-consumer 视角。 |
| DS-K2/DS-G2/DS-I1 | 三处 liveness canonical clauses 的替换完整且只加 compaction | 通过。三份 MODIFIED 条目保留原 Requirement 名称和既有 scenarios，分别加入 parent-run compaction scenario；没有平行 “fourth rule”。 |
| DS-G1 | Gateway visible recovery 是新的用户验收投影 | 通过。`ADDED` Gateway requirement 区分 valid recovery、unavailable/mismatch closure 和 explicit control，且不泄漏 Registry implementation。 |
| M1 | 单一垂直切片、范围、测试和 exit criteria | 通过。`design.md:199-205` 覆盖 kernel SDK/event、coordinator ledger、delivery lifecycle 和跨层回归；包括 old-terminal ordering、多 origin batch、prefix/suffix、corrupt/duplicate/late event、ACK/receipt count、one final output 和 lifecycle controls。 |

### 架构进攻

| 角度 | 结论与证据 |
|---|---|
| 归属 | 通过。Registry 产生它唯一知道的 pending/batch/settlement 事实；SDK 传递它；Gateway ledger 拥有 external delivery continuity；runtime delivery 只管理其 context。没有让 IM 或 Feishu 了解 Registry。 |
| 该不该存在 | 通过。没有 recovery descriptor 时，A3/A5 强迫 Gateway 从 timing、active id 或 origin 猜测 successor；`pending_id` 与 settlement 直接消除了这个真实缺口。 |
| 深还是浅 | 通过。D2 不暴露 Registry 重提交流程，D3 收拢 coordinator-specific follower complexity，D4 重用已有 delivery seam。consumer 得到的是足以闭环的 descriptor，不是半个 predecessor field。 |
| 治本还是补丁 | 通过。D1 修父 run 静默等待的真实 liveness 漏口；D2-D4 把 Kernel 的 input preservation 连到 Gateway 的 visible delivery。没有延长 watchdog、加 channel special case，或以隐式 retry 掩盖竞态。 |

### Issues

None.

### Recommendations

- [R2-R1][non-blocking] Implement M1's named ordering and delivery-count tests as contract-level regression evidence.  In particular, make the test observe the real order of old terminal, successor queued descriptor, settlement, recovery output, and terminal lifecycle; a unit test that only asserts a continuation run exists would not prove this approved handoff contract.

### Author Resolutions
