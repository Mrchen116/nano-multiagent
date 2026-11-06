# feat-723: Code Review

## Review scope

- Base / executed_base: `005a36057`（origin/main）。
- Review mode: `full`。
- Branch: `unit/feat-723`。
- Included dirty files: 本 unit 对 base 的全部 diff，含 `apps/im-server`、`apps/node`、`packages/product-contracts`、`src/IM/frontend`、`src/IM/ios` 的改动与本 unit 文档；主仓里用户自己的未提交改动未复制。
- Head: 本 unit 分支的实现提交。

## Round 1

- Status: 4 个 CONFIRMED、2 个 PLAUSIBLE；其中 3 个已在实现侧修复，1 个补测试，1 个确认为非问题，1 个作为已知升级窗口影响记录。
- Reviewer: 独立 reviewer，只读审查 base..head 全量 diff。

### CONFIRMED 1：PA 在途创建请求重放会 409

- 事实核对：`personal-agent-creation.ts:67` 用 `sortedJsonUtf8(parseConfigurationInput(args.configuration,true))` 冻结请求，`:69` 用冻结串做同 `request_key` 的幂等比对。冻结串里的 `work_mode` 是显式写入的，缺省值从 `single_thread` 变 `global` 后，升级前冻结、升级后重放的同一次请求会产生不同冻结串，命中 `409 creation_request_key_conflict`。
- 处置：**接受并记录**，不改代码。理由：影响面仅限“跨一次部署的在途单次创建请求”，PA 换 `request_key` 重试即成功，不产生错误数据、不改动既有 Agent；若为此在幂等校验里加“忽略模式差异”的分支，会让该校验长期对真实模式变更失去防护。已写入 `design.md` 的失败路径段。
- 复现判定：需要“升级前冻结 + 升级后重放”的时序，现有测试环境无法构造，只做代码路径确认。

### CONFIRMED 2：默认 global 后，部分功能路径对新建 Agent 不可用

- 事实核对：`chat-streaming.ts:84` 对非 `single_thread` 返回 400（无聊天内权限卡片）；`conversation-actions.ts:212`、`:233`、`:424` 的筛选条件硬编码 `work_mode='single_thread'`（会话蒸馏候选只含单线程 Agent）。
- 处置：**接受，用户已确认为预期行为**。这两条是 `global` 既有的模式语义，不是本次改动引入的缺陷；产品设定里默认走 global 就意味着默认不要这两项。已在 `design.md` 写明“用户可见影响”，并注明若产品要覆盖需要单独开 unit 改筛选条件；本 unit 不改这三处、不扩大范围。

### CONFIRMED 3：iOS 详情页/配置页仍标注“全局模式 · 实验”

- 事实核对：`AgentsView.swift:150`、`AgentsView.swift:263`、`AgentConfigView.swift:43` 三处都带“· 实验”，而 Web 端已在 feat-652 去掉。与“global 是缺省模式”直接矛盾。
- 处置：**已修**。三处统一为 `L("全局模式", "Global")`，创建页 Picker 也把 `global` 调到首位。

### CONFIRMED 4：PA 推荐默认值缺测试

- 事实核对：`personal-agent-creation.ts:51` 的 `defaults` 没有断言覆盖。
- 处置：**已修**。`apps/im-server/tests/personal-agent-creation.test.ts` 增加 `expect(options.defaults).toMatchObject({work_mode:'global'})`，把“PA 推荐值”和“创建实际缺省”钉在一起。

### PLAUSIBLE 5：滚动升级时旧节点收到 `global`

- 事实核对：`apps/node/src/configuration.ts:120` 的工作模式白名单一直是 `['single_thread','global']`，`packages/dsh-integration/src/global-mode.ts` 也是既有实现。
- 结论：**非问题**。`global` 不是本次新增的模式，旧节点收到 `global` 正常执行；本次只改“新建时选哪个值”。已在 `design.md` 记为“滚动升级顺序无约束”。

### PLAUSIBLE 6：库表列默认与测试 fixture 分叉

- 事实核对：把 `schema.sql` 的列默认改成 `global` 后，`configuration-boundaries.test.ts` 期望 `single_thread` 而得到 `global`——因为该 fixture 的 INSERT 没写 `work_mode`，靠列默认。
- 处置：**已修**，且选择回退列默认而不是改 fixture 期望。列默认的语义是“历史行兜底”，而所有新建链路都已显式写入模式；改列默认只会让新库与既有库（`CREATE TABLE IF NOT EXISTS` 不升级列默认）对同一 INSERT 产生不同结果。`control-fixture.ts` 同时显式 pin 成 `'single_thread'` 并注明理由。

## 审查中发现并修正的衍生缺陷

| 缺陷 | 现象 | 修正 |
|---|---|---|
| 提示词预览只在 global 时带 `work_mode` | 服务端缺省改 global 后，创建页选 `single_thread` 会预览成 global 的提示词 | 预览始终携带当前模式（`agent-create-page.tsx:176`） |
| 更新请求省略模式被当成“改成缺省” | 任何 `PATCH` 都会把 single_thread Agent 判成模式变更并 409 | 更新路径省略模式＝保持存储值（`configuration-input.ts:68`） |
| `fixedTools` 的 `mode` 有默认参数 | 创建期能力目录在 Agent 未知时调用它，single_thread 草稿会显示 global 的固定工具 | 去掉默认参数，未知模式不产生固定工具（`capabilities.ts:57`） |

## 验证记录

- 类型检查：`npx tsc -p packages/product-contracts/tsconfig.json`、`apps/node`、`apps/im-server` 三个包全部 exit 0。
- im-server 定向：`configuration-edits.test.ts`(8) + `personal-agent-creation.test.ts`(9) + `configuration-boundaries.test.ts`(4) → **21 passed**。
- product-contracts：`capabilities.test.ts` **10 passed**（含新增 `fixedTools(undefined,'root',false)` 为空）。
- 前端（在完整依赖的主仓副本中运行，worktree 的 `src/IM/frontend/node_modules` 不完整）：
  - `agent-create.test.tsx` **14 passed**（默认选中 global、两种模式各自提交值、预览始终带模式）
  - `capability-editor.test.tsx` + `agent-edit.test.tsx` **41 passed**
- `apps/node/tests/configuration.test.ts`：**11 passed**。中途曾出现“11 例全挂在 cleanup 的 `unlink` 上”的失败，原因是本机安全删除守卫的状态锁卡死导致所有 `unlink` 返回 `EPERM`，失败发生在断言之外的清理阶段；清除守卫状态后复跑 11/11 通过，与代码无关。
- 指纹：`apps/im-server/tests/control.test.ts` **21 passed**，其中钉住的 Python 时代候选哈希未变（`gatewayCandidate` 对缺失模式仍取 `single_thread`）。

## 剩余事项

- 用户实际验收：代码侧验收点（新建 Agent 默认选中全局模式）已实现；CONFIRMED 2 的两条限制经用户确认为预期行为，不需要在本 unit 处理。
- canonical 归并（`docs/specs/im/agents-nodes.md`）与归档：待用户验收后执行，本次不改 `docs/specs/`。
