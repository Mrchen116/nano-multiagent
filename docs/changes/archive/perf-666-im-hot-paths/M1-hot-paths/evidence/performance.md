# 隔离性能验证

## Claim / Baseline / Method

2026-10-27，基线 main `85910853`；候选为本 unit 实现树。Node 25.8.2 / SQLite 3.51.3，本机隔离内存库/模拟 relay；没有访问生产数据。原代码从 `git show 85910853:<path>` 获取，与候选在同一进程串行测量。SQL 表格为七次查询中位数，非冷盘或压力测试；性能数值不进入永久测试门禁。

## 流式 ACK

直接运行基线与候选 SingleThread，通过同一 runtime/relay public port 注入 100 个有序文本片段，每个片段之间约 1ms，每次 delta ACK 人工延迟 20ms，最后给 durable answer 和 turn/end；检查增量拼接、最终正文一致。此为传输机制实验，不是真模型性能结论。

| 实现 | delta 请求数 | 生成片段用时 | 收到最终 completed 用时 | 正文完整 |
|---|---:|---:|---:|---|
| 基线 | 100 | 123ms | 2156ms | 是 |
| 候选 | 5 | 132ms | 155ms | 是 |

模型完成后的显示尾延迟由约 2033ms 降为 23ms（本次合成条件）。连续输入实际速率和定时器调度可能改变批次数，不承诺固定倍数。

## Watchdog

分别加载基线和候选 schema；均有 10000 条 messages（3 条 running），合成事件按 `n % 10000 + 1` 分配 message_id，时间相同且已过 cutoff。每规模比较结果集合完全一致。

| 历史事件数 | 基线查询 | 候选查询 |
|---:|---:|---:|
| 10000 | 4.635ms | 0.002ms |
| 100000 | 23.572ms | 0.002ms |
| 500000 | 124.024ms | 0.002ms |

基线 EXPLAIN：MATERIALIZE e → SCAN conversation_events USING INDEX conversation_events_message → SCAN m → SEARCH e USING AUTOMATIC COVERING INDEX。

候选 EXPLAIN：SCAN m USING COVERING INDEX messages_running → CORRELATED SCALAR SUBQUERY → SEARCH e USING COVERING INDEX conversation_events_latest(message_id=?)。50 万事件目标 < 基线 20% 达成；微秒级结果受内存缓存影响，不作生产延迟保证。

永久 watchdog 行为测试另覆盖近期活动、较旧事件后插入、无事件、严格 cutoff 边界、completed 忽略及正文保留，使用真实服务 timer + SQLite。

## 联系人

原 contactRows 直接从基线源码提取（仅移除 TypeScript 标注），复用同一身份判断函数；候选调用实际 contactPage/contactDetail。全部合成用户为 active 真人，按 ID 排序；测第一页和第二个用户的详情。计数仅包含联系人查询本身，不含登录鉴权。

| 候选人数 | 列表 SQL 数：前→后 | 列表耗时：前→后 | 详情 SQL 数：前→后 | 详情耗时：前→后 |
|---:|---|---|---|---|
| 100 | 101→1 | 1.210→0.288ms | 101→1 | 1.210→0.037ms |
| 1000 | 1001→1 | 11.830→0.279ms | 1001→1 | 11.492→0.036ms |
| 5000 | 5001→1 | 70.768→0.291ms | 5001→1 | 61.378→0.035ms |

Agent 候选按批次增加一次 owner 资格查询，PA binding 已在唯一键 JOIN 中批量关联。新增 users(owner_id) 索引支持 owner 批量读取，保留首个人类账号选择和原展示名关联。稀疏可见性/搜索仍需扫描多个候选批次；永久 HTTP 测试覆盖 180 个穿插隐藏 Agent、两页结果、Unicode 搜索和详情、PA/owner 资格改变。未声称任意过滤下都只需一次查询。

## Locator / Limit

本轮临时脚本和原始输出保存于执行机 `/tmp/perf-666-evidence/` 及 `/tmp/perf-666-{benchmark,stream}.log`；脚本不进入永久测试套件。报告保留基线、数据生成规则、指标与实际结果，真实模型/产品旅程由独立 acceptance 报告记录。未测生产 RTT、生产数据规模、磁盘 IO 或并发容量。
