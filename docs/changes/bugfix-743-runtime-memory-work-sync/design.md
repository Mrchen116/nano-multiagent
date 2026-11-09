# bugfix-743：历史按需读取，Work 按持久位置补传

## 决策

### 历史正文归原有磁盘记录

- Nano profile 停挂官方 `session_projcache`，保留原文件和原生 Session 日志。这个域是可重建的 fold 快捷方式，不是审计所有者；公开 query 在无服务时使用官方 projection registry 从精确原生日志 hydrate。Nano 现有 Work/轨迹通过 sessionQuery 和 trusted binding 读取；校验标题/子关系仍能从日志派生。原生 Session 恢复、审核入模与证据文本无变化。已有缓存不在启动时迁移或删除。普通 profile 的永久删除以显式 profile 配置启用，继续按已经证明的范围删除旧 projection 文件及备份；不装缓存也没有新缓存写者可与删除竞争。
- 工具 presenter 的冻结输出不能从今天的定义重建。保留现有 `storages/nano_tool_views/calls/<key>.json` 格式，以已声明的 `JsonStorageBackend` 写原有 per-record 单元；只读当前事件的键，文件路径/格式在一个 Nano adapter 内。保留原写入顺序、失败重试与关机屏障。永久删除等目标写入结束后按会话扫键并删除，不为枚举加载正文。不改上游包或使用私有 import。不进行需要授权的一次性迁移；回退时旧读取者能读相同记录。

### 观察与确认分开

- 私有 stdio 的 Work 读以消费方已处理的 native seq 取 own 事件。主会话读按页；子会话先维持现有目录/可信根与持久见证，回复对**所有**子会话共享字节/事件预算，仅把已发的区间标为 throughSeq，未读完显式 more；未提供游标才从 own 起点开始。先按游标选取，再逐条附工具展示并计入预算。标准页预算 1 MiB / 256 事件；单条可独占一页以保留完整记录，超过 32 MiB 明确失败、从同一位置重试或走原生轨迹检查。原生轨迹协议不变。原生冷观察的公开接口仍可能读取单份日志，保持官方恢复与有界缓存；不在 Nano 再留全量副本。
- Work 传输缩小不消费的大请求快照：request/header 只保留 model 和 request/context 只保留 model/contextWindow，保持原 seq。原生存储与轨迹正文不改。实时 `session.event` 只发所需的变化/事件识别和来源元数据；持久读取是权威，必要的实时流和审批协议保持。
- Node 已有根事件 ledger 保存收到的页，从 Work checkpoint 保留的逻辑轮起点投影。子执行将未完成逻辑轮的事件保存在 Inbox SQLite，与子 Work facts/checkpoint 一起提交；页到达后用本地前缀完成工具配对、用量及模型回退轮合并，投影后删除已结束轮次的处理上下文。旧 checkpoint 没有本地上下文时仅补一次未完成轮前缀。模型元数据更新时使用本地重投影，不重新发送已处理正文；保留现有稳定 event ID 和不可靠观察的 pending 状态。多页先应用再拉下一页，重启从事务已提交位置开始。中心同步 ACK 独立。取消或连接关闭不推进未消费页；目标停用的末尾事实继续走同一投影规则，使用有界读取。
- RPC 在 stdout 写入返回 false 后等待 drain，等可写再序列化；输出队列有限，历史页限并发生成，避免大量已生成的页等待可写。传输故障显式断开并拒绝未决请求，现有 supervisor 重连后从持久位置恢复；保留双向独立 dispatch，不能用读暂停或全局串行 handler 造成反向调用死锁。

## 本次审查安排

- 实现与契约：审真实 profile/Node 组装、两条游标持久化、停用/关闭、删除和读取范围。验证 inherited cut、冷中断合成结束、失败不推进、跨页工具与 fallback 逻辑轮。
- 性能：相同隔离历史与追加量，记录启动读取/heap 和 Work 返回字节；阻塞可写端，观察 writableLength、帧序和恢复。明确单条与总页界限。
- 用户旅程：以隔离的真实 Node→DSH→Work 写入路径，已有主子内容可读，新工具跨页、断开恢复后正文和关联仍完整；既有权限负例复用/补测。无页面或交互设计变更。若冷标题/子会话展示被模型工具消费，同时核对官方 hydrate 和实际工具结果。
- 风险与回退：无缓存的冷查首次 fold 成本增加，由官方有界冷观察及既有 Work durable catalog 避免不变历史反复重建。回退可恢复旧 profile，原始日志和工具冻结记录仍原位。Node 的额外子工作上下文是派生记录，不影响旧版本读取原日志。

| Milestone | 依赖 / 并行组 | 范围 | 退出标准 |
|---|---|---|---|
| M1-runtime-work | 无 / 单组 | DSH integration、Node、PA 的历史读与 Work 消费；受影响测试 | [reviewer] 长历史、断线、重启、停用下 Work 可恢复且完整，隔离权限仍有效。 [worker] 旧数据留存、定点读写删除、只读所需 seq、字节预算与慢消费者实测；跨页投影与最终游标对账。 |
