---
status: research-in-progress
recorded-at: 2026-07-27
nano-baseline: not-recorded
source-baseline: multiple-see-source-log
current-owner: docs/development/documentation-system.md
---

# Agent 时代的代码仓知识体系研究

> 状态：Research in progress，非方法论定稿，不能作为本仓 current 规范
>
> 开始日期：2026-07-27
>
> 研究对象：面向 Coding Agent 与人类协作者、可跨代码仓复用的知识与上下文管理体系
>
> 当前方法论草案：[`../development/documentation-system.md`](../development/documentation-system.md)

## 研究问题

本研究试图回答：

> 当 Coding Agent 成为代码仓的主要参与者之一，而且每次任务只能获得有限上下文时，仓库应如何组织、
> 路由、维护和验证知识，使人和 Agent 都能以较低成本获得足够、可信、不过载的信息？

研究目标不是设计某个 Agent 产品的 instruction 文件，也不是为 nano-multiagent 单独整理一套目录。
最终产物应该是一套工具中立、可以在不同规模仓库中采用的方法论；`AGENTS.md`、skills 和本仓
`change-*` 流程都只是它的具体适配。

## 子问题

1. **知识模型**：current、proposed、decision、history、operations、research、generated 和 local
   等知识应如何区分？同一事实的权威如何确定？
2. **上下文架构**：什么应进入常驻上下文，什么应按任务发现和加载？如何兼顾可发现性与上下文成本？
3. **开发闭环**：需求、设计、实现、验证、current 文档更新和历史归档如何形成一个生命周期？
4. **可信度治理**：读者如何判断文档是否适用、仍然有效、由谁维护？哪些检查可以机械化？
5. **跨仓复用**：哪些是普适内核，哪些应根据仓库规模、风险和工具做适配？
6. **效果评估**：如何证明一套知识体系真的提高了 Agent 与人的任务成功率，而不仅是目录更整齐？

## 不研究什么

- 不把 Claude Code、Codex 或 Copilot 的配置语法当成研究主体。
- 不以“把所有文档塞进固定目录模板”为目标。
- 不把传统文档框架原样改名为“Agent 时代方法论”。
- 不先假定 nano-multiagent 当前的 spec/change 结构一定正确。
- 不用单篇厂商文章或个人经验直接推出普适结论。

## 证据分级

| 等级 | 证据 | 用法 |
|---|---|---|
| A | 团队公开的一手实践、官方工程文章、真实 Agent 仓库中的现行机制 | 支撑“有人实际采用并运行”的判断 |
| B | 实证研究，或成熟开源项目长期运行的提案、决策和治理流程 | 比较实际效果、生命周期、权威和规模化治理 |
| C | Docs-as-Code、Diátaxis、ADR、C4 等基础方法的原始资料 | 提供概念和设计工具，不自动等于 Agent 时代答案 |
| D | 社区讨论、个人复盘、案例文章 | 发现失败模式和争议，不能单独作为强结论 |
| E | 基于多项证据做出的本研究推论 | 必须显式标为“推论”，等待实践验证 |

对每个重要来源至少记录：

- 它解决的问题；
- 它实际采取的结构或机制；
- 它提供的是事实、经验还是建议；
- 适用范围与局限；
- 对通用方法论可能产生的影响。

## 暂定分析框架

对每种实践从九个维度比较：

| 维度 | 观察内容 |
|---|---|
| Artifact | 知识以哪些形式存在，各自回答什么问题 |
| Authority | 哪一处内容是 current 权威，冲突如何处理 |
| Lifecycle | 创建、评审、生效、替代、归档和删除如何发生 |
| Scope | 知识属于组织、仓库、组件、变更还是单次运行 |
| Trust | 来源、review、完整性和安全边界如何表达；它能否成为指令 |
| Enforcement | 内容是背景/建议、程序契约、确定性门禁，还是技术权限边界 |
| Retrieval | 人与 Agent 如何从入口发现任务所需信息 |
| Governance | owner、review、CI、freshness 和清理机制 |
| Feedback | 如何观测知识体系是否真的帮助完成任务 |

## 研究日志

### 2026-07-27：课题校准

最初把问题错误地收窄为“各 Coding Agent 如何加载 instruction”。用户校准后的课题是整个代码仓的
知识与上下文管理体系，并且最终要跨仓复用。后续仍会研究 Agent 的上下文约束，但只把它作为知识系统
的一个输入条件。

### 2026-07-27：第一批候选证据

以下只是候选来源，尚未完成逐项分析：

- OpenAI：[Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)
- Anthropic：[Building effective agents](https://www.anthropic.com/research/building-effective-agents)
- Diátaxis：[The Diátaxis framework](https://diataxis.fr/)
- Docs as Code：[Docs as Code](https://docs-as-co.de/)
- Backstage：[TechDocs](https://backstage.io/docs/features/techdocs/)
- Kubernetes：[Kubernetes Enhancement Proposals](https://github.com/kubernetes/enhancements/tree/master/keps)
- Rust：[The Rust RFC Book](https://rust-lang.github.io/rfcs/)
- Michael Nygard：[Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
- matklad：[ARCHITECTURE.md](https://matklad.github.io/2021/02/06/ARCHITECTURE.md.html)

### 2026-07-28：用户补充二次调研

用户提供了两份由 ChatGPT 生成的综合调研，核心主题包括 `Repository as Harness`、Agent 自主检索、
上下文的作用域/加载时机/约束强度/生命周期、验证闭环、长任务状态外部化，以及把重复纠正沉淀为
测试、脚本、skill 或长期文档。

这两份材料用于发现来源和挑战现有模型，不直接作为证据。核验后的处理原则：

- 能由官方文章、真实仓库或论文支持的事实，回到原始来源记录；
- 二次材料自己的分类和命名只作为 E 级候选推论；
- 引用不支持的产品事实不进入结论。例如其中一处把 `/goal` 描述为 Codex 长程模式，但所引链接实际是
  Claude Code best-practices 页面，不能用该引用证明 Codex 的行为；
- `Repository as Harness` 与当前 `Repository Knowledge System` 并非二选一：前者还包括工具接口、
  执行环境、验证、隔离和权限；后者是其中负责权威、记忆、上下文交付和知识演进的子系统。

二次材料提出的“作用域、加载时机、约束强度、生命周期”四维模型适合描述 context delivery，但不足以
独立治理仓库知识：它没有回答知识的主要角色、来源/权威和 owner。本研究将其分别吸收到 `Scope`、
`Delivery`、`Enforcement`、`State`，并保留 `Role`、`Authority/Provenance`、`Owner`，形成七属性模型。

本轮补充核验还发现一项 2026-07-20 提交的对照研究，直接比较强 Agent harness 的自主导航与
progressive disclosure。它被单独记录为 B9，而不是用社区经验代替效果证据。

### 2026-07-28：可搜索性与可发现性的校正

前一版综合把 Agent 的文件搜索能力看得过重，进而把索引中的文件清单描述成低价值重复。这混淆了两个不同问题：工具决定 Agent **能不能搜索**，引用和目录决定 Agent 在当前任务中**是否知道某项知识存在、为什么值得读取、读到后如何继续探索**。一个文件即使能被 `find` 或全文搜索命中，如果没有从已知入口通向它的路径，也仍可能在实际任务中不可见。

本轮因此专门补查 Agent 原生知识库，而不只研究 Coding Agent instruction。Karpathy 的 LLM Wiki、Google Cloud 的 Open Knowledge Format、OpenAI 的 agent-first 仓库和 Anthropic 的 just-in-time context 在这里形成了清晰的一致信号：常驻入口、索引、页面摘要和页面间交叉引用共同构成知识的交付图。目录清单不是需要删除的旧习惯；带链接和用途说明的目录本身就是让后续内容进入 Agent 候选上下文的基础设施。新的问题应当表述为“地图不能**止于**文件清单”，而不是“地图不应该是文件清单”。

## 来源分析

### A1. OpenAI：agent-first 仓库把知识库本身作为工程系统

来源：

- [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)

证据性质：OpenAI 团队对一个近百万行、约 1,500 个 PR、主要由 Codex 生成的真实内部代码仓所做的一手
工程复盘。文章也明确提醒，这种自治程度依赖该仓库的具体结构和工具投入，不能无条件外推。

实际实践：

- 早期尝试用一份巨大的 `AGENTS.md` 作为总手册，遇到了上下文挤占、信号稀释、快速腐化和无法机械
  校验等问题。
- 后来把约 100 行的 `AGENTS.md` 当作目录，把结构化 `docs/` 当作 repository knowledge 的
  system of record。
- 仓内区分 architecture、design docs、product specs、active/completed execution plans、
  generated references、quality、reliability 和 security 等知识内容。
- 大任务的 execution plan、progress 和 decision log 进入版本控制；小任务保留轻量计划。
- 用 CI 检查知识库的结构、交叉链接和更新状态，并运行周期性 doc-gardening agent 找陈旧文档、提交
  修复 PR。
- 架构约束不只写在文档中，还通过自定义 lint 和 structural tests 机械执行。
- 团队把 Agent 失败当作 repository environment 缺口的信号：补充工具、guardrail 或文档，使后续
  Agent 可以直接复用。

对本研究的影响：

- 强支持“知识系统 ≠ 一份 Agent instruction”“短入口 + 仓内 system of record + 按需加载”。
- 支持把 active work、completed history、generated knowledge 和 current reference 明确分开。
- 支持“重要规则应尽量变成可执行约束”，而不是单靠自然语言提醒。
- 提出一个比文档检查更强的反馈循环：从失败轨迹反向发现仓库知识和工具缺口。

局限：

- 单一团队、单一高度 Agent-first 仓库的一手经验，不是跨项目对照实验。
- 文章展示的是高投入后的体系，不能直接把完整目录复制给小仓库。

### A2. Anthropic：上下文目标是最小高信号集合，不是最大信息量

来源：

- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

证据性质：Anthropic 基于内部开发和客户实践总结的 Agent context engineering 原则，不是专门的
代码仓文档规范。

实际观察：

- 上下文越长，模型在远距离关系和精确检索上的表现会逐渐下降；更长的窗口并没有消除
  context pollution。
- 有效上下文的目标是寻找“能最大化目标结果概率的最小高信号 token 集合”。
- just-in-time context 不预装所有资料，只保留文件路径、查询和链接等轻量标识，让 Agent 在运行时
  主动检索。
- 长任务依赖 compaction、structured note-taking 等外部记忆机制；压缩时要保存架构决策、未解决问题
  和实现状态，丢弃冗余工具输出。
- 系统提示既不应把流程硬编码得过细，也不能停留在无法执行的空泛原则。

对本研究的影响：

- “可发现”与“常驻”必须分开设计；把链接和路由放进启动层，不能等同于把正文全部注入。
- 上下文预算不是按文件行数单独判断，而要看任务相关性、信号密度和遗漏后果。
- 长任务需要显式的 handoff/progress/decision state，不能只依赖对话记忆或自动 compaction。

局限：

- 主要研究运行时上下文，不直接回答哪些文档应成为 current 权威以及如何治理生命周期。

### A3. Anthropic：跨 session 工作需要持久、结构化、可验证的交接记录

来源：

- [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

证据性质：Anthropic 对跨多个 context window 完成长时间编码任务的内部实验与工程总结。

实际实践：

- 初始化 Agent 建立结构化 feature list、进度文件、启动脚本和初始 git commit。
- 后续 Agent 开始工作时读取 progress 与 git history，并先运行基本测试确认工作区实际状态。
- 每个 session 只做增量工作；结束时提交代码、更新进度。
- feature 只有经过实际验证后才能从 failing 改为 passing。
- 目标是让下一位没有前序记忆的 Agent 能快速恢复“现在做到哪里、什么是真的、下一步是什么”。

对本研究的影响：

- 变更状态必须是 durable artifact，并与 git、测试证据互相校验。
- “写了进度”不等于“状态真实”；新 session 需要从可执行验证恢复 reality。
- current knowledge system 与 active-work memory 应是两层：前者长期稳定，后者支撑尚未完成的任务交接。

局限：

- 实验主要针对从空项目构建 Web 应用；单个 `claude-progress.txt` 不一定适合多变更并行的成熟仓库。
- feature list 是特定 harness 的实现，不应直接普遍化成固定文件名。

### A4. Stripe：文档既要进入 Agent 的检索面，也要接受 Agent 任务基准验证

来源：

- [Minions: Stripe’s one-shot, end-to-end coding agents](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents)
- [Minions: Stripe’s one-shot, end-to-end coding agents—Part 2](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents-part-2)
- [Stripe Sessions 2026 developer keynote](https://stripe.com/sessions/2026/developer-keynote)

证据性质：Stripe 对内部生产级 Coding Agent 和面向外部 Agent 的开发者体验所做的一手公开说明。

实际实践：

- Minions 已经每周产出上千个合并 PR，代码由 Agent 端到端完成，但仍由人类评审。
- Agent 通过统一工具面检索内部文档、任务详情、构建状态和 code intelligence；固定的 git、lint、test
  阶段尽量由确定性程序执行。
- Stripe 发现 Agent 会依据过期训练知识生成已经淘汰的支付集成，于是建立真实集成 benchmark，再用
  benchmark 的结果反向调整文档和 Agent context。
- 面向开发者的文档提供原始 Markdown 表示，去掉网页导航等无关 token；复杂集成还提供可复制给
  LLM 的结构化 blueprint。
- 2026 keynote 报告，Agent 已约占 Stripe 文档流量的 40%，因此文档不再只有人类读者。

对本研究的影响：

- “Agent 可访问”不能只理解为把链接写进 instruction；文档要有稳定、轻量、可检索的机器表示。
- 组织方法论应把文档消费面与文档源分开：Markdown/source 是 canonical，网页或 LLM projection
  是派生视图。
- 评价知识系统应使用真实领域任务 benchmark，观察 Agent 是否选对 API、方案和验证路径。
- 确定性规则应下沉到脚本、lint、tests 和 workflow nodes；自然语言负责解释和路由，不负责重复执行
  机器可以稳定完成的判断。

局限：

- Stripe 的内部知识库和规则文件没有完整公开，不能从文章推导其全部文档分类或权威模型。
- 外部 API 文档和内部代码仓知识不是同一个问题；这里只借鉴机器可消费与 benchmark 反馈机制。

### A5. OpenAI ExecPlan：长任务需要可恢复的工作记忆，但它不等于 current 权威

来源：

- [Using `PLANS.md` for multi-hour problem solving](https://developers.openai.com/cookbook/articles/codex_exec_plans)

证据性质：OpenAI 提供的一种长时间 Coding Agent 工作方式。它是一套可采用的实践模板，不是所有仓库
都必须照搬的协议。

实际机制：

- `AGENTS.md` 只保留“什么情况下启用 ExecPlan”的短规则，完整方法放在单独的 `PLANS.md`。
- 每个 ExecPlan 是 living document，要求在执行过程中持续维护 `Progress`、
  `Surprises & Discoveries`、`Decision Log` 和 `Outcomes & Retrospective`。
- 新 session 应能够只凭工作树和 ExecPlan 恢复工作；计划需要明确路径、命令、环境假设、可观察验收、
  幂等性、失败恢复方式和关键证据。
- 计划描述用户最终能观察到什么，而不是只列出内部类或文件已经创建。
- 已经入仓的前序计划可以按路径引用；未持久化的关键上下文必须重新写进当前计划。

它暴露出的重要张力：

- ExecPlan 为了跨 session 恢复，刻意要求较强的 self-containment，甚至允许重复必要背景；而长期知识
  治理通常要求同一事实只在 canonical source 写全。
- 这两条并不真正矛盾。任务计划保存的是“在某一变更和代码基线上足以继续工作的上下文快照”，
  current 文档保存的是“现在对所有任务成立的事实”。前者必须注明来源、基线和适用范围，完成后也
  不能继续覆盖后者。
- 对稳定且已入仓的知识，优先使用带用途说明的引用；对可能在计划执行期间变化、又会影响恢复的关键
  假设，可以在计划中留下经过压缩的快照，并记录其来源。

对本研究的影响：

- active-work memory 应独立记录，不应塞进根 instruction，也不应只存在于聊天记录。
- “计划、进度、决定、发现、证据”是不同字段；只有待办清单不足以让下一位 Agent 恢复真实状态。
- 工作记忆的完成条件包括把长期有效结论归并到 current/decision/runbook，再把任务记录降级为历史。

### A6. OpenClaw：给数百份文档加检索提示，并用受限 Agent 做持续园艺

来源（固定到本次研究所检查的 commit `0dfea099d6facb4c317f82869c8d3125a3495db1`）：

- [根 `AGENTS.md`](https://github.com/openclaw/openclaw/blob/0dfea099d6facb4c317f82869c8d3125a3495db1/AGENTS.md)
- [`docs-list.js`](https://github.com/openclaw/openclaw/blob/0dfea099d6facb4c317f82869c8d3125a3495db1/scripts/docs-list.js)
- [Docs Agent prompt](https://github.com/openclaw/openclaw/blob/0dfea099d6facb4c317f82869c8d3125a3495db1/.github/codex/prompts/docs-agent.md)
- [Docs Agent workflow](https://github.com/openclaw/openclaw/blob/0dfea099d6facb4c317f82869c8d3125a3495db1/.github/workflows/docs-agent.yml)
- [Docs directory](https://github.com/openclaw/openclaw/blob/0dfea099d6facb4c317f82869c8d3125a3495db1/docs/start/docs-directory.md)

证据性质：大型、快速演进、以 Agent 为核心产品的开源仓库真实代码快照；它证明机制已经被采用，
但没有公开对照数据证明这些机制提高了多少任务成功率。

实际机制：

- 根入口要求 Agent 先运行 `pnpm docs:list`，再只读与任务匹配的资料。
- live Markdown 页面普遍使用 `summary` 与自然语言 `read_when` frontmatter。
  `docs-list.js` 把路径、摘要和读取条件生成成紧凑目录，并主动排除 `archive`、`research`。
- 本次快照中脚本列出 463 份 Markdown；445 份带 `read_when`，只有 2 份被报告缺 frontmatter。
  这说明检索 metadata 已经形成高覆盖的写作制度，而不只是少量示例。
- `docs/start/docs-directory.md` 明确区分精选的高频入口和完整 hubs，避免让新读者面对平铺的全量列表。
- 主分支 CI 成功后可以触发 Codex Docs Agent。它根据真实 commit diff 检查既有文档，只允许修改
  `docs/**`、`README.md`、`CHANGELOG.md`，禁止新增、删除、重命名或修改代码；随后再运行 docs checks。
- workflow 还检查目标 commit 是否仍是最新 main、限制执行频率，并在 main 已推进时放弃过期更新。

对本研究的影响：

- 路由表不必完全手写；“页面元数据 → 可生成目录/检索面”可以让大量文档保持可发现。
- `read_when` 比裸路径多回答了两个 Agent 真正需要的问题：为什么读、何时读。它也是
  `Blind Reference` 的一种工程化修复。
- 文档园艺 Agent 需要最小权限、明确 allowed paths、输入 commit 范围、陈旧写入保护和确定性检查；
  “定期让 Agent 自由整理整个 docs”风险过大。
- 防止文档爆炸也可以成为自动化约束。该 Docs Agent 只能校正既有页面，需要新增文档时仍回到
  人类可见的普通设计/评审流程。

### A7. Vercel：检索面可以动态选择，但必须排序、去重、限额并验证

来源：

- [Introducing the Vercel plugin for coding agents](https://vercel.com/changelog/introducing-vercel-plugin-for-coding-agents)
- [Make your documentation readable by AI agents](https://vercel.com/kb/guide/make-your-documentation-readable-by-ai-agents)
- [Chrome Lighthouse：`llms.txt`](https://developer.chrome.com/docs/lighthouse/agentic-browsing/llms-txt)

证据性质：Vercel 对其 Agent context 和文档交付能力的官方产品说明；部分内容带有产品推广性质。
Chrome 文档将 `llms.txt` 明确称为 emerging convention，并说明当前仍是可选项。

实际机制：

- Vercel 的 injection engine 根据文件 glob、命令、import 和 prompt 信号选择知识，进行优先级排序、
  去重和预算控制，而不是让所有 platform knowledge 常驻。
- 编辑后 hook 检查 deprecated pattern、sunset package 和 stale API，把一部分“别用旧知识”的要求
  变成即时验证。
- 面向站点文档，Vercel 建议把发现、干净 Markdown retrieval、结构化 freshness/canonical metadata
  和精确查询工具分层；`llms.txt`/`sitemap.md` 是索引，单页 Markdown 才是正文表示。

对本研究的影响：

- progressive disclosure 不只是一组链接，还可以是一个有 rank、dedupe、budget 和触发信号的
  retrieval policy。
- 机器友好入口应被视为 canonical source 的投影，不应成为另一份人工维护的正文。
- `llms.txt` 之类仍是新兴、可选的站点协议；仓库方法论应吸收“轻索引 + 干净正文”这个能力，
  不能把某个文件名写成普适强制标准。

### A8. 四个 Agent 项目的真实仓库：不存在由文件长度决定的单一成熟形态

来源（固定 commit 快照）：

- [OpenAI Codex `AGENTS.md`](https://github.com/openai/codex/blob/c9d52de5ca52a6b4439e7c0f69b34f6331926bb4/AGENTS.md)
- [OpenClaw `AGENTS.md`](https://github.com/openclaw/openclaw/blob/0dfea099d6facb4c317f82869c8d3125a3495db1/AGENTS.md)
- [OpenCode `AGENTS.md`](https://github.com/anomalyco/opencode/blob/014dbd34c4f5612d9a037b3641a8244b213a8a30/AGENTS.md)
- [Hermes Agent `AGENTS.md`](https://github.com/NousResearch/hermes-agent/blob/e20ff352b91623d51ae05ea586a1800aee852402/AGENTS.md)

证据性质：对四个公开 Agent 项目本地镜像的只读结构快照。它们反映真实采用方式，但不能单凭文件存在
或 star 数推出效果优劣。

| 仓库 | 根 `AGENTS.md` | 全仓 `AGENTS.md` 数 | 主要形状 |
|---|---:|---:|---|
| OpenAI Codex | 322 行 / 22.5KB | 2 | 大量 Rust/TUI/app-server 专用约束集中在根；用户文档另有外部权威 |
| OpenClaw | 189 行 / 17.4KB | 19 | 根规则 + 多模块 scoped guide + 大型带 metadata 文档库 |
| OpenCode | 103 行 / 2.6KB | 8 | 根只放少量 workflow/style/test 规则，复杂模块使用局部入口 |
| Hermes Agent | 1,399 行 / 71.9KB | 1 | 产品意图、架构、配置和开发指南大量集中在一个根文件 |

当前只能得出的结论：

- “Agent 项目都已收敛到 100 行入口”并不符合公开仓库现实。
- 根文件长度可以发现值得审计的异常，但不是独立质量指标；内容是否高频、高后果、难发现，以及它对
  真实任务的净效果更重要。
- nested guide 是 monorepo 的一种作用域机制，但其加载语义依赖 harness；通用方法论应描述
  “组件局部知识”能力，再由各工具 adapter 实现。
- Hermes 等反例值得后续做任务级对照，不能仅依据 1,399 行就宣告其工程方式失败。

### A9. Anthropic：只有能证明结果改善时，才增加 workflow 复杂度

来源：

- [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)

证据性质：Anthropic 基于内部实现与客户实践给出的通用 agentic system 设计经验，不专门讨论仓库
文档，但直接约束 workflow、tool 和 evaluation 应如何进入知识系统。

关键原则：

- 从最简单可行方案开始，只有效果提升能够被测量时才增加多步 workflow 或 autonomous agent。
- workflow 适合可预测、可分解的任务；Agent 适合无法预先确定步骤的开放任务，两者成本与可靠性不同。
- Agent 在每一步都需要从工具结果和代码执行中取得 environmental ground truth。
- prompt chain 中可以插入 programmatic gate；Coding Agent 的输出天然适合用 tests 做客观验证，
  但仍需要人类评审判断更广的系统要求。
- tool interface 需要像 HCI 一样被认真设计、记录并反复测试；防误用的参数和结构通常比追加提醒更有效。

对本研究的影响：

- 仓库不应因为“Agent 时代”就默认建立最重的 spec/reviewer/orchestrator/skill 体系。
- workflow、router、metadata 和 docs automation 都应从任务失败模式出发，并用结果决定是否升级。
- tests、schema、脚本和 runtime observation 不是文档的附属物，而是 Agent 校准工作状态的 grounding
  interface。

### A10. Agentic search 是 harness 能力，仓库路由不应变成固定检索行程

来源：

- Anthropic：[How Claude Code is used in practice](https://www.anthropic.com/research/claude-code-expertise)
- Claude Code：[Best practices](https://code.claude.com/docs/en/best-practices)
- Cursor：[Best practices for coding with agents](https://cursor.com/blog/agent-best-practices)

证据性质：前者是 Anthropic 对约 40 万个 Claude Code sessions 的观察研究；后两项是产品方对各自
Agent 的当前使用建议。它们说明现有 harness 如何分工和找上下文，不是跨产品的独立效果证明。

已核实的事实：

- Anthropic 样本中，人平均做约 70% 的 planning decisions、约 20% 的 execution decisions；典型
  session 中 Claude 做约 80% 的 execution decisions。它支持“人定义做什么，Agent 决定怎么做”
  这一观察，但不代表任何任务都应采用同样自治比例。
- Claude Code 的官方建议是先 Explore，再 Plan、Implement、Commit，并要求为 Agent 提供可执行的
  验证手段。
- Cursor 明确建议：已知精确文件时可以直接引用；否则不必手工标记所有文件，Agent 会使用 grep、
  semantic search 和分支上下文按需寻找。无关文件反而可能干扰判断。

对本研究的影响：

- Agentic search 是引用图的补充，不是替代。知识库应先通过根入口、目录索引、页面摘要和交叉引用声明“有哪些长期知识以及如何进入”；Agent 再使用搜索跳转、补漏和验证。
- 文档地图和 router 不应规定 Agent 必须按固定文件序列或固定检索算法探索仓库，但必须让受治理的重要文档从已知入口可达，并暴露适用状态、authority 和 `read-when`。
- 代码、测试、配置和 git history 的开放探索默认交给 harness 的 agentic search；文档 corpus 的基本引用覆盖不需要等到评测失败才建立。只有更深层级的 catalog、专用检索或跨仓基础设施才应由规模和任务数据触发。
- 任务入口应优先把目标、约束、完成标准和不可推断事实说清楚；不应由人预先拼接一大包“可能相关”
  文件替代 Agent 的探索。

### A11. 常驻上下文的最佳形状会随模型与 harness 演进

来源：

- Anthropic：[The new rules of context engineering for Claude 5 generation models](https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models)
- Anthropic：[Steering Claude Code: when to use CLAUDE.md, skills, hooks, and subagents](https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more)

证据性质：Anthropic 对 2026 年 Claude 5 系列和 Claude Code 的一手产品复盘。结论受到特定模型、
harness 工具集和内部 coding eval 约束，不能直接外推到旧模型或其他 Agent。

关键事实：

- Anthropic 报告为 Claude 5 高级模型删除了 Claude Code 超过 80% 的 system prompt，在其 coding
  evaluations 上没有可测量损失；原因包括旧提示过度约束、多个来源冲突，以及新模型和工具已有更好判断。
- 其当前建议从“规则和示例堆叠”转向更清晰的工具接口、渐进式披露、轻量 `CLAUDE.md` 和按需 skill；
  根文件主要保留 repo 概览和代码中无法可靠推断的 gotchas。
- 另一篇文章把根/子目录 `CLAUDE.md`、path rules、skills、hooks、subagents 等按加载时机、压缩行为、
  context cost 和用途区分，并建议根文件由 owner 维护、作为 overview/index。

对本研究的影响：

- 常驻内容不是一次设计后永久正确的配置；它必须声明适用 harness/model 范围，并接受版本升级后的删减
  和配对评测。
- “以前模型需要”不足以成为继续常驻的理由。重复提示、过窄示例和已经由工具接口表达的知识都应成为
  定期删除候选。
- 固定行数只能触发 review；真正标准仍是任务效果、冲突率、token/tool 成本和遗漏后果。

### A12. 约束强度必须与执行机制分开表达

来源：

- Anthropic：[Steering Claude Code](https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more)
- Anthropic：[Building verification loops in Claude Code with skills](https://claude.com/blog/building-verification-loops-in-claude-code-with-skills)
- Block：[3 Principles for Designing Agent Skills](https://engineering.block.xyz/blog/3-principles-for-designing-agent-skills)

证据性质：前两项是 Claude Code 产品机制和团队实践；Block 是其内部多种 Agent skills 的工程经验。
它们支持机制分工，但不证明每个仓库都应采用某个产品的 hook/skill 形式。

关键机制：

- Anthropic 明确指出，真正“绝不能发生”的行为不能只靠 `NEVER` 文本；需要 permissions 或确定性
  hook。常驻说明、按路径规则、skill、hook 和权限具有不同 context cost 与 enforcement 能力。
- verification loop 是“收集上下文 → 行动 → 运行测试/lint/自定义检查 → 修复”的重复反馈；可在本地、
  PR/CI、spec validation 或独立 grader 中运行。
- Block 把固定评分、命令和查询结构交给脚本，把诊断、解释和冲突判断留给 Agent。稳定部分追求确定性，
  情境部分保留判断空间。

对本研究的影响：

- 当前的知识属性需要新增 **Enforcement**：背景信息、行为指导、程序契约、确定性门禁、权限边界不能只靠
  文件名或“必须”措辞区分。
- 自然语言可以解释意图与后果，但不能冒充技术权限或稳定门禁；可形式化规则优先下沉到 schema、tests、
  scripts、CI、sandbox 和 credential policy。
- 这不意味着 scripts/tests 是所有 claim 的“最高权威”。它们主要约束 implementation 和
  observational claims；产品应该怎样表现仍由对应 normative authority 决定。

### A13. Skill 需要运行入口、维护契约、来源与评测分层

来源：

- Sentry：[`getsentry/skills` snapshot `e7a87fa`](https://github.com/getsentry/skills/tree/e7a87fa72645158f9b5e722cbb1c7e09266f48f1)
- [Agent Skills specification](https://github.com/agentskills/agentskills)

证据性质：公开仓库当前结构和开放格式规范，证明这些机制已被实际采用；文件存在和 star 数不证明其对
软件任务有净收益。

实际结构：

- Agent Skills 规范把 discovery metadata、激活后加载的 `SKILL.md`、执行时按需读取的
  `scripts/references/assets` 分开，形成渐进式披露。
- Sentry 把 `SKILL.md` 定位为 runtime instructions，把 `SPEC.md` 定位为维护契约，把来源清单放入
  `SOURCES.md`、长期样例放入 `references/evidence/`，并为 skill-writer 保留可重复的 `EVAL.md`。
- Sentry 还显式区分 global、domain-specific 和 repo-specific skill 的物理归属，并让
  `CLAUDE.md` 链接到 `AGENTS.md`，避免维护两套根事实。

对本研究的影响：

- “按需加载”只解决 delivery，不自动解决来源、兼容版本、owner、评测和退役问题。
- runtime 路由与 maintenance contract 可以逻辑分离；小 skill 不必机械创建所有文件，但必须具备等价的
  intent、scope、source、compatibility、evaluation 和 limitation 信息。
- skill 目录深度同样需要任务验证，不能把根上下文膨胀转移成无人能导航的 reference tree。

### A14. Compound Engineering 把纠正写回仓库，但仍需要 promotion 门槛

来源：

- Every：[`compound-engineering-plugin` snapshot `a9f6d53`](https://github.com/EveryInc/compound-engineering-plugin/tree/a9f6d530d4446d805a3100387dedd86268d7e695)
- 社区对照：[`obra/superpowers` snapshot `3dcbd5c`](https://github.com/obra/superpowers/tree/3dcbd5c4b48e02263fbf4a3c01e3fe4f81d584d9)

证据性质：两个被广泛采用的公开 workflow/skill 系统的现行机制。它们展示可运行的流程设计，但公开
仓库没有提供足以证明整套流程普遍优于轻量开发的受控结果。

实际机制：

- Every 的主循环是 brainstorm → plan → work → simplify → review → compound；`ce-compound` 把本轮
  学习写入 `docs/solutions/`，让后续 brainstorm/plan 读取。
- Superpowers 把 plan、独立任务上下文、fresh subagent、验证和分阶段 review 编成程序性 skill，并把
  “先观察无 skill 时的失败，再写最小 skill，再复测”类比为 process documentation 的 TDD。

对本研究的影响：

- “每次工作让下一次更容易”是重要目标，但一次解决方案不应自动成为 current、常驻 rule 或通用 skill。
- 需要一个显式反馈编译过程：纠正/发现先成为候选证据，再按 claim 类型路由，做重复性和任务效果验证，
  最后 promotion 或退役。
- 没有 candidate 状态、source grounding、去重和负反馈时，compound loop 会自我强化偶然经验并形成
  `learnings/solutions` 垃圾场。

### A15. LLM Wiki 与 Google Cloud OKF：索引链和交叉引用共同构成知识的发现图

来源：

- Andrej Karpathy：[LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- Google Cloud：[How the Open Knowledge Format can improve data sharing](https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing/)
- GoogleCloudPlatform：[`Open Knowledge Format v0.2` specification，snapshot `3fcbb9f`](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/3fcbb9f828c2f23d109c855ee403c3a4c81f3a96/okf/SPEC.md)
- OpenAI：[Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)
- Anthropic：[Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

证据性质：LLM Wiki 是由实践者提出并公开采用的社区模式，不是标准或对照实验；Google Cloud 在 2026 年把该模式形式化为新发布的开放格式，并提供 reference producer/consumer，但 OKF 仍很新。OpenAI 和 Anthropic 提供独立的一手工程证据，说明同一结构如何进入 Agent 运行时。

实际机制：

- LLM Wiki 把知识库定义成由 Agent 持续维护的、相互链接的 Markdown 页面集合，而不是一批等待每次查询重新拼接的原始文件。
- 根 schema/instruction 告诉 Agent Wiki 的结构和维护协议；`index.md` 列出每个页面的链接和一句话摘要。查询从 index 定位候选页面，再下钻正文；新增来源时同步更新 index、相关页面和 cross-reference。
- Wiki lint 专门寻找没有入链的 orphan page、缺失 cross-reference、冲突和陈旧内容。这里的链接不只是给人点击，也是 Agent 后续检索和维护的显式关系。
- OKF 把 `index.md` 定义为可出现在每层目录的渐进披露入口：枚举该层内容，为每个链接带上 concept description，使 Agent 在打开正文前先知道“这里有什么”。
- OKF 同时把页面间普通 Markdown 链接定义为超出目录父子关系的概念关系。Catalog/index 提供从入口向下的**可达性**，页面交叉引用提供从当前概念向相关概念继续探索的**关联性**。
- OpenAI 的真实 agent-first 仓库采用 `AGENTS.md → structured docs/indexes → deeper sources`，并在 CI 中检查 cross-links；Anthropic 的 just-in-time context 则明确把 file path、stored query 和 web link 作为运行时动态加载正文的轻量标识。

对本研究的影响：

- **可搜索不等于可发现。** 搜索工具提供能力，但 Agent 是否发起搜索、用什么词搜索、是否认为结果值得读，仍依赖当前上下文中的入口、名称、摘要和引用。
- 文件索引有独立价值。它建立“已知入口 → 文档”的第一跳，声明知识集合的边界，并让 Agent 在读取正文前得到最低成本的用途提示。真正应避免的是只有裸文件名、没有说明和状态的机械转抄，或要求把整个全量索引固定注入上下文。
- 知识图至少有两类边：`bootstrap → 顶层 index → 领域 index/page` 是路由/包含边；`page → related/current/superseding/source page` 是语义边。前者保证重要知识有入口，后者支持沿问题关系继续探索。
- 在代码仓适配中，固定进入上下文的根 instruction 应明确链接顶层文档地图；否则地图本身也可能成为没有第一跳的孤立页面。顶层地图再直接或经领域 index 覆盖长期文档，形成可检查的引用链。
- 因此仓库地图应同时承担基本 inventory 和语义路由：列出或分层覆盖有哪些知识，再补充 summary、read-when、state、authority 和 owner。后者增强前者，不能拿后者否定前者。
- 对重要长期文档，应建立一个可以从 Agent 已知入口到达的有限引用路径。它不要求所有页面都平铺在一个巨大表格里；可以用顶层地图、领域 index、局部 README、生成 catalog 或等价检索投影分层覆盖。
- 链接图应进入治理：检查断链、孤立文档、索引覆盖、重定向和被替代文档的 successor link。Agent 能批量维护 cross-reference，降低了过去人类 Wiki 最难承受的 bookkeeping 成本。

边界与局限：

- 显式 Markdown 链接不是唯一的 discovery 实现。带 metadata 的搜索索引、vector retrieval、catalog API 或知识图服务也可以把未直接互链的内容暴露给 Agent；通用不变量是“从已知 discovery surface 可达”，不是强迫所有系统手写同一种链接。
- 强 Agent 在文件名高度可预测时可以跳过 index 直接读取目标，这不意味着 index 对未知任务、陌生命名和跨领域问题没有价值。
- 链接数量不是质量指标。失效链接、错误关系和过深链路会制造新的误导，因此需要 health checks 和真实任务评测。

### B1. 关于 repository-level context file 的实证结果并不一致

来源：

- [Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?](https://arxiv.org/abs/2602.11988)
- [On the Impact of AGENTS.md Files on the Efficiency of AI Coding Agents](https://arxiv.org/abs/2601.20404)

第一项研究：

- 在 SWE-bench 及 12 个真实包含开发者 context file 的仓库、138 个 issue 组成的 CTXbench 上比较多个
  Agent/模型。
- context file 会使 Agent 更多探索、测试并遵循仓库工具，但整体成功率没有显著提高，推理成本增加
  约 20% 以上。
- 开发者维护的文件平均优于自动生成的文件；自动生成的 context file 经常只是重复已有文档。
- 当研究者移除仓库其他文档、使 context file 成为唯一文档时，自动生成 context 才显示小幅收益。
- 研究者因此建议只保留 README 中没有、而且确实必需的要求，并在采用前做严格评估。

第二项研究：

- 在 10 个仓库、124 个 PR 上比较有无 `AGENTS.md`。
- 报告有 `AGENTS.md` 时中位运行时间降低约 28.64%、输出 token 降低约 16.58%，任务完成行为相近。
- 研究重点是效率，不足以单独证明正确率、长期维护性或知识体系质量。

当前判断：

- 两项结果测量对象、任务、Agent 和指标不同，暂时不能合并成“`AGENTS.md` 有用”或“没用”的单一结论。
- 它们共同否定了一个朴素假设：增加 repository context 不会自动增加成功率。
- 方法论必须要求 task-level evaluation，并分别观测正确率、成本、检索路径、规则遵循和维护成本。
- 自动生成的大段仓库叙事尤其需要谨慎；如果它只是复述代码和既有正文，就可能成为昂贵重复。由 canonical metadata 生成的链接目录、摘要和状态投影解决的是可达性与选择问题，不能与“重新生成一份仓库百科”混为一谈。

### B2. Google：可发现性、owner、反馈入口和开发工作流决定文档能否成为 canonical

来源：

- [Software Engineering at Google：Knowledge Sharing](https://abseil.io/resources/swe-book/html/ch03.html)
- [Software Engineering at Google：Documentation](https://abseil.io/resources/swe-book/html/ch10.html)

证据性质：Google 对长期、大规模软件工程知识管理的系统复盘，早于当前 Coding Agent 浪潮。

实际实践与失败：

- 对话和邮件可以留下 paper trail，但其主要目标不是教学，难以替代正式文档。
- 文档若不可搜索、不可预测地发现，实际效果近似于不存在；Google 的 g3doc 把文档放到源码旁，并让
  ownership、review 和变更历史可见。
- 早期共享 Wiki 因无 owner、无新增流程、扁平命名空间而产生大量重复和过期页面；同一 Borg setup
  一度存在 7～10 份文档，只有少数还维护。
- canonical information 需要更高投入、显式 owner 和领域专家 vetting；不是所有局部知识都值得提升
  成组织级 canonical。
- 文档应进入现有工程工作流：有 owner、随代码评审、像 bug 一样跟踪问题、周期性评估，条件允许时
  衡量准确度和 freshness。
- landing page 的主要职责是交通指挥；如果它同时承担用户手册、团队主页和完整说明，会很快失控。
- 读者发现过期或缺失内容时，需要直接、低摩擦的反馈入口，并能找到负责响应的人。

对本研究的影响：

- “仓内”本身不保证 canonical；可预测位置、唯一入口、owner、review 和反馈闭环缺一不可。
- canonical 应按作用域分层：组织级、仓库级、组件级、本地团队级，而不是把所有事实集中到一个顶点。
- 文档治理不仅是 CI，也包含责任和激励；如果修正文档总是额外工作，自动 Agent 也只会制造更多无人
  维护的页面。
- Agent 时代继承了 Wiki 时代的重复/漂移问题，并因生成速度更快而放大。

### B3. GitLab：文档与设计方案进入同一 MR 流程，但复杂度门槛必须显式

来源：

- [Documentation testing](https://docs.gitlab.com/development/documentation/testing/)
- [Documentation workflow](https://docs.gitlab.com/development/documentation/workflow/)
- [Global navigation](https://docs.gitlab.com/development/documentation/site_architecture/global_nav/)
- [Architecture Design Workflow](https://handbook.gitlab.com/handbook/engineering/architecture/workflow/)

证据性质：大型开源产品当前运行中的公开流程和文档治理规则。

实际实践：

- 文档和代码同库，并通过 MR、lint、链接检查、redirect 检查、构建、owner metadata 等 CI 规则治理。
- 用户/API/workflow 的产品变化要求在同一 milestone 更新文档，且建议尽早进入开发流程，而不是最后
  补写。
- 顶层导航按用户 workflow 组织；月度报告寻找没有进入导航的孤儿页面，明确排除项必须写 metadata。
- 复杂、跨团队、跨 milestone 或高风险变更使用 Architecture Design Workflow；小 refactor、依赖升级、
  flaky test 等走普通轻量流程。
- design document 是 version-controlled、持续演进的主文档；讨论通过 MR 归并回同一正文，避免读者
  穿越多个 issue/thread 才能重建当前提案。
- design doc 有 `proposed / accepted / ongoing / implemented / rejected` 状态、DRI、领域专家和
  blocking authority。
- 关键 decision 可以拆成轻量 ADR；常见做法是 immutable，改变时标记 superseded 并建立新 ADR。
- 工作完成后，可以把 design doc 校正为长期知识，也可以在没有持续价值时归档。

对本研究的影响：

- 内容类型、生命周期和审查强度是三个独立维度。
- 不能对所有变化强制同等重流程；需要按影响、风险、陌生度和协调范围进行 process scaling。
- navigation coverage、ownership 和 redirects 都可以变成机器检查，不必停留在写作建议。
- “讨论记录”与“当前提案正文”应分离：讨论可以保留，但重要反馈必须回写到可直接阅读的正文。

### B4. Kubernetes 与 Rust：accepted proposal 仍不是 current behavior

来源：

- [Kubernetes Enhancement Proposal Process](https://github.com/kubernetes/enhancements/blob/master/keps/sig-architecture/0000-kep-process/README.md)
- [Kubernetes KEP index](https://github.com/kubernetes/enhancements/blob/master/keps/README.md)
- [The Rust RFC Book](https://rust-lang.github.io/rfcs/)

证据性质：两个大型开源生态长期运行的重大变更制度。

Kubernetes KEP 的机制：

- 通过标准化、版本化的文档把 feature tracking、需求和设计结合起来，目标之一是减少散落在会议、邮件和
  讨论区的 tribal knowledge。
- metadata 显式记录 `status`、owning/participating SIG、authors、reviewers、approvers、创建和更新
  日期、replaces/superseded-by。
- lifecycle 区分 `provisional / implementable / implemented / deferred / rejected / withdrawn /
  replaced`；rejected 仍作为历史保留。
- 对 process 本身也提出指标：各状态停留时间、orphaned、retired、superseded 数量等。
- 明确承认额外流程可能形成 review bottleneck，模板和工具门槛也可能排斥贡献者。

Rust RFC 的机制：

- 只有 substantial change 进入 RFC；bugfix、文档改善和不改语义的重构可走普通 PR。
- RFC 合并后只是 `active`，表示主要利益相关方原则上同意实施，不代表已经实现、已有负责人、确定优先级
  或最终一定进入产品。
- accepted RFC 实施后可能与原始设计不同；重大变化用新 RFC，并从旧 RFC 链接过去，而不是重写历史。
- 线下讨论必须摘要回 PR，长讨论在决策前先总结主要 trade-off 和分歧。

对本研究的影响：

- `accepted/implementable` 必须与 `implemented/current` 分开；这条边界对 Agent 尤其重要。
- proposal 是 decision/history 权威，不天然是产品当前行为权威。
- owner、reviewer、approver 是不同责任，不能只写一个模糊的“维护者”。
- lifecycle metadata 不只用于展示，还可以支撑检索、自动检查、仪表盘和过程评估。
- 方法论必须自带 lite 路径，并观测流程是否出现 orphan 和瓶颈。

### B5. SWD-Bench：文档质量应通过“发现、定位、完成任务”来测量

来源：

- [Evaluating Repository-level Software Documentation via Question Answering and Feature-Driven Development](https://arxiv.org/abs/2604.06793)

证据性质：2026 年预印本，提出 4,170 条 repository-level 文档评测样本，并在 57 个
SWE-bench Verified 实例上做下游 issue-solving 实验。尚不能当成业界定论，但研究问题和评测形状与
本课题高度一致。

评测设计：

- 不让一个不了解仓库的 LLM 直接按“清晰、完整、有用”给文档打印象分。
- 从真实高质量 PR 构造三个连续任务：
  `Functionality Detection → Functionality Localization → Functionality Completion`。
- 依次测量读者能否判断能力是否存在、能否定位相关文件、能否取得足够具体的信息完成实现。
- 在该实验中，给 SWE-Agent 提供检索出的文档后，issue-solving rate 相对提高 8%～20%，相关文件
  定位也提高；文档与源码结合始终优于只询问文档。
- 论文案例显示，表面流畅的文档可能被 LLM judge 同样打满分，但在跨文件细节填空中完全失败。

对本研究的影响：

- 文档体系的核心效果指标可以直接对应开发路径：
  “判断已有能力 → 找到修改点 → 正确使用接口 → 完成并验证变化”。
- 文档不是代码的替代物；高价值文档补充代码难以局部观察的全局关系、意图和定位线索。
- 不能只检查“有没有索引、链接是否有效、写得是否顺”，还要用仓库真实任务验证检索和实现效果。
- 评测必须保留任务基线、Agent/模型/工具配置和多次 trial，否则结果无法比较。

局限：

- 论文主要评估自动生成的 repository documentation，不能直接证明某一种人工目录体系最好。
- 下游实验只有 57 个 issue，报告的提升是特定 Agent、检索预算和数据集下的结果。

### B6. Instruction 与 Skill 的实证研究：按需加载也会产生漂移和负收益

来源：

- [Configuration Smells in `AGENTS.md` Files](https://arxiv.org/abs/2606.15828)
- [SkillsBench](https://arxiv.org/abs/2602.12670)
- [SWE-Skills-Bench](https://arxiv.org/abs/2603.15401)
- [From Anatomy to Smells: An Empirical Study of `SKILL.md`](https://arxiv.org/abs/2607.01456)

证据性质：全部是 2026 年的新兴实证研究或预印本，结论仍可能随 Agent、模型和数据集变化。它们的
价值主要在于否定“拆成 instruction/skill 就自然有效”的假设。

主要结果：

- 对 100 个热门开源仓库的 context file 挖掘发现，91 个至少命中一种所定义的 smell；
  `Lint Leakage` 62%、`Context Bloat` 42%、`Skill Leakage` 35%。论文还提出
  `Blind Reference`：只给路径而不说明用途和读取条件。
- SkillsBench 在 86 个跨领域任务、7,308 条 trajectory 上报告：人工精选 skill 平均提升
  16.2 个百分点，但软件工程领域只提升 4.5 个百分点，84 个任务中有 16 个出现负向变化；
  自动生成 skill 平均没有收益。
- SWE-Skills-Bench 的约 565 个软件工程任务中，49 个 skill 只有 7 个取得显著提升，3 个因版本不匹配
  和项目上下文冲突使表现下降；平均提升只有 1.2%。
- `SKILL.md` smell 研究发现其样本中的质量问题很少随演进自然消失，但作者也明确承认：单个 smell
  对实际 Agent 表现的直接因果影响仍待验证。

对本研究的影响：

- instruction、skill 和 workflow 都需要 owner、版本、适用条件、验证与退役，
  不是“把正文搬进去”后的免维护区。
- skill 应优先承载确实重复、任务特定、难由仓库直接推导的程序性知识；通用常识、lint 规则和
  已有文档正文不应再次复制。
- 路由项必须写“何时读、解决什么问题”，不能只列路径。
- 外部或跨仓 skill 必须声明兼容版本，且仓库本地事实优先；否则旧框架知识会与当前代码冲突。
- 是否保留一个 workflow/skill，应通过配对任务观察成功率、token/tool 成本和失败模式，不靠
  “看起来很完整”判断。

局限：

- 各研究的 skill 定义、任务领域和 agent harness 不同，绝对百分比不能直接横向比较。
- smell detector 包含启发式和 LLM 判断；例如固定行数阈值只适合预警，不足以证明某文件有害。

### B7. 陈旧引用可以部分机械检测，但 freshness 不能只靠日期

来源：

- [Detecting outdated code element references in software repository documentation](https://link.springer.com/article/10.1007/s10664-023-10397-6)

证据性质：2024 年发表的 repository mining 研究，不针对 Coding Agent，但直接研究仓库文档与代码演进
之间的漂移。

主要结果：

- 研究比较“文档最后更新时的代码快照”和“当前代码”，检测文档中已经不存在的 code element。
- 在可分析的 top-1000 开源仓库样本中，19.2% 的文档、28.9% 的项目至少含一个当前陈旧引用；
  Google 开源仓样本中分别为 9.7% 和 5.4%。
- 研究还沿 git history 计算引用从有效到失效的时间，并通过 issue 向维护者报告。

对本研究的影响：

- 文档与代码同库使基线关联和自动检查成为可能，但并不会自动消除漂移。
- 比“超过 90 天即过期”更有价值的信号是：文档引用的路径、符号、命令、配置字段和 API 是否仍存在。
- freshness 应由多种证据组成：最后核验基线、上游事实变化、代码引用检查、owner 确认和真实任务失败。

局限：

- exact string/reference 消失只能发现一部分陈旧问题；实现仍存在但语义改变时可能漏报，也可能因重命名
  产生误报。

### B8. 知识、指令与行动授权必须是三条不同的信任链

来源：

- GitHub：[Risks and mitigations for Copilot cloud agent](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/risks-and-mitigations)
- OpenAI：[Running Codex safely at OpenAI](https://openai.com/index/running-codex-safely/)
- [Agent Skills in the Wild: An Empirical Study of Security Vulnerabilities at Scale](https://arxiv.org/abs/2601.10338)
- [Skill-Inject: Measuring Agent Vulnerability to Skill File Attacks](https://arxiv.org/abs/2602.20156)

证据性质：前两项是平台方公开的实际威胁模型与控制；后两项是 2026 年预印本，其自动检测率与攻击
成功率只能解释为特定数据集和 harness 下的风险信号。

关键事实：

- GitHub 明确把 issue/comment 中的隐藏文本视为 prompt injection 来源，并通过触发者权限、分支限制、
  人类合并、workflow 审批、session/audit log 等机制限制后果。
- OpenAI 把 sandbox、approval、network policy、identity/credential 和 agent-native telemetry
  作为独立控制面；文本指令不能自行扩大 Agent 的技术权限。
- 大规模 skill 挖掘研究在 31,132 个样本中标记 26.1% 含值得安全审查的模式，并发现带 executable
  script 的 skill 更高风险。作者特别提醒，该比例混合恶意、疏忽与模糊模式，不等于 26.1% 都是恶意。
- Skill-Inject 在 202 个攻击任务对上观察到最高 80% attack success rate，并判断仅靠模型变强或简单
  输入过滤不足以解决问题。

对本研究的影响：

- 仓库中“可以被检索的文本”不自动成为 instruction。issue、PR comment、LLM 交互日志、外部网页、
  research snapshot 和 generated summary 都应默认视为 evidence/input，而不是行动授权。
- 根 instruction、workflow 和 skill 会直接影响 Agent 行为，需要 owner、review、变更审计和明确适用域；
  外部 skill 还应像依赖一样 pin 版本、审查脚本与权限，并支持撤销。
- “允许做什么”应由 sandbox、branch protection、CODEOWNERS、CI、credential scope 和审批策略实现，
  不应只靠 Markdown 中一句“不要做”。
- LLM 交互日志对复现和诊断非常重要，但它们同时可能包含 secret、个人信息、外部不可信内容和已过期
  上下文。知识地图应清楚路由到日志位置和检索方法，同时设置访问、留存、脱敏和引用规则，不能把整段
  日志复制进常驻上下文。

### B9. 渐进式披露补的是 context budget，不是 Agent 智力

来源：

- [Is Progressive Disclosure All You Need for Long-Context Agents?](https://arxiv.org/abs/2607.17598)

证据性质：2026-07-20 提交的 v1 预印本。研究在 InfiniteBench 长文问答上，跨三个 Agent harness、
三个模型家族，对比 raw-document navigation、多种 Agent Skills 分层和传统 hybrid retriever。它不是
代码仓开发任务，但直接检验了“让强 Agent 自主读文件”和“预建渐进式路由”的边界。

主要结果：

- 单本材料中，progressive disclosure 的收益依赖 harness：当 harness 自身导航弱时收益较大；强
  harness 已能切分和检索时，额外收益接近零。
- 跨多本材料时，raw navigation 明显退化，一层 progressive disclosure 下降更慢并取得优势。
- 第二层更深路由没有带来收益，并在部分设置中破坏准确率。

对本研究的影响：

- progressive disclosure 主要购买的是 context scalability，不是给 Agent 增加推理能力。
- 默认应让 Agent 直接搜索代码和少量清晰资料；只有 corpus、跨仓范围或实际错误定位证明需要时，才加
  一层紧凑路由。
- 多层 catalog/reference tree 不应被当作天然成熟形态。每增加一层都要证明它降低定位成本，而不是增加
  选择错误和维护漂移。

局限：

- 任务是长文问答而非软件修改，不能直接推断代码仓成功率。
- 论文仍是 v1 预印本；其“一层足够”只能作为强设计信号，仍需在 repository task eval 中复现。

### B10. LLM Wiki 实验：访问结构能改变成本和多文档任务表现，但不能用链接密度代替效果

来源：

- [Progressive Disclosure for LLM-Maintained Wiki Knowledge Bases: a Preregistered Ablation](https://arxiv.org/abs/2607.04576)
- [The Living Wiki: Schema-Driven LLM Knowledge Bases as Persistent Agent Memory](https://openreview.net/forum?id=e64EcfHp8L)

证据性质：第一项是在一个真实的 709 页、页面互相链接的 Markdown Wiki 上做的预注册消融实验，固定页面正文，只改变 Agent 到达内容的访问结构。第二项是 AgentSkills 2026 workshop poster，在 56 份 `uv` 项目资料上比较 LLM Wiki 与 hybrid RAG，并测量 Wiki 链接图的增长；其自动评分、人类复核和样本规模限制比第一项更明显。

主要结果：

- 709 页实验发现，强工具型 Agent 在页面路径容易从问题推断时会跳过约 150KB 的总 index，直接打开目标页。这说明“每次强制读完整总目录”不是渐进披露的必要条件。
- 但加入页面摘要和定向 retrieval 后，自主路由条件的回答成本仍下降约 30%–34%，强制 catalog preload 条件下降约 58%；自主路由条件下总体质量非劣，Agent 引用的页面和工具轮次更少。收益来自更有针对性的访问，而不只是省掉总 index。
- Living Wiki 在 `k=10` 时到达 ground-truth source 的比例为 90.0%，hybrid RAG 为 87.5%，但 Wiki 的总体回答分更低，瓶颈转移到长上下文中的答案综合。需要跨多份材料聚合同一实体的问题是例外，Wiki 得分 1.70，RAG 为 1.30。
- Living Wiki 的页面从 21 增至 102 时，唯一内部链接从 59 增至 656，但 unresolved wikilinks 也从 0 增至 199。它证明 Agent 可以构建越来越密的关联图，也同时暴露“生成更多链接”并不等于“知识库更健康”。

对本研究的影响：

- “Agent 有搜索工具，所以索引和摘要多余”不成立。强 Agent 的确可能绕过索引，但结构化摘要和 retrieval surface 仍能让访问更集中、成本更低。
- 反方向也不能推出“每次必须先读 index”。Index 的职责是让知识可被发现和判断，不是成为强制串行步骤；Agent 可以从根入口、局部链接、搜索或直接路径进入同一张图。
- 现有实验没有干净隔离“有无页面交叉引用”这一变量：709 页实验的各 arm 共享相同页面正文和链接，Living Wiki 也同时改变了 synthesis、index 和图结构。因此“所有 Agent 知识库必须手工互链”仍不能写成已由实验普遍证明的定律。
- 更可靠的工程结论是：重要知识必须从已知 discovery surface 可达；链接、索引摘要和搜索是互补通道。评测既要看 answer/task success，也要看首次命中正确页面的成本、orphan、broken/unresolved link 和错误引用。

### B11. Code-QA-Bench 与 SWE-Explore：文档只在补充信息和帮助定位时显示出增量

来源：

- [Code-QA-Bench: Separating Code Reasoning from Documentation Memorization in Repository-Level QA](https://arxiv.org/abs/2605.29277)
- [SWE-Explore: Benchmarking How Coding Agents Explore Repositories](https://arxiv.org/abs/2606.07297)

证据性质：两项都是 2026 年预印本。前者直接比较 `code-only` 与 `code + docs`，后者把 Coding Agent 的仓库探索单独拿出来评测。

Code-QA-Bench 的设计与结果：

- 在 10 个 Python 仓库上构造 528 个完全可由代码回答的任务和 100 个需要文档才能完整回答的任务，让四个前沿模型分别在 closed-book、code-only、documented 三种条件下作答。
- 对 code-derivable 任务，`code-only` 与 `code + docs` 的总体差异小于 0.01。代码访问相对 closed-book 带来约 0.23 的平均增益，是理解实现的主要信息源。
- 对 doc-dependent 任务，文档平均再带来 0.071 的增益。提升主要来自 design rationale、deprecation warning、edge-case caveat 等代码中缺失的信息，完整性指标的提升最大。
- 在答案本可由代码推出的任务中，`Where` 是唯一从文档获得统计显著增益的类别。论文把原因归结为 README 和 module docstring 提供了 feature location 与 dependency tracing 的导航索引。
- Gemini 在 code-derivable 任务中加入文档后反而下降 0.018；论文推测是 Agent 被引导去阅读无关 README/docs，消耗了有限探索轮次。文档的存在不自动等于有效上下文，选择和路由仍然重要。

SWE-Explore 的设计与结果：

- 评测覆盖 203 个开源仓库的 848 个 issue，要求探索器在固定代码行预算内返回相关代码区域，并比较 coverage、ranking 和 context efficiency。
- 现代 Agent 的文件级定位已经较强，行级覆盖和有效证据的排序仍是区分探索能力的关键，而且这些指标与后续 repair 结果显著相关。
- 这支持一个更窄的结论：Agentic search 很强，但在有限上下文和工具预算下仍可能找漏关键区域或把次要代码排在前面。

对本研究的影响：

- 能由代码稳定推出的实现问题，代码应是默认信息源；再写一份手工实现说明通常没有净收益。
- 文档有两个被现有证据支持的独立价值：补充代码中没有的信息，以及把分散在大仓中的实现压缩成可用的导航入口。
- 导航文档的职责是缩小搜索空间、指出入口和关系，Agent 到达目标后仍应回到代码核实。它不需要复制完整实现。
- 评测文档时应分开测量“最终答案是否正确”和“是否更快、更完整地找到正确代码”；只看最终 patch 可能掩盖探索成本与漏读风险。

局限：

- Code-QA-Bench 使用 LLM judge，任务生成从既有文档出发，并只覆盖 10 个 Python 仓库；其绝对分数不能直接外推到所有代码仓。
- SWE-Explore 研究的是代码区域检索，没有直接比较有无架构文档；它只能支持“探索仍有覆盖和排序问题”，不能单独证明应建立哪一种文档。

### C1. ADR：保存决策的上下文，不用历史文档冒充当前事实

来源：

- Michael Nygard：[Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)

证据性质：ADR 实践的经典原始文章和早期经验报告。

核心机制：

- 只记录 architecturally significant decisions，例如结构、非功能特性、依赖、接口和构建技术。
- 每份记录只处理一个 decision，包含 context、decision、status、consequences。
- 决策被推翻时保留旧记录并标记 superseded，引用新的替代记录。
- 小而模块化的文档比大型总设计更可能被阅读和更新。

对本研究的影响：

- 决策历史与 current architecture 应形成链接，但职责不同：前者解释“为什么当时这么选”，后者说明
  “现在系统是什么”。
- 是否独立建立 `adr/` 是适配选择；“决策必须有上下文、后果和替代链”才是方法论内核。
- 如果 change unit 已完整承担这些字段和不可变历史，就不必为了目录形式再复制一份 ADR。

### C2. Docs-as-Code：解决生产机制，不负责完整的信息模型

来源：

- [Docs-as-Code](https://docs-as-co.de/)
- Backstage：[TechDocs](https://backstage.io/docs/features/techdocs/)

核心机制：

- 纯文本源、版本控制、peer review、自动构建与发布。
- 文档与代码共同 branch、merge 和 version；Backstage 建议文档源与所描述组件 co-locate，并通过组件
  catalog 提供发现和 ownership。
- 生成后的 HTML/PDF/网站是派生物，source 才是应编辑和评审的入口。

对本研究的影响：

- 它为文档提供了与代码相同的变更和审计基础，是本方法论的生产底座。
- 它没有自动回答 current/proposed/history 如何划分，也不保证一份受版本控制的文档就是正确权威。
- “docs beside code”与“全仓顶层索引”并不矛盾：内容可以就近拥有，入口和 metadata 可以集中汇总。

### C3. Diátaxis：按读者需要约束内容，不能机械投影成四个顶层目录

来源：

- [The Diátaxis framework](https://diataxis.fr/)
- [Diátaxis in complex hierarchies](https://diataxis.fr/complex-hierarchies/)
- [Diátaxis as a guide to work](https://diataxis.fr/how-to-use-diataxis/)

核心机制：

- 区分 tutorial、how-to、reference、explanation 四类读者需要。
- 它是一种判断内容目的的方法，不要求物理目录只能有四个盒子；复杂项目还要考虑 topic、产品和受众
  等第二维度。
- 文档改进应从真实页面和读者问题小步推进，不应先制造一套空目录再强迫内容进入。

对本研究的影响：

- Diátaxis 更适合约束“页面在帮助读者做什么”，而不是替代 lifecycle、authority 或 repository
  artifact 分类。
- `operations/` 中仍可以同时存在 how-to、reference 和 explanation，但一篇页面不应混淆主要模式。
- 目录结构应从读者任务、领域所有权和生命周期共同推导，不从四象限机械复制。

### C4. `ARCHITECTURE.md`：提供稳定的物理地图，而不是复述所有实现

来源：

- matklad：[ARCHITECTURE.md](https://matklad.github.io/2021/02/06/ARCHITECTURE.md.html)

核心机制：

- 对中等规模仓库提供短的 bird’s-eye view、coarse-grained codemap、模块关系、边界、architectural
  invariants 和 cross-cutting concerns。
- 重点回答“做 X 去哪里”“眼前模块负责什么”；下钻实现细节另放文档或代码。
- 只记录不易频繁变化的结构，降低同步成本。

对本研究的影响：

- 目录 index 和 architecture map 解决不同问题：前者让相关资料可达并说明页面用途，后者提供无法从文件名获得的模块语义、关系和边界。Agent 两者都可能需要。
- 难以从代码中观察的负向约束、边界和不存在关系，具有比可直接搜索的类清单更高的记录价值。
- 架构地图的效果可以用“到第一次命中正确修改点的步骤/时间”评估，而不是只看是否存在该文件。

### C5. Backstage Catalog：知识源、目录图和展示面必须分离

来源：

- [Backstage Software Catalog](https://backstage.io/docs/features/software-catalog/)
- [Creating the Catalog Graph](https://backstage.io/docs/features/software-catalog/creating-the-catalog-graph/)
- [The Life of an Entity](https://backstage.io/docs/features/software-catalog/life-of-an-entity/)

核心机制：

- 组件 metadata 与代码一起存入版本控制，由组件 owner 通过正常 Git workflow 维护。
- Catalog 汇集组件、owner、lifecycle、关系、API 和外部工具入口，使数千个软件实体可以被发现。
- Backstage 明确提醒：Catalog 是聚合和展示信息的 hub/cache，不应反过来成为所有事实的最终
  source of truth；动态运行状态继续由外部运行系统拥有。
- orphan、处理错误和无效 owner 可以成为显式状态，而不是让缺失关系静默发生。
- Catalog graph 代表有用的人类心智模型，不追求复制所有动态依赖和运行时细节。

对本研究的影响：

- 大型 monorepo 或多仓组织需要一个 discovery/control plane，但正文仍可以由组件就近维护。
- 目录中的 owner、状态、路径和关系可以集中，领域事实不必集中；“统一入口”不等于“统一正文”。
- generated site、搜索索引、知识图谱和 Agent retrieval index 都应注明上游 source，并支持重建；
  对它们的直接人工编辑应被禁止或回写到源。
- owner 不能只是装饰性字符串：失效 owner 和 orphan 文档需要可检测、可分派的治理路径。

### D1. 社区实践：静态 workflow 与 instruction 必须证明自己有用

来源：

- HumanLayer：[Writing a good CLAUDE.md](https://www.humanlayer.dev/blog/writing-a-good-claude-md)
- Armin Ronacher：[Agentic Coding Recommendations](https://lucumr.pocoo.org/2025/6/12/agentic-coding/)
- Armin Ronacher：[Agentic Coding Things That Didn’t Work](https://lucumr.pocoo.org/2025/7/30/things-that-didnt-work/)
- Thorsten Ball：[How I use Amp](https://ampcode.com/notes/how-i-use-amp)

证据性质：有较多实际使用经验的从业者个人复盘；只能作为案例和反例，不能视为行业标准。

共同信号：

- HumanLayer 主张 root instruction 只放普适信息，通过自描述文件名和链接做 progressive disclosure，
  并把格式、lint 等可确定规则交给工具；同时承认很多建议尚未严格验证。
- Armin Ronacher 删除了许多没有形成使用习惯的 slash commands；他观察到静态 context 自动化经常取
  太多或太少，要求一种自动化只有在重复任务上做过多次并对比结果后才保留。
- Thorsten Ball 倾向短 session，把 architecture、陷阱、相关代码、测试和 trade-off 作为当前任务的
  定向 context；也把 git commit/history 当成高价值的历史知识载体。
- 社区经验反复指向：快速、低噪声的工具反馈，通常比把同一规则再写成一段自然语言更可靠。

对本研究的影响：

- progressive disclosure 不能只有目录设计，还要验证 Agent 是否真的找到、选择并读取了正确资料。
- workflow/skill 也会腐化，应该有使用数据、成功率/方差观察和删除机制。
- git history 是有价值的取证层，但缺少索引和语义状态，不能单独充当 current knowledge system。

## 专题：什么值得写成长期文档，什么应由代码表达

这个问题的判断单位不应是文件类型，而应是某一项知识是否值得再建立一份自然语言表示。单独写文档会增加一种表达能力，也会增加一个需要与代码同步的地方。

可以把取舍写成一个简单关系：

> 文档的净价值 = 代码中没有的信息 + 节省的仓库探索成本 − 同步成本 − 过期后的误导成本

Martin Fowler 在 [Code As Documentation](https://martinfowler.com/bliki/CodeAsDocumentation.html) 中把代码视为系统最详细、最精确的主要说明，同时强调代码仍需要补充文档。Google 的工程文档实践给出了更具体的分工：有意义的命名、类型和代码结构负责表达局部事实；reference 尽量从源码注释单源生成；README 负责告诉读者目录用途和首先应该看哪里；design document 保存目标、方案和 trade-off。[Google Documentation Best Practices](https://google.github.io/styleguide/docguide/best_practices.html) [Software Engineering at Google：Documentation](https://abseil.io/resources/swe-book/html/ch10.html)

### Code as documentation 适合表达什么

以下信息通常应让代码、类型、schema、测试或生成结果直接承担：

- 某个函数、类和字段现在叫什么，参数和返回值是什么；
- 当前调用顺序、分支逻辑、数据结构和错误处理怎样实现；
- 一个局部模块内部有哪些文件和私有对象；
- 依赖版本、配置默认值、API 字段等可以从唯一机器源生成的清单；
- 只有实现改变时才会跟着改变、又能通过搜索和调用链可靠得到的细节。

这些信息变化频繁，而且代码可以被编译、执行、测试和精确搜索。再维护一份手写说明，主要增加同步责任。Google 的实践也指出，当 Code Search 能直接找到原始定义时，单独维护同一份 reference 的收益很低；需要面向读者的视图时，应尽量从源码定义或 docstring 生成。

Code-QA-Bench 为这个边界提供了直接证据：在 528 个答案完全可由代码推出的仓库问题上，四个前沿模型使用 `code-only` 与 `code + docs` 的总体差异小于 0.01。代码访问本身是主要增益来源，额外文档没有普遍改善这些问题。[Code-QA-Bench](https://arxiv.org/abs/2605.29277)

### 长期文档需要创造什么额外价值

一份长期文档至少应创造下面两类价值之一。

第一类是补充代码中没有的信息：

- 产品目标、行为契约和非目标；
- 选择当前方案的原因、trade-off 和被放弃的替代方案；
- 外部约束、领域概念、安全假设和已接受风险；
- 以“不允许发生什么”表达的架构不变量；
- 部署、恢复和排障中来自真实运行环境的知识；
- 某项历史决定在什么上下文中成立，以及何时需要重新评估。

代码只能说明当前实现，无法独自裁决“系统应该怎样”。因此 current spec 有长期价值；它保存行为和边界，而不是逐段复述当前类与调用过程。设计思想、决定理由和替代方案也无法从最终代码可靠还原，适合进入架构说明、ADR 或历史 design。

第二类是压缩大仓库的探索路径。一个功能可能横跨入口、领域逻辑、存储、协议、后台任务和测试。Agentic search 可以逐步还原这些关系，但探索受上下文、工具轮次和搜索词影响，可能命中同名旧实现、只找到主路径、遗漏异步消费者，或者在多个可疑入口之间选择错误。

高价值的导航文档会回答：

- 系统由哪些主要领域和组件构成；
- 每个组件负责什么，边界在哪里；
- “要修改 X”通常从哪个目录、模块或稳定符号开始；
- 一个跨模块能力经过哪些关键边界；
- 哪些相似实现是 current，哪些已经 deprecated；
- 还应沿哪些 spec、runbook、test 或历史决定继续探索。

matklad 对 `ARCHITECTURE.md` 的建议正是这种 codemap：回答“做 X 的东西在哪里”“眼前这个模块负责什么”，明确边界和难以从代码观察的负向不变量，同时把模块内部细节留给 inline documentation 和代码。[ARCHITECTURE.md](https://matklad.github.io/2021/02/06/ARCHITECTURE.md.html)

Agent 时代的实证结果也支持这种导航价值。Code-QA-Bench 中，即使答案最终完全可由代码推出，`Where` 仍是唯一从文档取得统计显著增益的类别，README 和 module docstring 帮助了 feature location 与 dependency tracing。SWE-Explore 对 203 个仓库、848 个 issue 的评测则显示，现代 Agent 的文件级定位已经较强，行级覆盖、证据排序和上下文效率仍会显著影响后续修复。[SWE-Explore](https://arxiv.org/abs/2606.07297)

### 导航文档怎样避免成为第二份实现真相

导航文档应比代码高一个抽象层级：

| 文档负责 | 代码负责 |
|---|---|
| 领域、组件、职责和边界 | 精确目录与文件内容 |
| 功能的主要入口和稳定符号 | 完整调用链与分支 |
| 跨模块关系和需要继续检查的方向 | 当前依赖和具体数据流 |
| 架构不变量及其原因 | 实现这些约束的机制 |
| current / deprecated / successor 路由 | 每个版本的具体实现差异 |

文档可以列出关键目录、模块和符号，因为它的价值正在于帮助定位；它不需要把这些对象的内部实现再讲一遍。可从代码机械得到的依赖图、API 表和 schema reference 应生成，并记录来源 commit。人工维护的部分集中在代码不能生成的职责解释、边界含义、检索入口和风险提示。

OpenAI 的 agent-first 实践采用的也是“map, not manual”：架构文档提供领域和 package layering 的顶层地图，Agent 沿地图进入代码，再用代码和测试核实最终事实。文档与代码的关系是导航与落地，不是两份并列实现说明。[OpenAI Harness Engineering](https://openai.com/index/harness-engineering/)

### 一个可执行的判断顺序

准备写一份长期文档时，依次问：

1. 这里是否包含代码无法可靠表达的信息？如果包含，写入对应的 spec、architecture、ADR 或 runbook。
2. 如果信息最终存在于代码中，Agent 是否需要跨大量文件和调用链才能找到，而且真实任务中容易找错或找漏？如果是，写一份高层地图，指向代码入口。
3. 这份内容能否从 code、schema、config 或 test 自动生成？如果可以，保留机器源，按需生成阅读视图。
4. 文档是否会随着每次局部实现调整而同步改写？如果会，它的抽象层级通常太低，应把细节还给代码。
5. 删除这份文档后，未来 Agent 是会失去代码中不存在的关键知识，还是只需要多做一次可靠搜索？只有前一种，或搜索成本与漏读风险已经被真实任务证明较高时，才值得承担长期维护成本。

因此，`design 实施后留下什么`只是这个原则的一个应用：实现细节回到代码；目标、理由、边界、不变量和确有价值的功能地图继续保留。

### 证据边界

Code-QA-Bench 和 SWE-Explore 都是新预印本，前者还使用 LLM judge，并只覆盖有限的 Python 仓库。它们不足以给出适用于所有项目的固定文档清单，但已经能支持一个比“文档越多越好”或“代码足够自解释”更窄、更可检验的结论：代码是实现事实的默认来源；文档需要用不可推导的信息或可测量的导航收益证明自己的存在价值。

## 跨来源张力

研究不能把来源中顺耳的部分简单相加。当前至少存在五组需要在方法论中显式化解的张力：

| 张力 | 证据两端 | 当前解释 |
|---|---|---|
| Canonical vs self-contained | Google/Backstage 强调唯一权威；OpenAI ExecPlan 要求单计划可恢复 | 长期事实只保留一个权威；active task 可以保存带来源、基线和适用范围的恢复快照 |
| 短入口 vs 真实复杂度 | OpenAI/Anthropic 主张最小高信号；真实开源仓的 root instruction 从 103 到 1,399 行不等 | 行数只是预警；应按 task-level 净收益、常驻必要性和可检索性决定 |
| 人工文档 vs generated knowledge | Google 强调专家 vetting；Stripe/SWD-Bench 展示机器表示和自动文档价值 | 生成物适合作为 projection、索引和候选修订；除非声明为 schema-first authority，否则不能无审核取代源 |
| 文档表示 vs code as documentation | Fowler、Google 与 Code-QA-Bench 都显示代码是可推导实现事实的主要来源；OpenAI、matklad、Code-QA-Bench 与 SWE-Explore 又显示大仓仍需要意图和导航 | 文档必须提供代码中没有的信息，或把分散代码压缩成可验证的探索地图；其余实现细节留在 code/schema/test，阅读视图优先从机器源生成 |
| reusable skill vs local context | SkillsBench 显示精选 skill 可提升；SWE-Skills-Bench 显示多数无益且版本冲突会降级 | skill 是带适用域和版本的可执行程序知识，必须选择、验证和退役，不能当通用真理包 |
| Agent 自主搜索 vs 显式引用图 | Cursor 鼓励 Agent 按需检索；LLM Wiki/OKF 用 index、摘要和 cross-link 建立可达性；实验显示强 Agent 有时会跳过 index | 显式入口声明知识存在和关系，搜索负责跳转、补漏和验证；不强制固定阅读行程，更深检索基础设施再由规模和任务失败触发 |
| 自然语言约束 vs 确定性控制 | 文档解释意图；Anthropic/Block 把不可违背规则下沉到 hook、script、CI、permissions | 每个约束声明 enforcement level；文字不能冒充门禁或授权 |
| 知识复利 vs 经验垃圾场 | Compound Engineering 持续沉淀 solution；Google/wiki 和 skill 研究显示无 owner 内容会腐化 | 新发现先作为候选证据，经分类、去重、验证和 promotion 后才成为长期知识 |

这使本研究逐渐从“文档目录设计”转向一个更完整的问题：

> 如何让仓库中的事实、工作记忆、历史证据和执行知识各有权威与生命周期，再通过一个可预算、可观测、
> 可机械约束的检索与反馈平面，把当前任务需要的最小可信集合交给人或 Agent？

## 阶段性综合 v0.1（E 级推论）

以下内容是基于上述证据形成的研究推论，还不是本仓 current 规范。

### 1. Repository Knowledge System 是 Repository Harness 的一个子系统

代码仓作为 Coding Agent 的长期 Harness，至少还包括可操作的代码/环境、工具接口、验证反馈、隔离和
权限。Repository Knowledge System 负责其中的权威、工作记忆、证据、历史和上下文交付，不能独自替代
一个可运行、可观察、可验证的工程环境。

知识系统至少包含五个逻辑平面；这些是职责，不要求对应五个物理目录：

| 平面 | 回答的问题 | 常见内容 |
|---|---|---|
| Truth | 现在应该是什么、实际由什么定义 | 产品原则、架构、current contract、code/config/schema、development policy、runbook |
| Work | 准备改变什么、当前做到哪里 | issue/spec、design、execution plan、progress、decision log、delta |
| Evidence | 凭什么相信、刚才实际发生了什么 | tests、CI、runtime state、LLM trace/log、acceptance evidence、benchmark |
| Memory | 为什么这样决定、过去发生过什么 | ADR、completed change、incident/retro、research snapshot、git/PR history |
| Control | 去哪里找、如何执行、谁负责、什么被允许 | router/index/catalog、metadata、workflow/skill、CODEOWNERS、CI policy、permissions |

关键边界：

- Control 负责路由和约束，不能偷偷成为产品/架构事实的唯一存储。
- Evidence 证明或反驳 Truth，但一段日志不是规范；Truth 与 Evidence 冲突时要登记为实现缺陷或文档漂移。
- Work 面描述未来和过程，只有完成验证并 promotion 后才改变 Truth。
- Memory 保留上下文和取证价值，不自动恢复为 current。

### 2. 每类知识都要能回答七个属性，而不是只靠目录名

1. **Role**：它属于上面哪个主要平面，回答什么问题？
2. **Scope**：组织、仓库、组件、变更、环境还是单次运行？
3. **State**：draft、proposed、accepted、active、implemented、current、superseded、archived 中的哪一种？
4. **Authority/Provenance**：人工 source、schema/code source、generated projection、observed evidence、
   imported snapshot 中的哪一种？上游是什么？
5. **Owner**：谁有责任评审、校正和退役？
6. **Delivery**：常驻、路由后读取、按查询检索、任务胶囊，还是由源生成的 projection？
7. **Enforcement**：它只是背景/建议、Agent 程序契约、确定性门禁，还是技术权限边界？

这些属性可以由目录、frontmatter、catalog metadata、CODEOWNERS 或索引表表达，不应把一种 YAML 格式
变成方法论本身。

### 3. “单一事实来源”需要改写成 claim-scoped authority

“代码永远是真相”“spec 永远最高”都过于粗糙。一个 claim 至少包含：

```text
(scope, subject, claim kind, time)
```

其中 `claim kind` 要区分：

- **normative**：系统应该怎样表现；
- **implementation**：构建和运行由什么定义；
- **observational**：某次运行实际发生了什么；
- **historical**：为什么在当时做出某个决定。

每种 claim 只应有一个 declared authority。不同 kind 的内容互相校验而不是互相冒充。发生冲突时：

1. 先确认问题问的是“应该”“实现”“观察”还是“历史”；
2. 读取相应 authority 和 supporting evidence；
3. 把差异登记为 bug、doc drift 或未完成 change；
4. 修复并重新建立一致性，而不是靠一条全局优先级静默选边。

### 4. Agent context 是知识系统的 delivery path，不是知识源

推荐的交付层级：

```text
Resident bootstrap
→ repository map/index
→ domain index or semantic cross-link
→ selected current sources + code
→ active-work recovery capsule
→ evidence on demand
```

- **Resident bootstrap**：项目身份、最高后果红线、顶层知识地图入口，以及何时进入特殊流程。
- **Repository map/index**：让受治理的长期知识全部直接或分层可达；至少提供路径和 summary，必要时再提供 read-when、state、authority 和 owner，不复制正文。
- **Domain index / semantic cross-link**：领域 index 继续枚举局部内容；页面间链接表达相关、依赖、来源、替代等关系，让 Agent 能沿当前问题继续探索。
- **Selected sources**：只读当前任务相关的架构、contract、runbook、代码和 schema。
- **Recovery capsule**：为长任务冻结足够的背景、进度、决定、发现和恢复方法；必须记录基线。
- **Evidence on demand**：测试、运行状态、LLM 日志、历史 PR 和研究材料，按问题取证，不默认常驻。

这条链描述的是可发现性和逐步披露，不是要求 Agent 每次按固定顺序读取。强 harness 可以在路径明显时直接跳到目标，也可以搜索代码、测试、配置和 history；但重要长期文档不应把“Agent 或许会搜到”作为唯一入口。它们应从 Resident bootstrap 已知的地图出发，经有限层引用或等价 catalog/retrieval advertisement 可达。

因此，“文件清单”和“语义路由”不是二选一：链接清单先声明知识集合及其用途，state、authority、read-when 等语义帮助 Agent 正确选择和解释。默认保持顶层地图加局部入口的一层紧凑结构；只有仓库任务评测证明 corpus 规模仍导致定位失败时，才增加更深层级或专用检索。

外部网站的 clean Markdown、`llms.txt`、MCP、搜索索引和 generated architecture map 都是 delivery
projection。它们应能追溯和重建，不能与源并列人工维护。

### 5. 通用 lifecycle 是 promotion，不是文件搬家

```text
Current truth
→ proposed delta
→ accepted/active work
→ implementation + evidence
→ promote verified delta
→ new current truth
→ freeze rationale/evidence as memory
```

核心事件是 promotion：

- 把验证后的行为与架构变化写入 current；
- 把 design 中已经由代码、类型、schema 和测试精确表达的实现细节退出 current 文档；
- 把操作发现写入 runbook；
- 把确实重复且经验证的程序提炼成 workflow/skill；
- 把 design 中仍有长期价值的决策理由、约束、trade-off 和完成证据冻结成 history；
- 删除 active 路由，避免旧计划继续被当作工作入口。

目录从 `active/` 移到 `archive/` 只是这一语义事件的一个实现动作。

### 6. 反馈闭环要把纠正编译成仓库能力

```text
运行失败 / 人类纠正 / 新发现
→ candidate evidence
→ 判断 claim、scope、重复性与风险
→ 选择 doc / test / script / skill / runbook / task state / 不保留
→ 建立调整前后的基线或验证案例
→ promotion、缩小适用域或退役
```

- 一次修复只证明“这次发生过”，不自动证明值得进入长期规则。
- 可确定判断的问题优先进入 tests、lint、scripts、CI 或权限；需要解释和权衡的部分留给文档与 Agent。
- 多步骤程序只有在重复、非显然且任务验证有净收益时才提炼为 skill。
- 对当前任务有用但不具备复用价值的信息留在 recovery capsule，完成后冻结或删除。
- 聊天记录和 LLM 日志是证据，不是跨 session 工作状态的唯一载体。

### 7. 治理需要同时覆盖结构、语义、权限和效果

| 层次 | 可检查内容 |
|---|---|
| Structure | 从已知入口的可达性、index 覆盖、links、orphan、broken/unresolved link、metadata、owner、redirect、active/archive 冲突 |
| Grounding | 路径/符号/命令/配置字段存在，schema/generated drift，示例可运行 |
| Lifecycle | accepted 未伪装 implemented，superseded chain 完整，change 完成时 current 已 promotion |
| Security | secret、外部 skill provenance/版本/权限、日志访问与脱敏、Agent allowed paths |
| Effect | 真实任务成功率、检索正确率、首次正确定位成本、token/tool 成本、人工返工 |

自动 Docs Agent 适合修复范围窄、事实可由 diff grounding 的问题；新增权威、改变语义或删除历史仍应走
显式评审。

### 8. 评测单位应该是仓库任务，不是页面

建立一个小而稳定的 repository knowledge eval set，至少覆盖：

- 新成员/Agent 判断能力是否已存在；
- 在任务没有给出文件名时，从根入口发现正确文档，并能说明为什么要读；
- 为一个 feature/bug 定位正确组件和文件；
- 选择 current 而不是 proposed/superseded 资料；
- 按 runbook 启动或诊断系统；
- 完成长任务后正确 promotion 和归档；
- 面对冲突文档、过期 skill 或不可信日志时不被误导。

同一 commit、环境、Agent/模型和资源预算下，对“原体系 / 新体系”做配对多次 trial。组合使用：

- deterministic outcome：tests、state、diff scope、link/metadata checks；
- trajectory metrics：读了哪些源、何时命中正确位置、tool calls、tokens、错误 authority 次数；
- human review：设计合理性、遗漏、过度工程和高风险判断。

单独看页面长度、文档数量、LLM 印象分或一次成功案例，都不足以证明体系有效。

### 9. 通用方法只规定能力，仓库 profile 决定形状

| Profile | 适用信号 | 最小能力 |
|---|---|---|
| Compact | 单组件、低风险、少量维护者，定位成本仍低 | 短 bootstrap、README、开发/验证入口、必要的 architecture/runbook、轻量 change history |
| Structured | 多组件、长任务、Agent 经常改代码 | docs map、claim authority、current/change 分离、active work memory、owner、docs checks、task eval |
| Federated | monorepo/多仓、多团队、高风险或生产自治 | 全局 catalog + 组件局部知识、正式 proposal 状态、generated projections、权限/审计、受限 gardening、持续 eval |

升级 profile 应由真实痛点触发，例如错误定位、重复文档、owner 缺失、并行 change 冲突、长任务频繁失忆
或 Agent 已成为主要贡献者；不按 LOC 或文件数机械创建空目录。

## 待验证假设

这些是假设，不是结论：

1. Agent 时代没有推翻 Docs-as-Code、ADR、RFC 等传统实践，而是放大了它们对明确权威、结构化状态和
   自动治理的要求。
2. 仓库需要的是“短入口 + 可导航知识图”，而不是一份覆盖所有内容的总手册。
3. 文档类型和文档生命周期是两个独立维度；只按 `guide/reference` 分类或只按
   `active/archive` 分类都不够。
4. proposed 与 current 的明确隔离，是防止 Agent 用未来设计解释当前代码的关键机制。
5. Agent 可执行的 workflow/skill 属于知识体系，但不应成为架构、行为和历史事实的唯一存储位置。
6. 文档质量最终应通过真实任务的检索与完成效果来评估，而不只是链接检查、文件长度或目录覆盖率。
7. 强 Coding Agent 默认能够自主搜索仓库，但搜索不能替代知识的显式可达性；结构化路由首先让 Agent 知道有哪些知识、各自用途和关系，在大 corpus 中进一步控制 context，同时不替 Agent 设计固定检索流程。
8. 人类纠正只有经过候选、分类、验证和 promotion，才可能成为可复用仓库能力；直接追加到根文件会造成
   经验污染。

## 尚未形成结论的争议

- 是否应该普遍设立 ADR，还是让变更单元的 design/history 承担决策记录。
- current spec 应更接近代码、测试，还是集中在独立的产品/组件契约层。
- 小仓库是否需要显式生命周期目录，还是可以只用状态元数据。
- 文档 owner 应使用 CODEOWNERS、页面元数据、组件 catalog，还是由代码归属隐式继承。
- generated 文档在什么情况下可以成为权威，如何避免生成结果与源定义形成双重事实。
- 应如何衡量“Agent 找到了正确上下文”，以及怎样构造可重复的仓库知识评测。
- 一次纠正、第二次重复和统计上稳定的失败分别应达到什么 promotion 门槛。
- repository task 中“一层渐进披露足够”的适用边界，以及何时值得引入跨仓搜索或专用 retriever。
