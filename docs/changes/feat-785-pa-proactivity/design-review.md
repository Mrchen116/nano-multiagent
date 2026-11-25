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
