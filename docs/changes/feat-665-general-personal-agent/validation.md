# Validation ledger

独立审查与真实验收持续追加，当前还不是全量完成声明。每种证据保持自己的适用范围，不合并为一个“全通过”。

- [M1 memory worker evidence](M1-memory/evidence.md)
- [M2 proactivity worker evidence](M2-proactive/evidence.md)
- [M3 execution/delivery worker evidence](M3-delivery/evidence.md)
- [Independent product acceptance](acceptance.md)
- [Independent code review](code-review.md) / [verification](verification.md)

## Local CI snapshot

`bd1cb8cf0`，支持的Node24.22.1：完整`pnpm build`、`pnpm typecheck`、`pnpm check:ios-runtime`通过，日志`/tmp/pa665-final-{build,typecheck,ios-runtime}.log`。完整native/IM suite 149 files /794 tests：792通过，knowledge-policy与task-execution-limits两个等待超时；同两文件低并发独立重跑6/6通过（`/tmp/pa665-final-test-recheck.log`），没有隐藏首次失败。

Python辅助/架构70 passed/43 deselected，ruff check/format通过，docs283通过（`/tmp/pa665-final-{pytest,ruff,ruff-format,docs}.log`）。Web108 files/1031 tests通过（`/tmp/pa665-frontend-tests.log`）；`npm audit --audit-level=critical`通过，仍有非critical既有依赖报告，没有顺带升级依赖。

后续forget/child-delivery改动使用对应native与实际层回归，并对三个受影响包重新build通过（`/tmp/pa665-child-return-build2.log`）。同一代码不因review交接机械重跑全量；最终归并后仍须docs/类型与远端required CI完成，届时补明确head。
