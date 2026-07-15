# feat-344: change-impl-worker 前端验收分流

## Relations

- Related: feat-340
- Related: feat-341
- Related: feat-343

## 原始需求

> 我和chatgpt深入沟通后决定，前端做tdd不是总是合理的，不是后端。前端要分情况。

> 我觉得不用Storybook和Chromatic，就真实浏览器截图验证就行了，这样简化点一来。你再认真分析一下是否有问题。

> 你总结的很好，开始给我改。注意，不要引入无关的修改

> 我忘记说了，这个skill是通用场景的skill，不要写入任何本仓库的特定内容

> .claude/skills中change-*系列skill是一起中的工作流，你在里面讲的spec和外面的spec重名了，你想表达的这个spec要落入到哪里？

> skill的description的作用是，给agent挑选skill的时候用的，不用写这么具体

> 那就是算了。直接在主仓上改。当前的这个修改其实也是一个需求，按.claude/skills/change-spec-author/SKILL.md做一个spec追溯说明，然后在新分支提交，然后把新分支合并到feat 340分支，最后回到feat 340分支，明白吗

## 澄清记录

- Q1: 前端 UI 是否仍然强制后端式 TDD?
  A: 不强制。后端/API/纯逻辑保持 Red → Green → Docs 的 TDD 心智；前端 UI 按风险分流，C1 可以是测试、状态矩阵、验收清单或 regression 复现。
- Q2: 前端视觉/普通 UI 是否引入 Storybook / Chromatic?
  A: 不引入。普通 UI 和视觉细节优先用真实浏览器验收、截图证据和状态覆盖；不为单个 milestone 强行引入新基础设施。
- Q3: 核心业务路径和历史 bug 是否可以只靠截图?
  A: 不可以。核心路径和历史 bug 必须留下可重复 regression 保护；若项目已有浏览器 E2E 体系则优先复用，没有则使用现有测试体系的交互/集成回归。
- Q4: 新增的 roadpoint 级别验收内容应落在哪里?
  A: 落在 worker 创建的 `docs/changes/<unit_dir>/<milestone_dir>/tasks.md` 中；完成证据落在同目录 `progress.md` 中。不要命名为 spec，避免和 change-spec-author 的 `spec.md` 或项目 `SPEC.md` 混淆。
- Q5: skill frontmatter description 应写到什么粒度?
  A: 只写给 agent 选择 skill 所需的信息：用途、触发条件和不要用于哪些场景。具体执行规则放正文。

## 用户场景

维护 change 工作流的人在调度 `change-impl-worker` 时，需要同一个 worker 同时适配后端/API、纯逻辑和前端 UI milestone。

当 milestone 是后端/API/纯逻辑时，worker 仍应坚持明确的 TDD 三提交循环，先写失败测试再实现。

当 milestone 是前端 UI 时，worker 不应机械套用后端 TDD。它应先判断变化属于核心业务路径、普通 UI、视觉细节还是历史 bug，再选择合适的验收方式：状态矩阵、现有测试体系中的 regression、真实浏览器操作、console/network 检查和截图证据。

这样 reviewer 和 orchestrator 能从 `tasks.md` / `progress.md` 里看到前端到底覆盖了哪些状态、打开了哪个真实入口、执行了哪些用户操作、是否需要落库 regression，以及不落库时的理由。

## 验收标准

- [ ] `change-impl-worker` 不再以“所有 roadpoint 都必须先写失败测试”描述前端 UI 任务。
- [ ] 后端/API/纯逻辑仍保留 TDD 三提交要求，不能被前端分流规则削弱。
- [ ] 前端 UI 任务明确要求真实浏览器验收，包括真实页面入口、关键用户操作、console error 检查、failed network request 检查和可复查证据。
- [ ] 前端核心业务路径和历史 bug 必须有可重复 regression 保护；如已有 E2E 体系优先复用，没有则使用现有测试体系，不强行搭新基础设施。
- [ ] 前端普通 UI 和视觉/样式细节不强行写 E2E，不引入 Storybook / Chromatic 要求，以状态矩阵和真实浏览器截图证据为主。
- [ ] roadpoint C1 的前端语义命名为 `Verify/Red` 或“验收清单”，不使用容易和 `spec.md` / `SPEC.md` 混淆的 `spec`。
- [ ] `tasks.md` 模板为前端 UI milestone 提供用户路径分类、UI 状态矩阵、测试与验收映射。
- [ ] `progress.md` 模板拆出 `Frontend State Matrix`、`Browser QA`、`E2E/Regression`、`Visual/Interaction` 证据字段。
- [ ] `SKILL.md` frontmatter `description` 保持简短，只服务 skill 选择，不塞入执行细节。
- [ ] 文档内容保持通用，不写入 nano-multiagent 当前前端工具栈、路径或其他本仓库特定实现细节。

## 范围与非目标

- 在范围：
  - 更新 `.claude/skills/change-impl-worker/SKILL.md` 的执行规则。
  - 更新 `.claude/skills/change-impl-worker/assets/tasks.md`。
  - 更新 `.claude/skills/change-impl-worker/assets/progress.md`。
  - 新增本追溯 spec 文档。
- 非目标：
  - 不修改产品代码。
  - 不新增 Storybook、Chromatic、Playwright 或其他前端基础设施。
  - 不修改 change-orchestrator、change-design-author、change-reviewer 的行为。
  - 不重开完整 design/milestone 流程；本文件仅作为这次已明确需求的追溯说明。
