# Code Review: feat-677

## Round 1

- review_mode: `full`
- executed_base: `51b23e42b`
- validated_at: `97a8b168339fd6dc454537744db152597a3cf0cf`
- branch: `codex/feat-677-memory-evaluation`
- verdict: **pass**
- 范围：上述完整实现 diff 及其受影响的 MemorySources、Dreaming、DocumentMemory、Global 工具和 RuntimeClient 消费链。审查者未参与实现，未修改源码、测试、配置或设计。

## Findings

```json
[]
```

未发现具有具体触发场景及直接证据的存活缺陷。此结论覆盖机制与接口，不表示真实候选模型或 judge 已验证。

## Coverage

- `evals/memory/dataset.ts:53` 白名单拆开 history/question/gold，保留全部双方回合、日期和同日顺序；原题 ID 及 `_abs` 等标注不进入候选输入。`evaluation/history.ts:20` 经公开 persistence 导入合法配对事件，空来源 baseline 先于导入；user 使用 Inbox，assistant 使用 send_message，imported provenance 不冒充本轮网络送达。
- `evaluation/runtime.ts:70` 由真实 Dreaming status/start 处理当前候选准备完成度，不以文件存在或一次维护成功替代全部完成；未完成、阻塞与预算耗尽均有独立状态。框架只依赖 product-contracts 的 prepare/answer/close，未读取 Dreaming 状态或记忆布局。
- `evaluation.ts:91` 每次 answer 启动独立 runtime/workspace/session，复制封存记忆及必要状态后走正常 DocumentMemory 装配。`runtime.ts:45` 在宿主工具入口拒绝旁路；`evaluation.ts:183` 的本地产品服务只提供本题 question 与本地投递，不连接历史 Inbox 或生产 IM。即使 Global 固定基础工具仍出现在 schema，其他操作也被该 guard 拒绝。
- `runtime.ts:24` 在 agent/request 施加输出上限，并在 llm/stream 验证和限制请求数；`evaluation.ts:58,97,120,152` 的阶段定时器、取消与进程组终止负责回收。Runner 的超时清理失败会停止后续题，不把后台环境泄漏隐藏成成功。
- `plan.ts:50` 分别冻结数据/题集/评分协议与产品/实际构建/锁文件/模型及限额身份；`runner.ts:44,78,127` 保留全部计划分母、原回答和历次 judge 尝试。CLI 默认计划零模型调用，run/score 明确 opt-in；score 不重启候选。
- 未修改生产接线或 current 产品行为。suite README 是新增评测协议权威，`docs/README.md` 与 `evals/README.md` 已更新导航；Gateway/PA 的 no spec delta 成立。

## Agent Context Implementation Review — Mode B

触发面：历史物化、时间/身份/来源、准备材料、记忆恢复、答题工具及问题、独立 judge。沿来源→物化→真实来源选择→Dreaming 文件读取→记忆封存→冷上下文→本地公开交付检查。

复用 `progress.md` 在受审实现上的 5 files / 13 tests、相关 package build 和 eval tsc 证据；阅读了全部新增测试及相关现有产品限制。另执行 `pnpm exec tsx /tmp/feat677-review-probe.ts`，使用真实锁定 DSH 与现有确定性 provider fixture，新增 assistant-only 会话、连续 user、中文/emoji/换行，共 3 sessions / 6 messages：prepare=ready、answer=completed。准备阶段 12 次实际 llm/stream 请求包含新增双方原文、长消息尾部与原日期；首请求是 Dreaming 的受限 system/user，工具为 edit/finish/glob/grep/read/write。冷答题 7 次请求未包含这些原历史；问题只在 answer 出现；旧 runtime read 与越界 glob 均被拒绝（deniedTools=2）。最终答案来自实际本地 send_message 回执。

脱敏执行摘要对应现场：`/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/feat677-review-9cAoYH/`，准备请求 `prepare-iF5WJ2/requests.jsonl`，答题请求 `answer-gCbkoG/requests.jsonl`；完整请求仅留本机，不提交。所有候选子进程均经 close 结束。脚本与合成审计材料保留供本轮复查。

证据限制：llm/stream 捕获证明 DSH 组装后、provider 适配前的交付及确定性工具链，不能独立证明 OpenAI-compatible wire 序列化，也不能证明真实模型理解、工具选择或记忆质量。本轮授权禁止真实候选与真实 judge，未运行它们，未下载或跑正式 benchmark；这符合本 unit 明确的交付范围。独立审查未重复全量测试；调用方随后提供的全仓 build/typecheck 与 Python/docs/lint 结果作为补充门禁，不替代上述机制检查。

## Round 2 — 最新父分支适配

- review_mode: `patch`
- executed_base（main merge-base）: `082e72ec4becb37d4ba08c3e3a8e0d2bf45da087`
- effective stacked base: `3e9a46030939bfcce351b7df2e29e5f3c2439055`
- review_diff: `117873fd1..93c8e305bf30de6f0354510f3d9e8eee46b293c1`
- parent_upgrade: `80db8b9a6..3e9a46030`
- validated_at: `93c8e305bf30de6f0354510f3d9e8eee46b293c1`
- branch: `codex/feat-677-memory-evaluation`
- verdict: **pass**

### Findings

```json
[]
```

无确认缺陷。此次只审评测自有增量，并沿父升级影响到的 Dreaming、DocumentMemory、来源物化及上下文恢复检查适配是否完整；未重新审父 PR 全部实现。Round 1 的历史结论保留，涉及旧准备机制的描述以本轮证据为准。

### 增量覆盖

- `evals/memory/plan.ts:14,69` 移除已退役的 Dreaming `maxSteps/maxRunMs` 并更新 candidate adapter 标识为 v2；strict schema 拒绝静默忽略旧配置，README 明示迁移方法。prepare 的外部 timeoutMs/maxModelCalls/maxOutputTokens 不变，实际构建、锁文件、候选模型/记忆配置仍进入 candidate 身份；历史、问题、评分规则和 protocol 计算未改。
- `packages/dsh-integration/src/evaluation.ts:212` 只给 prepare 加入既有 contextTools。父实现 `knowledge/dreaming-agent.ts:35` 通过父工具资格开启维护自身 notes/history/new_context/get_context_remaining；独立业务来源恢复由 `dreaming-history.ts:63` 的 source_history 提供。两者有不同的描述及数据作用域。父级的 sourceDirectory/qualifiedEvents 按可信来源、冻结时间/序号范围过滤；评测仍只导入完整原对话，没有构造子任务。
- `evaluation/history.ts:20` 的公开原生导入和空来源 baseline 接线不变，仍适用于新版根会话连续原文选择；`evaluation/runtime.ts:70` 继续使用真实 start/status，只有最终 backlog=no_eligible_increment 才 ready。父 `dreaming.ts:159-211,330` 已在自身循环中处理连续批次；框架不需要理解新批次或 finish 私有格式。
- 父 DocumentMemory 改为业务 Agent 只读、Dreaming 写正式记忆，评测没有另加写入器或旧 checkpoint 调用。`evaluation.ts:224` 的复制集合仍只含 memory 及 documents.json；父 MemoryDocuments 状态布局在这次父升级没有变化。准备侧的 notes、维护 session、Dreaming 输入和 runtime 数据没有复制给 answer。answer 的工具 guard 与仅本题 Inbox/本地发送服务也未改。
- 新 fixture 在当前产品的 direct input 上执行 source_history、notes/new_context/history、正常文件维护和批次级 finish，不再解析旧逐单元 File list。输入容量降到 1000 使长消息走真实连续批次；扩展的既有主旅程检查成功工具结果和冷答题排除维护笔记。没有把这些实现细节移入稳定 Runner 测试。
- 评测没有独立 IM 服务。实际 Dreaming schema 仍可能包含父级 conversations，但本地产品桥没有 memory.conversations 接线，因而不会获得额外 IM 原文；suite README 明确说明该限制。此处不把工具名出现在 schema 当作已可用的服务证据。

### Agent Context Implementation Review — Mode B（delta）

复用 `/tmp/feat677-sync-before.log` 的兼容性红测：旧 fixture 在新版第一次维护后因 without finish 返回 failed，没有误报 ready。复用 `/tmp/feat677-sync-targeted.log`：`pnpm exec vitest run evals/memory packages/dsh-integration/tests/evaluation-runtime.test.ts`，5 files / 13 tests 通过，包含现有请求上限与挂起 provider 清理。

独立执行 `pnpm exec tsx /tmp/feat677-sync-review-probe.mts`，仅复用本仓确定性 provider，保留可复查现场：`/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/feat677-sync-review-mtuKAl/`。2 sessions / 4 messages、maxInputTokens=1000，prepare=ready，6 个独立 Dreaming 批次合计 66 次 llm/stream 请求，全部 maxTokens=2048。每批实际工具结果均证明 source_history 查询成功返回原长消息尾部、notes 恢复 EVALUATION_RECOVERY、history 返回自身旧窗口。首批第 0 次请求含原批次输入，第 3 次请求在 new_context 后不再含原输入，第 4 次请求才通过 notes 成功读回维护笔记，随后 history 返回该维护 session 的 initial 窗口；这证明换窗与恢复真实执行，未仅核对工具列表。

本次冷答题 completed，本地 send_message 交付成功；冷请求没有 LONG_MESSAGE_END、UNRELATED_HISTORY_ONLY 或 EVALUATION_RECOVERY；FUTURE_SYNC_REVIEW 未进入准备请求，旧 runtime read 和越界 glob 拒绝共 2 次。准备请求定位 `prepare-jZMNdU/requests.jsonl`，答题 `answer-J19mpw/requests.jsonl`；pid 26076 / 28086 已确认均不存在，所有子进程经 close 清理。

限制：捕获仍是 DSH 组装后、HTTP provider 适配前的 llm/stream，不证明最终 wire 或真实模型理解、恢复策略和记忆质量。LongMemEval 本次只有对话，未覆盖父产品的子任务提炼；未接真实 IM。真实候选/judge/正式 benchmark 均未启动。源码和上述受影响机制的证据充分后停止，不扩大复审未变的 dataset/Runner/judge 或重跑全量门禁。后者由调用方另行记录。
