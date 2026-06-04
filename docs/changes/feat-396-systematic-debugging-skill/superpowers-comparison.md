# Superpowers vs. 本项目 change-* 工作流 — skill 体系对比

> 调研日期：2026-06-02
> 对比对象：[obra/superpowers](https://github.com/obra/superpowers)（v5.1.0+，克隆于 `~/Repos/opensource-hub/superpowers`） vs. 本项目 `.claude/skills/change-*`
> 用途：feat-396 立项调研材料。结论见末尾「引入决策」。

---

## 1. 整体定性

| | superpowers | change-* |
|---|---|---|
| 本质 | **单 agent 内嵌的开发方法论**——一组自动触发的 skill,把一个驱动 agent 的行为规训好 | **多角色工程组织的流水线**——用显式门禁 + 文档契约 + 子 agent 团队把一个需求当带验收关卡的交付线跑 |
| 角色模型 | 同一个驱动 agent 顺着 skill 走;subagent 只是某个 skill 里的可选执行手段 | 6 个角色都是独立子 agent,各有「§0 不可越界硬规则」,靠 Team/SendMessage/后台派发物理隔离 |
| 阶段衔接 | 软衔接(存个 design doc / plan) | 硬门禁(门禁 1/2)+ 输入输出文档契约,上游不达标下游直接退出 |
| 失败处理 | 到 `finishing-a-development-branch` 给几个选项收尾 | 轮次上限(5/7)、issue 指纹去重、revise-design 三道闸、escalate、out-of-unit 自动立 issue |
| 适用面 | 跨 harness(CC/Codex/Gemini/Cursor…);单人 + 单 agent 自治几小时 | 绑 Claude Code 的 Agent/Team 原语;orchestrator 无人值守把一个 unit 推到 PR |
| 哲学 | TDD-first、systematic over ad-hoc、evidence over claims、复杂度优先 | 同上 + 用户可观察纯度、门禁、双重验收(产品旅程 + 代码核对) |

---

## 2. Skill 清单对照

### superpowers（14 个）

| 类别 | skill | 职责 |
|---|---|---|
| 元/入口 | `using-superpowers` | 会话开始即激活,强制任何回应前先查该用的 skill |
| | `writing-skills` | 创建/修改/测试 skill 本身 |
| 协作设计 | `brainstorming` | 苏格拉底式追问把模糊想法逼成 spec,分段确认,存设计文档 |
| | `writing-plans` | 拆成 2–5 分钟微任务,每个带精确文件路径 + 完整代码 + 验证步骤 |
| 执行 | `using-git-worktrees` | 设计批准后建隔离 worktree 分支,跑初始化,验证测试基线 |
| | `subagent-driven-development` | 当前会话内每任务派新 subagent + 两阶段审查(合规 → 质量) |
| | `executing-plans` | 另起会话分批执行,带人工 checkpoint |
| | `dispatching-parallel-agents` | 2+ 个无共享状态的独立任务并发派 agent |
| 质量 | `test-driven-development` | RED-GREEN-REFACTOR,删掉测试前写的实现代码 |
| | `systematic-debugging` | 4 阶段根因定位(含 root-cause-tracing / defense-in-depth / condition-based-waiting 子技法) |
| | `verification-before-completion` | 宣称完成前必须跑验证命令、贴输出,证据先于断言 |
| | `requesting-code-review` | 派 code-reviewer 子 agent,查 diff vs plan + 代码质量/架构/测试,出 Critical/Important/Minor + merge verdict |
| | `receiving-code-review` | 收到 review 反馈的姿态:别表演式点头、先核实再改、该 pushback 就 pushback、不清楚先问、别道谢 |
| | `finishing-a-development-branch` | 任务完成后验证测试,给 merge/PR/保留/丢弃选项,清理 worktree |

### change-*（6 个角色）

| skill | 职责 | 门禁 |
|---|---|---|
| `change-spec-author` | 对齐「做什么」,产首文档(spec/incident/motivation/fix),只写用户视角,Requirement/Scenario 结构,原话落盘 | 门禁 1 |
| `change-design-author` | 对齐「怎么做」,强制先调研代码仓,产 design.md + 现状分析 + Milestone 拆分(反向门槛) | 门禁 2 |
| `change-orchestrator` | 接管实施:建 unit 分支、派 worker、调 reviewer/verifier、失败循环、提 PR | — |
| `change-impl-worker` | 执行单 milestone:三提交(C1 红测/C2 实现/C3 文档)、前端浏览器验收矩阵 | — |
| `change-reviewer` | 产品旅程验收,验用户可观察,产 acceptance/regression.md | 门禁 3 |
| `change-verifier` | 读代码核对实现 vs spec/design(Completeness/Correctness/Coherence),产 verification.md | 门禁 3 |

---

## 3. 工作流阶段对位

| 阶段 | superpowers | change-* |
|---|---|---|
| 对齐「做什么」 | `brainstorming` | `change-spec-author`(门禁 1) |
| 设计「怎么做」 | 折进 brainstorming + writing-plans | `change-design-author`(门禁 2,强制调研代码仓) |
| 拆任务 | `writing-plans`(微任务含完整代码) | 折进 design Milestone 表 + worker 自写 `tasks.md` roadpoint |
| 隔离工作区 | `using-git-worktrees` | orchestrator §2.3 建 unit + 每 milestone worktree |
| 执行 | `subagent-driven-development` / `executing-plans` / `dispatching-parallel-agents` | orchestrator 派发循环 + `change-impl-worker` 三提交 |
| TDD | `test-driven-development`(删掉测试前的代码) | worker §5 三提交 + 前端状态矩阵 + 真实浏览器验收 |
| 调试 | `systematic-debugging`(4 阶段根因) | **散落**在 worker §7 + spec 的 bugfix RCA(无独立纪律) |
| 审查(代码) | `requesting-code-review`(派 code-reviewer 子 agent) | `change-verifier`(代码 vs spec,Completeness/Correctness/Coherence) |
| 审查(产品) | 无对应 | `change-reviewer`(产品旅程,用户可观察) |
| 接收反馈 | `receiving-code-review` | **散落**在 orchestrator §6.2(现象线索 not 方案)+ worker §0.1 |
| 确认完成 | `verification-before-completion` | orchestrator §3.3 退出标准逐条核对 + verifier |
| 收尾 | `finishing-a-development-branch` | orchestrator §7 提 PR + 失败循环 + escalation |

---

## 4. 关键环节差异

### 4.1 代码审查:一个角色 vs 拆成两维

superpowers 的 `requesting-code-review` = 单一代码审查角色(派 fresh 子 agent 看 diff,查 plan alignment / code quality / architecture / testing / production readiness,出 Critical/Important/Minor + merge verdict)。

change-* 把它拆成两个:
- `change-verifier`≈superpowers 的 code-reviewer(代码 vs spec,严重度 CRITICAL/WARNING/SUGGESTION 几乎逐项对得上)。
- `change-reviewer`=产品旅程、用户可观察验收 —— **superpowers 没有这一维**,是 change-* 多出来的。

**审查时机差异**:superpowers 主张「review early, review often」,`subagent-driven-development` 里每完成一个 task 就派一次代码审查;change-* 的 verifier 是 unit 末尾一次性兜底。change-* 的过程内质量控制靠 worker 三提交 + C2 测试门禁 + orchestrator §3.3,**没有**「每 milestone 合并前来一次独立 fresh-eyes 审查」这一层。

### 4.2 TDD 立场

superpowers 更狠:测试前写的实现代码**直接删**。change-worker 用 C1 红测 + C2 实现 + C3 文档三提交,额外禁兜底/降级/防御性编程,前端还有一整套状态矩阵 + 真实浏览器验收(superpowers 的 TDD 偏后端/通用)。

### 4.3 失败循环工程化程度

superpowers 到 `finishing-a-development-branch` 给选项就收;change-orchestrator 有轮次上限(同 issue 5 轮 / 同 unit 7 轮)、issue 指纹去重、revise-design 三道闸、escalate 给人、out-of-unit 自动立 issue、PR body 模板 —— 一整套自治跑多轮还能优雅停下找人的机制。

---

## 5. superpowers 有、change-* 缺的

| superpowers skill | change-* 现状 | 评估 |
|---|---|---|
| `systematic-debugging` | 精神散落在 worker §7 + spec bugfix RCA,**无独立调查纪律**:撞到故障时没有「动手前先打边界日志定位、反向追数据流、写单一假设、最小验证」这套强制顺序手法 | **决定引入**(见 §7) |
| `receiving-code-review` | 核心已存在一半(orchestrator §6.2「现象线索 not 方案」),但「逐条核实、不清楚先问、该 pushback、别表演式点头」未成文 | 暂不引入。判定为护栏类(姿态约束),宜内联进角色 §0 而非新建 skill;本期不做 |
| `requesting-code-review` 的增量时机 | verifier 仅 unit 末尾一次 | 暂不引入。可选增量审查(milestone 合并前按判据插一次)留作后续考虑 |

## 6. change-* 有、superpowers 缺的

- **门禁机制**(门禁 1/2/3)与文档契约(spec→design→tasks/progress→acceptance/verification)。
- **用户可观察纯度**:验收标准只能用户可观察,实现层标准归 design.md;防 reviewer 滑进 engineer 模式(整轮作废)的硬流程约束。
- **产品旅程验收维**(`change-reviewer`):走真实用户旅程验收,而非只看代码 diff。
- **失败循环工程化**:轮次上限、指纹去重、revise-design 三道闸、escalate、out-of-unit issue。
- **前端验收体系**:状态矩阵 + 真实浏览器验收 + 视觉/reference 对照。
- **bugfix lite/full 双路径** + RCA 原始意图追溯(防为消症状砍功能)。

---

## 7. 引入决策（feat-396）

经讨论,本期**只引入 `systematic-debugging`,其余暂不引入**:

| skill | 决定 | 理由 |
|---|---|---|
| `systematic-debugging` | ✅ 引入,**保留原名**(不改名 change-debugging) | 它是有阶段、可复用、值得单一真源的调查过程;worker/orchestrator/spec-author 三处可复用。change-* 当前撞到故障时缺一套强制顺序的根因优先纪律 |
| `receiving-code-review` | ❌ 暂不 | 护栏/姿态类,宜内联非新建;且核心已存在一半 |
| `requesting-code-review`(增量审查) | ❌ 暂不 | 增量审查时机是取舍项,留后续 |

**引入要点**(留给 design 阶段细化):
- 定位为**技法 skill**(非被派发角色):无 worktree、无门禁、无产出文档、不被 orchestrator 当 milestone 派发。某角色执行中途用 Skill 调起,走完回原角色。
- call-in 两处:`change-impl-worker`(主场,§0 + §7 异常处理)、`change-spec-author`(bugfix RCA,**仅调查部分 Phase 1–2,不调 Phase 4 修复**——spec-author 禁碰代码)。`change-orchestrator` 经 design 评估**不接入**:Project Lead 不亲自 debug,其 §6.2 已覆盖「判根因在哪层」的路由判断,真正执行 fix 的 fix worker 本就跑 worker 那条纪律。
- 明确**不接入** `change-reviewer`(会破坏其用户可观察边界,推进 engineer 模式)。
- 需调和的冲突:① Phase 4「先写复现测试」与 worker 三提交 C1 重叠 → call-in 写「回到 §5 三提交」不重抄;② 失败阈值(superpowers 3 次质疑架构 vs worker §7.3 的 6 次回退)如何分层;③ 与 worker §0.2 禁兜底是同向加强。
