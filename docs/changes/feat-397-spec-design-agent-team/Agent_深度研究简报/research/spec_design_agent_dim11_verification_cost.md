# 维度11：人机验证成本优化（Human-on-the-Loop Verification）

## 研究概述
> 研究使命：如何让人的验证成本足够低（不被一堆markdown淹没），同时不牺牲对drift的防护
> 搜索次数：5次（因agent故障转为直接搜索）

---

## 1. Human-on-the-Loop的核心设计模式

Claim: 生产级HITL系统通常采用分层模式：Human-in-the-loop（执行中干预）→ Human-on-the-loop（完成后监督）→ Human-out-of-the-loop（完全自主+监控）
Source: Elementum.ai - Human-in-the-Loop Agentic AI
URL: https://www.elementum.ai/blog/human-in-the-loop-agentic-ai
Date: 2026-03-12
Excerpt: "Human-in-the-loop: Humans intervene during execution to approve or correct agent actions...Human-on-the-loop: Humans supervise after completion to review outcomes and flag exceptions...Human-out-of-the-loop: Full autonomy for predetermined low-risk scenarios"
Context: 业界最佳实践表明，human-on-the-loop比human-in-the-loop更适合高频率agent交互
Confidence: high

Claim: Multi-layered AI on-the-loop是multi-agent系统的推荐模式——在每个agent层级插入AI OTL监控，最终汇总给人类做post-hoc review
Source: Lumenova.ai - The Human-AI Agents Partnership
URL: https://www.lumenova.ai/blog/ai-agents-the-human-ai-partnership/
Date: 2025-10-15
Excerpt: "Multi-layered AI on-the-loop: At each layer of the system, an AI OTL is implemented...decisions and actions would permeate and aggregate through layers of the agent hierarchy"
Context: 这与用户已有的"门禁"机制设计高度吻合
Confidence: medium

## 2. 降低Review负担的关键策略

Claim: 关键策略是"只在真正需要时escalate"——通过分层gate设计，大部分决策由自动化pre-check处理
Source: Phase 4 insight synthesis from dim02_escalation + dim10_failure_cases
URL: Internal cross-reference
Date: 2026-06-03
Excerpt: "I-CALM证明4.1% abstention rate增加可带来13%成本降低+5%错误率降低" / "escalation rate应作为product health metric"
Context: 将escalation机制与验证成本直接关联
Confidence: medium

Claim: Spec refinement的可视化（diff lines随version递减）是有效的review辅助手段
Source: From Specification to Service (API-First MAS paper)
URL: https://arxiv.org/html/2510.19274v1
Date: 2025-07-30
Excerpt: "We plotted the number of diff lines against each version for every specification...many of the lines visibly trend downward, often reaching zero"
Context: diff可视化帮助人类reviewer快速理解spec演变
Confidence: medium

## 3. Gate设计的最佳实践

Claim: 4种gate模式：inline（同步拦截）、async（异步审查）、blended（混合）、peer escalation（agent-to-agent-to-human）
Source: Phase 4 synthesis from dim02_escalation
URL: Internal cross-reference
Date: 2026-06-03
Excerpt: "peer escalation作为agent-to-agent-to-human路径" / "layered guardrails架构"
Context: 对用户的门禁设计有参考价值
Confidence: medium

## 4. 对用户场景的建议

基于交叉分析的核心建议：
1. **渐进式验证**：Gate 1（spec对齐）保持human-on-the-loop，Gate 2（design对齐）增加自动化pre-check
2. **Diff-only Review**：只展示spec/design的变更部分+决策摘要，不展示全文
3. **AI-AI Review前置**：让reviewer agent先做pre-review，只将争议点escalate给人
4. **Escalation Rate监控**：将escalation rate作为系统健康指标，目标<20%
5. **结构化输出**：用decision matrix替代纯markdown，突出关键决策点

---

## 研究局限
本维度因技术故障未执行完整的20+次搜索，证据基于：
1. 5次直接web搜索的结果
2. 与其他维度（尤其是dim02_escalation和dim10_failure_cases）的交叉引用
3. 需要补充更深入的实证数据
