# Design Review: bugfix-520-compaction-context-loss

## Round 1

### Metadata

- reviewer: `/root/bugfix_520_design_reviewer`
- review_mode: `full`
- mode_reason: `R1 恒为 full；且用户在审查启动后补充了 automatic/overflow failure 的用户可见闭环，已丢弃旧快照并从当前 incident/design/delta/milestone 重新完整取证。`
- started_at: `2026-08-09T23:47:21+08:00`
- completed_at: `2026-08-09T23:56:23+08:00`
- duration: `9m02s`

### Verdict

Issues Found — 4 CRITICAL / 2 WARNING

### Coverage

- 已完整读取本 unit 当前 `incident.md`、`design.md`、kernel delta-spec 与 M1/M2 空目录骨架；本轮没有沿用用户补充前的文档快照。
- current-code 基线：nano-multiagent `83531f010225e8095fe4aaf04bc8d3306a117c8a`。从 `agent.sdk.build_kernel()` 正向追到生产 `ConversationSession → AgentRuntime/AgentLoop → JsonlTranscript`，并继续追到 RunsRegistry terminal、realtime assistant event、Gateway external/shadow delivery。
- current-spec/history 基线：`docs/specs/kernel/context-persistence.md`、`docs/specs/gateway/external-channels.md`、`docs/development/testing.md`、`docs/development/e2e-critical-paths.md`，以及 archive 中的 `refactor-462`、`feat-330`、`bugfix-443`。
- Claude Code 固定源码基线：本地 committed tree `0991eac5ccd518d6bd0486752f61a42f9ad68fa8`；公开契约复核了 [How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works#when-context-fills-up)、[Troubleshooting](https://code.claude.com/docs/en/troubleshooting#autocompact-is-thrashing) 与 [Context window](https://code.claude.com/docs/en/context-window#what-survives-compaction)。外部 checkout 是 dirty 的，因此源码证据全部取自 `git show HEAD:<path>`，未把工作区改动当基线。
- 按 design-reviewer 边界，本轮没有实现代码、没有走产品旅程，也没有修改任何受审产物。

### 核实台账

#### 现状断言

| ID | 原子 | 核实结论与独立证据 |
|---|---|---|
| A1 | `transcript.py` 是 raw JSONL、物化、event projection 与 compaction commit owner | 成立；`list_event_entries()` 在 `src/agent/core/session/transcript.py:171-223`，常规物化在 `639-686`，唯一原子提交在 `374-429`。但两条读取路径当前并非只差字段，见 R1-C1。 |
| A2 | `entries.py` 是 `SessionEntry` 构造/恢复 seam | 成立；constructor/consumer 位于 `src/agent/core/session/entries.py:92-164`，当前 producer 未写而 consumer 读取 top-level relation fields。 |
| A3 | compaction 包、loop、runtime 分别拥有 planner/summarizer、threshold 与 manual/overflow 编排 | 成立且是生产路径；`src/agent/sdk/kernel.py:730-770` 组装 `AgentEngine`/`ConversationSession`，loop threshold 在 `src/agent/core/agent/loop.py:335-354,967-1087`，runtime overflow/manual 在 `src/agent/core/agent/runtime.py:681-744,1888-2026`。Coding CLI 与 PA 分别从 `src/coding_cli/product.py:143-155`、`src/personal_assistant/product.py:418-430` 调 `build_kernel()`。 |
| A4 | `errors.py` 是 typed runtime error 位置 | 成立；`NanoMultiAgentError.to_dict()` 可携带 code/retryable/details，见 `src/agent/core/errors.py:6-42`。但当前 run terminal 不使用这条序列化，见 R1-C3。 |
| A5 | `conversation.py` 是 per-session transaction/state owner | 部分成立；`ConversationSession` 的 turn gate 确实串行 manual/turn（`src/agent/core/session/conversation.py:216-230,284-298`），但 `ConversationState` 是可重建/可淘汰 payload，不是进程期稳定 identity，见 R1-C2。 |
| A6 | 现有 E2E stack/catalog 可承载一条 recording-LLM 旅程 | 成立；catalog 明示 fake/recording LLM #14/#15（`docs/development/e2e-critical-paths.md:7-22,48-49`），当前总数确为 14 条（编号跳过 #7），压缩恢复仍在 backlog（`:30-60`）。 |
| A7 | 产品依赖边界与 JSONL append-only 约束 | 成立；产品组装只从 `agent.sdk` 进入，`append_compaction()` 以 atomic batch 写 boundary+replacement 且 epoch mismatch 返回 false（`src/agent/core/session/transcript.py:374-429`）。 |
| A8 | summary 在 mutation 外计算、external epoch 防带外追加被隐藏 | 成立；loop 先 capture/summary 再 commit（`src/agent/core/agent/loop.py:990-1017,1062-1073`），manual/overflow 同样 capture 后提交（`src/agent/core/agent/runtime.py:1910-1943,2001-2024`）。 |
| A9 | 同会话事务状态不应放共享 loop/provider | 成立；`AgentRuntime.execute_turn()` 以当前 state 绑定 ContextVar，`ConversationSession` 是稳定 identity；共享 loop 上建跨 session map 会破坏现有归属。但 design 选到可重建的 `ConversationState` 仍不成立，见 R1-C2。 |
| A10 | 测试分层与隔离 runtime 约束 | 成立；`docs/development/testing.md` 要求最窄原因层与 worktree 隔离，既有 critical fixture 已集中真 IM/Gateway 启停。 |
| A11 | 加深 `new_turn_appended_entry()` / `message_from_turn_entry()`，不建第三 DTO | 对字段不对称是正确复用；`_message_to_raw()` 已持久化 parent/tool/group/reasoning/parts（`src/agent/core/session/transcript.py:906-935`）。但它不足以独自达成 design 宣称的整条 `load()` 等价，见 R1-C1。 |
| A12 | 复用 `append_compaction()` 作为唯一 durable owner | 成立；archive `refactor-462` 的 transaction 方向与 current code `src/agent/core/session/transcript.py:374-429` 一致。 |
| A13 | planner、CC-style prompt、reinjection/file restore 可复用 | 成立；事故根因不在 prompt/planner 选择；current planner 消费 event vocabulary（`src/agent/core/agent/compaction/planner.py:18-67`），loop/runtime 复用 reinjection/file restore。 |
| A14 | summarizer 当前把异常/空结果变成固定 fallback | 成立；current `CompactionSummarizer.summarize(strict=False)` 捕获后进入 `_fallback_summary()`；loop 随后无条件构造 summary 并 commit（`src/agent/core/agent/loop.py:1007-1076`）。删除 fallback 直接针对 RCA-B。 |
| A15 | `ConversationState` 可作为本进程 per-session 连续失败计数 owner | 不成立；普通 external append 增加 epoch（`src/agent/core/session/transcript.py:265-306`），下一次 operation 会重建 state（`src/agent/core/session/conversation.py:403-430`）；LRU 也会清空它（`:432-440`、`src/agent/core/session/directory.py:182-200`）。见 R1-C2。 |
| A16 | 泛化既有 `stub_llm_stack` 比复制进程 fixture 更深 | 成立；同一真栈已有两个 recording journey，设计只加可选 script/env/window，避免第二套生命周期 owner。 |
| A17 | 现有 fidelity helper 绕过真实 projection seam | 成立；事故复现发生在 `list_event_entries()` producer，而手工 `SessionEntry` 无法证明 producer 写对，改成真实 transcript 双路径是正确测试层。 |
| A18 | `refactor-462` 奠定 session transaction/单 commit | 成立；历史 design 把 summary 计算放 mutation 外、commit 检 epoch，current code仍沿用。 |
| A19 | `feat-330` 奠定 boundary+summary restart model | 成立；current `_materialize()` 从最后 boundary 后恢复（`src/agent/core/session/transcript.py:660-686`）。 |
| A20 | `bugfix-443` 说明 12K 真历史不会触发 200K 默认窗口 | 成立；因此小 window+受控 usage 是短 E2E 的必要触发手段，而不是 mock private method。 |
| A21 | 历史 M16 固化 fallback-success | 成立；当前代码与旧测试期望共同证明该历史取舍，改写为 no-commit 是此次需求直接驱动。 |
| A22 | “Claude Code 连续 auto summary failure 三次后显示错误；Nano 精确移植” | 不成立；固定源码 `autoCompact.ts:257-265,312-349` 在第三次 summary exception 后只返回 `wasCompacted:false` 并静默 skip，`query.ts:536-543` 只线程内传计数，没有用户消息；公开 troubleshooting 的 user-visible thrashing error描述的是 compaction **成功后上下文立即再次填满**。见 R1-W1。 |

#### 编号决策

| 决策 | 完整性 / 自洽 / 依据核实 |
|---|---|
| D1 `raw turn → SessionEntry → Message` 等价常规 `load()` | 目标由 RCA-A/不丢历史直接驱动，拒绝第三 raw-dict path 正确；但列出的字段搬运和测试样本没有覆盖 active branch 与 `tool_call_recovery` 注入，无法兑现所称“等价”，见 R1-C1。 |
| D2 summarizer 只返回有效文本或 `None` | 拍板清楚，与 incident 不允许假成功一致；manual/threshold/overflow 都在 commit 前拿到有效 summary。overflow cause 的 terminal 出口未闭合，见 R1-C3。 |
| D3 per-session 三次 automatic 熔断、成功重置、固定 assistant event | 固定文案、前两次静默、overflow 立即终止、不进 transcript、复用标准 assistant event 的用户闭环已拍死；event 路径由 `src/agent/platform/hooks/builtins/realtime_stream.py:35-64` 与 Gateway observer `src/personal_assistant/gateway/runtime_delivery/observer.py:549-591,803-816` 支持。状态 owner 的生命周期错误，见 R1-C2；CC 归因错误见 R1-W1。 |
| D4 单 durable owner、成功后才替换 state | 单 owner、epoch stale 不计 failure、成功后 reset 都自洽；但 flow 把 stale false 与 persistence exception 合并成没有出口的 `Keep`，见 R1-W2。 |
| D5 一条短而完整的长期 E2E | 成立；真 IM/Gateway、真 Gateway tool、匹配 result、真实 threshold、recording request、有效 boundary、restart 形成最短完整事故链。旧字段丢失会在 provider mapper/stub pairing 处红，fallback/错误 boundary 会在 JSONL与 sentinel 连续性处红。 |
| D6 unit/integration/E2E 分层 | 成立；字段 seam、三入口 transaction、真进程 restart 分别落最低有效层，没有把失败矩阵复制进 E2E。external assistant text 已有 canonical Gateway 契约（`docs/specs/gateway/external-channels.md:146-148`），因此 no Gateway delta 合理。 |

#### Incident 约束、澄清、矩阵与非目标

| ID | 约束 | 设计覆盖核实 |
|---|---|---|
| I1 | RCA-A：projection 丢 tool/group 等结构关系 | D1/M1 正面落点正确，但只修字段不足以覆盖所有 recoverable history，见 R1-C1。 |
| I2 | RCA-B：异常被固定 fallback 伪装成功 | D2/M2 删除 fallback、先有效摘要后 commit，完整覆盖。 |
| I3 | RCA-C：测试绕开关键 seam | D5/D6/M1 以真实 transcript projection + recording E2E 补齐。 |
| I4 | 用户要求长青 E2E | D5、M1、catalog 修改完整覆盖。 |
| I5 | 失败语义按 CC 业务逻辑 | no-loss/circuit-breaker 原则覆盖；第三次 fixed message、shared overflow count、per-session lifetime 是用户后续确认的 Nano 决策，不是固定 CC 精确行为，见 R1-W1。 |
| I6 | manual/threshold/overflow 同一 no-loss invariant | D2/D4/M2 覆盖摘要失败与 commit 前置；commit exception 的后续结果仍有歧义，见 R1-W2。 |
| I7 | 只新增一条 E2E，其余矩阵下沉 | D5/D6/M1/M2 完整覆盖。 |
| I8 | fixture 短而完整，含 user/tool call/result/trigger/continuation | D5 状态机逐项具备，并用小 window/usage 而非 200K filler。 |
| I9 | compaction 输入保持 tool pair/group/parts | D1 字段样本覆盖常规 closed pair；recovered pair/active branch 缺口使本项未完全覆盖，见 R1-C1。 |
| I10 | 只有可继续任务的有效摘要可提交 | D2 判空/异常、D4 commit gate 覆盖；主观质量明确非目标。 |
| I11 | 失败不写假摘要，历史/boundary 不变 | D2/D4及 M2-C1 覆盖。 |
| I12 | 三入口同一 no-loss 语义 | D2/D4与 public Kernel integration matrix 覆盖。 |
| I13 | automatic 连续失败熔断并显式可诊断 | 文案/顺序已覆盖，但 state owner 与 terminal diagnostic carrier 分别被 R1-C2/R1-C3破坏。 |
| I14 | 成功 compaction 当前进程/restart/resume 连续 | D4/D5/M1 成功旅程覆盖。 |
| I15 | E2E 贯穿 transcript→entry→message→summarizer→boundary→turn | D5 sequence 与 recording/JSONL 双断言覆盖。 |
| I16 | threshold success | M1 E2E覆盖 tool pair、目标 sentinel、后续 turn。 |
| I17 | threshold failure | M2 matrix/固定消息覆盖；跨 turn 的三次计数无法由当前 owner保证，见 R1-C2。 |
| I18 | overflow success/failure，成功只 retry once | D2/D3与 M2-C3覆盖；failed terminal root cause 出口缺失，见 R1-C3。 |
| I19 | manual success/failure | D2/D4、existing control reply与 integration tests覆盖。 |
| I20 | restart/resume after success | D5 Gateway restart+M1 worker JSONL断言覆盖。 |
| I21 | 不引入 CC memory/microcompact/context collapse | design 明确 no new layer/schema/CC product scope，未越界。 |
| I22 | 不重做 prompt/主观质量 | D2保留 prompt，只判空/异常，未越界。 |
| I23 | 不删历史 transcript、不绕 provider pairing | D4明确不修旧 boundary，D1/E2E修 relation seam，未越界。 |

#### Delta-spec

| 条目 | 锚点 / 用法 / 消费者可观察性核实 |
|---|---|
| K0 MODIFIED `上下文压缩在长会话中保持可恢复` | 精确锚定 canonical 同名 requirement，原有 manual/focus/idempotency/model-window/workspace scenarios 均保留；用 MODIFIED 正确。 |
| K1 手动触发压缩 | 保留 canonical 行为，consumer API/result/boundary replay 可观察。 |
| K2 focus 指导后续上下文 | 保留 canonical 行为，focus 不成为普通 turn 可由 transcript观察。 |
| K3 manual failure 不改变上下文 | 调用错误、compaction record、后续可恢复上下文均为 consumer 可观察。 |
| K4 threshold failure 不伪装成功 | record/active context/下一次模型可见历史是 kernel consumer 可观察行为。 |
| K5 连续 automatic failure 有界 | assistant-before-failed、无新 record、summarizer 不再重复是外部 stream+档案可验；state owner实现不了跨外部 turn，见 R1-C2。 |
| K6 overflow failure | no retry、assistant-before-failed、diagnostic、history 可观察；diagnostic data flow未闭合，见 R1-C3。 |
| K7 tool history compaction restart | THEN 同时写了内部“摘要模型收到关系有效历史”，违反 delta 场景消费者可观察红线，见 R1-C4。 |
| K8 automatic 不继承 manual focus | 保留 canonical 行为，可从 subsequent compaction outcome/request seam验收。 |
| K9 manual idempotency | 保留 canonical 行为，result与 record count可观察。 |
| K10 按当前模型窗口判定 | 保留 canonical 行为，触发边界可观察。 |
| K11 未声明窗口回退 | 保留 canonical 行为，默认边界/不报错可观察。 |
| K12 workspace session compact/replay | 保留 canonical 行为，terminal与重放结果可观察。 |
| package coverage | kernel delta 是唯一新增契约；Gateway canonical 已要求任意 external-triggered assistant text 回原 chat并同步 shadow（`docs/specs/gateway/external-channels.md:146-148`），IM/CLI/wire/API/schema不变，显式 no delta 正确。 |

#### Milestones

| Milestone | 垂直性 / 并行 / 范围 / 退出标准核实 |
|---|---|
| M1 projection-continuity | 是独立成功切片：修 production projection，并以真产品入口+restart交付用户连续性；与 M2 文件无交集，当前 summarizer 在有效 summary 时可独立工作，故同组 A 可真并行。reviewer/worker 两轨齐全。但范围与 C2 没要求 recovery/active-branch seam，当前会交付一个仍非无损的投影，见 R1-C1。 |
| M2 cc-failure-semantics | 是独立失败切片：三入口 no-loss、assistant-before-failed、Feishu/shadow与 reset均有 reviewer/worker退出标准；文件范围与 M1 无交集。`ConversationState` owner使 C2无法实现，RunsRegistry不在范围使 overflow terminal root cause C3没有落点，见 R1-C2/R1-C3。 |

### 架构进攻

| 角度 | 主动攻击结果 |
|---|---|
| 归属 | 不新增跨层依赖、assistant event 复用既有 kernel→Gateway路径、durable commit继续归 transcript，均自然。唯一错放是把进程期 session circuit state放入可因 epoch/LRU重建的 payload；长期代价是负载/入口决定安全策略是否生效，见 R1-C2。 |
| 该不该存在 | 没有新增 framework/registry/DTO；`CompactionError`承载稳定 code/details且服务三入口诊断，存在有必要。泛化既有 recording fixture 比复制 stack 更少 owner。无 YAGNI 问题。 |
| 深还是浅 | 深化既有 entry seam 是正确方向，但只共享字段 serializer、没有共享 active-branch/recovery materialization，接口仍宣称“等价”却藏不住复杂恢复规则；这会让下一种 control entry 再次漂移，见 R1-C1。 |
| 治本还是补丁 | 删除 fallback并守唯一 commit是治本；短真栈 E2E可永久捕获原事故。固定消息通过通用 event/outbound seam而非 Feishu特例，也是长期路径。CC标签失真不会改变当前用户拍板，但会污染后续基线判断，见 R1-W1。 |

### Issues

- [R1-C1][CRITICAL] [决策 1 / M1]: 所谓“`list_event_entries() → Message` 等价常规 `load()`”只设计了 raw turn 字段搬运，遗漏了常规物化的两项语义：`_reachable_turn_entries()` 会过滤到 active branch（`src/agent/core/session/transcript.py:689-739`），`_inject_recovery_messages()` 会把 `tool_call_recovery` control entry 物化成闭合 tool result（`:675-685,742-777`）；当前 `list_event_entries()` 却遍历所有 raw turn且忽略 recovery（`:171-223`）。M1 的 guard/E2E 只覆盖正常闭合 pair/group/parent，worker完全可以按文档补完字段并全绿，却在 fork/steer后的死分支或中断工具恢复会话再次把 orphan tool call交给 summary provider。**不改会导致本事故的不变量只对 happy path成立，生产中的可恢复历史仍会稳定触发 provider配对失败或摘要错误分支。** 设计需拍死 event projection 如何复用与 `load()` 相同的 boundary、active-reachability、recovery语义，并把 recovery+abandoned branch加入 M1最低 guard，而不是只扩字段列表。

- [R1-C2][CRITICAL] [决策 3 / M2]: `ConversationState` 不是设计声称的“本进程 per-session”稳定 owner。PA/外部入口每次 `append_external()` 都递增 external epoch（`src/agent/core/session/transcript.py:265-306`），下一轮 `_ensure_loaded()` 会新建 `ConversationState`（`src/agent/core/session/conversation.py:403-430`）；即使没有带外追加，超过32个 loaded conversation时 LRU也会清空 state（`src/agent/core/session/directory.py:182-200`、`conversation.py:432-440`）。因此第1/2次 threshold failure若跨用户 turn发生，计数会在同一进程内归零，永远到不了第3次 fixed assistant message/failed terminal。**不改会让安全熔断是否生效取决于入口和会话负载，M2-C2无法兑现且长会话仍可无限重试摘要。** 计数应归属进程期稳定的 `ConversationSession` identity（或文档另选同等稳定 owner），并用 external append reload与LRU eviction后的连续失败测试证明只在 process restart/reset-on-success时归零。

- [R1-C3][CRITICAL] [决策 2/3 / 接口与数据流 / M2]: design承诺 `CompactionError` 的 trigger/root cause/details进入 overflow failed terminal诊断，但当前 RunsRegistry在 target completion时只做 `str(completion.error)`（`src/agent/core/runs/registry.py:510-525`），再固定写成 `{code: run_execution_failed, message}`（`:674-701`）；`NanoMultiAgentError.to_dict()` 的 code/details（`src/agent/core/errors.py:30-42`）完全没有被调用。M2范围也不含 registry或 terminal序列化测试。**不改会出现“异常对象内部保留 cause、真正消费者收到的 failed terminal却丢根因”，delta K6和 M2-C3可在错误层级上被误判为通过；另一种猜法则会把 provider原始错误塞入用户消息字符串并改变隐私/契约。** 设计必须指定 structured diagnostic的唯一 carrier与序列化边界，补齐相应 source/test scope，并明确 fixed assistant文案与 diagnostic details分离。

- [R1-C4][CRITICAL] [kernel delta K7]: `含工具历史的压缩在重启后继续任务` 的 THEN 写“摘要模型收到关系有效的历史”（`specs/kernel/context-persistence.md:51-54`），这是内部 provider输入断言，不是 kernel代码消费者可观察结果，违反 delta-spec的 THEN红线。**不改会在收尾归并时把内部实现/测试 seam写进长期 canonical契约，未来即使更换为本地摘要器或共享物化路径、消费者行为完全不变也会被误判 breaking change。** delta只应保留 subsequent run、restart/resume、transcript/compaction outcome等消费者可观察结果；provider pairing校验留在 design/M1 worker退出标准。

- [R1-W1][WARNING] [现状分析“相关历史” / 决策 3 命名]: 当前文档没有准确复刻固定 Claude Code 的失败语义。`autoCompact.ts:257-265,312-349` 的 summary exception在前三次都只返回 `wasCompacted:false`，到上限后静默跳过；`query.ts:268-279,536-543` 的 tracker是该 query状态，并没有 Nano文档所称跨 turn per-session owner或第三次 fixed assistant message。公开 troubleshooting 的 user-visible thrashing error针对的是“压缩成功但上下文立即再次填满”，reactive overflow恢复也在 `query.ts:1068-1178` 单独处理。用户本轮已经明确拍板了更强的 Nano闭环，所以目标行为本身不冲突；但**不改归因会让 worker/reviewer在未写明的 reset/count/overflow边界上把错误 upstream模型当 oracle，并让未来维护者误以为这是 source-identical port。** 请改成“复用 CC 的 no-replacement + bounded retry原则，第三次固定提示、threshold/overflow共计数与进程期 session生命周期是用户确认的 Nano产品决策”，同时保留固定源码版本和差异表。

- [R1-W2][WARNING] [决策 4 failure flow / M2-C3]: 设计把 `append_compaction()` 的 epoch stale `False` 与 durable persistence exception都画到同一个无出口的 `Keep`，但 current code二者机制不同：只在 epoch mismatch返回 false，writer failure会抛出（`src/agent/core/session/transcript.py:387-426`）。文档只拍死 stale不计数，没有说明 threshold/overflow在真实持久化异常后是继续旧prompt、以 typed compaction failure终止，还是保留哪个 cause；M2测试矩阵也只显式列 stale和 summary failure。**不改会让两个 worker都能声称“历史没变”却交付不同 terminal/retry/diagnostic行为，overflow甚至可能覆盖原始 overflow cause。** 建议分别拍死 manual/threshold/overflow 的 stale与 persistence-exception出口，并在 M2退出标准加入相应可观察断言。

### Recommendations

- [R1-R1] 让 compaction event vocabulary消费一个与 `load()`共享的 canonical “latest-boundary active recoverable messages”投影；若必须保留 event形状，也应由同一 reachability/recovery语义生成，而非复制第三套规则。
- [R1-R2] 把 automatic failure state移到不会因 external epoch或LRU unload消失的 process-lifetime session identity，并写明 process restart是唯一非成功 reset边界。
- [R1-R3] 定义 `CompactionError → RunRecord.error/run_status` 的结构化序列化契约与测试落点；fixed assistant文本保持恒定且不承载 provider内部诊断。
- [R1-R4] 把 delta K7 的 provider输入断言移回 M1 worker验收，只在 canonical delta保留后续 run/restart持续原目标等 consumer outcome。
- [R1-R5] 把“CC语义”拆成固定版本事实、Nano复用原则、用户确认的本地差异三列，避免错误声称精确移植。
- [R1-R6] 为 commit stale与 persistence exception分别补齐三入口状态机；无需扩成通用错误框架，只需拍死 terminal/retry/count/cause四个结果。

### Author Resolutions

| Issue | Resolution |
|---|---|
| R1-C1 | **accepted** — current `_materialize()` 确实额外执行 latest-boundary、`_reachable_turn_entries()` 与 `_inject_recovery_messages()`，只补 top-level 字段不能兑现无损语义。`design.md` 决策 1、架构图、成功时序、测试分层与 M1-C2 已改为两条读取路径共享 canonical active recoverable projection，并把 `tool_call_recovery` 与 abandoned branch 加入永久 guard；delta 只保留消费者结果。 |
| R1-C2 | **accepted** — `ConversationState` 会因 external epoch reload 与 payload LRU 重建。tracker owner 已移到进程期稳定 `ConversationSession` identity，每次 payload 只注入同一引用；process restart 是唯一非成功 reset，external reload/LRU 与成功 reset 都进入设计、风险、测试和 M2-C2。 |
| R1-C3 | **accepted** — current RunsRegistry 对 completion error 只做 `str()`。M2 范围已加入 `src/agent/core/runs/registry.py` 与 `tests/unit/agent/runs/test_runs_registry_executor.py`；设计限定只对 `CompactionError` 调 `to_dict()` 保留 `code/trigger/failure_kind/root cause`，普通 exception 仍为 `run_execution_failed`。固定 assistant 文案不含 cause，并与 failed terminal diagnostic 分离。 |
| R1-C4 | **accepted** — kernel delta 的 provider-input THEN 已删除；`含工具历史的压缩在重启后继续任务` 只承诺后续目标连续与 compaction record 可恢复，provider pairing 留在 M1 worker seam。 |
| R1-W1 | **accepted** — incident 与 design 已更正固定 CC 证据：summary exception 返回 `wasCompacted=false`、query 内 bounded retry、无第三次用户消息；公开 thrashing error 属另一场景。文档明确区分 CC no-replacement/bounded-retry 原则与用户确认的 Nano session 计数、threshold/overflow 合并及固定提示，M2 重命名为 `bounded-failure-semantics`。 |
| R1-W2 | **accepted** — design 决策 4 与 failure flow 已拆开 epoch stale 和 persistence exception。stale：threshold 保留 prompt 等下轮重算、manual 失败确认、overflow 保留原错误，均不计 summary failure；persistence exception：manual 失败确认，automatic 固定提示 + typed terminal，overflow 同时保留两类 cause，均不计 summary failure。delta 新增持久化失败 Scenario，M2-C1/C3 与测试矩阵同步。 |

Recommendations R1-R1 至 R1-R6 均已随对应 accepted issue 落入 `incident.md`、`design.md`、kernel delta、Milestone 范围/退出标准与骨架命名；没有另建兼容层、通用错误框架或 Gateway 专用分支。

## Round 2

### Metadata

- reviewer: `/root/bugfix_520_design_reviewer`
- review_mode: `delta`
- mode_reason: `Round 1 已有可信 full inventory；本轮 6 组修订均直接对应已知 issue，影响可封闭到 projection materialization、session tracker lifetime、typed terminal carrier、kernel delta、CC/Nano 证据分层、commit failure state machine 及两条 milestone。逐项追到上下游后未发现范围外溢，因此未升级为 full。`
- started_at: `2026-08-10T00:07:36+08:00`
- completed_at: `2026-08-10T00:11:51+08:00`
- duration: `4m15s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### Coverage

- 重新完整读取当前 `incident.md`、`design.md`、kernel delta-spec、Round 1 + Author Resolutions 与两个 milestone 骨架；当前目录确为 `M1-projection-continuity`、`M2-bounded-failure-semantics`，旧 M2 名称目录已不存在，milestone rows/dirs 均为 2。
- nano current-code 基线仍为 `83531f010225e8095fe4aaf04bc8d3306a117c8a`；重新核对 `transcript.py` 的 materialization/projection、`conversation.py`/`directory.py` 的 identity/payload 生命周期、`errors.py`/`runs/registry.py` 的 terminal error 数据流，以及 `append_compaction()` 的 stale/exception 边界。
- Claude Code 固定 committed 基线仍为 `0991eac5ccd518d6bd0486752f61a42f9ad68fa8`；外部 checkout 仍 dirty，继续只使用 Round 1 已从 `git show HEAD:<path>` 建立的固定源码证据。本轮文档对该证据的表述与源码一致。
- changed atoms：D1 canonical active/recovery projection；D3 stable session tracker；D3 `CompactionError → RunRecord.error` 窄 carrier；D4 stale/persistence 分流；incident/CC attribution；kernel delta K7 + 新 persistence scenario；M1/M2 scope/criteria/目录名。
- `retained_from: Round 1` — D2 删除 fallback、D5 单一短真栈 E2E、D6 测试分层、既有产品依赖边界/no Gateway delta/非目标均未被本轮修订改变，且 changed atoms 没有新调用方向或共享文件波及这些结论。
- 本轮运行 `PYTHON="$PWD/.venv/bin/python" ./scripts/docs-check`，结果为 `documentation integrity passed: 216 maintained Markdown sources, 67 required routes`；按 design review 边界未运行产品旅程或实现测试。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | accepted：共享 latest-boundary active/recovery projection，并扩 M1 guard | `design.md:78-88` 先统一 latest boundary、`_reachable_turn_entries()`、`tool_call_recovery`，再做 event adapter；这正覆盖 current `src/agent/core/session/transcript.py:639-777` 与 `171-223` 的语义差。M1-C2 明列正常/recovery pair、abandoned branch、全部 durable Message fields；synthetic recovery id 明确排除业务等价比较。 | closed |
| R1-C2 | accepted：tracker 移到稳定 `ConversationSession` identity | `design.md:100-108,165,240,267` 明确 identity 持有、payload 仅引用、external epoch reload/LRU 不 reset、process restart 才是非成功 reset。它匹配 current `conversation.py:403-440` 与 `directory.py:182-200` 的真实生命周期；M2 新增 conversation source/test 与两种 unload 验收。 | closed |
| R1-C3 | accepted：RunsRegistry 只窄序列化 `CompactionError` | `design.md:20-22,43,110-116,151,166,241,267` 指定 fixed assistant 文案与 structured diagnostic 分离，只对 `CompactionError.to_dict()` 保留 code/trigger/failure-kind/root cause，普通 exception 仍 `run_execution_failed`。这闭合 current `errors.py:6-42 → runs/registry.py:510-525,674-701,828-854` 的缺失 carrier；M2 scope/test 已包含 registry。 | closed |
| R1-C4 | accepted：delta K7 移除 provider-input THEN | 当前 `specs/kernel/context-persistence.md:57-60` 只承诺 subsequent run 延续目标与 compaction record 可恢复；provider pairing 仅留在 `design.md:86,132,146,266` 的 worker/E2E seam，不再进入 canonical consumer contract。 | closed |
| R1-W1 | accepted：区分 CC 固定事实与 Nano 产品增量 | `incident.md:28-29,71-76,95-100` 与 `design.md:47-53,100-116` 均准确写明 CC summary exception 是 `wasCompacted=false` + query 内 bounded retry、第三次无用户消息，公开 thrashing 是成功后立即 refill；session 级 threshold/overflow 合并与固定提示明确归因于用户确认的 Nano 决策。 | closed |
| R1-W2 | accepted：stale 与 persistence exception 分开 | `design.md:118-126,199-224` 对三入口分别拍死 stale 与 persistence outcome：stale 不计数，threshold 重算、manual 失败、overflow 保留原错误；persistence 不替换历史且 automatic typed 失败，overflow 同时保留两类 cause。kernel delta `:13,51-55` 新增 consumer-visible persistence scenario；M2-C1/C3 同步矩阵。 | closed |

### Changed-atom 核实

| Atom | 上下游影响与独立结论 |
|---|---|
| canonical recoverable projection | 归属仍在 `JsonlTranscript`，`load()` 与 `list_event_entries()` 是唯一两个消费者；event vocabulary、planner、JSONL schema均不外扩。把 boundary/reachability/recovery 集中一次解决根因，未造第二 DTO或第三 raw reader。 |
| stable automatic failure tracker | `ConversationSession` 是 SessionDirectory 进程期 interned identity，payload unload只清 `_state`，所以该 owner能兑现跨 external append/LRU 的 session语义；loop/runtime仍通过当前 ContextVar state窄引用，不需要共享 map。 |
| typed failed-terminal carrier | `RunRecord.error` 已是 `Mapping[str, Any]`，event hub会复制该 mapping；窄识别 `CompactionError` 可直接复用既有 transport，不需要新 wire/Gateway分支。fixed assistant message仍由既有 `message_end → assistant_message` 路径先行，诊断不会进入 transcript或用户文案。 |
| stale/persistence state machine | current `append_compaction()` 只在 epoch mismatch返回 `False`，writer异常会抛出（`src/agent/core/session/transcript.py:387-426`）；修订后的两分支与实际机制一致，三入口的 retry/terminal/count/cause均不再要求 worker猜测。 |
| kernel delta | MODIFIED 仍精确锚定 canonical同名 requirement并保留全部既有 scenarios；新 persistence scenario的 THEN只写 record、active context、terminal assistant/diagnostic等消费者可观察结果。删除的 provider-input断言已在 M1实现验收保留，没有丢测试意图。 |
| milestone split | M1 只含 `entries.py/transcript.py` + fidelity/E2E/catalog；M2只含 errors/summarizer/loop/runtime/conversation/registry + failure tests，source/test范围均无交集。M1有效 summary成功路径不依赖 M2，M2失败矩阵可用纯文本历史独立验证，仍可同组 A 真并行；两轨退出标准完整。 |

### 受影响架构进攻

| 角度 | 本轮结论 |
|---|---|
| 归属 | projection规则归 transcript、进程期状态归 stable session identity、terminal error投影归 RunsRegistry semantic writer，三处均放在现有唯一 owner，没有反向产品依赖或跨 session污染。 |
| 该不该存在 | canonical projection消除重复规则；private tracker只有一个owner/策略；typed terminal分支复用现有 `NanoMultiAgentError.to_dict()`。删除任一都会重新引入 R1 的漂移、生命周期或诊断断链，均不是 YAGNI abstraction。 |
| 深浅与治本 | D1共享的是 boundary/branch/recovery完整物化而非字段补丁；D3修在identity/terminal语义writer而非loop map或用户字符串；D4正面对待writer exception而非fallback commit。修订均加深既有 seam，没有专用 Feishu/wire/兼容层维护税。 |
| 并行交付 | 新增 registry/conversation source与tests只扩 M2，未进入 M1范围；两个切片仍各自有 reviewer用户价值与worker保真门禁，orchestrator可并行派发且不需隐式串行。 |

### Issues

None.

### Recommendations

None. Gate 2 可进入 `change-orchestrator`。
