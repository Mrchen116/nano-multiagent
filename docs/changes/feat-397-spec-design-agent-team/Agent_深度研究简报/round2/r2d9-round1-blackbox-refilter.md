# r2d9：第一轮推荐方法的黑盒再过滤

> **维度定位**：针对第一轮报告 sec07（推荐）、dim01（品味编译）、dim02（escalation）、dim12（个性化）
> 中的每个核心推荐方法，产出 CAN / CANNOT（黑盒下）过滤表，纠正对 Drift / AMULET / T-POP
> 的分类错误，并给出黑盒可落地的替代或等效做法。
>
> **黑盒定义**：通过 provider 代理调用，文本进文本出，**无法访问 logprob / logit / token
> probability / entropy / 解码层**。排除一切需要 fine-tune / RLHF / DPO / RL / LoRA
> / 奖励模型训练的方法。

---

## 1. 关键发现

### 1.1 第一轮最大分类错误：Drift / AMULET / T-POP 被错误标为"黑盒可行"

第一轮 sec07（7.2.2）写道：

> "测试时方法（Drift、AMULET、T-POP）适合个人开发者快速启动——无需训练、计算高效。"

这是**严重错误**。三个方法的工作机制均依赖解码层介入，黑盒下完全无法运行：

| 方法 | 论文关键机制 | 黑盒障碍 |
|------|-------------|---------|
| **Drift** | "(3) Drift Decoding 将加权属性奖励**整合到 logit 空间**实现个性化生成"（arXiv 2502.14289v3）| 需要写入 logit 空间，黑盒 API 不暴露 |
| **AMULET** | "formulating the decoding process of **every token** as a separate online learning problem"，"provides a **closed-form solution for each iteration step**"（arXiv 2502.19148）| 每 token 解码干预，需 token-level 访问权 |
| **T-POP** | "steers the **decoding process** of a frozen LLM by learning a reward function online… applying dueling bandit strategy at each token generation step"（arXiv 2509.24696）| token-level dueling bandit，需解码层控制 |

🟡RESEARCH — 三者均只在受控实验环境（本地跑模型权重）中验证，未见任何生产 provider API 上的采用记录。

**第一轮把"无需重训练"误判为"黑盒可行"**。这是两个不同约束：
- "无需重训练" = 不改模型权重
- "黑盒可行" = 只用文本输入/输出 API

Drift / AMULET / T-POP 满足前者，但**不满足后者**。个人开发者通过 provider 代理调用，拿不到 logits，这三个方法全部出局。

### 1.2 KnowNo 原版同样需要 logits，但 LofreeCP / ConU 是真正的黑盒变体

第一轮 sec07（7.2.1）用 KnowNo 作为 escalation 的主要推荐框架。原版 KnowNo 的局限已在 dim02 证据2.2 中记录：

> "KnowNo 的局限性包括需要 **next-token probability 访问**"（arXiv 2506.04089v1）

原版 KnowNo = 🟡RESEARCH + gray-box（需要 logit 访问），个人开发者用不了。

但 dim02 同一节已经指出黑盒替代：**LofreeCP**（"a CP-based approach that is compatible with logit-free models"）和 **ConU**（"ConU 在 7 个 LLM 上实现严格的 correctness coverage rate 控制"，纯黑盒）。这两个是真正可落地的。🟢SHIPPED 状态待确认，但机制上黑盒可行。

### 1.3 PReF 需要训练奖励模型，不是纯黑盒

第一轮 sec07（7.2.3）推荐"当偏好数据积累至足够规模（20+ 对），启用 PReF 进行矩阵分解个性化"。

PReF（arXiv 2503.06358v1）的机制：先训练共享基础奖励函数（矩阵分解 + 训练），再通过主动学习确定用户系数。训练步骤需要 RL/DPO 基础设施。个人开发者不能自己跑训练，**出局**。

🟡RESEARCH — 只在 Qwen 2.5 模型家族受控实验中验证。黑盒替代见 §2 表格。

### 1.4 Verbalized Confidence 可用但必须知道其上限

Verbalized confidence（直接问模型"你有多确定"）是黑盒可行的，但第一轮报告已引用了其可靠性数据：ECE 在 RLHF 训练模型上可达 0.377+，是 SFT 模型的 4 倍。

**可用，但只能作为多信号之一，不能单独作为 gate 依据**。

### 1.5 Constitution + Critic Agent + Few-shot 三件套黑盒完全可行，是最强基线

这三个方法不依赖任何训练或解码层访问，全程文本输入输出。有最扎实的工程采用证据：

- Constitution：🟢SHIPPED — GitHub Spec-Kit（MIT 开源，GitHub 官方），AWS Kiro（Steering Files），BMAD
- Critic Agent：🟢SHIPPED — MetaGPT（生产使用），CVE-Genie，INDICT（代码生成场景）
- Few-shot 案例库：🟢SHIPPED — 所有主流 in-context learning 实践

---

## 2. CAN / CANNOT 过滤主表

下表覆盖第一轮 sec07、dim01、dim02、dim12 中出现的全部核心推荐方法。

| 方法 | 第一轮推荐位置 | 黑盒状态 | 根本原因 | 最佳黑盒替代 |
|------|--------------|---------|---------|------------|
| **Constitution 文件** | sec07-7.1.2、dim01 §1 | ✅ CAN | 纯 prompt 注入，文件→context | —（直接用） |
| **Critic Agent（Generator-Critic）** | sec07-7.1.1、dim01 §3 | ✅ CAN | 独立 agent prompt，文本审查 | — （直接用）|
| **Few-shot 案例库（静态/检索）** | sec07-7.1.2、dim01 §2 | ✅ CAN | In-context learning，纯文本 | — （直接用）|
| **Procedural Memory / LangMem** | sec07-7.2.2、dim01 §5 | ✅ CAN（含条件） | system prompt rewrite 仍是文本操作；需在自有基础设施上运行 LangMem/Letta | 若无基础设施：用结构化 JSON memory 文件 + agent 读写 |
| **Sample Consistency（SC）** | dim02 §2.1 | ✅ CAN | 多次调用 API 取输出，无需 logits | — （直接用，成本高于 verbalized）|
| **Verbalized Confidence** | dim02 §2.1 | ✅ CAN（低可靠性） | 纯文本输出；但 ECE 可达 0.377+，系统性 overconfident | 与 SC 叠加使用，不单独作 gate |
| **ConU（黑盒 Conformal）** | dim02 §3.4 | ✅ CAN | 纯文本输出 + calibration set，无需 logits | — （直接用）|
| **LofreeCP** | dim02 §3.1 | ✅ CAN | 显式设计为 logit-free，纯文本 | — （直接用）|
| **Conformal Social Choice** | dim02 §3.3 | ✅ CAN（含条件） | 依赖多 agent 输出的 non-conformity 分数，可从文本计算 | 需有 multi-agent debate 结构 |
| **LLM-as-Judge** | sec07-7.2.3、dim08 | ✅ CAN | 纯文本打分；κ=0.77-0.87 | — （直接用）|
| **EARS DSL + MBSE 结构化需求** | sec07-7.1.3 | ✅ CAN | 需求格式约束，文本模板 | — （直接用）|
| **Value Fork 检测（关键词/模式）** | dim02 §2.3 | ✅ CAN | 规则匹配 + prompted 分类 | — （直接用）|
| **FSPO（Few-Shot Preference Optimization）** | dim01 §2、dim12 §1.2 | ❌ CANNOT | 框架名称含"Optimization"——需在模型上做 meta-learning 训练步 | **黑盒替代**：CIPHER / PROSE 风格的偏好推断：从历史编辑/审查记录中用 LLM 推断偏好，检索相似案例注入 |
| **PReF（Preference Reward Factorization）** | sec07-7.2.3、dim12 §1.2 | ❌ CANNOT | 训练共享基础奖励函数（矩阵分解 + DPO/RL 步）| **黑盒替代**：用 LLM 提取偏好维度标签（"简洁 vs 完整"等），手工标注或 prompted 分类后存为结构化 preference profile，检索时加权注入 |
| **VPL（Variational Preference Learning）** | dim12 §1.2 | ❌ CANNOT | 变分编码器训练，奖励模型条件化 | 同上 PReF 替代 |
| **PPT（Preference Pretrained Transformer）** | dim12 §1.2 | ❌ CANNOT | 离线阶段需训练策略模型（DPO） | **黑盒替代**：PPT 的在线阶段（生成两候选 → 用户排序 → 追加 context）可纯文本实现；去掉离线训练步，仅保留在线收集偏好对 |
| **RLPA（Reinforcement Learning Personalized Alignment）** | dim12 §1.2 | ❌ CANNOT | RL 训练，fine-tune Qwen-2.5 | 同 PReF 替代 |
| **Drift（Decoding-time Alignment）** | sec07-7.2.2、dim12 §1.2 | ❌ CANNOT | Drift Decoding 写入 logit 空间 | **黑盒替代**：Drift 的*属性分解*思路（把偏好分解为"简洁/类型安全/..."维度）可黑盒实现：prompted 属性打分 → 加权 few-shot 检索；放弃解码层干预部分 |
| **AMULET（Test-Time Online Learning）** | sec07-7.2.2、dim12 §1.2 | ❌ CANNOT | 每 token 解码层在线学习 | **黑盒替代**：AMULET 的*动机*（实时偏好适应）可黑盒实现：session 内维护偏好 delta 文件，每轮结束 prompted agent 更新，下轮注入 |
| **T-POP（Test-Time Online Preference Feedback）** | sec07-7.2.2、dim12 §1.2 | ❌ CANNOT | token-level dueling bandit，解码层介入 | 同 AMULET 黑盒替代 |
| **KnowNo（原版）** | sec07-7.2.1、dim02 §3.1 | ❌ CANNOT（原版） | 需要 next-token probability | **黑盒替代**：ConU + LofreeCP；或纯 SC + verbalized confidence 融合 gate |
| **LPP（LLM Performance Predictors）** | dim02 §2.2 | ⚠️ 部分可用 | gray-box 特征（logit）不可用；black-box 特征（verbalized confidence、uncertainty attribution）可用 | 仅使用 black-box 特征子集训练 meta-model；gray-box 部分用 SC 替代 |
| **DPO-f+** | dim01 §4.2 | ❌ CANNOT | DPO 训练步 | **黑盒替代**：收集 approve/reject 对，作为 few-shot 案例注入，无需训练 |
| **CIPHER / PROSE** | dim12 §1.2 | ✅ CAN | LLM 从历史编辑/样本中推断偏好，检索注入；无训练步 | — （直接用，是 PReF/FSPO 的黑盒替代）|
| **Mem0 / Zep（semantic + episodic）** | sec07-7.2.2、dim01 §5 | ✅ CAN（需基础设施）| 事实检索，向量存储，无模型训练 | 若无基础设施：结构化 JSON 文件 + 文件系统 memory |

---

## 3. 黑盒替代方案详解

### 3.1 Drift / AMULET / T-POP → "属性分解 + prompted 偏好检索"（黑盒等效）

这三个方法的*工程动机*是合理的：把隐性偏好分解成可解释维度，轻量级、无需训练地个性化输出。这个动机可以用纯黑盒方式实现，只是放弃解码层干预，改用 context 注入：

**黑盒等效做法（可落地）**：

```
1. 预定义偏好维度清单（本项目示例）：
   - 简洁 vs 完整（spec 粒度）
   - 类型安全 vs 灵活（API 设计）
   - 快速交付 vs 长期可维护（scope 判断）
   - 模块边界严格 vs 实用主义

2. 从历史 unit spec.md 中 prompted 提取用户在每个维度的倾向：
   [System] 读以下用户在历史设计决策中的原话，
   判断他在"简洁 vs 完整"维度上更偏哪端，
   给出 -2 到 +2 的打分和支撑引用。

3. 把分数和引用存入 preference_profile.json。

4. 生成 spec/design 时，把相关维度的分数 + 代表性原话作为 few-shot context 注入。
```

🟢SHIPPED 等效基础：CIPHER（NeurIPS 2024，Microsoft/DeepMind）的"从历史中检索推断偏好"机制、PROSE（Apple Research 2025）的"迭代偏好推断"机制——两者均纯文本，已发表。

### 3.2 KnowNo 原版 → ConU + SC 融合 gate（黑盒等效）

**黑盒等效做法**：

```
1. 对同一个 spec/design 决策点，用不同 prompt 变体调用 3-5 次（SC 采样）。
2. 计算输出一致性：embedding 相似度 > 0.85 → high confidence；否则 uncertain。
3. 同时让 agent verbalize：[0-1] 你对这个决策的置信度，
   并说明不确定的具体来源。
4. 两个信号均 high → 自主执行；任一 low → escalate 队列。
5. 用历史 human approve/reject 数据校准两个阈值（calibration set）。
```

ConU 的 correctness coverage guarantee（≥1-α）理论上可通过 black-box 非符合分数实现，不需要 logits——但需要校准集。🟡RESEARCH（ConU 论文实验使用 API 调用，技术上黑盒，但尚未见生产 agent harness 中的 SHIPPED 证据）。

### 3.3 PReF / FSPO → CIPHER 风格的"偏好案例库 + prompted 推断"（黑盒等效）

PReF 的*工程价值*（少量数据个性化）可以用以下纯文本方式获得：

```
1. 每次 human review 后，记录：
   {
     "decision_context": "...",
     "user_choice": "A",
     "user_reasoning_verbatim": "用户原话",
     "preference_tags": ["简洁优先", "不引入新依赖"]
   }

2. 新决策时，用 TF-IDF / embedding 检索最相关的 3-5 条历史记录。

3. 注入 system prompt：
   "以下是该用户在类似场景的历史决策，请参考其判断风格：..."

4. 可选：用 CIPHER 的方式，让 agent 先推断"在这种约束下用户会倾向什么"，
   再生成答案。
```

🟢SHIPPED（in-context learning + RAG 检索方式）：Claude Code AGENTS.md 机制、GitHub Spec-Kit few-shot 加载，均是此类做法的工程实现。

---

## 4. 第一轮推荐的黑盒状态汇总（修正版）

下表是对 sec07 三阶段推荐路线图的逐条修正：

### 阶段 1（第一轮推荐：立即实施）

| 推荐项 | 黑盒状态 | 修正意见 |
|--------|---------|---------|
| Constitution 文件（20条以内）| ✅ CAN | 保留，无需修正 |
| 3-4 角色顺序流水线 | ✅ CAN | 保留，无需修正 |
| Escalation 机制（KnowNo + CP） | ⚠️ 原版 CANNOT | **修正**：用 ConU / LofreeCP + SC 替代原版 KnowNo；或纯 SC + verbalized 融合 gate |
| Few-shot 案例库（TF-IDF 检索）| ✅ CAN | 保留，无需修正 |

### 阶段 2（第一轮推荐：1-3 个月）

| 推荐项 | 黑盒状态 | 修正意见 |
|--------|---------|---------|
| Core Memory（Letta/LangMem procedural）| ✅ CAN（含条件）| 需自托管基础设施；退化方案：结构化 JSON 文件 + agent 读写工具 |
| 偏好信号收集（approve/reject + 原话）| ✅ CAN | 保留，无需修正 |
| 测试时方法（Drift、AMULET、T-POP）| ❌ CANNOT（全部） | **删除**。替换为：§3.1 的属性分解 + prompted 偏好检索（CIPHER / PROSE 风格） |

### 阶段 3（第一轮推荐：3-6 个月）

| 推荐项 | 黑盒状态 | 修正意见 |
|--------|---------|---------|
| LLM-as-Judge 评测（ISO 29148 rubric）| ✅ CAN | 保留，无需修正 |
| PReF 矩阵分解个性化 | ❌ CANNOT | **删除**。替换为：§3.3 的偏好案例库 + prompted 推断（CIPHER 风格） |
| Continuous Evaluation（Golden Dataset）| ✅ CAN | 保留，无需修正 |
| Procedural memory governance | ✅ CAN | 保留，无需修正 |

---

## 5. 修正后的品味编译黑盒方案（三层，全部可落地）

替代第一轮 sec07-7.1.2 的三层结构，修正后版本全部黑盒可行：

**第一层：Constitution（静态约束）** 🟢SHIPPED

- 15-20 条原则文件，按需加载（不随每个请求发送）
- 覆盖"不可违反的硬约束"
- 工程参考：GitHub Spec-Kit `.specify/memory/constitution.md`

**第二层：Critic Agent（主动审查）** 🟢SHIPPED

- 独立 critic prompt，与 producer 隔离
- prompt 中固化评价维度（ISO 29148 + 自定义品味维度）
- 工程参考：MetaGPT QA role，CVE-Genie critic agent

**第三层：偏好案例库 + CIPHER 风格推断（动态学习）** 🟢SHIPPED（CIPHER / PROSE 已发表可复现）

- 从历史 spec.md 原话中 prompted 提取偏好标签和决策依据
- 新决策时检索相关历史案例注入
- 周期性 prompted 总结成 preference_profile.json
- **完全替代** Drift / AMULET / T-POP / PReF 的个性化动机，且黑盒可行

---

## 6. Escalation 修正后的黑盒方案

替代第一轮 sec07-7.2.1 的 KnowNo 为主推荐，修正后全部黑盒：

**信号 1：Sample Consistency（SC）** 🟢SHIPPED（Claude Code 多次采样机制、Self-Consistency 论文）

- 3-5 次 API 调用，embedding 计算一致性
- 成本：每次 escalation 判断多 3-5 次 LLM 调用
- ROC AUC 0.68-0.79（Stanford 医学研究）

**信号 2：Verbalized Confidence** 🟢SHIPPED（所有主流 agent 均使用）

- 作为辅助信号，不单独作 gate
- 注意 ECE 可达 0.377+，RLHF 模型更差

**Gate 逻辑（黑盒版 Conformal）**

- 用历史 human review 数据校准 SC 一致性阈值
- ConU 机制（黑盒非符合分数）可作为统计保证框架，但需 calibration set
- 价值判断类决策：规则匹配"此处涉及权衡/取舍"→ 无条件 escalate，不依赖置信度

**异步 escalation ticket 格式**（黑盒可实现）：

```
{
  "context": "当前 spec/design 片段",
  "proposed_decision": "agent 倾向方案",
  "sc_score": 0.62,
  "verbalized_confidence": 0.7,
  "uncertainty_source": "agent 自述不确定原因",
  "alternatives": ["方案A", "方案B"],
  "value_fork_detected": true/false
}
```

---

## 7. 对本 unit 实现的可操作建议

### 7.1 立即可做（不依赖任何新基础设施）

1. **删除 Drift / AMULET / T-POP 所有引用**，从实施计划中移除。这三个方法在本项目 provider 代理调用环境下无法运行，不存在"后期引入"的可能性。

2. **保留 PReF 的工程动机，换掉实现**：不要收集 pairwise preference 对去"训练"任何东西。改为：每次 human review 记录原话 + 决策依据 + preference_tags，存 JSON，用 CIPHER 风格的 prompted 推断 + 检索实现个性化。

3. **KnowNo 只引用 ConU / LofreeCP 变体**，或改为 SC + verbalized 融合 gate，不要引用原版 KnowNo（需要 logit）。

4. **阶段 3 删除 PReF 个性化**，替换为：偏好案例库达到 20+ 条后，用 CIPHER / PROSE 风格的 LLM 推断总结成 preference_profile，注入 critic agent 的评价 prompt。

### 7.2 本项目独有的资产可直接利用

本项目 `docs/changes/*/spec.md` 已积累跨历史 unit 的"用户原话 + 设计取舍"语料。这正是 CIPHER / PROSE 方案的输入材料：

```bash
# 可直接用以下 prompted 流程启动偏好档案
find docs/changes -name "spec.md" -exec grep -l "用户.*说\|原话\|取舍\|不要\|优先" {} \;
# → 提取偏好原话
# → prompted 分类到预定义维度
# → 存入 preference_profile.json
# → 每次 spec-author / design-author agent 启动时注入
```

这是黑盒下最快启动个性化的路径，且数据已在手。

### 7.3 不要做的事（黑盒下永远不可行）

- 不要引入任何需要本地跑模型权重的测试时方法
- 不要设计"收集 pairwise preference 对去训练奖励模型"的 pipeline
- 不要以"无需重训练"为由把 Drift / AMULET / T-POP 加回来
- 不要依赖 verbalized confidence 作为 escalation 的唯一信号

---

## 8. Shipped vs Research 状态汇总

| 方法 | 状态 | 谁在用 / 来源 |
|------|-----|-------------|
| Constitution 文件 | 🟢SHIPPED | GitHub Spec-Kit（MIT 开源），AWS Kiro（Steering Files），BMAD，Claude Code AGENTS.md |
| Critic Agent（Generator-Critic）| 🟢SHIPPED | MetaGPT QA role，CVE-Genie，INDICT，LiveClin；LangGraph / CrewAI 原生支持 |
| Few-shot 案例库（ICL）| 🟢SHIPPED | 所有主流 LLM agent；Claude Code tools/prompts |
| Sample Consistency（SC）| 🟢SHIPPED | Claude Code（多次采样），Self-Consistency 论文已被广泛工程化 |
| LLM-as-Judge | 🟢SHIPPED | MT-Bench，Chatbot Arena，SWE-Judge，GitHub Spec-Kit 质量评测 |
| CIPHER 偏好推断 | 🟢SHIPPED（已发表可复现）| NeurIPS 2024，Microsoft/DeepMind，无训练步，LLM API 调用 |
| PROSE 偏好推断 | 🟢SHIPPED（已发表可复现）| Apple Research 2025，纯文本，无训练步 |
| ConU（黑盒 Conformal）| 🟡RESEARCH（机制黑盒）| arXiv 2024，7 个 LLM 实验，未见生产 harness 集成 |
| LofreeCP | 🟡RESEARCH（机制黑盒）| arXiv 2025，AmbiK 数据集，未见生产采用 |
| Conformal Social Choice | 🟡RESEARCH | arXiv 2026，MMLU-Pro 实验，未见生产采用 |
| Mem0 / LangMem（事实记忆）| 🟢SHIPPED | Mem0（50K+ GitHub stars，AWS Agent SDK exclusive memory provider），LangMem（LangChain 官方）|
| Letta Core Memory | 🟢SHIPPED | Letta（原 MemGPT）生产版本，Letta Code |
| Drift | 🟡RESEARCH + ❌黑盒不可 | arXiv 2502.14289，学术实验，需 logit 访问 |
| AMULET | 🟡RESEARCH + ❌黑盒不可 | ICLR 2025，需 token-level 解码干预 |
| T-POP | 🟡RESEARCH + ❌黑盒不可 | ICML 2026，token-level dueling bandit |
| KnowNo（原版）| 🟡RESEARCH + ❌黑盒不可（原版）| ICRA 2023，需 next-token probability |
| PReF | 🟡RESEARCH + ❌黑盒不可 | arXiv 2503.06358，需训练奖励函数 |
| VPL | 🟡RESEARCH + ❌黑盒不可 | arXiv 2408.10075，需变分编码器训练 |
| RLPA | 🟡RESEARCH + ❌黑盒不可 | NeurIPS 2025，fine-tune Qwen-2.5 |
| DPO-f+ | 🟡RESEARCH + ❌黑盒不可 | arXiv 2511.01043，DPO 训练步 |

---

## 9. 一句话 reality check

**第一轮报告中，品味编译三层路径的阶段1和阶段2部分方法、escalation 的 KnowNo 主推荐、个性化的全部测试时方法（Drift / AMULET / T-POP）和训练时方法（PReF / VPL / RLPA），在黑盒 provider 代理调用环境下均无法运行，需全部替换。**

替换后的黑盒可行组合（全部 SHIPPED 或已发表可复现）：

1. Constitution + Critic Agent + 偏好案例库（CIPHER 风格）——品味编译
2. SC + Verbalized Confidence 融合 gate（阈值用历史 review 数据校准）——escalation
3. LLM-as-Judge（ISO 29148 rubric）——spec/design 质量评测
4. Mem0 / LangMem（事实记忆）+ 结构化 preference_profile.json——长期个性化

这四件套全部黑盒可行，且有生产级工程采用证据，是本 unit 实现的核心基础设施。
