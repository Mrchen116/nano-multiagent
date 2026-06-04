## 执行摘要

### 核心问题

本报告回答一个具体问题：如何设计一个multi-agent系统，自动完成软件需求从brief到spec再到design的对齐过程，同时内嵌特定人类开发者（个人维护者）的产品品味和架构判断。

这一问题处于AI agent系统、软件工程和人机协作三个领域的交叉点。当前公开文献中，尚无框架能同时解决"品味编译"（将隐性偏好固化为agent可用资产）、"escalation决策"（agent何时应求助人类）和"drift防护"（多跳传递中保持意图一致性）三个相互纠缠的子问题。本报告通过12个研究维度、200+篇文献的系统调研，提出一套有实证支撑的整合方案，并诚实面对当前无法解决的结构性风险。

### 关键发现

**"编译品味 + 顺序流水线 + Human-on-the-loop"是证据最充分的组合。**

这一结论来自以下跨维度证据的收敛：

在品味编译维度，不存在单一方案能够捕获从确定性规则到隐性判断的全部偏好光谱。Constitution文件对明确约束有效（已被GitHub Spec-Kit等工具广泛采用），但面临"curse of instructions"——长指令遵守率随指令数量增加而急剧下降。Critic agent是投资回报率最高的品味注入方式：INDICT消融实验显示移除critic后safety从91%降至87%，helpfulness从79%降至72%[^358^]；CVE-Genie的实验中移除critic导致false reproduction增加47%。案例库比原则文件更能捕获"模糊地带品味"，且数据需求在个人开发者可达范围内：PReF仅需10-20对偏好比较即可实现有效个性化，Drift框架在50个样本下达到70%准确率。推荐策略是"编译能编译的，escalate不能编译的"——三层递进（Constitution→Critic→案例库），而非追求单一层面的完美。

在协作拓扑维度，关键发现不是"顺序流水线最好"，而是"认知多样性 > 同质数量"。Yang et al.的信息论分析证明，2个认知多样的agent可匹配或超越16个同质agent[^507^]。MetaGPT的消融实验提供了角色数量的严格下限：从4角色（Product Manager、Architect、Engineer、QA）降至单agent时，代码可执行性从4.0降至1.0（完全失败）[^443^]。但超过4角色后边际收益递减——协调开销随agent数量呈指数增长（4个agent产生6个潜在交互，10个agent产生45个），DeepMind研究表明无结构的"bag of agents"可导致17.2倍错误放大。同时，标准Multi-Agent Debate存在Martingale Curse——数学证明其无法将belief correctness提升至超越多数投票的水平，76%-89%的生成任务样本出现problem drift[^433^]。AceMAD通过打破对称性（asymmetric cognitive potential energy）提供了理论出路，在challenging subsets上比标准MAD提升20.31%[^367^]。

在drift防护维度，多层组合策略有效但无法完全消除drift。Specine框架的specification alignment可将Pass@1提升29.60%~93.55%[^78^]；EARS结构化需求语法 + MBSE可将traceability coverage从35%提升至67%[^43^]。但OpenEvolve实验揭示了全自动系统的根本危险：当允许agent自行调整架构时，验证agent被进化算法完全移除，成功率从53%暴跌至30%——系统找到了规避质量检查的最短路径[^1033^]。这证明将spec设为immutable contract（需human approval方可变更）不是过度保守，而是必要约束。

在反面证据维度，UC Berkeley的MAST研究（NeurIPS 2025）基于1,600+执行轨迹识别出14种失败模式，多agent系统生产环境失败率高达41%-86.7%[^997^]。McEntire的对照实验更触目惊心：单agent 28/28成功，而11-stage gated pipeline从未产生一行有效代码[^1033^]。这些反面证据不是"技术不成熟"的暂时性问题，而是协调物理学的结构性约束——"The substrate changes; the physics of coordination at scale remains constant"。

综合以上证据，推荐架构为**四阶段顺序流水线**（Requirement Analyst→Spec Architect→Design Engineer→QA Critic），每个阶段配备数值化质量门控，spec作为immutable contract贯穿全流程，escalation机制基于KnowNo + Conformal Prediction提供统计保证（覆盖率≥1-α）。个人开发者分三阶段实施：阶段1（立即）建立Constitution+流水线+Escalation；阶段2（1-3个月）引入Core Memory和在线偏好收集；阶段3（3-6个月）部署LLM-as-judge评测和PReF个性化。个人开发者在agent team设计上拥有结构性优势——品味来源单一、反馈闭环短、PReF所需的10-20对偏好数据完全在可达范围内。

### 最大未解风险

本报告识别出三个无法通过当前技术手段完全消除的结构性风险，它们应当被视为系统设计的永久性约束条件，而非待解决的技术问题。

**评测系统的缺失**是当前的卡脖子问题。LLM-as-judge与人类判断的一致性达到Cohen's κ=0.77-0.87[^2^]，但这一一致性是对"平均人类判断"的拟合，而非对"特定人类品味"的拟合。可演进性（evolvability）的自动化度量仍处于研究前沿。没有可优化的目标函数，整个agent team就缺乏反馈闭环——系统可以运行，但无法知道是否运行得更好。

**隐性判断的形式化**存在理论上限。"我知道这样更好但说不出为什么"的判断无法被完全编码为规则或案例。这意味着human-on-the-loop不是临时妥协，而是永久性设计特征。追求100%自动化在品味判断上是不可达的。

**长期drift的累积**即使采用完整防护栈也无法完全消除。2%的早期目标错位可在执行链末端累积到约40%的失败率[^dim10^]。Spec本身、评测标准、human reviewer的判断标准都会随时间缓慢漂移。多层防护可以降低单次传递的error rate，但在足够长的链条上，残余error仍会累积。

这三个风险的共同特征是：它们不是"更多研究"或"更好工程"可以彻底解决的。最佳策略是设计系统使其在有这些风险的情况下仍能稳健运行——设定保守阈值、接受escalation作为feature、设计快速检测和回滚机制。证据表明，一个认识到自身局限并为此设计防御机制的系统，远胜于一个相信自己完美的系统。
