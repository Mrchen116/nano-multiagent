# perf-695：As-built Design

> 实现后根据代码与实际证据形成；没有补造事前设计或产品验收报告。

## 实现范围

Base：`9f2c73e0e40a81da05d0859719830b3a0089b6bb`。完整代码提交由 code-review.md 固定。涉及 IM、PA、DSH 接入及前端通知分类，不改变 DSH 公共接入边界。

## 最终结构与约束

- **PA**：NodeStore 增加按 Agent/未交付控制查询与部分索引；SingleThread 一轮恢复中每 Agent 执行一次控制恢复，仍先 ensure、控制屏障、待输入与 reconcile。Task 原文 prepare/commit 共用单条投影，commit 从现有 `(agent_id,message_id)` 唯一键读取，并重新验证 admitted、未消费、非 personal_unclassified、完整 content 与安全整数 turn；既有消费事务与回执次序保留。ExternalStore 按 Agent/来源查询，搜索/锚点读复用 scoped target 查询，保留首条持久顺序、未镜像错误及 Agent 隔离。
- **DSH**：TrajectoryRuns 在公开 storage-domain 表打开后构建 session→run ID 派生索引；persist 成功后维护父/子两个关系。现有 durable table 仍是唯一事实，read 等待原有写屏障，再 get 相关 ID，保留排序、running→unknown 与授权。索引只增加 ID 关系，不复制完整 run；生命周期随 service，冷启动重建。Skill 桥先计算实际手势，无手势时清理 pending 并返回原 decision；需要去重时才读历史。NativeHistory 使用公开 pre-step turn，保留 next 的拒绝判定、route/config 捕获时点与串行首次持久化；没有为减少少量 config copy 添加新缓存。
- **IM**：Work turn/item 依现有排序键增加索引；最新 usage 采用 iterator，遇到第一个 truthy usage 后停止，保留“最新几轮没有 usage 时使用之前最近值”。Replay 保留大 gap 优先级、空/负/最新游标行为，在需要时间窗口时明确使用 covering 时间索引；不假设时间戳单调。38 组旧/新实际方法对照包含无近期事件、非单调时间、边界游标、Work 多页与旧 usage，输出一致。
- **上传**：media 是 attachment_storage 的现有唯一运行写者，启动时仍清理 reserved。首次上传按 owner 汇总一次，服务总量包含所有历史 owner，后续逐块更新 DB 后同步更新派生数值，中间没有 await。每请求另存 accepted reservation 字节数；size 包含被拒绝块，不能用于回滚。stored 状态切换不改变用量；失败、幂等重复、内容拒绝与权限撤销 DELETE 成功后释放 accepted 字节。失败返回前等待流 close，避免异步 open 越过文件清理。管理员容量读仍以 DB 为准；没有持久化第二套账本、TTL 或失效回退。
- **前端**：未决外部分类以 conversation ID 保存最新候选；对象身份作为过期回包判断。缓存已有新消息立即废弃旧候选；取消旧列表请求后、发查询前再次确认候选仍有效，从而合并同步突发。保留登录身份、会话状态、候选到达之后的新权威读取及重连重试；不使用可能复用旧请求的 fetchQuery。

## 失败、迁移与回滚

新 SQLite 索引由现有 schema/Store 构造路径自动创建，不改数据语义、不需要人工一次性迁移。上传及轨迹索引仅为进程内派生状态，重启从原事实重建；DB 写失败不会提前更新派生计数/关系。多实例同时写同一附件库不属于现有上传生命周期（现有启动会清除全部 reserved）；没有为测试修改 live DB 添加失效协议。回滚代码不需回滚数据；额外索引可保留。

## 验证证据

稳定证据目录：`/Users/czj/.codex/reports/perf-695-20261102/`，含三个独立审计报告、旧/新增长探针、日志和前端对照；均为隔离数据。

- PA：300 会话/1,000 已完成控制，解码 300,000→0；500 原文凭证解码 125,750→1,000，全部消费；外部搜索/锚点读 3,001→2、来源读 3,000→1，转发目标不变。
- DSH：无手势与 NativeHistory 每步历史快照均 25→0。轨迹索引仅初始化遍历一次；30 次请求只 get 30 个目标，与无关历史量无关。真实轨迹测试覆盖冷重启、嵌套、并行、失败与取消。
- Work/replay：固定 20 条/100,000 turn 的实际 view 约 0.47 ms，latest 不再物化全历史；38 组完整输出一致。上述时延为机器上的合成探针，不能作生产承诺。
- 上传：100,000 附件/8 MiB，首次 1 次合计、之后 0 次；首个约 31 ms，后两个约 12 ms；每次持久总量与预期相等。新增 4 项 handler/storage/file 回归覆盖 owner/service 并发、终止释放、超大块不误减、重启 reserved 清理、MIME 拒绝、图片重试及权限撤销。初次测试暴露异步 close 问题，修复后 4 passed、0 errors。
- 前端：相同最终 toast，100 次初始和重连读取各降到 1。旧回包测试明确等待首个请求发出后再发新候选，保留真实倒序完成覆盖。
- 初次定向 8 文件：33 passed、1 failed（复制 Skill 的文件监听发现超时，发生于任何 submit/pre-step 前）。同版本单独重跑该项通过；保留两次日志，不把一次未复现写成根因确认。构建与类型检查通过。完整门禁结果在 code-review.md 收口。

## Canonical 文档

无 spec delta：接口、模型可见文字、权限、错误、排序/分页、恢复与容量保持既有契约。本轮按用户本次亲测豁免由工程证据与独立审查验收；未改变通用规则，未部署生产。
