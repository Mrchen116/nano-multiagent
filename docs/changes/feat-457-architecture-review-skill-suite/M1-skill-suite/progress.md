# feat-457-M1 — Progress

> 计划已对齐 `design.md` 的单 milestone 范围；实施与验证仅在
> `/Users/czj/Repos/nano-multiagent/.worktrees/feat-457-M1` 进行，不读取或修改主仓未跟踪的
> `.claude/skills/improve-codebase-architecture/` 副本。

## Baseline

- Sync gate: `unit/feat-457` 与 `origin/unit/feat-457` 同为 `0f123b727d181a9427c2bb62dbd0b202f3ca394f`。
- Upstream: `/Users/czj/Repos/opensource-hub/mattpocock-skills` 已校验 commit `d574778f94cf620fcc8ce741584093bc650a61d3` 存在。
- Tests: `pytest -q tests/unit/test_skill_registry_frontmatter.py` → `3 passed`。
- Structure: 现有 `change-design-author` frontmatter 名称与目录一致，相对链接可解析；`git diff --check` 通过。

## R1 — 引入 deep-module 设计技法

- Status: DONE
- Verify/Red: 一次性完整性校验要求 `SKILL.md`、`DEEPENING.md`、
  `DESIGN-IT-TWICE.md` 与 `LICENSE` 全部存在；当前失败并精确报出四个缺失路径，
  证明未把主仓用户副本当作实现基线。
- Verification contract:
  - 四份文件来自锁定上游 commit，文档主体可逐文件 diff。
  - frontmatter `name` 等于目录名 `codebase-design`。
  - `SKILL.md` 指向 `DEEPENING.md` 和 `DESIGN-IT-TWICE.md` 的相对链接存在。
  - 兼容文案只限正式术语优先级、普通设计不机械触发，以及重要 interface 存在实质多方案且用户需比较时才执行 Design It Twice。
- Context: 巡检与 design-author 需要共用 deep-module 设计语言，但不应引入 Matt 的整套工程流程。
- Decision: 从锁定上游 commit 引入三份方法文档与 MIT notice；`SKILL.md` 只补项目正式术语优先级和非机械 Design It Twice 触发，`DESIGN-IT-TWICE.md` 只补实质方案门槛与可选 `CONTEXT.md`。
- Rationale: 保留上游 glossary、deepening 依赖分类、seam discipline、interface-as-test-surface 和并行多方案比较的完整方法，同时避免共享词汇覆盖项目命名或普通设计自动 fan-out。
- Evidence:
  - Tests: 一次性 Python 校验确认四文件集合、frontmatter、相对链接、LICENSE 逐字相同、`DEEPENING.md` 逐字相同；`pytest -q tests/unit/test_skill_registry_frontmatter.py` → `3 passed`；`git diff --check` 通过。
  - Entry: 真实 skill 入口文档 `.claude/skills/codebase-design/SKILL.md` 可被 frontmatter 发现，且从该入口指向的两份按需参考均可解析。
  - Frontend State Matrix: N/A（纯 skill Markdown）。
  - Browser QA: N/A（无前端）。
  - E2E/Regression: N/A；提示词执行效果由 reviewer 按 design Runbook 真调用验收，不为文案内容引入脆弱字符串单测。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert C2 `b35a6f90` 可完整删除新 skill；C1 只是验证记录。
- Commits: C1=`08bdf401`, C2=`b35a6f90`, C3=本提交。
- Next: R2 引入并最小修改架构巡检 skill。

## R2 — 修正架构巡检的通用流程接点

- Status: DONE
- Verify/Red: 一次性完整性校验要求 `SKILL.md`、`HTML-REPORT.md` 和 `LICENSE` 全部存在；当前失败并精确报出三个缺失路径。
- Verification contract:
  - 保留上游 organic exploration、deletion test、候选卡、before/after、推荐强度和 top recommendation。
  - grounding 读取项目实际存在的 instructions/架构文档/领域词汇/决策记录，`CONTEXT.md`、`CONTEXT-MAP.md` 与 ADR 均可缺失且不创建。
  - 报告根目录、`docs/architecture-reviews/`、时间 + 短 SHA/`no-git`、递增后缀、完整 Git 元数据和 dirty 警示全部显式。
  - 候选选择后只输出固定 handoff；有 `change-spec-author` 则作为 refactor 需求转交，无则交还项目流程/用户，不设计 interface 或改代码。
  - 无固定扫描集合、排除规则、候选台账或仓库专项检查清单。
- Context: 上游 skill 的探索与 HTML 表达正是需要的主体，但强制 `CONTEXT.md`/ADR、OS 临时报告和 grilling/domain-modeling continuation 与当前通用流程不兼容。
- Decision: 保留 Explore 问题集、deletion test、候选卡与视觉指南；将 grounding 改为读取实际存在的项目文档，将报告改为仓库内带 Git 语境的独立快照，将选中候选后的流程改为固定 handoff。
- Rationale: 只替换 design 指定的通用流程接点，既不把 skill 改成 nano-multiagent 专用扫描器，也不引入候选状态系统或另一套 interface 设计流程。
- Evidence:
  - Tests: 一次性 Python 校验确认三文件集合、frontmatter、相对链接、LICENSE，覆盖上游主体保留点、报告路径/Git 元数据/不覆盖/无 Git、handoff 字段和禁止范围；`pytest -q tests/unit/test_skill_registry_frontmatter.py` → `3 passed`；`git diff --check` 通过。
  - Entry: 真实 skill 入口 `.claude/skills/improve-codebase-architecture/SKILL.md` 现在从 Explore 到 report 再到 handoff 形成完整用户路径；主文档链接的 `HTML-REPORT.md` 可解析。
  - Frontend State Matrix: N/A（输出为架构报告文件，本 milestone 无产品前端）。
  - Browser QA: N/A；真调用生成/打开 HTML 属于 reviewer 轨退出标准，已在 design Runbook 指定。
  - E2E/Regression: N/A；本 roadpoint 是提示词契约，以结构校验 + reviewer 真 skill 调用验收，不将一次性验收脚本留入测试套件。
  - Visual/Interaction: HTML 指南保留 Tailwind/Mermaid、多种 diagram pattern、before/after 和 top recommendation；实际报告证据由 reviewer 生成。
  - Prototype Comparison: N/A。
- Rollback: revert C2 `d2a5cdb9` 可完整删除新 skill；C1 只是验证记录。
- Commits: C1=`7d091ec3`, C2=`d2a5cdb9`, C3=本提交。
- Next: R3 将 `codebase-design` 按需接入 `change-design-author`。

## R3 — 把 deep-module 技法条件接入设计作者

- Status: TODO
- Next: 等待 R2。
