# As-built design

本文在实现后形成，记录第一轮实际改动。

## 实现

- IM 会话列表以 username 的 `agent:` 前缀解析 Agent 主键；新增按 conversation_id 查询 running 消息的部分索引，保留 watchdog 使用的原索引；work 广播把 root 固定属性读取移出用户循环。
- NodeStore 增加未提交输入的选择性读取和单输入 terminal 查询，复用 admission rowid 顺序；恢复路径也使用相同筛选。Task 使用既有 session 主键及当前 conversation binding 查询，继续拒绝旧 session 和未经映射的外部 conversation。
- ExternalStore 使用审批 request 主键、聊天 shadow 表达式索引与目标集合读取。describe 保留原聊天顺序和去重；查询仍限定 Agent，外部 raw ID 与 IM shadow 的既有规则不变。
- ModelFallback 按 session 组织权威 run 引用；live run 表仅跟踪已附着运行，用于原有 busy/continuation 生命周期。存储格式不变，恢复先等持久历史加载完成。allowed 在一次调用中复用同一 session 的列表。
- Memory 在一次选择中建立 first-call-name、message-carrier 集合及准确 session/inherited/call 分组，预计算组大小。parent 快照及 seq 索引只在同一次 children 调用中复用；每份快照仍通过既有持久化屏障，来源摘要、资格过滤、时间边界及 sourceVersion 不变。
- Task pre-step 仅在当前输入包含 schedule 时提取 schedule 历史。
- 前端先更新事件时钟、流式累积和完成失效通知，只有生成通知 candidate 才查会话列表。

## 契约、失败与回滚

无对外行为变化、无 canonical spec delta、无新缓存失效协议或并行运行系统。索引由现有建库流程 `IF NOT EXISTS` 添加，旧数据无需改写；回滚代码可保留额外索引。Memory 的模型可见文本及 omissions 通过旧/新函数逐字对比，独立 review 覆盖 Agent Context 选择和恢复链。

## 验证

证据目录：`/Users/czj/.codex/reports/perf-694-20261101/`。已有 9 文件 88 测试及前端 2 文件 23 测试通过；后者包含临时成本探针。扩展 Task alias/reset 与外部 describe 作用域回归。Memory 12 组输入/预算逐字一致。最终 CI 和 review 见 code-review.md；未运行生产流量、真实模型或故障注入。
