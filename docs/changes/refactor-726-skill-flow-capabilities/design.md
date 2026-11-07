# refactor-726: 流程与能力组合 — 技术方案

## Changelog

## 现状分析

基线为 `29e3f2947699fb92b382c5f61b4a1ef169a40ede`。`.agents/skills` 指向 `.claude/skills`，只改真实文件。现有 workflow 与 storage 分别管理生命周期和产物；orchestrator 的 validation、派发适配可复用。前端体验原则已有 prototype-and-runbook/ui-decision-gotchas，Context 规范和观测入口已有独立权威文档，不复制它们。

用户批准在新 worktree 的 develop 上试验，覆盖旧流程默认首文档推 main 和交付 PR 的安排。保留隔离、真实证据、独立审查、不可静默改需求及生产授权边界；不修改其他 checkout。

## 结构与关键决定

1. 新增 `docs/development/skill-composition.md` 作为流程/能力/项目规范分工、选择与组合的唯一说明；workflow 负责各生命周期何时选择和收口，引用该说明，能力不反向调用编排或自行派发。
2. 保留 spec/design author、design reviewer、两条 orchestrator、fast-close、retro 的流程职责。code review 吸收实现遗漏、设计一致性与最终 delta 核对；移除其强制内嵌的专项方法，专项由执行安排明确选择。代码审查与专项可由同一独立人完成。
3. 将 change-reviewer 拆为 `product-journey-review` 与 `frontend-experience-review`；新增窄 `performance-review`；保留并收紧 `agent-context-review`。前端两份现有通用参考迁入前端能力，设计作者仍负责设计和原型产物，能力供其自检及独立审查复用。架构能力复用 codebase-design，不额外造入口。
4. 删除 change-verifier 和 change-reviewer 的旧入口、重复模板与报告同步说明，更新所有现行调用者和索引。历史 unit 不改写；接手旧 unit 时引用已有报告，新的结论写统一 review.md，不仅因换格式重审。
5. 新任务在 design.md / lite fix.md / 快速开发现有记录选择“问题、能力、证据”；设计 reviewer 核选择是否漏掉关键影响。实施中新增影响则补问题，复审按受影响结论选择，不按 skill 数量决定 Agent 数。故障调查与部署入口只增加按问题选择能力的路由，不移除其专有边界。
6. 实施后统一 `review.md`：每项问题记录能力/执行者、模式/范围、实际版本、结论、证据/限制、finding 与关闭依据。流程汇总覆盖和等待状态，不生成第二份 verifier 报告。并行审查返回结论，由 owner 串行归集并保留归属，避免共享文件互踩和报告提交引发 rebase。独立审查者确认自己的实际范围；空 findings 不等于所有证据已齐。
7. Codex 模型适配按执行任务所需能力和用户配置选择，合并时明确所需配置，不以旧角色档位强迫拆 Agent。保留现有可用型号；不构建注册表、自动评分器或新的编排运行时。

## Context 消费链与证据

消费者是开发 Agent：描述用于发现 → 仅加载当前流程与选中能力 → 读取任务问题和必要项目参考 → 返回可复核判断 → 流程收口。Before 是固定角色套餐和分立报告；After 是问题驱动选择与统一结果。

能力的自检/审查模式不能改变执行者独立性或授权。Context 实施审查先读实际交付输入及相关后续轮次，再解释源码；受控装配、真实模型行为与静态文档必须区分。对本次 skill 变更做独立有界演练，检查实际选择/执行输出；不声称已证明真实产品可靠或 token 节省。

## 本次审查安排

| 问题 | 能力 | 证据 |
|---|---|---|
| 所有现行入口、模板、报告与引用是否接到同一套职责，是否遗失需求覆盖/独立性/授权？ | change-code-review，含实现与设计覆盖 | 完整 diff、引用扫描、docs-check、已有契约测试 |
| 开发 Agent 能否按任务选择有限能力并在等待/文档变化时正确收口？ | agent-context-review，实施模式 | 独立 Agent 按新入口处理未给答案的有限场景，实际输出与所读材料；记录证据上限 |

不选择产品旅程、前端或性能验收：没有对应运行时/界面/性能改动，不启动 Nano 服务。上述能力本身的文字与接线由独立审查覆盖，后续 develop 自然需求试验由用户另行推进。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-skills | 流程与能力接线 | 无 | 串行 | skills、开发文档/索引、受影响契约测试 | [worker] 引用/模板/校验一致，独立设计与实施审查完成；[reviewer] 有界执行验证能力选择和收口，明确自然任务可靠性仍待用户试验 |

## 验证与交付

先跑现有 workflow contract 与 docs-check 得到基线；退休固定角色矩阵文本断言，保留仍有效的生命周期检查，按文档完整性保护入口和链接，不为新文案逐句加断言。完成后跑相关 Python 工具/契约测试、ruff、skill frontmatter 校验、引用扫描。此变更不涉及 TS/Web/iOS 产品源码，不以全产品回归代替 skill 行为验证。

独立设计审查按现有 Gate 2；实施审查采用用户批准的新职责组合和统一 review.md，保留实际执行记录。完成实现和有界验证后提交推送 develop，保留 worktree；unit 留 active，记录自然需求试验待用户进行。无 main PR、无部署，不把未触发远端 CI 写为通过。

## 契约、迁移与回退

no spec delta：不改变产品运行时行为；开发流程权威文档直接随实现更新。无常驻服务、无一次性部署迁移。旧入口删除需同步现行调用者，历史报告保留；发现失效接线直接修正，不保留第二套默认流程。可用 Git revert 回退本 unit 的实现提交。
