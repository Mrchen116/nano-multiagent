# R2D6: Spec/Design 质量评测 Harness

> **维度**：spec/design 质量评测 harness（第一轮最大缺口）
> **约束**：纯黑盒 LLM；工程优先；shipped 优先；🟢SHIPPED / 🟡RESEARCH 必标
> **关联**：第一轮 §6.2 已覆盖 ISO 29148 rubric 基础（不重复）；本轮向下挖"怎么工程化落地"

---

## 执行摘要

第一轮识别出"评测系统缺失是卡脖子问题"，但停在了问题描述层。本轮的核心问题是：**practitioner 实际怎么搭一套能用的 spec/design judge harness——以及它究竟能做到什么、不能做到什么？**

核心结论三条：

1. **LLM-as-judge 对"平均质量"可靠（κ≈0.77-0.87），对"单人品味"不可靠**——除非你用自己的 accept/reject 历史来校准 judge prompt，而非依赖预制 rubric。这是一个工程问题，不是研究问题，且黑盒可落地。

2. **Prompt-as-test（prompt-based behavioral test）是目前 shipped harness 里最主流的 spec/design 自评模式**——Claude Code 的 `promptEngineeringAudit` 就是这种模式：把期望行为列成一批 `expect(prompt).toContain(X)` 的断言，每次 prompt 变更自动跑，发现回归。这是从"写文档"到"有质量门"最低成本的一跳，且与测试框架完全正交。

3. **"可演进性"没有被生产级工具直接量化过**——现有代理指标（M-score、ADR coverage、ATAM）都在研究前沿或需要专家介入；对个人开发者最可操作的替代是"下游滞后指标"（fix round 数、verifier CRITICAL 数）+ "中期可演进性信号"（架构决策 ADR 覆盖率、spec-to-code 漂移检测），配合 LLM-as-judge 做近期预测。

---

## 关键发现

### F1：LLM-as-Judge 作为 spec 质量 gate 的 shipped 模式

🟢**SHIPPED**（谁：多个 coding agent / SDD 工具使用 prompted critic 做内嵌质量门）

**最直接的工程证据**来自本仓库自身的 `change-verifier` skill（`/Users/czj/Repos/nano-multiagent/.claude/skills/change-verifier/SKILL.md`）：它是一个 LLM-as-judge 实例——由 verifier agent 读 spec/design + 代码，按 Completeness / Correctness / Coherence 三维打分，产出 CRITICAL / WARNING / SUGGESTION 分级问题清单，不通过则阻塞 PR。这不是研究模型，是这个项目生产中跑的门禁。

**外部 shipped 证据**：

- Claude Code 的 `/security-review` 命令（`src/commands/security-review.ts`）是 LLM-as-judge 的典型实现：分三 phase（context research → finding identification → false-positive filtering），每个 finding 要求给 confidence score 0.7-1.0，低于 0.7 不报。false-positive 过滤规则是一份明确的排除清单（14条），实质是用 prompt engineering 把 judge 校准到"高精度 / 低噪声"维度，而非"全面覆盖"。这是个人开发者可直接参考的校准模式。

- Claude Code 的 `/simplify` 技能（`src/skills/bundled/simplify.ts`）：三路 judge 并行（Code Reuse Review / Code Quality Review / Efficiency Review），各自有独立的检查清单，最后汇总修复。这是 multi-criteria judge 的 shipped 模板。

- GitHub Spec-Kit 的 Constitution + Checklist phase：agent 在进入 Plan/Tasks 之前必须过 Checklist 验证，实质是一个 prompted quality gate。🟢SHIPPED，来源：GitHub Spec-Kit 官方文档，八阶段流程中 Constitution → Specify → Clarify → **Checklist** → Plan → Tasks。

- AWS Kiro：EARS 格式 requirement 验证是内嵌的结构性 gate——不符合 EARS 五种句型的 requirement 会被标记。🟢SHIPPED，来源：AWS Kiro 产品文档（GA 2025.11）。

**第一轮漏覆盖的关键点**：LLM judge 的 κ=0.77-0.87 是与"平均人类"的对齐，而非与"当前用户品味"的对齐。这两者的差距在 spec 评测中尤其大——你认为的"好 spec"与通用 rubric 的差距，正是 judge 噪声的主要来源。

---

### F2：把 Judge 校准到单人品味——工程做法（黑盒可落地）

🟢**SHIPPED 做法**：用已批准/拒绝的历史决策样本作 few-shot，替换通用标准。

**具体工程模式**：

**模式 A：Few-shot judge calibration**（最低成本）

把 5-10 个你自己 accept 的 spec 段落和 5-10 个你自己 reject / 大改的 spec 段落作为 few-shot 示例，注入到 judge prompt 里：

```
# 评判标准

参考以下历史样本：

【我接受的 spec（示例 1-5）】
...

【我大改或拒绝的 spec（示例 6-10）】
...

现在评判这份 spec：
```

这不是新技术——它是 FSPO 框架（Stanford/DeepMind/OpenAI）的纯黑盒退化版：不训模型，直接靠 in-context learning。🟢SHIPPED 类似形式：本仓库 `change-spec-author` SKILL.md §0 已经要求"把用户原话粘进去 + 原话不准改写"，就是在构建这类少量高保真样本的语料库——只差把它接进 judge prompt 这一步。

**模式 B：Persona prompt + decision rationale**（中成本）

从 `docs/changes/*/spec.md` 的"澄清记录"段提取用户在各个价值岔路的选择与原话，构建一段 persona prompt：

```
你是一个有以下偏好的产品作者：
- [从历史 spec 澄清记录中提取的偏好 1]
- [从历史 spec 澄清记录中提取的偏好 2]
...

以上偏好来自你过去在以下场景的实际决策：
- [场景 + 岔路 + 选择 + 原话]
```

这对应第一轮 §P0-5 提到的"委托方现有做法"——docs/changes 里已经攒了多 unit 的原话语料，这是 bootstrap persona 的一手材料。

**模式 C：Rubric diff（规则性排除法）**（已 shipped 于 security-review）

不是问"这份 spec 好不好"，而是问"这份 spec 是否违反了以下明确的不该有的条目"。Claude Code 的 security-review 排除清单就是这个模式：14 条 HARD EXCLUSIONS + 12 条 PRECEDENTS + 4 条 SIGNAL QUALITY CRITERIA。对 spec 评测，同样可以建一份"spec 异味清单"：

```
HARD EXCLUSIONS（判到就报，不用综合评分）：
- 包含实现层决策（"使用 SQLite"）而非用户面行为描述
- 验收标准不含 GIVEN/WHEN/THEN 结构（无法被测试化）
- 使用模糊表达（"适当地"、"尽可能"、"大约"）而无可测量标准
- 某条 requirement 无法被独立验证（依赖另一条才能判）
...
```

这种方式的优点：不依赖 judge 对"好"的主观理解，只依赖对"坏的已知模式"的匹配，误报率低，可随时添条目。

---

### F3：Prompt-as-Test——把 spec 质量门接入 CI

🟢**SHIPPED**（谁：Claude Code；来源：`src/constants/promptEngineeringAudit.runner.ts` + `src/constants/__tests__/promptEngineeringAudit.test.ts`）

这是本轮最重要的工程模式发现。Claude Code 实际运行的 `promptEngineeringAudit` 测试套件的工作原理：

1. 把 system prompt 用 mock 环境渲染成字符串（`getSystemPrompt()`）
2. 对渲染结果跑 64 个 `expect(prompt).toContain(X)` 断言，每个断言对应一条期望行为
3. 断言失败 = prompt 回归，CI 拦截合并

```typescript
// 来自 src/constants/promptEngineeringAudit.runner.ts (第 241-263 行)
describe('#1 Decision tree for tool selection', () => {
  test('prompt contains tool selection guidance via dedicated tools', async () => {
    const prompt = await getFullPrompt()
    expect(prompt).toContain('Prefer dedicated tools')
    expect(prompt).toContain('Reserve')
  })
  test('provides concrete tool preference examples', async () => {
    const prompt = await getFullPrompt()
    expect(prompt).toContain('over cat')
    expect(prompt).toContain('over sed')
  })
})
```

**迁移到 spec 评测**：spec/design 的"prompt-as-test"等价物：

- 对 spec.md 做结构性断言：`assert "## 验收标准" in spec_content`
- 对每条 requirement 做格式断言：`assert re.search(r'GIVEN.*WHEN.*THEN', scenario)` 
- 对 design.md 做关键决策断言：`assert "## 关键决策" in design_content`

这是把"有没有正确结构"编码为可重复运行的门禁，成本极低（纯字符串匹配），且每次 spec 更新自动跑，不依赖 LLM。

对应本仓库：`change-verifier` 的 §2.1 Task 完成检查是这个模式的人工实现（verifier agent 执行）——可以把其中纯结构性的检查前移为自动化测试（pytest），把需要理解的部分保留给 LLM judge。

---

### F4：Golden Set 的工程化——不是一次性建成的

🟢**SHIPPED 策略**（谁：ArbiterOS EDLC；Claude Code 的 audit runner；本仓库的 acceptance.md 历史）

Golden set 的实际工程形态，不是先建一批"金标准样本"然后用来评测——在 spec/design 场景里这不可能（品味本身在漂移）。生产中的做法是**增量积累 + 定期修剪**：

**增量积累路径**：

1. 每次 human review accept 一份 spec → 把它加入 "good examples" 集（few-shot 材料）
2. 每次 verifier 发现 CRITICAL 问题 → 把对应的 spec 片段 + 问题加入 "bad examples" 集
3. 每次 reviewer 发现 R1 过不了 → 记录"spec 哪条 requirement 措辞导致了歧义"，加入排除清单

这三条路径在本仓库当前工作流里全部已经发生，只是没有被系统化地接入 judge。`docs/changes/` 里的历史 spec.md / acceptance.md / verification.md 就是这个 golden set 的原材料。

**关键设计决策**：golden set 的用途不是"用来评分"，而是"用来让 judge 的口径向你的品味靠拢"。因此它的维护策略是：
- 每 5-10 个 unit 做一次 review，删掉过时的样本（品味已经更新了的部分）
- 每次发现 judge 输出你明确不认同的评价 → 把这个案例加进去 + 修正 judge 的判断

---

### F5：可演进性（Evolvability）的可操作代理指标

第一轮已确认可演进性的自动度量"在研究前沿"。本轮聚焦：**实际能用什么代理指标**？

🟡**RESEARCH**：M-score（模块化度量）、ATAM/SAAM scenario-based 评估——需要专家介入或代码级分析，不直接适用于 spec 评测阶段。

🟢**SHIPPED 代理指标（间接但可操作）**：

**短期（当前可立即采集）**：

| 指标 | 来源 | 说明 |
|---|---|---|
| Verifier CRITICAL count / milestone | `verification.md` 历史 | spec 措辞不清导致 verifier 误判 → spec 质量信号 |
| Reviewer fix round 数 | `acceptance.md` 历史 | R1 pass vs R3 pass → spec→design 转化损耗 |
| Design 关键决策改变次数 | `design.md` git diff | 实施中 design 反复 → spec 未覆盖真实约束 |
| Spec 修订次数（post-门禁1） | git log `spec.md` | 过了门禁1还在改 spec → 第一轮澄清不充分 |

**中期（可演进性的直接代理）**：

- **ADR（架构决策记录）覆盖率**：design.md 的"关键决策"段是否覆盖了所有在实施中被翻案的选型。被翻案但 design 未记录 → spec 没有把约束传到 design。🟢SHIPPED 用于 design 质量评估：Claude Code 的 ADR 自动生成已在研究中（GPT-4 0-shot 可生成相关 ADR，但未达人类水平）。
- **spec-to-code 漂移检测**：`change-verifier` 的 Coherence 维度是这个的现有实现。把 verifier 报告中 Coherence 段的 WARNING 率作为"spec 可演进性"的负向指标（高 WARNING = spec 写的内容实施时经常偏）。

🟡**RESEARCH 但黑盒可实验**：

- LLM-as-judge 对 spec 的"is this spec testable without ambiguity"评分——让 judge 问"如果我是 verifier，我能根据这条 requirement 给出明确 pass/fail 判断吗？"。这是可演进性的**最近端代理**（不可测 = 不可演进），且纯黑盒。没有 shipped 证据，但机制上合理，风险低。

---

### F6：Eval-Driven Development Lifecycle（EDLC）——工程化落地路径

🟢**SHIPPED 概念**（ArbiterOS，概念层）；🟡**RESEARCH**（具体实现）

第一轮提到 ArbiterOS 的 EDLC，本轮具体化其工程落地：

EDLC 的核心机制：
1. 定义 golden dataset（你认为的好 spec/design 样本集）
2. 定义 judge criteria（rubric / few-shot）
3. 每次 spec/design 产出后跑 judge
4. judge 分数低于阈值 → 自动阻塞（或 flag for review）
5. 每次 human review 的 accept/reject → 更新 golden dataset + 重新校准 judge

在本仓库的工程化等价物：

```
docs/changes/<unit>/
├── spec.md              ← 被评测对象
├── verification.md      ← verifier 产出（Completeness/Correctness/Coherence）
├── acceptance.md        ← reviewer 产出（用户旅程验收）
└── judge-eval.md        ← 【新增】spec/design judge 评分记录（可选）
```

门禁 1 前的 spec judge 可以复用 `change-verifier` 的逻辑，但更早、更轻：不看代码（代码还不存在），只看 spec 结构 + 完整性 + 与 constitution 的一致性。

**具体实现路径**（黑盒，今天就能搭）：

```python
def judge_spec(spec_content: str, few_shot_examples: list, constitution: str) -> JudgeResult:
    """
    spec judge 的核心 prompt 结构：
    1. constitution（角色定义 + 硬约束）
    2. few-shot：accepted examples + rejected examples
    3. rubric checklist（spec-smell 排除规则）
    4. 待评 spec
    5. 输出格式：PASS/FAIL + CRITICAL/WARNING 分级问题
    """
    ...
```

输出结构与 `change-verifier` 的 `verification.md` 格式对齐，复用已有的 orchestrator 路由逻辑。

---

### F7：黑盒 CAN / CANNOT 表

| 方法 | 黑盒 CAN/CANNOT | 最佳黑盒替代 |
|---|---|---|
| LLM-as-judge（通用 rubric） | **CAN**：κ≈0.77-0.87 对平均质量；完全黑盒 | — |
| LLM-as-judge（校准到单人品味） | **CAN**：用 few-shot 历史样本 + persona prompt；黑盒 in-context | F2 三种模式 |
| Golden set 驱动的持续评估 | **CAN**：增量积累 accept/reject 案例，定期更新 judge prompt | 增量积累策略（F4） |
| Prompt-as-test（结构性断言） | **CAN**：纯字符串匹配，零 LLM 成本 | — |
| Spec-smell 排除清单 | **CAN**：规则性检测，完全黑盒 | — |
| LLM 对"可演进性"的预测 | **CAN（部分）**：问"这条 requirement 是否可测试化"；但无统计保证 | 下游滞后指标 + ADR 覆盖率 |
| Conformal prediction 对 spec 质量 | **CANNOT**：需要校准集 + exchangeable 假设；spec 质量不符合 CP 前提 | sampling consistency（多次生成比较一致性） |
| ATAM/SAAM 可演进性评估 | **CANNOT**：需要专家介入，无法自动化 | M-score 代理（需代码）+ verifier Coherence 警告率 |
| Verbalized confidence 作为质量信号 | **CANNOT（不可靠）**：系统性过度自信（ECE 可达 0.377+）| Monte Carlo sampling：多次生成 → 比较方差 |
| Meta-model 路由（LPP）用于 spec 质量 | **CANNOT（黑盒受限）**：需要 gray-box 特征（token logprob）| verbalized + uncertainty indicators（精度较低） |

---

### F8：本仓库现有测试观与评测 harness 的对接

本仓库 TESTING_GUIDE.md 的核心原则："测试来源 = 首文档 / design.md 里每条可观察行为"，"改个内部写法就变红的测试是负债"。

这与 spec/design eval harness 的设计原则高度一致，但指向了一个当前的空白：**spec/design 本身没有对应的"可观察行为测试"**。

当前工作流：spec.md 写完 → 人工审查 → 门禁 1 → design.md → 门禁 2。两个门禁目前是人工的（`change-spec-author` 和 `change-design-author` 的自我 review）。

eval harness 的接入点：

```
docs/changes/<unit>/
spec.md          ← 已有（spec-author 产出）
design.md        ← 已有（design-author 产出）

tests/spec_eval/ ← 【可新增】
  test_spec_structure.py    ← 结构性断言（prompt-as-test 模式，零 LLM）
  test_spec_quality.py      ← LLM-as-judge（有 LLM 成本，可标 @pytest.mark.llm_eval）
```

按 TESTING_GUIDE 的分层原则：结构性检查（文件存在、段落完整、GIVEN/WHEN/THEN 格式）落 `tests/unit/`；LLM judge 调用真实 API，归 `tests/e2e/`，打 `@pytest.mark.e2e`，不进 `pytest -m "not e2e"` 默认跑。

---

## 对本 Unit 实现的可操作建议

### 立即可做（零基础设施成本）

**B1：建 spec-smell 排除清单**（模式 C，F2）

在 `change-spec-author/SKILL.md` 增加一个 self-check 段，列出 spec-smell 清单。agent 在产出草稿后自检：

```markdown
## §X spec-smell 自检（产出前必过）

对下列每条判断：若命中则修改后再呈给用户

- [ ] 是否包含实现层决策（"用 SQLite"、"走 SSE"）？→ 删除，改为用户面描述
- [ ] 是否有 requirement 没有对应 GIVEN/WHEN/THEN 格式的 scenario？→ 补结构
- [ ] 是否有 scenario 的 THEN 无法被 verifier 判断 pass/fail？→ 改写为可测量表述
- [ ] 是否有模糊表达（"适当地"、"尽快"）？→ 改为可测量量词
- [ ] 是否有 requirement 仅描述系统内部行为而非用户可观察行为？→ 改写
```

这直接降低 verifier CRITICAL 数的预期（对应 F5 短期指标）。

**B2：把历史 spec 澄清记录结构化为 judge few-shot 材料**

当前 `docs/changes/*/spec.md` 的澄清记录段包含大量用户在价值岔路的原话。建一个轻量索引：

```
docs/eval-assets/
├── spec_good_examples/   ← 从 accepted spec 里提取的"好"片段（人工 5-10 条）
├── spec_bad_examples/    ← 从 rejected/大改 spec 里提取的"坏"片段
└── constitution-spec.md  ← 关于 spec 质量的原则（从个人偏好提炼，20 条以内）
```

这是 F4 golden set 的初始化，也是 F2 few-shot calibration 的数据源。

### 短期可做（1-2 unit 实施周期后）

**B3：给 change-spec-author 增加 LLM-as-judge 自评 step**

在 spec-author SKILL 的门禁 1 前增加一个 judge step：

```
## §Y 门禁 1 前 LLM self-judge

用 judge prompt（含 few-shot）对当前 spec.md 跑一遍评估。
若有 CRITICAL 问题 → 修改后再过用户确认。
judge prompt 路径：docs/eval-assets/constitution-spec.md + good/bad examples
```

judge prompt 初期可以是 `change-verifier` 的 Correctness 维度的前移版（不看代码，只看 spec 结构），后期用 B2 的 few-shot 材料校准。

**B4：接入滞后指标仪表盘**

在每个 unit 收口时（PR merge 后），记录以下 4 个指标到 `docs/eval-assets/metrics.csv`：

```
unit_id, fix_rounds, verifier_critical, reviewer_fix_rounds, spec_revisions_post_gate1
```

这是 F5 短期指标的系统化采集。10 个 unit 后开始分析相关性：哪些 spec 特征预测了高 fix round 数？这些发现反哺 B1 的 smell 清单和 B2 的 bad examples 集。

### 中期（3-6 个月后）

**B5：Monte Carlo spec judge（多次采样比一致性）**

对同一 spec，用不同随机种子跑 judge 3-5 次，若 CRITICAL 问题在不同 run 中的一致性低（有时报有时不报）→ 该 judgment 不可信，escalate for human review。这是 sampling-based confidence 在 spec eval 的黑盒实现，无需 logprob。

**B6：spec-to-code 漂移检测**

在 `change-verifier` 的 Coherence 段增加一个漂移分析：记录"spec 的哪条 requirement 在实施时被 design/worker 实质性改变了"。这构成可演进性的负向代理——高漂移率 = spec 未充分约束设计空间。

---

## Reality Check：不要做什么

**不要追求"spec 质量分数"的精确性**：一个 0-100 的 spec 质量分数对个人开发者没有意义，你不会在 72 分和 75 分之间做任何不同的决策。有意义的是"这份 spec 是否会导致 verifier CRITICAL 问题"（二值判断），以及"哪里需要修改"（可操作的问题清单）。

**不要一次性建大型 golden set**：5 个好样本 + 5 个坏样本的 few-shot judge，比一个没有校准过的通用 rubric 更能反映你的品味。从小开始，每次 human review 都是更新材料的机会。

**不要期望 LLM judge 能评测"可演进性"**：它能评测的是"这份 spec 现在是否清晰可测试化"，而不是"这个设计 6 个月后是否还好用"。后者只有下游滞后指标（fix rounds、技术债积累）才能告诉你。

**不要跳过结构性检查直接上 LLM judge**：结构性断言（prompt-as-test）成本接近零，且能以确定性方式捕获"没有 GIVEN/WHEN/THEN"、"缺段落"这类问题。LLM judge 应该只处理结构性检查过后的 spec，不要让它替代可以用规则捕获的东西。

---

## 必读一手工程来源（本维度专属）

1. `/Users/czj/Repos/nano-multiagent/.claude/skills/change-verifier/SKILL.md` ——本仓库已 shipped 的 LLM-as-judge 三维评测框架，是 spec eval harness 的最近邻参考，可直接扩展到 spec 阶段。

2. `/Users/czj/Repos/opensource-hub/claude-code/src/constants/promptEngineeringAudit.runner.ts` ——Claude Code 的 prompt-as-test 工程模式（64 个行为断言），是"spec 结构性检查进 CI"的最直接参考实现。

3. `/Users/czj/Repos/opensource-hub/claude-code/src/commands/security-review.ts` ——Claude Code 的多 phase judge + false-positive 排除清单 + confidence scoring 的工程模板，直接迁移到 spec quality judge。

4. `/Users/czj/Repos/nano-multiagent/.claude/skills/change-spec-author/SKILL.md` ——当前 spec-author 的产出规范（§0 原话保留 / §澄清记录 / GIVEN/WHEN/THEN 结构），是 spec-smell 清单的直接来源。

5. 本仓库 `docs/changes/` 下历史 spec.md + acceptance.md + verification.md 的集合 ——是 golden set 原材料库，无需额外采集。

---

## 总结

| 问题 | 答案 |
|---|---|
| practitioner 实际用什么评 spec/design | LLM-as-judge（rubric 或 few-shot 校准）+ 结构性断言（prompt-as-test）+ 下游滞后指标 |
| 怎么把 judge 校准到单人品味 | 用 accept/reject 历史做 few-shot（F2 模式 A）+ 从澄清记录原话构建 persona prompt（F2 模式 B）+ spec-smell 排除清单（F2 模式 C）|
| 可演进性有无可操作代理 | 短期：fix_rounds / verifier_critical（滞后）；中期：ADR 覆盖率 / spec 漂移率；LLM 问"是否可测试化"（近端代理）|
| 黑盒 CANNOT 做什么 | ATAM/SAAM 可演进性评估；CP 对 spec 质量；meta-model logprob 特征 |
| 对本 unit 的立即行动 | B1 spec-smell 清单 + B2 few-shot 材料建立；B3 judge step 接入 spec-author |
