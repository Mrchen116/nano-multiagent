# Code review

## 范围

第一轮完整 diff，包含 IM/PA/DSH/前端实现、测试和本 unit 文档。检查起点 `39a1d78ed25b4c19878dc98b63d96d4810cb2523`；实施中另一个已合入的 Inbox 修复保留在最新 main 中，不作为本轮实现。

## 独立 full review

Reviewer：独立 `gpt-6.1-sol/high`，未参与实现。固定范围 `114318397..0ac5fa040d80581b72e274bcb038ac55ceaf27d0`，工作区干净。执行 change-code-review full 和 Agent Context Implementation Review，最终 findings：`[]`。

核对 Task current binding/alias、外部查询 Agent 作用域及顺序、fallback live/history 恢复、Memory first-call/group/budget/parent snapshot，并沿 Dreaming renderInput/extract 核对模型消费。独立运行 model-fallback、memory-sources、memory-child-runtime、PA task-execution/external 共 5 文件 39 测试通过。Context 运行时证据采用 DSH llm/stream fixture，不是线上模型。

## 验证状态

- build、typecheck、check:ios-runtime、docs-check、ruff check/format 通过。
- 前端全量：109 文件 1,039 测试通过；Python：129 passed、28 deselected；前端 critical audit exit 0。
- 第一次默认并发后端全量：8 文件失败、193 文件通过；9 测试失败、1,081 通过，280.63 秒。失败为能力检查截止、测试超时、自动续跑 poll 时限，以及 5 秒评测准备期内模型调用尚未发生。原始日志完整保留于证据目录，不用定向结果覆盖。
- 同一代码、相同超时阈值，仅改运行参数 `--maxWorkers=2` 重跑全套：201 文件、1,090 测试全部通过，416.22 秒。此对照支持本机并发负载影响；未宣称消除了所有环境下的测试抖动，也未改产品截止语义。
- 额外定向及旧/新等价证据见 design.md；所有本地门禁完成，允许本轮归档。远端 PR CI 通过后方可合入。
