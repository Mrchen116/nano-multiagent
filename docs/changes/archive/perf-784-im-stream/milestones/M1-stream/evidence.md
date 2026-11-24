# 服务端复测

## 同负载结果

基线 6e387616f，候选 796b42b16；Node 24.22.1，macOS arm64，本机文件数据库，WAL。chat streaming 的同步调用计时覆盖解码、写入授权、SQLite、读者解析、序列化和计数 socket。没有测公网传输、模型生成、真实客户端绘制或同时生成回复的 1000 个用户。

| 每帧 | 基线 | 候选 |
|---|---:|---:|
| 群内 99 名真人与 1 个 Agent，1000 个浏览器，99 个投递 | 1119 get + 2 all + 3 run | 116 get + 1 all + 3 run |
| 群聊五组均值 ms | 12.079 / 12.127 / 10.766 / 11.081 / 11.115 | 0.746 / 0.819 / 0.746 / 0.746 / 0.815 |
| 1 真人与 1 个 Agent，无浏览器 | 34 get + 2 all + 3 run | 16 get + 3 run |
| 无浏览器五组均值 ms | 0.764 / 0.804 / 0.812 / 1.144 / 0.744 | 0.315 / 0.297 / 0.340 / 0.320 / 0.328 |
| 各场景 100 帧新增 WAL 字节 | 4,956,392 | 4,845,152 |

组间时间有机器负载波动；一次较早候选测得群聊中位数 0.825 ms。计数是 StatementSync 实际执行，不含事务的 BEGIN/COMMIT 或 SQLite 内部触发器。WAL 采样关闭自动 checkpoint，以截断后的 100 帧计；差值 2.24%。正文拼接仍存在。每帧三次独立写提交合为一次，并保证重试、正文、事件原子落库。按字节累加的逻辑拷贝估算不能代替 WAL 页数或磁盘吞吐。

复测用 control-fixture 的用户、Agent 与 chat 基础数据，VACUUM INTO 隔离文件并用 openDatabase 打开；用真实 Messaging/Gateway，置 type 为 group。群中 99 个真人账号各有一个有效 session，另外 901 个有效 session 属于群外账号。用 Gateway.streaming 发 turn_start，然后每帧同一 message_id、100 个 ASCII 字符和唯一 idempotency_key。预热 12 帧，在第 13 帧统计 get/all/run 并核对目标 socket 数；截断 WAL 后计时 5 × 20 帧，并断言正文长度。数据库和临时目录在测后删除。

## 原报告各项复核

- **广播**。gateway.ts 原逻辑先筛收件人和 cursor，群外 901 个在线者不逐人查数据库。conversation-access.ts 原先预先校验所有成员，命中 socket 再校验。新逻辑同一帧批量取真人成员，复用其当前空间字段，逐 socket 核验 session，私聊沿用观察者规则。显式成员变化通知沿用其原收件人。
- **流式授权与合批**。普通 Agent 空浏览器小群依然有写入权限、代次和幂等性的实际成本。chat-streaming.ts、messaging.ts、agent-lifecycle.ts 复用同帧读取，PA 来源、成员移除、Agent 停用的当前权威继续生效。single-thread.ts 在 50ms 或 4096 个 UTF-16 单元时触发 flush；无法单从 2KB 算出帧数。部分正常生产帧没有 run_id。
- **编译 SQL**。context.ts 的 one/all 确实反复 prepare。独立内存库中文本主键单行读取，三轮各 5 万次：每次 prepare 2.84 / 2.53 / 2.44 µs；复用 0.52 / 0.47 / 0.48 µs。此结果只适用于该微基准。实际改动只缓存语句，不缓存行；许多直接 db.prepare 的调用也不经过 one/all。
- **幂等键**。schema.sql 的外键会随消息删除而级联，旧实现对保留历史的已结束消息持续保留键，还给迟到帧新增键。新 trigger 覆盖正常结束、禁用与超时变更。历史整理脚本在隔离旧状态文件中运行：2 个旧终态键删除、1 个 running 键保留；消息及事件各 3 条，回滚与二次执行验证通过，随后 running → failed 自动回收到零。
- **周边**。identity.ts 的 bcrypt worker、schema.sql 的会话/消息/时间索引、gateway.ts 的 2001 条重放探测均已确认。server.ts 的 5 秒 guard 仍逐在线 session 验证，1000 个浏览器理论上每 5 秒 1000 次。relay-delivery.ts 的 250ms timer 只有一个，drain 会遍历在线节点，空闲轮询成本随节点数增长。两者与本次一条 delta 的同步计时口径不同。
