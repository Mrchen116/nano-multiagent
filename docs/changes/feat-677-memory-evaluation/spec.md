# feat-677: Memory 效果评测

状态：需求对齐中。用户要求逐个 benchmark 讨论具体落地方案；本文先保存原始输入与已确认事项，场景、范围和验收标准尚未定稿。

## Relations

- Related: feat-676
- Related: feat-628

feat-676 提供本分支的角色文档记忆与 Dreaming 实现基线；feat-628 是已有长期行为评测设计参考，不据此假定其完整运行器已经实现。

## 原始需求

> [https://chatgpt.com/c/6adf0391-43fc-83ec-9e72-d177db94a4ee](https://chatgpt.com/c/6adf0391-43fc-83ec-9e72-d177db94a4ee) 最新我问他怎么评测，你帮我在本分支基础上，分叉一个新分支，在新worktree中，做一个新需求，就是关于memory的评测，你看看gpt说的，再下载下它新给的附件，理解一下

> 我帮你按了确认

> 然后我们一个个bench讨论具体落地方案

## 原始材料

2026-10-29 已下载并读取 `nano-memory-evaluation.zip`，其中四个文件为：

- `评测方案.md`
- `给本地Agent的评测实施指令.md`
- `scenarios.yaml`
- `CHECKS.md`

原包位置：`/Users/czj/Downloads/nano-memory-evaluation.zip`。

解压位置：`/Users/czj/Downloads/nano-memory-evaluation-source/nano-memory-evaluation/`。同级 `chatgpt-evaluation-response.md` 保存该轮对话正文；对话在线来源见原始需求。

原包 SHA-256：`50cd297b0c1d3f2883905782f08b692ddca4fe64e4fa0ddf2b8502c148401e3e`。包内《评测方案.md》与另行下载的同名文件逐字节一致。

附件是待讨论的评测提案；其中八个原生场景全部标记为 `not_run`，包内检查记录明确未执行模型评测。它不是本仓已有适配器或验收结果。

## 澄清记录

- 用户明确要求从当前分支建立独立分支与 worktree。已从 `80db8b9a604de15476dceb5e2e9a3c92d5fdf170` 创建 `codex/feat-677-memory-evaluation`，工作区为 `/Users/czj/.codex/worktrees/unit-feat-677-memory-eval/nano-multiagent`。本 unit 在该分支对齐，不写入 main。
- 用户要求逐个 benchmark 讨论具体落地方案。尚未确认首期 benchmark 范围、对照条件、输入适配方式、预算或完整跑量；不将附件中的全部建议直接视为已批准要求。

## Agent 对材料的理解

附件希望分别回答三个问题：记忆是否正确保留事实；既有知识是否实际改善后续行动；Dreaming 是否在同一段经历上产生额外收益或退化。它建议把公开评测与 Nano 原生旅程结合，并将纯记忆归因和包含正常历史恢复的产品验收分开报告。

材料中的候选及其用途如下，均为讨论输入：

| 候选 | 材料提出的用途 |
|---|---|
| LongMemEval cleaned | 信息提取、跨会话、时间、更新和信息不足时拒答的基础回归 |
| DolphinBench | 历史信息是否转化为正确的模拟应用工具行动 |
| FrontierMemory | 从既往成功／失败经历生成记忆后，专家后续任务是否改善 |
| MemoryArena | 连续任务之间的信息和结果依赖 |
| Nano 原生场景 | 自然反馈、PA／专家范围、Global 换窗与实际交付；附件优先提议 PA-01 与 EXP-01 |

公开集的静态历史不能直接等同于 Nano 中实际发生的交互；适配时需要明确保留的原始材料、生成记忆的实际路径，以及最终结论能覆盖的范围。具体决定在后续逐项讨论后记录。

## 当前依据

- [评测资产入口](../../../evals/README.md)：现有长期评测资产与候选执行环境分离。
- [角色文档记忆与 Dreaming 当前契约](../../specs/gateway/agent-capabilities.md)：生产能力与待测基线。
- [Global 当前契约](../../specs/gateway/global-agent.md)：原生持续主体、内部委派与交付。
- [feat-676 原始设计与实施](../archive/feat-676-role-memory-dreaming/)：本分支继承的实现来源。
- [feat-628 需求](../feat-628-pa-long-horizon-evaluation/spec.md)：长期评测的已有目标与证据边界。

本 unit 尚未实施适配器，尚未运行任何 benchmark 或原生评测。用户场景与验收标准将在讨论收口后补充。
