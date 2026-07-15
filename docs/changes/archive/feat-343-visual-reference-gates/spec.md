# feat-343: 前端视觉/reference 证据门禁

> 追溯说明:本 unit 是 feat-340 实战中暴露出的 change-* 工作流缺口后补 spec。skill 改动已经在对话中先行完成,本 spec 用于记录为什么需要把"真实视觉效果 + reference 对照"前移到 worker 自测和 reviewer 验收中。

## Relations

- Surfaced from: feat-340-agent-native-im 原型重写验收
- Builds on: feat-341-change-workflow-skills, feat-342-reviewer-boundary-and-runbook

## 原始需求

用户在 feat-340 继续使用 change-* skill 时发现 reviewer 没有做真实前端页面与原型的对比:

> 现在观察到一个新问题，就是 feat-340 继续用这套 skill 进行时，做 review 的时候没做真实的前端页面和原型的对比，你分析对应的 spec，design，还有进展文档等，以及各个 skill 下，分析到底哪些环节出现了问题

进一步分析后,用户指出问题不能只靠 reviewer 兜底:

> 所以我觉得 "M4/M5 的 tasks 明确把视觉测试 punt 给 design-review，自己'不写 snapshot / 本期只做行为测试'" 这个是关键，不能所有事情都到 review 的时候才判断不 work 然后又要找 agent 翻修，这不符合逻辑。开发自测都不进行。

最终收口为通用 skill 规则:

> 对，谨慎地加进去。关键就是要真实视觉效果和交互效果，验收。如果有原型/设计稿/reference，要对照。对吧

> ok，这个也作为新 feature，补 spec，然后新建分支做 commit

## 澄清记录

- Q1: 这是某个项目的特殊要求,还是通用工作流问题?
  A: 通用问题。任何软件仓库中,只要任务涉及前端 UI、视觉效果、原型、设计稿、reference screenshot、响应式或布局样式,worker 和 reviewer 都不能只靠单元测试或组件测试判断完成。

- Q2: worker 阶段要做什么?
  A: worker 仍然按 TDD 做自动化测试,但前端 UI milestone 还必须用真实入口打开页面/界面做自测。若任务有 reference,必须记录截图/录屏、viewport/状态、reference 对照结论。页面"能渲染"不等于"符合 reference"。

- Q3: reviewer 阶段要做什么?
  A: reviewer 必须把 reference artifact 当作验收真值的一部分,真实打开产品,拿当前截图/录屏/可观察输出对照 reference。缺少真实证据或无法对照时,对应验收项必须是 `inconclusive` 或 `fail`,不能 pass。

- Q4: orchestrator 要不要判断视觉质量?
  A: 不要。orchestrator 只做证据完整性 gate:worker DONE 时检查 progress 里是否有前端视觉/交互自测证据;reviewer pass 时检查报告覆盖表是否包含期望来源和真实对照证据。质量判断仍归 reviewer。

- Q5: 是否引入自动像素 diff / 固定浏览器工具?
  A: 不引入。skill 保持工具无关,只要求真实入口证据和 reference 对照结论。

## 用户场景

### 场景 A:worker 实现一个按设计稿重写的前端页面

worker 读到 milestone 退出标准包含"原型 / 视觉一致 / 响应式"。它除了写组件交互测试,还会启动或打开真实产品入口,在设计要求的关键 viewport 下操作页面,保存截图或录屏,并在 `progress.md` 的 `Visual/Interaction` 中写清:

- 当前产品入口和页面状态
- 截图/录屏路径
- 对照的设计稿 / 原型 / reference 名称或路径
- 对照结论和明显差异

没有这段证据,orchestrator 不接收 worker DONE。

### 场景 B:reviewer 验收带 reference 的 UI unit

reviewer 读 spec/design 时发现验收标准引用了原型、设计稿或 reference screenshot。它会先读取/打开 reference,再走真实用户旅程,保存当前产品截图/录屏,并在 acceptance 覆盖表中逐条记录"期望来源 / 验证方式 / 证据 / 结果"。如果只看到"页面能渲染",但没有 reference 对照,该项不能 pass。

### 场景 C:orchestrator 接到 pass 或 DONE

orchestrator 不评价页面好不好看,只检查报告和进展文档有没有对应证据:

- worker DONE:涉及前端视觉/reference 的 milestone,`progress.md` 必须有真实入口视觉/交互证据
- reviewer pass:覆盖表不能只列 focus fix;涉及 reference 的验收项必须有期望来源和真实产品截图/录屏/对照结论

缺证据则退回对应 agent 补验,不代写、不自行判断。

## 验收标准

- [ ] 前端 UI 新功能在 worker 测试策略中不仅要求组件交互测试,还要求真实入口下的视觉/交互自测
- [ ] 当首文档、design 或 milestone 退出标准引用原型、设计稿、reference screenshot、视觉一致、像素级、响应式、布局/样式时,worker 必须记录真实产品截图/录屏、viewport/状态和 reference 对照结论
- [ ] `change-impl-worker` 的 progress 模板包含 `Visual/Interaction` 证据栏,非前端任务可写 `N/A`
- [ ] orchestrator 接 worker DONE 时,若任务涉及前端视觉/reference 要求,会检查 `progress.md` 是否有真实入口视觉/交互自测证据;缺失则退回 worker 补齐
- [ ] reviewer 读到 reference 类验收要求时,会把 reference artifact 视为验收真值的一部分,并在覆盖表记录期望来源
- [ ] reviewer 对 reference 类验收项必须用真实产品截图/录屏/可观察输出做对照;缺少对照证据时不能 pass
- [ ] acceptance 模板的验收标准覆盖表包含 `期望来源` 列,用于记录 spec/design/reference 路径或名称
- [ ] orchestrator 接 reviewer pass 前会检查报告覆盖表是否完整,不会允许 focus round 把未关闭的 `fail` / `inconclusive` 或 reference 缺证据项冲掉
- [ ] 所有 skill 改动保持通用,不引用具体仓库的服务名、模块名、页面名或专属命令

## 范围与非目标

**在范围**:

- `.claude/skills/change-impl-worker/SKILL.md`
- `.claude/skills/change-impl-worker/assets/progress.md`
- `.claude/skills/change-reviewer/SKILL.md`
- `.claude/skills/change-reviewer/assets/acceptance.md`
- `.claude/skills/change-orchestrator/SKILL.md`

**非目标**:

- 不引入自动像素 diff、截图阈值或视觉回归平台
- 不指定必须使用某个浏览器/截图工具
- 不要求所有 CSS 细节都自动化测试
- 不让 orchestrator 判断视觉质量
- 不修改项目业务代码
- 不回溯修复 feat-340 本身的页面实现
