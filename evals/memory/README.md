# LongMemEval memory evaluation

本套件把完整历史交给候选系统的记忆机制，封存状态后，用冷上下文回答原问题，再按 LongMemEval 官方规则评分。默认命令只生成计划，**不会调用候选模型或 judge**。首期实现只完成确定性机制验证；没有正式 LongMemEval 分数。

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

## 确定性自检

```sh
pnpm exec vitest run evals/memory packages/dsh-integration/tests/evaluation-runtime.test.ts
```

这些检查使用合成材料、本地 HTTP 响应和固定 provider 响应。Nano 集成检查启动锁定版本的真实 DSH，经过公开原生持久化、现有记忆服务、文件工具、冷启动和本地 `send_message` 交付；不会连接生产 IM 或真实模型。它们证明接线、保真、隔离、预算与报告机制，不能证明真实模型的记忆质量。

## 准备一次真实运行

1. 从 [LongMemEval cleaned](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned) 获取需要的 JSON 文件，先选 S 的少量完整题目。将数据、配置与产物放在仓库外；本套件不会下载数据或默认选取全部题目。
2. 复制 `examples/plan.json` 到控制目录，填入数据路径、明确 revision、文件 SHA-256、候选模型与 judge 的 OpenAI-compatible `/v1` base URL、模型名和凭证环境变量名。配置中的路径相对于配置文件；凭证只从命名的环境变量读取，不写入 JSON。
3. 创建非空 JSON ID 数组，例如 `["原始题目ID"]`。使用完整样本，不能根据 `answer_session_ids` 或 `has_answer` 选段、删回合或缩短历史。
4. 明确每阶段的 `timeoutMs`、`maxModelCalls` 和每次请求的 `maxOutputTokens`。候选另外固定当前 Dreaming 的 `maxInputTokens`。新版 Dreaming 已移除自身的 `maxSteps` / `maxRunMs`，旧评测配置须删除这两项；准备阶段的外部评测限额仍有效，耗尽会报告 `incomplete`。
5. 运行 `plan`，检查题集规模、配置和限额，再决定是否执行。读取器当前读取一个完整 JSON 数组，内存须足以容纳数据文件；不会暗中截断超大文件。

**下列命令会花费模型预算。本轮开发没有执行它。**

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
| `candidate-data/` | 每题独立的准备环境、封存状态与每次独立答题环境；包含原生历史、实际模型请求、来源映射、维护回执、拒绝访问记录与进程日志 |

`accuracy` 只以有效评分题为分母；`correctPerPlanned` 以全部计划题为分母，同时展示未完成准备、准备失败、答题失败、judge 失败与未评分数量。失败不能悄悄从分母移除。用量按阶段记录；输入/输出 token 或费用不可得时写 `null`，不能把它当零费用。请求数量和每次输出有上限，输入 token 与实际费用是观察值，并非精确计费硬上限。

`protocolId` 由数据版本/内容、题集、输入规则、冷上下文规则与固定评分规则确定。`candidateId` 另包含产品 commit、实际构建字节、锁文件、候选模型/记忆配置及准备和答题限额。改记忆实现时沿用前者，比对后者；应重新构建后再计划和运行。

## 边界与维护位置

- `dataset.ts`、`runner.ts`、`judge.ts` 不读取 Nano 记忆目录，不依赖 DSH、Dreaming 游标、批次数或存储介质。稳定协议类型在 `packages/product-contracts/src/memory-evaluation.ts`。
- `nano.ts` 只在显式运行时加载 `@nano/dsh-integration/evaluation`；当前 Nano adapter 负责历史的 `inbox` / `send_message` 原生映射、先空基线后导入、真实记忆准备和完成判定。
- 当前文档候选封存整个记忆目录及必要的文档版本/来源状态。冷答题使用新的 runtime、workspace 与 session，只能读准备后的记忆；旧 session、Inbox、维护输入、控制文件和旁路历史工具不可达。
- 当前 adapter `nano-document-memory-v2` 对接 feat-676 的连续原文 Dreaming：准备阶段保留原生 `source_history` 补查与维护自身的 `notes/history/new_context` 恢复能力；这些维护记录不复制到答题环境。仅在产品报告无待处理增量后返回 `ready`，不以某一批完成代替全部准备完成。
- LongMemEval 提供双方对话，没有子任务执行轨迹；本候选按 Global 历史导入，不伪造第一层任务。因此这里评测新版记忆对这些对话的处理效果，子任务提炼仍由产品自己的测试验证。评测不连接独立 IM 服务，`conversations` 补查不开放；原生 `source_history` 可回查本题已导入的合格原文。
- 上述工具隔离针对候选模型的访问入口，不宣称是操作系统沙箱。评测插件是受信任宿主代码，不能添加未经审查的插件或执行工具后仍沿用本协议的隔离结论。
- 候选以后可改用数据库、向量库、知识图谱或原文索引。只要保存/恢复仍满足相同接口和信息边界，就无需改题集、评分或 Runner；产品接线变化由 adapter 承担。
- 历史时间按原 session 精度保存，同日保留原顺序；未标时区的日期解释为 UTC。未来问题和 `question_date` 只在答题阶段出现，答案标注只供控制区使用。
- 官方 judge 原文保存在 `judge-prompts.json`，源 blob 为 `4732f3772b04a2b9069121ade304e6320494abc2`；保留题型规则和 `yes` 子串判断。许可见 `LICENSE.longmemeval`。公开集用于可复现回归，不声称排除了训练污染。
