# perf-666: IM 热路径性能优化 — 技术方案

对齐 [motivation.md](motivation.md)。

## Changelog

## 现状分析

### 涉及范围

`packages/personal-assistant/src/single-thread.ts` 负责普通会话输出及收口；`apps/im-server/src/gateway.ts` 处理流式增量；`server.ts` 定时检查停滞回复；`messaging.ts` 提供联系人 API；`schema.sql` 维护可重复创建的索引。

### 既有约束

只通过现有 runtime 和 relay ports 工作，不修改 DSH、不扩大依赖边界。流式消息发送者/节点/生命周期/会话写权限校验不能省略。保留群聊草稿抑制、显式发送哨兵抑制、模型 fallback 的发布检查、关闭 flush 和失败最终 reconcile。联系人保持 current auth-tenancy 的空间资格与 PA 可联系性规则。

### 可复用能力

复用现有串行 ACK、batch 请求的 idempotency_key、message_completed 全文校正，以及现有 lifecycle 校验。复用 SQLite DatabaseSync 和声明式索引；不引入缓存、后台数据库或第二份最后活动状态。联系人复用 canAccessSpace 的纯权限判断、ownerAccount 的真人选择规则和现有响应字段。

### 相关历史

基线已有 model-fallback 测试保护最后一个 delta 与 completed 的顺序，tenancy 测试保护私人/公司权限；interactive-replies 测试保护显式发送哨兵。保留这些保护并扩展适用 seam，不重复新建对应测试。

## 架构总览与关键决策

1. **流式按待发文本合并，保持每条 stream 至多一个在途发送。** 空闲时最多等待 50ms，累计达到 4096 个 UTF-16 code units 时提前 flush；等待 ACK 期间只累积文本与末索引，ACK 到达后一次发送积累内容，不给每个碎片挂 Promise。阈值是 flush 触发点，不是强制切分大 chunk 的协议上限。首尾 chunk 索引形成稳定 batch 幂等键。end、stop、modelCheck 强制 flush 并等待；deactivate 清理定时器/待发数据。发送失败沿用 onError 与最终 durable answer 校正，不增加自动重发。
2. **服务端 delta 只读取验证和投递所需的消息字段。** 非 delta 仍走完整 message()；delta 查询消息 id、conversation、sender 类型和身份、生命周期、状态，复用后续所有权限检查。继续使用原子 content 拼接和事件写入；合并降低次数，不另建分片存储。
3. **watchdog 先定位 running，再索引取最新事件。** 使用 correlated subquery ORDER BY created_at DESC LIMIT 1；保留 COALESCE(message.created_at)、严格小于 cutoff、空正文填充/非空正文追加失败信息。索引 conversation_events(message_id,created_at DESC)，以及 messages 上仅 running 的 partial index。无活动消息时不扫描历史事件；不另维护容易漂移的 last_activity。
4. **联系人详情定向读取，列表使用有界候选批次。** SQL 下推 id/cursor/kind 和可直接筛选的候选条件；每批最多 100 个候选，批量读取其真人 owner 和 PA binding，再用 canAccessSpace 与现有等价资格判断过滤；凑满 51 个可见且匹配搜索的联系人即停止，响应前 50 个。详情只装配指定 id 并执行相同权限判断。Unicode toLowerCase/includes 搜索保持 JavaScript 语义，不换成 SQLite ASCII lower/LIKE。稀疏可见性/搜索仍可能扫描多个批次，这是为保真保留的成本，但不全量装配或 N+1。JOIN 按 users.username 的 agent 前缀取 agent_id 定向关联，避免每个 user 扫描全部 profiles。

## 接口与数据流

对外 HTTP/WS envelope 不变。流式仍发 message_delta(delta_text,idempotency_key)，但一个请求可以覆盖多个 runtime chunk；每批重新检查 delivery、fallback 和显式发送资格。计时器只触发 flush，发送链串行处理当前待发 buffer，并在结束后释放 stream。completed 必须等最后批次 ACK。

联系人查询辅助代码可以独立于 Messaging 提供一个窄 contacts 模块，以便列表和详情共享装配与资格逻辑；不新增公开 API。批量 owner 选择遵循 ownerAccount：owner_id 匹配且 username 非 agent:/shadow:/system，多个候选时沿用首个真人规则。展示用 owner_display_name 保留既有 owner.id 关联语义。

模型上下文不变：不改变 runtime 事件、输入内容、投递权限或最终回答，仅改变向用户传输增量的批次与内部查询；modelCheck 仍等待已产生文本的发布结果，不能因缓冲未 flush 而误判为未发布。

## 契约层增量

no spec delta：保持现有消息、联系人 API 和权限契约，不将固定 50ms 或批量大小提升为公开承诺。

## 风险与回退

主要风险为最后批次遗漏、完成抢跑、停用后泄漏，以及联系人过滤前后位置变化造成遗漏/越权。通过公开 relay 输出、HTTP contacts、真实 SQLite 与原有权限回归覆盖。错误重试策略不扩大。回滚代码可恢复原查询，索引兼容旧代码。

## 一次性部署迁移

无。新增幂等索引随 schema 初始化创建，无历史数据格式变化；首次建索引有一次扫描成本。没有本次生产部署授权。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 隔离 IM + Node/DSH | `./scripts/e2e-down.sh` | `./scripts/e2e-up.sh --profile daily` | 使用 `.e2e-ports.env` 的 IM_URL 与脚本 readiness；版本、运行目录和 `.e2e-daily.json` 随交接提供 |

Review 驱动方式：不改客户端面，独立 reviewer 走端到端真栈，使用客户端同一 HTTP/WS 接口驱动私聊、群聊与联系人；测试用户和配置仅来自隔离 daily profile。daily 默认 P/E/Q 与 PA 均为 Global，须在本次隔离实例通过正常 Agent 创建接口新增一个 `work_mode=single_thread` 的普通 Agent，复用 daily 可用真实模型；不修改全局模板。普通私聊长回复和群聊草稿抑制均用该普通 Agent，显式发送回归使用 daily Global Agent。交接记录新增 Agent ID、工作模式、会话 ID 与配置增量；普通私聊必须实际观察该 Agent 的 message.delta 与最终 message.completed，不能用 Global 显式发送成功替代。watchdog 用隔离库建立确定的活跃/停滞前置，经真实服务定时执行观察状态。验收前置：本机现有模型凭据由 daily 脚本使用，先检查 readiness；凭据不得进入证据或 PR。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-hot-paths | 按流式、watchdog、contacts 顺序完成 | 无 | 串行 | 上述模块及对应 tests | [reviewer] motivation 所有回归场景；[worker] 延迟 ACK 下碎片被合并、完整有序、end/stop/modelCheck 正确 flush、幂等与权限保留；watchdog 相同筛选结果且 EXPLAIN 按 running 和最新事件索引查找，50 万历史事件目标 < 原耗时 20%；contacts 定向详情及多页/Unicode/不可见候选回归，批量查询不随单批人数逐人增加；窄测试、适用本地 CI 和远端 CI 通过 |
