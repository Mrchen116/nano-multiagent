---
status: research-snapshot
recorded-at: 2026-08-08
nano-baseline: b95e19f152cf498ea05601df4f76a67c924dbfd5
upstream: claude-code-local-reconstruction
upstream-baseline: 0991eac5ccd518d6bd0486752f61a42f9ad68fa8
installed-claude-code: 2.1.226
current-owner: pending-adoption
---

# Claude Code Dynamic Workflows — 2026-08-08

本研究包还原 Claude Code Dynamic Workflows（界面入口名 `ultracode`，工具名 `Workflow`）的可观察运行契约与可复刻架构。它是带版本和本机 trace locator 的研究快照，不代表 nano-multiagent 已采用该能力，也不覆盖任何 current spec。

结论先由三条主证据链交叉确认：Anthropic 当前官方文档、本地 Claude Code 开源重建仓的固定 commit、以及 Claude Code 2.1.226 经 LLM Proxy 产生的 Luna 最小实验；对“AST 解释还是直接执行 JS”的剩余歧义，再以哈希固定的 installed binary 做只读静态取证。

| 材料 | 作用 |
|---|---|
| [`research.md`](research.md) | 基线、来源、实验记录、逐项证据矩阵与未知项 |
| [`Claude Code Dynamic Workflows 运行机制.md`](Claude%20Code%20Dynamic%20Workflows%20运行机制.md) | 面向实现者的运行机制、提示词分层与复刻蓝图 |
| [`../../../../.claude/skills/reverse-engineer-claude-code/SKILL.md`](../../../../.claude/skills/reverse-engineer-claude-code/SKILL.md) | 从源码、官网和低成本 Luna trace 复刻其他 Claude Code 能力的程序化方法 |

若后续决定把该能力引入 nano-multiagent，应单独建立 change unit，并将最终行为归并到相应 current spec；本包继续冻结为上游研究证据。
