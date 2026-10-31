# FrontierMemory：从旧任务经历生成记忆，再检验它能否改善执行

FrontierMemory 让一个记忆系统阅读成功和失败的旧轨迹，生成一份持久记忆，再让新的任务 Agent 带着这份记忆完成编码或知识工作。**最值得 Nano 借鉴的是“真实运行 Dreaming，再用独立任务执行检验产物”的分工；最需要守住的是两阶段的信息边界，以及任务 Agent、模型和预算的对照。** 它的成绩不能直接解释为从未见过的新任务上的泛化能力。

本文是后续 benchmark 的方法研究，承接 [feat-677 原始需求与澄清](spec.md)。其中 Nano 路径均为待讨论选项，不是已批准设计或已实现适配器；当前可运行协议仍见 [Memory suite README](../../../../evals/memory/README.md)。MemoryArena 仅是原提案中的另一备选，本文不展开。

| 记录项 | 核验基线与边界 |
|---|---|
| 核验日期 | 2026-11-01 |
| 公开主分支 | `letta-ai/frontiermemory@9af28c2f8210779f442aa36a1d73553630441af5` |
| v1.1 更新分支 | Draft PR #4，head `eb38df91dba388fe0584b2b5698c16fb6488189e`；核验时未合入主分支 |
| Nano 参照 | 本分支 `f09f44c4ecf66672b21834cc76e7a7eee4eea31c` 的 Memory suite、协议类型和候选适配入口 |
| 直接检查 | 官方网页、公开源码、公开 smoke、公开任务轨迹、匿名 Hugging Face 元数据和文件列表 |
| 没有做 | 未接受 gated 条款、申请访问或读取受限 corpus 正文；未运行模型、judge、benchmark 或生产服务；未复现任何榜单成绩 |

## 1. 数据是多种 harness 的旧轨迹，不是一份统一聊天表

v1.1 的公开 corpus card 声明：750 个文件中 256 次成功、494 次失败；每个文件是 ATIF 轨迹，或 Codex、Claude Code、OpenCode、ACP 会话日志。末尾追加一个用户消息，记录 `# Verifier result` 和 `PASS`／`FAIL`。文件使用不透明名称并打乱排列，不提供名称到任务的映射，也不提供 verifier 细节。成功／失败数量和各格式的内部字段在本次没有逐文件复核。[v1.1 corpus card][card-v11]

因此，发布数据大致有以下层次；不是每种日志都保证每个字段齐全。

| 层次 | 能看到什么 | 记忆系统需要保留什么判断 |
|---|---|---|
| 任务与交流 | 原 user 请求、assistant 回答、用户后续纠正 | 原话与角色；assistant 自称完成不等于任务成功 |
| 执行经历 | 原工具名、参数、工具返回；有的轨迹含推理文本 | 做过什么、观察到什么，以及调用与结果的关系 |
| 来源信息 | 日志格式、session／step 标识、时间或环境信息 | 按原始精度保存；没有时间时不能编出真实时间线 |
| 结果反馈 | 发布材料追加的 PASS／FAIL | 可用于判断旧尝试成败；不能凭 FAIL 唯一确定根因 |

公开仓库的 [smoke 日志][smoke-trace] 可以直接看到 Claude Code JSONL：外层有 `type/sessionId/uuid/parentUuid/timestamp/cwd/version`，内层是 `message.role/content`，assistant 正文可为内容块数组。这个 smoke 只展示一段对话；其测试任务只是写出 `hello world`，不是正式 15 题的难度样本，也不能用它推断全部 corpus 的字段覆盖率。[smoke 任务][smoke-task]、[smoke verifier][smoke-verifier]

正式案例的公开网页另展示真实 `Write` 调用、代码参数和工具返回，证明它包含可学习的执行经历，而不只是聊天事实。但网页展示层不等于下载后的原文件：完整 gated corpus 的角色分布、工具种类、上下文压缩记录、遗漏字段和时间覆盖率，仍待合法取得后统计。[Word2Vec 来源轨迹][word2vec-trace]

### 不同 harness 如何消费这些历史

**通用入口直接给记忆 Agent 一目录旧轨迹文件，由它阅读；它不需要拥有旧 Agent 的所有业务工具。** 原先调用 `Write` 或某个应用 API 的内容，是“旧时做了什么”的证据，不会因此执行一次新的写文件或外部请求。原 assistant 回复不重新生成，历史里的 system／developer 提示若存在，也不自动成为新 Agent 的活动系统指令。[记忆阶段构建代码][build-dream]、[通用整理指令][dream-instruction]

原工具和新工具可以不同。例如历史中通过某工具发现配置位置，未来 Agent 可以用自己的文件工具查同一位置；它要迁移的是方法和约束。真正执行下游任务时，任务环境要求的文件、命令或 MCP 能力仍要可用，不能因为历史无需重放就省去任务工具适配。[任务适配示例][hermes-adapter]

官方维护的接线也展示了多种转换方式：

| 记忆生成方式 | 历史如何进入 | 输出怎样给新 Agent |
|---|---|---|
| 通用 Harbor agent | `/evidence/inputs/` 挂载发布文件，收到固定整理指令 | 写入 `/memory/`；默认入口为 `MEMORY.md`。[构建代码][build-dream] |
| OpenAI Agents SDK | 每个源文件完整包成一个 SDK rollout，交给 SDK 自己的提取与整合流程 | 只导出整理后的入口、skills、rollout summaries；不导出原始 rollout 或中间 raw memories。[SDK driver][sdk] |
| Hermes `/learn` | 固定请求指向整个证据目录，真实执行原生学习 turn，保留 skill authoring | 导出新建／修改的技能，程序生成一个技能索引 `MEMORY.md`，不再另请模型总结一遍。[Hermes driver][hermes] |
| Claude Managed Agents Dreams | 把历史文件上传为 evidence memory；创建一个只回复 ACK 的 anchor session | 使用 Dreams API，导出新生成的 `/memory/` 文档；历史没有被逐回合重演为原生聊天。[Managed Agents driver][claude-dream] |

SDK 的 `updated_at` 是按文件顺序从一个固定日期递增生成的调度值，不是原经历时间。它还调整了提取并发与默认 rollout token 限制。这些说明“使用原生机制”仍包含明确的 benchmark 接线选择，不能把 adapter 当作无影响的搬运代码。[SDK driver][sdk]

对用户关心的“别人是否也需要转换”而言，答案是需要；转换目标取决于记忆入口。有的读取文件，有的接收 rollout，有的要求特定 memory store。它们未必都把历史变成自身完整前台会话。Nano 要求经过自己的真实 Dreaming 来源链路，仍然需要专门核对并实现原生历史映射。

## 2. 用一个真实失败案例走完两阶段

官方公开的 Word2Vec 来源轨迹 `build-word2vec-pipeline__2qYiRaz` 使用 Claude Code／DeepSeek V4。旧 assistant 调用 `Write` 创建 `/workspace/solution.py`，实现 `task_func`：清理文本、去停用词，然后直接训练 Word2Vec。它在最后声称实现正确；网页附带 verifier 结果却是 6 项检查中 1 项失败，空词表导致训练报错，reward 为 0。[原轨迹与网页 verifier 输出][word2vec-trace]

**这是真实公开案例，但下面的记忆内容与后续成功路径是教学推演，不是本次或官方某次 Dreaming 的实际输出。** 尤其不能把网页的详细 verifier 报告额外注入 memory agent：发布规则只允许 corpus 本身，card 明确不包含 verifier 细节。[发布材料边界][card-v11]

```text
全部发布轨迹（含这次失败，也含不相关经历）
  │  旧任务请求、assistant 的实现／解释、原工具调用与返回、FAIL
  ▼
记忆 Agent 阅读并归纳
  │  可能形成：“这个任务族的接口与文件位置是什么；
  │             文本清理后可能没有可训练词，需检查这一分支。”
  │  这只是示意；一条 FAIL 不足以直接证明根因，系统也可能归纳失败。
  ▼
冻结一份 memory/，记录内容摘要值
  │  不携带原始 evidence、旧活动上下文或旧的完整解答文件
  ▼
新的任务 Agent + 任务环境 + 同一份记忆
  │  收到简化后的 Word2Vec 需求，用自身工具重新实现与验证
  ▼
任务 verifier 检查实际产物 → reward → 严格通过／未通过
```

这道下游题要求建立可复用的 NLTK／Gensim 文本处理组件，但省略了原来的具体接口、文件约定、预处理细节和空输入行为，要求沿用从以往实现中学到的约定。公开题面给出 1,200 秒执行时间。记忆应帮助新 Agent 补回这些约束，再由新 Agent 完成代码；仅回答“我记得要处理空输入”不能代替完成任务。[Word2Vec 题面][word2vec-task]

记忆生成阶段的 verifier 仅检验文件格式、大小和入口是否合规，不评价这条经验对不对；真正的效果来自后面的任务 verifier。即使记忆目录格式全对，Agent 仍可能没读到相关文件、理解错误或执行失败。[格式检查代码][memory-check]、[严格评分代码][score]

官方通用指令还禁止把旧最终答案、提交产物、完整 patch／diff 或重建最终产物的命令直接搬进记忆。允许保存的是可复用方法、环境事实、决策规则、验证方法和失败经验。纯格式检查无法识别所有违规复制，提交还要审查轨迹。[通用整理指令][dream-instruction]、[提交审查规则][rules]

## 3. 谁生成记忆，谁执行任务，如何建立对照

memory model 是负责学习旧经历的模型；task model 是使用结果完成新一轮工作的模型。二者可以不同。一轮记忆生成只产出一份记忆，随后用于全部 15 题，不能先看某道目标题，再专门挑历史或给它生成答案导向的记忆。[规则][rules]

任务执行仍保留各 harness 的原生提示词、Agent loop 和工具。公开 adapter 把相同的文件产物送进不同记忆入口：

| 任务 harness | 启动时的记忆入口 | 对照中的注意点 |
|---|---|---|
| Codex | 放进 `$CODEX_HOME/memories/`；缺少 `memory_summary.md` 时复制 `MEMORY.md` 为入口 | 有记忆和无记忆都开启 memories 功能；使用 ephemeral 模式，避免启动同步删除外部注入的记忆。[Codex adapter][codex] |
| Claude Code | 放进实际工作目录对应的 auto-memory 路径 | 路径要随 task cwd 计算；不能只复制到固定 `-app` 目录便假定会加载。[Claude Code adapter][claude-code] |
| Hermes | notes 放入原生 memories，skills 放入原生技能目录 | 每次从 fresh home 启动；下游任务的 MCP 也由 adapter 注册。[Hermes adapter][hermes-adapter] |

这些入口不同，意味着同一记忆写法也可能有不同的可发现性和加载效果。不能把某个文件“存在于容器里”当作它被 task model 实际读到的证据；应看当次调用和轨迹。

官方至少区分以下比较：

- **无记忆对照**：同一 task agent、task model、推理强度、任务和尝试次数，省去记忆注入。它回答这份记忆给这套执行系统增加了多少帮助。[运行入口][cli]
- **不同记忆模型**：发布实验用 Letta Dream 生成、Letta Code 执行，再比较 memory model；应在固定 task model／effort 的行内比较。[发布实验][blog]
- **不同 harness**：发布实验包括 Letta Dream、OpenAI Agents SDK、Prime Agent、Hermes 和 Claude Managed Agents，并搭配各自的执行 harness。它比较整套“生成＋加载＋执行”，不能把差额全部归因于记忆整理算法。[发布实验][blog]
- **gold memory**：作者为任务构造参考记忆，检验补充信息后是否可解。这是诊断任务设计的特权材料，不能注入普通被测记忆生成过程，也不是普通候选能合法读取的 baseline 输入。[任务构造说明][blog]

公开仓库已给出第三方接入方式：实现可导入的 Harbor memory agent 类，读取规定证据，真实运行自己的学习流程并导出文件；可以复用现有 task agent，或提供原生加载与任务执行 adapter。仅提交 task agent 不满足 harness 投稿要求。[harness 接入说明][submission-guide]

**这些 adapter 是官方仓库公开的运行方法，不等于已有相应厂商独立复现报告。** 本次定向检索没有找到可核验的第三方完整运行包，足以逐项核对 corpus digest、fresh memory、全部任务和评分；因此不列“第三方已验证分数”。官网默认正式评测使用 Letta Dream／Letta Code，发布榜单和公开本地运行也不自动等价。[官网投稿说明][submit]

## 4. 冻结、隔离、预算与重复次数是协议本身

| 阶段 | 必须固定或隔离的内容 | 原因 |
|---|---|---|
| 记忆构建 | 只提供发布 corpus；不提供目标环境、目标 verifier、任务映射或额外答案；通用／原生 harness 分别使用规定指令 | 防止根据未来评分定向组织答案。[规则][rules] |
| 输出 | 顶层非空 `MEMORY.md`；仅 UTF-8 普通文件和目录；无隐藏路径、symlink 或特殊文件；总量至多 8 MiB | 固定跨 harness 交付物；文件数量和正文布局可以不同。[检查实现][memory-check] |
| 冻结后 | 给每次任务启动同一份记忆种子，记录 digest；不携带 evidence 和记忆生成会话 | 后一题不能学习前一题评测反馈；衡量冻结产物的帮助。[整理指令][dream-instruction]、[bundle][bundle] |
| 网络 | 记忆阶段只允许所用模型 API host，关闭模型服务端提供的搜索工具；安装阶段联网只用于安装 | 主机白名单拦不住 provider 代搜索，两个层面都要约束。[任务配置][dream-task]、[规则][rules] |
| 任务执行 | 禁止浏览网络找答案；保留任务原有环境与时间预算，核对实际模型请求的 effort | 不能因 harness 默认值差异改变比较条件。[接入要求][submission-guide]、[官网说明][home] |

“冻结”指固定用于所有任务的种子产物，并隔离各次任务的后续状态；不能据此声称所有原生 harness 都在操作系统层把记忆挂成只读。例如 Codex adapter 明确允许其用户写配置和记忆更新。某次任务内产生的修改不应回灌成下一次试验的起点。[Codex adapter][codex]

记忆生成预算是 6 小时，timeout multiplier 为 1.0；模板配置为 4 CPU、16 GiB 内存、20 GiB 存储。6 小时是时间限制，不是统一 token 数或统一美元预算。任务阶段则遵守各题自己的预算，不能把记忆生成的 6 小时复制给每道题。[任务配置][dream-task]、[接入要求][submission-guide]

网络限制也有实现边界：CLI 对原本受限的任务传入模型 host 许可，源码明确说这不改变本来有网络的任务。Docker 的网络隔离可能影响 DNS；Managed Agents 在供应商端运行时，API 回执也不能证明 Harbor 网络规则确实生效。正式记录应保留实际网络设置和限制缺口，不只写“禁止联网”。[CLI][cli]、[README 运行说明][readme]、[Managed Agents driver][claude-dream]

当前公开规则要求每题 **3 次尝试**。正式候选材料又要求 **3 轮独立运行**，每轮重新生成记忆并评全部 15 题；同一个记忆产物下的 3 次尝试不能充当 3 轮。按这份公开规则，一种固定任务模型／强度配置，每轮是 45 次任务执行，三轮是 135 次，另有 3 次记忆生成；无记忆对照、另一任务模型和其他强度另计。[规则][rules]

官网投稿页简写为由 Letta 运行 3 次正式评测，公开 README／rules 则还要求申请方提交 3 个完整本地运行包。二者描述层次不完全一致；这里保留公开规则的复现要求，不声称提交本地分数就能自动进入榜单。[官网投稿页][submit]、[公开提交说明][submission-guide]

## 5. 总分、失败分母和成本到底表示什么

`score.py` 读取每次任务的 `verifier_result.rewards.reward`，只有 `reward >= 1.0` 才算严格通过。部分正确的 0.83 不是一次通过；一个任务 3 次里成功 1 次，也不是“这题算通过一次就满分”的 pass@3。[评分源码][score]

```text
单轮通过率 = reward >= 1.0 的任务尝试数 / 有 reward 的任务尝试数
完整的 15 题 × 每题 3 次：分母为 45

有 reward 的超时／崩溃：保留在有效尝试中，按 reward 判定
没有 reward：单列 invalid，规则要求补跑，不能静默丢弃后报告正式完整成绩
```

评分命令会输出 `passed/valid/invalid` 和逐任务结果，本身并不把不完整运行变成完整实验。正式 bundle 还核对使用的 memory digest，并保留异常和轨迹；即使自动检查没有问题，也仍需人工检查来源与行为。[评分源码][score]、[bundle 实现][bundle]

3 道 APEX 任务使用 LLM judge，当前公开 CLI 固定为 `openai/gpt-5.6-sol`。这部分既有额外费用，也有评分波动。维护者记录的公开任务 oracle 检查也并非全部满分：例如一个 APEX oracle 为 0.83，另有参考解未满足偏好或空调用记录的情形。这里说明的是参考解与 verifier 的已知边界，不是本次发现某个模型退化。[CLI][cli]、[维护者发布检查][maintainers]

官网当前汇总分是 3 次独立运行的均值，误差为样本标准差；总榜取 Opus 5.5 与 GPT-6 Sol 两种 task model 在 max effort 下较好的结果，只有一种可用时用该结果。因此某一行“记忆模型得分”还依赖所选任务模型，不能读成该模型单独执行所有阶段的能力。[官网指标说明][home]、[v1.1 更新记录][changelog]

还有两种容易混淆的展示口径：任务详情页的 `Mean Score` 明确是跨 effort 水平的平均；它不同于总榜选 max 的规则。发布文章中的 task cost 只计算估计的任务模型成本，排除 Dreaming，并跳过缺用量的 trial；它不能用来预算完整实验，judge、容器及无法取得的费用也应另列。[任务详情页说明][word2vec-task]、[成本图注][blog]

Nano 若做内部对照，至少应同时展示有记忆／无记忆严格通过率、逐题结果、invalid／补跑次数，以及记忆生成、任务执行、judge 的分项用量。只对齐 task model 还不够：harness 版本、推理强度、工具、记忆入口、任务预算和实际所用记忆都必须相同，差值才更接近记忆带来的增益。

## 6. 它证明什么，又留下哪些问题

在边界一致的前提下，FrontierMemory 能回答：从固定的成功和失败经历里提炼出的持久文件，是否让新的 Agent 更容易完成一组依赖既往契约、偏好或环境知识的工作；它也能暴露记忆是否写得有用却找不到、读到了却没有遵循、或被过度具体的规则束缚。[任务与实验定义][readme]、[公开任务][word2vec-task]

它**不自动证明“面对完全没见过的任务也会泛化”**。官网明确说 source transcripts 覆盖下游任务，也混入不相关任务；Word2Vec 公开来源轨迹本身就使用同一任务名称和相同简化请求。某些题可能要求把经验迁移到变化的条件，但整体数据没有提供一个可直接等同“任务身份全未见”的独立测试划分。[官网输入说明][home]、[Word2Vec 来源轨迹][word2vec-trace]

它也不直接覆盖 Nano 的长期在线能力：这里先离线集中学习，再冻结执行，不能据此确认真实消息到达、Dreaming 周期、静默准入、跨角色授权、删除失效或持续任务后的增量更新。公开源任务还存在训练污染可能；没有模型训练资料或额外实验，不能排除模型预先知道任务的影响。

公开资料足以重建方法，却不足以本次验证全部运行条件。受限 corpus 未读取、完整任务环境未下载执行、官方评分包未逐 trial 重放，本文不能确认每条材料保留了哪些原始上下文，也不能给出 Nano 的预期得分。

## 7. 复现前锁版本：官网榜单与公开主分支已经不同步

截至核验日，有三组不能混用的数字。

| 来源 | 轨迹规模 | 应怎样解释 |
|---|---:|---|
| 1.0 发布文章 | 665，文中称 219 条与评测相关 | 发布文章中的实验描述，不能当作今天下载文件的计数。[发布文章][blog] |
| 当前公开主分支默认 corpus | 674 | `corpus.py` 固定 `v1.0`；匿名 Hugging Face 元数据列出 558 个 JSON、116 个 JSONL。[代码固定值][corpus-v1]、[v1.0 元数据][hf-v1] |
| 官网 v1.1 与 HF `v1.1` | 750 | 官网称 10 月 29 日已换用新 corpus 并重跑；匿名文件列表为 634 个 JSON、116 个 JSONL。公开代码更新仍在 Draft PR #4。[更新记录][changelog]、[v1.1 元数据][hf-v11]、[PR #4][pr4] |

这里的“核对文件数”只是读取公开元数据中的文件名列表，**没有读取这些文件内容，也没有重新计算 corpus digest**。v1.0 的 HF revision 是 `67250357405072066498c061f9af0eccfdac20c0`，v1.1 与当时的 `main` 均是 `5b428653fc860abd0e35b9604dc0da23ac252077`。

主分支声明的 v1.0 digest 为 `c7d31214ed20af4f14f46c4b9a838ebc9aa35a9491dfbce0fa50f7aa456eedd1`；PR #4 声明的 v1.1 digest 为 `47641d5b66bea64191f857923e587fca86e6b306fd8ff0591a2e4a0c07742fab`。它们是 `SHA256SUMS` 文件的 SHA-256，而非把轨迹条数写进名称就算锁定版本。[v1.0 校验代码][corpus-v1]、[v1.1 校验代码][corpus-v11]

v1.1 的变化也不只是多收集一些经历。维护者发现 v1.0 含构造语料时加入的偏好、阶段、筛选字段，以及带任务名称的轨迹标识；记忆系统可能直接利用这些提示。新导出器删除这类标签，并拒绝重复文件。因而，旧版本高分不能无条件当作新版本基线。[PR #4][pr4]、[标签清理实现][export-v11]

任务集则由当前 CLI 指向 Harbor Hub 的 `letta-ai/frontier-memory@v1.0`，与 corpus 版本分别固定。`tasks.json` 还区分实验内部任务和公开发布任务的 checksum；维护说明披露部分基础镜像在发布时重新固定了 digest。以后实验必须同时记 corpus、任务集、harness 和模型配置，不能只写“FrontierMemory v1”。[CLI][cli]、[任务清单][tasks]、[发布说明][maintainers]

## 8. 对 Nano 可讨论的接入路径

当前 Nano LongMemEval 适配器的输入类型只有 `user/assistant` 文本回合；它按会话时间构建同一 Global 的原生窗口，运行本系统记忆机制，封存文档记忆和聊天，再在空活动上下文中回答。答题仍允许 `conversations` 查询封存聊天。`prepare → answer → close` 的阶段分工可借鉴，但输入、任务执行和原始证据可见性不能直接照搬。[suite 协议](../../../../evals/memory/README.md)、[当前输入类型](../../../../packages/product-contracts/src/memory-evaluation.ts)、[候选执行入口](../../../../packages/dsh-integration/src/evaluation.ts)

有两条值得分别讨论的路径：

| 路径 | 如何真正测到 Nano | 能回答的问题与限制 |
|---|---|---|
| Nano 只担任 memory agent | 把获准的发布轨迹转换成 Nano Dreaming 能消费的历史；真实运行本版本 Dreaming；仅导出合规记忆，再用固定官方 task agent 做有／无记忆对照 | 更容易观察 Nano 生成的经验是否有用；还测不到 Nano 自己的记忆加载和任务执行 |
| Nano 同时担任 task agent | 同样生成记忆；每个任务在隔离 Harbor 环境里启动冷上下文 Nano，接任务所需工具与产物；仍由原 verifier 评分 | 能评生成、读取、执行的整体组合；与官方 native harness 分数的差异含执行能力，不能只归因于 Dreaming |

两条路径都有几个必须先说清楚的问题。

**原生历史怎样保真。** 历史导入需要保存 source ID、原角色、正文、调用参数、调用结果、顺序及结果标签，必要时保留可回查的原文件。不能把所有内容压成几句人工经验，也不能把工具轨迹变成模型新生成的行动。末尾 verifier 标签被包成 `user` 是数据格式，不表示 Nano 主人说过这句话或授予了权限，导入时还要保留反馈来源。本次尚未统计完整 corpus，不能承诺现有两角色 `EvaluationHistory` 能无损表达它。选 Global、专家还是任务历史作为来源，也需要核对本产品的资格和归属，不能把所有项目及用户经历冒充同一主人聊天。

**真正运行谁的 Dreaming。** 转换器负责结构与来源映射；材料选择、批次、提炼提示、记忆写入应由被测 Nano 版本决定。若只让一个临时总结 Agent 读 corpus 再写 Markdown，测到的是这段临时流程。若接官方 memory-only 路径，还须说明如何在固定 6 小时内触发产品原生整理；是否为一次离线整理，不能静默借用 LongMemEval 的自然周期回放并假装协议相同。

**时间如何解释。** corpus 文件名是随机、不透明顺序，公开 SDK 还使用合成调度时间。没有全量原始时序证据时，不能拿文件顺序生成“真实几个月的生活史”。官方先集中提供完整材料的离线学习，与用户已批准的 LongMemEval 按时间逐步可见，应该作为不同实验条件讨论。

**导出与冷启动怎样隔离。** 可以讨论在评测适配层把 Nano 正常记忆导出为 `MEMORY.md` 和可引用的 UTF-8 文档，不因此改生产布局；不能导出原始聊天库、DSH 窗口、Dreaming 工作日志、隐藏数据库或旧解答文件。冷任务中如果继续开放查询原 corpus 的 `conversations/source_history`，就突破了本 benchmark 的“只携带记忆”边界，需要另命名为内部变体。[官方整理指令][dream-instruction]

**一份记忆怎样服务 15 题。** 当前 LongMemEval 候选按题创建独立身份与准备环境，而 FrontierMemory 是一次全 corpus 学习、一个共享冻结产物、多个互不回灌的任务副本。可以复用隔离和收据思路；不宜把每一道题重新各做一次 Dreaming，否则既变了协议，也显著改变成本。

这些问题收口之后，稳定的 benchmark 层应固定数据、可见信息、任务环境、预算、重复与评分；Nano adapter 承担历史物化、真实整理、导出和恢复。以后 Dreaming 提示词或内部存储变化可以作为候选变化重新比较；如果开放旧轨迹检索、换语料版本，或改变允许的任务能力、环境和预算，就需改变实验协议，不能混算旧分数；等价工具实现的内部改动仍可归入候选变化。这里提出的是讨论边界，没有执行上述接入。

[readme]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/README.md
[rules]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/docs/rules.md
[blog]: https://frontiermemory.com/blog/v1/
[home]: https://frontiermemory.com/
[changelog]: https://frontiermemory.com/changelog/
[submit]: https://frontiermemory.com/submit/
[pr4]: https://github.com/letta-ai/frontiermemory/pull/4
[hf-v1]: https://huggingface.co/api/datasets/letta-ai/frontier-memory-corpus/revision/v1.0
[hf-v11]: https://huggingface.co/api/datasets/letta-ai/frontier-memory-corpus/revision/v1.1
[corpus-v1]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/src/frontier_memory/corpus.py
[corpus-v11]: https://github.com/letta-ai/frontiermemory/blob/eb38df91dba388fe0584b2b5698c16fb6488189e/src/frontier_memory/corpus.py
[card-v11]: https://github.com/letta-ai/frontiermemory/blob/eb38df91dba388fe0584b2b5698c16fb6488189e/release/corpus-card.md
[export-v11]: https://github.com/letta-ai/frontiermemory/blob/eb38df91dba388fe0584b2b5698c16fb6488189e/scripts/export_corpus.py
[tasks]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/tasks.json
[maintainers]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/docs/maintainers.md
[smoke-trace]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/smoke/corpus/inputs/claude-code-intro.jsonl
[smoke-task]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/smoke/task/instruction.md
[smoke-verifier]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/smoke/task/tests/test.sh
[word2vec-task]: https://www.frontiermemory.com/tasks/build-word2vec-pipeline/
[word2vec-trace]: https://www.frontiermemory.com/traces/build-word2vec-pipeline/build-word2vec-pipeline__2qYiRaz/
[build-dream]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/src/frontier_memory/dream_task/__init__.py
[dream-instruction]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/src/frontier_memory/dream_task/instruction.md
[dream-task]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/src/frontier_memory/dream_task/task.toml
[sdk]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/src/frontier_memory/sdk_dream.py
[hermes]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/src/frontier_memory/hermes_dream.py
[claude-dream]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/src/frontier_memory/claude_dream.py
[codex]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/src/frontier_memory/agents/codex.py
[claude-code]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/src/frontier_memory/agents/claude_code.py
[hermes-adapter]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/src/frontier_memory/agents/hermes.py
[cli]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/src/frontier_memory/cli.py
[memory-check]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/src/frontier_memory/memory.py
[score]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/src/frontier_memory/score.py
[bundle]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/src/frontier_memory/bundle.py
[submission-guide]: https://github.com/letta-ai/frontiermemory/blob/9af28c2f8210779f442aa36a1d73553630441af5/docs/submitting-a-harness.md
