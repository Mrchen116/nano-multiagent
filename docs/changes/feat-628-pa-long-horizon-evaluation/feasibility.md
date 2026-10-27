# 当前 DSH 时间控制可行性探针

日期：2026-10-21。目的仅验证当前锁定依赖能否受隔离测试环境时间控制，不是产品实现、PA 质量评测或完整链路验收。

## 方法

- 从当前 checkout 的 `packages/dsh-integration/lib/client.js` 使用已有 `prepareProfile` / `RuntimeClient`，启动官方 DSH CLI 和真实 stdio RPC。
- DSH 与 schedule 均为当前 `0.2.1-alpha.1`。单独在仓库外安装 `@sinonjs/fake-timers@15.0.0`，通过 child env `NODE_OPTIONS=--import <preload>` 在加载应用前替换 Date、setTimeout/clearTimeout、setInterval/clearInterval。没有 DSH private import、包修改或产品源码修改。
- 初始时间 2026-10-01 00:00 UTC，启动阶段随现实短暂推进，初始化后暂停为手动 tick。控制 Unix socket 在临时控制根，不放在 DSH_HOME 内；此前放在 home 内曾触发 HMR watch socket 错误，移出后正常。
- 用已有 `schedule.command create` 创建每 86400 秒任务与 604800 秒一次性任务，每次 `tickAsync(86400000)` 后通过公开 history 查询等待真实持久化收据。第 3 天关闭并以相同 home/session 及当前模拟 epoch 重启。
- 前六天断言 once 无记录，每天断言 daily 累计数为当日天数，第七天断言 once 仅 1 次；公开 `schedule.evidence` 检查所有触发为 timed。最后关闭进程。

## 观察结果

| 观察 | 实际结果 |
|---|---|
| 现实耗时 | 2.505131208 秒（包括初始化和第 3 天重启） |
| 模拟跨度 | 7 天；启动与重启各额外推进约 100ms，记录于原始 receipt |
| 每日任务 | 7 条不同日期的原生 timed admission 与持久 history |
| 七天 once | 第七天 1 条，前六天 0 条 |
| 保状态重启 | 第 3 天历史保留 3 条，随后继续达到 7 条 |
| 调度来源 | 8 条证据全部 trigger=timed，不是 schedule_run |
| 模型/业务结果 | 未提供模型凭据；存在 MISSING_CREDENTIAL、重启时 aborted 及末尾 pending。不能认定模型执行成功或送达。 |

临时探针的日结果字段 `latest` 误用了 history 的最后一项（API 返回新到旧），因此该字段显示最早记录；逐日计数、once 断言以及带 scheduledAt 的全量 evidence 是本结论依据，未根据 `latest` 推断日期。

## 本地证据与复现

临时文件位于 `/tmp/nano-eval-clock-ym7mc6/`，不承诺临时目录永久保留，不提交运行数据库/日志：

| 文件 | SHA-256 |
|---|---|
| `preload.mjs` | `8b54333f005673107b8714f287fbacc913d7652a19fc9de34f41552654055327` |
| `probe.mjs` | `8cfa74f1089b39b81693514bab27fe27580d9176fe88cddf2910634597d2c663` |
| `receipt.json` | `2bf19a2f3aeccc6d921efac638624b112507e69898243ee56f675324139dc5d3` |

本机可用 `node /tmp/nano-eval-clock-ym7mc6/probe.mjs` 重跑；会新建自己的临时 home，不触碰生产。迁移复现按上面的方法使用锁定依赖与该 fake-timers 版本，后续正式校准由 M1 提供可持续运行的 fixture。

这不是最终多进程 preload 的实现：它没有同步 IM/Node，没有 admission/drain 屏障，没有真实 provider，也没有证明认证/网络/知识维护时间一致。正式设计必须另外验证这些面。单进程 tickAsync 的成功仅消除了“必须等待上游 Clock API 才能控制 native schedule”的假设。

## 技术参考

- [Sinon fake-timers 官方说明](https://github.com/sinonjs/fake-timers)：支持 Date 与 timer 安装、异步 tick；setSystemTime 不是经过时间，jump 不是连续在线回放。
- 本地 DSH 参考仓库 `/Users/czj/Repos/opensource-hub/deepseek-harness/packages/schedule/schedule/tests/runtime.spec.ts` 使用 Vitest fake timers。该源码仅作为方法参考，本次运行使用 Nano 当前安装的 alpha.1，未使用参考仓库内部 ScheduleRuntime。
