# Agent Team 自动化软件需求 Spec & Design 深度研究报告

## 执行摘要
### 核心发现
#### 核心问题回答：如何设计一个multi-agent系统自动完成spec对齐与design对齐
#### 关键结论："编译品味+顺序流水线+Human-on-the-loop"是证据最充分的组合
#### 最大未解风险：评测系统的缺失和长期intent drift的累积

## 1. P0核心问题深度综述（一）：编译人类品味/判断的最佳实践（~5000字，2表，1图）
### 1.1 问题本质：为什么Agent需要"品味"
#### 1.1.1 "张小龙"类比——内化的品味是接住轻brief的前提
#### 1.1.2 现有方案的结构性缺陷：可形式化的偏好不是真正的品味
### 1.2 五大候选方案对比
#### 1.2.1 Constitution/原则文件：广泛采用但面临Curse of Instructions
#### 1.2.2 Few-shot案例库：FSPO证明87%/72%胜率，5-7个示例后收益递减
#### 1.2.3 角色化Critic Agent：ROI最高，消融实验一致证明+5-15%质量提升
#### 1.2.4 偏好学习/RLHF-style：T-POP>AMULET 14.7%，个人开发者难以运行
#### 1.2.5 Memory系统：LangMem的procedural memory是唯一"习得"品味的方案
### 1.3 横向对比与推荐
#### 1.3.1 对比表：有效性证据/维护成本/实现复杂度/抗drift/个人开发者可行性
#### 1.3.2 推荐策略：阶段1 Constitution+Critic+案例库 → 阶段2 Core Memory → 阶段3 T-POP/AMULET

## 2. P0核心问题深度综述（二）：Escalation——何时该问人（~4000字，1表，1图）
### 2.1 技术路线谱系
#### 2.1.1 Logit-based/Verbalized/Sampling-based/Conformal Prediction/Meta-model五条路线
#### 2.1.2 Verbalized confidence的系统性overconfidence问题（ECE可达0.377+）
### 2.2 最佳实践：Confidence-Gated Escalation
#### 2.2.1 KnowNo+Conformal Prediction：统计保证的escalation框架
#### 2.2.2 LLM Performance Predictors：gray-box+black-box特征融合
#### 2.2.3 Conformal Social Choice：multi-agent场景中拦截81.9%的wrong-consensus
### 2.3 价值岔路识别与Ask-vs-Act
#### 2.3.1 Value Forks——AI与人类在价值判断上的系统性分歧
#### 2.3.2 Learning-to-defer的Bayes-optimal规则
### 2.4 生产级Handoff设计
#### 2.4.1 Inline/Async/Blended三种模式
#### 2.4.2 Escalation rate作为product health metric（目标<20%）

## 3. P0核心问题深度综述（三）：防Intent Drift（~4500字，1表，1图）
### 3.1 Drift的本质与度量
#### 3.1.1 LLM-generated code "plausible but not correct by construction"
#### 3.1.2 2%早期错位→40%末端失败的级联效应
### 3.2 多层防护体系
#### 3.2.1 Traceability自动化：BERT/SimCSE-based TLR可达85%+ accuracy
#### 3.2.2 Spec-as-Contract：immutable spec + human-approved变更
#### 3.2.3 Requirement DSL：EARS语法（Airbus/Bosch/NASA采用）+ Gherkin
### 3.3 Bidirectional Sync前沿
#### 3.3.1 Specine：Pass@1提升29.60%~93.55%
#### 3.3.2 Tessl实践：spec-as-source的局限（非确定性问题）
### 3.4 推荐策略
#### 3.4.1 渐进路径：Spec-first→EARS DSL+Traceability→3-Checkpoint Gates→Spec-anchored

## 4. 协作机制：拓扑、角色与澄清（~4500字，2表）
### 4.1 协作拓扑对比
#### 4.1.1 Multi-Agent Debate的Martingale Curse——数学证明收敛到平庸
#### 4.1.2 顺序流水线的优势（MetaGPT SOP: 85.9% HumanEval）与缺陷（错误级联）
#### 4.1.3 Generator-Critic对抗：最可靠的quality-improvement模式
#### 4.1.4 推荐：顺序Pipeline + 形式化质量门控
### 4.2 角色分解的真实价值
#### 4.2.1 消融实验证据：MetaGPT可执行性1.0→4.0，ChatDev Quality 0.22→0.40
#### 4.2.2 认知多样性 > 同质数量：2认知多样agent > 16同质agent
#### 4.2.3 最优角色集：PM+Architect+Engineer+QA（3-4个角色的有效下限）
### 4.3 澄清策略
#### 4.3.1 ClarifyGPT：Pass@1 +13.87%~16.83%，平均仅需2.85个问题
#### 4.3.2 3轮澄清上限的业界共识
#### 4.3.3 有条件澄清 > 无条件澄清；澄清作为"品味学习"机会

## 5. 反面证据与陷阱（~3500字，1表）
### 5.1 全自动角色的失败
#### 5.1.1 ChatDev 33%成功率与MetaGPT项目级通信崩溃
#### 5.1.2 MAST Taxonomy：14种失败模式，79%源于specification和coordination
### 5.2 共识陷阱与Degrade
#### 5.2.1 Martingale Curse与Problem Drift（76-89% generative task）
#### 5.2.2 OpenEvolve的Reward Hacking——agent自行移除verification
### 5.3 原则文件被忽略
#### 5.3.1 Curse of Instructions与"表面遵从"
#### 5.3.2 Constitution内容与AGENTS.md重复问题
### 5.4 过度角色化的代价
#### 5.4.1 通信开销可达2-11.8倍token（AgentPrune, ICLR 2025）
#### 5.4.2 强agent被弱agent拖累（性能损失高达37.6%）

## 6. 前沿产品、评测与长期演进（~4000字，2表）
### 6.1 前沿产品深度对比
#### 6.1.1 BMAD-METHOD：90% token节省，但QA幻觉和上下文压缩
#### 6.1.2 GitHub Spec Kit：Constitution治理，30+ agent支持
#### 6.1.3 Tessl：Spec-as-Source先驱，Private Beta阶段
#### 6.1.4 AWS Kiro：强制EARS三阶段，厂商锁定风险
### 6.2 评测方法
#### 6.2.1 ISO 29148九大质量特征作为基础rubric
#### 6.2.2 LLM-as-Judge：与人类判断一致性κ=0.77-0.87
#### 6.2.3 评测系统的缺失是当前的卡脖子问题
### 6.3 前端/UI设计与架构可演进性
#### 6.3.1 AI视觉设计Agent成熟度：原型生成★★★★☆，跨页面一致性★★☆☆☆
#### 6.3.2 架构Trade-off推理：LLM F1仅0.35-0.39，Multi-Agent方法最佳

## 7. 方向性建议与未解风险（~3000字，1表）
### 7.1 系统架构建议
#### 7.1.1 推荐拓扑：顺序流水线（3-4角色）+ 形式化质量门控 + Generator-Critic
#### 7.1.2 推荐品味编译：Constitution + Critic Agent + 渐进式案例库
#### 7.1.3 推荐Drift防护：Spec-first + EARS DSL + 3-Checkpoint Gates
### 7.2 个人开发者的实施路线图
#### 7.2.1 阶段1（立即）：Constitution + 3-4角色流水线 + Escalation机制
#### 7.2.2 阶段2（1-3个月）：Core Memory + 在线偏好收集 + 案例库积累
#### 7.2.3 阶段3（3-6个月）：LLM-as-Judge评测 + PReF个性化 + Continuous Evaluation
### 7.3 最大的未解风险
#### 7.3.1 评测系统的缺失——没有可优化的目标函数
#### 7.3.2 隐性判断的形式化——"我知道更好但说不出为什么"
#### 7.3.3 长期drift的累积——即使多层防护也无法完全消除

## 8. 必读来源推荐（~1000字）
### 8.1 五篇核心论文/文章
#### 8.1.1 "Why Do Multi-Agent LLM Systems Fail?" (MAST, UC Berkeley NeurIPS 2025)——反面证据大全
#### 8.1.2 "Breaking the Martingale Curse" (AceMAD)——打破共识陷阱的理论方案
#### 8.1.3 MARE (Jin et al., 2024)——多Agent需求工程的代表性框架
#### 8.1.4 KnowNo (ICRA 2023) + Conformal Social Choice——escalation的统计保证
#### 8.1.5 "Spec-Driven Development: From Code to Contract" (2025)——spec-as-source的理论基础

# References
## spec_design_research_outline_references_raw.md
- **Type**: Citation collection
- **Description**: All sources gathered during research
- **Path**: /mnt/agents/output/research/

## Research Dimension Files
- **Type**: Research reports (12 dimensions)
- **Path**: /mnt/agents/output/research/spec_design_agent_dim01.md through dim12.md

## Cross-Verification
- **Type**: Confidence classification and conflict analysis
- **Path**: /mnt/agents/output/research/spec_design_agent_cross_verification.md

## Insight Extraction
- **Type**: Cross-dimension insights
- **Path**: /mnt/agents/output/research/spec_design_agent_insight.md
