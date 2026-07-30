# Architecture Review Snapshots

架构审查报告描述某个 commit 和 working-tree 状态下发现的候选，不直接改变 current 架构。候选被选择后
进入 change 流程；经过实现、验证和归并的结论由 `SPEC.md`、`docs/specs/`、代码和测试承担。

当前没有纳入 Git 的报告。新报告由 `improve-codebase-architecture` 生成；值得长期保留时，提交报告并在
本页登记：

| 报告 | 时间与基线 | working tree | 后续落点 | 状态 |
|---|---|---|---|---|

生成报告带 dirty warning 时，commit 只能复现已提交部分；索引必须继续保留这一限制。没有被选择、没有
后续解释价值的本机报告无需进入仓库历史。
