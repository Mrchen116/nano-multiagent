# Round 3 深挖报告：agent-review-panel（wan-huiyan/agent-review-panel）

> **来源库**：https://github.com/wan-huiyan/agent-review-panel（已克隆至 `/tmp/claude-feat397-r3/02-agent-review-panel-wan-huiyan-agent-revi`）
> **关键文件**：`skills/agent-review-panel/SKILL.md`（v3.3.0，1739行）、`HOW_WE_BUILT_THIS.md`（883行，完整设计历程）、`docs/research-foundations.md`、`skills/plan-review-integrator/SKILL.md`
> **标注**：🟢 SHIPPED — 真实运行在 Claude Code plugin marketplace 的生产产品
> **本轮焦点**：反同质化辩论的具体工程手段 + 对 spec-reviewer agent 的可迁移性

---

## 1. 这个库针对哪个单 agent 失败模式，用什么 multi-agent 结构去补

### 1.1 问题来源

agent-review-panel 从一个明确的单 agent 失败出发：

> "Ask one reviewer 'review this' and you get one perspective. It won't argue with itself, catch its own blind spots, or volunteer 'I'm not sure about this.'"

（README，直接引用）

### 1.2 四个单 agent 失败模式与对应补丁

| 失败模式 | 在库中的表现（实测证据） | 补丁结构 |
|---|---|---|
| **单一视角 / objective 满足即止** | v1 测试中单 agent baseline 只过 2/6 断言（多视角覆盖 + 可操作建议），在结构化分歧、数值评分、辩论证据、执行摘要上全部失败 | 4-6个独立 persona agent，content-type 自动映射（code/plan/docs/mixed 各有不同默认 persona 集）|
| **无法可靠自我批判** | "debate shifts cognitive mode from discovery to argumentation"（HOW_WE_BUILT_THIS Step 5）；v1 panel 4个reviewer + judge 全部遗漏了 `_CLOSED_CODES` 中缺少 `CM` 这类代码细节 | Phase 8 Completeness Auditor（专职只找遗漏，不评质量，post-debate 独立运行）；Phase 4 Private Reflection（在看到他人意见前自评 confidence） |
| **无独立 checkpoint / 单一 objective** | 单 agent 对高置信度错误没有外部压力 falsify | Phase 14.5 Post-Judge Verification Gate（v3.2.0）：judge 引入的每一个 P0/P1 finding 必须经过 ground-truth 核查；14.5 发现的 hallucination 会降级并重算 verdict 分数 |
| **无对抗压力 surfacing 假设** | 2026-04-09 真实案例：4个reviewer 一致将 "50 months = GA4 360" 标为 P0 但没有 web 验证（HOW_WE_BUILT_THIS Step 13 引用的 Phase 11 外部域声明检测动机） | Phase 11 Severity Verification：外部域声明（产品限制、监管、API 行为）自动 web-search 验证，标 `[WEB-VERIFIED]`/`[WEB-CONTRADICTED]`/`[WEB-INCONCLUSIVE]` |

### 1.3 拓扑结构

```
Orchestrator（父 agent，持有全局 context 路由）
│
├── Phase 2: Data Flow Tracer（单 Opus，前置路径追踪，产出 certificate 注入 Phase 3）
│
├── Phase 3: 4-6 Reviewer Agents（并行，each 独立 context，no cross-talk）
│   └── 每个 reviewer 携带：persona + agreement_intensity(20-60%) + reasoning_strategy（不同）
│
├── Phase 4: Private Reflection（并行，each 只看自己 Phase 3 输出，评 confidence）
│
├── Phase 5: Debate Rounds 1-3（并行，但每轮基于前轮 Phase 6 摘要，非 verbatim）
│   └── Phase 6: Round Summarization（orchestrator，无子 agent，提炼 resolved/unresolved）
│
├── Phase 7: Blind Final（并行，每个 reviewer 不看他人 final，独立评分）
│
├── Phase 8: Completeness Auditor（单 Opus，只找遗漏，不评质量）
├── Phase 10: Claim Verification（单 Opus，核对所有行号引用）
├── Phase 11: Severity Verification（单 Opus，读真实 codebase 验证 P0/P1）
├── Phase 12b: Tier Refinement Advisor（单 Opus，审核 dispute 分级初稿）
├── Phase 13: Targeted Verification Agents（并行，每个 dispute point 一个对应 persona 的专职 agent）
├── Phase 14: Supreme Judge（单 Opus，domain-neutral，裁定所有输入）
├── Phase 14.5: Post-Judge Verification Gate（单 Opus，re-verify judge 新引入的 P0/P1）
└── Phase 15: Output Generation（三文件：primary md + process history + HTML dashboard）
```

**关键工程细节**：Phase 3/4/5/7 subagent 输出写入 `state/reviewer_<name>_phase_<N>.md`，subagent 只返回文件路径 + 100字摘要——orchestrator 不在自己的 context window 里持有 verbatim 输出，按需 read disk（v3.1.0 引入，解决 context pressure）。

---

## 2. 反同质化辩论的具体工程手段——逐项拆解

### 2.1 Blind Final Scoring（Phase 7）

**来源**：ChatEval（ICLR 2024）

**实现**：
- Phase 7 与 Phase 3/4/5 完全隔离：每个 reviewer 被重新 spawn 一个新的 subagent，只能看到自己的 Phase 3 review + Phase 4 reflection，**看不到**他人的 Phase 7 final
- 每人独立给出：final score、top 3 points、recommendation、one-line verdict
- 所有 N 个 blind final 汇入 Phase 14 judge，judge 才能完整看到全部

**为什么有效**：截断 "最后发言者影响力"——若辩论在 Round 3 结束时有一人发表了强势立场，其他人在 Phase 5 的最后一轮可能已经向其靠拢，但 Blind Final 让每人在不知道他人最终立场时独立锁定评分，防止最终评分聚集到最后发言者附近。

**规模限制**：仍然是同底层模型，所有 reviewer 共享 model bias——README 坦白："Unanimous agreement may reflect shared model biases rather than ground truth." Blind Final 防止辩论尾期的 sycophancy，但无法对抗所有人从同一 source lines 读出同一 interpretation 的结构性问题（见 2.4 的 `[STATIC-INFERENCE-CONSENSUS]` 机制）。

**可迁移到 spec-reviewer**：直接搬。spec-author 产出 spec.md 后，多个独立 reviewer subagent 并行读 spec.md，private reflection 后给出 blind final verdict，不看他人意见——防止先看到 author 立场就顺着走。

---

### 2.2 Private Reflection（Phase 4）

**来源**：MachineSoM（ACL 2024），tf/ft/tt/ff conformity tracking

**实现**：
- Phase 4 每个 reviewer 只收到自己的 Phase 3 输出（不含他人意见）
- 任务：re-read 源材料，对每个 finding 评 confidence（High/Medium/Low），标出最不可辩护的 finding，发现新问题
- Phase 4 的 confidence 评级被 Phase 12a 的 Confidence-Based Tier Draft 使用：Low confidence → Deep verification tier，High confidence + 简单事实 → Light tier

**为什么有效**：在辩论开始前锁定 confidence，阻断 "被高声音量 reviewer 压倒后无意识放弃" 的路径——若某 reviewer 在 Phase 4 对某 finding 评为 High confidence，Phase 5 辩论中若无新证据就改口，Phase 6 sycophancy detection 会标记出来（见 2.3）。

**关键证据**（HOW_WE_BUILT_THIS Step 7）：引入 Private Reflection 后的 v2 benchmark 中，Code Quality Auditor 在 private reflection 中自己重新追踪逻辑后主动撤回了一个误报，而非在辩论中被他人说服。这是"self-correction via re-read"而非"social pressure conformity"。

**可迁移到 spec-reviewer**：可以将 spec-reviewer 的 Private Reflection 设计为：reviewer 在看到 author 对初轮反馈的回应前，先独立对自己的每条 objection 评 confidence 级别。这样 author 的后续回复无法让 reviewer 在没有新证据的情况下静默放弃批评。

---

### 2.3 Calibrated Skepticism（Agreement Intensity，20-60% 可配置）

**来源**：DebateLLM（ICML 2024），~15% improvement

**实现（SKILL.md Phase 1）**：

| Persona 类型 | Agreement Intensity |
|---|---|
| Devil's Advocate | 20% |
| Security Auditor / Risk Assessor | 30% |
| Code Quality Auditor | 40% |
| Completeness Checker | 40% |
| Feasibility Analyst | 60% |
| Stakeholder Advocate | 50% |
| Clarity Editor | 60% |

- 该数值注入每个 reviewer 的 Phase 3 system prompt："你的角色 agreement intensity 为 30%——面对他人意见时 70% 倾向维持自己立场，除非对方提供新证据"
- 配合 reasoning_strategy 差异（见 2.5）：Devil's Advocate 使用 Analogical reasoning（"compare to known failure patterns"），Security Auditor 使用 Adversarial simulation（"imagine you are an attacker"），Feasibility Analyst 使用 Backward reasoning（"start from desired outcome"）——不同 intensity + 不同推理路径 = 结构性认知多样性，而非同质辩论

**可迁移到 spec-reviewer**：spec-reviewer 可以设置一个 Devil's Advocate 角色，agreement intensity 20%，且使用"failure mode enumeration"推理策略——不论 author 的 spec 写得多完整，该 reviewer 的任务就是找失效路径，其 intensity 的低设置确保它不会在 author 解释后轻易收手。

---

### 2.4 Sycophancy Detection（CONSENSAGENT，ACL 2025）

**实现（SKILL.md Phase 5/Phase 6）**：

```
Phase 6 (Round Summarization，orchestrator logic，无子 agent):
- 统计每轮所有 position changes（reviewer 改变了立场）
- 判断每次改变是否有新证据支撑（evidence-based）还是纯被说服（rhetoric-based）
- 若 >50% 的 position change 无新证据 → 在下一轮 Phase 5 prompt 里给所有 reviewer 注入 sycophancy alert：
  "Detection: In the previous round, X of Y position changes occurred without new evidence. 
   Maintain your position unless a substantively new argument or evidence is presented."
```

**扩展版本（v3.3.0，`[STATIC-INFERENCE-CONSENSUS]`）**：

Phase 6 还检测一类特殊 sycophancy：多个 reviewer 都同意同一个 claim，但他们的证据来自**同一份 source lines**，没有独立验证。

```
- 若 2+ reviewer 引用了相同的 source lines 来支持同一 claim → 标记 [STATIC-INFERENCE-CONSENSUS]
- 该标记意味着：这是对一份 artifact 的 interpretation 的共识，不是 fact 的独立验证
- [STATIC-INFERENCE-CONSENSUS] 点不能 promote 到 [VERIFIED]，不能用于支撑 P0
- 这些点被路由到 Phase 13 targeted verification，必须通过独立验证才能升级
```

**Phase 14 judge 的反修辞评估**（Anti-Rhetoric，"Talk Isn't Always Cheap"，ICML 2025）：

Judge prompt Step 0.5a-b 要求：
- 识别 Phase 5 中所有 position change
- 判断每次改变是 evidence-driven 还是 eloquence-driven（被修辞说服）
- 对 rhetoric-driven position change：记录但不提升该 finding 的可信度

**可迁移到 spec-reviewer**：这是对 spec-reviewer 防被 author 立场同化的最直接工具：
1. spec-author 提交 spec.md 后，reviewer 给出初始批评
2. spec-author 回应批评（这等同于 Phase 5 辩论）
3. 若 reviewer 在 author 回应后改变了立场，orchestrator 检查：是否有新信息/证据，还是只是 author 更流畅地重申了原立场？
4. 无新证据的 position change → 触发 sycophancy alert，要求 reviewer 显式说明是什么新证据促使改变

---

### 2.5 Diverse Reasoning Strategies（DMAD，ICLR 2025）

**实现**：每个 persona 在 Phase 3 prompt 里携带不同的推理策略注入字符串：

| Persona | Strategy | 注入文本 |
|---|---|---|
| Correctness Hawk | Systematic enumeration | "Enumerate every code path, constant, edge case." |
| Architecture Critic | Backward reasoning | "Start from desired outcome, trace backward." |
| Security Auditor | Adversarial simulation | "Imagine you are an attacker. How would you break this?" |
| Devil's Advocate | Analogical reasoning | "Compare to known failure patterns from similar projects." |
| Stakeholder Advocate | First-principles | "Question every assumption from scratch." |

**关键设计原则**：这不是通过 persona 名称来产生多样性（"你是安全审计师"），而是通过**推理路径**产生多样性——两个人读同一份文档，一个从 outcome 往回推，另一个模拟攻击者正向走，结构性地会 surface 不同的问题集。

**可迁移到 spec-reviewer**：spec design 有多个评审维度可以对应不同推理路径：
- "从用户旅程终点往回推，哪些 spec 约束是必要条件"（Backward reasoning）
- "作为实现者，哪些 spec 声明会让我困惑或有歧义"（First-principles）
- "列举所有可能的 brief 解读方式，spec 是否歧义消除了它们"（Systematic enumeration）

---

### 2.6 Judge Confidence Gating（Trust or Escalate，ICLR 2025 Oral）

**实现**：

Phase 14 Supreme Judge 的 verdict 携带：
```
Verdict Confidence: High | Medium | Low
```

Low confidence → Phase 15.1 report 中强制输出 `⚠️ HUMAN REVIEW RECOMMENDED`

还有一个 correlated-bias warning：若所有 reviewer 的 Phase 7 blind final score 分布极窄（spread < 2），report 中必须插入 "Correlation Notice"，明确提示可能是 shared model bias 而非 ground truth。

**可迁移到 spec-reviewer**：reviewer 对 spec 的每条 objection 应携带 confidence level。若 spec-reviewer 对某一判断的 confidence 为 Low，不能让这条 objection 自动 block 通过；应作为 escalation trigger 升给人类。

---

### 2.7 Phase 13.5 Pre-Judge Verification Gate（防沉默压缩，v3.1.0）

**动机**（HOW_WE_BUILT_THIS Step 17 的一个 latent bug）：subagent 可能静默崩溃并留下 stub 文件——外观上文件存在，实际是空的或不完整的。若不检测，judge 在不完整输入上运行，产出的 verdict 没有任何警告。

**实现**：三重检查：
1. **Existence check** — 文件是否存在
2. **Minimum-bytes check** — 文件 ≥ 500 bytes（低于此视为 stub）
3. **Required-headers check** — 解析文件，确认包含该 phase 的必填 schema section

失败处理：re-dispatch → 单次重试 → 若仍失败，不阻断运行，而是标记 `[COMPRESSED]` 并带显式警告继续（"partial review with loud warning beats no review"）。

**可迁移到 spec-reviewer**：orchestrator 在 dispatch judge/verifier 前，必须验证所有 reviewer 输出文件存在且非 stub——对 spec-reviewer 流水线尤为重要，因为并行 reviewer 在网络/token 压力下可能静默截断。

---

### 2.8 Phase 14.5 Post-Judge Verification Gate（防 judge hallucination，v3.2.0）

**动机**（SKILL.md Phase 14.5 说明）：2026-04-27 README review 中，judge 引入了一个 "12 unresolved git conflict markers P0"——该文件实际是干净的，`wc -l` 和 `grep -c` 都能证伪，但这个幻觉驱动了 3/10 REJECT 判决（issue #41）。

**实现**：
- 分类每个 P0/P1：`[PANEL-RAISED]`（跳过，Phase 11 已验证）vs `[JUDGE-INTRODUCED]`（在这里验证）
- 对每个 `[JUDGE-INTRODUCED]` finding：执行 ground-truth check（grep/Read/git/Bash）
- 产出标签：`[JUDGE-CONFIRMED]`、`[JUDGE-HALLUCINATED]`（降级到 P3 或删除）、`[JUDGE-PARTIAL]`
- 若有 P0 被降级，重算 verdict score

**对 spec-reviewer 的核心启示**：reviewer 自己也可能引入幻觉。若采用 generator-critic 结构，critic agent 的所有 "blocking issue" 都应经过独立 ground-truth 验证，不应直接成为 FAIL verdict 的证据——尤其当 critic 读的是文本 spec 时，它无法执行代码，很容易把 spec 里的描述性语句误读为 bug。

---

## 3. 人留在哪（哪些决策升级给人）

基于 SKILL.md + HOW_WE_BUILT_THIS 的完整流程，人的介入点：

| 触发条件 | 人的决策 |
|---|---|
| Judge Confidence: Low | Phase 15.1 强制输出 `⚠️ HUMAN REVIEW RECOMMENDED`，人决定是否接受结论 |
| Correlated-bias warning（所有 reviewer score spread < 2） | 提示可能 shared model bias，人决定是否重新运行或外部验证 |
| Finding 标 `[DISPUTED]`（reviewer 分歧未解决） | 人最终裁决 |
| Phase 13 Tier = Deep（需要外部知识或生产运行时数据） | 人决定是否要提供外部证据，还是接受 `[VR_INCONCLUSIVE]` |
| Phase 15.3 HTML report 生成失败且重试失败 | 人手动触发 "generate the HTML review report" |
| Phase 13.5 gate：phase output 不可恢复 → `[COMPRESSED]` run | 人决定是否重跑完整 panel |

README 对此有坦白的局限性说明：

> "This is structured self-critique, not independent verification — unanimous agreement may reflect shared model bias rather than ground truth."

人的角色是**结构性的，不是偶发的**：reviewer confidence gating + correlated-bias warning 是让人介入的系统性信号，不是流程故障的降级路径。

---

## 4. 黑盒 CAN / CANNOT

| 机制 | 黑盒 CAN/CANNOT |
|---|---|
| Blind Final Scoring（Phase 7） | CAN — 纯 prompt 隔离：subagent launch 时不携带他人 Phase 7 输出 |
| Private Reflection + confidence rating | CAN — 纯 prompt instruction：要求 reviewer 对每个 finding 评 H/M/L |
| Calibrated Skepticism (20-60% agreement intensity) | CAN — 纯 prompt 注入 agreement intensity 数值 |
| Sycophancy Detection (>50% position change 触发 alert) | CAN — orchestrator 数 evidence-free flips，注入 alert prompt |
| `[STATIC-INFERENCE-CONSENSUS]` 检测 | CAN — orchestrator 比较 reviewer 引用的 source lines 是否重叠 |
| Diverse Reasoning Strategies（DMAD） | CAN — 每个 persona prompt 携带不同的推理策略字符串 |
| Judge Confidence Gating | CAN — judge prompt 要求输出 confidence field |
| Post-Judge Verification Gate（Phase 14.5） | CAN — grep/Read/Bash 核查 judge-introduced findings |
| Pre-Judge Gate 三重检查（bytes + headers） | CAN — orchestrator 执行 bash file size + markdown header parsing |
| Multi-Run Union Protocol（Phase 16 merge） | CAN — 多次运行不同 persona 集，合并 findings |
| Anti-Rhetoric Assessment（Phase 14 judge prompt） | CAN — judge prompt 要求区分 evidence-driven vs eloquence-driven position change |
| Force opus on all subagent launches | CAN — `model: "opus"` 参数 + test 自动验证 co-occurrence |
| Data Flow Trace（Phase 2，semi-formal certificate） | CAN — 纯 prompt instruction，要求 agent 产出结构化 certificate |
| Verification Tier Assignment（confidence-based draft + judge refinement） | CAN — 两步 pipeline：orchestrator logic + 单 Opus 精化 |
| Fine-tune / RLHF / logit access 类方法 | CANNOT — 全库无任何训练步，纯黑盒 prompt orchestration |

---

## 5. 🟢 SHIPPED 标注与证据

🟢 **SHIPPED** — 生产可用 Claude Code plugin，在 marketplace 上线（`claude plugin marketplace add wan-huiyan/agent-review-panel`）。

证据：
- `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json`：符合 Claude Code plugin manifest schema，通过 Claude Code ≥1.0 的 plugin loader
- 401 个测试全绿（Node.js built-in test runner，`npm test`）
- HOW_WE_BUILT_THIS.md 记录了 v1-v3.3.0 的全部 21 个迭代步骤，含 A/B benchmarks、real engagement 案例（PUMA GA4 audit、README review 等）
- CHANGELOG.md 含语义版本历史 v1.0→v3.3.0
- README 样本输出来自对该 README 本身的 2026-05-14 panel run（`docs/reviews/2026-05-14-readme/`），artifacts 已提交至库中

**已在生产中验证的关键数值**：
- v1 vs baseline：100% pass rate（6 assertions）vs 33.3%（HOW_WE_BUILT_THIS Step 4）
- 单次 panel run 覆盖约 60-70% 可发现问题；两次独立 run 仅 ~30% finding overlap（Step 17，consistency analysis）
- Completeness Auditor（Phase 8）在 v2 benchmark 中发现 v1 panel 遗漏的 6 类代码细节（Step 8）

---

## 6. 对 feat-397 实现直接可搬的内容

### 6.1 直接搬（最小改造）

**Blind Final → spec-reviewer 防同化核心机制**

```
实现方案：
- spec-reviewer 的每轮 review 作为独立 subagent launch
- subagent prompt 中不携带任何 author 的前次回应或其他 reviewer 的意见
- reviewer 先给出 blind initial verdict（PASS/FAIL + 问题清单）
- 只有在 author 明确回应后，reviewer 才收到 author 回应 + 自己的 initial verdict
- 若 reviewer 改变立场，必须在 reasoning 中显式说明"新证据/新信息是什么"
```

**Agreement Intensity 注入 spec-reviewer prompt**

```
Devil's Advocate spec-reviewer（agreement intensity 20%）：
注入文本：
"Your agreement intensity is 20%. This means you maintain your position
in 80% of cases unless presented with substantively new information or
evidence. Eloquent re-framing of the same position is not new evidence.
Your role is to stress-test the spec, not to converge toward the author's
framing."
```

**Sycophancy Detection trigger（orchstrator 层实现，无 LLM 成本）**

```python
# orchestrator 数 position changes
flip_without_evidence = 0
for reviewer in reviewers:
    if reviewer.changed_position(round_n, round_n_minus_1):
        if not reviewer.cited_new_evidence():
            flip_without_evidence += 1

if flip_without_evidence / len(reviewers) > 0.5:
    inject_sycophancy_alert(next_round_prompt)
```

**Private Reflection 在 spec-reviewer 中的具体形态**

```
当 spec-reviewer 收到 author 的回应时，先 spawn 一个 reflection 步骤：
- 重读自己的原始批评
- 对每条 objection 标 confidence（H/M/L）
- 标出"如果 author 的回应能说服我放弃这条，需要提供什么样的证据"
然后才看 author 的实际回应
```

### 6.2 工程模式可搬（需要一定适配）

**Phase 13.5 Pre-Judge Verification Gate → milestone 合并前的 artifact 完整性检查**

feat-397 的 spec-reviewer 产出 spec-verdict.md，design-reviewer 产出 design-verdict.md。在 orchestrator dispatch judge/集成前，必须验证这些文件的完整性（existence + bytes ≥ 500 + required headers），而非只检查文件是否存在。

**[STATIC-INFERENCE-CONSENSUS] 检测 → spec/design 中的 "多人一致反对" 处理**

若多个 reviewer 都反对同一条 spec 声明，但他们的反对来自同一个 spec 原文的同一段落（没有引入独立证据），这只是对该段落的共同误读——不应自动判 FAIL。应标 `[CONSENSUS-NEEDS-VERIFICATION]`，升给人类裁决，或要求独立 challenger 从不同角度验证。

**Verification Tier Assignment（confidence-based draft + refinement）→ escalation 决策分层**

spec-reviewer 的每条 objection 可以分层：
- Low confidence objection → 建议但不 block（Light tier）
- Medium confidence → 需要 author 提供具体澄清（Standard tier）
- High confidence + 可用 spec 文本证伪 → block + 要求修改（Deep tier）

tier assignment 第一步是 orchestrator logic（based on reviewer confidence rating），第二步可以是一个独立的轻量 judge subagent 精化——而不是每次都跑重量级 judge。

**Phase 14.5 Post-Judge Verification → spec-reviewer 防幻觉保障**

若 spec-reviewer 产出了 FAIL verdict，orchestrator 应对 FAIL 的依据做一次 ground-truth check：
- 是否 spec.md 中确实存在 reviewer 声称的问题（文本 grep + 段落引用）
- reviewer 的批评是否引用了正确的 spec 段落
- 若 reviewer 声称 "X is missing from spec" 但 X 确实在 spec 的某章节 → 降级为 WARNING，不 FAIL

### 6.3 直接挪用的 Anti-Pattern 列表（feat-397 要避免的）

从该库的 HOW_WE_BUILT_THIS 中提取的反面教训，直接适用于 spec-reviewer 设计：

1. **"Debate shifts cognitive mode from discovery to argumentation"**（Step 5）：不能只有 debate 没有 discovery。spec-reviewer 的 debate 是评估 spec 声明，但 discovery（是否遗漏了关键的未表达假设/约束）需要一个独立的 Completeness Auditor 角色，专门扫描 spec 里没有说的东西。

2. **"All downward-pressure mechanisms need a corresponding upward-pressure mechanism"**（Step 13，Lesson 19）：若 spec-reviewer 只增加严格性（更多检查点、更严格的 FAIL 条件），会在减少 false positive 的同时增加遗漏真实问题的风险。每个"收紧"机制需要配一个"兜底"机制（等价于 Phase 8 Completeness Auditor）。

3. **Silent phase compression**（v3.1.0 的动机）：subagent 可能静默崩溃留下 stub。不能因为 reviewer subagent 返回了文件路径就认为输出完整——bytes check + required headers check 是必要的。

4. **Force opus on ALL launches including specialist agents**（v2.14 修复的 latent bug）：若不显式 override model，specialist subagent 可能用 sonnet/haiku 运行，跨 run 推理深度不一致。在 feat-397 的 subagent dispatch 中，永远显式传 model 参数。

---

## 7. 本库对"朴素 multi-agent debate 常帮倒忙"这一张力的处理

该库没有回避这个张力——README 坦白写明"all reviewers are Claude instances; unanimous agreement may reflect shared model biases rather than ground truth"。但它给出了具体的工程手段区分"真正增加能力的多 agent 分解"vs"只加成本/噪声的同质辩论"：

| 模式 | 是否只加成本/噪声 | 如何真正增加能力 |
|---|---|---|
| 4个相同 persona 辩论 | 是——Martingale Curse | 通过不同 persona + 不同 agreement intensity + 不同 reasoning strategy 的**结构性认知多样性**打破对称 |
| 辩论后多数投票 | 是——被修辞压倒 | 通过 Phase 7 Blind Final（辩论前锁定，辩论后不看他人 final）+ Anti-Rhetoric judge 防修辞主导 |
| 多 agent 同时读 source → 共识 | 是——`[STATIC-INFERENCE-CONSENSUS]` | 通过检测是否引用了相同 source lines，强制路由到独立验证而非直接 promote |
| 同质 judge | 是——模型偏见叠加 | Supreme Judge 的设计是 domain-neutral，且 Phase 14.5 对 judge 自己引入的 findings 也做 ground-truth falsification |

HOW_WE_BUILT_THIS Lesson 1（Step 9）直接总结了这个结构：

> "Debate trades discovery for argumentation. Multi-agent debate is excellent for evaluating the significance of findings but bad for finding them. Always add a dedicated discovery phase (like the Completeness Auditor) that ignores the debate entirely."

这与 feat-397 的核心命题直接对应：单 agent 在 spec/design 上做不好的，不是辩论不足，而是没有**专职角色**分别承担 discovery（遗漏的假设/约束）、adversarial stress-test（证伪 spec 声明）、independent verification（独立 ground-truth 核查），而是把这些全压在一个 agent 身上。

---

## 附录：关键文件路径

| 文件 | 路径 | 含义 |
|---|---|---|
| SKILL.md（主 skill 定义） | `skills/agent-review-panel/SKILL.md`（1739行） | 16个 phase 的完整 prompt orchestration 规范 |
| 设计历程 | `HOW_WE_BUILT_THIS.md`（883行） | 21个迭代步骤，含 benchmark 数据和 46 条 Lesson |
| 研究基础 | `docs/research-foundations.md` | 9篇论文 × 具体机制映射表 |
| prompt 模板 | `skills/agent-review-panel/references/prompt-templates.md` | 所有 phase 的 subagent prompt 模板（Phase 2 Data Flow Tracer 等） |
| plan 集成 skill | `skills/plan-review-integrator/SKILL.md` | plan-review-integrator，reviewer 输出 → plan 更新的闭环 |
| 真实 review 输出 | `docs/reviews/2026-05-14-readme/` | 对该 README 自身运行的完整 panel artifacts |
| v2.8 研究文档 | `skills/agent-review-panel/references/research-v28.md` | 19个来源的 severity calibration + multi-agent debate 研究综述 |
