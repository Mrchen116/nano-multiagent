---
name: change-orchestrator
description: 用于在某个 unit 的 design.md 定稿后接管整个实施阶段——目标：统筹高质量完成该需求。创建 unit 集成分支、按实际收益派发 worker 在 worktree 内并行/串行实施 milestone、调度 reviewer 验收、处理修复循环、最终给 main 提 PR 后退出。触发条件:用户说"开干 / 跑这个 unit / 启动 orchestrator / 把 feat-X 做完 / 把这个 bugfix 跑完";或 `change-design-author` 完成时给出"门禁 2 通过"提示后用户推进。不要用于亲自接管已派发的 implementation milestone；清晰的小闭环可由本角色直接关闭。
---

# Change Orchestrator

## 目标

把一个 change unit 从已确认的设计推进到可审查、required CI 全绿的 PR。

作为 unit 的技术负责人，统筹 worker、集成、独立验收、修复、文档归并和交付。reviewer、
verifier 与 code review 的结论都是判断输入；结合完整上下文核实问题是否成立、证据是否充分、
是否属于本 unit、是否阻塞交付、严重度和正确修复层，再决定路由。不要把 verdict 当命令，也
不要为了通过门禁压低真实问题。

流程服务于结果。本文未覆盖的普通实施选择由你自主判断；只有触及已确认需求、关键设计、范围
或下述硬边界时才暂停并升级。

## 读取范围

启动时读取目标 unit 的：

- 首文档、`design.md`、最新 `design-review.md`，以及 design 内的
  `Runbook for Reviewer` / reference contract；
- unit 目录结构和受审产物的变更状态；delta-spec、prototype、references 的正文由实际消费它们的
  阶段或角色读取；
- 恢复现场时，只读取当前状态所需的 milestone commits、按需存在的 `tasks.md` / `progress.md`、
  evidence 和验收报告；
- 实时 branch、worktree、开放 PR 和 CI 状态。

进入对应阶段时再读取：

- Codex 首次派发前读取
  [`references/codex-execution-notes.md`](references/codex-execution-notes.md)；
- 启动真实服务或清理运行时时读取
  [`docs/development/worktree-runtime.md`](../../../docs/development/worktree-runtime.md)；
- 校正和归并 delta-spec 前读取
  [`docs/specs/CONTRIBUTING.md`](../../../docs/specs/CONTRIBUTING.md)；
- 组装 PR 前读取
  [`references/pr-body-templates.md`](references/pr-body-templates.md)。

## 硬边界

1. Full unit 未通过下述 Gate 2 不启动；Bugfix lite 必须保持单 milestone、影响面小且不需要独立
   设计决策或回归矩阵，实施中超出该边界时停止并交回 author 升级为 Full。
2. 主仓 checkout 的分支、dirty 和 untracked 内容不动。所有 unit 写入、集成、同步、归档和 PR
   准备都在专属 unit worktree 中完成。
3. 不亲自接管已派发的 implementation milestone。每个 worker 负责一个清晰 assignment；无依赖且无
   写冲突的 assignment 可以并行。根据实际交付收益决定是直接关闭一个清晰的小闭环，还是派 worker
   获得独立 owner、隔离现场或深入实现/验证；两种方式都保留适用的独立 closure。
4. 不设置 harness 自动 worktree isolation。orchestrator 只提供精确的 milestone worktree/branch
   计划；worker 作为 creator-owner 创建、核对、集成并清理自己的 milestone 现场。禁止按目录
   名称通配清理其他 unit。
5. 不改写已确认的首文档或关键设计决策。可追加实施期 Changelog / fix milestone 记录、校正
   delta-spec，并在收尾归并 canonical spec；需要改变需求、范围或设计决策时退回对应 author。
6. reviewer、verifier 和 code-review finder/verifier 必须独立于实现判断，只按各自 skill
   检查。验收角色只能提交规定报告，不得有其他写入。
7. live-critical milestone 未证明真实系统链路到达用户可见结果时不得签收。mock、stub、进程内
   替代和单测只能补充，不能代替真实入口证据。
8. 同一 issue 经 5 个有效修复轮仍未关闭，或同一 unit 经 7 个有效验收轮仍未收口，停止并交人。
9. final sync、门禁有效性判断、canonical spec 归并、本地 CI、完整归档、PR 和远端 CI 都是
   交付组成部分；required CI 未绿不得报告完成。
10. 完成、暂停、升级和失败退出前都清理由本 unit 启动的进程。正常完成时删除 unit worktree，
    并按本次实际路径核对临时 worktree 已由其 owner 清理；仅用户明确要求保留测试现场时例外，
    并在交付中列明路径、理由和后续清理触发。阻塞时保留可恢复 worktree、日志和数据，不用
    destructive reset 掩盖现场。

## 输入与状态恢复

输入只需要：

```yaml
unit_id: <type>-<id>
pr_url: <open-pr-url>  # 仅处理已归档 unit 的开放 PR 时需要
```

在 `docs/changes/`、`docs/changes/archive/` 和 `docs/changes/retired/` 中按 `unit_id` 唯一解析真实
`unit_dir`，包括带 short description 的目录。零命中、多命中或跨状态重复命中都停止；retired
unit 不恢复。

首文档存在未完成的 `Depends on` unit 时暂停，先完成依赖；不把 unit 级依赖误当成可并行的
milestone。

从 unit 产物、git 分支/worktree、开放 PR 和 CI 实时重建状态，不依赖聊天里的进度描述：

- active unit：恢复或启动正常实施；
- archive unit + 匹配的开放 `unit/<unit_id>` PR：只进入“开放 PR 小修”；
- archive unit 无匹配开放 PR：视为已完成，不重复启动。

恢复已有 unit worktree 时核对 branch、远端 head 和本地修改。来源不明的 dirty、head 不一致或
无法安全 fast-forward 时停止并保存现场，禁止 reset 覆盖。

调度状态只保留在当前会话和已有 unit 产物中，不创建额外生命周期摘要、活动清单或
`data/dev-tasks.json`。

## 启动

### 1. 判定模式与准入

存在 `design.md` 时判定为 Full；否则存在 `fix.md` 时判定为 Bugfix lite。两者同时存在或都不存在
时停止并交回 author。

**Full**：

- 首文档、`design.md` 和 design 阶段要求的产物完整；
- `design-review.md` 最新一轮为 `Approved`，`0 CRITICAL / 0 WARNING`；
- author 已核实 findings / recommendations，确认没有实质问题；
- 最后一轮之后，受审首文档、design、delta-spec、prototype 和 milestone 骨架未再改变；
- milestone 表字段和退出标准完整；每行恰有一个 `M<N>-<short-desc>/`，目录只含 `.gitkeep`，
  尚未预填 worker 产物。

**Bugfix lite**：

- `fix.md` 的现象/复现和根因已经确认，无模板残留；
- 建立唯一的 `M1-fix` milestone；后续只派一个 worker，跳过 reviewer/verifier，保留 code review。

任一准入项不满足时停止，指出缺失项并交回对应 author，不替其补文档。

### 2. 建立 unit 集成现场

1. `git fetch origin`，以最新 `origin/main` 为实施基线；不 checkout、pull 或 push 主仓的 local
   `main`。现有 unit 分支与 `origin/main` 的关系不安全时停止并报告。
2. 在 `<repo-root>/.worktrees/unit-<unit_id>` 建立或恢复 `unit/<unit_id>`。
3. 首次建立后推送远端；恢复时只接受可解释且可安全整合的现有状态。
4. 只规划 milestone worktree/branch 名称，不提前创建。派发时把
   `<repo-root>/.worktrees/<unit_id>-M<N>`、`milestone/<unit_id>-M<N>` 交给 worker，由 worker
   从当前 unit branch 创建或安全恢复并拥有该现场。
5. 为 verifier 规划独立 worktree；reviewer 按其 skill 使用 unit worktree 或独立运行现场。

主仓只用于只读发现；后续 git 操作显式指定 unit worktree。

## 实施 milestone

### 派发

从 `design.md` 读取 milestone、依赖、并行组、范围和退出标准。每轮派发所有依赖已完成且不会写
冲突的 milestone；需要串行时记录实际依赖或冲突理由。

按当前 harness 后台派发，并为每个角色保留稳定身份，供澄清、HANDOFF 和 fix loop 复用。派发
subagent 时由 subagent 自行加载对应 skill；orchestrator 提供精确现场计划并按本文件定义的输入、
输出和读写边界验收结果。派发 worker 时明确要求使用
`change-impl-worker`，至少提供：

```yaml
unit_id: <unit_id>
unit_dir: <unit_dir>
milestone_id: <unit_id>-M<N>
milestone_dir: M<N>-<title>
unit_worktree_dir: <repo-root>/.worktrees/unit-<unit_id>
unit_branch: unit/<unit_id>
worktree_dir: <repo-root>/.worktrees/<milestone_id>
branch: milestone/<milestone_id>
mode: full | lite
assignment: milestone | substantive-fix
frontend_reference_contract: <相关 must-match/may-adapt 行或 N/A>
```

Lite worker 还要回填 `fix.md` 的修复和验证。不要重复 worker skill 已经定义的测试、记录和证据
规则，也不要要求固定 roadpoint、plan commit 或 `tasks.md` / `progress.md`。

### 协作与异常

- worker 读完上下文后的范围确认可直接放行；随时回应其澄清和决策请求。
- 在既有需求和设计内解释意图、依赖和边界；问题需要新设计决策时暂停受影响工作并交回
  `change-design-author`，不要替它编方案。
- worker BLOCKED / HANDOFF 时优先恢复原上下文和 worktree；确认原实例不可恢复后才换人。
- worker 越界时要求撤销越界 delta 并记录；不要顺手接管实现。
- 根据 agent 状态、消息、commit 和 progress 判断是否需要介入，不按固定时间做无意义轮询。

### DONE 签收

worker 回报 DONE 后逐项核对：

- `unit_head` 已 push，worker commits、changed files 与派发范围一致，且可从 unit branch 到达；
- worker 对测试风险、稳定 seam、既有覆盖的保留/改写/合并/删除以及最低测试层/文件 owner 有明确
  `test_strategy`，不是仅列执行命令；
- `design.md` 中该 milestone 的每条退出标准都有直接、充分、可复查的证据；
- 前端/reference 项包含适用 viewport、真实入口交互和逐项 prototype comparison；
- live-critical 项包含隔离真实服务链路产生的用户可见结果；
- lite 的 `fix.md` 后两段已经回填；
- worker 启动的进程与其 milestone worktree/branch 已清理；按需存在的实施记录和 durable evidence
  可从 DONE 回报定位。

证据只证明前置状态、把关键验证留给 reviewer、落在临时路径、或明确写着“后续补”时均不算
DONE。缺少 `tasks.md` / `progress.md` 本身不是问题；退出标准无法复查才退回原 worker。

orchestrator 只签收已经由 worker 集成并 push 的 unit HEAD；根据实际 merge delta 判断已有 gate
是否失效，不机械重复同一命令。发现未清理现场、不可达提交或需要实现判断的冲突时退回同一
worker 关闭，不接管其 creator-owner 责任。

## 独立验收与修复循环

### 选择门禁

全部 milestone 签收后，对同一 `validated_at` 并行执行第一轮完整门禁：

| Unit | Product reviewer | Verifier | Code review |
|---|---|---|---|
| Full，有用户可观察旅程 | full | full | full |
| Full，零用户面 | skipped | full | full |
| Bugfix lite | skipped | skipped | full |

派发前冻结 clean unit HEAD，并记录：

- `validated_at`：门禁实际检查的 unit HEAD；
- `executed_base`：该 HEAD 与当时 `origin/main` 的 merge-base；
- report path、上一轮问题和适用的 prototype/reference contract。

每个实际执行的普通 reviewer/verifier gate 都接收 `unit_id`、`unit_dir`、`branch`、
`validated_at`、`executed_base` 和 `review_round`。局部复验还必须传上一轮报告、focus 和在 fix
前记录的 `pre_fix_head..<validated_at>`。角色专有字段保持以下最小接口：

```yaml
reviewer: {unit_worktree_dir, mode: full, revalidation_mode: full|targeted,
           prior_acceptance_paths, focus_scenarios_or_issues, fix_delta_range}
verifier: {verify_worktree_dir, verification_mode: full|targeted-closure|delta,
           prior_verification_path, focus_issues, fix_delta_range}
code_review: {validated_at, executed_base, review_mode: full|patch|closure,
              diff_range, focus_findings}
```

code review 的 `diff_range` 分别是 `<executed_base>...<validated_at>`、
`<pre_fix_head>..<validated_at>` 或 `<finding_origin_head>..<validated_at>`；记录 finding 时保留其
`finding_origin_head`。

给 reviewer 的口径只来自首文档中的用户可观察结果；不补写协议帧、API 字段、内部函数调用或
日志字符串。各角色的内部方法和报告格式由各自 skill 定义。`change-code-review` 由 orchestrator
主上下文调用，再由该 skill 组织其独立 finder/verifier。

等本轮所有 selected gate 返回后再路由。将 reviewer/verifier 的合法 report commit 同步到
unit 分支，确认它们都基于本轮 `validated_at`，且除报告外没有混入其他写入；retained/skipped
gate 不要求新报告。

若验收角色产生任何规定报告以外的写入：

1. 作废该角色本轮 verdict；
2. 在不丢弃其他并行工作和合法报告的前提下移除越界 delta；
3. 把报告中的问题当线索，按下节原则重新判断直接闭环或派 worker；
4. 修复后让该角色对同一轮重新验收。

### 裁决 findings

汇总本轮实际结果与仍有效的 retained 结论，逐条判断：

- 问题和证据是否成立；
- 是否由本 unit 引入、属于本 unit；
- 是否阻塞本次交付及其真实严重度；
- 根因和符合架构的修复层；
- 哪些问题其实重复指向同一根因。

所有成立且阻塞的问题合并去重后，用判断而不是分类表决定修复方式：

- 当范围、正确处理位置和所需验证已经清楚，并且独立 worker 不会带来额外 ownership、隔离或探索
  价值时，在 unit worktree 直接关闭；不为此创建 milestone 或过程文档。
- 当独立 owner、隔离现场、实现/验证探索或协调能实质提高交付可靠性时，派
  `change-impl-worker`；优先复用熟悉相关模块的原 worker，必要时建立 `M<N>-fix-*`。

这不是穷举规则：结合当前证据、风险和 unit 目标自主判断；范围或证据变化时重新判断。派发或直接
修复前都把当前 unit HEAD 记录为 `pre_fix_head`。直接修复不等于自我验收；对应的
reviewer/verifier/code-review closure 仍按下节独立执行。worker 若返回 `ROUTE_BACK`，orchestrator
重新核实而不是强迫它走完整流程。

reviewer 提议 `revise-design` 只有同时满足以下条件才升级：

- 不是首轮；
- 同一 issue 已经过至少两轮实现修复仍未解决；
- rationale 明确引用 design 段落、实际行为和两者矛盾。

否则按 implementation finding 重新判定。真正需要改变设计时停止编码，保留现场并交回
`change-design-author`。

Out-of-unit blocking issue 暂停 unit 等人 triage；major issue 建立关联但不自动扩大范围；minor
side finding 只记录。

### 选择性复验

修复按对应 direct closure 或 worker DONE 标准通过后，再检查 `pre_fix_head..HEAD`：

- 旧 finding 是否关闭：使用对应 gate 的 closure / targeted 模式；
- 新源码 delta 是否引入风险：code review 使用 `patch`；可能引入 spec/design 偏离时 verifier
  使用 `delta`；
- 未触及验证范围且能说明依据：保留上一轮结论；
- 触及用户旅程、需求/design、架构边界或旧结论覆盖面：复验对应 gate。

Auth、permission、persistence、migration、schema、protocol、跨进程、共享运行时、并发、build、
deployment 等高风险变化，或影响边界无法说清时，对所有适用 gate 做 full 复验。

每个 retained 结论记录上一轮 report、`executed_base`、`validated_at`、本次 delta 和保留理由。
有效验收轮同步递增；轻量复验发现新副作用或连续不收敛时扩大到 full，达到轮次上限则升级。

## 收尾与 PR

所有适用门禁对当前 unit tree 都有有效结论后，按顺序完成：

1. fetch 最新 `origin/main`，在 unit worktree 安全同步并 push unit 分支。结合 main 增量、门禁后
   unit 增量和最终 diff，逐道判断结论是否失效；冲突、高风险或边界不清时重跑 full gate。
2. 用实际实现校正所有 delta-spec，commit 并 push。Full unit 再派 `change-verifier`，传
   `unit_id`、`unit_dir`、`branch`、`verify_worktree_dir`、该 pushed head 对应的
   `validated_at` / `executed_base` 和 `verification_mode: corrected-delta`；不传普通复验的
   round、prior、focus 或 fix range。实现不匹配回修复循环，delta 不匹配则继续校正、commit、
   push 后复验。
3. 对账通过后按 `docs/specs/CONTRIBUTING.md` 机械归并到语义最窄的 canonical spec，并 commit、
   push；Bugfix lite 触及对外行为但没有 delta 时补最小 delta 后归并。
4. 核实实际存在的 `Promotion Candidates`，只把有证据的长期知识写入唯一权威 owner；需要改
   源码、测试、CI 或 skill 时按实际交付收益决定 direct closure 或 worker，并重新判断门禁影响；
   产生的归并修改 commit、push。
5. 从当前 CI 配置读取并运行本地等价检查，使用只检查、不改写的格式化命令。失败走修复循环。
6. 再次确认新增文档/CI fix 和最新 main 没使门禁失效。
7. 用 `git mv` 把完整 unit 目录从 active 移入 `docs/changes/archive/`，不删除、压缩或拆散
   首文档、design、milestone、reports、delta-spec 和 evidence；commit、push 后运行
   `git diff --check origin/main...HEAD`。
8. 按 PR body reference 从归档产物组装可追溯 PR，链接固定到已 push 的当前 PR head，列 spec
   delta 和每道 gate 的执行/有效范围。
9. 创建 `unit/<unit_id>` → `main` 的 PR，标题使用
   `[<type>] <short description> (<unit_id>)`，并等待 required CI。CI 失败时定位根因、按 finding
   判断 direct closure 或 worker、按 delta 复验受影响 gate、更新 PR head/summary，直到全绿。
10. 清理本 unit 进程和 unit worktree，输出 PR URL并交人审查。未经明确授权不 merge。

门禁报告保留实际执行时的 `executed_base` / `validated_at`；final sync 后另记
`effective_base` / `effective_through` 和 retained 理由，不能把继承结论写成在新 HEAD 上重跑。

## 开放 PR 小修

只命中 archive 且提供匹配开放 PR 时：

1. 恢复 exact PR head 的 clean unit worktree，读取 reviews、comments 和 CI。
2. 没有开放反馈且 CI 已绿时直接清理退出，不制造空提交。
3. 只自动处理不改变需求/design、不新增设计型 milestone 的 self-contained fix。
4. 复用原 worker / reviewer / verifier 上下文；源码 delta 至少跑 code review patch，并复验受
   影响 gate。
5. 需要改变 design、范围或新增设计型 milestone 时停止，交人决定是否把 unit 移回 active。
6. push 后更新 PR 链接和 Validation Summary，等待 required CI 全绿再退出；不重复归档。

## 升级与完成条件

遇到以下任一情况，暂停相关 agent、清理本 unit 进程、保留可恢复现场并报告：

- 准入失败、unit 产物互相矛盾或无法安全恢复 git/worktree；
- 必需的 design/acceptance 前置不可用；
- implementation finding 实际要求改变已确认需求、范围或关键设计；
- out-of-unit blocking issue；
- final sync 冲突或无法判断门禁是否仍有效；
- 同 issue / unit 达到轮次上限；
- 必需 live 证据受环境阻塞且无法在当前权限内恢复。

只有以下条件全部成立才报告完成：

- 全部 milestone 范围和退出标准已实现并有直接证据；
- 所有成立且阻塞交付的 finding 已关闭；
- 所有适用 gate 对最终状态都有可追溯的有效结论；
- canonical spec 与实际行为一致，整个 unit 已归档；
- PR 已创建且 required CI 全绿；
- 主仓 checkout 未受影响，本 unit 运行时资源和 worktree 已清理，或交付中明确列出了用户要求
  保留的测试现场。

输出 PR URL、最终 head、有效门禁摘要和需要人审查的已知事项。CI 绿即退出，不等待 merge。
