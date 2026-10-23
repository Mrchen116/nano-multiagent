# 冷历史同步隔离实验

## 环境与范围

- 代码基线：`236a4698c7a8a2d03efa00c35049914d2422771d`；DSH `0.2.1-alpha.1`，默认 prepared Session cache = 5。
- Node `v24.22.1`，本机独立 RuntimeClient 子进程、专属 `/tmp/nano-647-benchmark/home`。每个阶段重新启动进程，确保实际冷历史恢复。没有访问生产 home、生产配置或会话；没有模型、审批、IM 网络调用。
- 用 DSH 公开 `SessionStore.prepare`、`sessionPersistence.create/append/flush` 生成 400 个子会话。每个继承 2003 个事件（2000 条随机合成用户消息和 3 个原生初始事件），各有 5 个自有事件。父目录由真实 `subagent/catalog` 事实构成。400 个子历史加根历史共 401 个 Zstd 文件、152.37 MiB（其中 400 个子会话为 151.97 MiB）。
- 基线执行与旧 handler 等价的 `subagents.listDescendants(root)`，再逐 child `sessionQuery.observeSession` 并取自有事件。统计公共 persistence handle 的 `read` 次数、`stat` 次数和 observation 次数。测试 instrumentation 只存在于隔离 fixture，不修改上游或产品。
- wall 是 `performance.now()` 差；CPU 是 `process.cpuUsage()` 差，含进程工作线程 CPU，因此可大于 wall。范围为原生后代读取核心，不包含 PA 投影、stdio 序列化、workflow/modelRun/toolViews 附加步骤。数字不能当作生产工具总耗时或 IM RTT。

## 修复前

| 阶段 | Wall ms | CPU ms | 冷日志 read | stat | observe | 返回自有事件 |
|---|---:|---:|---:|---:|---:|---:|
| 首次 | 18095.42 | 20437.02 | 800 | 800 | 801 | 2000 |
| 重复 1 | 20626.36 | 22771.28 | 800 | 800 | 801 | 2000 |
| 重复 2 | 31559.49 | 33365.38 | 800 | 800 | 801 | 2000 |

重复同步仍进行两轮完整冷读；800 次与 400 子会话 × 目录/事件两遍相符。绝对 wall 受机器负载影响，本实验主要以真实日志读取数量及同数据相对成本验证归因。

## 复现

从仓库根使用 Node 24，先构建。输出目录必须是本次独立新目录；脚本不会覆盖已有 seed/result。

```sh
pnpm build
node docs/changes/bugfix-647-trajectory-sync/M1-fix/evidence/cold-history-benchmark.mjs seed /tmp/nano-cold-history-check
node docs/changes/bugfix-647-trajectory-sync/M1-fix/evidence/cold-history-benchmark.mjs baseline /tmp/nano-cold-history-check
node docs/changes/bugfix-647-trajectory-sync/M1-fix/evidence/cold-history-benchmark.mjs fixed /tmp/nano-cold-history-check
node docs/changes/bugfix-647-trajectory-sync/M1-fix/evidence/cold-history-benchmark.mjs failure /tmp/nano-cold-history-check
```

`PROBE_CHILDREN`、`PROBE_PREFIX` 可缩小 smoke 数据。各模式结束均关闭自己启动的 RuntimeClient。生成日志/JSON/home 只保存在输出目录，不提交。

## 修复后（同一持久数据集）

被测 `DescendantReader` 源文件 blob：`4b8e826db45d71ca82e182f81d3503522c263c04`。基于 `236a4698` 的未提交实现；最终 commit 由交付记录补充。与基线一样重新启动 RuntimeClient，未修改 prepared cache 大小。

| 阶段 | Wall ms | CPU ms | 冷日志 handle read | stat | observe | 返回自有事件 |
|---|---:|---:|---:|---:|---:|---:|
| 首次 | 9628.07 | 10943.80 | 400 | 400 | 401 | 2000 |
| 无变化重复 1 | 103.70 | 116.72 | 0 | 400 | 1 | 0 |
| 无变化重复 2 | 101.05 | 110.81 | 0 | 400 | 1 | 0 |
| 无变化重复 3 | 97.95 | 109.49 | 0 | 400 | 1 | 0 |
| 一个冷 child 续写 | 139.63 | 208.72 | 1 | 401 | 2 | 6 |
| 新 child + 新 grandchild | 146.84 | 233.56 | 3 | 403 | 4 | 15 |
| 重建 Reader、保留确认游标 | 10322.34 | 11360.66 | 400 | 402 | 403 | 0 |
| 新消费者无游标完整恢复 | 9549.78 | 10528.34 | 402 | 804 | 403 | 2010 |

- 一次冷 child 续写后，该 child 的新内容可见，其余 399 个 sibling 均无重复事件。
- 新 child 和 grandchild 都可见；grandchild 的 `parentId=probe-child-0`、`depth=2` 正确。只有变化父分支和两个新增节点读取日志。
- 重建 Reader 时需重新恢复目录；已有确认游标不产生重复事件。此行仅重建 Reader，原生五条 prepared cache 仍在，所以 402 节点中实际读取 400 份日志。新消费者不带游标可完整恢复 402 个 child 的 2010 个自有事件。
- 由真实重启后的首次扫描可见：冷启动成本仍存在，但只读一轮，约 9.63 秒；不能声称启动后第一次历史恢复已经变为百毫秒。
- 无变化重复阶段只剩 400 次轻量版本检查；读取成本从 800 次完整冷日志读取降为零。稳定性结论基于 API 读取数量及内容完整性，绝对时间仅代表此合成数据与本机负载。


## 冷读失败与恢复

在上述 402 节点数据集新开 RuntimeClient，先完整建立 reader/catalog 与确认游标，再通过公开写 handle 给 `probe-child-0` 追加一条合成事件。测试仅对该节点下一次公开 `observeSession` 注入一次 `SESSION_QUERY_PERSISTENCE_FAILED`：

| 阶段 | Wall ms | 冷日志 handle read | 结果 |
|---|---:|---:|---|
| 失败读取 | 173.54 | 0 | 该分支返回 unavailable diagnostic，无 throughSeq，消费者确认游标保持原值 |
| 下一次重试 | 155.51 | 1 | 新增事件可见，402 个 child 及嵌套归属恢复，其他冷分支不重读 |

三个检查 `diagnostic`、`unchangedCursor`、`retryVisible` 均为 true。失败阶段该分支下的 grandchild 暂不遍历，重试后正常回到 402 节点；未把缺失分支当成成功同步。

## 现场与清理

四个阶段的 RuntimeClient 均正常 shutdown 并等待退出；没有启动监听端口，没有存活实验服务。合成数据、原始指标 JSON 与本机日志保存在 `/tmp/nano-647-benchmark/`，可用于复核；这些本机产物不提交。仓库中只保留合成数据生成/实验脚本与此脱敏指标报告。
