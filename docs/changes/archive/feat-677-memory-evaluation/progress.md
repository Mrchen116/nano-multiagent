# feat-677 implementation evidence

## Scope

2026-10-29 用户要求先实现、停在实际模型评测之前。本轮仅完成 LongMemEval 框架、Nano 文档记忆候选接线和确定性验证；真实候选模型、真实 judge、公开 benchmark 正式样本均未运行。不得从固定响应的通过率推断模型效果。

实现保留用户指定的 feat-676 分支基线，不把主仓的新 Dreaming 设计当成已实现行为。后续记忆改版的接线留在 Nano adapter。

本文初次交付记录对应旧基线；2026-10-29 晚间最新分支同步与验证见文末追加记录。

## M1 implementation

- 稳定 `MemoryCandidate.prepare/answer/close` 类型与 opaque 状态引用位于 product-contracts；数据、Runner、官方评分规则和报告不导入 DSH。
- Nano 专用入口加载评测 profile 插件，使用 DSH 公开 SessionPersistence 导入历史、实际 KnowledgeRuntime 准备记忆。空历史基线先登记，再追加原文，避免首次激活跳过经历。
- 每道题与每次答题分别创建独立 runtime/workspace/session。只恢复文档记忆和其必要版本/来源状态；答题工具拒绝访问旧 runtime、控制文件及越界 glob。
- 默认 CLI 为计划，真实 run/score 必须显式开启。未完成项不从分母移除；judge 可基于同一原回答重试，保留旧尝试。
- 入口与操作命令见 [suite README](../../../../evals/memory/README.md)。本 unit 不修改生产启动、RPC、工具或 current 记忆行为；no spec delta，长期评测契约在 suite README。

## Test ownership

搜索了 `packages/dsh-integration/tests/{dreaming-runtime,dreaming-incomplete-runtime,memory-runtime,communication-native}.test.ts` 和现有 `evals/`。保留全部既有产品机制覆盖；新评测接口的历史导入、跨环境恢复与控制区隔离此前没有同因覆盖。

| Risk | Owner / seam | Disposition |
|---|---|---|
| 原历史保真、标注与未来问题隔离 | `evals/memory/dataset.test.ts` 数据边界 | 新增最低层覆盖 |
| opaque 候选、失败分母、重评分保留 | `evals/memory/runner.test.ts` 公共候选协议 | 新增；两种状态表示复用同一 Runner |
| 默认计划零出站、显式开关 | `evals/memory/cli.test.ts` 真实 CLI 子进程及本地监听端点 | 新增用户入口覆盖 |
| 原生映射、真实记忆消费、冷答题越界、预算与清理 | `packages/dsh-integration/tests/evaluation-runtime.test.ts` 真实 DSH/provider seam | 新增适配器集成覆盖；不替代已有 Dreaming 产品测试 |
| 固定官方规则与 judge HTTP 失败 | `evals/memory/judge.test.ts` 固定模板/本地 HTTP | 新增评分接口覆盖 |

## Validation before independent gates

- 首次导入验证暴露 DSH 原生 turn/step 从 1 起编号；按锁定原生格式修正，未修改 DSH。
- 模型输入是冻结对象；预算在公开 `agent/request` 配置边界施加，`llm/stream` 只捕获和核验，不改写已组装消息。
- `pnpm --filter @nano/dsh-integration... --filter @nano/personal-assistant... build`：通过。
- `pnpm exec tsc -p evals/memory/tsconfig.json`：通过。
- `pnpm exec vitest run evals/memory packages/dsh-integration/tests/evaluation-runtime.test.ts`：5 files / 13 tests 通过；包括真实运行时完整准备/两次冷答题、请求上限、挂起 provider 超时终止。
- `pnpm memory-eval --config evals/memory/examples/plan.json --ids evals/memory/examples/ids.json`：通过，1 题 / 2 会话 / 4 消息，零模型调用；仅合成示例。
- 独立门禁与本地全量检查随后记录。

所有测试 runtime 使用独立临时目录并由 adapter 终止；默认回归清理临时数据。未触碰生产身份、生产配置或公开 IM。单次排障证据在 `/tmp/feat677-native-debug/`，仅为可清理本地产物。

## Independent gates and final checks

实现冻结版本：`97a8b168339fd6dc454537744db152597a3cf0cf`。

- 独立 code review + verification：pass，findings `[]`，0 CRITICAL / 0 WARNING / 0 SUGGESTION。另用真实 DSH 确定性探针覆盖 assistant-only、连续 user、中文/emoji/换行，3 sessions / 6 messages 保真；准备 12 次、冷答题 7 次模型请求，两个越界访问拒绝，进程已退出。见 [code-review.md](code-review.md)、[verification.md](verification.md)。
- 独立 CLI acceptance：pass，0 问题；默认计划、拒绝未授权 run/score、自检与第二候选同协议/不同 candidate 身份通过。见 [acceptance.md](acceptance.md)。
- `pnpm build`、`pnpm typecheck`、`pnpm check:ios-runtime`：通过。
- `pnpm test`：164 files / 855 tests 通过；日志 `/tmp/feat677-tests.log`。
- `pytest -m 'not e2e' -q`（仓库既有 venv）：124 passed / 28 deselected。
- frontend CI 等价检查：`npm ci`、shared contracts tsc、`npm audit --audit-level=critical`、`npm run test` 通过，108 files / 1031 tests。audit 为 0 critical；报告保留既有 11 项较低等级漏洞，不将其表述为所有依赖均无漏洞。未更新前端依赖。
- docs-check：285 maintained Markdown sources / 68 required routes；ruff check 与 ruff format --check 通过。

### Base and validity

用户明确要求从 feat-676 当前实现分叉。最终 fetch 确认 `origin/unit/feat-676` 仍是 `80db8b9a604de15476dceb5e2e9a3c92d5fdf170`；本交付以它为 stacked PR base。父 PR #428 尚未合入，不能将本交付描述成 main 或生产可用。

本轮读取的 main 为 `631b611ea80e4576e98e30697df3ef854f7a59c2`；相对指定开发基线，main 唯一新增提交为 feat-676 的新 Dreaming 设计文档，没有产品实现增量。本任务不将这份新目标设计覆盖成当前候选实现，不改变用户指定的分叉基线；日后父分支实施新机制时需单独核对 adapter。

报告内 `51b23e42b` 为实现审查 diff 起点（review_diff_base）；工作流的 executed main snapshot 为上述 `631b611ea`。各实现/CLI 门禁的 validated_at 均为 `97a8b1683`，effective_base 为 stacked base `80db8b9a`。此后只提交门禁记录、完成状态与整目录归档、修复归档相对链接；运行代码、测试、配置和产品上下文不变，因此这些门禁保留有效，不重跑未受影响的全量测试。

M1 已完成本轮框架交付范围；整 unit 归档不表示真实模型效果已验、PR 已合并或已部署。正式 benchmark 与真实模型/judge 始终 not_run，留给用户之后决定启动。

## 2026-10-29 latest memory branch compatibility

用户要求更新评测代码以测试最新记忆分支。本轮仍只更新可运行候选并使用确定性 provider 验证，未选择正式题集或启动真实候选/judge。

- 同步前 HEAD `25a89c61e`；上游固定为 `origin/unit/feat-676` 的 `3e9a46030939bfcce351b7df2e29e5f3c2439055`；无冲突合并记录 `117873fd1`。保持已有 PR #429 与原开发 worktree，不改主仓现场。上游 PR #428 已通过 CI，仍未合入。
- 复现：只合并并重新安装/构建后，原生准备测试失败，旧 fixture 仍解析逐单元 File list 并提供旧 finish 参数。日志 `/tmp/feat677-sync-before.log`：prepare=failed、1 次受控请求、without finish；未被错误判为 ready。
- 适配：fixture 使用新的直接批次输入、批次级 finish；准备的 toolAllowlist 包含既有 contextTools，使原生 Dreaming 恢复可用。配置和示例删除退役的 maxSteps/maxRunMs，CLI 拒绝含旧字段的配置，README 给出修改方法；评测 timeoutMs/maxModelCalls/maxOutputTokens 保持。
- 历史导入、真实 Dreaming start/status 完成判断、封存/冷恢复和通用 Runner/judge 无需改动。candidate adapter 标记为 v2，protocol 不变。没有改写产品 Memory/Dreaming，也没有新增 IM、任务或维护实现。
- 已有测试处置：rewrite-merge `fixtures/evaluation.ts`，让输入容量低于长消息以触发真实连续分批；扩展现有 evaluation-runtime 主旅程验证 source_history、notes/history 和换窗后恢复成功、维护笔记不进入冷答题。保留全部数据、Runner、评分、预算、进程清理保护；CLI 既有测试增加退役配置拒绝。没有新增平行测试文件。
- 窄验证：`pnpm install --frozen-lockfile`、候选相关包 build 通过；5 files / 13 tests 通过（`/tmp/feat677-sync-targeted.log`）。typecheck、全量 build/回归及独立复核随后追加结果。
- Gate 2 retained：需求、三个候选接口、信息边界与阶段限额均未改变；旧设计已明确允许随产品更新 adapter，新增说明只标识当前接线。独立 implementation review/verification 和 CLI 受影响验收需针对最终版本重做；旧数据/judge/Runner 门禁可按不变范围保留。
- 当前 main `c61b7629a` 相对指定父分支只有无关 bugfix-678 设计文档；本轮继续使用用户指定记忆分支，不把新设计文档误当产品实现。
- no spec delta。新版准备允许业务原文回查和维护恢复；答题仍只读取封存记忆。LongMemEval 缺少子任务轨迹，不能据本次通过声称验证了任务提炼质量；没有独立 IM，conversations 不开放。生产状态未变化。

### 同步后的最终门禁

实现冻结 `93c8e305bf30de6f0354510f3d9e8eee46b293c1`；executed_base（当时 main merge-base）=`082e72ec4becb37d4ba08c3e3a8e0d2bf45da087`，effective_base（指定父分支）=`3e9a46030939bfcce351b7df2e29e5f3c2439055`。交付前重新 fetch 父分支，仍为同一 SHA。

- 独立 code review + verifier Round 2：pass，findings=[]，0 CRITICAL / WARNING / SUGGESTION；CLI acceptance Round 2：pass，0 问题。报告均追加在原文件，没有覆盖初次证据。
- 独立原生探针：6 个准备批次、66 次确定性请求；source_history 读到原长消息尾部，换窗后原批次输入退出活动上下文，再经 notes/history 恢复；最终 prepare=ready、answer=completed；冷答题无原历史或维护笔记，越界拒绝 2 次，两个进程均退出。完整合成证据位置见 Round 2 报告，不提交运行产物。
- `pnpm build`、`pnpm typecheck`、`pnpm check:ios-runtime`：通过。日志 `/tmp/feat677-sync-{full-build,typecheck,ios-runtime}.log`。
- `pnpm test`：170 files / 867 tests passed，132.62 秒，日志 `/tmp/feat677-sync-tests.log`。
- `pytest -m 'not e2e' -q`：127 passed / 28 deselected，日志 `/tmp/feat677-sync-python.log`。
- 示例 plan：1 题 / 2 会话 / 4 消息，modelCallsStarted=0，日志 `/tmp/feat677-sync-plan.log`。只有合成数据，没有正式评测分数。
- Web 与原生 iOS 产品文件仅来自父分支原样 merge，无本 PR 自有改动；保留父 PR #428 在 `3e9a46030` 的远端 Web/iOS 成功证据，未重复本地 UI 验收。远端 PR #429 的本轮检查另按最终提交核对。

后续只提交本节和三个独立门禁报告，运行代码/测试/配置不变，`93c8e305b` 的适用验证保留有效。PR #429 继续以 unit/feat-676 为 base；本轮不合并、不部署、不开始真实评测，worktree 保留供后续运行。

## 2026-10-29 chronological preparation revision

用户确认统一时间回放方案，并明确授权实现后只跑此前选定的一道完整 LongMemEval 题。原先集中导入试跑已中断：27 次真实准备请求、3 批完成，无答题/评分；原始产物在 `/Users/czj/.local/share/nano-evals/longmemeval-one-case-20261029-202747/`，保留 incomplete 及 interruption-note，不算作时间回放结果。

- 冻结父基线仍为 `3e9a46030`；重新 fetch 后无新增父实现。复用开放 PR #429、原开发分支/worktree，不改主仓。首文档/设计修订 `a524e3b90`；独立设计 Round 2 Approved，0 CRITICAL / WARNING。
- 实施：Dreaming 包内宿主时钟与准入时点查询复用正常 timing，默认生产 timer/step 行为保留。Nano adapter 将空来源基线与逐 session 追加拆开，按逻辑时间跳转到真实自动准入点；同刻会话先整体追加，已触发工作结束才推进时间。末尾不手动启动、不跳未来，允许尚未触发积压；已触发失败/超限停止。全局 Date、真实预算计时、Runner 和 judge 不变。
- 证据：协议 v2 / candidate v3；计划解析实际周期与静默值，默认值由 product-contracts 与产品共同使用。请求增加逻辑时间/已导入会话数，timeline 逐条保留到达、准入结果和冻结状态。逐段 source-map 与 usage 持久化，中途失败不再把未导入历史计入收据。
- 已有测试处置：rewrite-merge `evaluation-runtime.test.ts` 主旅程与 fixture，用实际收到的原文/已读取记忆形成内容，覆盖未来历史回查为空、后到纠正、末段未触发积压、同刻原顺序、冷答题、原文长消息及维护恢复；保留预算/挂起截止/退出。新增同文件零到期/空记忆旅程，保护末尾不能强制整理。扩展既有 scheduling 测试保护到期时新活动重新延后，CLI 保护新协议和有效周期展示；通用 Runner 不新增内部批次断言。
- 红证据 `/tmp/feat677-timeline-red.log`：单段未到期历史在旧 adapter 发出 11 次确定性请求，预期 0 失败。原生多批测试首次失败来自 fixture 在无住址依据时写 unknown，随后修改正文却保持入口不变，被既有保存规则拒绝；工具结果证据保留在 `/tmp/feat677-timeline-debug-pCAyRa/`。修正 fixture 为无证据 no-change、正文改变同步入口，没有修改产品保存规则。
- 窄验证：相关包 build、`pnpm typecheck` 通过；`pnpm exec vitest run evals/memory packages/dsh-integration/tests/evaluation-runtime.test.ts packages/dsh-integration/tests/dreaming-scheduling.test.ts packages/dsh-integration/tests/dreaming-runtime.test.ts packages/dsh-integration/tests/dreaming-cycle-runtime.test.ts`：8 files / 19 tests passed（50.59 秒）。日志 `/tmp/feat677-timeline-{build,typecheck,targeted}.log`。
- no spec delta：生产准入行为与唯一记忆写者不变，权威评测协议更新到 suite README；没有客户端、生产迁移或部署工作。后续追加本轮独立门禁、全量检查与一道真实试跑结果；在这些证据产生前不宣称新实现已完整验收或已有分数。
