# feat-720: 在用户的浏览器里操作页面（macOS 页面内动作） — 技术方案

> 对齐: [spec.md](spec.md)（含 Gate 2 Round 1、Round 2 修订）

## 现状分析

### 涉及范围

本 unit 在 DSH 节点 runtime 进程内新增浏览器控制，不新增服务、数据库或第二套循环。PA 仅在既有 Inbox 结果投影保留真人消息的原始 `created_at`，供已存在的 runtime-live 来源 seam 判定新鲜度；不改 Inbox 唤醒、读取资格或消费/投递语义。IM 与 Channels 不改。恢复基线：`origin/develop eeaea47921806936da20e78c9ed96167716f5037`；旧分支 `d02416f0c` 保留，当前 `codex/feat-720` 已无冲突合并该基线。

| 位置 | 现状 | 本 unit 的处理 |
|---|---|---|
| `packages/dsh-integration/src/`（新增 `browser/`） | 无任何浏览器/桌面控制代码；全仓检索 `cua-driver` 无命中 | 新增驱动客户端、身份解析、事件分类、策略与工具注册 |
| `packages/dsh-integration/src/index.ts` | 装配 `NanoApproval`、`ProductBridge`、Workflow、Knowledge 等插件（L190–241）；`tools/pre-execute` 已有能力预留 hook（L229–238） | 在 `NanoRuntime` 构造期安装 `BrowserControl`，注册两项工具与一个静态参数守卫 |
| `packages/dsh-integration/src/capabilities.ts` | `defaultOff`（L16）决定未配置白名单的 Agent 默认看不到哪些工具 | 把 `browser_read`、`browser_act` 加入 `defaultOff` |
| `packages/dsh-integration/src/policy/approval.ts` | `safeTools`（L25）列出只读/低风险工具；`review()` 在此之后走分类器与人工分流（L104–153）；`route()`（L76–83）把轮次分为 interactive / unattended / return_to_agent，`escalate()` 只在 interactive 出卡片，其余按回退或拒绝（L97–102） | `browser_read` 进入 `safeTools`；`browser_act` 不进入任何自动允许集合，并加入"无人值守回退不放行"排除集；`route()` 的轮次输入判定抽成可复用函数（行为不变），供 TurnGate 复用 |
| `apps/node/src/capabilities.ts` | `projectCapabilities` 用排除清单计算工具 `default_on`（L50–55） | 两个新工具加入排除清单，设置页显示为默认未选 |
| `packages/product-contracts/src/capabilities.ts` | 新增能力通常做成 Feature（`featureDependencies`），Feature 依赖工具与 skill 存在 | **不新增 Feature**，只做两项独立工具（见决策 D10） |
| `apps/node/src/main.ts` | `RuntimeSupervisor` 为每个 partition 启动独立 DSH 子进程；节点主机为 macOS | 不改；能力跑在该进程内，直接与本机驱动通信 |

### 既有约束

- 执行运行时只能经 DSH 公开 exports 接入；不得 fork/patch 运行时，不得引入第二套 Agent Loop，节点与 DSH 之间仍是 stdio，不新增 HTTP 服务（`AGENTS.md` 架构红线）。
- 工具可见性由 `ToolSelection.restrict` 决定：`toolAllowlist === undefined` 时等于“除 `defaultOff` 外全部”，因此**新工具默认关闭必须进 `defaultOff`**，不能只靠文案提醒。
- 所有工具调用都经 `tools/pre-execute`：先经过 `CapabilityState.begin` 配置预留检查，再经 `NanoApproval.review`；`safeTools` 只对 `policy.rules !== 'dsh'` 生效，`dangerouslySkipPermissions` 会显式放行。
- 审批路由分 interactive / unattended / return_to_agent（`approval.ts` L76–83）；无人值守只按既有 `unattendedFallback` 处理。本 unit 只收紧一处：`browser_act` 不参与无人值守回退放行（`escalate` 的排除集），不新增放行分支。
- 安全边界：不提交 secret、日志、截图缓存；截图只能落在 Agent workspace 的约定目录，不落仓库，并按有限保留期清理。
- 驱动是外部依赖（`cua-driver 0.38.0`，MIT，宿主已安装）；仓库不 vendor 二进制，不自动安装或授权。

### 可复用能力

| 能力 | 结论 | 理由 |
|---|---|---|
| `NanoApproval` | 用 | 已有分类器、人工审批、审计、denied 计数与失败分流；本 unit 只增加一个只读工具的安全标记 |
| `ToolSelection` / `CapabilityState` | 用 | 默认关闭、配置保存期间预留、收缩立即生效都由既有机制保证 |
| `ctx.tools.register`（name/description/parameters/output/execute） | 用 | 与 `skill_manage`、`workflow` 等工具同一注册面，模型看到的结果与错误形状一致 |
| `cua-driver` CLI `call` | 用 | 有稳定 JSON stdout、有本次实测回读；进程内一次性调用即可，无需新服务 |
| `cua-driver` MCP transport | 不用 | 需要额外常驻连接与协议层，产品侧无收益；CLI 已足够 |
| 驱动 `run_script` / `run_steps` | 不用 | 一次调用内循环/条件/编排等于第二套 agent loop，违反架构红线 |
| 驱动 `page` / `query_dom`（AppleScript 路线） | 不用 | 多实例时直接 `browser_applescript_process_ambiguous`（证据 L479–485） |
| 驱动 `hotkey` / `type_text` / `press_key` / `bring_to_front` | 不用 | 原生 chrome/AX/HID 路线，属地址栏与窗口操作，不在页面内动作范围；也绕开审批语义 |
| 新增 Feature（`featureDependencies`） | 不用 | 见决策 D10 |

### 相关历史

- `feat-615-agent-approval-strategies`：确立 `NanoApproval` 作为唯一审批 facade 与 `safeTools`/人工/无人值守分流；本 unit 沿用，不新增审批路径。
- `bugfix-626-approval-context-fidelity`：审批必须看到真实来源与上下文；本 unit 的 `browser_act` 依赖“先读后点”让分类器在同一会话里看到页面文本，不引入新的来源伪造面。
- `feat-616-personal-agent`：执行隔离与最小权限；本 unit 的实例按 Agent 归属、默认关闭、不扩权，与其边界一致。
- 仓库中此前没有浏览器控制或 computer-use 类 unit；`docs/changes/` 全量检索无 `cua-driver` 记录。

## 验证结论：五条硬约束

证据报告全文已逐字复制到 [evidence/desktop-verification.md](evidence/desktop-verification.md)（570 行；本 design 引用的行号已逐条核对）。原始报告与截图在 `/tmp/desktop-verify/`（`report.md`；截图 `shots/01-example-cdp.png`、`02-window-two-tabs.png`、`04-fixture-page.png`、`05-before-click.png`、`06-after-ref-click.png`、`07-after-xy-click.png`、`08-after-scroll.png`、`09-resample-after-settle.png`、`10-after-scroll2.png`），截图只登记路径，不入库。

### 约束一：tab/target 身份不稳定

**证据。** 同一窗口、同一 about:blank 标签连续 3 次 `get_browser_state`（间隔 0.3s、中间无动作）得到 3 组不同的 `target_id` 与 `tab_id`（L493–501）；拿旧 id 操作返回 `browser_tab_not_found`（L291–299、L502–506）。`tabs[]` 顺序是活跃/MRU 语义：切换后 active 跑到 index 0、新标签插到 index 0（L305–307、L508–520）。ref 命名空间是 `p<snapshot>:<index>`，新快照作废旧 ref（L528–529、以及 `browser_click` schema 的 ref 说明）。

**判断。** 驱动在 0.38.0 上不提供跨调用的稳定句柄；把 `tab_id`/`target_id` 缓存在我们这层必然在生产上变成“点错标签/报 tab not found”。稳定身份只有“窗口 `(pid, window_id)` + 在该窗口一次 bind 结果里按 `url`+`title`+`active` 认标签”。

**实现约束。**

1. 每个公开工具调用内部都完整执行一次“解析窗口 → bind → 选标签 → 用本次返回的 `target_id`/`tab_id` 执行”，不跨调用复用任何驱动 id；缓存只允许存在于单次调用栈内。
2. 对外身份使用我们自己铸造的 `read_id`（单调递增的快照游标），绝不对模型暴露 `tab_id`/`target_id`。
3. 选标签只按 `url`+`title`+`active` 匹配；匹配到多个 → `browser_tab_ambiguous` 并列出候选，不按 index 取第一个。`tabs[]` 的 index 只用于展示，不参与判定。
4. ref 只在最近一次 `read` 的 `read_id` 下有效；驱动报 ref 失效或动作时 URL 与 `read_id` 记录不一致 → `browser_snapshot_stale`，要求重新读取，不做“再点一次试试”。
5. 同一 Agent 的驱动调用串行化（进程内互斥），避免两个工具调用交替 bind 后互相作废身份。

### 约束二：前台行为必须收窄承诺

**证据。** 第一轮所有 `delivery_mode:"background"` 动作前台 app 未变（L247–268）；第二轮 `browser_prepare` 启动时前台从 `Electron|49704` 变成驱动自己的 `Google Chrome|25324`（L543–549），与第一轮同一调用的 `foregrounded_window:false` 不一致（L267–268 与 L543–549）。`window.open`（带 gesture）弹出真窗口后，前台持续 ≥4 秒不恢复（连续 4 次采样都是驱动实例），直到 `end_session` 才回到用户 app（L549–554）；不主动结束时实例按 `idle_expires_in_seconds: 300` 回收（L85、L325），所以无人干预时前台占用上界约 5 分钟；同一份清理核实里，`end_session` 后用户自己的 Chrome（pid 660）仍是原来的 5 个窗口、全程未被波及（L556–558）。地址栏 AX 注入文本必须 `delivery_mode:"foreground"` 才会提交（L154–159、L184–190）。驱动文档层面：`bring_to_front` 明确不恢复原前台 app（L276–279），`hotkey`/`type_text` 的 foreground 分支只承诺“做这件事所需的短暂前置”。

**判断。** “不抢焦点”只在“页面内、background、不产生新窗口”这条路径上成立；“首次接入”和“页面自己开新窗口”都可能抢前台且我们无法阻止。承诺只能写成收窄后的那一句，且不能用它推导时长。正因为无法阻止，前台占用必须有机制上的上界（谁可以启动实例、出现新窗口后怎么归还），否则验收只能拿一次 4 秒中断当结论。

**实现约束。**

1. 产品文案使用 spec 里的原句；任何设计、工具描述、审批文案、错误说明都不得出现“绝不打扰用户”一类绝对表述（写入工具描述与 review 检查项）。
2. 我们只使用 `delivery_mode:"background"`；不提供、不透传 `foreground` 参数；不调用 `bring_to_front`/`hotkey`/`type_text`/`launch_app` 等会主动激活窗口的驱动工具。
3. **首次启动实例只允许“用户发起的、且仍在场的轮次”**：普通会话自身作为判定会话；子 Agent 沿 `header.parentSession` 经 `ctx.agents.get` 上溯到首个非子 Agent 祖先，用 `seen` 检出环，链断/环一律拒绝，不退回子任务 seed。只读活会话内存；三条同时满足才允许 `browser_prepare {allow_launch:true,profile:{mode:"isolated_new"}}`：① 最近 `turn/start` 之后无同号 `turn/end`；② 该打开轮次内有下述合格真人输入；③ **原始输入时间**距当前 `0 <= delta <= 300_000ms`。300s 与驱动空闲回收同量级；负差值、缺失/非法时间一律拒绝，不从“刚刚读取”推断用户刚刚发言。合格来源只有两种：
    - 直接输入：`isHumanSource` 的 `user/message`，时间为本节点 DSH append 的 `event.time`，仍复用既有来源谓词。
    - **Global/PA 实际 Inbox 输入**：既有 `ApprovalSources` 确认本进程执行并观察到的、当前判定轮次内成功 `inbox read` 的结构化真人消息。须 `sender.type === 'user'`、完整（无 `partial`）、非 `pa_agent_id` 代发、页面 `delivery` 非 `observer`，且带宿主原始 `created_at`（PA 的 `InboxStore.read` 从可信 `RelayInput.message.created_at` 原样保留，不采用正文、自报时间或 metadata fallback）。该时间由 IM/入口服务产生，需可解析且与节点当前时钟的差值在 0…300s；跨机时钟偏差/缺字段按不可证明在场拒绝，用户再发消息仍异常时提示检查系统时间。原始时间不因分页、重读或恢复刷新。`ApprovalSources.liveHumanTimes(agent, afterSeq)` 复用已有 `isLiveInbox` 标记和完整 `tool/result`，只返回该轮合格源时间，不授予业务授权；BrowserControl 通过进程内 callback 取得祖先时间，不新增 RPC、来源读取器或 loop。
    - mere Inbox wake、Agent/system 发言、partial、observer、PA 代发、历史 conversations、恢复的旧 tool result 均不产生在场证据。唤醒仍是系统通知，**不得改标真人**。定时/心跳/任务续跑没有这些输入时拒绝；同轮确有新的合格真人输入时才按其原始时间判定。无打开轮次、无合格真人、超窗、链断或环均返回 `browser_launch_requires_user_turn`；已有实例可复用，不由复用反向创造新开窗资格。
    - 为什么按层判定，而不是“子 Agent 一律拒绝”：`route()` 里确实有 `agent.session.header.origin === 'subagent'` 早退（`approval.ts` L77），但子 Agent 有自己按 Agent 归属的实例，若一律拒绝，主 Agent 在用户轮次里把“看/点页面”委派给子 Agent 就永远不可用（子 Agent 既没有实例也不能建实例）。按层判定恢复的只是**同步/前台委派**（同一轮次、人类发言在 300 秒内）；**后台委派（那一轮已结束）与长轮次末端委派（人类发言已超窗）仍然拿不到实例**，只复用已有实例——这条限制同时写进 spec/delta 与已知限制，避免用户按“委派就能开窗”预期使用。
    - 为什么不用子 Agent 自己的轮次输入，以及为什么“拿不到就拒”而不是“拿不到再决定”：`isHumanSource` 的注释写明 native child 的首轮 prompt 也用 `user`（`input-source.ts` L21），子 Agent 自己的 source 形状不足以证明“用户在场”，所以只认祖先层，结论不依赖 DSH seed 的字段形状。`ctx.agents` 是**活 Agent 注册表而不是持久血缘**（DSH 自己的 `liveLineage()` 也是 `ctx.agents.get(parentSession)` + `seen` 环检测；子 Agent 的 `parentSession`/`delegationDepth` 由 `childSessionMeta()` 写入），所以“父轮次结束后仍可解析”本来就不成立：父 Agent 销毁或不在注册表时链断，deny 是正确结果。实现上不存在“拿不到就退回硬闸门再决定”的分支——静态可解析就按在场窗口判定，解析不了就直接拒。
    - 与审批路由的区别：`task-execution`/`task-change` 轮次在审批上算 interactive（用户能看卡片），但不代表用户此刻在场，因此**不**计入可启动轮次。判定在 `tools/pre-execute` 内同步完成：只读内存事件与 `ctx.agents.get`，不做文件或进程 I/O、不调用驱动；并从 `approval.ts` 复用同一事件读取实现（`currentTurnInputs`，另加只读的轮次打开状态与人类消息时间判定），避免两份语义漂移。
4. 允许启动的那一次在结果里附固定说明：首次接入可能短暂占前台；这是唯一一次“启动即可能抢前台”的路径。说明里不写秒数。
5. **页面动作后若分类出真实新窗口**（见约束三）：在完成本次回读与截图后立即 `end_session` 结束该 Agent 的浏览器实例，结果里返回 `foreground_released: true` 与 `events[]`；继续操作需要新的用户轮次（重新 prepare）——用判定祖先的 `(sessionId, turn/start seq)` 记录已消费轮次，进程内共享于该祖先的根/子请求；同祖先同轮次即使新收一条真人消息、另派子 Agent 也不得 relaunch，直到新的合格 `turn/start`。请求入队执行时捕获判定轮次，回读/结束实例期间在场超窗或祖先轮次关闭都不丢掉该消费标记；不在 release 时重新要求 `presence.allowed` 才记录。`end_session` 前先校验目标：session label 属于本 Agent（`nano-br-<8hex>`，按 agentId 记账）**且**实例 pid 仍等于 `browser_prepare` 返回的 `owner_pid`（证据 L84）；任一不符则不调用驱动、直接按失败处理。`end_session` 失败重试一次；仍失败返回 `browser_foreground_release_failed`，请用户手动关闭该窗口，并让该 Agent 进入**需人工恢复**状态：后续调用不派发任何驱动动作、直接返回同一错误，直到冷却到期。冷却用 `failedAt + 300s`（与驱动 `idle_expires_in_seconds` 同量级）**惰性清除**——每次调用只比较内存时间戳，不做 pid 探测（那是进程 I/O，且 pid 会被复用）。冷却期内所有调用都先被静态守卫拒绝，因此不存在“新实例成功收尾清除状态”这条路径。否则模型可以在同一用户轮次里反复动作、反复把窗口带回前台。证据 L556–558 是“关窗不波及用户窗口”的直接依据。
6. **v1 不做自动恢复用户前台 app**：恢复需要我们把用户前台 app 重新激活，既无验证证据，也会在用户正在操作时与用户抢；但“不恢复”不等于“无上界”——上界由第 3、5 条与 300 秒空闲回收共同保证。
7. 不通过 `osascript`/System Events 采样前台 app：那会给节点进程引入新的 Automation 授权依赖，而检测“是否抢过前台”不是 v1 的产品承诺前提；`end_session` 是我们可以确定执行、且证据中观察到会归还前台的唯一动作（L549–554 为 1 次观察；V2 复采确认后才作为机制依据）。

### 约束三：驱动分不清真窗口与浏览器 chrome 弹层

**证据。** 正常地址栏输入就报 `opened new window(s)`，实测多出来的是 1038×218、无标题、紧贴地址栏的 omnibox 建议下拉（L193–217、L531–535）；另有 284×87 的「翻译此页？」气泡（L464–465、L536）。真窗口是 `window.open(...,width,height)` 产生的 520×426，带独立 `target_id`、`url=popup.html`、`binding_quality:exact`（L460–477、L537）。`target=_blank` 只开新标签、不开窗口（L450–458、L538）。驱动把两类都归为同一句 `🪟 Action opened new window(s)`。

**判断。** 不能把驱动的事件文案当分类结果；否则正常输入就会触发“出现意外就停”的自杀式护栏（第一轮正是如此，L193–217）。分类必须由我们在 bind 层做，且必须有三态：真窗口 / chrome 噪声 / 未分类。

**实现约束。**

1. 每次可能产生窗口的动作后，用 `list_windows {pid}` 对比已知窗口集合（已知集合只含 `browser_prepare` 时登记的主窗口，见约束五）；对每个新窗口调用 `get_browser_state {session, pid, window_id}` 做分类。
2. 判定表（有序决策树，实现按顺序短路并有单测）：
   1. `get_browser_state {session, pid, window_id}` bind 成功（`binding_quality: exact`）且至少一个 tab 的 `url` 是 `http(s)` → **真实浏览窗口**；记录 `events[]`，继续本次调用。
   2. 只有同时满足全部噪声证据才是 **chrome 噪声**：bind 失败/refused **且** 没有 target **且** 没有任何 URL **且** 标题为空或是浏览器自带文案（翻译/建议）**且** 窗口尺寸属于固定 UI 尺寸集合（`284×87`、`1038×218`，写死但有单测）。噪声只计数与记录，不算失败、不重试。
   3. 其余一切（包括 bind 失败但噪声证据不完整，或 bind 成功但 URL 非 `http(s)` 的 `about:blank` 类窗口）→ **未分类**：返回 `browser_unexpected_event` 与窗口证据并结束本次调用。错误文本要求模型先把这件事告诉用户、再决定是否继续；宿主不声称“停止后续动作”（v1 每次调用只有一个动作，没有批次可停）。
3. 驱动响应里的 `opened new window(s)` 只作为“需要检查窗口集合”的提示，不直接决定事件类别。
4. 模型可见结果里区分 `events[]`（真实窗口）与 `ignored[]`（噪声，仅计数/尺寸/标题），避免模型把噪声当异常反复处理。
5. 真实新窗口按约束二第 5 条结束实例、归还前台；噪声与未分类都不改变主窗口登记。同次检查同时有真实窗口与未分类窗口时，**先完成真实窗口的归还**，再返回 `browser_unexpected_event` 并附 `foreground_released:true` 与两类证据；不得先抛未分类错误而跳过已确定的归还。窗口列表/分类失败不能吞成“没有事件”的成功；返回具体驱动错误与状态未知，不自动重放动作。

### 约束四：读数口径

**证据。** `semantic_v2` 的 `in_viewport` 与真实视口稳定差约 1.92 倍（≈`deviceScaleFactor=2`）：请求 1200 CSS px，`in_viewport` 只前进 13 行，而截图显示前进 25 行（L433–446）。截图实测 2400×1464 设备像素 = 1200×732 CSS px（dp=2，`08-after-scroll.png`），而 `browser_read` 的语义结果不含元素几何、视口 CSS 尺寸或 DPR；坐标点击的 `x/y` 只能用“上一次点击后的 summary 回读”倒推（L411–416），不是动作前可用的输入。两个 Chrome 实例并存时旧 `page` 工具直接报 `browser_applescript_process_ambiguous`（L479–485），`query_dom` 还要求 `window_id`。`browser_pointer` 接受 `ref` 或 `x`/`y` 作为滚动锚点，缺两者时返回的是一句错误文本，包装层很容易吞成空对象（L486–489）。`browser_navigate` 拒绝 `file://`（L388–392）。

**判断。** 语义快照的可见性/滚动偏移只能当“大致方向”；位置类结论必须以截图为证据。结构化的 `effect: "unverifiable"`（点击返回，L404–407）意味着动作成功后必须回读，不能假设生效。坐标输入没有可靠来源：截图是设备像素、读数不含几何，模型无法从结果里推出可用的 CSS px 坐标，因此 v1 不接受坐标点击。

**实现约束。**

1. `read` 的文本结果只用于内容与元素定位；工具描述明确写“不要用可见性标签判断滚动位置/是否可见”“截图尺寸是设备像素，不要据此换算或给坐标”。
2. 提供 `screenshot: true` 时把 CDP 视口截图保存到该 Agent workspace 下的 `.nanoassistant/browser/<agentId>/`（先 `resolve` 再校验前缀，越界则不写文件、结果里返回 `screenshot_omitted:"outside_workspace"`），并返回 workspace 相对路径；工具描述与结果都写明“要看画面证据就用 `read_image` 读这个路径”。凡是“滚到某处/元素可见”的结论要求模型同时引用截图。滚动动作的默认返回附一张截图（见接口）。截图是页面内容的临时证据：每 Agent 保留最近 20 张、TTL 1 小时；**只在写入新截图时**按 TTL 与数量上限清理该 Agent 目录；进程启动时补一次**有界**清理（只扫已配置 Agent 的 workspace 下的 `.nanoassistant/browser/<agentId>/`，不遍历 home 或仓库，单次有界，失败只记录、不阻塞启动，只删本能力按 TTL/张数规则判定的文件），实例结束（含真窗口后的 `end_session`）与 Agent 销毁都不立即删除——真窗口路径要求“回读与截图后立即结束实例”，若结束时删图，模型下一次 `read_image` 就没有证据可读。截图不进 Memory/Skill/Dreaming。
3. 不使用 `page`/`query_dom`；任何依赖 pid 归属的 AppleScript 路线一律不接。
4. 驱动客户端的失败口径：非 0 退出、空 stdout、无法解析 JSON、缺少预期字段 → `browser_driver_malformed`（带截断的原始输出片段），**一律不当成功**；`browser_pointer` 的 scroll 参数在发请求前校验，缺 `ref` 或 `delta` 直接 `browser_arguments_invalid`。
5. `open` 只接受 `http`/`https`（`file://` 由我们提前拒绝，不依赖驱动报错）；本地夹具在验证里用 `127.0.0.1` 静态服务（证据 L388–392）。
6. 滚动只支持 `ref` 锚点，不接受坐标；锚点必须是最近一次读取里**声明了 `scroll` 或 `pointer` 动作**的 ref。实施期实测（V5）：`listitem`/静态文本 ref 被驱动拒绝（`browser_action_unavailable`，“does not declare the scroll or pointer action”），而 `button`/`link`/`textbox` 声明 `pointer`，`browser_pointer {action:"scroll", ref, delta_y:600}` 派发成功、截图前后对照位移与请求量一致。因此结果的 `refs[]` 必须带 `actions` 供模型选锚点，驱动 `browser_action_unavailable` 映射为结构化失败（保留 hint，提示换一个声明了 `pointer` 的 ref），不得吞成空结果。

### 约束五：一个实例只登记一个主窗口

**证据。** 同一 pid 可以同时有多个窗口：`window.open` 弹窗（520×426、独立 target）与两个「翻译此页？」气泡（284×87）并存（L460–477、L536–538）；`list_windows` 不承诺顺序，`browser_read {}` 省略 `tab` 时只取“某次 bind 的 active 标签”，没有任何跨窗口规则。

**判断。** v1 不做多窗口管理：一个 Agent 实例只在 `browser_prepare` 得到的主窗口里工作；新窗口是事件，不是新的工作目标（真窗口还会触发约束二的前台归还）。否则页面自己开窗后，下一次读取/点击可能落到弹窗，等于按位置猜目标。

**实现约束。**

1. `browser_prepare` 后立刻 `list_windows {pid}`，对每个候选窗口做一次 `get_browser_state`；候选 = `binding_quality: exact` 的窗口（`pid` 已把窗口集合限定为本 Agent 的驱动实例）。恰好一个 → 登记为**主窗口** `(pid, window_id)`，**不要求该窗口已有 `http(s)` tab**：实施期实测新建实例的初始窗口只有 `about:blank`（`binding_quality: exact`），若要求 `http(s)` 则首次使用永远 0 候选、必然 `browser_session_lost`；噪声窗口（`284×87` 翻译气泡等）本来 bind 失败，真弹窗与主窗口并存时按“多个候选”判 `browser_window_ambiguous`。零个 → `browser_session_lost`；多个 → `browser_window_ambiguous`（列出候选并结束本次调用，不按顺序取第一个）。`http(s)` 判据只保留在新窗口事件分类（约束三）。
2. 之后所有读取与动作都只解析主窗口；`browser_read` 结果里的 `tab.window_id` 是主窗口。请求可选 `window_id`，不等于主窗口 → `browser_window_not_registered`。
3. **初次登记与恢复分开**：主窗口 bind 失败时只允许对原 `(pid, window_id)` 重试一次，不再扫描并采纳其它窗口。仍失败则保留原主窗口基线做一次窗口分类，已确认真实新窗口按归还流程结束；无论剩下的唯一窗口是 http(s) 弹窗还是 about:blank 未分类窗口，都不得提升为主窗口或执行页面动作。然后结束该自持实例、清空登记与旧 read_id，返回 `browser_session_lost`（附已取得的事件/未分类证据与归还状态；结束失败沿用需人工恢复冷却）。不能证明原窗口身份时宁可重开，不把 surviving popup 当恢复结果。
4. 新窗口（真窗口/噪声/未分类）都不登记为主窗口；真窗口在本次调用结束时按约束二结束实例，因此不存在“第二个可操作窗口”。
5. 跨窗口不生效：`tab` 匹配器只在主窗口内匹配；匹配不到 → `browser_tab_not_found`，不跨窗口找。

### 实施期实测补充（V1 / V5 / V4 主窗口登记）

Gate 2 之后在实施期用本机 `cua-driver 0.38.0` 补跑了两项验证并纠正了一条设计判据；夹具与截图只在 `/tmp/desktop-verify/`，不入库。逐项结果、未执行项与驱动响应形状见 [M1-page-actions/evidence/real-driver-checks.md](M1-page-actions/evidence/real-driver-checks.md)。

- **V1 PASS**：页面内 `browser_type {delivery_mode:"background"}` 写入 14 字符，回读 `value` 与输入一致，全程前台 app 未变。
- **V5 PASS（带约束）**：`browser_pointer {action:"scroll", ref:<声明 pointer 的 ref>, delta_y:600}` 派发成功，截图前后对照位移与请求量一致，前台未变；用 `listitem`/静态文本当锚点会被驱动拒绝（见约束四第 6 条）。
- **V4 主窗口登记纠正**：新建实例的初始窗口只有 `about:blank` 且 `binding_quality: exact`，因此“候选必须含 `http(s)` tab”会让首次使用永远 0 候选；登记判据改为“唯一 exact 绑定”（见约束五第 1 条）。另一处实现期纠正是页面文本来源：`semantic_v2` 的页面文本在顶层 `outline`，`snapshot` 只是元数据。
- **未执行**：V2（`window.open` 后 `end_session` 是否把前台还给用户 app）、V4 的弹窗半边、V3 的完整独立采样——这些都要启动多个真实浏览器实例并抢前台，执行前被授权门禁拦下，记录在 evidence 文件；按设计 V2 未通过前不发布该能力，交付 PR 必须标注这一未验证项。

## 架构总览

```text
Agent (DSH session)
   │  tool call: browser_read / browser_act
   ▼
tools/pre-execute
   ├─ CapabilityState.begin        （既有：配置保存期间的预留/收缩）
   ├─ BrowserPolicy.static         （本 unit：平台、参数、scheme、窗口归属；纯同步，无 I/O）
   └─ NanoApproval.review          （既有：分类器 / 人工 / 无人值守，按会话类型分流）
   ▼
BrowserControl (per-Agent state, in-memory)
   ├─ TurnGate         按来源层 + 300s 在场窗口（决定能否新开实例）
   ├─ WindowRegistry   主窗口 (pid, window_id)，每实例一个
   ├─ TabIdentity      bind → 选标签 → 本次 target_id/tab_id → read_id/ref 校验
   ├─ EventClassifier  list_windows → bind → 真窗口/噪声/未分类
   ├─ Foreground       真窗口后 end_session 归还前台（失败重试一次后需人工恢复）
   ├─ Screenshots      workspace 相对路径、TTL 1h、最多 20 张
   └─ DriverClient     spawn `cua-driver call <tool> <json>`（无 shell）
        ▼
cua-driver daemon（宿主安装，0.38.x；TCC 身份 com.trycua.driver）
        ▼
driver-owned isolated Chrome（独立 profile；随浏览器会话/空闲结束）
```

前：Agent 没有任何桌面/浏览器控制面，只有网络读写（`web_search`/`web_fetch`）。后：新增两项默认关闭的页面级工具；没有新进程模型（驱动 daemon 是宿主既有依赖）、没有新 HTTP 服务、没有长期持久化（只有有限保留的截图文件），没有第二套循环。

## 关键决策

**D1：能力放在 `packages/dsh-integration` 的两个工具里，不新增服务、不新增 agent loop。**
工具是同步 request/response，一次调用最多产生“一次动作 + 一次回读 + 一次窗口检查”；不在我们这层做循环、条件编排或自动重试动作。备选（在 `apps/node` 另起浏览器服务、经 RPC 暴露给 DSH）会新增进程边界与协议，且与“节点只经 stdio 管 DSH”的现状相反；备选 MCP 连接会把驱动协议再包一层，收益只是省一次 spawn。

**D2：只通过 CLI `cua-driver call <tool> <json>` 调用驱动，直接读 stdout JSON。**
这是本次实测用过的路径（证据 L4–5），错误形状（refusal/hint）可原样转成结构化结果；不引入 MCP 客户端、不解析私有 socket 协议（未文档化，升级即碎）。spawn 使用参数数组、不拼 shell，避免 URL/输入文本进入命令解析；设置单次超时（默认 20s，导航 30s）与输出上限（截图走 base64，上限 32 MB），超时杀子进程并返回 `browser_driver_timeout`。

**D3：身份是“窗口 `(pid, window_id)` + 一次 bind 里的 `url`+`title`+`active`”，对外用 `read_id`。**
理由与实现约束见“约束一”。拒绝备选：缓存 `tab_id`（实测 3/3 次重铸）、按 `tabs[]` index 认标签（活跃/MRU 语义，实测新标签插到 index 0）、把 `continuation` 当稳定游标（驱动有该字段，但本次未验证语义与生命周期，v1 不用）。

**D4：窗口事件三分类，噪声不算失败，未分类结束本次调用并交回模型。**
理由见“约束三”。这是把“出现意外就停”的安全护栏从“驱动说什么就停”改成“我们确认过才停”。拒绝备选：见 `opened new window(s)` 就停（第一轮实测会让正常输入杀死任务）、或见文案就忽略（会把真实弹窗吞掉）。v1 没有“批次”概念，因此护栏写在错误文本（模型可见指导）里，不假装宿主能阻止模型的下一次调用。

**D5：读数与回读口径以画面为准，空响应即失败。**
理由见“约束四”。点击/输入的驱动返回是 `effect:"unverifiable"`，因此动作成功后做一次有界回读（页面文本 + 可选截图），结果里区分“驱动已派发”“回读确认变化”“未回读”。拒绝备选：相信 `effect`、或用 `in_viewport`/`omitted.offscreen` 推滚动位置。

**D6：前台只做披露，不做自动恢复；承诺以 spec 原句为上限，并用“谁能启动实例 + 真窗口后结束实例”给出上界。**
理由见“约束二”。不做自动恢复是因为没有验证过任何恢复路径，而且恢复本身是一次前台激活，会在用户正在打字时二次打扰；但这不能成为“占用无上界”的理由：首次启动实例只允许用户发起的轮次，真实新窗口在本次回读后 `end_session`（证据中有 1 次观察会归还前台，L549–554；V2 复采确认后才作为机制依据），失败则重试一次，仍失败则进入需人工恢复；300 秒空闲回收只是兜底。承诺仍按用户指定原句保留，不据此解释秒数。

**D7：审批分三层：静态守卫 → `NanoApproval` → 执行期身份/归属校验；出口随会话类型不同，必须写清。**
- `browser_read` 允许进入 `safeTools`（只读、只能读本 Agent 自持实例、无文件与登录态）。它仍受下游 allow/deny 与配置预留约束。注意：`browser_read` 也可能触发首次 `prepare`，所以真正的“不抢前台”不靠审批，而靠 TurnGate（约束二第 3 条）：TurnGate 不通过的轮次只复用实例。
- `browser_act` 不进入 `safeTools`/`alwaysAllowTools`/`contextTools`。实际出口按 `approval.ts` 的 `route()`：
  - **interactive**（单聊里出现真实用户消息，或 `task-execution`/`task-change` 轮次）：分类器判定；需要人工时出审批卡片。
  - **return_to_agent**（Global 根会话与子 Agent）：只有分类器放行才执行；分类器要求人工时**不出卡片**，直接拒绝（`NanoApprovalDenied`），模型须向用户说明“这一步需要在单聊里确认”。
  - **unattended**（`schedule`/`heartbeat`）：`browser_act` 加入无人值守回退排除集——分类器要求人工时一律拒绝，不因 `unattendedFallback: 'allow'` 自动放行；分类器明确放行的低风险动作仍可执行。理由是页面动作有外部副作用，没人看着时不应该用“回退允许”代替审批。
  - 唯一例外是用户显式开启 `dangerouslySkipPermissions`（既有产品语义，不为此新增分支）。
- 静态守卫在 `tools/pre-execute` 提供无 I/O 的确定性拒绝：非 darwin、`open` 的 scheme 不是 http(s)、click 无 ref（v1 不支持坐标）、scroll 无 `ref` 或无 `delta`、输入文本超长（默认 4000 字符）、请求的 `window_id` 不是已登记主窗口、**需要新实例但 TurnGate 不通过**（`browser_launch_requires_user_turn`）、**该 Agent 处于前台归还失败的需人工恢复状态**（`browser_foreground_release_failed`）。守卫的拒绝经 `next()` 先到达审批层，因此先于分类器。执行期只复核依赖页面实时状态的事：“是不是我们的 pid/窗口”“`read` 之后页面是否变了”“标签是否仍唯一”。
- `browser_act` 的审批文案与工具描述必须写明：不登录、不提交表单、不下载；需要改动页面状态的动作要先读后做；不接受坐标点击。

**D8：每个 Agent 一个驱动 session，串行、随 Agent 销毁结束。**
session label 随机生成（`nano-br-<8hex>`），同进程内按 agentId 复用；所有动作在同一 label 下串行；`agent/disposed` 调 `end_session`（幂等，证据 L320–325）。除销毁外还有两条结束路径：真实新窗口后主动 `end_session` 归还前台（约束二第 5 条），以及驱动 `idle_expires_in_seconds: 300` 与 `profile_persists_after_session:false` 兜底回收。**不提供模型可调用的 `close` 动作**：靠模型自觉收尾不是机制，实例纪律由宿主生命周期负责。进程级最多 2 个实例，超出返回 `browser_busy`。不按“每个对话一个实例”：结束一段对话不结束实例（只有 Agent 销毁、真窗口归还前台、空闲回收会结束），这里的执行 Agent 指 DSH 原生 session；同一 Global 根跨聊天共用该执行 session，普通 single_thread 的不同聊天与独立子 Agent 不共享实例。截图归属使用可信配置中的产品 agentId（不是原生 sessionId），因此写入路径与启动期按配置 Agent 清理的路径一致；同一产品 Agent 的多执行 session 共享 20 张上限。销毁必须与本 Agent 的串行队列收口，防止在 prepare/动作执行中销毁后又残留新实例。

**D9：驱动版本与宿主前置显式探测、只报告不修复。**
启动后首次调用探测 `cua-driver --version`（要求 `0.38.x`，其他版本返回 `browser_driver_version_unsupported` 并拒绝执行）、`cua-driver status`（当前版本输出的是人类可读文本而不是 JSON，按退出码与 “daemon is running”/`permission mode` 文本判断；文本匹配失败时把该命令的原始输出片段（截断）一并放进错误，便于用户自查）、`permissions status --json`（Accessibility / Screen Recording 的结构化结果）。缺任何一项返回可操作的错误，不自动安装、不自动授权、不自动启动 daemon（启动 daemon 会改变机器状态并可能弹 TCC 提示）。驱动路径可由 `NANO_CUA_DRIVER` 覆盖，否则查 `PATH`；路径不可执行属于驱动探测（`probe()`，运行时一次），不进无 I/O 的静态守卫。

**D10：不新增 Feature，只做两项默认关闭的工具。**
Feature 会进入 `featureDependencies`，需要在 `src/IM/frontend` 增 i18n 标签并触发前端原型/配置页设计；而本能力的开关语义就是“这两个工具选不选”，与 `skill_view`、Goal 工具同一模式。拒绝备选：`browser_control` Feature（requires 两个工具）—— 收益只是设置页多一个合并开关，代价是前端面、i18n 与原型门禁，与首版范围不成比例。将来若需要“一键开关”，可在不改本设计身份/审批层的前提下补 Feature。

**D11：能力只在 macOS 注册，但注册本身不代表可用。**
`process.platform !== 'darwin'` 时完全不注册（设置页看不到，符合 spec 的不可用场景）；darwin 上总是注册，让用户在设置里能看到并选择，调用时再给出驱动/TCC 的具体缺口。这样既不扩平台承诺，也不会在驱动缺失时让用户面对一个“神秘消失的能力”。

## 接口与数据流

### 工具：`browser_read`

只读页面。第一次调用时，如果本 Agent 还没有实例**且 TurnGate 通过（本轮由用户发起，见约束二第 3 条）**，先 `browser_prepare`（`allow_launch:true` + `isolated_new`），再用 `list_windows {pid}` 选出唯一可 bind 的主窗口并登记 `(pid, window_id)`（约束五）；没有实例且不是用户发起的轮次 → `browser_launch_requires_user_turn`。之后每次读取都只解析已登记的主窗口并 bind 当前标签，返回有界页面文本；主窗口消失或无法证明身份时按约束五关闭自持实例并返回 `browser_session_lost`，不采纳其它窗口。

| 参数 | 类型 | 必填 | 语义 |
|---|---|---|---|
| `tab` | object | 否 | `{url?, title?, active?}` 匹配器；省略时取主窗口的 active 标签。多个匹配 → 拒绝；只在主窗口内匹配 |
| `window_id` | string | 否 | 仅用于确认目标；必须等于已登记主窗口，否则 `browser_window_not_registered` |
| `query` | string | 否 | 语义收窄（传给 `semantic_v2` 的 `query`） |
| `screenshot` | boolean | 否 | 是否保存一张视口截图；路径是 workspace 相对路径，`width/height` 是设备像素 |
| `max_chars` | integer | 否 | 文本上限，默认 8000，硬上限 20000 |

返回：`{read_id, tab:{url,title,active,window_id}, text, refs:[{ref,role,name,actions}], truncated, screenshot?:{path,width,height}, driver:{version}, events?:[], ignored?:[], foreground_released?:true}`。`foreground_released` 只在读动作期间出现真实新窗口并成功结束后返回。

### 工具：`browser_act`

改变页面状态。每个动作都要求带最近一次 `read` 的 `read_id`（`open` 除外），否则拒绝并要求先读。`open` 在没有实例时同样受 TurnGate 约束（请求所属层当轮不是用户发起 → `browser_launch_requires_user_turn`）。

| 参数 | 类型 | 必填 | 语义 |
|---|---|---|---|
| `action` | enum | 是 | `open` / `click` / `type` / `scroll` |
| `url` | string | `open` 必填 | 只接受 `http`/`https` |
| `read_id` | string | 除 `open` 外必填 | 最近一次读取的快照游标 |
| `ref` | string | `click`/`type` 必填；`scroll` 必填 | 最近一次读取返回的 ref；`click` 只能用 ref，不接受坐标；`scroll` 的锚点必须是声明 `scroll`/`pointer` 动作的 ref |
| `text` | string | `type` 必填 | 最长 4000 字符 |
| `replace` | boolean | 否 | 透传驱动的整段替换语义 |
| `delta_y` / `delta_x` | number | `scroll` 至少一个 | 滚动量（CSS px）；在 `ref` 元素处滚动 |
| `screenshot` | boolean | 否 | 是否保存动作后的视口截图；`scroll` 默认 `true`，其他动作默认 `false` |
| `window_id` | string | 否 | 仅用于确认目标；必须等于已登记主窗口 |
| `tab` | object | 否 | 同 `browser_read`；动作必须与 `read_id` 的标签一致 |

返回：`{action, read_id?, dispatched:true, observed:{url,title,active}, effect:"changed"|"unverifiable"|"unchanged", text_after?, screenshot?, events?:[], ignored?:[], foreground_released?:true}`。`effect` 只表达“我们回读到了什么”，不表达业务成功。

没有 `close` 动作：实例由宿主在 Agent 销毁、真实新窗口后归还前台、或驱动 300 秒空闲回收时结束。

### 调用时序（以 ref 点击为例）

```text
model → browser_read {}
  TurnGate（打开中的轮次里最近人类发言 ≤300s？子 Agent 上溯到非子 Agent 祖先）→ 无实例则 prepare → 登记主窗口 → bind → snapshot semantic_v2
  → 返回 read_id=R1、tab(url,title,active,window_id)、refs
model → browser_act {action:"click", read_id:R1, ref:"p12:3"}
  static guard → NanoApproval（interactive 才有卡片）→ bind（新 target/tab）→ 选主窗口
  → 校验 read_id 仍是该标签最新读取、URL 未变
  → browser_click {target_id,tab_id,ref,delivery_mode:"background"}
  → 回读（bind+snapshot）→ 窗口集合检查
  → 真窗口？end_session 归还前台 → 返回 foreground_released + event
model → browser_read {}（需要更多内容时；若实例已因真窗口结束，需要新的用户轮次）
```

### 错误分类

| code | 触发 | 模型应做什么 | 可重试 |
|---|---|---|---|
| `browser_platform_unsupported` | 非 macOS | 告知用户此节点不支持 | 否 |
| `browser_driver_unavailable` | 找不到可执行文件 | 告知安装位置/环境变量 | 否 |
| `browser_driver_version_unsupported` | 版本不是 0.38.x | 告知当前与期望版本 | 否 |
| `browser_driver_not_running` | daemon 未运行 | 告知需要启动驱动服务 | 否（不由我们启动） |
| `browser_permission_missing` | Accessibility / Screen Recording 缺失 | 告知缺哪项与授权入口 | 否 |
| `browser_arguments_invalid` | 参数形状不合法（含 scheme、click 无 ref、scroll 无 ref/delta） | 修正参数 | 是 |
| `browser_snapshot_stale` | `read_id` 过期 / ref 作废 / URL 已变 | 重新 `browser_read` | 是 |
| `browser_tab_ambiguous` | 主窗口内匹配到多个标签 | 提供更精确的 `tab` 或先读 | 是 |
| `browser_window_ambiguous` | 首次 prepare 后主窗口候选多于一个 | 报告并等待；不按顺序取第一个 | 是（重新读取时再判） |
| `browser_window_not_registered` | 请求的 `window_id` 不是已登记主窗口 | 用最近一次读取返回的 `window_id` | 否 |
| `browser_launch_requires_user_turn` | 需要新实例，但请求所属层不在场：轮次已结束、无真实用户消息、最近人类发言已超 300 秒在场窗口，或来源是 `schedule`/`heartbeat`/`task-execution`/`task-change` 及其派生的子 Agent；链断/环检测失败同样归此码 | 告知用户需要在对话里发起；不要重试开窗 | 否（本任务） |
| `browser_session_lost` | 原主窗口 bind 重试一次仍失败，已结束自持实例 | 重新读取；持续失败则报告 | 一次 |
| `browser_navigation_rejected` | 非 http(s) | 换合法地址 | 否 |
| `browser_driver_refused` | 驱动结构化 refusal（含 `browser_tab_not_found`、滚动锚点未声明 `pointer` 的 `browser_action_unavailable`、foreground 拒绝） | 按 hint 处理，不原样重试 | 视 code |
| `browser_driver_timeout` | 子进程超时 | 报告并说明页面状态未知 | 一次 |
| `browser_driver_malformed` | 空/非 JSON/缺字段 | 报告失败，不当成功 | 一次 |
| `browser_foreground_release_failed` | 真窗口后 `end_session` 重试一次仍失败（含 label/pid 预校验不符）；失败后该 Agent 进入需人工恢复，后续调用直接返回本错误，直到 `failedAt + 300s` 冷却到期（冷却期内所有调用直接拒绝，不新增“新实例成功清除”分支） | 请用户手动关闭该浏览器窗口；不再派发动作 | 否（自动） |
| `browser_unexpected_event` | 未分类窗口 | 结束本次调用；先把事件告知用户，再决定是否继续 | 否（自动） |
| `browser_busy` | 超过进程级实例上限 | 稍后再试或结束其他 Agent 的实例 | 是 |
| `NanoApprovalDenied` | 审批拒绝，含无人工出口（Global 根/子 Agent/无人值守回退）被拒 | 说明被拒绝；需要用户确认时请在单聊里发起 | 否 |

### 身份与事件判定规则（实现口径）

| 判定对象 | 稳定依据 | 只在本调用内有效 | 不确定时 |
|---|---|---|---|
| 主窗口 | `(pid, window_id)`，pid 必须来自本 Agent 的 `browser_prepare` 结果；每实例只登记一个（约束五） | `target_id` | 无候选 → `browser_session_lost`；多候选 → `browser_window_ambiguous`；非登记窗口 → `browser_window_not_registered` |
| 标签 | 同一次 bind 结果里的 `url` + `title` + `active` 三元匹配，只在主窗口内 | `tab_id` | 多匹配 → `browser_tab_ambiguous`；零匹配 → `browser_tab_not_found` |
| 元素 | 最近一次读取的 `ref`（`p<snapshot>:<index>`） | 旧快照即作废 | ref 失效 / 页面 URL 变化 → `browser_snapshot_stale` |
| 读取游标 | 我们铸造的 `read_id`（单调、按会话） | 只对产生它的标签/URL 有效 | 与当前 bind 不一致 → `browser_snapshot_stale` |
| 新窗口事件 | bind 成功 + 至少一个 `http(s)` tab | 窗口集合只在本调用内比较 | 见错误分类（真窗口 / 噪声 / 未分类）；新窗口不登记为主窗口 |

判定顺序固定为：窗口归属 → bind（`binding_quality` 必须 `exact`）→ 标签匹配 → URL/`read_id` 一致性 → 动作；任何一步不满足即返回对应错误码，不进入动作。

### 审批与边界

| 动作 | 审批路径 | 确定性拒绝（先于审批/执行） |
|---|---|---|
| 读取页面 | `safeTools`（DSH 规则下仍走分类器）；首次启动实例另受 TurnGate 约束 | 非 macOS；目标不是主窗口；`browser_launch_requires_user_turn`；文本/ref 超限 |
| 打开 http(s) 页面 | 分类器；interactive 可转人工，其余会话按 D7 出口 | `file://` 与其他 scheme；空 URL；`browser_launch_requires_user_turn` |
| 点击元素（ref） | 分类器；interactive 可转人工 | 无 ref；`read_id` 过期；标签不唯一 |
| 输入文字 | 分类器；interactive 可转人工 | 无 `read_id`/ref；文本超长；目标不是可编辑元素（由驱动拒绝后原样回传） |
| 滚动页面 | 分类器；interactive 可转人工 | 无 `delta`；无 ref 锚点 |

无人值守回退不放行：`browser_act` 在 `unattended` 路由下，分类器要求人工时一律拒绝（不读 `unattendedFallback`）。Global 根与子 Agent 没有人工卡片，分类器要求人工时同样拒绝；模型应改为向用户说明“请在单聊里确认这一步”。

产品边界（不是驱动能力边界，写进工具描述与审批文案）：不登录、不提交表单、不下载、不上传、不处理 JS 对话框、不操作地址栏与浏览器界面、不执行自主脚本。边界靠“动作集 + 审批 + 模型指导”三层共同保证；我们不假装能检测页面语义上的“提交”。

### 失败与恢复

- **只重建只读前置，不重放动作**：bind 失败或 `browser_tab_not_found` 时允许“重新 bind 一次再判定”，但已经派发的 click/type/scroll 绝不自动重放（页面状态未知，重放可能产生第二次副作用）。
- **超时**：杀子进程并返回 `browser_driver_timeout`，明确“页面状态未知”；只允许一次由模型显式发起的重新读取。
- **实例缺失但需要启动**：TurnGate 不通过 → `browser_launch_requires_user_turn`，不启动、不重试开窗；TurnGate 通过 → 允许重新 `browser_prepare` 一次；连续两次失败即停止并报告，不循环重建。
- **会话丢失**：`browser_session_lost` 后清空本地登记；下一次调用按上一条重新 prepare（同样受 TurnGate 约束），旧 `read_id` 一律 stale。
- **未分类事件**：结束本次调用、返回窗口证据与模型可见指导（先告知用户再决定是否继续）；不自动重试、不自动忽略，也不声称宿主“停止批次”。
- **前台归还失败**：真实新窗口后 `end_session` 失败（含 label/pid 预校验不符）→ 重试一次；仍失败返回 `browser_foreground_release_failed`，请用户手动关闭，并让该 Agent 进入需人工恢复状态——后续调用不派发驱动动作、直接返回该错误，直到 `failedAt + 300s` 冷却到期（惰性清除，不做 pid 探测）；冷却期内 prepare 也被拒绝，所以不需要“新实例成功收尾清除状态”的分支。兜底是驱动 300 秒空闲回收。
- **驱动拒绝**：结构化 refusal 原样映射为 `browser_driver_refused`（保留 code 与 hint），由模型按 hint 处理；`background` 下被拒（如需要前台的路径）不得自动改 `foreground` 重试。
- **审批拒绝**：返回 `NanoApprovalDenied`，不重试、不换工具绕过；需要用户确认时，模型说明“请在单聊里发起这一步”，由用户决定是否改变任务方向。
- **进程/Agent 销毁**：`end_session` 幂等；截图不随实例结束或 Agent 销毁删除，只按 TTL 与数量上限在写入时清理（进程启动时补一次有界清理：只扫已配置 Agent workspace 下的 `.nanoassistant/browser/<agentId>/`，失败不阻塞启动）；进程崩溃时驱动按 300s 空闲回收实例，本地状态随进程消失，不需要持久恢复。

### 驱动工具白名单

只允许调用：`browser_prepare`、`get_browser_state`、`browser_navigate`、`browser_click`、`browser_type`、`browser_pointer`（仅 `action:"scroll"`）、`list_windows`（带 `pid`）、`end_session`、`status`、`permissions status`。其余（`run_script`、`run_steps`、`page`、`hotkey`、`type_text`、`press_key`、`bring_to_front`、`launch_app`、`browser_download`、`browser_set_input_files`、`browser_select`、`browser_dialog`、`clipboard_*`、`set_value`、`kill_app`、`set_window_frame`、`start_recording`）在客户端里没有调用入口，测试断言这一点。

## Agent Context 影响

- **Consumer**：节点的 Agent 模型；但可用面随会话类型不同——interactive 单聊可完整使用（需人工时出卡片）；Global 根与子 Agent 只有分类器放行时可用（无卡片）；无人值守轮次不能新开实例，能复用已有实例时只读始终可用，页面动作仅在该动作被分类器明确放行时执行（不读 `unattendedFallback`）。工具描述与错误文本必须让模型知道这一点。
- **Before / After**：之前模型没有任何“看/动页面”的能力，只能用 `web_fetch` 取静态 HTML；之后模型能读渲染后的页面并逐次操作，但每次动作都需要一次新的读取游标，且首次实例与真窗口受前台归还约束。
- **Context Lifecycle**：
  - 工具描述必须自包含可操作语义：`read_id` 的生命周期、ref 一次性、只接受 ref（无坐标）、滚动以 ref 锚定、滚动结论要看截图（并用 `read_image` 读 workspace 相对路径）、噪声不算失败、失败码含义、前台承诺原句。不能依赖模型“记住”设计文档。
  - 结果有界：文本默认 8000 字符、ref 列表截断、截图只给路径；大页面靠 `query`/`max_chars` 收窄，不把整页塞进上下文。
  - 页面内容不长期持久化、不跨会话继承：实例结束即丢页面状态；截图只是临时证据（TTL 1 小时、最多 20 张，只在写入时清理 + 启动期有界补清，不随 Agent 销毁删除），不写 Memory/Skill，不进 Dreaming 材料。
  - 与压缩/换窗的关系：工具结果是普通 tool result，遵守既有裁剪；`read_id` 不跨上下文窗口承诺有效（新窗口后必须重新读）。
- **Interactions**：审批分类器看到的是“参数 + 会话里最近一次读取的页面文本 + 用户原话”，不额外注入页面全文；`browser_read` 进入 `safeTools` 后不再重复走分类器（DSH 规则下仍走），但它的首次 `prepare` 由 TurnGate 决定，不靠审批。会话类型决定 `browser_act` 的出口（D7），错误文本必须把“为什么没执行、下一步该找谁”说清楚。
- **Validation**：单测断言两条工具描述的必含句（承诺原句、read_id/ref 生命周期、只接受 ref 不接受坐标、截图用 `read_image` 读、不登录/不提交/不下载、噪声与失败区分、非用户发起轮次（含任务续跑）、超窗（最近人类发言超过 300 秒）、轮次已结束与后台委派不能新开实例）；断言结果为有界结构、截图路径在该 Agent workspace 内；断言未选择时不注册到可调用视图（`ToolSelection` 行为复用现有测试面）。

## 契约层增量 (delta-spec)

- Agent 能力与审批：`docs/specs/gateway/agent-capabilities.md` → [delta](specs/gateway/agent-capabilities.md)（ADDED：默认关闭的浏览器页面能力、自持实例与前台承诺/首次启动边界、身份不确定时拒绝执行、按会话类型的审批出口、画面证据与读数口径）。
- IM 节点/配置展示：no spec delta（工具由既有能力目录自动列出，默认态由 node 投影计算；IM 前端不改）。
- 其它包：no spec delta。

## 风险与回退

| 风险 | 可能性 | 影响 | 处置 |
|---|---|---|---|
| 页面脚本开新窗口把前台抢走（实测 ≥4 秒不恢复，直到 `end_session`；无人干预上界约 300 秒，证据 L549–554、L85、L325） | 中 | 中（打断用户输入；最坏约 5 分钟） | 首次启动只允许在场窗口内（打开中的轮次 + 最近人类发言 ≤300s）的用户轮次与其同步委派；真窗口后回读完成即 `end_session` 归还前台（失败重试一次；仍失败则该 Agent 进入需人工恢复，后续调用直接报错）；不承诺时长、不做自动恢复；`run_script` 类入口关闭，避免放大 |
| 无人值守残留：无人在场时，分类器明确放行的页面动作仍会执行 | 低 | 中（无人看着时产生页面副作用） | 只有用户轮次（含该轮次派生的子 Agent）能新开实例，残留窗口仅限最近一次用户轮次后约 5 分钟内；`unattendedFallback` 不参与放行；不改分类器判定 |
| 驱动升级改变 id 重铸/`in_viewport`/事件文案行为 | 中 | 高（点错页面/读数失真） | 版本钉 0.38.x；升级需重跑本 design 的“五条硬约束”验证清单；契约测试覆盖分类与身份规则 |
| 语义快照定位偏差导致点到相邻元素 | 中 | 中 | 只接受最新 ref/`read_id`；动作后回读并返回 `effect`；v1 不接受坐标，避免“看着点”的偏移 |
| `ref` 锚点滚动只覆盖普通页面 pointer ref（V5 已有实测） | 中 | 中 | 产品节点仍需补证据；嵌套/水平滚动不宣称通过，失败不得退回坐标 |
| 页面内 `browser_type` 只覆盖普通 textbox（V1 已有实测） | 中 | 中 | 产品节点仍需补证据；富文本/受控组件不宣称通过 |
| 审批把 ref 当无意义字符串 | 中 | 中 | 强制“先读后做”，让页面文本进入审批可见的会话；`browser_act` 不自动放行（含无人值守回退） |
| 驱动/daemon 崩溃或 TCC 被撤销 | 低 | 中 | 明确错误码 + 一次重建；不自动修复系统状态 |
| 多 Agent 并发产生多个 Chrome 实例 | 低 | 中 | 每 Agent 一个 label、进程级上限 2、串行；不使用 AppleScript 路线 |
| 大页面文本撑爆上下文 | 中 | 低 | 文本/ref 上限、`query` 收窄、截图只给路径 |
| 用户误以为“独立实例=不会影响我的浏览器” | 中 | 低 | 文案只说“独立 profile、独立窗口”，不暗示 app 级沙箱（证据 L353–356） |
| 截图目录被写爆或残留页面内容 | 低 | 低 | 只写该 Agent workspace 的 `.nanoassistant/browser/<agentId>/`（解析后前缀校验）；每 Agent 最多 20 张、TTL 1 小时，只在写入时按 TTL/上限清理，不随实例结束或 Agent 销毁删除 |

回退：能力默认关闭，用户取消选择即停止暴露；代码层回退为移除 `BrowserControl` 安装与 `defaultOff` 条目，无数据、无配置、无迁移需要。驱动是外部依赖，回退不影响宿主。

## 一次性部署迁移

无。

运行前提（不是迁移，写在 Runbook）：宿主已安装 `cua-driver 0.38.x`、已授予 Accessibility 与 Screen Recording、驱动 daemon 正在运行。本 unit 不安装、不授权、不启动 daemon。

## Runbook for Reviewer

| 服务 | 停止命令 | 启动命令 | 健康检查 |
|---|---|---|---|
| 无新增常驻服务（工具注册在既有 node runtime 进程内，随 node 重启生效） | `./scripts/e2e-down.sh --wt <绝对 worktree 路径>` | `./scripts/e2e-up.sh --profile daily --wt <绝对 worktree 路径>` | `e2e-up.sh` 就绪后 IM health 通过、目标 owner 节点 online；工具列表出现两项浏览器工具 |

**Review 驱动方式**：端到端真栈；本 unit 不改客户端界面（设置页按既有能力列表自动多出两项工具），但用户可观察行为只在真实 Agent 对话里出现，因此 reviewer 用 Web IM 聊天真实驱动 Agent，不用接口替代。

**验收前置**：

- macOS 节点，Chrome 已安装；`cua-driver 0.38.0` 已安装（默认 `~/.local/bin/cua-driver`，或 `NANO_CUA_DRIVER` 指定）且 `cua-driver permissions status --json` 显示 accessibility/screen_recording 均为 true、`cua-driver status` 显示 daemon 运行。
- 本地夹具页：`python3 -m http.server 8765 --bind 127.0.0.1` 于 `/tmp/desktop-verify`（`page.html` 含按钮/计数器/长列表/`target=_blank`/`window.open` 按钮），因为 `browser_navigate` 拒绝 `file://`。
- 在 Agent 设置里显式勾选两项浏览器工具并保存；未勾选时先验证“能力不可用”场景。
- 审批与边界旅程在 **interactive 单聊**执行；无人值守与无人工出口的检查分别用一次 `schedule`（或 `heartbeat`）轮次与一次 Global 根/子 Agent 轮次执行。
- 验证结束后执行 `e2e-down.sh`，并确认驱动实例已结束（`cua-driver sessions list --json` / `ps`）、用户自己的 Chrome 窗口未被波及。

## Milestones

进实施前必须先完成下面 6 项本机验证（可由实施者执行；不通过就按“失败处置”改范围，不允许带着未验证动作直接进 M1 的验收）。建议顺序 **V2 → V1 → V5 → V4 → V6 → V3**：先跑决定发布与否（V2）与范围（V1/V5/V4）的项。验证时用户可能正在使用机器，需在结果里如实记录当时的干扰。

| # | 验证 | 通过标准 | 失败处置 |
|---|---|---|---|
| V1 | 页面内 `browser_type`（后台写入 + DOM 回读 + 前台 app 不变） | 在夹具页输入框写入文本；回读 `value` 与输入一致；全程前台 app 仍是用户原 app；`delivery_mode:"background"` | 首版移除 `type`：同步删除 spec 场景/范围中的输入、delta 对应描述、M1 范围与 reviewer 旅程第 3 条；不声称“输入可用” |
| V2 | 真窗口后 `end_session` 是否把前台还给用户 app | 至少 2 次采样：`window.open` 弹窗出现 → `end_session` 后前台回到原 app | 不得以“披露”代替上界：在找到可验证的归还手法前不发布该能力；备选分支“每次可能开窗的动作前显式征得用户同意”需另立同意流决策，**本 unit 不实现** |
| V3 | `browser_prepare` 首次启动的前台行为重测 | ≥3 次独立启动，记录启动前/后 0.5s/2s 的前台 app；结论只用于措辞与限制记录 | 结果不一致时保留“可能”措辞（现状），不影响范围；连续 3 次都不抢前台也不得删掉该披露 |
| V4 | 主窗口与弹窗的区分（同 pid 多窗口） | prepare 后唯一 `binding_quality: exact` 窗口被登记（允许初始 `about:blank`；http(s) 仅用于新窗口事件分类）；`window.open` 后主窗口登记不变、弹窗不被采纳；原主窗口不可 bind 而仅剩弹窗时亦不采纳，按失败关闭自持实例 | 若 prepare 时就有多个可 bind 的浏览器窗口 → 保持 `browser_window_ambiguous` 拒绝；需要窗口选择 UI 则另立 unit，不在本 unit 猜测 |
| V5 | `ref` 锚点滚动（`browser_pointer` scroll + ref） | 用最近一次读取的 ref 滚动成功；截图前后对照可见位移，且回读 `in_viewport` 至少同向变化（旁证，不替代截图）；前台不变 | 首版移除 `scroll`：同步 spec 场景/范围、delta、M1 范围与 reviewer 旅程；不得退回坐标滚动 |
| V6 | 截图证据链：workspace 相对路径可被 `read_image` 读取 | 在 `.nanoassistant/browser/<agentId>/` 写入一张视口截图，以该 workspace 相对路径调用 `read_image` 能读到文件内容（一次直接工具调用或最小 agent 轮次即可观测） | 若 `read_image` 读不到该路径，把截图根目录改到 V6 实测可读、且仍在该 Agent workspace 内的位置（保留 `resolve` 后前缀校验），不得落 `/tmp`、node home 或仓库；并同步 spec/design 的文案 |

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-page-actions | 页面内动作工具与边界 | V1–V6 完成 | — | `packages/dsh-integration/src/browser/**`、`src/features/browser-control.ts`、`src/index.ts`、`src/capabilities.ts`、`src/policy/approval.ts`（含抽出的 `src/policy/turn.ts` 当轮输入判定）、`apps/node/src/capabilities.ts`、相关测试 | 见下 |

**M1 退出标准**

`[reviewer]` 用户旅程（真实产品对话，默认在 interactive 单聊执行；另注明会话类型的项除外）：

1. 默认关闭：新建与既有 Agent 的工具列表里两项均未选中；未选中时要求 Agent 操作浏览器，它明确说明没有该能力，且没有浏览器窗口出现。
2. 独立实例：启用后让 Agent 打开公开页面并读取，用户自己的 Chrome 窗口与标签数量不变；读到的内容不含用户已登录页面；任务结束或空闲后实例消失。
3. 页面内动作与前台（V1/V5 通过后加入输入/滚动；实例启动后的）导航、读取、点击期间用户前台应用不变；页面 `window.open` 场景下新窗口可能出现并短暂占前台，Agent 结果说明发生了新窗口，并在回读后结束实例、前台回到用户应用（V2 通过后可观察前台 app 恢复）。
4. 噪声与事件：地址栏建议/翻译气泡类弹层出现时任务继续、不报失败；真实新窗口被报告；无法判断时结束本次动作并说明。
5. 身份：页面用 `target=_blank` 开新标签后，后续点击/输入落在正确页面；构造同 url/同标题两个标签时 Agent 拒绝执行并说明；页面 `window.open` 弹窗不被当成新的操作目标。
6. 审批与边界（interactive 单聊）：拒绝一次动作后页面无变化、结果说明被拒绝；要求登录/提交表单/下载时被拒绝并说明。
7. 不可用：在未授权/未运行/版本不符的机器上，用户看到具体缺口，且没有窗口被打开。
8. 画面证据：Agent 声称滚动到位/元素可见时附带截图（workspace 相对路径，可由 `read_image` 读到），结论与画面一致；截图落在该 Agent workspace 的 `.nanoassistant/browser/<agentId>/`（评审只核对目录与当前张数；TTL 与 20 张上限由 worker 测试注入旧时间戳验证）。
9. 无人工出口：在 Global 根会话或子 Agent 里，需要人工确认的动作被拒绝且没有审批卡片，模型说明“请在单聊里确认”；在定时/心跳/任务续跑轮次（含其派生的子 Agent）里，没有实例时不会新开窗口（`browser_launch_requires_user_turn`）；用户轮次里被委派的子 Agent 仍可新开实例。

`[worker]` 实现与验证证据：

1. 驱动客户端单测：版本/daemon/权限探测（status 文本匹配失败时错误带原始输出片段）；非 0 退出、空 stdout、非 JSON、缺字段 → `browser_driver_malformed`；超时杀进程；spawn 不经过 shell。
2. 身份单测（用录制 fixture，不依赖真实浏览器）：连续 bind 返回不同 id 时每次都用新 id；标签匹配按 url/title/active；多匹配 → ambiguous；index 不参与判定；`read_id` 过期/URL 变化 → stale。
3. 窗口登记单测：初次 prepare 唯一 exact 候选（包括 about:blank）→ 登记；零个 → `browser_session_lost`；多个 → `browser_window_ambiguous`；请求非主窗口 → `browser_window_not_registered`；弹窗出现后主窗口不变；原主窗口 bind 丢失、仅剩 http(s)/about:blank 弹窗时不得提升弹窗，结束自持实例、旧 read_id 失效。
4. 事件分类单测（有序决策树）：真窗口（bind 成功 + http(s)）、chrome 噪声（bind 失败 + 无 target/URL + 固定 UI 尺寸 + 空/自带标题）、未分类（bind 失败但噪声证据不完整；bind 成功但 URL 非 http(s)）三组 fixture 的判定与 `events`/`ignored` 输出。
5. 参数/边界单测：`file://` 被拒；click 无 ref 被拒；参数 schema 不接受 `x`/`y`；scroll 无 ref/delta 被拒；超长文本被拒；非 darwin 不注册；`browser_act` 不含 `close`。
6. 审批接线：`browser_read` 命中 `safeTools` 路径；`browser_act` 不进入 safe/alwaysAllow/context 集；无人值守回退不放行（fixture 断言 escalate 在 `unattendedFallback:'allow'` 下仍 deny）；拒绝返回 `NanoApprovalDenied` 且 execute 未被调用。
7. TurnGate（按来源层 + 在场窗口，全部用录制事件 fixture、无浏览器）：本会话无人类消息且无实例 → `browser_launch_requires_user_turn` 且未调用 `browser_prepare`；人类消息 60 秒前且轮次打开 → 允许 prepare；人类消息 10 分钟前（长轮次末端委派）→ 拒绝；父轮次已关闭（`turn/end`）而后台子 Agent 仍在跑 → 拒绝；`heartbeat`/`task-execution` 祖先 → 拒绝；链断（父会话不在 `ctx.agents`）→ 拒绝；构造环（`parentSession` 指向自身或互指）→ 拒绝且不无限循环；子 Agent 自身 seed source 形状不参与判定（子轮次 `kind:'user'` 无身份字段 + 人类父轮次仍在 300 秒窗口内 → 允许）；已有实例时非用户轮次可只读。直接输入的来源谓词继续复用 `isHumanSource`，审批路由的 `currentTurnInputs` 行为不变。补 Global 真形状 fixture：仅系统 Inbox wake 拒绝；本进程 live Inbox 中新鲜、完整、直接 participant 真人输入允许根/同步子请求；原始时间过期/未来/缺失、restored、partial、observer、PA 代发、Agent/system 均拒绝；读取时刻不刷新原始时间。
8. 真实驱动 e2e（本机 0.38.0，隔离端口 8765 夹具）：prepare → navigate → read → ref click（计数器 0→1）→（V1 通过后）页面输入 →（V5 通过后）ref 锚点 scroll（截图前后对照）→ 宿主结束实例；全程 `delivery_mode:"background"`，不使用 `run_script`/`run_steps`/`hotkey`/`type_text`/`page`；记录一次点击与一次输入的端到端延迟（含多次 CLI spawn 的叠加），并说明同 Agent 串行排队时的超时口径。
9. 只写约定目录与截图生命周期：截图路径落在该 Agent workspace 的 `.nanoassistant/browser/<agentId>/`（解析后前缀校验，越界拒绝）；注入旧时间戳与超额文件后，下一次写入只按 TTL 1 小时与 20 张上限清理；启动期有界清理只扫已配置 Agent workspace 下的 `.nanoassistant/browser/<agentId>/`（不遍历 home/仓库，路径不存在或无法读时记录并继续，不阻塞启动）；实例结束（真窗口 `end_session`）与 Agent 销毁都不删除截图；仓库 worktree 无新增未跟踪产物。
10. 日志与结果不含页面正文、查询串、Cookie、绝对 home 路径等敏感内容（URL 只记 host）。
11. 工具描述包含约定必含句（承诺原句、首次读取可能打开窗口并短暂占前台、read_id/ref 生命周期、只接受 ref、截图用 `read_image` 读、不登录/不提交/不下载、噪声与失败区分、非用户轮次不能新开实例），并有断言。
12. `docs/development/agent-context-engineering.md` 要求的 Context 影响已按本 design 的 Consumer/Before-After/Validation 落地，并由 **code review 按 `agent-context-review` Implementation 模式**确认无未覆盖消费链（不新增独立门禁）。
13. 前台归还失败冷却（fake timer，无浏览器）：`end_session` 失败 → `browser_foreground_release_failed`；`failedAt + 300s` 内每次调用都直接返回同一错误且**零驱动调用**（断言 driver client 未被调用、不做 `ps` 探测）；把 fake timer 推到 300s 后状态清空、可再次按 TurnGate 决策；冷却期内 prepare 同样被拒绝（不新增“新实例成功清除”分支）。
14. 归还后的消费轮次锁：根/子请求按同一判定祖先 session+seq 拒绝新开（包括同轮新真人消息、新派 sibling）；新的合格祖先轮次可启动。异步回读期间超窗/祖先关闭仍记录请求开始的消费轮次；真实窗口与未分类窗口同现时仍先归还，错误带证据。窗口列表失败不得当无事件成功。
15. 原生执行 Agent 销毁与 prepare/动作串行收口，不残留实例；截图用产品 agentId 路径，启动 sweep 能清到同一路径，销毁不删除证据。

## 已知限制与未验证清单

- `delivery_mode:"foreground"` 全部分支未实测（会抢前台，本次按边界不执行）；本设计不使用它。
- `existing_profile` 接入未执行：当前驱动安装是 `standard` 权限模式，`browser_prepare` 的 existing-profile 需要显式启动授权（`--grant existing-profile` 或 embedding authorization host），普通 MCP/工具审批不能替代 profile 授权；本 unit 不实施该通道，spec 中的固定文案只在将来接入时使用。
- 页面内文字输入：**V1 已实测通过**（`delivery_mode:"background"` 写入 14 字符，DOM 回读 `value` 与输入一致，前台 app 未变）；验证只覆盖普通 `textbox`，`contenteditable`/富文本/受控组件未验证。
- `ref` 锚点滚动：**V5 已实测通过**（锚点必须声明 `scroll`/`pointer`），截图对照位移与 `delta_y` 一致；水平滚动与嵌套滚动容器未验证，不退回坐标滚动。
- 坐标点击不在 v1：读数不含元素几何、截图是设备像素，没有可用的 CSS px 坐标来源；不接受“按画面估算坐标”。
- 本能力 v1 实际是“用户发起轮次 + 最近约 5 分钟内可复用实例”的按需/对话内能力：实例空闲 300 秒即回收，定时、心跳、任务续跑轮次（含其派生的子 Agent）都不会新开实例，因此“每小时巡检页面”这类周期任务几乎拿不到实例。**长轮次末端委派**（人类发言已超过 300 秒在场窗口）与**后台委派**（父轮次已结束）同样拿不到实例，只复用已有实例；按层判定恢复的仅是同轮次、300 秒内的同步/前台委派。
- 多显示器、其它 Space、窗口在不同屏幕上的行为未验证；`window.open` 的前台占用在连续 4 次采样下 ≥4 秒，但未做时长分布；无人干预时驱动 300 秒空闲回收是兜底上界。
- iOS、Windows、Linux 未涉及；非 macOS 节点不注册能力。
- 真实登录态站点（需要账号的页面）未验证；独立 profile 意味着这些页面本来就不可达。
- 驱动 daemon 的启动/自动启动行为未验证：本 unit 只探测 `status`，不启动、不重启。
- `browser_prepare` 首次启动是否把浏览器带到前台，两轮验证结果不一致（第一轮 `foregrounded_window:false` 且前台未变，第二轮启动后前台变成驱动实例）；原因未定位，因此承诺里保留“首次接入可能短暂占前台”（V3 继续采样，但不因此删披露）。
- `continuation` 语义与跨调用有效性未验证；v1 不使用。
- `browser_dialog` / `browser_download` / `browser_select` / `browser_set_input_files` / `run_steps` 未执行且不在白名单。
- 截图与 `semantic_v2` 可见性约 2 倍的偏差只在本机 `deviceScaleFactor=2` 上量化，其它缩放比例未验证；因此规则是“以截图为准”，不是“按比例换算”。
- 前台承诺原句中的“短暂”没有时长证据：实测新窗口占前台 ≥4 秒直到 `end_session`。产品承诺按用户指定原句保留，但不得据此向用户解释具体秒数；可控的是“启动只发生在用户轮次”和“真窗口后主动归还”这两条机制。
