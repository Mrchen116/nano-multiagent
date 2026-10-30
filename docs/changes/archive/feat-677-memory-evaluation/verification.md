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

## Round 3 — 时间回放修订

- reviewer_target: `/root/timeline_static_review`
- verification_mode: `delta`
- review_round: `3`
- fix_delta_range: `a524e3b900cfd32a4dc30ef88969dec635540a2e..13fff74b2ccb3d82e62638108a96363adea82fee`
- effective stacked base: `3e9a46030939bfcce351b7df2e29e5f3c2439055`
- validated_at: `13fff74b2ccb3d82e62638108a96363adea82fee`
- branch: `codex/feat-677-memory-evaluation`
- verdict: **pass**（本轮时间回放实现与受影响机制）
- requires_full_verification: `false`
- CRITICAL: 0; WARNING: 0; SUGGESTION: 0

### Completeness

核实固定 HEAD、直接父提交和 effective base 祖先链。本轮读 spec 的时间线/冻结/冷答题/有界执行要求、design.md:168-184 的实现决定以及 :262-268 的 M1 退出标准；M1 维护在 design.md，本目录没有独立 milestone 文档。设计 Round 2 Approved。保留原 Round 1/2 未变的数据、候选三方法、Runner、judge 与隔离结论；不沿用被新协议替换的 bulk 完成条件。

本次 delta 的实现与确定性退出条件均有覆盖。用户授权的一道真实题及实际消耗是 owner 的后续交付项，本 verifier 未执行、未把机制 pass 写成整项真实效果已完成。前端原型/Reference Contract：N/A；无生产迁移。

### Correctness / Coherence

| Requirement / design 决定 | 实现位置与证据 | 状态 |
|---|---|---|
| 逐会话到达，保持原文/双方身份/日期/顺序，早期无法读未来正文 | `evaluation/history.ts:18-35` 分开 baseline 与追加；`runtime.ts:88-105`；主旅程 early/late 请求和 future source_history 检查；独立 chronological 探针重复观察 through=-1 | aligned |
| 产品自身自动准入，宿主不复制调度规则或重演业务 | `dreaming.ts:74-107,131-149` 的实例 clock / shared timing / tick；`runtime.ts:90-95` 只查询并调用；既有 scheduling、Dreaming runtime/cycle 专项通过 | aligned |
| 同刻全量先到达，边界新活动参与静默 | `runtime.ts:97-109`；scheduling 测试记录活动后延后准入；独立 quietMs=0 探针 3 条到达先于唯一自动尝试，所有请求 importedSessions=3 | aligned |
| 每次已准入处理结束后推进时间，不强制末尾清空 | `runtime.ts:79-95,113-120`；正常探针 82 次请求只有两组固定逻辑时间，末尾 pending-ready；`evaluation-runtime.test.ts:8-22` 零到期时零请求封存初始空记忆 | aligned |
| 已触发失败、预算耗尽与正常 backlog 分开，无隐式重试 | `runtime.ts:84-86,93-94,109-110`；已有预算测试 incomplete 且实际导入仅 1 session；独立 provider 故障 failed、仅 1 次尝试并停止，不导入后续历史 | aligned |
| 真实预算/取消/清理不受逻辑时钟影响 | `evaluation.ts:53-82,94-99,133-160` 与 `runtime.ts:17-40` 仍 Date.now、真实 setTimeout 和模型请求上限；专项挂起 provider 截止/usage/退出通过，独立 3 个 PID 均已退出 | aligned |
| 冷答题只消费封存记忆与当前问题日期，维护恢复不旁路泄露 | `evaluation.ts:94-114,224-237`、`runtime.ts:49-69` 未扩大复制/工具/服务边界；主旅程真实冷请求、公开 Paris 交付、日期、两次独立 answer、原文/notes 缺席和越界拒绝通过 | aligned |
| 协议身份、候选配置与实际证据可复查 | `plan.ts:15-21,67-77` protocol v2 / adapter v3、实际周期与静默；`runtime.ts:21-38,81-83,102-104,116` timeline/requests/计数；CLI 默认 plan 零请求及新身份测试通过 | aligned |
| 不增加生产接口、第二套 Agent Loop 或记忆写者 | clock 仅 evaluation profile 调用，默认生产时钟/准入未变；导入仍经 DSH 已声明公开 persistence，评测通用层不 import DSH/Dreaming；共享常量来自 product-contracts | aligned |

复用同一独立审查者的 [Round 3 Implementation Review](code-review.md)；覆盖实际 system 消息、工具 schema、冻结来源/恢复结果、形成的记忆与受影响冷答题消费链，不再新增一轮 Context review。未发现实现偏离设计或设计本身导致的确定性缺陷；真实模型理解/策略与质量在本次范围内未验证。

### 执行证据与限制

- 复用 owner 冻结实现的窄验证：`pnpm exec vitest run evals/memory packages/dsh-integration/tests/evaluation-runtime.test.ts packages/dsh-integration/tests/dreaming-scheduling.test.ts packages/dsh-integration/tests/dreaming-runtime.test.ts packages/dsh-integration/tests/dreaming-cycle-runtime.test.ts`；`/tmp/feat677-timeline-targeted.log` 为 8 files / 19 tests passed（50.59 秒）。测试处置为现有主旅程/fixture rewrite-merge、同文件零到期场景、现有 scheduling/CLI 扩展；通用 Runner 未锁产品批次。
- 已读取 `/tmp/feat677-timeline-typecheck.log`、`/tmp/feat677-timeline-full-build.log`、`/tmp/feat677-timeline-python.log` 的通过结果；Python 127 passed / 28 deselected。全仓 pnpm test 由 owner 执行，本报告不代报尚未交接的全量结果。
- 独立命令 `pnpm exec tsx /tmp/feat677-timeline-static-review.mts` 通过；日志 `/tmp/feat677-timeline-static-review.log`。3 个隔离合成现场根目录 `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/feat677-timeline-independent-T5JKXm/`，逐项 receipt/requests/timeline locator 见 code-review.md Round 3；`summary.json` 保留脱敏状态/计数/PID。未运行真实 provider/judge、未下载正式集、未连接生产 IM。完整原请求留本机。
- 没有新建 worktree 或遗留运行进程；只追加 code-review.md / verification.md，不提交。其他角色并行追加 acceptance.md 的工作保持原样。

### Delta reconciliation / Issues

Gateway / PA：**no spec delta**。虽然 patch 提取共享时间函数并增加 Dreaming 包内宿主 seam，生产默认 Date.now、timer/step、周期/静默/重试及唯一写者语义保持；专用评测入口不进入正常 profile、生产 RPC 或模型工具。评测协议确有变更：suite README 的时间回放、ready/backlog、错误停止、默认配置、协议 v2 / candidate v3 与 timeline 审计说明均与实现及已批准 design 对齐；长期评测入口位置未变，不缺新增索引导航。未发现遗漏的产品可观察增量。

CRITICAL / WARNING / SUGGESTION 均无；本轮 delta aligned，不需扩大为 full verification。此结论只放行本次实现与机制证据，一题真实运行结果及整个 benchmark 效果仍由 owner 分开报告。

## Round 4 — 同一 Global 原生多窗口

- reviewer_target: `/root/window_static_review`
- verification_mode: `delta`
- review_round: `4`
- fix_delta_range: `cb296e8affc78715a3013bb35c737fc2bfec41a3..8ced1ccd7da12a6437a90927f8b2d632c4bcd66c`
- validated_at: `8ced1ccd7da12a6437a90927f8b2d632c4bcd66c`
- parent_product_baseline: `efaa2bbae3e21f8835fea477b1085c8efb7f0c93`，经 `9e5cfd6cc6019a2767f612ce5dbd504e4b3a29d9` 合入
- branch: `codex/feat-677-memory-evaluation`
- verdict: **pass**（本轮单根多窗口实现及确定性机制）
- requires_full_verification: `false`
- CRITICAL: 0; WARNING: 0; SUGGESTION: 0

### Completeness

冻结 HEAD 与现场一致，工作区初始 clean；父基线/merge 均在受审提交祖先链。核对 spec 的完整原文、单一 Global 主体、时间到达和冷答题要求，design.md:154-188 的单根多窗/交接决定及 :268-272 的 M1 退出条件，Gate 2 Round 4 Approved。保留 Round 3 对无 diff 的 dataset、Runner、judge、时间调度、限额与失败分母证据；没有重复审父产品正常结束变更，也没有把先前一题真实调用授权延续到本轮。Prototype / Reference Contract：N/A。

本轮 M1 增量全部有实现及直接证据：到达时生成真实窗口、surface 替换和重载一致、旧窗原文可恢复、单根单目标及连续进度、cold/live writer 交接、冷答题仍隔离。没有需要扩大 full verification 的共享边界变化。

### Correctness / Coherence

| Requirement / design 决定 | 实现与直接证据 | 状态 |
|---|---|---|
| 每题一个 Global、一个持久 root、一个主人 target；每段一个原生 window | `evaluation.ts:56,174,213`；`history.ts:22-26,66-86,93-105`；独立 chronological 和 no-due 各 4 段、4 窗、唯一 root/target，6 个唯一 callId | aligned |
| 未到达正文/窗口不预建；原段 ID、日期、原 turn 和正文保真 | `runtime.ts:91-110`；`history.ts:89-114`；实际早期/后期 source_history 列窗为 1/2，旧窗 read 完整恢复长消息，原段映射事件时间逐条匹配 | aligned |
| 原生 surface 真替换，正文仍由 History 恢复，结构标记不编造业务摘要 | `history.ts:67-86` 使用公开 Session / Compaction / TokenMeter；公开 agent/created 捕获第二次真实加载的 surface 只有 Paris 及 checkpoint，没有 Berlin 长原文；最终重载 4 窗并搜索/读取完整首段 | aligned |
| 同一 Dreaming owner/cursor，按 idle/flush/dispose/cold writer/resume 交接 | `runtime.ts:78-85`；`history.ts:29-38,55-60,116-118`；独立两次同 ID root 加载、baseline 始终 -1，冻结 backlog 从已消费 seq 36 继续到 61，窗口边界不重置进度或另起周期 | aligned |
| 正常产品完成、恢复和唯一写者 | 父 `dreaming-agent.ts` 的正常 turn/end + 文件核验未被改写；fixture 仅跟随去除 finish。实际维护 source_history、new_context、notes、history 成功，正式记忆封存 Paris；无额外写者或业务重演 | aligned |
| 零到期可冻结，末尾不强制启动；保留时间/预算失败语义 | 原调度循环继续由产品 nextAutomaticAt/tick 决定；no-due 四窗仅三分钟、零模型/零 root 加载且 pending-ready；本轮已有 15 项窄回归含模型上限、挂起截止和重试准备，Round 3 未变证据 retained | aligned |
| 冷答题仅用记忆及当前问题，无准备 History/notes 旁路 | `evaluation.ts:94-114,224-235`、`runtime.ts:48-69` 隔离逻辑未扩大；独立新 runtime 7 请求、实际本地 send_message 为 Paris，原日期存在、原历史/恢复笔记缺席、两次越界拒绝 | aligned |
| 版本/文档对应实际候选与协议 | `plan.ts:67-77` protocol v2 / adapter v4 / historyMapping；suite README 原生单根窗口、冻结、固定分段范围、证据和工具边界与 design 一致；研究页清楚区分外部方法与本仓执行协议 | aligned |

### Context 与执行证据

复用同一独立审查者的 [Round 4 Implementation Review](code-review.md)，不再新建 Context 审查。已组合检查实际 system、messages、工具 schema、原文来源目录、成功工具结果、新窗口及维护自身恢复、形成记忆和冷交付。未发现实现偏离设计、设计本身确定性不合理或必填身份无来源；真实模型理解/策略和质量按授权明确未验证。

- owner 窄验证：`pnpm exec vitest run packages/dsh-integration/tests/evaluation-runtime.test.ts evals/memory`，`/tmp/feat677-window-targeted.log`，5 files / 15 tests passed；相关 package build 已记入 progress。红证据 `/tmp/feat677-window-red.log` 在旧实现的四窗断言实际失败。未重复全量，owner 另行运行。
- 独立探针：`pnpm exec tsx /tmp/feat677-window-static-review.mts`；日志 `/tmp/feat677-window-static-review.log`。现场根 `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/feat677-window-static-review-awo4PT/`；逐项 receipt/requests/timeline/source-map/live surface 的 locator 见 code-review.md Round 4，`summary.json` 保存状态、范围与 PID。
- chronological：84 次准备请求，真实 automatic_start 两次，只有已导入 1/2 段时发生；末尾两段保留 pending，冻结 active=false。no-due：0 次模型请求。cold answer：7 请求、真实本地交付 Paris、deniedTools=2。所有准备请求 maxTokens=2048。
- pid 66811 / 69064 / 69395 均在 close 后验证不存在；无常驻服务、自建 worktree、真实 provider/judge 或生产操作。只追加本文件和 code-review.md，不提交，由 owner 统一交付。

证据限于锁定 DSH 和本地确定性 provider 的实际组装/工具/持久化/公开投递；不证明 HTTP wire、真实模型行为、正式 LongMemEval 分数或 token-pressure 自动换窗。公开 persistence 与 live surface 观察仅证明对应机制；冷答题和恢复结论另由实际工具结果与投递证明。

### Delta reconciliation / Issues

Gateway / PA：**no spec delta**。本 patch 产品代码只改专用 evaluation 入口和其本地插件；生产 profile、来源/写者语义、RPC/模型工具、正常调度和 current spec 均未改。父产品删除 input.md/finish 是独立已合入基线，不能算作本次评测增量。评测行为确有变更，由 canonical `evals/memory/README.md` 维护：adapter v4、同根原生窗口、唯一 target、cold/live 交接及证据定位均与批准设计/实现一致；导航已覆盖 suite 与新研究页，无遗漏对外行为。

CRITICAL / WARNING / SUGGESTION 均无；delta aligned，`requires_full_verification=false`。本轮完成实现和确定性验证，不新增真实模型效果或正式跑量结论。

## Round 5 — 常驻 PA 关系与冷答题产品接线

- reviewer_target: `/root/pa_context_static_review`
- verification_mode: `delta`
- review_round: `5`
- fix_delta_range: `75f4794d38cfcd33efbd49d259f7e5289ea9e763..a992a059d043fb118e98adb540304ed329e1b036`（12 files）
- validated_at: `a992a059d043fb118e98adb540304ed329e1b036`
- branch: `codex/feat-677-memory-evaluation`
- verdict: **fail — fix WARNING before delivery**
- requires_full_verification: `false`
- CRITICAL: 0; WARNING: 1; SUGGESTION: 0

### Completeness / Correctness / Coherence

仅核本轮修正及其影响，不重审父分支或整个 PR。开工 HEAD 正确、工作区 clean。读取 unit spec、design.md:190-210 的冷答题/PA 关系修正和 M1、suite README 的长期契约与保留差异、current Gateway Global/PA/Memory 契约及架构/测试规范。Prototype / Reference Contract：N/A；无生产迁移。复用 Round 4 对无 diff 的时间回放、原生窗口、Dreaming 唯一写者、通用 Runner / judge / 失败分母等结论。

| 契约 / 设计决定 | 实现及直接证据 | 结论 |
|---|---|---|
| 准备/冷答题是同一 PA、主人、binding、私聊、Global session | `evaluation.ts:64-86,174-191,206-217`；prepared.json 五项身份与 answer 实际 request session / Inbox sender / target 对齐；history.ts:102-106 使用同一 owner | aligned |
| 冷 runtime 仅恢复持久记忆，不能访问准备原历史/控制资产 | `evaluation.ts:108,179,226-237`、runtime.ts:51-70；首请求无准备正文/维护笔记，History.search 原标记为空、越界 read/glob 两次拒绝 | aligned |
| 正常 PA receive / Inbox / 唤醒 / 消费 / 回复链 | `nano-product.ts:19-22,43-88` 注入现有产品实现；实际 wake 不含问题正文、Inbox 提供 owner/direct/participant/web/原日期，读后无 unread，PA send_message 实际回包与本地 Paris 交付 | aligned |
| 首请求有效记忆及随包技能、答题自身恢复 | `evaluation.ts:109-112,210-213`；首请求角色与 Paris 入口/source generation=1，nano-memory 实际加载，Notes/new_context/History 与本次 conversations.read 成功 | aligned |
| 当前上下文工具和原生内部委派可以在冷答题工作 | 自身 Context 恢复已证实；但 runtime.ts:57 放行后台 subagent 后，idle 只等待 root，正常委派工作会被提前结束；独立复现见 WARNING | **implementation-mismatch** |
| 产品依赖边界与明确保留差异 | composition root 在 evals 中组合 PA，运行包只接 product port；未加生产 RPC/第二套执行环；本地单聊天 transport、关闭能力/限额/固定窗口均在 README:37-53 披露 | aligned（委派收口例外） |
| 可选容量、版本与可复查身份 | plan.ts:18,63-83；maxInputTokens 可选、产品 schedule 默认不变；candidate v5，新增实际 build/adapter/技能 hash，protocol v2 保持 | aligned |

### Context 与执行证据

复用同一独立 reviewer 的 code-review.md Round 5 Implementation Review，不另做一轮完整 Context Review。亲自读取 owner 提供的 `/tmp/feat677-product-suite-final.log`：5 files / 15 tests passed；读取 `/Users/czj/.local/share/nano-evals/context-parity-20261030/result.json` 及其实际 requests / prepared / receipt / answer。准备 84 请求、答题 16 请求，直接主链 completed/Paris；证据证明装配、工具与本地产品结果，不能证明后台委派完成。

关键缺口只补一个独立受控探针：`pnpm exec tsx /tmp/feat677-pa-delegation-probe.mts`。证据根 `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/feat677-pa-delegation-zVj084/`，`answer-XO15ZN/{answer.json,requests.jsonl,runtime.log}`。只复用封存的合成记忆，不调用真实 provider/judge 或生产。结果：subagent 工具成功、child 进入 provider 请求；根首轮结束时在 803ms 返回 failed/no public answer，早于 child 1200ms 后的正常原生回传，执行树随后关闭。根下一次模型步骤已设置为产品 send_message，但未获得继续机会。

prepare 9015、answer 9614、独立探针 18203 和初探 16781 均确认退出；无常驻服务或新 worktree。只追加 code-review.md / verification.md，未提交。接受其他角色并行维护 acceptance.md，不覆盖。

### Issues

#### WARNING — 后台委派被根 idle 提前截断（CONFIRMED）

- 契约：design.md:208-210、suite README:49 要求可见内部委派沿原生路径工作；current PA 复用 Global 能力。默认 subagent schema 明确后台执行并在完成时通知。
- 实现：`packages/dsh-integration/src/evaluation/runtime.ts:57` 新放行 subagent；同文件 :128-130 的 idle 仅 root.whenIdle；`evaluation.ts:113-126` 立即读取 audit/deliveries 并关闭 runtime。
- 直接后果：默认后台 child 仍在执行时根处于正常等待空档，整题被记为 failed；已有进度时还可能提前将进度当答案评分。主链的 15 项专项全部通过并不能排除此场景。
- 可执行建议：在既有时间/模型阶段限额内等待整个答题执行树和通知触发的后续根工作收口，然后统一采集结果；扩展现有 evaluation-runtime 测试覆盖 child 延后回传与根实际公开交付。不建议静默更改设计来迎合提前终止。

CRITICAL / SUGGESTION：无。无需扩大为 full verification；问题局限于本轮新增工具生命周期支持。

### Delta reconciliation

Gateway / PA：**no spec delta**。本 patch 修改评测 composition / 专用 runtime profile 和候选身份，未修改生产 Global/PA 正常行为、公开产品工具/RPC 或 current specs。评测契约在 canonical suite README 中更新，索引位置已存在。实现总体遵守设计；上述新工具的生命周期尚未兑现，属于 implementation-mismatch，而不是应通过修改 spec 接受的偏差。CRITICAL=0 / WARNING=1，当前 delta 不 pass；真实模型理解、策略、质量和正式分数仍未验证。

## Round 6 — 后台委派收口 targeted closure

- reviewer_target: `/root/pa_context_static_review`
- verification_mode: `targeted-closure`
- review_round: `6`
- fix_delta_range: `a992a059d043fb118e98adb540304ed329e1b036..de2b92942e5f4b03c9b6d86d2e13da510e3e3743`
- validated_at: `de2b92942e5f4b03c9b6d86d2e13da510e3e3743`
- branch: `codex/feat-677-memory-evaluation`
- focus_issue: Round 5 后台委派被根 idle 提前截断（CONFIRMED WARNING）
- validated_issues: **closed**；没有 still_open / superseded 项。
- verdict: **pass**
- requires_full_verification: `false`
- CRITICAL: 0; WARNING: 0; SUGGESTION: 0
- retained: Round 5 其余身份、接线、来源/入口、技能/自身恢复与隔离结论；Round 4 无变更的时间回放/窗口/Dreaming/Runner/judge 证据。

### Completeness / Correctness / Coherence

冻结版本核实、开工 clean；只复验指定 WARNING 与本次受影响 diff，不重跑全量、不重审父 PR。复用同一 reviewer 的 code-review.md Round 6 targeted Implementation Review。Prototype / Reference Contract：N/A。

| 关闭条件 / 受影响契约 | 实现与直接证据 | 结论 |
|---|---|---|
| 根 idle 不再截断已启动后台 child | `runtime.ts:27-33,135-146` 跟踪公开 lifecycle 事件，等待 child end 后再次等待根后续 idle；原失败探针现在 completed/Paris | closed |
| 回传后根真实消费并公开交付 | 原失败探针 8 请求中有 child 原生 send_message、根消费结果后的产品 send_message；既有旅程第二次 answer 的 child 还读取正式记忆，根实际 request 包含 DELEGATED_RESULT、公开交付 Paris | aligned |
| 全树 usage 完整、不越请求/输出预算 | 正常重跑 requests=8 / modelCalls=8；maxModelCalls=5 探针 root+child 只进入 5 请求，无公开交付时 failed；所有请求 maxTokens=2048；未提供的 token/cost 为 null | aligned |
| 新等待仍可被阶段真实时间截止 | child provider 等 10 秒时，timeoutMs=5000 终止 runtime 并返回 failed，child 已进入真实第 5 请求；PID 不存在 | aligned |
| 当前模型容量说明准确 | README:68 与 design:208 直接沿产品完整输入容量规则，正常评测不设额外材料上限；公开可选字段保留，没有引入产品行为变更 | aligned |

### 执行证据与边界

- 红：`/tmp/feat677-pa-child-red.log`，旧实现第二次 answer failed/no public answer。绿：`/tmp/feat677-pa-child-final.log`，既有专项 5 files / 15 tests passed；构建由 owner 交接为 passed，本 reviewer未重复全量。
- 独立关闭：`pnpm exec tsx /tmp/feat677-pa-delegation-probe.mts`；证据 `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/feat677-pa-delegation-tIyJpR/answer-lFAfzh/`，completed/Paris、8 calls，正常后台回传/后续根工作/公开投递均已完成才采集结果。
- 独立限额：`pnpm exec tsx /tmp/feat677-pa-closure-limits.mts budget` 与 `timeout`；最终证据分别在 `feat677-pa-closure-budget-dLTEAv/answer-oHETjs/`、`feat677-pa-closure-timeout-mco4AG/answer-Sie6tK/`（同一系统临时根目录）。预算实际 root+child 5 calls；截止发生时 child 活跃，整个 runtime 被回收。过程额外探针记录保留本机，不入仓。
- PID 52379 / 60488 / 59583 以及额外探针 54850 / 54851 均确认退出；无常驻进程、新 worktree、真实模型、judge 或生产调用。仅追加两份审查报告，不提交。

真实模型策略、质量、HTTP wire 与正式分数未验证；确定性机制通过不外推模型能力。Round 5 其他有效结果全部 retained，不因修复重复运行原准备/直接答题全链。

### Delta reconciliation / Issues

Gateway / PA：**no spec delta**。新等待只位于隔离评测专用 runtime，不新增产品 RPC/工具、修改 PA 生产生命周期或更改 current specs。设计与 README 的材料预算纠正对齐当前产品已存在规则，没有将旧固定值当当前契约。候选 v5 / protocol v2 不变，原真实单题记录保持原身份。

WARNING 已 closed，新增 CRITICAL / WARNING / SUGGESTION 均无；本轮 aligned，`requires_full_verification=false`。保留 Round 5 失败与原始复现作为历史证据，以本轮 closure 为最新有效结论。
