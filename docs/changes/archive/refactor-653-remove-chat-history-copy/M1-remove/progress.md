# M1 实施与验证

## 版本与范围

- 基线：c097a63219d5d303526c2ede583df39b6f81ff9d；2026-10-25 fetch 核实为 origin/main，主仓已 clean fast-forward 同步。
- 删除 turn/end、fork 和 initialize 恢复触发；删除可读投影、增量游标、stat/append/rebuild 和无用 raw 标志。显式原始导出保留串行合并、持久化切面与原子 rename；完成的队列项释放。
- 当前契约将在独立校验后按 delta 归并。内置说明两处与 operations 历史迁移验收同步清理；历史 archive、历史评测与无关 IM 聊天查询保持原义。

## 测试策略与证据

- `history-export.test.ts` rewrite-merge：删除已经退役的增量 append/rebuild 保护；保留原始导出切面、并发、失败保留旧快照、冷转live屏障；增加普通聊天零副本写入与显式导出不碰旧文件。
- `history.test.ts` rewrite-merge：真实 DSH subprocess 的 RPC fork/compact/observe/export/restart 链继续保护，移除旧正文投影断言，改为副本不创建、重启与继续源会话不改旧文件；原始快照显式断言继承前缀与分支隔离。
- `native-human-source.test.ts` delete 退役副本断言；保留原生真人来源、权限和工具结果验证；PA history test keep（提炼消费者）。
- 红测：`pnpm exec vitest run packages/dsh-integration/tests/history-export.test.ts -t 'does not generate'` 在旧实现失败：期望0，实际82字节，证明自动写入；日志 `/tmp/refactor-653-red.log`（本机临时证据，不提交）。
- 修改后导出低层7/7通过；`pnpm build` 及 history/native-human-source/PA history 三文件6/6通过（日志 `/tmp/refactor-653-export-test.log`、`/tmp/refactor-653-native-test.log`）。最终队列释放简化后低层再次7/7通过，完整构建及本地 CI 后续统一执行。
- 无生产服务；fixture 临时目录和子进程由 finally 清理。未新增永久测试文件或调整超时。

## 独立门禁与 canonical 归并

- 受审实现 head `72b2ddb001792f1862764b51ba0d68f5179c61c0`；base `c097a63219d5d303526c2ede583df39b6f81ff9d`。代码审查 findings=[]；verifier Pass（0 CRITICAL/WARNING/SUGGESTION），corrected-delta aligned；产品真实 RPC 验收 pass（0 issues）。详见 unit 对应报告。
- 产品验收在最终受审版本重新 `pnpm build` 通过；完整 CI 复用该构建，继续 typecheck/后端/Python/Web 等检查。
- 按已校正 delta 机械替换两项 requirement、删除一项；入口摘要改为按需原始历史导出，计数23→22。历史 change archive 和评测题库不改写。报告后无源码/测试变化，canonical 归并不使实现验收失效。

## 最终同步与全量检查

- 最终 fetch：origin/main 仍为 `c097a63219d5d303526c2ede583df39b6f81ff9d`；无需merge，无新共享边界变化。
- 最终受审源码 `72b2ddb001792f1862764b51ba0d68f5179c61c0` 未再改动；后续 `60ac943f9` 只有报告与canonical归并。Gate2、code review、verification、acceptance 均 retained，effective_base 为上述 base；effective_through 为本归档提交（PR body 写确切SHA）。
- `pnpm build`（独立产品reviewer）通过；`pnpm typecheck`、`pnpm check:ios-runtime` 通过。
- `pnpm test --maxWorkers=2`：132 files / 703 tests 全通过，未重跑或放宽超时。
- `pytest -m "not e2e" -q`：65 passed / 31 deselected；ruff check、ruff format --check 通过。
- docs-check：273 maintained Markdown sources / 67 required routes，通过。归档后再次检查文档与 unit archive 状态。
- Web `npm ci`、共享contracts tsc、`npm audit --audit-level=critical`、`npm run test -- --maxWorkers=2` 均通过。具体前端数量见PR验证摘要。
- 全量本机日志 `/tmp/refactor-653-ci-*.log` 仅为本次临时验证证据，不进入仓库。无生产部署，既有磁盘副本未清理。
