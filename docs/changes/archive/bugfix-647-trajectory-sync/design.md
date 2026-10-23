# bugfix-647: 轨迹同步增量化 — 技术方案

> 对齐 incident.md

## Changelog

## 现状分析

### 涉及范围

`packages/dsh-integration/src/index.ts` 负责原生后代查询；`packages/personal-assistant/src/global-agent.ts` 负责 durable 根事件、Inbox 和工作投影。

### 既有约束

只在 integration 使用 DSH 已声明公开 exports；不 patch 上游。保护发送重验和 source evidence。不更改 UI、审批与生产配置。

### 可复用能力

采用公开 `sessionPersistence.stat` 的 identity + revision（文档保证相同版本可视为日志未变）、`sessionQuery.observeSession` 的 cursor 与 `projections.values.subagentCatalog`。以真实 observation 的 revision 保存元数据，不能在读取后采样较新 stat 冒充已读版本。沿用 store/inbox 的持久投影与幂等键。拒绝扩大 prepared cache：会保留庞大继承历史。拒绝仅过滤返回值：仍会解压全部历史。

### 相关历史

沿用 feat-630 的根会话连续工作与发送重验；保留现有模型 fallback logicalEvents 和原生工具 presenter。bugfix-644 与 feat-645 不在本 unit 范围。

## 架构与关键决策

1. integration 内新增专用 DescendantReader，缓存每个已读会话的轻量 `{persistenceIdentity, revision, cursor, children}`，不缓存事件/Session/observation。每轮用公开目录投影迭代稳定先序树，visited 防重复；每个冷节点只 stat，版本相同复用目录，只有请求游标与已知 cursor 不同才重新读事件。live 节点先 flush，再 observe；cursor 一致时不物化 events。首次扫描与重启需要恢复目录，成本诚实保留。
2. 请求 cursors 与 modelVersions 共同确认 PA 已完成投影。reader 取得 native observation cut 后，同步调用 handler 回调深拷贝 fallback.list(id)，以该 modelRuns 快照 JSON 的 SHA-256 作为 modelVersion，并决定是否物化 events；从模型快照到事件数组取出之间不再 await。不能在 flush/observe 的 await 之前固定模型状态，避免旧模型快照配到新 fallback turn 并产生不可撤销的错误幂等投影。冷 cache 快路在 stat 后同步判断模型版本；若需重放，取得 observation 后再次捕获并覆盖前一快照。请求 modelVersions[id] 不同则强制重放该 child，即使 native cursor/revision 相同。返回同一快照及 modelVersion，PA 投影成功后同时确认两项。无变化节点返回空 events，变化节点返回全部自有事件，保留跨批工具配对、turn/source/model/usage 与 fallback 上下文；这是按会话增量，而非事件截断。缺少 modelVersions 的旧调用安全地完整重放。throughSeq 只在实际 observation/已验证版本基础上返回。失败不更新缓存；不可读分支沿用 diagnostic，根不可读拒绝。冷版本改变但游标相同仍重新读取目录以核对。服务更换或 session 重新加载不能错误沿用旧目录。第 1 项中的 cursor 复用条件均同时要求模型版本已确认，不能将服务端曾返回视为消费者确认。
3. PA 将根证据 drain 与后代展示 drain 分开。reconcile 仍用于通知/恢复并等待两者；task_graph 和 send_message 仅等待根证据 drain。后代 drain 独立按 root 合并 dirty 通知，失败上报且下次通知/恢复重试；busy 与 stop 同时覆盖两个 drain。projectChildren 不写 NodeStore，不为根证据提供输入；根 durable/Inbox 取证沿既有 binding 路径，保留子调用与 personal send 的既有独立取证/授权路径，不新增 root-only 限制。
4. 保留根事件的既有幂等重放，本次不重写投影引擎。新增 dependency 为同版本公开 dsh-session-persistence，仅 integration 导入；不引入文件格式读取或额外持久缓存。

## 接口与数据流

`session.descendants({sessionId,cursors,modelVersions})` 返回结构保持兼容，events 可为空；通过 reader 返回 child 元数据和已验证 throughSeq，再附 workflowRunId/modelRuns/modelVersion/toolViews。reader 接受按 child 判断是否强制重放的回调，由 handler 负责模型状态快照与版本，reader 不耦合模型业务。catalog 每个节点仅读一次，与事件共用 observation。缓存生命周期为当前 runtime；停机释放内存，无迁移。PA 的 childCursors 与 childModelVersions 仅在该子会话投影成功后同时更新，重启从零回放，inbox 幂等去重。

## 契约层增量

no spec delta：既有连续工作、展示与发送契约不变，修复实现成本与无关等待，不新增用户操作或 SLA。

## 风险与回退

风险是目录失效和上下文截断；公开 revision 检查、无事件缓存、变化会话完整自有上下文及重启覆盖防止静默漏失。首次冷扫描仍有成本。撤回本 PR 即回到旧行为，无数据库迁移。

## Runbook for Reviewer

影响 Node 内的 DSH 与 PA；使用 `./scripts/e2e-up.sh` 启动本 worktree 的隔离真栈，`./scripts/e2e-down.sh` 停止；参数及健康检查按 `docs/development/worktree-runtime.md`。禁止接管生产或其他任务服务。

**Review 驱动方式**：不改客户端面；使用客户端实际接口访问 Agent 工作视图和消息结果，通过隔离真栈确认新增/续写子轨迹与发送。长冷历史性能由合成持久 DSH 会话实验独立量化，不用 mock 时间代表生产。

**验收前置**：现有隔离脚本与测试用 fixture provider 可用；涉及模型语义的原审批/授权保持不变。reviewer 自行核实服务版本与所有权。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-fix | 后代增量同步与业务证据隔离 | 无 | 无 | integration/PA 及相关测试 | [worker] 真实压缩冷历史前后对照，重复同步零冷日志读取；新增、续写、孙会话与重启正确；跨批工具结果保真；同 native cursor 下 fallback completion 的终态和逻辑 turn 正确；未完成子同步不阻塞业务且 root durable 错误仍拒绝。[reviewer] 工作视图显示新子工作及最终工具结果，发送/任务正常并保留新消息重验。 |
