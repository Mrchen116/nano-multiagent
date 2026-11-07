# feat-723: As-built Design

> 本文在实现完成后根据实际代码、diff 与已确认决定整理，描述最终落地设计。

## 实现范围

- Base: `005a36057`（origin/main）
- Head: 本 unit 分支 `unit/feat-723` 的实现提交
- Commits: 实现提交一个；unit 文档随同提交
- Included dirty files: 无（实现来自干净 worktree；用户在主仓的其它未提交改动未触碰）
- 受影响模块：
  - `apps/im-server`：创建/配置写入边界、PA 代创建推荐、注册兜底、库表列默认
  - `apps/node`：本地配置读取兜底（保持不变，仅加注释）
  - `packages/product-contracts`：固定工具函数签名
  - `src/IM/frontend`：创建页默认选中与选项顺序、能力目录兜底
  - `src/IM/ios`：创建表单默认模式与“实验”标注

## 最终结构

### 组件与职责

| 位置 | 职责 | 本次变化 |
|---|---|---|
| `apps/im-server/src/configuration-input.ts` | 把 HTTP 体解析成创建/更新候选 | 创建路径把缺失模式解析为 `global`；更新路径缺失仍是“不变” |
| `apps/im-server/src/agent-creation.ts` | 创建候选落库 | 缺模式兜底 `global` |
| `apps/im-server/src/control-routes.ts` | 配置读写路由 | 创建候选缺模式兜底 `global` |
| `apps/im-server/src/personal-agent-creation.ts` | PA 代主人创建 Agent 的推荐配置 | 推荐 `work_mode: 'global'`，字段说明写明省略即 global |
| `apps/im-server/src/schema.sql` | 建库骨架 | 保持旧默认 `single_thread`（见关键决策 5） |
| `apps/im-server/src/control.ts` | 候选规范化与指纹 | `gatewayCandidate` 的缺模式兜底保持 `single_thread`（见关键决策 2） |
| `apps/im-server/src/gateway.ts` | 节点注册 | 节点未上报模式时的兜底保持 `single_thread`（见关键决策 3） |
| `apps/node/src/configuration.ts` | 本地配置读取 | 缺模式兜底保持 `single_thread`（见关键决策 3） |
| `packages/product-contracts/src/capabilities.ts` | 固定工具集合 | 去掉 `mode` 的默认参数：未知/缺失模式不产生 global 固定工具 |
| `src/IM/frontend/.../agent-create-page.tsx` | 创建页 | 草稿默认 `global`；选项顺序 `global` 优先；单选兜底 `global`；提示词预览始终携带当前模式 |
| `src/IM/frontend/.../capability-editor.tsx` | 能力目录 | 客户端固定工具兜底改为传原始 `mode`（不再假装 `single_thread`） |
| `src/IM/ios/.../AgentModels.swift`、`AgentsView.swift`、`AgentConfigView.swift` | iPhone 创建/详情/配置 | 默认 `global`，选项 global 在前，三处都去掉“· 实验”字样 |

### 调用链与数据流

创建一条 Agent 的模式有三个入口，最终都落到节点配置写入：

1. Web 创建页：`agent-create-page.tsx` 的草稿 → `createNodeAgent()` → `POST /im/v1/nodes/:id/agents` → `parseConfigurationInput(create=true)` → `agent-creation.ts` → 配置操作 → 节点 `agent.config.apply`。
2. PA 代创建：`personal-agent-creation` 先返回推荐 `defaults`（现为 global），模型提交的配置同样经 `parseConfigurationInput(create=true)`。
3. 节点注册：网关把节点上报的 `agent_work_modes` 落到 `agent_profiles`；缺失时按旧节点语义兜底。

读路径（`GET settings`、工作模式不可切换校验、指纹比对）不受缺省影响：它们读的是已落库的具体值。

### 状态、数据与兼容性

- 已存在的 Agent：`work_mode` 在创建时已落库，读路径不做缺省替换，因此不会因为本次改动变成 global；`work_mode is immutable` 的校验保持不变。
- 未落库的旧记录（缺列值、旧节点注册、旧 YAML）：仍按 `single_thread` 解释，避免升级即改变运行行为。
- 候选指纹：`candidateFingerprint` 经由 `gatewayCandidate` 规范化，后者对缺失模式仍取 `single_thread`，因此 `apps/im-server/tests/control.test.ts` 中钉住的 Python 时代哈希不变，升级前未完成的配置操作仍可重放。
- 建库列默认：保持 `single_thread`，只作为“没有写入模式的历史行”的兜底。产品代码所有插入都显式带模式，若把列默认改成 `global`，会让新库与既有库（`CREATE TABLE IF NOT EXISTS` 不升级列默认）对同一 INSERT 产生不同结果，也会让一批未显式写模式的测试 fixture 静默变成 global Agent。

## 关键决策

| 决策 | 原因与约束 | 代码定位 |
|---|---|---|
| 缺省 global 只落在“新建”语义上，读取旧记录仍按 single_thread | 全局模式会改变运行形态（主会话、Inbox、固定工具）。把旧记录缺字段解释成 global 会在升级瞬间改变既有 Agent 行为，并与 IM 侧既有记录冲突（工作模式不可变）；同时会让旧候选指纹失效 | `apps/node/src/configuration.ts:91`、`apps/im-server/src/gateway.ts:325`、`:336` |
| `gatewayCandidate` 的兜底保持 `single_thread` | 它同时是候选指纹的规范化函数，改默认等于改写历史哈希；创建路径已在上游显式给出 global，不依赖这里 | `apps/im-server/src/control.ts:73`、`:90` |
| 更新请求省略模式＝保持不变 | 若沿用“省略即取默认”，任何 `PATCH` 都会把 single_thread Agent 判成模式变更并 409 | `apps/im-server/src/configuration-input.ts:68` |
| `fixedTools` 去掉默认参数 | 创建期能力目录在 Agent 未知时调用它；若默认 global，single_thread 草稿会把 inbox/conversations/send_message/subagent 显示成固定项 | `packages/product-contracts/src/capabilities.ts:57` |
| 建库列默认保持 `single_thread` | 列默认是“旧行兜底”而不是“新建缺省”：每条新建链路都已显式写模式，改列默认只会让新旧库分叉，并让未显式写模式的 fixture 悄悄变成 global | `apps/im-server/src/schema.sql:81` |
| 创建页把 global 放在选项首位 | 默认值与视觉顺序一致，减少“默认值在第二位”的读数成本 | `agent-create-page.tsx:769` |
| 提示词预览始终发送当前模式 | 预览原先只在 global 时带 `work_mode`；服务端缺省改成 global 后，选 single_thread 会预览成 global 的提示词 | `agent-create-page.tsx:176` |
| iOS 三处一并去掉“实验” | Web 端已在 feat-652 去掉；创建页、详情页、配置页各有一处“全局模式 · 实验”，与“global 是缺省”直接矛盾 | `AgentsView.swift:150`、`:263`、`AgentConfigView.swift:43` |

## 失败路径、风险与回滚

- 旧节点（不上报 `agent_work_modes`）注册新 Agent：仍记为 `single_thread`，与其实际运行能力一致；升级节点后该 Agent 不会自动变 global（工作模式不可变）。
- 滚动升级顺序：不需要“先升节点再升服务端”。`global` 是节点侧一直合法的工作模式（`apps/node/src/configuration.ts:120` 的白名单、`packages/dsh-integration/src/global-mode.ts` 的既有实现），旧节点收到 global 正常执行；本次改的只是新建时选哪个值。
- 升级前未完成的创建/更新操作：候选里若没有模式，指纹仍按 `single_thread` 计算，重放结果与升级前一致。
- **已知且接受的升级窗口影响**：PA 代创建用 `pa_agent_creations.configuration_json` 做请求幂等（`personal-agent-creation.ts:69`），冻结值里模式是显式写在 JSON 里的。若某条 PA 创建请求在升级前冻结（当时解析为 `single_thread`）、在升级后才用同一 `request_key` 重放，新解析出的 `global` 会与之不一致，返回 `409 creation_request_key_conflict`。保留原 `request_key`，通过 `action=status` 沿已冻结配置查询或恢复；已创建或 pending 时换 key 会因同一 `agent_id` 已存在而 409，不能用换 key 作为通用恢复方法。若 status 为 `not_started` 且原配置操作尚未建立，应以原 key 和原冻结配置（显式 `single_thread`）重试，避免把旧请求改成新默认模式。该窗口不会自动迁移既有 Agent。没有加“忽略模式差异”的兼容分支，是因为那会让幂等校验长期对模式变更失去防护，收益不抵成本。
- 只回滚代码不回滚数据：已按 global 创建的 Agent 保持 global（该模式是合法且受支持的），不影响回滚后的读写。
- 用户可见影响（既有模式语义，非本次新增限制）：新建 Agent 默认跨聊天持续工作，因此 Web 聊天内不再有权限卡片（`chat-streaming.ts:84` 对非 single_thread 返回 400），会话蒸馏的候选来源只包含 single_thread Agent（`conversation-actions.ts:212`、`:233`、`:424`）。这两条是 `global` 本来就有的语义，本次只是让新建默认值落到它上面；用户已确认这属于预期行为，本 unit 不改这些筛选条件，若日后要让蒸馏覆盖 global 需单独开 unit。

## 与初始意图的差异

- 初始指令是“默认走 global，缺省走 global”。实现把“缺省”限定在新建链路；对旧记录缺字段的兼容读取保持 single_thread，理由是它等价于给既有 Agent 做静默模式迁移，与“已有 Agent 保持原行为”冲突。用户未要求迁移既有 Agent。
- 额外修改：iOS 去掉“实验”标注、创建页选项顺序调整、测试 fixture 显式 pin 模式。都属于同一意图下的最小一致性修正。

## 验证定位

- 验收安排（2026-11-07）：原 PR 的用户亲测尚未发生；用户本轮明确委托“你测就行了，我交给你。”由独立 Agent 通过真实 Web 入口验证创建默认 global、显式 single_thread、旧 Agent 保持及模式不可切换。实际结果与证据记入 `acceptance.md`；不将委托验收写成用户已亲测。iOS 属默认字段和既有控件文案变化，复用 CI 的编译与测试，共享创建语义在 Web 验证，不宣称 iOS 实机体验通过。
- 自动化测试：
  - `apps/im-server/tests/configuration-edits.test.ts`（新增：省略模式创建为 global，显式 single_thread 保持）
  - `apps/im-server/tests/configuration-boundaries.test.ts`（更新语义：null 保持存储值）
  - `apps/im-server/tests/control.test.ts`（指纹哈希不变）
  - `packages/product-contracts/tests/capabilities.test.ts`（未知模式无 global 固定工具）
  - `apps/node/tests/configuration.test.ts`
  - `src/IM/frontend/src/features/settings/agents/agent-create.test.tsx`（默认选中 global、两种模式提交值）
- 运行证据：见本 unit 提交说明与 code review 的测试记录。

## Canonical 文档影响

- Delta-spec：`specs/im/agents-nodes.md`（MODIFIED：新建时选择工作模式，未选择时缺省全局）
- 归并目标：`docs/specs/im/agents-nodes.md` 的同名 Requirement
- 未改动 gateway 契约：`global`/`single_thread` 各自的行为、固定工具和投递语义没有变化，变化的只是新建时的取值
