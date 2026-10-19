# Intelligent UI 开源选型

状态：research snapshot / review pending；日期：2026-10-19。

研究问题：如何让 Nano Web IM 中的任意 Agent 按需生成交互式回复，以及哪些开源能力值得直接采用。

结论与证据见 [research.md](research.md)。建议优先验证 Thesys OpenUI 的独立渲染器，以 json-render 为备选；尚未完成 Nano 内真实模型与浏览器验证，不宣称生产稳定。

目标归属：[feat-617](../../../changes/archive/feat-617-agent-interactive-responses/spec.md)。当前行为归属：[IM 消息](../../../specs/im/conversations-messages.md)、[Web 聊天体验](../../../specs/im/web-chat-ux.md)。本研究没有修改产品代码或 feat-616。

后续实施：feat-617 已采用上述固定版本 OpenUI；已恢复完整上游组件、原生局部动作和连续探索；真实模型与 Web 产品验证见[验收报告](../../../changes/archive/feat-617-agent-interactive-responses/acceptance.md)。本文保留选型时的研究快照，current 行为以上述 specs 为准。
