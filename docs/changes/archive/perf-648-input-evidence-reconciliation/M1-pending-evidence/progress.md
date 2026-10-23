# M1 实施与证据

采用 change-orchestrator-simple，主 Agent 实施；没有派发 implementation worker。

## 实现

- 产品提交 `95a8c00ea2835e1e8578b55725dabeec7281ef1d`，base `1ef49808ffd2618c275b6e38683f93f74ff8455d`。
- inputs 增加 final evidence 标记及 session/finality 索引，旧 DB 默认未确认；fresh lookup 与标记同 SQL 原子保存。
- SingleThread 只回查未固定证据 ID；pending、缺证据、running/switching 不收敛。
- recordEvents 保留全量事件，已固定逻辑 terminal 不被延迟物理 turn/end 改写。
- delivery/receipt 遍历、runtime、usage、安全审核均未改动。

## 测试策略与结果

长期风险 owner：既有 `model-fallback.test.ts` 保留 fallback 通知/正文/usage 断言并扩展 running→completed 后稳定零 lookup；`single-thread.test.ts`、`store.test.ts` keep。新增 `input-reconciliation.test.ts` 保护此前未覆盖的持久证据复用与 RPC 性能边界，从公开 recover、runtime RPC、relay 和持久 DB 观察，不调用私有 drain。

- Red：原实现下新增 3 个用例全部失败（历史 1000 次重复 lookup、重启再次 lookup、延迟事件场景再次 lookup）。初次缺少 workspace 构建产物的收集失败不作为 Red 证据，构建后重新取得行为失败。
- Green：4 个最窄文件 34 tests 通过；加上 snapshot 滞后 running/switching 两例后，完整 PA 24 files / 171 tests 通过。
- `pnpm build`、`pnpm typecheck`、Web build 通过。Node 为隔离命令显式指定的 24.22.1。构建后产品代码未变化，构建内容对应上述提交。
- 本地日志：`/tmp/perf-648-red.log`、`/tmp/perf-648-green.log`、`/tmp/perf-648-pa-tests.log`、`/tmp/perf-648-build.log`、`/tmp/perf-648-typecheck.log`。

## 性能证据

Claim：常态完成历史不再引发线性 lookup RPC，不宣称整个 drain 与历史无关。

Baseline：审计基线 236a4698，1000 已完成输入、零新事件，1000 lookup，1 ms 人为延迟时 1155 ms。

Method：原审计探针的真实 NodeStore/SingleThread，运行于本 unit tree；补入真实协议具备的 pending=false，并先通过公开 recover 补全可信证据，随后测量 steady-state recover。模拟 runtime/relay，无真实网络 RTT。样本非统计基准；升级首次补证据仍为 N 次 lookup。

Result：100/1000 历史输入、模拟 lookup 延迟 0/1 ms 的四个样本均 0 lookup / 0 relay。1000 输入两个样本为 121 ms / 36 ms；仍包含原全量交付遍历，不能用一次计时推导生产占比。长期测试另证明 1000 历史 + 3 待定时仅 3 lookup，取消未消费输入取得终态后不再回查。

Locator：`/tmp/perf-648-benchmark.jsonl`，临时探针来源为审计 root/lookup-probe.mts（不进入永久测试）。

Limit：仅 RPC 选择优化；不优化全历史事件/交付遍历，未运行生产负载计时，不部署生产。
