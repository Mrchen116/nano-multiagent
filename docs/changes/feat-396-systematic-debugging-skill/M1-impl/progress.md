# feat-396-M1 — Progress

> 实施方式:本 unit 由用户指定「不派 worker,orchestrator 亲自实施」(亲自干模式)。单 milestone,直接在 unit/feat-396 worktree 内完成,未另起 milestone 分支。

## R1 — 新建 systematic-debugging skill(SKILL.md + 3 子技法)

- Context: design 决策 1/2/3/5——新建技法 skill 作为调试纪律单一权威,结构 = SKILL.md + references/ 三子技法,中文、效果优先。
- Decision: 写 `.claude/skills/systematic-debugging/SKILL.md`(核心铁律「没找到根因不许修」+ 4 阶段 + 「3 次失败质疑架构」+ Red Flags + 常见自我开脱表 + 子技法索引);写 `references/` 三子技法。
- Rationale: 忠实改写 superpowers 原文(亲自读了 superpowers 的 SKILL.md + 三个 .md 子技法),译成中文、例子从 TS/Node 换成本项目 Python/pytest 语境;裁掉 Phase 4 自带提交流程,改为「回 §5 三提交」避免与 worker 三提交打架;子技法放 references/ 按需引(沿用 orchestrator references/ 模式)。defense-in-depth 显式调和与 worker §0.2 禁兜底的张力(多层校验是「非法就炸」非「吞错」)。
- Evidence:
  - Tests: N/A —— 纯方法论 markdown,无可断言代码行为(免 C1 红测,见 tasks.md 测试策略)。
  - Entry: 文件树确认 `SKILL.md` + `references/{root-cause-tracing,defense-in-depth,condition-based-waiting}.md` 四文件就位;frontmatter `name: systematic-debugging`;SKILL.md 在 阶段1.5/4.4/4.5 + 索引段按需引三 references(grep 命中 6 行)。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A —— 无运行时入口。
  - Visual/Interaction: N/A
- Rollback: 删 `.claude/skills/systematic-debugging/` 整目录。
- Commits: 见 unit/feat-396 分支 `feat(feat-396/M1)` commit。

## R2 — 接 call-in + 收敛重复

- Context: design 决策 4——在调试纪律真正被触发/被防误触发的地方接上。
- Decision:
  - worker `§0.12` 新增硬规则「撞 bug 先 invoke skill 找根因再修」(挂 §0.11 后,声明与 §0.2 同源);`§7.2` 把「分析原因」展开为 invoke skill 走根因流程 + flaky 用 condition-based-waiting;`§7.3` 末尾加 3-vs-6 并列说明,**6 次数值不动**。
  - spec-author `§4` bugfix RCA 处加 call-in,明标「只用调查阶段 Phase 1–2,不进修复」(spec-author §0.6 禁碰代码)。
  - reviewer `§0.8` 新增「不 invoke systematic-debugging」声明,理由对齐既有 §0.2/§0.3 禁 debug-by-editing。
  - orchestrator / verifier:**不动**(design 决策 4:Project Lead 不亲自 debug,§6.2 已覆盖根因路由;verifier 读码核对非调试,无关)。
- Rationale: call-in 只加引用句、不重写既有规则(spec Q3:只动调试相关内容);worker §0.12 用追加而非插入,避免重排 §0.3–§0.11 编号引发的连锁引用错误。
- Evidence:
  - Tests: N/A
  - Entry: `grep "systematic-debugging"` —— worker 3 处(§0.12 / §7.2 / §7.3)、spec-author 1 处(§4 RCA)、reviewer 1 处(§0.8);orchestrator + verifier **零命中**(符合 design 决策 4)。引用名全部 = skill frontmatter `name`(`systematic-debugging`),无指空。§7.3 仍写「连续失败 > 6 次」(数值未动)+ 新增 3-vs-6 并列说明。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: revert worker §0.12/§7.2/§7.3、spec-author §4、reviewer §0.8 三文件对应段。
- Commits: 见 unit/feat-396 分支 `feat(feat-396/M1)` commit。

## 退出标准核对(self)

design.md M1 全部 `[worker]` 轨退出标准逐条已满足(见 tasks.md 勾选 + 上方 Evidence)。本 unit 零用户面 → reviewer 跳过,留待 verifier 读文档复核 spec 5 条 Requirement。
