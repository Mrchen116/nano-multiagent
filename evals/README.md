# Evaluation suites

`evals/` 保存需要长期复用、可独立物化并进入版本管理的 Agent 评测资产。这里的内容不是产品测试，也不属于某个 change unit 的过程文档。

| Suite | 用途 | 入口 |
|---|---|---|
| Spec/design alignment | 比较需求对齐工作流的用户对齐负担与最终产物质量；当前包含 8 个历史回归和前瞻 pilot case | [spec_design_alignment/](spec_design_alignment/README.md) |

每个 suite 负责维护共享的 case、schema、materializer、validator 与稳定收据；具体待比较方案的协议和 seal 放在 suite 的 `experiments/<experiment-id>/` 下。候选仓由 materializer 生成，不提交物化输出，也不得把 `evals/` 控制资产暴露给候选 Agent。

本仓公开 Git 历史中的 case 适合开放回归和方法迭代。需要证明完全未知需求泛化能力的 clean holdout，应在 treatment 冻结后放入独立的私有 escrow，再以新的 dataset version 纳入。
