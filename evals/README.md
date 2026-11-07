# Evaluation suites

`evals/` 保存需要长期复用、可独立物化并进入版本管理的 Agent 评测资产。这里的内容不是产品测试，也不属于某个 change unit 的过程文档。

| Suite | 用途 | 入口 |
|---|---|---|
| Intelligent UI | 酒店、看板、会议确认、广告分析；每 case 独立空白上下文 | [intelligent-ui/](intelligent-ui/README.md) |
| Memory / LongMemEval | 完整历史准备记忆、冷上下文答题和固定评分；默认计划零模型调用 | [memory/](memory/README.md) |
| Spec/design alignment | 比较需求对齐工作流的用户对齐负担与最终产物质量；当前包含 8 个历史回归和前瞻 pilot case | [spec_design_alignment/](spec_design_alignment/README.md) |
| Agent 内部协作 | Global Agent 的独立派工、同主题续派和授权问答 | [agent_coordination/](agent_coordination/README.md) |

后续记忆评测的方法研究位于 feat-677：[DolphinBench](../docs/changes/archive/feat-677-memory-evaluation/dolphinbench-methods.md) 关注 PA 将偏好用于行动，[FrontierMemory](../docs/changes/archive/feat-677-memory-evaluation/frontiermemory-methods.md) 关注历史经验对专家任务的帮助。它们仍是研究材料，尚未接入本仓执行。

公共可视化入口见 [ui/](ui/README.md)，复用已有 Memory 原生轨迹页面；各 suite 的执行和评分协议保持独立。

每个 suite 负责维护共享的 case、schema、materializer、validator 与稳定收据；具体待比较方案的协议和 seal 放在 suite 的 `experiments/<experiment-id>/` 下。候选仓由 materializer 生成，不提交物化输出，也不得把 `evals/` 控制资产暴露给候选 Agent。

本仓公开 Git 历史中的 case 适合开放回归和方法迭代。需要证明完全未知需求泛化能力的 clean holdout，应在 treatment 冻结后放入独立的私有 escrow，再以新的 dataset version 纳入。

## 默认评测配置

除非 case 明确要测试特殊配置，评测按被测产品角色的新建默认值启用工具、Feature 和 Skill。复用产品的能力清单、固定工具、Feature 依赖和 Skill 发现规则。A/B 记录实际生效的配置，除实验变量外保持一致。特殊配置在运行前写明差异和原因，结果单独标记适用范围。

依赖项目知识的 case，应在对应项目的独立仓库快照中运行，保留源码、AGENTS.md 和项目技能。两个候选从相同版本开始，工作区彼此独立。运行前核验工作目录和实际加载的项目指令。评分答案、回放脚本和其他评测控制资产放在候选工作区之外。
