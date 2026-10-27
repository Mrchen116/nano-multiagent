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

turn/end → 单会话合并队列 → 捕获 seq / flush → 校验可读副本水位 → 仅取未导出事件 → 追加可读消息 → 成功后推进水位。session.export 进入同一队列，另外读取完整持久切面，以临时文件 + rename 发布原始 JSONL。DSH 为唯一权威；内存只存序号和可读文件字节长度，不存正文。

## 关键决策

1. **原始历史按显式请求完整发布。** 实际消费者是 PA distill，它取得路径后可能很久才让 Skill 读取；因此原始文件始终采用原子替换，绝不原地 append。turn/end、fork 和启动不再更新原始导出；只在 session.export 生成最新完整持久切面，返回原有命名的路径。后续聊天不改变该文件，下一次显式导出也只发布完整文件。保留历史遗留文件，不删除、不另建全量缓存。生成时机的变化写入 delta。
2. **可读副本正常采用 JSONL 追加。** 首次、重启、文件缺失/长度不符或失败后完整原子重建。每个 live Session 生命周期仅记录下一个事件序号、可读字节长度（WeakMap，不保留 Session 强引用）；原始和可读写入（若适用）均完成后才更新水位。追加不重编码旧消息，不截掉 fork 前缀。同长度的用户原地改写不属于支持的派生文件编辑协议。
3. **合并尚未完成的请求。** 每会话最多一个执行任务加 pending/raw/rebuild 标志。新 turn/end 设 pending；显式 export 同时保留 raw 标志，恢复请求保留 rebuild 标志，不能被普通请求覆盖。循环处理到最新请求，未变化切面不写可读文件。失败保留拒绝结果并使水位失效；如果失败期间有新请求，继续处理且不能丢失未成功的 raw/rebuild 意图；无新请求则报错，不无限自重试。不同会话独立。
4. **持久切面、排队和恢复统一。** 队列捕获 session.seq 后再 flush，导出上界固定到捕获序号。session.export 会主动请求导出，故失败后再次请求可以恢复；fork 返回前等待可读副本；stop 等待已排队任务。启动 recoverExports 使用同一队列强制重建可读副本，避免与已加载 Session 的事件回调交叉写。无须假定 initialize 期间完全没有后台回调。
5. **不引入第二份派生全量缓存。** 仅合并队列不能改善顺序轮次；每轮增量追加原始文件会破坏延迟读取完整性；为原始 append 文件再建快照副本会增加磁盘副本和状态。选择低频显式完整原始导出 + 高频增量可读副本，满足已证实消费者且保持结构小。

## 接口与数据流

NativeHistory 公共方法及 RPC 签名不变，path 由只检查文件改为请求/等待完整快照。队列以 session id 标识，每次执行从 ctx.sessions.get 取实时 Session；若未加载，使用既有 sessionQuery.observeSession 租约并检查实际 source：prepared 才使用持久 observation；如果等待读盘时会话变 live，重新取得 live Session 并走同一捕获上界/flush 路径，无法取得或 flush=false 则失败，不发布。实时读取只改现有 snapshotEvents 调用为按上界/起点读取（无新读取调用点），普通任务取尾段；raw 请求取完整切面，其可读投影仍只处理水位后的尾段。prepared 恢复不建立可供未来 live Session 复用的水位；首次接管新的 live Session 完整重建，避免把冷读中补齐的 interrupted-turn closers 当成另一生命周期的稳定前缀。冷读需要完整 observation，这是低频恢复/请求成本。

writeExport 内部验证可读文件长度（ENOENT 视为需要重建，其他错误传播）。有可信水位时只 append 非空消息行；无水位时写临时文件并 rename。无消息完整副本允许空文件。raw 请求单独序列化 header + 全部原生事件并原子 rename。任一步失败清除水位，下次从零重建可读副本；原始生成失败保留上次完整原始文件，并向 RPC 返回失败。DSH facts 不改变。

直接读取正在追加的可读 JSONL 可能看到未完成尾行；完成队列后提供完整消息。原始文件给延迟消费者的完整性不依赖读取时机，也不依赖模型能否容忍半行。两个派生文件不承诺跨文件原子事务（旧实现也没有）；失败不得返回成功路径。

## 契约层增量 (delta-spec)

`specs/gateway/routing-delivery.md` 增补原始历史显式快照、可读副本自动更新及失败重建边界。RPC 与 JSONL schema 不变。既有可读副本条款提及 conversation-id，而实际自 DSH 迁移后采用原生 session-id；本次不做命名迁移，新增条款按实际文件接口描述。

## 风险与回退

冷启动仍完整恢复绑定会话的可读消息；显式原始导出仍为 O(总历史)，这是低频消费者要求，不优化历史文件占用。未请求 session.export 的原始旧文件可能停留在旧切面，不作为最新查询入口。可读追加中断可能留下尾行，下一次队列请求/启动完整重建修复。回退旧实现可以直接重建同格式文件。本次不部署。

## 一次性部署迁移

无。旧原始文件保留且显式请求时更新；启动/首次可读恢复是正常产品路径。不新增迁移或删除历史。

## Runbook for Reviewer

无新增常驻服务。验收运行隔离 DSH RuntimeClient 子进程，临时 home/cwd，由驱动结束时 shutdown 并清理。使用本 worktree 构建，Node 24.22.1；无生产连接和外发。

**Review 驱动方式**: 本 unit 不改客户端；workspace 读取直接消费生成文件，原始导出/fork 使用 PA 实际调用的 session.export/session.fork 同一运行时 RPC，使用真实锁定 DSH + 确定性 fixture LLM。不宣称真模型、Web/iOS UI 或生产时延验收；变更仅在上述文件/RPC 下游，模型内容不影响导出机制。可复用现有 history.test.ts fixture，在隔离运行中独立观察原始/可读文件、fork 与重启结果。

**验收前置**: pnpm install --frozen-lockfile、pnpm build；fixture 不访问外网。停止为驱动 finally 中 RuntimeClient.shutdown/kill，启动为 RuntimeClient + initialize。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-export | 增量导出与合并队列 | 无 | 无 | history.ts、history tests、unit evidence 与 delta | [worker] 顺序 20 轮相较 baseline 的原始事件序列化和应用写入字节下降 ≥95%，同样完整输出；突发请求不逐项全量重写；测试覆盖持久上界（含 observe 从 prepared 查询转为 live）、同会话并发、跨会话隔离、延迟原始读取、失败重建、缺失文件、fork 与 restart；[reviewer] 完整历史阅读/提炼输入、fork 独立增长和重启恢复场景保持成立 |
