# Architecture Review Snapshots

架构审查报告描述某个 commit 和 working-tree 状态下发现的候选，不直接改变 current 架构。候选被选择后进入 change 流程；经过实现、验证和归并的结论由 `SPEC.md`、`docs/specs/`、代码和测试承担。

新报告由 `improve-codebase-architecture` 生成。文件名记录生成时间和代码基线，报告正文记录完整 Git 语境、候选与 dirty warning；Agent 需要历史候选时直接查看本目录。报告带 dirty warning 时，commit 只能复现已提交部分。没有被选择、没有后续解释价值的本机报告无需进入仓库历史。
