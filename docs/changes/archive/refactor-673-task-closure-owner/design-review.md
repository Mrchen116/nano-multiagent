# refactor-673 Design Review

## Round 1

### Metadata

- reviewer target: `/root/design_review`，独立于设计作者的 Gate 2 reviewer。
- review_mode: `full`。
- mode_reason: 首轮设计审查，完整核对 motivation、design、delta-spec、M1 骨架及实际消费链；同时执行 agent-context-review Mode A / Design Review。
- started_at: `2026-10-28T10:52:30+08:00`（首个显式时钟取证点；初读在此前开始）。
- completed_at: `2026-10-28T10:55:26+08:00`。
- duration: 显式取证时钟窗口 2 分 56 秒；包含此前初读的总耗时未单独计时。
- validated_at: `be46c6e6276d4a91f0deec4d4400ff5b9b988163`。
- executed_base: `a34af8473c15f1145d6a1dbbc036bc320560f351`，审查时本地 `main`。
- checkout: `/Users/czj/.codex/worktrees/task-closure-owner/nano-multiagent`，`codex/task-closure-owner`；初始 clean。受审差异仅含 motivation、design、delta 和 `M1-task-closure/.gitkeep`。
- 同步边界：收尾时 `origin/main` 已更新到 `ff326c351`，受审分支尚未同步；核对 `a34af8473..origin/main` 的 task-graphs.ts / messaging.ts 无差异。后续仍须针对实际同步 delta 执行门禁失效判断，本轮不预先声明对新基线有效。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

方案能在当前架构内兑现目标。此结论是实施前设计判断，不代表新实现、真实 HTTP/WS 旅程或模型行为已经验收。

### Coverage 与证据

#### 现状与产品入口

- 实际 HTTP DELETE 入口位于 `apps/im-server/src/messaging.ts:867`，经用户认证、会话写资格和 creator 检查后调用 `dissolveConversation`；其当前实现（`:713-733`）直接遍历 task JSON，只更新未完成节点状态/时间、选项及图 revision/时间，确实没有清理 wait/resume_request 或刷新审计主体。
- 普通领域写入在 `apps/im-server/src/task-graphs.ts:595-600,682-690,810-848` 维护可信主体、provenance、恢复意图及持久化。`pauseNode`（`:906-909`）也显式删除等待和恢复信息。现状缺陷不是仅凭来源报告推测。
- Web 详情读取 `updated_by`（`src/IM/frontend/src/features/tasks/task-graphs-page.tsx:115`）；iOS 优先显示 `updated_by_actor`（`src/IM/ios/NanoIM/Features/Tasks/TasksView.swift:450`）。两端等待区域均受 waiting 状态控制（分别 `:105`、`:404`）。设计只修记录及投影，不宣称已有可见的双重状态、Schedule 误执行或新 UI 交互，符合实际影响边界。

#### 职责、依赖与事务决定

- `Gateway` 已以同一 `ctx.db`/`ctx.messaging` 组装唯一任务服务与 execution hooks（`apps/im-server/src/gateway.ts:50-70`）。由 Messaging 保留 creator 授权、会话冻结、relay 取消和整体事务，TaskGraphService 承担节点关闭规则及持久一致性，符合 `SPEC.md` 的 IM 产品权威与包依赖边界，无需新增跨包依赖。
- 不复用 `execute` 是正确取舍：它自行 BEGIN/COMMIT 并在提交后发布任务消息（`task-graphs.ts:461-480`）；普通 executeTransaction 还写 receipt、任务通知与 activity（`:848-858`），与解散的既有静默契约不同。已有 `executeDelegated`（`:564`）说明调用方拥有事务并非新的架构模式。
- 窄命令只接收 conversationId、可信 userId 和统一时间，返回图 ID；无需调用方理解节点或 JSON。复用 `save`（`:968-999`）能同步 SQL/JSON 的修改者、revision 和时间，且方案明确传回原 row.owner_id，避免 INSERT/UPSERT 缺少存储元数据。保存时所有节点已处于 done/closed，不会由 save 的活跃责任保护引入额外工作。
- `context.ts:31-40` 的同步事务可以覆盖会话、多个图和 relay 取消；领域命令不启动事务、不发消息。提交后 `notifyChange` 从保留的 assignee 收集负责人并容错发布（`task-graphs.ts:941-950`），返回图 ID 消除了 Messaging 再查 Task 表的职责泄漏。
- done/closed 节点通常逐字段保持；只有当前选项被清空时更新对应 scope 审计。保留 selection_reason、结果、创建者、负责人、last_chat 与旧 activity，不伪造新的任务讨论。全完成图仍 revision +1，保持当前解散行为。保留生命周期冻结凭据与真实 Schedule、仅清当前节点 wait/resume_request，是有界修复，没有增加一套跨运行时清理机制。

#### 需求、delta 与 milestone

- motivation 的三项 Requirement 均有明确落点：历史只读/完成事实、可信真人修改归因、无新任务消息且提交后失效。非创建者与事务失败不发生部分变更；无图、全完成图、多图以及仅选项变更均已列入设计或 M1 退出条件。
- delta 准确锚定 `docs/specs/im/task-graphs.md` 的“群任务视图记录本群创建及编辑的节点”，保留该 Requirement 全部四个既有 Scenario，仅在解散历史段增加审计与状态信息清理。与 `docs/specs/im/conversations-messages.md:410-423` 的创建者解散、历史和消息契约相容；不重复新增聊天治理规则。
- `M1-task-closure/.gitkeep` 存在，符合设计阶段仅建骨架要求。单阶段范围明确，关闭语义、原子性、读投影和验证相互依赖，不需机械拆成并行层次。没有 schema、历史数据迁移或部署动作，省略 deployment-prompt 合理。

#### Agent Context Design Review

- 触发 Surface 是按需 `task_graph get` 返回的当前事实和执行责任失效，而非提示词改写。来源 owner 是 TaskGraphService；解散者由认证 HTTP 请求传入，模型不提供身份。历史权限仍由固定会话 ACL 决定（`conversation-access.ts:29-44`），设计没有扩大 Agent 可见范围或将系统事件当作新真人授权。
- `get` 保留节点字段并解析审计身份（`task-graphs.ts:1054-1085`）；Gateway 包装为 task_graph.result（`gateway.ts:479` 起），PA `global-agent.ts:482-520` 仅转交结果，`tool-references.ts:111` 仅处理列表游标，integration 工具 `output.render` 对结果执行 JSON.stringify（`packages/dsh-integration/src/features/task-graphs.ts:26-29`）。因此 closed、wait/resume_request 的缺席及真人修改者能沿既有路径实际交付，不需要新增工具参数或发现入口。
- Before/After 足够明确：之前 Agent 审计与旧 wait/resume 信息可能随已关闭节点返回；之后只对发生修改的节点返回真人审计、解散原因和已关闭事实，旧消息仍作为历史保留。现有 Task 指导要求调度先重读事实、不能重新打开 closed（同文件 `:16-17`），与新记录一致。
- 执行读取只纳入 doing/waiting 且会话 can_write 的责任（`task-graphs.ts:601-610`）；PA snapshot 继续投影该结果（`packages/personal-assistant/src/task-execution.ts:38-53`），integration 在下一步骤对齐撤回事实（`packages/dsh-integration/src/task-execution.ts:130-145`）。提交后失效沿用现有行为，关闭不会依靠旧 resume_request 重新成为有效责任。
- 设计要求真实 WS get 序列化、HTTP 历史读取以及提交后 executionSnapshot，结合上述未改 renderer 的静态核对，是此次字段修复的最低有效证据。没有新模型选择策略，暂不要求真实模型语义评价；仍不得把 WS 响应、测试 stub 或源码核对称为真实 provider 输入/模型行为成功。

#### 验证可执行性与限制

- 既有 `apps/im-server/tests/e2e/conversation-tasks.test.ts:4-43` 已通过实际 HTTP 与 Agent WS 入口覆盖群权限、解散后历史和选项保持；可在同一 seam 扩充真人归因、任务消息计数与非法解散。`tests/task-execution.test.ts:156-167` 有提交后重读 seam，设计提出多图 SQLite trigger 故障注入，可验证整体回滚与失败不通知。
- `tests/e2e/helpers.ts:71-123` 确实启动真实 IM 子进程，使用临时数据库、端口 0、隔离 JWT，并在 cleanup SIGTERM/删除临时目录。无需为纯 IM 记录变化启动生产服务、真实模型或原生客户端；独立产品 reviewer 仍须亲自驱动 HTTP 场景，不以单测结果替代验收。
- 本轮未运行实现测试、真实服务或真实模型；这些是 M1 退出证据，尚未完成。前端字段消费仅作静态核对，没有声称完成渲染画面验收。本单元不改布局/交互，不需原型或前端 must-match。

### 历史问题闭环

首轮，无历史 issue 或 Author Resolution。

### Issues

无。

### Recommendations

- **R1-R1（可选）**：可在既有服务测试中用一个超过 100 节点的合法图覆盖解散，以守住“不复用 apply 操作上限”的设计理由；无需增加真实模型或大规模 E2E。

### Author Resolutions

- 无 Issues；主 Agent 核实职责、事务与消费证据后接受 Approved。
- R1-R1 accepted：在既有 task-execution 测试扩展图节点数量超过 100，保护批量关闭不受普通 apply 上限影响，不新增平行测试文件。
- 计划同步 origin/main ff326c351：main 增量未改 Messaging/TaskGraphService/对应消费投影；相关 product-contracts 增量为 Node 更新契约，PA 默认指导与 E2E 工具变化不改变本设计。Gate 2 retained；实现与后续门禁基于同步后版本。
