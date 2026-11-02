# perf-686 实现记录

本记录在实现后整理。基线为 `7e79e9b79`，实现提交为 `34f55c173`。

## 投递与资格检查

`RelayDelivery.drain` 仍按节点读取至多 256 条 relay，先排除在途和退避中的任务，然后为每个剩余候选保存原行、解码后的 payload 和字符串 Agent ID。解码对象的生命周期限于本次节点 drain。每移除一行，按剩余行中各 Agent 首次出现的位置重新计算轮转次序。交错队列中这个顺序会变化，所以保留原选择算法。

每次即将发送时，`Messaging.relayEligible` 用该 payload 查询当时的节点归属、epoch、生命周期、上下文及会话权限。直接以持久行调用此方法时仍从该行解码。失去资格的任务标记为 cancelled 并继续选取；发送失败立即停止本轮。成功写入才更新在途窗口、Agent 游标及 sent 状态。回执、重连及超时处理沿用原路径。

这项改动减少了解码次数。剩余候选的 Agent ID 仍按发送名额重复扫描，同时在内存中保留至多一页解码对象。没有跨 drain 缓存、数据库迁移、协议或模型可见内容变化。回退实现提交即可恢复基线算法。无 canonical spec delta。

## 前后对照

在内存 SQLite 中准备 256 个唯一 payload，单节点、单 Agent、32 个空位。调用真实 `RelayDelivery.drain`，在 gateway.send 边界采集完整 payload。仅在 drain 期间计数，只计参数等于这些持久化 payload 的 JSON.parse 调用。两版均逐项深比较帧内容和顺序（ID 000 至 031）。

| 资格检查 | 基线解析次数 | 实现后解析次数 | 两版发出的帧 |
|---|---:|---:|---|
| 固定为允许，用于复现调度开销 | 7,760 | 256 | 相同的 32 条 |
| 真实 Messaging 和 SQLite 资格检查 | 7,792 | 256 | 相同的 32 条 |

基线在 32 次选择中对整批剩余候选解码 7,696 次；此样本另有 32 次查找、32 次发帧解码，真实资格检查再增加 32 次。数据仅衡量该场景的解析次数，没有测量生产延迟或吞吐量。

[一次性计数探针](evidence/drain-probe.ts) 可复制到任一对照版本的 `apps/im-server/tests/relay-parse-probe.test.ts`，在已安装依赖并构建 product-contracts 的 worktree 根目录运行 `pnpm exec vitest run apps/im-server/tests/relay-parse-probe.test.ts`。基线在消息对照通过后触发解析上限断言。

## 行为证据

- `apps/im-server/tests/relay-delivery.test.ts` 在前后两个版本都通过。使用交错的三个 Agent 和真实资格检查，覆盖剩余候选次序变化、窗口填满，以及第一次向 C 发帧后从群中移除 C，后续 C 的行被取消。
- `apps/im-server/tests/e2e/relay-recovery.test.ts` 通过隔离 IM 进程和本地 WebSocket 验证回执腾出窗口、迟到回执和重连恢复。`apps/im-server/tests/task-context-revocations.test.ts` 验证撤销和生命周期边界。
- 用户授权以正常体验不变为交付条件。以上为开发者测试，未进行生产试投或用户亲测。
- 一次性时钟验证在单条未确认 relay 上先令发送返回 false，检查持久行仍为 queued，再让发送成功。时钟依次取 100、10099、10100、11099、11100、21100、23099、23100 毫秒，捕获到的成功发送时刻仅为 100、11100、23100 毫秒，覆盖首次和再次超时的退避。
