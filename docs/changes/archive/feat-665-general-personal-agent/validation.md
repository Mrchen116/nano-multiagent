# Validation ledger

独立审查与真实验收已完成适用的交付门禁；58 项完整模型 case 并未全部通过。每种证据保持自己的适用范围，不合并为一个“全通过”。

- [M1 memory worker evidence](M1-memory/evidence.md)
- [M2 proactivity worker evidence](M2-proactive/evidence.md)
- [M3 execution/delivery worker evidence](M3-delivery/evidence.md)
- [Independent product acceptance](acceptance.md)
- [Independent code review](code-review.md) / [verification](verification.md)

## Local CI snapshot

`bd1cb8cf0`，支持的Node24.22.1：完整`pnpm build`、`pnpm typecheck`、`pnpm check:ios-runtime`通过，日志`/tmp/pa665-final-{build,typecheck,ios-runtime}.log`。完整native/IM suite 149 files /794 tests：792通过，knowledge-policy与task-execution-limits两个等待超时；同两文件低并发独立重跑6/6通过（`/tmp/pa665-final-test-recheck.log`），没有隐藏首次失败。

Python辅助/架构70 passed/43 deselected，ruff check/format通过，docs283通过（`/tmp/pa665-final-{pytest,ruff,ruff-format,docs}.log`）。Web108 files/1031 tests通过（`/tmp/pa665-frontend-tests.log`）；`npm audit --audit-level=critical`通过，仍有非critical既有依赖报告，没有顺带升级依赖。

后续forget/child-delivery改动使用对应native与实际层回归，并对三个受影响包重新build通过（`/tmp/pa665-child-return-build2.log`）。同一代码不因review交接机械重跑全量；最终归并后仍须docs/类型与远端required CI完成，届时补明确head。

## 最后已观察边界的修复

- `a4a0f9a55`：I02真实owner消息被相邻peer拒绝误清除。原失败`/tmp/pa665-runs-v5/candidate-I02-r1/results`；定向红测`/tmp/pa665-adjacent-red.log`，修复后Global/Inbox/PA三文件80/80，独立复验`/tmp/pa665-independent-round8.log`同为80/80。真正来源撤权仍清源，拒绝单条只退役该消息，保留邻近主人输入。
- `06d8041bf`：M08真实7924字长输入两片均被读入，却因每片partial标志丢原交办来源，完成回执requires_attention。`/tmp/pa665-fragments-red.log`复现；同轮live同消息分片齐全才恢复，单片/跨轮/跨源/历史不授予；原生来源+delivery19/19，独立`/tmp/pa665-independent-round9.log`19/19。
- EvaluationClient只在取headers前续fixture登录，保持实际动作不重放；独立HTTP/clock探针证实1次login/0业务mutation。12协议测试通过，`ruff check .`及95个Python文件format check通过。
- 最后source树的全workspace typecheck通过（`/tmp/pa665-final-source-typecheck.log`），DSH与PA受影响包分别build通过（`/tmp/pa665-fragments-build.log`、`/tmp/pa665-adjacent-build.log`）。其余全量构建/Web/native首次timeout及重跑证据按上表保留；不伪称某一次全量毫无失败。

完整case与核心重复的实际分类见[evaluation](evaluation.md)，与产品代表验收分列。归档后的文档检查与远端required CI在最终交付补记。

## Final synchronization and delivery

- executed_base / effective_base: `85910853ebe4a7a22c5b761029cf46da2f78cd5a`; final fetch confirms origin/main unchanged.
- Final source: `06d8041bfcc16870ab3af9a0f8379ffa621c305c`; final independent code/verification validated_at: `fb792c8d22b5f75d252b58bba4949152a7806380`, report commit `dc696c5a0`. Product acceptance is recorded at `57fd15853` with per-journey version receipts.
- All applicable pre-PR gates pass; no blocking/major product issue or static finding remains. PA-2 first-draft wording is a retained minor. Corrected delta R7 remains aligned.
- effective_through: the final archive/PR head, whose exact hash is recorded in the PR. After the validated tree, only review reports, current-spec promotion, documentation routing and whole-unit archive changed. No product, test, eval adapter or prompt changed, and no main increment exists; existing code/Context/product conclusions are retained.
- Current specs incorporate all four corrected deltas; the entire unit is archived, including original failures and review history. Final documentation integrity passes (271 maintained Markdown sources / 68 routes, `/tmp/pa665-archive-docs.log`); the archive checker explicitly verifies `unit/feat-665-general-personal-agent` because the actual `codex/` branch prefix would skip its branch-name dispatch. Remote CI is recorded by the PR checks, not predicted here.
- Isolated evaluation/acceptance stacks, dedicated proxy and idle task-owned tmux sessions are stopped; the temporary proxy credential file is removed. Raw evidence remains available at the paths in the reports. The feature worktree is retained for PR review. No production operation, merge, package release, live purchase or external contact was performed.

## First remote CI and fixture-module correction

CI run `40341170257`, head `16cc51fad2cd0e63b7e3a937158a7aed3fca2799`: frontend passed; backend build/typecheck/packaged runtime and all **149 native/IM files, 801 tests passed**. The Python gate failed only because the newly added evaluation runner grew to 432 lines, above the repository's 400-line per-file limit. Local reproduction is `/tmp/pa665-ci-size-red.log`; the earlier local Python result predates the final runner additions and did not prove this final size check.

The evaluation login client, authenticated request helper and isolated-manifest validation move unchanged to `fixture.py`; the runner now imports them, and the protocol test imports manifest validation from its owning module. An AST comparison confirms every original runner class/function is unchanged. No product, prompt, adapter scenario, receipt or adjudication behavior changes. Protocol plus naming/size contract: **14 passed**, `/tmp/pa665-ci-size-green.log`; full ruff check and 96-file format check pass. This is a limited post-PR test-harness organization correction; existing product/Context/58-case evidence remains valid. Remote CI must rerun on the updated head; the failed first attempt remains recorded.
