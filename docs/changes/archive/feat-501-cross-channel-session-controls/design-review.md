# Design Review: feat-501-cross-channel-session-controls

## 2026-08-06 设计修正

评审后的用户澄清将 `/compact` 的并发语义从“busy 时拒绝”改为“排入当前聊天 FIFO”。因此本文此前关于 D3/S12 的 idle-only 或 busy outcome 结论仅保留为当时评审记录；当前权威契约见 `spec.md` 的“正在运行时排队压缩当前会话”及 `design.md` 的决策 3。

## Round 1

### Metadata

- reviewer: `/root/design_review`
- review_mode: `full`
- mode_reason: `R1；首次独立 Gate 2 审查，且新增跨入口会话边界、Gateway/Kernel 共享契约、delta-spec 与两个 milestone。`
- started_at: `2026-08-05T01:16:55+08:00`
- completed_at: `2026-08-05T01:21:58+08:00`
- duration: `5m 03s`

### Verdict

Issues Found — 5 CRITICAL / 0 WARNING

该方案的总体归属（shared inbound seam → coordinator → binder / SDK）和 `/compact` 的内核收口是正确方向；但 `/new` 的终态可见性围栏、provider replay 的操作幂等、IM 离线时控制确认的 durable shadow，以及两处 delta-spec 的 MODIFIED 锚点尚未拍死。此时进入实施会让 worker 在已明确的用户安全边界上自行猜测，不能通过 Gate 2。

### Coverage

完整读取并逐条核对：`spec.md`、`design.md`、三个 delta-spec、`docs/specs/gateway/{routing-delivery,external-channels}.md`、`docs/specs/kernel/context-persistence.md`、`SPEC.md`；生产组装与执行路径为 `composition.py:390-405,474-510` → `InboundDispatcher._run_root()` → `InboundPipeline.handle_inbound()` → `SessionRunCoordinator` → `GatewaySessionBinder` → `agent.sdk.Kernel` → `ConversationSession` / `AgentEngine`。也追到了 Web IM 文本发送、Feishu 入站、external shadow saga、control/background reply、FIFO 和 compaction persistence，而非只对照 design 中的引用。

#### 现状断言台账

| 原子 | 结论 | 本轮实际证据 |
|---|---|---|
| A1 `InboundPipeline` 是 Web relay 与外部 channel 共用入站门面 | 成立 | 生产 compose 在 `composition.py:474-498` 构造唯一 coordinator/pipeline/dispatcher；`inbound_pipeline.py:102-147` 依次 route、group gate、shadow、`/stop`/normal dispatch。 |
| A2 coordinator 是 session run/control 转换 owner，`/stop` 在此执行 | 成立，但其终态抑制不能直接承诺 `/new`（R1-C1） | `session_run_coordinator.py:175-240,242-295,380-505` 持 per-session transition、steer/FIFO、interrupt 与 reply；终态细节见 R1-C1。 |
| A3 binder 持有 binding、reply context、runtime/provenance 与创建 | 成立 | `session_binder.py:203-307,397-410` 是 `resolve`/lookup/current agent 的 owner；`_build_session_metadata()` 在 `637-694`。 |
| A4 SDK 已有 `Kernel.compact`，Conversation 与 normal turn 同 gate | 成立 | `kernel.py:1203-1222` 公开 compact；`conversation.py:210-224,278-288` 让 turn/compact 共用 `_turn_gate`。 |
| A5 runtime 先 plan/summary，后 append；summarizer 当前 fallback | 成立 | `runtime.py:1817-1921` 先 plan、await summarize、再 append；`summarizer.py:54-88` 对空/异常返回 fallback。 |
| A6 summarizer/prompt 是摘要输入单点 | 成立 | `summarizer.py:57-81` 构造 summary 输入并取 `get_compact_prompt()`；`prompts.py:124-150` 是 prompt/format 单点。 |
| A7 Web IM 原样发文本，已有 `/compact` warning | 成立 | `chat-api.ts:69-80` 只 POST `content`；`chat-workspace-page.tsx:773-793` 直接把 composer text 交给它；`i18n/zh.json:506-512` 含 `/compact` 提示。 |
| A8 `personal_assistant` 仅经 SDK、IM 不 import agent | 成立 | `SPEC.md:150-161` 是当前跨包硬规则；compose 从 `agent.sdk` 创建 Kernel，pipeline 不跨入 IM 内部。 |
| A9 external 入站先 shadow，再判断控制/normal；IM 不可达不阻塞飞书主回复 | 前半成立；控制确认的离线恢复断言不成立（R1-C3） | `inbound_pipeline.py:112-147,149-192` 在判断 `/stop` 前 sync user message；但 control reply 的离线行为见 R1-C3。 |
| A10 MENTION 下仅裸 `/stop` 是例外 | 成立 | `_should_process()` 的唯一裸例外是 `message.text.strip() == "/stop"`，见 `inbound_pipeline.py:232-251`；stop mention normalization 见 `253-281`。 |
| A11 coordinator 的 lock/FIFO 是控制操作应归属的原子域 | 成立 | `_transition` 在 `session_run_coordinator.py:1097-1124`；queue active/serialize 在 `run_queue.py:58-116,187-224`。 |
| A12 transcript 是 append-only；成功 compact 后才替换缓存 | 成立 | canonical `context-persistence.md:37-48`；实际 `runtime.py:1906-1922` 先 `append_compaction` 成功，再替换 history。 |
| A13 checkout 有用户 dirty 邻接文件 | 成立 | 本轮开始的 `git status --short --branch` 显示 `node-config.yaml`、`src/personal_assistant/gateway/composition.py` 已修改；未改动它们。 |
| A14 复用 `/stop` 窄解析点而不造 channel parser | 成立，方向合理 | 当前窄点只有 `_is_stop_command()`，`inbound_pipeline.py:131-147,253-281`；没有平行 adapter parser。 |
| A15 复用 coordinator 的 control reply/interruption/lock | 成立，但需补 reset-specific visibility rule（R1-C1） | `_deliver_control_reply()` 在 `session_run_coordinator.py:926-953`；`stop()` 的 atomic order 在 `242-288`。 |
| A16 binder 可承接受控 forced reset，coordinator 不应直碰 repository | 成立 | repository 仅由 binder 的 `resolve()` 调用 `bind()`，`session_binder.py:235-307`；coordinator 仅构造 `SessionBindingRequest`，`session_run_coordinator.py:676-703`。 |
| A17 focus 应沿 SDK → conversation → runtime → summarizer 下传，自动路径不带它 | 成立为可行路径 | manual entry 是 `runtime.py:294-304`，auto threshold/overflow 调用分别在 `loop.py:951-972`、`runtime.py:633-645`，均可保持无 focus。 |
| A18 命令可复用 external/IM 可见回复路径 | 在线时成立；不能据此推出离线 durable shadow（R1-C3） | compose 将 `bg_reply_sender` 注入 coordinator，`composition.py:457-485`；sender 同时 external send 与 IM send，`background.py:113-159`。 |
| A19 不复用 CLI session control | 成立且无反向依赖 | `SPEC.md:150-161` 禁止产品互相 import；本方案的实际生产入口已是 Gateway composition，而非 CLI。 |
| A20 不向 `InProcessKernelClient` 加实时聊天 compact | 成立 | 该 adapter 的 session open 依据 heartbeat/cron snapshot，`kernel_client.py:32-49,51-108`；实时聊天已直持 `kernel`，`composition.py:474-498`。 |
| A21 `feat-447` 的 external→IM shadow 是可复用现状 | 成立，但只能复用其已落盘的事实（R1-C3） | 历史 unit 存在于 `docs/changes/archive/feat-447-feishu-channel`；现行 saga 先 durable provider inbound，`shadow_saga.py:207-318`。 |
| A22 `feat-436`/`bugfix-471` 的 compaction/workspace 连续性是当前基础 | 成立 | 历史 unit 均已归档；current contract 仍规定 workspace-bound JSONL 与可恢复 compact，`context-persistence.md:14-39`。 |
| A23 CLI owner 收深不改变 Gateway owner | 成立 | 当前 Gateway owner 的 production composition 与 coordinator/binder 路径见 A1-A3；没有从 CLI import/复制实现。 |
| A24 Feishu listener lifecycle 与本项独立 | 成立 | `bugfix-496` 已归档；listener/channel 启动在 runtime `start_channels()`，`runtime.py:230-278`，会话控制只经 compose 注入的 pipeline/coordinator，`composition.py:474-510`。 |

#### 决策台账

| 决策 | 结论 | 本轮核实 |
|---|---|---|
| D1 精确文本命令在 shared inbound seam 解析 | 成立 | 与 A1/A10 一致；精确 grammar、保留 group gate、无 command framework 都有明确边界，`design.md:71-79`。 |
| D2 coordinator 负责 `/new` cancel/fence/ack，binder 负责 reset | 不成立（R1-C1、R1-C2） | ownership 正确，但现有 terminal delivery 在 reset 后没有 generation-aware final visibility check；replay 也只有 ack dedupe，不能保护 reset 操作本身。 |
| D3 idle-only `/compact`，无 binding no-op | 成立 | `run_queue.is_active()` 代表 queued/running，`run_queue.py:99-116,187-224`；同一 transition 下的 busy check 与 `ConversationSession` gate 闭合，`design.md:108-116`。 |
| D4 focus 走 SDK，manual strict failure、automatic unchanged | 成立为架构方向；canonical delta 分类不成立（R1-C5） | `runtime.py:1817-1921` 有清晰 summary-before-append seam，自动路径独立；但这改变了已有 manual compact 的 failure 语义。 |
| D5 文本优先、无 IM UI/API delta | 成立 | A7 已证实 UI 是通用 text POST；新行为可由 Gateway consumer contract 单点定义，`design.md:128-134`。 |

#### Spec 约束台账

| 原子 | 结论 | design 落点 / 核实 |
|---|---|---|
| S1 澄清：`/new` 留可读历史，只换后续 Agent context | 覆盖 | `design.md:83-89,106` 明确只换 binding、不删 transcript/time line。 |
| S2 澄清：支持 `/compact <关注点>` | 覆盖 | `design.md:73-79,118-126,190-195`。 |
| S3 内部 IM `/new` | 覆盖 | D2、`design.md:159-188`，但 R1-C1 阻断其运行中安全性。 |
| S4 飞书私聊 `/new` 与 shadow | 覆盖目标，R1-C3 阻断 IM 离线时的实现闭合 | `design.md:77,171-185,231-232`。 |
| S5 running `/new` 停止旧 run、无迟到回复 | 未覆盖到可实施的原子规则（R1-C1） | 只说复用 `/stop` terminal path，`design.md:83-87`；实际 race 路径不被 generation recheck 覆盖。 |
| S6 group 明确 @ 后 `/new` | 覆盖 | `design.md:75-77` 与 pipeline gate 一致；delta 合并仍须修 R1-C4。 |
| S7 bare `/compact` 延续关键工作 | 覆盖 | `design.md:108-116,190-195`。 |
| S8 focused `/compact` 保留重点 | 覆盖 | `design.md:118-126`，focus 不写 normal turn。 |
| S9 飞书 `/compact` 同步 shadow | 覆盖目标，R1-C3 阻断离线恢复 | `design.md:192-197,233-234`。 |
| S10 无历史 no-op、不创建空会话 | 覆盖 | `design.md:110-116,192-195`；binder lookup 是明确入口。 |
| S11 summary/persistence failure 不丢上下文 | 覆盖 | `design.md:120-126,208-210`；`append_compaction` 成功前不替换 cache 的现状可承载该规则。 |
| S12 busy `/compact` 不静默改写 | 覆盖 | `design.md:108-114,192-195`。 |
| S13 范围：两入口、文本命令、飞书 shadow、群 @ | 覆盖 | D1-D5 和两个 delta 已列出；R1-C3/C4 是未闭合部分。 |
| S14 非目标：不建新聊天窗口、不删可见历史 | 覆盖 | `design.md:83-89,106,128-134`。 |
| S15 非目标：不改自动策略、不加 `/reset` alias | 覆盖 | `design.md:75,122-124,210`。 |
| S16 非目标：不做恢复/选择历史会话 | 覆盖 | `design.md:89,213` 仅替换 binding，回退不改写档案。 |
| S17 非目标：不按用户拆群上下文、不建新群权限 | 覆盖 | `design.md:77` 与 `inbound_pipeline.py:232-251` 的按 group+agent gate 一致。 |
| S18 非目标：不增飞书原生 slash menu | 覆盖 | D1 的 plain-text parser 和 D5 的无 UI/API 结论没有扩张该面。 |

#### Delta-spec 台账

| 原子 | 结论 | 本轮核实 |
|---|---|---|
| gateway/external-channels ADDED 「飞书文本会话控制与 IM shadow 同义」 | 对外行为覆盖，但不能实现 offline shadow（R1-C3） | target current 已将 control confirmation 纳入外部可见事件，`external-channels.md:112-139`；delta 的 offline Scenario 在 `specs/gateway/external-channels.md:24-28`。 |
| gateway/routing-delivery ADDED `/new` 与 `/compact` | `/new`/compact 场景覆盖；group gate 的 ADDED 用法错误（R1-C4） | target current 的「控制命令」已是 group gate 条件，`routing-delivery.md:53-60`；delta 又声明裸 `/new`/`/compact` 不触发，`specs/gateway/routing-delivery.md:23-28,46-52`。 |
| kernel/context-persistence ADDED focused safe manual compact | focus 场景完整；只 ADDED 未锚定被改变的 existing manual contract（R1-C5） | target existing manual Scenario 是 `context-persistence.md:14-20`；delta 将 manual empty/error/persistence 改为失败，`specs/kernel/context-persistence.md:7-26`。 |

#### Milestone 台账

| Milestone | 结论 | 本轮核实 |
|---|---|---|
| M1 fresh-session | 垂直切片、两轨 exit 正确，但被 R1-C1/C2/C3/C4 阻断 | 它从 parser 到 binder/visible reply/E2E 都覆盖，`design.md:237-244`；应把 terminal-completion-vs-new、provider duplicate `/new`、IM-offline durable confirmation、canonical delta merge 加到范围与退出标准。 |
| M2 guided-compaction | 垂直切片、依赖 M1 合理；被 R1-C3/C5 阻断 | 内核 focus/strict failure 和 Gateway idle UX 共同交付，且没有横切拆分；但 external command confirmation 的 offline recovery 与 kernel MODIFIED delta 尚未闭合。 |

#### 架构进攻

| 角度 | 发现 | 结论 |
|---|---|---|
| 归属 | parser 放 shared inbound、并发与 reply 放 coordinator、binding/provenance 放 binder、summary 放 SDK/engine，符合 `SPEC.md:150-161` 的依赖方向。唯一错位是把 external control 的 durable shadow 当作已有 reply helper 能力：该 helper 是即时发送者，不是 saga owner。 | R1-C3；不改会让对 IM 离线的飞书控制结果没有可恢复事实，跨入口连续性只在在线时偶然成立。 |
| 该不该存在 | 不建 registry/plugin、也不加 IM UI，是合适的删除测试结果：三条命令共用一个资源域，直接复用窄 parser/coordinator 比再加框架更少状态。generation fence 和 typed requests 是必要的。 | 无新增 issue。为 replay 新增的最小 persistent operation identity 应复用已有 provider identity/saga 边界，而不是引入泛化 command framework（R1-C2）。 |
| 深浅 | `Kernel.compact(focus)` 把 focus 留在已有压缩深模块，屏蔽了 planner、transcript 和 summarizer 细节；比 Gateway 拼 summary 深。反之，「只给 ack 加 dedupe key」是浅处理：它没有抽象/封住同一 provider event 的 reset 副作用。 | R1-C2；不改，重复投递仍会产生多个 reset/new session，维护者需在 UI/回复层掩盖已经发生的状态错误。 |
| 治本还是补丁 | `/new` 不能只把 `/stop` 的中断顺序拼到 binder reset：已提交 terminal 的可见性是 coordinator 的独立竞争点。`_await_terminal_run()` 将 completed 当正常结果后仍送 final，而 reset generation 只在 queued submit 前复核。 | R1-C1；不改，用户先看到「新会话已开始」仍可能收到旧任务 final reply，破坏明确放弃边界。 |

### Issues

- [R1-C1][CRITICAL] [决策 2、`/new` 主流程、风险「旧排队输入跨越 `/new`」] `/new` 的 generation fence 只规定在 `_run_turn` 提交前复核（`design.md:83-89,159-188,208-209`），却没有规定 coordinator 在 reset publication 后如何屏蔽已经获得 completed terminal 的旧 run final reply。现行路径中 `stop()` 只记录 user-interrupt 后调用 Kernel（`session_run_coordinator.py:264-274`）；`_await_terminal_run()` 遇到 `completed` 仍返回正常结果（`961-1041`），随后 `_close_active_run()` 已移除 interrupt marker（`456-486,554-565`）才调用 `_deliver_final_reply()`。若 run 已提交 completed terminal、但 Gateway 仍在 observe/close window，`/new` 可以先确认新 binding，旧 final 随后仍发送。只说“沿用 `/stop` terminal path”不足以让 worker 选择正确屏蔽点。**不改，用户的明确放弃边界会出现旧任务迟到回复，直接违背 S5/M1-C3。**设计必须拍死同一 transition domain 中的 reset-generation/active-record 终态可见性规则：旧 generation 的 final 在发送前必须被拒绝（并保留正确 relay terminal outcome），而非仅在 Kernel submit 前检查 generation；同时写出 completed-terminal-vs-`/new` 的 race test。

- [R1-C2][CRITICAL] [决策 2、`/compact` 流程第 4 步、reply dedupe（`design.md:197`）] 方案只让 acknowledgement 的 dedupe key 使用 provider/message identity，没有定义控制**操作**的幂等边界。Feishu adapter 每次事件都会交给 inbound callback（`channels/feishu/adapter.py:371-397,399-446`）；external shadow saga 对重复 provider event 只复用 user anchor（`shadow_saga.py:224-248`），而 pipeline 在 `sync_user_message()` 返回后仍继续 command dispatch（`inbound_pipeline.py:112-147`）。当前 `_control_ack_from_session_id()` 也只是 reply identity（`session_run_coordinator.py:1203-1223`）。因此重复 `/new` 会再次 `reset`，甚至能在第一次 reset 后、用户下一条输入前后把 binding 换第二次；只压掉第二条 confirmation 不能撤销已发生的状态改变。**不改，provider 重试会制造额外 Kernel session，且可能将用户已经发送的下一条消息 supersede/drop，worker 无法从 ack 去重推导操作去重。**设计需指定在 command parse/coordinator 边界以 session key + stable inbound identity + command kind 线性化并持久复用一次 terminal operation outcome；复用现有 external provider identity/saga 是候选，但必须明确无 provider identity 的 IM relay 已有 adapter dedupe、focus 不能是 identity，并将重复 `/new` 与 repeated focused `/compact` 写入 M1/M2 tests。

- [R1-C3][CRITICAL] [决策 3、`/compact` 第 4 步、风险「外部 shadow/IM 离线」、external delta] 设计断言控制回复沿“既有 best-effort shadow / saga replay”恢复（`design.md:195,211`），但生产的 control path 没有把确认写入 saga。`build_bg_reply_sender()` 先把文本发给外部，随后 IM manager 不在线便直接 return（`runtime_delivery/background.py:113-159`）；它没有调用 `IMShadowConversationSync`。`recover_pending()` 只能重放先前被记录的 user anchors、bubble snapshots 和 agent outputs（`shadow_sync.py:421-477`），而 control path 没有创建其中任一 durable record。外部 delta 却承诺 IM 暂不可达时 shadow 会按恢复机制补齐（`specs/gateway/external-channels.md:24-28`）。**不改，飞书会收到 `/new`/`/compact` 结果，但其 IM shadow 永远缺少相同确认，跨入口连续性和 delta Scenario 都失败。**设计需明确一个最小的 control-output durable seam：以当前 saga/source identity 在外发前记录控制确认（不等待 IM），并由现有 recovery 重放到同一 shadow；需要规定其 idempotency、new/no-binding 时的 reply context、以及 M1/M2 的 IM-offline recovery tests。不能把即时 `bg_reply_sender` 当成该 durable owner。

- [R1-C4][CRITICAL] [gateway routing-delivery delta] `specs/gateway/routing-delivery.md` 只 ADDED 两个新 Requirement，却没有 MODIFIED 当前群聊门控 Requirement。canonical 现状把“控制命令”作为 MENTION gate 的例外（`docs/specs/gateway/routing-delivery.md:53-60`），而 proposed delta 又声明未 @ 的 `/new` 不切换、未 @ 的 `/compact` 不压缩（`docs/changes/feat-501-cross-channel-session-controls/specs/gateway/routing-delivery.md:23-28,46-52`）。归并后「control command」会同时可被读成 `/stop` only 或包括新命令，直接矛盾。**不改，worker/收尾归并者会得到两份相冲突的群聊触发契约，未 @ 的新命令可能被实现为例外。**请以 MODIFIED 精确锚定既有「群聊只在被 @提及 / 回复 Agent / 控制命令时触发 Agent」及其未 @ Scenario，保留 `/stop` 的唯一裸例外并写清 `/new`、`/compact` 不是该例外；新能力 Requirement 可继续 ADDED。

- [R1-C5][CRITICAL] [kernel context-persistence delta、决策 4] kernel delta 仅以 ADDED 写入「安全手动压缩」（`specs/kernel/context-persistence.md:5-26`），但设计实际改变了已存在的 `Kernel.compact` manual failure contract：当前 `Kernel.compact()` 对 executor 的结果直通（`agent/sdk/kernel.py:1203-1222`），summarizer 对 empty/error fallback 并继续 append（`summarizer.py:54-88`）；新方案要求任何 manual empty/error/persistence failure 以可辨识失败结束并不写入（`design.md:120-126,153-157,208-210`）。canonical 既有「手动触发压缩」Requirement/Scenario 正是此 public method 的原契约（`docs/specs/kernel/context-persistence.md:14-20`）。**不改，delta 归并会把一个改变既有 consumer 行为的规则伪装成平行新增，旧的 `None`=no-op 语义和新的 strict failure 的边界无法由后续维护者判定。**请 MODIFIED 精确锚定该 existing Requirement/Scenario：保留 `None` 仅指 planner 无窗口，明确 manual summary empty/error 与 `append_compaction` false/throw 都是可辨识失败且历史不变；focused capability 可作为同一 MODIFIED Requirement 的新增 Scenario 或另行 ADDED，但不得遗漏原 Scenario。

### Recommendations

- [R1-R1] 作者先修 D2：用一张 reset linearization 图或一段明确的不变量，分别定义 pre-reset queued、old active terminal、post-reset new input 和 reset failure 的 generation/visible-reply/lifecycle outcome；不要把 terminal safety 留给 worker 从 `/stop` 推断。
- [R1-R2] 为 control operation 指定一次性 identity 与 durable control-shadow record 的 owner/接口；明确外部 replay、IM relay replay、无 binding `/compact`、reset success/failure 的关联方式和恢复顺序。
- [R1-R3] 修正两份 delta 为精确 `MODIFIED` + 保留原 Scenario，再把 group bare-command 和 manual failure 的 canonical final text 与 design 用词对齐。
- [R1-R4] 更新 M1/M2 exit/tests：completed-terminal-vs-`/new`、duplicate Feishu `/new` 不再 reset、IM offline 后 reconnect/recovery 出现同一 control confirmation、manual `append_compaction` false 与 exception 都保持 pre-compact context。

### Author Resolutions

| Issue | Resolution | Changed design evidence |
|---|---|---|
| R1-C1 | accepted — `/new` 不再只在 submit 前检查 generation。新 binding 发布、generation 推进、old active reset-suppressed 标记为同一 transition 的线性化点；old terminal final 必须在同一 lock 领取可见性，reset 先线性化则只发 superseded lifecycle。candidate 失败不再先 interrupt old run。 | `design.md` 决策 2、状态图、`/new` 主流程、风险项与 M1-C3/C4。 |
| R1-C2 | accepted — 引入由已存在 source identity 派生的 persistent `ControlOperation`。binder/session-binding persistence 拥有 outcome；external saga id 或 Web relay idempotency key 是 operation source，focus 明确不是 identity。manual compact 以同一 opaque SDK key 重放，防止 append 后 crash 再压缩。 | `design.md` 决策 3/4、接口与 `/compact` 主流程、M1-C5、M2-C4/C5；三份 delta 增加 replay Scenario。 |
| R1-C3 | accepted — external control confirmation 在飞书 send 前写为 saga 的 `control` output，在线用 prepared-output mirror，离线由既有 recovery 补 user anchor 后重放。即时 bg sender 只保留 Web IM/无 saga 控制回复。 | `design.md` 决策 5、`/new` 与 `/compact` 主流程、风险/Runbook、M1-C2/C4、M2-C3/C5；external delta 的离线/重放 Scenario。 |
| R1-C4 | accepted — gateway routing delta 已将既有群聊门控 Requirement 改为完整 `MODIFIED`，保留原 scenarios，明确裸 `/stop` 是唯一例外，`/new`/`/compact` 必须明确指向 Agent。 | `specs/gateway/routing-delivery.md` 的 `MODIFIED Requirements`。 |
| R1-C5 | accepted — kernel context delta 已将既有「上下文压缩在长会话中保持可恢复」完整改为 `MODIFIED`，保留原 manual/window/workspace scenarios，并新增 focus、strict manual failure 和 idempotency scenarios。 | `specs/kernel/context-persistence.md` 的 `MODIFIED Requirements`；`design.md` 决策 4。 |

## Round 2

### Metadata

- reviewer: `/root/design_review`
- review_mode: `full`
- mode_reason: `R1 后不仅补了措辞或测试证据：决策 2 新增 reset 终态可见性线性化，决策 3 引入跨重启的 ControlOperation，决策 5 新增 saga durable output，SDK 公共 compact 契约、三份 delta 与两条 milestone 都改变了。它们跨 Gateway persistence、external shadow、流式投递与 Kernel，必须重建全部台账并重跑四角度进攻。`
- started_at: `2026-08-05T01:53:15+08:00`
- completed_at: `2026-08-05T01:58:28+08:00`
- duration: `5m 13s`

### Verdict

Issues Found — 2 CRITICAL / 0 WARNING

R1 的五个原始缺口都已被正确地拍死：`/new` terminal final、操作而非 ack 幂等、offline shadow 的目标 owner，以及两份 canonical delta 的 `MODIFIED` 用法均已修正。可是本轮新增的持久化和可见性边界没有完整闭合：control outcome 落到 session-binding SQLite 后、saga output 尚未生成时的崩溃无法由任何现有 recovery 找回；同时 `/new` 的 generation fence 仍只围住 coordinator terminal final，绕过它的实时 streaming/external mirror 可在新会话确认之后抵达用户。两者都会直接破坏已写入的跨入口与放弃边界，不能通过 Gate 2。

### Coverage

完整重读 `spec.md`、本轮 `design.md`、R1 与 Author Resolutions、三个 delta-spec，以及 canonical `gateway/{routing-delivery,external-channels}`、`kernel/context-persistence`、`SPEC.md`。生产追踪重新从 `composition.py:240-248,390-405,435-498` 进入 `InboundDispatcher._run_root()` → `InboundPipeline.handle_inbound()` → `SessionRunCoordinator` → `GatewaySessionBinder` / `PersistentSessionBindingStore` → `agent.sdk.Kernel` / `ConversationSession` / `AgentEngine`；也复核了 Web relay 的 durable idempotency、Feishu shadow saga/output recovery、实时 observer/task tracker 和 Kernel manual compaction。以下为本轮完整 inventory，不把 R1 的结论当作未经复核的前提。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | reset publication、generation 与 reset-suppressed 线性化；terminal final 在同一 transition lock 领取可见性 | `design.md:85-93,217-224,235-236` 规定 old final 与 `/new` 不交错，且 M1-C3/C4 覆盖 completed-terminal 两种锁顺序。它闭合了 R1 所指的 coordinator terminal-final race；但实时 output 旁路另见 R2-C2。 | closed |
| R1-C2 | 按 source identity 的 persistent `ControlOperation`，并将同一 id 透传给 manual compact | `design.md:114-124,165-177` 的 key、outcome、first-claim 和 core idempotency 边界与 Web relay 的 durable key（`web_relay_adapter.py:213-240,307-335`）及 external saga identity（`shadow_saga.py:224-318`）对齐；M1-C5/M2-C4/C5 已要求重放测试。 | closed |
| R1-C3 | control confirmation 先成为 saga durable output，offline 后由 recovery 写入 shadow | `design.md:136-144` 已不再把 `bg_reply_sender` 当 durable owner，并准确复用 `IMShadowConversationSync.prepare_agent_output()` / `recover_pending()` 的 output row 语义（`shadow_sync.py:244-264,421-477`）。目标 owner 正确；跨 store 崩溃交接另见 R2-C1。 | closed |
| R1-C4 | routing delta 完整 MODIFIED group gate，并保留既有 scenarios | delta 精确修改 `群聊只在被 @提及 / 回复 Agent / 控制命令时触发 Agent`，`/stop` 是唯一裸例外，`/new`/`/compact` 必须 mention/reply（`specs/gateway/routing-delivery.md:59-80`），与 canonical target 同一 Requirement 对齐。 | closed |
| R1-C5 | kernel delta 完整 MODIFIED 既有 manual compact contract | delta 保留 existing manual/window/workspace scenarios，并把 focus、idempotency 与 strict manual failure 纳入同一 Requirement（`specs/kernel/context-persistence.md:5-51`）；`None` 与 error 的分界同 `design.md:126-132,173-177` 一致。 | closed |

### 完整核实台账

#### 现状断言

| 原子 | 结论 | 本轮实际证据 |
|---|---|---|
| A1 shared inbound 是唯一文本入口 | 成立 | production composition 构造单一 `InboundPipeline`/`InboundDispatcher`（`composition.py:474-498`）；pipeline 在 route、group gate、shadow 后才分 `/stop`/normal（`inbound_pipeline.py:102-147`）。 |
| A2 coordinator 是 run/control transition owner | 成立 | normal submit 和 active marker 在同一 transition 内（`session_run_coordinator.py:380-432`），`stop()` 同样使用该锁（`242-295`）。 |
| A3 binder/store 是 binding 与 reply context owner | 成立 | binder 是唯一 resolve/bind seam；生产注入 `PersistentSessionBindingStore`（`composition.py:240-247`），store bind 是 session-key upsert（`session_keys.py:537-611`）。 |
| A4 external saga 是 source anchor/output 的 durable owner | 成立 | saga 先持久 provider identity（`shadow_saga.py:224-318`）；output table 以 saga/run/kind/ordinal 去重（`99-111,428-485`）。 |
| A5 `Kernel.compact` 是 manual compact 的 SDK seam | 成立 | public method 直接进入 ConversationSession executor（`kernel.py:1203-1222`），Conversation 的 compact 与 turn 同 gate（`conversation.py:278-288`）。 |
| A6 current manual summary 是 plan → summarize → append | 成立 | runtime 先 plan/summary 后 `append_compaction`，commit 后才改 history（`runtime.py:1817-1922`）。 |
| A7 current summarizer fallback 适用于 manual/auto | 成立 | empty/error 均返回 fallback（`summarizer.py:54-88`），所以 strict manual 分支确需显式分流。 |
| A8 Web IM 已带 stable ingress identity | 成立 | relay payload 强制 `relay_task_id`/`idempotency_key`，并持久去重后才 callback（`web_relay_adapter.py:213-240,307-344`）。 |
| A9 package dependency red lines | 成立 | `SPEC.md:150-161` 仍要求 personal_assistant 只经 SDK、IM 不 import agent；设计未反转依赖。 |
| A10 external user anchor 在 control 前处理且 IM 不能阻塞主链 | 成立 | pipeline 先 `_sync_external_shadow_message()`（`inbound_pipeline.py:112-172`）；saga 在 IM 请求前持久（`shadow_sync.py:107-123`）。 |
| A11 MENTION 的唯一裸 control exception 是 `/stop` | 成立 | `_should_process()` 只特判裸 `/stop`（`inbound_pipeline.py:232-251`）。 |
| A12 coordinator lock/FIFO 是正确的操作域 | 成立 | `_transition()` 是 per-session lock（`session_run_coordinator.py:1097-1124`）；queue 的 active/serialize state 在 `run_queue.py:58-116,187-224`。 |
| A13 transcript 与 visible history 的不变量 | 成立 | canonical kernel contract 是 append-only JSONL（`context-persistence.md:37-53`）；design 只换 binding（`design.md:85-93`）。 |
| A14 精确 parser 是最窄可复用点 | 成立 | 当前 `_is_stop_command()` 已在 pipeline 的 shared gate 后规范化 mention（`inbound_pipeline.py:253-281`）。 |
| A15 coordinator 的 terminal path 不是唯一可见输出路径 | 成立，且暴露 R2-C2 | `_await_terminal_run()` 对每个 `assistant_message` 调 observer（`session_run_coordinator.py:1000-1020`）；observer 可脱离 coordinator 发 streaming delta/external mirror（`runtime_delivery/observer.py:254-296,1127-1157`）。 |
| A16 binder 不能被 coordinator 绕过 | 成立 | current repository access 已封在 binder/store 组合，设计的 reset 保持同一归属（`design.md:89-93,167-171`）。 |
| A17 focus 的自然路径是 SDK → engine → summarizer | 成立 | public SDK、Conversation 和 engine compact 链已连通（`kernel.py:1203-1222`、`conversation.py:278-286`、`runtime.py:294-304`）；Gateway 无需拼摘要。 |
| A18 realtime delivery 有独立 task owner | 成立，且暴露 R2-C2 | `RuntimeDeliveryTaskTracker.start()` 建 detached task（`task_tracker.py:20-51`），不属于 coordinator transition lock。 |
| A19 CLI 与 `InProcessKernelClient` 不在实时聊天链 | 成立 | realtime compose 直接把 `kernel` 注入 coordinator（`composition.py:474-490`）；`kernel_client.py:32-108` 是 heartbeat/cron adapter。 |
| A20 saga recovery 只扫描 saga 自己的 row | 成立，且暴露 R2-C1 | `recover_pending()` 仅遍历 `recovery_sagas()`、snapshots、`pending_outputs()`（`shadow_sync.py:421-477`），没有读取 session-binding store。 |
| A21 binding 与 saga 是两份独立 SQLite durability domain | 成立，且暴露 R2-C1 | composition 分别创建 `session_bindings.sqlite3` 与 `external_shadow_sagas.sqlite3`（`composition.py:240-248,390-405`）；store 的 `BEGIN IMMEDIATE` 只覆盖自身 connection（`session_keys.py:656-696`）。 |
| A22 historical shadow/recovery 基础可复用 | 成立 | current `prepare_agent_output()` 和 output replay 完整存在（`shadow_sync.py:244-264,421-477`），但不自动覆盖另一 store 的未物化 outcome。 |
| A23 historical compaction/workspace basis 未被越界改变 | 成立 | new delta 保留 workspace/manual/window scenarios（`specs/kernel/context-persistence.md:11-51`），design 保持 auto 无 focus（`130-132`）。 |
| A24 CLI ownership history 不改变 Gateway owner | 成立 | 设计仅以 product meaning 借鉴 CLI，实际调用仍在 Gateway composition/coordinator/binder（`design.md:39-40,51-67`）。 |
| A25 listener lifecycle 与本项独立 | 成立 | command changes 位于 pipeline/coordinator/binder/SDK，不改变 channel listener composition（`composition.py:491-509`）。 |
| A26 dirty adjacent composition must remain out of this unit | 成立 | 本轮 scoped status 仍显示 `src/personal_assistant/gateway/composition.py` 为既有修改；本 review 只追加 review artifact，未改代码。 |

#### 决策

| 决策 | 结论 | 本轮核实 |
|---|---|---|
| D1 shared seam 精确解析 | 成立 | grammar、mention normalization、无 plugin framework 与 A1/A11/A14 一致（`design.md:73-81`）。 |
| D2 `/new` coordinator linearization + binder reset | terminal-final 部分成立；流式可见性仍不完整（R2-C2） | reset publication/generation/final claim 明确（`design.md:83-110`），但 observer 不经这一 claim（A15/A18）。 |
| D3 persistent operation outcome + idle-only compact | operation 幂等成立；跨 store delivery handoff 不完整（R2-C1） | identity/key/idle branches 可实施（`design.md:112-124`）；outcome 后的 saga row 没有 durable handoff。 |
| D4 SDK focus/idempotency + strict manual failure | 成立 | public boundary、manual-only strictness、auto unchanged 与 current plan-before-append seam 自洽（`design.md:126-134,173-177`）。 |
| D5 saga durable control output | owner 与 online/offline recovery方向成立；崩溃窗口不闭合（R2-C1） | output row、caller key、no IM wait 都明确（`design.md:136-144`），但不是与 operation commit 同一 transaction。 |
| D6 text-first/no IM delta | 成立 | existing composer/relay 已发送原始 text，Gateway/SDK delta 是最窄 canonical owner（`design.md:146-152`）。 |

#### Spec 约束

| 原子 | 结论 | design 落点 / 核实 |
|---|---|---|
| S1 `/new` 保留可读历史，仅换后续 context | 覆盖 | D2 明示旧 transcript/history 不删除（`design.md:89-93,110`）。 |
| S2 支持 `/compact <focus>` | 覆盖 | D1/D4 和 SDK signature（`75-79,126-132,173-177`）。 |
| S3 内部 IM `/new` | 覆盖 | `/new` flow 与 M1-C1（`179-217,271-272`）。 |
| S4 飞书私聊 `/new` 与 shadow | 覆盖目标，但 R2-C1 阻断 restart 后确认 | D5 与 M1-C2（`136-144,271-272`）。 |
| S5 running `/new` 无迟到旧回复 | 未完整覆盖（R2-C2） | terminal direct reply 已围栏，streaming/external mirror 仍绕过。 |
| S6 群聊明确 @ 后 `/new` | 覆盖 | D1 和 routing delta MODIFIED scenario（`75-81`; delta `75-80`）。 |
| S7 bare `/compact` 连续工作 | 覆盖 | D3 idle branch（`120-124,219-224`）。 |
| S8 focused `/compact` 保留重点 | 覆盖 | D4 focus only changes summarized window（`126-134`）。 |
| S9 飞书 `/compact` 同步 shadow | 覆盖目标，但 R2-C1 阻断 restart 后确认 | D5、M2-C1/C3（`136-144,273`）。 |
| S10 无历史 no-op、不创建空会话 | 覆盖 | explicit no-binding result（`120-124,221-224`）。 |
| S11 summary/persistence failure 不丢 context | 覆盖 | strict manual no-append rule和 kernel MODIFIED scenario（`130-132`; delta `21-25`）。 |
| S12 busy `/compact` 不静默改写 | 覆盖 | transition/queue busy outcome 规则明确（`120-122,221-224`）。 |
| S13 范围：两个入口、文本、shadow、群 @ | 覆盖，但 external restart handoff 留 R2-C1 | D1-D6、三份 delta 覆盖对应 consumer faces。 |
| S14 不建新窗口/不删历史 | 覆盖 | D2/D6 不创建 UI 或删除 transcript。 |
| S15 不改 auto policy、不加 alias | 覆盖 | exact grammar 与 auto no-focus 均明确（`75-81,130-132`）。 |
| S16 不做恢复/选择历史会话 | 覆盖 | reset 只建立 fresh binding，不提供旧 session selector（`89-93`）。 |
| S17 不按用户拆分群 context/权限 | 覆盖 | session key 与 group gate 没有 per-user 分支（`79,120-124`）。 |
| S18 不增飞书 slash menu | 覆盖 | shared plain-text parser，未改 adapter UI（`73-81,146-152`）。 |

#### Delta-spec

| 原子 | 结论 | 本轮核实 |
|---|---|---|
| gateway external `MODIFIED` control/background requirement | 分类与消费者场景正确；restart confirmation handoff 被 R2-C1 阻断 | 精确扩展既有 control confirmation，而非造平行 Requirement（`specs/gateway/external-channels.md:5-47`）。 |
| gateway routing `ADDED` new/compact + `MODIFIED` group gate | 成立 | new capabilities 是平行新增；既有 gate 正确完整 MODIFIED 且保留 scenarios（`specs/gateway/routing-delivery.md:5-80`）。 |
| kernel context `MODIFIED` long-session compaction | 成立 | existing manual Scenario 未丢，new strict/idempotent scenarios 是其同一 public contract 的增量（`specs/kernel/context-persistence.md:5-51`）。 |

#### Milestone

| Milestone | 结论 | 本轮核实 |
|---|---|---|
| M1 fresh-session | 垂直切片、串行拆分理由充分；被 R2-C1/C2 阻断 | parser → reset → confirmation → external shadow → real context test 形成完整用户价值（`design.md:267-272`）；需补 outcome-commit-before-output restart 与 old streaming/output-after-new tests。 |
| M2 guided-compaction | 垂直切片、正确依赖 M1；被 R2-C1 阻断 external confirmation delivery | SDK focus/strict failure 和 Gateway visible result 同 slice（`design.md:267-273`）；需补 compact outcome commit-before-output restart/recovery test。 |

### 架构进攻

| 角度 | 主动检验 | 结论 |
|---|---|---|
| 归属 | parser 在 pipeline、session transition 在 coordinator、binding/operation outcome 在 binder/store、summary 在 SDK/core、shadow output 在 saga，均符合包依赖和数据归属。可见 delivery 则不是 coordinator 独占，现有 observer/task tracker 也是 owner。 | D2 没有把 streaming owner 纳入 generation fence（R2-C2）；不改会让同一 run 的不同用户可见出口拥有相互矛盾的 reset 语义。 |
| 该不该存在 | `ControlOperation` 是外部 at-least-once 与 manual compact exactly-once 所必需的最小状态；复用 saga output 也比新增 command framework/outbox service 更小。 | 不需新 framework；但两个 SQLite owner 之间必须有一个最小 durable handoff/outbox，不是把“重放入站消息”误当成恢复机制（R2-C1）。 |
| 深浅 | `Kernel.compact(focus, idempotency_key)` 吸收压缩细节，是深接口。相反，只在 `_deliver_final_reply()` 加 generation check，没有封住 observer 已排队的 message delta/external mirror。 | R2-C2；不改，维护者要在每一种 transport 的末端临时补 suppress，认知和回归面都会随新输出类型增长。 |
| 治本还是补丁 | D5 把 IM offline 的 durable truth 放回 saga，是治本；但 `ControlOperation` committed 后另一步才写 saga output，进程崩溃时两边都不会自动补齐。 | R2-C1；不改，状态已改变却没有确认的失联窗口只能碰运气等 provider replay，违背 restart recovery 目标。 |

### Issues

- [R2-C1][CRITICAL] [决策 3 / 决策 5、`/new`/`/compact` 主流程、M1-C4/C5、M2-C5] ControlOperation 与 binding 被设计为同一次 `PersistentSessionBindingStore` 提交（`design.md:93,118,165-171,217`），而 control output 要在其后才写入另一份 `ExternalShadowSagaStore`（`design.md:138-144,209-212,224`）。生产中这两者确是 `session_bindings.sqlite3` 与 `external_shadow_sagas.sqlite3` 两个独立 durability domain（`composition.py:240-248,390-405`）；现有 `recover_pending()` 只扫描 saga 自己已存在的 anchor/output row（`shadow_sync.py:421-477`），不可能发现「binding/outcome 已提交、但进程在 `prepare_output()` 前退出」的命令。provider 未再投递时，Gateway restart 不会补飞书确认或 IM shadow confirmation。**不改，用户的 `/new` 或 `/compact` 已实际改变会话/上下文却可能永远得不到结果，M1/M2 的 external restart/offline 约束和 external delta replay Scenario 都无法成立。**设计必须指定一个 durable handoff：例如 operation owner 同事务写 pending control-delivery intent，启动/reconnect recovery 从该 intent 以 saga/op id 幂等 materialize output；或明确另一种先后顺序及其无丢失恢复 owner。仅要求“同一 inbound 重放”不够。并把 `outcome committed → process exit before saga output → no inbound replay → reconnect/restart` 加入 M1 与 M2 的退出测试。

- [R2-C2][CRITICAL] [决策 2、风险「旧排队输入或已完成终态跨越 `/new`」、M1-C3/C4] D2 已为 coordinator 的 terminal `_deliver_final_reply()` 建立正确的 final-visibility claim（`design.md:85-93`），但它没有围住真实运行的其他用户可见输出。当前 `_await_terminal_run()` 会把每条 `assistant_message` 交给 `_kernel_event_observer`（`session_run_coordinator.py:1000-1020`）；observer 可直接向 external sender 投递（`runtime_delivery/observer.py:254-296`）或交给 detached `RuntimeDeliveryTaskTracker` 发 IM `message_delta`（`1127-1157`，`task_tracker.py:20-51`）。这些任务不取得 coordinator transition lock，也不在发送前复核 handle generation/reset-suppressed。更窄的是，D2 的顺序本身先 publish new binding/generation、再 interrupt old Kernel run（`design.md:89-91`）；`RunController.publish_if_active()` 只在 `Kernel.interrupt()` 后才禁止新的 assistant event（`run_control.py:79-94`），已经排队的 transport task 仍可在“新会话已开始”确认之后到达。**不改，M1-C3 的“无迟到旧 reply”只对一条 terminal path 成立，旧 run 的 streaming bubble 或 Feishu mirror 仍会晚于 `/new` confirmation，用户的明确放弃边界被破坏。**设计需要把 generation/reset-suppressed 变成所有 old-run user-visible delivery 的共同 visibility lease（含 IM streaming/provisional bubble 与 external mirror），并规定 reset 如何取消/收敛已排队但尚未投递的 old output，而非只在 terminal final 处判断；M1 要分别覆盖 event-before-reset/delivery-after-reset、event-after-reset、以及 Feishu mirror 三种竞态。

### Recommendations

- [R2-R1] 作者先为 R2-C1 选择唯一的 control-delivery recovery handoff，并在 D3/D5、两条 flow、风险段和 M1/M2 退出标准写出其 source id、pending/completed 状态与 restart scanner；保持 saga 为 shadow owner，不引入泛化 command system。
- [R2-R2] 为 R2-C2 将“final visibility”改为“all user-visible old-run delivery visibility”，明确 observer/streaming/external mirror 同 Coordinator generation 的接口边界及 reset 后 provisional bubble 的收敛结果。
- [R2-R3] 两项修订完成后再做 Round 3 full review：R2-C1/C2 都改变了 persistence/recovery 与可见性主链，不能以 closure 轮次替代。

### Author Resolutions after Round 2

| Issue | Resolution | Changed design evidence |
|---|---|---|
| R2-C1 | accepted — external control 的 `ControlOperation` outcome 与 `PendingExternalControlDelivery(saga_id, operation_id)` 现在在同一 binder-store transaction 提交。materializer 在当前请求、external-ready startup 和 IM reconnect 先扫描 intent，再以 `(saga_id, operation_id)` 幂等 materialize saga control output、外发飞书并交给既有 shadow recovery；`materialized`/`outbound_handed_off` 明确重试边界，provider 保持已有 at-least-once 语义。 | `design.md` 决策 3/5、typed data flow、两条 command flow、风险/Runbook、M1-C5、M2-C5；external delta 新增 crash-without-replay Scenario。 |
| R2-C2 | accepted — generation fence 扩为 `RunDeliveryContextStore` 的 `RunVisibilityLease`：observer、detached IM task、terminal final 和 external mirror 在持久化/排队/外发前统一申请 permit。`/new` 先 quiesce 并 settle old permits，再将 binding/outcome/pending intent/`superseded_run_id` 同次持久发布，随后 commit discard provisional/pending output；publish 失败 restore old visibility。recovery 从同一 durable fact 过滤 old saga output，故 restart 后也不复活旧文本。 | `design.md` 决策 2、typed data flow、`/new` sequence、routing delta running Scenario、风险/Runbook、M1-C3/C4。 |

## Round 3

### Metadata

- reviewer: `/root/design_review`
- review_mode: `full`
- mode_reason: `R2-C1/C2 的修订同时改动跨 SQLite recovery、启动/reconnect materializer、所有可见输出的撤销协议和 M1/M2 exit criteria；共享契约与失败顺序均已改变，不能继承 R2 的台账。`
- started_at: `2026-08-05T02:35:52+08:00`
- completed_at: `2026-08-05T02:40:05+08:00`
- duration: `4m 13s`

### Verdict

Issues Found — 1 CRITICAL / 0 WARNING

R2-C1 的 durable handoff 已形成正确的单向恢复链：outcome/intent 同 binder transaction，materializer 再写 saga，router handoff 后明确采用 provider at-least-once。R2-C2 也把所有生产输出入口纳入同一 lease，并用 durable `superseded_run_id` 补上 restart recovery。仍有一个会使失败 `/new` 丢失旧 run 已产生但尚未取得 permit 的可见输出的反向分支；因此“失败不等于隐形 `/stop`”尚不能成立，不能通过 Gate 2。

### Coverage

完整重读并逐项核对 `spec.md`、`design.md`、三个 delta-spec、当前 `docs/specs/gateway/{routing-delivery,external-channels}.md`、`docs/specs/kernel/context-persistence.md` 与 `SPEC.md`。从真实生产组装重新追踪 `composition.py:240-248,390-405,428-524` → `InboundPipeline.handle_inbound()` → `SessionRunCoordinator` → `GatewaySessionBinder` / `agent.sdk.Kernel`，以及 observer、detached task、external saga、router、IM reconnect recovery 路径；没有将 design 中的拟议接口当作现状证据。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | terminal final 在同一 transition/lease 下复核 | `design.md:85-97,204-251` 要求 terminal 在短临界区 claim permit；`session_run_coordinator.py:450-486,961-1041` 证明这是当前 final race 的真实落点。 | closed |
| R1-C2 | `ControlOperation` 与 Kernel manual idempotency key | `design.md:118-132,173-181` 的 identity/outcome 和 `web_relay_adapter.py:213-240,307-335`、external saga identity 一致；M1-C5/M2-C4 覆盖 replay。 | closed |
| R1-C3 | 外部 control confirmation 改由 saga durable output/recovery owner 负责 | `design.md:144-152,192-196` 对准 `shadow_sync.py:244-264,421-477` 的 output/recovery owner，而不是即时 `bg_reply_sender`。 | closed |
| R1-C4 | routing delta MODIFIED group gate 且保留 scenarios | `specs/gateway/routing-delivery.md:60-90` 精确保留裸 `/stop`，并限制 `/new`/`/compact`。 | closed |
| R1-C5 | kernel delta MODIFIED existing manual compact contract | `specs/kernel/context-persistence.md:7-51` 保留现有 manual/window/workspace behavior，并增加 focus/idempotency/strict failure。 | closed |
| R2-C1 | outcome 与 `PendingExternalControlDelivery` 同 binder transaction，materializer 在 current request/startup/reconnect drain | `design.md:120-126,144-152,181,242-258` 明确 `(saga_id, operation_id)`、`materialized`/`outbound_handed_off` 和 no-replay recovery；external delta `49-54`、M1-C5/M2-C5 覆盖该 crash。两个 SQLite store 确实独立（`composition.py:240-248,390-405`），而现有 saga recovery 只扫 saga rows（`shadow_sync.py:421-477`），故这一新增 handoff 正是必要且足够的 owner。 | closed |
| R2-C2 | `RunVisibilityLease` 覆盖 observer/task tracker/terminal/external mirror，binding transaction 写 durable supersession | `design.md:85-97,183-190,231-249` 明确所有出口、quiesce→publish→commit 顺序；当前旁路实证是 observer external send/task tracker（`runtime_delivery/observer.py:254-296,1127-1157`）和 terminal route（`session_run_coordinator.py:480-648`）。成功 reset/restart 的迟到旧文本边界已闭合；publish-failure reverse path 见 R3-C1。 | closed with follow-up |

### 完整核实台账

#### 现状断言

| 原子 | 结论 | 本轮实际证据 |
|---|---|---|
| A1 shared inbound 是两类聊天文本的唯一产品入口 | 成立 | composition 构造单一 pipeline/dispatcher（`composition.py:474-498`）；pipeline 先 route、gate、shadow，再分 control/normal（`inbound_pipeline.py:102-147`）。 |
| A2 coordinator 是 session transition owner | 成立 | normal submit/active marker 同锁（`session_run_coordinator.py:380-432`），active close 与 stop 也经 `_transition()`（`554-565,1097-1124`）。 |
| A3 binder/store 是 binding、reply context、runtime/provenance owner | 成立 | production 注入 `PersistentSessionBindingStore` 给 binder（`composition.py:240-247`）；store 的 bind/upsert 在 `session_keys.py:537-611`。 |
| A4 external saga 是 provider source/IM shadow output 的 durable owner | 成立 | saga 在 IM I/O 前持久化 provider fact（`shadow_sync.py:107-123`）；output 以 saga/run/kind/ordinal identity 落盘（`shadow_saga.py:428-485`）。 |
| A5 现有 control reply 不是 durable shadow owner | 成立 | coordinator control reply 直接走 current sender/router（`session_run_coordinator.py:900-953`）；而 saga recovery 只扫描其 own rows（`shadow_sync.py:421-477`）。 |
| A6 `Kernel.compact` 与 normal turn 同 conversation gate | 成立 | SDK public seam 是 `kernel.py:1203-1222`；Conversation compact 复用 turn gate（`conversation.py:278-288`）。 |
| A7 manual compact 的可安全失败窗口存在 | 成立 | runtime 是 plan → summarize → append，append 成功后才更新 live history（`agent/core/agent/runtime.py:1817-1922`）。 |
| A8 Web relay 有稳定 durable ingress identity | 成立 | relay adapter 在 callback 前持久去重（`web_relay_adapter.py:213-240`），并将 relay id/key 带入 runtime protocol（`307-335`）。 |
| A9 external inbound 先 durable saga/shadow 尝试，再作 command 判定 | 成立 | pipeline 在 route/gate 后调用 shadow sync（`inbound_pipeline.py:112-129,149-192`）；IM 不可达时仍带回 `shadow_saga_id`（`159-172`）。 |
| A10 MENTION 下裸 `/stop` 是唯一例外 | 成立 | `_should_process()` 仅特判精确 `/stop`（`inbound_pipeline.py:232-251`）。 |
| A11 streaming、detached IM 与 external mirror 不在现有 terminal lock 内 | 成立 | observer 直接 external send/创建 detached task（`runtime_delivery/observer.py:254-296,1127-1157`）；tracker 目前只持全局 task 集（`task_tracker.py:13-51`）。 |
| A12 completed terminal 当前会在 observer 后走 final router | 成立 | stream 对每条 `assistant_message` 调 observer（`session_run_coordinator.py:1000-1020`），完成后 `_deliver_final_reply()` 发送（`450-506,599-648`）。 |
| A13 current router only has process-local dedupe | 成立 | `OutboundRouter` 发送后才记内存 key（`outbound_router.py:20-56`）；这不能取代 durable operation/intent，但与 design 声明的 at-least-once boundary 一致。 |
| A14 session binding 与 saga 是独立 SQLite durability domains | 成立 | composition 分别建 `session_bindings.sqlite3`、`external_shadow_sagas.sqlite3`（`240-248,390-405`）；store transaction 是单 connection `BEGIN IMMEDIATE`（`session_keys.py:656-696`）。 |
| A15 existing IM recovery 是 post-register owner | 成立 | `ConnectionReadyCoordinator.on_connected()` 调度 shadow recovery（`connection_ready.py:69-114`），compose 将 `shadow_sync.recover_pending` 注入（`composition.py:512-524,582`）。 |
| A16 Gateway 启动先启动 channels，IM connection 可随后重连 | 成立 | runtime 在 `start_channels()` 后才进入 IM supervised loop（`runtime.py:277-302`）；因此 external-ready startup 不能仅依赖一次 inbound replay。 |
| A17 package dependency red lines 未变 | 成立 | `SPEC.md:150-161` 要求 personal_assistant 仅经 `agent.sdk`，IM 不 import agent；design 的 materializer 留在 Gateway composition。 |
| A18 dirty 邻接文件必须保留 | 成立 | 本轮 status 仍显示 `node-config.yaml`、`composition.py` 等用户修改；本 review 只追加本 artifact。 |
| A19 当前 parser/reply/SDK seams 可复用，不需新 command framework、IM API 或 CLI adapter | 成立 | parser 的 `/stop` normalization 在 `inbound_pipeline.py:253-281`，composer relay 保持文本协议（`web_relay_adapter.py:246-335`），实时聊天 compose 直接持 Kernel（`composition.py:474-490`）。 |
| A20 历史 external recovery / compaction / listener 结论没有改变 owner | 成立 | current source 仍分别由 saga recovery、SDK compact 与 channel bootstrap owner 承担（`shadow_sync.py:421-477`、`kernel.py:1203-1222`、`gateway/bootstrap.py:67-87`）。 |

#### 决策

| 决策 | 结论 | 本轮核实 |
|---|---|---|
| D1 shared seam 的三个精确命令 | 成立 | grammar、mention normalization、plain-text-only 与 group gate 均明确（`design.md:73-81`），且是 A1/A10/A19 的最窄延伸。 |
| D2 `/new` 线性化与 all-output lease | 部分成立；publish failure 反向分支缺口见 R3-C1 | 成功路径的 quiesce→binder transaction→commit、terminal lock、durable recovery filter 均明确（`85-99,183-190,231-251`）；但 `91,95` 的“立即拒绝 permit”与 restore 不能恢复已拒绝 output 冲突。 |
| D3 persistent control outcome + idle-only compact | 成立 | source identity、ledger、busy/no-op、core idempotency 形成清晰唯一边界（`118-132,173-181,253-258`）。 |
| D4 SDK focus/idempotency + strict manual failure | 成立 | public signature、manual-only strict branch 和 auto unchanged 互不矛盾，并利用 A6/A7 的真实 seam（`134-142,198-202`）。 |
| D5 binder intent → saga control output → router/IM shadow | 成立 | materialize before router，router success 后 handoff，IM 为 saga recovery owner，provider exactly-once 未被伪造（`144-152,192-196`）。 |
| D6 text-first/no IM delta | 成立 | 行为由 Gateway/SDK delta 单点表达，未增加 IM endpoint/visual state（`154-160,260-265`）。 |

#### Spec 约束

| 原子 | 结论 | design 落点 / 核实 |
|---|---|---|
| S1 澄清：`/new` 留可读历史，只切换后续 context | 覆盖 | binding replacement 不删 transcript/history（`design.md:87-99`）。 |
| S2 澄清：支持 `/compact <focus>` | 覆盖 | exact parser 和 SDK focus chain（`75-79,134-142,198-202`）。 |
| S3 内部 IM `/new` | 覆盖 | `/new` flow、routing delta、M1-C1（`204-251,293-294,306`）。 |
| S4 飞书私聊 `/new` 与 shadow | 覆盖 | intent/materializer/recovery 与 M1-C2（`144-152,242-247,294,306`）。 |
| S5 running `/new` 后无旧回复 | 成功 reset/restart 覆盖；failure rollback 被 R3-C1 阻断 | all-output lease/M1-C3 已覆盖成功切换（`85-97,269,306`），但 failed publish 能丢 old output。 |
| S6 群聊明确 @ 后 `/new` | 覆盖 | D1 与 routing MODIFIED scenario（`75-81`; delta `76-81`）。 |
| S7 bare `/compact` 连续当前工作 | 覆盖 | idle-only compact 的 result branch（`120-130,253-258`）。 |
| S8 focused compact 保留重点 | 覆盖 | focus 只影响 summary window，非普通 turn（`134-142`）。 |
| S9 飞书 compact 同步 shadow | 覆盖 | pending intent/materializer 复用同一 shadow output identity（`144-152,258`）。 |
| S10 无历史 no-op、不建空 session | 覆盖 | explicit no-binding/no-plan outcome（`128-132,257-258`）。 |
| S11 summary/persistence failure 不丢 context | 覆盖 | strict manual failure + delta Scenario（`136-142`; kernel delta `21-25`）。 |
| S12 busy compact 不静默改写 | 覆盖 | active/queued busy outcome 不调用 Kernel（`128-130,256-258`）。 |
| S13 范围：双入口、文本、shadow、群 @ | 覆盖 | D1-D6 与 three deltas 各有唯一 consumer owner。 |
| S14 不建窗口、不删历史 | 覆盖 | D2/D6 均不引入 UI/history deletion。 |
| S15 不改 auto policy、无 `/reset` alias | 覆盖 | exact grammar、auto no focus（`75-81,138-140`）。 |
| S16 不提供恢复/选择历史会话 | 覆盖 | reset 只换 current binding，不露出旧 session selector（`89-99`）。 |
| S17 不按用户拆群上下文/权限 | 覆盖 | D1 保持 current group+agent model（`77-79`）。 |
| S18 不增飞书原生 slash menu | 覆盖 | text parser only，no adapter protocol/UI change（`73-81,154-160`）。 |

#### Delta-spec

| 原子 | 结论 | 本轮核实 |
|---|---|---|
| gateway/external-channels MODIFIED control/background requirement | 成立 | 保留 `/stop`、background scenarios，并把 outcome+intent, startup/reconnect drain, no-replay crash 写成用户可观察行为（`specs/gateway/external-channels.md:7-65`）。 |
| gateway/routing-delivery ADDED `/new` + `/compact` | 成立 | `/new` exact grammar、visibility fence、replay 与 compact result matrix 都可观察（`specs/gateway/routing-delivery.md:7-58`）；S5 failure reversal 仍随 R3-C1 阻断。 |
| gateway/routing-delivery MODIFIED group gate | 成立 | 正确修改既有 Requirement，保留所有原场景并补 `new/compact` mention rule（`60-90`）。 |
| kernel/context-persistence MODIFIED compaction requirement | 成立 | 已有 manual/automatic/window/workspace contract 均保留，新增 focus/idempotency/strict failure 是同一 SDK consumer contract（`specs/kernel/context-persistence.md:7-51`）。 |

#### Milestone

| Milestone | 结论 | 本轮核实 |
|---|---|---|
| M1 fresh-session | 垂直切片、串行前置合理；被 R3-C1 阻断 | parser→operation/binder→lease→external confirmation→real context test 是完整用户 slice（`design.md:300-306`）；M1-C3/C4 需要增加 publish-failure 中 old intermediate/terminal/external output 恢复断言。 |
| M2 guided-compaction | 垂直切片、依赖 M1 合理 | focus/strict SDK behavior 与 Gateway/external confirmation 是同一可见能力（`306-307`）；R2-C1 recovery test 已纳入 M2-C5，未承担 `/new` lease rollback。 |

### 架构进攻

| 角度 | 主动检验 | 结论 |
|---|---|---|
| 归属 | `ControlOperation`/intent 留在 binding-store transaction owner，control output 仍留 saga owner，materializer 只在 composition 协调 two-domain handoff；lease 留 runtime-delivery context 而非令每个 transport 读 coordinator fields。 | 合法且符合 `SPEC.md:150-161`；没有跨包反向依赖或新 generic command service。 |
| 该不该存在 | 删除 `PendingExternalControlDelivery` 会重新暴露 committed outcome→no saga row crash；删除 lease 会重新留下 observer/task/external mirror bypass。反之，没有 plugin registry、第二个 shadow outbox 或 IM API。 | 两个新增概念都有当前生产缺口驱动，规模适当。 |
| 深浅 | `Kernel.compact(focus, idempotency_key)` 隐藏 planner/transcript 细节；pending intent 只承载 outcome→saga 的单向交接；saga 保持唯一 shadow output owner。 | 接口足够深，未复制现有 recovery 或把 SQLite coordination 泛化成框架。 |
| 治本还是补丁 | successful reset 与 crash recovery 已从统一 visibility fact / durable intent 解决根因，而非末端 transport patch；但 quiesce abort 只拒绝而不保存 output，使 rollback 没有恢复语义。 | R3-C1；不改会把一次本应无状态变更的失败 `/new` 变成不可恢复的可见输出丢失。 |

### Issues

- [R3-C1][CRITICAL] [决策 2、`/new` 主流程、风险「旧排队输入或任意可见输出跨越 `/new`」、M1-C3/C4] `quiesce_and_settle()` 被定义为“立即拒绝所有尚未取得的 old-run visibility lease”并取消未出站任务（`design.md:91,185-190`）；`permit()` 也只规定在 quiesce/commit 后“取得不了”（`95`）。随后 binder publish 失败时，设计只调用 `restore_visibility()` 并说 old run “继续产生后续输出”（`91,93,251`），没有保留或重放在 temporary quiesce 内已经到达、却被拒绝的 output identity。这个窗口在生产中真实存在：每个 `assistant_message` 先进入 observer（`session_run_coordinator.py:1000-1020`），observer 可立即发 external intermediate 或创建 detached IM `message_delta` task（`runtime_delivery/observer.py:254-296,1127-1157`）。因此一个 old intermediate bubble/mirror 可在 candidate 已成功、publish 尚未成功时申请 permit 而被丢弃；若 publish 失败，它不会因 lease 恢复而重新出现，且可能不是最终 reply 的内容。**不改，失败 `/new` 虽未换 binding、未 interrupt old run，却会永久吞掉旧工作的可见输出，违背“旧工作可继续/不是隐形 `/stop`”，并使 worker 无法在 task cancel、permit deny、restore 三者间选择不丢消息的实现。**设计必须拍死 abortable quiesce 的交付语义：quiescing 中尚未 outbound 的 output 应被可恢复地暂挂（例如 `permit` await 到 commit/restore；commit 返回 suppressed、restore 放行原 identity），而不是直接拒绝/取消后丢失；`quiesce_and_settle()` 只等待已持有 permit 的真正 in-flight send。同步规定 IM stream、terminal、external mirror 的处理，并在 M1-C3/C4/Runbook 加入“event 已到达/permit 等待 → inject `publish_reset` failure → restore 后同一 output exactly once，且无新会话确认”的测试。

### Recommendations

- [R3-R1] 在 D2 的 lease state machine 写出 `active → quiescing → committed-revoked | restored`：quiescing 阶段的 output reservation 必须保留原 identity 和 delivery work；成功 commit 才丢弃，失败 restore 才放行。不要用重新读取 Kernel event 或复制新的 outbox 来补救。
- [R3-R2] M1-C3/C4 除既有成功 reset 三类 race 外，补 `publish_reset` injected failure 的 IM intermediate、terminal-ready 和 Feishu mirror 三项；断言 binding/generation 未变、没有“已开始新会话”确认、每条 old output 最终恰好一次可见。

### Author Resolutions after Round 3

| Issue | Resolution | Changed design evidence |
|---|---|---|
| R3-C1 | accepted — `RunVisibilityLease` 明确为 `active → quiescing → committed-revoked | restored`。quiescing 不再拒绝或取消未出站 output，而是以原 run/output identity、payload 与 reply context 暂挂 `DeferredRunDelivery`；`commit_revocation()` 才 suppress，`restore_visibility()` 则 FIFO 放行同一 delivery work。已持 immediate permit 的 send 仍先 settle，所以成功 `/new` 不会收到迟到旧文本；失败 `/new` 不换 binding，也不会吞掉 old intermediate/terminal/Feishu mirror。 | `design.md` 决策 2、lease interface、`/new` sequence、风险/Runbook、M1-C3/C4；routing delta 新增 publish-failure Scenario。 |

## Round 4

### Metadata

- reviewer: `/root/design_review`
- review_mode: `delta`
- mode_reason: `R3-C1 的修订改变了 D2 内 abortable-quiesce 的有界状态语义及其 Gateway delta/M1 验收，但未改变需求范围、SQLite handoff、包边界或 milestone 拆分；重查 R3-C1、所有受影响输出入口与下游契约。其余完整台账 retained_from: Round 3 — 未修改且本轮变更不触及其事实前提。`
- started_at: `2026-08-05T02:52:55+08:00`
- completed_at: `2026-08-05T02:54:17+08:00`
- duration: `1m 22s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

`/new` 的失败分支现在与成功分支使用同一个 lease owner，却有明确相反的终态：quiescing 只暂挂原 delivery work，commit 才 suppress，publish failure 则按原 identity FIFO 恢复。它既不会让旧输出越过成功确认，也不会把失败 reset 变成无声丢失。可进入 `change-orchestrator` 实施。

### Coverage

本轮重查 D2 的 lease/sequence/风险段（`design.md:85-97,183-190,219-251,267-275`）、Gateway routing delta 的新增失败 Scenario（`specs/gateway/routing-delivery.md:7-35`）、Runbook（`design.md:291-298`）及 M1-C3/C4（`300-307`）。同时从生产路径复核了 terminal stream、observer external mirror、detached IM task、saga recovery 和 composition wiring（`session_run_coordinator.py:440-486,961-1041`、`runtime_delivery/observer.py:254-296,1125-1157`、`task_tracker.py:13-51`、`shadow_sync.py:421-477`、`composition.py:390-405,428-456,512-524`）。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R3-C1 | quiescing 保存 `DeferredRunDelivery`，commit suppress，restore FIFO 放行原 delivery work | D2 明确不再拒绝/取消未出站 output，而以 `(run_id, output_identity, payload, reply context)` 暂挂（`design.md:91`）；`permit` 的 `ImmediatePermit | DeferredPermit | Suppressed` 与 commit/restore outcome 也已拍死（`183-190`）。这正覆盖当前 observer 先处理每个 event（`session_run_coordinator.py:1000-1003`）、随后可能创建 external/IM detached delivery（`runtime_delivery/observer.py:254-296,1127-1157`）的丢失窗口。 | closed |

### 受影响原子与波及链

| 原子 | 本轮核实 | 结论 |
|---|---|---|
| D2 state machine / owner | `RunDeliveryContextStore` 持有同一 lease；quiescing 只停止 immediate permit，defer 不写 saga row、不创建 detached task，成功才 commit discard、失败才 restore（`design.md:91,95,183-190`）。 | 成立；worker 不再需要在 task cancel、permit deny 与重放 Kernel event 间猜测。 |
| terminal path | 当前 terminal 在 `_await_terminal_run()` 后才走 final route（`session_run_coordinator.py:450-486,961-1041`）；design 保留 terminal 先取 transition lock、再 claim lease，reset 先取 lock 时 terminal 会进入同一 deferred/restore outcome（`design.md:95-97`）。 | 成立；无 deadlock，失败发布后可用原 final identity 继续。 |
| IM stream / detached task | 当前 observer 对 content 创建 `RuntimeDeliveryTaskTracker` task（`runtime_delivery/observer.py:1125-1157`），tracker 不有 per-run cancellation owner（`task_tracker.py:13-51`）。新契约在 task admission 前 defer 原 work，恰好避免“先建 task 后 cancel”丢失。 | 成立。 |
| external mirror / saga | 当前 mirror 可在发送前写 saga output、再启动 mirror/send（`runtime_delivery/observer.py:254-296`）；新契约要求 deferred output 在 restore 前不持久化 saga/不发 task（`design.md:91,95,190`）。成功 commit 仍按 durable supersession filter 丢弃，故不与 R2-C1 materializer/recovery 混淆。 | 成立。 |
| linearization and failure sequence | sequence 的 quiesce reply 明示 “later output held pending outcome”（`design.md:231-236`）；publish failure restore same lease、不发布/确认 new binding（`251`）。 | 成立；成功与失败分支有互斥、完整的可见性终态。 |
| Gateway consumer contract | 新 Scenario 要求原 binding/context 保持、无 success confirmation、held stream/final/mirror 原 identity exactly once（`specs/gateway/routing-delivery.md:30-35`）。 | 成立；是可观察行为，不泄露实现类型。 |
| Runbook and M1 exit evidence | Runbook 分别覆盖 IM 三类与 Feishu mirror 的 publish-failure restore（`design.md:293-294`）；M1-C3/C4 同时写 reviewer outcome 和 worker injection coverage（`306`）。 | 成立；成功 reset 与 failure rollback 都有可验门槛。 |

### 架构进攻（受影响角度）

| 角度 | 检验 | 结论 |
|---|---|---|
| 归属 | Deferred delivery 仍住在已有 `RunDeliveryContextStore`，而不是让 coordinator、observer、task tracker 各自缓存一份 retry state。 | 正确；保留单一 visible-delivery owner。 |
| 该不该存在 | 删除 `DeferredRunDelivery` 会重现 R3-C1；把它改成第二个 durable outbox 会为一次短暂、可回滚的进程内 transition 引入多余跨存储状态。 | 当前最小化设计合适。 |
| 深浅 | lease 接口吸收了 payload/context/identity 与 commit-or-restore outcome，调用方只走原 delivery path；没有让每种 transport 自己实现 rollback。 | 足够深，且没有重造 saga recovery。 |
| 治本 | 成功 commit 仍用 revoke/suppress 解决迟到输出，失败则恢复同一 delivery work，不依赖重读 Kernel event 或 provider replay。 | R3-C1 已治本关闭。 |

### Issues

None.

### Recommendations

None.
