# Cross-Verification Report: Agent Team 自动化 Spec & Design 深度研究

## 验证方法
基于12个维度的独立深度研究报告，对所有关键发现进行置信度分类和冲突检测。

---

## High Confidence Findings（≥2个维度独立确认）

### HC-1: 没人能把人完全踢出spec/design还拿到生产级质量
- **确认维度**: dim10（失败案例）+ dim07（前沿产品）+ dim04（协作拓扑）
- **证据**: ChatDev 33%成功率、MetaGPT项目级通信崩溃、MAST 14种失败模式、McEntire对照实验（单agent 28/28成功→多agent 36%-100%失败）
- **置信度**: **HIGH** — 28条High confidence证据 + 14条Medium confidence证据

### HC-2: Debate存在系统性共识陷阱（Martingale Curse）
- **确认维度**: dim04（协作拓扑）+ dim10（失败案例）+ dim05（角色分解）
- **证据**: Liu et al.数学证明、76-89% generative task出现problem drift、85.5% sycophantic conformity、3-agent voting ensemble生产环境1月内废弃
- **置信度**: **HIGH** — 有数学证明 + 多项独立研究确认

### HC-3: 角色分解有真实价值，但来自"认知多样性"而非"角色扮演"
- **确认维度**: dim05（角色分解）+ dim04（协作拓扑）+ dim07（前沿产品）
- **证据**: MetaGPT消融（可执行性1.0→4.0）、ChatDev消融（Quality 0.22→0.40）、Yang et al.信息论分析（2认知多样agent > 16同质agent）
- **置信度**: **HIGH** — 多项消融实验一致支持

### HC-4: Constitution/原则文件有效但面临"Curse of Instructions"
- **确认维度**: dim01（品味编译）+ dim10（失败案例）+ dim07（前沿产品）
- **证据**: Spec-Kit广泛采用、curse of instructions（长指令遵守率下降）、agent replicate AGENTS.md内容、RL训练导致"表面遵从"
- **置信度**: **HIGH**

### HC-5: Spec-anchored + Bidirectional Sync是防drift的核心手段
- **确认维度**: dim03（drift防护）+ dim07（前沿产品）+ dim10（失败案例）
- **证据**: Specine Pass@1 +29%~93%、Prometheus 74.4% rescue rate、Tessl实践、spec drift 8个结构性维度
- **置信度**: **HIGH**

### HC-6: 个性化LLM可行，但软件设计品味是研究空白
- **确认维度**: dim12（个性化）+ dim01（品味编译）
- **证据**: PReF 10-20对偏好即可个性化、Drift 50样本达70%准确率、NS-DPO处理偏好漂移——但所有方法验证于对话/文本生成，缺少"architecture taste"研究
- **置信度**: **HIGH**（方法可行）+ **MEDIUM**（迁移性待验证）

### HC-7: Escalation机制有成熟技术路线
- **确认维度**: dim02（escalation）+ dim11（验证成本）
- **证据**: KnowNo+Conformal Prediction提供统计保证、SC方法AUROC 0.68-0.79、LPP融合多信号、I-CALM 4.1% abstention → 13%成本降低
- **置信度**: **HIGH**

### HC-8: 澄清策略有效但需控制轮数
- **确认维度**: dim06（澄清）+ dim10（失败案例）
- **证据**: ClarifyGPT Pass@1 +13.87%~16.83%、平均2.85个问题、3轮为业界共识上限、有条件澄清 > 无条件澄清
- **置信度**: **HIGH**

---

## Medium Confidence Findings（1个维度的权威来源）

### MC-1: Generator-Critic对抗是最可靠的拓扑选择
- **来源维度**: dim04（协作拓扑）
- **证据**: IronEngine Planner-Reviewer、RLAC对抗性critic更鲁棒——但open-ended设计任务直接对比实验稀缺
- **置信度**: **MEDIUM** — 理论强但缺乏spec/design任务直接证据

### MC-2: LangMem的procedural memory是唯一让agent"习得"品味的方案
- **来源维度**: dim01（品味编译）
- **证据**: procedural memory（prompt self-optimization）可让agent持续改进——但工程复杂度高
- **置信度**: **MEDIUM** — 学术perspective，缺少大规模验证

### MC-3: 3-4个角色是有效下限
- **来源维度**: dim05（角色分解）
- **证据**: MetaGPT/ChatDev消融显示≥3-4角色有效，但>4后边际递减
- **置信度**: **MEDIUM** — 特定任务上的数据，泛化性不确定

### MC-4: EARS DSL + Traceability可将coverage从35%→67%
- **来源维度**: dim03（drift防护）
- **证据**: MBSE+LLM实证数据——但样本有限
- **置信度**: **MEDIUM**

---

## Conflict Zones（维度间存在张力）

### CZ-1: Debate是否有效？
- **dim04正面**: Liang et al. +16.0%、Du et al. +7.2-15.9%、FORD +4.9%
- **dim04/dim10反面**: Martingale Curse数学证明、76-89% problem drift、3-agent ensemble 1月废弃
- **解决**: **有条件的有效** — 对抗性debate（AceMAD）有效，标准debate有害；N≤4, T≤2是安全边界

### CZ-2: 多Agent是否优于单Agent？
- **dim05正面**: 消融实验一致显示多角色 > 单角色
- **dim05反面**: Xu et al./Tran & Kiela显示token预算匹配时单agent可匹配多agent；McEntire实验单agent 28/28成功
- **解决**: **取决于协调开销** — 认知多样性 > 同质数量；协调成本是关键变量

### CZ-3: Constitution文件是否有效？
- **dim01正面**: Spec-Kit广泛采用、ArbiterOS治理框架
- **dim01/dim10反面**: Curse of instructions、agent replicate AGENTS.md、表面遵从
- **解决**: **有效但需要工程化** — 需要长度控制、harness enforcement、continuous evaluation

### CZ-4: 个性化方法的选择
- **dim12训练时**: VPL/PReF效果好但需要训练
- **dim12测试时**: Drift/AMULET/T-POP无需训练但效果稍弱
- **解决**: **混合方案** — 测试时方法（Drift + Memory）适合个人开发者快速启动，训练时方法（PReF）适合规模化

---

## Low Confidence Findings（需进一步验证）

### LC-1: Spec-as-source是终极目标但尚未成熟
- **来源**: dim03
- **理由**: Tessl是唯一探索者，面临MDD同样的历史问题
- **置信度**: **LOW** — 主观判断，缺少客观证据

### LC-2: AI-AI Review前置可将human review成本降低80%
- **来源**: dim11（部分基于推理而非实证）
- **理由**: 逻辑合理但缺少production数据
- **置信度**: **LOW**

### LC-3: 2%早期错位→40%末端失败的drift级联效应
- **来源**: dim03 + dim10
- **理由**: 单一来源，需要独立验证
- **置信度**: **LOW-MEDIUM**
