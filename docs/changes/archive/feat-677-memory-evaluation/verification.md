# Verification Report: feat-677

> Validation snapshot: `51b23e42b → 97a8b168339fd6dc454537744db152597a3cf0cf`

## Round 1

- verification_mode: `full`
- validated_at: `97a8b168339fd6dc454537744db152597a3cf0cf`
- branch: `codex/feat-677-memory-evaluation`
- verdict: **pass**
- requires_full_verification: `false`
- CRITICAL: 0; WARNING: 0; SUGGESTION: 0

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | M1 的实施与确定性证据要求已覆盖；产品 reviewer 的独立 CLI 旅程报告另见 acceptance.md |
| Correctness | 首文档 4 组要求、5 个 Scenario 均有实现和对应证据 |
| Coherence | Followed；框架与 Dreaming 内部解耦，变化限于专用 adapter 与离线评测入口 |

本轮 full verification 通过。真实模型效果、正式 subset、模型预算配置及付费跑量明确未执行，也不是本轮退出标准。

## Completeness

- M1 实施项 1/1：稳定候选协议、LongMemEval 数据边界、Nano 原生历史物化与记忆准备、冷答题、本地投递、judge、报告、CLI 及长期操作文档均已落地。
- M1 worker 条件：历史/Context 隔离、真实产品记忆消费、opaque 候选替换、失败分母、预算/超时/清理与阶段请求审计有就近确定性保护。通用测试未锁定 Dreaming 游标、批次数或 Markdown 介质。
- M1 reviewer 条件：独立产品旅程归 acceptance.md 的 reviewer；本 verifier 复核其机制接线，不替代产品 reviewer。
- Prototype / Reference：N/A；无客户端 UI、部署迁移或生产服务变更。
- 对全仓测试的首次独立补充尝试 `python3 -m pytest tests/contract/test_runtime_dependency_contract.py -q` 未执行成功：系统 Python 未安装 pytest。未因此安装环境或修改依赖。调用方随后提供已通过的 124 passed / 28 deselected、docs-check、ruff、全仓 build/typecheck 结果；本报告主要依据受审源码、已定位的窄验证和下述独立运行时探针，不将未执行命令计为通过。

## Correctness

| Requirement / Scenario | 实现位置 | 测试 / 直接证据 | 状态 |
|---|---|---|---|
| 从原始经历评测真实记忆：完整双方正文、时间、身份及顺序，不重演或替候选总结 | `evals/memory/dataset.ts:53`；`packages/dsh-integration/src/evaluation/history.ts:20` | dataset.test.ts；evaluation-runtime.test.ts；独立 3 sessions / 6 messages 探针包含 assistant-only、连续 user、中文/emoji/换行及长消息尾部 | covered |
| 未来 question / gold / 标注不进入准备 | `dataset.ts:79`；`evals/memory/runner.ts:95` | dataset.test.ts；runner.test.ts；独立准备实际请求不含 FUTURE_REVIEW_ONLY | covered |
| 改变记忆机制仍沿用相同历史、问题、评分和口径 | `packages/product-contracts/src/memory-evaluation.ts:46`；`runner.ts:78`；`evals/memory/nano.ts:5` | runner.test.ts 的 during-ingestion / after-ingestion 私有状态替身复用同一 Runner；通用模块无 DSH / Dreaming import | covered |
| 冷答题不能回查旧 Global / Inbox / 维护材料 | `evaluation.ts:91,162,183`；`evaluation/runtime.ts:45`；`evaluation.ts:223` | evaluation-runtime.test.ts 的两次独立答题、原历史缺席和访问拒绝；独立探针答题 7 次请求无新增原历史，拒绝旧 runtime read 与越界 glob | covered |
| 默认计划 / 确定性自检不请求真实模型 | `evals/memory/cli.ts:22`；`evals/memory/plan.ts:50` | cli.test.ts 真实 CLI 子进程及本地监听：modelCallsStarted=0、零 HTTP 请求；progress.md 合成计划入口 | covered |
| 显式执行需开关、非空题集及阶段限额，失败不伪装通过 | `cli.ts:24,43`；`runner.ts:82`；`evaluation/runtime.ts:24` | cli.test.ts 的 run/score opt-in；evaluation-runtime.test.ts 的调用预算与挂起 provider 超时终止 | covered |
| 原回答、失败分母、独立评分与重评分可审计 | `runner.ts:44,62,127`；`evals/memory/judge.ts:14,23` | runner.test.ts 的异常准备、分母与保留旧 judge 尝试；judge.test.ts 的全部题型规则及本地 HTTP 503/yes/usage | covered |

## Coherence

| design 决策 | 遵守? | 代码 / 证据 |
|---|---|---|
| 三方法候选接口、opaque preparedRef，框架不理解记忆介质 | 是 | product-contracts/memory-evaluation.ts；runner.ts 只转交 ref 和核验公共收据 |
| DSH 只由 integration 经公开 exports 接入 | 是 | history.ts 的 SessionPersistence / Session 公开 API；integration package.json 已声明依赖；evals 仅在 nano.ts 动态加载专用导出 |
| 空来源 baseline 先于完整导入 | 是 | history.ts:21-27；准备后真实 Dreaming 读取到所有合成历史 |
| 使用被测版本真实来源选择、Dreaming 和文档装配 | 是 | evaluation/runtime.ts:70；既有 knowledge/dreaming.ts、memory-sources.ts、document-memory.ts；未引入另一套总结器 |
| 封存全部当前记忆及必要状态，答题新进程与新 session | 是 | evaluation.ts:73,98,162,223；既有 DocumentMemory context 与 sources sync；实际冷答题读取到 knowledge/city.md |
| 问题日期只在 answer；原文索引可由候选记忆自行保存 | 是 | dataset.ts:87；evaluation.ts:193；框架未限制 opaque 状态介质或删改原材料 |
| 本地真实 send_message 为答案，无 gold 择优或私稿代替 | 是 | evaluation.ts:107-113,197；测试与独立探针经过本地投递 |
| 协议与候选身份分离，judge 固定规则，缺失用量为 null | 是 | plan.ts:63-70；judge.ts:8,29；evaluation/runtime.ts:19-23 |
| 超时/失败清理并保留审计，清理失败停止后续题 | 是 | evaluation.ts:120-159；runner.ts:34,108,118；现有预算/挂起 provider 确定性测试 |
| 默认零出站，真实模型调用由维护者未来显式决定 | 是 | cli.ts:24-41；未执行任何真实候选或真实 judge |

### Agent Context evidence

复用同一独立审查者的 [Mode B 检查](code-review.md)，不另做完整 Context Review。实际覆盖准备受限 system prompt、工具 schema、导入来源/日期/双方正文、文件读取后的后续请求、冷答题记忆入口与问题、本地公开交付、越界拒绝和两阶段隔离。独立探针准备 12 次 / 答题 7 次 llm/stream 请求，maxTokens=2048，准备工具为 edit/finish/glob/grep/read/write；冷答题的 Global 固定基础工具仍在 schema，执行 guard 对不允许动作作宿主拒绝，产品服务也没有旧历史接线。

证据是确定性 provider 下的真实 DSH 装配与实际工具/产品事实；未证明 HTTP provider 的最终 wire 序列化或真实模型选择、理解、记忆质量。没有把后者写成已通过。原请求只保留在本机 `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/feat677-review-9cAoYH/`，进程已关闭；不提交原件。

### Prototype / Reference Contract

N/A。

### Delta reconciliation

Gateway / PA：**no spec delta** 成立。完整 diff 只新增专用离线评测代码和包导出、测试/脚本及文档入口，未改生产 profile 的加载链、产品来源选择、记忆行为或消息服务。suite README 承担新增评测协议的长期权威；docs/README.md 和 evals/README.md 均已导航。保留用户指定的 feat-676 `80db8b9a` 父分支，不将 main 的后续设计文档当作当前被测实现。

## Issues

### CRITICAL

无。

### WARNING

无。

### SUGGESTION

无。

## Handoff

未创建 worktree、未切换或同步分支、未修改源码/测试/配置/设计、未提交报告，由调用方在本 unit 分支提交。没有生产操作、真实模型请求或正式 benchmark 下载。独立报告位置即本文件及 code-review.md；后续真实评测应按 suite README 冻结配置并取得用户单独启动授权。

## Round 2 — 最新父分支适配

- verification_mode: `delta`
- review_round: `2`
- executed_base（main merge-base）: `082e72ec4becb37d4ba08c3e3a8e0d2bf45da087`
- effective stacked base: `3e9a46030939bfcce351b7df2e29e5f3c2439055`
- fix_delta_range: `117873fd1..93c8e305bf30de6f0354510f3d9e8eee46b293c1`
- parent_upgrade: `80db8b9a6..3e9a46030`
- validated_at: `93c8e305bf30de6f0354510f3d9e8eee46b293c1`
- branch: `codex/feat-677-memory-evaluation`
- verdict: **pass**
- requires_full_verification: `false`
- CRITICAL: 0; WARNING: 0; SUGGESTION: 0

### 范围与完成度

用户本轮要求评测跟随最新版记忆父分支。只核验该兼容增量及受其影响的原生历史、准备/恢复、封存/冷答题与外部预算链；不替代父 PR 本身的完整审查。数据白名单、题集/协议、三方法接口、通用 Runner、独立 judge、失败分母和重评分实现均无本轮 diff，复用 Round 1 仍适用的结论。M1 的 adapter 接线替换符合原设计允许的变化；新增设计附注明确旧源码观察的版本限制。

| 受影响契约 / 决定 | 实现与适用证据 | 结论 |
|---|---|---|
| 完整原生历史继续由真实记忆机制消费 | `evaluation/history.ts:20` 仍先建立空来源 baseline 再导入；父 `knowledge/memory-sources.ts` 按原文连续片段及冻结来源处理；确定性请求含长消息尾部、日期和第二会话更新 | aligned |
| 新版连续批次及批次 finish，不以单批成功替代全部准备 | `evaluation/runtime.ts:70` 的现有 start/status 接线配合父 `dreaming.ts:159-211,330`；独立现场 6 批 / 66 次请求后才 ready | aligned |
| 准备可恢复自身工作与回查合格业务原文 | `evaluation.ts:212` 放开 prepare 的 contextTools；父 `dreaming-agent.ts:35`、`dreaming-history.ts:63` 分离自身恢复和 source_history；实际 new_context 后原批次输入消失，notes/history 工具成功，source_history 返回原文尾部 | aligned |
| 冷答题仍仅恢复持久记忆，不能继承准备轨迹或笔记 | `evaluation.ts:99,224` 的新 runtime 与 memory/documents.json 复制集合未变；`evaluation/runtime.ts:45` guard 与本地题目桥未变；独立冷请求无原文标记/维护笔记，旧 runtime read 和越界 glob 均拒绝 | aligned |
| 当前正式记忆只由 Dreaming 更新 | 父 DocumentMemory 的只读业务契约被沿用；adapter 不调用旧 checkpoint、不引入额外写入器，fixture 对 staging 写入并经真实 finish/apply 封存 | aligned |
| 删除内部步数/时长后仍保留外部有界运行 | `evals/memory/plan.ts:14` 只保留 maxInputTokens，strict 拒绝退役字段；README 说明迁移；EvaluationLimits 及 runtime 请求上限、阶段定时器、进程清理未变；专项测试保留 budget/timeout/重试准备保护且通过 | aligned |
| 稳定协议与候选身份分离 | `plan.ts:69` 候选 adapter 为 v2，并含最新实际构建/锁文件/配置；protocol 计算及 dataset/Runner/judge 不变 | aligned |
| 不伪造 LongMemEval 没有的子任务，不声称 IM 接线完成 | 原生映射仍为 Global 对话，没有 subagent/catalog；无 IM product handler，conversations 名称可见不表示补查服务可用；suite README 说明子任务提炼和 IM 的证据范围 | aligned |

### Context 与执行证据

复用同一 reviewer 的 [Round 2 Implementation Review](code-review.md)，不另发 Context reviewer。已读取受影响的当前 agent-capabilities 契约、父 DreamingAgent/DreamingHistory/DocumentMemory、来源连续片段与冻结边界，以及评测自身的配置、工具集、准备状态判断和冷复制。

- 兼容性 before：`/tmp/feat677-sync-before.log`，旧逐单元 fixture 在新产品无有效 finish 时 prepare=failed；没有把失败推进成 ready。
- 专项回归：`/tmp/feat677-sync-targeted.log`，`pnpm exec vitest run evals/memory packages/dsh-integration/tests/evaluation-runtime.test.ts`，5 files / 13 tests passed；包含新增恢复结果与退役配置拒绝，以及保留的预算/超时/清理。
- 独立窄探针：`pnpm exec tsx /tmp/feat677-sync-review-probe.mts`，真实锁定 DSH、受控 fixture、1000 输入容量、6 批 / 66 次准备请求、maxTokens 均 2048；prepare=ready、answer=completed。source_history 返回原长消息尾部，new_context 确实移除活跃原批次输入，notes/history 成功恢复维护自身工作。未来问题未进入准备；冷答题无原历史与维护笔记，越界拒绝 2 次。
- 本机证据：`/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/feat677-sync-review-mtuKAl/prepare-jZMNdU/{receipt.json,requests.jsonl}` 与 `answer-J19mpw/{answer.json,requests.jsonl}`。完整请求不提交。pid 26076、28086 均已确认退出；本轮没有自建 worktree 或常驻服务。

证据限制：确定性 llm/stream 请求与真实工具/产品结果证明接线和恢复机制，不证明最终 HTTP wire、真实模型主动选择、记忆质量、子任务提炼或真实 IM 行为。本轮没有正式评测授权，真实候选与 judge、正式 benchmark 始终未运行。全量 build/typecheck/回归由调用方独立完成，不将其仍在运行的状态写成已通过。本轮已充分覆盖适配增量，保留旧不变结论，无需扩大为 full verification。

### Delta 与问题

Gateway / PA：本轮评测自有增量仍为 **no spec delta**；父产品的正式记忆只读、连续批次、任务提炼和恢复行为由其自身 current spec 与父 PR 负责，不能把包含父 merge 的全部分支 diff 说成没有产品行为变化。新增评测配置兼容说明、v2 adapter 与能力限制归 suite README；历史、问题、评分、冷上下文和预算的稳定协议未变。

CRITICAL / WARNING / SUGGESTION 均无。仅在原 code-review.md 与本文件追加 Round 2，未改实现/测试/配置、未提交；由调用方提交本轮报告。保留 Round 1 原记录；本轮候选基线以最新 stacked base 为准。
