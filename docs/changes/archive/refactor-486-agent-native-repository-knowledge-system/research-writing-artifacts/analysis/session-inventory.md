# Agent-Native 文档体系：会话谱系与语料边界

取证时间：2026-07-31  
扫描范围：`/Users/czj/.codex/sessions/2026/07/27/` 至 `2026/07/31/`，并补充同一研究链上的 ChatGPT conversations  
时间口径：下文均为 Asia/Shanghai；JSONL 内部顶层时间戳为 UTC。  
本文件只确定会话边界，不替代后续的用户原话摘录与主题分析。

## 结论

应纳入后续用户原话分析的历史 session 有 9 个，分成 core 与 supporting 两层。

Core 有 5 个：

1. ChatGPT 研究起点 `6a680399-a0b4-83ec-83a8-1f3f4d31f05f`
2. Codex 核心主干 `019fa2f5-2fc5-76e0-890c-8ccc657b4935`
3. Codex 文章精修 fork `019fabca-a1a0-7641-b3c3-4a721673459d`
4. Codex 仓库改造复核 fork `019fb322-eca1-71e2-a2fb-cc316a057f04`
5. Codex 收尾复核 fork `019fb3f3-a316-7a91-8d39-e4176a6f1a25`

Supporting 有 4 个：

1. ChatGPT Better Harness 机制研究 `6a68bc9e-2194-83ec-bdd8-6cdcceba47f1`
2. ChatGPT 技术插图研究 `6a6aa430-148c-83ec-940e-98dd0a1d7f39`
3. ChatGPT ADR / PRD / SPEC 边界研究 `6a6aaeda-46bc-83ec-aa16-d3521485f49c`
4. Codex Better Harness 实跑 `019fabd3-8476-7bb1-bfb5-d3d490f72629`

9 个 session 共 **254 条真实用户输入**：

- Core：235 条
  - ChatGPT 研究起点：5
  - Codex 核心主干：152
  - Codex 文章精修 fork：6
  - Codex 仓库改造复核 fork：49
  - Codex 收尾复核 fork：23
- Supporting：19 条
  - ChatGPT Better Harness：11
  - ChatGPT 技术插图：1
  - ChatGPT ADR / PRD / SPEC：5
  - Codex Better Harness 实跑：2

其中 5 个 Codex session 按 response item id 对 fork 继承历史去重后共有 **232 条分支新增的真实用户输入**：

- 核心主干：152
- 文章精修 fork：6
- Better Harness 实跑：2
- 仓库改造复核 fork：49
- 收尾复核 fork：23

`019fa31a` 是独立的 reviewer 生命周期改造；`019fb1ab-*` 是核心主干派出的审计 subagent；`019fb404` 是仓库复核分支派出的实现 subagent。三者都不应被误当成用户在 Agent-Native 文档体系项目里的新增对话分支。

## 取证和计数规则

1. 真实用户输入指 `response_item.payload.role == "user"` 中由用户实际发出的内容。
2. 不计入：
   - `recommended_plugins`
   - `AGENTS.md`、环境、权限、skills catalog 等自动注入
   - `<skill>...</skill>` 的自动展开
   - subagent 派发任务、follow-up 和父代理消息
3. 同一 response item id 在 fork JSONL 中会被完整复制。fork 的“新增输入数”按子会话 id 集减去即时父会话 id 集计算。
4. CLI 会话 `019fabd3` 的两条用户 message 没有稳定的 `payload.id`，按顶层时间戳和出现顺序计数。
5. 桌面用户 fork 的首个 `session_meta.parent_thread_id` 可能为空。此时以 JSONL 内嵌的历史 `session_meta` 链和重复的 response item id 判定父子关系。
6. subagent JSONL 即使含 `role=user`，其新增内容也是父代理派发包，不是用户本人输入，因此“真实用户输入数”为 0。
7. ChatGPT conversation 没有落入本地 Codex JSONL；其用户回合数来自 ChatGPT 原会话逐回合核验。不能拿 conversation id 当作 Codex fork id，也不能据此虚构 parent。
8. ChatGPT 与 Codex 之间只有“研究结果作为附件带入”的内容交接，不是产品层的父子 thread 关系。

## 已确认的谱系

```text
6a680399  ChatGPT 独立会话：核心研究起点（5）
└── 研究结果作为附件进入 019fa2f5（内容交接，不是 thread fork）

019fa2f5  用户主干（152）
├── 019fabca  用户 fork：文章精修（6；继承 44）
├── 019fb322  用户 fork：仓库改造逐项复核（49；继承 127）
│   ├── 019fb3f3  用户 fork：剩余 drift 与 PR 收尾（23；继承 166）
│   ├── 019fb3c1  subagent：corrected delta 冷测（0）
│   ├── 019fb3e3  subagent：简化版 corrected delta 冷测（0）
│   └── 019fb404  subagent：D-014 实现（0）
├── 019fb1ab-*  subagent：证据、记忆、治理审计（均为 0）
├── 019fb21b-* 等  subagent：冷启动文档可用性测试（均为 0）
└── 019fb3fe  subagent：final sync gate 冷测（0）

019fabd3  独立 CLI 用户会话：实际运行 Better Harness（2）
└── 019fabde-*  subagent：三路证据复核（均为 0）

6a68bc9e  ChatGPT 独立支持会话：Better Harness 机制研究（11）
6a6aa430  ChatGPT 独立支持会话：技术插图标准（1）
6a6aaeda  ChatGPT 独立支持会话：ADR / PRD / SPEC 边界（5）
```

这里的“继承 N”只表示 fork 时复制进去的真实用户 message 数。父会话在 fork 后仍可能继续，因此不要求等于父会话最终总数。

## 纳入的 ChatGPT 直接用户 session

ChatGPT conversations 不存在于 `/Users/czj/.codex/sessions/`，因此“JSONL”栏明确记为无，而不是伪造本地路径。可用定位是 ChatGPT conversation id / URL。日期只保留到当前已核验的粒度；没有本地事件流时不推断精确到秒的时间。

### C1. 核心研究起点：《代码仓文档管理体系》

- Conversation：`6a680399-a0b4-83ec-83a8-1f3f4d31f05f`
- URL：`https://chatgpt.com/c/6a680399-a0b4-83ec-83a8-1f3f4d31f05f`
- 父 conversation：无可核验 parent；独立 ChatGPT conversation
- 时间：2026-07-27 至 07-28，当前工作区只保留日期级记录
- 本地 Codex JSONL：无
- 真实用户输入：**5 回合**
- 用户回合边界：
  1. 发起代码仓文档管理体系的深度研究。
  2. 纠正研究方向：先理解 Coding Agent 通过 agentic search 探索和修改仓库的真实开发范式，再讨论文档体系。
  3. 确认纠正后的方向并要求继续深挖社区最佳实践。
  4. 追问 LLM Wiki 对 Agent-Native 代码仓文档体系是否有启发。
  5. 追问哪些内容不应进入代码仓，以及哪些知识即使在仓库中也不应文档化。
- 阶段与产物：形成第一轮研究判断；其结果后来以附件形式进入 Codex `019fa2f5`，成为后续研究和文章的候选材料。
- 纳入层级：**Core**。
- 纳入理由：它把问题从传统“文档怎么分类”校准到“Agent 如何消费仓库知识、哪些信息值得文档化”，是可识别的研究起点。它与 Codex 主干是内容交接关系，不是 fork。

### S1. 《Better Harness 项目解析》

- Conversation：`6a68bc9e-2194-83ec-bdd8-6cdcceba47f1`
- URL：`https://chatgpt.com/c/6a68bc9e-2194-83ec-bdd8-6cdcceba47f1`
- 父 conversation：无可核验 parent；独立 ChatGPT conversation
- 时间：2026-07-28，日期级记录
- 本地 Codex JSONL：无
- 真实用户输入：**11 回合**
- 阶段与产物：
  - 从“项目做什么”持续追问到 skill 的触发时机、运行时机制和实际读取对象。
  - 要求回到具体代码和文档，说明 Episode 怎么划分、完整分析对象长什么样，并给出实例。
  - 质疑 Agent 1 的产出信息量不足，要求补足证据与机制。
- 纳入层级：**Supporting**。
- 纳入理由：它不是文章或仓库迁移主干，但高度集中体现用户“研究项目不能停在概括，必须追到代码、运行时对象、完整输入和证据上限”的研究方式。

### S2. 《GPT Image 2 插图提示》

- Conversation：`6a6aa430-148c-83ec-940e-98dd0a1d7f39`
- URL：`https://chatgpt.com/c/6a6aa430-148c-83ec-940e-98dd0a1d7f39`
- 父 conversation：无可核验 parent；独立 ChatGPT conversation
- 时间：2026-07-30，日期级记录
- 本地 Codex JSONL：无
- 真实用户输入：**1 回合**
- 阶段与产物：要求研究能生成“放在 paper 中真正有价值的技术插图”的提示方式，重点是论证信息量，而不是装饰性。
- 纳入层级：**Supporting**。
- 纳入理由：支撑作图价值标准；具体的图片迭代、比例纠正和“图必须压缩复杂论证”仍以 Codex 主干原话为主。

### S3. 《ADR 在软件工程中》

- Conversation：`6a6aaeda-46bc-83ec-aa16-d3521485f49c`
- URL：`https://chatgpt.com/c/6a6aaeda-46bc-83ec-aa16-d3521485f49c`
- 父 conversation：无可核验 parent；独立 ChatGPT conversation
- 时间：2026-07-30，日期级记录
- 本地 Codex JSONL：无
- 真实用户输入：**5 回合**
- 阶段与产物：讨论 ADR、PRD、SPEC 的职责差异，并追问本仓 unit 首文档还缺少什么必要信息。
- 纳入层级：**Supporting**。
- 纳入理由：支撑“知识角色不能混写”和“不同文档承担不同问题”的分析；它不是本次文章正文或仓库迁移的执行主干。

## 纳入的 Codex 直接用户 session

### 1. 核心主干

- Session：`019fa2f5-2fc5-76e0-890c-8ccc657b4935`
- 父 session：无
- `thread_source`：`user`
- 时间：2026-07-27 17:43 至 2026-07-31 01:43
- JSONL：`/Users/czj/.codex/sessions/2026/07/27/rollout-2026-07-27T17-43-25-019fa2f5-2fc5-76e0-890c-8ccc657b4935.jsonl`
- 分支新增真实用户输入：**152**
- 阶段与产物：
  - 从 `AGENTS.md` 过长切入，扩大为全仓文档体系审计。
  - 先做权威、入口、运维文档等初步整理，并创建早期 PR #213。
  - 重新对齐研究课题为“Coding Agent 时代可跨仓复用的知识与上下文管理体系”。
  - 进行外部研究、二手材料核验、Better Harness 源码学习、文章大纲和正文反复重写、排版与作图。
  - 回到 nano-multiagent，在隔离 worktree 内按 Agent-Native 方法重构文档体系，逐步 commit，并建立 drift review。
- 纳入理由：这是研究、文章写作和仓库重构三段工作的共同主干，用户绝大多数方法论纠正都在这里。

### 2. 文章精修 fork

- Session：`019fabca-a1a0-7641-b3c3-4a721673459d`
- 即时父 session：`019fa2f5-2fc5-76e0-890c-8ccc657b4935`
- `thread_source`：`user`
- 时间：2026-07-29 10:53 至 12:21
- JSONL：`/Users/czj/.codex/sessions/2026/07/29/rollout-2026-07-29T10-53-31-019fabca-a1a0-7641-b3c3-4a721673459d.jsonl`
- fork 证据：
  - 首个 metadata 没写 `parent_thread_id`。
  - JSONL 内嵌 metadata 链为 `019fabca → 019fa2f5`。
  - 50 条真实用户 message 中，44 条与父会话 id 相同，**6 条为本分支新增**。
- 分支新增真实用户输入：**6**
- 阶段与产物：
  - 安装并验证 Better Harness 插件。
  - 精修文章 WHY 的因果链。
  - 明确两项 context-file 研究只适合支撑 HOW 中的根级指令设计。
  - 删除没有真实错误前提的“不是……而是……”式虚假对照。
  - 直接修改 Obsidian 文章 `Agent-Native 代码仓文档体系.md`。
- 纳入理由：6 条新增输入都是研究工具落地或高价值文章纠正，不能只靠主干历史替代。

### 3. Better Harness 实跑

- Session：`019fabd3-8476-7bb1-bfb5-d3d490f72629`
- 父 session：无，独立 CLI 会话
- `thread_source`：`user`
- `source`：`cli`
- 时间：2026-07-29 11:03 至 11:29
- JSONL：`/Users/czj/.codex/sessions/2026/07/29/rollout-2026-07-29T11-03-13-019fabd3-8476-7bb1-bfb5-d3d490f72629.jsonl`
- 分支新增真实用户输入：**2**
  - `$better-harness review this project's AI coding workflow and generate a report`
  - `html报告用中文`
- 阶段与产物：
  - 实际运行 Better Harness 的 Codex / project / customization 三路审查。
  - 生成并验证中文 HTML 报告：`/Users/czj/Repos/nano-multiagent/.codex/better-harness/review-2026-07-29/report.html`。
- 纳入理由：它不是 fork，但它是 Better Harness 研究由源码理解转为真实项目验证的直接用户 session；适合作为支撑证据，不应与长篇写作纠正等量解读。

### 4. 仓库改造复核 fork

- Session：`019fb322-eca1-71e2-a2fb-cc316a057f04`
- 即时父 session：`019fa2f5-2fc5-76e0-890c-8ccc657b4935`
- `thread_source`：`user`
- 时间：2026-07-30 21:07 至 2026-07-31 01:49
- JSONL：`/Users/czj/.codex/sessions/2026/07/30/rollout-2026-07-30T21-07-18-019fb322-eca1-71e2-a2fb-cc316a057f04.jsonl`
- fork 证据：
  - 首个 metadata 没写 `parent_thread_id`。
  - JSONL 内嵌 metadata 链为 `019fb322 → 019fa2f5`。
  - 176 条真实用户 message 中，127 条与父会话 id 相同，**49 条为本分支新增**。
- 分支新增真实用户输入：**49**
- 阶段与产物：
  - 用户逐项复核重构后的 coding guideline、skill 引用、E2E 清单、research 索引、current spec、历史材料和 drift 记录。
  - 集中暴露“无增量信息却维护手工索引”“文档声称的机械保护超过真实测试”“把 skill 行为约束写到普通指南”“为聪明 Agent 设计过度状态机/哈希契约”等问题。
  - 将外部并行完成的简化 change workflow 集成回文档体系，并拆分提交与 issue。
- 纳入理由：这是“Agent-Native 文档体系落地时容易犯什么错”的最密集用户纠正语料。

### 5. 收尾复核 fork

- Session：`019fb3f3-a316-7a91-8d39-e4176a6f1a25`
- 即时父 session：`019fb322-eca1-71e2-a2fb-cc316a057f04`
- 祖先 session：`019fa2f5-2fc5-76e0-890c-8ccc657b4935`
- `thread_source`：`user`
- 时间：2026-07-31 00:55 至 02:01
- JSONL：`/Users/czj/.codex/sessions/2026/07/31/rollout-2026-07-31T00-55-16-019fb3f3-a316-7a91-8d39-e4176a6f1a25.jsonl`
- fork 证据：
  - 首个 metadata 没写 `parent_thread_id`。
  - JSONL 内嵌 metadata 链为 `019fb3f3 → 019fb322 → 019fa2f5`。
  - 189 条真实用户 message 中，166 条与即时父会话 id 相同，**23 条为本分支新增**。
- 分支新增真实用户输入：**23**
- 阶段与产物：
  - 继续处理 Testing 指南、code-review 记忆、延期 issue、PR 前问题清零等剩余 drift。
  - 完成 contract tests、方法论转正、临时 drift 队列删除、refactor-486 归档。
  - push `codex/docs-knowledge-system-rebuild`，创建 Draft PR #221，并按用户要求保留 worktree。
- 纳入理由：仓库改造的最终可交付性、验收和收尾边界都在此分支形成。

## 相关 subagent：保留为执行证据，不纳入用户原话

以下 session 与项目相关，但 `thread_source == "subagent"`。它们的新增 `role=user` 内容是父代理派发包，不是用户本人输入，故真实用户输入统一为 **0**。

### Better Harness 的三路复核

| Session | 父 session | 时间 | JSONL | 阶段/产物 | 处理 |
|---|---|---:|---|---|---|
| `019fabde-5dc4-70f1-b5d8-9a4ced5ce6e4` | `019fabd3-8476-7bb1-bfb5-d3d490f72629` | 2026-07-29 11:15 | `/Users/czj/.codex/sessions/2026/07/29/rollout-2026-07-29T11-15-04-019fabde-5dc4-70f1-b5d8-9a4ced5ce6e4.jsonl` | `/root/session_evidence`，会话证据审查 | 支撑报告；用户原话排除 |
| `019fabde-7680-7223-bc2a-de50c3ba90c8` | `019fabd3-8476-7bb1-bfb5-d3d490f72629` | 2026-07-29 11:15 | `/Users/czj/.codex/sessions/2026/07/29/rollout-2026-07-29T11-15-11-019fabde-7680-7223-bc2a-de50c3ba90c8.jsonl` | `/root/project_harness`，项目 harness 审查 | 支撑报告；用户原话排除 |
| `019fabde-8ddc-7c13-9acb-807bfb1dfde4` | `019fabd3-8476-7bb1-bfb5-d3d490f72629` | 2026-07-29 11:15 | `/Users/czj/.codex/sessions/2026/07/29/rollout-2026-07-29T11-15-17-019fabde-8ddc-7c13-9acb-807bfb1dfde4.jsonl` | `/root/agent_customize`，Agent 定制面审查 | 支撑报告；用户原话排除 |

### 核心主干的审计与冷启动验证

| Session | 父 session | 时间 | JSONL | 阶段/产物 | 处理 |
|---|---|---:|---|---|---|
| `019fb1ab-409e-7462-ae88-e0f2119f4f4a` | `019fa2f5-2fc5-76e0-890c-8ccc657b4935` | 2026-07-30 14:16 | `/Users/czj/.codex/sessions/2026/07/30/rollout-2026-07-30T14-16-58-019fb1ab-409e-7462-ae88-e0f2119f4f4a.jsonl` | `/root/evidence_audit` | 支撑 drift 审计；用户原话排除 |
| `019fb1ab-673f-7071-b8b9-44f53b888022` | `019fa2f5-2fc5-76e0-890c-8ccc657b4935` | 2026-07-30 14:17 | `/Users/czj/.codex/sessions/2026/07/30/rollout-2026-07-30T14-17-08-019fb1ab-673f-7071-b8b9-44f53b888022.jsonl` | `/root/memory_audit` | 支撑 drift 审计；用户原话排除 |
| `019fb1ab-c544-79d3-8a57-6093f6b8724c` | `019fa2f5-2fc5-76e0-890c-8ccc657b4935` | 2026-07-30 14:17 | `/Users/czj/.codex/sessions/2026/07/30/rollout-2026-07-30T14-17-32-019fb1ab-c544-79d3-8a57-6093f6b8724c.jsonl` | `/root/governance_audit` | 支撑 drift 审计；用户原话排除 |
| `019fb21b-83ae-7160-87d6-6663842657ac` | `019fa2f5-2fc5-76e0-890c-8ccc657b4935` | 2026-07-30 16:19 | `/Users/czj/.codex/sessions/2026/07/30/rollout-2026-07-30T16-19-35-019fb21b-83ae-7160-87d6-6663842657ac.jsonl` | `/root/cold_architecture` | 冷启动可发现性验证；用户原话排除 |
| `019fb21b-c66d-7351-9639-8189ae1beab9` | `019fa2f5-2fc5-76e0-890c-8ccc657b4935` | 2026-07-30 16:19 | `/Users/czj/.codex/sessions/2026/07/30/rollout-2026-07-30T16-19-52-019fb21b-c66d-7351-9639-8189ae1beab9.jsonl` | `/root/cold_im_change` | 冷启动 change 路由验证；用户原话排除 |
| `019fb21f-21d5-7d81-b458-71c8c7c7068e` | `019fa2f5-2fc5-76e0-890c-8ccc657b4935` | 2026-07-30 16:23 | `/Users/czj/.codex/sessions/2026/07/30/rollout-2026-07-30T16-23-32-019fb21f-21d5-7d81-b458-71c8c7c7068e.jsonl` | `/root/cold_runtime` | 冷启动运行文档验证；用户原话排除 |
| `019fb229-6d82-7752-909d-18c5d8060d8a` | `019fa2f5-2fc5-76e0-890c-8ccc657b4935` | 2026-07-30 16:34 | `/Users/czj/.codex/sessions/2026/07/30/rollout-2026-07-30T16-34-47-019fb229-6d82-7752-909d-18c5d8060d8a.jsonl` | `/root/cold_llm_diagnosis` | 冷启动 LLM 排障验证；用户原话排除 |
| `019fb229-c221-7f30-8936-d9866cb4cb60` | `019fa2f5-2fc5-76e0-890c-8ccc657b4935` | 2026-07-30 16:35 | `/Users/czj/.codex/sessions/2026/07/30/rollout-2026-07-30T16-35-09-019fb229-c221-7f30-8936-d9866cb4cb60.jsonl` | `/root/cold_active_recovery` | 冷启动活动单元恢复验证；用户原话排除 |
| `019fb22a-0c60-7493-83af-a6d729285073` | `019fa2f5-2fc5-76e0-890c-8ccc657b4935` | 2026-07-30 16:35 | `/Users/czj/.codex/sessions/2026/07/30/rollout-2026-07-30T16-35-28-019fb22a-0c60-7493-83af-a6d729285073.jsonl` | `/root/cold_history_decision` | 冷启动历史决策验证；用户原话排除 |
| `019fb230-3658-7443-b88c-48aece12bc69` | `019fa2f5-2fc5-76e0-890c-8ccc657b4935` | 2026-07-30 16:42 | `/Users/czj/.codex/sessions/2026/07/30/rollout-2026-07-30T16-42-12-019fb230-3658-7443-b88c-48aece12bc69.jsonl` | `/root/cold_change_closure` | 冷启动 change 收尾验证；用户原话排除 |
| `019fb23d-636f-7f70-ae72-f0cb673efbc9` | `019fa2f5-2fc5-76e0-890c-8ccc657b4935` | 2026-07-30 16:56 | `/Users/czj/.codex/sessions/2026/07/30/rollout-2026-07-30T16-56-35-019fb23d-636f-7f70-ae72-f0cb673efbc9.jsonl` | `/root/cold_im_change_blind` | 无提示冷启动 change 路由验证；用户原话排除 |
| `019fb3fe-b9f5-7b00-96bd-e9bd88662afb` | `019fa2f5-2fc5-76e0-890c-8ccc657b4935` | 2026-07-31 01:07 | `/Users/czj/.codex/sessions/2026/07/31/rollout-2026-07-31T01-07-23-019fb3fe-b9f5-7b00-96bd-e9bd88662afb.jsonl` | `/root/forward_test_sync_gate` | final-sync gate 冷测；用户原话排除 |

### 仓库复核分支的执行 subagent

| Session | 父 session | 时间 | JSONL | 阶段/产物 | 处理 |
|---|---|---:|---|---|---|
| `019fb3c1-0d1d-74d3-a260-150ea6b66c1e` | `019fb322-eca1-71e2-a2fb-cc316a057f04` | 2026-07-31 00:00 | `/Users/czj/.codex/sessions/2026/07/31/rollout-2026-07-31T00-00-01-019fb3c1-0d1d-74d3-a260-150ea6b66c1e.jsonl` | `/root/delta_reconciliation_cold_test` | corrected delta 冷测；用户原话排除 |
| `019fb3e3-fb61-7821-a601-cd4072392a1d` | `019fb322-eca1-71e2-a2fb-cc316a057f04` | 2026-07-31 00:38 | `/Users/czj/.codex/sessions/2026/07/31/rollout-2026-07-31T00-38-10-019fb3e3-fb61-7821-a601-cd4072392a1d.jsonl` | `/root/delta_reconciliation_simplified_test` | 简化版 corrected delta 冷测；用户原话排除 |
| `019fb404-5d72-76b3-8e25-0e7f528b9403` | `019fb322-eca1-71e2-a2fb-cc316a057f04` | 2026-07-31 01:13 | `/Users/czj/.codex/sessions/2026/07/31/rollout-2026-07-31T01-13-32-019fb404-5d72-76b3-8e25-0e7f528b9403.jsonl` | `/root/fix_d014_legacy_contract_terms`，修正旧 contract 术语 | 实现支撑；用户原话排除 |

## 排除的 ChatGPT 直接用户 session

| Conversation | 父 conversation | 时间 | 来源 | 真实用户输入 | 阶段/产物 | 排除理由 |
|---|---|---:|---|---:|---|---|
| `6a6704e8-a6fc-83ec-9bb7-c9b18626d4f3`《浏览器渲染MD文档》 | 无可核验 parent | 2026-07-27 | `https://chatgpt.com/c/6a6704e8-a6fc-83ec-9bb7-c9b18626d4f3`；无本地 JSONL | 未统计 | Markdown / Mermaid 浏览器渲染工具 | 只解决渲染手段，不包含研究判断、文章逻辑或信息型作图标准 |
| `6a641c7a-b610-83ec-a563-c619275d4314`《研究方向概述》 | 无可核验 parent | 2026-07-25 | `https://chatgpt.com/c/6a641c7a-b610-83ec-a563-c619275d4314`；无本地 JSONL | 未统计 | 翻译另一篇多 Agent 论文段落 | 更早且研究对象不同 |
| `6a57410e-1530-83ec-8b78-2f88b2941680`《Agent任务边界分析》 | 无可核验 parent | 2026-07-15 | `https://chatgpt.com/c/6a57410e-1530-83ec-8b78-2f88b2941680`；无本地 JSONL | 未统计 | 长程 Agent 系统与任务边界研究 | 能体现更一般的研究偏好，但不属于这次 Agent-Native 文档体系工作 |

“未统计”是明确的证据边界：这三条会话已凭主题足以排除，但当前取证包没有逐回合导出，不能编造精确用户回合数。若未来要提炼跨课题通用研究人格，应另建语料范围再核验。

## 排除的 Codex 直接用户 session

这些 session 的 `thread_source` 确实是 `user`，但目标不是本次 Agent-Native 文档研究、文章写作或仓库知识体系重构。

| Session | 父 session | 时间 | JSONL | 分支新增真实用户输入 | 阶段/产物 | 排除理由 |
|---|---|---:|---|---:|---|---|
| `019fa0f2-f6d2-7900-b708-38564e6cf72c` | 无 | 2026-07-27 08:21 | `/Users/czj/.codex/sessions/2026/07/27/rollout-2026-07-27T08-21-45-019fa0f2-f6d2-7900-b708-38564e6cf72c.jsonl` | 1 | 拉代码、构建前端、启动 IM/Gateway | 服务运维任务 |
| `019fa1b1-1516-7f21-a6dc-c99462be0d49` | 无 | 2026-07-27 11:49 | `/Users/czj/.codex/sessions/2026/07/27/rollout-2026-07-27T11-49-24-019fa1b1-1516-7f21-a6dc-c99462be0d49.jsonl` | 6 | feat-484 消息交互设计与 design review | 产品功能任务；只被别的流程优化会话当案例引用 |
| `019fa31a-b237-7321-a6b6-85944a6a0ca3` | 无 | 2026-07-27 18:24 | `/Users/czj/.codex/sessions/2026/07/27/rollout-2026-07-27T18-24-23-019fa31a-b237-7321-a6b6-85944a6a0ca3.jsonl` | 15 | reviewer 复用、分轮记录、PR #214 | 邻近的 change-* 生命周期改造；没有内嵌父 metadata，与 `019fa2f5` 的真实用户 message id 交集为 0 |
| `019fa763-de87-7a53-bbc1-3053811f000f` | 无 | 2026-07-28 14:22 | `/Users/czj/.codex/sessions/2026/07/28/rollout-2026-07-28T14-22-47-019fa763-de87-7a53-bbc1-3053811f000f.jsonl` | 2 | 清理 Playwright Chrome 残留 | 本机清理任务 |
| `019fb1d6-18d7-7160-acdd-34749ec39296` | 无 | 2026-07-30 15:03 | `/Users/czj/.codex/sessions/2026/07/30/rollout-2026-07-30T15-03-46-019fb1d6-18d7-7160-acdd-34749ec39296.jsonl` | 1 | 诊断 Codex GPT-5.6 上下文窗口 | Codex 产品诊断 |
| `019fb211-1cca-7241-ad89-be8f66854f29` | 无 | 2026-07-30 16:08 | `/Users/czj/.codex/sessions/2026/07/30/rollout-2026-07-30T16-08-13-019fb211-1cca-7241-ad89-be8f66854f29.jsonl` | 19 | 新建简化版 change orchestrator（feat-487） | 邻近且后来被文档分支集成，但原任务是流程实现/对比，不是 Agent-Native 文档研究或整理；`<skill>` 自动展开已从数量中扣除 |
| `019fb3b8-713d-7e93-aee4-a3b8e21d3742` | 无 | 2026-07-30 23:50 | `/Users/czj/.codex/sessions/2026/07/30/rollout-2026-07-30T23-50-37-019fb3b8-713d-7e93-aee4-a3b8e21d3742.jsonl` | 1 | 复核 feat-484 修复说明 | 产品功能验收 |
| `019fb409-6578-72d0-a876-0488d33cfed3` | 无 | 2026-07-31 01:19 | `/Users/czj/.codex/sessions/2026/07/31/rollout-2026-07-31T01-19-02-019fb409-6578-72d0-a876-0488d33cfed3.jsonl` | 2 | feat-484 是否可提 PR、调用 orchestrator 收尾 | 产品功能交付 |
| `019fb42c-c753-71d3-a253-f87a43781085` | 无 | 2026-07-31 01:57 | `/Users/czj/.codex/sessions/2026/07/31/rollout-2026-07-31T01-57-41-019fb42c-c753-71d3-a253-f87a43781085.jsonl` | 2 | 当前 `/goal` 复盘任务 | 这是取证请求本身，不是被复盘的历史证据 |

## 特别核验

### `019fa31a`

它是 `thread_source=user` 的独立根会话，目标是让 design reviewer 跨轮复用并改进 review 记录。它与文档体系项目时间接近，也体现用户偏好“减少过度机制、保留可复盘历史”，但没有会话继承关系，产物是 reviewer 生命周期和 PR #214。结论：**从本次主语料排除；若以后提炼通用 Agent 协作偏好，可另行引用。**

### `019fb1ab-*`

三条 metadata 都明确写有：

- `thread_source=subagent`
- `parent_thread_id=019fa2f5-2fc5-76e0-890c-8ccc657b4935`
- agent path 分别为 `/root/evidence_audit`、`/root/memory_audit`、`/root/governance_audit`

结论：**它们是核心主干派出的并行审计，不是用户 fork；真实用户输入为 0。**

### `019fb404`

metadata 明确写有：

- `thread_source=subagent`
- `parent_thread_id=019fb322-eca1-71e2-a2fb-cc316a057f04`
- agent path `/root/fix_d014_legacy_contract_terms`

其 JSONL 内嵌链为 `019fb404 → 019fb322 → 019fa2f5`。结论：**它是 D-014 实现 worker，不是新的用户复核 session；真实用户输入为 0。**

## 给后续摘录工作的边界

1. 研究与写作原话：
   - 先取 ChatGPT `6a680399` 的 3 个研究起点回合，说明问题怎样第一次被校准。
   - 再取 `019fa2f5` 中研究课题二次对齐、来源处理、文章逻辑、表达、排版和作图阶段。
   - 再补 `019fabca` 的 6 条分支新增输入。
   - ChatGPT `6a68bc9e`、`6a6aa430`、`6a6aaeda` 和 Codex `019fabd3` 只作为对应专题的 supporting evidence，不让专题追问压过主干。
   - `019fabd3` 只提供“两条用户要求 + 实跑结果”的支撑，不把 subagent 报告冒充用户观点。
2. 仓库改造原话：
   - 取 `019fa2f5` 后半段的重构与第一轮 drift 复核。
   - 按 id 差集追加 `019fb322` 的 49 条和 `019fb3f3` 的 23 条。
3. 不要从 fork 文件顺序复制整段 user message，否则会把父历史重复计算两到三次。
4. subagent 的 finding 可以作为“发生过什么”的实施证据，但不能写成“用户说过什么”。
5. `019fa31a` 和 `019fb211` 可在综合阶段作为邻近对照材料，但不进入本次两个核心问题的原话统计。
6. ChatGPT conversations 没有本地 JSONL；最终引用其原话时必须回到原 conversation 逐回合复核，不能只把本文件的摘要改写成引号。
