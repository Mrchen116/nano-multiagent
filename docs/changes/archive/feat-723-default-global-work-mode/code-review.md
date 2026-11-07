# feat-723: Code Review

> 当前结论（2026-11-07）：独立代码审查 Approved，真实产品验收 pass，本地完整交付检查通过。原实施轮记录保留；最终 remote CI 与精确交付 head 见 PR #471 Validation Summary。

## Review scope

- Base / executed_base: `005a36057`（origin/main）。
- Review mode: `full`。
- Branch: `unit/feat-723`。
- Included dirty files: 本 unit 对 base 的全部 diff，含 `apps/im-server`、`apps/node`、`packages/product-contracts`、`src/IM/frontend`、`src/IM/ios` 的改动与本 unit 文档；主仓里用户自己的未提交改动未复制。
- Head: 本 unit 分支的实现提交。

## Round 1

> 原实施轮记录保留。下述 CONFIRMED 1 的“换 key”恢复建议与“无法构造”限制已由本轮独立复现更正，见后续 Round；原轮不得用作最终版本的放行结论。

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

## 原实施轮剩余事项（历史）

- 用户实际验收：代码侧验收点（新建 Agent 默认选中全局模式）已实现；CONFIRMED 2 的两条限制经用户确认为预期行为，不需要在本 unit 处理。
- canonical 归并（`docs/specs/im/agents-nodes.md`）与归档：待用户验收后执行，本次不改 `docs/specs/`。


## Round 2 — 2026-11-07 集成后独立 full review

- Reviewer: `pr471_static_review`，独立于受审实现与本轮文档收尾；模型 `gpt-6.1-sol/high`。
- Mode: `full`；同时执行 Agent Context Implementation Review。
- `validated_at`: `6cf5cd5084f68baafaf7f211e666ccafdc48fc19`；另核对本轮 spec/design/code-review 的文档更正 diff。
- `executed_base`: `29e3f2947699fb92b382c5f61b4a1ef169a40ede`。
- 审查范围：完整 `executed_base...validated_at`，不是只看 merge；24 个文件，325 additions / 17 deletions。本轮没有产品代码修复。
- 结论：**Approved，0 CRITICAL / 0 WARNING，最终 findings `[]`**。唯一恢复文档问题已更正并独立 closure；没有存活产品代码 finding。
- 真实用户授权：本轮在指出原 PR 验收/归档缺口后，用户要求继续收尾并明确委托 Agent 实测；验收事实单独见 `acceptance.md`。不补造原实施时未发生的用户亲测或 Gate 2。

### main 增量与门禁有效性

从原 base `005a360579d9e2c73f0a613073bcaecd705b7e62` 到本轮 main `29e3f2947699fb92b382c5f61b4a1ef169a40ede` 的 9 个提交，主要修改 PA 草稿/发言身份提示词、披露审核和上游参考文档。独立 reviewer 核对了增量与本 PR 的组合：没有改变配置写入、模式兼容读取、指纹或 PA 创建协议；普通 global 不会因模式而获得 personal identity。既有 global 固定工具与新 PA 提示词仍通过 personal/root/subagent 身份分支隔离。本轮全量审查与产品验收在同步 main 后执行，不仅凭无文本冲突保留结论。

后续只做验收报告、canonical 同条 Requirement 归并、整个 unit 路径归档和验证记录，不修改产品代码。精确最终 `effective_base` / `effective_through` 在 PR Validation Summary 中按提交完成后的实际 SHA 列出；任何 main 或产品代码继续变化须重新判断适用门禁。

### 恢复建议 finding closure

原 Round 1 的“换 request_key 即成功”不成立。独立 reviewer 以旧省略模式请求的等价冻结配置（显式 single_thread）构造 pending/lost ACK：

1. 升级后省略模式并用原 key 再 create：409 `creation_request_key_conflict`。
2. 换新 key、保留同 agent_id：409 `agent_id already exists`，因为新 operation_id 不能认领旧 pending 操作。
3. 保留原 key 调 `status`，恢复 ACK 后成功返回 created/single_thread；节点最终只有一份创建回执。

本机临时 fixture 复现 **1 test passed**，不加入永久套件；locator 为本轮仓外 `pr471-close-20261107/pa-replay-review.log`。`design.md` 已更正恢复指引：优先原 key + status；若 status 为 not_started 且没有原配置操作，以原 key 和原冻结配置重试。独立 reviewer 已读取文档 delta，确认 **closed**。原 Round 保留用于历史取证，不再沿用错误指引或原“无法构造”限制。产品的升级窗口行为仍是已记录的接受项，不增加兼容分支。

### Context Implementation Review

- 覆盖创建解析 → 显式模式配置 → Node runtime / 候选规范化 → 固定工具选择及预览；核对所有 fixedTools 调用方、root/personal/subagent 的原有过滤与身份边界。
- PA options 的 defaults 和 omit-to-global 字段说明与实际 create 解析一致；核对 agent_creation schema、JSON output.render、ProductBridge 与 IM handle 的参数/结果透传，宿主身份未变成模型必填参数。
- 随包 nano-agent-creation Skill 已要求 pending/unknown 保留原 key 查询 status，与真实恢复路径一致；错误换 key 建议只在历史 unit 文档中，未将其误称为实际模型失败。
- Web 创建页预览显式发送当前模式，iOS previewPayload 始终带模式；既有 AgentConfig.draft 使用已保存模式覆盖创建草稿默认。
- 限制：源码消费链与确定性 fixture 不能证明真实 provider wire 或模型选择。本次没有修改 global 的既有 prompt/序列化算法，不宣称做过真实模型全链或 iOS 实机验收；真实 Web 创建结果单列。


## 本轮验证（2026-11-07）

受审源码为 `6cf5cd5084f68baafaf7f211e666ccafdc48fc19`，Node 24.22.1、Python 3.12.9。主仓其他任务的 dirty/untracked 内容未复制或修改；本 unit 在原专属 worktree 完成检查。

| 检查 | 实际结果 |
| --- | --- |
| `pnpm build` | passed |
| `pnpm typecheck` | passed，包含 evals |
| `pnpm check:ios-runtime` | passed |
| 前端 `npm ci` + `npm audit --audit-level=critical` | passed；0 critical，已有 4 low / 2 moderate / 5 high，未在此 unit 扩大依赖升级 |
| 前端 `npm test` | 113 files / 1077 tests passed |
| `python -m pytest -m "not e2e" -q` | 135 passed / 28 deselected |
| `ruff check .` / `ruff format --check .` | passed |
| 定向回归（上一轮独立审查） | 6 files / 63 tests passed |
| 原 key / 新 key / status 恢复独立复现 | 1 test passed |

本机首次前后端全量及 UI 构建并行时，8 核机器 load average 曾达 88，运行时套件出现超时；该次没有作为成功证据，也未通过修改测试超时或产品代码掩盖。前端完成后，终止本 unit 那次受争用的后端测试进程树，保留 `backend-tests.log`，以 `pnpm exec vitest run --maxWorkers=2` 原阈值复跑完整后端套件。最终结果与产品验收在完成后追加。

本机日志保留于仓外 `/Users/czj/.codex/reports/pr471-close-20261107/`；runtime、截图、DB、token 和构建 dist 不提交。


## 第一次最终集成、验收与交付有效性（至 c2b41c096）

- `effective_base`: `c2b41c09645618ca1d406cf90ae91d60ecafcd2c`。
- 最终同步提交：`b543e18e2999b3ea36b892457b1d43f2d30dc7e1`。其后仅本 unit 文档收尾、原 Requirement 的 canonical 归并及整个 unit 归档；精确最终 `effective_through` 在提交后写入 PR #471，避免把文档自身提交号递归写入文档。
- `validated_at` / `executed_base` 保留每个门禁真实执行版本，不改写为后来的集成树。
- 静态审查：保留 Round 2 Approved。后续 main 产品增量仅 `.chat-sidebar-header-row` 把 overflow:hidden 移到搜索折叠态；没有改变模式解析/配置/PA 工具或 Context 消费链。新增归档材料与本 unit 无关。产品源码与原已审链路保持一致，故 code review retained。
- 产品验收：独立 `pr471_product_acceptance`（`gpt-6-astra/low`）在 `6cf5cd5084f68baafaf7f211e666ccafdc48fc19` 实际执行，5/5 Scenario pass、0 issues，见 `acceptance.md`。后续 CSS 仅作用聊天侧栏标题行，不作用创建模式、配置详情、HTTP 创建、模式不可变或单 Thread 的运行行为；本轮不重写其验收 SHA，保留结论。
- 本地后端完整复跑：`pnpm exec vitest run --maxWorkers=2`，**214 files / 1164 tests passed**，727.35s；原超时阈值未变。源码与本轮最终 main 的后端/测试/配置/依赖无差异，因此保留该结果。
- 本地前端：113 files / 1077 tests passed。最终 main 只改上述 CSS，保留 JS/组件测试结论，并对最终 CSS 重新执行真实 UI 内容指纹构建。
- Python 135 passed、ruff、root build/typecheck、ios-runtime 的对应输入未因最终 main 改变，保留有效结果；归档后的 docs-check 与归档门禁另在提交前实际重跑。
- Delta 校正只将 Requirement 标题对齐现有 canonical 原名，正文新增缺省 global 场景、保持其它约束。最终 canonical 条目与 delta 的完整 Requirement 一致，不扩大到其它 area；归并不增加 Requirement 数量。
- 原未完成验收/归并/归档项在本轮按用户明确委托收口；没有补造事前设计门禁，也不宣称用户亲测。
- 本轮没有数据迁移：既有 Agent 不改模式，库表默认不改，故不生成 deployment-prompt；交付不执行部署或发布安装包。


### 第一次交付提交前检查实际结果

- 最终 CSS 内容指纹 UI 构建：passed，前端重新构建成功，trajectory 输入未变而复用；locator `final-ui-build.log`。
- 归档后 `./scripts/docs-check`：passed。
- `python3 scripts/check_change_unit_archived.py --head-ref unit/feat-723`：passed，unit 在 archive 唯一存在。
- canonical 同名完整 Requirement 与最终 delta 逐字相等；未改变 Requirement 数量。
- 本轮真实服务已执行 `e2e-down.sh`，Node/DSH 和 IM 停止，IM 端口 54056 已释放，tmux pr471-close 已关闭。runtime/截图保留在本地，开发 worktree 按开放 PR 规则保留。


## 第二次 main 同步（#469，2026-11-07）

第一次交付 head `699ef60100694c7716b7c1a41bb4283fbe73dee7` 的远端 CI（run 42353670814）4/4 checks success。最终 fresh check 时发现 main 又合入 `70d781d6197ccc918dd943f4743df5fe3bfc3719`，故继续同步，而非将上面的 c2b41c096 误写成最新 main。

- 实际新集成树 / 本轮 `validated_at`：`a3ecccf991663e96176799b406ecc2af9eb2398c`。
- 本轮 `executed_base`：`70d781d6197ccc918dd943f4743df5fe3bfc3719`。
- main 增量：#469 的 message_discarded 事务与提交后广播、预览/未读投影恢复、相应 Gateway port 接入及 7 项回归。没有修改新建模式默认、旧记录读取、PA 创建协议、指纹或 immutable 校验。
- 局部验证已实际完成：im-server build/typecheck passed；本 unit 原 6 个定向文件 + 新 discarded-message-projection 文件，**7 files / 70 tests passed**，5.11s；locator `final-main-build.log`、`final-main-tests.log`。
- 前一次本地全量 214 files / 1164 tests 是旧树的有效历史证据；本轮不将其改称为新树的全量执行。新 head 将重新执行远端完整 CI。
- 精确最终 `effective_base` / `effective_through` 仍在提交后更新到 PR #471；前述第一次交付字段只作为历史保留。


### 独立增量复核与 retained 结论

独立 `pr471_static_review` 对 `699ef60100694c7716b7c1a41bb4283fbe73dee7..a3ecccf991663e96176799b406ecc2af9eb2398c` 执行 targeted/closure，最终 JSON `[]`，无存活 finding。源码增量仅来自新 main 的 discard 四个模块；Gateway 新 publishCommitted port 正确使用已先初始化的 Messaging，与本 unit 模式、创建及权限边界没有冲突。discard 不在 PA source trigger 集合，未新增模型输入或 wake。

- Code review / Context Implementation Review：**retained**，配置、PA 创建、fixedTools 与模型接口没有 delta。
- 5 个真实产品 Scenario：**retained**。创建默认、显式选择、旧记录解释与 immutable 都不依赖 discarded 分支；已成功完成的单 Thread 聊天没有进入该恢复路径。没有将旧实测 SHA 改为新树，也不要求与本 unit 无关的完整产品重验。
- 前端、iOS、Python 和依赖输入未因 #469 改动，保留其本地结果；后端真实发生变化的部分已有本轮 70 项局部复验，最终远端 CI 再覆盖完整集成树。
- 本轮最终 `effective_base` 更新为 `70d781d6197ccc918dd943f4743df5fe3bfc3719`；精确 `effective_through` 为 PR #471 提交后的 head。后续文档提交仅记录本次真实复核和测试，没有新产品改动。
- 证据：仓外 `final-main-retained-review.md`；旧 head699 完整远端 CI 见 run 42353670814，新 head 的实际远端结果以 PR Validation Summary 为准。
