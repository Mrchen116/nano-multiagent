---
status: research-snapshot
recorded-at: 2026-08-10
nano-baseline: ed69eabd8aac87f885c34a96a52626440dc74c32
source-baseline: tau2-bench@668d3bcd135c02aa3438f987ef45735b7c163ee3; ToolSandbox@165848b9a78cead7ca7fe7c89c688b58e6501219; SWE-Together@811a70a28ff20bfbeabf9a8b5ec42152d16c9b4f
current-owner: docs/changes/feat-532-spec-memory-loop/design.md
---

# 面向 Agent 评测的受控用户模拟 — 2026-08-10

本研究包回答：当被测 Agent 需要通过多轮对话向用户澄清需求时，如何用另一个 LLM/Agent 代替真人参与评测，同时避免模拟用户提前泄漏答案、主动替被测 Agent 完成任务，或因自身失真改变实验排名。

研究结合交互式 Agent benchmark 的论文、官方开源实现与 nano-multiagent 当前评测资产，从 Native 的开放问答优势及其主动泄漏、脑补判断、推荐锚定和过度配合风险出发，推导出 `native conversational core + non-intervening post-run audit + observed-failure escalation`。feat-532 不预设复杂控制管道更优，也不把未经审计的 Native 当作可靠用户；它服务于 spec Memory Loop，但方法本身适用于其他需要模拟人类澄清、确认和纠偏的 Agent 评测。

这是研究快照，不是 nano-multiagent 的 current behavior。feat-532 最终采用的实验契约以其 `design.md` 为准。

| 材料 | 作用 |
|---|---|
| [`research.md`](research.md) | 研究问题、固定来源、源码观察、证据限制与采用推导 |
| [`面向 Agent 评测的受控用户模拟.md`](%E9%9D%A2%E5%90%91%20Agent%20%E8%AF%84%E6%B5%8B%E7%9A%84%E5%8F%97%E6%8E%A7%E7%94%A8%E6%88%B7%E6%A8%A1%E6%8B%9F.md) | 面向评测设计者的结论文章：模拟用户该知道什么、何时回答、如何校准 |
