# Design Review: feat-532

## Round 1

### Metadata

- reviewer: `/root`
- review_mode: `full`
- mode_reason: R1；用户要求在整体设计完成后，从每个 Agent 的上下文适配性出发重新审查全部实验架构、信息边界、数据流与里程碑。
- started_at: `2026-08-10T23:54:15+08:00`
- completed_at: `2026-08-11T00:02:03+08:00`
- duration: `7m48s`

### Verdict

Changes Requested — 6 CRITICAL / 3 WARNING

当前不应进入 M1 实施。方向上成立的部分包括：独立 Codex session、逐 case leave-one-lineage-out、Native 对话核心、非介入式审计、Memory 一次构建三次消费、质量与负担双门禁，以及 exploratory 结论边界。阻断项集中在实验真正的承重面：各 Agent 的上下文还停留在角色说明，没有被收敛成唯一、可物化、可 hash 的输入契约；其中已有几处上下文直接互相冲突或泄漏。

### Coverage

本轮完整读取：

- `docs/changes/feat-532-spec-memory-loop/spec.md`
- `docs/changes/feat-532-spec-memory-loop/design.md`
- 八例 `public/brief.md`、共享 dataset/README/methodology、H01 私有 inventory/rubric
- base-repository recipe/materializer、owner-answer 与 decision inventory schemas
- 当前 `.claude/skills/change-spec-author/SKILL.md`
- 本机 `codex exec`/`resume` CLI 契约与 Codex repo skill loader
- Owner Simulator 独立研究包

### 承重原子核实台账

#### 现状断言

| 原子 | 核实结论与证据 |
|---|---|
| S1：共享 suite 有八个目标 case 与可物化 base | 成立；registry 为 H01/H02/H03/H04/H05/H07/P01/P02，见 `evals/spec_design_alignment/dataset.json:9-74`；materializer 固定 parentless `main` identity，见 `evals/spec_design_alignment/base_repo/materialize.py:24-37`。 |
| S2：既有 case 可以原样作为 spec-only 输入 | 不成立；H01/H03 明确要求 `spec 和 design`，P01/P02 明确要求技术设计，见各 `public/brief.md`；触发 R1-C1。 |
| S3：当前首文档构成 Memory 原始语料 | 成立；当前 Skill 强制保存原始需求、每轮用户原话与 Agent 解读，见 `.claude/skills/change-spec-author/SKILL.md:10-17`、`:139-145`。 |
| S4：既有 owner policy/inventory 可作为新 owner context 的基础 | 部分成立；policy 有语义答案与来源，inventory 有 F/P/V/H、expected handling，见 `schema/owner-answer-policy.schema.json:91-127`、`schema/decision-inventory.schema.json:95-148`；但现有结构不是 Native Simulator 可直接读取的披露契约，触发 R1-C4。 |
| S5：Codex 可从候选仓原生发现当前 Skill | 方案与现状不闭合；Codex loader 搜索 `.agents/skills`，见 `codex-rs/core-skills/src/loader.rs:388-413`，但现有 recipes 安装并强制保留 `.claude/skills/**`，见 `base_repo/recipes/H01-feat-484-A.json:155-223`、`:255-270`；触发 R1-C1。 |
| S6：进程/目录隔离可阻止主会话上下文自然继承 | 方向成立；`codex exec` 支持独立 `CODEX_HOME`、`--ignore-user-config`、`--output-schema` 与持久 session resume；但 design 未将这些能力下沉为逐角色的封存上下文 manifest，触发 R1-C2。 |

#### 设计决策

| 决策 | 核实结论与证据 |
|---|---|
| D1：feat-532 使用独立 experiment overlay，终点为 `gate1_complete` | 成立且由 spec-only 非目标驱动，见 `design.md:30-35`、`spec.md:195-201`。 |
| D2：固定层与 Memory 可变层分离 | 成立，见 `design.md:87-99`；但 task-specific consumption 尚未在承载模型中闭合，见 R1-C3。 |
| D3：正式角色使用独立上下文 | 目标正确，见 `design.md:101-116`；输入只写成自然语言集合，尚不可实施或复验，见 R1-C2。 |
| D4：Native Owner Simulator 直接处理开放问题 | 成立，避免封闭 decision router，覆盖 Q12/Q14；见 `design.md:118-162`。 |
| D5：auditor 只做 post-run validity，不介入 Candidate | 成立，见 `design.md:164-178`；auditor 自身输入不完整，见 R1-C2。 |
| D6：full-context 失败后才升级 on-demand/controller | 成立且不过度预造控制层，见 `design.md:180-194`。 |
| D7：latest-main 多源校对后由 owner 冻结 truth | 成立，见 `design.md:213-222`；但 judge-only truth 与 simulator 可披露 context 未分钟，见 R1-C4。 |
| D8：Memory 每 case 构建一次，三次 run 复用 | 符合 Q1 与用户追加确认，见 `design.md:253-257`；“构建”与 task-specific runtime consumption 被混为一层，见 R1-C3。 |
| D9：质量和 Owner contribution units 分别过门 | 成立，见 `design.md:224-239`；quality judge 输入仍携带 burden/arm 信号，见 R1-C5。 |
| D10：Python runner 承载隔离 Codex sessions | 方向成立，见 `design.md:307-324`；需要逐角色 context manifest 才能落地，见 R1-C2。 |
| D11：失败结果驱动下一版 scheme | 需求成立，见 `design.md:261-290`；没有一个被定义的 Agent/上下文负责把 attribution 变成下一版方案，见 R1-C6。 |
| D12：M1 冻结 benchmark，M2 承载 Memory Loop | 拆分有硬前置且各自交付独立实验价值，见 `design.md:196-257`、`:410-417`；允许串行。 |

#### Spec 澄清记录

| 约束 | 核实结论与设计落点 |
|---|---|
| Q1 leave-one-lineage-out | 已覆盖 `design.md:200-211`、`:253-257`；miner 不应看到 exclusion identity，见 R1-C3。 |
| Q2 “记什么”属于实验变量 | 已覆盖 `design.md:91-99`。 |
| Q3 Owner contribution units | 已覆盖 `design.md:224-239`。 |
| Q4 不引入预设 Agent Team，Candidate subagent 不受额外限制 | 已覆盖 `design.md:295-305`、`:369`。 |
| Q5 不改变 Memory 外的 spec workflow | 已覆盖固定/可变层与 scheme 审计，见 `design.md:87-99`、`:379-388`。 |
| Q6 暂不设 holdout | 已覆盖 `design.md:16-20` 与 `spec.md:275-281`。 |
| Q7 广义首文档语料，不把 Agent 内容一刀切掉 | 已覆盖 `design.md:26-27`、`:200-211`。 |
| Q8 代码是当前行为强证据但不自动覆盖产品意图 | 已覆盖 `design.md:213-222`。 |
| Q9 使用 current owner-answer bank | 已覆盖 owner 校对与 simulator context；context 的 disclosure/clock 仍未定义，见 R1-C4。 |
| Q10 只跑一次 author，不走 reviewer | 已覆盖 `design.md:32`、`:326-367`；原 public brief 仍要求 design，见 R1-C1。 |
| Q11 质量不降且负担明显下降 | 已覆盖 `design.md:224-239`。 |
| Q12 发散问题不能都映射到 Decision | Native 直接回答已覆盖 `design.md:150-162`。 |
| Q13 独立 unit | 已覆盖独立 overlay 与目录，见 `design.md:37-39`。 |
| Q14 不把四层控制器伪装成研究结论 | 已覆盖 `design.md:118-122`。 |
| Q15 不走纯 Native，要求第一性原理综合 | Native + audit + observed-failure escalation 已覆盖 `design.md:164-194`。 |

#### Spec Requirements 与非目标

| Requirement / 边界 | 核实结论 |
|---|---|
| 探索记什么、怎么存、怎么消费 | 结构/存放覆盖；task-specific context Agent 未闭合，R1-C3。 |
| 每例无自身答案 | lineage 规则覆盖；exclusion manifest 反向泄漏目标，R1-C3。 |
| Memory 影响逐项溯源 | trace/provenance 契约覆盖 `design.md:379-408`。 |
| Memory 是唯一 workflow 变量 | 固定层覆盖；Candidate 当前有双 Skill 根与 brief 终点冲突，R1-C1。 |
| 一次 author 直接产出 | runner 状态机覆盖；brief 冲突仍会让 Candidate 继续 design，R1-C1。 |
| 负担按实际语义贡献计 | scorer 角色与门禁覆盖；setup burden 未报告，R1-W2。 |
| latest-main 校准真值 | M1 覆盖；truth/context 时钟未分离，R1-C4。 |
| 双门禁停止 | 覆盖；quality comparison 的 repetition pairing 无自然配对依据，R1-W1。 |
| exploratory 结论 | 覆盖。 |
| 非目标：design 消费/review、Agent Team、spec reviewer、非 Memory rewrite、非首文档 Memory、holdout、预拍存储技术 | 未发现主动越界；Owner Simulator/auditor 属实验控制面，不是被测 design review。 |

#### Delta-spec 与 Milestone

| 原子 | 核实结论 |
|---|---|
| delta-spec | 本 unit 增加 eval 控制资产，不改变 current 产品行为；没有包级 delta-spec 可以接受，但 design 应在修订时明确 `no product spec delta`，避免 worker 猜。 |
| M1-benchmark-freeze | 必须在 M2 前完成，交付 benchmark、truth、simulator/auditor 与 Baseline，可独立复验；拆分成立。 |
| M2-memory-loop | 用户明确要求 Loop 是主体 milestone；交付胜出 Treatment 与全轮证据，拆分成立；scheme 设计责任缺失，R1-C6。 |

### 架构进攻

| 角度 | 结论 |
|---|---|
| 归属 | context projection、角色 prompt、workspace/tool closure 应统一归 runner/control plane，并由 manifest 驱动；当前散落在自然语言表格和各角色自觉中，长期会出现“角色独立但输入不独立”的复发，R1-C2。 |
| 该不该存在 | Native 热路径 + post-run audit 的两层有独立职责，删除 auditor 会让 simulator 污染静默进入统计，删除 Native 则失去开放问答；二者均有存在价值。无需预造 per-turn controller。 |
| 深浅 | `current owner context` 与 `Memory bundle` 都是浅名词：前者隐藏 authority/disclosure/clock，后者混合 corpus build 与 task-time consumption；接口没有降低调用方需要猜的复杂度，R1-C3/R1-C4。 |
| 治本 | post-run invalidation 能防污染进入结果，但不能替代正确上下文；若不先修 Candidate、Simulator、auditor、judge 的输入闭包，靠审计重跑只会形成昂贵的 optional stopping，R1-C2/R1-W3。 |

### Issues

- [R1-C1][CRITICAL] [Candidate context / spec-only 终点]: Candidate 同时收到互相冲突的任务和 Skill 权威。design 宣称固定原 brief 且只到 `gate1_complete`（`design.md:32`、`:93-95`），但 H01/H03 brief 明确要求完成 `spec 和 design`，P01/P02 要求“需求与技术设计”（各 `public/brief.md`）；同时 base recipe 安装 `.claude/skills/**`（`H01-feat-484-A.json:155-223`），design 又新增 Codex 原生 `.agents/skills/change-spec-author`（`design.md:322`），而 Codex 实际只自动发现 `.agents/skills`（`loader.rs:388-413`）。不改会让不同 run 有的继续做 design、有的停 Gate 1，Treatment 还可能读到两份不一致 Skill，实验测到的是上下文冲突而不是 Memory。需要把原 brief 作为不可改的数据保留，另加统一、高优先级的 spec-only task envelope；候选仓只保留一个可执行、可读的权威 Skill closure，并对另一 workflow root 做明确 scrub/同一性断言。

- [R1-C2][CRITICAL] [全部 Agent / context closure]: 角色表只列语义输入，没有为任何 LLM 角色定义可物化、可 hash 的 context manifest。`design.md:313-324` 没有拍死高优先级 role instructions、初始/续轮 user envelope、工作目录文件 allowlist、tool/network 权限、Skill/AGENTS 加载闭包、输出 schema 和 session carry-over；`design.md:335-341` 还把 Candidate 文本直接作为 Owner 的 resume user message。auditor 输入遗漏 public brief、interaction guidance 和冻结 simulator prompt，无法判断“主动披露”；blind judge 的 `clean-room repo` 也没说明是中性 base 还是含 Treatment asset 的真实 run repo。`design.md:384` 又重新出现旧 `mediator`，与 Native 直答冲突。不改会让同名角色在实现时拿到不同权威层级和资产，Candidate 文本可覆盖 Owner 角色，judge/auditor 可能看见错误信息或根本无从判断。需要为 Truth auditor、miner、Candidate、Owner Simulator、run/batch auditor、burden scorer、quality judge 和 loop experimenter 各冻结一份 role-context manifest，绑定 prompt authority、文件/hash、工具、cwd、HOME/CODEX_HOME、输入 envelope、输出 schema、生命周期与 forbidden surface；runner 只按 manifest 物化。

- [R1-C3][CRITICAL] [Memory build / task-time consumption]: 设计一边允许“先形成 task-specific context”（`design.md:95`），一边让唯一 Memory miner 看不到 brief/repo（`:109`、`:316`），因此专门 context Agent 没有任何阶段能基于当前任务工作；同时 miner 可见“该 case 排除清单”（`:109`），会从被排除 unit 名直接知道目标 lineage，破坏 task-blind。`design.md:382` 又把二者压成一次 `Memory bundle`。不改会使一类明确在实验空间内的方案无法实现，并让其余 scheme 可以按 case 反向定制 Memory。应拆成：control plane 先机械投影匿名 allowed corpus，builder/miner 只看投影后的内容而看不到 case id、exclusion manifest 或缺失目录；每 case 构建一次 cross-fitted Memory store；runtime consumer/context Agent 才可看 brief/base repo + 冻结 store，绝不看原始 corpus/private truth，并按 scheme 声明在每 run 检索或形成一次 task context。

- [R1-C4][CRITICAL] [Owner Simulator context]: `current owner context` 被定义成“事实、产品判断、原则、未知、委托边界及来源”（`design.md:126-131`），同时 M1 truth 来源包含 latest-main 代码和后续 unit（`:213-222`）。现有 inventory 明确区分应自行查证的 F 与 owner judgment（`decision-inventory.schema.json:114-148`），H01 rubric 也要求 D01-D06 零用户提问（`H01 rubric:7-20`）。当前 context 没有标记哪些事实属于 Candidate 的 B 世界、哪些 latest-main 证据只供 judge、哪些可由 owner 披露；Native Simulator 因而可能把 later-main 实现事实或 repo 可查事实直接回答给 Candidate。不改会把“Agent 自己 ground”伪装成“少对齐”，并把未来实现泄漏回历史 base。owner-context manifest 必须按 atom 标记 authority、evidence clock、disclosure class 和 source：public/restate、owner-only answerable、product judgment、repo-retrievable redirect、design/out-of-scope、known-unknown/delegated；latest-main truth evidence 默认 judge-only，只有 owner 当前产品判断的中性语义可进入 Simulator。

- [R1-C5][CRITICAL] [Blind quality judge context]: design 让 judge 读取“匿名化首文档、clean-room repo、冻结 truth/rubric”（`design.md:112`），但没有定义中性 judge repo；真实 Treatment repo 含 Memory 与扩展 Skill，会直接暴露 arm。当前 Skill 又强制把所有 Q/A 原话写进首文档（`.claude/skills/change-spec-author/SKILL.md:12-15`），质量 judge 因此能看见 Owner contribution 数和回答内容，违反 `design.md:116` 声称的质量/归因隔离；既有 H01 rubric 还包含完整 Design oracle（`H01 rubric:39+`），不适合 spec-only。若不改，质量分会被对齐次数、Memory 痕迹和 design 缺失系统性污染。应给 judge 一份从 base recipe 重建、无 arm/Memory/workflow extension 的中性 repo；将完整首文档先做确定性结构校验，再给语义 judge 一个去掉原始 Q/A 与 trace 的 conclusion projection；M1 必须为八例冻结 spec-only rubric/truth projection，不能直接把 feat-397 spec+design rubric 塞进去。

- [R1-C6][CRITICAL] [M2 Loop owner]: 图中 `Analyze → Scheme` 是本需求主体（`design.md:57-65`、`:83`），但角色表只有 Attribution analyst，职责停在“下一轮假设”（`:114`、`:305`），Python runner 又明确不生成方案（`:315`）。没有任何角色、上下文或输出契约负责把失败证据变成下一版可运行 scheme。若不改，worker 只能临时让主会话拿着全部 private truth 手工改 prompt，既不可复验也极易把 case 答案硬编码进方案。最简单的修法不是再加浅角色，而是把 Attribution analyst 深化为 `Loop experimenter`：输入冻结的上一版 scheme、匿名/允许暴露的逐 case 质量与负担证据、Memory build/use trace、成本和失败分类；明确不可见 raw private truth/owner bank；输出 suite-global 下一版 scheme manifest、变化假设与禁止 case-specific atoms，再由 runner 机械验证并预注册。

- [R1-W1][WARNING] [质量比较]: 三份 Baseline 与三份 Treatment “按 repetition 编号配对”（`design.md:236`、`:376`）没有自然匹配变量；模型采样不是同一个受控 seed，repetition 1 对 1 与 1 对 3 同样任意。不改会让单个 case 的 win/tie/loss 因配对排列改变。应改成 arm-blind 的 3-vs-3 case-level comparison，或预注册能解释的共同随机条件/全配对聚合，并在 pilot 上验证 judge 稳定性。

- [R1-W2][WARNING] [Owner 成本]: M1 要 owner 校对八例 truth、answer bank、Simulator profile 和 qualification，但正式指标只报告 run 内 contribution units；没有单列真实 owner 的一次性 setup 时间。若不改，最终可能宣称“少对齐”，却隐藏为了建 Memory/模拟用户先投入的大量人工。setup burden 不应算给 Baseline 或 Treatment 任一 arm，但必须单列并给出预计摊销点。

- [R1-W3][WARNING] [运行矩阵与重跑]: “一版方案实际要跑多少工作”只列 8 miner + 24 Candidate（`design.md:371-377`），遗漏 24 个持久 Owner sessions、每 run auditor、每 case batch auditor、48+ quality judges、burden scorer 和 attribution/loop experimenter；critical simulator error 的最大重跑次数也未拍死。虽在 `design.md:231` 提到要预注册异常政策，但下游仍无法估算一轮预算或防 optional stopping。应给出完整调用矩阵和 fail-closed 上限：超过上限则 simulator seal 失败，不继续抽样到“碰巧通过”。

### Recommendations

- [R1-R1] 把“每个 Agent 的 context manifest”提升为 M1 第一等资产，与 suite seal 同级；先用一张矩阵画清 `role × authority layer × files × tools × session state × forbidden`，再写 runner。
- [R1-R2] 用 1 个非计分 case 做端到端 dry run，保存每个 Codex 请求实际发送的 developer/user context 与可见文件 manifest，人工核对后才启动 24 次 Baseline。
- [R1-R3] 为 `owner-context` 和 `judge-context` 分别建 schema；不要让 private truth、Owner 可说内容、Candidate 可查事实继续共享一个模糊对象名。

### Author Resolutions

- [R1-C1] accepted — 原 brief 改为保留的数据输入，新增更高权威的统一 spec-only task envelope；Candidate projection 只允许一份 `.agents/skills/change-spec-author` closure，并整根移除/断言不存在 `.claude/skills` 等 workflow 副本。
- [R1-C2] accepted — 将 role-context manifest 提升为 seal 资产，逐角色绑定指令、输入 envelope、文件/hash、cwd、工具/网络、隔离 home、Skill/AGENTS closure、输出 schema、生命周期和 forbidden surfaces；调用后保存实际 context/文件清单并 fail closed 比对。
- [R1-C3] accepted — 拆成 suite-owned 匿名 Corpus projector、每 `scheme × case` 一次 cross-fitted Memory builder，以及每 run 的 deterministic/Agentic runtime consumer；builder 不再看到 case id、exclusion identity、brief 或 repo。
- [R1-C4] accepted — owner context atom 新增 authority/source、evidence clock 与 disclosure class；latest-main judge truth 和 Simulator-safe context 使用不同 projection/schema，repo 可查事实只触发 research redirect。
- [R1-C5] accepted — judge 使用 arm overlay 前独立物化的 neutral repo；完整首文档先做确定性结构校验，语义 judge 只看移除原始转录、Q&A、trace 和运行元数据的确定性 conclusion projection；formal M1 冻结 spec-only truth/rubric。
- [R1-C6] accepted — 将 attribution analyst 深化为 Loop experimenter；它只读允许的匿名结果、trace、成本和失败分类，输出下一版 suite-global scheme manifest、delta/hypothesis 与禁用 case-specific atoms。
- [R1-W1] accepted — 删除任意 repetition 配对；两个 judge 在同一匿名批次内对六份产物绝对评价，控制面冻结评分后再做 case-level 3-vs-3 比较。
- [R1-W2] accepted — 单列 truth/answer bank 校准、interaction guidance 和 simulator qualification 的 owner setup 时间/contribution 及摊销点，不归因给任一 arm。
- [R1-W3] accepted — 补齐 builder/consumer、Candidate/Owner、run/batch audit、burden、judge 和 Loop experimenter 的调用矩阵；simulator critical failure 整批 fail closed，不以继续抽样替代修 seal；pilot 零重试。
- [R1-R1] accepted — role-context manifests 已与 suite/pilot seal 同级，并明确 runner 只能按 manifest 执行。
- [R1-R2] accepted — 新增 H02 `1 case × 1 repeat` 非计分 pilot，Baseline/Treatment 全链路运行；provisional fixture 明确不得作为 formal 结果。
- [R1-R3] accepted — owner-context 与 judge-only truth/conclusion projection 分离，实施时分别建立 schema。

## Round 2

### Metadata

- reviewer: `/root`
- review_mode: `full`
- mode_reason: R1 的修订改变了 Candidate、Memory、Simulator、judge 和 Loop experimenter 的核心上下文/dataflow，按承重架构变化重新检查全文而非只看 diff。
- started_at: `2026-08-11T00:09:31+08:00`
- completed_at: `2026-08-11T00:10:06+08:00`
- duration: `35s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

设计已具备进入非计分 pilot 实施的必要闭环。尤其是：原 brief 与 spec-only 执行权威不再冲突；每个 Codex 角色都有待物化并 hash 的 context manifest；Memory build 与 task-time consumption 已分层；Simulator-safe owner context 不再混入 judge-only latest-main truth；质量 judge 的输入不再携带 arm、Q&A 或 Treatment repo 信号；失败归因由有明确上下文边界的 Loop experimenter 落成下一版可运行 scheme。H02 provisional pilot 与 formal M1 也已严格分开，不会把未获得 owner 确认的结果冒充正式 benchmark。

### Coverage

本轮重新检查完整 `spec.md`、完整修订后 `design.md`、R1 全部 Author Resolutions，以及与八例 draft suite、H02 pilot、Codex Skill 加载和当前文档路由相关的承重边界。`git diff --check` 通过；将本 unit、模拟用户 study 及 worktree 中被其他未跟踪文档引用的现有文件加入临时 index 后，`scripts/docs_check.py` 通过（238 maintained Markdown sources、67 required routes）。正常 index 的失败仍只来自本任务外的未跟踪文档，未用其掩盖 feat-532 问题。

### Issues

无。

### Recommendations

- Pilot receipt 应保存每个角色的 expected/actual visible-file manifest 与 prompt/input envelope hash；验收时直接比较，而不是从日志反推。
- Pilot 结论必须使用 `infrastructure_pass/fail`，不要复用正式 `win/tie/loss` 或双门禁字段。

## Round 3

### Metadata

- reviewer: `/root`
- review_mode: `delta`
- mode_reason: R2 后仅把已经批准的先行 H02 pilot 显式拆成可独立实施的 M0，并新增空 milestone 骨架；实验角色、数据流、上下文边界与正式 M1/M2 设计均未改变。
- started_at: `2026-08-11T00:12:00+08:00`
- completed_at: `2026-08-11T00:12:22+08:00`
- duration: `22s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### Coverage

核对 design Changelog、先行非计分 Pilot 章节、Milestone 表、串行关系和 `M0-pilot/.gitkeep`。M0 完成条件完整覆盖既有 pilot 矩阵，且以 `formal_eligible=false`、`infrastructure_pass/fail` 明确阻止把 provisional H02 结果升级为正式结论；M1/M2 的 owner freeze 与双门禁未被削弱。

### Issues

无。

### Recommendations

无。
