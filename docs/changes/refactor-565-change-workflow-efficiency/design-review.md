# Design Review: refactor-565

## Round 1

### Metadata

- reviewer_target: `/root/design_review_565`
- review_mode: `full`
- mode_reason: 首轮独立 Gate 2；覆盖首文档、全部设计决定、现行流程入口和验证约束。
- started_at: `2026-09-16T15:00:00+08:00`
- completed_at: `2026-09-16T15:03:00+08:00`
- duration: 约 3 分钟
- reviewed_base: `983a77485e1fee651ef10c753b8ce0b493d9c77d`，主仓 `main`；受审对象是当前 unit 文档，保留既有 dirty/untracked。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING**

### Coverage 与证据

- **现状与消费者入口**：核对 `docs/development/change-workflow.md` 阶段 2/3/4、收尾与角色边界，以及 simple、原 orchestrator、design-author/review-loop、design-reviewer、code-review、verifier/handoff、product-reviewer/handoff 的实际指令。现行同一 reviewer 强制复用、所有受审产物变化使 Gate 2 失效、finder 后必须独立候选核验、Full 收尾独立 corrected-delta 均有直接文本依据；simple 已允许自主组织，本次明确主 Agent 默认实施符合现状。
- **用户约束与需求覆盖**：motivation 中减少机械拆分、避免假定缓存有效、保留独立审查和真实产品验收分别映射到 design 决策 1/2/3/6/7。方案未扩展原 worker 实施组织，未增加调度/计费系统；不涉及 CLI/SDK/Gateway/IM 产品实现。
- **独立性与职责**：未参与实现的静态 reviewer 兼任 code review 与 verification 可行，两类输出和各自 verdict 保留，产品 reviewer 仍独立于实现和静态审查。普通明确 finding 的直接举证与风险/争议项的第二人核验边界可执行；未允许作者自签。设计 Gate 2 的独立性与报告追加历史保留。
- **决定与数据流**：已有 `closure/delta/targeted/corrected-delta`、SHA 与 retained 字段足以支持范围复验及证据复用。换 reviewer 的范围、历史 finding、差异与证据交接避免把旧结论冒充新执行；证据不足扩大审查。共享测试证据仍带版本和命令，允许必要独立重跑。隔离测试配置受既有授权限制，不扩大生产或外发权限。
- **delta 与架构**：`no spec delta` 合理，受影响的权威是开发 workflow 与角色 Skills，产品包 current specs 无行为增量。没有新增模块、运行依赖、抽象或产品接口；SDK/内核职责审查要求仅改善未来流程检查。
- **milestone 与验收**：单 M1、无并行写冲突，`M1-workflow/.gitkeep` 已存在。矩阵覆盖主要减负场景和独立性反例；无产品面可跳过产品 reviewer。实际契约测试仍固定旧规则，与“仅文档”范围和退出标准冲突，见 R1-W1。
- **冲突同步面**：author/review-loop、原 orchestrator 的准入/复用/门禁/收尾文字、validation、verifier handoff、product reviewer 的配置边界均需按设计同步；`docs/changes/README.md:110` 也明确要求同一 reviewer，属于必要引用同步面。

### 历史问题闭环

首轮，无历史 findings。

### Issues

#### R1-W1 — 现有契约测试固化了被替换的 reviewer 身份规则，但设计范围未允许同步

- 位置：`design.md:9-13`、`design.md:57`；证据为 `tests/contract/test_change_workflow_documentation_contract.py:53-68`。
- 当前测试 `test_gate_two_reuses_one_reviewer_until_clean_approval` 要求 workflow 出现 Gate 2 “同一个” reviewer、后续“同一 reviewer”，并要求 design-author 写 Gate 2 “只创建”“一个”。这正是 design 决策 3/6 计划解除的强制身份约束。
- 后果：按“只修改流程文档”的范围实施，正确删除旧约束会使 M1 要求的既有契约检查失败；为让字符串测试通过而保留旧指令又会导致实际入口相互冲突。下游需要明确的最小测试同步范围，不能靠保留过时措辞蒙混通过。
- 建议：在范围与 M1 验证中明确允许同步这一现有流程契约测试，改为守护独立审查、R1 full、后续按实质变化/证据选范围、有据交接及 Approved/零阻塞问题等新规则；不扩展到产品代码或另建测试体系。未受影响的 gate matrix、lite 和 archive 契约继续保留并运行。

### Recommendations

- **R1-R1**：实施时将 `docs/changes/README.md:110` 纳入已授权的必要引用同步，并核对原 orchestrator `SKILL.md` 的“受审产物未变”、固定复用、独立发现/验证及 corrected-delta 表述。设计已允许冲突引用同步，无需新增机制或拆 milestone。

### Author Resolutions

- R1-W1: accepted。design 涉及范围和既有约束、motivation 影响范围已纳入旧固定 reviewer 身份文本测试的退役；保留既有 gate matrix，用设计情景矩阵与独立审查覆盖新规则，遵循 testing.md 不逐句锁定文案。
- R1-R1: accepted。实施同步 docs/changes/README.md 的同一 reviewer 表述，保留同一报告与历史。
## Round 2

### Metadata

- reviewer_target: `/root/design_review_565`
- review_mode: `closure`
- mode_reason: 仅核对 R1-W1 的范围/验证修订及 R1-R1 的引用同步承诺；核心流程、职责、接口、milestone 目标均未改变。
- started_at: `2026-09-16T15:03:12+08:00`
- completed_at: `2026-09-16T15:04:03+08:00`
- duration: 约 51 秒

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**

### Coverage 与证据

- retained_from: Round 1。现状 grounding、全部设计决定、独立性、架构、产品边界、no spec delta 和单 M1 可行性保持有效；本轮只补充受影响测试处置。
- 已重新读取 `motivation.md` 影响范围、`design.md` 涉及范围/既有约束/M1/验证矩阵，核对 `tests/contract/test_change_workflow_documentation_contract.py` 与 `docs/development/testing.md` 的旧测试处置要求。
- 原固定身份文本断言允许退役，其余 gate matrix 保留；用本 unit 的情景矩阵与独立静态审查检查新规则，不新增逐句文本测试。此处置解决旧约束与新目标的真实冲突，并符合 testing.md 对历史文本断言的维护要求。

### 历史问题闭环

- **R1-W1 — closed**。Author Resolution 为 accepted；design 已明确纳入受影响旧测试，M1 范围同步。原问题是“只改文档却必须通过固化旧规则的测试”不可同时满足，现在已闭合。无需按 R1 建议另写文本断言；审查新规则的情景矩阵、独立 gate 和保留的现有门禁检查足以承担本次验证。
- **R1-R1 — closed**。Author Resolution 为 accepted；`docs/changes/README.md:110` 与原 orchestrator 的相关冲突表述纳入必要同步，未另增流程或 milestone。

### Issues

无未解决 CRITICAL/WARNING。

### Recommendations

无新增建议。此结论是设计 Gate 2，不替代实施后的实际 diff、测试与独立静态验收。

## Round 3

### Metadata

- reviewer_target: `/root/design_matrix_565`
- review_mode: `delta`
- mode_reason: 用户补充并定稿模型分配、后续修复归属与派发约束；只复审决定 8–10、对应情景及其对既有角色组合的影响。
- started_at: `2026-09-16T17:33:01+08:00`
- completed_at: `2026-09-16T17:33:08+08:00`
- duration: 7 秒（最终交叉核对；此前已读取受审文档与派发入口）

### Verdict

**Approved — 0 CRITICAL / 0 WARNING**

### Coverage 与证据

- retained_from: Round 2（及其保留的 Round 1）。原有门禁独立性、证据复用、旧测试退役、产品边界、no spec delta 与单 M1 范围不变；本轮不重新评审这些已批准部分。
- `motivation.md` 最新用户原话及澄清记录与 `design.md` 决定 8 和模型情景一致：实施、复杂调查、设计 reviewer 继承主模型及 effort；spec/code/verifier 为 Terra/high，候选核验 Sol/medium，产品 reviewer Astra/low。模型策略归派发方，执行角色不自行升级；设计审查独立上下文与继承模型并不冲突。
- 决定 9 及后续反馈情景覆盖审查、验收、CI、用户反馈：后续修复均由主 Agent 完成，既不新派也不唤醒 worker；复杂调查不能成为外包修复的通道，独立定向复验仍保留。首轮并行实施的有限授权与该限制可同时执行。
- 决定 10 补齐实际派发条件：读取当前 harness 和可用模型，固定档显式传参，继承档使用主会话实际配置，复用核对角色与配置，不能覆盖时精简交接，不可用时报告并由用户决定替代。当前工具支持 model/effort，并要求显式覆盖模型时不用完整历史 fork，现有 Codex 适配已提供独立审查的中性事实包方式，具备可执行路径。
- code review 与 verifier 同属 Terra/high，仍可合并派发；设计 reviewer 与静态角色档位不同时，决定 10 禁止通过合并静默换档，解决既有 workflow 允许静态 reviewer 兼任 Gate 2 的影响。实际入口核对了 `change-workflow.md`、两种 orchestrator、`references/validation.md` 与 `references/codex-execution-notes.md`；其中现行“深入探索时派 worker”、默认继承和兼任文字均属设计已授权的必要引用同步面，实施检查须覆盖。
- 新情景覆盖固定档、继承档、候选/产品档、后续修复、旧角色不匹配及型号不可用；不引入运行代码、产品接口或新的记录系统，M1 仍能承载该增量。

### 历史问题闭环

- R1-W1、R1-R1 保留 Round 2 的 closed；本次变化未重新触发。

### Issues

无未解决 CRITICAL/WARNING。

### Recommendations

无新增建议。本轮仅批准上述设计增量；实际派发入口的一致性仍由实施后的独立静态审查核实。
