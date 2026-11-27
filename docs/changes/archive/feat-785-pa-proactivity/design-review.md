# feat-785: Personal Agent 主动性闭环与渐进式目标图 — Design Review

## Round 1

### Metadata

- **reviewer**: `change-design-reviewer` (independent subagent, integrating `codebase-design`, `agent-context-review`, `frontend-experience-review`)
- **target**: `docs/changes/feat-785-pa-proactivity` (`spec.md`, `design.md`, `prototype.html`, `evidence/prototype-walkthrough.md`, `evidence/screens/*.png`, `specs/im/{task-graphs,personal-agent,ios-client}.md`, `specs/gateway/{task-graphs,personal-agent,agent-capabilities}.md`, `M1/`)
- **review_mode**: `full`
- **mode_reason**: Initial Gate 2 independent review (`Round 1`) covering a full-unit cross-package architecture, Agent Context design, Web/iOS UX prototype, 6 delta-specs, and milestone plan.
- **started_at**: `2026-11-25T14:16:24+09:00`
- **completed_at**: `2026-11-25T14:32:25+09:00`
- **duration**: `16m 01s`

### Verdict

**Issues Found** — `4 CRITICAL / 5 WARNING` (plus `2 Recommendations`)

### Coverage 与证据

1. **现状 Grounding 与架构判断（`codebase-design`）**：
   - 核对了 `SPEC.md`、`AGENTS.md` 及真实装配入口：`packages/product-contracts/src/{task-execution,capabilities,chat,configuration}.ts`、`apps/im-server/src/{schema.sql,task-graphs,task-notifications,personal-agent,personal-actions,messaging,message-records,agent-creation,configuration-assembly}.ts`、`packages/personal-assistant/src/{inbox,personal-assistant,global-agent,heartbeat,task-execution,knowledge,configuration}.ts`、`packages/dsh-integration/src/{index,cron-owners,task-execution,product-bridge,message-arguments,features/task-graphs,knowledge/dreaming,knowledge/dreaming-agent,knowledge/dreaming-history,knowledge/runtime,knowledge/memory-documents}.ts`、`apps/node/src/{main,configuration}.ts`。
   - **合理的架构收敛**：原位演进 `task_graphs`（`schema_version: 2`）以「单卡即根、按需原位成图」承接日常小事、长线目标、`prep_draft` 与 `proposed` 提议卡（决策 1、3），避免拆出多套独立提案/待办表；聊天消息仅保存 `(graph_id, node_id)` 引用而非静态 OpenUI 快照，从数据源消除双端状态脱节；跨包依赖方向符合 `SPEC.md` 红线（不引入新 HTTP 内核或跨包私调）。
   - **发现的关键装配断裂**：①原生 `Cron` 运行在 `dsh-integration` 子进程而非 `personal-assistant`，导致设计中的早间顺风车与定时唤醒 `<proactive-focus-snapshot>` 注入整条断链（`R1-C1`）；②`PersonalAssistant.send()` 缺少 `publicationEvidence` 同轮已读冲刷且 `pendingReadCalls` 硬编码 `attention=1`，直接放宽 `blocking()` 会造成同轮重发死循环，同时纯文本提醒无 `source_refs` 关联会话（`R1-C2`）；③后台隔离会话调 `task_graph` 会误继承主会话上一轮人类 `source_message_id` 且未被服务端/宿主禁止写入 `doing` 或触碰 `.nanoassistant/memory/`（`R1-C3`）；④漏改 `packages/personal-assistant/src/task-execution.ts` 的 `snapshotAdmitted`，导致 `waiting(kind: "decision")` 触发 256 轮连续修复唤醒风暴（`R1-C4`）；⑤`CanonicalAgentConfiguration` 指纹兼容、`Dreaming` 静默翻牌事件源与消息 `task_cards` 落库链路存在具体缺口（`R1-W1`–`R1-W3`）。
2. **用户约束与产品目标对齐（`spec.md` Q1–Q7）**：
   - 逐项核对了 `spec.md` 的 7 项已拍板决策与 ADHD 早/午/晚三锚点场景：零摩擦单卡起步与北极星目标锁定、垫步草稿 vs 有界 `proposed` 提议、跨观察流发前新鲜度核验、通用无货零打扰早报 + 自定义早间 Cron 顺风车合并（不硬编码特定作息或日记 Skill）、显式一次/隐式两次分寸沉淀、PA 专属 `proactive_planning` 开关及离线只读边界均已在方案中建模，但自定义 Cron 顺风车、发前新鲜度门控、未批不执行硬边界与静默翻牌学习需先修复 `R1-C1`–`R1-C4`、`R1-W2` 才能兑现承诺。
3. **Agent Context 审查（`agent-context-review` 设计模式）**：
   - 核查了四条模型可见消费链（PA/Global 主会话、`TaskExecutionDriver` 自动续跑、`proactive-digest`/`proactive-plan` 独立短期维护会话、`Dreaming` 整合会话）及 `docs/development/agent-context-engineering.md` 前缀缓存不变量（`NoSilentPrefixRewrite`）。
   - 将动态 `<proactive-focus-snapshot>` 放入定时唤醒当轮追加的 `nano-system` 用户消息、不在活跃窗口中途重写 `systemPrompt.section` 或 `MEMORY.md`/`ROLE.md` 快照、将安静后消化与夜间筹划隔离到短期会话的设计符合前缀稳定原则；`verify-context-cache-prefix` 与隔离栈 `llm_logs` 验证计划明确。待补齐的是 `dsh-integration` 原生 `schedule` 唤醒如何桥接注入 `<proactive-focus-snapshot>`（`R1-C1`）以及 `Dreaming` 如何获取无聊天轮次的静默 UI 翻牌结果（`R1-W2`）。
4. **前端体验与原型审查（`frontend-experience-review` 设计模式）**：
   - 完整阅读 `prototype.html`、`evidence/prototype-walkthrough.md` 及双端现有实现（`src/IM/frontend/src/features/tasks/{task-progress,task-graphs-page}.tsx`、`chat/components/message-pane.tsx`、`settings/agents/agent-detail-page.tsx`；`src/IM/ios/NanoIM/Features/{Tasks/TasksView,Chat/ChatMessageView,Agents/PersonalAgentManagementView,Agents/AgentConfigView}.swift`），并逐张目视检查全部 10 张实际渲染截图（`focus-web.png`、`focus-triaged.png`、`goal-web.png`、`chat-web.png`、`focus-mobile.png`、`ios-goal.png`、`ios-draft.png`、`ios-chat.png`、`settings-online.png`、`settings-offline.png`）。
   - 视觉层级与主路径体验扎实：「待你拍板 → 正在推进与盯梢 → 长线目标」焦点顺序清晰，主次按钮权重受控（仅主操作实心填充），右下浮层不挤动相邻卡片，手机端纵向阶段脊柱流有效消除了 `320pt` 二维画布双指缩放痛点，离线只读横幅与开关禁用状态直观。但与现有产品功能基线及双端配置页架构对照，存在群任务新建入口丢失、`按负责人 / 团队全部` 视图未定义、多层嵌套子图与 iOS 节点编辑入口缺失、前置未完时的批准文案失真及双端 PA 开关保存/依赖冲突 5 处具体缺口（`R1-W4`）。
5. **契约增量（Delta-specs）、部署迁移与里程碑（`M1`）**：
   - 核对了全部 6 份 delta-spec 的格式、Scenario 结构及 `Canonical Areas` 计数加减（`im/task-graphs` `19→20`、`im/personal-agent` `8→8`、`im/ios-client` `19→19`、`gateway/task-graphs` `24→24`、`gateway/personal-agent` `18→19`、`gateway/agent-capabilities` `64→65`，算术准确）。发现 `gateway/personal-agent.md` 遗漏更新存量冲突条文、`im/task-graphs.md` 替换整条 Requirement 时误删多层逐级进入与列表增量加载契约（`R1-W5`）。
   - 单 `M1` 里程碑切分合理（先落契约与服务端，再按物理隔离包并行推进 runtime / Web / iOS），Runbook 使用 `./scripts/e2e-up.sh --profile daily` 隔离栈与真实模型验证双路径并包含完整回收步骤；无需外部人工凭据或 `deployment-prompt.md`，但需补齐 `messages` 表启动期兼容加列与配置指纹平滑策略（`R1-W1`、`R1-W3`）。

### 历史问题闭环

首次审查（`Round 1`），无历史遗留问题。

### Issues

#### `R1-C1` [CRITICAL] 用户自定义 Cron 在 `dsh-integration` 内部直接入队，完全绕过 `personal-assistant` 的唤醒前观察流拉取、早间顺风车合并与 `<proactive-focus-snapshot>` 注入

- **位置**：
  - `docs/changes/feat-785-pa-proactivity/design.md:13, 99-100, 207-212, 227, 336`
  - `docs/changes/feat-785-pa-proactivity/specs/gateway/personal-agent.md:15-21`
  - 代码基线：`packages/personal-assistant/src/heartbeat.ts:13`、`packages/dsh-integration/src/cron-owners.ts:58, 91`、`packages/dsh-integration/src/index.ts:153-157`、`packages/dsh-integration/src/task-execution.ts:101, 133`、`apps/im-server/src/personal-agent.ts:451`
- **证据**：
  1. `design.md:13, 208-210, 227` 将 `proactive-coordinator.ts` 放在 `packages/personal-assistant`，并假定所有主会话 `cron` / `heartbeat` 唤醒均由 `PA` 先调 `pa.observations.pull`（注：`apps/im-server/src/personal-agent.ts:451` 真实 RPC 方法名为 `pa.observations.read`），再由 `PA ->> DSH` 提交附带 `<proactive-focus-snapshot>` 的 `nano-system` 唤醒消息。
  2. 真实代码装配中，`packages/personal-assistant/src/heartbeat.ts:13` 仅管理节点侧 `Heartbeat`（注释明确声明：*"Node-owned heartbeat policy. Cron's native timer and storage never enter this loop"*）；用户创建的全部 `Cron` 定时任务均运行在 `dsh-integration` 子进程的原生 `ScheduleService` 中（`packages/dsh-integration/src/cron-owners.ts:58`、`packages/dsh-integration/src/index.ts:153-157`），到期时在子进程内直接向 `agent.inbox` 推入 `source: { kind: 'schedule' }` 的 `UserMessage`，根本不经过 `packages/personal-assistant`。
  3. 同时，`personal-assistant` 本地并不持有用户的 Cron 列表；若 `proactive-coordinator` 不通过 `schedule.command({ action: 'jobs' })`（`CronOwners.catalog`，`cron-owners.ts:91`）向 `dsh-integration` 查询并按主人时区解析 `[06:00, 11:30]` 内启用的主会话 Schedule，默认早报无法获知 `09:10` 自定义早间 Cron 的存在。此外，`design.md:100` 将“成功回复主人私聊后统一打上 `briefed_at`”绑定在整轮回复上，若早间 Cron 回复仅处理了日程而未引用某张草稿/提议卡，粗粒度全量标记会把实际未呈报的成果静默吞掉。
- **未修后果**：
  - 核心旅程路径 B（`09:10` 晨间计划对齐顺风车合并、`14:10` 午后防走神主线检查、`23:00` 晚间日记回看目标——`spec.md:174-184, 261-265`）在真实运行时彻底失效：原生 Cron 唤醒既不会先拉取观察流新消息，也不会携带 `<proactive-focus-snapshot>`，默认早报还会因看不到 `dsh-integration` 内的 Cron 而与用户 `09:10` 定时任务重复双发。（需在 `dsh-integration` 的 `agent/pre-step` 拦截 `source.kind === 'schedule'` 反向请求 `personal-assistant` 完成观察流同步与快照组装，并在 `proactive-coordinator` 经 `schedule.command` 读取主会话早间任务列表，且仅对当轮实际携带或明确呈报的条目更新 `briefed_at`。）

#### `R1-C2` [CRITICAL] `PersonalAssistant.send()` 直接纳管 `attention=0` 未读消息会导致同轮重发死循环，且纯文本提醒与推进中任务缺失关联会话范围

- **位置**：
  - `docs/changes/feat-785-pa-proactivity/design.md:13, 29, 94-95, 128, 337`
  - `docs/changes/feat-785-pa-proactivity/specs/gateway/personal-agent.md:23-25`
  - 代码基线：`packages/personal-assistant/src/personal-assistant.ts:235-248`、`packages/personal-assistant/src/global-agent.ts:905-915, 979-999`、`packages/personal-assistant/src/inbox.ts:565-579, 707-726`
- **证据**：
  1. **同轮重发死循环**：`design.md:29, 95` 计划在 `PersonalAssistant.send()`（`personal-assistant.ts:235`）拉取观察事件并将 `inbox.blocking()` 放宽至包含 `attention=0` 未消费观察消息。但与 `GlobalAgent.send()`（`global-agent.ts:905, 979-999`）不同，`PersonalAssistant.send()` 并未在检查 `blocking()` 前执行 `publicationEvidence`（调 `session.publication` + `commitInboxRead` 冲刷当轮已读工具调用）；且即便在 `GlobalAgent` 中，`InboxStore.pendingReadCalls()`（`inbox.ts:707-712`）也硬编码了 `WHERE i.attention=1 AND i.consumed=0`。因此当 PA 收到 `held_for_revalidation`、在同一轮内调用 `inbox(action="read")` 读完该观察群新消息并再次调用 `send_message` 时，这些 `attention=0` 记录的 `consumed` 仍为 `0`，会被无限次重复返回 `held_for_revalidation`。
  2. **纯文本提醒与非提议节点无 `source_refs`**：`design.md:337` 限定仅对「主人私聊 + 本轮草稿/任务 `source_refs` 指向的会话」做 `attention=0` 拦截，但 `source_refs` 仅定义在 `TaskProposalMeta`（`design.md:128`，即 `proposed` 节点），而午后防走神提醒或 `waiting(scheduled)` 到期催办（`spec.md:180-182, 272-275`、`design.md:359`）发出的往往是不带 `task_cards` 的纯文本 `send_message`，对应任务也处于 `doing` / `waiting` 而非 `proposed`。此时 `PersonalAssistant.send()` 拿不到任何关联观察群 ID，主人在「研发日常群」刚完成的进展无法触发拦截。
- **未修后果**：
  - PA 在观察群有新消息时要么陷入同轮 `held_for_revalidation` 无法发信的死循环，要么在午后防走神/定时跟进纯文本提醒中完全漏检观察群动态，继续发出马后炮催问（违反 `spec.md:272-275`）。（需让任务节点通用元数据保留来源会话引用、在定时唤醒快照中显式提示关联观察群未读动态，并在 `PersonalAssistant.send()` 复用 `publicationEvidence` 且让 `pendingReadCalls` 覆盖 `attention=0` 已读消费。）

#### `R1-C3` [CRITICAL] 「未批准不执行」与后台筹划隔离存在三处越权旁路：跨会话人类 `source_message_id` 串用、后台写 `doing` 唤醒主会话执行、以及 `.nanoassistant/memory/` 写保护缺失

- **位置**：
  - `docs/changes/feat-785-pa-proactivity/design.md:21, 23, 64, 91, 171-173, 204-205`
  - `docs/changes/feat-785-pa-proactivity/specs/gateway/personal-agent.md:11-13, 33-35`、`specs/im/task-graphs.md:17-20`
  - 代码基线：`packages/personal-assistant/src/global-agent.ts:787-818`、`apps/im-server/src/task-graphs.ts:673, 692-868`、`packages/dsh-integration/src/knowledge/dreaming-agent.ts:60-103`
- **证据**：
  1. **后台短期会话误继承上一轮人类 `source_message_id`**：当 `proactive-digest-<id>` 或 `proactive-plan-<id>` 作为子会话（`call.sessionId !== binding.sessionId`）通过 `ProductBridge` 调用 `task_graph` 时，`GlobalAgent.execute`（`global-agent.ts:796-800`）只读取根会话 `binding.sessionId` 最后一次 `turn/start` 之后的事件，既不检查根会话该轮是否早已 `turn/end`，也不区分调用方是否为后台维护会话。若主人睡前最后一轮是真人私聊消息，凌晨 2 点的 `proactive-plan` 调用 `task_graph` 时会自动附带昨晚那条 `human` `messageId`，在 `im-server`（`task-graphs.ts:673`）通过 `verifiedHuman` 校验——从而获得删除整张任务图（`:865`）或解除 `/stop` 冻结（`:818-826`）的人类级权限。
  2. **后台写 `status: "doing"` 直接唤醒主 PA 会话重度执行并外发**：`design.md:28, 64, 91` 依赖「`proactive-plan` 不挂 `send_message`」与「`TaskExecutionDriver` 仅推进 `doing`」来保证零自动执行。但 `proactive-plan` 挂载了 `task_graph`，而 `apps/im-server/src/task-graphs.ts:692-858` 允许 `actor.kind === 'agent'` 直接创建或更新 `status: "doing"`（负责人指向 PA 自身）。一旦模型在 `proactive-plan` 中误填 `status: "doing"`，`im-server` 立即下发 `task.execution.changed`，唤醒**拥有全套 `send_message` / `delegate_worker` 工具的主 PA 会话**在凌晨自动开工并发信。同时，设计未定义 `im-server` 对 `proposed -> doing | todo` 的鉴权边界：既要拦截无真人指令的后台自批，又要保留主人在私聊用自然语言同意时 PA 凭本轮真实人类 `source_message_id` 代为翻牌的路径（`spec.md:255`）。
  3. **自定义 `host.agents.create` 会话的正式记忆仓只读守卫缺失**：`design.md:21, 91, 231` 说明 `proactive-plan-<id>` 与 `dreaming-<id>` 同构并可读写“工作区文件”。但 `runDreamingAgent`（`dreaming-agent.ts:60-103`）通过 `host.agents.create` 手工装配工具（不走普通前景会话预设），其 `tools/pre-execute` 恰恰放行了对 `.nanoassistant/memory` 的写入与无沙箱 `bash`（`:94-99`）。若 `proactive-plan` 以 `<workspace>` 为根目录开放工作区文件写权限或 `bash` 而未显式挂载 `.nanoassistant/` 拒绝规则（含符号链接逃逸检查），后台筹划可直接改写 `.nanoassistant/memory/`，破坏 `feat-676` 正式记忆单写者红线。
- **未修后果**：
  - 夜间筹划或静默对账可能伪造人类消息凭据、在凌晨唤醒主会话执行未批准构想并对外发消息、或污染 `.nanoassistant/memory/` Git 仓，直接击穿 `spec.md:251, 295` 与 `SPEC.md` / `feat-676` 安全边界。（需在 `global-agent.ts` 仅当调用处于活跃人类轮次且非后台维护会话时传递 `source_message_id`；在宿主对 `proactive-digest`/`proactive-plan` 的 `task_graph` 强制限定私人会话、禁 `delete`、`proactive-plan` 禁写 `doing`/`todo` 执行态；在 `im-server` 要求 `proposed` 批准出列必须具备 `actor.kind === 'user'` 或当轮已核验主人 `source_message_id`；并对 `proactive-plan` 物理封禁 `.nanoassistant/` 写入与 `bash`。）

#### `R1-C4` [CRITICAL] `waiting(kind: "decision")` 漏改 `packages/personal-assistant/src/task-execution.ts` 导致 256 轮自动修复死循环，且负责人与焦点可见性校验不闭合

- **位置**：
  - `docs/changes/feat-785-pa-proactivity/design.md:12, 14, 152-156, 175, 179`
  - `docs/changes/feat-785-pa-proactivity/specs/gateway/task-graphs.md:24-31`、`specs/im/task-graphs.md:27-32`
  - 代码基线：`packages/personal-assistant/src/task-execution.ts:52-64`、`packages/dsh-integration/src/task-execution.ts:154-175`、`apps/im-server/src/task-graphs.ts:519, 898-955`
- **证据**：
  1. **漏改 Node 侧等待校验器**：`design.md:12, 175` 只列出了修改 `apps/im-server/src/task-graphs.ts`（`validateWait`）和 `packages/dsh-integration/src/task-execution.ts`，遗漏了中间层 `packages/personal-assistant/src/task-execution.ts:52-64`。该文件的 `TaskExecution.snapshotAdmitted()` 会遍历 `task.execution.snapshot` 返回的所有 `task.status === 'waiting'` 节点并无条件调用 `this.inspect({ schedule_id: task.wait?.schedule_id ?? '' })`。当节点为无闹钟的 `kind: "decision"` 时，`inspect` 因空 `schedule_id` 返回 `{ valid: false, reason: 'missing' }`，将该节点压入 `repair_task_ids` 并置 `snapshot.kind = 'continue'`，进而驱动 `TaskExecutionDriver`（`dsh-integration/src/task-execution.ts:164-174`）连续自动唤醒 Agent 多达 256 轮要求补挂 Schedule。
  2. **负责人约束与群聊指向歧义**：现行 `apps/im-server/src/task-graphs.ts:519` 强制要求 `waiting` 节点的 `assignee.type === 'agent'`，设计未说明真人负责的事项是否也可置为 `waiting(decision)` 等待他人拍板；同时 `TaskWait`（`design.md:155`）将 `asked_user_id` 设为可选，若在多人团队群聊中省略 `asked_user_id`（或填入非本会话活跃成员），`GET /im/v1/task-graphs/focus` 的 `needs_you` 规则（`design.md:179`：“指向本人的 `waiting(decision)`”）将导致该待决问题在所有成员的焦点台中全部不可见。反之，`design.md:179` 将“有权写入的团队会话中处于 `proposed`”的节点无差别放入所有群成员的 `needs_you`，会让单个成员或 Agent 的未定提议刷进全群每个人的「待你拍板」首屏。
- **未修后果**：
  - Agent 一旦使用 `waiting(kind: "decision")` 即陷入最高 256 次的无意义续跑修复风暴，彻底违背“免挂轮询闹钟、安静等真人回复”的核心目标（`spec.md:214-216`）；多人协作群中的待决策卡与提议卡会出现“无人可见”或“全员被刷屏”的错配。

#### `R1-W1` [WARNING] `proactive_planning` 配置归一化与依赖表未隔离普通 Agent 且改变存量配置指纹，破坏滚动升级与非 PA 能力开关

- **位置**：
  - `docs/changes/feat-785-pa-proactivity/design.md:102-103, 165, 345-346`
  - `docs/changes/feat-785-pa-proactivity/specs/gateway/agent-capabilities.md:7-16`
  - 代码基线：`packages/product-contracts/src/configuration.ts:9-62`、`packages/product-contracts/src/capabilities.ts:28-55, 80-95`、`apps/im-server/src/agent-creation.ts:175-182`、`apps/node/src/configuration.ts:55, 120`、`packages/personal-assistant/src/configuration.ts:50-65`、`packages/dsh-integration/src/index.ts:506`
- **证据**：
  1. **指纹兼容冲突**：`design.md:345-346` 声称由 `CanonicalAgentConfiguration` 对未保存过 `proactive_planning` 的存量 PA 归一化补入 `true`，同时建议先升 `im-server` 再升 `node`。但在 `packages/product-contracts/src/configuration.ts:9-62` 中，`agentConfigurationFingerprint` 直接对 `canonicalAgentConfiguration` 计算 SHA-256；若改写存量候选对象的 `features` 字典，新 `im-server` 与未升级 `node`（以及 `agent_config_operations` 表中的历史 `candidate_fingerprint` / `expected_previous_fingerprint`）将立即产生指纹不一致，导致滚动窗口内配置保存与恢复报错。仓库既有 `dreaming` 默认开启做法（`apps/node/src/configuration.ts:55, 120`）是不改写 `canonicalAgentConfiguration` 存储值，仅在 `effectiveFeatures` 层按默认值生效。
  2. **`featureDependencies` 无角色入参**：`packages/product-contracts/src/capabilities.ts:28-50` 的 `featureDependencies` 与 `effectiveFeatures(features)` 不感知 `personal_agent` 角色。直接向 `featureDependencies` 加入默认开启的 `proactive_planning`（依赖 `task_graph`，传递依赖 `cron_scheduling`），会导致 `apps/im-server/src/agent-creation.ts:176-178` 新建普通团队 Agent 时自动写入 `proactive_planning: true`，并在 `changeCapability` / `validateCapabilities` 中阻止普通 Agent 关闭 `task_graph` 或 `cron_scheduling`。
- **未修后果**：
  - `im-server` 先于 `node` 滚动升级时 PA 配置更新/对账因指纹漂移失败；普通非 PA 团队 Agent 被误开启 `proactive_planning` 或被锁死 `task_graph` 依赖开关。

#### `R1-W2` [WARNING] 静默 UI 翻牌结果无通往 `Dreaming` 的事件/拉取通道，且夜间筹划触发周期与 `dreaming` 特性/白天运行耦合失当

- **位置**：
  - `docs/changes/feat-785-pa-proactivity/design.md:14, 165, 202-205, 232-233, 335`
  - `docs/changes/feat-785-pa-proactivity/specs/gateway/agent-capabilities.md:20-26`、`specs/gateway/personal-agent.md:10-13`
  - 代码基线：`packages/dsh-integration/src/knowledge/dreaming.ts:190-215`、`apps/im-server/src/task-graphs.ts`、`packages/dsh-integration/src/knowledge/runtime.ts:126-131`
- **证据**：
  1. **UI 翻牌无会话增量导致 `Dreaming` 跳过不跑**：`design.md:185` 关闭了 PA 私聊的任务系统通知，且用户在焦点台或私聊活卡片点击「关闭 / 放远期」直连 `im-server` 改库，不产生任何 DSH 会话消息。而在 `packages/dsh-integration/src/knowledge/dreaming.ts:204` 中，当 `!batch.units.length && !pendingMaterial` 时 `Dreaming.execute` 直接以 `no_eligible_increment` 退出不调模型，且 `dsh-integration` 目前没有任何 RPC 从 `im-server` 拉取自上次游标以来的 `triage_outcome` 记录。若用户仅在界面连续两次点掉同类提议而未发私聊消息，`Dreaming` 根本感知不到这两次拒绝。
  2. **夜间窗口与 `dreaming` 开关解耦缺失**：`design.md:14, 202-204` 将 `proactive-plan` 挂在 `dreaming.ts` 之后作为“下半场”，但 `Dreaming` 按间隔 + 10 分钟安静在**白天**也会运行，而 `proactive-plan` 只应在用户本地夜间窗口执行；反过来，`design.md:165` 定义 `proactive_planning` 仅依赖 `task_graph`（不依赖 `dreaming`），若用户关闭了 `dreaming` 或当晚无新对话但长线目标需要夜间起草 `prep_draft`，仅靠 `dreaming.ts` 串联会导致夜间筹划不触发。此外，关闭 `proactive_planning`、`agent.disable` 与节点更新屏障（`UpdateBarrier`）需同步中断在途 `proactive-digest` / `proactive-plan` 会话。
- **未修后果**：
  - `spec.md:283` 要求的“无需聊天解释、连续两次点掉同类提议即自动收敛克制规则”在纯 UI 翻牌路径下失灵；主动筹划可能误在白天空闲触发，或在关闭 `dreaming` 时静默罢工。

#### `R1-W3` [WARNING] 消息 `task_cards` 契约位置与现有扁平消息模型不符，且遗漏 `messages` 表迁移、发送幂等摘要、外发审计与客户端本地缓存

- **位置**：
  - `docs/changes/feat-785-pa-proactivity/design.md:12, 15, 166, 182-183, 288, 342-344`
  - `docs/changes/feat-785-pa-proactivity/specs/im/task-graphs.md:45-59`
  - 代码基线：`packages/product-contracts/src/chat.ts:61-75, 118-135`、`packages/dsh-integration/src/message-arguments.ts:4-51`、`apps/im-server/src/schema.sql:136-166`、`apps/im-server/src/message-records.ts:10-32`、`apps/im-server/src/messaging.ts:486`、`apps/im-server/src/personal-actions.ts:154`、`packages/personal-assistant/src/personal-assistant.ts:189`、`packages/personal-assistant/src/global-agent.ts:868`、`src/IM/frontend/src/features/chat/components/message-pane.tsx:2218`、`src/IM/ios/NanoIM/Features/Chat/{ChatModels,ChatStorageController}.swift`
- **证据**：
  1. **消息字段层级不一致 & 前端定位路径偏差**：`design.md:12, 166` 将字段定为 `metadata.task_cards?: TaskCardRef[]`，但 `product-contracts/src/chat.ts:118-135`、`apps/im-server/src/message-records.ts:10-32`、Web `chat-types.ts` 与 iOS `ChatModels.swift:141-172` 全部采用顶层平铺字段（如 `attachments`、`interactive`、`reply_to`、`system_notice`），不存在 `metadata` 对象。（另：`design.md:15, 288` 引用的 `src/features/chat/message-pane.tsx` 真实路径为 `src/IM/frontend/src/features/chat/components/message-pane.tsx`。）
  2. **持久化、幂等与缓存链路遗漏**：①`apps/im-server/src/schema.sql:136` 的 `messages` 表及启动期兼容 `ALTER TABLE` 未列入设计（`design.md:342-344` 仅讨论了 `task_graphs.document_json`）；②`packages/dsh-integration/src/message-arguments.ts:4-51` 的 JSON Schema 校验及空正文 + 纯 `task_cards` 是否合法的规则未定义；③`AgentPublication`（`chat.ts:61`）、`publicationBody` 幂等哈希（`personal-assistant.ts:189`、`global-agent.ts:868`）、`publishAgent` 幂等冲突校验（`messaging.ts:486`）与 `pa.action.prepare/commit` 披露摘要（`personal-actions.ts:154`）均需纳入 `task_cards`，否则重试或审计摘要会失配；④iOS 本地 SQLite 消息缓存（`ChatStorageController.swift`）需持久化该字段并在收到 `task_graph.changed` WS 事件时刷新聊天内嵌卡片状态；⑤发往飞书等外部桥接会话时需定义文本退化摘要而非静默丢卡。
- **未修后果**：
  - 前后端字段名/层级分叉、`im-server` 旧库升级缺列报错、携带 `task_cards` 的消息幂等校验误判，或 iPhone 冷启动/跨端翻牌后私聊卡片丢失与不刷新。

#### `R1-W4` [WARNING] Web 与 iPhone 体验及原型存在 5 处交互断点：群任务创建入口丢失、非默认范围视图未定义、多层子图与 iOS 编辑动作缺失、前置阻塞批准反馈失真、双端 PA 开关保存与依赖模型冲突

- **位置**：
  - `docs/changes/feat-785-pa-proactivity/design.md:15-16, 173, 276-278, 285-299`
  - `docs/changes/feat-785-pa-proactivity/prototype.html:1040-1055, 1080, 1260-1265, 1301-1359, 1491-1515`
  - 代码基线：`src/IM/frontend/src/features/tasks/{task-progress,task-graphs-page}.tsx`、`src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:1888-1935, 2101`、`src/IM/ios/NanoIM/Features/Tasks/TasksView.swift:310-430`、`src/IM/ios/NanoIM/Features/Agents/{PersonalAgentManagementView,AgentConfigView}.swift`
- **证据**：
  1. **团队群任务新建入口与无 PA 兜底目标缺失**：旧 `task-progress.tsx` 的「新建根任务」弹窗支持选择目标群聊会话；`prototype.html:1049` 将其整体替换为无会话选择器的单行速建框后，用户在 `/tasks` 或 iOS「任务」Tab 无法再为团队群创建目标/任务，且设计未定义尚未开通 PA 的用户回车速建时绑定哪个 `conversation_id`。
  2. **删除 `task-progress.tsx` 后「按负责人 / 团队全部」布局与状态筛选接口未定义**：`prototype.html:1040-1042` 虽保留了「按负责人」「团队全部」顶栏按钮，但点击仅切换高亮样式、仍渲染同一份「与我有关」DOM；设计未定义这两个范围在九状态模型下的分组结构与分页方式，也未同步更新 `GET /im/v1/task-graphs` 的 `statuses` 过滤参数以支持 `proposed,backlog`。
  3. **多层嵌套子图钻取与 iOS 目标内页编辑能力缺失**：`docs/specs/im/task-graphs.md:48, 69` 支持多层级嵌套 `dag`/`explore` 容器（如阶段节点内部再拆子阶段或探索分支），但桌面阶段列与手机纵向阶段流仅展示了单层扁平阶段，未定义嵌套子容器的展开/面包屑钻取交互。同时在 `ios-goal.png`（`prototype.html:1301-1359`）中，「前序已完成 · 2 阶段」不可点击展开回看，且整页无「添加子节点」与打开既有节点完整详情/编辑页（`TaskNodeView` / `TaskEditorView`）的入口，较现有 `TasksView.swift` 发生功能回退。
  4. **全景图前沿新芽漏掉「关闭」动作，且前置未完节点的批准文案与实际状态矛盾**：`goal-web.png`（`prototype.html:1260-1263`）的前沿 `proposed` 新芽仅提供「批准 / 放远期」，缺少 `specs/im/task-graphs.md:10, 41` 要求的「关闭」入口；同时 `design.md:173` 规定当前置 `dag` 阶段未完成时批准 `proposed` 节点应进入 `todo` 而非 `doing`，但 `prototype.html:1080, 1261` 对前置阶段 3 仍在推进中的阶段 4 新芽仍显示「批准开工」并在点击后直接标为「推进中（`doing`）」，会误导用户以为后台已跳过前置立即开工。
  5. **Web / iOS PA「主动筹划」开关保存机制与二级配置页依赖阻断冲突**：Web 现有 `AgentDetailPage`（`agent-detail-page.tsx:1888, 2101`）中 `BehaviorCard` 特性开关需点击页脚统一「保存」按钮走版本乐观锁，而 `prototype.html:1491`（`settings-online.png`）将其画成位于「聊天观察范围」上方的独立即时切换卡片；iOS 端一级 `PersonalAgentManagementView.swift` 仅对接 `/im/v1/personal-agent`、不持有 `AgentConfig` / `profile_version` 与 `AgentCapabilities`，且二级 `AgentConfigView.swift` 对 PA 隐藏了 `proactive_planning`（`design.md:103, 289`）——这会导致用户在二级页尝试关闭 `task_graph`（或 `cron_scheduling`）时被 `required_by_feature: ["proactive_planning"]` 拦截，但在当前页面根本找不到可先关闭的 `proactive_planning` 开关。
- **未修后果**：
  - 实施阶段在 `must-match` 原型约束与双端真实组件架构之间出现硬冲突，造成团队群建任务退化、多层任务图无法进入下层、iOS 无法编辑目标节点，以及 iOS 二级配置页出现无法解除的隐藏依赖死锁。

#### `R1-W5` [WARNING] Delta-specs 未清理 `gateway/personal-agent.md` 存量冲突断言，且 `im/task-graphs.md` 整段替换时误删多层逐级浏览与大数据量增量加载契约

- **位置**：
  - `docs/changes/feat-785-pa-proactivity/specs/gateway/personal-agent.md` 对照 `docs/specs/gateway/personal-agent.md:12-16`
  - `docs/changes/feat-785-pa-proactivity/specs/im/task-graphs.md:6-11, 27-44` 对照 `docs/specs/im/task-graphs.md:72-97`
- **证据**：
  1. **存量条文自相矛盾**：`docs/specs/gateway/personal-agent.md:15` 现行 `Requirement: PA 复用完整 Global 执行能力` 的 Scenario 原文写有：**“不增加主人输入审核或 PA 目标引擎”**。本次 `specs/gateway/personal-agent.md` 未修改该条 Requirement，归并后同一份 canonical spec 将同时断言“不增加 PA 目标引擎”与“PA 分层静默维护个人目标图”。
  2. **误删既有嵌套层级与分页加载保证**：`specs/im/task-graphs.md:27-44`（`MODIFIED Requirement: 每个拆分层级提供结构与完成情况视图`）全量替换原条文时，删去了 `Scenario: 查看大任务并逐层进入`（多层嵌套子作用域进入与面包屑返回）和 `Scenario: Web 五列独立自然加载`（单区超 50 条时的有界分页/增量加载），但未补充北极星全景图对多层子作用域的钻取契约，也未声明焦点台、`远期与已完结`、`按负责人 / 团队全部` 在任务量增长后的分页或截断契约。
  3. **`proposed` 批准状态判据与口头批准契约未写入 `im/task-graphs.md`**：`specs/im/task-graphs.md:10` 仅写“批准后节点按排期进入 `todo` 或直接进入 `doing`”，未写明确定性判据（Agent 负责且无未完结 `dag` 前置进 `doing`，否则进 `todo`）及主人在私聊自然语言同意的等价批准路径（`spec.md:255`）。
- **未修后果**：
  - 归并后 `docs/specs/gateway/personal-agent.md` 出现前后矛盾的规范断言，`docs/specs/im/task-graphs.md` 丢失多层任务结构导航与长列表有界加载的正式契约保护。

### Recommendations

- **`R1-R1`**：在 `design.md:227, 248-260` 明确 `<proactive-focus-snapshot>` 超出 `1,500` 字符预算时的确定性裁剪优先级与省略提示（例如优先保留 `unbriefed_prep_drafts` 与 `open_proposals_awaiting_owner`，再按最近更新时间保留前 N 条 `active_focus_frontiers` 并附 `+K more via task_graph(list)`），避免直接按字符截断破坏 XML 闭合标签或末尾 `guidance`。
- **`R1-R2`**：针对 `design.md:346` 提到的滚动升级窗口兼容，建议在 M1 `[worker]` 测试项中显式加入一条 iOS `TaskModels` 未知 `status` / 未知 `wait.kind` 安全解码回退单测，防止后续再扩枚举时导致旧客户端整页解码失败。


### Author Resolutions

- **`R1-C1` — `accepted`**：核实属实（`packages/dsh-integration/src/cron-owners.ts:58`、`index.ts:153-157` 原生 `ScheduleService` 在子进程直接推入 `source.kind === "schedule"`，且 IM 观察读取 RPC 实名为 `pa.observations.read`）。已在 `design.md`（§现状分析、§架构总览、§关键决策 D6、§接口与数据流 3/4、§Milestones）与 `specs/gateway/personal-agent.md` 补齐：①在 `dsh-integration` 的 `agent/pre-step` 拦截 PA 主会话 `source.kind === "schedule"` 反向调用 `product.proactive.prepare_wake` 执行 `pa.observations.read` 并追加 `<proactive-focus-snapshot>`；②`proactive-coordinator` 通过 `schedule.command({ action: 'jobs' })` 读取主会话早间 `[06:00, 11:30]` 计划以决定默认早报是否自动让路；③将 `briefed_at` 改为仅对本轮快照批次或 `task_cards` 实际呈报并送达的条目打标。
- **`R1-C2` — `accepted`**：核实属实（`PersonalAssistant.send()` 缺少 `publicationEvidence` 且 `inbox.ts:711` 硬编码 `i.attention=1`）。已在 `design.md`（§现状分析、§关键决策 D5、§接口与数据流 1/3、§Milestones）与 `specs/gateway/personal-agent.md` 修正：①在 `TaskNode` 增加通用 `source_conversation_ids` 并在 `TaskResponsibility` / 唤醒快照中透出，使纯文本推进/等待提醒也具备关联观察群范围；②`PersonalAssistant.send()` 先调 `pa.observations.read`，再执行 `publicationEvidence`（将 `pendingReadCalls` 放宽至覆盖 `attention IN (0, 1)`）冲刷同轮 `inbox(read)` 记录，随后用 `proactiveBlocking` 拦截剩余未读新消息，彻底消除同轮重发死循环。
- **`R1-C3` — `accepted`**：核实属实（`global-agent.ts:796-800`、`im-server/src/task-graphs.ts:692-858`、`dreaming-agent.ts:60-103`）。已在 `design.md`（§关键决策 D2/D4、§接口与数据流 2/4、§Milestones）及 `specs/im/task-graphs.md`、`specs/gateway/personal-agent.md` 建立三重机械隔离：①`global-agent.ts` 仅在 `call.sessionId === binding.sessionId` 且根会话处于尚未 `turn/end` 的活跃真人轮次时才传递 `source_message_id`；②宿主桥接禁止 `proactive-plan` 调用 `delete` 或写入非 `"proposed"` 创建态，且 `im-server` 要求脱离 `"proposed"` 进入 `"doing" | "todo"` 必须具备 `actor.kind === "user"` 或当轮 `verifiedHuman`（否则返回 `403`）；③`proactive-digest` / `proactive-plan` 不挂 `bash` 与外发工具，并挂载真实路径解析守卫拒绝写入 `.nanoassistant/memory/**` 与 `ROLE.md`。
- **`R1-C4` — `accepted`**：核实属实（`packages/personal-assistant/src/task-execution.ts:52-64`）。已在 `design.md`（§涉及范围、§关键决策 D2、§接口与数据流 1/2、§Milestones）与 `specs/im/task-graphs.md` 补齐：①`TaskExecution.snapshotAdmitted` 对 `wait.kind === "decision"` 跳过 `inspect` 且不列入 `repair_task_ids`；②`waiting(decision)` 允许任意负责人，单聊自动补全对端真人 `asked_user_id`，群聊强制指定成员真人 `asked_user_id`；③焦点台 `needs_you` 仅收录本人私人空间 `proposed` 或显式指定本人的团队节点，不向全群无关成员刷屏。
- **`R1-W1` — `accepted`**：核实属实（`configuration.ts:52-58`、`capabilities.ts:28-50`）。已在 `design.md`（§关键决策 D7、§接口与数据流 1、§一次性部署迁移、§Milestones）与 `specs/gateway/agent-capabilities.md` 修正：不改写 `canonicalAgentConfiguration` 存储值（保持存量 SHA-256 指纹零漂移）；在 `FeatureDependency` 引入 `roles: ['personal']` 与 `definitionsForRole(isPersonal)`，使普通非 PA Agent 完全不暴露也不受 `proactive_planning` 依赖约束。
- **`R1-W2` — `accepted`**：核实属实（`dreaming.ts:204`）。已在 `design.md`（§关键决策 D4、§接口与数据流 2/3/4、§Milestones）与 `specs/gateway/{personal-agent,agent-capabilities}.md` 修正：①新增 `pa.proactive.feedback` 增量游标将静默 UI 翻牌结果作为 `Dreaming` 合格 `pendingMaterial`；②`proactive-plan` 采用独立本地夜间窗口（`01:00–05:00`）调度，与 `dreaming` 开关解耦（同夜两者均到期时先跑 `Dreaming` 再跑筹划，白天 `Dreaming` 不触发筹划），并接入生命周期与配置关闭取消链。
- **`R1-W3` — `accepted`**：核实属实（修正前端路径为 `src/features/chat/components/message-pane.tsx`）。已在 `design.md`（§涉及范围、§关键决策 D3、§接口与数据流 1/2、§一次性部署迁移、§Milestones）与 `specs/im/{task-graphs,ios-client}.md` 将字段统一为顶层 `ChatMessage.task_cards`，补齐 `messages.task_cards_json` 启动期加列、`message-arguments.ts` 校验、发送幂等哈希与 PA 外发审计纳入、飞书纯文本退化摘要，以及 iOS `ChatStorageController` 本地 SQLite 缓存与 `task_graph.changed` 实时刷新。
- **`R1-W4` — `accepted`**：已在 `prototype.html`、`evidence/prototype-walkthrough.md`、`design.md`（§前端原型）与 `specs/im/{task-graphs,personal-agent,ios-client}.md` 全部补齐并重绘截图：①速建栏增加归属会话选择胶囊（支持切团队群）与「完整新建…」入口；②实装「按负责人 / 团队全部」切换视图与九状态过滤；③补齐多层子脉络钻取入口及 iOS 前序展开、`+ 子节点`、详情/编辑入口；④全景新芽补齐「关闭」，并将受阶段 3 阻塞的阶段 4 新芽改为「批准立项 → 待办（等前置完成）」，与无前置单卡「批准开工 → 推进中」准确区分；⑤对齐 Web 与 iOS 二级 `AgentConfigView` 统一保存与同页 `task_graph` 依赖轻提示（iOS 一级页以状态行跳转进入），消除隐藏依赖死锁。
- **`R1-W5` — `accepted`**：已在 `specs/gateway/personal-agent.md` 新增 `MODIFIED Requirement: PA 复用完整 Global 执行能力` 消除旧“不增加 PA 目标引擎”措辞矛盾；在 `specs/im/task-graphs.md` 补齐多层子作用域钻取 Scenario、有界增量加载 Scenario 以及确定性 `proposed` 批准状态判据与口头批准契约。
- **`R1-R1` & `R1-R2` — `accepted`**：已在 `design.md` §接口与数据流 4 写入 `<proactive-focus-snapshot>` 1,500 字符按优先级整条裁剪与省略提示规则（`R1-R1`），并在 `M1` `[worker]` 退出标准第 ⑤ 条显式加入 iOS `TaskModels` 未知 `status` / `wait.kind` 兜底解码单测（`R1-R2`）。


---

## Round 2

### Metadata

- **reviewer**: `change-design-reviewer` (same independent subagent instance as Round 1, integrating `codebase-design`, `agent-context-review`, `frontend-experience-review`)
- **target**: `docs/changes/feat-785-pa-proactivity` (`design.md`, `prototype.html`, `evidence/prototype-walkthrough.md`, `evidence/screens/*.png`, `specs/im/{task-graphs,personal-agent,ios-client}.md`, `specs/gateway/{task-graphs,personal-agent,agent-capabilities}.md`)
- **review_mode**: `delta`
- **mode_reason**: `spec.md` user goals (Q1–Q7), single-table `schema_version: 2` model, 180-day `scheduled` wait, North Star continuation anchor, and single-milestone `M1` structure are unchanged; Round 2 changes are bounded to resolving `R1-C1`..`R1-C4`, `R1-W1`..`R1-W5`, and `R1-R1`..`R1-R2` across cross-process RPC bridges, runtime guards, Web/iOS prototype states, and the 6 delta-specs.
- **retained_from**: `Round 1` (`spec.md` Q1–Q7 alignment, `SPEC.md` single-direction package boundaries, `NoSilentPrefixRewrite` prefix-cache design for append-only wake messages and short-lived maintenance sessions, single-table `schema_version: 2` evolution, and `M1` isolated E2E Runbook & cleanup).
- **started_at**: `2026-11-25T14:46:53+09:00`
- **completed_at**: `2026-11-25T14:52:05+09:00`
- **duration**: `5m 12s`

### Verdict

**Approved** — `0 CRITICAL / 0 WARNING` (plus `1 Recommendation`)

### Coverage 与证据

- **`retained_from: Round 1`**：`spec.md` 未发生变更；原位升级 `task_graphs` `schema_version: 2`、`SPEC.md` 依赖方向、`NoSilentPrefixRewrite` 缓存前缀保护基线及单里程碑 `M1` 隔离验证拓扑保持不变，直接沿用 Round 1 已核实的证据。
- **本轮变更与波及范围（`delta` 展开核查）**：
  1. **原生 Cron 跨进程桥接、同轮新鲜度冲刷与 `decision` 等待闭环（`codebase-design`）**：
     - 对照 `packages/dsh-integration/src/{task-execution.ts:101-153, cron-owners.ts:77-88, context-order.ts:8-18}` 核实了修订方案（`design.md:13-14, 29-30, 95-101, 165-166, 208-214`）：`CronOwners.catalog`（即 `schedule.command({ action: 'jobs' })`）直接返回 `scheduledAt`、`sessionId` 与 `status === 'active'`，足以让 `proactive-coordinator` 确定性判定用户本地 `[06:00, 11:30]` 是否存在主会话原生 Cron；同时在 `dsh-integration` 的 `agent/pre-step` 拦截 PA 主会话 `source.kind === "schedule"` 反向调用 `product.proactive.prepare_wake`（拉取 `pa.observations.read` 并注入 `<proactive-focus-snapshot>`），与现有 `TaskExecutionDriver` 在 `agent/pre-step` 异步拉取 `snapshot` 并追加系统消息的机制完全同构。
     - `PersonalAssistant.send()` 补入 `pa.observations.read` → `publicationEvidence`（放宽 `pendingReadCalls` 覆盖 `attention IN (0, 1)`）→ `proactiveBlocking`（结合 `TaskNode.source_conversation_ids`）三步闭环，既覆盖无 `task_cards` 的纯文本推进提醒，又消除了同轮 `inbox(read)` 后重发的死循环。
     - `packages/personal-assistant/src/task-execution.ts` 的 `snapshotAdmitted` 对 `wait.kind === "decision"` 显式跳过 `inspect`，消除 256 轮修复唤醒风暴；单聊自动解析/群聊必填 `asked_user_id` 与团队 `proposed_for_user_id` 收敛了多人焦点台的可见范围。
  2. **后台筹划三重机械隔离、零指纹漂移角色特性与顶层 `task_cards` 全链路（`codebase-design`）**：
     - `global-agent.ts` 限制仅根会话且处于未 `turn/end` 的活跃真人轮次才透传 `source_message_id`，配合宿主禁止 `proactive-plan` 调用 `delete`/写入执行态、服务端 `403 proposal_approval_requires_human` 门禁，以及 `proactive-runner.ts` 剥离 `bash`/外发工具并按 `realpath` 封禁写入 `.nanoassistant/memory/**` 与 `ROLE.md`（`design.md:64, 92, 175, 232`），彻底闭合了凌晨越权自启动与正式记忆写旁路。
     - 对照 `packages/product-contracts/src/capabilities.ts` 与 `apps/im-server/src/db.ts:25-32` 核实：`canonicalAgentConfiguration` 保持零改动（零 SHA-256 指纹漂移），`definitionsForRole(isPersonal)` 隔离普通非 PA Agent；消息字段统一为顶层 `ChatMessage.task_cards`，`messages.task_cards_json` 启动期幂等加列、幂等摘要、PA 外发审计、飞书纯文本退化与 iOS `ChatStorageController` 本地 SQLite 缓存全部闭合。
  3. **Agent Context 增量审查（`agent-context-review`）**：
     - `design.md:227-235, 241-253` 补齐了原生 `schedule` `pre-step` 唤醒注入、`1,500` 字符按条目优先级结构化裁剪（预留 220 字符闭合壳与 `guidance`，不硬截断破坏标签）、`active_focus_frontiers` 透出 `source_chats`，以及 `pa.proactive.feedback` 游标唤醒 `Dreaming` 学习纯 UI 连续两次关闭提议的输入链。四条消费链均保持首轮快照前缀稳定。
  4. **前端原型重绘与体验复审（`frontend-experience-review`）**：
     - 重新阅读更新后的 `prototype.html`（1–1627 行）、`evidence/prototype-walkthrough.md`，并逐张目视复核全部 10 张重渲染截图（`focus-web.png`、`focus-triaged.png`、`goal-web.png`、`chat-web.png`、`focus-mobile.png`、`ios-goal.png`、`ios-draft.png`、`ios-chat.png`、`settings-online.png`、`settings-offline.png`）：
       - `focus-web.png` / `focus-mobile.png`：速建栏已具备 `归属：小助私聊` 会话选择胶囊（支持切 `研发日常群`）与桌面端 `完整新建...` 入口；顶栏 `按负责人 / 团队全部` 可真实切换对应视图；无前置单卡按钮显示 `批准开工`，受前置阻塞的阶段 4 新芽显示 `批准立项`。
       - `focus-triaged.png`：批准后无前置单卡显示 `推进中 · 小助运行中`，受阶段 3 阻塞的新芽准确显示为紫色 `待办 · 等前置阶段 3 完成`（不再误标为推进中），右下脱离文档流浮层不挤动卡片。
       - `goal-web.png` / `ios-goal.png`：桌面与手机阶段节点均补齐 `进入子脉络 (3) ›` 多层钻取入口，前沿新芽补齐 `批准立项 / 放远期 / 关闭` 三动作；`ios-goal.png` 顶栏具备 `+ 子节点`，前序折叠卡提供可交互 `展开查看 ›`，前沿卡具备 `详情/编辑 ›`，底部标签栏完整无裁切。
       - `settings-online.png` / `settings-offline.png`：`主动筹划` 与 `任务图` 同处「运行设置」页共用右上 `保存` 按钮与依赖提示（开启主动筹划时关任务图弹出明确轻提示），离线时展示只读横幅并禁用全部开关与保存按钮，消除了跨页隐藏依赖死锁。
  5. **Delta-specs 与 `M1` 退出标准核查**：
     - 对照 `docs/specs/gateway/personal-agent.md:11-50`、`docs/specs/im/personal-agent.md:70-106`、`docs/specs/im/ios-client.md:250-294` 逐条核对全部 6 份更新后的 delta-spec：所有 `MODIFIED` Requirement 完整保留了仍适用的存量 Scenario，消除了“不增加 PA 目标引擎”的存量条文冲突，补回了多层子作用域逐级钻取与有界增量加载契约；`M1` `[reviewer]` 与 `[worker]` 退出标准已完整覆盖新增安全门禁、Cron 桥接、同轮新鲜度重发与 iOS 兜底解码测试。

### 历史问题闭环

- **`R1-C1`** — **Author Resolution**: `accepted`（增加 `dsh-integration` `agent/pre-step` 的 `product.proactive.prepare_wake` 桥接、`schedule.command(jobs)` 早间让路检测、修正 `pa.observations.read` RPC 名并改为条目级 `briefed_at`）。**本轮证据**: `design.md:13-14, 29, 98-101, 208-215`、`specs/gateway/personal-agent.md:25-30`，与 `packages/dsh-integration/src/{task-execution.ts:101-153, cron-owners.ts:77-88}` 现有机制吻合 — **`closed`**。
- **`R1-C2`** — **Author Resolution**: `accepted`（新增 `TaskNode.source_conversation_ids`，`PersonalAssistant.send()` 先执行 `pa.observations.read` 与覆盖 `attention IN (0, 1)` 的 `publicationEvidence` 再检查 `proactiveBlocking`）。**本轮证据**: `design.md:13, 30, 95-96, 165-166, 213, 322`、`specs/gateway/personal-agent.md:20-24` — **`closed`**。
- **`R1-C3`** — **Author Resolution**: `accepted`（`global-agent.ts` 仅活跃根会话真人轮次透传 `source_message_id`、宿主限制 `proactive-plan` 状态/动作且 `im-server` 对无真人凭据自批 `proposed` 返回 403、`proactive-runner.ts` 禁 `bash` 并按 `realpath` 封禁写 `.nanoassistant/memory/**` 与 `ROLE.md`）。**本轮证据**: `design.md:13-14, 21, 64, 92, 175, 232, 352`、`specs/im/task-graphs.md:9-13`、`specs/gateway/personal-agent.md:14-19` — **`closed`**。
- **`R1-C4`** — **Author Resolution**: `accepted`（`packages/personal-assistant/src/task-execution.ts` 的 `snapshotAdmitted` 对 `decision` 跳过 Schedule 核验，完善单聊/群聊 `asked_user_id` 与团队 `proposed_for_user_id` 校验及焦点过滤）。**本轮证据**: `design.md:13, 28, 65, 129, 156, 176, 180, 352`、`specs/gateway/task-graphs.md:11-14`、`specs/im/task-graphs.md:58-60, 146-154` — **`closed`**。
- **`R1-W1`** — **Author Resolution**: `accepted`（不改写 `canonicalAgentConfiguration` 保持指纹零漂移，引入 `roles: ['personal']` 与 `definitionsForRole(isPersonal)` 隔离普通 Agent）。**本轮证据**: `design.md:11, 23, 31, 103-104, 167, 330, 352`、`specs/gateway/agent-capabilities.md:5-13` — **`closed`**。
- **`R1-W2`** — **Author Resolution**: `accepted`（新增 `pa.proactive.feedback` 增量游标作为 `Dreaming` 合格 `pendingMaterial`，独立 `01:00–05:00` 夜间调度与 `dreaming` 解耦并接入取消链）。**本轮证据**: `design.md:12-14, 91, 93, 177, 202-206, 234, 352`、`specs/gateway/agent-capabilities.md:25-28`、`specs/gateway/personal-agent.md:14-19` — **`closed`**。
- **`R1-W3`** — **Author Resolution**: `accepted`（统一顶层 `ChatMessage.task_cards`、修正 Web 聊天组件路径、补齐 `messages.task_cards_json` 启动加列、幂等哈希/外发审计/飞书文本退化及 iOS `ChatStorageController` 本地缓存）。**本轮证据**: `design.md:11-16, 87, 168, 172, 274, 329, 352`、`specs/im/task-graphs.md:23-32`、`specs/im/ios-client.md:14` — **`closed`**。
- **`R1-W4`** — **Author Resolution**: `accepted`（补齐速建归属会话胶囊与完整新建入口、实装 `按负责人 / 团队全部`、补齐多层钻取与 iOS 展开/新增/编辑入口、补齐新芽「关闭」并区分 `批准立项 -> todo` 与 `批准开工 -> doing`、统一双端运行特性保存与同页 `task_graph` 依赖联动）。**本轮证据**: `design.md:257-292`、`prototype.html:967-1573`、`evidence/prototype-walkthrough.md:16-36` 及重绘的 10 张 `evidence/screens/*.png` — **`closed`**。
- **`R1-W5`** — **Author Resolution**: `accepted`（`specs/gateway/personal-agent.md` 修改存量 `PA 复用完整 Global 执行能力` 消除冲突，`specs/im/task-graphs.md` 补回多层子作用域钻取、有界增量加载及确定性 `proposed` 批准契约）。**本轮证据**: `specs/gateway/personal-agent.md:33-39`、`specs/im/task-graphs.md:9-13, 69-76` — **`closed`**。
- **`R1-R1` & `R1-R2`** — **Author Resolution**: `accepted`（写入 `1,500` 字符优先级裁剪规则与 iOS 未知枚举兜底解码单测）。**本轮证据**: `design.md:228, 352` — **`closed`**。

### Issues

无（`0 CRITICAL / 0 WARNING`）。

### Recommendations

- **`R2-R1`**：在实现 `packages/product-contracts/src/capabilities.ts` 的 `definitionsForRole(isPersonal: boolean)` 时，建议让 `effectiveFeatures(features, definitions)` 与 `featureClosure(features, definitions)` 在省略 `definitions` 参数时默认取非个人角色集合 `definitionsForRole(false)`，并让 `validateCapabilities(draft, catalog)` / `changeCapability(draft, action, catalog)` 默认回退到 `catalog.features ?? definitionsForRole(Boolean(draft.personal_agent))`，以防任何未显式传参的旧调用点误把 `proactive_planning` 混入普通 Agent。


### Author Resolutions

- **`R2-R1` — `accepted`**：采纳为 M1 代码实施细节（在 `packages/product-contracts/src/capabilities.ts` 实现 `definitionsForRole` 时，`effectiveFeatures` / `featureClosure` 缺省 `definitions` 取 `definitionsForRole(false)`，`validateCapabilities` / `changeCapability` 缺省取 `catalog.features ?? definitionsForRole(Boolean(draft.personal_agent))`）；与现有受审 `design.md` 及增量契约完全一致，无需修改已通过审查的冻结设计产物。


---

## Round 3

### Metadata

- **reviewer**: `change-design-reviewer` (same independent subagent instance as Rounds 1–2, integrating `codebase-design`, `agent-context-review`, `frontend-experience-review`)
- **target**: `docs/changes/feat-785-pa-proactivity` (`design.md`, `prototype.html`, `evidence/prototype-walkthrough.md`, `evidence/screens/*.png`, `specs/im/{task-graphs,ios-client}.md`)
- **review_mode**: `delta`
- **mode_reason**: Incremental user-feedback UX & contract refinement over the Round 2 `Approved` baseline (`4c7d5fb10`): renames UI-facing `放远期` copy to `先存着` (keeping wire/storage enum `backlog` unchanged) and materializes the interactive bottom `先存着 / 已完结` two-tab drawer (`?state=focus-stashed`) and `提上日程` (`backlog -> todo`) flow across `design.md`, `prototype.html`, `evidence/screens/*.png`, and `specs/im/{task-graphs,ios-client}.md`.
- **retained_from**: `Round 1, Round 2` (all cross-package architecture, `product-contracts` / `im-server` / `personal-assistant` / `dsh-integration` / `node` runtime & security mechanisms, 4 Agent Context consumer chains & `NoSilentPrefixRewrite` prefix-cache guarantees, `specs/im/personal-agent.md`, and all `specs/gateway/*.md` delta-specs remain unchanged from Round 2).
- **started_at**: `2026-11-25T15:38:43+09:00`
- **completed_at**: `2026-11-25T15:41:05+09:00`
- **duration**: `2m 22s`

### Verdict

**Approved** — `0 CRITICAL / 0 WARNING` (plus `1 Recommendation`)

### Coverage 与证据

- **`retained_from: Round 1, Round 2`**：对照 `git diff 4c7d5fb10 -- docs/changes/feat-785-pa-proactivity` 核实，`spec.md`、`specs/im/personal-agent.md`、`specs/gateway/{task-graphs,personal-agent,agent-capabilities}.md` 及 `design.md` 的后端接口、状态枚举（`backlog`）、跨进程 Cron 桥接、发前新鲜度门控、三重安全隔离与 Agent Context 预算规则均零改动，沿用 Round 1–2 已通过的审查证据。
- **本轮增量变更与波及范围（`delta` 展开核查）**：
  1. **术语统一与协议稳定性（`codebase-design` & Delta-specs）**：
     - 全仓检索 `docs/changes/feat-785-pa-proactivity/`（排除历史评审记录）确认：`design.md`、`prototype.html`、`evidence/prototype-walkthrough.md`、`specs/im/task-graphs.md` 与 `specs/im/ios-client.md` 中面向用户的界面操作与状态标签已全部统一为直白口语化的「先存着」，无残留「放远期」分叉文案；底层协议与数据库枚举保持 `backlog` 不变，不引入额外状态或跨包契约变更。
     - 核查「先存着」与 `Dreaming` 分寸学习的一致性：`specs/im/task-graphs.md:11` 明确「先存着」置为 `backlog`（`triage_outcome = "deferred"`，不计为负向拒绝线索），与 `specs/gateway/agent-capabilities.md:27`（仅连续忽略或关闭 `dismissed` 达两次才晋升克制规则）及抽屉副标题说明完全自洽，不会因用户暂存点子而误触发 PA 克制封禁。
  2. **「先存着 / 已完结」展开抽屉与「提上日程」交互走查（`frontend-experience-review`）**：
     - 阅读 `prototype.html:842-1797`（`renderStashedDrawer`、`activateStashed`、滚动位置保持逻辑）及 `evidence/prototype-walkthrough.md`，并逐张目视核查重渲染截图（新增 `focus-stashed.png` 及更新后的 `focus-web.png`、`focus-mobile.png`、`goal-web.png`、`chat-web.png`、`ios-goal.png`、`ios-chat.png`）：
       - **文案与主次层级**：Web/iOS 焦点台、北极星全景新芽与私聊活卡片中的次级按钮均已更新为「先存着」，主操作仍仅保留单颗主色填充按钮（「批准开工」或「批准立项」），窄屏 `390` 无折行挤压或裁切。
       - **展开态完整性与操作闭环（`focus-stashed.png`）**：焦点台上方「待你拍板 / 正在推进与盯梢 / 长线目标」保留完整真实内容，底部展开抽屉将「先存着 (2)」与「已完结 (3)」独立分栏呈现，不把待唤醒点子混入历史完结流水；每张「先存着」卡片清晰展示所属脉络、`先存着 · 免打扰` 标签及「提上日程」（`backlog -> todo` 回到活跃区，若负责人为 PA 且无前置阻塞可进一步点「让小助开工」转 `doing`）、「展开成目标图」与「关闭」入口；切换抽屉子分页保持当前滚动位置不跳回页顶，右下浮层不遮挡操作按钮。
  3. **Milestone `M1` 对齐核查**：
     - `design.md:281-282, 352` 已将「先存着」文案、底部「先存着 / 已完结」分栏抽屉及一键「提上日程」纳入原型 `must-match` 对齐契约与 `M1` `[reviewer]` 第 ②③ 条退出标准，下游实施与验收目标明确。

### 历史问题闭环

- **`R1-C1`–`R1-C4`、`R1-W1`–`R1-W5`、`R1-R1`–`R1-R2`**：已在 Round 2 核实 `closed`，本轮增量 diff 未触碰相关修复机制，维持 `closed`。
- **`R2-R1`**（Recommendation）— **Author Resolution**: `accepted`（作为 M1 实施 `capabilities.ts` `definitionsForRole` 缺省参数防护细节采纳）。**本轮证据**: `design-review.md:241`，与当前冻结契约完全兼容 — **`closed`**。

### Issues

无（`0 CRITICAL / 0 WARNING`）。

### Recommendations

- **`R3-R1`**：`specs/im/task-graphs.md:61` 将 `backlog` 与执行中途暂缓的 `paused` 共同归入底部折叠抽屉的第一分栏（与 `done / closed` 分离）；M1 实施前端抽屉卡片时，建议对 `paused` 节点保留显式「已暂缓」徽标与「恢复推进」（对应 `specs/im/task-graphs.md:156-157` 恢复 `doing`），与 `backlog` 节点的「先存着 · 免打扰」及「提上日程」（进 `todo`）在同栏内清晰区分。（另：`design.md:290` 正文中的“全部 10 个状态”可在归档时顺手同步为含 `focus-stashed` 在内的 11 个状态。）

### Author Resolutions

- **`R3-R1` — `accepted`**：采纳为 M1 前端抽屉实施细节（同栏内 `backlog` 显示「先存着 · 免打扰」与「提上日程 -> todo」，`paused` 保留「已暂缓」徽标与「恢复推进 -> doing」；演示态计数笔误留待归档收尾一并同步），无需改动当前已通过审查的冻结设计产物。

---

## Round 4

### Metadata

- **reviewer**: `change-design-reviewer` (same independent subagent instance as Rounds 1–3, integrating `codebase-design`, `agent-context-review`, `frontend-experience-review`)
- **target**: `docs/changes/feat-785-pa-proactivity` (`spec.md`, `design.md`, `prototype.html`, `evidence/prototype-walkthrough.md`, `evidence/screens/*.png`, `specs/im/{task-graphs,personal-agent,ios-client}.md`, `specs/gateway/{task-graphs,personal-agent,agent-capabilities}.md`)
- **review_mode**: `full`
- **mode_reason**: 自 Round 3 基线（`432a79041`）以来，`spec.md` 新增 `Q8`、`Q9` 对齐决议并重构了核心运行边界、共享契约、前端信息架构与全部 6 份 delta-spec（由独立 `proactive-digest`/`proactive-plan` 子会话改为 PA 主会话 `proactive_review` 静默唤醒 + 零改动复用半夜 `Dreaming`；去除 `doing` 空闲连拍 256 轮续跑与 `waiting` 强制闹钟限制；移除 `prep_draft`、`403` 硬门禁、`pa.proactive.feedback` 与 `<proactive-focus-snapshot>`；保留 PA 私聊任务系统提示气泡；引入顶栏「当前行动 / 长线目标」双视角、顶部「待你拍板 ⇄ 先存着」切换、9 状态徽章 + `? 状态说明` 与按阶段自适应详情抽屉）。按 `change-design-reviewer` 模式选择规则，需求、核心边界与跨包契约重构须执行 `full` 全量审查。
- **retained_from**: `none (full re-review)`；Round 1–3 历史问题在新架构下的存续或替代状态见「历史问题闭环」。
- **started_at**: `2026-11-25T21:06:37+09:00`
- **completed_at**: `2026-11-25T21:17:15+09:00`
- **duration**: `10m 38s`

### Verdict

**Issues Found** — `1 CRITICAL / 4 WARNING` (plus `1 Recommendation`)

### Coverage 与证据

- **跨包边界与模块收敛评估（`codebase-design`）**：
  - 全量对照 `AGENTS.md`、`SPEC.md` 及真实装配点（`packages/product-contracts/src/{capabilities,chat,configuration,runtime-rpc,task-execution}.ts`、`apps/im-server/src/{db,schema.sql,task-graphs,task-notifications,personal-agent,messaging,message-records}.ts`、`packages/personal-assistant/src/{heartbeat,task-execution,personal-assistant,global-agent,inbox}.ts`、`packages/dsh-integration/src/{index,task-execution,task-context,cron-owners,context-order,knowledge/dreaming,knowledge/dreaming-prompts}.ts`）：本轮按第一性原理砍掉了独立后台子会话、自定义 `.nanoassistant/memory` 旁路写通道、`pa.proactive.feedback` 回传管道、`prep_draft` 大文本列及 `403` 越权门禁，直接复用 PA 主会话与既有 `Dreaming` 夜间归并（已核实 `packages/dsh-integration/src/knowledge/dreaming-prompts.ts:80-83` 原生覆盖 PA 主动分寸沉淀），包依赖红线清晰，架构复杂度较 Round 2 显著下降。
  - 同时在与真实代码装配点逐行核对中，定位出 1 项 `CRITICAL`（单次事件唤醒与现有电平触发 `TaskExecution` / 私聊任务系统通知 `Inbox` 唤醒链冲突 + `task-notifications.ts` 状态文案缺失）和 3 项后端运行时 `WARNING`（`R4-W1`–`R4-W3`）。
- **Agent Context 与缓存前缀核查（`agent-context-review`）**：
  - 核查 `packages/dsh-integration/src/context-order.ts`、`cron-owners.ts` 与 `design.md`「Agent Context 消费链」：`proactive_review` 通过主会话 `session.submit({ onlyIfIdle: true })` 在消息流尾部追加单条 `<proactive-review-wake>` 提示，不改写 system prompt、tools 或历史消息前缀，100% 复用主会话活跃 KV Cache（符合 `NoSilentPrefixRewrite`）；`definitionsForRole` 保持普通 Global Agent 工具面零漂移；`task-context` 同步完整保留。
  - 但移除 `<proactive-focus-snapshot>` 与跨群 `held_for_revalidation` 后，原生 `ScheduleService` 定时唤醒在「观察流异步拉取竞态」与「`attention=0` 观察消息对当轮模型不可见」两处存在断链（见 `R4-W1`）。
- **前端体验与 13 张真实截图目视核查（`frontend-experience-review`）**：
  - 通读 `prototype.html`（1–2766 行完整核查）与 `evidence/prototype-walkthrough.md`，并逐张目视检查全部 13 张重渲染 PNG（`focus-web.png`、`focus-detail.png`、`goals-web.png`、`focus-help.png`、`focus-triaged.png`、`focus-stashed.png`、`goal-web.png`、`chat-web.png`、`focus-mobile.png`、`ios-goal.png`、`ios-chat.png`、`settings-online.png`、`settings-offline.png`）：
    - 顶栏 `当前行动 (4) / 长线目标 (2)` 双视角切分、顶部平级的 `待你拍板 (2) ⇄ 先存着 (2)` 分栏切换、严格统一的 9 状态双字/三字徽章、`? 状态说明` 单行流转浮层（`focus-help.png`）、右侧按阶段自适应详情抽屉（`focus-detail.png`）、去 `prep_draft` 后的私聊正文直出 + 内联活卡片（`chat-web.png`、`ios-chat.png`）以及 Crewden 风格低噪留白与 `390` 窄屏排版均忠实兑现 `spec.md` `Q8`/`Q9` 决议，无文字截断、主色泛滥或遮挡问题。
    - 局部交互一致性改进项归入 `R4-R1`（次级范围 `按负责人 / 团队全部` 与顶栏双视角联动、窄屏 `390` 搜索与建目标入口可达性）。
- **Delta-Specs 与 Milestone `M1` 对齐核查**：
  - 对照 `docs/specs/CONTRIBUTING.md` 与 `docs/specs/{im,gateway}/` 全部对应基线规范，发现 `specs/gateway/task-graphs.md` 与 `specs/im/task-graphs.md` 遗漏清理多处仍强制旧版「连续自动续跑 / `waiting` 必绑 `Schedule` / 旧状态通知集合」的 Canonical Requirement（见 `R4-W4`）。`M1` 两轨退出标准本身可证伪，待修齐上述设计契约后即可支撑实施。

### 历史问题闭环

- **在新架构下继续保留并核实有效的历史修复（维持 `closed`）**：
  - **`R1-C1`（主会话与晨间去重部分）**：`schedule.command(jobs)` 晨间早报静默吸纳与条目级 `briefed_at` 幂等提交仍完整保留（`design.md:106-112`）；跨进程观察流同步部分因改为单向通知出现新竞态，转入 `R4-W1` 跟踪。
  - **`R1-C3`（三重安全隔离核心）**：`publicationEvidence`、`attention IN (0, 1)` `pendingReadCalls`、`TaskNode.source_conversation_ids` 溯源撤销及活跃轮根节点 `source_message_id` 门禁完整保留（`design.md:114-135`）。原 `403` `proposed` 服务端硬门禁与 `.nanoassistant/memory` 路径守卫已随 `Q9`（改为同主会话直接复盘 + 取消 `403` 硬门禁 + 零改动复用 `Dreaming`）合理退役。
  - **`R1-C4`（`decision` 免排程与群聊 `asked_user_id`）**：结构化 `asked_user_id` 与群聊定向回复恢复仍保留（`design.md:145, 200`）；无闹钟静默 `waiting` 扩展后的 `waitHealth` / `prepareWaits` 兼容缺口转入 `R4-W2` 跟踪。
  - **`R1-W1`（普通 Global Agent 零工具指纹漂移）** & **`R2-R1`**：`definitionsForRole` 角色过滤完整保留（`design.md:148-153`）。
  - **`R1-W3`（顶层 `ChatMessage.task_cards` + `messages.task_cards_json`）**：完整保留（`design.md:155-157`）。
  - **`R1-W5` & `R3-R1`（前端与 iOS 能力对齐、「先存着」直白术语与 `backlog/paused` 区分）**：在新双视角与顶部 `待你拍板 ⇄ 先存着` 布局中继续保持（`design.md:258-262`、`prototype.html:889-930, 1690-1755`）。
- **随 `Q8`/`Q9` 架构简化已整体退役的历史条目（标记 `superseded by Q8/Q9`）**：
  - **`R1-W2`（`pa.proactive.feedback` 与独立夜间调度器）**、**`R1-W4`（`<proactive-focus-snapshot>` 1500 字符截断预算）**、**`R1-R1`（`prep_draft` 字节上限）**、**`R1-R2`（独立子会话 `usage()` 聚合）**：对应机制已在 `spec.md` `Q8`/`Q9` 中明确移除，不再适用（其中 `proactive_review` 在主会话内的 `usage()` / 停用门禁已转入 `R4-W3` 核查）。

### Issues

#### `R4-C1` [CRITICAL] 单次事件唤醒（去 `doing` 空转轮询）与现有电平触发 `TaskExecution`、私聊系统通知 `Inbox` 唤醒链及通知状态映射存在三处直接冲突

- **位置**：
  - `docs/changes/feat-785-pa-proactivity/design.md:12-14, 19-30, 42, 44, 76, 104, 164, 209`
  - `apps/im-server/src/task-graphs.ts:965-995`、`apps/im-server/src/task-notifications.ts:23-38, 65`、`apps/im-server/src/messaging.ts:653-658, 688-712`
  - `packages/personal-assistant/src/global-agent.ts:323-336`、`packages/dsh-integration/src/task-execution.ts:164, 275-283`、`packages/dsh-integration/src/index.ts:1241`
- **证据**：
  1. **电平触发 `snapshot.tasks.some(doing)` 导致无关图编辑与自改状态重复唤醒**：`design.md:14, 44, 76, 164` 将“去除 256 轮死循环”收敛为删除 `dsh-integration/src/task-execution.ts` 对 `agent/status === 'idle'` 的连续重入。但在现有实现中，`apps/im-server/src/task-graphs.ts:985-995`（`notifyChange`）在同图**任意节点**保存时都会向图上所有受派 Agent 广播 `task.execution.changed`，而 `packages/dsh-integration/src/task-execution.ts:164, 275-283` 与 `index.ts:1241`（`ensure`）按**电平**判断 `snapshot.tasks.some(task => task.status === 'doing')`。只要某 Agent 名下已有一张首轮执行完进入 `idle` 等待外部条件的 `doing` 任务，后续主人点另一张 `proposed` 卡的「先存着 / 关闭」、PA 在 `proactive_review` 更新其他节点、或节点断线重连 `ensure`，都会再次把 `idle` Agent 唤醒重跑该 `doing` 任务；甚至 Agent 自己在活跃轮把任务改为 `doing` 后，异步到达的 `task.execution.changed` 若落在刚进 `idle` 之后，也会立即触发多余的第二轮。
  2. **PA 私聊保留 `persistTaskNotice` 后，主人操作非 PA 负责卡片会走 `Inbox` 直接高优唤醒 PA**：`design.md:12, 42, 104` 决定保留 PA 私聊中的 `task_graph` 系统提示消息。核查 `packages/personal-assistant/src/global-agent.ts:323-336`：`taskContext` 仅在 `notice?.kind === 'task_graph' && notice.attention_actor_ids?.includes(config.agentId) === true` 时为 `true`。当卡片负责人是人类主人 `J` 或未指派（如 `prototype.html` 中「录制 3 分钟真实场景 Demo」「发邀请码给首批 10 位同路人」），`task-notifications.ts:23` 生成的 `attention_actor_ids` **不包含 PA 的 `agentId`**；一旦主人在私聊卡片上点「先存着」「关闭」或「批准立项」，`persistTaskNotice`（`messaging.ts:654-655`）以主人为 `sender` 入队 `relay_task`，`global-agent.ts:325-336` 因 `taskContext === false` 且私聊 `chatDelivery === 'high'`，会将其当作普通私聊新消息立即调用 `this.wake()` 唤醒 PA，直接违背 `spec.md:12, 263` 与 `specs/im/task-graphs.md:12, 20, 56`（点「先存着 / 关闭 / 待办」绝不触发 Agent 执行）。
  3. **`apps/im-server/src/task-notifications.ts:34` 漏入涉及范围，新状态系统消息会拼出 `undefined`**：`task-notifications.ts:34` 当前硬编码 `{todo, doing, waiting, in_review, done, paused, closed}` 七态映射并执行 `note('status', status[n.status])`；保留私聊系统通知后，创建或流转 `proposed` / `backlog` 会生成状态名为 `undefined` 的系统消息，且该文件未列入 `design.md:19-30` 涉及范围。
- **影响**：实施后会出现「点『先存着 / 关闭』立刻吵醒 PA」「图上有一张挂起 `doing` 卡时任何改图动作都反复重跑」「私聊任务提示出现 `undefined`」三类核心行为破损。
- **建议方向**：
  1. 在 `TaskExecution` / `TaskExecutionDriver` 将 `doing` 唤醒从电平触发改为**边沿触发水位**（例如按 `(graph_id, node_id, assignee_id, doing_entered_revision)` 持久化已唤醒标记；同会话在活跃轮内自行写入的 `-> doing` 直接记为当轮已消费，仅对未唤醒的新增 `-> doing` 跃迁或首轮 `interrupted` 恢复触发一次 `poke`）。
  2. 在 `packages/personal-assistant/src/global-agent.ts:324-336` 对所有 `input.message.system_notice?.kind === 'task_graph'` 系统消息统一禁止触发 `Inbox` 主动唤醒（无论 `attention_actor_ids` 是否含 `config.agentId`，均置 `attention = false, high = false`，仅走被动上下文索引；真正的开工唤醒唯一由 `TaskExecution` 边沿驱动）。
  3. 将 `apps/im-server/src/task-notifications.ts` 纳入涉及范围，补齐 `{ proposed: '待拍板', backlog: '先存着' }` 文案映射。

#### `R4-W1` [WARNING] 原生 `ScheduleService` 定时唤醒的观察流同步在单向通知竞态与 `attention=0` 可见性上未闭环

- **位置**：
  - `docs/changes/feat-785-pa-proactivity/design.md:11, 14, 108, 159-163, 192-194`
  - `docs/changes/feat-785-pa-proactivity/specs/gateway/personal-agent.md:21-24`
  - `packages/personal-assistant/src/global-agent.ts:610-632`、`packages/personal-assistant/src/personal-assistant.ts:28-35`、`packages/dsh-integration/src/index.ts:382-415`
- **证据**：
  1. **单向通知导致先开跑后入库竞态**：`design.md:11, 14, 192` 规定 `dsh-integration` 在 `source.kind === 'schedule'` 进入 `agent/pre-step` 时发出「定时唤醒观察流同步**通知**」（notify）。但 `recoverPersonalObservations()`（`global-agent.ts:610-632`）需要跨 Relay 请求 `pa.observations.read` 并执行入库审查；若 `dsh-integration` 仅发单向通知而不 `await` 请求完成，模型首步推理与工具调用会在群观察消息写入 `InboxStore` 之前抢跑。
  2. **移除 `<proactive-focus-snapshot>` 后，当轮定时唤醒看不到 `attention=0` 未读观察消息**：本轮移除了 `<proactive-focus-snapshot>` 与跨群 `held_for_revalidation`（`design.md:45, 76, 159-163`），而 `PersonalAssistant.send()`（`personal-assistant.ts:28-35`）仅拦截主人私聊（`attention=1`）未读消息，群观察流以 `attention=0` 存入 `InboxStore`（`global-agent.ts:625`）。当 `14:10` 原生 Cron 仅带着定时任务文本唤醒 PA 时，上下文里没有任何信号提示 `InboxStore` 中刚同步进了 `研发日常群` 的未读观察消息，模型可直接调用 `send_message` 发出过时催促。
- **影响**：`spec.md:189, 280-282` 核心验收项（用户已在可读群聊处理完事项后，PA 后续定时提醒不再拿旧状态重复催促）在真实定时唤醒下仍可能失效。
- **建议方向**：将 `runtime-rpc.ts` 中的定时观察流桥接定义为 `dsh-integration` 在 `agent/pre-step` 内 **`await` 的请求—响应 RPC**（带离线/超时降级），并在响应中返回当前 `InboxStore` 未读来源摘要（或在存在未读观察/私聊来源时向该轮 `schedule` 输入尾部附带一行轻量未读提示，配合 `nano-personal-agent` 提醒前先 `inbox` 核实的指引），确保先同步完成且模型当轮可见。

#### `R4-W2` [WARNING] 无闹钟静默 `waiting`（省略 `schedule_id`）与 `im-server` `waitHealth`、`prepareWaits` 负责人约束及 `task.wait.repair` 退役链路不一致

- **位置**：
  - `docs/changes/feat-785-pa-proactivity/design.md:12-14, 26, 77, 139-147, 165, 200`
  - `docs/changes/feat-785-pa-proactivity/specs/im/task-graphs.md:103-115`、`specs/gateway/task-graphs.md:30-55`
  - `apps/im-server/src/task-graphs.ts:516-531, 996-1012`、`packages/personal-assistant/src/task-execution.ts:68-76`、`packages/product-contracts/src/runtime-rpc.ts:85`
- **证据**：
  1. **`waitHealth` 对无 `schedule_id` 的 `waiting` 节点会报错或误标失效**：`apps/im-server/src/task-graphs.ts:996-1012` 在每次读取任务图时对所有 `node.status === 'waiting'` 无条件调用 `this.execution.inspect({ agent_id: node.assignee.id, ..., schedule_id: node.wait.schedule_id })`。当省略 `schedule_id` 或负责人为人类/未指派时，该调用会因缺少 `schedule_id`/`agent_id` 失败或标为 `invalid`/`unknown`，直接违背 `specs/im/task-graphs.md:114`（未关联定时器的静默等待任务不因无定时器被标为安排失效）。
  2. **`prepareWaits` 负责人限制与原型/契约不一致，且缺 `asked_user_id` 成员校验**：`apps/im-server/src/task-graphs.ts:519` 目前硬性拒绝非 Agent 负责人的 `waiting`（`'Waiting tasks must stay assigned to an agent'`），而 `prototype.html:277-285`（`f_wait`：「等法务确认新域名备案材料」，负责人 `J`）及 `specs/im/task-graphs.md:107-115` 均允许人类或 PA 的任务处于无定时器 `waiting`；同时新增 `wait.asked_user_id`（`design.md:145, 200`）尚未写明在 `im-server` 侧校验其属于当前会话有效成员。
  3. **`task.wait.repair` 跨包删除不完整**：`design.md:14, 26, 77` 移除了 `dsh-integration/src/task-execution.ts` 的 `task-wait-repair` 与 `product-contracts/src/task-execution.ts` 的 `repair_task_ids`，但未同步说明 `packages/product-contracts/src/runtime-rpc.ts:85`（`task.wait.repair`）、`packages/personal-assistant/src/task-execution.ts:68-76`（`scheduleDeleted`）及 `schedule-deletions.ts` 的去留，以及当用户/Agent 显式删除已绑定的可选 `waiting.schedule_id` 时如何收敛（例如仅由 `waitHealth` 如实标为 `invalid` 而不自动唤醒重绑）。
- **影响**：保存无 `schedule_id` 或人类负责的 `waiting` 节点会在 `im-server` 校验/读取阶段直接报错或误亮异常徽标，删除原生 `Schedule` 时也会触发悬空 RPC 调用。
- **建议方向**：在 `design.md` 明确：① `waitHealth` 仅对同时存在 `assignee.type === 'agent'` 且 `wait.schedule_id != null` 的节点巡检原生定时器，无 `schedule_id` 的静默等待不产出 `wait_health: invalid`；② 明确 `prepareWaits` 对无 `schedule_id` 人类/Agent 等待节点的准入规则及 `asked_user_id` 会话成员校验；③ 同步交代 `runtime-rpc.ts` 与 `personal-assistant` 中 `task.wait.repair` / `scheduleDeleted` 的清理或降级行为。

#### `R4-W3` [WARNING] `proactive_review` 静默唤醒在忙时游标推进、防自激重入、观察流触发面与特性停用门禁上缺少明确状态机

- **位置**：
  - `docs/changes/feat-785-pa-proactivity/design.md:13-14, 45, 103-104`
  - `docs/changes/feat-785-pa-proactivity/specs/gateway/personal-agent.md:14, 52-55`、`specs/gateway/agent-capabilities.md:12`
  - `packages/personal-assistant/src/heartbeat.ts:95-118`、`packages/dsh-integration/src/index.ts:640-648, 1270-1271`
- **证据**：
  1. **直接照搬 `Heartbeat` 的 `busy` 跳过语义会丢弃未复盘对话，反之不区分来源又会自激死循环**：`design.md:45, 103` 写明直接效仿 `Heartbeat` 的 `session.submit({ onlyIfIdle: true })`。但在 `heartbeat.ts:110-116` 中，`{ accepted: false, busy: true }` 会将当次视作已跳过边界并推进 `due`、清除 `pending`。若 `proactive-coordinator` 在 `busy: true`（例如 12 分钟到点时 PA 正在跑定时任务或子 Agent）时推进已复盘水位，整段用户对话将永久漏检；反之若不严格限定何种事件推进 `last_eligible_activity_seq`，`proactive_review` 自身写任务图产生的系统消息或自身回合完成事件又会在 12 分钟后再次触发 `proactive_review` 形成自激循环。
  2. **观察流重要承诺触发面缺失**：`spec.md:52, 185` 与 `specs/gateway/personal-agent.md:52-55`（`Scenario: 重要观察后的私人准备与提议立卡`）要求 PA 在观察到主人重要群聊承诺或变化后静默沉淀准备与 `proposed` 卡，但 `design.md:13, 103` 仅写「监听 PA 私聊对话推进」，若主人下午只在可读群聊拍板而未回私聊发言，将永远不触发 `proactive_review`。
  3. **缺少 `proactive_planning` 运行时门禁与忙态上报**：对照 `packages/dsh-integration/src/index.ts:646, 1270` 对 `heartbeat` 的处理，`channel === 'proactive_review'` 需在 `submit()` 检查 `capabilities.held(agentId, { kind: 'feature', name: 'proactive_planning' })`、在 `usage()` 上报在途 `proactive_review` 回合，并在关闭开关时取消/拦截在途静默复盘（兑现 `specs/gateway/personal-agent.md:14` 与 `specs/gateway/agent-capabilities.md:12`）。
- **影响**：可能出现忙时漏掉整段对话复盘、每 12 分钟自我唤醒空转、群聊承诺无法沉淀提案卡、或关闭「主动筹划」开关后仍在后台跑完静默复盘。
- **建议方向**：在 `design.md` 明确 `proactive-coordinator` 的双水位状态机（仅主人私聊消息与已准入的主人相关观察事件推进 `last_activity_seq`；`proactive_review` 自身回合与被动 `task_graph` 系统通知不推进 `last_activity_seq`；仅 `session.submit` 返回 `accepted: true` 时推进 `last_reviewed_seq`，`busy: true` 时保留未复盘水位待空闲重试），并在 `dsh-integration` 补齐 `proactive_planning` 的 `held` 校验与在途取消/上报。

#### `R4-W4` [WARNING] `specs/gateway/task-graphs.md` 与 `specs/im/task-graphs.md` 遗漏同步多处与 Q8/Q9 冲突的既有 Canonical Requirement

- **位置**：
  - `docs/changes/feat-785-pa-proactivity/specs/gateway/task-graphs.md:14, 30, 57` 对照 `docs/specs/gateway/task-graphs.md:22-25, 134, 185-190, 208-212, 306-312`
  - `docs/changes/feat-785-pa-proactivity/specs/im/task-graphs.md` 对照 `docs/specs/im/task-graphs.md:195-237`
- **证据**：
  1. **修改后标题与正文自相矛盾**：`specs/gateway/task-graphs.md:30` 保留了旧标题 `### Requirement: waiting SHALL 关联有效原生安排并允许主动恢复`，但其正文 `:34` 改为「未提供 `schedule_id`，系统直接保存等待说明而不强制要求绑定轮询定时器」，标题与正文直接冲突；`:14`（`持续推进全部本人 doing 任务`）与 `:57`（`自动续跑 SHALL...`）亦沿用了旧版连续续跑命名。
  2. **`docs/specs/gateway/task-graphs.md` 中三处未触碰的既有 Requirement 与单次唤醒/无闹钟等待正面冲突**：
     - `Requirement: 自动续跑 SHALL 保留原有产品交付与审批链`（`docs/specs/gateway/task-graphs.md:185-190`）：仍规定空闲后自动发起「SingleThread 自动第二轮」，与本轮废除空闲连拍直接矛盾，需在 delta-spec 中 `MODIFIED`（改为事件单次唤醒保留原有交付与审批链）或 `REMOVED`。
     - `Requirement: Task 等待与结果反馈 SHALL 交付到固定所属聊天`（`:208-212, 306-312`）：仍要求每次 `waiting` 说明必含「下次检查」且「不删除有效 Schedule」，未兼容无定时器静默等待。
     - `Requirement: Agent 可按讨论结果维护持久任务图` -> `Scenario: 配置任务图特性`（`:22-25`）：仍写“用于等待复查和自动续跑”（另请同步确认 `packages/product-contracts/src/capabilities.ts:30` 中 `task_graph` 依赖 `cron_scheduling` 是否因保留可选跨天 `waiting` 闹钟而有意维持，与 `prototype.html` 设置页文案保持一致）。
  3. **`specs/im/task-graphs.md` 漏改 `Requirement: 任务协作通知使用所属会话的一条系统消息`**：本轮恢复保留 PA 私聊任务系统消息（`design.md:12, 42`），但 `docs/specs/im/task-graphs.md:236` 仍仅列举 `通知 todo／paused 等状态变化不等于开工命令`，未纳入新增的 `proposed` 与 `backlog`。
- **影响**：归档合并至 `docs/specs/` 后，同一份 canonical spec 内会并存「必须自动第二轮续跑 vs 只在状态跃迁单次唤醒」「`waiting` 必绑 `Schedule` vs 允许无 `schedule_id`」两套冲突契约。
- **建议方向**：同步修订 `specs/gateway/task-graphs.md` 与 `specs/im/task-graphs.md`，统一标题与受影响兄弟 Requirement，使合并后的整篇 canonical spec 前后完全自洽。

### Recommendations

- **`R4-R1`**：补充两处前端/原型交互一致性细节：① `prototype.html:1774-1824`（`renderAssigneeOrTeamScope`）在切换左侧范围为「按负责人 / 团队全部」时，顶栏仍高亮显示「当前行动 (4) / 长线目标 (2)」双视角开关但点击未联动过滤，建议明确双视角在全部三个范围下一致生效（按单卡行动 vs 多步目标树过滤或分组）；② `prototype.html:2138, 2155`（`focus-mobile.png`）在 `390` 窄屏下隐藏了搜索框与「拆多步目标」入口，实施 Web 窄屏与 iPhone 原生工作区时建议保留折叠搜索图标与 `+` 菜单中的新建多步目标入口，保持与 `docs/specs/im/ios-client.md:96`（支持关键字搜索与快速创建）一致。

### Author Resolutions

- **`R4-C1` — `accepted`**：核实三处代码接线冲突均完全属实（`apps/im-server/src/task-graphs.ts:985-995`、`packages/dsh-integration/src/task-execution.ts:164, 275-283`、`packages/personal-assistant/src/global-agent.ts:323-336`、`apps/im-server/src/task-notifications.ts:34`）。已在 `design.md`（§涉及范围、§关键决策 D2/D4、§接口与数据流 1/2/3、§Milestones）及 `specs/gateway/task-graphs.md`、`specs/im/task-graphs.md` 完整修正：①在服务端引入 `doing_wake: { revision, assignee_id, actor, at }` 边沿戳，宿主按 `(agent_id, graph_id, node_id) -> last_woken_doing_revision` 持久水位边沿唤醒（同轮自写 `-> doing` 当即记为已消费，同图无关节点修改与重连 `ensure` 不重跑）；②在 `global-agent.ts` 将所有 `system_notice?.kind === "task_graph"` 统一置 `attention = false, high = false`（仅入被动 `task_context_index`，私聊点「先存着/关闭/待办」绝不经 `Inbox` 唤醒 PA）；③补齐 `task-notifications.ts` 九态中文文案映射。
- **`R4-W1` — `accepted`**：核实属实（单向通知存在先开跑后入库竞态，且 `attention=0` 群观察对当轮 `schedule` 不可见）。已在 `design.md`（§涉及范围、§关键决策 D5、§接口与数据流 1/3、§Milestones）与 `specs/gateway/personal-agent.md` 修正：改为 `dsh-integration` 在 `source.kind === "schedule"` 的 `agent/pre-step` 内 **`await` 请求—响应 RPC `product.proactive.sync_observations`**（带 5s 超时与离线降级），完成 `recoverPersonalObservations()` 入库后返回未消费会话摘要，对存在未读观察来源的轮次追加一行收件箱核实提示，并让 `InboxStore.pendingReadCalls` 覆盖 `attention IN (0, 1)`。
- **`R4-W2` — `accepted`**：核实属实（`apps/im-server/src/task-graphs.ts:519, 996-1012` 与 `runtime-rpc.ts:85`）。已在 `design.md`（§涉及范围、§关键决策 D2、§接口与数据流 1/2、§Milestones）与 `specs/gateway/task-graphs.md` 明确：①`prepareWaits` 对带 `schedule_id` 的 `waiting` 校验 Agent 负责人与 `<= 180d` 定时器，对无 `schedule_id` 的静默等待放行任意负责人并校验 `asked_user_id` 属于会话有效真人成员；②`waitHealth` 仅对 `assignee.type === "agent" && Boolean(wait.schedule_id)` 巡检定时器，无 `schedule_id` 不标 `invalid`/`unknown`；③统一退役 `runtime-rpc.ts` 的 `'task.wait.repair'`、`dsh-integration` 的 `repair()` 与 `personal-assistant` 的 `scheduleDeleted` 修复唤醒链路（删除可选 `Schedule` 仅在 `wait_health` 如实显示失效）。
- **`R4-W3` — `accepted`**：核实属实（`heartbeat.ts:110-116` 与 `dsh-integration/src/index.ts:646, 1270`）。已在 `design.md`（§涉及范围、§关键决策 D4、§Milestones）与 `specs/gateway/personal-agent.md` 明确双水位状态机：仅主人私聊真人消息与已准入主人相关群观察事件推进 `last_activity_seq`（`proactive_review` 自身回合与被动 `task_graph` 系统消息不推进，零自激循环）；仅 `session.submit({ onlyIfIdle: true })` 返回 `{ accepted: true }` 时推进 `last_reviewed_seq`，`busy: true` 时保留未复盘水位待空闲重试；并在 `dsh-integration` 对 `proactive_review` 补齐 `proactive_planning` 的 `capabilities.held`、`usage()` 忙态上报与停用/关闭取消门禁。
- **`R4-W4` — `accepted`**：已在 `specs/gateway/task-graphs.md`（更新为 `ADDED 4 · MODIFIED 6 · REMOVED 5`，净计数仍为 `24 -> 23`，彻底统一标题并同步修订 `Agent 可按讨论结果维护持久任务图`、`自动续跑 SHALL 保留原有产品交付与审批链`、`Task 等待与结果反馈 SHALL 交付到固定所属聊天`、`停止后的上下文同步 SHALL 不自行启动执行`、`Task 操作成功后 SHALL 提醒具体任务的实际交付`）与 `specs/im/task-graphs.md`（新增 `MODIFIED Requirement: 任务协作通知使用所属会话的一条系统消息` 覆盖九态文案及系统消息不主动唤醒 `Inbox`）全部补齐，并在 `design.md` 同步增量汇总表。
- **`R4-R1` — `accepted`**：已在 `prototype.html`、`specs/im/task-graphs.md` 与 `specs/im/ios-client.md` 补齐「按负责人 / 团队全部」与顶栏「当前行动 / 长线目标」双视角的一致联动及动态计数，并在 `390` 窄屏保留紧凑搜索按钮与「拆目标」入口，重新渲染截图核验通过。

---

## Round 5

### Metadata

- **reviewer**: `change-design-reviewer` (same independent subagent instance as Rounds 1–4, integrating `codebase-design`, `agent-context-review`, `frontend-experience-review`)
- **target**: `docs/changes/feat-785-pa-proactivity` (`design.md`, `prototype.html`, `evidence/prototype-walkthrough.md`, `evidence/screens/*.png`, `specs/gateway/{task-graphs,personal-agent}.md`, `specs/im/{task-graphs,ios-client}.md`)
- **review_mode**: `delta`
- **mode_reason**: 本轮围绕 Round 4 提出的 `R4-C1`、`R4-W1`–`R4-W4` 与 `R4-R1` 完成定向契约闭环，涉及共享契约结构增量（`TaskDoingWake`、`product.proactive.sync_observations`、`task.wait.repair` 退役）、宿主双水位与边沿唤醒规则、4 份 delta-spec 同步与局部窄屏/范围交互补齐，未再改变整体架构边界或产品方向，按规则采用 `delta` 增量复审。
- **retained_from**: `Round 4`（沿用 Round 4 全量审查已核实的跨包单向依赖架构、零改动 `Dreaming` 复用、顶层 `ChatMessage.task_cards` 活卡片方案、`proactive_planning` 零配置指纹漂移、`NoSilentPrefixRewrite` 缓存前缀保护、`spec.md`、`specs/im/personal-agent.md` 与 `specs/gateway/agent-capabilities.md`）。
- **started_at**: `2026-11-25T21:28:23+09:00`
- **completed_at**: `2026-11-25T21:31:30+09:00`
- **duration**: `3m 07s`

### Verdict

**Approved** — `0 CRITICAL / 0 WARNING`

### Coverage 与证据

- **`retained_from: Round 4`**：`spec.md`、`specs/im/personal-agent.md`、`specs/gateway/agent-capabilities.md` 及未改动的主干架构设计维持 Round 4 `full` 审查证据。
- **本轮增量修订与波及范围逐项核查（`delta`）**：
  1. **边沿触发单次唤醒、任务通知与 `Inbox` 解耦、九态通知文案（`codebase-design`）**：
     - 核查 `design.md:11-14, 76, 149-154, 168, 171, 331`：服务端在新进 `"doing"`、`"doing"` 下改派或由真人恢复时写入 `doing_wake: { revision, assignee_id, actor, at }`（离开 `"doing"` 清除），宿主按 `(agent_id, graph_id, node_id) -> last_woken_doing_revision` 持久水位边沿唤醒，且同轮自写 `-> doing` 即刻记为已消费，彻底消除了同图其他卡片编辑、断线重连 `ensure`、存量历史 `doing` 升级以及轮次刚入 `idle` 后的异步通知重跑；`global-agent.ts` 将全部 `system_notice?.kind === "task_graph"` 统一置 `attention = false, high = false`（仅入被动 `task_context_index`），杜绝私聊点「先存着 / 关闭 / 批准立项」经 `Inbox` 误唤醒 PA；`apps/im-server/src/task-notifications.ts` 已纳入涉及范围并补齐九态中文映射。
  2. **定时首步前请求—响应观察流同步与未读可见性（`agent-context-review` & `codebase-design`）**：
     - 核查 `design.md:11, 13-14, 108, 162, 199-202` 与 `specs/gateway/personal-agent.md:21-24`：`dsh-integration` 在 PA 主会话 `source.kind === "schedule"` 的 `agent/pre-step` 内改为 **`await` 请求—响应 RPC `product.proactive.sync_observations`**（带 5s 超时与离线降级），入库后再返回未消费会话摘要，并在存在未读观察来源（含 `attention=0` 群观察）时仅向当轮 `schedule` 输入尾部追加一行轻量核实提示，配合覆盖 `attention IN (0, 1)` 的 `pendingReadCalls` 与私聊 `held_for_revalidation`，既消除了异步抢跑与可见性盲区，又不改写既有历史前缀（满足 `NoSilentPrefixRewrite`）。
  3. **无闹钟静默 `waiting` 兼容与 `task.wait.repair` 全链路退役（`codebase-design`）**：
     - 核查 `design.md:11-14, 77, 162, 172` 与 `specs/gateway/task-graphs.md:21-31`：`prepareWaits` 对带 `schedule_id` 要求 Agent 负责人与 `<= 180d` 有效原生 Schedule，对无 `schedule_id` 放行人/Agent/未指派并校验 `asked_user_id` 属于会话有效真人成员；`waitHealth` 仅在 `assignee?.type === "agent" && Boolean(wait?.schedule_id)` 时巡检定时器；`product-contracts/src/{task-execution,runtime-rpc}.ts`、`personal-assistant/src/{task-execution,schedule-deletions}.ts` 与 `dsh-integration/src/task-execution.ts` 同步退役 `task.wait.repair` / `scheduleDeleted` 修复唤醒链。
  4. **`proactive-coordinator` 双水位状态机与 `proactive_planning` 门禁（`codebase-design`）**：
     - 核查 `design.md:13-14, 103, 331` 与 `specs/gateway/personal-agent.md:10-14`：仅主人私聊真人消息与已准入主人相关群观察推进 `last_activity_seq`（`proactive_review` 自身回合与被动 `task_graph` 系统通知不推进，零自激循环）；仅 `session.submit({ onlyIfIdle: true })` 返回 `{ accepted: true }` 时推进 `last_reviewed_seq`，`busy: true` 保留未复盘水位待空闲重试；`dsh-integration` 对 `proactive_review` 接入 `proactive_planning` 的 `capabilities.held`、`usage()` 忙态上报与关闭即时取消。
  5. **全部 6 份 Delta-Specs 标题与条文精确比对**：
     - 脚本逐字核对 `docs/specs/{gateway,im}/*` 与 `docs/changes/feat-785-pa-proactivity/specs/{gateway,im}/*` 全部 Requirement 标题与增删计数：`gateway/task-graphs.md`（`24 -> 23`，`ADD=4, MOD=6, REM=5`）、`im/task-graphs.md`（`19 -> 20`，`ADD=2, MOD=6, REM=1`）、`gateway/personal-agent.md`（`18 -> 19`，`ADD=1, MOD=2`）、`im/personal-agent.md`（`8 -> 8`，`MOD=1`）、`im/ios-client.md`（`19 -> 19`，`MOD=2`）、`gateway/agent-capabilities.md`（`64 -> 65`，`ADD=1`）全部 `missing_mod=[]`、`missing_rem=[]`、`dup_add=[]`，与 `design.md:284-293` 100% 一致，已消除全部新旧条文冲突。
  6. **前端范围联动与窄屏截图复核（`frontend-experience-review`）**：
     - 核查 `prototype.html:1774-1877, 2170-2207` 并目视检查重渲染的 `focus-mobile.png` 与 `focus-web.png`：`按负责人` 与 `团队全部` 范围下顶栏「当前行动 / 长线目标」双视角及动态计数已一致联动；`390` 窄屏顶栏在保持清爽留白的前提下补齐了紧凑「搜索」与「拆目标」入口，无折行挤压或裁切；`M1` `[worker]` 退出标准已同步覆盖全部新增契约测试点。

### 历史问题闭环

- **`R4-C1`** — **Author Resolution**: `accepted` → **本轮核实**: `design.md:11-14, 76, 149-154, 168, 171, 331`、`specs/gateway/task-graphs.md:5-20, 118-127`、`specs/im/task-graphs.md:120-162` 完整落地 `doing_wake` 边沿水位、系统消息禁主动唤醒 `Inbox` 及 `task-notifications.ts` 九态文案 — **`closed`**。
- **`R4-W1`** — **Author Resolution**: `accepted` → **本轮核实**: `design.md:11, 14, 108, 162, 199-202`、`specs/gateway/personal-agent.md:21-24` 改为 `agent/pre-step` `await product.proactive.sync_observations` 并返回未消费会话摘要附尾提示 — **`closed`**。
- **`R4-W2`** — **Author Resolution**: `accepted` → **本轮核实**: `design.md:11-14, 77, 162, 172`、`specs/gateway/task-graphs.md:21-31`、`specs/im/task-graphs.md:112-115` 闭环无 `schedule_id` 静默等待、`waitHealth` 条件巡检、`asked_user_id` 成员校验与 `task.wait.repair` 全链路退役 — **`closed`**。
- **`R4-W3`** — **Author Resolution**: `accepted` → **本轮核实**: `design.md:13-14, 103, 331`、`specs/gateway/personal-agent.md:10-14` 明确双水位状态机、私聊+群观察触发面与 `proactive_planning` 运行时门禁 — **`closed`**。
- **`R4-W4`** — **Author Resolution**: `accepted` → **本轮核实**: `specs/gateway/task-graphs.md`（`ADD 4 / MOD 6 / REM 5`）与 `specs/im/task-graphs.md`（`ADD 2 / MOD 6 / REM 1`）与基线规范逐字校验零失配、零冲突 — **`closed`**。
- **`R4-R1`** — **Author Resolution**: `accepted` → **本轮核实**: `prototype.html:1774-1877, 2170-2207`、`focus-mobile.png`、`specs/im/{task-graphs,ios-client}.md` 已同步落实 — **`closed`**。
- **Round 1–3 历史条目**：维持 Round 4「历史问题闭环」记录的 `closed` / `superseded by Q8/Q9` 状态。

### Issues

无（`0 CRITICAL / 0 WARNING`）。

### Recommendations

无。

---

## Round 6

### Metadata

- **reviewer**: `change-design-reviewer` (same independent subagent instance as Rounds 1–5, integrating `codebase-design`, `agent-context-review`, `frontend-experience-review`)
- **target**: `docs/changes/feat-785-pa-proactivity` (`spec.md`, `design.md`, `prototype.html`, `evidence/screens/{chat-web,ios-chat}.png`, `specs/gateway/{personal-agent,agent-capabilities}.md`)
- **review_mode**: `delta`
- **mode_reason**: 相对 Round 5 `Approved` 基线（`02c08f286`），本轮增量将 PA 主会话后台唤醒拆分为「平时聊完安静 12m 轻量记账 `proactive_review`」与「夜间睡眠窗口在 `Dreaming` 之后执行每日一次深度筹划备实质早报 `proactive_nightly`」（涉及 `spec.md` Q2/Q7 与验收标准、`design.md` 三水位状态机与双隐藏唤醒模板、`specs/gateway/{personal-agent,agent-capabilities}.md` 及 `prototype.html` 时间戳）；渐进式目标图、九状态与 `doing_wake` 边沿单次唤醒、灵活 `waiting`、顶层 `task_cards`、`product.proactive.sync_observations` 及全部 `im/*`、`gateway/task-graphs.md` 契约均未变动，按规则采用 `delta` 增量审查。
- **retained_from**: `Round 4, Round 5`（沿用已通过审查的任务图模型与 API、`doing_wake` 单次事件唤醒、任务系统通知禁唤醒 `Inbox`、无闹钟 `waiting` 与 `waitHealth`、定时前观察流 `await` 同步、角色感知 `proactive_planning` 零指纹漂移、双视角焦点台与北极星全景 UI 及未变动的 4 份 delta-spec）。
- **started_at**: `2026-11-25T22:50:42+09:00`
- **completed_at**: `2026-11-25T22:58:10+09:00`
- **duration**: `7m 28s`

### Verdict

**Issues Found** — `0 CRITICAL / 3 WARNING` (plus `1 Recommendation`)

### Coverage 与证据

- **`retained_from: Round 4, Round 5`**：`git diff --stat 02c08f286 -- docs/changes/feat-785-pa-proactivity` 确认仅 `spec.md`、`design.md`、`prototype.html`（2 处展示时间戳）及 `specs/gateway/{personal-agent,agent-capabilities}.md` 发生修改；其余全部模块契约与 4 份 delta-spec 零改动，且脚本校验全部 6 份 delta-spec 的 Requirement 标题与增删计数（`24->23`、`19->20`、`18->19`、`8->8`、`19->19`、`64->65`）100% 匹配无冲突。
- **本轮增量变更与跨模块联动核查（`delta`）**：
  1. **产品语义与两阶段职责拆分（`spec.md` & `frontend-experience-review`）**：平时 `proactive_review` 只做确定性任务/事项 `schedule` 原位记账、半夜 `proactive_nightly` 统揽全天上下文准备实质早报与 `<= 3` 张 `proposed` 卡的设计，很好地解决了用户「23:00 聊完 00:00 又补充导致反复重做早报」的真实痛点；目视核查重渲染的 `chat-web.png` 与 `ios-chat.png`（`今日 02:18` 夜间系统记录 + `今日 09:10` 晨间对齐附带要点与活卡片），画面自然清晰。
  2. **`Dreaming` 真实调度机制与跨进程时序核查（`codebase-design`）**：逐行核查 `packages/dsh-integration/src/knowledge/{dreaming,document-memory,runtime}.ts`、`packages/product-contracts/src/{knowledge,capabilities}.ts` 与 `packages/dsh-integration/src/index.ts`，发现「被动等待同夜已到期或在途 `Dreaming`」与现行 `Dreaming` 的 24 小时滚动间隔机制不匹配，且 `proactive_nightly` 存在午夜 `02:00` 熬夜抢占与跨 Compaction 早间交接缺口（见 `R6-W1`–`R6-W3`）。

### 历史问题闭环

- **`R1`–`R5` 全部历史问题**：维持 Round 5 已核实的 `closed`（及 `superseded by Q8/Q9`）状态；本轮新增的 `proactive_nightly` 已同步纳入 `dsh-integration` 的 `proactive_planning` `capabilities.held`、`usage()` 忙态与停用取消门禁（`design.md:14, 105`），未破坏既有修复。

### Issues

#### `R6-W1` [WARNING] 现成 `Dreaming` 按「上次成功 + 24h 滚动间隔」而非凌晨固定时钟触发，仅“被动等待已到期或在途 `Dreaming`”无法兑现当夜分寸先行落盘，且读取最新 `MEMORY.md` 依赖可选 `read` 工具

- **位置**：
  - `docs/changes/feat-785-pa-proactivity/spec.md:47, 166-167, 288-291`
  - `docs/changes/feat-785-pa-proactivity/design.md:13-14, 105, 163, 195-197, 216, 235, 330, 339`
  - `docs/changes/feat-785-pa-proactivity/specs/gateway/personal-agent.md:18-19`
  - `packages/dsh-integration/src/knowledge/dreaming.ts:112-118, 152-158, 165-175`、`packages/product-contracts/src/knowledge.ts:13`、`packages/product-contracts/src/capabilities.ts:57-62, 73`
- **证据**：
  1. **滚动 24h 计时导致凌晨 `02:00–05:00` 时 `Dreaming` 绝大多数情况下既未到期也未在运行**：`spec.md:288-291`（`Scenario: 从主人的对话反馈中学习主动分寸并在当夜筹划即刻生效`）与 `M1 [reviewer]` ⑤ 要求白天/晚间对话划定的免提议边界在当夜先经 `Dreaming` 写入 `MEMORY.md`，随后同一夜的 `proactive_nightly` 即刻读取遵守。但核查 `packages/dsh-integration/src/knowledge/dreaming.ts:112-118` 与 `knowledge.ts:13`，现行自动 `Dreaming` 并非凌晨定时任务，其 `dueAt = (lastSuccessAutomatic ?? activationAt) + 86_400_000`（距激活或上次自动成功满 24h + 安静 10m）。只要 PA 是在白天激活或上次自动 `Dreaming` 发生在白天（如 `14:00`），到了凌晨 `02:00–05:00` 时 `now < dueAt` 且 `active` 为空；若按 `design.md:105` 与 `specs/gateway/personal-agent.md:18` 字面实现（「若同夜 `Dreaming` 已到期或正在运行则先等待」），宿主会直接跳过 `Dreaming`，用昨天未更新的旧 `MEMORY.md` 跑完 `proactive_nightly`。同时 `proactive-coordinator`（`personal-assistant`）与 `Dreaming`（`dsh-integration`）分属父子进程，若在 `session.submit` 内同步阻塞数分钟等待 `Dreaming` LLM 整合，期间前台新消息到达也会产生准入竞态。
  2. **`<proactive-nightly-wake>` 指令强依赖未纳入固定/必选集合的 `read` 工具**：`design.md:216, 235` 指示模型在 `proactive_nightly` 首步调用 `read` 读取 `.nanoassistant/memory/MEMORY.md`；但 `read` 既不在 `fixedTools('global', 'personal')`（`capabilities.ts:57-62`）中，也未声明在 `proactive_planning.requires.tools`（`design.md:163` 仅声明 `['task_graph']`，以兼容存量配置不报错）中。若存量 PA 自定义 `tool_allowlist` 未勾选 `read`，该步骤将无法执行；而实际上 `dsh-integration` 在组装 `<proactive-nightly-wake>` 尾部消息时本身就持有 `documents.forConfig(config)`，可直接把相对窗口快照发生变更的最新 `MEMORY.md` 内容附在该尾部隐藏消息内（零额外工具轮次、兼容任意 `tool_allowlist`，且因仅追加尾部消息同样 100% 满足 `NoSilentPrefixRewrite`）。
- **影响**：真实运行中白天/晚间刚说的“某类家庭事务别立卡”在当夜 `02:15` 尚未进入 `MEMORY.md`，`proactive_nightly` 仍会在当夜违规立卡；未启用 `read` 工具的存量 PA 在夜间轮首步即报错。
- **建议方向**：保持 `dreaming*.ts` 零代码改动，在 `dsh-integration/src/index.ts` 处理 `proactive_nightly` 前置条件时：若 `effectiveFeatures.dreaming === true` 且 `memoryMode !== 'legacy'` 且当夜尚未完成本轮活动对应的 `Dreaming`，主动调用现成公开入口 `knowledge.dreaming.start(agent, false)`（`dreaming.ts:165` 原生绕过 `dueAt` 时间锁，且无新增材料时零模型调用直接返回 `no_eligible_increment`），在 `Dreaming` 运行期间对 `proactive_nightly` 返回 `{ accepted: false, busy: true }`（或经独立前置 RPC 协调）交由 `proactive-coordinator` 空闲重试；同时由 `dsh-integration` 在 `<proactive-nightly-wake>` 尾部消息中直接内联最新 `MEMORY.md`（或当 `MEMORY.md` 较窗口首轮快照有更新时附带最新正文）。

#### `R6-W2` [WARNING] `proactive_nightly` 缺少熬夜活跃后的最小静默时长门禁，`02:00` 边界可能抢占仍在连续发言的主会话

- **位置**：
  - `docs/changes/feat-785-pa-proactivity/spec.md:47, 164, 256`
  - `docs/changes/feat-785-pa-proactivity/design.md:104-105`
  - `docs/changes/feat-785-pa-proactivity/specs/gateway/personal-agent.md:17-18`
- **证据**：`proactive_review`（`design.md:104`）要求 `距 last_activity_at 满静默窗口（默认 12m）`，但 `proactive_nightly`（`design.md:105`、`specs/gateway/personal-agent.md:17-18`）仅检查「进入本地 `02:00–05:00` 窗口 + `last_activity_seq > last_nightly_seq` + 当夜未跑过 + `onlyIfIdle: true`」。若主人熬夜在 `01:58` 刚发完上一句、PA 在 `01:58:10` 回复完毕回到 `idle`，仅隔不到 2 分钟到 `02:00:00` 时上述条件即全部满足，宿主会立刻在主会话启动重度多步 `proactive_nightly` 筹划轮，与主人 `02:01` 的下一句实时消息撞车，违背 `spec.md:47, 164, 256`（「半夜彻底睡熟后」「实时对话优先快速自然回复，不在主人连续发言时插话」）。
- **影响**：熬夜跨 `02:00` 聊天时主会话会被长耗时的夜间深度筹划立即占用，拖慢实时对话响应且拿未聊完的半截对话提前立卡。
- **建议方向**：为 `proactive_nightly` 同样补齐最小静默时长门禁（例如在本地 `02:00–05:00` 窗口内同时要求 `now - last_activity_at >= nightly_quiet_ms`，如 `>= 30m` 或至少不低于静默记账窗口），确保主人真正停聊安静后再启动夜间 `Dreaming` 与 `proactive_nightly`。

#### `R6-W3` [WARNING] 固定早间 Cron 顺路送达仅靠“成果留在上文”，在自动上下文换窗（Compaction）与存量早间 Cron Prompt 下缺少持久承接与常驻指引

- **位置**：
  - `docs/changes/feat-785-pa-proactivity/design.md:108, 197, 204, 214-218, 235`
  - `docs/changes/feat-785-pa-proactivity/specs/gateway/personal-agent.md:21-25`
  - `packages/product-contracts/src/capabilities.ts:60`、`packages/dsh-integration/src/personal-agent-defaults.ts`
- **证据**：
  1. **跨上下文压缩丢失风险（`agent-context-review`）**：当主人已有固定早间 `schedule`（如 `09:10` 晨间计划对齐）时，`design.md:108, 235` 规定 `proactive_nightly` 不另设闹钟，仅把准备要点“留在主会话末尾 / 成果留在上文供明早顺路合一送达”。但由于 PA 主会话是长期复用的单根会话，`proactive_nightly` 多步查证与建卡后（或 `09:10` 唤醒首步）一旦触及模型上下文窗口上限触发自动 Compaction，仅留在历史助手回复中的候选要点、工作区草稿路径与待附带 `TaskCardRef` 精确 ID 会被压缩摘要抹平。
  2. **存量早间 Cron Prompt 不含新能力指令**：存量用户在升级前已建好的 `09:10` Cron 提示词（如“早上问候我并对齐今日计划”）并不会写“检查昨晚 `proactive_nightly` 准备的材料并在 `send_message` 附带 `task_cards`”；而 `design.md` §4 仅给出了 `<proactive-nightly-wake>` 模板，未同步交代 `nano-personal-agent` / `nano-proactive-care` 对早间 `schedule` 唤醒轮的承接指引。
- **影响**：主会话发生自动换窗或运行存量早间 Cron 时，`02:15` 夜间精心准备的实质干货与 `proposed` 活卡片无法在 `09:10` 顺路送达，退化回空手问候。
- **建议方向**：在 `design.md`（§关键决策 D5 与 §接口与数据流 4）明确：① `proactive_nightly` 将待早间顺路呈递的实质要点摘要/工作区文件路径与新立 `TaskCardRef` 同步记入跨 Compaction 持久保留的固定根工具 `notes`（`capabilities.ts:60`）；② 在 `nano-personal-agent` / `nano-proactive-care` 常驻指引中明确早间计划对齐定时轮检查未呈递的夜间筹备 `notes` 与 `proposed` 卡，于同一条早间消息附带要点/附件与 `task_cards` 后清理该待送达标记。

### Recommendations

- **`R6-R1`**：顺手同步两处文档细节笔误：① `design.md:272` 原型对齐契约第 5 行引用了 `M1 [reviewer] ⑦`，实际 `M1`（`:339`）共 `①–⑥` 项（对应 `⑥PA 主动开关与离线/依赖一致性`）；② `design.md:308` 风险表首行文案仍写“PA 安静后静默复盘产出过多或过时提议”，可同步更新为“PA 夜间深度筹划产出过多或过时提议”。

### Author Resolutions

- **`R6-W1` — `accepted`**：核实完全属实（`packages/dsh-integration/src/knowledge/dreaming.ts:112-118` 采用 24h 滚动 `dueAt`，且 `read` 不在 `fixedTools` 中）。已在 `design.md`（§涉及范围、§关键决策 D4、§接口与数据流 3/4、§Milestones）与 `specs/gateway/personal-agent.md` 修正：保持 `dreaming*.ts` 零代码改动，由 `dsh-integration/src/index.ts` 在准入 `proactive_nightly` 时若 `dreaming` 开启且当夜未整合最新活动，异步调用公开方法 `knowledge.dreaming.start(agent, false)` 并立即非阻塞返回 `{ accepted: false, busy: true }` 交由节点重试（异常达上限降级放行不饿死）；准入通过时由宿主直接将较窗口首轮快照有更新的 `MEMORY.md` 作为 `<updated-formal-memory>` 内联附入 `<proactive-nightly-wake>` 尾部消息，零 `read` 工具依赖且满足 `NoSilentPrefixRewrite`。
- **`R6-W2` — `accepted`**：核实属实。已在 `design.md`（§涉及范围、§关键决策 D4、§接口与数据流 3、§Milestones）与 `specs/gateway/personal-agent.md` 为 `proactive_nightly` 补齐 `now - last_activity_at >= nightly_quiet_ms`（默认 `30m`）最小夜间静默时长门禁，杜绝主人熬夜跨 `02:00` 连续发言时抢占主会话。
- **`R6-W3` — `accepted`**：核实属实（`capabilities.ts:60` 固定工具 `notes` 跨 Compaction 保留，而存量 `09:10` Cron 不含新指令）。已在 `design.md`（§涉及范围、§关键决策 D5、§接口与数据流 3/4、§Milestones）与 `specs/gateway/personal-agent.md` 明确：`proactive_nightly` 将待早间顺路送达的要点摘要/草稿路径与 `TaskCardRef` 写入固定根工具 `notes`，并在 `personal-agent-defaults.ts`（`nano-personal-agent`）与 `nano-proactive-care` 常驻指引中规定早间计划对齐定时轮读取消费该待送达 `notes` 与 `proposed` 卡、同条消息附带 `task_cards` 后清理标记。
- **`R6-R1` — `accepted`**：已同步修正 `design.md` 原型对齐契约编号（`⑦` → `⑥`）与风险表首行文案。

---

## Round 7

### Metadata

- **reviewer**: `change-design-reviewer` (same independent subagent instance as Rounds 1–6, integrating `codebase-design`, `agent-context-review`, `frontend-experience-review`)
- **target**: `docs/changes/feat-785-pa-proactivity` (`design.md`, `specs/gateway/personal-agent.md`)
- **review_mode**: `closure`
- **mode_reason**: 本轮仅针对 Round 6 的 `R6-W1`–`R6-W3` 与 `R6-R1` 在 `design.md` 与 `specs/gateway/personal-agent.md` 内完成闭环收敛，未扩大核心边界或新增跨包协议结构，按规则采用 `closure` 闭环复审。
- **retained_from**: `Round 4, Round 5, Round 6`（沿用前序轮次已核实的渐进式目标图、九状态与 `doing_wake` 单次边沿唤醒、无闹钟静默 `waiting`、顶层 `task_cards`、`product.proactive.sync_observations`、角色感知 `proactive_planning` 零指纹漂移、双视角焦点台与北极星全景原型及全部 6 份 delta-spec 标题/计数校验）。
- **started_at**: `2026-11-25T23:02:49+09:00`
- **completed_at**: `2026-11-25T23:05:10+09:00`
- **duration**: `2m 21s`

### Verdict

**Approved** — `0 CRITICAL / 0 WARNING` (plus `1 Recommendation`)

### Coverage 与证据

- **`retained_from: Round 4, Round 5, Round 6`**：脚本再次核对全部 6 份 delta-spec 与 `docs/specs/{gateway,im}/*` 的 Requirement 标题及增删计数（`24->23`、`19->20`、`18->19`、`8->8`、`19->19`、`64->65`）零失配、零冲突；其余未改动文件沿用前序审查证据。
- **本轮闭环项与局部一致性核查（`closure`）**：
  1. **主动前置 `Dreaming` 与尾部内联更新 `MEMORY.md`（`R6-W1`）**：核查 `design.md:14, 105, 195-197, 216, 234-239, 342` 与 `specs/gateway/personal-agent.md:18-19`，保持 `dreaming*.ts` 零代码改动，由 `dsh-integration/src/index.ts` 在准入 `proactive_nightly` 时对开启 `dreaming` 且当夜有未整合活动的 PA 异步调用现成公开方法 `knowledge.dreaming.start(agent, false)`，运行期间立即非阻塞返回 `{ accepted: false, busy: true }` 交由 `proactive-coordinator` 稍后重试（异常达上限降级放行不饿死，关闭 `dreaming` 特性直接放行）；准入通过时直接将较窗口首轮快照有更新的 `MEMORY.md` 作为 `<updated-formal-memory>` 附入 `<proactive-nightly-wake>` 尾部消息，彻底解除了 24h 滚动 `dueAt` 错位与可选 `read` 工具依赖，且严格保持 `NoSilentPrefixRewrite`。
  2. **夜间最小静默时长门禁（`R6-W2`）**：核查 `design.md:13, 105, 195, 342` 与 `specs/gateway/personal-agent.md:17`，夜间窗口调整为 `02:00–05:30` 并要求 `now - last_activity_at >= nightly_quiet_ms`（默认 `30m`），既防止 `02:00` 抢占熬夜连续对话，又给凌晨 `04:45` 刚停聊的场景留足 `30m` 安静触发余量。
  3. **固定工具 `notes` 跨 Compaction 早间交接与常驻指引（`R6-W3`）**：核查 `design.md:14, 108, 197, 204, 216-217, 238, 342`、`specs/gateway/personal-agent.md:19` 对照 `packages/dsh-integration/src/personal-agent-defaults.ts` 与 `packages/product-contracts/src/capabilities.ts:60`，`proactive_nightly` 将待早间顺路送达的要点摘要/草稿路径与 `TaskCardRef` 写入跨 Compaction 保留的固定工具 `notes`，并由 `nano-personal-agent` / `nano-proactive-care` 常驻指引驱动存量早间 Cron 同条消息消费并清理，链路完整自洽。

### 历史问题闭环

- **`R6-W1`** — **Author Resolution**: `accepted` → **本轮核实**: `design.md:14, 105, 216, 234-239`、`specs/gateway/personal-agent.md:18-19` 完整闭环 — **`closed`**。
- **`R6-W2`** — **Author Resolution**: `accepted` → **本轮核实**: `design.md:13, 105, 195`、`specs/gateway/personal-agent.md:17` 补齐 `nightly_quiet_ms = 30m` 静默门禁 — **`closed`**。
- **`R6-W3`** — **Author Resolution**: `accepted` → **本轮核实**: `design.md:14, 108, 216-217, 238`、`specs/gateway/personal-agent.md:19` 补齐固定 `notes` 跨压缩交接与早间常驻消费指引 — **`closed`**。
- **`R6-R1`** — **Author Resolution**: `accepted` → **本轮核实**: `design.md:275, 311` 编号与风险文案已同步 — **`closed`**。
- **`R1`–`R5` 全部历史条目**：维持 `closed`（及 `superseded by Q8/Q9`）。

### Issues

无（`0 CRITICAL / 0 WARNING`）。

### Recommendations

- **`R7-R1`**：M1 实施 `dsh-integration` 中的常驻指导（`personal-agent-defaults.ts`、`nano-ongoing-work`、`nano-proactive-care`）以及运行时动态注入提示（`<proactive-review-wake>`、`<proactive-nightly-wake>` 与 `sync_observations` 未读收件箱提示）时，注意遵循既有规范 `docs/specs/gateway/agent-capabilities.md:1118`（“Nano 自有固定指导和动态行动提示使用英文”），将 `design.md` §4 中文示意模板落为英文运行时文本（内联的 `MEMORY.md` 用户记忆正文照原样保留）。

### Author Resolutions

- **`R7-R1` — `accepted`**：采纳为 M1 代码实施细节（遵循 `docs/specs/gateway/agent-capabilities.md:1118`，将 `personal-agent-defaults.ts`、随包 Skills 及 `<proactive-review-wake>` / `<proactive-nightly-wake>` / `sync_observations` 运行时系统提示实现为英文，`<updated-formal-memory>` 中用户记忆正文照原样保留），与当前已通过审查的冻结设计产物完全一致，无需再改动受审文档。

---

## Round 8

### Metadata

- **reviewer**: `change-design-reviewer` (same independent subagent instance as Rounds 1–7, integrating `codebase-design`, `agent-context-review`, `frontend-experience-review`)
- **target**: `docs/changes/feat-785-pa-proactivity` (`spec.md`, `design.md`, `prototype.html`, `evidence/screens/{chat-web,ios-chat}.png`, `specs/gateway/{agent-capabilities,personal-agent}.md`)
- **review_mode**: `delta`
- **mode_reason**: 相对 Round 7 `Approved` 基线（`15d28b823`），本轮新增跨主体调度变更——将全员（PA 与所有普通 Agent）的自动 `Dreaming` 统一从 24h 滚动间隔升级为本地凌晨 `03:00` 自然日锚点 + `30m` 安静门禁 + 合盖唤醒补跑不漂移，涉及 `packages/product-contracts/src/knowledge.ts`、`packages/dsh-integration/src/knowledge/{dreaming,dreaming-state}.ts` 及 `specs/gateway/agent-capabilities.md` 新增 `MODIFIED Requirement`；其余任务图、九状态、单次边沿唤醒、观察流同步与双端 UI 架构未变，按规则采用 `delta` 增量审查。
- **retained_from**: `Round 4, Round 5, Round 6, Round 7`（沿用前序轮次已核实的渐进式目标图、九状态与 `doing_wake` 单次边沿唤醒、无闹钟静默 `waiting`、顶层 `task_cards`、`product.proactive.sync_observations`、固定工具 `notes` 跨压缩早间交接、角色感知 `proactive_planning` 零指纹漂移及未改动的 4 份 delta-spec）。
- **started_at**: `2026-11-26T00:21:07+09:00`
- **completed_at**: `2026-11-26T00:27:30+09:00`
- **duration**: `6m 23s`

### Verdict

**Issues Found** — `0 CRITICAL / 2 WARNING` (plus `1 Recommendation`)

### Coverage 与证据

- **`retained_from: Round 4, Round 5, Round 6, Round 7`**：`git diff --stat 15d28b823 -- docs/changes/feat-785-pa-proactivity` 确认仅 `spec.md`、`design.md`、`prototype.html`（`03:12` 时间戳）与 `specs/gateway/{agent-capabilities,personal-agent}.md` 发生变更；脚本再次核对全部 6 份 delta-spec 与基线 `docs/specs/{gateway,im}/*` 的标题及净计数（其中 `gateway/agent-capabilities.md` 为 `64 -> 65`，`ADD=1, MOD=1` 精确命中 `docs/specs/gateway/agent-capabilities.md:980-995`），零标题失配；目视检查重渲染的 `chat-web.png` 与 `ios-chat.png`（`今日 03:12` 系统记录与 `今日 09:10` 晨间对齐）正常无误。
- **本轮增量变更与全仓影响面核查（`delta`）**：
  - 将 PA 与普通团队 Agent 统一收敛到同一套「凌晨 `03:00` 自然日锚点 + 合盖唤醒补跑锁回 `03:00`」的 `Dreaming` 调度在概念上比上一轮“PA 单独强拉 `dreaming.start`”更简洁统一。
  - 对照真实代码 `apps/node/src/main.ts`、`packages/personal-assistant/src/store.ts`、`packages/product-contracts/src/knowledge.ts`、`packages/dsh-integration/src/knowledge/{dreaming,dreaming-state}.ts`、`packages/dsh-integration/src/owned-sessions.ts` 及 `packages/dsh-integration/src/evaluation/runtime.ts` 逐条追踪后，发现 2 项需要闭环的设计/装配缺口（`R8-W1`、`R8-W2`）。

### 历史问题闭环

- **`R7-R1`** — **Author Resolution**: `accepted`（作为 M1 英文运行时提示实施约束采纳）— **`closed`**。
- **`R1`–`R6` 全部历史条目**：维持 `closed`（其中 `R6-W1` 关于 `Dreaming` 先行落盘机制在本轮升级为全员统一 `03:00` 锚点后引出的时区源与边界细节由 `R8-W1`、`R8-W2` 跟进）。

### Issues

#### `R8-W1` [WARNING] 全员 `Dreaming`（`dsh-integration`）与 `proactive-coordinator`（`personal-assistant`）缺少统一时区同步，`TZ=UTC` 节点会出现 8 小时锚点错位与 `proactive_nightly` 空等失效

- **位置**：
  - `docs/changes/feat-785-pa-proactivity/spec.md:88, 274`
  - `docs/changes/feat-785-pa-proactivity/design.md:11, 13-14, 103, 106, 196`
  - `docs/changes/feat-785-pa-proactivity/specs/gateway/agent-capabilities.md:19`、`specs/gateway/personal-agent.md:17-18`
  - `apps/node/src/main.ts:263, 322, 602`、`packages/personal-assistant/src/store.ts:284-290`、`packages/dsh-integration/src/`
- **证据**：
  1. 在本仓多节点部署拓扑中，Linux 云主机/容器节点常以系统时区 `TZ=UTC` 运行，因此 `apps/node/src/main.ts:263, 322, 602` 专门从 `im-server` 接收并持久化 `store.ownerTimezone`（如 `Asia/Shanghai`）供 `Heartbeat` 与 `Inbox` 判定本地作息。
  2. 全仓检索 `packages/dsh-integration/src/` 确认子进程目前**从未接收 `ownerTimezone`**。若按 `design.md:13-14, 103, 106` 实现：
     - 若 `personal-assistant` 侧 `proactive-coordinator` 沿用 `store.ownerTimezone`（`Asia/Shanghai`），而 `dsh-integration` 侧 `Dreaming` 读取宿主进程系统时区（`UTC`），则北京时间凌晨 `03:00`（即前一日 `19:00 UTC`）两进程计算的 `currentSlotKey` 与 `03:00` 锚点相差 8 小时——`dsh-integration` 要么误判上一 UTC 槽位已完成而在未跑当夜 `Dreaming` 的情况下直接放行 `proactive_nightly`，要么因等待 `03:00 UTC`（北京时间上午 `11:00`）而连续 3 小时返回 `{ accepted: false, busy: true }` 导致当夜 `proactive_nightly` 彻底轮空；
     - 反之若两边都只读宿主 OS `TZ=UTC`，则 `UTC` 云节点上的“凌晨 `03:00` 记忆总结 + 夜间深度筹划”会在北京时间**上午 `11:00`**（工作日上午、且晚于 `09:10` 晨间对齐 Cron 两小时后）才触发。
- **影响**：云端或容器 `TZ=UTC` 节点上夜间 `Dreaming` 与 `proactive_nightly` 时钟错位，导致当夜筹划跳过 `Dreaming`、整晚 `busy` 空转或拖到白天 `11:00` 才运行。
- **建议方向**：由 `apps/node` 将 `effectiveTimezone = store.ownerTimezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone` 在启动握手及收到 `user.timezone`（`apps/node/src/main.ts:263`）时通过轻量运行时通知同步给 `dsh-integration`（**不写入 `canonicalAgentConfiguration`**，保持存量配置 SHA-256 指纹零漂移），使 `Dreaming` 与 `proactive-coordinator` 严格基于同一时区源计算 `03:00` 锚点与 `cycleKey`。

#### `R8-W2` [WARNING] `Dreaming` 自然日槽位升级与现有 `dreaming.ts` 四处实现边界（冷根会话未水合、运行中绕过 `quietMs`、`evaluation/runtime.ts` 调用链、无限重试无“耗尽”态）冲突

- **位置**：
  - `docs/changes/feat-785-pa-proactivity/design.md:11, 14, 103, 106, 343`
  - `docs/changes/feat-785-pa-proactivity/specs/gateway/agent-capabilities.md:19-21`、`specs/gateway/personal-agent.md:18`
  - `packages/dsh-integration/src/knowledge/dreaming.ts:31, 102-107, 133, 150, 156, 204-213, 294`、`packages/dsh-integration/src/owned-sessions.ts:25-32`、`packages/dsh-integration/src/evaluation/runtime.ts:103-108`
- **证据**：
  1. **冷根会话（Cold Root）未水合时 `dreaming.tick` 永远跳过普通 Agent 与重启开盖补跑（`dreaming.ts:150`）**：`dreaming.ts:150` 通过 `this.ctx.agents.get(SessionId(binding.sessionId))` 获取内存态根实例，未命中即直接 `return`。当节点进程重启或笔记本重启开盖后，尚未收到新前台消息触发 `owned.resolve(sessionId)` 的普通团队 Agent（或 PA）在 `ctx.agents` 中始终不存在，凌晨 `03:00` 自动整理与开盖补跑会永久静默跳过（到期且存在已持久化的绑定根会话时需经 `nanoSessions.resolve(binding.sessionId, false)` 按需水合）。
  2. **`dreaming.ts:156` 在 `parent.status === 'running'` 时会绕过 `30m` 安静门禁**：现行第 156 行 `if (this.foregroundRequests > 0 || !quiet && parent.status === 'idle') return;` 在主会话处于工具执行或子任务等待间隙（`parent.status === 'running'` 且无在途流式请求）时不检查 `quiet`。在默认夜间 `03:00` 锚点模式下，若用户熬夜至 `03:05` 正在跑工具任务，`Dreaming` 会无视 `30m` 安静门禁立即启动，违背 `specs/gateway/agent-capabilities.md:19`（应仅在显式配置 `intervalMs` 覆盖时保留旧判断，默认夜间自然日模式无条件要求 `quiet === true`）。
  3. **新建/评测初始化的初始槽位与 `evaluation/runtime.ts:103-108` `nextAutomaticAt` 循环**：记忆评测运行时（`evaluation/runtime.ts:103-108`）使用默认 `Dreaming` 配置在 `while (due < arrival)` 循环中驱动 `dreaming.nextAutomaticAt(agentId)`。由于 `[D 03:00, (D+1) 03:00)` 归属槽位 `D`，不仅存量升级、**新建或评测首次初始化的 `DreamingOwner`（`dreaming.ts:133`）也必须将初始 `lastCompletedCycle` 设为 `slotKey(imported?.lastSuccessAutomatic ?? owner.activationAt)`**（否则白天 `14:00` 新建的 Agent 因已跨过当日 `03:00`，会在 `14:30` 立即误跑一次白天 `Dreaming`），且 `nextAutomaticAt` 须基于 `this.now()` 返回下一未完成槽位的 `max(retryAt ?? 0, slotAnchorMs, quietAt)`，`lastCompletedCycle` 仅在整轮多批 `execute()` 完整消化冻结边界后（`:211`，含 `no_eligible_increment`）落盘。
  4. **`dreaming.ts:31, 294` 无“耗尽重试”终态**：`design.md:106` 与 `specs/gateway/personal-agent.md:18` 规定当夜 `Dreaming` “未耗尽重试”时 `proactive_nightly` 返回 `busy: true`、“耗尽时直接放行”；但 `dreaming.ts:31, 294` 中 `failures` 无限递增并以 `7200000ms`（2 小时）无限设置 `retryAt`，永远不会自动进入“耗尽”态。需明确具体放行条件（如当夜 `owner.failures >= 3` 或 `owner.retryAt` 已超过当日 `06:00` 筹划窗口截止时间时直接降级放行 `proactive_nightly`）。
- **影响**：重启后未发言的 Agent 漏跑夜间/开盖补跑 `Dreaming`、熬夜跑工具时 `03:00` 提前闯入、白天新建 Agent 首日下午误跑 `Dreaming` 或评测 `prepare` 行为偏移，以及 `Dreaming` 故障夜 `proactive_nightly` 整晚卡在 `busy` 无法降级。
- **建议方向**：在 `design.md`（§涉及范围 `dsh-integration` 与 §关键决策 D4.1 / D4.4）补充上述四点精确收敛规则，将 `Dreaming` 自然日升级与存量代码及评测管线严丝合缝对齐。

### Recommendations

- **`R8-R1`**：`spec.md:126`（「先零改动运行现有 `Dreaming`」）与 `spec.md:142` 流程图节点（「`2. 半夜 Dreaming（零改动）`」）仍残留上一轮措辞，建议顺手同步为与 `spec.md:47, 88, 303` 一致的「全员统一夜间 `Dreaming`（整理逻辑零改动）」。

### Author Resolutions

- **`R8-W1` — `accepted`**：核实完全属实（`apps/node/src/main.ts:263, 322, 602` 持有 `store.ownerTimezone`，而 `dsh-integration` 在 `TZ=UTC` 节点上此前仅读系统时区）。已在 `design.md`（§涉及范围、§关键决策 D4.1/D4.4、§Milestones）与 `specs/gateway/{agent-capabilities,personal-agent}.md` 补齐 `runtime.timezone` 跨进程同步（`effectiveTimeZone = store.ownerTimezone ?? hostSystemTimeZone`，不改写 `canonicalAgentConfiguration` 指纹），使 `Dreaming` 与 `proactive-coordinator` 严格共用同一时区源。
- **`R8-W2` — `accepted`**：核实四处实现边界均属实（`dreaming.ts:31, 102-107, 133, 150, 156, 211, 294` 与 `evaluation/runtime.ts:103-108`）。已在 `design.md`（§涉及范围、§关键决策 D4.1/D4.4、§Milestones）与 `specs/gateway/{agent-capabilities,personal-agent}.md` 全部闭环：①到期且安静时对未水合的已持久根会话按需 `owned.resolve(binding.sessionId, false)`；②默认夜间模式无条件要求 `quiet === true`（仅显式 `intervalMs` 保留旧判断）；③新建、评测与升级 `DreamingOwner` 统一以 `slotKey(imported?.lastSuccessAutomatic ?? activationAt)` 初始化初始槽位，`nextAutomaticAt` 基于 `this.now()` 单调推进且仅在整轮多批 `execute()` 收口时落盘 `lastCompletedCycle`；④明确 `proactive_nightly` 在 `owner.failures >= 3` 或 `owner.retryAt >= 06:00` 窗口截止时直接降级放行。
- **`R8-R1` — `accepted`**：已同步更新 `spec.md:126, 142` 措辞与流程图节点标签。

---

## Round 9

### Metadata

- **reviewer**: `change-design-reviewer` (same independent subagent instance as Rounds 1–8, integrating `codebase-design`, `agent-context-review`, `frontend-experience-review`)
- **target**: `docs/changes/feat-785-pa-proactivity` (`spec.md`, `design.md`, `specs/gateway/{agent-capabilities,personal-agent}.md`)
- **review_mode**: `closure`
- **mode_reason**: 本轮仅围绕 Round 8 的 `R8-W1`、`R8-W2` 与 `R8-R1` 补齐 `runtime.timezone` 跨进程时区同步及 `Dreaming` 四处运行时边界收敛，未扩大产品范围或改变核心模块职责，按规则采用 `closure` 闭环复审。
- **retained_from**: `Round 4, Round 5, Round 6, Round 7, Round 8`（沿用前序轮次已核实的渐进式目标图、九状态与 `doing_wake` 单次边沿唤醒、无闹钟静默 `waiting`、顶层 `task_cards`、`product.proactive.sync_observations`、固定工具 `notes` 跨压缩早间交接、角色感知 `proactive_planning` 零指纹漂移、双视角焦点台与北极星全景原型及全部 6 份 delta-spec 标题/计数校验）。
- **started_at**: `2026-11-26T00:31:22+09:00`
- **completed_at**: `2026-11-26T00:33:40+09:00`
- **duration**: `2m 18s`

### Verdict

**Approved** — `0 CRITICAL / 0 WARNING`

### Coverage 与证据

- **`retained_from: Round 4, Round 5, Round 6, Round 7, Round 8`**：脚本再次核对全部 6 份 delta-spec 与 `docs/specs/{gateway,im}/*` 的 Requirement 标题及增删计数（`24->23`、`19->20`、`18->19`、`8->8`、`19->19`、`64->65`）100% 匹配零冲突；未改动文件沿用前序审查证据。
- **本轮闭环项与局部一致性核查（`closure`）**：
  1. **`runtime.timezone` 跨进程统一时区源（`R8-W1`）**：核查 `design.md:11, 13-14, 103, 106, 343` 与 `specs/gateway/{agent-capabilities,personal-agent}.md`：`apps/node/src/main.ts` 在运行时连接建立与收到 `user.timezone` 更新时将 `effectiveTimeZone = store.ownerTimezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone` 经 `runtime.timezone` 同步给 `dsh-integration`（不进入 `canonicalAgentConfiguration`，保持存量配置 SHA-256 指纹不变），使 `Dreaming` 与 `proactive-coordinator` 在 `TZ=UTC` 节点上严格共用同一时区计算 `03:00` 锚点与 `currentSlotKey`。
  2. **`Dreaming` 四处运行时边界收敛（`R8-W2`）**：核查 `design.md:14, 103, 106, 343` 对照 `packages/dsh-integration/src/owned-sessions.ts:172-174` 与 `evaluation/runtime.ts:103-108`：①到期且安静时对存在已持久化根会话记录但尚未水合的绑定按需 `owned.resolve(binding.sessionId, false)` 加载（未创建过持久会话的新空绑定安全跳过）；②默认夜间模式无条件要求 `quiet === true`（`30m`），仅显式 `intervalMs` 保留旧判断；③新建、评测与升级 `DreamingOwner` 统一以 `slotKey(imported?.lastSuccessAutomatic ?? activationAt)` 初始化初始槽位（避免白天新建首日误跑），`nextAutomaticAt` 基于 `this.now()` 单调推进且仅在整轮多批 `execute()` 收口时落盘 `lastCompletedCycle`；④`proactive_nightly` 在 `owner.failures >= 3` 或 `(owner.retryAt ?? 0) >= nightWindowEndAt`（`06:00`）时直接降级放行，消除整晚死等风险。`M1 [worker]` ③ 已同步覆盖上述全部单测/集成测试点。

### 历史问题闭环

- **`R8-W1`** — **Author Resolution**: `accepted` → **本轮核实**: `design.md:11, 13-14, 103, 106, 343`、`specs/gateway/{agent-capabilities,personal-agent}.md` 完整闭环 — **`closed`**。
- **`R8-W2`** — **Author Resolution**: `accepted` → **本轮核实**: `design.md:14, 103, 106, 343`、`specs/gateway/{agent-capabilities,personal-agent}.md` 四处边界全部闭环 — **`closed`**。
- **`R8-R1`** — **Author Resolution**: `accepted` → **本轮核实**: `spec.md:126, 142` 已同步统一 — **`closed`**。
- **`R1`–`R7` 全部历史条目**：维持 `closed`（及 `superseded by Q8/Q9`）。

### Issues

无（`0 CRITICAL / 0 WARNING`）。

### Recommendations

无。

---

## Round 10

### Metadata

- **reviewer**: `change-design-reviewer` (same independent subagent instance as Rounds 1–9, integrating `codebase-design`, `agent-context-review`, `frontend-experience-review`)
- **target**: `docs/changes/feat-785-pa-proactivity` (`spec.md`, `design.md`)
- **review_mode**: `delta`
- **mode_reason**: 相对 Round 9 `Approved` 基线（`3ada3a078`），本轮在 `spec.md` 新增 `Q10` 并在 `design.md` 新增隔离 E2E 统一逻辑时钟控制面（`NANO_E2E_LOGICAL_CLOCK_SOCKET`、`runtime.clock.advance`、`CronOwners` 基于 `@deepseek-ai/dsh-schedule` 公开导出的推进机制）、随包 `packages/personal-assistant/assets/skills/{nano-ongoing-work,nano-proactive-care}/SKILL.md` 升级定位与 5 关卡 24 小时真实模型验收脚本 `scripts/verify_pa_proactivity_24h.py`；6 份 delta-spec 与前端原型未改动，按规则采用 `delta` 增量审查。
- **retained_from**: `Round 4, Round 5, Round 6, Round 7, Round 8, Round 9`（6 份 delta-spec、`prototype.html` 及已通过审查的核心产品架构与前端体验沿用前序轮次证据）。
- **started_at**: `2026-11-26T01:10:17+09:00`
- **completed_at**: `2026-11-26T01:14:30+09:00`
- **duration**: `4m 13s`

### Verdict

**Issues Found** — `0 CRITICAL / 2 WARNING`

### Coverage 与证据

- **`retained_from: Round 4..Round 9`**：`git diff --stat 3ada3a078 -- docs/changes/feat-785-pa-proactivity` 确认仅 `spec.md` 与 `design.md` 变更，6 份 `specs/` delta-spec 与 `prototype.html` 零改动。
- **本轮增量与真实代码核查（`delta`）**：
  1. **架构红线与公开导出核查（`SPEC.md` & `test_runtime_dependency_contract.py`）**：
     - 核查 `packages/dsh-integration/node_modules/@deepseek-ai/dsh-schedule/package.json` 与 `lib/types/index.d.ts:7, 10`：`scheduleDomain`、`renderReminderFraming`、`renderRecurringReminderBatchFraming`、`resolveRecurringOccurrence`、`isRecurringScheduleRecord` 均由 `@deepseek-ai/dsh-schedule` 根入口 `"."` 正式公开导出，完全符合 `test_integration_imports_only_declared_public_dsh_exports`；本地 `0600` Unix Domain Socket（参照 `evaluation/runtime.ts:81`）在未配置 `NANO_E2E_LOGICAL_CLOCK_SOCKET` 或 `IM_PUBLIC_MODE=1` 时不挂载且不新增任何 HTTP 服务，严守 `AGENTS.md` 红线。
     - 核查 `packages/personal-assistant/assets/skills/{nano-ongoing-work,nano-proactive-care}/SKILL.md` 真实路径与现行正文（如 `nano-ongoing-work` 第 28 行 `.nanoassistant/ongoing-work.md` 与第 65 行强制 `waiting` 关联 `Schedule`），`design.md:13` 的归属包修正与英文重构要点准确命中真实文件。
  2. **跨进程启动校验与逻辑时钟存储不变量核查（`codebase-design`）**：
     - 逐行对照 `apps/node/src/main.ts:63-66` 与 `@deepseek-ai/dsh-schedule/lib/index.js:1599-1626, 1678-1690` 及 5 关卡推进时序，发现 2 项需在实施前收口的 `WARNING`（`R10-W1`、`R10-W2`）。

### 历史问题闭环

- **`R1`–`R9` 全部历史条目**：维持 `closed`（及 `superseded by Q8/Q9`）。

### Issues

#### `R10-W1` [WARNING] `apps/node/src/main.ts:63-66` 启动期静态能力依赖校验未适配角色作用域与存量关停 `task_graph` 的 PA 升级兼容

- **位置**：
  - `docs/changes/feat-785-pa-proactivity/design.md:11, 14, 37, 111-112, 164, 340`
  - `apps/node/src/main.ts:63-66`、`packages/product-contracts/src/capabilities.ts:28-40, 88-109`
- **证据**：`apps/node/src/main.ts:63-66` 在节点启动早期遍历所有持久化的 `config.agents` 执行硬拦截：`const invalid = validateCapabilities(agent, { features: featureDependencies.filter(feature => feature.key !== 'dreaming') }); if (invalid.length) throw new Error(...)`。引入 `proactive_planning`（`roles: ['personal'], default_on: true, requires: { features: ['task_graph'], tools: ['task_graph'] }`）后存在两处启动崩溃隐患：
  1. `main.ts:65` 直接传入全局 `featureDependencies` 而未按 `definitionsForRole(Boolean(agent.personal_agent))` 过滤，若某普通非 PA Agent 曾关闭 `task_graph`，启动校验会误报 `task_graph required by proactive_planning` 直接崩进程；
  2. 若存量 PA 在升级前已显式关闭 `task_graph: false`（或 `tool_allowlist` 移除了 `task_graph`）且旧 `gateway.yaml` 中尚未写入 `proactive_planning` 键，`effectiveFeatures` 将 `proactive_planning` 默认置为 `true` 同样会触发 `main.ts:65` 启动抛错（这正是第 64–65 行当年专门过滤 `dreaming` 的同一类存量升级兼容问题）。
- **影响**：含自定义关闭 `task_graph` 的普通 Agent 或存量 PA 节点在升级启动阶段直接报错退出。
- **建议方向**：在 `design.md`（§涉及范围 `capabilities.ts` / `apps/node/src/main.ts` 与 §接口与数据流 1）明确：① `apps/node/src/main.ts:65` 使用 `definitionsForRole(Boolean(agent.personal_agent))`；② 对未显式配置 `proactive_planning` 但已显式禁用 `task_graph` 特性或工具的存量 PA 配置，`effectiveFeatures` 不暗中强开 `proactive_planning`（或在启动静态校验中与 `dreaming` 一致兼容放行并降级为未开启）。

#### `R10-W2` [WARNING] 逻辑时钟手动推进 `scheduleDomain` 须同步维护 `lastDelivery`/`deliveryHistory` 严格不变量，且验收剧本第 3 关对照夜不可单跳越过 `03:00–06:00` 窗口

- **位置**：
  - `docs/changes/feat-785-pa-proactivity/design.md:14, 250-252, 258, 353, 362`
  - `packages/dsh-integration/node_modules/@deepseek-ai/dsh-schedule/lib/index.js:1599-1626, 1678-1690`
- **证据**：
  1. **`scheduleDomain` Zod 严格一致性校验（`dsh-schedule/lib/index.js:1678-1689`）**：`@deepseek-ai/dsh-schedule` 的 `scheduleDomain` 表 schema 定义了 `.strict().refine(...)` 强约束——凡带有 `deliveryHistory` 的任务，其 `deliveryHistory.records.at(-1)` 的 `(scheduledAt, deliveredAt, messageId)` **必须与 `lastDelivery` 逐字段严格相等**，否则重挂 `ScheduleService` 打开存储域时会直接抛出 `ScheduleLogError` / Zod 异常导致整个 Agent 定时服务不可用。`design.md:250` 目前仅写明推进时更新 `status: "inactive"` 或 `nextScheduledAt`，必须明确按 `deliveredAt = new Date(nowMs).toISOString()` 与投递 `message.id` 同步写入配套的 `lastDelivery` 与 `deliveryHistory` 收据（同时兼容同一会话多条到期周期任务合并投递一条 `renderRecurringReminderBatchFraming` 的原生规则）。
  2. **第 3 关②“无干货空转夜”若一次跳至 `09:30` 会跳过 `proactive_nightly` 造成假通过（`design.md:258`）**：按 `design.md:106` 契约，`proactive_nightly` 仅在本地 `03:00–06:00` 窗口内触发（越过 `06:00` 视作白天开盖不补跑筹划）。若 `verify_pa_proactivity_24h.py` 在第 3 关②直接将逻辑时钟一步推过 `03:00–09:30` 落到 `09:30`，`proactive-coordinator` 因当前时间不在 `03:00–06:00` 内压根不会调用 `proactive_nightly`，“不创建一次性早报 `schedule`”将在模型根本未参与判断的情况下假阳性通过，失去 `Q10` 验证模型克制分寸的意义。
- **影响**：周期任务二次推进或重挂 `ScheduleService` 时存储域校验崩溃；第 3 关负向克制验收可能因一步跳过凌晨窗口而漏测真实的 `proactive_nightly` 模型决策。
- **建议方向**：① 在 `design.md:250` 补充 `CronOwners` 逻辑时钟投递时同步按原生格式更新 `lastDelivery` 与 `deliveryHistory` 收据以通过 `scheduleDomain` `.refine()` 校验；② 在 `design.md:258` 明确第 3 关②分步停靠 `03:05`（`Dreaming`）→ `03:15`（断言 `proactive_nightly` **已实际运行完成一轮**，且面对纯日常寒暄自主保持 `0` 新 `proposed` 卡与 `0` 一次性早报 `schedule`）→ `09:30`（断言早间 `0` 唤醒与 `0` 外发空早报）。

### Recommendations

无。

### Author Resolutions

- **`R10-W1` — `accepted`**：核实完全属实（`apps/node/src/main.ts:63-66` 直接传入全局 `featureDependencies` 且未处理存量关停 `task_graph` 的旧 PA 配置）。已在 `design.md`（§涉及范围 `apps/node/src/main.ts`、§接口与数据流 1、§Milestones `M1 [worker]` ②）明确：`validateCapabilities` 缺省按 `Boolean(draft.personal_agent)` 取 `definitionsForRole`，对未显式写入 `proactive_planning` 键但已显式禁用 `task_graph` 特性或工具的存量 PA 自动降级缺省 `proactive_planning` 为 `false`，且 `apps/node/src/main.ts` 启动期校验同步按角色过滤并兼容未显式声明的新特性。
- **`R10-W2` — `accepted`**：核实两处细节均完全属实（`@deepseek-ai/dsh-schedule/lib/index.js:1678-1689` `scheduleDomain` Zod `.strict().refine()` 要求 `lastDelivery` 与 `deliveryHistory.records.at(-1)` 严格一致；单跳至 `09:30` 会越过 `03:00–06:00` 窗口跳过 `proactive_nightly`）。已在 `design.md`（§涉及范围 `cron-owners.ts`、§接口与数据流 5.A/5.B、§Runbook、§Milestones `M1 [worker]` ③）补齐：①逻辑时钟投递到期任务时原子同步写入匹配的 `lastDelivery` 与 `deliveryHistory.records` 末尾收据（兼容多条周期任务单消息合并收据）以通过重挂校验；②第 3 关②分步停靠 `23:15` → `03:05` → `03:15`（经 `llm_logs` 断言 `proactive_nightly` 已实际运行完成一轮且自主保持 `0` 新卡、`0` 一次性闹钟）→ `09:30`（早间 `0` 唤醒）。

---

## Round 11

### Metadata

- **reviewer**: `change-design-reviewer` (same independent subagent instance as Rounds 1–10, integrating `codebase-design`, `agent-context-review`, `frontend-experience-review`)
- **target**: `docs/changes/feat-785-pa-proactivity` (`design.md`)
- **review_mode**: `closure`
- **mode_reason**: 本轮仅针对 Round 10 的 `R10-W1` 与 `R10-W2` 在 `design.md` 内完成闭环收敛，未扩大核心边界或改动其他契约文件，按规则采用 `closure` 闭环复审。
- **retained_from**: `Round 4, Round 5, Round 6, Round 7, Round 8, Round 9, Round 10`（`spec.md`、6 份 `specs/` delta-spec、`prototype.html` 及前序轮次已核实的全部跨包架构、运行时边界与体验设计沿用既有审查证据）。
- **started_at**: `2026-11-26T01:16:49+09:00`
- **completed_at**: `2026-11-26T01:18:10+09:00`
- **duration**: `1m 21s`

### Verdict

**Approved** — `0 CRITICAL / 0 WARNING`

### Coverage 与证据

- **`retained_from: Round 4..Round 10`**：`spec.md`、全部 6 份 `specs/` delta-spec 与 `prototype.html` 维持前序轮次审查证据。
- **本轮闭环项与局部一致性核查（`closure`）**：
  1. **启动期角色隔离与存量 PA 升级兼容（`R10-W1`）**：核查 `design.md:14, 164, 362` 对照 `apps/node/src/main.ts:63-66` 与 `packages/product-contracts/src/capabilities.ts:88-109`，`validateCapabilities` 在未传 `catalog.features` 时自动按 `Boolean(draft.personal_agent)` 限定角色定义集；对未显式持久化 `proactive_planning` 键但已显式禁用 `task_graph` 特性或工具的存量 PA 自动降级缺省 `proactive_planning` 为 `false`，且 `apps/node/src/main.ts` 启动校验同步角色隔离并兼容放行未显式声明的新特性，`M1 [worker]` ② 已补充对应单测门禁。
  2. **`scheduleDomain` 收据不变量与第 3 关分步克制验证（`R10-W2`）**：核查 `design.md:14, 250, 258, 353, 362` 对照 `@deepseek-ai/dsh-schedule/lib/index.js:1599-1626, 1678-1689`，`CronOwners` 逻辑时钟投递时构造 `receipt = { scheduledAt, deliveredAt: new Date(nowMs).toISOString(), messageId: message.id }` 原子同步写入 `lastDelivery` 与 `deliveryHistory.records` 末尾（兼容多周期任务合并单消息收据），严格满足重挂 `ScheduleService` 的 Zod `.strict().refine()` 校验；第 3 关②无干货空转夜明确分步停靠 `23:15` → `03:05` → `03:15`（经 `llm_logs` 断言 `proactive_nightly` 实际运行完成一轮且自主保持 `0` 新卡、`0` 一次性早报闹钟）→ `09:30`（早间 `0` 唤醒），消除单跳越窗假阳性。

### 历史问题闭环

- **`R10-W1`** — **Author Resolution**: `accepted` → **本轮核实**: `design.md:14, 164, 362` 完整闭环 — **`closed`**。
- **`R10-W2`** — **Author Resolution**: `accepted` → **本轮核实**: `design.md:14, 250, 258, 353, 362` 完整闭环 — **`closed`**。
- **`R1`–`R9` 全部历史条目**：维持 `closed`（及 `superseded by Q8/Q9`）。

### Issues

无（`0 CRITICAL / 0 WARNING`）。

### Recommendations

无。
