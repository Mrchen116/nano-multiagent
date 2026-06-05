# QUARE: Multi-Agent Negotiation for Balancing Quality Attributes in Requirements Engineering

> **来源**: arXiv:2603.11890 (2026-03-12)  
> **作者**: Haowei Cheng, Milhan Kim, Foutse Khomh, Teeradaj Racharak, Nobukazu Yoshioka, Naoyasu Ubayashi, Hironori Washizaki  
> **标注**: 🟡 RESEARCH（2026-03 发表，无公开代码仓库，CC BY 4.0）  
> **服务目标**: 深挖 QUARE 对 feat-397 spec-reviewer 多维检查单设计的直接启示

---

## 1. 单 Agent 的哪个 spec/design 失败模式

QUARE 直接命名的失败模式是 **"Monolithic Integration Gap"（单体集成缺口）**：

> 单 agent 从单一视角执行需求分析，把多方利益相关者的诉求折叠为一个统一叙事，而没有机制让不同质量目标（Safety vs. Efficiency vs. Green…）之间的冲突浮出水面。

具体展开：

| 失败表现 | 机制原因 |
|---|---|
| 质量属性覆盖不均衡 | 单 agent 倾向于沿"主线叙事"展开，ISO/IEC 25010 中的非主线质量维度（如 Green/Responsibility）被系统性欠生成 |
| 冲突隐藏而非暴露 | 单 agent 遇到矛盾时默认隐式融合（取权衡中间值），而非将冲突记录为设计信号留给人决策 |
| 无法区分冲突类型 | "Safety 冗余 vs. 功耗最小化"（资源型冲突）和"加密延迟 vs. 响应时限"（逻辑不相容）在单 agent 输出中无法区分，下游无法做出正确的解决路由 |
| 合规覆盖率极低 | 缺乏专职验证层，单 agent baseline 仅覆盖约 47.8% ISO 条款（QUARE 达 98.2%） |

这一失败与第一/二轮报告已识别的"单一 objective 满足即止"完全对应，QUARE 提供了更精确的机制性描述：**不是 agent 能力不足，而是缺乏让不同 objective 对抗的结构**。

---

## 2. 什么 Multi-Agent 结构去补：角色 / 拓扑 / 协议

### 2.1 五个质量专职 Agent（不同 objective）

| Agent | 质量维度 | 核心 objective |
|---|---|---|
| Safety | 安全可靠性 | 危害识别与缓解（对标 ISO 26262） |
| Efficiency | 性能 | 资源优化与延迟 |
| Green | 可持续性 | 能耗与碳足迹 |
| Trustworthiness | 安全/隐私 | 数据保护与访问控制（对标 ISO 27001） |
| Responsibility | 伦理/合规 | 监管与社会责任 |

全部对标 **ISO/IEC 25010 SQuaRE** 质量特征，角色划分有正式标准背书。

### 2.2 四阶段拓扑（Phase 1–4）

```
Phase 1: 专业生成
  每个质量 agent 独立产出候选需求集（CHV），不互相可见
  → 作用：保证初始多样性（消融实验：Phase 1 单独可使 CHV +53.6%）

Phase 2: 辩证协商（三段式，≤3轮）
  Thesis:    焦点 agent 提出候选需求集
  Antithesis: 其余 agent 根据自身 objective 提出具理由的批判
  Synthesis:  中立 moderator（Orchestrator）整合，冲突分类后路由
  → 作用：语义保留 100.0%（全程不重写文本，冲突以结构化 metadata 记录）

Phase 3: 模型整合与 KAOS 构建
  语义去重（BERTScore）+ 跨 agent 父子节点拼接
  → 输出：三层 KAOS 目标树（Strategic / Tactical / Operational）
  → 验证：DAG 拓扑检查（禁止环路）

Phase 4: RAG 合规验证
  嵌入相似度检索标准条款 → 独立 verifier LLM 做条款蕴含判断
  → 作用：合规覆盖率达 98.2%（+105%）
```

### 2.3 冲突检测与分类机制

- **第一阶段（余弦相似度）**：BERT 嵌入 + τ=0.85 阈值，快速标记候选冲突对
- **第二阶段（LLM 分类）**：将标记对送入 LLM，分类为三类：
  1. **冗余**（语义重复）→ 去重合并
  2. **资源型冲突**（共享有限资源）→ 优先权重整合
  3. **逻辑不相容**（互斥状态）→ 升级给人裁决（或 priority-weighted 兜底）

### 2.4 关键不对称设计

QUARE **不是**同质辩论（每个 agent 都可以评论一切），而是：
- 每个 agent **只有一个 objective**，批判必须从自己的质量维度出发，有理由支撑
- Moderator 是专职中立角色，不参与生成，只做冲突路由
- 这打破了 Martingale Curse 的对称性前提（第一轮报告识别的朴素 MAD 失败根因），因为各 agent 持有**真正不同的 objective**，而非同质 LLM 的随机采样变体

---

## 3. 有什么证据

### 3.1 定量结果（5 个案例，3 随机种子，180 次运行）

| 指标 | QUARE | MARE | iReDev | 单 agent |
|---|---|---|---|---|
| 合规覆盖率（ISO 条款） | **98.2%** | ~47.8% | ~47.8% | ~47.8% |
| 语义保留（BERTScore） | **94.9%** | 97.0% | 99.4% | — |
| Phase 2 语义保留 | **100.0%** | — | — | — |
| 冲突检出量 | 3.2× MARE | 基准 | — | — |
| 需求数量 | +25–43% | 基准 | — | — |
| 可验证性得分 | **4.96/5.0** | — | — | — |

**覆盖率 +105% 的来源**：Phase 4 的 RAG 合规验证层——MARE/iReDev 根本没有这一层，单 agent baseline 同样缺失。

**语义保留 +2.3pp 的来源**：Phase 2 的"冲突记录而非重写"原则——冲突以 metadata 形式记录，文本在 Phase 3 才经过语义去重，比 MARE 的即时文本改写保留了更多原始语义意图。

### 3.2 消融实验关键结论

- 移除 Phase 1（专业化）→ CHV -53.6%，质量维度覆盖坍塌
- 移除 Phase 2（协商）→ 冲突检出率大幅下降，冲突隐藏在输出中
- 移除 Phase 4（验证）→ 合规覆盖率回退至 baseline（~47.8%）

QUARE 的 **CRR（冲突解决率）仅 25.0%** vs. MARE 的 66.7%，乍看更低，实则是因为 QUARE **检出了 3.2 倍更多的冲突**，未解决冲突通过优先权重整合保留意图而非丢弃。

### 3.3 模型规模独立性

全部实验使用 **gpt-4o-mini**（轻量级），目的是"隔离架构与协商机制对模型规模的影响"。作者结论：

> "Effective RE automation depends...less on model scale than on principled architectural decomposition, explicit interaction protocols, and automated verification."

平均每案例运行时间 **55.4 秒**，具备迭代开发可行性。

---

## 4. 人留在哪（哪些决策升级给人）

QUARE 论文本身的人机边界设计（原文）：

1. **逻辑不相容冲突**：检测到互斥状态（如加密延迟 vs. 响应时限）后，优先升级给人裁决（priority-weighted 整合是兜底，非首选）
2. **iReDev 的 human-in-loop 操作化**：论文用 surrogate LLM 替代（实验场景），承认真实部署需要人介入知识注入
3. **KAOS 目标树中 Strategic 级目标**：最高层战略目标由框架生成后，需人确认是否与业务意图对齐（论文隐含）

本报告补充（基于前两轮结论的延伸）：
- **资源型冲突的优先权重设置**：谁的 objective 权重更高（Safety > Efficiency > Green？）本质是产品/业务决策，不应由 agent 自行设定——应作为 constitution 输入或显式升级
- **KAOS 树中的架构约束假设**：Phase 3 父子节点拼接隐含了架构结构假设，需人在门禁点确认

---

## 5. 黑盒 CAN / CANNOT

| 机制 | 黑盒 CAN/CANNOT | 说明 |
|---|---|---|
| 五个专职 agent，不同 system prompt（不同 objective） | **CAN** | 纯 prompt 工程，零基础设施变化 |
| 辩证三段式（Thesis→Antithesis→Synthesis） | **CAN** | 文本进文本出，prompt 编排 |
| 冲突两阶段检测（余弦相似度 + LLM 分类） | **CAN** | 余弦相似度用嵌入 API（或本地），LLM 分类纯推理 |
| 冲突类型三分类（冗余/资源型/逻辑不相容） | **CAN** | LLM 零样本分类，有 JSON schema 约束 |
| 冲突以 metadata 记录（不改写文本） | **CAN** | 输出结构约束，prompt 层可实现 |
| KAOS 三层目标模型 | **CAN** | 输出格式约束（JSON/XML schema） |
| DAG 环路检测 | **CAN** | 确定性图算法，纯代码层 |
| RAG 合规条款验证（Phase 4） | **CAN** | 嵌入检索 + LLM 条款蕴含，黑盒全程 |
| BERTScore 收敛检测 | **CAN** | 嵌入 API 即可，无需 logit |
| 需要 logit/fine-tune/RLHF | **CANNOT** | 论文不使用，全程黑盒友好 |

**结论**：QUARE 整体架构**完全黑盒可行**。论文刻意使用 gpt-4o-mini + zero-shot + JSON schema 的最简配置来验证架构本身的有效性，与 feat-397 场景的技术约束高度匹配。

---

## 6. 对 feat-397 直接可搬的内容

### 6.1 核心可搬模式：「不同 objective Agent 的对抗式 surface 假设」

**什么可搬**：spec-reviewer 不应是单一角色拿着一份通用检查单检查，而应分解为**持不同 objective 的专职子 reviewer**，每个子 reviewer 只从自己的维度批判，批判必须给出理由。

**feat-397 的对应映射**：

| QUARE 质量 Agent | feat-397 spec-reviewer 子维度 |
|---|---|
| Safety | 边界条件 / 错误路径 / 安全性假设 |
| Efficiency | 性能约束 / 数据规模假设 |
| Trustworthiness | 数据隐私 / 权限模型完整性 |
| Responsibility | 合规/法规约束是否显式声明 |
| （新增）Consistency | spec 内部逻辑自洽 / 与 constitution 对齐 |
| （新增）Feasibility | 技术可行性 / 下游实现可达性 |

每个子维度用独立 system prompt 注入 objective，输出结构化 `{dimension, finding, severity, rationale}`。Orchestrator 聚合，按 severity 路由：CRITICAL（逻辑不相容）→ 升级给人，WARNING（资源型冲突）→ 记录入 spec 冲突段，INFO（冗余）→ 自动去重。

### 6.2 冲突三分类可直接搬入 spec-reviewer 输出 schema

```json
{
  "conflict_type": "logical_incompatibility | resource_bound | redundancy",
  "dimensions_involved": ["safety", "efficiency"],
  "description": "...",
  "severity": "CRITICAL | WARNING | INFO",
  "recommended_action": "escalate_human | priority_weight | deduplicate"
}
```

`logical_incompatibility` → 门禁强制升级人裁决（不允许 agent 自行解决）。

### 6.3 "冲突记录而非重写"原则 → spec 语义保留

QUARE Phase 2 的核心设计决策：**协商阶段不修改文本，只记录冲突 metadata**。对应 feat-397：

- spec-reviewer 的 critique 不应直接改写 spec，应输出问题清单（spec-verdict.md）
- spec-author 在下一轮修改时持有完整的冲突上下文，决定如何处理
- 这与第二轮报告推荐的 `spec-verdict.md（PASS/FAIL + CRITICAL/WARNING 清单）` 完全一致，QUARE 提供了这一设计决策的机制性理由：保留语义意图，让文本修改在信息最完整的时机发生

### 6.4 KAOS 输出目标层级 → spec 结构化层级

QUARE 的 Strategic / Tactical / Operational 三层对应 feat-397 spec 的：
- **Strategic**：用户目标（User Story / Job-to-be-done）
- **Tactical**：功能需求（Feature / Behavior 级别）
- **Operational**：验收条件（GIVEN/WHEN/THEN）

若 spec 缺少某层（如直接从 Strategic 跳到 Operational，无 Tactical 过渡），spec-reviewer 的 Consistency 子 agent 应检测并标记为 WARNING。

### 6.5 Phase 4 RAG 合规验证 → constitution 自动对标

QUARE Phase 4 的"条款蕴含"逻辑可迁移为：spec 产出后，自动检查每条需求是否有 constitution 中的原则蕴含支撑（"哪条 constitution 原则覆盖了这条需求？"），无覆盖的需求段应标记为可能越界或遗漏。

### 6.6 运行时效率验证

QUARE 用 gpt-4o-mini 跑 5 agent × 3 轮协商，平均 55.4 秒。对应 feat-397 场景（spec-reviewer 分解为 4–6 个子维度 reviewer，单次 spec 评审），用 Sonnet 级模型估算约 **60–120 秒**，属于可接受的交互等待范围（用户提交 spec 后异步通知）。

---

## 7. 需要注意的局限与张力

1. **CRR 25.0% 看起来低**：QUARE 实际解决的冲突只有 1/4，其余靠优先权重整合或升级。在 feat-397 场景中，这意味着 spec-reviewer 发现大量冲突后，大多数冲突**不会被自动解决**，而是进入问题清单等待人裁决——这实际上是正确设计（人在冲突解决处），而非失败。

2. **Green / Responsibility agent 在纯软件 spec 中的等价物不明显**：QUARE 面向 SE 质量属性，而 feat-397 面向功能 spec 的正确性/完整性。映射时需重新定义每个子 reviewer 的 objective，不能直接照抄 ISO 25010 维度。

3. **论文不含 human-in-loop 的生产级实现**：iReDev 的"human-in-loop"用 surrogate LLM 替代。真实部署（如 feat-397 的 IM 通知等待）需自行设计异步 escalation 链路——这在第二轮报告的推荐架构中已有，QUARE 不提供该部分的参考实现。

4. **KAOS 输出格式**：JSON/GSN XML 的下游解析开销在 feat-397 中是否必要，取决于是否需要机器可读的目标追踪。若只需人可读的 spec.md，可退化为 Markdown 层级结构，不必实现完整 KAOS。

---

## 小结

QUARE 的核心贡献对 feat-397 的直接价值集中在两点：

**①"不同 objective 专职 agent"是 surface 假设的正确结构**——不是同质辩论，而是每个角色持有真正不同的质量标准，批判有义务给出来自自己 objective 的理由。这为 spec-reviewer 的多维检查单提供了机制性设计依据，而非只是"列更多检查项"。

**②"冲突三分类 + 类型路由"是人机边界的关键操作化**——逻辑不相容强制升级人，资源型冲突优先权重整合，冗余自动去重。这让"哪些决策升级给人"有了可实现的、非主观的判断标准，直接可以转化为 spec-verdict.md 的 schema 设计和 Orchestrator 的门禁逻辑。
