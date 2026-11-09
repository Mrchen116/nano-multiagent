# 模型前置只确认新 Task 证据

## 方案

- DSH 首次为 Session 建立 Task 消费状态时，通过公开 `ctx.sessionQuery.observeSession`、`projectionMode:'none'` 取得原生 cut 和开放轮。公开 `session/event` 订阅随后按 seq 推进开放轮边界并记录 Task `user/message` 的引用，启动期间与观察 cut 重叠的事件去重。热步不重新读取历史。发送新证据前要求 `ctx.sessions.flush` 明确返回成功；冷历史和热积压均按事件和字节预算分批送至 `product.task_context.commit`。
- Gateway 对每批按输入 ID 与 native seq 返回 `consumed` 或 `discarded`，其余仍待确认。消费证据必须匹配 session、输入 ID、原文摘要及轮次；两库写入中断后，仅 Inbox 的持久 `ingestions` 同一输入、会话和轮次可补记消费，不能以 `consumed=1` 推断。权威撤销或已退休的旧领取可用匹配的持久映射终态确认丢弃；若已存在匹配 ingestion，保留已消费事实和当前撤销状态。未知身份或摘要不匹配不确认。ACK 丢失重发同样证据，后到的已确认项可独立释放，未匹配项仍由该会话抑制重复原文注入。已确认输入由 Gateway 持久状态排除，无需在 DSH 长期保留已结算正文或重新遍历历史。消费 ACK 独立于本次模型授权，授权失败仍不交付未验证的 Task。
- 保留 Gateway 原文、权限和撤销校验。同一 Agent 只合并在同一 authority cut 发出前抵达的授权同步；cut 发出后的调用请求下一 cut。领取由 NodeStore 的 `agent/message` 唯一键裁决，prepared 映射不能因其他仍可执行的 session 到达而移交；每个调用独立检查作用域、领取与生命周期。单线程 `/new` 由既有 cancel、whenIdle 和 durable reconcile 确认旧会话停止，结清已持久证据后，在 NodeStore reset 事务中将旧会话标为不再有 Task 原文准入资格并释放仍未消费的领取；原 delivery binding 仍可查历史。旧会话后续准入返回无原文，晚到回执可对账。pre-step 对本轮 native 已领取的 Task 原文也按这次 authority cut 的当前 session 领取名单过滤，包括 `/stop` 被动放入 Inbox 的副本；有新领取后旧副本不能越过这道门。
- 证据对账和共享授权在 `system-prompt/assemble` 的既有入口完成，返回后按既有规则更新 Memory 来源可用性；`agent/pre-step` 仍从领取批次移除失权原文。冷读取、flush 或对账失败时不得推进确认，继续查询当前授权以获得受影响输入的引用，但暂扣这些 Task 原文。授权失败也只提示可辨认的 Task 及输入引用。两类失败都复用既有独立输入准入与 Memory 来源隔离，不以 ACK 替代当前授权。模型及审批继续收到相同的真实 Task 原文、来源、撤销和停止事实，无 canonical delta。

## 验证安排

结合性能、独立代码与 Agent Context 审查。真实 DSH fixture 验证旧历史、跨开放轮分页、同页匹配与未匹配、两次写之间失败、撤权、重启和 ACK 丢失。两个会话争用同一原文、旧会话重放、cut 后撤权均观察实际模型及审批输入。比较冷恢复、稳定热步和并行请求的 RPC 字节和调用次数。

| Milestone | 依赖 | 文件范围 | 退出标准 |
|---|---|---|---|
| M1-task-cut | 无 | DSH TaskContextDriver、Gateway TaskContext 及测试 | [reviewer] 原文和最新撤权在正确模型步出现。[worker] 历史不会在稳定热步重发，失败不丢失确认、重连重放幂等。 |
