# IM 流式消息性能设计

## 数据路径与取舍

1. 由 Gateway 在每次发布持久聊天事件时解析当前读者。先排除没有就绪接收端的情况。Conversation access 模块一次读取会话及带空间资格字段的成员，直接使用 canAccessSpace 判断真人成员，复用 canActorAccess 判断候选 Agent；私聊继续用现有 directAgentOwners 并验证每个非成员观察者的真人身份及空间。只在本次同步广播内复用读者 Set。每个 socket 独立核验 session、ready、cursor 和背压。显式定向广播（成员变更、Work 等）保留原有权限边界。覆盖所有持久聊天事件出口，包含 discard 后提交、删除清理和延迟发布。
2. 所有流式写入仍逐帧执行当前 Agent、PA、会话与生命周期授权。两次代次校验共用本帧的一份 lifecycle 行；缺省 revision 仍只允许第一代。one/all 按 DatabaseSync 隔离、按 SQL 文本有界缓存编译好的 statement，每次重新绑定和执行。只复用编译结果。
3. 单个 delta 的幂等插入、正文追加和事件插入在同一个事务提交，成功后才广播。PA 观察触发器只消费四类事件，delta 没有 PA 唤醒对象；保留其他事件的唤醒和提交语义。运行中的最新正文仍在 messages 中，支持历史、搜索、看门狗、完成帧缺省 final_content、Web/iOS 刷新。保留 50ms/4096 个 UTF-16 单元的上游批量策略。
4. 在写 key 之前识别非 running；数据库状态从 running 转为 completed/failed 时，用以 message_id 开头的主键清理该消息的 key，覆盖正常完成、禁用及 watchdog。消息删除已有级联。既有终态历史键按 [部署整理说明](deployment-prompt.md) 处理。仅清理无需再接收增量的消息。
5. 设置页轮询按路由、启用条件和 query key 生效。提高间隔会改变跨设备变化的可见时间，能力事件也不涵盖所有这些资源。保留刷新策略。

当前契约见 docs/specs/im/auth-tenancy.md、conversations-messages.md、personal-agent.md。较早的搜索优化 8af1a2b44 引入的公开群发现与私聊观察资格继续复用。no spec delta。消息格式、结果、新鲜度、历史保证及模型输入均沿用现有契约。

## Milestone

| ID | 依赖 / 并行组 | 文件范围 | 退出标准 |
|---|---|---|---|
| M1-stream | 无 / 单组 | apps/im-server 的 conversation-access、gateway、messaging、context、生命周期、流式记录、schema 和相关测试 | [reviewer] 观察者、授权撤销、重试、刷新、重放与终态保持现有行为。[worker] 同基线比较 SQL 次数、时间、WAL 字节和终态键；验证事件插入失败回滚、晚到帧和历史整理；复用服务端 WS/HTTP 测试。 |

设计审查复核权限和投影，实施后以 performance-review 同负载复测，独立 change-code-review 检查最终 diff 与不变量。
