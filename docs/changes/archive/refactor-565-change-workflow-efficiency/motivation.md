# refactor-565: 精简 change 流程的重复编排

## Relations

- Related: feat-563, refactor-564, refactor-556

## 原始诉求

> 我发现，你用我的skill体系工作的这两个unit花费了大量token，我怀疑主要是你开了一堆subagent。根据这次的轨迹帮我分析下，哪些其实是没什么用的流程，哪些地方可以简化流程

> 有一个容易忽略问题：如果一个subagent放着很久，过了cache时间，又重新复用，就会有大量消耗。

> 简单列一下哪些skill要改哪些关键点

> ok，新开一个unit改下

> 然后code review，change-verifier这种subagent现在要求用什么模型？这两次unit中不会也用的Astra吧，那就消耗大了。

> 要改啊，这就是本unit要解决的其中一个问题

> `change-verifier`、`change-code-review`、`change-spec-reviewer` Terra + High就好了。候选问题二次核验 Sol / medium。然后`change-reviewer`涉及界面操作，多模态，用astra low。`change-design-reviewer`很重要，继承主agent。

> 修复我觉得是不是不用开subagent了，直接主agent干？第一轮有必要就分工多个agent，但是后面发现问题，全部主agent干，可以不

> 好

## 澄清记录

用户已接受前轮列出的五个 Skill 修改方向与 workflow 同步：simple 默认主 Agent 实施；设计复审按实质变化；代码审查的二次核验按风险与争议；代码和一致性审查可由同一独立 Agent 完成；保留真实产品验收、定向复测与测试证据复用。用户进一步明确模型选择同属本 unit：实现、复杂调查和设计审查继承主模型；spec/code/verifier 用 Terra/high，候选核验用 Sol/medium，产品 reviewer 用 Astra/low；由派发方控制，不把模型选择放入执行角色 Skill。后续问题统一由主 Agent 修复，不再派修复 worker。无需重新对齐相同决定。

## 现状痛点

feat-563 / refactor-564 的轨迹显示 EOF 空行变更重新审设计、同一小修三路静态复核、fixture 未稳定就启动全量测试。14 个子 Agent 占非缓存输入约 66%，但不能等同浪费比例。缓存失效原因未知，不能规定固定 TTL 或保证复用一定省钱。

当前 workflow 强制同一个设计 reviewer，最后一轮后任何文件变化都会失效；code review 默认 finder 与候选 verifier 分开；simple 未明确默认主 Agent 端到端实施。角色方法已有 targeted/closure/retained 能力，可直接复用。

## 目标状态

保留独立审查、完整需求覆盖和真实产品验收，减少机械拆分、重复复审、碎片化唤醒与重复验证。同一独立静态审查者可以覆盖代码、契约与 delta，报告仍可追溯。旧 Agent 复用基于历史必要性与上下文成本，不假定缓存有效。

## 用户侧验收标准（不变性）

无产品用户面：仅修改仓库开发流程和 Skill 文档，不改 CLI、SDK、Gateway、IM 或运行配置。开发流程消费者的检查标准见 design 的情景矩阵；真实产品验收在其他有用户面 unit 中仍必需。

## 影响范围

五个目标 Skill、change-workflow，以及存在冲突的 author/orchestrator 引用和 handoff 文档。同步退役受影响的旧规则文本测试；仅做必要同步，不扩展原流程的 worker 实施组织。

## 迁移与回滚策略

新派发按新规则；旧报告与 reviewer 身份、已执行版本和未解决 findings 保留，接手时明确审查范围。独立性不降低为作者自签；无法保留旧证据时扩大审查。回滚本 unit 文档提交即可，不涉及运行数据迁移。
