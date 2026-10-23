# perf-651: 增量生成原生历史导出 — 技术方案

> 对齐: motivation.md

## Changelog

## 现状分析

### 涉及范围

`packages/dsh-integration/src/history.ts` 是唯一修改的产品模块；`index.ts` 在 initialize 调用 recoverExports，在已校验 binding 的 session.export 调用 path，shutdown 调用 stop。`packages/personal-assistant/src/history.ts` 的 distill 通过 session.export 取得原始 JSONL。workspace 副本是直接文件消费面。原始日志、配置快照和 fork 操作账本不属于派生文件。

### 既有约束

只使用声明的 DSH exports；不改 runtime、不创建第二份历史库。DSH Session.header 为深度冻结创建元数据，事件日志 append-only，Session.seq 是长度；既有 snapshotEvents 调用可传半开区间，不新增私有 API 或同步读取调用点。导出必须经过 flush；只导出 flush 前捕获的序号上界，避免等待 flush 时新事件混入未确认的持久切面。

### 可复用能力

保留现有临时文件 + rename 作为初次和恢复写入；保留原始版本头、human envelope 过滤、图片占位及命名。保留原生 query 的启动恢复和完整 fork prefix。复用 history.test.ts 的真实 DSH 子进程 fork/compaction/restart 回归；新文件仅承担最低层的文件故障、队列并发和写入工作量风险，不复制产品链路断言。

### 相关历史

`a3a842f21` 建立原生 fork/export 与 distill 链路；`1c77ccb0d` 恢复真人来源语义。现有来源过滤与 fork 配置快照不改变。2026-10-23 审计作为问题线索，本次以最新源码及合成 benchmark 复核。

## 架构总览

turn/end → 单会话合并队列 → 捕获 seq / flush → 校验派生文件水位 → 仅取未导出事件 → 写原始和简化 JSONL → 两份完成后推进水位。DSH 为唯一权威；内存只存少量水位，不存事件或序列化全文。

## 关键决策

1. **正常导出采用 JSONL 追加。** 首次、重启、文件缺失/长度不符或写失败后仍完整原子重建每份文件。每会话记录下一个事件序号、原始字节长度与可读字节长度；append 成功且两份均完成才更新水位。追加不重新编码旧事件，不截掉 fork 前缀。文件属于派生结果，不支持用户在运行中同长度改写其内容。
2. **合并尚未完成的请求。** 每会话最多一个执行任务加一个 dirty 标志。新 turn/end 标记 dirty，执行循环持续到最新请求被处理；未变化切面不写文件。队列失败保留拒绝结果供 path 感知，下一请求可以重试。若写失败期间已有新请求，循环必须处理它，不能吞掉。不同会话仍可并行。
3. **保持自动生成，拒绝按需生成和仅合并。** 按需生成会改变原始文件更新时机；仅合并不能改善顺序 turn/end 的重复成本。无需新增磁盘索引、正文缓存或永久游标。
4. **完整边界以导出完成为准。** session.export 等待其 session 队列，fork 返回前等待副本，stop 等待排队任务。普通文件读取发生在追加期间可能看到完整行前缀或未完成尾行；不承诺运行中两份派生文件的跨文件事务（旧实现也没有）。需要完整切面的原始消费者必须经过 session.export。失败不返回成功路径；下一次尝试/启动完整重建清除部分尾行，保留 DSH 事实。
5. **恢复由既有初始化阶段统一负责。** initialize 在 accepting=true 前串行 recoverExports，按 observation 完整重建并建立水位；运行中队列共用同一写入逻辑。无新增后台全库扫描；未绑定子会话在首次新 turn/end 接管时完整生成。

## 接口与数据流

NativeHistory 的公共方法和 RPC 无签名变化。writeExport 内部接受本次事件片段与可选成功水位，返回新水位。队列中先捕获 session.seq，再 await flush；通过现有 snapshotEvents(from, to) 读取这次已持久上界内的尾段。缺少可信水位或派生文件长度不符时 from=0。读取错误除 ENOENT 外传播，不将权限/磁盘错误当空文件。

writeExport 首次用临时文件和 rename 写完整原始和可读 JSONL；正常用 appendFile 追加非空片段。没有可读消息时追加字节为 0；完整生成的无消息副本允许空文件。任一失败清除水位，下次从零重建；不添加自动无限重试。恢复与实时写入不同时运行：既有 initialize 接线先 recover 再开放产品请求。

## 契约层增量 (delta-spec)

`specs/gateway/routing-delivery.md` 增补派生历史导出的完成与恢复边界，明确读取者需要的完整状态；不改变 RPC 格式。既有可读副本条款提及 conversation-id，而实际自 DSH 迁移后采用原生 session-id；本次不扩展为命名迁移，新增条款按实际文件接口描述。

## 风险与回退

追加期间直接文件读取可能看到未完成尾行；等待导出完成后提供完整 JSONL。进程崩溃留下的尾行在现有初始化重建时修复。磁盘故障可能使两份文件停留在不同切面，path 报错而非成功；随后完整恢复。初次/重启仍为 O(总历史)，本次不优化冷启动或历史磁盘占用。回退旧实现仍可直接读同格式文件并重建。

## 一次性部署迁移

无。启动恢复和首次接管已是正常产品路径，不新增生产迁移；此次不部署、不删除旧历史。

## Runbook for Reviewer

无新增常驻服务。验收运行隔离 DSH RuntimeClient 子进程，临时 home/cwd，由驱动结束时 shutdown 并清理。使用本 worktree 构建，Node 24.22.1；无生产连接和外发。

**Review 驱动方式**: 本 unit 不改客户端；workspace 读取直接消费生成文件，原始导出/fork 使用 PA 实际调用的 session.export/session.fork 同一运行时 RPC，使用真实锁定 DSH + 确定性 fixture LLM。不宣称真模型、Web/iOS UI 或生产时延验收；变更仅在上述文件/RPC 下游，模型内容不影响导出机制。可复用现有 history.test.ts fixture，在隔离运行中独立观察原始/可读文件、fork 与重启结果。

**验收前置**: pnpm install --frozen-lockfile、pnpm build；fixture 不访问外网。停止为驱动 finally 中 RuntimeClient.shutdown/kill，启动为 RuntimeClient + initialize。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-export | 增量导出与合并队列 | 无 | 无 | history.ts、history tests、unit evidence 与 delta | [worker] 顺序 20 轮相较 baseline 的原始事件序列化和应用写入字节下降 ≥95%，同样完整输出；突发请求不逐项全量重写；测试覆盖持久上界、同会话并发、跨会话隔离、失败重建、缺失文件、fork 与 restart；[reviewer] 完整历史阅读/提炼输入、fork 独立增长和重启恢复场景保持成立 |
