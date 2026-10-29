# feat-677: Memory 效果评测

状态：首期 LongMemEval 框架与 Nano 适配器已交付；2026-10-29 用户授权继续实现统一时间回放，并在完成后只跑一道真实用例，不扩大到批量评测。其他 benchmark 后续单独讨论。

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

> 很好，那就细化，写到设计文档中

> 你注意你设计什么测试，应该要跟我的dreaming机制解耦一点。后面我的记忆机制改，测试框架应该不用改

> 啊,我有点想问一个问题,就是因为我们的这个历史记录是global的嘛,是一直长期存在的。那你问问题的时候，它去不去我之前的 context，不就泄露答案了吗。你有考虑到这个问题吗？就你是怎么解决的。

> OK，明白了，那你先去实现，停在实际测之前，不要真的开始大规模测，token消耗大，我要确认没问题，我再去测

> 那就按这个方案把 LongMemEval 的时间回放实现了，改完再跑一个用例试试，先别大规模跑。

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

- 2026-10-29 时间回放口径补充：用户提出“带时间戳的，我们应该尽量模拟，按照真实情况的进行记忆抽取”，并确认“我也觉得可以兼容吧，就做一套可以不”。统一采用“按可靠时间线逐步摄入 → 被测系统按正常规则触发记忆处理 → 等待已经触发的处理结束 → 冻结记忆 → 冷上下文测试”，不另立一套严格时点快照实验。等待不表示人为跳到下个周期或强制触发尚未到期的整理；冻结时尚未触发的积压须如实记录。数据缺少逐消息时间或时区时保留原始精度并披露解释约定，不虚构时间线。本次决定不扩大首期 LongMemEval 的实现范围；其他 benchmark 后续接入时沿用原则并遵守各自原协议。当前已交付的集中导入实现尚未满足这条新增要求，旧验收不覆盖时间回放。
- 用户明确要求从当前分支建立独立分支与 worktree。已从 `80db8b9a604de15476dceb5e2e9a3c92d5fdf170` 创建 `codex/feat-677-memory-evaluation`，工作区为 `/Users/czj/.codex/worktrees/unit-feat-677-memory-eval/nano-multiagent`。本 unit 在该分支对齐，不写入 main。
- 用户要求逐个 benchmark 讨论具体落地方案。本轮已批准细化 LongMemEval 的原生历史适配方案；整个 unit 的首期 benchmark 范围、对照条件、预算和完整跑量仍未确认，不将附件中的全部建议直接视为已批准要求。
- 用户强调历史摄入需要映射到 Nano 实际系统设计，例如消息从 Inbox 进入。后续明确：旧对话不需要重新执行，需要转换并导入本系统的原生历史数据，才能真实运行本系统的记忆与 Dreaming 过程。
- 用户进一步要求先理解不同 harness 如何处理提示词、机制、工具和历史轨迹差异。需要区分固定历史材料、在线环境交互，以及本系统真实运行生成的新轨迹；本轮调查不代表用户已接受某个历史转换方案。
- Agent 修正此前理解：评测适配器负责历史格式、身份、会话、时间和事件关系的转换与导入；实际来源选择、增量处理、Dreaming 提示词与工具、记忆产出由本系统现有机制承担。不能只把外部文本交给另一个总结流程，不能让模型重新生成数据集已有回复，也不需要把原 assistant 改成其他旁观对象。用户要求的是原生历史物化，不是重新演出旧交互。具体可用的历史导入接口和事件映射交给技术设计核实。
- 用户要求评测框架和测试与当前 Dreaming 机制解耦。稳定部分是历史、问题、评分和实验协议；原生历史导入、记忆准备与冷上下文恢复由 Nano 适配层承担。后续记忆实现变化不应要求改题、改评分或改通用框架；实现相关接线允许在适配层局部调整。
- 用户确认冷上下文隔离方案后授权先实现当前 LongMemEval 方案。本轮只运行无真实模型请求的确定性验证，不运行候选真实模型、真实 judge 或完整 benchmark；模型、样本和预算不是实现阻塞项，留给用户之后配置并显式启动。

## 已确认的 LongMemEval 要求

本 unit 实施以下 LongMemEval 范围；不实施附件的其他 benchmark 与原生场景。

### Requirement: 从原始经历评测本系统真实记忆能力

#### Scenario: 导入固定历史并回答后续问题
- **GIVEN** 一道 LongMemEval 题的完整历史以及独立保存的问题和评分材料
- **WHEN** 维护者评测 Nano 的记忆能力
- **THEN** 原有 user/assistant 正文、身份、会话、日期和顺序被保留并转换为 Nano 可消费的原生历史，由被测版本自己的记忆机制处理；之后在冷上下文中回答问题。
- **AND** 历史适配不重新生成已有回复，不先替被测系统总结答案，不在生成记忆时泄露未来问题或答案标注。

### Requirement: 在一套协议中按时间线积累记忆并等待已触发工作完成

#### Scenario: 历史跨越记忆维护周期
- **WHEN** 摄入带可靠会话时间的 LongMemEval 历史
- **THEN** 按日期及原顺序逐步让经历可见，被测系统依据自己的正常自动整理规则积累记忆；较早整理不能读取尚未到达的历史。
- **AND** 用模拟时间消除真实等待；保留会话级精度和无时区解释约定，报告模拟假设与触发时点，不把执行机器今天当作经历时间。

#### Scenario: 摄入结束后冻结
- **WHEN** 最后一组历史已导入
- **THEN** 等待已经触发的处理完成后冻结当前记忆并冷答题，不因测试将开始而强制启动未到期的维护，不另设严格时点快照模式。
- **AND** 未触发积压与已触发却失败或超限的工作分别报告；前者不等于准备失败，后者不能伪装为准备就绪。

#### Scenario: 只进行一次有界真实试跑
- **WHEN** 时间回放通过确定性验证
- **THEN** 仅对先前选定的一道完整题执行真实准备、冷答题与评分；保留逐阶段结果和实际消耗，不自动追加题目或重跑候选。

### Requirement: 改变记忆机制仍能沿用同一评测

#### Scenario: 比较前后两个记忆版本
- **WHEN** 维护者更改记忆的存储、检索、整理策略或 Dreaming 实现
- **THEN** 可沿用同一版本的历史、问题、评分器和报告口径运行比较；必要的产品接线变化局限于 Nano 适配层。
- **AND** 通用测试验历史保真、问题隔离、冷启动答题和结果完整性，不把某种游标、分页格式、记忆文件布局或 Dreaming 调用次数作为通过条件。

### Requirement: 冷答题不能旁路访问旧 Global 上下文

#### Scenario: 长期历史仍存在于准备环境
- **WHEN** 维护者使用准备后的记忆回答测试问题
- **THEN** 答题在新的 session 与隔离运行环境进行，不继承旧 Global 上下文、摘要、Inbox 或维护轨迹；工具与服务不能回查准备环境。
- **AND** 允许被测记忆机制自行保留的原文索引，但框架不得额外开放原始历史、未来问题标注或 gold。

### Requirement: 实施完成后由维护者决定何时花费模型预算

#### Scenario: 仅检查数据与执行计划
- **WHEN** 维护者运行默认计划或确定性自检入口
- **THEN** 不请求真实候选模型或 judge，能查看题集规模、配置、限额及尚未执行状态。

#### Scenario: 显式执行评测
- **WHEN** 维护者之后提供模型、题集与有界运行配置，并显式允许模型调用
- **THEN** 才执行对应评测，报告逐题状态、评分、成本证据及未完成项；无记忆生成或回答结果时不伪装成已通过。

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

- [评测资产入口](../../../../evals/README.md)：现有长期评测资产与候选执行环境分离。
- [角色文档记忆与 Dreaming 当前契约](../../../specs/gateway/agent-capabilities.md)：生产能力与待测基线。
- [Global 当前契约](../../../specs/gateway/global-agent.md)：原生持续主体、内部委派与交付。
- [feat-676 原始设计与实施](../feat-676-role-memory-dreaming/)：本分支继承的实现来源。
- [feat-628 需求](../../feat-628-pa-long-horizon-evaluation/spec.md)：长期评测的已有目标与证据边界。

当前 LongMemEval 技术细节见 [design.md](design.md)。本轮交付实现及确定性验证，真实模型效果与正式跑量明确待用户启动；其余 benchmark 不在本 unit 实施范围。
