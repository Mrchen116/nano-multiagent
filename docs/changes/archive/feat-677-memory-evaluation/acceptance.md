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
