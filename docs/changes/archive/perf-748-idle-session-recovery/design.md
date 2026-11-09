# 节点按可恢复义务激活会话

## 方案

- NodeStore 用已有输入、交付和 receipt 状态选出真实恢复候选。包括未提交或证据未终结输入、未终结交付，以及已有终态交付却没有对应终态 relay receipt。待命令按 Agent 走现有 SessionControls 恢复；同进程已知的待审批继续由原等待者处理，冷进程不重造审批等待，由已有中断／到期状态结算。
- 原生 Schedule 可先持久写入 Inbox 才记交付回执。为避免漏恢复或每次冷启读全量，新增按 root Session 的本地恢复覆盖标记。DSH 的公开 SessionController 和产品入口共用 OwnedSessions，未激活 root 在取得可写 Agent 前，通过 Node 回调持久标记当前 activation generation 为待核对；回调失败不得激活。原生 Schedule、Task 及后续同一可写 Agent 上的生产者继承这次标记。标记不记录消息正文。新启动时，对有旧标记、首次迁移未知的 binding，以及本地真实义务作有界检查；已确认空闲且未再次打开的 binding 不读原生日志。任何没有标记的 binding 都是未知，包含原生 fork 先创建可写会话、Node 后绑定的新会话；只要仍在本进程可写便不能标为已核对。
- 未知或旧 activation generation 使用公开 `SessionPersistence.open(id, 'read')`，校验 header、读取 Node durable cursor 后第一条 own event，并马上关闭 handle。有新事实走原有 ensure/reconcile，已读取的事件不创建第二份交付。空尾且无本地义务、或明确无 Session 文件，可以用 generation 比较更新为已核对；期间的新 activation 先换代，旧检查不能覆盖它。失败或身份不符保持未知并报告。锁定 JSONL 的首次读取会解析日志，因此只做一次冷核对并限制并发，不用分页循环。热重连已打开的 root 可用公开 SessionQuery 的 live cursor，未变化时无需物化事件或投影。仅证明旧 generation 已不再可写且 Node cut 完成对账才可清除；活的可写 generation 不提前清除。
- 在 Node 的 partition onReady、Relay ready 和 update release 保留现有启动、通道范围与持久恢复契约，三处复用 per-session 恢复所有者，同一 generation 不重复 ensure。先恢复原生已初始化的 stop fence，再按当前生命周期与通道范围裁决本地及原生候选；正式 ready 等当前启动范围的必要持久恢复完成，必需错误不得经 log-only 汇总后继续写 ready。节点主动更新的 prepare 阶段当前有独立的全量 drain，在本次重启／重连路径以外，仍会预先激活所有会话；它触发的 dirty generations 计入更新后首次冷启，单独观察。迁移未知批次低并发运行，已经持久接收的新输入继续走现有优先按需 ensure。绑定停用、通道失权、更新持有或会话 generation 变化时重新裁决，不从旧探针结论直接启动。历史访问仍按需，现有启动和恢复用户契约无 canonical delta。

## 验证安排

独立代码审查与恢复旅程验证。构造千个 idle 绑定和少量在途输入、失去 ACK 的交付、审批和原生触发，分别记录 reconnect、cold restart 到接新请求、ensure 数、读入字节和堆。核对历史按需访问、重试、权威证明缺失、外部范围和停用。强杀原生 Schedule 在 Inbox flush 与回执落盘之间，验证 Task 原生触发以及缺终态 receipt。分别量首次迁移、有覆盖证明的重复冷启、同进程 Relay 重连，包含核对结束时总读量。

| Milestone | 依赖 | 文件范围 | 退出标准 |
|---|---|---|---|
| M1-recovery | 无 | Node 恢复入口、PA 状态查询和 DSH 冷观测测试 | [reviewer] 节点能接新输入，历史可读、真实恢复义务无遗漏。[worker] 空闲绑定不批量 activate，证明缺失和重试失败边界有实证。 |
