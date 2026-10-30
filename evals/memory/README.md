# LongMemEval memory evaluation

本套件按会话时间逐步把完整历史交给候选系统的记忆机制，等待已触发的处理结束并封存状态后，用冷上下文回答原问题，再按 LongMemEval 官方规则评分。默认命令只生成计划，**不会调用候选模型或 judge**。首期实现只完成确定性机制验证；没有正式 LongMemEval 分数。

理解官方和业界怎样使用这套题，先读 [LongMemEval：官方基线与业界评测方法](longmemeval-methods.md)。其中包含商业产品、多会话记忆、全文输入与检索的具体例子，以及影响分数可比性的设置；本页负责本仓实际运行协议。

## 先看计划

在仓库根目录使用项目要求的 Node 与 pnpm。首次安装、构建：

```sh
pnpm install --frozen-lockfile
pnpm --filter @nano/dsh-integration... --filter @nano/personal-assistant... build
```

以下例子只有一题合成材料，模型地址是不可用的本地占位符。命令仅检查输入和展示计划，可直接运行：

```sh
pnpm memory-eval --config evals/memory/examples/plan.json --ids evals/memory/examples/ids.json
```

输出包含计划题数、会话数、消息数、阶段限额、数据 SHA-256、`protocolId` 和 `candidateId`，以及 `modelCallsStarted: 0`。`--output /absolute/path/plan` 可另存 `plan.json`；不传 `run` 就不会执行模型。计划不输出历史正文、问题或 gold，也不读取凭证值。

## 时间回放与冻结

只提供一套协议：按时间线摄入 → 候选按正常规则自动整理 → 等待已触发工作完成 → 冻结记忆 → 冷答题。

- 回放从首段历史推进到末段历史；未来问题及 `question_date` 不进入准备环境，也不用于决定整理时点。没有到达的会话正文不会提前落入候选历史。
- 同一时间的会话按原顺序一起到达，再判断自动准入；如果消息恰逢周期边界，新活动会参与静默条件计算。会话内没有逐消息时间时按会话整体到达，不编造消息间隔。无时区日期按 UTC 解释，原日期字符串保留。
- Nano 使用产品自身的周期、静默与资源准入规则，默认周期 24 小时、静默 10 分钟；`candidate.dreaming.intervalMs` / `quietMs` 可以显式配置，plan 会显示实际采用的数值。适配器推进逻辑时钟，不修改全局 Date 或真实超时计时器。
- 每次整理结束后再推进逻辑时钟；模型处理的真实耗时单独计量，不转换成额外经历时间。这里验证会话级顺序积累，不模拟真实前台/后台耗时竞争。
- 最后只等待已经启动的工作，不手动清空积压、不跳到未来强制启动下一周期。`prepare=ready` 表示完整导入、已触发工作成功结束且记忆已封存；收据中仍可有尚未到期的 backlog。尚无任何周期到期时，可以封存初始空记忆，准备阶段零模型请求。
- 已触发处理失败或超限会停止本题，分别报告 failed/incomplete；不会用之后的模拟时间自动重试，或把这类失败当成正常未触发积压。

时间回放使用 protocol version 2、Nano adapter v5。每题只有一个 Global、一个持久 session 和一个主人聊天目标；每段数据集会话到达时成为这个 session 的一个原生 window。未来窗口不预建，换窗不重置记忆游标、不额外触发 Dreaming；上一窗正文离开活动上下文，但仍能通过 History 按窗口读回。不生成数据集未提供的业务摘要或 Notes。这个固定分段约定不代表验证了产品按 token 压力自动换窗。旧 v3 多根历史构造及更早的集中导入产物保留原身份，不能作为当前候选的运行或成本基线。通用 Runner 仍只认识 prepare/answer/close；具体时钟与维护接线由候选适配层负责。

## 与真实 PA 的一致性及保留差异

冷答题的接收、唤醒消息、Inbox 的 `sources` / `delivery` / `conversation_type` / `sender.is_owner`、分页与消费、回复前重核及实际发送回包，均经过现有 PA 实现。问题正文只通过 Inbox 进入，基准题号只留控制区；`question_date` 保留为问题的原时间。首请求使用产品正常角色规则、有效文档记忆入口和技能目录，不另写评测答题提示词。

`nano-memory` 可正常发现、加载和读取随包资源。答题自己的 `notes/history/new_context/get_context_remaining` 可用，换窗后可恢复这次答题；它们不能读取准备 runtime 的旧窗口和维护笔记。普通文件工具只读封存记忆与随包技能，生产目录、控制资产、其他题和原始历史仍不可读。

以下是明确保留的评测条件，不能据此宣称完整产品链路验收：

| 部分 | 保留差异及原因 |
|---|---|
| 原始经历 | 数据集双方文本按已确认的固定原生窗口导入，带原时间/来源映射；没有真实前台执行、子任务轨迹或自动压力换窗。 |
| 冷上下文 | 保留关系和 session 标识，去掉原活动历史、原 Inbox 及维护恢复状态，避免绕过待评测的记忆。 |
| 聊天服务 | PA 代码真实运行；IM transport 由单一私聊的本地适配器承接，不连接公网 IM，不开放其他聊天、创建/加入群或来源变更。`conversations` 只能读本次问答，回复落本地回执。 |
| 能力与限额 | 不加载私人技能；答题不启动 Dreaming、Task、定时任务或 Heartbeat。可见的当前上下文工具与内部委派沿原生路径运行，所有模型请求共享阶段限额；普通文件读受上述隔离约束。 |
| 时间与资源 | 历史按 session 精度推进逻辑时钟，问题保留原日期；执行时长、取消和外部请求限额使用真实时间。实验目录可见，但阶段名称不再充当 Agent 身份。 |

v5 改变的是 Nano adapter，通用 protocol v2 不变。旧 v4 轨迹、配置及封存文件保持原样，不能仅改名后当成新候选证据；后续真实复跑须生成新 run。本轮确定性接线通过不等于真实模型分数改善。

## 确定性自检

```sh
pnpm exec vitest run evals/memory packages/dsh-integration/tests/evaluation-runtime.test.ts
```

这些检查使用合成材料、本地 HTTP 响应和固定 provider 响应。Nano 集成检查启动锁定版本的真实 DSH，经过公开原生持久化、现有记忆服务、文件工具、冷启动和本地 `send_message` 交付；不会连接生产 IM 或真实模型。它们证明接线、保真、隔离、预算与报告机制，不能证明真实模型的记忆质量。

## 准备一次真实运行

1. 从 [LongMemEval cleaned](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned) 获取需要的 JSON 文件，先选 S 的少量完整题目。将数据、配置与产物放在仓库外；本套件不会下载数据或默认选取全部题目。
2. 复制 `examples/plan.json` 到控制目录，填入数据路径、明确 revision、文件 SHA-256、候选模型与 judge 的 OpenAI-compatible `/v1` base URL、模型名和凭证环境变量名。配置中的路径相对于配置文件；凭证只从命名的环境变量读取，不写入 JSON。
3. 创建非空 JSON ID 数组，例如 `["原始题目ID"]`。使用完整样本，不能根据 `answer_session_ids` 或 `has_answer` 选段、删回合或缩短历史。
4. 明确每阶段的 `timeoutMs`、`maxModelCalls` 和每次请求的 `maxOutputTokens`。Dreaming 的 `maxInputTokens` 为可选材料上限；省略时使用产品按模型容量计算的首轮完整输入预算，不再由示例强制覆盖为 24K。显式数值仍生效，并与计划中解析出的 `intervalMs` / `quietMs` 一起记录。新版 Dreaming 已移除自身的 `maxSteps` / `maxRunMs`，旧评测配置须删除这两项；准备阶段的外部评测限额仍有效，耗尽会报告 `incomplete`。
5. 运行 `plan`，检查题集规模、配置和限额，再决定是否执行。读取器当前读取一个完整 JSON 数组，内存须足以容纳数据文件；不会暗中截断超大文件。

**下列命令会花费模型预算；只对已明确选择的题目和阶段限额执行。**

```sh
pnpm memory-eval run --config /absolute/path/config.json --ids /absolute/path/ids.json --output /absolute/path/new-run --allow-model-calls
```

输出目录每次使用新位置；已有 manifest 会拒绝覆盖。一次只执行一题，依次准备记忆、答题、清理候选环境、评分。没有自动重答、自动重评或自动恢复全量跑量。中断后未开始的题保持 `not_run`；重跑候选需使用新 run，旧记录继续保留。`Ctrl-C` 停止当前候选并防止开始后续题。

只有 judge 失败时，可以对已经保存的回答补评分：

```sh
pnpm memory-eval score --output /absolute/path/existing-run --allow-model-calls
```

该命令使用 manifest 中冻结的 judge 配置；不重新启动候选、不修改原回答、不覆盖历史评分尝试。改 judge 模型、规则或题集应产生新协议，不能混用旧分数。

## 报告与证据

| 产物 | 内容 |
|---|---|
| `manifest.json` | 固定协议、候选配置、源 commit/dirty 状态、实际运行时构建 hash、依赖锁 hash、题目清单、限额 |
| `gold.json` | 控制区独立评分材料；不传给候选 |
| `report.json` | 所有计划题目的 prepare/answer/score 状态、评分尝试、用量和证据位置 |
| `answers.jsonl` | 官方兼容 `question_id/hypothesis` 原始交付答案；按实际发送顺序保留所有公开回复 |
| `candidate-data/` | 每题独立的准备环境、封存状态与每次独立答题环境；包含原生历史、实际模型请求、来源映射（原段/回合到同一 rootSessionId、windowId 和事件范围）、维护回执、拒绝访问记录与进程日志；准备目录的 `timeline.jsonl` 记录会话到达、自动尝试结果和最终积压，`requests.jsonl` 记录每次请求的逻辑时间和已导入会话数 |

`accuracy` 只以有效评分题为分母；`correctPerPlanned` 以全部计划题为分母，同时展示未完成准备、准备失败、答题失败、judge 失败与未评分数量。失败不能悄悄从分母移除。用量按阶段记录；输入/输出 token 或费用不可得时写 `null`，不能把它当零费用。请求数量和每次输出有上限，输入 token 与实际费用是观察值，并非精确计费硬上限。

`protocolId` 由数据版本/内容、题集、输入规则、冷上下文规则与固定评分规则确定。`candidateId` 另包含产品 commit、DSH 接入及 PA 的实际构建字节、候选接线源码、随包技能、锁文件、候选模型/记忆配置及准备和答题限额。改记忆实现时沿用前者，比对后者；应重新构建后再计划和运行。

## 边界与维护位置

- `dataset.ts`、`runner.ts`、`judge.ts` 不读取 Nano 记忆目录，不依赖 DSH、Dreaming 游标、批次数或存储介质。稳定协议类型在 `packages/product-contracts/src/memory-evaluation.ts`。
- `nano.ts` 只在显式运行时加载 `@nano/dsh-integration/evaluation` 与 `nano-product.ts`；后者组合现有 `GlobalAgent`、`InboxStore`、`NodeStore`。PA 不 import DSH，DSH 接入包通过注入的 product 接口调用 PA，不反向 import PA。当前 Nano adapter 负责历史的 `inbox` / `send_message` 原生映射、先空基线后导入、真实记忆准备和完成判定。
- 当前文档候选封存整个记忆目录及必要的文档版本/来源状态，同时保留同一 PA、主人、常驻私聊和 Global session 标识。冷答题使用新的 runtime/workspace，将该 session 恢复为空活动上下文，先同步来源资格再接收原问题；不新建另一段“评测问题”聊天，也不使用 evaluation-answer 等会话名。旧原始 session 内容、Inbox、维护输入和恢复笔记不复制。
- 当前 adapter `nano-document-memory-v5` 对接 feat-676 的连续原文 Dreaming：准备阶段保留原生 `source_history` 补查与维护自身的 `notes/history/new_context` 恢复能力；这些维护记录不复制到答题环境。按产品自动准入执行；`ready` 仅表示本协议准备和冻结完成，不能解读成 backlog 必然为空。每次已触发的连续分批必须正常结束。
- LongMemEval 提供双方对话，没有子任务执行轨迹；本候选按 Global 历史导入，不伪造第一层任务。因此这里评测新版记忆对这些对话的处理效果，子任务提炼仍由产品自己的测试验证。评测不连接独立 IM 服务；准备阶段原生 `source_history` 可回查本题已导入的合格原文，IM 历史补查不可用。答题阶段的本地聊天适配器只提供当前问题与本次回复的 conversation 信息/读取，不提供准备原文。
- 上述工具隔离针对候选模型的访问入口，不宣称是操作系统沙箱。评测插件是受信任宿主代码，不能添加未经审查的插件或执行工具后仍沿用本协议的隔离结论。
- 候选以后可改用数据库、向量库、知识图谱或原文索引。只要保存/恢复仍满足相同接口和信息边界，就无需改题集、评分或 Runner；产品接线变化由 adapter 承担。
- 历史时间按原 session 精度保存，同日保留原顺序；未标时区的日期解释为 UTC。未来问题和 `question_date` 只在答题阶段出现，答案标注只供控制区使用。
- 官方 judge 原文保存在 `judge-prompts.json`，源 blob 为 `4732f3772b04a2b9069121ade304e6320494abc2`；保留题型规则和 `yes` 子串判断。许可见 `LICENSE.longmemeval`。公开集用于可复现回归，不声称排除了训练污染。
