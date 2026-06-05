# 对《Multi-Agent 系统设计复盘报告》(你+GPT)的独立评审

> 被评审对象:`Multi-Agent 系统设计复盘报告：从"拟人化争议"到 SDD Spec Design Agent Team 架构.md`(你和 GPT 一起读文献产出,其中 §8-11 的 SDD 架构未经你审核 = GPT 产出)。
> 评审方法:用本 unit 已有的四轮研究 + 222 条澄清数据 + Clowder 一手源码 teardown,**独立**核查,不照单全收。
> 评审人:主 agent。日期 2026-06-05。

## 一句话结论

**诊断层(§1-7)很强,可以直接吸收;处方层(§8-11 的推荐架构)是"理论正确但显著过重"的纸面架构,和它自己引用的文献(Building Effective Agents 的"从简单开始"、MAST 的"协调即失败")相矛盾,也比任何 SHIPPED 系统(Clowder/BMAD/spec-kit)都重——直接照搬有撞上 McEntire"11 阶段流水线 100% 失败"反模式的风险。** 建议:吸收诊断 + 角色机制化原则 + 15 问 checklist;处方降级为"理念参考",落地以 Clowder 的精简 shipped 形态为准。

---

## 一、诊断层(§1-7):强,和我们的研究收敛,直接吸收

| 报告论点 | 评审 |
|---|---|
| §1 反对的不是 multi-agent,是**浅层拟人化**(同模型/同 context/同工具/同权限/只改 prompt) | ✅ 与 round-3 的"真增能力三条件(objective 不同+context 隔离+工具层强制)"**完全一致**。这是全报告最有价值的一句。 |
| §1.2 **Role = bundle**(accessible_context / allowed_tools / decision_rights / objective_function / output_artifacts / verification_obligations) | ✅ **最值得吸收的设计原则**。它把"角色机制化"讲得比我们任何一轮都干净——岗位名可留,但必须真有不同的 context/工具/权限/产物/验证义务。 |
| §2 六类价值(context scaling / parallel / diversity / 生成-批判-验证分离 / 工具权限隔离 / 证据链) | ✅ 都成立,和我们结论一致。 |
| §3 三层失败(L1 局部 / L2 交接 / L3 系统组合) | ✅ 好框架,对应 MAST 三类。 |
| §6 **群聊是可见性,claim-owner review 才是可靠性** | ✅ 洞察对,和我们"别用群聊辩论"一致。而且 Clowder 的 **Contributor Check**(综合后原作者确认没被误读)就是这条的**轻量 shipped 版**——验证了方向。 |
| §7 verification 三类(mechanical/semantic/human)+ **必须能 block** | ✅ 对,和 D5 + Clowder 的 gate 一致。 |
| §10 15 问设计 checklist | ✅ 直接可当评估 rubric 用。 |

诊断没问题。问题全在处方。

---

## 二、处方层(§8-11 推荐架构):五个具体问题(这是 GPT 未审核的部分)

报告推荐:**Main Orchestrator + Product Context Agent + Codebase Context Agent + QA/Risk Agent + Architecture/Design Agent + Gate Verifier(≈6 个 agent)+ Claim Registry + Usage Tracking + Owner Review + Canonical Artifact Store + Mechanical Verifier + Semantic Verifier + Human Gate + 4 道 Gate**。逐条问题:

### 问题 1:它和自己引用的文献直接打架(最严重)

- 它引 Anthropic《Building Effective Agents》——那篇的核心忠告是**"从最简单方案开始,只在必要时加 agentic complexity"**。这份处方却一上来就是 6 agent + claim 协议 + 3 verifier + 4 gate,是反向操作。
- 它引 MAST(2503.13657)——MAST 的结论是 **79% 的失败来自 specification + coordination**。而**协调机构越多,这两类失败的暴露面越大**。处方堆的全是协调机构。
- 我们 round-3 的 McEntire 对照实验:**11 阶段门控流水线 100% 失败**,把全部预算烧在规划阶段、零代码产出。这份处方(6 agent + 4 gate 全压在 spec/design,即写码之前)**形态上非常接近这个反模式**。
→ 它有"严谨的样子",但严谨过头本身就是 spec/design 阶段最高频的失败模式。

### 问题 2:Claim Registry + Owner Review 优雅但未经验证、且高摩擦

- 没有任何 SHIPPED 系统(Clowder/BMAD/spec-kit/Kiro)实现"claim-id + 下游引用必须声明 + claim owner 逐条 review usage"这套。它是**纸面机制**。
- 摩擦极高:每个 claim 配 id/owner/evidence/scope/caveat/confidence,每次下游使用要声明,每个 owner 要 review 每次使用——这是**企业级 traceability 机器**,对单人维护者的 spec/design 大概率过度。
- 方向有文献支持(round-3 Traceability 2510.07614:"结构化交接提升准确率")——但被支持的是"**结构化交接 + 保留原始 brief 锚点**"这种轻量形态,**不是**完整 claim-registry。
- **Clowder 的轻量等价物**:产物即文件;reviewer 只读 artifact 不读作者推理("fresh eyes");Contributor Check 让原作者确认"没被误读"。**用文件 + 一次复核**达到了 owner-review 的核心目的,没有 registry 的账本开销。→ 取 Clowder 的轻版,弃 GPT 的重版。

### 问题 3:整套架构是"代码改动影响分析"形状,不是你要的"产品/架构/审美"形状

- 通篇跑例都是 coding 任务(billing/seat.ts、bulk import、impact map、call graph),**Codebase Context Agent(AST/call graph 工具)是主角**。
- 但你的真实诉求含**产品经理全局视角、架构师长期可演进、前端审美、参考同类产品**——这份处方**几乎没碰审美/产品愿景/竞品调研**,它解的是"AI 给一次代码改动做影响面分析"。对 greenfield 的产品/功能 spec,这个 codebase-impact 重心**部分偏靶**。

### 问题 4:它把 gate 押在 LLM "Semantic Verifier" 上,错过了"确定性 gate 优先"

- 处方的 gate = Mechanical Verifier(✅ 确定性,对)+ **Semantic Verifier(一个 LLM 判语义)** + Human Gate。
- 但 round-3 + Clowder 的关键教训是:**gate 能确定性就确定性**(Clowder 的 computeBucket/detectRisks/predicate.type、结构性断言),**LLM-judge 有 Critic 高方差/有害问题**(Traceability 2510.07614:Critic 损害率 1.90%,会把对的判错)。
- 正确次序是"**先跑确定性结构断言,通过的才交 LLM-judge**"。处方把 Semantic Verifier 摆得过重,没点出这个次序。

### 问题 5:它没有(也无法)对接 76% 数据现实

- 它把 Human Gate 当成每阶段末尾的一个框。但我们 222 条数据显示:**76% 的澄清是人的判断、不可剥离**——human gate 不是"末尾一个框",而是**主要成本**。
- 系统真正的活是:把这 76% 的人介入**批量化/结构化变便宜** + 自动消化可检索的 24%。处方没 grapple 这件事(它没有这份数据,情有可原,但落地必须补)。

---

## 三、吸收 vs 降级(给 feat-397 的净结论)

**吸收(写进我们的设计依据):**
1. **Role = bundle 机制化原则**(§1.2)——作为"什么时候该拆 agent"的判据:只有当一个角色真有不同 context/工具/权限/产物/验证义务时才拆。这是 D3/design 的好支点。
2. **L1/L2/L3 失败分层 + "verify human intent"**——L2 交接失败用 Clowder 的 **Contributor Check(轻量 owner-review)** 防,不上 claim-registry。
3. **15 问 checklist(§10)**——直接作为"评估我们自己 agent team 设计"的 rubric。
4. **gate 必须能 block + 三类 verifier**——但落地次序改成"确定性 mechanical 先行 → LLM semantic 只看通过的 → human 只看价值岔路"。

**降级为"理念参考",不照搬:**
- 6-agent + Claim Registry + Usage Tracking + Owner Review + 4-gate 的完整重型架构——过重、未经验证、撞 McEntire 反模式。落地以 **Clowder 的 shipped 精简形态**为准:3-4 个跨模型猫 + 文件化 artifact + 确定性 gate + 轻量 Contributor Check,**按需才上更多机构**。
- Codebase-impact 重心——补上你真正要的产品愿景/架构演进/审美/竞品调研维度(可参考 Clowder 的 expert-panel 角色 Analyst/Assessor/Strategist + 元审美自检)。

---

## 四、三方对照(一张表收束)

| 维度 | GPT 报告(纸面) | Clowder(SHIPPED) | 我们该取 |
|---|---|---|---|
| agent 数 | ~6 专职 agent | 3-4 跨模型猫 + 按任务分角色 | Clowder 的少而异质 |
| 交接可靠性 | Claim Registry + Owner Review(重) | 文件 artifact + Contributor Check(轻) | Clowder 的轻版 |
| gate | Semantic Verifier(LLM)为主 | 确定性谓词(computeBucket/predicate.type)为主 | 确定性优先,LLM 兜底 |
| 价值判断 | Human Gate(末尾一个框) | 决策漏斗 + 可逆性闸门(分档) | 漏斗 + 我们 222 数据的 6 类红线 |
| 验证体量 | 3 verifier + 4 gate(全压 spec/design) | 门禁 + 跨猫守护(够用就停) | 按需,警惕 McEntire 反模式 |

**核心判断**:GPT 报告给了对的**词汇和原则**(机制化角色、闭环、可阻断 gate),但给的**机器太重**;Clowder 给了对的**体量和落地**。两者合起来,再叠我们的 222 数据红线,才是 feat-397 该走的形态。
