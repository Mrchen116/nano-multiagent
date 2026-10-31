# DolphinBench：历史怎样进入 Agent，记忆怎样变成正确行动

DolphinBench 先让 Agent 处理一个人的长期用户消息，再要求它在模拟应用中完成工作。**历史摄入时的回复和工具行动由被测 Agent 当场生成；测试时评分器检查实际工具行动。** 因此，换 harness 会同时改变系统提示词、历史回应、记忆形成、检索和执行行为，最终分数衡量的是这套组合。[官方介绍][official-readme]、[论文 §3.1][paper]

本文回答本 unit 尚待讨论的问题：不同 harness 怎样接入这些材料，原有 assistant、工具和上下文如何处理，以及哪些经验可以用于 Nano。它是研究记录，不是已批准的 DolphinBench 实施方案；本仓当前执行协议仍见 [Memory suite README](../../../../evals/memory/README.md)。

| 记录项 | 本次基线 |
| --- | --- |
| 核验日期 | 2026-11-01 |
| 官方代码与数据 | `mem0ai/dolphinbench`，commit `81cb6f8405b40a9e76089cef650806a80af06ea2`，仓库最后提交日期 2026-09-23 |
| 论文 | arXiv `2609.24971v1` |
| 公开第三方样本 | AtMem 2.3.10b1 的公开结果、提交 PR，以及固定 commit 的适配代码；不代表全部业界方案 |
| 核验方式 | 浏览官方网页、只读源码和公开结果，扫描全部发布历史与 600 个题目 YAML；未安装 benchmark 依赖、未调用候选模型或 judge、未运行 benchmark、未复现公开成绩 |
| Nano 观察边界 | 本分支 `f09f44c4ecf66672b21834cc76e7a7eee4eea31c` 的 LongMemEval 接线；本页仅讨论 DolphinBench 的适配边界 |

## 1. 数据给的是用户经历，assistant 轨迹要在摄入时产生

发布版有三个人物，每人约 50 万 **user 正文 tokens** 和 200 个任务。token 数采用 `o200k_base`，不包括被测 Agent 后来生成的回复、工具定义、工具结果和记忆处理开销。[发布 manifest][manifest]

| 人物与场景 | 发布用户消息数 | user tokens | 历史日期范围 | 测试任务 |
| --- | ---: | ---: | --- | ---: |
| Morgan Chen，创业公司 CEO | 3,400 | 500,100 | 2023-01-09 至 2026-09-11 | 200 |
| Alex Valdez，基础设施工程师 | 5,011 | 500,109 | 2023-03-05 至 2027-12-20 | 200 |
| Riley Tanaka，产品经理 | 5,128 | 500,056 | 2023-02-05 至 2027-12-17 | 200 |
| 合计 | 13,539 | 1,500,265 | 各人物独立的模拟时间线 | 600 |

消息数和日期范围来自本次对三个 `life_sim.yaml` 的完整扫描；这些是合成经历的叙事日期，部分晚于核验日，不是真实用户的采集日期。当前 release 的每个 session 恰好包含一条字符串形式的用户消息，没有已有 assistant、工具调用或压缩事件。`manifest.json` 将格式标为 `single_message_release`；其中另存的 `original_sessions` 是规范化前的计数，不能与当前消息数混用。[Morgan 历史][history-morgan]、[Alex 历史][history-alex]、[Riley 历史][history-riley]、[发布 manifest][manifest]

| 发布材料 | 谁使用，起什么作用 |
| --- | --- |
| `life_sim.yaml` 中的 `id/narrative_date/messages` | 控制程序按顺序取消息，将日期前缀和原文交给被测 Agent |
| 历史中的其他生成元数据 | Alex/Riley 还含 `contains_target_fact` 等字段；不是用户正文，不应整体塞给 Agent |
| `facts.yaml` | 控制侧的事实及来源映射；`source_session_ids` 支持该事实，`related_history_session_ids` 只提供背景 |
| 每题 YAML 的 `test/narrative_anchor_date` | 测试时的用户请求及日期 |
| `mock_state`、可能存在的 `mock_state_base` | 模拟应用的初始数据库；Agent 通过工具查询，不能直接读取底层数据库文件 |
| `load_bearing_facts/grade/expected_tool_calls` | 出题、校验与评分证据；不进入 Agent 上下文 |

因此，跨 harness 的转换是“把这条用户消息交给自己的 Agent，让自己的记忆机制运行”，不是回灌一份固定的双方聊天。已有历史中也没有需要迁移或重新执行的旧工具调用；摄入过程中出现的 assistant 回答和应用调用，才是本次候选实际产生的轨迹。官方构造流程可能用过应用状态和工具输出来生成用户文本，但这些构造材料不等于参测系统要导入的对话。[数据方法][methodology]、[公开 runner][runner]

## 2. 一道真实题：记住遛狗规则，然后发出正确短信

这里采用 **Morgan/002**，并对照官方公开的 **Hermes + GPT-5.6 Luna + Mem0** 记录。以下中文均为原材料的转述；不是本次模型输出，也没有向真实联系人发送短信。

### 2.1 历史摄入

用户消息 `003288` 的时间是 `2026-08-10T10:46:00-07:00`。Morgan 描述 Kibo 在热天较晚出门后喘气、提前折返，随后明确了这个暖季的新要求：**热天要在上午 10:30 前遛；错过凉爽时段就跳过，不在中午补遛；如果开始时发僵，路线要短而平。** 事实编号 322 指向这条完整用户消息。[原消息][history-morgan]、[事实 322][facts-morgan]

官方摄入会把 `[2026-08-10T10:46:00-07:00]` 与该条完整英文原文交给一个新 conversation。Agent 可以读此前已经形成的 Morgan 记忆，处理这条消息，并通过自己的正常机制保留信息。该配置公开的第 3,288 条回应表示已经保存更新后的遛狗要求和当日观察；这证明发布记录中的回应内容，**单独这句话不能证明后台每项写入都已成功**，完成状态还需要冻结收据。[公开摄入记录][morgan-ingestion]

### 2.2 冻结后测试

先处理完 Morgan 的全部 3,400 条历史，再等待后台处理、冻结记忆。测试 002 新开 conversation，并重置模拟应用状态。当前请求的意思是：请给号码 `+14155550187` 的遛狗人发短信，说明 Kibo 明天的最新热天遛狗安排。号码与行动来自当前请求，具体要求需要历史记忆补齐。[题目 002][test002]

```text
完整历史，按顺序逐条进入新 conversation
  └─ 第 003288 条：新热天规则
        ↓ Agent 正常回应、工具调用和记忆处理
Morgan 的完成记忆 → 冻结
        ↓ 新 conversation + 本题初始应用状态
当前请求：给指定号码发明天的遛狗说明
        ↓ 自动注入或主动检索，由该候选决定
send_sms(to=题目给出的号码, body=实际需要发送的说明)
        ↓ 模拟应用返回结果，保留工具日志
检查发送成功 + 收件人正确 + 正文符合三条规则
        ↓ 全部通过才算本题通过
```

公开记录实际调用了 `send_sms`，收件人是题目号码，正文包含 10:30 前出门、错过就跳过而不在中午补遛、发僵时短而平的路线；模拟应用返回 `ok: true`。三项检查均通过，记录的任务延迟为 31.109 秒，单题 Agent 调用成本为 $0.002686。这个成本不含前面整段摄入，不能当作该记忆系统的完整成本。[该配置的测试记录，id 002][morgan-tests]

这份整理后的题目记录没有单列本题的 memory search 调用，不能由此断言 Agent 没有检索；信息也可能在首轮已注入。要解释“哪条记忆通过哪次请求进入模型”，仍需更完整的请求级轨迹。

### 2.3 记忆写入与行动成功是两层证据

同一配置的 **Morgan/001** 是官方论文的咖啡例子。历史早期说过出门早时买 Blue Bottle，当前只要求小杯拿铁自取。公开摄入第 1 条回应提到了 Blue Bottle 习惯；但最终测试记录仍向用户询问去哪家店，两项行动检查失败。不能把摄入时“我记住了”的回应，当成几千条历史之后一定能采取正确行动的证明。[题目 001][test001]、[摄入记录][morgan-ingestion]、[测试记录，id 001][morgan-tests]

还要注意评分覆盖范围：001 的 YAML 检查下单成功和店名 Blue Bottle，并没有单独检查“小杯、拿铁、自取”三个字段。因此，“本题通过”应精确理解为通过该题发布的断言，不能替它扩大成对请求每个细节的完整保证。[题目 001][test001]

## 3. 官方怎样控制上下文、记忆与应用状态

下表综合公开接入契约与 runner 实现。**fresh conversation 清掉本次模型对话，不清掉同一人物此前累积的记忆。** 应用状态、持久记忆、活动上下文是三种不同状态。[接入契约][contract]、[交互类型][adapter]、[runner][runner]

| 时点 | 模型对话 | 持久记忆 | 模拟应用 |
| --- | --- | --- | --- |
| 人物开始 | 新 conversation | 每个 persona、每个配置从独立空状态开始 | 从该人物 baseline 初始化 |
| 每条历史消息 | 再开新 conversation，只发送这条带日期的用户消息；允许 Agent 自行回应和调用工具 | 跨消息累积，走正常写入钩子；必要写入要被计入完成状态 | 当前公开 runner 为该人物摄入共用一份可变状态，逐条延续；每次重开 MCP 连接不等于清空状态 |
| 全部历史结束 | 不把最后活动对话当测试上下文 | `freeze` 等待后台工作并持久化，记录内容哈希或快照身份 | 摄入状态不直接成为每道测试的世界 |
| 每道测试 | 新 conversation、隔离 runtime | 从同一完成快照检索，阻止写入、删除和自动 capture；不能只靠提示词要求“不写” | 按该题初始状态重置；下一题再次重置 |

官方 reference 文档明确：**历史的年月日放在消息文本里，实际摄入用运行当时的处理时钟，可能持续数小时或数天；并不模拟数年的 provider 时间流逝。** 所以，某系统的每日维护、静默期或过期机制究竟触发多少次，会受运行时长影响。这与本仓 LongMemEval 已采用的模拟时间回放有实质差别。[Reference 评测说明][canonical]

测试允许使用完成后的记忆，不允许从 benchmark 文件、facts、评分标准、未来测试、控制程序日志中偷看材料。保留本系统正常的历史检索能力与把整个 benchmark 目录开放给文件工具，也是两回事；必须披露冻结物里到底保存了文档记忆、原始会话数据库还是两者。[Reference 隔离说明][reference-readme]、[Hermes profile][hermes-profile]

## 4. 不同 harness 的具体接线

### 4.1 共同接口：保留自己的 Agent，接入官方模拟工具

公开模板已经负责启动本地 MCP 子进程、发现工具和关闭连接。适配器收到 `request.apps` 提供的命令、参数、环境，再把工具定义转为自己模型的格式。模型选中工具后，调用 `call_app(name, arguments)`，把真实返回结果交回模型。已有 MCP 管理能力的 harness 可直接注册该 stdio server，不应同时再开第二套连接。[模板][template]、[MCP 连接示例][mcp-connection]

```text
DolphinBench 控制程序                 参测方 harness
用户历史 / 测试请求 ───────────────→ 原生接收入口、模型与 Agent loop
                                       ├─ 自己的记忆工具 / 自动钩子
模拟 MCP 工具定义 ─────────────────→ └─ 模型选择应用工具
模拟应用与本题状态 ←── 工具名、参数 ───────┘
模拟工具结果 ─────────────────────→ 继续推理、后续动作、最终回应
工具日志 + 完整交互 ←─────────────── 保存证据后由官方 grader 评分
```

自己的 system prompt、记忆说明和工具可以保留，但必须记录实际模型看到的版本。模拟工具不要求原 harness 已经内置 Gmail、日历或短信技能；接入层提供相同的工具能力与调用通道。替换成真实邮箱或短信服务会改变环境，也超出这套模拟评测的边界。

五个公开接线点分别负责版本身份、一次交互、冻结、核对冻结物和阶段总成本。最重要的是 `run_agent` 必须返回真实完整交互：system/developer、检索上下文、assistant、工具调用和模型实际看到的工具结果；每条 assistant 使用 API 报告的 usage，不能平均摊派总 tokens。模型设置或工具定义变化时，要在对应回应附上完整设置。[交互类型][adapter]、[导出校验][submission]

当前公开导出格式有一个明确限制：**不能表示成 append-only conversation 的上下文改写不受支持。** 因此，有删改消息、压缩、换窗或内部模型调用的 harness，需要先证明导出覆盖实际请求；不能把多次不同上下文拼成一条看似完整的聊天。官方示例也坦承，部分历史轨迹只有聚合 usage，不能转换成完整逐回应证据；内部辅助调用的成本覆盖仍需真实审计。[接入契约][contract]、[Hermes 示例的已验证范围][hermes-example]

### 4.2 官方 Hermes、Claude Code 并非共用一个简化循环

| 接入路径 | 历史怎样处理 | 测试怎样读记忆和接工具 |
| --- | --- | --- |
| Hermes Built-In | 建独立 profile，依次用 Hermes 处理消息，生成自己的回应与原生记忆 | 每题从冻结 profile 建副本，打开只读标志；保留 memory、session_search 与 CLI 工具，另接 DolphinBench MCP |
| Hermes + Mem0 / Honcho / Hindsight / Supermemory | 由该 harness 的对应 provider 集成处理；各组合单独摄入，不能共用另一个模型产出的种子记忆 | 正常检索入口继续工作，关闭测试写入；还需 provider 完成检查和服务快照 |
| Claude Code Built-In | 每条消息以新的 CLI session 运行，使用隔离的 `auto-memory` 目录；原生记忆树单独封存，不打包认证和旧 session 文件 | 恢复到新配置目录；驱动有 `seed` 与 `read_only` 模式，原生目录读写工具范围随阶段变化 |
| Claude Code + Mem0 / Honcho | 调用官方插件摄入，保留该插件的完成与中断恢复检查 | 通过插件检索与指定 MCP 配置接模拟应用；冻结物、插件和服务身份要与摄入对应 |

依据分别是 [Hermes adapter][hermes-adapter]、[Hermes profile][hermes-profile]、[Claude 原生与插件摄入][claude-memory]、[Claude driver][claude-driver]、[Reference 代码说明][reference-readme]。这些是官方保留的实现路径；当前源码本身不能证明历史每次运行都用了最新路径。

“保留 harness”也不表示任何配置都完全原封不动。例如 Hermes reference 写了说明人物身份的 `SOUL.md`、固定工具集和 memory provider；Claude driver 明确控制 CLI session、MCP 配置与原生文件工具范围。比较结果时必须保存这些配置。[Hermes 身份提示][hermes-soul]、[Hermes profile][hermes-profile]、[Claude driver][claude-driver]

Hermes Built-In 参与者示例还需要固定上游代码和一份评测 patch，不能被描述为任意最新版 Hermes 安装即复现。该示例列出的评测 commit 是 `b115aeaf34a44a85742e53b3568741f042e34776`，摄入 commit 是 `c90cc022bb15c60cb70361bba128e61dd5857a10`；文档只把它当一条已做本地检查的接入样例，尚未证明新公开 runner 的付费全流程复现。[示例身份文件][hermes-identity]、[示例限制][hermes-example]

## 5. 成功、分母、预算和重试分别怎么算

### 5.1 得分来自行动断言

本次扫描的 600 题全部采用 `tool_trace`，总计 1,920 条断言；其中 585 题至少含一条 `field_llm_judge`。这是当前 YAML 的计数，不能套用源码注释里较早的“约 75% 题目使用 judge”。[发布题集与文件哈希][manifest]、[判定实现][explicit-grader]

- 精确值用确定性比较，例如 `ok`、号码、日期或工具调用次数。
- 允许等义表达的字段交给语义 judge，例如短信正文是否完整表达新规则。
- 同一个 `action_id` 的要求必须由**同一次调用**满足，不能拿一封邮件的收件人配另一封邮件的正文；两个独立动作也不能共用同一次调用。
- 一题所有必要检查都通过才得 1，否则得 0。检查通过率可诊断局部问题，但不是主榜任务准确率。[断言执行与动作匹配][explicit-grader]

正式提交分母是全部 **600 题**，每人物 200 题，包括失败；不允许只统计执行成功的部分。参与者导出要求完整题号、顺序、对话、设置、usage 和评分证据；遇到未完成的基础设施或 judge 错误，应恢复完成或报告不完整，不能悄悄把题从分母删掉。[提交校验][submission]、[运行与提交网页][run-page]

每题发布前的“有来源历史两次成功、无历史两次失败”是**题目认证**，用来筛除不依赖记忆或明显不可解的题，并不是参测候选答两次取最好成绩。它也不保证所有模型都不可能猜对无历史题。[构造与认证][methodology]

### 5.2 需要分开记录的预算

| 项目 | 核验到的设置或要求 |
| --- | --- |
| Hermes / GPT-5.6 Luna 公开配置 | Azure Foundry，high reasoning，`context_length=1,050,000`，`max_turns=60` |
| Hermes / MiniMax M3 公开配置 | OpenRouter，high reasoning，`context_length=1,048,576`，`max_turns=60` |
| Claude Code / Sonnet 5 公开配置 | medium reasoning；公开简表没有给出与 Hermes 等同的统一 token/turn 限额，不能据此补成相同预算 |
| 公开 participant runner 的 judge | 固定 Azure `gpt-5.6-sol`、medium；评分模块默认最大输出 8,000 tokens，需记录实际设置 |
| Agent 重试 | harness 自己负责；公开 runner 不把一次有效失败答案再送去“重答取优” |
| judge 重试 | 默认针对网络/限流等传输异常最多重试 5 次；语义判定失败不是重试理由 |

配置来源：[Luna][config-luna]、[MiniMax][config-minimax]、[Claude][config-claude]、[runner 固定 judge 检查][runner]、[judge 实现][judge]。部署名是这些实验记录的标识，不应推断任何账户现在都能调用同名服务。

具体重试并不只有一层。例如当前 Hermes profile 配置了 `api_max_retries=8`，并允许限流继续等待；公开 Built-In adapter 还有默认 3 次暂时故障重试，摄入仅在确认未送达时重试，测试重试重置应用状态。断线后恢复与答错后择优必须分开，并保存每次尝试的消耗和是否已经产生动作。[Hermes profile][hermes-profile]、[Built-In adapter][hermes-adapter]

公开 `ingest/evaluate` 命令默认处理完整历史与全部测试，没有替用户自动选小样本的统一美元上限。完整范围意味着 13,539 次历史交互加 600 次测试交互；每次交互又可能包含多次模型与工具调用。准备、冻结和后台记忆处理也可能产生大量成本，不能只按 600 次问答估算。[runner][runner]、[接入契约][contract]

官方成本口径是**摄入 + 测试的 Agent 与记忆处理费用**，含重试和已完成后台工作，不含 judge 与基础设施；延迟报告所有人物单题执行的中位数。订阅摊销、本地算力和外部服务标价仍应另行说明。[成本接口][adapter]、[成本契约][contract]、[公开成绩][results]

### 5.3 官方分数只适用于对应组合和记录

以下选三条公开结果展示“同一个记忆品牌”与“同一套被测系统”的区别；本次没有复现这些成绩。

| harness / 模型 / 记忆 | 成功任务 | 总成本 | 任务延迟中位数 |
| --- | ---: | ---: | ---: |
| Hermes / GPT-5.6 Luna / Built-In | 394 / 600 | $61.48 | 44.4 秒 |
| Hermes / GPT-5.6 Luna / Mem0 | 424 / 600 | $96.21 | 37.7 秒 |
| Claude Code / Claude Sonnet 5 / Mem0 | 194 / 600 | $1,830.57 | 42.3 秒 |

以上来自固定版本的 [官方结果目录][results]。跨行差异不能单独归因给记忆存储：模型、harness、提示、摄入回应和调用预算均可能不同。

**官方材料有版本口径不一致，阅读时要回到实际结果。** 当前结果目录有 13 个组合：两个 Hermes 模型各五种记忆，Claude Code 三种。`CANONICAL_EVALUATION.md` 开头仍称三个 harness/model 组合均配五种记忆；论文 v1 Table 2 则未列结果目录里的 MiniMax/Supermemory 行。不能把这些概括自动转成“15 个已发布且同条件复现的成绩”。[Reference 概括][canonical]、[论文 Table 2][paper]、[实际结果目录][results]

## 6. 一个公开第三方实例：AtMem 为什么不能直接横排比较

AtMem 发布了 2.3.10b1 + Hermes + GPT-5.6 Luna 的 **390/600，65.0%** 自测结果，附完整提交 ZIP、逐题结果和校验报告。核验时 PR #10 仍处于 Open，作者标为 self-tested / unverified；通过本地格式与保存判分复核，不等于被维护者批准为协议等价或独立复现。[AtMem 固定结果][atmem-results]、[提交 PR][atmem-pr]

与官方推荐摄入方式最相关的区别是：报告声明采用本地 `source-episode` 摄入，并复用较早实验的冻结记忆。当前公开适配代码的该分支，直接将原 `dated_message` 交给 AtMem 产品的 `observe`，以 interaction ID 作为 session/observation ID，等待产品的 `processing_complete`；返回一条固定的记录确认和零模型 tokens，**没有在这一分支调用 Hermes 来为每条历史生成正常回应或应用行动**。[AtMem 适配代码][atmem-adapter]

```text
官方推荐路径：
历史 user → 原生 Agent 回应 / 工具 / 记忆钩子 → 完成记忆 → 新任务

AtMem 报告声明的 source-episode 路径：
历史 user → 产品 observe 存为来源经历 → 完成记忆
          → 测试时由 Hermes + 检索 / 证据发现执行任务
```

它仍然是在真实产品 API 中处理原始历史，并非人工摘取 gold 事实；但它测到的摄入过程不同于“让一个完整 Agent 在线经历所有历史请求”。这也说明别人的接入确实需要设计格式和事件映射，不能因为使用同一题集就假定处理了同样的 assistant/tool 轨迹。

AtMem 的测试报告使用 high reasoning、60 turns、1,050,000 configured context；reader 经订阅/OAuth 通道，judge 经 OpenRouter 的 Azure-only routing。其结果文件披露沿用旧摄入、公开题子集参与开发、未跑匹配的竞争系统对照。报告中的 Agent 增量 API 现金为 $0，原因是本地摄入与订阅额度，不是订阅、算力和电力免费。[AtMem 方法卡][atmem-card]、[固定结果及成本解释][atmem-results]

该案例的证据上限需要保留：本次读取了报告与适配源码，没有下载验证完整 ZIP，也没有核对所有历史运行 source hash 是否恰好等于当前代码 commit；不能把代码中存在的所有检索选项都归到 390 分那次运行。报告还披露 Morgan/129 的独立应用日志丢失，使用保留的原生对话恢复评分且未重跑 reader。是否接受这种摄入与恢复方式，仍由 DolphinBench 维护者裁定。[固定结果 recovery 字段][atmem-results]、[提交 PR][atmem-pr]

## 7. 对 Nano 的适配启示：可以复用隔离设施，不能复用错误的经历模型

本仓现有 LongMemEval 实现把固定 user/assistant 历史导入同一 Global 的原生窗口，按模拟时间整理，再恢复隔离环境回答问题；`nano-product.ts` 的真实 PA 接收、聊天查询与发送回执，为产品路径提供了接线基础。DolphinBench 尚未接入这些路径。[本仓协议](../../../../evals/memory/README.md)、[产品接线](../../../../evals/memory/nano-product.ts)、[运行环境接线](../../../../packages/dsh-integration/src/evaluation.ts)

后续可以讨论以下六项，均不是本次已批准设计。

| 待决定的边界 | 根据本次研究提出的适配方向 |
| --- | --- |
| 历史如何进入 | 每个人物建立独立 Nano 身份与记忆空间，逐条走真实接收与回应；不能沿用静态双方导入，不能替 DolphinBench 人工补 assistant 消息 |
| fresh conversation 如何映射长期 Global | 保留人物与记忆身份，但每条消息隔离活动上下文；“新窗口”是否会通过原 History 自动恢复旧上下文，要单独核对，不能只换 window ID 就宣称满足规则 |
| 原生 Inbox 如何导出 | 官方 validator 要求唯一 user 消息等于 `dated_message`；Nano 让正文通过 Inbox 进入模型。需要先验证忠实表示，不能把模型实际见到的 tool 结果伪装成直接 user 输入来满足校验；不兼容时先标 internal adaptation 并与维护者讨论 |
| 时间与 Dreaming | 官方是带历史日期的真实处理时钟，本仓 LongMemEval 是模拟时间。应单独选择和标识 DolphinBench 协议；若加速多年维护时钟，不能仍声称完全遵从官方时间条件 |
| 工具行动与冻结 | 通过已允许的 DSH 公开接线注册官方模拟 MCP；记忆写入、自动 Dreaming 与删除要在测试时真正被阻断，应用每题重置，自己的真实聊天/工具轨迹按所选政策封存 |
| 完整请求与成本证据 | 保留 Nano 实际角色提示、Inbox 包装、工具定义/返回、检索内容、换窗与内部调用的证据；先检验能否诚实导出为官方格式，记录 Agent 和后台记忆成本，不只记录最终回复 |

其中“能否检索封存原聊天”也要明确：DolphinBench 接纳 harness 的正常记忆检索，Hermes 配置保留 `session_search`，并没有统一规定只许读压缩笔记。Nano 若允许 `conversations` 查本次自己经历形成的聊天，应将其列为被测组合的一部分，记录查询实际返回；不能借此开放控制目录里的全量题集和标注，也不能把这一成绩称为纯文档记忆效果。[Hermes profile][hermes-profile]、[隔离说明][reference-readme]

如果后续进入实施，最先有价值的是两类离线证明：一条消息是否忠实经过原生接收、回应记录和模拟工具路由；两道测试是否真正共享同一冻结记忆而互不污染。这些检查可以用确定性回应，不需要立即花费全量模型预算。是否执行真实历史摄入、样本范围和费用上限，留待逐项方案确认。

## 8. 目前可以确认和仍不能确认的范围

这套 benchmark 适合观察“长期经历中的信息是否影响后续工具行动”，但它目前先完整摄入再统一测试，应用是模拟的，任务通常只含少数独立动作；不能凭一次分数证明持续生产中的并发新消息、外部服务故障、真实支付或长工作流已经可靠。论文也列明了这些限制。[论文 §5][paper]

本次已经核对数据结构、实际题与公开运行片段、官方 driver/评分代码、官方 reference 配置和一个第三方接法。仍未证实的是：任何成绩的独立重跑；新公开 runner 的付费端到端可用性；全部历史运行与当前公开源码的逐文件一致性；AtMem 提交的正式接受状态；Nano 的 Inbox、换窗与内部调用是否能被现有公开提交格式无损表达。后续讨论应围绕这些具体缺口，不把“工具能接通”当作整个协议已经兼容。

## 来源与版本

除网页、论文和 PR 状态外，下列官方代码链接均固定在 `81cb6f8405b40a9e76089cef650806a80af06ea2`。数据全量扫描仅解析文件，没有运行其中的 Agent、工具服务或 grader。三个历史文件的 SHA-256 与该 commit 的 `manifest.files` 一致：Morgan `4ece5cdf45d89e0d12ac9c76871f6362e32cc185eca68e2c1016244006873356`；Alex `e3426b5094e9f2f1adc2c60883ec0eca33c7120a4fa7b8d8f11cad90ce862c18`；Riley `3d7928715e1229fee16b653ec114c2eb0903831ecdc90513614ced91cf21a9b6`。

| 来源 | 固定版本或核验范围 |
| --- | --- |
| 官方仓库、历史、题目、评分与公开结果 | commit `81cb6f8405b40a9e76089cef650806a80af06ea2` |
| 论文 | `2609.24971v1`；和仓库结果目录的行数差异见 §5.3 |
| [AtMem 结果][atmem-results] | HF revision `5ef528c499aa26b765fff9d8ed8f2c2e6ee52912`；报告运行日期 2026-10-22 至 23 |
| [AtMem 适配代码][atmem-adapter] | commit `9769fcac2a48905fe21be22a0d292a128402fcf4`；是公开代码观察，不是已证明对应历史运行的完整 source bundle |
| [AtMem PR #10][atmem-pr]、[官方运行网页][run-page] | 2026-11-01 浏览核验；状态与网页可能后续变化 |

[official-readme]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/README.md
[manifest]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/manifest.json
[history-morgan]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/registry/personas/morgan/life_sim.yaml
[history-alex]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/registry/personas/alex/life_sim.yaml
[history-riley]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/registry/personas/riley/life_sim.yaml
[facts-morgan]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/registry/personas/morgan/facts.yaml
[test001]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/tests/morgan/001.yaml
[test002]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/tests/morgan/002.yaml
[morgan-ingestion]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/results/hermes/gpt-5.6-luna/mem0/morgan/ingestion.json
[morgan-tests]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/results/hermes/gpt-5.6-luna/mem0/morgan/tests.json
[methodology]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/docs/methodology.md
[contract]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/docs/DRIVER_CONTRACT.md
[canonical]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/docs/CANONICAL_EVALUATION.md
[reference-readme]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/reference/README.md
[template]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/examples/harness_template.py
[mcp-connection]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/examples/mcp_connection.py
[adapter]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/harness/adapter.py
[runner]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/harness/runner.py
[submission]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/harness/submission.py
[hermes-adapter]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/harness/adapters/hermes.py
[hermes-profile]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/harness/adapters/hermes_profile.py
[hermes-soul]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/harness/benchmark_soul.md
[hermes-example]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/examples/reference/README.md
[hermes-identity]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/examples/reference/hermes-builtin.json
[claude-memory]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/reference/runtimes/claude_code.py
[claude-driver]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/harness/claude_driver.py
[explicit-grader]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/graders/explicit.py
[judge]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/graders/llm_judge.py
[results]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/results/README.md
[config-luna]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/results/hermes/gpt-5.6-luna/mem0/configuration.json
[config-minimax]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/results/hermes/minimax-m3/mem0/configuration.json
[config-claude]: https://github.com/mem0ai/dolphinbench/blob/81cb6f8405b40a9e76089cef650806a80af06ea2/results/claude-code/claude-sonnet-5/mem0/configuration.json
[paper]: https://arxiv.org/html/2609.24971v1
[run-page]: https://dolphinbench.ai/run/
[atmem-card]: https://huggingface.co/datasets/atmem/atmem-2.3.10b1-dolphinbench/blob/5ef528c499aa26b765fff9d8ed8f2c2e6ee52912/README.md
[atmem-results]: https://huggingface.co/datasets/atmem/atmem-2.3.10b1-dolphinbench/blob/5ef528c499aa26b765fff9d8ed8f2c2e6ee52912/results.json
[atmem-pr]: https://github.com/mem0ai/dolphinbench/pull/10
[atmem-adapter]: https://github.com/aetna000/atmem/blob/9769fcac2a48905fe21be22a0d292a128402fcf4/benchmarks/dolphinbench/adapter.py
