# refactor-673 Code Review

## Round 1

- review_mode: `full`
- reviewer: 独立静态 reviewer；未参与受审设计或实现。
- skills: `change-code-review`；`agent-context-review` Mode B / Implementation Review。
- executed_base: `ff326c351d104447028f4b185740ab6d6be55de6` (`origin/main`)
- validated_at: `7a77516c0dfd7a0b41d838b193bc5ca9318397d5`
- product/test head: `ff9a2a39f`；其后仅增加本 unit 验证记录。
- checkout: `/Users/czj/.codex/worktrees/task-closure-owner/nano-multiagent`，`codex/task-closure-owner`；开审 clean。
- completed_at: `2026-10-28T03:02:56Z`（报告写入前取证时间）。

## Findings

```json
[]
```

无有证据支持的存活正确性、架构或 Context 缺陷。

## Coverage

- 审查完整 base..head：两处产品文件、两个既有测试文件、首文档/design/delta/design-review/validation；沿真实 HTTP DELETE、Gateway 初始化、领域 save/get/list、执行失效及 renderer 检查接线。
- `messaging.ts:713-725` 保留写资格与 creator 检查；同一 `context.ts:31-40` 事务覆盖 dissolved_at、所有图及 relay 取消。新命令不另启事务、不产生消息，返回图 ID 后才调用 notifyChange/membership。第二图保存失败会回滚先前写入，成功更新不提前发布。
- `task-graphs.ts:917-942` 关闭全部非 done/closed 节点，删除 wait/resume_request，更新真人审计与直接操作 provenance。创建者、负责人、结果、层级、last_chat_id、selection_reason 保留。done/closed 仅在选项清空时更新审计，其他已完成节点字段不变；全完成图仍按既有规则增加 revision。
- `save`（`task-graphs.ts:1006-1039`）复用统一 SQL/JSON 写入，传入存储 owner_id。所有节点已终态，不触发新增活跃责任的配置保护，也不伪造 task activity/receipt。
- Gateway 使用同一 db/messaging 创建唯一 TaskGraphService（`gateway.ts:47-70`），无跨包依赖变化、DSH private import、运行时副本或新调度机制。
- 复用 `M1-task-closure/evidence/validation.md` 的版本化证据，并实际读取 `/tmp/task-closure-green.log`、`/tmp/task-closure-red.log`：3 files / 21 tests green；旧实现分别暴露 Agent 图审计残留和完成 scope 选项变更未更新时间。未重复运行主 Agent 正在执行的全量 CI。
- 测试沿既有责任 owner 扩展：真实 Messaging/SQLite 验证 101 节点、wait/resume、完成记录原样保持、图 SQL/JSON 审计、无新消息/receipt/activity、提交后重读；SQLite trigger 验证第二图失败完整回滚；真实 IM HTTP/WS 验证权限、历史只读、选项审计和协议序列化。task-collaboration 保留不同协作风险，没有新建平行测试文件。

## Agent Context Implementation Review

### Surface、交付与失效

触发理由：持久任务 get 的节点当前事实及执行责任失效发生变化。Consumer 是按需读取历史任务的 Agent，以及在下一步骤重新核对责任的执行消费者；并非新增 Prompt、Skill 或工具动作。

1. 宿主从已认证 HTTP 请求取得 userId，经 creator/write 校验后传入领域命令（`messaging.ts:860-869,713-720`）；模型无新增必填参数，无法通过本工具伪造解散者。领域记录 `{type:'user',id:userId}` 及实际显示名（`task-graphs.ts:918-936`）。
2. get 在固定会话 ACL 下投影节点与修改者（`task-graphs.ts:1090-1125`），不丢弃 closed、change_note、updated_by_actor；已删除的 wait/resume_request 不会由投影恢复。Gateway `task_graph.result` 交付真实 get 结果（`gateway.ts:480-513`）。
3. 实际进程 WS 证据来自 `conversation-tasks.test.ts:46-48` 及 validation：revision=3、conversation.can_write=false、closed 子节点的 user/alice 修改者与解散时间。此为协议序列化证据，不是模型输入捕获。
4. 对未改消费链另作静态核对：`global-agent.ts:482-520` 原样包装 result，`tool-references.ts:111` 仅处理顶层列表游标；`packages/dsh-integration/src/features/task-graphs.ts:30` 的 output.render 使用 JSON.stringify(result)。现有指导要求 Schedule 重读事实，不能重开 closed/done/in_review（同文件 `:16-17`）。没有组合后冲突或授权升级。
5. assignee 保留，notifyChange 可在提交后找到原责任主体（`task-graphs.ts:978-988`）；executionSnapshot 仅返回 doing/waiting 且会话可写的责任（`:598-610,862-865`）。测试回调直接验证 transaction=false、责任为空。integration 的既有下一步机制仍同步责任撤回且不为同步单独启动空闲执行（`packages/dsh-integration/src/task-execution.ts:125-145`）。

### 限制

未捕获真实 provider 请求，未运行真实模型任务，也未验证所有模型、多轮或恢复行为；此次无需改变的 renderer/下一步组装链为静态证据。实际捕获到的 WS 响应与受控 Schedule inspection 不等于模型语义成功或生产 Schedule 取消。独立产品验收和完整 CI 由 caller 汇总，本报告不替代这些门禁。
