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
