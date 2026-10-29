# feat-677: Memory 效果评测 — Design Review

## Round 1

### Metadata

- reviewer_target: `/root/design_review`，独立设计 reviewer，未参与受审设计编写。
- review_mode: `full`
- mode_reason: 首轮 Gate 2；覆盖 LongMemEval 首期全部需求、架构/接口、Context 生命周期、delta-spec、Runbook 与 M1。
- started_at: 2026-10-29T13:07:44+08:00
- completed_at: 2026-10-29T13:10:38+08:00
- duration: 174 秒；计时自本轮首次显式时间记录开始，前置文档与源码阅读未计入。
- 冻结版本：分支 `codex/feat-677-memory-evaluation`，HEAD `82c82e55b1918985f135f4d3ef03da01c02744ec`，加本轮受审的 `spec.md` / `design.md` 工作区修订。
- `spec.md` SHA-256：`6fb7ba6882de85d9f7c85f79f51d8e6643a9b94b9e78d60ce59f6355a885bf0a`。
- `design.md` SHA-256：`fec6437f8ed808fc807776dbd9c53f2c98e55ac809403d06a23df34310f1945f`。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

方案能够在现有架构和已安装 DSH 公开接口中实施。当前首期范围、机制验证与真实模型评测的边界已明确；没有发现会让下游实质走偏的未解决设计问题。本结论是设计可实施性判断，不是原生导入、隔离或模型能力已经运行通过的结论。

### Coverage 与证据

#### 需求与用户约束

`spec.md:65-99` 的四组要求已分别落到设计的数据白名单/原生物化、三方法候选接口、冷环境与访问边界、默认计划及显式运行开关。历史双方正文、日期与顺序保留；不重演旧回复、不预先总结、不按答案标注挑材料。其他 benchmark 留在材料背景，实施范围与 M1 均只含 LongMemEval。

本轮授权明确停在真实模型评测之前。`design.md:141-143,240-260` 将默认 `plan` 定为不加载候选运行时、不探测模型、零 judge 请求；真实 `run` 另需显式开关、非空题集和阶段限额。确定性 provider 的运行目标是验证真实产品机制及请求/交付边界，未把候选真实分数、正式 subset 或真实 judge 参数作为本轮门禁。此范围与用户授权一致。

#### 原生历史与实际准备链

- DSH 公开能力：安装版 `@deepseek-ai/dsh-session-persistence@0.2.1-alpha.1` 的 `package.json` 公布根 export；`lib/types/index.d.ts` 与 `handle.d.ts` 提供 `create/open/append/flush/close`，定义连续序号、单写者 ownership 与持久屏障。`@deepseek-ai/dsh-session/lib/types/types.d.ts:58-93,255-285,350-386` 提供当前 header、turn/step、工具调用/结果词汇。设计使用的无继承根 session、已有枚举、配对事件与保留时间路径可实现；不需要写物理 JSONL、private import 或上游补丁。
- 当前产品装配入口是 `packages/dsh-integration/src/index.ts:179-180` 的 `KnowledgeRuntime`，该服务在 `knowledge/runtime.ts:35-55` 组装真实 `DocumentMemory` 与 `Dreaming`。`client.ts:15-27,45-55` 已有独立 home/profile 和官方 DSH 子进程启动路径。评测专用插件与本地控制 socket 可以接入这些服务，生产 profile 不加载它；没有要求新建生产 RPC 或替代 Agent loop。
- 消息形状核对到 `packages/personal-assistant/src/inbox.ts:273-288` 和 `packages/dsh-integration/src/global-mode.ts:22-43`：用户历史应保留 Inbox 的发送者、时间、目标和正文；助手历史应位于 `send_message target/text`，不成为私稿。导入 provenance 与本次实际发送回执分开，避免把结构化导入冒充在线业务执行。
- `knowledge/memory-sources.ts:94-122` 对 Inbox JSON 保留来源字段并重组分页；普通工具结果内容也保留。该选择器确实不普遍投影 event time，因此 `design.md:164` 把日期和原 turn 位置保留在模型将读取的工具结果中是必要且可行的适配，不依赖只存 header 的日期。长文本经来源分页及 `dreaming.ts:198-212` 的 input 文件转换继续交付；M1 要求实际请求/读取结果处审计保真，未以磁盘有原文代替消费证明。
- `MemorySources.baseline`（`memory-sources.ts:210-226`）按已有安全 step 建立位置；`Dreaming.owner`（`dreaming.ts:70-82`）首次使用该 baseline，后续 `execute`（149-154）补登记新流。设计先持久化空来源、可信绑定并完成初始化，再追加完整历史，明确规避首次登记跳过旧材料的问题。真实准备可通过现有 `Dreaming.start`（110-122）触发；完成判断有当前 `status`/backlog（322-337）及持久进度可用，不需要 Runner 理解游标。

#### Context Design Review — Mode A

触发面包括历史转换、来源和身份、记忆准备输入、文件按需读取、持久状态恢复及冷答题。以下是源码和设计层面的确认；本轮未捕获新实现的真实请求或运行模型。

| Consumer / Surface | 设计判断与证据 |
|---|---|
| 记忆准备模型：消息、工具结果、来源与时间 | `HistoryInput` 只含完整历史，原题 ID/题型/问题日期/答案标注留在控制区；白名单先于候选边界。Inbox 的可信 owner 标识、原角色/日期和 imported provenance 保留，外部材料没有升格为新授权。真实 Dreaming 的受限 prompt、正常读取和 finish 语义继续由 `dreaming.ts:214-230` 负责。未来问题不会引导准备阶段选择保留事实。 |
| 答题模型：常驻入口、按需正文、历史与工具 | `design.md:174-184` 明确 fresh session、新运行目录、独立工具与服务访问边界；禁止旧 Global context、摘要、Inbox、维护轨迹与框架旁路历史。隔离要求由宿主和可达性落实，不能靠 prompt。候选机制自身保留的原文索引是合法状态，不把当前文档布局提升为所有候选的协议。 |
| 答题恢复：正文、版本与来源许可 | `MemoryDocuments.context`（`memory-documents.ts:144-152`）按版本 basis、generation 和 pending 判断入口是否有效；`DocumentMemory.forConfig`（`document-memory.ts:98-112`）在 PA 打开时标记来源待刷新，`MemoryDocuments.syncSources`（173-183）可清除 pending。设计明确封存正文及必需状态、恢复后走正常装配；现有 `index.ts:439` 的来源同步接线可用。因此不是只复制 `MEMORY.md` 就假定记忆已可消费。 |
| 问题与回答：时间和公开交付 | 原问题及 `question_date` 仅在封存后给 answer，防止机器今天覆盖题目时间。Global 答案取本地隔离目标的实际 `send_message` 回执；现行 `global-mode.ts:19,28-43` 将私稿与公开发送区分。新上下文不继承此前答题状态，避免重答择优。 |
| Judge：题型规则与状态 | gold 只给独立 judge，评分不反馈候选重答。已读取并核实官方 `evaluate_qa.py` 的题型分支、`_abs` 判断及 `question_id/hypothesis` 格式；实时内容 Git blob 为设计记录的 `4732f3772b04a2b9069121ade304e6320494abc2`，SHA-256 为 `ecce9c4c79dc89d99534ac17b383a5cbb5b9f0c69ee98adaf0684742e3d95251`。来源：[官方 evaluator](https://github.com/xiaowu0162/LongMemEval/blob/main/src/evaluation/evaluate_qa.py)。 |

Before/After 例子（设计的 A→B 住址更新）能说明转换保持原始经历、候选自行生成记忆，后续问题不反向污染准备。配置、模型和存储差异进入 candidate identity；数据、问题、完整历史与评分规则进入 protocol identity。这些边界能支持有意义的版本对照。

#### 职责、依赖与复用判断

稳定输入/结果契约放在 `product-contracts`；数据、编排、评分与报告在 `evals/memory`；只把 DSH、来源初始化、当前 Dreaming 完成判定及文档快照恢复放在 integration adapter。该分工与 `SPEC.md` 的依赖方向及 `tests/contract/test_runtime_dependency_contract.py:14-45,58-86` 一致。现有 `KnowledgeRuntime`、文件与 profile 生命周期足以承接实现，无需通用调度平台或另一套记忆系统。

Inbox 格式来自 PA，而 integration 不可导入 PA。设计允许复用投影 helper，同时已明确遵守依赖边界；实施时可在合法共享契约层复用纯投影，不能跨包相对导入。此处没有要求新增反向依赖，不构成设计缺陷。

三方法接口加 opaque preparedRef 足以承载当前离线整理和未来摄入时更新；Runner 不解释候选内部状态。两种轻量替身只用于验证协议独立性，没有把产品 Dreaming 的 cursor/page/文件布局复制成框架断言。当前接线变化允许局部修改 adapter，满足用户的解耦要求。

#### Delta、验证与退出标准

- Gateway/PA `no spec delta` 合理：首期是离线评测入口，未改变用户产品行为。新增协议权威在 `evals/memory/README.md` 并由 `evals/README.md` 导航；实施若必须改来源等产品行为，应按设计补窄 delta，不能静默扩张。
- 无客户端 UI 或生产迁移，不需要原型或 `deployment-prompt.md`；不要求连接生产 IM。
- M1 同时覆盖完整历史、实际准备请求、冷上下文和工具可达性、正常记忆消费、最终发送回执、失败与超时清理、计划零出站及正式 run 开关。`design.md:133,137-143,200-221,244-256` 区分 ready/incomplete/failed、计划分母/有效评分分母及 unavailable 用量，不把成功结束或文件存在当成准备完成。
- 现有 `packages/dsh-integration/tests/dreaming-runtime.test.ts` 已提供官方运行时加 `llm/stream` 确定性 fixture 的测试接线参考；本轮只检查其代码，没有重跑测试，也没有调用真实候选模型或 judge。新适配器仍必须按 M1 做实际集成验证。

### 历史问题闭环

首轮，无历史问题。

### Issues

无。

### Recommendations

无新增建议。已有 M1 中的消费/隔离证据要求足够，实施后按真实差异复核，不另加真实模型分数门禁。

### Author Resolutions

- 接受 Round 1 结论。已核对公开持久化接口、空来源初始化、当前 KnowledgeRuntime 接线和冷答题来源状态，未发现实质异议。
- 用户授权边界：本轮只做确定性 provider 验证，不执行真实候选或 judge；真实效果继续标记未测。
- design.md 状态行仅将“待 Gate 2”改为已通过，无受审行为变化；保留本轮审查证据。

## Round 2

### Metadata

- reviewer_target: `/root/timeline_design_review`，独立设计 reviewer，未参与受审设计或实现编写。
- review_mode: `full`
- mode_reason: 时间回放本身有界，但同时修改稳定 `prepare.ready` 语义、协议身份与 M1 退出标准；因此按 full 核对完整需求与链路，详细展开时间准入、原生历史可见性和状态语义。没有把 Round 1 Approved 当作本轮放行依据。
- reviewer_handoff: 原 reviewer `/root/design_review`；本轮由新独立上下文接手，依据 Round 1 完整报告、当前 diff、实际组装入口及现行实现重新核对。Round 1 无存活问题。
- started_at: 2026-10-29T22:08:28+08:00
- completed_at: 2026-10-29T22:10:51+08:00
- duration: 143 秒；计时自本轮首次显式时间记录开始，前置文档与 diff 阅读未计入。
- validated_at: 分支 `codex/feat-677-memory-evaluation`，HEAD `31f68e4152e06948575065f0e59dcd91ff6b4915`，加本轮受审的 `spec.md` / `design.md` 工作区修改。
- `spec.md` SHA-256：`077df3589a1e65394479bba1f390a137852fa3f4a8f874329004bcf6ced5e327`。
- `design.md` SHA-256：`4f5c7a9807368dd9af34f2dcc518c80e3575d878a40fc332d600c6504d12a864`。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

统一时间回放可在当前产品组装和公开持久化接口中实施。准入规则由 Dreaming 持有，评测宿主负责按已确认的会话时间推进、等待和封存；未发现会使实施实质走偏的未解决设计问题。本结论只确认设计可行性，不表示新回放已经实现或通过运行验收。

### Coverage 与证据

#### 需求、协议与用户约束

`spec.md:72-118` 的完整历史、正常自动积累、末尾只等待已触发工作、冷答题、框架独立性和显式花费预算均有对应落点。`design.md:172-184` 只定义一套 chronological-session-ingestion；回放终点是末段历史，不传未来问题或 `question_date` 给 prepare，不跳到下一周期清空积压。会话原子到达、同刻原顺序、碰到周期边界先记录新活动、维护期间逻辑时间暂停和无时区解释均已明确。这是会话级顺序回放，设计没有宣称覆盖真实前后台耗时竞争。

`prepare.ready` 的新含义与用户要求一致：完整导入、已准入处理成功结束、当前状态已封存；不等于全部历史已提炼。协议 version 2 与 candidate v3，以及有效 `intervalMs` / `quietMs` / `maxInputTokens` 和时间假设进入身份，避免旧集中导入结果与新结果混用（`design.md:137,180-182`）。通用 Runner 当前只核对完整导入收据及 ready 状态后交付问题，不读取 Dreaming backlog，因此不需要把时间调度或游标知识引入框架（`evals/memory/runner.ts:95-114`）。

默认 plan 仍不加载候选；实际运行开关、非空题集和阶段限额保留（`evals/memory/cli.ts:22-46`）。`design.md:256-272` 明确独立门禁使用确定性 provider，owner 随后只执行已选 e47becba，一题准备 40 请求/600 秒、答题 12 请求/180 秒、judge 1 请求/120 秒；不自动加预算、换题或重跑候选。该授权范围没有被扩大到完整 benchmark、生产服务或本 reviewer 的真实模型调用。

#### 实际组装与时钟接入

- 实际服务由 `packages/dsh-integration/src/index.ts:179-180` 装配 `KnowledgeRuntime`，后者在 `knowledge/runtime.ts:53-58` 建立 `DocumentMemory` 与 `Dreaming`。评测 profile 挂载独立插件，仍通过同一 `RuntimeClient` 和本地控制 socket 使用这些服务（`evaluation.ts:163-179,204-219`）。设计没有要求替换 Agent loop、DSH 私有导入或生产 RPC。
- 当前 `Dreaming.owner` 的 activation、`execute` 的自动成功/失败重试时点直接取 `Date.now`，只给 `tick` 传入历史时间不足以完成回放（`knowledge/dreaming.ts:72-107,133,196,213`）。设计已明确在 owner 初始化前调用 `useClock`，使逻辑时间的所有者仍是 Dreaming，并关闭 timer/step 自动准入；因此没有把这一差异留给适配器私改 owner 状态。
- 当前 initialize 在恢复知识服务后注册配置，owner 的首次创建发生于 `status` 或绑定 root 的 `agent/created`；现有评测 import 先调用 status，之后才 ensure 独立 root（`index.ts:305-350`、`evaluation/history.ts:20-27`、`evaluation.ts:61-64`）。因此在评测插件/导入初始化中先设宿主时钟，再创建空来源与 owner，最后解析 root 的顺序有真实接入位置；不是依赖测试专有装配。
- 自动准入现状包含周期、retryAt、静默、前台 provider 容量、父 Agent 状态和停用条件（`dreaming.ts:92-107`）；自动成功会更新下次周期基准，即使本次没有合格增量也不会无限卡在同一到期点（`196-198`）。设计要求 `nextAutomaticAt` 与 `tick` 复用这些产品条件；长时间空档可以按真实周期检查，无需复制常量或建立第二个调度器。实际执行失败由本次评测立即终止，不能拿产品后续重试时间把失败掩盖成 ready；这与复用产品准入条件不冲突。
- 当前阶段超时、退出 watchdog 和用量耗时均在 adapter/runner 使用真实计时（`evaluation.ts:53-59,79-84,98,149-157`、`evaluation/runtime.ts:17-43`、`evals/memory/runner.ts:23-40`）。设计只替换 Dreaming 逻辑时间，禁止全局 Date/timer 替换，能够保留这些硬截止和取消边界。准备过程结束再停子进程、复制正式记忆的顺序已有实现（`evaluation.ts:64-78`），可承接新的 idle/freeze 屏障。

#### 原生历史后续可见性与冻结范围

当前 `importHistory` 已通过公开 persistence `create/open/append/flush/close` 保留事件身份和正文（`evaluation/history.ts:20-67`）。拆成空来源初始化与逐 session 追加不会改变该存储契约。`MemorySources.baseline` 按空日志得到 `-1`，后续 freezeTarget 与 freeze 每次重新 observe，而非把首次读到的事件数组永久保存（`knowledge/memory-sources.ts:110-120,241-277,323-337`）。

本轮另核实安装版 `@deepseek-ai/dsh-session-query@0.2.1-alpha.1`：其公开根 export 的实现 `lib/index.js:348-393,419-425` 每次先 stat，冷读缓存以持久化 identity 和 revision 为键；`dsh-session-persistence/lib/types/index.d.ts:141-145` 明确 revision 的变化契约。因此先 observe 空来源不会阻止后续 append 对新观察可见，不需要广播历史事件、重演旧工具或手工失效 DSH 缓存。此处是本地安装版源码核对，未运行新的导入试验。

现有真正执行的 root 与导入的历史 session 分离（`evaluation.ts:171,179,214-215`），历史来源保持冷读；设计只解析该真实 root，不把所有历史 session 激活成运行中的 Agent。未来正文到时才写入，并且每轮 tick 完成前不继续追加，形成物理可见性边界。产品自身 freezeTarget 再限制连续批次，source_history 在资格检查后按 seq/time cutoff 过滤（`knowledge/dreaming.ts:153-164`、`dreaming-history.ts:19-33,78-90`），两者能共同保证早期整理与回查不读到后到正文。

#### Context Design Review — Mode A

触发面为历史交付时机、整理者可见来源、先前记忆累积、维护恢复和冷答题；不是提示词字面改动。以下均为设计与源码层面判断，没有新实现的模型请求或行为证据。

| Consumer / Surface | 本轮判断 |
|---|---|
| 记忆整理者：消息、来源与时间 | 数据白名单继续只给历史，原文/角色/会话日期与 imported provenance 沿原生事件进入实际来源选择。未到达正文不落可读存储；同刻全部追加后再准入，后到纠正进入下一轮。历史只是经历数据，不增加业务授权。 |
| 记忆整理者：既有记忆与按需原文 | `runDreamingAgent` 仍提供当前正式库、staging、真实 input 和 source directory，保留受限文件工具与 source_history（`dreaming-agent.ts:35-85`）。source directory 和参数由宿主派生，模型有可发现的来源 ID 和读取入口，不要求猜测内部身份。早期 Berlin 只能生成当时知识，中期 Paris 纠正可更新已有记忆，末段尚未到期的新事实可以留在 backlog。 |
| 维护换窗恢复 | `history` 恢复维护者自身，`source_history` 回查获准业务原文；来源资格与本批 cutoff 在读取时复核，换窗不自动扩大到后到历史（`dreaming-agent.ts:49,52,59-60`、`dreaming-history.ts:70-90`）。设计保留原恢复测试，没有把维护笔记当作答题记忆。 |
| 冷答题：Memory、问题与日期 | 独立 runtime 仅复制正式记忆及必要的 documents 状态，经正常来源同步与装配消费；文件守卫不开放准备目录，服务只提供本次问题和本地发送（`evaluation.ts:97-114,186-202,224-235`、`evaluation/runtime.ts:45-64`）。末尾有 backlog 不产生额外注入，空记忆同样可冷答题。 |
| 运行者与 Runner：成功、未触发、失败 | tick 返回实际尝试结果，whenIdle 只等待已准入工作；已触发失败/超限不能用空闲或文件存在推断成功。最终 backlog 与 timeline 留证，Runner 只消费稳定状态和 locator。没有对模型隐藏失败并继续补跑的设计。 |

`design.md:184` 的验证样例能够区分新的时间行为与旧的集中导入：依据实际收到的原文生成 fixture 记忆，核查早期请求无后续纠正、中期确已收到纠正、末段未到期事实没有进入封存记忆，并由冷答题实际读取封存值。另有零到期/零准备模型请求用例；预算、挂起截止、产品 scheduling 和真实 Dreaming 回归保留。该证据计划能证明交付与边界，不把固定写入 Paris 的替身当作记忆理解证据；模型理解能力仍须与确定性机制结果分别报告。

#### 完整性、职责与未受影响边界

完整历史无损、问题/gold 隔离、独立评分、失败分母和最终回答原样保留均未被本次修改改变。本轮从 `evals/memory/dataset.ts` 的字段白名单/稳定时间排序、`runner.ts:85-117` 的阶段交接和 `judge.ts:14-46` 的独立评分重新核对了本地链路；官方 evaluator 原始核验 `retained_from: Round 1`，因本次不改评分模板或题型规则，不重复联网核对上游。所有真实模型效果均未在本轮验证。

职责分工合理：Dreaming 维护自身时钟与准入语义，evaluation runtime 维护回放顺序和来源物化，adapter 维护隔离/真实预算/快照，通用 Runner 维护稳定状态和评分。新增四个宿主方法服务于可验证的生命周期，没有新增通用调度服务、重复记忆写者或第二套候选协议。生产默认 Date.now/timer/step 行为要求保持；因此 Gateway/PA `no spec delta` 成立，实施若改变正常产品准入须按现有约定补窄 delta。评测协议的长期权威继续在 `evals/memory/README.md`，M1 已纳入新时间与消费验证；无前端变化或一次性生产迁移，不需要原型或部署提示词。

### 历史问题闭环

Round 1 无 Issues。Author Resolutions 中的“当轮不执行真实模型”属于历史授权；本轮以已确认的一题有界授权和新 Runbook 为准，未将旧范围继续当作当前禁止条件。原轮关于来源初始化、框架独立与冷答题隔离的判断已经在当前装配和上述代码中重新核对，没有新增存活问题。

### Issues

无。

### Recommendations

无。实施按既有 M1 和本轮已明确的时间/失败/Context 证据要求验证即可，不新增可选机制或第二套严格时点实验。

### Author Resolutions — Round 2

Author 已核对本轮实际组装、公开持久化 revision、准入时钟与 Context 分析，接受 Approved；无 Issues / Recommendations 待处理。本次仅补审查状态说明，受审方案不再实质修改。后续由同一 owner 按 M1 实施，保留一题上限，验证与效果结论分开。
