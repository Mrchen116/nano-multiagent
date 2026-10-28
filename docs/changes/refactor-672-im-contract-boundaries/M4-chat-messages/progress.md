# M4 — 聊天发送与流式完整契约

用户授权在同一 PR #426 扩展。设计 Round 3 Approved（0 CRITICAL/WARNING）后实施。

- product-contracts 的 ChatStreamFact / AgentPublication / ChatMessage / ChatEvent 区分生产、传输事实、回执与公开投影；decoder 校验实际消费字段并返回原对象，动态工具内容不规范化。
- SingleThread / GlobalAgent 真实生产点使用有限契约；External 的转发和持久 outbox 读取使用同一 decoder，system_notice 保留独立分支。
- MessageRecords 持有具名 SQLite 行、JSON 列与消息/事件投影，只有 DB、交互窄端口和发布回调。ChatStreaming 保留授权、生命周期和既有状态分支，Gateway 仅接线。正文增量仍不读取过程 JSON。
- 普通 HTTP 经 MessageInput / SendMessageCommand 进入 Messaging 事务编排；原认证对象引用保留响应前撤销校验。Agent 显式 publication 业务移入 Messaging，保留独立 dispatch identity；普通幂等指纹、交互事务、PA provenance、relay 队列及序列化 owner 不变。

Node 24.22.1，本地日志 `.e2e-refactor-672/m4-*.log`（不提交）：

- 基线：7 文件 61 tests passed；真实 SingleThread → WS → IM → HTTP/history 1 passed。
- 新畸形字段用例先失败（非法过程字段得到 ACK），实施后通过；确认不落 SQL、不消耗该 delta key、不发布事件，合法重试只拼接一次，终态后不重开。
- 相关回归：10 文件 110 passed；追加身份/tenancy/PA 代发/Task/relay 恢复/watchdog/codec 11 文件 52 passed。
- build、全包 typecheck（包括 SQL/View 与生产配对负例）、check:ios-runtime 通过。

真实模型不在本次类型/归属重构验证范围；贯通测试仅将 native RuntimePort 作为确定性事实源，真实 PA、协议和 IM 均执行。provisional discard 原子投影回滚的既有 spec/code drift 不计为本次修复或通过；no spec delta，无 schema/部署迁移。
