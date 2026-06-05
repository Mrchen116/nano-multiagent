# AgenticAKM: Enroute to Agentic Architecture Knowledge Management

> **来源**: arXiv:2602.04445 — Rudra Dhar, Karthik Vaidhyanathan, Vasudeva Varma (IIIT Hyderabad, sa4s-serc)
> **代码**: https://github.com/sa4s-serc/AgenticAKM（开源，MIT）
> **标注**: 🟡 RESEARCH（学术论文 + 开源实现；尚无已知生产部署证据）
> **本轮焦点**: 五角色流水线中 generator-critic 对的能力增量量化；有界 loop 的终止条件；SummaryChecker 防幻觉机制

---

## 1. 单 agent 的失败模式——论文针对的是哪个问题

AgenticAKM 的出发点是 Architecture Knowledge Management（AKM）的"低采用率困境"：架构决策记录（ADR）理论上对软件可维护性至关重要，实践中却几乎无人坚持写。原因是它"laborious"——从代码库中提取分散的架构知识、形成结构化 ADR，对人来说费力，对单 LLM 来说有三个具体失败：

| 单 agent 失败模式 | 具体表现 |
|---|---|
| **Context 容纳不下分布式知识** | 代码库的架构知识分散在数百个文件里；单 prompt 塞进所有文件会超出 context 窗口，或 LLM 在超长 context 中注意力发散，导致遗漏关键决策 |
| **Completeness 系统性低** | 用户研究结果：LLM-only 的 Completeness 得分（GPT: 3.7、Gemini: 3.0）显著低于 Agentic（3.9 / 3.8）；定性反馈：LLM-only 输出"very abstract and generic"，"occasional omissions and limited reasoning depth" |
| **无自我核验机制，幻觉传播** | 单 prompt 对自己声称的架构摘要没有独立验证步骤；生成的 ADR 可能与实际代码库结构不符但 LLM 无法察觉 |
| **Objective 满足即止** | 单 agent 完成"生成一份 ADR"的 objective 后即停；没有"这份 ADR 是否准确反映了代码库"的独立 critic 驱动迭代 |

这四个失败模式在 spec/design 场景的映射：**Context 容纳不下分布式知识** 对应 spec 阶段"需求分散在 brief + 历史对话 + 产品文档里"；**无自我核验** 对应 spec 阶段 author 产出的文档与实际用户意图偏离而无人察觉；**Objective 满足即止** 对应 design 阶段 agent 产出了"看起来完整"的设计但缺乏架构约束检验。

---

## 2. Multi-agent 结构——五角色流水线拓扑

### 2.1 实际角色列表（与论文代码一致）

论文命名与代码（`AdrAgents.py`）有轻微出入，以代码为准：

```
OrchestratorAgent
    │
    ├─► RepoSummarizer          [Extractor / Generator-1]
    │       │ summary
    │       ▼
    │   SummaryCheckerAgent     [Critic-1 / 独立验证器]
    │       │ (correct, feedback)
    │       └─► 最多 3 轮 feedback loop → RepoSummarizer
    │
    └─► AdrWriterAgent          [Generator-2]
            │ ADRs
            ▼
        AdrCheckerAgent         [Critic-2 / 独立验证器]
            │ (correct, feedback)
            └─► 最多 3 轮 feedback loop → AdrWriterAgent
```

**人类 Architect**（论文中第五个"角色"）= 配置初始工作流、监控执行、可随时介入——即 human-on-the-loop，不是 LLM agent。

**信息流向**：两个独立 generator-critic 对串联；Critic 的 feedback 作为下一轮 Generator 调用的额外参数传入（`summary_or_feedback` 参数）。

### 2.2 两个 Generator-Critic 对的分工

**对一：RepoSummarizer ↔ SummaryCheckerAgent**
- 目的：从代码库提取准确的架构摘要（"基础事实层"）
- 分工分离点：Summarizer 做提取，Checker 做验证——两者 objective 不同，Checker 不帮助生成，只做真/假判断

**对二：AdrWriterAgent ↔ AdrCheckerAgent**
- 目的：从已验证摘要生成 ADR；Checker 确保 ADR 与摘要（而非直接与源码）逻辑一致
- 注意：Pair-2 的 Checker 验证对象是摘要而非源码，这是有意的层级设计——防止 Checker-2 重做 Checker-1 的工作

---

## 3. Generator-Critic 能力增量——定量证据

### 3.1 用户研究数据（29 个仓库，13 名参与者，盲测，1-5 分制）

| 指标 | LLM-only GPT | LLM-only Gemini | Agentic GPT | Agentic Gemini | 提升幅度 |
|---|---|---|---|---|---|
| Relevance | 3.8 | 3.8 | 4.1 | 4.3 | +0.3 ~ +0.5 |
| Coherence | 3.8 | 3.6 | 4.3 | 4.1 | +0.5 ~ +0.3 |
| **Completeness** | **3.7** | **3.0** | **3.9** | **3.8** | **+0.2 ~ +0.8** |
| Conciseness | 3.5 | 3.4 | 3.9 | 4.1 | +0.4 ~ +0.7 |
| **Overall** | **3.3** | **3.3** | **3.8** | **3.9** | **+0.5 ~ +0.6** |

- **Overall 提升约 15–18%**（绝对值 0.5–0.6 分），跨两个 LLM 一致。
- **Completeness 提升最大**（Gemini 从 3.0 → 3.8，+27%）——正是"分布式知识漏掉"失败模式被 Critic-1 补上的直接证据。
- **统计显著性**：论文未做显著性检验（无 p 值/置信区间），13 个参与者样本量较小，需谨慎推断。

### 3.2 定性增量

> "actually captured different underlying decisions" vs LLM-only "very abstract and generic"

这条反馈直接指向 SummaryChecker 的贡献：独立验证强制 Summarizer 提取"不同的、具体的"架构决策，而非生成泛化描述。

---

## 4. SummaryChecker 防幻觉的具体机制

这是本论文技术上最值得细读的部分（源码可验证）：

### 4.1 独立重构 + LLM 比较

```python
# SummaryCheckerAgent.verify_summary() 核心逻辑（源码重建）
actual_tree = reconstruct_directory_tree(repo_path, ignore_patterns)
# actual_tree 是文件系统的真实目录树字符串，与 LLM 生成无关

prompt = f"""
Compare this ACTUAL repository structure:
{actual_tree}

Against this SUMMARY:
{summary_text}

Respond with exactly:
CORRECT: <justification>
or
INCORRECT: <specific mismatches, e.g. "Summary incorrectly identifies this as Python project">
"""
result = llm.call(prompt)
is_correct = result.startswith("CORRECT")
feedback = result[result.index(":")+1:].strip()
```

**关键设计**：
1. `actual_tree` 由代码确定性生成（`os.walk` + 过滤），完全绕过 LLM——这是"地基"，不受幻觉污染
2. Checker 自己也是 LLM，但它的 job 是"比对真实 vs 声称"，而非"生成"——reducing task from generation to verification
3. 返回格式强制为 CORRECT/INCORRECT 前缀（`startswith` 解析），而非自由文本

### 4.2 为什么这能防幻觉传播

单 agent 场景：Generator 产生的错误摘要直接成为 ADR 生成的输入→错误在 ADR 层放大。

Multi-agent 场景：SummaryChecker 将"Generator 对源码的主观描述"与"文件系统的客观事实"做对比——这是引入了独立信息源（文件系统真值），而不仅仅是另一个 LLM 重读同一内容。这是与普通"LLM 自我反思"的本质区别。

**局限**：Checker 只验证目录结构和项目类型（Python vs JS），无法深入验证逻辑层的架构声明（如"这个项目用了 CQRS 模式"是否属实）——那需要读懂代码语义，超出当前 Checker 的能力范围。

---

## 5. 有界 Loop 的终止条件设计

### 5.1 实现细节（源码级）

```python
# OrchestratorAgent 内的两处 loop（结构一致）
for attempt in range(max_attempts):  # max_attempts = 3
    summary = summarizer.summarize(repo_path, feedback=feedback)
    is_correct, feedback = checker.verify_summary(summary, repo_path)
    if is_correct:
        break
    # 若未 break，feedback 传入下次 summarize()

# max_attempts 耗尽后：注释掉的 halt 条件 → 直接进入下一阶段
```

### 5.2 三轮上限的设计理由

论文未给出理论推导，但 3 轮是 multi-agent refinement 的经验共识（MetaGPT、INDICT 均在 2-3 轮后边际收益趋零）。三轮可覆盖：
- 轮 1：修正明显结构错误
- 轮 2：填补遗漏的主要组件
- 轮 3：对齐细节描述与事实

### 5.3 max_attempts 耗尽后——未解决的终止问题

**这是论文的一个设计缺陷**：源码注释显示 halt 条件被注释掉（"commented-out halt conditions suggest incomplete early-termination logic"），三轮后无论 Checker 仍持 INCORRECT 还是成功通过，都继续进入下一阶段。

实际效果：max 3 轮后直接把最后一个（可能仍不正确的）输出传给下游，没有 human escalation，没有 fallback 输出标记，没有警告。这是论文与工程化系统之间的差距。

对 feat-397 的启示：**有界 loop 必须定义 fallback 策略**——至少要在 max 轮后触发 human escalation，而不是静默继续（否则下游处理的是已知错误的输入）。

---

## 6. 人留在哪——哪些决策必须升级给人

论文中的 human Architect 角色定义（"configures initial workflow, monitors execution, can intervene"）实际上是 human-on-the-loop 而非 human-in-the-loop。具体需要人介入的场景：

| 场景 | 论文处理方式 | 工程化应补充 |
|---|---|---|
| 3 轮后 Checker 仍 INCORRECT | 静默继续（缺陷） | 应升级 human 决策：接受有缺陷输出 or 人工修正 |
| 仓库类型超出工具能力（二进制、多语言混合等） | 未处理 | 应 early exit + human 通知 |
| 架构判断无法从代码推断（仅有注释/文档说明意图）| 未处理 | 需人工补充语义标注 |
| ADR 生成后的"是否要创建这条决策记录"价值判断 | 全量生成，无筛选 | 需人类过滤——不是所有可被检测的决策都值得记录 |

---

## 7. 黑盒 CAN / CANNOT

| 技术/机制 | 黑盒 CAN/CANNOT | 说明 |
|---|---|---|
| 两级串联 generator-critic 对 | **CAN** | 纯 prompt + 文本 I/O |
| Feedback 参数传递（feedback→下一轮调用）| **CAN** | 字符串参数注入 |
| 有界 loop（for attempt in range(N)）| **CAN** | 外部控制流，与 LLM 解码无关 |
| CORRECT/INCORRECT 前缀强制格式 | **CAN** | 输出格式约束，zero-cost |
| 确定性基准（文件系统 directory tree）作为 Checker 真值 | **CAN** | 关键：Checker 的"地基"来自代码系统，不来自 LLM |
| Pydantic schema 约束 ADR 结构 | **CAN** | 结构化输出 |
| 深层语义验证（"是否真的用了 CQRS"）| **CANNOT**（当前）| 需代码语义理解，超出纯文本比对 |

---

## 8. 🟡 RESEARCH 标注与已知局限

**🟡 RESEARCH**——论文已发表（arXiv 2602.04445），代码开源（GitHub sa4s-serc/AgenticAKM），但：
- 13 个参与者、29 个仓库，样本量较小，无统计显著性检验
- 无生产部署证据，无 Java 以外多语言充分验证（论文提到 Java 仓库 LLM-only 表现更接近 Agentic，提示 Completeness 收益与语言相关）
- 有界 loop 的 fallback 策略未完成（halt 逻辑被注释掉）
- Checker 只验证结构层，不验证语义层

---

## 9. 对 feat-397 直接可搬的内容

### 9.1 直接可搬的模式（高置信度）

**模式一：独立验证器引入外部真值**

AKM 里的"外部真值"是文件系统目录树；spec/design 场景的对应物是：
- Spec 阶段：用户 brief 原文 + 历史对话记录（anchor documents）
- Design 阶段：已通过门禁的 spec.md（immutable contract）

SummaryChecker 的机制可直接移植为：SpecChecker 把"spec 文档中的声明"与"brief anchor 里的原始需求"做对比，而不是让 SpecAuthor 自审——两者 context 分离，Checker 不携带 Author 的推理链。

**模式二：两级串联 generator-critic，层级分工明确**

- Pair-1（spec 层）：SpecAuthor → SpecChecker（对比 brief anchor）
- Pair-2（design 层）：DesignAuthor → DesignChecker（对比已锁定 spec.md）

Checker-2 只验证 design 与 spec 的一致性，不重做 Checker-1 的工作——这是论文架构里"层级分工"的核心，防止下游 Checker 做重复验证或引入新的判断维度。

**模式三：CORRECT/INCORRECT + feedback 强制格式**

Checker 输出格式：
```
CORRECT: <justification>
INCORRECT: <specific issues, actionable feedback for next iteration>
```

- `startswith("CORRECT")` 解析，零歧义
- feedback 字符串直接注入下一轮 Generator 调用（不是新的 system prompt，是追加的 user context）

**模式四：有界 loop（max=3）+ 显式 fallback**

论文的 max=3 是合理上限，但必须补上论文缺失的 fallback：

```python
for attempt in range(3):
    output = generator.run(input, feedback=feedback)
    ok, feedback = checker.verify(output)
    if ok:
        break
else:
    # 论文缺失这里——feat-397 必须补上
    escalate_to_human(
        message="3轮后 Checker 仍未通过，请人工决策",
        last_output=output,
        last_feedback=feedback
    )
    return  # 不继续下游
```

### 9.2 需要适配的差异

| AgenticAKM 的设计 | feat-397 的差异 | 需要调整 |
|---|---|---|
| 外部真值 = 文件系统 directory tree | 外部真值 = 用户 brief 原文（非结构化文本）| Checker 的 grounding 改为"brief 原句 + 意图声明"比对，而非目录树比对 |
| ADR 是已有知识类型（有标准格式）| Spec/Design 是新创建文档（格式由我们定义）| 格式模板 + Pydantic schema 仍可用，但 schema 自己定义 |
| 仓库是客观存在 | Brief 是主观意图表达 | Checker 无法像文件系统那样做完全确定性 grounding；需补充"对 brief 中明确约束点的 checklist" |
| Human-on-the-loop（监控+可介入）| feat-397 已有 IM escalation 通道 | 直接复用，但需定义触发条件（3轮失败 + 值域岔路问题） |

### 9.3 不可搬的部分

- **Completeness 量化评测**：AgenticAKM 用人类用户研究（13人）量化；feat-397 目前无可用的 judge 评测框架，这是 spec/design 场景的卡脖子问题（与第一轮报告结论一致）。
- **语义层验证**：论文的 SummaryChecker 只验证结构；AdrChecker 只验证摘要→ADR 逻辑；真正的"spec 是否准确捕获了产品意图"需要更深的语义理解，当前无法自动化。

---

## 10. 与前两轮报告的关系

| 前两轮已有结论 | AgenticAKM 的补充/确认 |
|---|---|
| Generator-Critic 顺序对增加能力（MetaGPT、INDICT、CVE-Genie）| **量化确认**：29 仓库 Overall +15-18%，Completeness +27%（Gemini）；代码级可验证 |
| Critic 应独立 context 窗口（不携带 author 推理链）| **机制确认**：SummaryChecker 独立 context + 引入外部真值（目录树）而非 LLM 内部比对 |
| 有界 loop（MetaGPT 2-3轮经验值）| **代码确认**：max_attempts=3，但揭露了一个论文中的设计缺陷——fallback 逻辑被注释掉 |
| Spec 作为 immutable contract（OpenEvolve 反例）| **角色间信息流确认**：Checker-2 只读 spec（已验证摘要），不重新读源码——层级隔离防止下游绕过上游验证 |
| Human escalation 是必要约束而非临时妥协 | **缺失证据**：论文未设计 escalation，导致 3 轮后静默继续——这是反面教材，进一步支撑 feat-397 必须显式 escalation |

---

## 结论

AgenticAKM 是第一轮/第二轮报告中 Generator-Critic 模式的一个**可验证实例**，其贡献在于：
1. 在 29 个真实仓库上提供了量化的能力增量数据（Overall +15-18%，Completeness +27%）
2. 揭示了"引入外部真值而非 LLM 自我比对"是 Critic 防幻觉的关键机制
3. 开源代码（`AdrAgents.py`）提供了两级串联 generator-critic + 有界 loop 的可直接参考实现
4. 同时揭示了一个设计缺陷（fallback 逻辑注释掉），为 feat-397 提供了反面教材

对 feat-397 的核心迁移价值：**SpecChecker 必须 ground 在 brief anchor（外部真值）上，而非只让 Author 自审**；**有界 loop 的 fallback 必须触发 human escalation，而非静默继续**。这两点是超越论文现有实现的关键补强。
