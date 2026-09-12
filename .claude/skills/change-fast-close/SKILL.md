---
name: change-fast-close
description: "用户明确选择快速开发或事后补 unit，已有实现且已亲自验收，需要补齐文档、code review 和交付时使用。"
---

# Change Fast Close

为已实现、已获用户实际验收的快速开发结果补齐可追溯 unit。已有 active unit 则沿用，不另起生命周期；没有用户确认时保留 active 状态，不伪造验收。

## 约束与产物

- 只处理本次 diff/commits，保留其他修改；从用户原话与决定写需求，从代码和证据写实际实现，二者不能倒置。
- 新建时使用 [编号脚本](../change-spec-author/scripts/next_unit_id.py)；按类型选择 [首文档模板](../change-spec-author/assets/TEMPLATES_README.md)、[as-built design](assets/design.md) 和 [code review](assets/code-review.md)。
- design 明示事后形成，记录真实模块、调用链、已采用决定、兼容/失败/回滚边界和验证定位。没有发生的 milestone、tasks/progress、design review、verifier、产品 reviewer 报告不补造。
- 对外行为变化按 [CONTRIBUTING](../../../docs/specs/CONTRIBUTING.md) 写最窄 delta；纯内部改动说明无 spec delta。无关漂移单列，不顺手决定预期。

## 完成

主会话调用 change-code-review，对完整本次 diff 做独立 review；将 base/head、dirty 范围、findings 与 resolutions 记入 code-review.md。修复成立的阻塞项，运行适当验证，按实际 delta 做 patch/closure。改变用户可观察结果时重新取得受影响旅程的用户确认。

用户验收、首文档/as-built design、code review、适用测试/本地 CI 和 canonical 归并均完成后，按 [change-workflow](../../../docs/development/change-workflow.md) 完整归档。提交、push、PR 做到当前授权范围；阻塞时留下事实、未完成项与恢复入口。
