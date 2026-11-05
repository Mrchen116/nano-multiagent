# feat-720: 在用户的浏览器里操作页面（macOS 页面内动作） — 技术方案

> 对齐: [spec.md](spec.md) v1

## Changelog

## 现状分析

### 涉及范围

本 unit 在 DSH 节点 runtime 进程内新增一个浏览器控制能力，不新增服务、不新增持久化、不改 IM/PA/Channels。

| 位置 | 现状 | 本 unit 的处理 |
|---|---|---|
| `packages/dsh-integration/src/`（新增 `browser/`） | 无任何浏览器/桌面控制代码；全仓检索 `cua-driver` 无命中 | 新增驱动客户端、身份解析、事件分类、策略与工具注册 |
| `packages/dsh-integration/src/index.ts` | 装配 `NanoApproval`、`ProductBridge`、Workflow、Knowledge 等插件（L190–241）；`tools/pre-execute` 已有能力预留 hook（L229–238） | 在 `NanoRuntime` 构造期安装 `BrowserControl`，注册两项工具与一个静态参数守卫 |
| `packages/dsh-integration/src/capabilities.ts` | `defaultOff`（L16）决定未配置白名单的 Agent 默认看不到哪些工具 | 把 `browser_read`、`browser_act` 加入 `defaultOff` |
| `packages/dsh-integration/src/policy/approval.ts` | `safeTools`（L25）列出只读/低风险工具；`review()` 在此之后走分类器与人工分流（L104–153） | `browser_read` 进入 `safeTools`；`browser_act` 不进入任何自动允许集合 |
| `apps/node/src/capabilities.ts` | `projectCapabilities` 用排除清单计算工具 `default_on`（L50–55） | 两个新工具加入排除清单，设置页显示为默认未选 |
| `packages/product-contracts/src/capabilities.ts` | 新增能力通常做成 Feature（`featureDependencies`），Feature 依赖工具与 skill 存在 | **不新增 Feature**，只做两项独立工具（见决策 D10） |
| `apps/node/src/main.ts` | `RuntimeSupervisor` 为每个 partition 启动独立 DSH 子进程；节点主机为 macOS | 不改；能力跑在该进程内，直接与本机驱动通信 |

### 既有约束

- 执行运行时只能经 DSH 公开 exports 接入；不得 fork/patch 运行时，不得引入第二套 Agent Loop，节点与 DSH 之间仍是 stdio，不新增 HTTP 服务（`AGENTS.md` 架构红线）。
- 工具可见性由 `ToolSelection.restrict` 决定：`toolAllowlist === undefined` 时等于“除 `defaultOff` 外全部”，因此**新工具默认关闭必须进 `defaultOff`**，不能只靠文案提醒。
- 所有工具调用都经 `tools/pre-execute`：先经过 `CapabilityState.begin` 配置预留检查，再经 `NanoApproval.review`；`safeTools` 只对 `policy.rules !== 'dsh'` 生效，`dangerouslySkipPermissions` 会显式放行。
- 审批路由分 interactive / unattended / return_to_agent（`approval.ts` L76–83）；无人值守只按既有 `unattendedFallback` 处理，本 unit 不新增放行分支。
- 安全边界：不提交 secret、日志、截图缓存；截图只能落在 Agent workspace 的约定目录，不落仓库。
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

## 验证结论：四条硬约束

证据报告全文已逐字复制到 [evidence/desktop-verification.md](evidence/desktop-verification.md)（570 行，行号与本 design 引用一致）。原始报告与截图在 `/tmp/desktop-verify/`（`report.md`；截图 `shots/01-example-cdp.png`、`02-window-two-tabs.png`、`04-fixture-page.png`、`05-before-click.png`、`06-after-ref-click.png`、`07-after-xy-click.png`、`08-after-scroll.png`、`09-resample-after-settle.png`、`10-after-scroll2.png`），截图只登记路径，不入库。

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

**证据。** 第一轮所有 `delivery_mode:"background"` 动作前台 app 未变（L247–268）；第二轮 `browser_prepare` 启动时前台从 `Electron|49704` 变成驱动自己的 `Google Chrome|25324`（L543–549），与第一轮 `foregrounded_window:false` 不一致（L286–289 与 L547–549）。`window.open`（带 gesture）弹出真窗口后前台持续 ≥4 秒不恢复，直到 `end_session` 才回到用户 app（L549–554）。地址栏 AX 注入文本必须 `delivery_mode:"foreground"` 才会提交（L154–159、L184–190）。驱动文档层面：`bring_to_front` 明确不恢复原前台 app（L276–279），`hotkey`/`type_text` 的 foreground 分支只承诺“做这件事所需的短暂前置”。

**判断。** “不抢焦点”只在“页面内、background、不产生新窗口”这条路径上成立；“首次接入”和“页面自己开新窗口”都可能抢前台且我们无法阻止。承诺只能写成收窄后的那一句，且不能用它推导时长。

**实现约束。**

1. 产品文案使用 spec 里的原句；任何设计、工具描述、审批文案、错误说明都不得出现“绝不打扰用户”一类绝对表述（写入工具描述与 review 检查项）。
2. 我们只使用 `delivery_mode:"background"`；不提供、不透传 `foreground` 参数；不调用 `bring_to_front`/`hotkey`/`type_text`/`launch_app` 等会主动激活窗口的驱动工具。
3. 首次 `browser_prepare`（`allow_launch:true` + `profile.mode:"isolated_new"`）在结果里附一条固定说明：首次接入可能短暂占前台；这是唯一一次“启动即可能抢前台”的路径。
4. 页面动作后若分类出真实新窗口（见约束三），结果里必须说明“该窗口可能占用了前台”。**v1 不做自动恢复**：恢复需要我们把用户前台 app 重新激活，既无验证证据，也会在用户正在操作时与用户抢；列为已知限制，不写进承诺。
5. 不通过 `osascript`/System Events 采样前台 app：那会给节点进程引入新的 Automation 授权依赖，而检测“是否抢过前台”不是 v1 的产品承诺前提。

### 约束三：驱动分不清真窗口与浏览器 chrome 弹层

**证据。** 正常地址栏输入就报 `opened new window(s)`，实测多出来的是 1038×218、无标题、紧贴地址栏的 omnibox 建议下拉（L193–217、L531–535）；另有 284×87 的「翻译此页？」气泡（L464–465、L536）。真窗口是 `window.open(...,width,height)` 产生的 520×426，带独立 `target_id`、`url=popup.html`、`binding_quality:exact`（L460–477、L537）。`target=_blank` 只开新标签、不开窗口（L450–458、L538）。驱动把两类都归为同一句 `🪟 Action opened new window(s)`。

**判断。** 不能把驱动的事件文案当分类结果；否则正常输入就会触发“出现意外就停”的自杀式护栏（第一轮正是如此，L193–217）。分类必须由我们在 bind 层做，且必须有三态：真窗口 / chrome 噪声 / 未分类。

**实现约束。**

1. 每次可能产生窗口的动作后，用 `list_windows {pid}` 对比已知窗口集合；对每个新窗口调用 `get_browser_state {session, pid, window_id}` 做分类。
2. 判定表（实现直接按此写死并有单测）：
   - bind 成功（`binding_quality: exact`）、且至少一个 tab 的 `url` 是 `http(s)` → **真实浏览窗口**；记录事件，继续。
   - bind 失败或没有 target、没有 URL、窗口尺寸是固定 UI 尺寸（如 284×87 / 1038×218）、标题为空或是浏览器自带文案（翻译/建议）→ **chrome 噪声**；只计数与记录，不算失败、不重试。
   - 其余（包括“能 bind 但 URL 既非 http(s) 也非预期页面”，例如 `about:blank` 弹窗）→ **未分类**：停止本批次后续动作，返回 `browser_unexpected_event` 与窗口证据，不自动重试；由模型决定告知用户或重新读取。
3. 驱动响应里的 `opened new window(s)` 只作为“需要检查窗口集合”的提示，不直接决定事件类别。
4. 模型可见结果里区分 `events[]`（真实窗口）与 `ignored[]`（噪声，仅计数/尺寸/标题），避免模型把噪声当异常反复处理。

### 约束四：读数口径

**证据。** `semantic_v2` 的 `in_viewport` 与真实视口稳定差约 1.92 倍（≈`deviceScaleFactor=2`）：请求 1200 CSS px，`in_viewport` 只前进 13 行，而截图显示前进 25 行（L433–446）。两个 Chrome 实例并存时旧 `page` 工具直接报 `browser_applescript_process_ambiguous`（L479–485），`query_dom` 还要求 `window_id`。`browser_pointer` 缺 `ref`/`x`/`y` 时返回的是一句错误文本，包装层很容易吞成空对象（L486–489）。`browser_navigate` 拒绝 `file://`（L388–392）。

**判断。** 语义快照的可见性/滚动偏移只能当“大致方向”；位置类结论必须以截图为证据。结构化的 `effect: "unverifiable"`（点击返回，L404–407）意味着动作成功后必须回读，不能假设生效。

**实现约束。**

1. `read` 的文本结果只用于内容与元素定位；工具描述明确写“不要用可见性标签判断滚动位置/是否可见”。
2. 提供 `screenshot: true` 时把 CDP 视口截图保存到 workspace 约定目录并返回路径；凡是“滚到某处/元素可见”的结论要求模型同时引用截图。滚动动作的默认返回附一张截图（见接口）。
3. 不使用 `page`/`query_dom`；任何依赖 pid 归属的 AppleScript 路线一律不接。
4. 驱动客户端的失败口径：非 0 退出、空 stdout、无法解析 JSON、缺少预期字段 → `browser_driver_malformed`（带截断的原始输出片段），**一律不当成功**；`browser_pointer` 的 scroll 参数在发请求前校验，缺 `ref` 或 `x/y` 直接 `browser_arguments_invalid`。
5. `open` 只接受 `http`/`https`（`file://` 由我们提前拒绝，不依赖驱动报错）；本地夹具在验证里用 `127.0.0.1` 静态服务（证据 L388–392）。

## 架构总览

```text
Agent (DSH session)
   │  tool call: browser_read / browser_act
   ▼
tools/pre-execute
   ├─ CapabilityState.begin        （既有：配置保存期间的预留/收缩）
   ├─ BrowserPolicy.static         （本 unit：平台、参数、scheme、启用；纯同步，无 I/O）
   └─ NanoApproval.review          （既有：分类器 / 人工 / 无人值守）
   ▼
BrowserControl (per-Agent state, in-memory)
   ├─ TabIdentity   bind → 选标签 → 本次 target_id/tab_id → read_id/ref 校验
   ├─ EventClassifier  list_windows → bind → 真窗口/噪声/未分类
   └─ DriverClient  spawn `cua-driver call <tool> <json>`（无 shell）
        ▼
cua-driver daemon（宿主安装，0.38.x；TCC 身份 com.trycua.driver）
        ▼
driver-owned isolated Chrome（独立 profile；随会话/空闲结束）
```

前：Agent 没有任何桌面/浏览器控制面，只有网络读写（`web_search`/`web_fetch`）。后：新增两项默认关闭的页面级工具；没有新进程模型（驱动 daemon 是宿主既有依赖）、没有新 HTTP 服务、没有持久化、没有第二套循环。

## 关键决策

**D1：能力放在 `packages/dsh-integration` 的两个工具里，不新增服务、不新增 agent loop。**
工具是同步 request/response，一次调用最多产生“一次动作 + 一次回读 + 一次窗口检查”；不在我们这层做循环、条件编排或自动重试动作。备选（在 `apps/node` 另起浏览器服务、经 RPC 暴露给 DSH）会新增进程边界与协议，且与“节点只经 stdio 管 DSH”的现状相反；备选 MCP 连接会把驱动协议再包一层，收益只是省一次 spawn。

**D2：只通过 CLI `cua-driver call <tool> <json>` 调用驱动，直接读 stdout JSON。**
这是本次实测用过的路径（证据 L4–5），错误形状（refusal/hint）可原样转成结构化结果；不引入 MCP 客户端、不解析私有 socket 协议（未文档化，升级即碎）。spawn 使用参数数组、不拼 shell，避免 URL/输入文本进入命令解析；设置单次超时（默认 20s，导航 30s）与输出上限（截图走 base64，上限 32 MB），超时杀子进程并返回 `browser_driver_timeout`。

**D3：身份是“窗口 `(pid, window_id)` + 一次 bind 里的 `url`+`title`+`active`”，对外用 `read_id`。**
理由与四条实现约束见“约束一”。拒绝备选：缓存 `tab_id`（实测 3/3 次重铸）、按 `tabs[]` index 认标签（活跃/MRU 语义，实测新标签插到 index 0）、把 `continuation` 当稳定游标（驱动有该字段，但本次未验证语义与生命周期，v1 不用）。

**D4：窗口事件三分类，噪声不算失败，未分类停止。**
理由见“约束三”。这是把“出现意外就停”的安全护栏从“驱动说什么就停”改成“我们确认过才停”。拒绝备选：见 `opened new window(s)` 就停（第一轮实测会让正常输入杀死任务）、或见文案就忽略（会把真实弹窗吞掉）。

**D5：读数与回读口径以画面为准，空响应即失败。**
理由见“约束四”。点击/输入的驱动返回是 `effect:"unverifiable"`，因此动作成功后做一次有界回读（页面文本 + 可选截图），结果里区分“驱动已派发”“回读确认变化”“未回读”。拒绝备选：相信 `effect`、或用 `in_viewport`/`omitted.offscreen` 推滚动位置。

**D6：前台只做披露，不做自动恢复；承诺以 spec 原句为上限。**
理由见“约束二”。不做自动恢复是因为没有验证过任何恢复路径，而且恢复本身是一次前台激活，会在用户正在打字时二次打扰；因此把“新窗口/首次接入可能短暂占前台”作为产品事实披露，而不是承诺“短”。`browser_prepare` 的前台不一致也说明“我们无法可靠控制它”。

**D7：审批分三层：静态守卫 → `NanoApproval` → 执行期身份/归属校验。**
- `browser_read` 允许进入 `safeTools`（只读、只能读本 Agent 自持实例、无文件与登录态）。它仍受下游 allow/deny 与配置预留约束。
- `browser_act` 不进入 `safeTools`/`alwaysAllowTools`/`contextTools`；默认由分类器判定，interactive 下可转人工。唯一例外是用户显式开启 `dangerouslySkipPermissions`（既有产品语义，不为此新增分支）。
- 静态守卫在 `tools/pre-execute` 提供无 I/O 的确定性拒绝：非 darwin、`open` 的 scheme 不是 http(s)、click 既无 ref 也无坐标、scroll 无 `delta`、输入文本超长（默认 4000 字符）、驱动路径不可执行。执行期再做“是不是我们的 pid/窗口”“read 之后页面是否变了”“标签是否仍唯一”。
- `browser_act` 的审批文案与工具描述必须写明：不登录、不提交表单、不下载；需要改动页面状态的动作要先读后做。

**D8：每个 Agent 一个驱动 session，串行、随 Agent 销毁结束。**
session label 随机生成（`nano-br-<8hex>`），同进程内按 agentId 复用；所有动作在同一 label 下串行；`agent/disposed` 调 `end_session`（幂等，证据 L320–325），异常退出靠驱动 `idle_expires_in_seconds: 300` 与 `profile_persists_after_session:false` 回收。进程级最多 2 个实例，超出返回 `browser_busy`。不按“每个对话一个实例”：一个 Agent 的多个会话应看到同一页面上下文，且驱动的 lifecycle session 本来就以 label 为界。

**D9：驱动版本与宿主前置显式探测、只报告不修复。**
启动后首次调用探测 `cua-driver --version`（要求 `0.38.x`，其他版本返回 `browser_driver_version_unsupported` 并拒绝执行）、`cua-driver status`（当前版本输出的是人类可读文本而不是 JSON，按退出码与 “daemon is running”/`permission mode` 文本判断）、`permissions status --json`（Accessibility / Screen Recording 的结构化结果）。缺任何一项返回可操作的错误，不自动安装、不自动授权、不自动启动 daemon（启动 daemon 会改变机器状态并可能弹 TCC 提示）。驱动路径可由 `NANO_CUA_DRIVER` 覆盖，否则查 `PATH`。

**D10：不新增 Feature，只做两项默认关闭的工具。**
Feature 会进入 `featureDependencies`，需要在 `src/IM/frontend` 增 i18n 标签并触发前端原型/配置页设计；而本能力的开关语义就是“这两个工具选不选”，与 `skill_view`、Goal 工具同一模式。拒绝备选：`browser_control` Feature（requires 两个工具）—— 收益只是设置页多一个合并开关，代价是前端面、i18n 与原型门禁，与首版范围不成比例。将来若需要“一键开关”，可在不改本设计身份/审批层的前提下补 Feature。

**D11：能力只在 macOS 注册，但注册本身不代表可用。**
`process.platform !== 'darwin'` 时完全不注册（设置页看不到，符合 spec 的不可用场景）；darwin 上总是注册，让用户在设置里能看到并选择，调用时再给出驱动/TCC 的具体缺口。这样既不扩平台承诺，也不会在驱动缺失时让用户面对一个“神秘消失的能力”。

## 接口与数据流

### 工具：`browser_read`

只读页面。第一次调用会确保本 Agent 的隔离实例存在（必要时 `browser_prepare`，再用 `list_windows {pid}` 找到该实例的顶层窗口并登记 `(pid, window_id)`），然后 bind 当前窗口并返回有界页面文本。之后每次读取都从已登记窗口集合里解析目标窗口；集合为空或实例已消失时重新 prepare。

| 参数 | 类型 | 必填 | 语义 |
|---|---|---|---|
| `tab` | object | 否 | `{url?, title?, active?}` 匹配器；省略时取 active 标签。多个匹配 → 拒绝 |
| `query` | string | 否 | 语义收窄（传给 `semantic_v2` 的 `query`） |
| `screenshot` | boolean | 否 | 是否保存一张视口截图到约定目录 |
| `max_chars` | integer | 否 | 文本上限，默认 8000，硬上限 20000 |

返回：`{read_id, tab:{url,title,active,window_id}, text, refs:[{ref,role,name}], truncated, screenshot?:{path,width,height}, driver:{version}, events?:[], ignored?:[]}`。

### 工具：`browser_act`

改变页面状态。每个动作都要求带最近一次 `read` 的 `read_id`（`open` 除外），否则拒绝并要求先读。

| 参数 | 类型 | 必填 | 语义 |
|---|---|---|---|
| `action` | enum | 是 | `open` / `click` / `type` / `scroll` / `close` |
| `url` | string | `open` 必填 | 只接受 `http`/`https` |
| `read_id` | string | 除 `open`/`close` 外必填 | 最近一次读取的快照游标 |
| `ref` | string | `click` 二选一 | 最近一次读取返回的 ref |
| `x` / `y` | number | `click` 二选一 | CSS px 视口坐标，必须与 `read_id` 对应 |
| `text` | string | `type` 必填 | 最长 4000 字符 |
| `replace` | boolean | 否 | 透传驱动的整段替换语义 |
| `delta_y` / `delta_x` | number | `scroll` 至少一个 | CSS px；锚点默认取最近一次读取的视口中心，读不到则要求显式 `x/y` |
| `screenshot` | boolean | 否 | 是否保存动作后的视口截图；`scroll` 默认 `true`，其他动作默认 `false` |
| `tab` | object | 否 | 同 `browser_read`；动作必须与 `read_id` 的标签一致 |

返回：`{action, read_id?, dispatched:true, observed:{url,title,active}, effect:"changed"|"unverifiable"|"unchanged", text_after?, screenshot?, events?:[], ignored?:[]}`。`effect` 只表达“我们回读到了什么”，不表达业务成功。

`close`：结束本 Agent 的驱动 session（幂等），清空内存状态。

### 调用时序（以 ref 点击为例）

```text
model → browser_read {}
  ensure instance (probe → prepare if none) → bind → snapshot semantic_v2
  → 返回 read_id=R1、tab(url,title,active)、refs
model → browser_act {action:"click", read_id:R1, ref:"p12:3"}
  static guard → NanoApproval → bind（新 target/tab）→ 选标签
  → 校验 read_id 仍是该标签最新读取、URL 未变
  → browser_click {target_id,tab_id,ref,delivery_mode:"background"}
  → 回读（bind+snapshot）→ 窗口集合检查 → 返回
model → browser_read {}（需要更多内容时）
```

### 错误分类

| code | 触发 | 模型应做什么 | 可重试 |
|---|---|---|---|
| `browser_platform_unsupported` | 非 macOS | 告知用户此节点不支持 | 否 |
| `browser_driver_unavailable` | 找不到可执行文件 | 告知安装位置/环境变量 | 否 |
| `browser_driver_version_unsupported` | 版本不是 0.38.x | 告知当前与期望版本 | 否 |
| `browser_driver_not_running` | daemon 未运行 | 告知需要启动驱动服务 | 否（不由我们启动） |
| `browser_permission_missing` | Accessibility / Screen Recording 缺失 | 告知缺哪项与授权入口 | 否 |
| `browser_arguments_invalid` | 参数形状不合法（含 scheme、坐标、scroll 锚点） | 修正参数 | 是 |
| `browser_snapshot_stale` | `read_id` 过期 / ref 作废 / URL 已变 | 重新 `browser_read` | 是 |
| `browser_tab_ambiguous` | 匹配到多个标签 | 提供更精确的 `tab` 或先读 | 是 |
| `browser_session_lost` | bind 失败且重建一次仍失败 | 重新读取；持续失败则报告 | 一次 |
| `browser_navigation_rejected` | 非 http(s) | 换合法地址 | 否 |
| `browser_driver_refused` | 驱动结构化 refusal（含 `browser_tab_not_found`、foreground 拒绝） | 按 hint 处理，不原样重试 | 视 code |
| `browser_driver_timeout` | 子进程超时 | 报告并说明页面状态未知 | 一次 |
| `browser_driver_malformed` | 空/非 JSON/缺字段 | 报告失败，不当成功 | 一次 |
| `browser_unexpected_event` | 未分类窗口 | 停下并说明，等模型决定 | 否（自动） |
| `browser_busy` | 超过进程级实例上限 | 稍后再试或关闭其他实例 | 是 |
| `NanoApprovalDenied` | 审批拒绝 | 说明被拒绝，不绕过 | 否 |

### 身份与事件判定规则（实现口径）

| 判定对象 | 稳定依据 | 只在本调用内有效 | 不确定时 |
|---|---|---|---|
| 窗口 | `(pid, window_id)`，pid 必须来自本 Agent 的 `browser_prepare` 结果 | `target_id` | 不在已注册实例内 → `browser_session_lost` |
| 标签 | 同一次 bind 结果里的 `url` + `title` + `active` 三元匹配 | `tab_id` | 多匹配 → `browser_tab_ambiguous`；零匹配 → `browser_tab_not_found` |
| 元素 | 最近一次读取的 `ref`（`p<snapshot>:<index>`） | 旧快照即作废 | ref 失效 / 页面 URL 变化 → `browser_snapshot_stale` |
| 读取游标 | 我们铸造的 `read_id`（单调、按会话） | 只对产生它的标签/URL 有效 | 与当前 bind 不一致 → `browser_snapshot_stale` |
| 新窗口事件 | bind 成功 + 至少一个 `http(s)` tab | 窗口集合只在本调用内比较 | 见错误分类（真窗口 / 噪声 / 未分类） |

判定顺序固定为：窗口归属 → bind（`binding_quality` 必须 `exact`）→ 标签匹配 → URL/`read_id` 一致性 → 动作；任何一步不满足即返回对应错误码，不进入动作。

### 审批与边界

| 动作 | 审批路径 | 确定性拒绝（先于审批/执行） |
|---|---|---|
| 读取页面 | `safeTools`（DSH 规则下仍走分类器） | 非 macOS；目标不在自持实例；文本/ref 超限 |
| 打开 http(s) 页面 | 分类器 / 人工 | `file://` 与其他 scheme；空 URL |
| 点击（ref 或坐标） | 分类器 / 人工 | 无 ref 且无坐标；`read_id` 过期；标签不唯一 |
| 输入文字 | 分类器 / 人工 | 无 `read_id`/ref；文本超长；目标不是可编辑元素（由驱动拒绝后原样回传） |
| 滚动 | 分类器 / 人工 | 无 `delta`；无锚点且读不到视口尺寸 |
| 关闭实例 | 分类器 / 人工 | 无可关闭实例（幂等返回） |

产品边界（不是驱动能力边界，写进工具描述与审批文案）：不登录、不提交表单、不下载、不上传、不处理 JS 对话框、不操作地址栏与浏览器界面、不执行自主脚本。边界靠“动作集 + 审批 + 模型指导”三层共同保证；我们不假装能检测页面语义上的“提交”。

### 失败与恢复

- **只重建只读前置，不重放动作**：bind 失败或 `browser_tab_not_found` 时允许“重新 bind 一次再判定”，但已经派发的 click/type/scroll 绝不自动重放（页面状态未知，重放可能产生第二次副作用）。
- **超时**：杀子进程并返回 `browser_driver_timeout`，明确“页面状态未知”；只允许一次由模型显式发起的重新读取。
- **会话丢失**：`browser_session_lost` 后结束本地状态，下一次 `browser_read` 重新 `browser_prepare`；连续两次失败即停止并报告，不循环重建。
- **未分类事件**：停止后续动作、保留窗口证据、把决定权交回模型/用户；不自动重试、不自动忽略。
- **驱动拒绝**：结构化 refusal 原样映射为 `browser_driver_refused`（保留 code 与 hint），由模型按 hint 处理；`background` 下被拒（如需要前台的路径）不得自动改 `foreground` 重试。
- **审批拒绝**：返回 `NanoApprovalDenied`，不重试、不换工具绕过；是否改变任务方向由模型向用户说明。
- **进程/Agent 销毁**：`end_session` 幂等；进程崩溃时驱动按 300s 空闲回收实例，本地状态随进程消失，不需要持久恢复。

### 驱动工具白名单

只允许调用：`browser_prepare`、`get_browser_state`、`browser_navigate`、`browser_click`、`browser_type`、`browser_pointer`（仅 `action:"scroll"`）、`list_windows`（带 `pid`）、`end_session`、`status`、`permissions status`。其余（`run_script`、`run_steps`、`page`、`hotkey`、`type_text`、`press_key`、`bring_to_front`、`launch_app`、`browser_download`、`browser_set_input_files`、`browser_select`、`browser_dialog`、`clipboard_*`、`set_value`、`kill_app`、`set_window_frame`、`start_recording`）在客户端里没有调用入口，测试断言这一点。

## Agent Context 影响

- **Consumer**：节点的 Agent 模型（含 Global/子 Agent 中选择了该工具的会话）。新增两条工具 schema，以及它们的结果与错误文本。
- **Before / After**：之前模型没有任何“看/动页面”的能力，只能用 `web_fetch` 取静态 HTML；之后模型能读渲染后的页面并逐次操作，但每次动作都需要一次新的读取游标。
- **Context Lifecycle**：
  - 工具描述必须自包含可操作语义：`read_id` 的生命周期、ref 一次性、坐标是 CSS px 视口坐标、滚动结论要看截图、噪声不算失败、失败码含义、前台承诺原句。不能依赖模型“记住”设计文档。
  - 结果有界：文本默认 8000 字符、ref 列表截断、截图只给路径；大页面靠 `query`/`max_chars` 收窄，不把整页塞进上下文。
  - 页面内容不持久化、不跨会话继承：实例结束即丢；不写 Memory/Skill，不进 Dreaming 材料。
  - 与压缩/换窗的关系：工具结果是普通 tool result，遵守既有裁剪；`read_id` 不跨上下文窗口承诺有效（新窗口后必须重新读）。
- **Interactions**：审批分类器看到的是“参数 + 会话里最近一次读取的页面文本 + 用户原话”，不额外注入页面全文；`browser_read` 进入 `safeTools` 后不再重复走分类器（DSH 规则下仍走）。
- **Validation**：单测断言两条工具描述的必含句（承诺原句、read_id/ref 生命周期、不登录/不提交/不下载、噪声与失败区分）；断言结果为有界结构；断言未选择时不注册到可调用视图（`ToolSelection` 行为复用现有测试面）。

## 契约层增量 (delta-spec)

- Agent 能力与审批：`docs/specs/gateway/agent-capabilities.md` → [delta](specs/gateway/agent-capabilities.md)（ADDED：默认关闭的浏览器页面能力、自持实例与前台承诺、身份不确定时拒绝执行）。
- IM 节点/配置展示：no spec delta（工具由既有能力目录自动列出，默认态由 node 投影计算；IM 前端不改）。
- 其它包：no spec delta。

## 风险与回退

| 风险 | 可能性 | 影响 | 处置 |
|---|---|---|---|
| 页面脚本开新窗口抢前台且不自动恢复（证据 L549–554） | 中 | 中（打断用户输入数秒） | 披露事件、不承诺时长、不做自动恢复；`run_script` 类入口关闭，避免放大 |
| 驱动升级改变 id 重铸/`in_viewport`/事件文案行为 | 中 | 高（点错页面/读数失真） | 版本钉 0.38.x；升级需重跑本 design 的“四条硬约束”验证清单；契约测试覆盖分类与身份规则 |
| 语义快照定位偏差导致点到相邻元素 | 中 | 中 | 只接受最新 ref/`read_id`；动作后回读并返回 `effect`；坐标动作同样绑定 `read_id` |
| 审批把 ref 当无意义字符串 | 中 | 中 | 强制“先读后做”，让页面文本进入审批可见的会话；`browser_act` 不自动放行 |
| 驱动/daemon 崩溃或 TCC 被撤销 | 低 | 中 | 明确错误码 + 一次重建；不自动修复系统状态 |
| 多 Agent 并发产生多个 Chrome 实例 | 低 | 中 | 每 Agent 一个 label、进程级上限 2、串行；不使用 AppleScript 路线 |
| 大页面文本撑爆上下文 | 中 | 低 | 文本/ref 上限、`query` 收窄、截图只给路径 |
| 用户误以为“独立实例=不会影响我的浏览器” | 中 | 低 | 文案只说“独立 profile、独立窗口”，不暗示 app 级沙箱（证据 L353–356） |
| 截图目录被写爆 | 低 | 低 | 只写 workspace `.nanoassistant/browser/`，每 Agent 保留最近 20 张，超限删除最旧 |

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
- 验证结束后执行 `e2e-down.sh`，并确认驱动实例已结束（`cua-driver sessions list --json` / `ps`）、用户自己的 Chrome 窗口未被波及。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| M1-page-actions | 页面内动作工具与边界 | — | — | `packages/dsh-integration/src/browser/**`、`src/features/browser-control.ts`、`src/index.ts`、`src/capabilities.ts`、`src/policy/approval.ts`、`apps/node/src/capabilities.ts`、相关测试 | 见下 |

**M1 退出标准**

`[reviewer]` 用户旅程（真实产品对话）：

1. 默认关闭：新建与既有 Agent 的工具列表里两项均未选中；未选中时要求 Agent 操作浏览器，它明确说明没有该能力，且没有浏览器窗口出现。
2. 独立实例：启用后让 Agent 打开公开页面并读取，用户自己的 Chrome 窗口与标签数量不变；读到的内容不含用户已登录页面；任务结束或空闲后实例消失。
3. 页面内动作与前台：导航、读取、点击、输入、滚动期间用户前台应用不变；页面 `window.open` 场景下新窗口可能出现并短暂占前台，Agent 结果说明发生了新窗口。
4. 噪声与事件：地址栏建议/翻译气泡类弹层出现时任务继续、不报失败；真实新窗口被报告；无法判断时停下说明。
5. 身份：页面用 `target=_blank` 开新标签后，后续点击/输入落在正确页面；构造同 url/同标题两个标签时 Agent 拒绝执行并说明。
6. 审批与边界：拒绝一次动作后页面无变化、结果说明被拒绝；要求登录/提交表单/下载时被拒绝并说明。
7. 不可用：在未授权/未运行/版本不符的机器上，用户看到具体缺口，且没有窗口被打开。
8. 画面证据：Agent 声称滚动到位/元素可见时附带截图，结论与画面一致。

`[worker]` 实现与验证证据：

1. 驱动客户端单测：版本/daemon/权限探测；非 0 退出、空 stdout、非 JSON、缺字段 → `browser_driver_malformed`；超时杀进程；spawn 不经过 shell。
2. 身份单测（用录制 fixture，不依赖真实浏览器）：连续 bind 返回不同 id 时每次都用新 id；标签匹配按 url/title/active；多匹配 → ambiguous；index 不参与判定；`read_id` 过期/URL 变化 → stale。
3. 事件分类单测：真窗口（bind 成功 + http(s)）、chrome 噪声（bind 失败 + 固定 UI 尺寸 + 空标题）、未分类（bind 成功但 URL 非 http(s)）三组 fixture 的判定与 `events`/`ignored` 输出。
4. 参数/边界单测：`file://` 被拒；click 无 ref 无坐标被拒；scroll 无锚点被拒；超长文本被拒；非 darwin 不注册。
5. 审批接线：`browser_read` 命中 `safeTools` 路径；`browser_act` 不进入 safe/alwaysAllow/context 集；拒绝返回 `NanoApprovalDenied` 且 execute 未被调用。
6. 真实驱动 e2e（本机 0.38.0，隔离端口 8765 夹具）：prepare → navigate → read → ref click（计数器 0→1）→ 坐标点击（1→2）→ scroll（截图前后对照）→ close；全程 `delivery_mode:"background"`，不使用 `run_script`/`run_steps`/`hotkey`/`type_text`/`page`。
7. 只写约定目录：截图路径落在 workspace `.nanoassistant/browser/`，保留最近 20 张；仓库 worktree 无新增未跟踪产物。
8. 日志与结果不含页面正文、查询串、Cookie、绝对 home 路径等敏感内容（URL 只记 host）。
9. 工具描述包含约定必含句（承诺原句、read_id/ref 生命周期、不登录/不提交/不下载、噪声与失败区分），并有断言。
10. `docs/development/agent-context-engineering.md` 要求的 Context 影响已按本 design 的 Consumer/Before-After/Validation 落地，并由独立 context review 确认无未覆盖消费链。

## 已知限制与未验证清单

- `delivery_mode:"foreground"` 全部分支未实测（会抢前台，本次按边界不执行）；本设计不使用它。
- `existing_profile` 接入未执行：当前驱动安装是 `standard` 权限模式，`browser_prepare` 的 existing-profile 需要显式启动授权（`--grant existing-profile` 或 embedding authorization host），普通 MCP/工具审批不能替代 profile 授权；本 unit 不实施该通道，spec 中的固定文案只在将来接入时使用。
- 页面内文字输入（`browser_type`）在本机验证中**未执行**：证据只覆盖了地址栏的 `type_text`（AX 路线）。实施时必须先补一条真实页面输入验证，再声称“输入可用”。
- 多显示器、其它 Space、窗口在不同屏幕上的行为未验证；`window.open` 的 ≥4 秒前台占用只在单次采样下观察，未做时长分布。
- iOS、Windows、Linux 未涉及；非 macOS 节点不注册能力。
- 真实登录态站点（需要账号的页面）未验证；独立 profile 意味着这些页面本来就不可达。
- 驱动 daemon 的启动/自动启动行为未验证：本 unit 只探测 `status`，不启动、不重启。
- `browser_prepare` 首次启动是否把浏览器带到前台，两轮验证结果不一致（第一轮 `foregrounded_window:false` 且前台未变，第二轮启动后前台变成驱动实例）；原因未定位，因此承诺里保留“首次接入可能短暂占前台”。
- `continuation` 语义与跨调用有效性未验证；v1 不使用。
- `browser_dialog` / `browser_download` / `browser_select` / `browser_set_input_files` / `run_steps` 未执行且不在白名单。
- 截图与 `semantic_v2` 可见性约 2 倍的偏差只在本机 `deviceScaleFactor=2` 上量化，其它缩放比例未验证；因此规则是“以截图为准”，不是“按比例换算”。
- 前台承诺原句中的“短暂”没有时长证据：实测新窗口占前台 ≥4 秒直到会话结束。产品承诺按用户指定原句保留，但不得据此向用户解释具体秒数。
