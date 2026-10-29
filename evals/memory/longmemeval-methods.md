# LongMemEval：官方基线与业界评测方法

LongMemEval 给出带时间的历史对话，再提出一个需要利用历史回答的问题。**系统怎样读入历史、保留什么、答题时能看什么，以及如何评分，共同决定结果。** 看到两个 LongMemEval 分数时，应先核对这些条件。

本文是本仓对该 benchmark 评测方法的展开记录。运行本仓实验仍以 [Memory suite 协议](README.md) 为准。

| 记录项 | 基线 |
|---|---|
| 核验日期 | 2026-10-29 至 2026-10-30 |
| 范围 | ICLR 2025 LongMemEval、后续 cleaned 数据及下列公开评测代码；LongMemEval-V2 另行研究 |
| 本仓代码基线 | `cb296e8affc78715a3013bb35c737fc2bfec41a3` |
| 证据状态 | 论文与公开代码核验；本次未运行候选模型、商业产品或 judge，未复现厂商成绩 |
| 维护归属 | `evals/memory/`；本文维护外部方法研究，本仓执行协议由 suite README 维护 |

## 1. 数据里有什么，评测系统要自己完成什么

官方发布 500 道问题，覆盖信息提取、跨会话推理、知识更新、时间推理和拒答。S 的历史约 115k tokens，M 扩展到约 1.5M；oracle 只保留含答案的会话。2025 年发布过 cleaned 修订，因此 original、cleaned 和 oracle 必须分别标记。[官方数据说明][official-readme]

一题的主要材料如下。答案标注供评测控制程序使用，不能作为普通记忆系统挑选历史的提示。

| 数据 | 用途 |
|---|---|
| `haystack_sessions` | 多段历史会话；每段包含有顺序的消息 |
| `haystack_dates`、`haystack_session_ids` | 会话时间与身份，和会话数组对应 |
| 消息的 `role`、`content` | 谁说了什么，包含已有的 assistant 回答 |
| `question`、`question_date` | 答题阶段的问题与提问时间 |
| `answer`、`answer_session_ids`、消息上的 `has_answer` | 正确答案及证据标注；oracle 实验会明确使用这类特权信息 |

**本次直接扫描的 S cleaned 文件只有 `user`、`assistant` 两种角色，没有工具调用事件或上下文压缩事件。** 扫描覆盖全部 500 题，共 122,416 条 user 消息、124,334 条 assistant 消息；消息字段集合为 `role/content/has_answer`。数据 revision 为 `98d7416c24c778c2fee6e6f3006e7a073259d48f`，SHA-256 为 `d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`。[固定版本数据][cleaned-data]

这意味着：

- 原始 assistant 消息已经是数据的一部分。导入它们与让新模型重新回答每个历史 user 消息，是两种不同操作。
- 数据中的 session 是一次聊天的边界。把它映射成产品的 thread、存储 session 或 Global 的一个 context window，需要适配器作出决定。
- 摘要、压缩、检索、观察与反思，以及摄入时发生的工具调用，属于被测系统的处理过程。不能从本数据推断某个产品天然具有或不具有上下文压缩。
- 该版本可以评对话记忆；单靠这些数据，不能验证真实工具执行结果、失败恢复或子任务轨迹的记忆质量。

## 2. 先用一个例子理解题目

**下面的“团团”全部是教学示例，不是论文原题、产品实测记录或实际模型输出。** 三段历史与最终问题设在不同日期；这里的日期也只服务于说明。

```text
历史会话 A，5 月 1 日：
用户：我养了一只猫，叫团团，今年三岁。
助手：正常回复……（示意）
结束这次聊天。

历史会话 B，5 月 10 日：
用户：团团吃鸡肉会过敏，兽医让我避开含鸡肉的猫粮。
助手：正常回复……（示意）
结束这次聊天。

历史会话 C，5 月 20 日：
用户：我下周要出差，帮我准备一份行李清单。
助手：给出行李清单……（示意）
结束这次聊天。

测试问题，6 月 1 日：
用户：我的猫叫什么？给它买猫粮时要避开什么？

期望答案：猫叫团团，买猫粮时要避开鸡肉。
```

这道示例需要合并 A、B 的信息；C 是无关历史。评测系统持有期望答案，被测系统在答题前只能接触协议允许的历史或记忆。

同一段材料，还可以帮助理解不同能力。下表仍然只是自编示意，不是官方题目分布。

| 能力 | 示例问题或新增历史 | 要观察什么 |
|---|---|---|
| 用户信息提取 | “我的猫叫什么？” | 是否取回用户说过的事实 |
| 助手信息提取 | 假设助手曾给一份计划起名“出差照护表”，再问其名称 | 是否保留 assistant 提供的信息 |
| 偏好应用 | “结合我家猫的情况，写一条选粮提醒。” | 是否主动运用已知限制 |
| 跨会话推理 | 同时问猫名与过敏原 | 是否合并不同会话的证据 |
| 知识更新 | 后来更正“过敏原是牛肉，鸡肉已排除” | 是否采用更新后的事实 |
| 时间推理 | “我是哪天告诉你过敏情况的？” | 是否正确利用会话日期 |
| 拒答 | “团团的芯片编号是什么？”但历史从未提及 | 是否承认信息不足 |

## 3. 官方到底评了哪些产品和方法

官方论文有三类核心实验。下表列主要正文实验对象；具体模型版本与设置应随原论文表格读取。[论文 §3.4、§5.1][paper]

| 实验类别 | 主要对象 | 历史怎样交给系统 |
|---|---|---|
| 商业聊天产品 | ChatGPT：GPT-4o、GPT-4o-mini；Coze：GPT-4o、GPT-3.5-turbo | 人工逐回合、逐会话交互，最后新开聊天提问 |
| 长上下文阅读 | GPT-4o、Llama 3.1 Instruct 8B/70B、Phi-3 128k 14B、Phi-3.5 Mini 4B | 将完整历史或 oracle 历史放入答题上下文；比较直接回答与 Chain-of-Note |
| 检索与阅读设计 | 主实验采用 Stella V5 检索，GPT-4o、Llama 3.1 70B/8B 阅读；比较索引与阅读策略 | 历史建立索引，问题检索相关材料，再交给阅读模型 |

论文 Table 2 还讨论 MemoryBank、LD-Agent、RAPTOR、MemWalker、HippoRAG 等系统的架构位置。**列入架构分类表不等于都参加了同一组实测排名。** 商业产品实验、阅读实验和检索实验也各有条件。[论文 §4.2][paper]

### 3.1 商业产品：真的分多次聊天，再开新聊天问

按“团团”示例理解，操作顺序是：

1. 为这一题准备隔离的记忆状态，开启待测产品的记忆能力。
2. 在同一产品账号的第一次聊天中告知猫名，结束聊天。
3. 新开第二次聊天，告知过敏情况，结束聊天。
4. 新开第三次聊天，聊出差等干扰内容，结束聊天。
5. 再开新聊天，只问“猫叫什么、选粮避开什么”，观察产品是否从跨聊天记忆中找回两件事。
6. 对照答案判定；下一道题开始前清理记忆，避免上一题的信息混入。

这里最终提问时没有把 A、B、C 重新粘贴到消息里。这个实验所观察的是产品跨聊天保留与利用信息的表现。

官方这次商业产品 pilot 在 **2024 年 8 月前两周**进行，采用 97 道、每题 3–6 段会话的短历史子集；排除了特定跨月时间题、assistant 信息题，早期版本也未包含拒答题。论文报告人工评答案并在题间清理记忆。它不能代表当前产品，也不能直接等同于完整 S cleaned 的成绩。[论文 Appendix B][paper]

**复现细节仍有缺口：** 论文描述人工交互，但没有充分交代如何强制产品复现数据中原有的 assistant 回答、如何统一产品内部不可见的记忆状态。因此示例中的“正常回复”只是帮助理解操作，不能据此声称官方逐字回灌了双方原文。

### 3.2 Full context 与 oracle：答题时直接读给定材料

用同一示例：

```text
Full context：
输入 = 日期 + 历史 A + 历史 B + 历史 C + 测试问题
模型阅读当前输入，输出答案。

Oracle：
评测程序先按证据标注选出 A、B。
输入 = 日期 + 历史 A + 历史 B + 测试问题
模型输出答案。
```

全文输入观察长上下文中的查找与推理；oracle 排除了寻找相关会话的困难，常用于诊断阅读环节。oracle 仍可能答错，也不保证是所有系统的数学上界。它使用了证据位置，必须单列。

官方生成工具支持历史的 JSON/自然语言格式，以及直接回答、Chain-of-Note 等策略。Chain-of-Note 会引导模型先整理相关笔记再回答，不能因此认定它具有跨次请求的持久记忆。[官方运行说明][official-readme]

### 3.3 RAG：先检索，再把找到的材料给回答模型

```text
准备：A、B、C → 分段 → 建索引
提问：“我的猫叫什么？选粮避开什么？”
检索：可能找回 A、B，也可能只找回 A
回答：模型根据检索结果作答
评分：对照完整期望答案
```

如果只找回 A，回答模型即使完全读懂，也缺少过敏信息。如果 A、B 都找回但仍只答猫名，则问题在阅读或作答环节。**检索到证据与最后答对，应该分开观察。**

官方工具允许按 turn/session 建索引，使用 BM25、向量检索，以及摘要、关键词、用户事实等 key 扩展；还支持时间过滤。摘要用来帮助检索，与只允许模型阅读摘要，是不同配置。复现时要分别记录索引 key 和交给模型的 value。[官方检索说明][official-readme]

论文中的摘要、关键词与事实提取只使用 user 消息；这不等于所有阅读实验都删除 assistant 内容。官方生成工具另有 `USERONLY` 开关，应分别核对提取端和阅读端。[论文 Appendix D][paper]、[官方运行说明][official-readme]

## 4. 业界记忆系统怎样接入

下面记录三个有公开代码的实现切片。它们说明具体流程，不构成覆盖所有厂商的调研，也没有确认任一公开成绩恰好使用了这些 commit 的全部默认参数。

### 4.1 Mastra Observational Memory：回放原对话，运行记忆处理器

核验代码显示，准备阶段按日期处理历史，原 session 映射为 thread，同题共享 resource；双方消息成对送入。OM 主聊天模型返回空的 mock 响应，Observer/Reflector 使用真实模型，状态存为 `om.json`。答题阶段恢复状态，使用新的 eval thread 发起问题。[准备代码][mastra-prepare]、[答题代码][mastra-run]

用“团团”示例理解：

```text
线程 A 的双方原文 → 记忆处理器
线程 B 的双方原文 → 同一份累积记忆
线程 C 的双方原文 → 同一份累积记忆
保存 → 恢复 → 新答题线程询问猫名与过敏原
```

因此，摄入阶段 mock 主聊天模型，并不表示记忆实验全程没有调用真实模型。实际保存了哪些观察、哪些原文仍会注入，需要检查该配置和产物。

此 commit 有几个必须核对的变体：内容清洗、逐消息合成 5 秒时间偏移、shortcut 在末尾集中观察、`sessionLimit` 下按 gold 证据会话补选历史；答题代码还有条件触发的重答与修订 question/answer 路径。**代码中存在这些路径，不表示每次成绩都用了它们。** 比较成绩前应核对实际参数和 original/fixed 结果列。[准备代码][mastra-prepare]、[答题代码][mastra-run]

### 4.2 Mem0：写入记忆，再检索；两种评分模式需分开

核验 runner 为每题及 run 建立独立 `user_id`，按日期导入，消息保留 `role/content`、去掉 `has_answer`，每两条调用一次 `add` 并传入会话时间。答题时用问题检索，按 cutoff 取记忆；支持额外 user profile。[Mem0 runner][mem0-run]

```text
用户 Q 的 A/B/C → 多次 add → 用户 Q 的记忆
测试问题 → search → 若返回“猫叫团团”和“鸡肉过敏”

answerer 模式：记忆 → 回答模型 → 答案 → judge
retrieval 模式：记忆 + 标准答案 → judge 判断信息是否足够
```

第二种模式跳过了“回答模型实际能否答对”这一环。这里的 retrieval 分数是语义充分性判断，也不同于按证据位置计算的 Recall@k。当前代码还会跳过含空内容的消息对；复现时应记录 provider、题集、cutoff、profile、回答模型和 judge。[Mem0 runner][mem0-run]

### 4.3 Zep：导入对话，检索图中的事实与实体

核验的研究 notebook 将一题的多段历史放进一个 Zep user/session，逐消息导入角色、正文与会话日期。提问时分别检索图的 edges/nodes，组合事实、有效时间与实体摘要，再让 GPT-4o-mini 回答、评分。[Zep notebook][zep-notebook]

```text
A/B/C → 同一个用户的图记忆
问题 → 检索事实与实体 → 组成上下文 → 回答 → 评分
```

这里的一个存储 session 不等于把全文始终塞进一个 LLM 上下文。它是存储组织方式；答题可见内容由图检索决定。

该 notebook 当前保留了只摄入 `single-session-assistant` 的过滤、每条消息截到 8,000 字符、搜索 query 截到 255 字符等设置，示例数据路径指向原版 S。直接执行此快照不能宣称复现完整 500 题的历史成绩；其后端版本与完整实验配置还需另行核实。[Zep notebook][zep-notebook]

## 5. 同一题为什么会得到不同结果

回到“团团”示例，下列差异都足以改变结果。这些是根据上述流程作出的分析，不是本次运行结果。

| 条件变化 | 可能改变什么 |
|---|---|
| 完整历史换成 oracle | 排除了大量干扰，也免除了寻找证据的困难 |
| 把三段会话平铺，或逐会话更新记忆 | 信息在不同阶段被选择、压缩或丢弃 |
| 每段后整理，或全部导入后整理 | 记忆处理时看到的信息范围与调用预算不同 |
| 重新生成历史 assistant 回答 | 后续系统记住的内容可能偏离原始数据 |
| 只导入 user | 无法完整覆盖 assistant 提供信息的题目 |
| 让问题参与准备记忆 | 可以针对“猫名与过敏原”预先筛选信息，改变了长期记忆任务 |
| 答题能查全部原文，或只能看压缩记忆 | 可恢复的证据范围不同 |
| 检索 top-k、时间过滤、日期处理不同 | 可能漏掉过敏信息，或误用已被更正的事实 |
| 原题换成澄清题，失败后重答取成功 | 题目或成功机会变化，不能作为同一次原题作答 |
| 只统计成功完成的题 | 准备失败、超时可能从分母消失 |

正式对比分数时，至少一并保存：**数据版本与题目 IDs、导入转换、会话/窗口映射、整理触发规则、准备阶段可见信息、答题可见信息、模型与预算、judge 与分母、失败及重试规则。** “用了同一个 benchmark”不足以证明协议一致。

官方 QA evaluator 根据题型构建 judge 提示，读取 `question_id/hypothesis`，判定最终答案是否满足要求；其中包括更新信息、时间容差、个性化和拒答规则。它的准确率与检索召回、记忆充分性分数含义不同。保存回答与 judge 配置，才能区分候选变化和评分变化。[官方评分代码][official-judge]

## 6. 对本仓 Global 评测的含义

本仓希望考察长期累积后的记忆表现，应明确区分“逻辑上持续的 Global”与“某一时刻的模型上下文窗口”。原始 session 可以作为导入边界；若采用“一段会话对应一个 window”，应记录窗口切换是否触发摘要、哪些信息跨窗口保留、是否可以回查原文。这是本仓适配协议的一部分，不是 LongMemEval 已提供的运行轨迹。

把 user/assistant 转为本仓的 `inbox` / `send_message` 形式，是对已有文本的表示转换。它不能为 benchmark 补出原本不存在的工具执行、子任务或压缩事件，也不能重新生成原始 assistant 内容后仍声称输入未变。

本仓当前采取怎样的时间回放、整理准入、冻结与冷答题规则，统一查 [suite README](README.md)；实现背景可从 [feat-677 unit](../../docs/changes/archive/feat-677-memory-evaluation/spec.md) 进入。本文不把外部厂商的设置自动转成本仓产品规则，也不据此宣称 window 适配已经实现。

## 来源与版本

下列代码链接固定到核验时 commit，便于后续确认变化。论文固定 v2；商业产品结论按论文实验日期理解。

| 来源 | 固定版本 |
|---|---|
| [LongMemEval 论文][paper] | arXiv `2410.10813v2`，2025-03-04 |
| [官方仓库说明][official-readme]、[评分实现][official-judge] | `9e0b455f4ef0e2ab8f2e582289761153549043fc` |
| [S cleaned 数据][cleaned-data] | HF revision `98d7416c24c778c2fee6e6f3006e7a073259d48f`；文件校验值见 §1 |
| [Mastra prepare][mastra-prepare]、[run][mastra-run] | `cf92428a7676fd83aa1042c6fea23ac462adce50` |
| [Mem0 memory-benchmarks][mem0-run] | `4b61c5d31b9c668a12b4f5e78064248a02c82d2b` |
| [Zep 研究 notebook][zep-notebook] | `4b7f26cc76cca20743314ba9acb8c2cb6adc42f6` |

[paper]: https://arxiv.org/html/2410.10813v2
[official-readme]: https://github.com/xiaowu0162/LongMemEval/blob/9e0b455f4ef0e2ab8f2e582289761153549043fc/README.md
[official-judge]: https://github.com/xiaowu0162/LongMemEval/blob/9e0b455f4ef0e2ab8f2e582289761153549043fc/src/evaluation/evaluate_qa.py
[cleaned-data]: https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/blob/98d7416c24c778c2fee6e6f3006e7a073259d48f/longmemeval_s_cleaned.json
[mastra-prepare]: https://github.com/mastra-ai/mastra/blob/cf92428a7676fd83aa1042c6fea23ac462adce50/explorations/longmemeval/src/commands/prepare.ts
[mastra-run]: https://github.com/mastra-ai/mastra/blob/cf92428a7676fd83aa1042c6fea23ac462adce50/explorations/longmemeval/src/commands/run.ts
[mem0-run]: https://github.com/mem0ai/memory-benchmarks/blob/4b61c5d31b9c668a12b4f5e78064248a02c82d2b/benchmarks/longmemeval/run.py
[zep-notebook]: https://github.com/getzep/zep-papers/blob/4b7f26cc76cca20743314ba9acb8c2cb6adc42f6/kg_architecture_agent_memory/zep_longmem_eval.ipynb
