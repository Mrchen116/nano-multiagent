# Design Review: feat-485

## Round 1

### Metadata

- reviewer: `/root/design_reviewer_485`
- review_mode: `full`
- mode_reason: first review; no prior Round or retained evidence exists, so R1 rebuilt all five atom classes and ran all four architecture-attack angles.
- started_at: `2026-07-27T18:57:13+08:00`
- completed_at: `2026-07-27T19:05:50+08:00`
- duration: `8m37s`
- code_baseline: `2eb7103913d857e15c2e3ff8fda804aae9d66d11`
- artifacts:
  - `spec.md`: `sha256:014b6525d53e5e1761f8eebab4ba2015461f0860e24ae7b697ab7bd93efa4db0`
  - `design.md`: `sha256:3ce5a497ffb0d343513caa3489b6ae4718b7529314b1eff2d0bacc298a6bdfd2`
  - `M1-skill-contract/.gitkeep`: `sha256:01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`
- absent_artifact_classes:
  - `prototype.html`: not applicable; no frontend scope.
  - delta-spec: not applicable; the unit changes repository workflow rather than kernel/IM/Gateway/CLI behavior.

### Verdict

Issues Found — 2 CRITICAL / 3 WARNING

### 核实台账

#### 1. 现状断言与生产流程

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| G1：design-author 每轮创建全新 reviewer，禁止复用 | 从 design 阶段真实入口追 §6 调度 | ✓ 当前唯一默认调度明确要求“每一轮”启动全新 subagent，并禁止复用上一轮 reviewer（`.claude/skills/change-design-author/SKILL.md:561-567`）。 |
| G2：任意返工都强制全量复审 | 追非通过报告后的循环分支 | ✓ 无论是否改产物，当前 §6.3 都要求全新 reviewer 从头执行完整 review（`.claude/skills/change-design-author/SKILL.md:583-589`）。 |
| G3：固定报告路径只保留最新结果 | 追 author 的停止条件与输出契约 | ✓ 当前规则明确覆盖旧报告、只保留最新完整报告且不建轮次台账（`.claude/skills/change-design-author/SKILL.md:567,591-597,641`）。 |
| G4：reviewer 只有单次报告格式，无 Round/mode/time/hash | 逐段检查 reviewer 输出与落盘契约 | ✓ 当前格式从结论直接进入台账/进攻/Issues/Recommendations，落盘只描述一份完整报告，没有 round metadata 或 mode（`.claude/skills/change-design-reviewer/SKILL.md:164-210`）。 |
| G5：feat-475 把 fresh/full/overwrite 固化成历史需求 | 对照 related unit 的 Requirement 与非目标 | ✓ feat-475 要求修订后换新 reviewer 全量复审，并把历史报告列为非目标（`docs/changes/feat-475-design-review-loop/spec.md:62-73,110-123,140-145`）；feat-485 作为后续 unit 显式覆盖是正确做法。 |
| G6：orchestrator 已有稳定 agent 与选择性复验相邻模式 | 追 orchestrator 的稳定 name、delta selection 和热上下文恢复 | ✓ 稳定 name/ID 与 `SendMessage` 复用在 `.claude/skills/change-orchestrator/SKILL.md:32-34`；`retained/closure/delta/full` 路由及升级条件在 `:568-605`；热 worker 恢复在 `:611-637`。 |
| G7：本 unit 不触及产品 runtime 或四包行为契约 | 核 planned write set 与跨包权威 | ✓ 决策 6 的 planned writes 全是 skills/workflow/docs/tests（`design.md:151-161`）；`SPEC.md:153-171` 的四包职责和依赖方向均不受影响，`no spec delta` 成立。 |
| G8：真实 Gate 2 消费者是 change-orchestrator 启动门 | 从 author 交接正向追到 worker 派发前检查 | ✗ author 之后的真实消费者只检查 design 模板、Unit branch、Milestone 字段和空目录（`.claude/skills/change-orchestrator/SKILL.md:93-122`），完全不读 `design-review.md`、Verdict 或 artifact hashes；而本设计的 write set 未包含 orchestrator（`design.md:151-161`）。见 R1-C2。 |
| G9：主仓在途 canonical workflow 当前仍写 fresh reviewer | 只读核对主仓未跟踪文档及其权威归属 | △ 主仓在途 `docs/development/change-workflow.md:86-94` 仍要求每轮 fresh/full；同文件 `:156-163` 声明 workflow 与 skills 必须同变更同步。设计已识别该并发文档（`design.md:161,192`），但合并顺序仍只是条件句，见 R1-R1。 |

#### 2. 关键决策

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| D1：Reviewer 以 unit 为生命周期，R1 创建、后续唤醒 | 核拍板、failover、既有 harness seam 与 spec 驱动 | ✓ R1 独立上下文、稳定 target、后续只恢复、客观不可恢复才替换且替代者 full 均已拍死（`design.md:59-65`），覆盖 spec 的三个 reviewer 生命周期场景（`spec.md:38-57`），并复用 orchestrator 已验证的稳定 agent seam。 |
| D2：Reviewer 自主选择 closure/delta/full | 核 owner、模式边界、升级条件和 author 派发包 | △ owner 与强制 full 条件清楚（`design.md:67-88`），但轻量 mode 如何与 reviewer 当前“每个 atom 必须有一行、四角度逐个走”的铁律共存没有闭合；不同 worker 会实现成“仍全量跑”或“静默省略未跑角度”。见 R1-W1。 |
| D3：design-review.md 以 Round 为不可覆盖一级单元 | 核顺序、稳定 ID、双 writer 权限与历史纠错 | ✓ Round 结构、reviewer 正文不可改、author 只追加 Resolution、后续纠错进新 Round、稳定 ID 均明确（`design.md:90-133`），覆盖按轮组织的用户拍板（`spec.md:23-24,79-101`）。 |
| D4：每轮记录时间与受审快照 | 核时钟语义、hash 算法、full/light 差异及增删检测 | ✗ 时间契约清楚，但轻量轮只要求“至少列全部变化文件”，不是完整受审集合（`design.md:135-139`）；这无法支撑最新 Round 的全体产物失效判断。示例也只列 `design.md`（`:94-108`）。见 R1-C1。 |
| D5：最新完成 Round 是 Gate 2 权威 | 核 Verdict、author 判真、snapshot equality 与实际 consumer | ✗ 条件文字完整（`design.md:141-149`），但它只比较最新 Round 已记录的子集，且真实 orchestrator gate 不消费这些条件。R1-C1 与 R1-C2 共同使该决策无法落地。 |
| D6：同步已提交入口，不复制主仓在途文档 | 核用户 worktree 约束、planned files 与未来 canonical | △ 不触碰主仓在途文件符合 spec（`spec.md:118-123,132-138`），且列出当前分支入口（`design.md:151-161`）；但 planned set 漏了真实 Gate 2 consumer，见 R1-C2。未来 canonical 的双向 merge-order 约束建议补强，见 R1-R1。 |

#### 3. 首文档约束

##### 3.1 用户场景与澄清记录

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| U1：连续返工的主要浪费是 reviewer 冷启动与重复取证 | 对照当前 author/reviewer 调度和实际报告输入 | ✓ 当前每轮 fresh/full/ignore prior report 的组合确实重读全量材料（author `SKILL.md:561-589`）；设计以稳定 reviewer + routed mode 正面消除这部分成本（`design.md:11-42`）。 |
| U2：一个 Gate 2 闭环只创建一个 reviewer，由 reviewer 决定深度 | 对照总览、D1/D2 与接口 | ✓ 总览和 Author→reviewer 数据流一致，author 只交修订事实、不传 mode（`design.md:11-42,59-88,165-177`）。 |
| U3：同一报告按 Round 留全历史，Resolution 紧邻来源轮 | 对照 D3、双 writer 数据流与风险 | ✓ 单文件 append-only、Round 内聚、稳定 ID 与 author 追加权限闭合（`design.md:90-133,169-181,185-194`）。 |
| Q1：永远复用 reviewer，且 reviewer 自主路由 mode | 核是否被降级或另设轮换 | ✓ D1/D2 精确采用用户原话，仅客观不可恢复时 failover（`spec.md:21-22`; `design.md:59-88`）。 |
| Q2：历史按轮次组织，并记录每轮时间 | 核报告 schema 与时间字段 | ✓ D3/D4 以 `## Round N`、started/completed/duration 实现（`spec.md:23-24`; `design.md:90-139`）。 |
| Q3：独立 worktree，主仓不动 | 核 branch、实际 git 状态和 planned integration | ✓ design 声明 `codex/design-review-round-history`（`design.md:3-5`）；R1 期间受审文件只存在该 worktree，主仓 dirty/untracked 工作未被写入。 |

##### 3.2 Requirement 与每个 Scenario

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| Req 1：一个 Gate 2 闭环固定复用同一 reviewer | 对照 D1 与流程图 | ✓ `design.md:11-42,59-65` 给出唯一 stable reviewer owner 和 failover。 |
| Req 1 / 首轮建立独立 reviewer | 核 R1 隔离与稳定标识保存 | ✓ R1 不继承 author 对齐上下文并保存 stable target（`design.md:61-63`）。 |
| Req 1 / 修订后再次送审 | 核恢复机制与历史上下文 | ✓ R2+ 强制使用 `SendMessage`/`followup_task`/等价恢复机制（`design.md:61`），不新派实例。 |
| Req 1 / 固定 reviewer 客观不可恢复 | 核替换留痕与检查深度 | ✓ 旧/新标识、原因和替代者首轮 full 已拍死（`design.md:65`）。 |
| Req 2：Review mode 由 reviewer 自主路由 | 对照 D2 owner 与 author 禁区 | △ owner/路由条件覆盖，但 scoped audit contract 尚有 R1-W1。 |
| Req 2 / Author 提交返工结果 | 核派发包字段和禁止字段 | ✓ round/unit/target/changed artifacts/resolutions/task 齐，明确不含 review_mode 或期望结论（`design.md:69-78,165-167`）。 |
| Req 2 / Reviewer 选择检查深度 | 核三 mode 判据与 mode_reason | ✓ 三 mode 的适用边界和最低范围已给出，Round metadata 有 `review_mode`/`mode_reason`（`design.md:82-88,99-108`）。 |
| Req 2 / 轻量检查发现影响扩大 | 核升级 trigger 与 author 权限 | ✓ 新副作用、未声明 delta、无法封闭、新阻断均触发同轮扩围，author 不得降级（`design.md:88`）。 |
| Req 3：报告按轮次保留完整历史 | 对照 D3 与 append data flow | ✓ 单文件、顺序 append、旧 Round immutable（`design.md:90-133,169-181`）。 |
| Req 3 / 完成一轮 review | 核 append 而非 overwrite | ✓ reviewer 校验 round=N+1 后一次性 append 完整 Round（`design.md:171-177`）。 |
| Req 3 / 每轮问题独立成组 | 核 section 内聚与稳定 issue ID | △ schema 有 ledger/attack/issues/recommendations 和 Rn-C/W/R ID（`design.md:94-133`），但轻量轮对未重跑维度的表示不明确，见 R1-W1。 |
| Req 3 / Author 处理一轮问题 | 核 Resolution owner、状态和原文保护 | ✓ author 对每个 Issue/Recommendation 判真并只追加 accepted/rejected/escalated Resolution，不回写 reviewer 文本（`design.md:125-133,179-181`）。 |
| Req 3 / 记录 review 时间 | 核 timezone、开始/完成时点和 wall duration | ✓ started_at 在读输入前、completed_at 在落盘前，均 ISO 8601 显式时区，duration 为 wall-clock（`design.md:135-139`）。 |
| Req 4：Gate 2 只认最新轮次与其受审快照 | 从 author 规则追到 orchestrator consumer | ✗ 规则未形成完整 snapshot，也未接到真正放行实施的 consumer；见 R1-C1、R1-C2。 |
| Req 4 / 最新轮次通过 | 核 Approved/count/author judgment/current snapshot | ✗ Verdict 和 author judgment 有落点，但 latest Round 可能只含 changed subset，orchestrator 又不检查（`design.md:139-149`; orchestrator `SKILL.md:93-122`）。 |
| Req 4 / 通过后受审产物再次变化 | 构造 R1 full→R2 closure→未列 spec/prototype/skeleton 变化 | ✗ R2 只列 changed files 时，R2 后另一个受审产物变化不在最新 hash 集内，无法触发失效；新增/删除 milestone path 也没有集合相等规则。见 R1-C1。 |
| Req 5：本次修改与主仓工作区隔离 | 核实施 branch 与主仓 dirty state | ✓ branch/worktree 声明、D6 和风险段都不复制主仓在途文件（`design.md:3-5,151-161,192`）。 |
| Req 5 / 在独立 worktree 实施 | 核当前实际状态 | ✓ worktree 为 `codex/design-review-round-history`，本 unit 目录仅在该 worktree 未跟踪；主仓现有修改未被纳入。 |

##### 3.3 范围与非目标

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| In-1：author 生命周期、返工派发、Gate 2 判据 | 查 D1/D2/D5 与 planned write | △ 生命周期和派发覆盖；Gate 2 缺真实 consumer，见 R1-C2。 |
| In-2：reviewer mode、Round/time/append contract | 查 D2-D4 与 report schema | △ 主体覆盖；轻量 mode 的 scoped ledger/attack 表示缺位，见 R1-W1。 |
| In-3：已提交 workflow/agent routing 入口 | 查 D6、AGENTS、docs/changes 与 canonical migration | ✓ 当前已提交入口均列入；主仓在途 canonical 通过 rebase 条件处理（`design.md:151-161`），建议把 merge-order 变成硬 gate，见 R1-R1。 |
| In-4：文档契约测试 | 查 Runbook、M1 worker 轨与风险 | ✓ contract test 同时覆盖 append-only 与协议字段（`design.md:188-203,207-211`），测试具体实现留给 worker。 |
| Non-1：不改变核实维度、严重度、架构进攻标准 | 对照 D2 与当前 reviewer 铁律 | △ 设计没有改变定义或严重度，但没有明确 light mode 是“保留未失效证据”还是“放弃必跑维度”，容易让实现事实改变标准。见 R1-W1。 |
| Non-2：reviewer 不写 design/code/其他受审产物 | 核 writer 权限 | ✓ reviewer 只 append report Round；author 才改设计并追加 Resolution（`design.md:169-181`）。 |
| Non-3：不定期轮换 reviewer | 核 D1 failover | ✓ 仅客观不可恢复时留痕替换（`design.md:65`）。 |
| Non-4：不引数据库或每轮一文件 | 做删除测试 | ✓ 单 Markdown 日志足够，设计没有新增存储/索引层（`design.md:90-133,190`）。 |
| Non-5：不复制主仓未提交 docs | 核实际 write set | ✓ D6 明确禁止复制，并只在 main 已引入后 rebase 归并（`design.md:151-161`）。 |
| Non-6：不改产品运行时代码 | 核 M1 range 与 no-delta | ✓ M1 只涉及 workflow skills/docs/tests，`no spec delta`（`design.md:205-215`）。 |

#### 4. Delta-spec

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| no spec delta | 核是否改变 kernel/IM/Gateway/CLI 消费者可观察行为 | ✓ 变化对象是仓库开发 agent workflow，不是四个产品包；同步 current workflow 文档而非产品 delta-spec 是正确落层（`design.md:151-161,213-215`; `SPEC.md:153-171`）。 |

#### 5. Milestone

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| M1-skill-contract：单一 Gate 2 协议切片 | 核垂直性、拆分理由、范围、目录、两轨退出和下游 schema | △ 单 M1 是正确垂直切片，目录数量匹配且两轨退出存在（`design.md:205-211`）；但表没有下游要求的独立 `ID`/`标题` 字段，`M1-skill-contract` 实际是 milestone_dir 而不是 `<unit_id>-M<N>` ID。见 R1-W3。 |

### 整体判断

| 维度 | 结论 + 证据 |
|---|---|
| 上层可读性 | ✓ 总览、流程图和 sequence diagram 清楚串起“stable reviewer → reviewer-owned mode → append-only rounds”（`design.md:9-42`）。 |
| 接口与数据流 | ✗ author/reviewer/report 三段闭合，但 report snapshot 没覆盖完整 artifact set，且 report→orchestrator Gate 2 消费边缺失；见 R1-C1/R1-C2。 |
| 常规完整性 | ✓ 标题、对齐行、branch、空 Changelog、风险与回退、no delta 均齐；无模板注释/TBD。 |
| 命名与图 | ✓ stable reviewer、review_mode、Round 在图、决策和接口中一致。 |
| 风险与回退 | △ 锚定、低报 delta、旧轮改写、增长、failover 均有实质应对；主仓在途 canonical 只覆盖“它先合入 main”的顺序，反向顺序建议补硬 gate（R1-R1）。 |
| Runbook | ✗ 已写“无常驻服务/无仓外前置”，但缺当前 author skill 强制的 `Review 驱动方式`（`.claude/skills/change-design-author/SKILL.md:507-513`），且 M1 `[reviewer]` 轨没有可照搬的真实 workflow 旅程。见 R1-W2。 |

### 架构进攻

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | D1/D2：lifecycle 属 author、深度判断属 reviewer | ✓ 归属自然：author 有全局编排和修订权，reviewer 有独立证据与影响判断；没有把 mode 决策泄回 author。 |
| 归属 | D5/D6：Gate 2 authority 与实际 orchestrator consumer | ✗ authority 只写在 producer 侧，真正启动实施的 orchestrator 不消费它。长期代价是任何跨会话启动或 design-revision resume 都能绕过 Round/hash gate，让“最新快照”成为无人执行的纸面规则。→ R1-C2。 |
| 该不该存在 | Stable reviewer | ✓ 删除测试不通过：删掉就恢复每轮冷启动，直接失去用户要的时间/token收益。 |
| 该不该存在 | Round history + stable IDs | ✓ 删除测试不通过：删掉会失去逐轮问题、Resolution、耗时和复盘证据；单文件满足需求，无需数据库或 per-round 文件。 |
| 该不该存在 | closure/delta/full 三 mode | ✓ 三档分别覆盖非语义修正、有界语义 delta、高风险/不可界定变化；复用既有词汇而非另造策略层。 |
| 深还是浅 | 最新 Round artifact hashes | ✗ 当前接口只暴露“本轮变化文件”，却声称隐藏完整 Gate 2 snapshot 复杂度；接口比它承诺的 invariant 浅。长期会产生 silent stale approval，且新增/删除/重命名 artifact 无法可靠失效。→ R1-C1。 |
| 深还是浅 | light-mode 审查记录 | ✗ 只给最低检查范围，没给未重跑 atom/angle 的 retained evidence contract；长期会在“省 token”和“保留审查标准”之间由每个 agent 临场摇摆，报告也无法证明为什么没重跑。→ R1-W1。 |
| 治本还是补丁 | 冷启动成本 | ✓ 以 unit-scoped reviewer 保留上下文，并把 mode route 交给掌握证据的 reviewer，直接处理重复取证根因，不是缩短 prompt 或硬限轮数。 |
| 治本还是补丁 | 历史可追溯 | ✓ append-only Round + author Resolution 分权解决覆盖丢历史的根因，并保留 reviewer 原话。 |
| 治本还是补丁 | workflow acceptance | ✗ Runbook 只列静态校验，没有定义如何真实观察“同一 target 被唤醒、reviewer 自主选 mode、历史 append、主仓不变”。长期会让产品 reviewer 退化成读 skill 文本/跑 contract test，无法证明用户实际看到的新 lifecycle。→ R1-W2。 |

### Issues

- [R1-C1][CRITICAL] [决策 4 / 决策 5 / Gate 2 快照] 最新 Round 的 artifact snapshot 不是完整、可比较的受审集合。D4 允许 `closure`/`delta` 只列“全部变化文件”（`design.md:139`），D5 却只拿最新 Round 已记录的 hashes 与当前文件比较（`:143-149`）。构造一个合法流程：R1 full 记录 spec/design/prototype/delta/skeleton，R2 closure 只改并记录 design，R2 Approved 后 spec 或 milestone skeleton 被修改/新增；最新 Round 没有它的 hash，Gate 仍可能通过，直接违反 `spec.md:112-116`。不改会让 stale design 被派 worker 实施。请把 `changed_artifacts`（路由事实）与 `reviewed_artifact_manifest`（Gate 事实）分开：每个 Round 都记录完整受审集合的路径 + sha256，未变项可显式继承上轮但必须物化到本轮 manifest；Gate 比较集合和值都相等，检测新增、删除、重命名，并明确包含首文档、design、所有 delta、prototype 和 Milestone skeleton。

- [R1-C2][CRITICAL] [决策 5 / 决策 6 / 生产 Gate 2 consumer] 方案没有把新 Gate 2 authority 接到真正放行实施的 `change-orchestrator`。当前 orchestrator 的 §2.1 只检查 design 结构和空目录（`.claude/skills/change-orchestrator/SKILL.md:93-122`），全文件没有读取 `design-review.md`/Verdict/hash 的启动门；D6 的 planned write set 又漏掉该 skill（`design.md:151-161`）。不改时，author 退出后只要有人改了受审产物并直接启动/恢复 orchestrator，worker 仍会被派出，spec 要求的“hash 变化立即过期并新增 review”无人执行。请把 `change-orchestrator`（或一个由 author 与 orchestrator 共同调用的唯一 Gate 2 validator）纳入边界：full 模式启动及 design 修订后的 resume 都必须验证最后完成 Round 为 Approved、0C/0W、完整 manifest 与当前集合/内容一致；否则退回同一 stable reviewer 的下一 Round。

- [R1-W1][WARNING] [决策 2 / Round 核实台账与架构进攻] 轻量 mode 和现有 reviewer 铁律之间缺少明确的 retained-coverage 契约。当前 reviewer 要求每个枚举 atom 都有证据行，并要求四角度逐个走、无发现也不能省略（`.claude/skills/change-design-reviewer/SKILL.md:48-58,137-150,183-189`）；新设计只说 closure 查旧 issue/直接依赖、delta 查受影响角度（`design.md:82-88`），同时 spec 又把每轮台账和架构进攻作为必有内容并禁止改变标准（`spec.md:86-90,132-134`）。不改时，worker 要么保留全量规则让 closure 名存实亡，要么静默删角度让报告不能证明审查标准未降。请拍死 light Round 的输出：列本轮重查 atoms/angles，并对未重跑部分逐项或按可审计分组记录 inherited-from Round/hash + 本次 delta 未失效的证据；无法说明 retained 边界就升级 full。严重度和四角度定义保持不变。

- [R1-W2][WARNING] [Runbook for Reviewer / M1 reviewer 轨] Runbook 没有声明必填的 `Review 驱动方式`。当前 author self-check 明确要求说明真实端到端如何驱动，否则 reviewer 会即兴（`.claude/skills/change-design-author/SKILL.md:507-513`）；本设计只有“无服务/无前置 + 静态验证”（`design.md:196-203`），M1 却要求 reviewer 证明 stable target、mode routing、Round history、时间和主仓隔离全部成立（`:207-209`）。不改时，下游产品 reviewer 很可能只读 skill/跑文本 contract test，无法证明用户实际看到同一 reviewer 被唤醒及报告 append。请给出可照搬的 workflow 旅程和观察点（至少 R1→author Resolution→R2 same target、reviewer 自主 mode、旧 Round byte-preserved、hash invalidation、主仓 status 不变），并说明用哪个可控 fixture/unit 驱动。

- [R1-W3][WARNING] [Milestone 表] M1 行不符合现有下游字段协议。design 表把 `M1-skill-contract` 放在 `Milestone` 列、另设“价值切片”（`design.md:205-209`），但 author 模板/契约要求独立 `ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准`，ID 为 `<unit-id>-M<N>`（`.claude/skills/change-design-author/SKILL.md:393-402`; asset `design.md:130-145`）；orchestrator/worker 派发要求 `milestone_id: <unit_id>-M<N>` 与 `milestone_dir: M<N>-<title>` 分离（orchestrator `SKILL.md:284-300`; worker `SKILL.md:63-76`）。不改会让严格 orchestrator 拒绝 Gate 2，或被迫猜 `M1-skill-contract` 是 ID 还是目录。请改为 `ID=feat-485-M1`、`标题=skill-contract`、`milestone_dir=M1-skill-contract`，并把修复 R1-C2 后新增的实际 skill/doc 范围写进范围列。

### Recommendations

- [R1-R1] [决策 6 / 集成顺序] 把“若 main 已引入 docs/development 再归并”升级成对称的 merge-order gate：要么主仓文档重构先落地、feat-485 rebase 后同步 `docs/development/change-workflow.md`；要么 feat-485 先落地时，文档重构分支必须 rebase feat-485 后才能提交。否则后落地的一方可能重新引入 `fresh reviewer`，与 skills 冲突并触发 canonical workflow 的暂停规则（主仓在途 `docs/README.md:62-70`; `docs/development/change-workflow.md:156-163`）。

- [R1-R2] [Runbook 最窄验证] 将 `skill-creator/scripts/quick_validate.py` 改成当前环境可解析的完整调用或仓库 wrapper；仓库内不存在该相对路径，当前脚本实际位于 `/Users/czj/.codex/skills/.system/skill-creator/scripts/quick_validate.py`。这不改变架构，但可避免 worker/reviewer照抄命令即失败。

### Author Resolutions

- [R1-C1] accepted — 将路由用的 `changed_artifacts` 与 Gate 用的 `reviewed_artifact_manifest` 分离；任意 mode 的每个 Round 都物化完整、排序后的受审路径集合与 sha256，集合比较覆盖新增、删除和重命名。修改 `design.md` 决策 3-5、接口、风险、Runbook，并强化 spec 的 Gate 场景。
- [R1-C2] accepted — 把 `.claude/skills/change-orchestrator/SKILL.md` 纳入实现范围；Full unit 首次派 worker 和 design-revision resume 前，orchestrator 必须独立核最新 Round、0C/0W 与完整 manifest，不成立就退回 design-author 复用同一 reviewer。修改 `spec.md`、`design.md` 的总览、决策 5-6、接口、风险、Runbook 和 Milestone。
- [R1-W1] accepted — 为 `closure`/`delta` 增加 `Coverage` 契约：本轮重查项列 `rechecked`，未重跑项按可审计分组列 `retained`、来源 Round/hash 与未失效依据；无法证明就扩围或升级 full。审查维度、严重度和四角度定义不变。修改 `spec.md` mode 场景与 `design.md` 决策 2-3。
- [R1-W2] accepted — 以 feat-485 自身的 R1→Resolution→同 reviewer R2 作为 workflow canary，Runbook 增加稳定 target、reviewer-owned mode、历史前缀、完整 manifest 失效与主仓状态隔离的真实观察步骤。
- [R1-W3] accepted — Milestone 表改为既有 `ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准` 协议，使用 `ID=feat-485-M1`、`标题=skill-contract`、`milestone_dir=M1-skill-contract`，并补入 orchestrator 范围。
- [R1-R1] accepted — 将并发文档重构的集成顺序从条件说明升级为双向 merge-order gate，后合入的一方必须 rebase 并消除旧 `fresh/full/overwrite` 口径。
- [R1-R2] accepted — Runbook 改为当前环境可执行的 repo venv Python + skill-creator validator 绝对路径，并扩为三个受影响 skill。

## Round 2

### Metadata

- reviewer: `/root/design_reviewer_485`
- review_mode: `full`
- mode_reason: `spec.md` 新增轻量轮 retained-evidence 与 orchestrator 启动/恢复场景，`design.md` 同时改变完整 manifest、跨 skill Gate 2 consumer、数据流和 M1 范围；这些变化命中需求、共享契约和跨模块接口的 full 条件，因此本轮没有把检查限制为旧 issue closure。
- started_at: `2026-07-27T19:12:20+08:00`
- completed_at: `2026-07-27T19:16:18+08:00`
- duration: `3m58s`
- code_baseline: `2eb7103913d857e15c2e3ff8fda804aae9d66d11`
- prior_history_sha256: `871abee334564e350153b7c5d645a781942d8c26cade09387653302f1fc5c600`
- prior_history_bytes: `25616`
- reviewed_artifact_manifest:
  - `M1-skill-contract/.gitkeep`: `sha256:01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b`
  - `design.md`: `sha256:d5c405fd8326c8fd9a5ce9c7a7f31d93c7749bba7e97510e7c7621eee39f24b2`
  - `spec.md`: `sha256:5296c9a08f18f115559561dcaf82348ebe40866ca1337e54a69d9926290abd20`
- absent_artifact_classes:
  - `prototype.html`: not applicable; no frontend scope.
  - delta-spec: not applicable; this unit changes repository workflow rather than kernel/IM/Gateway/CLI product behavior.

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### Coverage

| 分组 | 覆盖内容 | 结论 + 证据 |
|---|---|---|
| `rechecked` | Round 1 全部 2 CRITICAL、3 WARNING、2 Recommendation 及 author resolutions | 逐项从当前 spec/design、真实 skill 消费入口、模板和主仓在途 canonical workflow 重新取证；7 项均闭合，见“历史问题闭环”。 |
| `rechecked` | 五类承重原子 | 完整重建现状断言、6 个关键决策、首文档全部用户场景/Scenario/范围与非目标、no-delta 判断、单 M1；未只复查改动段。 |
| `rechecked` | 生产数据流与消费边 | 正向追 `design-author → stable reviewer → design-review.md → change-orchestrator → worker`，并反查当前 orchestrator 启动门、稳定 agent seam、resume 分支和 worker 输入契约。 |
| `rechecked` | 四角度架构进攻 | 对稳定 reviewer、三档 mode、append-only Round、完整 manifest、orchestrator Gate、单 M1 分别执行归属、删除测试、深浅边界、治本/补丁检查。 |
| `rechecked` | 历史完整性与 worktree 隔离 | 写入前报告恰为 `25616` bytes 且 sha256 与上列一致；当前受审文件只位于指定 worktree，主仓在途 canonical 文档仅作为只读冲突证据。 |
| `retained` | 无 | 本轮 mode 为 `full`；没有从 Round 1 继承而未重跑的 atom 或 architecture-attack angle。 |

### 历史问题闭环

| 历史项 | author 处理 | 本轮独立核实 | 状态 |
|---|---|---|---|
| R1-C1：最新 Round manifest 不完整 | accepted | `changed_artifacts` 已降为路由事实；任意 mode 都物化完整、排序的首文档/design/delta/prototype/skeleton manifest，Gate 比较路径集合与 sha256 并检测增删改名改内容（`design.md:161-168`）；spec 同步完整集合与失效场景（`spec.md:109-122`）。 | closed |
| R1-C2：真实 orchestrator 不消费 Gate 2 | accepted | orchestrator 已进入架构图、决策、planned write set、数据流与 M1（`design.md:25,43-49,170-191,218-220,254-258`）；首次派 worker和 design-revision resume 都是明确消费点（`:180`），spec 新增可观察 Scenario（`spec.md:124-128`）。 | closed |
| R1-W1：轻量 mode 缺 retained coverage | accepted | `Coverage.rechecked/retained` 的来源 Round/hash/未失效依据、扩围与 full 升级条件均已拍死（`design.md:99-106`），并进入 spec Scenario（`spec.md:73-83`）。 | closed |
| R1-W2：Runbook 缺真实 workflow drive | accepted | feat-485 自身成为 R1→Resolution→同 target R2 canary，观察稳定 target、reviewer-owned mode、前缀字节、完整 manifest 失效和主仓隔离（`design.md:237-250`）。 | closed |
| R1-W3：Milestone ID/title/schema 错位 | accepted | 表头恢复六字段，`ID=feat-485-M1`、`标题=skill-contract`、`milestone_dir=M1-skill-contract`，范围含三个 skill 与消费入口（`design.md:252-258`），与 author asset 和 worker 输入契约一致。 | closed |
| R1-R1：并发 canonical 文档合并顺序 | accepted | 决策 6 已改为双向 merge-order hard gate，后合入方必须 rebase 并消除旧口径（`design.md:193-196`）。 | closed |
| R1-R2：validator 路径不可解析 | accepted | Runbook 使用 repo venv Python 和当前机器存在的 skill-creator validator 绝对路径，并覆盖三个受影响 skill（`design.md:247-250`）；本轮只读确认解释器与脚本路径均存在。 | closed |

### 核实台账

#### 1. 现状断言与生产流程

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| G1：当前 design-author 仍是 fresh reviewer/full/overwrite | 从 design 阶段真实入口追返工循环与退出条件 | ✓ 已提交基线仍要求每轮创建全新 reviewer、完整重审并覆盖旧报告（`.claude/skills/change-design-author/SKILL.md:561-597`），所以本 unit 的目标不是重复已有能力。 |
| G2：当前 reviewer 的五类 atom 与四角度标准不能因 light mode 降级 | 核 reviewer 铁律和报告输出 | ✓ 每个枚举 atom 必须有证据行，四角度均须执行且无发现也不能省略（`.claude/skills/change-design-reviewer/SKILL.md:48-58,137-150,183-210`）；D2 用 retained evidence 保留标准而非删除维度。 |
| G3：真实实施放行点是 orchestrator 的 Full 启动门 | 从模式判定追到首次 worker dispatch | ✓ 当前 §2.1 在派 worker 前只核 design 结构和 milestone skeleton，尚未读 design review（`.claude/skills/change-orchestrator/SKILL.md:93-122,280-300`）；把该 skill 纳入本 unit 是必要生产落点。 |
| G4：仓库已有稳定 agent 与选择性复验 seam | 核稳定 name、SendMessage、delta/full 路由和热上下文 | ✓ orchestrator 已用稳定 name/ID（`.claude/skills/change-orchestrator/SKILL.md:32-34`）、按 delta 选 retained/closure/delta/full（`:568-605`）并恢复热 worker（`:611-637`）；方案复用机制词汇但把 design mode owner 留给 reviewer。 |
| G5：design revision resume 是独立绕过风险 | 追 revise-design escalation 与恢复入口 | ✓ 当前升级会退出并等待人修订 design 后重启 orchestrator（`.claude/skills/change-orchestrator/SKILL.md:645-679`）；因此只守首次启动不足，D5 同时守 resume 是正确边界。 |
| G6：feat-475 是被本 unit 显式覆盖的历史规则 | 对照 related unit 与现状证据 | ✓ 旧 fresh/full/overwrite 是已有流程而非误读；spec 的 Related 与 design 现状表显式声明后续覆盖（`spec.md:3-5`; `design.md:52-64`）。 |
| G7：主仓在途 canonical workflow 与目标口径冲突 | 只读核 current docs 权威与冲突规则 | ✓ 主仓在途 `docs/development/change-workflow.md:86-94` 仍写 fresh/full，`docs/README.md:62-70` 要求 workflow/skill 冲突时暂停；D6 的双向 merge gate 是必要集成约束。 |
| G8：本 unit 不改变四包 runtime 或产品行为 | 核 planned writes、M1 scope 和跨包 spec | ✓ 写集只有 skills、workflow routing、unit docs 与契约测试（`design.md:182-191,252-262`），没有 `src/` 或产品 API，no delta-spec 正确。 |
| G9：当前 artifact 集与 worktree 声明一致 | 枚举 unit 文件、核 branch/baseline/status | ✓ 受审集合为 spec、design、一个 `.gitkeep` skeleton；无 prototype/delta；HEAD 为 `2eb7103`，unit 只在 `codex/design-review-round-history` worktree 未跟踪，符合隔离设计。 |

#### 2. 关键决策

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| D1：Reviewer 以 unit 为生命周期 | 核 R1 隔离、R2+ 恢复、failover 与记录 | ✓ stable target、禁止便利性重建、客观不可恢复时留原因/旧新标识且替代者 full 均明确（`design.md:68-74`），覆盖 spec 三个生命周期 Scenario（`spec.md:38-57`）。 |
| D2：Reviewer 自主路由 closure/delta/full | 核 owner、输入禁区、边界、Coverage 与升级 | ✓ author 只传事实；三 mode 条件互斥可判；轻量轮记录 rechecked/retained，证据不能继承时扩围/full（`design.md:76-106`），覆盖 `spec.md:59-83`。 |
| D3：Round 是 append-only 一级单元 | 核 schema、writer 权限、稳定 ID 和纠错路径 | ✓ 单文件顺序追加，reviewer 正文 immutable，author 只加 Resolution，纠错进入新 Round；schema 含 metadata/verdict/coverage/ledger/attack/issues/recommendations（`design.md:108-155`）。 |
| D4：每轮完整 materialize 受审快照 | 核 routing/Gate 分离、集合边界、hash 与历史前缀 | ✓ manifest 在所有 mode 都完整生成，路径集合和值都比较并覆盖新增/删除/重命名/内容变化；R2+ 另存前缀 bytes/hash（`design.md:157-168`）。 |
| D5：最新完成 Round 是 Gate 2 authority | 核三项通过条件、stale 处理与独立 consumer | ✓ Approved+0C/0W、author findings judgment、当前完整 manifest 三项齐；orchestrator 在首次 dispatch 与 design-revision resume 重核，不成立即退回 stable reviewer（`design.md:170-180`）。 |
| D6：同步全部已提交 consumer，隔离主仓在途文档 | 核 planned files、canonical 冲突与双向顺序 | ✓ author/reviewer/orchestrator、两个已提交入口和契约测试均入集；未复制主仓未提交 docs，双向 rebase gate 避免后合入方复活旧口径（`design.md:182-196`）。 |

#### 3. 首文档约束

##### 3.1 用户场景与澄清记录

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| U1：连续返工的浪费来自 reviewer 冷启动和重复取证 | 对照当前 author/reviewer 行为与目标数据流 | ✓ G1/G2 证明现状；stable reviewer + reviewer-owned mode 直接减少重复上下文加载（`spec.md:28-34`; `design.md:11-49`）。 |
| U2：一个 Gate 2 闭环永远复用 reviewer，深度由 reviewer 决定 | 核 D1/D2 owner | ✓ author 不传 mode，后续唤醒 stable target；只有客观不可恢复才 failover（`design.md:68-106`）。 |
| U3：历史按 Round 分组并记录每轮时间 | 核 D3/D4 schema | ✓ 每轮内聚问题、台账、进攻、结论、时间和 author Resolution，旧轮不可覆盖（`design.md:108-168`）。 |
| Q1：永远复用 reviewer | 查是否有定期轮换或便利性重建 | ✓ 无定期轮换；唯一例外是有留痕的客观 failover（`spec.md:21-22`; `design.md:70-74`）。 |
| Q2：按轮次保留问题与时间 | 查是否改成问题生命周期或 per-file history | ✓ 单报告下 `## Round N` 是唯一组织单元，没有按 issue 重排或每轮一文件（`spec.md:23-24`; `design.md:108-155`）。 |
| Q3：独立 worktree，主仓不动 | 核 branch、write set 与并发 docs 策略 | ✓ branch 明示且 D6 禁止复制主仓工作副本（`design.md:3-5,182-196`）；Runbook另有隔离检查（`:237-250`）。 |

##### 3.2 Requirement 与每个 Scenario

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| Req 1：固定复用同一 reviewer | 对照 D1 与 sequence | ✓ 单 stable target 贯穿 R1/R2+（`design.md:30-49,68-74`）。 |
| Req 1 / 首轮建立独立 reviewer | 核隔离上下文和标识保存 | ✓ R1 独立创建一次并保存 harness 标识（`design.md:70-72`），满足 `spec.md:40-44`。 |
| Req 1 / 修订后再次送审 | 核恢复机制与上下文复用 | ✓ R2+ 只允许 follow-up/SendMessage/等价恢复同一标识（`design.md:70`），满足 `spec.md:46-51`。 |
| Req 1 / 固定 reviewer 客观不可恢复 | 核 failover 条件、留痕和 mode | ✓ 原实例先判不可恢复，下一轮记录原因与旧新标识，替代者 full（`design.md:74`），满足 `spec.md:53-57`。 |
| Req 2：mode 由 reviewer 自主路由 | 对照 D2 owner 与 author 禁区 | ✓ 输入只含事实，mode 决策及升级均属于 reviewer（`design.md:76-106`）。 |
| Req 2 / Author 提交返工结果 | 核派发包完整性和禁止字段 | ✓ round/unit/target/changed artifacts/resolutions/task 齐，明确不含 mode/期望结论（`design.md:78-87,200-202`），满足 `spec.md:61-65`。 |
| Req 2 / Reviewer 选择检查深度 | 核三档判据与 metadata | ✓ closure/delta/full 的语义边界、最低范围、mode_reason 均可落盘（`design.md:89-106,117-132`），满足 `spec.md:67-71`。 |
| Req 2 / 轻量轮保留未失效证据 | 核 Coverage schema 与继承证据 | ✓ retained 必含来源 Round、artifact hash 和 delta 未失效依据，不允许静默省略（`design.md:99-106`），满足 `spec.md:73-77`。 |
| Req 2 / 轻量检查发现影响扩大 | 核升级 trigger 与权限 | ✓ 新副作用、未声明 delta、不可封闭影响或新阻断触发同轮扩围/full，author 不得降级（`design.md:97,106`），满足 `spec.md:79-83`。 |
| Req 3：报告按轮保留完整历史 | 对照 D3 与 append dataflow | ✓ 单文件按完成顺序追加，旧 reviewer 正文 immutable（`design.md:108-155,204-212`）。 |
| Req 3 / 完成一轮 review | 核 round=N+1 与一次性 append | ✓ reviewer 先核编号、后一次性追加完整 Round（`design.md:204-212`），满足 `spec.md:87-90`。 |
| Req 3 / 每轮问题独立成组 | 核 section 归属与 ID | ✓ 每轮包含全部审查段，issue ID 为 `R<round>-C/W/R<n>`（`design.md:128-155`），满足 `spec.md:92-96`。 |
| Req 3 / Author 处理一轮问题 | 核 writer 权限与三态 Resolution | ✓ author 只能追加 accepted/rejected/escalated 及证据，不改 reviewer 文本（`design.md:155,214-216`），满足 `spec.md:98-102`。 |
| Req 3 / 记录 review 时间 | 核时钟时点、时区和 duration | ✓ 开始读取前/落盘前记录 ISO 8601 时区时间并算 wall-clock（`design.md:157-159`），满足 `spec.md:104-107`。 |
| Req 4：Gate 2 只认最新 Round/快照 | 从报告追到实际 consumer | ✓ D4 完整快照与 D5 orchestrator 独立验证闭合（`design.md:157-180,218-220`）。 |
| Req 4 / 最新轮次通过 | 核 Approved/count/author judgment/manifest | ✓ 三项同时成立才通过，历史不被覆盖（`design.md:172-178`），满足 `spec.md:111-116`。 |
| Req 4 / 通过后产物变化 | 构造 add/delete/rename/content change | ✓ current manifest 重新枚举完整集合，任一集合或 hash 差异让 Round stale 并开下一轮（`design.md:163-178`），满足 `spec.md:118-122`。 |
| Req 4 / Orchestrator 启动或恢复 | 核首次 dispatch、design resume 与拒绝路径 | ✓ 两入口均重核，缺报告/未通过/计数/manifest 任一失败都不派 worker并退回同 reviewer（`design.md:180`），满足 `spec.md:124-128`。 |
| Req 5：本 unit 与主仓隔离 | 核实施位置和集成策略 | ✓ 当前产物只在指定 worktree；D6 明确不复制主仓未提交文件（`design.md:182-196`）。 |
| Req 5 / 独立 worktree 实施 | 核实际 branch/status 与 Runbook | ✓ 当前未跟踪 unit 仅在目标 worktree，Runbook把主仓隔离列为可观察项（`design.md:237-250`），满足 `spec.md:132-135`。 |

##### 3.3 范围与非目标

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| In-1：author lifecycle、返工派发、Gate 判据 | 查 D1/D2/D5 与 planned writes | ✓ owner、输入、循环与三项 Gate 均有落点（`design.md:68-106,170-191`）。 |
| In-2：reviewer mode、Round/time/append | 查 D2-D4 | ✓ mode、Coverage、schema、writer 权限、时间和 manifest 闭合（`design.md:76-168`）。 |
| In-3：orchestrator 真实消费 Gate | 查 D5、数据流和 M1 | ✓ consumer skill、首次 dispatch/resume、拒绝路径均进入实施范围（`design.md:180,184-191,218-220,256`）。 |
| In-4：已提交 workflow/agent routing 入口 | 查 D6 | ✓ `docs/changes/readme.md` 与 `AGENTS.md` 均列入，同步职责明确（`design.md:182-196`）。 |
| In-5：文档契约测试 | 查 planned writes/Runbook/M1 worker 轨 | ✓ 测试在三处都出现，覆盖 append-only 与 Gate 协议的实现细节可由 worker按设计落地（`design.md:191,247-250,256`）。 |
| Non-1：不改变核实维度、严重度、四角度 | 对照 D2 与 reviewer 基线 | ✓ light mode 只继承未失效证据，不删除维度；严重度/四角度保持原定义（`design.md:99-106`）。 |
| Non-2：reviewer 不写 design/code/其他产物 | 核 writer 权限 | ✓ reviewer 只 append Round，author 才修 design 和追加 Resolution（`design.md:155,204-216`）。 |
| Non-3：不定期轮换 reviewer | 核 D1 | ✓ 只有客观不可恢复才留痕 failover（`design.md:68-74`）。 |
| Non-4：不引数据库或每轮一文件 | 做删除测试 | ✓ 单 append-only Markdown 足以承载历史；无新持久化层（`design.md:108-155,230`）。 |
| Non-5：不复制主仓未提交 docs | 核 D6 与实际状态 | ✓ 仅只读取证并设置 merge-order gate，没有把主仓 `docs/README.md`/`docs/development/` 带入 worktree（`design.md:193-196`）。 |
| Non-6：不改产品 runtime | 核 M1、Delta-spec 和 artifact tree | ✓ 所有目标均为 workflow 文本/契约测试，无 `src/` 写入（`design.md:252-262`）。 |

#### 4. Delta-spec

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| no spec delta | 核消费者可观察行为是否属于四个产品包 | ✓ 变化只影响仓库内 change-* agent workflow，不改变 kernel、IM、Gateway 或 CLI；把规则同步到 workflow docs 而非产品 delta-spec 是正确落层（`design.md:182-196,260-262`）。 |

#### 5. Milestone

| 原子 | 核实动作 | 结论 + 证据 |
|---|---|---|
| feat-485-M1 / skill-contract | 核 ID/title/dir、垂直性、范围、依赖和双轨退出 | ✓ `feat-485-M1` 与 `M1-skill-contract` 分离且符合 worker contract；三个角色和两个入口在同一不可分割协议切片内，单 M1 避免中间提交契约撕裂，`[reviewer]`/`[worker]` 退出轨齐（`design.md:252-258`; author asset `design.md:130-145`; worker `SKILL.md:63-76`）。 |

### 整体判断

| 维度 | 结论 + 证据 |
|---|---|
| 上层可读性 | ✓ 架构图与 sequence 先讲清 stable reviewer、mode owner、append-only report 和 orchestrator consumer，再进入决策（`design.md:9-50`）。 |
| 接口与数据流 | ✓ author→reviewer→report→author/orchestrator 的 owner、输入、写权限和拒绝路径闭合（`design.md:198-220`）；接口摘要可再显式列 author Resolution 核对，见 R2-R1。 |
| 常规完整性 | ✓ 对齐版本、branch、现状证据、6 个决策、风险/回退、Runbook、Milestone、no delta 齐；无模板注释、TBD 或未拍板问题。 |
| 命名与图 | ✓ stable reviewer、review_mode、Round、manifest、orchestrator Gate 在图、schema、决策和接口中一致。 |
| 风险与回退 | ✓ 锚定、低报 delta、light 少审、历史改写、报告增长、failover、stale design、并发 canonical 冲突均有对应机制（`design.md:222-235`）。 |
| Runbook | ✓ 真实 canary 与观察点覆盖核心用户旅程，validator 路径可解析；主仓隔离证据在并发编辑时可进一步改成可归因检查，见 R2-R2。 |
| Milestone 可执行性 | ✓ 单垂直 M1、合法 ID/dir、完整 scope 和双轨退出足以让 orchestrator/worker 无需猜字段或跨 milestone 等待。 |

### 架构进攻

| 角度 | 攻的对象 | 发现 + 长远代价 |
|---|---|---|
| 归属 | Reviewer lifecycle 与 review-mode owner | ✓ lifecycle 编排归 author，影响判断归独立 reviewer；author 只传事实，既保留全局推进责任，也不把结论偏见注入 mode。 |
| 归属 | Gate 2 authority 与 orchestrator consumer | ✓ 报告产生结论，author 判 findings，orchestrator 在真正派 worker 的边界独立验最新 Round/manifest；没有让 producer 自证后直接放行。 |
| 归属 | report 双 writer | ✓ reviewer 独占 Round 正文，author 只追加 Resolution；纠错进入新 Round，历史责任边界可审计。 |
| 该不该存在 | Stable reviewer | ✓ 删除即恢复每轮冷启动和重复取证，直接破坏用户要优化的成本；有明确价值。 |
| 该不该存在 | closure/delta/full | ✓ 三档分别处理非语义 closure、有界语义 delta 和高风险/不可界定 full；删到单档会恢复全量浪费，继续加档则没有新语义。 |
| 该不该存在 | append-only Round + prior-history hash | ✓ 删除会失去按轮问题/耗时/Resolution复盘，或无法证明历史前缀未改；单文件机制已是满足需求的最小层。 |
| 该不该存在 | Orchestrator Gate consumer | ✓ 删除会让跨会话首次启动或 design revision resume 绕过 stale approval；这是生产放行边界，不是重复校验装饰。 |
| 深还是浅 | 完整 artifact manifest | ✓ 接口隐藏了“哪些文件算受审产物”的集合规则，并对外只暴露排序路径+sha256；能检测增删改名改内容，不再用 changed subset 冒充 Gate snapshot。 |
| 深还是浅 | Light-mode Coverage | ✓ `rechecked/retained + source Round/hash + non-invalidation reason` 让 light mode 省取证但不泄漏隐式遗漏；不能证明时升级 full，抽象边界足够深。 |
| 深还是浅 | Gate 2 三方数据流 | ✓ author、reviewer、orchestrator 各自只承担其可判真的部分；唯一轻微文案不对称是接口摘要省略 Resolution 核对，见 R2-R1，不构成实现方向阻断。 |
| 治本还是补丁 | Reviewer 冷启动成本 | ✓ 保留 unit 级 reviewer 上下文并由其按真实 delta 路由范围，处理重复加载/重复取证根因，不靠删检查项或硬限 token。 |
| 治本还是补丁 | 历史与 stale approval | ✓ append-only history、完整 manifest、真实 consumer 同时处理“报告被覆盖”和“结论与当前产物漂移”两个根因。 |
| 治本还是补丁 | Workflow acceptance | ✓ Runbook 用本 unit 自身完成 R1→Resolution→同 target R2，并构造 manifest mismatch；不是只跑文本 grep。 |
| 治本还是补丁 | 并发 canonical 文档 | ✓ 双向 merge-order hard gate 防止任一落地顺序复活旧协议；没有复制并维护第二套未提交文档。 |

### Issues

- None.

### Recommendations

- [R2-R1] [Report → orchestrator 接口摘要] 决策 5 要求 orchestrator 重核三项，其中包含 author 对当前及历史 issue 的处理（`design.md:172-180`）；接口摘要和 spec 的 orchestrator Scenario 目前只逐字列 Verdict/count/manifest（`design.md:218-220`; `spec.md:124-128`）。实现方向已由决策 5 拍死，不阻断 Gate；建议在实施时同步把该摘要/契约测试显式列出 Resolution/历史 issue closure，避免未来维护者只照短摘要实现三项中的两类。

- [R2-R2] [Runbook 主仓隔离证据] 用整份主仓 `git status` hash 前后相等证明“本 unit 没动主仓”（`design.md:246`），在用户明确同时修改主仓的场景会把无关并发变化误判为本 unit 违规。建议 canary 记录目标路径 before/after、feat-485 操作日志或可归因 diff，并把全 status hash 留作提示信号；这只提高验收诊断性，不改变架构。

### Author Resolutions

- [R2-R1] accepted — 实施 `change-orchestrator` Gate 时除最新 Verdict、0C/0W 和完整 manifest 外，显式核对最新 Round 对历史阻断 issue 的 closure 记录与 author Resolution，不按短摘要漏掉第三类条件；契约测试固定该要求。
- [R2-R2] accepted — 验证主仓隔离时以本次操作始终使用 worktree 绝对路径、主仓目标路径的 path-scoped 状态和最终可归因 diff 为主证据；整份 status hash 只作并发提示，不把其他任务的变化误判为本 unit 写入。

### User Direction After Round 2

- recorded_at: `2026-07-28T14:24:48+08:00`
- `change-orchestrator` 不需要检查 `design-review.md`，撤回对应修改；本条取代 R2-R1 的实施方向。
- 不记录 sha256、byte length 或完整产物 manifest；保留由 agent 直接判断的 reviewer lifecycle、mode 路由和按轮历史。
- `tests/contract/test_design_review_round_contract.py` 整个删除；skill 与流程文档不建立字符串断言契约测试。
- 根级 `AGENTS.md` 不增加 design-review 细节；该规则属于相关 skill 与 change workflow 文档。`docs/changes/readme.md` 中与本需求无关的 milestone skeleton 改写一并撤回。

### PR Review Resolutions

- recorded_at: `2026-07-28T14:37:24+08:00`
- 已有 Round 的 unit 重新进入 design-author 时，先恢复报告中记录的 reviewer 并从 `N+1` 继续；只有无历史时创建 R1，客观不可恢复才留痕 failover。
- `closure` 只记录历史问题关闭证据，`delta` 只展开受影响项；不再要求轻量轮复写全量 Coverage、台账和架构进攻。
- 恢复既有严重度语义：非实质 WARNING 不因本 PR 被提升为强制返工条件。
