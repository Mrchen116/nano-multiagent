# bugfix-580：As-built Design

> 本文在实现后根据实际代码与测试整理，不代表事前设计门禁。

## 实现范围

- Base / executed_base: `d87ffa3d19160d45d309f281b0ace4ff92f55a38`（origin/main）。
- Branch: `codex/bugfix-580-task-delete-permission`；提交树见 code-review.md。
- 改动仅涉及任务删除授权、对应测试及行为契约；主 checkout 的既有修改未复制或改动。

## 最终结构与调用链

模型的 task_graph 参数 → 既有 ToolRegistry / auto_mode_gate → TaskGraphTool → TaskGraphBridge → IM task_graph.command → TaskGraphService → 原子删除与回执。

统一权限层保留完整参数和对话上下文判断是否可执行；拒绝时不到达工具网络发送。TaskGraphBridge 继续验证真实 PA session 及已应用工具配置，但不要求删除操作绑定当轮真人消息。IM 保留公司资格、Agent/节点身份、可选来源真实性、revision、子树范围和幂等事务，不再匹配真人消息句式。

删除只用于第二次授权的 source_message_ids 协议字段、Inbox committed_human_sources 查询及其无调用者测试。保留单个 source_message_id 与数据库来源查询，因为创建/修改的发起人和外部渠道来源仍依赖它们。

工具说明允许按会话上下文承接既有授权，不要求用户重述标题、ID 或固定口令。范围不明确时仍应澄清。

## 关键决策

| 决策 | 原因 |
|---|---|
| 删除重复授权，不新增确认票据或布尔参数 | 复用现有统一权限裁决，避免维护第二套授权状态 |
| 保留服务端身份、来源及数据一致性检查 | 用户授权不替代资源访问资格和原子修改约束 |
| 删除无调用者的 Inbox 授权辅助代码 | 不保留退役机制或额外兼容分支 |

## 状态、兼容和回滚

无数据库迁移；图 ID、节点 ID、revision、回执和公开工具业务参数不变。内部 Gateway/IM 删除授权字段同步移除；旧 IM 的口令检查不会被新 Gateway 自动解除，正式发布需更新相关服务。本 PR 不执行发布。若回退产品代码，将重新出现原确认限制，既有任务数据无需迁移。

统一权限仍是可信 Gateway 执行工具的前置；直接内部调用任务服务不是新的用户审批入口。

## 测试策略与验证定位

| 风险 / 既有测试 | 处置与证据 |
|---|---|
| IM 删除再次分析消息措辞：test_company_task_graphs.py | rewrite-merge；无来源、“对”、“直接删！”均能删除；同一场景保留子树范围、稳定节点 ID、过时 revision 和回执重试 |
| Gateway 要求当轮 Inbox 授权：test_global_task_authorization.py | 删除退役协议测试，保护转移至 test_task_graph_bridge.py 的 global / single_thread 无当前消息删除 |
| Inbox 专用授权查询：test_global_inbox.py | 删除唯一退役查询测试；Inbox 消费、完整读取和提交证明的既有覆盖保留 |
| 统一权限失效：test_task_graph_tool.py | 通过实际 Hook loader、Auto gate 和 ToolRegistry 验证 classifier 允许/拒绝决定网络调用，模型裁决用确定性测试替身 |
| WS/服务接线与身份：test_task_graph_api.py | 扩展既有全链路 fixture，失效 Agent 删除拒绝，恢复后通过已认证 WS 删除，浏览器 API 观察图消失，重试相同回执 |

旧实现的 5 个定向场景失败；修复后初轮相关测试 67 passed（含公司任务、Gateway、工具、Inbox、图规则与所有权）。后续完整检查与独立审查结果追加到 code-review.md。

用户实际验收：尚未发生。自动化覆盖不等于生产真实用户旅程；unit 保持 active，PR 明示此状态。

## Canonical 文档影响

最窄修改归入 gateway/task-graphs 与 im/task-graphs；前者权威定义统一权限及自然语言确认，后者链接前者并保留资源与事务边界。对应 delta 位于 specs/。
