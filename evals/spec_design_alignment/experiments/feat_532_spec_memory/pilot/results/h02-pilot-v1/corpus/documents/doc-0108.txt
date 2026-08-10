# feat-350: 派发开工报信 + 澄清通道

## Relations

- Related: feat-341-change-workflow-skills, feat-342-reviewer-boundary-and-runbook, feat-337-cc-background-subagents

## 原始需求

> 我在反思 change-*（/Users/czj/Repos/nano-multiagent/.claude/skills 中的）这一组 skill，现在发现一个问题，可能 orchestrator 派发任务不够明确，或者有歧义。然后 worker，reviewer 理解有偏差。这种问题我理解一定无法避免的，单向沟通在通用场景永远无法完全精准。所以需要 worker 和 reviewer 对任务有比较大不肯定的情况，我觉得需要向主 agent（orchestrator）问澄清。现在是不是没这样的机制？

> 我觉得先简单点，不要太多约束。先无论有没有问题，都给主 agent 报个信。没问题就简单说一声开始干了。有问题就做 3 轮以内的澄清。

> 看下 orchestrator 有保证 agent 在后台执行吗，不是后台可能也没法有相互发消息的能力。

> 回应开工报信的时候，orchestrator 是需要从全局的角度给出最合理的答案的，不能太死板的，你现在写法它就像机器人，不会思考的。

## 澄清记录

- Q1: worker / reviewer 对任务不确定时,目前有没有向 orchestrator 问澄清的机制?
  A: 没有。现有的逃生通道(worker §1 缺字段拒绝 / §4 Pause-on-design-issue / §8.2 HANDOFF / §7.3 连续失败;reviewer §2.5 缺 Runbook / §1.1 错派 / §3.1 非用户可观察标准)全是"出问题了"才走,缺"能开工但对意图没把握、想先问一句"的通道。

- Q2: 这个机制要做多重?要不要加"先读完所有上下文才能问""orchestrator 只能引用原文回答"等门槛?
  A: 先简单。不加重门槛。核心是:无论有没有疑问,开工前都给 orchestrator 报一个信——没疑问就一句话说"开始干了",有疑问就做 ≤3 轮澄清。

- Q3: orchestrator 派发子 agent 时有没有保证后台运行?
  A: 原 skill 没有显式保证,只隐含依赖(§0.6 默认并行、§3.2 监控 RUNNING worker)。前台(阻塞)派发时,orchestrator 在子 agent 返回最终结果前不执行回合,收不到也回不了消息——开工报信 / 澄清通道根本无法工作。必须显式要求 `run_in_background: true`。

- Q4: orchestrator 回应澄清时的口径?
  A: orchestrator 是这个 unit 的技术领导者,要用 unit 全局视角(用户意图 + 整体拆分 + milestone 依赖 + reviewer 验收角度)思考、给最合理的答案,不是机械摘抄某段原文。边界是"别新造 / 别改 design 决策";真需要改 design 或全局也判断不出来的,才是文档缺口,走 escalate。

## 用户场景

change-* 这组 skill 是一条单向派发流水线:orchestrator 把 milestone / unit 派给 worker / reviewer,子 agent 自取上下文后独立干活。单向沟通在通用场景永远无法完全精准——orchestrator 的派发包 + design.md 再细,worker / reviewer 读下来仍可能对"这个 milestone 到底要什么""这条验收标准的预期结果是什么"存在实质歧义。

在此之前,一个不确定的 worker 只有两条路:猜着做(理解偏差的来源,可能整轮被 reviewer 打回),或走 Pause-on-design-issue / HANDOFF 这类重通道(但那些是"出问题了"才用,语义不对)。reviewer 同理,只能猜着判或标 inconclusive 白烧一轮。

feat-350 加一条轻量双向通道:

- **worker** 读完上下文、基线绿之后,开工前先给 orchestrator 报一个信。没疑问就一句话报"已读懂 M<N>,开始实施";有疑问就把对 milestone 意图 / 范围 / 退出标准的不确定列出来问。
- **reviewer** 服务接管完成、走旅程之前,同样先报一个信。没疑问报"已读懂验收口径,开始走旅程";有疑问就把对验收标准预期结果的不确定列出来问。
- **orchestrator** 收到报信:报"开始干了"就确认收到、不打扰;报澄清问题就以技术领导者的全局视角思考、给最合理的答案。答这个问题必须真的改 / 补 design,或全局也判断不出来,才走 escalate。
- 澄清最多来回 3 轮。3 轮没收敛,要么 escalate,要么让对方按最合理理解推进并记录。
- 这条通道依赖子 agent 在后台并发运行——orchestrator 派发 worker / reviewer 一律后台运行,否则前台阻塞期间根本收不到报信。

整个机制刻意保持轻:不加"必须读完全部上下文才能问"之类的前置门槛,默认路径就是一句话报信,澄清是少数情况下的附加动作。

## 验收标准

- [ ] worker 在读完上下文、跑完基线之后、写 tasks.md 规划之前,会给 orchestrator 发一条开工报信:无疑问时是一句话"开始实施",有疑问时列出对意图 / 范围 / 退出标准的澄清问题
- [ ] reviewer 在服务接管完成之后、走用户旅程之前,会给 orchestrator 发一条开工报信:无疑问时是一句话"开始走旅程",有疑问时列出对验收标准预期结果的澄清问题
- [ ] worker / reviewer 的澄清来回不超过 3 轮;3 轮未收敛时按最合理理解推进,并在 progress.md(worker)/ 验收报告(reviewer)留记录
- [ ] orchestrator 派发 worker 和 reviewer 时都以后台方式运行子 agent
- [ ] orchestrator 收到"开始干了"类报信只确认、不打扰;收到澄清问题时给出基于 unit 全局的判断性答复,而不是机械摘抄文档原文
- [ ] orchestrator 遇到"必须改 / 补 design 决策才能回答"或"全局也判断不出来"的澄清,走 escalate 而不是硬编一个答案
- [ ] worker 的澄清问答记入对应 milestone 的 progress.md;reviewer 的澄清问答记入验收报告

## 范围与非目标

- 在范围:`change-impl-worker`、`change-reviewer`、`change-orchestrator` 三个 SKILL.md 的开工报信 + 澄清通道 + 后台派发约定
- 非目标:不改 `change-spec-author` / `change-design-author`;不引入"必须读完全部上下文才能问"等重门槛;不改派发包字段结构;不改 design / spec 文档本身的写法;不替代既有的 Pause-on-design-issue / HANDOFF / escalate 等通道(本机制是它们之外的轻量补充)
