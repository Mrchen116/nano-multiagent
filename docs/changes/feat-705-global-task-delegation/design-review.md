# feat-705 设计审查

## Round 1

### Metadata

- reviewer_target: `/root/feat705_design_review`，独立 reviewer；不是受审文档作者。
- review_mode: `full`
- mode_reason: 首轮 Gate 2；覆盖完整当前阶段需求、技术设计、两个 Gateway delta 与单阶段 milestone，并由同一 reviewer 执行 Agent Context Review / Design Review。
- started_at: `2026-11-03T17:01:00+08:00`（本轮首个显式时钟记录；初读与 checkout 核实已开始）。
- completed_at: `2026-11-03T17:05:39+08:00`
- duration: `0:04:39`（从上述显式时钟记录计算）。
- baseline: 实际 checkout `/Users/czj/Repos/nano-multiagent`，branch `codex/bugfix-704-performance`；HEAD `9762ad3b44ca3cb2eebd6f2025fe8f169a544de3`。
- 受审冻结材料：本目录 `spec.md`、`design.md`、`specs/gateway/global-agent.md`、`specs/gateway/personal-agent.md`、`M1-global-delegation/.gitkeep`。
- 工作目录边界：已有 IM Work/轨迹、Node/DSH 轨迹、前端 Agent 设置的 dirty 修改，以及 `.pnpm-store/` 和 research 未跟踪文件均来自其他工作；未改动、未作为本 unit 的实现成果。受审 unit 目前仅有文档，未将其他任务的实现纳入本轮验收。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

整项单一执行责任、日常主会话处理、唯一公开沟通、原执行者更正与接续的主路径可以复用现有运行时；没有发现需新增 Task 联动、新工具、权限扩展或第二套执行循环的理由。停止范围的设计还遗漏可运行的一次性后台 fork 分支，需在实施前收口。该结论是设计判断，不是模型行为或产品旅程已通过。

### Coverage 与证据

#### 用户范围、需求与契约

1. 已核 `spec.md` 的当前阶段、澄清记录、五组 Requirement / 十个 Scenario、范围与后续 Task 记录。最新决定明确暂缓 Task 改造；设计没有把自动建 Task、执行者绑定、自动续推或流转事件作为前置。保留 Task driver 现状及其可能唤醒根的限制，与当前范围一致。
2. 完整独立交办交给一个一级 continuable 执行者，自主进一步分工；根处理日常、新独立输入、父级独有资料、必要决定、交付覆盖核对及公开发送。结果不足交回原执行者，不替它调查和常规测试。该职责区别符合用户约束，不是只把多个研究者换一个名字。
3. 已逐项对照 canonical `docs/specs/gateway/global-agent.md` 的旧统筹/委派 Requirement 与其四个 Scenario。Global delta 以 REMOVED + ADDED 替换该完整 Requirement，保留日常直接处理、多事项独立、可见委派及外部 IM 通信不自动授予派工权限；其他 Inbox、发送前复核、公开交付、`/stop` 等 Requirement 未被删除。新增聊天内停止协调与既有命令强停是不同入口，设计明确不改变后者。
4. PA delta 的 canonical target 正确，MODIFIED 保留现有“主人请求与普通工具”Scenario，增加遵循 Global 同一分工；其他主人身份、participant/observer、披露和配置契约继续有效。未要求回写旧 Persona 或覆盖用户同名 Skill。
5. 没有新 UI 或平台交互，本轮不需要前端原型；用户能辨认事项及下级仍以已有 Work/轨迹为产品验收对象，不据其他任务的前端 dirty 修改推断已实现。

#### 实际装配、权限与架构

- `packages/dsh-integration/src/client.ts:18-29`：`prepareProfile` 使用锁定安装的 base 与 Nano bundle，原生 maxDepth 保持 2。`packages/dsh-integration/cordis.patch.yml` 未替换委派运行时。安装的 `@deepseek-ai/dsh-base@0.2.1-alpha.1/cordis.patch.yml:362-388` 实际加载控制/发现插件，`subagent` 为 spawn + continuable，`subagent_fork` 为 fork + one-shot。不是仅根据工具名称推断模式。
- `packages/dsh-integration/src/index.ts:252-269`：实际 `agent/created` 路径从配置/历史取得当前 config，调用 `attachAgent` 后装配审批、模型及 history。`agent-config.ts:120-162` 证明 Global 产品工具不装在共享 preset，普通 child 不装 Persona、调用 child guidance；根与 fork 走 Global / Persona 路径。因此设计把核心分工放在这些现有角色装配位置，并保留 SingleThread 分支，是有真实落点的最小改动。
- `child-role.ts:17-40` 保留 fork 前缀，并在初次委派输入尾部解释内部身份。设计要求根规则自身适用范围明确，核实际 fork 请求而非靠尾提示宣称优先级；没有要求修改继承 Schema、篡改历史或扩展 fork 权限。
- `product-bridge.ts:12-28` 由可信 root binding 派生产品身份，限制主人代发；`packages/personal-assistant/src/global-agent.ts:473-476` 独立拒绝 child 的 Inbox / conversations / 公开 send 等产品调用。角色提示不是唯一权限检查。普通工具本身不是完整网络隔离，设计也没有声称新增硬隔离。
- `apps/im-server/src/personal-agent-defaults.ts` 与随包 `nano-ongoing-work`、`nano-proactive-care` 的现状确实存在“较长事项可委派”与直接执行并列文案；设计同步这些方法并保留来源核对、观察不等于授权、用户选择与 SingleThread 行为，覆盖了真实组合冲突面。
- 职责分配合理：DSH 继续拥有 child 身份、目录、消息和执行状态；Nano integration 解释产品角色与产品权限；PA 宿主维护来源与交付；已有笔记只承载必要恢复事实。复用这些能力比新增工单/账本/调度器更符合当前范围，未发现无实际收益的新抽象。

#### 原生工具、返回、接续与恢复

本轮直接读取安装锁定包的模型定义、output.render 与实现；以下 package locator 均指 `0.2.1-alpha.1`，不依赖远端最新文档，也未修改依赖。

- `@deepseek-ai/dsh-tool-subagent/lib/index.js` 的工具定义及 execute：continuable 默认为后台，显式 `run_in_background:true` 正确；内部 `{kind:"continuable",subagentId}` render 为 `started subagent <id>`，不是内部 JSON。设计取得真实 ID 后结束根轮次、继续接新输入，不要求 wait/list 轮询，匹配实际能力。
- `@deepseek-ai/dsh-tool-subagent-control/lib/index.js`：内部 send schema 为 `agent_id/message`，受理返回不含 child 答案；interrupt 立即返回 accepted，并明确下级继续运行。`@deepseek-ai/dsh-subagent/lib/types/continuation.js:192-218,242-278,334-382` 支持直接 child 冷恢复、忙时 steering 与同一身份接续，不允许随意跨深层发送。
- `@deepseek-ai/dsh-subagent/lib/types/continuation-messages.js:31-49,58-105` 实际把父 ID 与完整回传要求加入初始任务，随后按结束原因发 settlement；设计让 continuable child 内部回传一次完整结果、fork 走 completion，根不因随后通知重复交付，符合两条真实返回路径。
- `owned-sessions.ts:42-138` 通过可信产品 root、parent catalog、descriptor、cwd/preset/depth 验证管理会话，普通可接续 child 可恢复；不可恢复 one-shot 不被假冒为可接续。`history.ts::configuration` 与 `index.ts` / `attachAgent` 说明保存配置和当前角色代码是不同来源。设计要求同 DSH home、同 root/child ID 的旧角色保存→候选恢复→下一 provider 请求验证，不能用新建预览替代，必要的最窄装配修正也已纳入 M1。
- `packages/dsh-integration/tests/global-child-tools.test.ts` 已有真实 RuntimeClient + 受控 llm hook 的 root/ordinary child/fork、二级 child、Global/PA/SingleThread 及 child 冷恢复 seam，证明设计指定的验证入口可实现；本轮只读了现有测试，没有运行，也不将 stub 算作自主模型行为。
- 停止与 one-shot 后代的缺口见 R1-W1；其余已明确受理与结束不同、B 不受影响、晚到成果不恢复授权。

#### Agent Context Design Review

- Consumer / Surface 已覆盖 Global 根 System Prompt、普通 child、fork 继承/尾提示、PA 默认 Persona、Skill 发现/加载、内部工具参数与模型结果、Inbox 来源及跨轮笔记/历史。关键职责常驻的理由成立：禁用 Skill 时根仍需知道整项职责；具体方法按需，避免把所有恢复操作常驻。
- 必填信息有来源：原话与真实来源经 Inbox/conversations，内部 ID 经工具实际 render，深层 parent/depth 经已有目录；宿主身份仍由可信绑定派生，不让模型填 owner 或自行推断真人授权。
- Before/After 说明了分工行为变化；方法未将观察承诺升级成给 PA 的新交办。更正、停止、原目标和真实回执被保留为恢复事实；旧笔记/摘要不覆盖当前要求，正式 Memory 不承载临时 child ID。
- 普通 child、fork、SingleThread、旧 Persona、同名/禁用 Skill、恢复的最终请求都进入 M1 退出标准。不能据静态角色文字确认模型会遵守；设计已要求自然完整目标的真实 Global 与 PA 旅程，区分实际请求、受控 fixture 和自主行为。当前无产品实现、测试运行或真实模型结果，不将这些必要的实施期证据缺失单独制造为设计缺陷。

#### Milestone、验证与部署

M1 骨架存在且仅 `.gitkeep`；没有提前宣称里程碑完成。单阶段足以覆盖本次有界改动，退出标准包含十个 Scenario、装配/权限、后台接续、冷恢复、真实来源与回执、Task/前端不变、窄回归及 required CI。`docs/development/worktree-runtime.md:43-64` 的 daily 确实提供普通 Global 与 PA、隔离主人、合成资料和模型/审核配置，设计 runbook 可以执行；ready 未被当作验收通过。无一次性数据迁移，不需要 deployment-prompt；本轮未启动、部署、重启或发送生产探针。

### 历史问题闭环

首轮，无历史 findings 或 Author Resolutions。

### Issues

#### R1-W1 — 停止流程未覆盖允许的 one-shot 后代，continuable 目录为空不能证明整支停止

- severity: **WARNING**
- evidence_status: **CONFIRMED**（确定性接口与设计覆盖缺口）；模型实际是否选择后台 fork、是否误报已停止尚未运行确认。
- 位置：`design.md:25-33` 的复用工具事实、`:66` 停止决策、`:103-105` 组合验证与 `:141` M1 的“下级停止”；关联 spec“更正或停止一个独立事项”。
- Context Surface：原生发现/控制工具的 Schema、render 与父级/执行者停止指导。
- expected：执行者可以自行选用已有下级能力，用户停止 A 时，根应理解哪些下级能被发现/中断、哪些仍由 A 的执行者持有并停止；无法确认的范围要明确保留，不能只凭可接续分支 inactive 推断整个事项停止。
- observed：设计允许 fork 并保留其默认一次性能力，但停止方法只说明沿 `descendants` 查询和原生 interrupt 处理对应执行者及后代，未说明目录过滤 one-shot、interrupt 对其不生效，以及一次性后台 job 的持有者/停止协调顺序。泛称“工具不足如实表达”没有让模型知道该限制在管理工具全部启用时仍存在。
- 直接证据：锁定 base patch `:383-388` 将 fork 配为 one-shot；`@deepseek-ai/dsh-tool-subagent-control/lib/types/list-agents.js:23-31` 的 `project` 对 `entry.mode !== 'continuable'` 返回 undefined（递归目录遍历也过滤结果）；`@deepseek-ai/dsh-subagent/lib/types/continuation-activation.js:151-180` 只查 continuable resident activation，找不到直接返回；控制工具仍给 accepted。`@deepseek-ai/dsh-tool-subagent/lib/index.js:538-553` 的后台 one-shot 使用 jobs.start、独立 AbortController 和 jobId，不走这套 continuable 控制身份。
- 成立场景与影响：A 执行者在自主分工时启动后台 one-shot fork。根收到“停止 A”，先转发停止再立即 interrupt A；转发仅证明受理，不保证 A 已消费并清理自己持有的 job。根用 descendants 只能看到 continuable 后代，全部 inactive 后，后台 one-shot 仍可能运行。当前验证若只造 continuable 二级 child，会漏掉此分支，造成用户要求停止后仍执行，或无法兑现设计承诺的停止范围。不是声称所有 fork 都会泄漏：前台 fork 的取消/清理可能沿其待收集调用传播，后台 job 与其不同。
- 建议：在现有设计内明确 continuable 与 one-shot/后台 job 的发现和控制边界；复用已有 job 控制与执行者持有的真实 ID 时，说明由谁协调、何时确认、何时才中断持有者，避免让“send 已受理”替代清理完成。若当前配置或能力不能处理该类下级，明确不确认整支已停止及真实尚未停止范围，不新增工具、权限或自动级联。M1 加一个混合 continuable + 后台 one-shot 下级的确定性停止 fixture，验证不会以过滤后的目录冒充整树状态；不要求真实模型为了验收主动开 fork。
- 作者需要收口的决定：选择已有能力可兑现的 one-shot 停止协调路径，或明确其不能确认停止时的产品边界，并使角色/Skill 指导与验证一致。无需借此恢复暂缓的 Task 范围。

### Recommendations

无额外可选建议。本轮只保留上面的实质缺口，避免扩展实现范围。

### 未验证与交接

本轮为文档审查及只读源码/锁定依赖取证，没有运行候选代码、测试或真实模型；未验证实际 provider 装配、自主分工、旧会话升级行为和产品交付，这些是 M1 已列出的实施退出证据。没有启动服务或留下运行资源。仅新增本报告，不修改其他受审文件、不提交。后续复审应核作者对 R1-W1 的实际修订及相应 delta；其余范围可在无实质变化时 retained，不需重做全部审查。

### Author Resolutions

- R1-W1 — **accepted**。锁定包 continuation-activation.js:155-180 只中断 continuable activation，且 keepInbox:true；list-agents 过滤 one-shot。后台 one-shot 的 job 只由启动者管理，job_kill 也只确认 cancellation-requested。设计已区分 continuable、前台 one-shot 与后台 job：由原持有者按真实 jobId 做停止清理，必要时在中断终结后发送仅清理控制，不恢复原业务；取消请求、空目录和 inactive 不作为整树已停止证据，未确认范围需明确回报。M1/Runbook 增混合下级取消、工具不足及真实终止／未知证据。未增加工具、权限或 Task 调度。
- 用户新增 fork 默认值决定已同步到 spec、design 和能力 delta：采用 Goal 同款 opt-in，统一默认关闭但保留手动开启／撤回和旧名单，不是硬禁止。这是实质变化，后续独立 reviewer 按真实差异选择审查模式；R1 原结论与正文保留。


## Round 2

### Metadata

- reviewer_target: `/root/feat705_design_review`，沿用独立 reviewer，与设计作者分离。
- review_mode: `full`
- mode_reason: 不止关闭旧问题。新增用户 Q4、跨 Global/PA/SingleThread 的工具默认规则、能力 delta 和 M1 范围，涉及需求与共享工具选择接口；依 skill 扩为 full。对未变源码与原需求使用 Round 1 的已核证据，不重复调查未受影响链路。
- started_at: `2026-11-03T17:13:38+08:00`
- completed_at: `2026-11-03T17:16:26+08:00`
- duration: `0:02:48`
- baseline: 同一 checkout / `codex/bugfix-704-performance` / HEAD `9762ad3b44ca3cb2eebd6f2025fe8f169a544de3`；其他任务 dirty 状态继续保留。审查 spec、design、三个 Gateway delta、M1 skeleton 及 R1 Author Resolutions 的本轮冻结状态。产品仍未实施。
- Agent Context mode: Design Review，与本轮设计审查同报告。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

fork 的统一 opt-in 设计已覆盖真实默认值入口、显式名单、撤回/新增时机、Goal 分离与验证；没有发现额外阻断。R1-W1 已接受并修正大部分控制边界，但停止清理还依赖原生 job_kill 实际会抑制的结束通知，需要补齐终止结果收集方法。

### Coverage 与证据

#### 全范围核对及 retained 证据

- 已复读当前 spec/design 与新增能力 delta，并复核 Q4、十三个验收 Scenario、范围、runbook 与 M1。原来的完整事项单一执行者、日常根处理、唯一用户沟通、同执行者接续、根不重复调查均保持。Task 的自动建图、绑定、续推、状态和联动仍明确暂缓，未被本轮默认值变化带回。
- `retained_from: Round 1`：原有 Global/PA canonical 与两个 delta 的覆盖和归并目标；根/普通 child/fork/SingleThread 的实际装配落点；ProductBridge 与 Global 主入口权限；PA 默认 Persona 与两个随包 Skill；实际 ID、continuable 回传/settlement、冷恢复和旧会话升级取证；无新账本、调度层、循环及无数据迁移的架构判断。理由：上述源码未受本轮目标修订，三份原受审文档对应部分未发生改变这些结论的实质变化；本轮补入的 opt-in 与停止链路在下文单独核查。保留用户 Persona/Skill 与实际 provider 请求验证要求没有减弱。
- M1 仍为一个有界阶段，新增的 Node 默认值和 integration 默认筛选属于同一 fork 用户选择规则；无需新增 Feature、前端布局、服务或数据模型。角色分工由 integration 持有，工具目录默认由 Node 投影，实际执行约束继续由现有 ToolSelection 承担，比另建 root-only 禁用机制少一套状态且符合 Q4。

#### fork 统一默认关闭：真实装配和生命周期

1. `apps/node/src/capabilities.ts::projectCapabilities` 的 tools 映射（当前第 49-54 行附近）直接给 default_on，现有 Goal 三工具在同一默认排除表内。设计在此排除 subagent_fork 可改变所有消费该目录的新建默认勾选，不是只改 Prompt。
2. `packages/dsh-integration/src/capabilities.ts:15-33,58-81`：`goalTools` 目前仅三项；`selection` 在 `toolAllowlist===undefined` 时排除 Goal，显式名单则按当前选择与既有内部/已安装 workspace 有限增量处理；`refresh` 生成实际限制层。将 fork 放入独立默认关闭集合、保持 Goal 专属数组不变，可以同时覆盖预览与实际执行，并避免 fork 开启触发 `agent-config.ts:136` 的 Goal 指导注入。设计写明两处默认值与 selection/refresh，改动位置足以指导实施。
3. `packages/product-contracts/src/capabilities.ts:53-58` 的 fixedTools 包含 Global root subagent，不含 subagent_fork。设计不改固定集合和普通 subagent，因此不会因为关闭 fork 破坏主路径。内部 child 继续继承现有工具限制，没有默认自动增加 fork。
4. `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx:49-54,469-487` 用 default_on 初始化可选工具，保留用户编辑；`apps/im-server/src/personal-agent.ts:452-453` 用目录 default_on 生成 PA 工具名单。既有设置保存 explicit allowlist，无需新 UI 布局或按钮即可承接默认未选、用户手动选中/撤回。当前没有候选实现或渲染，本轮仅确认设计复用路径，实际默认勾选与保存必须按 runbook 在已有界面核验。
5. `packages/dsh-integration/src/index.ts:654-680` 的 configuration.apply 先 restrictSelection、后 whenIdle / setConfiguration；`agent-config.ts:171-184` 从当前有效集计算撤回。新默认筛选必须让无显式名单的收缩也从“fork 未启用”计算，设计指定同类 seam 测忙时撤回且新增不提前开放，覆盖了该重要组合。没有用更新配置中“包含 fork”伪造提前启用。
6. 已读 `packages/dsh-integration/tests/goal-opt-in.test.ts`：现有真实 RuntimeClient + 受控模型 seam 可核默认、显式单选、强制调用失败、实际请求和忙时新增/撤回；设计复用同类测试而非镜像字符串是可实现的。旧显式名单保留和冷恢复也在 M1；新默认不是授权迁移，不回写 Persona 或历史选择。
7. 新 `specs/gateway/agent-capabilities.md` ADDED 的 target 正确，与 canonical `docs/specs/gateway/agent-capabilities.md:846-855` Goal Requirement 和普通工具设置/白名单规则一致，不删除未改变 Scenario。Global/PA 两个 delta 继续只管职责，不重复完整工具默认契约。

#### 停止修订及 Agent Context 组合

- 已接受 R1 对 continuable 目录与 one-shot 的区分：设计明确 list 过滤 one-shot、interrupt 对其是 no-op、keepInbox:true、前台调用 signal 与后台独立 job 不同；更正/停止沿原持有者，不让根跨 owner 杀 job。必要时等中断终结后向同一原执行者发“仅清理、不恢复业务”控制输入；这不是新业务执行者，也没有扩大权限。
- `@deepseek-ai/dsh-tool-jobs@0.2.1-alpha.1/lib/index.js:347-365,367-412` 直接核实 job_list 无参数、job_kill 的 job_id/reason，以及 list/kill/get 都带 `exec.agent?.id`；返回 cancellation-requested / already-finished，设计没有冒充业务或终止已完成。
- 受影响 Context 已包含默认工具 schema、预览、强制执行限制、根与 child 指导、fork 前缀、保存配置/恢复、停止消息/回执和 late result。consumer 应知道能力未开启与动作被拒的区别，显式启用不增加产品聊天权限，停止清理不恢复原授权目标；设计已给这些语义和实际请求验证。
- mixed fixture 覆盖 continuable、前台 one-shot、后台 one-shot，工具缺失和无法确认范围；真实 Global/PA 自然目标任务不诱导开 fork。R1 的真实模型、版本/配置/session/locator、旧会话下一请求与非生产验收要求继续有效。唯一尚未闭环点为主动取消 job 后没有结束通知（下方 R2-W1）。
- 无一次性迁移或部署提示词需求，runbook 不要求生产探针。十三个 Scenario、fork 设置/旧名单、真实 provider/原生通信及回执都在退出标准；本轮未跑测试或产品旅程，不能把设计可验证当作验证已通过。

### 历史问题闭环

- **R1-W1：still-open（范围已缩小）**。
  - Author Resolution：accepted；区分执行类别、由 owner 取消后台 job、必要时只做清理接续、未确认范围明确回报，加入混合 fixture。
  - 本轮证据：上述目录、activation 和 job owner/kill 定义支持这些修订，原“只靠 list/interrupt 覆盖所有后代”的缺口已修正。
  - 未关闭原因：实际 job kill 会抑制相应 settled 通知，当前清理后的终止收集仍无兑现路径，见 R2-W1。计数为本轮一个 WARNING，不重复计 R1-W1。

### Issues

#### R2-W1 — 主动 job_kill 的结束通知被原生抑制，不能靠该通知收集停止结果

- severity: **WARNING**
- evidence_status: **CONFIRMED**（锁定运行时的确定性通知与工具定义）；尚未运行模型或混合 fixture。
- 位置：`design.md`“更正、停止和接续按执行类别协调”第二段的“正常取消后的结束通知和内部回报触发后续处理”，以及 M1/Runbook 混合取消验证；承接 R1-W1。
- Context Surface：job_kill 模型结果、后台结束通知、仅清理控制输入与原执行者回报。
- expected：取消受理后，原持有者有可执行方式拿到真实终止结果，并将停止范围交回根；不能没有通知却等待通知，也不能把受理当已终止。
- observed：设计要求 owner 用 job_kill 请求取消，然后依靠正常取消后的结束通知及回报触发后续；没有指定主动取消后由谁调用可用的有界收集工具。
- 直接证据：锁定 `@deepseek-ai/dsh-tool-jobs/lib/index.js:262-269` 的 `killedByModel` 集合在 settled handler 中被消费并直接 return；`:403-407` 在 job_kill 返回 requested 时加入该 ID。因此主动 model job_kill 的 settled notice 被刻意抑制，不能作为恢复触发。相同文件 `:298-344` 已提供 `job_output({job_id,wait:true,timeout_ms})`，timeout 被配置封顶，超时不停止 job；这是可复用的原生收集路径，无需新增工具。
- 成立机制与影响：原执行者收到只清理控制输入，调用 job_kill 后只得到 cancellation-requested 并结束。job 随后真实终止，但通知 handler 跳过它。根最多得到“请求取消”而没有最终范围证据；若等待该通知，清理闭环无法发生，可能永久停在未知，或为宣称完成而错误提升受理语义。设计已允许诚实未知，因此不是断言一定误报，但“能在能力齐备时取得真实取消结果”的主成功分支尚未收口。
- 建议：让实际 owner 在同一清理轮次用已有 job_output 的有界等待收集 kill 后终止结果（或明确另一条实际存在的收集路径），区分 terminal 与超时/错误并向父级回报。收集受阻时按既定规则列出未确认范围，不能例行轮询/无条件续跑。将“主动 kill 不发 settled notice”的确定性条件纳入 mixed fixture，验证成功终止与有界未知均能正确收尾。无需改上游通知、权限、工具或 Task。

### Recommendations

无额外可选建议。

### 未验证与交接

仅追加本 Round，未改 R1 或 Author Resolutions，未修改 spec/design/delta/代码、未提交、未启动服务。源码/依赖证据可支持本轮设计缺口，不能证明候选实现或自主模型行为。后续只需作者收口 R2-W1 后按真实 delta 复验；没有发现需要重开 Task 设计或扩大架构范围的理由。

### Author Resolutions

- R2-W1 — **accepted**。独立核实原生 job_output 参数和执行路径，wait:true 的 timeout_ms 被已有配置封顶，超时不停止 job。设计取消了对主动 job_kill 后 settled notice 的依赖，改为真实 owner 在同一清理轮次做一次有界 job_output 收集，区分 terminal 与 running／超时／错误／不可用，并内部回报未确认范围。不循环、不新增通知或工具，不恢复业务。混合 fixture 明确覆盖主动 kill 抑制通知以及 terminal、超时两个出口；仅修订原停止指导与验证，Task 仍暂缓。


## Round 3

### Metadata

- reviewer_target: `/root/feat705_design_review`，沿用同一独立 reviewer。
- review_mode: `closure`
- mode_reason: 本轮实际变化仅为 R2-W1 对原有停止收尾的局部消歧及相应 fixture 条件；不改变需求、工具接口、owner 权限、fork 默认值或 M1 结构。核历史问题闭环，其他有效范围 retained。
- started_at: `2026-11-03T17:18:26+08:00`
- completed_at: `2026-11-03T17:19:19+08:00`
- duration: `0:00:53`
- baseline: 同一 checkout、HEAD `9762ad3b44ca3cb2eebd6f2025fe8f169a544de3`；只追加本报告，不操作其他任务 dirty 内容。
- Agent Context mode: Design Review / closure，范围为停止消息→job_kill 受理→同 owner 有界 job_output→真实状态解释→内部回报。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

本轮修订补齐主动取消后真实终止结果的取得方式，不依赖已被抑制的结束通知；历史停止范围问题已在设计层关闭。Approved 仅表示当前设计可交实施，不表示模型行为、混合 fixture、旧会话升级或产品旅程已经运行通过。

### Coverage 与证据

- 已读取冻结 `design.md:34-36,73-77`、混合 fixture/runbook 与 M1 关联文字，以及 R2 后的 Author Resolutions。实际修订由真实 job owner 在同一清理轮次调用既有 `job_output({job_id,wait:true,timeout_ms})` 做一次有界终止收集；terminal 才确认对应范围，running/超时/错误/不可用则内部回报未确认范围。没有新增循环、通知、工具、权限或业务恢复。
- 独立复核安装的 `@deepseek-ai/dsh-tool-jobs@0.2.1-alpha.1/lib/index.js:223-229,298-344`：timeout 受原生配置上限约束；`wait:true` 调用 `jobs.wait`，随后 `jobs.read`，两者均带 `exec.agent?.id` 和适用 signal。模型结果 render 含实际 `[status: ...]`，并非只在宿主内部保存 terminal。`:28-46` 的 publicJob/statusLine 保留 status 与可用 detail，因此执行者有可消费的真实结果或错误来决定下一步，不必猜 owner 或内部状态。
- 同文件 `:262-269,403-407` 仍证明主动 kill 的结束通知被抑制。新设计明确不得等待它，改在同一控制轮次收集并内部回报，因此不再出现 kill 受理后靠不存在的通知恢复的缺口。
- 单次有界等待属于停止结果收集，不是例行催进度或无条件续跑；原生超时不会保证停止，新设计在 running/超时出口明确报告未确认，未把状态提升为成功。控制输入只做清理不恢复业务，当前更正/停止仍优先于晚到业务成果。
- 混合 fixture 明确检查主动 kill 不发 settled notice、terminal 与超时/未知两个出口，覆盖了本 finding 的成功与失败机制。所需工具与原生 seam 已存在，验证方式可兑现；本轮没有执行 fixture，不把设计中的要求记为测试通过。
- `retained_from: Round 2`：Q4 与统一 fork opt-in、Node default_on + integration selection/refresh、显式名单/旧选择/忙闲规则、Goal 三项分离、三个 delta 与十三个 Scenario、角色/权限与真实模型验证范围。理由：上述设计内容、本轮需求与 M1 结构未变。
- `retained_from: Round 1`（由 R2 full 复核保留）：完整事项单一执行者、根处理日常/必要协调/唯一交付、普通 child 与 fork 组合、来源/授权/PA Persona 和 Skill 选择、continuable 返回与冷恢复、旧会话实际请求证据、无新增执行循环/数据迁移及隔离 runbook。Task 始终暂缓，当前修订没有扩大边界。

### 历史问题闭环

- **R2-W1 — closed（设计层）**。
  - Author Resolution：accepted；取消对主动 kill 后 settled notice 的依赖，用原 owner 的一次有界 job_output 收集并区分 terminal/未确认，再内部回报。
  - 本轮证据：`design.md:36,75-77` 与上述真实工具 schema、execute、render 一致；mixed fixture 同时守护无通知和两个退出分支。必要能力可被模型取得、理解并执行，没有新增人工授权步骤。
- **R1-W1 — closed（设计层）**。
  - R2 已补 continuable / 前台 one-shot / 后台 job 的类别、目录过滤与中断 no-op、owner 限制和只清理接续；本轮补上该路径最后的终止结果收集。
  - 不用过滤目录、inactive、interrupt accepted 或 cancellation-requested 宣称整支已停止；不可恢复 owner、工具不足或未确认 one-shot 保留具体范围。设计层的能力与限制均已明确，实际实施仍须用已指定的混合 fixture 和适用产品证据验证。

### Issues

无存活 CRITICAL / WARNING。

### Recommendations

无额外可选建议。

### 冻结版本定位

本轮受审文件 SHA-256（用于后续比对，不表示实现验收）：

- `spec.md`: `df70c25147a0c8d0465e6b7871f62bfdc6e95d4503cf43e42319c049a5ac71c1`
- `design.md`: `0ec5197df29044bf046909bec8629f8d8ce2cd2b9610498a69a3e36347454ac6`
- `specs/gateway/global-agent.md`: `60c24feb3c7ffe6fb6c5a33db6af544f01a70f34b1d582463e07461a38bd0bb2`
- `specs/gateway/personal-agent.md`: `7df8c4795d8a7ec6f442cdef313a49a0b10dbdc84fdf4be0bb8ed87f19f42e86`
- `specs/gateway/agent-capabilities.md`: `1f32fab464f4178d911cc7ffe91b2d3b44a34ea46b49d81361862ece1df5b025`
- `M1-global-delegation/.gitkeep`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

### 未验证与交接

未运行候选实现、测试或真实模型，未启动服务、部署或提交。M1 仍需完成实际 provider 请求、模型自主行为、旧会话恢复、工具默认/显式/撤回、混合取消及真实交付证据。仅追加 Round 3，保留全部历史与作者 resolutions；本轮不存在需作者再决定的设计阻塞。


## Round 4

### Metadata

- reviewer_target: `/root/feat705_design_review`，独立 reviewer，非设计作者。
- review_mode: `full`
- mode_reason: 首文档增加一级独立工作能力／二级原生 Context，design 全文重写、能力 delta 重写，影响核心职责、共享工具选择／更新／恢复和 M1 范围；R3 Approved 不能覆盖本次变化，按 full 重新判断。
- started_at: `2026-11-03T17:45:03+08:00`
- completed_at: `2026-11-03T17:49:24+08:00`
- duration: `0:04:21`
- actual_checkout: `/Users/czj/Repos/nano-multiagent`，**main**，HEAD `9762ad3b44ca3cb2eebd6f2025fe8f169a544de3`。派发中所述旧分支不是本轮现场状态；已向主 Agent 告知，不自行切分支或恢复旧 dirty 内容。
- 当前 status：本 unit spec 修改、design/review/delta/M1 未跟踪，以及 `.pnpm-store/`、`:memory:`、research 未跟踪；未操作其他内容。受审材料为本轮 spec、完整 design、三个 delta 与 M1 skeleton，产品尚未实施。
- Agent Context mode: Design Review；覆盖 root／一级／普通二级／fork，及其工具、系统指导、来源、更新与恢复。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

新稿明确将主工具选择与内部工作能力分离，保留原生 preset/lineage，在 Nano 既有装配点按可信角色投影。一级负责完整事项、普通二级不注入产品身份、fork 保留原生继承，三者已区分。真实更新／占用／恢复和权限证据已进入实施范围与退出标准，未发现会使下游实质走偏的未收口设计决定。

该结论不表示实现或真实模型行为已经通过。工具投影、普通二级最终 Context、配置占用及旧会话恢复都须按 M1 验证，不能直接沿用旧测试的共享名单预期。

### Coverage 与证据

#### 用户范围、需求与契约

1. 已读取 spec 的新原话、Q4 后续修订、分层解读及全部 Scenario。完整独立事项仍由一个后台可接续一级负责，根处理日常、必要资料／决定及公开交付，不重复调查；一级自行组织下级。Task 改造持续暂缓，无 Task 绑定、自动续推或新状态链。
2. 主会话 fork 默认关闭但可手动选中，仅恢复原生工具能力；一级使用实际已装载 DSH 工作能力，不继承根普通勾选；普通二级不附加 Nano 身份或一级整项职责。fork 的父前缀继承作为明确例外，不要求通过裁剪 prefix 伪造“无身份”。新建 SingleThread 仅采用已确认的根 fork 默认值，职责和其 child 行为保持。
3. Global delta 继续替换 canonical 旧“统筹并偏向按需委派”整个 Requirement，保留日常、多事项、可见归属及外部 IM 无默认派工权；PA delta 继续保留原 Scenario 并复用 Global。能力 delta 新增分层工具／Context、更新恢复和 root-only fork 规则，其 canonical target 正确。已对照 `docs/specs/gateway/agent-capabilities.md` 的静态工具规则、Goal 独立选择、配置更新、workspace 增量、两层原生委派与权限边界：本阶段明确改变的是 Global 普通内部执行者的共享 allowlist 接线，不将单 Thread 的白名单例外扩成全产品放开。
4. 同一职责分别由 Global/PA 分工契约与能力分层契约承载，未在 Task 创建或调度条目里另建机制。现有固定根能力、Goal 三项独立 opt-in、来源／审批、深度、Skill/扩展选择均明确保留。
5. 用户已排除专门 fork 取消／清理流程；新稿不新增它。聊天内停止仍按既有可用管理机制处理，受理、无法控制与未知范围如实表达，不承诺自动级联整树。没有据历史 R1/R2 再要求被用户排除的功能。

#### 参考仓与锁定公开能力

- 已核参考 checkout `/Users/czj/Repos/opensource-hub/dsh-superagent-prototype` 当前 HEAD 为指定 `6337fc823ce20251c8de8085948165c81aaa701e`。`cordis.patch.yml` 的 Worker 工作工具／指导及下级 `agentPreset: standard`，`sessions.ts:232-266,282-315` 的 Worker 追加业务段／workOnly／下级 limitSubagent，`prompts.ts::promptParts` 和 executor 的原始交办路径，共同支持设计所借鉴的“基础工作层＋Worker 职责、下级不装 Worker 业务 Prompt”；它们不是本仓已实现的 current。
- 本仓安装锁定 `@deepseek-ai/dsh-tool-subagent@0.2.1-alpha.1` 的 Config 不提供参考仓 agentPreset 字段；新稿没有虚构该配置、升级依赖或创建独立 Worker 产品会话。
- `@deepseek-ai/dsh-subagent/lib/types/child-agent.js::childSessionMeta/applyChildComposition` 与 `@deepseek-ai/dsh-agent-preset-registry/lib/types/index.js:274-319`：子 Agent 加入父持有的确切 preset generation，通过 `bindScopeParent` 连接到共享 generation；不是把父 Agent 的每个局部角色注册逐项复制。将根／一级业务职责留在 Agent 局部 scope、共享产品 prompt 按消费者投影，是可由现有公开能力承载的方案，不需要 private import 或运行时 fork。
- base `cordis.patch.yml` 实际含 agent-instructions、原生工具与委派，system-prompt 的 personaPrefix 为空。设计已明确“DSH 默认”仅指当前实际装载能力，不声称已有参考仓 coding Persona，也不恢复宿主禁用的插件管理、workflow 或 web_fetch。

#### 实际装配及角色工具／Context

- `packages/dsh-integration/src/index.ts:252-269` 的 agent/created 经 history/configuration、attachAgent、审批、模型及 history；`agent-config.ts:104-162` 负责共享 preset 与局部 Agent 注册。当前代码确实对普通一级／二级使用相同 identity 和 child guidance；新设计把此作为待改落点，而未把现状误报为已分层。
- `capabilities.ts::ToolSelection.selection/refresh` 当前共享同一产品 toolAllowlist；角色投影在该层及 ConfigurationScopes 收口，可从已装载注册集合取得工作工具，另保留产品排除／Goal／共享选择。无需复制全量静态 DSH 工具名单，也不会为了给一级工作能力而改根有效集合。
- `child-role.ts` 已识别普通 child 与 fork（含初次创建及已持久 descriptor），并为 fork 保留内部尾说明。设计没有按 depth 一概升级所有 child，而是要求结合可信 root binding、origin、父链、fork 及已有特定子任务配置；Workflow/维护的特定范围不作为普通一级放开。
- 已查 `workflow/engine.ts::childConfiguration` 及 `:395-440`：现有 Workflow 经受控 creating 配置和 native toolFilter 保留窄范围；`history.ts::configuration` 保存配置 override；`workflow/state.ts` 与持久 run/budget 记录持有已有执行归属。设计将必要配置／历史接线纳入 M1，并明确保留这些非目标范围，不依赖模型传 role 或公开新增角色字段。
- 普通二级不再注册 identity/child guidance/source 段，仅删 Agent 局部注册尚不足以满足目标：共享 preset 当前还含 Task、PA、Heartbeat、Cron 等贡献。设计已明确要求共享 prompt 的消费者投影、不可用工具与指导一起过滤，并把最终 provider 请求列为证据，因此没有遗漏这一真实继承面。
- 原生 plan/user-interaction 类能力不应让内部执行者绕过 Global，新稿明确排除面向用户提问／计划展示入口；内部 send 仍为直接父子 schema。二级没有额外身份不改变原生 parent ID／委派来源，不把 `role=user` 或父级转述提升为真人授权。
- 产品权限由既有 `product-bridge.ts` 和 `personal-assistant/src/global-agent.ts:473-476` 按真实 root/child 身份拒绝 Inbox/产品聊天/公开发送/主人代发；`policy/approval.ts::attach/review` 继续取得可信父证据及来源。去掉二级产品 Prompt 不等于移除这些检查，也不意味着普通工作工具获得新对外授权。

#### 更新、占用、历史与冷恢复

- 当前 `ConfigurationScopes.restrictSelection/setConfiguration` 会遍历同产品 config，`whenIdle` 会等同产品的 live agents；`capability-state.ts::CapabilityState` 的 held/begin/busy/prepare 当前按 agentId＋tool 聚合，`index.ts:229-239,626-648` 接入工具调用和候选保存。这些都是工具分离时的真实波及面，不是仅在初建 child 跳过一次 allowlist 就能完成。
- 新设计明确上述入口都需使用同一角色语义：根普通工具撤回不撤掉一级工作工具、不因一级使用它而误报根保存依赖；真实调用占用仍记账，共享 Feature/Skill/扩展或权限撤回仍生效。相关已有接线和占用／预览测试已进入 M1，故下游有明确一致性目标，不是把使用记录删除来规避校验。
- `history.ts:99-128` 的 saved override 与 desired revision、`OwnedSessions.resolveManaged/activateChild` 的 catalog/descriptor/preset/cwd/depth 校验及公开 composition 路径，支持保留原身份的恢复设计。投影必须在新建、候选配置与冷恢复相同入口应用；设计要求用同一 DSH home 保存旧一级／二级 ID 后捕获候选 runtime 下一请求，并保留来源及当前要求，不用新 child 冒充恢复或重写旧历史。
- 根 fork 默认值仍在 Node default_on 与 integration 根默认筛选两处，显式名单优先；一级不进入该 root-only 过滤。Goal 专属数组/指导不与 fork 合并。既有 allowlist 记录无需迁移，但其对内部普通工具的适用范围按本次用户决定改变；设计已明确该行为变化，未悄悄宣称“继承行为保持不变”。

#### Agent Context、验证、架构与里程碑

- Consumer 为根、普通一级、普通二级及 fork；常驻指导只给需长期承担的角色，原话／资料由直接父级按任务传递，Skills 继续按已授权 provider 发现／加载。不复制根历史到普通子会话、不复制一套上游 Prompt，不把临时 ID 写入正式 Memory。
- 来源、选择、组装、消费、更新／失效与恢复链均有设计落点；可恢复目标、原执行者 ID、停止／等待／已交付事实复用现有笔记，用户 Persona、同名 Skill 及选择不回填。模型行为仍需自然目标任务验证，工具合法或字符串存在不能证明模型自主执行符合分工。
- 验证已经区分实际装配 fixture 与真实 Global/PA 产品旅程：前者守 root/一级/二级/fork 的请求、schema/强制执行、深度、权限、更新／占用／共享撤回和冷恢复；后者观察整项负责、根接日常、原事项更正、无重复调查及真实公开回执。不要求真实模型机械创建二级/fork，也不增加专门 fork 取消测试体系。
- 架构仍由 DSH 拥有执行和 lineage，integration 拥有角色投影，PA 拥有来源与产品交付；职责与依赖方向符合仓库红线。单 M1 范围扩大到必要配置／历史／capability reservation 接线是这次工具投影所必需，未引入通用代理框架、独立 Worker 会话、账本或第二套调度。
- 无新增客户端布局或交互形式，复用现有选择界面，不需新前端原型；实际默认勾选与保存仍需实施验收。daily 隔离 runbook、自然输入、provider/upstream 请求和 IM 回执可定位的退出依据保持。无数据迁移、无部署探针要求；M1 骨架存在，未宣称实现完成。

### 历史问题闭环与范围变化

- R1-W1、R2-W1 的旧方案问题及 R3 关闭结论保留原样。本轮用户明确排除额外清理流程，设计范围已调整；它们不再作为要求作者恢复旧清理机制的存活 finding。
- 本轮独立核对的控制契约是复用原生机制并如实表达受理／未知范围，不自动级联、不承诺后台 fork 全树终止。该范围与当前 spec/delta 一致，没有用旧批准跳过新分层审查。

### Issues

无存活 CRITICAL / WARNING。

### Recommendations

无额外可选建议；实施按现有 M1 收集所列证据即可，不因本报告新增流程。

### 冻结版本定位

本轮受审文件 SHA-256：

- `spec.md`: `fe3422ac46c50a38a81ede0877582033c4593064534181c03ade464d34489674`
- `design.md`: `e32e7f53a49e9c7217c52a88310a6e8508e3a27138fe8a6f26d477413f53bb8c`
- `specs/gateway/global-agent.md`: `60c24feb3c7ffe6fb6c5a33db6af544f01a70f34b1d582463e07461a38bd0bb2`
- `specs/gateway/personal-agent.md`: `7df8c4795d8a7ec6f442cdef313a49a0b10dbdc84fdf4be0bb8ed87f19f42e86`
- `specs/gateway/agent-capabilities.md`: `a04bcb27ab241898b1ffbea1e599860f4158a1775a0cdd69536ebd7fe1baf7e7`
- `M1-global-delegation/.gitkeep`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

### 未验证与交接

本轮为只读源码／锁定依赖／参考仓及文档审查，未运行服务、实现测试、真实模型或候选产品，不把设计可实现当成行为已验证。产品权限和分层最终请求、更新占用、同 ID 冷恢复、Global/PA 自然旅程及相关回归仍是实施退出条件。仅追加本 Round；未修改 spec/design/delta/代码、未提交、未切换 checkout，也未动现场其他未跟踪内容。

### Author Resolutions

- R4 无存活 issue，作者接受 Approved 结论。已对照用户最新决定、实际装配与本轮受审文件确认：二级普通 subagent 无额外 Nano 身份，一级 DSH 工作能力不受主会话 fork 开关影响；不恢复旧专门取消流程，Task 继续暂缓。
- 另核原生参数来源：锁定 DSH `dsh-subagent/lib/types/continuation-messages.js:42` 已向 continuable 子会话注入真实父级 ID 和 send_message 回报方式，支持受审设计无需给二级另造身份提示。此为原设计依据补充，不改变受审产物。
- 受审 spec、design、三份 delta 和 M1 骨架保持 R4 SHA-256 未变。文档检查通过：纳入本 unit 全部文件后为 289 maintained Markdown sources / 68 required routes；运行代码、真实模型与产品旅程尚未实施。
