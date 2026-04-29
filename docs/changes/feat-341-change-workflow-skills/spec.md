# feat-341: Change Workflow Skills(变更工作流 skill 套件)

> **追溯说明**:本 unit 是工作流套件 skill 立项后的回溯 spec/design,流程本身就是工作流第一次落地。立项过程中尚没有 `change-spec-author`/`change-design-author` 引导,所以"原始需求 / 澄清记录"是从对话归档中整理出来的。

## Relations

- Related: feat-338(项目目前已有的 docs/changes 结构,本 unit 的工作流就是用来管它这种 unit 的)

## 原始需求

第一段(关于 docs/changes 流程本身的痛点):

> 我们讨论下。docs/changes/readme.md 这里写了目录规范。我希望通过需求进来的时候,agent 和我先对齐这些文档,然后 agent 自主去做执行。我现在按照这个规范试着写了一些 feat 和 bugfix。发现一些问题。1。需求之间是有关联性。比如 feature 337,在做分解的时候,发现需要先做 feature 338,所以我们就先去设计 338 了。这种依赖或者关联关系,我觉得很常见,参考 github 的 issue 的模式,好像是可以关联不同的 issue?另外,我看很多基于 spec 做开发(也就是 sdd)的 skill(现在就挂载着有这类 skill,你可以读),他们会分 proposal,spec,design,再到 task。你觉得 proposal 有必要吗,以及这些个文档的边界要清晰才行,经常出现 agent 在和我澄清 spec 的时候,问我一些实现层面的技术方案选择问题。还有就是我经常遇到一个问题,就是 design 可能做了不完美(不可能永远完美),导致实现之后会有一些小问题。这时候应该去去改这个 design。顺便把代码改了。还是说加一个 bug fix?或者加一个 feature。然后在一个新的需求里面解决呢?有很多东西是一个很小的点,比如说就是一个存储配置文件目录位置改一下。感觉新开一个需求又挺麻烦的。你给我分析一下,这一系列的问题。除了那些 skill,我之前还认真看过人类开源社区中是如何做需求的。"/Users/czj/Library/Mobile Documents/iCloud~md~obsidian/Documents/奇迹日历/agent 笔记/agent workflow for SE.md"。我感觉人类的做法也可以参考。

第二段(立项 5 个 skill):

> Project Lead Orchestrator、TDD Execution Worker、product-acceptance-reviewer 是之前设计的 skills。当时,没有考虑 spec,没有意识到需要人和 agent 共同明确 design。以及之前的文档体系和现在有差异,我想做一轮重构。不过当时识别到了一些问题,做了很多经验,在 skill 中有体现,比如小需求被分了多个 milestone,导致主要在写文档等等。现在要根据现有的我们的讨论重新设计。首先明确下,我觉得我们这里需要 4-5 个 skill,在生成 spec 和 design 阶段需要 1-2 个 skill,我没想好是否应该拆开两个还是合并成一个。先捋一遍流程,我以新 feature 为例,人和 agent 先明确 spec,明确 design,拆分好了 milestone 以及他们之间的依赖关系,然后进入到全 agent,无人参与的实现工作,Project Lead Orchestrator 接收整个 feature 任务,根据 milestone 依赖关系,并行/串行安排 TDD Execution Worker 在 worktree 实现 milestone。最终,Project Lead Orchestrator 再安排 product-acceptance-reviewer 做端到端使用,并给出明确的 feature 完成独立审查意见。如果有问题,Project Lead Orchestrator 安排继续解决。(大部分情况下会有问题,可能是实现没对,可能是设计漏导致实现不对,或者有优化改进问题)。直到最终 product-acceptance-reviewer 通过。

## 澄清记录(产品/用户视角)

> 注:对话中走过 D1-D9 决策树,大部分属于 design 范畴(架构层)。下面只摘出影响"用户视角行为"的几条。

- Q1: 流程要不要分 spec / design / proposal 三件套(参考 sdd-skill / opsx)?
  A: 不要 proposal。spec + design 两份够,proposal 对单人协作冗余。
- Q2: 用户与 agent 在哪些阶段同步,哪些阶段全自动?
  A: spec、design、PR review 三个关键点必须人介入;实施(worker)和验收(reviewer)阶段全自动,失败循环大部分自愈,极端才升级回人。
- Q3: 多个 unit 能否并行(我同时跑 feat-X 和 bugfix-Y)?
  A: 是,通过独立 unit 集成分支天然隔离,不需要工具自动并排;一次一个 orchestrator session,用户手动开多 session 即可。
- Q4: 小 bug 走 lite 路径(单文档 fix.md),不一定开完整 spec/design 吗?
  A: 是,bugfix 默认 lite,影响面大才升 full。
- Q5: out-of-unit 发现的问题(实施期或验收期发现根因不在本 unit)怎么办?
  A: 走 GitHub issue,不立刻转 unit,人 triage 决定要不要做。
- Q6: design 不可能完美,实现期发现偏差怎么处理?
  A: Pause-on-design-issue:停手 + 改 design.md + Changelog,不悄悄绕过。
- Q7: 失败循环里 agent 容易把锅甩给"design 漏了",怎么防?
  A: revise-design 三道闸(首轮禁用 / ≥2 轮 fix-implementation 失败 / 必须引用 design 段落)。
- Q8: unit→main 怎么合?有没有人审?
  A: 走 GitHub PR,orchestrator 提交后退出,人审 + merge。
- Q9: 命名约定?
  A: 沿用现有 `docs/changes/feat-338-kernel-message-sse/M3-presentation-layer/` 这种格式(unit 目录含 short-desc,milestone 目录是 `M<N>-<title>`)。

## 用户场景

```
A. 立项                          B. 设计                          C. 实施
人:有个想法 X                   ┌─→ design-author              ┌─→ orchestrator
   ↓                            │   人 + agent 对齐架构            │   全自动
   spec-author                  │   产 design.md                  │   ├─ 创 unit 分支
   人 + agent 一轮一问澄清       │   产 milestone 表                │   ├─ 派 worker(可并行)
   产 spec.md                   │   产空目录                       │   ├─ Pause-on-design-issue
   ┌─ feat → spec.md            │                                  │   ├─ 派 reviewer
   ├─ refactor → motivation.md  │                                  │   ├─ 失败循环(fix/issue/escalate)
   ├─ perf → motivation.md      │                                  │   └─ 提 PR + 退出
   ├─ bugfix lite → fix.md      │                                  │
   └─ bugfix full → incident.md │                                  ↓
                                │                                  人:GitHub PR review + merge
                                │                                  GitHub:auto-close 关联 issue
```

主路径:user 提需求 → 走 spec-author → 走 design-author → 调起 orchestrator → 收到 PR URL → review + merge。

边界路径:
- 实施期 worker 发现 design 偏差 → orchestrator 暂停 → 通知 user → user 修 design → orchestrator 续跑
- reviewer 找出问题 → orchestrator 自动 fix-implementation 循环;3 轮没解决升级 design;7 轮没 pass 升级人
- reviewer 发现根因不在本 unit → 走 `gh issue create`,本 unit 不停(major)或停等修复(blocking)

## 验收标准

- [ ] 任意类型变更(feat/bugfix-lite/bugfix-full/refactor/perf)能从立项一路走到 PR
- [ ] 在 spec 阶段,agent 不会一次性问一堆问题,也不会跳过澄清直接生成结论段落
- [ ] 在 design 阶段,agent 不会回头改用户视角,会逐段对齐架构决策,完成后做整体自检
- [ ] 默认 milestone 拆分是单 M1,需要拆分必须举证;横切式拆分(model/api/ui)被禁止
- [ ] 实施期 worker 发现 design 偏差会暂停而非悄悄绕过,修订写入 progress.md + design.md Changelog
- [ ] reviewer 不修代码、不读大量源码、不在第一轮给 revise-design
- [ ] out-of-unit 严重问题自动 `gh issue create`,unit 与 issue 通过 `Closes #N` / `Refs #N` 关联
- [ ] orchestrator 提交 PR 后退出,不等 merge / 不等 CI
- [ ] 多个 unit 可以在不同 session 并行跑,通过 unit 集成分支天然隔离

## 范围与非目标

**在范围**:

- 5 个 skill(`change-spec-author`, `change-design-author`, `tdd-execution-worker`, `product-acceptance-reviewer`, `project-lead-orchestrator`)+ 各自 assets 模板
- `docs/changes/readme.md` 配套规范(已存在,本 unit 复用)
- 命名 / 路径 / 派发包字段约定

**非目标**:

- 不做 CI 集成 / 不替代 GitHub web UI 的 PR 审查
- 不做跨多 unit 的自动调度(一次一个 orchestrator session)
- 不做 skill 的 eval / benchmark(后续真实试用后迭代再说)
- 不做 GitHub 远端缺失时的降级路径(用户明确说不考虑)
- 不做工作流可视化 dashboard(git + ls 已经够查)
