# bugfix-656: Code Review

## Review scope

- Base: `b80e6d74d72ed6f169142008a16c7c0811646754`。
- Head / validated_at: `40f3660a0303bd027833fbb0d5842ab2d270e23d`。
- executed_base: `b80e6d74d72ed6f169142008a16c7c0811646754`。
- Review mode: `full`。
- 范围：本次 task-execution 源码、limits 回归测试与本 unit 文档。

## Round 1 — Full

- 2026-10-25，由用户授权新开的独立线程 `01a1722d-28da-7711-8d29-f53a6a033ecd` 执行，标题 `Review bugfix-656 自动续推上限`。
- 审查全部 6 个文件，核对原生事件时序、输入调用方和既有屏障；复用已提供测试，独立运行内存事件探针及 diff 检查。审查 checkout 保持干净，HEAD 未变。
- Result: 1 个 CONFIRMED P2，未通过。

### F1 — personal-state 配置同步错误解除触顶停推

- Origin: `40f3660a0303bd027833fbb0d5842ab2d270e23d`，`packages/dsh-integration/src/task-execution.ts:14`。
- 触发链：PA `updatePolicy()` 写入 `policy.changed`；GlobalAgent 将其以 `personal-state` source 提交给主会话；`externalWake()` 未排除此内部配置同步，消费后将触顶计数从 256 清零，重新允许自动续推。
- 独立探针结果：`exhaustedCount=256, afterPersonalState=0`。
- Resolution: 实施者核对实际调用链后确认，排除 `personal-state`，在现有 native limits 回归的内部通知序列加入该通道，并更新 as-built 输入分类。
- 修复后验证：`pnpm --filter @nano/dsh-integration build` 通过；Task execution + limits 两文件 14/14 通过（51.66 秒）；docs-check 通过（272 maintained Markdown sources、67 required routes）；`git diff --check` 通过。环境仍为 Node 25.8.2 / pnpm 11.7.0，未扩充为全仓 CI 或产品验收。

## Closure

Pending。F1 已按上述方向修复，待独立 closure 核对固定修复提交。尚未取得用户实际产品验收，也未完成完整本地 CI 或 canonical 归并；unit 保留 active，不声明 Passed。
