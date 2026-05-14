# feat-347: 验收标准分轨与 spec→reviewer 链路对齐

> **追溯说明**:本 unit 是审查 `feat-333-auto-mode-classifier` 的 design 时,发现首文档把实现层细节误标成验收标准、进而暴露 change-* 工作流 skill 集系统性缺陷后,回溯立的派生 feat。skill 改动已经在对话中完成并落到 `.claude/skills/`,本 spec.md 用于留下"为什么改"的追溯记录,属于 retrospective feat,无 design.md / 实施 milestone。

## Relations

- Surfaced from: feat-333-auto-mode-classifier(design 阶段审查实战)
- Modifies skills from: feat-341-change-workflow-skills
- Related: feat-342-reviewer-boundary-and-runbook(同属 change-* skill 加固谱系)

## 原始需求

起点是审查 feat-333 的 design 时,用户要求核对 reviewer 验收标准是否清晰,随即发现 feat-333 的 spec.md 把一整段 `max_tokens=64` / `stop_sequences` / XML 标签名这类实现细节用 `- [ ]` 标成了"验收标准"。用户原话:

> "你看看 .claude/skills/change-orchestrator/SKILL.md 要求 reviewer 走首文档(spec / motivation / incident)里**用户可观察**的验收标准——用户在 UI/CLI 上能看到/听到/敲到什么。本需求 spec 文档写清楚了吗?"

> "你回到 change-spec-author skill 收口,我想明确到底是这个 skill 没写清楚,还是说当时执行的不好?如果是 skill 没写清楚,和后面的 orchestrator 和 reviewer 不协调,那你告诉我 skill 哪里需要改进。"

> "来,你再跟我一起讨论一下。我们深度对齐。"

约束(用户多次强调):

> "另外,这组 skill 是通用软件开发的 skill,不要混入本项目特殊的内容。"

## 澄清记录

- Q1: 是 skill 没写清楚,还是执行不好?
  A: 两者都有,根子在 skill。skill 有四个真实缺口让这种错误既易发生又没被任何关卡拦住:① 没处理"需求本身就是实现对标 / 面向内部的变更"该怎么写验收标准;② 实现约束核心且必须落文时没有归处;③ §7 输出契约完全没提"验收标准会成为 reviewer 逐字清单"这条下游链路;④ §5 完成判据没有"验收标准须用户可观察"这道闸。

- Q2: 把 user story 改成离散场景、它本身当 reviewer 验收标准,好不好?自由叙事还要不要?
  A: 自由叙事必须保留——它建立画面、传达意图、展示场景间的流、防止 reviewer/worker 窄读。不是"叙事 OR 清单",是"叙事 + 派生的可验条目":叙事是 user story 本体(design-author 读它取意图),验收标准是叙事的"可勾投影"(reviewer 的覆盖表从这里来,每条追溯到叙事)。

- Q3: 纯内部改动(refactor / perf)的 user story 和验收标准怎么写?
  A: 写"不变性"。常见情况——有回归面:user story = 既有用户旅程的基线快照(回归基线镜头),验收标准 = "现有行为在变更后与变更前一致";reviewer 做的是回归。罕见情况——真零用户面:显式写"无用户可观察变化"并举证,验证全落 design.md 实现层标准 + 测试套件,这类 unit 不走 reviewer。

- Q4: 实现层验收标准(协议字段、参数、单测、保真点)不是不需要,只是 verifier 不同。归属在哪?
  A: 全归 design.md。spec 保持纯用户可观察。实现层标准的 verifier 是 worker(milestone 内单测 / 构建)+ 人(架构师 PR review)。design.md 的 Milestone 退出标准因此分两轨,每条标 `[reviewer]` / `[worker]`。

- Q5: 架构师在 PR 时验收实现层标准,这一步在 skill 里显式化吗?
  A: PR 由人验收。orchestrator 在 §7.2 组装 PR body 时,把 design.md `[worker]` 轨条目抽成"实现层验收标准(供 PR review)"段,给架构师当清单。

- Q6: "不派 reviewer"的场景在 change-orchestrator 写全了吗?
  A: 没有——只覆盖了 lite 模式,漏了"零用户面 unit"。补进 orchestrator §5,使其成为主决策点;change-reviewer §1.1 退为"错派即退出"的防御网。

## 用户场景

这组 change-* skill 的"用户"是:驱动变更工作流的人,以及逐个执行 spec-author / design-author / orchestrator / reviewer 的 agent。

**变更前**,工作流在"验收标准"这件事上是脱节的:

写 spec 的人面对一个"验收标准"段,没有任何提示告诉他这段会成为 reviewer 的逐字验收清单,于是很自然地往里写实现细节("越详细越好")。当需求本身带"复刻某实现"或属于纯内部重构时,他更是没有出路——skill 没教他这种情况下验收标准该怎么写,只能把实现保真要求硬塞进验收标准。这段污染的验收标准一路传到 reviewer:reviewer 要么试图验证 `max_tokens=64` 这种条目、滑进 engineer 模式去翻源码抓帧,导致整轮验收作废;要么对着自己根本观察不到的条目卡住。与此同时,实现层的东西明明需要验,却没有正经归处和 verifier;PR 阶段架构师手上也没有一份实现层清单可对。

**变更后**,工作流把"验收标准"清晰分成两轨,各有归处和 verifier:

用户可观察的东西留在首文档——user story 保持自由叙事(传意图),验收标准是它的可勾投影(reviewer 的覆盖表),spec-author skill 会主动拦截混进来的实现细节,并明确告知这段的下游就是 reviewer。实现层的东西归 design.md,milestone 退出标准标 `[worker]`,由 worker 单测和架构师 PR review 验。面向内部的变更有了明确的"回归基线 + 不变性"写法。reviewer 万一还是拿到污染的条目,会识别并标 `not-applicable` + flag、弹回 spec-author,而不是被带跑。零用户面的 unit,orchestrator 直接不派 reviewer。

## 验收标准

<!-- "用户可观察" = 打开改动后的 skill / 模板文件、或观察工作流跑出来的产物,能看到。 -->

- [ ] `change-spec-author` §4:user story 段明确"保留自由叙事 + 其价值";验收标准段定义为"叙事的可勾投影,每条追溯到叙事、只写用户可观察";含"两种镜头(feat 憧憬式 / refactor·perf 回归基线)"、"不变性写法"、"真零用户面写法"、"实现层标准不进 spec 归 design.md"。
- [ ] `change-spec-author` §7:出现下游链路警告——验收标准会被 orchestrator 逐字透传给 reviewer,混入实现/协议/接口/内部状态条目会让整轮 reviewer 验收作废。
- [ ] `change-spec-author` §5:门禁 1 完成判据多一条——"验收标准每条都是用户可观察的,且追溯到 user story,无实现层条目"。
- [ ] `change-spec-author` assets:`spec.md` 与 `motivation.md` 模板的注释同步上述口径;`motivation.md` 补上"用户侧验收标准(不变性)"段。
- [ ] `change-design-author` §4.6:出现"两轨退出标准"——`[reviewer]` 用户可观察 / `[worker]` 实现层,每条标 verifier;明确 design.md 是实现层验收标准的家。§1.1 接收 spec-author 交接扩展到"实现保真要求 / 实现约束"。
- [ ] `change-design-author` assets:`design.md` 模板补上 Milestones 段(此前 SKILL 引用但模板缺失),含两轨退出标准注释。
- [ ] `change-orchestrator` §7.2:PR body 模板含"实现层验收标准(供 PR review)"段,从 design.md `[worker]` 轨抽取,供架构师把关。
- [ ] `change-orchestrator` §5:跳过 reviewer 的条件从"只 lite"扩为两种——lite + 零用户面 unit。
- [ ] `change-reviewer` §3.1:含"refactor/perf 回归基线镜头";含防御条款——遇到非用户可观察的验收标准条目,标 `not-applicable` + flag,不 debug-by-reading。
- [ ] `change-reviewer` §1.1:覆盖"错派到无需 reviewer 的 unit(lite / 零用户面)→ 立即退出",判据指向 orchestrator §5。
- [ ] `change-reviewer` assets:`acceptance.md` 模板覆盖表注释同步两轨与回归镜头口径。
- [ ] 全部 skill 改动用通用软件开发语言,不含本项目的包名 / 文件名 / 机制名。

## 范围与非目标

- 在范围:`change-spec-author` / `change-design-author` / `change-orchestrator` / `change-reviewer` 四个 skill 的 SKILL.md + 各自 assets 模板,围绕"验收标准分轨与 spec→reviewer 链路对齐"的改造。
- 非目标:`change-impl-worker` 本次未改动(其退出标准消费方式不受影响)。
- 非目标(留作后续):`change-reviewer` 的 `acceptance.md` / `regression.md` 模板"上层文档同步"段、以及 reviewer SKILL §7,仍硬编码本项目文档路径(`docs/内核设计SPEC.md`、`CodingCLI / NodeGateway / IM` 等),违反"通用 skill"原则——属既有内容,需另起一轮"去项目特例化"清理。
- 非目标(留作后续):`feat-333-auto-mode-classifier` 的 spec.md 本身仍含被误标成验收标准的实现细节段——本 unit 修的是 skill 层,feat-333 spec 的收口是把改好的 skill 应用回去的另一件事。
