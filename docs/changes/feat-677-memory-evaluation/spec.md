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

> 摄入历史，要真正转换成我们的系统的设计对不对，比如消息是从inbox进来的

> 所以应该改造成收消息也是send message吧？其实我不太懂的是，不同的agent harness他们的系统提示词，各种agent机制，工具也不同。他们和我们也会有类似的困难吧？大家怎么测的？比如它用的工具，肯定不是所有agent都有它的轨迹中的工具吧

> 你还是不理解我的意思。我知道旧对话是评测材料，不需要重新执行。但是我们要评测我们的记忆系统好坏，不得把旧对话导入到我们系统，才能真实的跑我们的记忆dreaming过程吗，不然格式都不同，我们怎么测

> 所以我问你，别人评测是不是也要做这个步骤，我们并不特殊啊，只是`inbox`、`send_message`这个特殊一点点。

> 我们一个一个讨论，不要搞串。LongMemEval，这个benchmark有哪些agent，Hugging Face已经测过了？那他们是怎么做转换的呢？

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
- 用户强调历史摄入需要映射到 Nano 实际系统设计，例如消息从 Inbox 进入。后续明确：旧对话不需要重新执行，需要转换并导入本系统的原生历史数据，才能真实运行本系统的记忆与 Dreaming 过程。
- 用户进一步要求先理解不同 harness 如何处理提示词、机制、工具和历史轨迹差异。需要区分固定历史材料、在线环境交互，以及本系统真实运行生成的新轨迹；本轮调查不代表用户已接受某个历史转换方案。
- Agent 修正此前理解：评测适配器负责历史格式、身份、会话、时间和事件关系的转换与导入；实际来源选择、增量处理、Dreaming 提示词与工具、记忆产出由本系统现有机制承担。不能只把外部文本交给另一个总结流程，不能让模型重新生成数据集已有回复，也不需要把原 assistant 改成其他旁观对象。用户要求的是原生历史物化，不是重新演出旧交互。具体可用的历史导入接口和事件映射交给技术设计核实。

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

### 2026-10-29 官方适配方式核对

- [LongMemEval 官方回答代码](https://github.com/xiaowu0162/LongMemEval/blob/main/src/generation/run_generation.py) 把固定历史或检索结果交给回答模型，比较最终回答；已有 assistant 回合属于历史输入，不要求参测模型重新生成这些回合。这类结果与真实在线经历积累的证据范围不同。
- [DolphinBench 接入契约](https://github.com/mem0ai/dolphinbench/blob/main/docs/DRIVER_CONTRACT.md) 保留参测方的模型、Agent loop 和记忆系统，另提供模拟应用 MCP 工具；适配器负责工具格式和调用转发。fresh conversation 与 append-only 导出要求仍需核对，不能因工具可接入就宣称整体协议已兼容。
- [FrontierMemory 规则](https://github.com/letta-ai/frontiermemory/blob/main/docs/rules.md) 把旧轨迹作为记忆生成材料，随后在任务环境中执行并评分；并不要求记忆生成者具备旧轨迹中的每一种业务工具。[Claude Code adapter](https://github.com/letta-ai/frontiermemory/blob/main/src/frontier_memory/agents/claude_code.py) 和 [Codex adapter](https://github.com/letta-ai/frontiermemory/blob/main/src/frontier_memory/agents/codex.py) 分别接入各自原生记忆入口。

以上是文档和代码核对，尚未在 Nano 执行。Agent 的讨论建议：固定外部任务与评分，按其规则适配本系统；把“格式转换得到的历史轨迹”与“本轮模型真实生成的动作”分开记录，不把跨 harness 的系统分数直接归因成记忆本身的收益。

### LongMemEval 的具体历史适配证据

用户要求先聚焦 LongMemEval，本节不以其他 benchmark 的适配方式代替它的证据。Hugging Face 上的 `xiaowu0162/longmemeval-cleaned` 是数据集托管页；下面是分别由原作者或系统厂商公开的评测与代码，不是 Hugging Face 统一测试的 Agent 名单。

- **Mastra Observational Memory**：[公开评测报告](https://mastra.ai/research/observational-memory)；当前 [prepare.ts](https://github.com/mastra-ai/mastra/blob/main/explorations/longmemeval/src/commands/prepare.ts#L873) 真实创建 `ObservationalMemory`，Observer／Reflector 使用真实模型，摄入用主 Agent 则接空响应 mock。脚本按日期排序历史，将原始回合转成带 `role/content/createdAt` 的消息，以 user/assistant 对依次传给 `agent.generate`，经真实输入输出处理器积累记忆，并保存 `om.json`。答题阶段 [run.ts](https://github.com/mastra-ai/mastra/blob/main/explorations/longmemeval/src/commands/run.ts#L899) 读回该状态。脚本有内容清洗与可选 shortcut 配置；这里核实的是适配方法，不认定所有配置都与 Nano 目标等价。
- **Mem0**：[官方评测说明](https://github.com/mem0ai/mem0/blob/main/docs/core-concepts/memory-evaluation.mdx)；[LongMemEval runner](https://github.com/mem0ai/memory-benchmarks/blob/main/benchmarks/longmemeval/run.py#L291) 按日期排序 session，保留 user/assistant 的角色和正文并删除 `has_answer`，每题创建独立 user_id，将相邻两条消息组成一组，调用 `mem0.add(messages, user_id, timestamp=...)`，随后检索并答题。不是先由测试脚本手写事实再灌库。
- **Zep**：[官方 LongMemEval notebook](https://github.com/getzep/zep-papers/blob/main/kg_architecture_agent_memory/zep_longmem_eval.ipynb) 为每题建立 user/session，把每条历史变成 `Message(role, role_type, content, created_at)` 后调用 `zep.memory.add`。当前 notebook 含题型筛选及 8000 字符截断，不能直接把这份代码快照当作完整无损全量执行协议。
- **ChatGPT／Coze**：[原论文附录 B](https://arxiv.org/html/2410.10813v2#A2) 记录了 2024 年 8 月人工通过网页逐 session 交互的研究，使用 97 题、每题 3–6 个 session，并排除了部分题型；这不是完整 500 题的自动原生历史导入案例。

对 Nano 的适用判断：Mastra 的历史转换、真实记忆处理器执行和答题时加载产物，是当前最直接的同类参考。Nano 应转换为自身记忆来源可消费的历史结构，再执行现有 Dreaming；具体导入方式仍需核对本仓公开接口。

## 当前依据

- [评测资产入口](../../../evals/README.md)：现有长期评测资产与候选执行环境分离。
- [角色文档记忆与 Dreaming 当前契约](../../specs/gateway/agent-capabilities.md)：生产能力与待测基线。
- [Global 当前契约](../../specs/gateway/global-agent.md)：原生持续主体、内部委派与交付。
- [feat-676 原始设计与实施](../archive/feat-676-role-memory-dreaming/)：本分支继承的实现来源。
- [feat-628 需求](../feat-628-pa-long-horizon-evaluation/spec.md)：长期评测的已有目标与证据边界。

本 unit 尚未实施适配器，尚未运行任何 benchmark 或原生评测。用户场景与验收标准将在讨论收口后补充。
