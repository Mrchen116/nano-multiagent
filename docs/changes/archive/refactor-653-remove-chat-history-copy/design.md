# refactor-653: 移除 workspace 聊天历史副本 — 技术方案

> 对齐: motivation.md v1

## Changelog

## 现状分析

### 涉及范围

`packages/dsh-integration/src/history.ts` 同时维护配置/fork 元数据、workspace 可读副本和原始导出。构造函数监听 turn/end，performFork 主动导出，index.ts 启动时 recoverExports 扫描绑定会话。测试 history-export 覆盖文件写入队列；history 与 native-human-source 以真实 DSH subprocess 验证产品路径。

### 既有约束

DSH 只通过公开 exports 接入；不改运行时或原生存储。主仓和历史副本均不清理；本任务独立 worktree。原始导出供提炼消费者延迟读取，须完整原子发布。

### 可复用能力

保留配置快照、fork 元数据、DSH flush/observeSession 和显式 path 导出；移除可读正文投影、WeakMap 游标、rebuild 标记及自动触发。保留按 session 合并的显式请求队列，以串行化同名临时文件写入；新显式请求在当前写入后再发布，错误不会冒充成功。stop 等待队列。

### 相关历史

perf-651 把原始快照改为按需发布，并实现可读副本增量维护。本次移除可读部分；保留其持久化切面、原子发布与延迟读取语义，不改历史归档。

## 架构总览

会话持久化仍由 DSH 负责。NativeHistory 只记录 Nano 配置/fork 事实并响应显式原始导出，不再派生 workspace 文件。无需新增模块、配置开关或兼容路径。

## 关键决策

- **完全移除 workspace 副本写入。** 包括显式导出的副作用；不保留无消费者的可读投影和恢复代码。
- **既有文件原样保留。** 用户要求停止生成，不包含删除历史文件。
- **保留按需原始导出契约。** 每个显式请求经过持久化屏障；并发请求合并后等待完整发布。普通新 turn 不触发导出或重试。

## 接口与数据流

删除 recoverExports 及启动调用。path(sessionId) 排队 → live session 捕获 seq 后 flush，或冷会话 observeSession → 将完整版本头和事件写入 exports 临时文件 → rename 原子替换 → 返回既有路径。observe 返回 live 时重新取得 live session 并走 flush。自动 turn/end 和 fork 不调用导出。失败向请求方抛出，保留旧原始文件，后续显式请求可重试。

## 契约层增量 (delta-spec)

- gateway/routing-delivery.md: 删除可读副本 requirement；修改历史导出 requirement 和真人消息 envelope requirement，见 specs/gateway/routing-delivery.md。

## 风险与回退

手动阅读旧副本的用户将看到冻结内容，因此当前说明明确不再维护。原始导出失败不能返回过时文件作为成功结果。回退代码恢复生成；不需要数据回滚。

## 一次性部署迁移

无。

## Runbook for Reviewer

无常驻服务。真实 DSH subprocess fixture 使用临时 home/workspace、测试 provider，并在 finally 关闭进程、删除临时目录，不接触生产。

启动：`pnpm build` 后 `pnpm exec vitest run packages/dsh-integration/tests/history.test.ts packages/dsh-integration/tests/native-human-source.test.ts --maxWorkers=1`。停止：fixture 正常结束自动 shutdown；异常只清理本次 fixture 子进程。

**Review 驱动方式**: 不改客户端面。通过真实 RuntimeClient 的 session.submit / session.observe / session.fork / session.export RPC 端到端驱动 DSH，检查回复、历史、文件和重启恢复；允许 reviewer 增补临时 probe。

**验收前置**: Node 24.22.1、pnpm frozen dependencies，均本机可用；不需要外部模型密钥。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1 | 停止副本生成并保留原生历史 | 无 | 无 | dsh-integration 历史模块/启动/测试，内置说明、gateway 契约 | [reviewer] 普通聊天、重启、fork 与显式导出真实路径通过，副本不存在或旧字节不变；[worker] 先取得自动生成回归红测，移除所有可读写入路径，原始导出持久化切面/并发/失败/冷观察测试通过，构建、相关回归及本地 CI 通过 |
