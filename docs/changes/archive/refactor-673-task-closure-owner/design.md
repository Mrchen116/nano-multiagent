# refactor-673: 解散群任务关闭职责归位 — 技术方案

> 对齐: motivation.md

## Changelog

## 现状分析

### 涉及范围

`apps/im-server/src/messaging.ts` 负责会话权限、解散事务、relay 取消与 membership 广播，现持有 task JSON 规则。`task-graphs.ts` 负责 Task 状态、审计、持久化、读投影与执行失效；Gateway 已实例化并通过 ctx.gateway.tasks 提供同一 service，无需新增依赖注入框架。

### 既有约束

保持单个 SQLite transaction，无嵌套 BEGIN、无事务前/内外发。普通 execute/apply 会开启事务、写任务协作消息、receipt 和 activity，不能直接套用。done/closed 保持状态与结果。现有解散对每个图 revision +1（含全完成图）并发布失效，维持此行为。

### 可复用能力

- 用 TaskGraphService.save：统一图 JSON 与 SQL updated_by/revision/updated_at；传入原 row.owner_id，避免丢失存储元数据。
- 用 identity 解析真人显示名，沿普通操作的 `display_name (id)` 和 `{type:'user',id}` 审计表示；不新增 graph updated_by_actor schema。
- 用现有 notifyChange 在提交后发布执行状态失效；用现有 Messaging transaction/membership/relay 取消。
- 不用 execute/apply：副作用和操作上限（100）不适合解散，图可达 500 节点。不新建 Repository/总线/通用 mutation runner。

### 相关历史

feat-584 提供固定会话与只读历史；feat-635 引入 waiting 任务责任；feat-659 关注 Context 生命周期。当前任务执行/生命周期代码有 pauseNode 和 resume_request，不能只机械搬原解散 SQL。来源报告是候选快照，不是接口契约。

## 架构总览

HTTP DELETE → Messaging 授权 → 单事务内冻结会话 + TaskGraphService 关闭持久记录 + 取消 relays → COMMIT → Task 执行失效 + membership 更新。TaskService 不负责解散授权、事务启动或消息外发。

## 关键决策

**新增一个窄的事务内领域命令 `closeForConversationDissolution(conversationId, userId, at): string[]`。**
调用方已经完成 creator/write 检查，并持有相同 db 事务。返回受影响图 ID（包括全完成图），让现有通知路径不再查询 Task 表。不接受 JSON 或节点列表，不增加公开 HTTP/tool action。事务要求写入 docstring，沿已有 executeDelegated 的调用方事务模式。

**在任务领域维护关闭所需完整记录，不泛化所有状态转换。**
未完成节点 status=closed，删除 wait/resume_request；updated_at、updated_by、updated_by_actor 和 change_note 记录真实解散者/原因。修改节点 provenance 设为真人直接操作的空 Agent/source 字段，与普通真人操作一致；created_by、assignee、result、last_chat_id 和 task_node_chat_activity 保留。activity 是发生过任务操作的聊天关联，不为解散伪造对话活动。

候选关闭时清空 selected_candidate_id，保留 selection_reason。仅选项被清空的 done/closed scope 也更新审计，但不改完成状态/结果。其他 done/closed 节点逐字段保留，包括旧历史信息。图统一 revision +1、updated_at=at、updated_by=真人显示名，复用 save 同步 SQL/JSON。所有图共享解散时间。

**不在本操作清理生命周期冻结表或取消真实 Schedule。**
关闭不等于恢复；freeze/schedule 是停用历史控制凭据，与原解散相同保留。移除当前节点 wait/resume_request 即可，不能凭残留关联宣称真实 Schedule 已取消。当前只读/执行快照已排除解散会话。

## 接口与数据流

1. Messaging 检查 conversationAccess.can_write 与 creator_id。
2. transaction 内生成 at，写 dissolved_at，调用 `ctx.gateway.tasks.closeForConversationDissolution(id,userId,at)` 得图 ID，取消待投递 relays。任一步失败全部 rollback。
3. TaskService 内按 conversation_id 读图；解析 user 身份；关闭/清空选项并更新对应节点审计；保存每图；不调用 messaging、execution hooks、BEGIN/COMMIT、receipt 或 activity。
4. 成功提交后逐图 `notifyChange(undefined,graphId)`，再 membership；notifyChange 保持现有断线容错。无图时仍更新 membership，无 Task 通知。

## Context 消费影响与验证

Consumer 是通过 task_graph get 查询历史的 Agent，以及任务执行列表消费者。按需 get 从持久节点投影，更新后 closed 节点不再携带旧 wait/resume_request，修改者为真人（before: Agent (a)/agent a；after: Human (u1)/user u1）。既有历史消息不改写，不生成新任务消息；任务执行失效在 COMMIT 后，重读不包含已解散责任。权限、工具定义和提示词不变。

验证最低链路：真实 Gateway task_graph.command/get 的序列化响应 + HTTP 历史读 + 提交后 executionSnapshot；独立审查检查现有工具 renderer 是否原样交付这些记录。此次不改变模型决策指导，不运行真实模型语义评价，不能把协议证据声称为真实模型行为成功。

## 契约层增量 (delta-spec)

- `specs/im/task-graphs.md` → `docs/specs/im/task-graphs.md`，补充解散修改归因/清除旧等待与恢复信息；聊天既有解散语义无增量，不重复维护。

## 风险与回退

主要风险是嵌套事务、保存多图时部分成功、误生任务消息、遗漏完成 scope 的选项审计。以真实 Messaging 入口和 SQLite 触发器故障注入验证回滚，以通知 hook 重读验证提交后。保持已有全完成图 revision 语义。回退本提交无需数据转换。

## 一次性部署迁移

无。只修正未来解散；历史缺少可靠解散者，不猜测补写，不提供生产修复脚本。

## Runbook for Reviewer

客户端面不变，使用客户端实际 HTTP DELETE/GET 与任务写入接口代驱动真实 IM 进程，辅以真实 WS Gateway 查询核对模型侧序列化结果。无需前端原型或双端模拟器。隔离 IM 是本单元唯一改动的常驻服务；无 LLM 依赖。

标准 daily 栈可用 `./scripts/e2e-up.sh --profile daily` / `./scripts/e2e-down.sh`；本单元无 native 执行变化，可复用 `apps/im-server/tests/e2e/helpers.ts` 的隔离 IM 真进程启动（端口 0、临时 SQLite、独立 JWT、测试用户），其 cleanup SIGTERM 并删临时数据。独立 reviewer 用同一 HTTP 接口自行走场景，不以单测通过代替观察；服务地址、PID、证据留本机。健康检查 GET /health（或登录成功）。验收前置：锁定依赖已安装，Node 24.22.1。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-task-closure | 事务内关闭与审计一致性 | 无 | 单阶段 | messaging.ts、task-graphs.ts、既有 task-execution/e2e conversation-tasks 测试 | [reviewer] 三项 Requirement 的真实 HTTP 历史/授权/无消息旅程通过；[worker] wait/resume/审计与 SQL/JSON 一致，完成节点/选项规则保持，多图失败完整回滚且不发布，空/全完成图兼容，真实 WS get 序列化记录正确；窄测试、typecheck 与 CI 通过 |
