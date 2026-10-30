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

### 时间回放实现冻结与独立验证

运行代码冻结 `13fff74b2ccb3d82e62638108a96363adea82fee`；review diff=`a524e3b90..13fff74b2`，effective_base=`3e9a46030939bfcce351b7df2e29e5f3c2439055`。

- 独立 Round 3 code review：findings=[]；verification delta=pass/aligned，0 CRITICAL / WARNING / SUGGESTION；CLI targeted acceptance=pass（无真实模型的机制验收）。三份报告追加保留旧轮。
- 独立原生探针核实常规时间回放、quiet=0 周期边界同刻全部会话先到达、provider 失败立即停止；对应 82 / 72 / 1 次确定性请求，3 个子进程均退出。证据根和最终模型输入观察见 Round 3 报告。未用真实模型或 judge。
- `pnpm build`、`pnpm typecheck`、`pnpm check:ios-runtime`、docs-check、ruff check/format、archive check 通过；`pnpm test`：170 files / 868 tests passed（151.60 秒）；`pytest -m 'not e2e' -q`：127 passed / 28 deselected。日志 `/tmp/feat677-timeline-{full-build,typecheck,ios-runtime,tests,python,ruff,ruff-format}.log`。
- 单题计划：1 question / 53 sessions / 550 messages；默认 interval=86400000ms、quiet=600000ms；prepare 40 请求/600秒，answer 12 请求/180秒，judge 1 请求/120秒。模型与上一题一致，尚未执行本轮真实请求。保留父分支原生 UI 证据，当前修改无 Web/iOS 用户流程。

后续真实试跑不自动提高限额、不重试候选、不扩题；失败或 incomplete 作为该次真实结果保存，不以机制通过推导记忆质量通过。

## 2026-10-30 single Global native-window revision

用户确认“一题一个 Global、一个持久 session、每段原对话一个原生 window”；本轮只做实现与确定性验证，不沿用已执行的一题真实试跑授权。父分支已提交的 input.md 删除和正常 turn/end 完成逻辑通过 `9e5cfd6cc` 原样合并，本次不重写产品 Dreaming。设计冻结 `cb296e8af`，Round 3 唯一 Runbook 授权冲突已在 Round 4 关闭，Approved / 0 CRITICAL / 0 WARNING。

- `evaluation/history.ts` 通过公开 SessionPersistence 和 detached Session 物化同一根中的原生 compaction 边界及真实 surface replacement；保留原文、段 ID、日期与连续 turn/callId，source-map/timeline 增加根和窗口定位。没有业务摘要、Notes、额外模型请求或 DSH private import。
- `evaluation.ts` 只注册一个根 binding 和主人聊天目标。`evaluation/runtime.ts` 首次基线时保留空根冷态；自动整理前 resume，同步等待 parent/maintenance idle 并 flush/dispose 后再导入下一窗口。owner 和游标不重建；仅对 native 异步 close 的单写者交接作有界等待。
- 原生 Session.create 对带 seed 的 detached 恢复会补 `session/end-seed`，首次实现漏持久化该结构事件导致 seq 从 1 起写入空流而失败。现在显式提供并保存同一个 restore marker，所有原始逻辑时间均写入持久日志，无全局 Date 改写。最终结果以 targeted 日志为准。
- candidate v4 显式记录 single-global-session / dataset-session-as-native-window / one-owner-conversation；稳定 protocol v2、Runner、题目与 judge 不变。canonical 使用说明更新在 `evals/memory/README.md`；no spec delta，无部署迁移。

### 测试策略与已得证据

- 扩展既有 `evaluation-runtime.test.ts` 和共享 fixture（rewrite-merge），不新增测试文件。原生持久化观察器仅在 fixture 记录宿主实际写入；恢复后验证当前 surface、History 完整原文、唯一根/目标、连续调用身份和原时间。旧实现先出现四窗口断言失败，日志 `/tmp/feat677-window-red.log`。
- 同一真实运行时旅程改为从实际 Source directory 取唯一 root；验证早期只有已到达窗口、后续列出同根多窗并读取旧窗完整长消息、维护自身换窗/notes/history 恢复、冷答题无旧原文或维护笔记。fixture 使用父版本正常完成响应，未调用退役 finish 工具。
- 保留零到期、请求预算、超时杀进程、Runner/评分/CLI 既有保护。新增同文件四窗无到期旅程，保护真实持久化和恢复，不按 Dreaming 私有批次数设通过条件。
- `pnpm --filter @nano/dsh-integration... build` 通过；`pnpm exec vitest run packages/dsh-integration/tests/evaluation-runtime.test.ts evals/memory` 5 files / 15 tests 通过，日志 `/tmp/feat677-window-targeted.log`。无真实候选/judge 调用，所有测试目录和子进程由既有 finally 清理。
- 独立门禁与本地检查见下节；不会将确定性机制通过写成真实模型效果提升。

### 窗口修订的独立门禁与交付检查

实现 `785c1ec7c`，冻结审查版本 `8ced1ccd7da12a6437a90927f8b2d632c4bcd66c`；review diff=`cb296e8af..8ced1ccd7`，effective parent=`efaa2bbae3e21f8835fea477b1085c8efb7f0c93`。最终 fetch 未发现父分支新增提交；executed main snapshot=`9bf2b13da`，与 HEAD 的 merge-base=`082e72ec4becb37d4ba08c3e3a8e0d2bf45da087`。本轮继续用户指定的 stacked base，不合入 main 的无关 bugfix-678 设计文档。

- design Round 4 Approved；code-review / verification / acceptance Round 4 全部 pass，零存活发现。独立静态探针验证四窗单根、两次同根恢复后的活动正文替换、旧长原文读回、baseline 与游标连续、冷交付 Paris 和两次越界拒绝；另一个四窗未到期探针零请求。完整证据与进程退出核实见三份报告。
- 独立 CLI 默认 plan：protocol v2 / candidate v4 / modelCallsStarted=0；未授权 run/score 均 exit 1；自检 5 files / 15 tests passed。新增一次真实模型或 judge 调用数均为 0。
- `pnpm build`、`pnpm typecheck`、`pnpm check:ios-runtime`、docs-check（283 sources / 68 routes）、ruff check/format、archive check 通过；Python 127 passed / 28 deselected。日志 `/tmp/feat677-window-{full-build,typecheck,ios-runtime,docs,ruff,ruff-format,archive,python}.log`。
- 默认并发 `pnpm test` 为 875 passed / 2 failed：`agent-disable-native` 的 B 清理返回 kill EPERM；`task-execution-limits` 未在等待期限内达到完成条件。完整失败日志 `/tmp/feat677-window-full-tests.log`。未修改这两个测试或对应产品；单 worker 隔离复跑 2 files / 8 tests passed，日志 `/tmp/feat677-window-failures-isolated.log`。根因尚未确认，不能称为已修复。
- 因上述全量失败，追加 `pnpm exec vitest run --maxWorkers=2` 全套验证，结果日志 `/tmp/feat677-window-full-bounded.log`；最终状态连同 PR 当前 head 的远端 CI 记录在 PR Validation 与交付回报。没有 Web/iOS UI 自有改动，保留父分支适用产品证据。

此后只追加独立报告和本检查记录，运行代码/测试/配置未变，`8ced1ccd7` 的专项与审查证据 retained。PR #429 继续以 `unit/feat-676` 为 base；未合并或部署，开发 worktree 保留。旧 v3 incomplete 结果保留原构造身份，本轮不产生正式效果分数。

## 2026-10-30 persistent PA context parity revision

用户要求对齐真实 PA 与主人的常驻关系，并检查评测引入的不必要 Context 差异。父基线更新为 `c2a7fe3c3`，已通过 `75f4794d3` 合并其模型容量预算实现；最终 fetch 确认没有更新。原始实验配置、答案和轨迹保留，本轮不追加真实候选或 judge 调用。

- `a992a059d`：准备/答题复用 PA、owner、binding、conversation 与 Global session 身份；冷进程只恢复正式记忆和必要状态。通过 evals composition root 组合实际 GlobalAgent、InboxStore 和 NodeStore，统一唤醒、来源字段、Inbox 消费、回复前重核及交付。
- 首轮之前同步来源资格；开放包内 nano-memory、答题自身 Notes/History/换窗、当前私聊查询及原生内部委派。文件边界继续隔离原历史、维护笔记、控制数据和其他题。candidate v5 记录实际 PA build、adapter 和技能；protocol v2 不变，Gateway/PA no spec delta。
- Dreaming 正常评测直接使用产品按实际模型容量计算的完整首请求预算，不另设固定材料上限。按用户纠正移除当前说明中的旧固定值解释；产品本身的可选材料配置仍按公开契约解析，确定性 fixture 的较小材料量只用于覆盖连续批次。
- 独立 acceptance Round 5 通过；code review / verification Round 5 发现真实遗漏：默认后台 child 尚未回传时根已 idle，评测提前关闭并判失败。原始独立探针和 finding 保留于报告。
- 修正使用 DSH 公开 subagent/start/end 生命周期，在隔离候选内等待已启动 child 全部收口并再次等待根后续工作 idle；不终止正常委派、不延长阶段限额。扩展既有 evaluation-runtime 主旅程的第二次冷答题及 fixture，子 Agent 延迟 1200ms、读正式记忆、回传并触发 PA 公开交付；核对实际请求已消费 child 结果和全树调用用量。没有新建平行测试文件。
- 红证据 `/tmp/feat677-pa-child-red.log`：旧实现第二次答题 failed/no public answer；最终 targeted `/tmp/feat677-pa-child-final.log`：5 files / 15 tests passed（24.12 秒）。实现构建通过；独立复验和完整交付检查随后追加。

### PA 接线最终门禁与交付检查

运行实现冻结 `de2b92942e5f4b03c9b6d86d2e13da510e3e3743`；整体 review diff=`75f4794d3..de2b92942`，修复增量=`a992a059d..de2b92942`，effective parent=`c2a7fe3c3727db2c557a28915fda6ccee5e4298e`。本轮末尾仅追加报告和记录，运行代码/测试/配置不变。

- acceptance Round 5 pass；code-review / verification Round 6 pass，原 WARNING closed、零存活发现，其他未失效证据 retained，no spec delta。
- 独立原失败探针现为 completed/Paris，8 次实际请求与 usage 一致；5 次全树请求上限及 child 等待期间的 5 秒截止均生效，相关 PID 全部退出。详见两份 Round 6 报告。
- `pnpm build`、`pnpm typecheck`、`pnpm check:ios-runtime`、docs-check（283 sources / 68 routes）、ruff check/format、archive check 全过；`pytest -m 'not e2e' -q`：127 passed / 28 deselected。
- `pnpm exec vitest run --maxWorkers=2` 全套 170 files / 883 tests passed（375.30 秒）。本轮使用已知可复现的两 worker 配置，没有重跑默认高并发；先前默认并发/远端偶发失败的根因未在本轮声称修复。日志 `/tmp/feat677-pa-{full-build,typecheck,ios-runtime,docs,ruff,ruff-format,archive,python,full-tests}.log`。
- 默认 plan：1 题 / 2 sessions / 4 messages、modelCallsStarted=0，candidate v5，Dreaming 无额外材料上限，日志 `/tmp/feat677-pa-plan.log`。确定性 provider 验证接线与执行生命周期，不证明真实模型策略或记忆质量；本轮真实候选/judge 调用均为 0。

PR #429 保留 `unit/feat-676` base；最新 head 的远端 CI 结果单独记录在 PR。未合并、未部署；保留开发 worktree 供 review 和后续运行。用户已要求保留的旧单题只读查看入口继续运行，原始轨迹/配置不改写；本轮测试进程已退出。
