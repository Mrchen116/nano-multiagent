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
