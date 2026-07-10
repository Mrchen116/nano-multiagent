# feat-457-M1: skill-suite — Tasks

> 对齐: ../design.md v1

## 目标

以上游 `mattpocock-skills` commit
`d574778f94cf620fcc8ce741584093bc650a61d3` 为基线，引入通用
`codebase-design` 技法，保留 `improve-codebase-architecture` 的 organic
exploration 与 HTML 表达，只修复其与现有通用 skill 流程的三个兼容点，
并让 `change-design-author` 仅在 deep-module 设计场景按需调用该技法。

## 退出标准

- [ ] `codebase-design/` 含上游三份方法文档与 MIT `LICENSE`，只增加项目正式术语优先级和 Design It Twice 按需触发说明。
- [ ] `improve-codebase-architecture/` 含上游主文档、HTML 指南与 MIT `LICENSE`，差异仅覆盖可选 grounding、仓库内版本化报告、handoff continuation 与正式术语优先级。
- [ ] `change-design-author/SKILL.md` 明确四类正向触发、普通设计反向条件、既有章节投影和 Design It Twice 二级门槛。
- [ ] 无固定扫描过滤、候选台账、仓库专项检查清单，无 `src/`、canonical spec 或其他 change-* 角色改动。
- [ ] 目标 Markdown frontmatter 可解析且 skill 名与目录一致，内部相对链接可解析，`git diff --check` 通过。
- [ ] reviewer 可按 `design.md` 两轨退出标准真调用 skill，验证 Git/非 Git 报告、候选 handoff 和 design-author 的条件 call-in。

## 测试策略

- 被测行为（来自退出标准）：上游文档完整引入且差异受限；报告路径/版本元数据/不覆盖约束可执行；handoff 字段完整；design-author 条件触发与二级门槛明确；frontmatter、相对链接和范围边界合法。
- 已有测试在：`tests/unit/test_skill_registry_frontmatter.py`（运行时 frontmatter 解析基线）；无适合的仓库 skill 文档内容回归测试，本 milestone 不在 design 范围外新建测试文件。
- 落层/目录/marker：现有 `tests/unit/`，marker：无；文档内容以一次性结构校验、上游 diff 审计与 reviewer 真调用验收。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：临时 Python 校验命令的输出摘要记入 `progress.md`，不留临时脚本。
- 前端 UI：N/A。
- Prototype / Reference Contract：N/A（design 无前端原型/reference）。

## Roadpoints

### R1 — 引入 deep-module 设计技法

- 状态：DOING
- 步骤：从锁定上游 commit 引入 `codebase-design` 三份方法文档与许可证；只补正式术语优先级、按需 Design It Twice 兼容说明。
- 验证：逐文件对比上游；校验 frontmatter 名称、三份内部相对链接、MIT notice 和术语优先级/二级门槛文案。

### R2 — 修正架构巡检的通用流程接点

- 状态：TODO
- 步骤：引入并最小修改 `improve-codebase-architecture`，实现可选 grounding、仓库内独立 HTML 快照、Git/非 Git 元数据、固定 handoff 与现有流程 continuation。
- 验证：对比上游确认 organic exploration/候选卡/before-after/强度/top recommendation 保留；逐条检查报告路径、Git 语境、不覆盖、无 Git、handoff 与无候选台账。

### R3 — 把 deep-module 技法条件接入设计作者

- 状态：TODO
- 步骤：在 `change-design-author` 的 grounding 后增加按需 call-in，结果只投影到既有现状/决策/接口与风险段。
- 验证：检查四类正向触发、普通设计反向条件、正式术语优先级、既有章节投影、两种以上实质方案 + 用户需比较的二级门槛；全套目标文件结构校验与 `git diff --check`。
