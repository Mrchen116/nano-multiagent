# feat-396: 引入 systematic-debugging 技法 skill — 技术方案

> 对齐: spec.md v1
> Unit branch: `unit/feat-396` (will be created by orchestrator)

## Changelog

## 现状分析

### 涉及范围

- `.claude/skills/systematic-debugging/`（**新建**）—— `SKILL.md` + `references/` 三个子技法文件。
- `.claude/skills/change-impl-worker/SKILL.md` —— 改:§0 加一条硬规则、§7.2/§7.3 加 call-in。主场。
- `.claude/skills/change-spec-author/SKILL.md` —— 改:§4 bugfix 根因(RCA)段加 call-in(仅调查)。
- `.claude/skills/change-reviewer/SKILL.md` —— 改:§0 加「不接入」声明。
- `.claude/skills/change-orchestrator/SKILL.md` —— **不改**(Project Lead 不亲自 debug,§6.2 已覆盖根因路由)。

### 既有约束

- skill = `.claude/skills/<name>/SKILL.md`,frontmatter 仅 `name:` + `description:`。**无 manifest / 注册文件**——harness 按目录约定自动发现,按 `name` invoke。新增 skill 零注册即可用。
- 补充材料惯例放 `references/`,SKILL.md 里用「见 `references/X.md`」**按需引**,不自动注入(沿用 change-orchestrator 的 `references/pr-body-templates.md` 模式)。
- `description` 的「触发条件」决定自动触发口径 + Skill 工具列表呈现。
- 只动「调试相关」内容,不碰无关规则(spec Q3)。
- skill 内容用中文、效果优先,**不受现有 change-* skill 写法范式约束**(spec Q4)——不必套 §0 硬规则编号、机制性表达等既有风格。

### 可复用能力

- **superpowers `systematic-debugging` 原文**(4 阶段根因纪律 + Red Flags + 3 个子技法 root-cause-tracing / defense-in-depth / condition-based-waiting)——**改**:译成中文、裁掉 Phase 4 自带的「先写失败测试 + 提交」流程(交回 worker 三提交 C1,避免两套提交流程打架)、去掉点名他工具的表述。
- **change-orchestrator `references/` 目录组织**——**用**:照搬「SKILL.md 主文件 + references/ 按需引」的结构。
- **worker §0.2 禁兜底 / §7 异常处理、spec §4 RCA、reviewer §0.2-0.3 禁 debug-by-editing**——**改/加强**:worker/spec 处加 call-in(同向加强),reviewer 处加「不接入」声明(强化既有禁令)。

### 相关历史

- feat-341(change-workflow-skills):这套 change-* skill 的起源。本 unit 是其增量,不阻塞。
- feat-389(fix-loop-three-dimensions):动过 orchestrator 失败循环。本 unit 不碰 orchestrator,无交集。

> **契约层 grounding**:N/A —— 本 unit 不动 `src/` 任何产品代码,不涉及 `docs/specs/<包>` 契约层。

## 架构总览

本 unit 不改产品代码,只在 **skill 体系内**新增一个「技法 skill」并接线。技法 skill 与现有 6 个「角色 skill」的本质区别:它**不被 orchestrator 当 milestone 派发、不建 worktree、不产文档契约**——是某角色执行中途用 `Skill` 调起、走完即回的展开手法。

```
                      .claude/skills/
                      ┌──────────────────────────────────────────────┐
   [新增]             │  systematic-debugging/        (技法 skill)     │
                      │    SKILL.md  ── 根因铁律 + 4 阶段 + Red Flags  │
                      │                 + 3-strike 质疑架构            │
                      │    references/                                 │
                      │      root-cause-tracing.md    (反向追调用栈)   │
                      │      defense-in-depth.md       (多层加校验)    │
                      │      condition-based-waiting.md(治 flaky)     │
                      └───────▲──────────────▲─────────────▲──────────┘
              invoke(撞 bug)  │              │ invoke(RCA  │ 显式不 invoke
                              │              │  仅调查)    │ (carve-out)
                ┌─────────────┴───┐  ┌───────┴───────┐  ┌──┴──────────┐
                │ change-impl-    │  │ change-spec-  │  │ change-     │
                │ worker          │  │ author        │  │ reviewer    │
                │ §0 硬规则       │  │ §4 bugfix RCA │  │ §0 不接入   │
                │ §7.2/§7.3       │  │ (只调查不修)  │  │ 声明        │
                └─────────────────┘  └───────────────┘  └─────────────┘

   change-orchestrator: 不接入(Project Lead 不亲自 debug;§6.2 已覆盖根因路由判断)
```

**before**:撞 bug 时调试纪律散落在 worker §7 + spec §4,无单一权威,agent 易 thrashing。
**after**:`systematic-debugging` 成为单一权威,worker / spec-author 在该用的地方引它;reviewer 显式不引(防滑进 engineer 模式);散落的重复表述收敛过去。

## 关键决策

### 决策 1: skill 文件结构 = SKILL.md + references/ 三子技法

- **选择**: 单 `SKILL.md` 承载根因铁律 + 4 阶段纪律 + Red Flags 自查 + 「3 次同类 fix 失败 → 质疑架构」;三个子技法各一文件放 `references/`,SKILL.md 里按需引。
- **理由**: 沿用项目既有 `references/` 模式,主文件保持精简(随时被 invoke,不宜过长),子技法只在真用到时才被读取。
- **拒绝**: 全塞进单文件——会让每次 invoke 都拖入三段长技法,稀释主纪律。
- **风险**: 子技法按需引依赖 agent 主动去读,若 SKILL.md 引导不清可能不读。对策:在 4 阶段对应步骤处明确「需要时见 references/X.md」。

### 决策 2: 发现/安装 = 放 .claude/skills/,零注册

- **选择**: 新建 `.claude/skills/systematic-debugging/`,靠 harness 目录约定自动发现,按 `name` invoke。
- **理由**: 现有 6 个 change-* skill 全是这么被发现的,无 manifest。零注册成本。
- **拒绝**: 引入注册表/manifest——项目根本没有,凭空造。
- **风险**: 无。

### 决策 3: 3-strike 归属 = skill 内 worker 调试纪律,§7.3 数值不动

- **选择**: 「同类 fix 连续 3 次失败、每次在别处冒新问题 → 停手质疑架构、上报 leader」写进 skill 内容(Phase 4),是 worker 调单个 bug 当下的纪律。worker §7.3 的「同 roadpoint 6 次失败 → 回退重拆」**数值与逻辑不动**。
- **理由**: 二者都在 worker 内,但量不同的轴——3-strike 是「架构方向信号」(级联式 fix 暴露架构问题),§7.3 是「roadpoint 级机械重试」。并列共存,不冲突(经用户确认:superpowers 的 3 次对应 worker 内,不是 worker-reviewer 外循环)。
- **拒绝**: 统一成一个数 / 把 §7.3 改成 3——会混淆两个不同信号,且 §7.3 已被现有实施流程依赖。
- **风险**: worker 同时读到 3 和 6 困惑。对策:§7.3 call-in 处加一句点明「3-strike 在 skill 内、是架构信号,与本节 6 次机械回退并列、各管各轴」。

### 决策 4: call-in 落点 = worker + spec-author 两处 + reviewer 不接入

- **选择**:
  - **worker §0**:新增硬规则「撞到非平凡 bug / 测试失败 / 意外行为 → 动手修前先 invoke `systematic-debugging` 找根因」,挂在 §0.2 禁兜底旁(同源:都要修根因不修症状)。
  - **worker §7.2**:把「分析原因」这步展开为 invoke skill(读报错→复现→多层定位→反向追源头→单一假设最小验证),根因定位后回三提交 C1 写复现测试。
  - **worker §7.3**:加决策 3 的并列说明,数值不动。
  - **spec-author §4**:bugfix 根因(RCA / fix.md 根因段)处加 call-in——用 skill **调查阶段**挖「为什么这种错能进来」,**明标只调查、不做 Phase 4 修复**(spec-author 禁碰代码)。
  - **reviewer §0**:加「不 invoke `systematic-debugging`」声明,理由=会驱动 trace/加日志/读源码,正是 §0.2/§0.3 禁的;看不到判 fail,归因交 fix worker。
- **理由**: 落点都是「调试纪律真正被触发/被防止误触发」的地方;orchestrator 不亲自 debug 故不接入;fix worker 跑的就是 worker 那条纪律,已覆盖。
- **拒绝**:
  - orchestrator call-in——Project Lead 不 debug,§6.2 已写全根因路由,加了冗余且诱导越界。
  - worker §9 反 anti-pattern 加条目——§0 + §7 已足够强调,再加显厚重(经用户确认)。
- **风险**: 改动散落 4 个文件,引用名/§号写错会让 call-in 指空。对策:M1 退出标准逐条核对引用名与 skill 实际 `name` 一致。

### 决策 5: 自动触发口径 = description 限定「非平凡 bug」+ reviewer carve-out 兜底

- **选择**: skill 的 `description` 触发条件写成「遇到 bug / 测试失败 / 意外行为,在提出修复方案之前」可自动触发;同时靠 reviewer §0 的「不接入」声明拦住它在产品验收场景误触发。
- **理由**: 既要让任意角色撞 bug 时它能自触发(不必每处都显式 invoke),又要防它在 reviewer 走旅程遇到「意外行为」时被拉起、把 reviewer 推进 engineer 模式。
- **拒绝**: description 写得极宽(「任何报错」)——会在普通预期内失败、reviewer 旅程异常时狂触发。
- **风险**: 自动触发是 harness 行为,实际触发时机不完全可控。接受:reviewer carve-out 是显式兜底;其余角色多触发一次调查纪律也无害(顶多多走一遍根因流程)。

## 接口与数据流

技法 skill 无代码接口,「接口」= invoke 契约与调用流。

**调用流(worker 撞 bug 时)**:
```
worker 实施中 <test_command> 失败 / 行为异常
  └─ (§0 硬规则) invoke systematic-debugging
       ├─ Phase 1 根因调查:读完整报错 → 稳定复现 → 多组件系统打边界日志定位哪层断
       │     └─ 需要时读 references/root-cause-tracing.md(反向追调用栈到坏值源头)
       ├─ Phase 2 模式分析:找能跑的相似代码对照,逐条列差异
       ├─ Phase 3 假设:写下单一假设 → 最小改动验证(一次一个变量)
       │     └─ 3 次同类 fix 失败且各冒新问题 → 停手质疑架构 → 上报 orchestrator(worker §4/§7.3 既有通路)
       └─ Phase 4 实施:根因确认后 → 回 worker §5 三提交(C1 写复现测试 → C2 修 → C3 文档)
              └─ 需要时读 references/defense-in-depth.md(根因处多层加校验)
                 references/condition-based-waiting.md(flaky 用条件轮询替代写死 timeout)
```

**调用流(spec-author 写 RCA 时)**:invoke 仅取 Phase 1–2(读报错 / 复现 / 反向追源头)挖根因写进 RCA;**不进 Phase 3/4**(禁碰代码)。

**反向契约(reviewer)**:显式**不** invoke;遇用户面异常直接判 fail + 描述现象,归因交 fix worker。

**触发契约(description)**:frontmatter `description` 含「遇 bug / 测试失败 / 意外行为、提出修复前」的触发语;reviewer §0 carve-out 为唯一显式例外。

## 契约层增量 (delta-spec)

- kernel: no spec delta
- im:     no spec delta
- gateway: no spec delta
- cli:    no spec delta

> 本 unit 只改 `.claude/skills/` 方法论文档,不触及任何产品包对外行为,故四包全 no spec delta。

## 风险与回退

- **风险:skill 沦为「没人真照着走」的死文档**。prompt 类变更固有,无法 e2e 证明 agent 行为真的改变。**接受**(spec Q2 已认):验收只到「文档存在 + 自洽」,不强求动态演示。
- **风险:自动触发误伤**。description 太宽会在预期内失败 / reviewer 旅程异常时狂触发。**对策**:description 限定「非平凡 bug、修复前」+ reviewer §0 carve-out。
- **风险:阈值混淆**(3 vs 6)。**对策**:决策 3——§7.3 处点明并列关系,数值不动。
- **风险:call-in 指空**(引用名 / §号写错)。**对策**:M1 退出标准逐条核对。
- **回退**:删 `.claude/skills/systematic-debugging/` + revert 4 个 call-in 段。纯文档、无数据迁移、无运行时依赖,`git revert` 即干净回滚。

## Runbook for Reviewer

**无常驻服务**——本 unit 只产出 / 修改 `.claude/skills/` 下的 markdown,无任何需启停的进程。

> 且本 unit 为**零用户面**(无产品 UI / CLI / 旅程可走):按 orchestrator §5,**reviewer 跳过**,只派 **verifier** 读文档核对 spec 的 6 条 Requirement(skill 存在性 + 内容完整 + 4 处 call-in 文本 + 自洽)。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| feat-396-M1 | impl | — | A | `.claude/skills/systematic-debugging/`(新建 SKILL.md + references/);`.claude/skills/change-impl-worker/SKILL.md`;`.claude/skills/change-spec-author/SKILL.md`;`.claude/skills/change-reviewer/SKILL.md` | 见下方两轨 |

**feat-396-M1 退出标准**（本 unit 零用户面 → 无 `[reviewer]` 轨;全部 `[worker]` 轨,由 worker 读文件自验、verifier 复核）:

- `[worker]` `.claude/skills/systematic-debugging/SKILL.md` 存在,正文中文无英文残留,含:根因优先铁律、4 阶段调查纪律、Red Flags 自查清单、「3 次同类 fix 失败 → 质疑架构」停手条件（覆盖 spec Req「skill 可用且内容完整」)
- `[worker]` `references/` 含三子技法 `root-cause-tracing.md` / `defense-in-depth.md` / `condition-based-waiting.md`,SKILL.md 在对应步骤按需引用它们（覆盖 spec Req「三个子技法在位」)
- `[worker]` worker §0 新增硬规则 + §7.2 展开 invoke + §7.3 并列说明(数值不动)已就位,引用名指向真实存在的 skill（覆盖 spec Req「worker 被引导走根因优先」「不和三提交重复」)
- `[worker]` spec-author §4 RCA call-in 就位,明标「只调查不修」（覆盖 spec Req「spec-author 仅调查」)
- `[worker]` reviewer §0 「不接入」声明就位（覆盖 spec Req「reviewer 显式不接入」)
- `[worker]` 自洽:无两套打架的调试说法(3-vs-6 有并列说明);call-in 引用名与 skill `name` 一致;未重复三提交流程（覆盖 spec Req「现有重复调试内容已收敛」)
- `[worker]` orchestrator/verifier 未被改动(范围外)
