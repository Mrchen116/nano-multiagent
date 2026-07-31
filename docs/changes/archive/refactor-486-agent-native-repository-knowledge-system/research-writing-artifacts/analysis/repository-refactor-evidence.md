# Agent-Native 仓库文档体系改造：用户纠偏取证与文章增补候选

> 临时取证文件。本文只服务于本次会话分析，不是仓库 current 文档、最终文章或 skill 的权威来源。
>
> 原始证据来自三个 Codex rollout JSONL；`refactor-486` 的最终 `plan.md`、`validation.md` 与删除前的 `drift-review.md` 只用于还原 D 编号语境和核对最终裁决，不能替代用户原话。

## 1. 会话范围与去重

| 代号 | Session id | 原始文件 | 本文用途 |
|---|---|---|---|
| `M` | `019fa2f5-2fc5-76e0-890c-8ccc657b4935` | `/Users/czj/.codex/sessions/2026/07/27/rollout-2026-07-27T17-43-25-019fa2f5-2fc5-76e0-890c-8ccc657b4935.jsonl` | 主干；从最初审计、文章研究一直到仓库改造与第一轮复核 |
| `R1` | `019fb322-eca1-71e2-a2fb-cc316a057f04` | `/Users/czj/.codex/sessions/2026/07/30/rollout-2026-07-30T21-07-18-019fb322-eca1-71e2-a2fb-cc316a057f04.jsonl` | 仓库改造复核分支；索引、门禁、skill 契约、历史与 current 漂移 |
| `R2` | `019fb3f3-a316-7a91-8d39-e4176a6f1a25` | `/Users/czj/.codex/sessions/2026/07/31/rollout-2026-07-31T00-55-16-019fb3f3-a316-7a91-8d39-e4176a6f1a25.jsonl` | `R1` 的复核分支；测试指南、可恢复状态、剩余流程漂移 |

去重方法：

1. 只取 `response_item.payload.type=message` 且 `role=user` 的输入。
2. 排除 Codex 自动注入的 `<recommended_plugins>`、`<environment_context>`、`# AGENTS.md instructions` 和空输入。
3. `R1` 按 response item id 减去 `M` 已出现的输入；`R2` 再减去 `M ∪ R1`。因此 fork 复制的父历史不会重复计入。
4. 顺序号含义：
   - `M-###`：主干过滤后的第 N 条真实用户输入；
   - `R1-###`：`R1` 相对主干新增的第 N 条真实用户输入；
   - `R2-###`：`R2` 相对 `M ∪ R1` 新增的第 N 条真实用户输入。
5. 去重结果：主干 152 条真实用户输入；`R1` 新增 49 条；`R2` 新增 23 条。
6. 下列时间均为 JSONL 顶层 UTC 时间戳（`Z`）。

证据强度说明：

- “用户直接判断”可以直接用于提炼偏好和原则。
- D 编号消息通常包含 Agent 先前生成的问题描述；其中可以确认的是用户选择、追问和否决，不能把整段 D 描述都当成用户原创理论。
- 单独的“改吧”“commit”不提供独立原则，除非它确认了紧邻的明确方案；本文原则分析优先使用有因果说明的输入。

## 2. 用户原话证据

### 2.1 范围：整理知识体系，不擅自改变产品或开发政策

#### E-S01：起点就不是只缩短 `AGENTS.md`

`M-001` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-27T09:43:28.648Z` · `msg_019fa2f5-3c88-7673-8b97-8b939d2c6ee5`

> 现在我想整理一下我这个仓库的文档体系。AGENTS.md我觉得作为每次都要放入agent上下文的内容写的太长了，有些不是必须的东西应该搬出去到其他文档或者独立文档中。以及应该把本仓的开发流程，change-* skill的流程注入吧。以及AGENTS.md中应该把整个仓库的文档体系，写进去吧，或者一个index.md中，然后AGENTS.md再引用他。还有其他的文档可能也要做整理。
>
> 你先了解下本仓的现状，再上网学习人家的做面向agent时代的代码仓文档体系构建的一些最佳实践。然后再给我应该怎么整理的思路

#### E-S02：审视整个文档体系

`M-002` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-27T09:46:34.542Z` · `msg_019fa2f8-12ae-7bf3-9307-db5b79baf348`

> 除了agents.md还要审视我的整个文档体系。如果大家的最佳实践有更清晰的设计，我们可以采用

#### E-S03：文档整理不授权流程语义漂移

`M-005` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-27T10:34:28.275Z` · `msg_019fa323-ec33-7701-8112-e0c74487d3e7`

> 我原本是不是没有强制要做spec-review？你加的？

`M-006` · 同 session · `2026-07-27T10:38:19.535Z` · `msg_019fa327-738f-7a01-9754-8a5f2996c41a`

> 我没改这个流程，你不要改。你只做文档整理，因文档整理而导致的相关修改当然可以改，但是这种把原本流程都改了就不要了

#### E-S04：大迁移要拆成可核对的小提交

`M-076` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-30T02:32:00.174Z` · `msg_019fb0dd-49ae-7f21-88a6-7a09b8061572`

> 现在整套理论指导差不多了。现在回到我们的nano项目上审视。我觉得codex/docs-knowledge-system 改的东西有点太多了。我觉得应该拆分成更小的commit。你一步步改，我们一步步对齐。

#### E-S05：不能把目标缩成“重建一个 PR”

`M-081` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-30T03:07:38.321Z` · `msg_019fb0fd-e9d1-71b2-922e-25416e986971`

> NO，是要从我们总结出来的agent native文档体系思考，把整个仓库的文档规整好。不单单是重建pr

#### E-S06：遇到漂移先留证、再由用户裁决

`M-091` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-30T06:24:29.415Z` · `msg_019fb1b2-22e7-7e72-9621-706165ba507a`

> 有一些漂移如果不是我期望的，我希望提issue后面解决掉。所以漂移的东西，你先用临时文件记录下来，我审核是否符合我期望

### 2.2 权威、根指令和入口：概念必须让读者真正理解

#### E-A01：`canonical owner` 不能只作为黑话出现

`M-103` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-30T11:39:15.116Z` · `msg_019fb2d2-4f2c-7be3-b5be-9adaccda59b6`

> 我跟你一点点过。/Users/czj/Repos/nano-multiagent/.worktrees/docs-knowledge-system-rebuild/AGENTS.md的工作红线中，“同一事实只在 canonical owner 写全”是啥意思，canonical owner是什么

#### E-A02：根指令仍需极简项目定位

`M-105` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-30T11:44:35.153Z` · `msg_019fb2d7-3151-70d2-a8a5-995dd3ce93bf`

> 另外，根据我们写文章的时候的结论：
> **仓库级定位和必要的粗粒度地图。**  
> 如果仓库名称和目录结构不足以说明项目做什么、主要组件如何分工，可以用几句话建立最小心智模型。完整架构仍然属于 `ARCHITECTURE.md`；根文件只提供足够开始探索的信息和链接。
> 我觉得AGENTS.md开头，我觉得应该用极简的几句话，描述我们的项目是做啥的，你现在没

#### E-A03：标题也要表达真实关系

`M-104` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-30T11:41:15.116Z` · `msg_019fb2d4-23ec-7853-93cb-7eef579bb39d`

> 调研与联调入口，我觉得这是两件不太相关的事，不应该放一个标题里吧

#### E-A04：文档规范不应偷偷承载 actor 的 workflow

`M-112` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-30T12:05:52.667Z` · `msg_019fb2ea-af9b-7801-822e-2b8d22b84417`

> /Users/czj/Repos/nano-multiagent/.worktrees/docs-knowledge-system-rebuild/docs/specs/CONTRIBUTING.md
>
> 中，**## 读侧 grounding checklist(change-\* 作者在各自阶段执行)**
> **## 收尾归并 checklist(orchestrator 在提 PR 前执行)**
>
> 这是skill自己的行为约束吧？为啥写到这里了？

#### E-A05：领域文档应承载稳定领域，而不是当前唯一小主题

`R1-001` · session `019fb322-eca1-71e2-a2fb-cc316a057f04` · `2026-07-30T13:09:25.640Z` · `msg_019fb324-de08-7160-b97c-5f7755b75376`

> docs/development/commenting.md 这个文件名我觉得不太好，不知道我有没有理解错你的修改。我希望有个文件讲的是coding 的 guideline，也就是说我这个仓库写代码的规范，只是目前只有Commenting and Docstrings而已。你懂吗？你是不是没有一个文件承载这个

#### E-A06：文档路径变化要同步真实消费者，包括 skill

`R1-003` · session `019fb322-eca1-71e2-a2fb-cc316a057f04` · `2026-07-30T13:21:21.857Z` · `msg_019fb32f-cbc1-7132-bed2-6cf49f944b41`

> skill是不是也要改，我记得skill有要求遵守

#### E-A07：skill description 只服务于触发

`M-123` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-30T13:00:23.410Z` · `msg_019fb31c-97f2-7851-8b23-39376bbcafd9`

> description是触发skill用的，别写那么多东西，就写什么时候用

### 2.3 索引：必须提供文件系统之外的增量信息

#### E-I00：顶层文档地图有真实的可发现性价值

`M-038` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-28T11:32:20.994Z` · `msg_019fa87f-4582-7be2-8bbf-61a284711c14`

> 仓库地图不应该只是“有哪些文件、每个文件写了什么”的清单。Agent 本来就能列目录、搜索文件名和全文检索，重复文件树提供的价值有限，也很容易随着文件增删而过期。
>
> 这个我不同意。文档肯定要通过文档之间的引用链起来，这是Agent-Native 代码仓文档体系的常识吧。比如AGENTS.MD肯定要写这个docs/README.md文档。否则agent根本不知道有这个文档存在，他就很难读到，虽然他可以探索目录，但是他在解决他的问题的时候，又没有上下文信息提示他有这些文档，他不会去读。再者说，哪怕无意中看到有这个文件，他只能猜测这个文件的作用，也低概率读取消费。同理，docs/README.md中列出“有哪些文件、每个文件写了什么”也有价值，就是上述的价值。理解吗

这条与后来的 E-I01/E-I02 并不矛盾：顶层地图解决“Agent 不知道文档存在和作用”的第一跳；频繁变化的下层目录若只机械重列文件，则没有新的路由信息。

#### E-I01：活动目录本身已是索引时，不要手工再抄一份

`M-125` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-30T13:03:25.713Z` · `msg_019fb31f-6011-7640-b0fc-d2a25a072113`

> docs/changes/README.md有**## 活动区索引这个合理吗，我觉得这带来了额外无意义的文档维护。不符合我们的文章的精神吧**

`M-126` · 同 session · `2026-07-30T13:03:50.956Z` · `msg_019fb31f-c2ac-76d0-8909-04d19c8537b8`

> 压根没带来增量信息

#### E-I02：研究集合 README 不该维护易漂移文件清单

`R1-015` · session `019fb322-eca1-71e2-a2fb-cc316a057f04` · `2026-07-30T14:48:25.093Z` · `msg_019fb37f-7f05-79b1-a265-83136e7d832a`

> docs/research/architecture-reviews/README.md 干嘛又要放**## 已保留快照。没有价值啊。多了一处要维护的地方**

`R1-016` · 同 session · `2026-07-30T14:51:40.930Z` · `msg_019fb382-7c02-7590-8c72-8004fa14806d`

> 这次重构文档体系，还有没有类似的问题，对于频繁更新的文档非要维护一个index这种愚蠢的做法

`R1-017` · 同 session · `2026-07-30T15:02:54.110Z` · `msg_019fb38c-c19e-7480-b28f-2cdb9332fe84`

> [brainstorms/README.md (line 5)](/Users/czj/Repos/nano-multiagent/.worktrees/docs-knowledge-system-rebuild/docs/research/brainstorms/README.md:5)、[comparisons/README.md (line 9)](/Users/czj/Repos/nano-multiagent/.worktrees/docs-knowledge-system-rebuild/docs/research/comparisons/README.md:9)是非常不符合我们文章精神的，删掉里面的单纯列文件，没信息量的行为。其他的可以讨论

#### E-I03：有导航价值的统计可以保留，但要解决漏更新

`R1-019` · session `019fb322-eca1-71e2-a2fb-cc316a057f04` · `2026-07-30T15:10:22.298Z` · `msg_019fb393-985a-7b22-834a-728643b10131`

> [kernel/spec.md (line 23)](/Users/czj/Repos/nano-multiagent/.worktrees/docs-knowledge-system-rebuild/docs/specs/kernel/spec.md:23)，我觉得里面的 Requirements数量还是值得维护的，但是确实容易漏更新，这种最好咋做

### 2.4 手工状态：外部化不等于新建重复快照

#### E-ST01：先问状态文件的来源和更新触发

`M-127` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-30T13:05:44.473Z` · `msg_019fb321-7e19-7190-9016-65eb7a3ffa10`

> status.md是啥，之前有吗

`M-128` · 同 session · `2026-07-30T13:10:07.437Z` · `msg_019fb325-814d-7bf3-b776-c2c96feed959`

> status.md 啥时候触发更新？

#### E-ST02：已有阶段产物能表达状态时，状态副本没有价值

`M-129` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-30T13:11:57.742Z` · `msg_019fb327-302e-72c2-a8c5-848a73bc9bd5`

> 我觉得没必要吧，本身每个阶段完成，对应的文档都能看出来

`M-130` · 同 session · `2026-07-30T13:13:25.228Z` · `msg_019fb328-85ec-7f20-926b-6ac4d1ef11f2`

> 改掉，恢复成原本没有status.md的样子

#### E-ST03：真正无法恢复的状态仍应持久化

`R2-007` · session `019fb3f3-a316-7a91-8d39-e4176a6f1a25` · `2026-07-30T17:12:30.202Z` · `msg_019fb403-68fa-7f21-87ad-a14c0880ed64`

> [D-024 (line 172)](/Users/czj/Repos/nano-multiagent/.worktrees/docs-knowledge-system-rebuild/docs/changes/refactor-486-agent-native-repository-knowledge-system/drift-review.md:172)code-review finding 和轮次只存在于内存 这是啥问题

语境还原（非用户原话）：D-024 讨论的不是再建一份全局 `status.md`，而是 code-review finding、轮次、origin head 和 open/closed 状态只存在于 orchestrator 内存，跨 session 后无法恢复。用户随后要求建 issue。这里与 E-ST02 共同形成边界：**重复的状态不要写；无法从已有 durable artifact 与实时状态恢复的信息必须写。**

### 2.5 动态计数和机械门禁：声明必须与真实保护范围一致

#### E-M01：先分清“数字写错”与“保护能力不存在”

`R1-007` · session `019fb322-eca1-71e2-a2fb-cc316a057f04` · `2026-07-30T13:33:10.279Z` · `msg_019fb33a-9b07-7890-be27-8330ee80cf7c`

> ### D-001：关键路径 E2E 清单的计数与“已有门禁”不一致
>
> - 现状：`docs/development/e2e-critical-paths.md` 写“v1 必保活当前为 12 条”，表中实际有 13 行
>   （1–6、8–14）。
> - 现状：同页声称清单与测试 drift 时“门禁不过”，但现有 `tests/unit/test_e2e_catalog.py` 只检查隔离
>   Gateway model catalog 注入，没有解析这份 Markdown 或核对表中的测试符号。
> - 影响：读者会高估当前关键路径数量的准确性和机械保护程度。
> - 待决定：
>   1. 如果这份清单应是强约束，修正计数并在 `scripts/docs-check` 中加入表项/测试符号检查；
>   2. 如果它只是人工 catalog，修正计数并收回“门禁不过”的承诺；
>   3. 如果其中某行不应属于 v1，先调整清单内容，再决定检查方式。
> - 状态：Awaiting user review；原文未修改。
>
>
> 这个问题我只理解了计数的问题，这个我觉得更新下就行。剩下的问题，我不太理解，你解释下

`R1-008` · 同 session · `2026-07-30T13:36:16.263Z` · `msg_019fb33d-7187-7ab1-b29b-15744e41201e`

> 等下，CI虽然没强制要求e2e测试，但是这13条e2e测试不存在？？是这个意思？

`R1-009` · 同 session · `2026-07-30T13:39:16.938Z` · `msg_019fb340-334a-75f2-896e-7b149047340e`

> 那你思考是否有必要“清单与测试 drift 时门禁不过”

#### E-M02：测试指南不能声称超出 contract tests 的保护

`R2-001` · session `019fb3f3-a316-7a91-8d39-e4176a6f1a25` · `2026-07-30T16:56:14.417Z` · `msg_019fb3f4-8551-7ac2-8f06-7501802c8516`

> [D-003 (line 23)](/Users/czj/Repos/nano-multiagent/.worktrees/docs-knowledge-system-rebuild/docs/changes/refactor-486-agent-native-repository-knowledge-system/drift-review.md:23)Testing 指南声称的机械保护超过真实 contract tests 这个你建议如何

`R2-003` · 同 session · `2026-07-30T17:02:29.647Z` · `msg_019fb3fa-3f0f-7671-9b98-00d35a28695e`

> 当前有三项机械保护，我没懂你跟change-impl-worker说这个有什么用

`R2-004` · 同 session · `2026-07-30T17:03:15.448Z` · `msg_019fb3fa-f1f8-78c1-88bc-9ec33facbd00`

> 你立足于这是给change-impl-worker的测试指导文档，来审视你的修改

### 2.6 Code-as-docs、current、history 与运行证据

#### E-T01：是否写长期文档要从“增量知识 vs 双写漂移”判断

`M-062` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-29T08:23:10.376Z` · `msg_019facf8-6f28-7582-a2b9-9eea27f9fb11`

> 我觉得你研究歪了。应该研究的是哪些值得写成文档，哪些直接code as documentation更好。再去研究下我理解写文档的优势是，1. 一些东西是代码没有的，比如这么实现背后的一些思想。2. 代码仓很大，如果纯靠agentic search代码来或者某个功能的实现设计，很可能找错了，或者找漏了。code as documentation的优势是：一份真相，不会有同步不及时的问题。

#### E-T02：比较研究天然是时间快照，不应追改成 current

`M-115` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-30T12:20:58.006Z` · `msg_019fb2f8-8016-7df2-b7f2-4426bdb1bdf4`

> ### D-004：Claude Code tools 比较材料仍把已经实现的能力写成缺口
>
> - 现状：原 `docs/tools-diff-cc/`（现
>   `docs/research/comparisons/claude-code-tools/`）中 Read-Before-Write、SessionFileState 等材料记录的是
>   旧 nano 基线；当前代码已经包含相关能力。
> - 影响：旧研究如果继续靠近 current 入口，Agent 可能把历史差距当成当前缺陷。
> - 待决定：迁入 research 并冻结为带基线的 snapshot；其中仍未解决的缺口是否建立 issue，需逐项审核。
> - 状态：Awaiting user review；正文不重写。
>
>
> 这个问题我给你解释下，对比研究都是带时间的，过时了很正常，所以我觉得docs/research/comparisons/下的目录名都应该带时间戳，对比什么+时间，那就一目了然了。

#### E-T03：运行手册应暴露 current 证据入口，而不是堆一次性成功快照

`M-118` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-30T12:33:18.591Z` · `msg_019fb303-ccff-76c3-95aa-f6e313685c1a`

> docs/development/llm-integration.md中
> 为啥写：
> ## 最近验证快照
>
> 2026-02-26 的留档结果：
>
> - 请求：`POST /v1/messages`
> - 模型：`codexOAuth:gpt-5.2-codex`
> - 返回：`HTTP/1.1 200 OK`
> - 结果：`content[0].text = "pong"`
>
> 这是一条带日期的运行证据，不保证该 model id 在后续代理配置中持续可用。若 `codexOAuth:gpt-5.2-codex` 不可用，历史上使用过 `moonshot:kimi-k2.5`；实际联调仍以当前代理配置、健康检查、请求响应和 session 日志为准。
>
> 我觉得没用啊，反而那边的配置文件路径还有用点，应该加进去，因为要看有哪些模型

#### E-T04：代码注释中的引用也必须指向 current owner

`R1-012` · session `019fb322-eca1-71e2-a2fb-cc316a057f04` · `2026-07-30T14:38:54.187Z` · `msg_019fb376-c8eb-7383-b426-7cb849ece875`

> ### D-007：生产代码注释仍指向 retired Gateway SPEC
>
> - 现状：`src/personal_assistant/gateway/composition.py` 引用 `NodeGateway-SPEC §4.2`。
> - current 替代入口：`docs/specs/gateway/routing-delivery.md` 的“重启后同一通道会话续接原内核会话”。
> - 影响：从生产代码追踪约束时会进入 retired 文档。
> - 待决定：改为 current spec 路径；或把足够的“为什么”直接保留在代码注释中。
> - 状态：Awaiting user review；代码未修改。
>
>
> 这个，改最新的路径吧

#### E-T05：历史脑暴未落地是正常状态，不是 current drift

`R1-037` · session `019fb322-eca1-71e2-a2fb-cc316a057f04` · `2026-07-30T16:51:29.799Z` · `msg_019fb3f0-2d87-7082-8b7a-2dd179c3bbe1`

> [D-006 (line 45)](/Users/czj/Repos/nano-multiagent/.worktrees/docs-knowledge-system-rebuild/docs/changes/refactor-486-agent-native-repository-knowledge-system/drift-review.md:45)旧脑暴提出通用 reviewer，与当前三类门禁不同
> 脑暴没做不是很正常吗

#### E-T06：暂停中的 active 文档仍可能是 live consumer，不能因为“不是 current spec”而放任失效

`R1-042` · session `019fb322-eca1-71e2-a2fb-cc316a057f04` · `2026-07-30T17:11:19.762Z` · `msg_019fb402-55d2-76b3-966d-a8b7d8a57a84`

> [D-016 (line 110)](/Users/czj/Repos/nano-multiagent/.worktrees/docs-knowledge-system-rebuild/docs/changes/refactor-486-agent-native-repository-knowledge-system/drift-review.md:110)：paused feat-444 的 design 中保留了失效健康检查，属于 active unit 文档问题。这个你改下

#### E-T07：知识表面不止 Markdown，测试文件名和模块说明中的旧术语也会误导探索

`R1-043` · session `019fb322-eca1-71e2-a2fb-cc316a057f04` · `2026-07-30T17:13:05.671Z` · `msg_019fb403-f387-7333-bc53-61f00dedae42`

> [D-014 (line 92)](/Users/czj/Repos/nano-multiagent/.worktrees/docs-knowledge-system-rebuild/docs/changes/refactor-486-agent-native-repository-knowledge-system/drift-review.md:92)：旧术语位于测试文件名和模块说明，需要重命名测试文件，不是纯 Markdown 整理。这个问题我觉得本pr要修，你开个subagent修一下吧

### 2.7 Change 流程：允许不同实施顺序，但必须保持真实和可验

#### E-C01：允许“实现先发生、交付前补 as-built 文档”的快速开发路径

`M-120` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-30T12:41:10.910Z` · `msg_019fb30b-01fe-7683-8996-4f01bda2d146`

> docs/development/change-workflow.md 还有一种情况，是开发者vibe coding，用户一边说，agent一边改，改完之后再补unit的spec，design等文档。

`M-121` · 同 session · `2026-07-30T12:41:43.104Z` · `msg_019fb30b-7fc0-76c0-a7b2-9a00d1073762`

> 这叫快速开发模式

`M-122` · 同 session · `2026-07-30T12:43:30.183Z` · `msg_019fb30d-2207-77a1-9437-21c9e90b0162`

> verifier 不用。用户已经测过，就放心好了。code review需要。

#### E-C02：并行 Agent 应保留自治，不把报告提交集中到 orchestrator

`M-135` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-30T14:45:30.493Z` · `msg_019fb37c-d4fd-7ef2-acbd-1ca3159e43e7`

> ### D-018：并行 reviewer/verifier 的报告 push 存在竞态
>
> - 现状：`change-orchestrator` 要求 reviewer 与 verifier 并行。reviewer 在 unit worktree commit 并直接
>   push；verifier 在独立 detached worktree fetch/rebase 后 push。orchestrator 等两者返回后只读取
>   unit worktree 的本地 `BEFORE..AFTER`，没有先把远端 verifier report commit 快进回本地。
> - 风险：两者可能发生 non-fast-forward；或者远端已有两个报告、unit worktree 只含 reviewer 报告，后续
>   `push --force-with-lease` 覆盖 verifier 报告。
> - 待决定：报告产出是否改成串行集成；或由 orchestrator 在每个报告返回后 fetch/fast-forward，并验证所有
>   report commits 都是本地 HEAD 祖先后再继续。
> - 状态：Awaiting user review；skills 未修改。
>
> 这个你觉得怎么又简单又合理

`M-139` · 同 session · `2026-07-30T15:23:21.546Z` · `msg_019fb39f-7c4a-79b0-9f86-4c57ec86bc06`

> 有什么更简单的方式来解决，我觉得你让Orchestrator做commit不合适，他们应该自己自治

`M-140` · 同 session · `2026-07-30T15:35:57.324Z` · `msg_019fb3ab-048c-71d2-8ddf-fb2989e01a01`

> 其实agent的应变能力很强的，你简单点说，他能解决的。

#### E-C03：发现历史规则时，先追溯它为什么存在，再决定保留或删除

`R1-024` · session `019fb322-eca1-71e2-a2fb-cc316a057f04` · `2026-07-30T15:37:57.527Z` · `msg_019fb3ac-da17-75d0-8b69-ed2569354581`

> ### D-025：校正后 delta 的软对账缺少可恢复的执行契约
>
> - 现状：orchestrator 在所有门禁后校正 delta，并要求 reviewer/verifier 对每条 Requirement/Scenario
>   “软对账”；但两类 skill 的派发包和报告 schema 都没有 corrected delta path/SHA、对账 mode 或固定
>   报告段。
> - 影响：Agent 可以口头声称已经对账，却无法从 archive 判断哪个角色核对了哪个 delta 版本。
> - 待决定：为 corrected-delta review 定义稳定输入和 durable report；或把该检查并入已有门禁且明确
>   invalidation/复验规则。
> - 状态：Awaiting user review；delta 流程未修改。
>
>
> 这个是啥

`R1-025` · 同 session · `2026-07-30T15:41:44.902Z` · `msg_019fb3b0-5246-7481-aef8-13db2f6644c2`

> 等下，orchestrator不是在reviewer/verifier 检查完再写的delta-spec吗，哪个文档写了reviewer/verifier 要检查delta-spec

`R1-026` · 同 session · `2026-07-30T15:43:54.585Z` · `msg_019fb3b2-4cd9-7433-a2f4-abc4e572c091`

> 当初为啥加入reviewer/verifier 软对账，还能找到记录吗

#### E-C04：保留必要对账，但只放给真正负责的角色

`R1-027` · session `019fb322-eca1-71e2-a2fb-cc316a057f04` · `2026-07-30T15:49:38.559Z` · `msg_019fb3b7-8c7f-7b72-8163-b57c9712e420`

> 我觉得不需要软对账，相信他了

`R1-028` · 同 session · `2026-07-30T15:53:52.142Z` · `msg_019fb3bb-6b0e-7f21-aaf1-b0a4ee8d314c`

> 算了，我觉得应该要一步对账。但是仅verifier负责就行

#### E-C05：不要为了“可恢复”机械增加 SHA 和状态协议

`R1-029` · session `019fb322-eca1-71e2-a2fb-cc316a057f04` · `2026-07-30T16:21:12.727Z` · `msg_019fb3d4-7397-78a3-919c-61a7665a412b`

> 为什么搞SHA，哪里来的思想？

`R1-030` · 同 session · `2026-07-30T16:22:38.952Z` · `msg_019fb3d5-c468-7233-9c40-8bb2ba31a356`

> 删掉！画蛇添足，没必要

`R1-031` · 同 session · `2026-07-30T16:31:38.945Z` · `msg_019fb3de-01c1-7281-b4ec-7b9fef3bd718`

> ok，两边verifier和orchestrator都是能力非常强的agent，审视你的设计有无过于冗余的地方

#### E-C06：也不能简化到接口含糊

`R1-033` · session `019fb322-eca1-71e2-a2fb-cc316a057f04` · `2026-07-30T16:45:42.038Z` · `msg_019fb3ea-df16-7e40-8420-cbf3f13b3669`

> **③ Full unit 由 verifier 对账**:只派 `change-verifier`,指定 `verification_mode: corrected-delta`,其余按该
> skill 的输入契约派发。
>
> 这里他知道“该skill 的输入契约派发。”是啥吗

#### E-C07：skill 变长时要重新证明每一条是否必要

`M-150` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-30T17:28:06.854Z` · `msg_019fb411-b3c6-71a2-853d-8036406969b5`

> 怎么增加了这么多行。如果考虑执行这些skill的agent很聪明，也要这么写吗，还是说这些就是说清流程必备的

#### E-C08：简化流程不能比原流程更重

`R1-046` · session `019fb322-eca1-71e2-a2fb-cc316a057f04` · `2026-07-30T17:31:46.431Z` · `msg_019fb415-0d7f-79f3-a166-6aacd98f97b6`

> ### D-027：简化实施与零用户面 Full 的 reviewer 政策冲突
>
> - 现状：`change-orchestrator-simple` 要求所有 Full unit 执行 reviewer、verifier、code review 三道闸；现有 `change-reviewer` 则要求零用户面 unit 立即退出，这与原 `change-orchestrator` 的 selected-gates 矩阵一致。
> - 影响：零用户面 Full unit 如果选择简化实施，无法同时满足“两份规则都不跳过”。
> - 待决定：简化实施是否沿用零用户面跳过 reviewer 的既有政策，还是只允许存在用户可观察旅程的 Full unit 使用。
> - 状态：Awaiting user review；本轮只让 reviewer/verifier 兼容简化实施不强制 `tasks.md` / `progress.md` 的记录方式，没有改变零用户面政策。
>
>
> 当然，简化的版本当然不可能比原本的还复杂

#### E-C09：流程中的例外授权不能只靠隐含判断

`R2-016` · session `019fb3f3-a316-7a91-8d39-e4176a6f1a25` · `2026-07-30T17:40:41.247Z` · `msg_019fb41d-369f-77e0-9b26-c35cff9e8f37`

> D-022 pass-with-issues 缺少明确授权来源 说下这个是啥问题

`R2-018` · 同 session · `2026-07-30T17:43:11.320Z` · `msg_019fb41f-80d8-7123-82a1-7fc051676b8c`

> D-022的问题 提issue

语境还原（非用户原话）：D-022 指 `pass-with-issues` 可以放宽，但派发包没有 acceptance bar，也没有规定谁、何时、依据什么授权。用户选择建 issue，而不是让 orchestrator 临场继续猜。

### 2.8 兼容入口、格式与语言：迁移不能制造新噪声

#### E-H01：live consumer 已迁完时，不保留无意义兼容入口

`R1-002` · session `019fb322-eca1-71e2-a2fb-cc316a057f04` · `2026-07-30T13:14:21.008Z` · `msg_019fb329-5fd0-7460-8cfa-6f17672f40fc`

> 第二点，按你说的改吧。但是根目录 COMMENTING_GUIDE.md 不继续作为兼容入口。一步改到位了

`M-146` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-30T16:33:34.607Z` · `msg_019fb3df-c58f-7953-8a04-86fd3da11e42`

> docs/IM前端蓝图.md，docs/需求.md 这些等等的旧文档，后续也不消费了的，都删了吧，不要留兼容入口了

#### E-H02：禁止无意义硬换行

`M-109` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-30T12:02:02.476Z` · `msg_019fb2e7-2c6c-73f1-828b-070f72593a53`

> IM 提供独立中心服务与
> Web 客户端。
>
> 这中间为啥要加个换行？？？

`M-143` · 同 session · `2026-07-30T15:52:25.350Z` · `msg_019fb3ba-1806-7761-a325-ea142f964b76`

> 我看很多文档有很多无端端的换行，比如docs/changes/README.md：
> 根目录旧 `TASKS/`、`PROGRESS/`、`ACCEPTANCE/` 已停止接收新内容并整体迁入
> [`docs/archive/legacy-development-records/`](../archive/legacy-development-records/README.md)。旧 milestone id
> 只代表当时的 TDD control-tower 流程，不能机械映射成 change unit。
>
> `data/dev-tasks.json` 当前不存在；现行 orchestrator 明确只在内存和 unit 文档中维护调度状态。审计只发现一个
> 无生产调用者的旧 worktree symlink helper 及其测试，本次已移除该兼容接线；gitignore 条目暂时保留，避免旧
> worktree 的本机残留进入版本控制。
>
>
> 帮我全部改掉。并且以后你都不要无端端加换行！！

#### E-H03：一次 Agent 的排版错误不应升级成仓库行为规则

`M-144` · session `019fa2f5-2fc5-76e0-890c-8ccc657b4935` · `2026-07-30T16:18:57.544Z` · `msg_019fb3d2-6388-7021-9ffb-5ed621c93334`

> 这个所谓的规则不要加进去任何我的仓库里的文档，只有你个猪会这么做，任何其他模型不会这样做

这条输入的情绪很强，但原则很清楚：修掉局部错误，不要因为一次个体失误就给所有未来 Agent 增加一条长期规则。

## 3. 从纠偏中抽出的常见错误模型

| 常见错误 | 为什么错 | 更好的原则 | 文章当前覆盖 | 是否值得补回文章 | 建议位置 |
|---|---|---|---|---|---|
| 把文档迁移当成重写产品/流程政策的授权 | “整理表达”与“改变制度”是两种决策；静默改语义会让漂亮目录掩盖未经批准的政策变化 | 迁移前写清非目标；语义改动与路径/结构改动分开；遇到 code/doc/process drift 先留证、列选项、由真正 owner 裁决 | `HOW` 只在自动 Docs Agent 段落说“不应自行改变产品语义”（约 710 行），对人工迁移不够显眼 | **高，值得新增** | `最佳实践 → 从已有仓库迁移`，在步骤表前增加“迁移授权边界与 drift queue” |
| 只改 `AGENTS.md`，或反过来把目标缩成一个 PR | 根入口只是 Control 的第一跳；如果 current、work、evidence、history、runbook 和 consumer 不一起对账，入口会指向旧世界 | 以整条知识消费链为迁移单位，同时保持小提交、逐项裁决 | 已充分覆盖五种角色、三层入口和迁移顺序 | **不新增理论**；可以在迁移案例中加一句“小提交不等于缩小最终系统边界” | `从已有仓库迁移` 的实践说明 |
| 使用 `canonical owner` 等术语，却没有让读者知道它是什么 | 术语不能代替判权；读者不知道它指“某类事实唯一写全的位置”、维护角色还是审批人 | 优先写“这类事实唯一完整维护在哪里”；必须用 owner 时区分内容 owner、执行 actor、审批者 | 概念已经存在，但仍有 `canonical` / `owner` 英文散落（约 323、661、703、731 行） | **中，值得编辑性修订** | 全文术语统一；首次出现时定义，不新建理论章节 |
| 根指令只顾变短，删掉项目最小心智模型或难发现入口 | Agent 在探索前没有项目定位，就无法形成正确搜索空间；外部日志/参考仓也无法从代码树自然发现 | 根文件保留极简项目定位、全仓高后果边界、顶层地图和无法自然发现的关键入口，正文下沉 | 约 267–346 行已经充分覆盖，并有 nano 示例 | **无需新增** | 保留现文；用本次迁移作为验证案例即可 |
| 任何目录都建 README/index，并手工列出所有文件或 active unit | 文件系统已经表达“有哪些文件”；手工镜像没有增量信息，却引入每次增删都要同步的漂移点 | index 的单位应是“路由决定”，不是“文件”；只有提供用途、状态、权威、读取时机或跨目录关系时才保留。纯清单应删除或生成 | 约 470–485 行写了“每层索引都要证明降低定位成本”，但前文又容易让人理解为每层都应列清单 | **高，值得补一个明确反例** | `第二层是仓库地图` 末尾，区分“稳定语义地图”与“波动目录镜像” |
| 为了跨 session 恢复，给每个 change 新建一份 `status.md` | 如果阶段文档、commit、报告、PR/CI 和 live runtime 已能重建状态，手工摘要只是一个更易过期的副本；但只在内存中的 finding/轮次又确实不可恢复 | 外部化“不可从现有 durable artifact 或实时来源恢复的信息”；可推导状态直接查询/生成；非显然暂停写入当前阶段已有 owner | 约 491–502 行要求保存可恢复状态，但没有说明“不等于单独 status 文件” | **高，值得新增** | 长任务恢复表后增加“durable state ≠ universal status.md”边界 |
| 手工维护动态计数，却没有生成或检查 | 数字本身可能有导航价值，但最容易与正文漂移；删除所有计数也会损失信息 | 先问计数是否影响理解/导航；有价值则从唯一源生成，或做窄而客观的结构校验；无价值则删除 | 约 578–579 行覆盖 generated view，但没有动态计数例子 | **中高，值得加入例子** | “可以生成的内容不要人工双写”后 |
| 文档声称“CI/contract tests 会兜底”，实际只检查其中一小层 | “测试存在”“符号可收集”“CI 会运行”“语义真正覆盖用户旅程”是四个不同命题；含混总括会制造虚假安全感 | 机械承诺必须逐字匹配真实检查范围；只自动化稳定可判定的结构关系，语义覆盖由 review、任务评测或真实 E2E 判断 | 约 695–721 行列出静态检查与任务评测，但缺少“声明粒度”这条原则 | **高，值得新增** | `验证这套体系是否真的有效`，在 Structure/Task eval 之间加入四层区分 |
| 按主题把 actor 行为塞进 spec 写作指南，或把门禁实现细节塞给不需要它的 worker | 文档主题相近不等于消费时机相同；读者无法据此行动的机制说明只增加上下文，actor 的流程还会与 skill 双写 | 规则放置由“谁在什么时候需要据此做决定”确定。结果格式/内容契约放 guide，操作步骤和派发契约放 skill/workflow，确定性保证放 test/CI | 约 314–325、559–589 行已有载体分层，但缺少 consumer/actor 维度 | **高，值得补一句判据和例子** | `约束放进与其强度匹配的位置` 前后 |
| 把代码已经精确表达的实现重新长期文档化 | 双写后自然漂移；可读旧文档比难读代码更危险 | 文档只保存代码中没有的意图/理由/边界，或显著压缩跨模块探索；实现细节以 code/type/test 为真源 | 约 174–210 行已经完整覆盖 | **无需新增** | 保留现文 |
| 把 research、brainstorm、单次 runtime evidence 当成 current，或为“新鲜感”反复追改历史 | 时间快照过时是正常属性；一次成功请求不说明现在可用；旧脑暴未实施也不是产品缺陷 | research 标日期和 baseline 后冻结；current 结论回到 code/spec；runbook 提供当前配置、检查命令和证据入口；active/paused 文档因仍会被恢复而需要保持可执行 | 五种角色和约 487 行已覆盖；对 runbook 中“最近成功快照”的反例不够具体 | **中，值得补 operational 例子** | Evidence 角色或 runbook 说明处 |
| 只搜索 Markdown，漏掉代码注释、测试名、模块说明、skill、脚本提示中的旧知识 | Agent 会用文件名、注释和错误信息探索；这些同样是机器可见的上下文接口 | 文档迁移的 live-consumer audit 要覆盖 Markdown 引用、代码注释、测试名/说明、skill、脚本提示和错误信息 | 约 707 行 Consistency 已含一部分，但不够具体 | **中，值得扩充一行** | `验证 → Consistency` 或迁移步骤 2 |
| 为强 Agent 写固定重试状态机、专属 SHA、重复 schema 和过多流程散文 | 过度规定恢复手法会增加协议面和维护成本，压缩 Agent 自主解决空间；“可恢复”不能自动证明每个字段必要 | 写清不变量、责任归属、输入输出、最终可核验证据和失败升级条件；让 Agent自行选择 fetch/rebase/retry 等局部策略 | 约 278–280、733 行支持“过量指令无收益”，但没有 workflow/skill 的最小充分契约原则 | **高，值得新增** | 根指令讨论后的 skill/workflow 边界，或“约束放进匹配位置”后 |
| 追求简短时只写“按该 skill 输入契约”，让跨角色接口变成隐含知识 | 能力强不等于能读到不存在的接口；跨角色、跨 worktree、跨 session 的交界必须明确 | **最小充分契约**：明确 mode、权威输入位置、产物、通过/失败含义和谁接手；不重复 skill 内部步骤，不规定无关实现手法 | 尚未明确形成一个命名原则 | **高，建议与上一条合并新增** | 同上，形成“结果明确、手法自治”的一段 |
| 把 docs-first 的完整流程当成唯一合法顺序 | 真实开发可能由对话和实现先发生；事后伪造未发生的 milestone/review 比没有记录更糟 | 允许 spec-first、bugfix-lite、快速开发等入口；顺序可变，但交付前必须留下真实的 as-built 意图/设计、适用 review、current 归并和可验证证据 | 约 510–545 行隐含 spec-first，尚未说明快速开发 | **高，值得新增** | `把文档更新嵌入开发过程` 开头或“变更开始时”前，加“顺序可变、闭环不变” |
| 简化流程反而增加门禁或文档 | 名为 simple 却叠加原流程没有的 gate，是语义矛盾；门禁应由风险和用户可观察面决定 | 简化减少编排成本，不改变或增加既有适用性；按风险/用户面选择 gate | 约 733 行只讲无收益就缩小/退役 | **中，作为流程变体例子** | 快速开发/流程变体段落 |
| 旧路径一律保留兼容入口 | 完成迁移后，旧入口继续出现在搜索结果，会延长双重权威和维护期；Git 已保存历史 | 只有外部消费者、未迁 live consumer、稳定公开 URL 或明确过渡窗口存在时才保留 redirect；否则更新所有 live 引用后删除旧入口 | 约 576、688 行只列“标明替代/重定向或删除”，没有选择标准 | **高，值得新增** | `从已有仓库迁移` 的退役步骤 |
| 把一次排版错误写成新的全仓规则 | 每次局部错误都升级为常驻 instruction，会让根文件和指南无限膨胀 | 修正源文件；只有重复、非显然、跨任务且能验证的错误模式才晋升为规则 | 约 547–568 行已充分覆盖 | **无需新增理论** | 可以把“无意义硬换行”作为轻量编辑检查，不升级成规则 |
| 任意硬换行、混用语言、含糊标题和过时术语 | 它们增加 diff 噪声、降低人类可读性，也让搜索与分类信号变差 | prose 按自然段排版；标题表达真实关系；术语首次定义并与 current architecture 一致；格式修复保持 scoped | 文章当前排版本身已基本符合，但没有将其列为迁移质量项 | **低到中**；最多一条 checklist，不值得独立理论节 | `从已有仓库迁移` 或附录式 checklist |

## 4. 最值得补回文章的六组内容

### P1. 文档迁移的授权边界与 drift queue

优先级：**最高**。

建议增加的核心意思：

> 文档整理可以发现产品、代码、测试和流程之间的漂移，但“发现不一致”不等于有权选择哪一方胜出。迁移前应明确非目标，把路径移动、结构调整和语义修改拆开。无法从现有权威直接裁决的差异先进入临时 review queue，记录现状、证据、影响和选项；由产品/架构/流程 owner 决定修文档、改实现、建立 issue 或确认不处理。

为什么值得写：这是本次最早、也最危险的实际错误。Agent 为了让新体系“自洽”擅自增加 spec-review 政策，说明文档重构本身会诱发语义漂移。现文只约束自动 Docs Agent，尚未把它作为所有迁移工作的首要安全边界。

建议位置：`最佳实践 → 从已有仓库迁移`，步骤表之前。

### P2. 索引与状态的“增量信息测试”

优先级：**最高**。

建议把两类问题合并成一个简单判据：

> 新建 index、catalog、status 或 summary 前，先问：它是否保存了源目录、阶段产物、Git/PR/CI 或 runtime 无法直接给出的信息？如果只是抄一遍文件名、active unit、阶段完成状态或动态数量，它就是新的漂移点。真正有价值的 index 提供用途、读取时机、状态、权威和跨目录关系；真正有价值的状态记录保存决定、非显然暂停原因、下一步和已验证边界。可推导内容应查询或生成。

为什么值得写：现文已经说“索引要证明价值”和“长任务要外部化”，但未把二者放在一起，容易让实施者同时创建“每层 README + 每 unit status.md”，正是本次迁移实际发生的过度设计。

建议位置：仓库地图章节末尾增加 index 反例；长任务恢复表后增加 status 反例，二者互相链接。

### P3. 机械保证必须按真实粒度表述

优先级：**最高**。

建议明确四层：

1. 清单中写了一个测试符号；
2. 该符号能被测试框架收集；
3. CI 或指定命令实际运行它；
4. 它在语义上覆盖所声明的用户旅程。

前 1–3 层通常可以机械检查；第 4 层需要 review、真实 E2E 或任务评测。文档只能声称已经实现的那一层。

为什么值得写：D-001 与 D-003 都不是“要不要自动化”的二元问题，而是承诺粒度问题。文章当前把 static checks 与 task eval 分开了，但没有直接提醒作者避免一句“contract tests 会兜底”覆盖多个不同事实。

建议位置：`验证这套体系是否真的有效` 的自动检查表后。

### P4. 面向强 Agent 的最小充分契约

优先级：**最高**。

建议增加一条成对原则：

> 对强 Agent，流程文档应当“结果明确、手法自治”。跨角色边界要明确输入位置、mode、产物、通过/失败含义、责任人和升级条件；角色内部如何搜索、fetch/rebase、重试和组织局部步骤，除非高风险或反复失败，不要写成固定状态机。不要用“能力强”掩盖缺失接口，也不要用“可恢复”给每一步增加 SHA、字段和重复报告。

为什么值得写：用户先否决 SHA/状态协议和 orchestrator 集中提交，随后又指出“按该 skill 输入契约”太含糊。真正的偏好不是一味少写，而是精确写接口、少写策略。这是本次复核中最有普适价值的新原则。

建议位置：`根级指令` 的 skill/workflow 分流之后，或 `约束放进与其强度匹配的位置` 后。

### P5. 流程顺序可变，闭环不变

优先级：**高**。

建议增加：

> Agent-Native 不等于所有变更都必须先写完整 spec/design。高风险或多人协作任务适合 docs-first；快速交互开发可能先形成实现，再在交付前补 as-built spec/design。无论顺序如何，都不能伪造没有发生的里程碑和评审；不变量是目标与边界可追溯、实现经过与风险相称的 review/验证、current 得到归并、历史和证据真实冻结。

为什么值得写：文章现有生命周期图天然让人读成单一 docs-first 流程。本仓真实流程已经证明需要多个入口，且“简化”不能额外增加门禁。

建议位置：`把文档更新嵌入开发过程` 的四个关键时刻之前。

### P6. 兼容入口有退出条件

优先级：**高**。

建议增加：

> redirect/兼容文件不是迁移的默认尾巴。保留它需要至少一个理由：仍有无法同步迁移的 live consumer、公开稳定 URL、外部依赖，或明确的过渡窗口。所有 live consumer 都已更新时，旧入口继续存在只会让 Agent 搜到两个路径并延长双重权威；这时应删除旧入口，让 Git 保存历史。

为什么值得写：现文同时提到 redirect 和删除，却没有选择算法。本次迁移两次出现“明明一步到位却保留兼容入口”的具体问题。

建议位置：`从已有仓库迁移` 的历史/旧入口步骤。

## 5. 已经充分写进文章、不建议重复扩写的内容

1. **根 `AGENTS.md` 的准入条件与极简项目地图**：现文约 267–346 行已经有完整推导和 nano 示例；本次改造只是证明 Agent 实施时仍容易“瘦过头”。
2. **入口可发现性与引用链**：现文约 243–485 行已经从 Agent 探索方式、顶层地图、领域入口和页面引用完整论证。
3. **code-as-documentation 的边界**：现文约 174–210 行已经准确表达“一份实现真相 + 文档保存增量知识/压缩探索”。
4. **Truth / Work / Evidence / Memory / Control**：现文约 113–130、487–502、510–545 行已经覆盖 current、proposed、history、evidence 与 promotion。
5. **一次错误不要直接晋升成长期规则**：现文约 547–568 行已经完整给出“确认根因和适用范围 → 选择位置 → 建立验证 → 写入/缩小/不保留”。

这些主题如果要补，最合适的是加入本次 nano 迁移的简短实践案例，而不是再写一轮抽象原则。

## 6. 对最终写作的建议

如果主代理最终要新建一份“哪些值得补回原文”的用户审阅稿，建议使用下面结构，而不是把本文件原样交给读者：

1. **先给结论**：六项高价值增补、五项已覆盖内容。
2. **每项只写一个真实失败案例**：活动索引、`status.md`、E2E catalog、corrected-delta SHA、快速开发、兼容入口。
3. **案例后给最小原则和文章落点**，不复述整个 refactor-486 流程。
4. **把 repo-specific 名词翻译成通用问题**：
   - `status.md` → 重复状态快照；
   - `D-001` → 机械承诺粒度；
   - `corrected-delta SHA` → 过度协议化；
   - `change-orchestrator-simple` → 简化流程反而加码；
   - `COMMENTING_GUIDE.md` → 无退出条件的兼容入口。
5. 保留“这是从一次实际迁移中归纳出来的经验”这一证据地位，不把 nano 的具体流程写成所有仓库都应照抄的规范。
