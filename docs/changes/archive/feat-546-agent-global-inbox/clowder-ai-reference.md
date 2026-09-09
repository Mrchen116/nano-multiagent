# Clowder AI：独立 Thread 会话之间的显式通信

调研日期：2026-09-09。依据本地 `/Users/czj/Repos/opensource-hub/clowder-ai` 的 `main`，HEAD 为 `6b6fbbaa863ced704081f0ddc718d797b619f8c2`（提交日期 2026-09-07）。未拉取远端，不声称这是上游最新版本。参考仓库已有暂存改动和未跟踪内容，本轮均未修改；下述关键文件不在所见改动清单内。

本文是文档与源码阅读结果，未启动服务或执行跨 Thread 实测；测试文件仅作为已有断言的补充证据。本单尚未选择该方案。

## 结论与概念

Clowder AI 已有跨 Thread 设计，核心是**独立工作会话之间显式传话、按需查阅背景，并携带准确的回信地址**。它没有把同一只猫的所有 Thread 合并成一个全局 Session。

- Project 对应工作目录；Thread 是独立对话／工作流，可有多只猫参与。
- Cat 是 Agent 的身份；同一 catId 可以出现在不同 Thread。
- Session 是某用户、某只猫在某个 Thread 下的工作上下文。
- Session Chain 是该猫在该 Thread 内先后使用的会话序列，不是跨 Thread 的共享会话。

概念来源：[Project / Thread 决策](/Users/czj/Repos/opensource-hub/clowder-ai/docs/decisions/003-project-thread-architecture.md)、[F052 身份隔离](/Users/czj/Repos/opensource-hub/clowder-ai/docs/features/F052-cross-thread-identity-isolation.md)。代码证据以以下各节为准。

```text
Thread A                        Thread B
├─ codex → Session A-codex      ├─ codex → Session B-codex
└─ opus  → Session A-opus       └─ opus  → Session B-opus

Session A-codex ── 显式跨 Thread 消息 ──→ Session B-codex
                 ←── 指定来源的回信 ──
```

图中的两只 codex 具有相同 catId，但工作上下文不同。需要把“Thread A 的 codex”与“Thread B 的 codex”区分开，否则接收方可能将跨 Thread 消息误认成自己之前说过的话。

## 会话隔离的实际代码

`SessionManager` 的内存索引使用 `userId:catId:threadId`，持久存储接口也同时接收这三个维度。实际调用路径在 `invoke-single-cat.ts` 中使用 `sessionManager.get(userId, catId, threadId)` 恢复会话，并用同样维度保存运行时 session ID。这是当前调用代码中的隔离，不只是历史设计文字。

证据：[SessionManager](/Users/czj/Repos/opensource-hub/clowder-ai/packages/api/src/domains/cats/services/session/SessionManager.ts:31)、[调用时恢复 Session](/Users/czj/Repos/opensource-hub/clowder-ai/packages/api/src/domains/cats/services/agents/invocation/invoke-single-cat.ts:2198)。

`SessionChainStore` 提供按 catId、threadId 查询 active session 和完整 chain 的接口，支持封存、续接与轮转。`handoff/compress/hybrid` 配置讨论的是这些会话的生命周期策略，不是“单 Thread／全局”的作用域选项。[Session Chain 接口](/Users/czj/Repos/opensource-hub/clowder-ai/packages/api/src/domains/cats/services/stores/ports/SessionChainStore.ts)、[F033 策略说明](/Users/czj/Repos/opensource-hub/clowder-ai/docs/features/F033-session-strategy-configurability.md)

## 跨 Thread 消息如何走通

常规 invocation 调用路径使用 `cat_cafe_cross_post_message` 指定目标 Thread，以及目标猫或有效提及。发送后消息属于目标 Thread，并携带来源信息；不会复制来源 Thread 的完整上下文。

已核对的路径：

1. **显式寻址**：跨 Thread 工具有目标 `threadId` 和 `targetCats`。普通 `post_message` 对 invocation 身份拒绝显式 Thread 参数，引导使用专门的跨 Thread 工具。长期 agent-key 身份有另一套明确寻址规则，不能与 invocation 路径混为一谈。[工具定义与边界](/Users/czj/Repos/opensource-hub/clowder-ai/packages/mcp-server/src/tools/callback-tools.ts:779)
2. **保留出处**：API 在跨 Thread 投递时记录 `sourceThreadId`、`sourceInvocationId`，并将消息存入目标 Thread。[投递代码](/Users/czj/Repos/opensource-hub/clowder-ai/packages/api/src/routes/callbacks.ts:3149)
3. **目标猫触发**：目标猫进入 A2A 的投递／工作队列路径。跨 Thread 情况不会仅因发送者与接收者 catId 相同而当作自引用过滤。[目标解析](/Users/czj/Repos/opensource-hub/clowder-ai/packages/api/src/routes/callbacks.ts:3042)、[A2A 入队](/Users/czj/Repos/opensource-hub/clowder-ai/packages/api/src/routes/callback-a2a-trigger.ts:181)
4. **接收方拿到回信信息**：系统从触发消息的结构化字段提取来源 Thread 与发件猫，再交给 invocation context。F193 专门修复了“处理了内容，却只在自己的 Thread 回复，来源 Thread 收不到结果”的问题。[元数据提取](/Users/czj/Repos/opensource-hub/clowder-ai/packages/api/src/domains/cats/services/stores/ports/MessageStore.ts:2173)、[路由注入](/Users/czj/Repos/opensource-hub/clowder-ai/packages/api/src/domains/cats/services/agents/routing/route-serial.ts:1125)、[F193](/Users/czj/Repos/opensource-hub/clowder-ai/docs/features/F193-cross-thread-comm-unification.md)

例如 A 的 codex 向 B 的 codex 通知接口变化，B 应知道这是另一个工作上下文发来的信息；需要反馈时，要将消息送回 A 的 codex，而非只在 B 内 @codex。已有测试覆盖结构化来源提取及缺失来源时不凭空生成提示：[回信提示测试](/Users/czj/Repos/opensource-hub/clowder-ai/packages/api/test/hydrate-cross-thread-reply-hint.test.js)。本轮没有运行该测试。

## 连续性、检索与协作约束

独立 Session 不意味着完全信息隔绝。`SessionBootstrap` 可读取当前 Thread 的滚动记忆、此前 Session 的摘要及任务信息；标题驱动的项目知识召回在当前代码中只给模型候选指针，明确不将命中标题和摘要直接塞入 prompt。[Bootstrap](/Users/czj/Repos/opensource-hub/clowder-ai/packages/api/src/domains/cats/services/session/SessionBootstrap.ts:236)

仓库的跨 Thread 协作指南要求先发现相关 Thread，必要时用 evidence 搜索或 `get_thread_context` 补充背景，再决定投递。它还区分消息送达、需要语义回复、工作责任转移，避免将任何传话都当成新任务授权。这属于项目的行为指导；不能据此断言每一条要求都有运行时强制保证。[协作指南](/Users/czj/Repos/opensource-hub/clowder-ai/cat-cafe-skills/cross-thread-sync/SKILL.md)

## 设计阶段补查：聊天发现、分层读取与精确确认

2026-09-09 再次只读核对同一 `6b6fbbaa8` 基线，未运行参考服务。侧聊转达的源码位置已在本任务重新检查；下述机制作为适配候选，不将 Clowder 的完整产品语义引入 nano。

### 找到目标后，有界地读所需内容

- `cat_cafe_list_threads` 返回 Thread ID、标题和活动时间，支持按 keyword 查标题／ID及 activeSince 过滤最近活动。
- `cat_cafe_get_thread_context` 接收明确 threadId，支持分页、关键词，以及 messageId 周边窗口。`anchor` 与 `full` 是两种不同读取粒度；返回 `threadId/messages/hasMore/nextCursor`，预览可附下一步完整读取指针。
- 工具描述明确有界关键词扫描可能遗漏更早匹配（`scanCapped`），超预算单项可能降为 anchor；不能把摘要或截断表述为已读取完整正文。

证据：[工具声明](/Users/czj/Repos/opensource-hub/clowder-ai/packages/mcp-server/src/tools/callback-tools.ts:3364)、[列表声明](/Users/czj/Repos/opensource-hub/clowder-ai/packages/mcp-server/src/tools/callback-tools.ts:3458)、[查询 handler](/Users/czj/Repos/opensource-hub/clowder-ai/packages/mcp-server/src/tools/callback-tools.ts:1210)。这些可帮助 nano 细化 `conversations` 的发现／按需阅读，而非要求本期照搬全部筛选参数或专用 SOP 工具。

### 只确认本页实际完整返回的排队正文

`callbacks.ts` 先对预算和分页后的候选计算 `fullPublishedIds` 与 `returnedQueuedEntryIds`，据此得到 `fullyReturnedQueuedEntries`。后续只对这些条目调用 `markQueuedSeen`，并通过 custody coordinator 持久记录。只返回 queued body 的摘要不会进入该完整正文确认集合。

另有已发布消息的 `seenCursor`：代码按 visibility sequence 扫描，从已有游标起只连续跨过本页已经看到的相关消息；遇到未读且相关的消息即停止。这样即使迟到消息的发生时间更早，也不会因时间分页跨过它而误报已读。

证据：[完整返回集合](/Users/czj/Repos/opensource-hub/clowder-ai/packages/api/src/routes/callbacks.ts:4460)、[连续游标推进](/Users/czj/Repos/opensource-hub/clowder-ai/packages/api/src/routes/callbacks.ts:4576)、[循环中的未读停止分支](/Users/czj/Repos/opensource-hub/clowder-ai/packages/api/src/routes/callbacks.ts:4633)、[逐条确认与持久记录](/Users/czj/Repos/opensource-hub/clowder-ai/packages/api/src/routes/callbacks.ts:4713)。

### 不能直接复用的语义

Clowder 的历史工具承担部分 queue 与 freshness 状态更新；anchor 对已发布消息也可能推进 preview-read seenCursor。因此不能说“它的所有摘要查询都无副作用”，也不能说它已经实现 nano 的 `conversations` 完全只读／`inbox.read` 才确认的分工。

可借鉴的是完整返回范围、稳定消息身份和不跨未读空洞的规则。服务端记录“已返回”仍不证明正文进入模型可恢复的工作记录；nano 的持久摄取提交位置仍需独立设计。

## 与另外两个参考的关系

| 维度 | Clowder AI | Raft | Claude Tag |
|---|---|---|---|
| 持续上下文边界 | user × cat × Thread，各自可有 Session Chain | 每 Agent 一个持续 Session | 频道 Session，加各工作 Thread 的 Session |
| 跨讨论手段 | 显式消息、来源与回信提示、检索 | 同一 Agent 跨讨论按需拉取收件箱 | 共享记忆、检索与在途工作路由 |
| 对本单的借鉴点 | 消息必须知道从哪里来、回哪里去 | Agent 自主选择摄取哪些通知 | 相关更新可以接续已有工作 |

Raft 与 Tag 的来源分别见 [Raft 参考](raft-reference.md)、[Claude Tag 参考](claude-tag-reference.md)。表中借鉴点是分析建议，不是 feat-546 已确认范围。

本轮未找到足以将 Clowder 的上述投递路径称为“Raft 式全 Agent 主动拉取收件箱”的证据；也未验证全部 runtime 的忙时抢占、队列恢复和并发保证。F193 仍有未完成阶段，不能把整份 feature 文档都当作已实现结果。
