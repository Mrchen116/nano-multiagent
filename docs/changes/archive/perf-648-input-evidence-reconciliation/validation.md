# 最终交付验证

## 版本与门禁有效性

- Gate 2 实际执行：`executed_base = validated_at = 13d5a40b1ff5d9e8e9b0411add6600e1688210e1`，Approved；设计与需求正文之后未变化。
- 代码审查 / verifier / 产品验收 R1：`executed_base = 1ef49808ffd2618c275b6e38683f93f74ff8455d`，`validated_at = 2c4b06abcad6ab4af35d2fffdf0daeb6ba7788a1`，pass。
- 三道实施门禁 R2：`executed_base = b78b263abc8249617906117f8f19eeb1e825fab3`，`validated_at = 817f92040be5916e5abb42196948c1147009c399`，pass。产品重新运行新 runtime 组装、同聊天连续回复和同数据重启；保留 R1 已实际完成的 fallback/连接中断恢复。
- 最后同步 main `4bb02455b1d072a899a54bf62cdf2927c4069a99`，本 unit 产品 patch 无冲突重放到 `b2087ede226bb0076c1d20895aef02843afdb417`。该 main 增量为 perf-650 usage；本 unit 不修改 usage、runtime input evidence 或 model fallback。
- 静态 R3 实际执行：`executed_base = 4bb02455b1d072a899a54bf62cdf2927c4069a99`，`validated_at = b2087ede226bb0076c1d20895aef02843afdb417`，code review / verifier 均 pass；`effective_base` 为该 main，`effective_through` 为该产品树及其后仅文档归档的提交（最终完整 SHA 见 PR）。
- 产品 R1/R2 retained：SingleThread 通知仍仅按原 sessionId 路由，不消费新增 rootSessionId；lookup/observe、fallback、交付/receipt、Node 接线与输入证据写路径未改。usage 新增状态只在独立 usage 表和 reader 内，因此 R1 备用模型及断连恢复、R2 新栈连续回复和同数据重启的具体结论仍有效，不冒称又做了一轮真实产品测试。
- 原始执行版本不因 rebase 或归档改写；最终有效范围在 PR 中同时展示。归档只移动整套 unit 并追加验证记录，不改变产品源码。
- no spec delta：独立 verifier 已核对，内部缓存和 SQL 选择不新增对外行为，无 canonical spec 需要归并。

## 本地检查与共享证据

本机全量尝试期间 load 曾接近 700，swap 约 9 GB。保留所有失败，不修改测试 timeout、断言、模型或 CI 配置。以下分别列出实际通过、环境失败和有界复用，不把不同运行合成为一次全绿记录。

- Node 24.22.1 / pnpm 11.7.0；原实现新增 3 个行为用例 Red，新实现 Green；首次完整 PA 为 24 files / 171 tests 通过。详见 M1 progress。
- 同步 b78 main 后 `pnpm install --frozen-lockfile`、`pnpm build`、`pnpm typecheck` 均通过，构建 metadata 对应 `817f92040...`。`pnpm check:ios-runtime`、Python 65 passed / 31 deselected、ruff check/format、docs-check、前端 critical audit 均通过。
- 后端全量单机 bounded 尝试：123 files 中 120 passed / 3 failed；601 tests 中 596 passed / 5 failed。失败为 cron、model-policy、conversation-tasks 的超时/轮询窗口。日志 `/tmp/perf-648-all-tests-bounded.log`。
- 在 `bbf343d565ed361986bf1136baf76f39ff0e7c24`，单 worker 复跑 30 files：26 passed / 4 failed，189 passed / 8 failed。完整 PA 171 tests、descendants、conversation-tasks 通过；model-policy、cron、native model-fallback、tool-presentation 仍触发超时或轮询窗口。日志 `/tmp/perf-648-final-retry.log`。此前中止的 default 并发和 targeted 尝试不作为通过证据。
- 前端完整单 worker：103 files 中 102 passed / 1 failed，963 tests 中 962 passed / 1 timeout；原文件 `permission-card-delayed.test.tsx` 单独原样复跑 2/2 passed。日志 `/tmp/perf-648-frontend-tests-bounded.log`、`/tmp/perf-648-frontend-retry.log`。前端目录 tree 在 R1/R2/最终同步均保持 `0432845539bbcf3bc413b54e081c5f866c033271`；新增 UsageReadResult 类型不改变前端或生成器。
- main b78 的 [CI 39979649421](https://github.com/Mrchen116/nano-multiagent/actions/runs/39979649421) 已完成 success；直接读取 job 日志确认上述 native runtime/IM 文件全部通过。其源码、依赖、测试配置与 bbf tree 相同，且这些测试不依赖本项 PA 修改，因此仅保留这部分未改动链的通过证据，不称为本项 PR 的完整验证。最终 PR 完整 CI 仍独立执行，交付以其全绿为准。

- 最终同步 tree `b2087ede...` 的串行 workspace build 和 typecheck 通过；`pnpm exec vitest run packages/personal-assistant/tests packages/dsh-integration/tests/usage.test.ts --maxWorkers=1` 为 25 files / 183 tests 全通过，覆盖共享 store 新索引、usage page 与输入证据并存。日志 `/tmp/perf-648-usage-sync-build.log`、`/tmp/perf-648-usage-sync-tests.log`、`/tmp/perf-648-usage-sync-typecheck.log`。
- 完整归档后 docs-check 通过（290 maintained sources / 67 routes），`check_change_unit_archived.py --head-ref unit/perf-648` 通过。当前 main 4bb 的 [CI 39982902517](https://github.com/Mrchen116/nano-multiagent/actions/runs/39982902517) backend 与 frontend jobs 已通过，确认 usage 增量下未修改链的运行证据；不替代本 PR CI。

## 清理与范围

本任务隔离 IM/Node/DSH 已停止，未操作其他任务或生产进程。临时配置、数据库和日志不提交。只交付 perf-648 的源码、回归和归档文档；不 merge、不部署、不把模拟 RPC 计时推广为生产性能占比。稳定 1000 历史输入为 0 lookup，新增 3 个待定输入仅 3 lookup；整个 drain 仍有历史事件与交付遍历。
