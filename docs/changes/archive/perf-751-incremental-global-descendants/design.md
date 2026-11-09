# perf-751 · 实施设计

## 当前路径与决定

`GlobalAgent` 的实时通知同时触发 root 和整树子执行 reconcile。子执行目录分页由 DSH 提供，Gateway 已有每个子执行的持久事件游标。保留该游标、原生事实和现有 Work journal，只调整候选发现。保留原生轨迹消费者现状，无外部契约 delta。

## 数据流

- DSH `DescendantReader` 从原生自有 `subagent/catalog` 事件建立子执行身份索引。冷载入时用同一份持久目录恢复索引；一次全量观察也回填。仅接受可信根、直接父和不可变身份。普通 root 事件只调度 root；子事件、model 变化和 catalog 创建事实调度具体 child。Catalog 创建用独立的按子 ID 合并提示。
- 点读在创建注册前确认 native 父目录事实的持久性。实时目录索引记录父序列，活父通过公开 flush 确认，父卸载时按该序列用公开 persistence read 验证事实。一次确认后可复用不可变边。冷索引从已有持久目录来。未登记祖先按由上到下顺序单独读，保持中心约束。事件增量单独用 live Session range + flush；冷体按需用 projectionMode none。热点非叶子不因自己的新事实物化或写回全量子目录。
- Workflow 创建上下文包含 run 与父 ID。DSH `agent/created` 在 native one-shot provider 创建子 Agent 期间被串行等待，早于 SubagentRuntime.start 在父 Session append 目录事实。该 hook 在匹配直接父时让 Workflow owner 把不可变 child ID→run 关系存入对应 durable Workflow record，通过同一 live record 和序列化 save queue 持久写成功后才返回允许原生 catalog 发布。Workflow 的模型侧共同 presentRun 入口过滤此内部字段，模型消息和能力维持现状。索引还从已有 attempts 恢复历史关系，点读不扫历史 runs。原生 catalog 通知再次标记 child，覆盖 catalog 创建前发出的子活动提示。已有版本遗留且完全没有 Workflow durable 关系的 native child 仍按其现有目录语义作为普通 child；已提交注册事件按现有 stable ID 去重，不能改中心身份。
- Gateway 每根保留 dirty child IDs、一次完整发现标志和 per-root 串行 drain。失败的已知 ID 留在本根，只重试失败项，正常 child 和其他根继续处理。DSH 尚未见可信 catalog 边的 child 活动提示不进入 pending 集合；原生 catalog 事实出现时独立重新标记，读取该 child 已持久的完整增量。若创建失败而未发布 catalog，不会留下永久待办；完整发现仅用于首次接手、重连、显式停机和显式未知枚举状态。所有 root/child/发现与待重试工作都结束才清除该根的 workPending；每个根独立退避，不通过全 Gateway recoverAll 重试点读错误。
- 全量发现由每根一个顺序迭代器续页；保存一个 lookahead 候选和上一响应。请求复用同一输入 cursor 时返上一响应，未知或前代 cursor 拒绝。生成页面时遇到遍历错误就废弃本代，Gateway 从该根首段开始重建；durable child 游标保证重试幂等。诊断 unavailable 使根保持未补齐，触发同根低频发现重试。新枚举替换旧代，停止使用已确认的 stop revision 枚举，不复用活动代。
- 点读和全量发现走同一 child 投影和 journal 提交。停止时等前一代正在运行的 drain，使用停止后已确认的只读根，再处理最终事实。非 Global 保持现状。

## 回退

不改变现有存储或导入数据，旧二进制继续使用既有完整发现。内存索引不是历史权威，不产生迁移脚本。

## Milestone

| ID | 依赖 | 并行组 | 范围 | 退出标准 |
| --- | --- | --- | --- | --- |
| M1-incremental-descendants | 无 | A | DSH Work 发现、PA 同步及测试 | [reviewer] 旧轨迹与运行中子执行完整可见，停止和恢复保持真实结果。[worker] 固定增量在 1 千和 1 万旧子执行目录下的访问量不随旧目录增长；完整恢复分页至多一次遍历，通过绑定、祖先、故障重试、并发和恢复回归。专门测高扇出非叶子、父 flush 失败、非首个目录页失败、已提交 child 注册冲突以及 Workflow 在 attempts 写入前退出的边界和模型工具响应不增加内部关系字段。 |

## 审查安排

独立代码审查覆盖真实组装、边界、事件丢失和并发恢复。性能审查使用真实目录消费者和合成树对比实际访问数，记录冷/热区别。产品旅程使用既有 DSH + Gateway 测试验证原有 Work、Workflow 与深层子执行。Work 读取仅用于产品记录，模型可见内容和前端交互保持现状。
