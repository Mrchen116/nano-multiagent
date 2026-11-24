# IM 流式消息性能设计审查

## Round 1

- Reviewer 为独立 reviewer `design_review`，target 为 `0652178162da7bb227623f790ba08591db6effca` 的 `perf-784-im-stream`。
- review_mode 为 full。首次 Gate 2 核对需求、五项决定、契约、生产数据整理及唯一实施 milestone。
- started_at 为 2026-11-24T11:41:49+09:00，completed_at 为 2026-11-24T11:43:47+09:00，duration 为 118 秒（有时间记录的代码核对至出报告）。
- **Approved**，0 CRITICAL / 0 WARNING。

### Coverage 与证据

1. **现有代价与收益口径。** `server.ts` 实例化 Messaging 和 Gateway，`Gateway.handleFrame` 的 `node.streaming_delta` 经 `ChatStreaming.receive` 进入 `MessageRecords`。`Messaging.publishEvent` 先枚举读者，`conversationReaderIds` 为每个候选再次查会话和资格，`Gateway.broadcast` 对命中的每个 socket 再查会话、用户和空间，空浏览器也提前做权限查询。动机的 1124 和 39 是服务端每帧 get/all/run 调用数。1000 个计数 socket 不测网络或绘制；同样的真实文件 WAL、行数、正文和 key、预热、批次、99 个投递端与小群空载复测可判断同步处理收益。M1 可用各版本五组均值的中位数和 150 条上限验收，大群须同时满足两项，小群须减少开销。WAL 字节和终态键数量分别说明写放大与保留量。候选实测留在实施阶段。
2. **访问与路由归属。** `conversation-access.ts` 的成员、两个 Agent 的 owner、真人与 PA 私聊 owner 有不同来源，`identity.ts` 已集中定义空间与 Agent 可用性。批量取成员字段、复用 `directAgentOwners` 和现有资格函数足以还原读者。公开群访客可通过 `Gateway.replay` 或 HTTP 查询；实时正文的候选仍是成员和合格 owner。Gateway 拥有 ready、cursor、单个 session 有效性及背压，可以在一次同步发布内复用资格，成员移除通知仍走原收件人名单。普通新增事件、discard 后的 `publishCommitted`、`publishMessages` 延迟发布及 `agent-deletion.ts` 的已提交帧都在设计覆盖中；Work 仍有自己的二次空间校验。M1 的观察、撤权、刷新与重放验证有对应的 WS/HTTP 入口。
3. **持久化及消费者。** `MessageRecords.appendDelta` 当前分别执行幂等插入与正文更新，`event` 另插事件；一次事务可保证事件写失败后同 key 仍可成功重试，且失败时没有在线帧。历史摘要直接读取 `messages.content`，缺省 final_content 的完成帧也读取该字段，watchdog 查最新事件并在超时正文中保留原内容。Web 的 `chat-stream-reducer.ts` 消费增量，iOS 的 `ChatStore.swift` 依靠 cursor 和聊天查询刷新。即时持久化及原帧顺序保留这些入口。`schema.sql` 中 `personal_observation_event` 仅为四类事件插入 PA 来源，delta 可省去唤醒对象查询，其他事件仍需沿原策略。两个 lifecycle revision 要与同一帧的当前代次分别比较，PA 与会话授权照常执行。有界缓存的 owner 是各 SQLite 连接，只复用准备好的语句。
4. **幂等生命周期及部署。** `message_delta_idempotency` 主键首列为 message_id，删除消息有级联。终态改变由正常完成、禁用、watchdog 和外部快照等路径写回 messages，同一数据库 trigger 可覆盖这些写入；晚到 delta 先判断 running，避免重建 key。`deployment-prompt.md` 限定已具备 trigger 的部署版本和积存终态键的中心库，写入停止后制作并检查备份，仅删 completed/failed 关联键，通过剩余目标数、running 键数和消息/事件总数复核，数量为零可跳过或安全续做。失败恢复与正常启动有明确顺序，功能和失败注入安排在隔离库。历史键清理不影响旧版本读取消息或事件。
5. **体验、契约与实施范围。** 上游 `single-thread.ts` 已有 50ms / 4096 个 UTF-16 单元条件，设置页的列表、生命周期及模型状态有各自 query key 与刷新条件。两处保留现状。检查 auth-tenancy、conversations-messages 及 personal-agent 后，公开合同无变更，no spec delta 合理；例如仅局部复用准备语句且达到性能目标，也不会被产品契约误判。没有需要用户决定的视觉或交互变化，原型无必要。M1 将读者选择、持久化和授权改动放在同一组，各模块仍承担既有职责，无跨包依赖或并行文件冲突。设计阶段结论不代替实现后的行为回归、独立代码审查与性能数据。

### 历史闭环、Issues 与 Recommendations

首次审查，无历史问题。本轮无阻断问题或额外建议。

### Author Resolutions

接受 R1。随后由目录组件实测发现逐行生命周期读取，补充 M2，交原 reviewer 审查增量。

## Round 2

- Reviewer 为独立 reviewer `design_review`，target 为 `fdd66285990b6dbed7c8393f958800195e9bf523`。
- review_mode 为 full。新增用户可观察的目录状态要求、联系人响应字段和并行 milestone；重新核对两个目标、共享生命周期数据以及各自的范围和验收。
- started_at 为 2026-11-24T11:47:31+09:00，completed_at 为 2026-11-24T11:49:03+09:00，duration 为 92 秒。
- **Approved**，0 CRITICAL / 0 WARNING。

### Coverage 与证据

1. **现状与收益。** 实际列表和详情/创建侧栏都将每个联系人渲染为 `AgentLifecycleRow`，本人 PA 条目也经过这个组件。`useAgentLifecycle` 为每个不同 Agent 注册独立缓存键、3 秒轮询和用户流回调。故挂载 50 个不同联系人会产生 50 个独立 lifecycle 读取，目录自身另做分页读取。动机中的 50+1 来自模拟 HTTP 的真实组件首屏计数，周期性开销由现有定时设置支持。本轮没有测公网耗时或候选性能。
2. **后端及公开契约。** `messaging.ts` 两个 contacts 路由都先认证，再调用 `contacts.ts` 的分页/详情；共用 candidates 和 visible。联系人资格先收窄到合法账号、空间及可公开 PA，真人和 PA 有各自显式投影。只在允许返回的 Agent 行提供布尔值，保留原筛选、分页、普通用户字段及 PA 脱敏。`agent_lifecycle.agent_id` 是主键，关联不会复制行。SQLite 采样条件与 `agent-lifecycle.tsx` 的 confirmedDisabled 相同：desired 和 observed 都为 disabled，且 applied_revision 与 revision 相等。agents-nodes 的现行场景描述紧凑徽标及节点确认，ADDED 新增可独立消费的响应字段，未替换现行场景。例如实现者也可按一页 Agent 批量查一次生命周期再投影，仍符合该公开 delta，无 SQL 策略被写入契约。
3. **客户端与体验边界。** `listContacts` 跟随 cursor，`publicAgentsFromContacts` 负责把 Contact 映射为行；`AgentsListPage` 使用 public-agents 键，`AgentsRailDesktop` 使用 contacts/self/agents 键，恢复/变化刷新各自的实际键即可。`PersonalAgentEntry` 支持目录已有 PA 及仅有绑定两种输入，缺字段时继续现有独立查询，已有明确 false 时应直接显示正常行。详情 HTML 预读和 `AgentLifecycleAction`、聊天提示继续读取完整状态，其中管理操作使用当前 revision，请求数目标只针对目录行。M2 沿用已有徽标的文案、位置与操作，节点在线标记和停用状态独立，无新视觉取舍需要原型。这里核实的是设计和代码路径，候选界面尚未验收。
4. **双轨及部署。** 流式 M1 的组装路径、权限/事务不变量、SQL/耗时目标与隔离恢复约定复核结果与 Round 1 一致，部署提示词相对该轮无 diff。目录 M2 只读取已存在的生命周期投影，不新增数据迁移，不改变 M1 的代次权限，两个 milestone 无写入文件依赖。M1 的同负载文件库复测与 WS/HTTP 回归、M2 的真实联系人端点与 50 行客户端计数可分别证明各自收益。M2 验收覆盖 ordinary/PA 的徽标转换、事件与恢复、旧中心降级、详情/聊天沿用完整状态。前后使用相同目录规模与查询节奏计数，详情为当前 Agent 的独立 GET 应单列，以免误算进逐行请求。

### 历史问题、Issues 与 Recommendations

Round 1 无问题待关闭。Author Resolution 引入的目录需求及两项 milestone 已在上文核实。无 CRITICAL 或 WARNING。

- **R2-R1（可选）** 复用本地 50 行测量时，注意当前 `mockAgentsAndNodes` 按字段重组 contacts 响应，会丢弃样本传入的 `lifecycle_disabled`。候选同条件复测需由模拟 HTTP 响应实际返回字段；另留缺字段样本检查旧中心降级。记录首屏和下一个 3 秒刷新周期各自的 GET 数量，可以同时复核常驻收益。

### Author Resolutions

接受 R2。在候选目录测量中按新版联系人字段构造响应，单独验证旧中心兼容。
