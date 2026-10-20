# M1 IM 可信消息事实与授权证据

实施基线：`unit/feat-623`，`2f789f62a`（本地集成 bugfix-621/622）。本记录只证明服务端 fixture 契约，不代表真实模型、飞书平台或生产验收。

## 变更

- `PersonalAgents.sourceFacts` 共用于 source.admit、原文授权/披露 evidence 和 PA 历史查询。可信主人身份独立于 participant/observer；Web 用真实 PA 成员，飞书用当前 enabled channel、绑定 owner/node/agent/app 与 shadow source 核实。
- `source.admit` 移除 role，返回 `is_owner`、`delivery`、`conversation_type`、`channel`，保留 policy_revision / actor_risk。
- observations 保留既有 XML mention / interaction_reply.agent_id 解析结果到事件 `mentioned_agent_ids`，不新增模型 mentions 结构。
- `ownerMessage` 只接受可信主人＋participant＋真实主人私聊或明确寻址群原文。完整 `authorization.owner_messages` 保留所有当前可访问的主人原文；`conversations` 按原会话携带问答上下文，`proposals` 保存这些原会话中实际发表的互动提案。
- `authorization.guard_messages` 只含直接主人输入与明确寻址群输入。PersonalActions.validate 比较该集合；无关 observer 新主人消息不使 permit 失效，直接更正/寻址群更正和既有目标主人已回复检查继续生效。旧 prepared/allowed 没有 guard 时须重新 prepare/review。
- Personal fixture 的 canonical PA chat 改为 direct，以匹配产品创建路径（此前继承 SQL 的默认 group）。

## 验证

1. 先改既有 tests，运行 `pnpm exec vitest run apps/im-server/tests/personal-sources.test.ts apps/im-server/tests/personal-disclosure.test.ts`：4 failed / 17 passed。失败点是旧 role 无新可信事实、授权遗漏观察原文、群明确寻址未被接受。
2. 实现后同两套加 `apps/im-server/tests/personal-agent.test.ts`：3 files / 38 tests passed。覆盖身份冒称、飞书 bound owner/群/重新绑定、真实 PA 成员、群 mention/reply、observer context、guard、旧 permit 更新、目标主人已回复及原披露限制。
3. 补充同会话完整问答与 source evidence 断言后 `personal-sources.test.ts`：8/8 passed。
4. `pnpm --filter @nano/im-server typecheck`：通过。
5. `pnpm exec vitest run apps/im-server/tests`：24 files / 144 tests passed；`node-connection.test.ts` 首次因 @nano/channels 未构建无法导入。构建该依赖后单独重跑：1 file / 5 tests passed。合计原 IM 25 suites /149 tests 已通过，无行为失败。
6. scoped `git diff --check`：通过。

初始测试还遇到 workspace package 未构建；已构建 @nano/product-contracts 和 @nano/channels，仅产生忽略的 lib，无提交。未启动持久真实服务，未发平台消息，未改 Inbox/Global/DSH 或设计文档。
