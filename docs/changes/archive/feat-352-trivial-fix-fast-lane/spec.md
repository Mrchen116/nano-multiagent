# feat-352: change-* 流程小修轻量通道

## Relations

<!-- 无依赖时整段可省略。只列 unit_id，理由写在正文。 -->
- Depends on:
- Blocks:
- Related: feat-341-change-workflow-skills, feat-342-reviewer-boundary-and-runbook, feat-347-acceptance-criteria-tracks, feat-350-dispatch-checkin-clarify

## 原始需求

> 我们一起来审视本仓中change-* 系列skill。我观察到change-orchestrator经常会在worker干完，自检或者reviewer检查，发现小问题，然后重新派新的worker去修，哪怕是个很小的问题。新worker需要很多时间才能知道背景然后修理。多轮反复这样修的话，很慢很慢。你能理解我的意思吗？

## 澄清记录

<!-- 与用户的交互式澄清。每轮一条 Q/A。结束后再写下面的段落。 -->

- Q1: 当前 change-* 流程在小修循环里慢的根因是什么?
  (claude 诊断,用户认可) 三块成本叠加,都是为 milestone-sized 工作设计、套到单点 trivial 修复上量级失配:
    - 冷启动税:每个新 worker 强制读 6 项上下文(首文档 / design / CLAUDE / AGENTS / LOGBOOK / 现有代码与测试结构) + 跑基线 + 开工报信 + 写 tasks.md 骨架。
    - 流程税:worker §0.4 强制 C1/C2/C3 三提交,C1 还要"红测试"——typo / 单一样式属性这类小修写不出有意义的红测试,只能形式主义凑。
    - 调度税:orchestrator §6.2 把每轮 reviewer 反馈都打包成新 fix milestone,追加 design.md Milestone 表行、建新子目录、建新 worktree(本地缓存全失效)。
  用户原话:"我认可你的说法。"

- Q2: 改造方向?
  (claude 提两个方向,用户认可"合理的思路")
    方向 1:reviewer 给每个 issue 标"修复成本"分级,orchestrator 看到一批都是小修时走轻量通道——不建 fix milestone、不强制完整 tasks.md/progress.md 骨架、worker 跳过强制 6 项阅读、允许单 commit。
    方向 2:复用原 worker 实例——orchestrator 不在 worker DONE 后丢句柄,reviewer 出 fix 反馈时通过 SendMessage 把 fix 列表回灌给原 worker,其上下文/worktree/已读文件全在,彻底消灭冷启动税。
    倾向 1+2 组合:2 作为优先复用路径,1 作为"原 worker 已死 / 跨 milestone 修"的兜底。
  用户原话:"我觉得这是合理的思路。"

- Q3: 怎么定义"trivial"才算够小、可以走快车道?
  (claude 推荐 reviewer 标 trivial/scoped/substantial 三档,用户否决) 用户认为"trivial"很难硬定义,不要立死分级表。让 agent(reviewer / orchestrator / worker)自己根据当前上下文判断走哪条通道——它有这个判断能力,只是过去没给它一条快车道可走,所以只能刻板地走 milestone 流程。本 unit 的工作是**让这条通道在流程里存在**,而不是规定"什么修复属于 trivial"。
  用户原话:"我觉得这个问题很难定义清楚。就让 Agent 自己遇到情况自己来决策就行了吧,我觉得。他有这个能力去决策。主要是我们之前没有给他这么一个通道,他只能刻板的按原本那个流程。"

- Q4: 这条快车道在流程的哪些环节存在?
  (claude 推荐"仅限 reviewer 反馈循环",用户认可) 范围切窄:
    - ✅ reviewer 走完旅程后报告里的 fix 反馈,orchestrator 据此派(或唤醒) fix worker 时可走快车道
    - ❌ worker 干 milestone 主任务时自检发现的小问题——它本来就在自己 worktree 里、上下文热,直接改即可,不需要"通道"概念
    - ❌ orchestrator §3.3 退出标准核对发现的问题——那是 worker 没干完要补齐,不是新派
    - ❌ PR merge 后人在 PR review comment 里提的反馈——orchestrator 已退出,走另一条流程(orchestrator §7.4 末尾的 "address PR <url>" 路径)
  痛点本质是"跨 worker 派发之间的冷启动",只有 reviewer 反馈循环才触发跨 worker 派发。
  用户原话:"合理。"

- Q5: 走快车道修完后,还要不要再派一轮 reviewer 复验?
  (claude 一开始走偏给 SOP 选项,用户纠正方向) 仍然要 reviewer 复验——这是硬边界,不能让 fix worker 自我验收(撕开 reviewer §0.1 "零写入 + 独立验收"防线)。但**怎么验、要不要复用上一轮的 reviewer 实例、要不要重走全旅程**——不规定,由 reviewer 自己根据 fix 范围、自己的上下文新鲜度判断。
  用户原话:"仍然要,但是我感觉很多时候也可以复用前面的 reviewer,不用新开。"

- Q6: 这条 unit 应该锁的是"SOP"还是"目标 + 边界"?
  (用户主动纠偏 claude 的 SOP 思路,定下根本方向) 不锁 SOP。本 unit 的产品不是"新流程模板",而是**给 orchestrator / reviewer / worker 解锁自主性**:
    - 告诉他们流程里**存在**一条小修快车道,
    - 告诉他们快车道的**目标**(小修循环要快),
    - 告诉他们快车道的**硬边界**(reviewer 仍独立验收、PR 文档可追溯、不能让 fix worker 自我验收等),
    - **不规定**:trivial 定义、worktree 路径、是否复用实例、跳过哪几步、reviewer 走哪条旅程——这些都交给 agent 看具体上下文决策。
  这一点回头会反过来约束 spec 的【用户场景】和【验收标准】:必须按 outcome / 边界写,不能写"orchestrator 应该跳过 §6.2 建 milestone 这一步"这种 SOP 条款。
  用户原话:"我觉得搞的有点复杂。我们不应该定义的太死这些规则。就是我们外部有个比较死的规则,内部要尽可能松一点,能够让这个领导,Agent 他能发挥他的自主性。... 我们更多应该给他的是目标,不是一个 SOP。"

- Q7: 小修快车道的硬边界(agent 不能松的底线)?
  (claude 列 8 条候选,用户全认同但提醒"不一定都写,很多是原本约束") 全认同;只写**和本 unit 强相关**、容易被"快车道"思维误破的硬边界:
    [B1] reviewer 仍独立验收 — fix worker 不能自我验收(承接 Q5)
    [B2] PR 可追溯 — 人审 PR 时仍能看到本轮 fix 改了什么、为什么改;不能为了快而把 fix 历史抹掉
    [B3] reviewer 复用实例时零写入约束保留 — 即使复用上一轮 reviewer,它仍然只读、不改源码(reviewer §0.1)
    [B5] 集成路径不变 — fix 最终仍合到 unit/<id> 分支,走原 PR 路径,不绕过
    [B6] 失败可回退 — 任何一次快车道 commit 都能回退到上一稳定状态
  不写进 spec 的(本来就是通用硬规则,与本 unit 关联弱):
    [B4] fix 不越 unit 范围 (worker 通用)
    [B7] 轮次上限闸 (orchestrator 通用)
    [B8] design / spec 不允许 agent 自己改 (通用 Pause-on-design-issue)
  用户原话:"这些我都认同。当然了,这些不一定都要写进去,因为嗯很多是原本的约束嘛,而且跟这个事也不太相关的一些。"

- Q8: 上线后,启动 orchestrator 的人怎么"看到"本 unit 生效?
  (claude 推荐 outcome 方向,用户认同) outcome-oriented 信号(不预设具体 form):
    - 同一 unit 跑完后,从 unit 启动到 PR 提交的 wall-clock 时间显著下降,尤其在 reviewer 给小修反馈 ≥ 1 轮的 unit 上
    - PR 提交时,docs/changes/<unit>/ 下不再为每个小修堆出新 fix milestone 子目录;小修痕迹归并到一处(具体形态由 agent 自定)
    - 小修 commit 历史轻量、可读——不再出现"C1 测试 / C2 实现 / C3 文档"三联里 C1 是空壳的形式主义产物
    - 复验 reviewer 报告仍完整(覆盖表覆盖首文档每条验收标准),但小修轮的旅程描述可以简短,不强制重列全部主路径
    - 硬边界 B1/B2/B3/B5/B6 仍然成立(不能为快牺牲)
  用户原话:"对,你说的对。"

## 用户场景

**当前状态(痛点)**:

我(仓库协作者)启动 change-orchestrator 跑一个 unit。worker 把 milestone 都干完后,reviewer 走旅程发现几个小问题——一个文案 typo、一个按钮 padding 不对、一个空态没处理。orchestrator 把这些 issue 打包成一个新 fix milestone:在 design.md Milestone 表追加一行、建一个新子目录、开一个新 worktree。然后派一个新 fix worker——这个 worker 启动时按 worker §2.3 要读 6 项上下文(首文档 / design / CLAUDE / AGENTS / LOGBOOK / 现有代码与测试结构),跑测试基线,写一份新 tasks.md(拆 3-7 个 roadpoint),每个 roadpoint 走 C1(红测试,但 typo 写不出有意义的红测试,只能凑) → C2 → C3 三提交。改三行字最后产出十几个 commit 加一套全套文档骨架。修完再派 reviewer 把整套主路径 + 边界路径重新走一遍。

我看到的:reviewer 反馈一轮 → orchestrator 折腾半小时 → reviewer 又反馈一轮(也许是上轮漏看的另一个小点)→ 又半小时。两三个小修循环下来,我等 PR 等到不耐烦。明明就是改几行字。

**期望状态**:

orchestrator / reviewer / fix worker 在面对"reviewer 反馈循环里的小修"这种场景时,**知道自己拥有一条快车道**——不强制建新 fix milestone、不强制完整冷启动六读、不强制三提交、不强制 reviewer 重走全旅程。**具体怎么走、什么时候走、复用什么、跳过什么——三个 agent 自己看上下文判断**,而不是被 SKILL.md 里的硬步骤刻板锁死。

我作为启动者,外部仍然看到该 unit 走完整个 实施 → 验 → 提 PR 流程;fix 历史从 PR / 仓库文档仍然可追溯;reviewer 仍独立验收;但总耗时显著下降,commit 历史不再被空壳形式产物污染。

## 验收标准

<!-- outcome-oriented:写 agent **能且会**做什么,不写 agent **必须按 X 步骤**做什么。 -->

- [ ] change-orchestrator / change-reviewer / change-impl-worker 三份 SKILL.md 里,**显式提到**"reviewer 反馈循环里的小修可以走快车道"这条选项;每份给出**目标**(小修循环要快、避免冷启动 / 流程 / 调度税)和**硬边界**(reviewer 仍独立验收 / PR 可追溯 / reviewer 复用实例时零写入约束保留 / 集成路径不变 / 失败可回退),但**不规定**固定 SOP 步骤
- [ ] reviewer 在 acceptance.md 报告里能(且会)对 fix 反馈表达"这一批小修可走快车道"的判断,但不强制使用任何固定字段名 / 分级标签
- [ ] orchestrator 在收到 reviewer 小修反馈时,能(且会)跳过原 §6.2 强制建 fix milestone 子目录 / 追加 design.md Milestone 表行的动作,自决如何归并 fix 痕迹
- [ ] fix worker 在处理小修时,能(且会)跳过原 §0.4 强制三提交(允许单 commit) + 跳过原 §2.3 全套 6 项强制阅读,自决要读什么
- [ ] reviewer 复验小修时,能(且会)跳过原 §2.5 完整服务接管 + §3.1 全量旅程清单重做,自决复验深度
- [ ] PR body 仍可追溯本 unit 经历的所有 fix 历史(fix 数量、由 reviewer 哪一轮触发、修了哪些点),人 review PR 时能看到完整经过
- [ ] reviewer 复用同一个实例做复验时,零写入约束仍然成立(只读、不改源码)
- [ ] reviewer 在快车道复验中发现新的或残留问题时,仍能像主流程一样升级回完整复验 / 立 issue / 升级 escalate

## 范围与非目标

- **在范围**:
  - 改造 change-orchestrator / change-reviewer / change-impl-worker 三份 SKILL.md,让小修快车道在三方都"被授权且被知道"
  - 仅覆盖 reviewer 反馈循环的小修场景
  - 把硬边界(reviewer 仍独立验收 / PR 可追溯 / reviewer 复用实例时零写入约束保留 / 集成路径不变 / 失败可回退)写进 SKILL.md,作为快车道的护栏
- **非目标**:
  - 不立 trivial 分级表 / 字段语义 / 数值阈值——agent 自主判断
  - 不规定 fix worker 应该在哪个 worktree 修、是否复用上一轮 worker / reviewer 实例
  - 不覆盖 worker 自检发现的小修
  - 不覆盖 orchestrator §3.3 退出标准核对发现的问题
  - 不覆盖 PR merge 后人在 PR review comment 里提的反馈(那是 orchestrator §7.4 "address PR" 的事)
  - 不重写 change-design-author / change-spec-author(本 unit 不动需求 / 架构层)
  - 不引入新的派发包字段强制规范
