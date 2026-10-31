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


## Round 4 — 单 Global 原生窗口 targeted acceptance

> mode=full；revalidation_mode=targeted；review_round=4；2026-10-30（北京时间）。
>
> validated_at / executed_base：`8ced1ccd7da12a6437a90927f8b2d632c4bcd66c`；prior：本文件 Round 3；本轮 focus 为 native-window delta 及父分支正常结束接线。开始时 HEAD 精确匹配、分支 `codex/feat-677-memory-evaluation`、工作区干净。

### Verdict 与用户旅程

**pass（无真实模型的 targeted 机制交付范围）**；0 blocking / 0 major / 0 minor；highest_required_action=pass；needs_re_review=false。本轮真实候选模型、真实 judge 和正式题集均 **not_run**；旧 v3 一题 incomplete 保留原构造身份，不能据本轮通过改写其结果、解释为 v4 质量结论或自动重跑。

从 README 复制默认计划入口，得到 1 题、2 个数据集会话、4 条消息和 `modelCallsStarted: 0`。计划明确 protocol version 2、`nano-document-memory-v4` 与 `historyMapping: single-global-session; dataset-session-as-native-window; one-owner-conversation`。sourceCommit 匹配 validated_at、dirty=false，runtimeHash 为 `9f8c613e15dab18c6eac59d855abc35fdf02aabb286cfad93e75dbe160fd6f4c`。输出只展示计数、配置、限额与身份，没有历史正文、问题或 gold。

README 清楚说明每段原对话到达时成为同一持久 session 的原生窗口，未来窗口不预建，不因换窗重设游标或强制 Dreaming；旧窗正文可通过 History 恢复，不生成业务摘要或 Notes。这是数据集固定分段约定，不等同产品 token 压力自动换窗验收。时间到达、等待已准入工作、冻结与冷答题仍为 v2；v4 身份及旧 v3 不可作为当前基线的说明，让维护者能够辨认结果可比边界。

实际尝试不带 `--allow-model-calls` 的 run 和 score，两者均 exit 1，并提示 `Model execution is disabled; pass --allow-model-calls explicitly`。随后独立运行文档自检入口（追加 verbose 展示逐项结果），5 files / 15 tests 全部通过，49.87 秒。入口实际覆盖单持久 Global 的可恢复窗口、只回放已到达历史并冷答题、无到期周期的空记忆冻结、预算 incomplete、停滞 provider 截止退出，以及数据/Runner/judge/CLI。该路径按 design Runbook 使用真实 Nano/DSH 运行时及合成本地 provider；没有手工调用真实模型，没有读取实现定位根因，也不把测试日志称为逐请求人工审计。

### 命令与证据

全部命令以 `PATH=/Users/czj/.local/share/nano-runtime/node-v24.22.1-darwin-arm64/bin:$PATH` 运行，复用 caller 已准备的构建。

- 默认 plan：`pnpm memory-eval --config evals/memory/examples/plan.json --ids evals/memory/examples/ids.json --output /tmp/feat677-window-acceptance-plan`。证据：`/tmp/feat677-window-acceptance-plan/plan.json`、`/tmp/feat677-window-acceptance-plan.log`。
- 显式门禁：`pnpm memory-eval run --config evals/memory/examples/plan.json --ids evals/memory/examples/ids.json --output /tmp/feat677-window-acceptance-denied`；`pnpm memory-eval score --output /tmp/feat677-window-acceptance-denied`。完整命令、输出及两个 exit 1 保存在 `/tmp/feat677-window-acceptance-gates.json`。
- 确定性自检：`pnpm exec vitest run evals/memory packages/dsh-integration/tests/evaluation-runtime.test.ts --reporter=verbose`。exit 0；逐项结果保存在 `/tmp/feat677-window-acceptance-selfcheck.log`。

### Scenario 覆盖与 retained 结论

| Scenario | 来源 | 本轮结果 | 证据与范围 |
|---|---|---|---|
| 不同日期和话题仍属于同一长期主体 | spec 新增同名 Scenario；design 原生窗口/Context 消费验证 | pass | 本轮自检 `imports dialogue segments as restorable windows of one persistent Global session` 通过；计划实际呈现 v4 单根映射；README 边界明确 |
| 导入固定历史并回答后续问题 | spec；design Runbook | pass | 本轮窗口及时间回放冷答题自检通过；真实模型记忆质量未测 |
| 历史跨越记忆维护周期 | spec；design 时间回放 | pass | 本轮 `replays only arrived history and freezes naturally formed memory for isolated answers` 通过；计划仍为 v2 |
| 摄入结束后冻结 | spec 同名 Scenario | pass | 本轮空记忆冻结和时间回放旅程通过；未到期不强制维护，失败/预算检查通过 |
| 长期历史仍存在于准备环境 | spec 冷答题隔离 | pass | 本轮真实运行时冷答题旅程通过；不扩展为操作系统沙箱证明 |
| 比较前后两个记忆版本 | spec 同名 Scenario | pass | opaque Runner 两种候选本轮通过；Round 3 候选配置变更保持协议的结论 retained；本轮 v4 与 v2 的身份可直接辨认 |
| 仅检查数据与执行计划 | spec 同名 Scenario | pass | 独立 plan 零模型请求、计数/限额/构建身份完整 |
| 显式执行评测 | spec 同名 Scenario | pass | 本轮 run/score 未授权拒绝；本地 judge/Runner 自检通过，真实授权执行不在本 verdict 内 |
| 只进行一次有界真实试跑 | spec；本轮明确授权边界 | not-applicable | 旧 v3 一题已有独立结果；此次明确禁止追加真实模型，不重跑、不以新机制通过替代旧结果 |

Round 3 不受影响的数据保真、官方评分规则、报告分母、固定答案补评分与 opaque Runner 结论 retained，并被本轮自检再次覆盖。准备/窗口/冷答题采用本轮结果，不沿用旧多根构造证明新单根窗口行为。

### 文档、问题与清理

无问题。Reference Artifacts Reviewed=N/A；用户入口为 CLI，无 UI、viewport、原型或 IM 常驻栈。已核对 current gateway spec 的跨窗恢复、持久化及 Dreaming 自动准入边界；README 和 design 描述本次固定窗口映射，没有把它泛化为产品压缩策略变化。docs/README.md 已提供评测入口；其余上层文档沿用前轮无需变更判断。

自检进程正常退出，子进程由 adapter/Runner 回收；未另建常驻服务、未连接生产或真实消息。日志留在仓库外。仅追加本 Round，未修改实现、测试、配置或设计；按 caller 要求未提交，report_commit=none，由 owner 收口。

## Round 5 — 同一 PA/主人常驻私聊冷答题 targeted acceptance

> mode=full；revalidation_mode=targeted；review_round=5；2026-10-30（北京时间）。validated_at=`a992a059d043fb118e98adb540304ed329e1b036`；增量范围 `75f4794d38cfcd33efbd49d259f7e5289ea9e763..a992a059d043fb118e98adb540304ed329e1b036`。开始时 HEAD 精确匹配、分支 `codex/feat-677-memory-evaluation`、工作区干净。依 change-reviewer 独立操作 CLI 并阅读实际 provider 捕获，未读取实现定位根因。

**Verdict：pass（无真实模型的 targeted 机制交付范围）**。0 blocking / 0 major / 0 minor；highest_required_action=pass；needs_re_review=false。真实 LLM、judge、正式分数及完整公网 IM/Node 链路不属于本轮结论。

### 用户入口与直接证据

独立执行 README 默认计划入口，实际返回 1 题、2 段会话、4 条消息、`modelCallsStarted=0`；protocol version=2，adapter=`nano-document-memory-v5`，answerMapping=`same-pa-owner-conversation-session; cold-runtime; product-global-inbox-delivery`。sourceCommit 与冻结版本相符、dirty=false；runtimeHash=`3f50ec324e6d0d1cb3a44d7b0f2e1faf4c371e82c015f7f269030b8c33a56807`。默认 dreaming 仅解析周期/静默，没有强加 maxInputTokens。另用仓库外配置显式设置 maxInputTokens=12345，计划保留该值并改变 candidateId，protocolId 仍为 `5d07e255c9a7d344ffcbcf2b7de47a82cfdbbae219b150f5a838477cde4d7463`，请求仍为零。省略值沿产品模型容量规则的契约见 README；执行接线复用本轮专项，不把计划输出解释为测量过真实模型容量。

不带 `--allow-model-calls` 实际执行 run 与 score，两者均 exit 1，明确提示 `Model execution is disabled; pass --allow-model-calls explicitly`。四条完整命令、退出码及输出分别保存于 `/tmp/feat677-pa-independent/0.json` 至 `3.json`；显式配置为同目录 `explicit.json`。使用项目 Node v24.22.1 的 PATH，没有运行获授权模型命令。

独立阅读 `/Users/czj/.local/share/nano-evals/context-parity-20261030/result.json`、`prepare-mdO7ot/prepared.json` 与 `answer-Dw0Qug/requests.jsonl` / `answer.json`，观察到：

- 封存身份为 PA `pa_c520e58de10b`、owner `bf2aecd6-7844-4f77-996e-d7992aa17d2f`、conversation `c_e228b6ce847b`、session `7b5a6551-34c6-4d6c-a655-4230fde84055`。答题首请求 session、唤醒 actor、Inbox sender 和目标分别匹配这些身份；不是仅把显示名称改成 Personal Assistant。
- 首请求有普通 PA/Global 规则、有效文档记忆入口 `Current city: Paris`、source generation=1 和随包技能目录。首请求只出现 Inbox 唤醒；原问题 `Where do I live?` 从后续 Inbox read 进入，携带 `direct`、`participant`、`sender.is_owner=true` 以及原日期 `2024/06/01`。
- `fixture-4` 成功读取封存页面 `You live in Paris. Former city: Berlin.`；`fixture-5` 成功加载 nano-memory，包含正式记忆仅由 Dreaming 写入的规则。`fixture-7/9` 写入并在换窗后读回本次回答的 reply.md；History 只列答题初始窗口，查询准备原文标记 `UNRELATED_HISTORY_ONLY` 返回空。
- 准备 runtime 文件读取与越界 glob 均收到隔离拒绝；answer receipt 为 importedSessions=0 / importedMessages=0。Inbox 再 check 返回 sources=[]；conversations read 仅含当前问题，未带准备原历史。最终 send_message 向同一 conversation 返回 status=sent；answer.json 的 deliveries 为 `You live in Paris.`，terminal completed、pending=false。这是本地实际回执，不是把内部草稿当答案。

复用 caller 的 `/tmp/feat677-product-suite-final.log`：5 files / 15 tests 通过（21.37 秒）；不因独立交接重跑全量。该证据与实际请求捕获共同覆盖默认/显式限额、真实 Nano/DSH 接线和隔离；固定 provider 不证明模型记忆质量。

### Scenario 覆盖与保留结论

| Scenario / 来源 | 本轮结果 | 实际证据与范围 |
|---|---|---|
| 同一长期主体；spec 与 design 2026-10-30 冷答题关系对齐 | pass | 封存身份与答题 session、PA 唤醒、owner Inbox、conversation 回执逐项匹配；冷 runtime 独立 |
| 导入历史后冷答题；spec / design Runbook | pass | 封存有效记忆首轮可见、页面与技能可读、正常 Inbox 获取问题、实际 sent 回执；确定性 provider |
| 长期历史仍在准备环境；spec 隔离 Scenario | pass | 本次请求中的目录/越界拒绝、History 无准备标记、当前 conversations 无准备正文、answer 零导入 |
| 仅检查数据与执行计划；spec | pass | 独立默认与显式限额计划均零请求；v5 candidate / v2 protocol 可辨 |
| 比较记忆版本；spec | pass | 显式 maxInputTokens 改 candidateId、不改 protocolId；旧 v4 不冒充 v5 |
| 显式执行评测；spec | pass | 未授权 run/score 独立实测拒绝；真实授权运行未执行 |
| 时间回放、冻结、完整保真、官方评分、失败分母及 opaque Runner | pass（retained） | Round 4 未失效结论及本轮 5 files / 15 tests；本补丁不修改通用 v2 协议 |
| 只进行一次有界真实试跑；spec | not-applicable | 本轮明确禁止真实 LLM/judge；旧 incomplete 及原候选标签保留，不自动复跑 |

已对照 current gateway personal-agent/global-agent 的主人身份、Inbox 消费、历史恢复和本人私聊投递契约，以及 README 的一致性/差异表。该表明确数据导入、冷上下文、本地单聊 transport、关闭后台能力和逻辑时间差异，足以避免把局部接线通过宣称成完整线上 PA 验收。Reference Artifacts Reviewed=N/A：CLI 入口，无界面改动、viewport 或原型要求。

仅追加本报告，未修改其他受控文件，未提交（report_commit=none）。未启动服务、真实模型或生产操作，没有本 reviewer 新建进程需清理。无阻塞事项。

## Round 6 — stored conversations 与并行隔离 targeted acceptance

> mode=full；revalidation_mode=targeted；review_round=6；2026-10-30 11:40–11:46（北京时间）。validated_at=`067850180ea388d92197fbf59546f464cafecb1b`；stacked parent=`c2a7fe3c3727db2c557a28915fda6ccee5e4298e`；executed main=`2b208eccf43b269242c6f1101c539fb4e0f8bd4f`。开始时 HEAD 精确匹配、分支 `codex/feat-677-memory-evaluation`、工作区干净。按 change-reviewer 阅读首文档 conversations 修订、design Runbook、suite README 和 current gateway 工具/来源约束；只操作 CLI、候选公开 API 和运行证据，不读取实现定位根因。

**Verdict：pass（仅本地确定性机制的 targeted 交付范围）**。0 blocking / 0 major / 0 minor；highest_required_action=pass；needs_re_review=false。真实候选模型、judge、正式分数、全量 benchmark 与生产访问均未执行。

### 独立用户旅程与直接观察

执行 README 默认 CLI：`pnpm memory-eval --config evals/memory/examples/plan.json --ids evals/memory/examples/ids.json --output /tmp/feat677-conversations-review-plan`。实际输出 1 题、2 sessions、4 messages、`modelCallsStarted=0`，protocol version=3、adapter=`nano-document-memory-v6`、sourceCommit 匹配冻结版本、dirty=false。`protocolId=42d7aa71a68fa8898690c1a17838c1d2ac71763ed2d6830fe9c5bc8d27d3449c`；runtimeHash=`9b4501229fa134dd294c7f7e52dce60b93687e0f73a443119b559a01d0ee2e35`，chatHash=`e1b2c3aeee8f0149c875ae60d222f9d3cd57e05ed162212d63faf7ab70c321fb`。计划和 README 均明确 persistent memory plus stored conversation retrieval，与旧 memory-only v2 不混算。

另在仓库外编写 `/tmp/feat677-conversations-acceptance/probe.mts`，通过公开 `NanoMemoryCandidate.prepare/answer/close`，复用已有 fixtureOptions 的本地确定性 provider（EVALUATION_CHAT_ONLY=1），导入一个短 session 的两条原文，再从同一封存状态回答两次不同问题。使用项目 Node v24.22.1，命令 `pnpm exec tsx /tmp/feat677-conversations-acceptance/probe.mts`。第一次探针扩展名 `.ts` 被 tsx 解释为 CJS，加载 ESM 依赖失败且未创建 runtime；仅改仓库外文件为 `.mts` 后正常 exit 0，没有修改产品或测试。

- prepare 返回 ready，importedSessions=1 / importedMessages=2 / modelCalls=0；历史是原日期 `2024/02/03 04:05`、user 的 brass key/blue drawer 陈述和 assistant 确认。两个 answer 均 completed，各 6 次本地确定性 provider 调用；没有真实模型请求。
- 直接查看两份 `requests.jsonl`：首请求都不含 `CASE_MARKER` 原文或当前问题正文。问题经正常 Inbox read 后进入；`conversations search` 用 limit=1 返回 assistant 原文，next_cursor 续页返回 user 原文，末页 has_more=false。两条 source_time 均为 `2024-02-03T04:05:00+00:00`，sender 分别为 agent 与 owner/user，正文逐字匹配输入。
- 原消息 ID `90596c91e64c4da8a9209fec90b1c690`（user）与 `3e6ec426f1f04059930978ff06e34659`（assistant）在 source-map 和实际工具结果中一致。两次冷答题保留 session `f11cdb74-78b2-4e36-8ae9-e4da247da5c8` 及 conversation `c_429ff37ed5b7`；各自产生独立分页 cursor。
- 两份实际 `send_message` 工具结果均为 status=sent，answer receipt 返回由两页原文组成的已交付文本；没有把内部 prose 当交付结果。
- 关闭 candidate 后只读检查 SQLite：sealed chat 仍是 2 条原历史、不含问题 A/B；两个可写副本各 4 条（历史、自己的问题和实际回复），分别只含 `UNIQUE_QUESTION_A` 或 `UNIQUE_QUESTION_B`。两个请求捕获也均不含另一轮问题。重复答题没有污染 sealed chat 或另一副本。

### 证据与复用检查

独立原始证据保留在 `/tmp/feat677-conversations-acceptance/`：`probe-esm.log`、`run/results.json`、`run/request-observations.json`、`run/db-observations.json`；准备目录 `run/prepare-yE5dk0/` 包含 source-map.json、prepared.json、prepared-chat.sqlite 与 receipt；答题目录 `run/answer-VGGgsK/` 和 `run/answer-KFh9LU/` 各有 requests.jsonl、answer.json、chat.sqlite。CLI plan 位于 `/tmp/feat677-conversations-review-plan/plan.json`。

复用 caller 已运行的 `/tmp/feat677-conversations-targeted.log`，命令为 `pnpm exec vitest run apps/im-server/tests/evaluation.test.ts packages/dsh-integration/tests/evaluation-runtime.test.ts evals/memory`，实际日志为 6 files / 17 tests passed，37.60 秒。caller 说明专项之后仅补 API docstring 与 identity secret/ctx 一致性；当前冻结构建的真实查询由本轮独立探针再验。该 runtime 旅程覆盖准备早期原文与未来纠正隔离、source-map/日期、首轮与检索后的 Context；parallel case runtimes 检查同时运行两题，B 开始请求后取消，A completed、B failed，随后可从 B 封存状态重答，并检查 PID 退出。IM evaluation 检查 30000+ 字符真实查询分页、cutoff 排除未来、跨题拒绝、跨准备/副本和跨副本 cursor 拒绝及写入隔离。这部分是复用确定性测试证据，不宣称 reviewer 另行手工执行了并行取消或长文旅程；不重复全套测试。

| Scenario / 来源 | 结果 | 本轮证据与边界 |
|---|---|---|
| 准备和冷答题查询主人聊天；spec 2026-10-30 新增 | pass | 独立实际两页原文/作者/时间/消息 ID 与发送回执；准备 cutoff、长文分页复用本轮专项 |
| 多题同时运行或重复答同一题；spec 新增 | pass | 独立重复冷答题与 sealed/副本 SQLite 检查；并行取消、跨题和游标隔离复用本轮专项 |
| 长期历史仍存在于准备环境；spec 冷答题隔离 | pass | 独立首轮无历史、查询后才出现原文；准备 runtime/Notes 文件隔离沿用 Round 5，结合本轮专项 |
| 仅检查数据与执行计划；spec | pass | 独立默认 CLI 零请求，明确 v3/v6，计划源版本与构建标识完整 |
| 导入固定历史并回答后续问题；spec | pass | 独立 ready 收据、空初始记忆、两次 completed 与实际 sent；不证明模型质量 |
| 比较前后记忆版本；spec | pass | 新 protocolId 与 v3 查询边界可辨；旧结果保持旧标签，Runner opaque 候选/分数规则测试 retained |
| 时间回放、自动周期、冻结、数据保真、失败分母、judge-only retry | pass（retained） | Round 4/5 未失效结论及本轮 17 tests；检索范围改变部分以本 Round 替代旧 memory-only 结论 |
| 显式执行评测 | pass（retained） | Round 5 run/score 未授权拒绝；本轮独立默认 plan 零请求，授权执行未重跑 |
| 有界真实试跑 | not-applicable | 用户预算边界明确禁止；旧 incomplete 记录保留，不追加真实候选/judge |

### 体验、清理与报告边界

Reference Artifacts Reviewed=N/A：CLI/候选 API 用户入口，无 UI、viewport、原型或 daily 常驻服务需求。README 已说明协议升级、原历史按需检索、旧快照不可改名复用、CLI 仍顺序调度及未来多实例并行边界；维护者能区分计划、执行、机制通过与正式效果。无新增文档同步要求或产品问题。

探针通过 finally 调用 close，主进程 exit 0；随后 `ps` 核对没有带本探针目录或 evaluation/runtime 的残留进程。没有 HTTP 监听、生产连接或真实模型调用；运行证据留在仓库外且未删除。只追加本 Round；未提交（report_commit=none），由 owner 收口。无阻塞事项。

## Round 7 — 父分支更新与 TaskContext 适配 targeted acceptance

> mode=full；revalidation_mode=targeted；review_round=7；2026-11-01。validated_at=`f09f44c4ecf66672b21834cc76e7a7eee4eea31c`；fix_delta_range=`0d6a534a5376bfc6e8e707c270fa6553fab7677c..f09f44c4ecf66672b21834cc76e7a7eee4eea31c`；executed_base=`f01ee218b10efccbfc3fa41bac14e73b9c5a9027`。分支 `codex/feat-677-memory-evaluation`，HEAD 精确匹配；开始已有并行文档修改（spec/code-review/verification），未改动受验源码。prior=本文件 Round 6（`067850180ea388d92197fbf59546f464cafecb1b`）。仅验父分支同步后的 CLI 与冷答题产品旅程，不审实现根因、不评两份新增 benchmark 研究。

**Verdict：pass（本地确定性机制的 targeted 交付范围）**。0 blocking / 0 major / 0 minor；highest_required_action=pass；needs_re_review=false。真实模型、真实 judge、正式 benchmark 分数与生产调用全部 not_run。

### 独立观察与证据

按 change-reviewer 阅读 spec/design Runbook、suite README、current Global Inbox/历史及 PA 关系约束，使用项目 Node v24.22.1 PATH。独立执行默认 plan、无授权 run、无授权 score，完整命令/退出码/输出在 `/tmp/feat677-sync-acceptance/cli-0.json` 至 `cli-2.json`。计划 exit 0，1 题/2 sessions/4 messages、`modelCallsStarted=0`、protocol v3 / adapter v6；protocolId 仍为 `42d7aa71a68fa8898690c1a17838c1d2ac71763ed2d6830fe9c5bc8d27d3449c`。run/score 均 exit 1，明确提示 `Model execution is disabled; pass --allow-model-calls explicitly`。

计划 `/tmp/feat677-sync-acceptance/plan/plan.json` 记录 sourceCommit=f09f44、dirty=true（并行报告/需求文档修改），没有伪称 clean。runtimeHash=`0124188a18090c0f2a3e3551360bca78a33bb7597b1de3531e77ef37fe6c224a`，productHash=`a4e6ed2fb8e800cd9e60037725d3461b5e416955352a789acd3ecda81fbe91ae`，chatHash=`86cd91fa6c7d57e959f0fb05093708b3fe6e13f54716462b2c6852d4da8ca3d7`。复用 `/tmp/feat677-sync-build-fixed.log` 构建：caller 确认先在 merge HEAD 的工作区写入最终适配源码再构建，之后仅调整测试断言与文档并提交 f09f44，应用/适配源码未再改；日志安装包标记 0d6a534 是构建时 HEAD，不作为已发布 f09f44 安装包证据。本轮使用同源码本地构建，无部署。

独立仓库外探针 `/tmp/feat677-sync-acceptance/probe.mts` 调用公开 `NanoMemoryCandidate.prepare/answer/close` 与允许的 fixtureOptions，`EVALUATION_CHAT_ONLY=1`；真实 Nano/DSH 子进程、本地确定性 provider、独立 SQLite，不启动 HTTP/UI 栈。执行 `pnpm exec tsx /tmp/feat677-sync-acceptance/probe.mts` 正常 exit 0，日志为同目录 `probe.log`。一段完整 user/assistant brass-key 合成历史准备 ready，导入 1 session/2 messages、准备 modelCalls=0；从同一封存状态回答两个不同问题，各 completed、6 次本地 provider 请求。

直接读取 `run/answer-hpSvjJ/requests.jsonl` 和 `run/answer-CVO5uz/requests.jsonl`，并只读查询数据库，汇总在 `run/observations.json`：

- 两个首请求都没有 `CASE_MARKER` 原历史或 `UNIQUE_QUESTION` 正文。当前角色为 PA `pa_47f0616932ca`，session=`b8b6b796-0cef-4673-a0d9-3a0ab52b5f0d`，主人=`a1e325f8-9271-4b42-ab51-726af91fc3dc`，私聊=`c_c5529bf57867`；与封存/source-map 一致。
- Inbox check/read 使用当前 direct/participant 来源，读到各自问题，sender.is_owner=true，问题日期分别保留 `2024/02/04` 与 `2024/02/05`。
- conversations search limit=1，第一页面 user 原文并给 next_cursor，第二页 assistant 原文且无 next_cursor。两页 source_time 均为 `2024-02-03T04:05:00+00:00`，原角色/正文完整。消息 ID `99e206b1a4c941aaa718ece2d23f10a0` 与 `5f7e0e8fd1fe40baa42d0294e1c59949` 和准备 source-map 一致。两次查询有不同分页 cursor。
- 两个实际 send_message 结果均 status=sent，目标为同一私聊；`run/results.json` 与各 answer.json 返回由原文组成的真实已交付文本，不把内部结束 prose 当答案。
- sealed `run/prepare-Wc6lkE/prepared-chat.sqlite` 仍为 2 条原历史，不含问题 A/B；两个 answer/chat.sqlite 各 4 条，各只含自己的问题，request 捕获也无另一轮问题。三个数据库的 task_context_index 都为 0：LongMemEval 没有 Task 原文，本轮未编造任务场景。

### Scenario 覆盖与 retained 范围

| Scenario / 来源 | 结果 | 证据与范围 |
|---|---|---|
| 仅检查数据与执行计划；spec | pass | 本轮独立默认 plan 零请求、v3/v6 与构建标识 |
| 显式执行评测；spec | pass | 本轮独立 run/score 未授权拒绝；未开启真实执行 |
| 导入固定历史并回答后续问题；spec/Runbook | pass | ready、两个冷答题 completed、实际 sent 与 SQLite 交付 |
| 长期历史仍存在于准备环境；spec | pass | 首轮无历史、Inbox 读题、调用 conversations 后才出现原文；准备轨迹/Notes 文件隔离沿 Round 5/6 与本轮专项保留 |
| 准备和冷答题查询主人聊天；spec | pass | 独立两页作者/时间/正文/消息 ID；长消息与准备 cutoff 复用专项 |
| 多题同时运行或重复答同一题；spec | pass | 独立封存/两次冷副本不串；并行取消及游标拒绝复用专项 |
| 不同日期话题属于同一长期主体；时间回放；摄入结束冻结 | pass（retained） | Round 6 引用的同根窗口、自动周期、未来隔离与冻结证据；本轮 17 tests 再覆盖这些运行时边界，最小冷答题独立验证身份及可恢复聊天 |
| 比较记忆版本；官方评分、失败分母、judge-only retry | pass（retained） | Round 6 通用 Runner/评分结论与本轮专项；v3 protocolId 不变，candidate 构建身份变化。未把机制通过当分数改善 |
| 一次有界真实试跑 | not-applicable | 本轮明确零真实模型/judge；旧 incomplete 保持原标签，不重跑 |

复用 `/tmp/feat677-sync-targeted-final.log`：6 files / 17 tests passed，28.27 秒，涵盖 evals/memory、IM evaluation 与 DSH evaluation runtime。Round 6 已具体记录并行取消、跨题/跨副本游标隔离、长文分页、截止退出与原生窗口的充分证据；本轮专项继续覆盖，故不重复全矩阵或声称 reviewer 手工重跑这些分支。父分支适配的当前身份/来源同步和交付以本轮真实旅程为准。Task 数据为空的结论仅对应本 fixture，不扩展为 Task 产品验收。

### 体验、清理与限制

Reference Artifacts Reviewed=N/A：CLI/API 入口，无 UI/viewport/原型。README 清楚区分默认计划、预算授权、机制证据与正式效果，并说明 TaskContext 正常同步、空 Task 范围及本地 transport 差异。未发现妨碍维护者完成本轮目标的问题。

探针 finally close，主进程 exit 0；随后 ps 核对没有本探针或 evaluation/runtime 残留（仅观察命令自身），未触碰旧 viewer。证据保留在 `/tmp/feat677-sync-acceptance/`。仅追加 acceptance Round 7，未改源码/测试/受控配置，未提交，report_commit=none。无阻塞事项。
