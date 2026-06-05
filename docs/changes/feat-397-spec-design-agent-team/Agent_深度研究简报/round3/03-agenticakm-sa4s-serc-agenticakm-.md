# Round 3 深挖报告：AgenticAKM — AdrWriter→AdrChecker Generator-Critic 对的代码级解剖

> **源**：https://github.com/sa4s-serc/AgenticAKM （ICSE 2025 Workshop 论文）  
> **克隆路径**：`/tmp/claude-feat397-r3/03-agenticakm-sa4s-serc-agenticakm-`  
> **关键文件**：`Code/AdrAgents.py`、`Code/AgenticAdr.ipynb`、`Code/evaluations.ipynb`  
> **完成日期**：2026-06-04  
> **前置**：本轮是第一轮/第二轮报告的延伸深挖，不重复已有发现。

---

## 0. 源的定位

AgenticAKM 是 IIIT Hyderabad SA4S 实验室发表于 ICSE 2025 Workshop 的研究性代码库。它的命题与 feat-397 高度同构：把一个需要人类架构师才能做好的、高度知识密集型的"从代码库提取设计决策并文档化"任务，交给多 agent 系统自动完成。其核心贡献是在**黑盒 LLM**（Gemini 2.5 Pro / GPT-5）上验证了一个**双层 generator-critic 对**能系统性优于 single-LLM-call 基线，并在 29 个真实仓库的用户研究中取得了可量化的质量增量。

标注：**🟡 RESEARCH**（ICSE 2025 Workshop，有 arXiv/PDF，有可运行代码，但无生产部署证据）

---

## 1. 单 agent 的哪些失败模式，用什么 multi-agent 结构去补

### 1.1 被攻击的失败模式：单次 LLM 调用的"上下文压缩幻觉"

论文和代码共同揭示的根本失败模式是：**单个 LLM call 在面对完整代码仓库时，会在不具备完整证据的情况下自信地合成一个"完整"的总结或文档**——即幻觉不是随机噪声，而是系统性的"过度自信合成"。

具体表现（来自 `AgenticAdr.ipynb` 执行日志，GPT-5 对 `karthikv1392/cs6401_se` 仓库的第一次尝试）：
- 第一次生成的 summary 声称包含"具体 gem 版本 `webrick ~> 1.7`"、"GitHub Pages 托管确认"等细节
- Checker 给出的反馈：`INCORRECT: The summary includes several unverified specifics not supported by the provided file/directory listing`
- 第二次修正后 summary 仍然断言具体 hosting，再次被 checker 打回
- 第三次后才通过

这与 feat-397 场景的映射：spec-author 在没有充分澄清的情况下，倾向于填充假设性细节而非显式标记"待确认"——单 agent 无法从外部质疑自己的假设。

**失败模式 1：无法从外部质疑自己生成内容中的未经支撑的断言。**

### 1.2 被攻击的失败模式：单一 context 下的 objective 满足即止

代码基线（`CodeToAdr.ipynb`）是一次 LLM 调用同时完成"分析仓库结构"+"生成 ADR 集合"。单 agent 优化的目标是"使 ADR 读起来合理"，而非"确认每条 ADR 都有代码证据"。这是不同的 objective。

双层结构把 objective 显式拆分：
- AdrWriter 的 objective：基于已验证的 summary 生成结构完整、逻辑自洽的 ADR
- AdrChecker 的 objective：验证每条 ADR 的 Context/Decision/Consequences 是否直接被 summary 中的证据支持

两个 objective 分开后，AdrChecker 可以在不被 AdrWriter 的"成就感"污染的前提下，独立判断"ADR-2 关于 PostgreSQL 的断言与 summary 中 H2 数据库描述矛盾"。

**失败模式 2：生成 agent 不会主动反驳自己刚刚生成的内容。**

### 1.3 被攻击的失败模式：长流程中的 context 污染

`RepoSummarizer` 需要读取仓库中最大的 5 个文件（`_summarize_key_files`），这些文件内容被截断到前 4000 字符后传入。如果同一个 agent 同时持有这些原始文件片段 + 中间总结 + ADR 生成逻辑，context 中的噪声（截断点、文件命名歧义）会影响后续 ADR 生成判断。

多 agent 拓扑通过"阶段性验收 + 只传 artifact"来控制 context 污染：
- SummaryChecker 只接收：`tree_str[:4000]` + `summary`，不携带原始文件内容
- AdrWriter 只接收：`summary`（已验证），不携带仓库原始文件
- AdrChecker 只接收：`summary` + `adrs_text`，不携带仓库原始文件或 writer 的内部推理

**失败模式 3：单一 context 窗口中噪声随任务深度累积，影响后续判断质量。**

---

## 2. Multi-Agent 结构的代码级实现细节

### 2.1 五角色与拓扑

```
OrchestratorAgent
  ├── RepoSummarizer          (Generator 层 1)
  ├── SummaryCheckerAgent     (Critic 层 1)
  ├── AdrWriterAgent          (Generator 层 2)
  └── AdrCheckerAgent         (Critic 层 2)
```

所有五个角色在 `OrchestratorAgent.__init__` 中被同一个进程实例化，**共享同一个 LLM model_name**（设计选择：同质模型，不同 prompt objective，不同 input context）。

### 2.2 独立 Context 如何传递

这是本轮的核心观察点。AgenticAKM 的"独立 context"不是通过框架层的 context isolation（无 sub-process、无独立 API session），而是通过**严格的 artifact 传递边界**实现的：

**Loop 1（Summary 层）：**

```python
# OrchestratorAgent.run() 中
summary = self.summarizer_agent.summarize_repo(repo_path=repo_path, feedback=summary_feedback)
is_summary_correct, summary_feedback = self.summary_checker_agent.verify_summary(
    summary=summary,        # 只传文本 artifact
    repo_path=repo_path     # 传路径，Checker 自己独立读 tree_str
)
```

关键：`SummaryCheckerAgent.verify_summary` 中，Checker **自己独立重建** `tree_str`（`os.walk`），而不是使用 RepoSummarizer 在生成 summary 时用的那份 `tree_str`。这意味着 Checker 的 context 是：
- `tree_str[:4000]`（独立构建，不携带 RepoSummarizer 的 file_summaries 中间产物）
- `summary`（待验证的 artifact）

Checker prompt 中没有 RepoSummarizer 的 `file_summaries`、`dependencies` 等中间推理内容。这是真正的独立视角，因为 Checker 看不到 Generator 为什么生成这个 summary，只看到 summary 本身与仓库结构是否一致。

**Loop 2（ADR 层）：**

```python
list_of_adr_objects, list_of_adr_strings = self.adr_writer_agent.write_adrs(
    summary=summary,        # 已验证的 summary artifact
    feedback=adr_feedback
)
are_adrs_correct, adr_feedback = self.adr_checker_agent.verify_adrs(
    summary=summary,        # 同一个 summary
    adrs=list_of_adr_strings  # 待验证的 ADR artifact
)
```

AdrChecker 的 context 是：`summary` + `adrs_text`。没有 AdrWriter 的内部 `_extract_design_decisions` 中间步骤（那个步骤先提取 JSON 再格式化为 markdown）。Checker 只看最终 markdown 产出，不看 writer 的 chain-of-thought。

**实现形式**：每个 agent 类持有独立的 `self.model = LLMCaller(model_name)` 实例，但 LLMCaller 是无状态的（每次 `.call(prompt)` 都是新的 API 请求，没有 conversation history）。这意味着"独立 context"是通过**无状态 LLM call + 精心选择传哪些 artifact**实现的，而非通过框架层的 session 隔离。

### 2.3 有界反馈 Loop 的终止条件

```python
# Loop 1: max_attempts = 3（由调用方传入，默认 3）
for attempt in range(max_attempts):
    summary = self.summarizer_agent.summarize_repo(repo_path=repo_path, feedback=summary_feedback)
    is_summary_correct, summary_feedback = self.summary_checker_agent.verify_summary(...)
    if is_summary_correct:
        break
    # else: 继续下一轮，summary_feedback 携带 checker 的 FEEDBACK 文本

# Loop 2: 同样 max_attempts 轮
for attempt in range(max_attempts):
    list_of_adr_objects, list_of_adr_strings = self.adr_writer_agent.write_adrs(
        summary=summary, feedback=adr_feedback
    )
    if not list_of_adr_strings:  # 空产出边界条件
        adr_feedback = "..."  # 强制 feedback
        continue
    are_adrs_correct, adr_feedback = self.adr_checker_agent.verify_adrs(...)
    if are_adrs_correct:
        break
```

终止条件：
1. **PASS**：`is_correct = result_text.startswith("CORRECT")`，退出 loop，进入下一阶段
2. **超限**：`attempt >= max_attempts - 1`，loop 自然结束，**不停机**（注释掉的 `return []` 说明这是有意决策——即使未收敛也继续向下传递当前最优产出）
3. **空产出**：AdrWriter 返回空列表时，强制注入标准 feedback 重试

注意：原代码中两个 `# if not is_XXX_correct: return []` 都被注释掉了。这意味着即使 Checker 在所有轮次都判定 INCORRECT，系统仍然会以最后一轮的产出继续执行，而非中止。这是一个明确的"best-effort"语义选择，不是 hard gate。

### 2.4 Orchestrator 如何路由 PASS/FAIL

```python
# OrchestratorAgent.run() 中的路由逻辑（简化）:

# --- LOOP 1 结束后 ---
# is_summary_correct: bool  → 如果 False 且 loop 用完，静默继续（不停机）
# summary: str              → 不管 is_summary_correct 如何，都用最后产出的 summary 进 Loop 2

# --- LOOP 2 结束后 ---
# are_adrs_correct: bool    → 如果 False 且 loop 用完，静默继续（不停机）
# list_of_adr_objects/strings → 直接传给 _save_adrs()
```

Orchestrator 没有实现基于 PASS/FAIL 的分支路由（如"FAIL 则 escalate 给人"）。路由逻辑极简：loop 内部 PASS 则 break，loop 外部不管结果如何都继续流水线。这是研究原型的简化，不代表生产设计建议。

---

## 3. 质量增量数据（29 仓库用户研究）

来自 `Code/evaluations.ipynb` 的完整评分表（5 分制，N=29 仓库，参与者提交自己熟悉的仓库并评分）：

| 条件 | 模型 | Relevance | Coherence | Completeness | Conciseness | Overall |
|---|---|---|---|---|---|---|
| **Agent（多 agent 流水线）** | GPT-5 | **4.5** | **4.0** | **4.0** | **4.5** | **4.0** |
| **Agent（多 agent 流水线）** | Gemini 2.5 Pro | **4.5** | **4.5** | **4.0** | **4.0** | **4.5** |
| LLM（单次调用基线） | GPT-5 | 3.0 | 3.5 | 3.0 | 3.5 | 3.0 |
| LLM（单次调用基线） | Gemini 2.5 Pro | 4.0 | 3.5 | 2.5 | 3.5 | 3.5 |

**质量增量**（Overall，相同模型对比）：
- GPT-5：4.0 vs 3.0，**+1.0 分（+33%）**
- Gemini：4.5 vs 3.5，**+1.0 分（+29%）**
- Completeness 增量最显著：Gemini Agent vs LLM 为 4.0 vs 2.5（**+60%**）

**关键发现**：质量增量在两种模型上一致（GPT-5 和 Gemini 都有约 +1 分 Overall 提升），说明这是结构性增量而非模型特有效应。

**局限性**：参与者是学生/研究者（多数 0 年行业经验），评分方是仓库所有者（不完全独立），评分人数不足以做统计显著性检验。数据可作为方向性证据，不可作为精确量化依据。

---

## 4. 独立 Context 带来的具体质量增量机制

通过对比 `dir1`（单次调用，Gemini）和 `dir3`（Agent，Gemini）生成的 amazon-clone ADR：

**单次调用（dir1）** 的 ADR-001：
- Status: `Inferred`（明确标注不确定性）
- Decision 中引用了具体文件证据：`.firebaserc`、`firebase.json`、`functions/package.json`
- Consequences 结构化为 Positive/Negative 列表，包含"vendor lock-in"、"cold starts"等专业分析

**Agent 流水线（dir3）** 的 ADR-001：
- Status: `Proposed`（Checker 确认后才落盘）
- 措辞更简洁但覆盖度相当
- 没有引用具体文件证据（因为 AdrWriter 只看 summary，不看原始代码）

有趣的发现：在这个特定案例中，单次调用的 ADR 反而包含了更丰富的原始证据引用（因为它直接读代码），而 Agent 流水线的 ADR 由于 AdrWriter 只能依赖经过 SummaryChecker 过滤后的 summary，反而丢失了部分代码级细节。

这揭示了一个关键的**架构张力**：
- Checker 的独立 context 提高了 **factual accuracy（不说错）**
- 但信息经过 summary 这一中间层压缩后，可能降低了 **detail richness（说全）**
- 评分数据中 Completeness 增量（Gemini Agent 4.0 vs LLM 2.5）表明这个张力在总体上被 Checker 的纠错效果所盖过——单次调用虽然有更多细节，但更多细节中有更多错误，导致 Completeness 感知反而更低

---

## 5. 人留在哪

AgenticAKM 在研究原型中**完全无人介入**——整个流水线从 repo URL 到落盘 ADR 文件全自动。代码中没有任何 human checkpoint：
- 没有"FAIL 超限后发通知给人"逻辑
- 没有"ADR 最终输出前等人确认"步骤
- 被注释掉的 `return []`（原本可以停机待人干预）被替换为静默继续

这是研究原型有意为之的简化（为了评估纯自动化的上限），而非生产设计建议。

**对 feat-397 的隐含信号**：研究原型的"无人"设计恰好暴露了它的局限——Checker 在多轮后仍 INCORRECT 时，系统无法区分"我确实做不到更好"和"需要人来裁决这个价值判断"。生产场景必须在此加 escalation：`max_attempts` 超限 + FAIL 时，将 Checker 的最后一条 feedback 发给用户，等待裁决。

---

## 6. 黑盒 CAN / CANNOT

| 机制 | 黑盒 CAN/CANNOT | 说明 |
|---|---|---|
| generator-critic 对（两阶段独立 LLM call）| **CAN** | 纯 prompt + response，无需 logit 访问 |
| CORRECT/INCORRECT 结构化输出 | **CAN** | `result_text.startswith("CORRECT")` 是字符串解析，无需特殊能力 |
| Checker 独立重建 context（不复用 generator 中间产物）| **CAN** | 只需传不同的 input artifact |
| 有界 loop（max_attempts=3）+ feedback 携带 | **CAN** | 纯逻辑控制 + prompt 拼接 |
| 静默继续（注释掉的 hard gate）| **CAN** | 代码控制流 |
| Checker 与 Generator 使用同一模型 | **CAN**（但这是局限，见下）| 同质 critic 存在 Martingale Curse 风险 |
| 非对称 Checker（不同模型/不同 temperature）| **CAN** | 只需在初始化时传不同 model_name |
| Checker 判据可编程化（规则+LLM 混合）| **CAN** | 当前全部是 LLM 判断，可加确定性规则前置 |

**唯一的 CANNOT**：AdrCheckerAgent 的 verify 判据依赖 LLM 对"逻辑一致性"的判断——这无法完全形式化为黑盒可测试的规则（不是 LLM 本身的限制，而是 spec/design 质量度量的根本困难）。

---

## 7. 对 feat-397 直接可搬的设计

### 7.1 完全可搬：Checker 独立 context 构建范式

AgenticAKM 的 Checker 不是"把 generator 的 context 复制过来再加一层判断"，而是：
1. 只接收 **artifact 文本**（已完成的 spec.md / design.md）
2. 加载**独立的参考上下文**（SummaryChecker 用 tree_str，对应 spec-reviewer 应独立加载 constitution + 用户需求原文）
3. **不**接收 generator 的内部推理、中间步骤、思维链

这个模式可直接搬到 feat-397 的 spec-reviewer / design-reviewer：

```python
# spec-reviewer 的独立 context 构成：
# - spec.md 文件内容（artifact）
# - constitution（参考约束）
# - 用户 brief 原文（参考锚点）
# 不包含：spec-author 的澄清问答历史、内部草稿、中间推理
```

### 7.2 完全可搬：有界 loop + feedback 注入的终止语义

`max_attempts=3`（第二轮报告已推荐）+ feedback 作为下一轮 generator 的 prompt 前缀。注意 AgenticAKM 的实现选择了 **best-effort 语义**（loop 满不停机）；feat-397 应改为 **hard gate + escalation**（loop 满 + FAIL → 发 IM 给用户，等待裁决）。

```python
# feat-397 推荐的终止条件（改进版）：
for attempt in range(max_attempts):
    spec = spec_author.write(brief=brief, feedback=prev_feedback)
    is_pass, verdict = spec_reviewer.review(spec=spec, constitution=constitution, brief=brief)
    if is_pass:
        break
    prev_feedback = verdict.feedback
else:
    # 所有轮次均 FAIL：escalate 给用户
    await im.send(user_id, f"Spec 审核未通过（{max_attempts} 轮），需要您裁决：\n{verdict.feedback}")
    user_decision = await im.wait_reply(timeout=86400)
    # 根据 user_decision 继续或终止
```

### 7.3 完全可搬：Orchestrator 路由 PASS 直接进下一阶段，FAIL 携带 feedback 重试

AgenticAKM 证明了 Orchestrator 不需要理解 Checker 输出的语义——它只需要：
1. 解析 PASS/FAIL 布尔值（字符串前缀匹配）
2. PASS → 解锁下一阶段
3. FAIL → 提取 feedback 文本传给下一轮 generator

这个路由逻辑极简，可直接复用。feat-397 的 Orchestrator 增加 escalation 分支即可。

### 7.4 部分可搬：双层 generator-critic 拓扑

AgenticAKM 的双层结构（summary 层 + ADR 层，每层各有 generator-critic 对）对应 feat-397 的：
- 层 1：spec-author + spec-reviewer（对应 summary 层）
- 层 2：design-author + design-reviewer（对应 ADR 层）
- spec.md 是层 1 的 output artifact，也是层 2 的 immutable input（对应 AgenticAKM 中 `summary` 经 SummaryChecker 验证后传入 AdrWriter 的模式）

**关键差异需注意**：AgenticAKM 的 AdrWriter 只看 summary（不看原始代码），这导致丢失代码细节（见第 4 节分析）。feat-397 的 design-author 类似地如果只看 spec 而不看更丰富的背景，可能丢失架构上下文。建议 design-author 接收：`spec.md`（来自层 1）+ `architecture-context.md`（codebase 扫描摘要或人工提供）。

### 7.5 需要改进：Checker 判据的可编程化

AgenticAKM 的 Checker 判据完全是 LLM 主观判断（"is this logical/plausible?"），没有确定性规则。这在 spec/design 场景不够——feat-397 的 spec-reviewer 应叠加：
1. **确定性规则前置**（结构性 spec-smell 检查：缺少必填段落、缺少 GIVEN/WHEN/THEN、缺少 acceptance criteria）
2. **LLM 语义判断后置**（在结构完整的前提下，判断内容是否与 brief 一致、是否有遗漏的边界情况）

这与第二轮报告推荐的"门禁 1（确定性）+ reviewer（语义）"分层一致。

### 7.6 需要改进：同质 critic 的风险

AgenticAKM 的所有 agent 使用同一个 `model_name`（同质）。这意味着 Checker 和 Generator 在相同的训练分布上，可能共享相同的盲点。在论文实验规模下（29 仓库），这个风险被结构性优势（独立 context + 不同 objective）所盖过，但理论上存在"同质 Checker 无法发现 Generator 系统性盲点"的风险。

**feat-397 的改进选项**（黑盒下可行）：
- 不同 temperature（reviewer 用 temperature=0.0 更保守，author 用 0.3-0.7 更有创意）
- 不同 prompt objective（reviewer system prompt 明确指定"你的职责是找错，不是认可"）
- 未来：不同 model provider（一个 author 用 Kimi，一个 reviewer 用 Claude——跨模型多样性）

---

## 8. 总结

AgenticAKM 针对的失败模式是"单次 LLM 调用在高知识密度任务上的过度自信合成"，用双层 generator-critic 拓扑解决。其核心工程贡献是：证明了在纯黑盒 LLM 下，通过**严格 artifact 边界 + 独立 context 重建 + 有界反馈 loop + 最简 Orchestrator 路由**，可以在 29 仓库用户研究中实现 Overall 评分 +1.0 分（+29%-33%）的系统性质量增量。

对 feat-397 最有价值的具体设计是：**Checker 不应复用 Generator 的 context，而应独立加载参考锚点（brief 原文 + constitution），只接收 Generator 的最终 artifact**——这是"fresh eyes"独立视角的代码级落地方式，不依赖任何框架、不需要 session 隔离，只需要在 Orchestrator 层控制传什么参数给 Checker。

| 维度 | AgenticAKM 的做法 | feat-397 的采纳建议 |
|---|---|---|
| generator-critic 独立 context | Checker 自己重建 tree_str，不复用 generator 中间产物 | spec-reviewer 独立加载 brief + constitution，不接收 author 的推理历史 |
| 有界 loop 终止语义 | best-effort（loop 满不停机，静默继续）| hard gate + IM escalation（loop 满 FAIL → 发用户裁决） |
| Orchestrator 路由 | PASS→break，FAIL→feedback 传下一轮 | 同，增加 escalation 分支 |
| Checker 判据 | 纯 LLM 主观判断 | 确定性结构检查前置 + LLM 语义判断后置 |
| Critic 多样性 | 同质（同模型、同 temperature）| 不同 temperature + 不同 objective prompt；未来考虑跨 provider |
| 人介入点 | 无（研究原型）| loop 满 FAIL 时 escalate；门禁通过后 IM 通知用户确认才进下一层 |
