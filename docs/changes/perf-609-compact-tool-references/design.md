# perf-609: As-built Design

> 本文在实现后根据实际代码与测试整理。路径为用户明确选择的快速开发；未补造事前 Gate 1/2、milestone 或产品验收。

## 实现范围

- Base: `247ae97ae358b66d7637b1cdfd5f910bf1a06cc9`。
- Branch: `codex/compact-tool-references`。
- Head/完整 dirty 范围：见 [code-review.md](code-review.md)，最终提交由 Git 记录。
- 受影响模块：PA 工具边界与持久化 Inbox、DSH integration 中本仓的 global-mode 图片来源和 Workflow。

## 最终结构

### 组件与职责

`NodeStore.toolReferences` 在 owner-bound Node 数据库保存 `(reference, agent_id, kind, value)`。`ToolReferences.arguments/result` 只处理已知工具的结构字段，不递归改写用户正文、任务内容、原生 schedule/subagent 身份或任意对象。

- 飞书 target 使用 `c_f_<8 hex>`；与 IM 的 `c_<8 alphanumeric>` 分离，避免短引用被误当普通 IM 目标。
- cursor 使用 `p_<8 hex>`；按 Agent 和工具名称隔离。原游标及其服务端查询绑定完整保留。
- 生成时检查持久化唯一键；重复输出复用原映射。
- Workflow 新 ID 使用 `wf_<8 hex>`，检查 live 与 recovered 运行集合；旧 UUID 仍按既有读/控路径定位。

### 调用链与数据流

1. `GlobalAgent.call` 先验证宿主绑定的 owner/Agent/session，再解析短引用。
2. 原 Inbox、会话查询、投递和任务图链路继续执行权限、成员、未读复核和幂等检查。
3. 普通结果在返回模型前投影。发送回执的持久记录不改写，结果相同的 `target/conversation_id` 只返回前者。
4. Inbox read 的投影在保存 `reads.body/digest` 前进行，保证消费证明验证的是模型实际收到的精确 body。`target` 移至页顶层，每条消息仍保留 message ID、sender、time、partial/content 等来源证据。
5. `inbox.image` 用 message_id 与 URL 从已保存页面派生可信来源，再解析为原 conversation ID；完整来源通过宿主 RPC 交给 trajectory attachment 存储，不进入模型正文。同页复用 URL 仍分别保留两条真实消息来源；旧页面的 per-message target 仍可读取。
6. `inbox_read_committed` 工作投影把短 target 还原为真实 conversation ID，保留工作记录/消息关联。
7. Workflow 工具的 read/control 单独剔除 parentSessionId/inputIds/budgetId、calls.key、attempts.id；内部 engine/RPC、预算、重放、持久记录和 UI 数据不缩减。

### 状态、数据与兼容性

工具引用跟随 Node 数据库持久化，不建立新配置或独立服务。完整旧 target 和 Base64 cursor 继续直通原处理器。短引用未知、属于其他 Agent 或另一工具时明确失败，不猜测目标。服务端仍校验游标所绑定的会话、查询和筛选条件。

旧 Inbox read 以原 body 重放；准备和消费检查仍以该次保存的精确 body 为准。旧 Workflow UUID 继续可用；本次不批量迁移旧运行，也不改变 DSH 自有 session identity。

## 关键决策

| 决策 | 原因与约束 | 代码定位 |
|---|---|---|
| 在 PA 模型工具边界映射 target/cursor | 避免迁移聊天、消息、IM 快照和授权真源 | `packages/personal-assistant/src/tool-references.ts` |
| 将 projected Inbox body 持久化后再消费 | 不能缩短输出后破坏精确摄取证明 | `packages/personal-assistant/src/inbox.ts` |
| 独立保存完整图片来源、工作来源 | 短引用不能改变 viewer 鉴权和来源关联 | `global-agent.ts`、`packages/dsh-integration/src/global-mode.ts` |
| 只缩短本仓新建 Workflow ID | 控制所有权/恢复仍使用原已持久化键，不改 DSH 内置标识 | `packages/dsh-integration/src/workflow/engine.ts` |
| 模型投影与内部运行记录分离 | 保留预算、重放与 UI 的字段需求 | `packages/dsh-integration/src/workflow/tool.ts` |

## 失败路径、风险与回滚

- 映射写入失败时不把未持久引用返回模型；原聊天/投递事实保持不变。
- 引用不是授权；跨 Agent、跨工具、原查询 scope 错误仍拒绝。
- 不删除历史来源 ID；不能简单移除 sender/message 身份以省 token。
- 短引用和快照具有同一宿主持久数据生命周期，不实现独立 TTL/清理策略。
- 回滚边界见 motivation；DSH 内置 schedule/subagent 不在改动范围。

## 与初始意图的差异

格式示例非固定协议：飞书用 `c_f_` 前缀确保不与内置 IM 命名空间混淆。Workflow 的短 ID 从新运行开始，历史运行保留 UUID，不做破坏性重命名。

## 验证定位

- 用户验收：待用户实际确认；本地自动化不替代生产/飞书实机验收，未部署。
- 初次窄验证：6 文件 / 46 测试通过。
- 补来源投影验证：`packages/personal-assistant/tests/tool-references.test.ts` 3 测试通过。
- 本地全量：`pnpm test`，83 文件 / 312 测试通过；`pnpm -r --if-present build`、`pnpm typecheck` 通过。
- `git diff --check` 通过；56 Python 测试、docs-check、ruff check/format 和安装包候选构建通过。
- 独立 review 的同页图片 URL 复用问题已修复；修复后 6 文件 / 43 测试通过，独立 closure 无剩余 findings。完整证据见 [code-review.md](code-review.md)。
- 字符 benchmark 见 motivation，不宣称实测 token 或生产费用下降。

### 测试策略与既有覆盖

| 风险 | 测试归属与处置 | 原因 |
|---|---|---|
| 引用跨重启、跨 Agent/工具、旧引用、图片/来源与投递接线 | 新建 `packages/personal-assistant/tests/tool-references.test.ts` | 新模型边界回归；通过真实 SQLite 与 GlobalAgent 公共调用验证，不重复 IM 服务端自身的权限实现测试 |
| 未读复核 | `global-agent.test.ts` rewrite-merge | 原测试继续验证 canonical unread targets，兼容模型短引用 |
| 精确 Inbox 摄取、分页快照 | `inbox.test.ts` keep | 不削弱底层消费证明 |
| 真实 Workflow 执行、恢复、预算、模型结果 | `workflow-native.test.ts` 扩展；lifecycle/control/budget keep | 在现有真实 DSH fixture 验证工具结果投影，内部运行事实仍完整 |

## Canonical 文档影响

最窄 delta 位于 `specs/gateway/global-agent.md` 与 `specs/gateway/workflows.md`。用户实际验收后按 fast-close 归并和归档；当前不覆盖 current spec。
