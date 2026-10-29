# feat-677 — 验收报告

> 对齐：spec.md 已确认的 LongMemEval 要求；design.md Runbook for Reviewer。
>
> Round 1 / full；2026-10-29；CLI，无 Web/iOS 用户面。
>
> Validation snapshot：`97a8b168339fd6dc454537744db152597a3cf0cf → 97a8b168339fd6dc454537744db152597a3cf0cf`。

## Verdict

**pass（本轮确定性机制交付范围）**。0 blocking / 0 major / 0 minor；highest_required_action=pass。

真实候选模型效果、真实 judge、正式 LongMemEval benchmark 均为 **not_run**，没有准确率或记忆质量结论。本报告的 pass 不授权后续模型调用，也不表示真实模型效果已通过。

## 用户旅程体验

从 `evals/memory/README.md` 出发，维护者能直接复制默认计划命令，在没有凭证、模型地址为不可用本地占位符的条件下看到 1 题、2 个历史会话、4 条消息及各阶段限额。输出有数据版本、SHA-256、协议与候选身份，明确 `modelCallsStarted: 0`。计划没有打印历史正文、问题或 gold。

随后分别尝试不带授权开关的 `run` 和 `score`，两者均退出 1，显示 `Model execution is disabled; pass --allow-model-calls explicitly`。错误直接说明下一步需要的显式选择，未进入实际模型执行。

按文档运行确定性自检入口，5 个文件、13 项全部通过，耗时 23.28 秒。独立观察到的入口结果包括真实运行时原生历史准备及隔离文档记忆答题、请求限额下 incomplete、停滞 provider 截止退出，以及固定 judge、报告分母和补评分保持原答案。这里采用 design 明确允许的“suite CLI 与集成测试驱动真实运行时”验收方式；没有读取实现定位原因，没有把 worker 成功叙述作为证据。测试内部产物未作为单独人工逐条审计证据，本报告不声称另行手工完成一次真实模型 run。

另在仓库外复制计划配置，只改变候选模型名称：第二份计划保持同一 protocolId、改变 candidateId，仍为零模型调用；结合自检中两种 opaque candidate 的同一 Runner 旅程，支持以后按同一口径比较候选。

## 实际入口与证据

所有命令使用项目 Node 24.22.1 路径。初始 checkout 为 `codex/feat-677-memory-evaluation`，无 dirty；计划内 sourceCommit 与 validated_at 一致，runtimeHash 为 `ef83beeeb7f0b64e95120c7f6238d46fa4e846b1df2aecf726e3c8aff383bc9c`。

- 默认计划：`pnpm memory-eval --config evals/memory/examples/plan.json --ids evals/memory/examples/ids.json --output /tmp/feat677-review-plan`。证据：`/tmp/feat677-review-plan/plan.json`。
- 拒绝执行：`pnpm memory-eval run --config evals/memory/examples/plan.json --ids evals/memory/examples/ids.json --output /tmp/feat677-review-denied`；`pnpm memory-eval score --output /tmp/feat677-review-denied`。两者现场输出均为上述 disabled 错误与 exit 1；未传 `--allow-model-calls`。
- 确定性自检：`pnpm exec vitest run evals/memory packages/dsh-integration/tests/evaluation-runtime.test.ts --reporter=verbose`。完整输出：`/tmp/feat677-review-selfcheck.log`，exit 0。
- 第二候选计划：`/tmp/feat677-review-second.json` → `/tmp/feat677-review-plan-second/plan.json`。JSON 比较输出：`sameProtocol=true, differentCandidate=true, modelCallsStarted=0`。

本地产物在仓库外，未提交日志、凭证或运行数据。测试命令正常结束；没有另建常驻服务或 HTTP 进程。共享工作区其他验证进程未操作。

## Reference Artifacts Reviewed

N/A。design 明确无客户端 UI 改动、无需前端原型；无 viewport 或视觉一致性契约。

## 问题清单

无。未发现阻塞本轮确定性交付的 CLI 问题。

## 验收标准覆盖

| Requirement / Scenario | 期望来源 | 实际旅程与证据 | 结果 | 范围说明 |
|---|---|---|---|---|
| 从原始经历评测本系统真实记忆能力 / 导入固定历史并回答后续问题 | spec.md 同名 Scenario；design Reviewer runbook | 自检入口的 `retains every turn and date...`、`preserves date precision...`、`prepares native history and answers from isolated document memory with no live provider` 均通过，见 selfcheck 日志 | pass | 合成历史、真实运行时、确定性 provider；真实记忆质量 not_run |
| 改变记忆机制仍能沿用同一评测 / 比较前后两个记忆版本 | spec.md 同名 Scenario | 第二候选计划同协议/不同候选；`runs unchanged against opaque during-ingestion memory...` 与 `...after-ingestion memory...` 两项通过 | pass | 验证复用协议与候选替换机制，不声称已比较两个真实版本效果 |
| 冷答题不能旁路访问旧 Global 上下文 / 长期历史仍存在于准备环境 | spec.md 同名 Scenario；design 冷上下文答题 | 文档指定真实运行时自检 `prepares native history and answers from isolated document memory with no live provider` 通过 | pass | 冷上下文和访问边界的确定性集成证据；未扩展为 OS 沙箱承诺 |
| 实施完成后由维护者决定何时花费模型预算 / 仅检查数据与执行计划 | spec.md 同名 Scenario | 默认计划的计数、限额、modelCallsStarted=0；自检 `defaults to a verifiable plan with zero model requests and gates execution before credential use` 通过 | pass | 真实模型 not_run |
| 实施完成后由维护者决定何时花费模型预算 / 显式执行评测 | spec.md 同名 Scenario；本轮边界 | 未授权 run/score 现场拒绝；自检固定 judge、失败分母、保存答案补评分、请求预算 incomplete 与停滞退出均通过 | pass | 授权门槛与报告机制已验；真实显式模型执行按用户限制 not_run，不能据此宣称正式 benchmark 完成 |

## 上层文档同步

- [x] `SPEC.md`：无需更新，离线评测不改变顶层运行架构。
- [x] `docs/specs/gateway/`：无需更新；已核对 agent-capabilities 的角色记忆和 Dreaming 当前契约，design 明确 no spec delta。
- [x] `AGENTS.md` / `CLAUDE.md`：无需更新。
- [x] `docs/specs/CONTRIBUTING.md`：无需更新。
- [x] `docs/README.md`、`evals/README.md`：已有 Memory / LongMemEval 入口；`evals/memory/README.md` 已提供计划、自检、未来真实运行、报告及效果未测说明。

报告未提交；按 caller 指示只写本报告，由 owner 统一收口。未更改分支、合并 main 或修改受审实现。

## Round 2 — 最新父分支同步 targeted revalidation

> mode=full；revalidation_mode=targeted；review_round=2。
>
> Validation snapshot：`082e72ec4becb37d4ba08c3e3a8e0d2bf45da087 → 93c8e305bf30de6f0354510f3d9e8eee46b293c1`。
>
> effective stacked base：`3e9a46030939bfcce351b7df2e29e5f3c2439055`；fix_delta_range：`117873fd1..93c8e305b`。

### Verdict 与用户旅程

**pass（确定性机制交付范围）**，0 blocking / 0 major / 0 minor；highest_required_action=pass；needs_re_review=false。真实候选模型、真实 judge 与正式题集跑分仍为 **not_run**，不产生模型能力结论。

本轮确认 HEAD 精确匹配 validated_at，分支为 `codex/feat-677-memory-evaluation`，开始验收时工作区干净。按最新 README 复制默认计划入口，得到 1 题、2 会话、4 消息，`modelCallsStarted: 0`。候选明确标为 `nano-document-memory-v2`，Dreaming 配置只有 `maxInputTokens: 24000`；sourceCommit 匹配 HEAD，runtimeHash 为 `6efcb48889574c8e3f97a62698dd3266fd6a23af7e9b11188c78bddfa2d19c6e`。

在仓库外复制合成配置，分别加入旧 `maxSteps` 和 `maxRunMs`，默认计划均退出 1，并指出 `candidate.dreaming` 下对应字段为 `Unrecognized key`。虽然错误采用结构化 schema 文案，字段和位置足以定位；README“准备一次真实运行”第 4 步明确要求删除这两项，并解释外部阶段限额仍有效、耗尽返回 incomplete，用户有可执行的迁移路径。

再实测未带授权开关的 run 与 score，均退出 1，仍为 `Model execution is disabled; pass --allow-model-calls explicitly`。没有传入允许模型调用的开关，没有连接真实模型。

### 本轮证据与继承范围

- 新计划命令：`pnpm memory-eval --config evals/memory/examples/plan.json --ids evals/memory/examples/ids.json --output /tmp/feat677-review-r2-plan`；证据 `/tmp/feat677-review-r2-plan/plan.json`、`/tmp/feat677-review-r2-plan.log`。
- 旧字段拒绝与 run/score 门禁：`/tmp/feat677-review-r2-rejections.log`，逐条保留实际命令、exit code 与原始错误；临时合成配置 `/tmp/feat677-review-r2-maxSteps.json`、`/tmp/feat677-review-r2-maxRunMs.json`。
- 按 caller 明确授权复用本次专项 `/tmp/feat677-sync-targeted.log`：5 files / 13 tests passed，17.95 秒。caller 交接覆盖新版确定性真实运行时准备、跨窗恢复、冷答题，以及原有数据/Runner/judge/CLI 专项；该日志是简洁汇总，不含逐断言轨迹，本轮未声称重新人工审计其内部请求，也未重复全量运行。
- 原 Round 1 无 fail/inconclusive。未改变的数据、评分、报告口径与候选 opaque 接口，继承 Round 1 的对应结论；与新适配器有关的准备与冷答题证据采用本轮专项，不以旧 runtimeHash 冒充新版验证。

| spec Scenario | Round 2 结果 | 依据与边界 |
|---|---|---|
| 导入固定历史并回答后续问题 | pass | 新版确定性运行时专项复用；真实模型质量 not_run |
| 比较前后两个记忆版本 | pass | 继承 Round 1 同协议/不同候选与 opaque 候选证据；本轮专项通过；计划明确候选 v2 |
| 长期历史仍存在于准备环境 | pass | 本轮新版准备/跨窗恢复/冷答题专项；只证明确定性机制边界 |
| 仅检查数据与执行计划 | pass | 本轮亲自运行新配置计划，零模型调用；旧字段均在计划阶段清楚拒绝 |
| 显式执行评测 | pass | 本轮 run/score 未授权拒绝；报告机制沿用专项与 Round 1；真实授权运行 not_run |

### 明确限制、文档与清理

README 已说明 LongMemEval 没有子任务执行轨迹，因此不伪造第一层任务；评测不连接独立 IM，`conversations` 补查不开放，准备阶段可通过 `source_history` 查询本题合格原文。新版维护自身 `notes/history/new_context` 与原文补查属于准备环境，不能据此扩大为对子任务记忆质量或独立 IM 检索效果的验收。

本轮没有 Web/iOS 改动，Reference Artifacts Reviewed=N/A。suite README 已包含迁移说明与上述范围，design 有同步最新父分支的说明；其余上层文档沿用 Round 1 无需更新判断。没有启动常驻服务或新建 HTTP provider，无自建进程待清理。只追加本报告，未修改实现、测试、受版本控制的配置或提交。

## Round 3 — 统一时间回放 targeted acceptance

> mode=full；revalidation_mode=targeted；review_round=3；2026-10-29。
>
> validated_at：`13fff74b2ccb3d82e62638108a96363adea82fee`；prior：本文件 Round 1/2；本轮比较范围 `93c8e305bf30de6f0354510f3d9e8eee46b293c1..13fff74b2ccb3d82e62638108a96363adea82fee`。
>
> 入口为 `pnpm memory-eval`；无 Web/iOS/生产服务变化，不适用 daily 栈或 viewport。caller 已构建，独立核实计划中的源 SHA、dirty 与实际构建 hash；没有重新构建受审版本。

### Verdict 与用户旅程

**pass（本轮无真实模型的 targeted 机制验收范围）**；0 blocking / 0 major / 0 minor；highest_required_action=pass；needs_re_review=false。真实一题由 owner 在本门禁之外按授权执行，本报告未验证真实答案、judge 或分数，也不声明整个新增真实试跑 Scenario 已完成。

初始 HEAD 与 validated_at 一致，分支 `codex/feat-677-memory-evaluation`，工作区干净。使用项目固定 Node 24.22.1 的 PATH，从 README 复制默认计划命令，返回 1 题、2 会话、4 消息及 `modelCallsStarted: 0`，无需凭证。计划明确 protocol version 2、`nano-document-memory-v3`，实际 `intervalMs=86400000`、`quietMs=600000`、`maxInputTokens=24000`；sourceCommit 正确且 dirty=false，runtimeHash=`025613fa44ddc728ef4ab6edc27da401e41d676ad4d0ea0d600f0035b64e63ab`。

维护者从 README 能辨认唯一执行顺序、会话原子到达/同刻原顺序、无时区按 UTC 解释、维护期间逻辑时钟暂停与真实超时分离。计划的 preparation 字段同样明确：仅从首段推进至末段历史，冻结只等待已准入工作，不强制未来周期，未触发 backlog 留在证据中。README 进一步解释 `ready` 不要求 backlog 清空、无周期到期可以封存空记忆，以及失败/超限不能伪装为未触发积压。上述说明与 spec/design 本轮要求一致，未形成第二套模式或模糊的“准备完成等于全量整理”承诺。

在仓库外复制配置，把周期/静默改为 3600000/60000 后再次运行 plan，输出确实采用显式值，仍为零模型调用；protocolId 不变、candidateId 改变，用户能够区分候选参数与实验协议。随后实际执行未带授权开关的 run 与 score，两者均 exit 1，明确显示 `Model execution is disabled; pass --allow-model-calls explicitly`。本轮从未使用该允许开关，没有候选模型或 judge 调用。

### 证据与 retained 范围

- 默认计划：`pnpm memory-eval --config evals/memory/examples/plan.json --ids evals/memory/examples/ids.json --output /tmp/feat677-review-r3-plan`；证据 `/tmp/feat677-review-r3-plan/plan.json`、`/tmp/feat677-review-r3-plan.log`。
- 显式参数计划：仓库外 `/tmp/feat677-review-r3-custom.json`，产物 `/tmp/feat677-review-r3-custom-plan/plan.json`、`/tmp/feat677-review-r3-custom-plan.log`；比较得到 sameProtocol=true、differentCandidate=true、modelCallsStarted=0。
- 未授权 run/score：`/tmp/feat677-review-r3-rejections.json` 保留两条完整命令、原始输出和 exit 1。
- caller 交接并允许复用的当前版本确定性专项：`/tmp/feat677-timeline-targeted.log`，8 files / 19 tests passed，50.59 秒。本 reviewer 亲自读取该结果；这是汇总日志，没有逐断言轨迹。其时间线可见性、正常准入、末尾 backlog、空记忆冻结、冷答题与失败边界覆盖按 caller 交接复用，不冒充本轮独立手工检查了每个模型请求。
- Round 1/2 均无未关闭 fail/inconclusive。未变化的数据保真、官方评分、报告分母、固定答案补评分、opaque 候选 Runner 接口结论 retained；时间回放及准备/冷答题使用本轮专项，不继承旧集中导入的时间语义，不把旧协议产物混成 v2 分数。

### Scenario 覆盖

| Scenario | 来源 | 本轮结果 | 证据与范围 |
|---|---|---|---|
| 导入固定历史并回答后续问题 | spec 同名 Scenario；design Runbook | pass | 当前确定性专项复用；保留完整原生历史与冷上下文机制，真实模型质量未验证 |
| 历史跨越记忆维护周期 | spec 同名 Scenario；design 时间回放 | pass | 亲自核实计划 v2、有效周期/静默及顺序语义；运行时行为采用本轮时间线专项 |
| 摄入结束后冻结 | spec 同名 Scenario；design 结束与失败 | pass | 计划与 README 清楚表述已触发等待、未到期 backlog、空记忆及失败区别；本轮专项复用，不依赖旧 bulk 证据 |
| 只进行一次有界真实试跑 | spec 同名 Scenario；本轮派发授权边界 | not-applicable | 本 reviewer 明确仅做无模型门禁，owner 单独执行选定一题；此行不代表真实试跑已完成，须另附实际逐阶段结果 |
| 比较前后两个记忆版本 | spec 同名 Scenario | pass | 本轮显式周期参数改变候选身份而保持协议；opaque Runner 证据 retained，旧协议与新协议不直接混比 |
| 长期历史仍存在于准备环境 | spec 同名 Scenario | pass | 当前准备/冷答题专项复用；保留工具/上下文隔离结论，不扩展为 OS 沙箱 |
| 仅检查数据与执行计划 | spec 同名 Scenario | pass | 两次独立 CLI plan，实际配置和限额可见，均 modelCallsStarted=0 |
| 显式执行评测 | spec 同名 Scenario | pass | 本轮未授权 run/score 均清楚拒绝；固定 judge、预算与报告机制 retained/专项复用；真实执行及分数不在本 verdict 内 |

### 文档、问题与清理

无问题。Reference Artifacts Reviewed=N/A：本轮为 CLI 用户入口，无原型或视觉匹配要求。README 已包含本轮时间回放与冻结契约；docs/README.md 已有评测入口。已核对 design 的 no spec delta 与 gateway agent-capabilities 当前自动准入/单写者边界，沿用 Round 1 对 SPEC.md、AGENTS.md/CLAUDE.md、specs/CONTRIBUTING.md 无需修改的判断。

仅追加本报告，未读实现定位根因，未修改源码、测试、受版本控制配置或设计，未提交。临时配置和日志留在仓库外。没有启动常驻服务或 HTTP provider，无本 reviewer 进程待清理。
