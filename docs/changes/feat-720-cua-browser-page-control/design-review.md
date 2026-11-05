# feat-720 设计审查（Gate 2）

> 每轮追加，不覆盖历史；author 只在本轮末尾追加 `Author Resolutions`，纠错写新 Round。

## Round 1

### Metadata

- reviewer: 独立 delegated design reviewer（子 Agent `nano-manager`，未参与本 unit 的需求、设计与证据制作；不修改方案）
- target: worktree `/Users/czj/Repos/nano-multiagent/.worktrees/feat-720-cua-browser-page-control`，branch `unit/feat-720-cua-browser-page-control`，head `0197b8cf7`，base `origin/main` `005a36057`
- 受审对象: `docs/changes/feat-720-cua-browser-page-control/` 的 `spec.md`(189)、`design.md`(386)、`specs/gateway/agent-capabilities.md`(84)、`evidence/desktop-verification.md`(570)、`M1-page-actions/.gitkeep`
- review_mode: `full`
- mode_reason: 本 unit 尚无历史 Round，change-workflow「门禁 2」要求 R1 必须 full；同时新增两项模型可见工具，按 `agent-context-review` Design Review 模式一并核 Context。
- started_at: 未记录精确起点（审查开始时未取时，如实说明）
- completed_at: 2026-11-05T18:09:43+08:00
- duration: 约 18 分钟（按本次会话工具调用顺序估算，非精确计时）
- 本地检查: `/Users/czj/Repos/nano-multiagent/.venv/bin/python scripts/docs_check.py` → `documentation integrity passed: 220 maintained Markdown sources, 68 required routes`（本报告写入后复跑结果见本轮末尾）

### Verdict

**Issues Found（Changes requested）— 2 CRITICAL / 7 WARNING**。

设计主体（职责归属、审批复用、单次调用无循环、身份与事件四条硬约束）方向正确，现状断言与代码基本对得上，`M1` 切片合理；阻断点集中在**前台承诺与证据的收口**、**坐标点击的参数来源**，以及若干"把机制写成结论"的地方。

### Coverage 与证据

**现状断言核对（回代码，不只看引用行存在）**

| design 断言 | 核对结果 |
|---|---|
| `defaultOff` 决定未配置白名单时的可见集（design L17、L26） | `packages/dsh-integration/src/capabilities.ts` L16、L41 一致 |
| `safeTools` 只读集合、`review()` 分流、三种审批路由（L18、L27–28） | `src/policy/approval.ts` L25、L76–83、L97–102、L104–153 一致 |
| `tools/pre-execute` 已有能力预留 hook（L16、L27） | `src/index.ts` L229–238 一致；`NanoApproval` 的 `review` 先 `await next()`，故静态守卫的拒绝先于分类器 |
| node 侧 `default_on` 排除清单（L19） | `apps/node/src/capabilities.ts` L53 一致（当前排除 7 个工具名） |
| 不新增 Feature（L20、D10） | `packages/product-contracts/src/capabilities.ts` L28–33 的 `featureDependencies` 形态与"Feature 依赖工具存在"一致 |
| 全仓无 `cua-driver` 命中（L15、L51） | `grep -rl cua-driver` 除本 unit 外无命中；`docs/changes/` 无历史记录 |
| RuntimeSupervisor 每 partition 一个 DSH 子进程（L21） | `apps/node/src/main.ts` L21、L64、L109 一致 |
| 工具注册面 `name/description/parameters/output/execute`（L38） | `src/features/task-graphs.ts` L40、`src/workflow/tool.ts` L108 一致 |

**用户约束核对**：spec L7–18 保留委派原文（页面内动作、`isolated_new`、不引第二套 loop、审批复用），未改写用户口吻；前台承诺原句只出现在 spec L87 与 delta L28，design 未出现"绝不打扰用户"一类绝对表述（D6 明确禁止）。

**delta-spec**：目标 `docs/specs/gateway/agent-capabilities.md` 锚定正确（该 area 已承载 Workflow、Goal 工具、审批策略等同粒度契约）；4 条 ADDED 未把实现细节写进契约。覆盖缺口见 R1-W2。

**milestone**：`M1-page-actions` 只有 `.gitkeep`，符合 Full 设计阶段的空骨架要求；退出标准分 `[reviewer]` 用户旅程与 `[worker]` 实现证据两段，可从最终树复核。

**Context（Mode A，并入本轮）**：Consumer / Before-After / Lifecycle / Interactions / Validation 五段齐全（L286–296），关键结论进了 M1 退出标准（第 9、10 条），大体满足 `agent-context-engineering.md`。已核对模型可见面：`read_id`/`ref` 均可由上一次结果取得（可追溯），错误码表给出"模型应做什么"（可行动）；不满足项见 R1-C2（`x/y` 无来源）、R1-W5（画面证据链）、R1-W4（Consumer 会话类型过宽）。

**实际覆盖的取证**：design 引用的证据区间逐条比对（约 30 处，见 R1-W6 的唯一不符）；`evidence/desktop-verification.md` 与 `/tmp/desktop-verify/report.md` `diff` 为空（逐字副本成立）；抽查 `/tmp/desktop-verify/shots/08-after-scroll.png`，画面首行为 `Row 18`、末行为 `Row 33`，与证据 L425–426 一致；截图实测像素 2400×1464（= 1200×732 CSS px × deviceScaleFactor 2），与证据 L444 吻合。

**未覆盖**：未启动浏览器或服务、未调用 `cua-driver`、未运行模型；未核前端渲染（本 unit 无前端改动）；未在真实模型上验证工具选择与参数填写。详见"未验证声明"。

### 历史问题闭环

无历史 Round（R1）。

### Issues

#### R1-C1 CRITICAL — 前台占用没有任何上界，风险表与退出标准低于自己的证据

- 位置：`design.md` L75、L82（v1 不做自动恢复）、L156（D6）、L308（风险表）、L353（M1 用户旅程第 3 条）、L386（未验证清单）；`spec.md` L87、L95–99、L101–104；证据 `evidence/desktop-verification.md` L545–554、L325
- 证据：
  - `window.open`（带 user gesture）弹出真窗口后，前台变成驱动实例并**持续 ≥4 秒不恢复**（连续 4 次采样），直到作者 `end_session` 才回到用户 app（L550–554）；驱动 `idle_expires_in_seconds: 300`（L85、L325），即不干预时实例最长约 5 分钟后才自退。
  - design L308 把影响写成"打断用户输入数秒"，L386 又写"≥4 秒…无时长证据"，两处不一致；spec L98 与 design L353 的验收项仍以"短暂占前台"作为可观察结论。
  - 全设计没有给出任何缩短占用的处置：只有"结果里说明该窗口可能占用了前台"（L82），`browser_act close` 完全靠模型自觉；`browser_read` 在 `safeTools`（L18、L159），意味着首次 `browser_prepare` 可能在**任何**会话里把浏览器带到前台，包括 `heartbeat`/`schedule` 触发的无人值守会话。
- 未修后果：① 验收可以在一次 4 秒中断上"通过"，而最坏分支（一直占到任务结束/空闲回收）没有任何验收；② 用户可观察体验没有上界，产品文案承诺与实现之间缺机制；③ reviewer / verifier 会按"短暂"字面放行，问题推迟到线上。
- 状态：CONFIRMED（文档与自己的证据矛盾、缺处置决定）；"后续 background 动作能否把前台还给用户"= 未验证（作者在窗口出现后按硬边界停止，没有继续采样）。
- 建议（不动用户固定原句）：
  1. 风险表与未验证清单统一为事实表述："新窗口或首次接入可能把实例带到前台，实测至少 4 秒，且在我们主动 `close` 或实例空闲回收（300 秒）前不恢复"。
  2. 给出一个有界处置决定（作者反对"自动恢复用户前台 app"的理由成立，不必改）：例如分类出真实新窗口后，工具结果显式要求在完成本次读取后 `close`，或该调用直接返回并要求用户确认是否继续；使前台占用有可预期上界，并在 M1 里可复核。
  3. 明确这两个工具在 unattended（`schedule`/`heartbeat`）会话中是否允许 `prepare`；若允许，说明"无人看着时抢前台"为何可接受。
  4. M1 用户旅程第 3 条把"短暂占前台"换成可观察事实链（新窗口出现 → 前台变化 → 按第 2 条的处置恢复），并补一条"无自动恢复"的实测记录。

#### R1-C2 CRITICAL — 坐标点击的 `x`/`y` 没有可靠来源与缩放口径

- 位置：`design.md` L201（`x`/`y` = "CSS px 视口坐标"）、L189 / L208（两个工具的返回结构）、L110（截图）、L109（禁止用可见性标签判位置）；证据 L411–416、L433–446、L444
- 证据：
  - 证据确认 `x/y` 语义是 **CSS px 视口坐标**，但作者取到 `{x:95,y:196}` 的来源是**上一次 `browser_click` 的 summary 回读**（"clicked (84, 201)"，L411–416）——这是动作发生后的读数，不是动作前可用的输入。
  - `browser_read` 返回 `refs:[{ref,role,name}]`（L189），**不含元素几何**；返回的 `screenshot:{path,width,height}` 也不含视口 CSS 尺寸或 `devicePixelRatio`。而截图实测是 2400×1464 设备像素（= 1200×732 CSS px，dpr=2），滚动读数偏差 1.92 倍也正源于此（L444）。
  - 于是模型若"按画面里按钮的位置"给坐标，会以 1/2 比例偏移；这正是 risk 表 L310「语义快照定位偏差导致点到相邻元素」的情形，而对坐标动作没有任何缓解。
  - 上下文规范 §1 要求"可由宿主可靠派生的字段不推给模型猜"；宿主侧本来就取得到视口尺寸（L204 的滚动锚点"视口中心"即依赖它）。
- 未修后果：真实使用中最常见的"点到某个看起来在那里的按钮"会点错位置；这是会产生页面副作用（可能触发提交类按钮）的错误，且当前 `read_id` 校验无法发现"坐标合法但落点错"。
- 状态：CONFIRMED（接口缺字段，可由返回值定义直接判定）。
- 建议（择一，并同步 delta / M1）：
  1. `browser_read` 返回 `viewport:{width,height,device_scale_factor}`，并为每个 ref 返回 CSS px 的 `box:{x,y,w,h}`；或
  2. 坐标参数改为归一化 `x_ratio`/`y_ratio`（0–1），由宿主换算；或
  3. v1 只保留 ref 点击，把"坐标点击"移出首版（需同步 spec L177、L201 与 M1 第 6 条）。
     另外无论选哪种，都要在结果里说明 `screenshot.width/height` 是设备像素还是 CSS px。

#### R1-W1 WARNING — 事件分类判定表的布尔语义含糊，且"停下"没有宿主执行手段

- 位置：`design.md` L94–99（判定表）、L97（"停止本批次后续动作"）、L277（失败与恢复）；`spec.md` L108–118
- 证据与问题：
  - L96 的噪声判定是一串用"、"和"或"连接的谓词（"bind 失败或没有 target、没有 URL、窗口尺寸是固定 UI 尺寸…、标题为空或是浏览器自带文案"），没有写 AND/OR 与优先级，而 L94 声明"实现直接按此写死"。按字面 OR 读，**"bind 失败"本身就等于噪声**：真实新窗口在 CDP target 尚未就绪时 bind 会失败，就会被静默计数为噪声，模型既不知道出现过窗口，也不知道刚才那次前台占用来自哪里——直接违反 spec L118「无法判断时停下说明」。
  - L97 要求"停止本批次后续动作"，但 v1 每次工具调用只有一个动作（D1 明确无循环、无批次），宿主也没有阻止模型下一次调用的手段；"停下"实际只能靠错误文本里的模型指导，当前却写成机制，verifier 会去找一个不存在的实现。
- 未修后果：分类实现按字面写死会静默吞掉真实窗口；"停止"语义无法验收。
- 状态：CONFIRMED（文本可直接反推错误实现）。
- 建议：改成有序决策树并写死正/负证据：① bind 成功且存在 `http(s)` tab → 真实窗口；② **正识别**的 chrome 噪声 = bind 失败 **且** 无 target **且** 无 URL **且** 标题为空/浏览器自带文案 **且** 尺寸属于 UI 尺寸集合；③ 其余（含 bind 失败但不能正识别）→ `browser_unexpected_event`，返回窗口证据并结束本次调用；把"必须先把该事件告知用户，再决定是否继续"写进错误文本（模型可见），不要声称宿主"停止批次"。写死后仍然"尺寸写死两个魔法值"是可接受的 fallback，但必须让 ③ 兜住未知尺寸。

#### R1-W2 WARNING — delta-spec 漏了两条首文档已收口的契约

- 位置：`specs/gateway/agent-capabilities.md` 全文（L1–84，4 条 ADDED）；`spec.md` L136–148、L165–172
- 证据：spec 的 8 条 Requirement 中，「关于页面画面与位置的结论必须有画面证据」（L165–172，且是 design 约束四的验收面、M1 用户旅程第 8 条）在 delta 里没有对应条目；「动作经既有审批」这条在 delta 里只剩"用户拒绝后没有副作用"，缺 spec L145–148「登录/提交/下载请求被拒绝并说明」的场景。
- 未修后果：归并 canonical 后，"以画面为准、读数不下结论"这条最容易被实现走样的契约在长青层没有落点；将来维护者按 canonical 判断该约束是否存在会得到否定答案。
- 状态：CONFIRMED。
- 建议：在 delta 增一条 ADDED（画面证据与读数口径：位置类结论必须以画面为据，只有读数时须明示未验证），并在审批 Requirement 下补"超出边界请求被拒绝并说明"场景；若认为应归到其它 area 文件，需要先建对应 area，不能省略。

#### R1-W3 WARNING — `browser_type` 从未实测，却被写进 M1 范围、评审旅程，退出标准里没有对应的验证门

- 位置：`design.md` L377（未验证清单）、L353（用户旅程第 3 条含"输入"）、L360–367（worker 退出标准，第 6 条 e2e 无 type）；证据 L310（把 `browser_type` 列入 CDP"完全后台"路线，但这是文档推断而非实测）
- 证据与问题：设计自己写了"实施时必须先补一条真实页面输入验证，再声称'输入可用'"，但这条不在 M1 worker 退出标准内，也不在 reviewer 旅程的前置条件里；评审旅程第 3 条已经要求"导航、读取、点击、**输入**、滚动期间前台不变"，reviewer 会直接对一个从未验证过的动作下结论。更深一层：若补验证发现 `browser_type` 需要前台（像第一轮地址栏 AX 输入那样，L154–159）或干脆不可用，首版范围要改，而设计没有定义回退路径（谁改 spec/delta、是否降级为"仅 ref/坐标点击"）。
- 未修后果：可能出现"输入能力未验证就交付"，或 reviewer 卡在一个设计没打算先验的动作上；范围变更时无既定处置。
- 状态：CONFIRMED（文档不自洽）；`browser_type` 是否 background 可用 = 未验证。
- 建议：把"真实页面上完成一次输入并回读 + 前台不变"写成 M1 worker 退出标准的一项（与第 6 条并列），并写明验证失败时的处置（把输入移出 v1 范围，同步修正 spec L177、delta、M1 标准与 reviewer 旅程）；在补验证完成前，旅程第 3 条只覆盖导航/读取/点击/滚动。

#### R1-W4 WARNING — 审批出口随会话类型不同，两个方向的产品后果都没收口

- 位置：`design.md` L28（现状：三种路由）、L261–268（审批表"分类器 / 人工"）、L288（Consumer 含 Global/子 Agent）；`packages/dsh-integration/src/policy/approval.ts` L76–83（`route`）、L97–102（`escalate`）
- 证据：`route()` 对 `origin === 'subagent'`（L77）与 `config.mode === 'global'`（L81）返回 `return_to_agent`；`escalate()` 只有 `interactive` 才返回 `{kind:'ask'}`，其余在 L102 直接 `deny`（`NanoApprovalDenied`）。也就是说：**Global 根会话和子 Agent 里 `browser_act` 需要人工时不会出现审批卡片**，而是直接拒绝；同时 unattended 会话在 `unattendedFallback:'allow'` 下会把分类器本要人工的 `browser_act` 自动放行——"没人看着也会点页面"。
- 未修后果：spec Req「动作经既有审批」的场景 1（用户拒绝一次审批）与 M1 用户旅程第 6 条只在 interactive 单聊会话成立；design L288 的 Consumer 表述会让实施与验收以为 Global/子 Agent 同样可用。Global 模式是产品主面，这点不讲清会让功能在最常用的会话里"看起来有、实际不能用"。
- 状态：CONFIRMED（按现有代码路径可判定）。
- 建议：在审批表后补一段"按会话类型的实际出口"：interactive 单聊 → 分类器/人工卡片；Global 根与子 Agent → 只有分类器放行，否则 deny，模型须改为向用户说明；unattended → 依 `unattendedFallback`。并对 unattended 是否允许 `browser_act` 给出决定（建议与 `bash`/`send_message` 一样排除自动放行，或明确接受并写理由）。同步修正 L288 的 Consumer 与 M1 验收所用的会话类型。

#### R1-W5 WARNING — 画面证据链与"页面内容不持久化"不一致

- 位置：`design.md` L110、L189 / L208（只返回截图路径）、L293（"页面内容不持久化、不跨会话继承"）、L316（截图落 workspace `.nanoassistant/browser/`、保留 20 张）
- 证据与问题：
  - spec L165–172 要求"结论要能对上它拿到的画面"，但设计只把截图存盘并返回 path：没有说明模型用既有 `read_image`（在 `safeTools` 内可用）去读这张图，没有说明截图必须落在**该 Agent workspace** 内（否则文件工具越界读不到，证据链断在读取权限上），也没有标注"结论依赖模型多模态"这一前提。
  - 截图是页面内容：落盘保留 20 张且没有 TTL，与 L293"页面内容不持久化、不跨会话继承"直接冲突；隐私与磁盘增长都没有边界。
- 未修后果：M1 第 8 条"结论与画面一致"可能无法真正执行（模型只看得到路径字符串），或验收靠人肉打开文件；同时"不持久化"的隐私表述不成立。
- 状态：CONFIRMED（文本冲突、路径归属未定义）；模型实际能否读图并据此下结论 = 未验证。
- 建议：结果给出可直接 `read_image` 的 workspace 相对路径，工具描述写明"要看画面证据就读这个路径"；截图保留改为有 TTL/条数上限并注明"临时证据、可能含页面内容"；修正 L293 的表述（或把截图目录纳入"会话结束清空"的同一条规则）。

#### R1-W6 WARNING — 证据行号引用与副本不一致

- 位置：`design.md` L73（"与第一轮 `foregrounded_window:false` 不一致（L286–289 与 L547–549）"）、L55（现称"570 行，行号与本 design 引用一致"）
- 证据：副本中 `foregrounded_window: false` 在 **L267**（`L262+5`）；L286–289 是 §5.1 `browser_prepare` / `existing_profile` 授权说明（L289 为"refuse with background_unavailable 除非 `delivery_mode:"foreground"`"）。L547–549 才是第二轮 `browser_prepare` 的前台变化。
- 未修后果：证据文档以行号为可复核锚点，错锚点会让 verifier/reviewer 核到无关段落；L55 的"行号一致"声明因此不成立，削弱整份证据的可信度。
- 状态：CONFIRMED（逐条比对约 30 处引用后唯一的偏差）。
- 建议：改为 L267、L543–549、L549–554。

#### R1-W7 WARNING — 同一 pid 多窗口时的"窗口解析"规则缺失

- 位置：`design.md` L61–67（身份约束）、L180（"从已登记窗口集合里解析目标窗口"）、L249–257（身份判定表）
- 证据：约束三自己的证据是"`window.open` 在同一 pid 下产生第二个窗口"（L460–477、L537）。此时 `browser_read {}`（省略 `tab` → 取 active 标签）到底读**哪个窗口**没有任何规则；`tab` 匹配器只在窗口内匹配 `url`+`title`+`active`，跨窗口的三元组冲突不会触发 `browser_tab_ambiguous`，而 `list_windows` 顺序无约定。
- 未修后果：页面自己开窗后，下一次读取/点击可能落到弹窗而不是主窗口，属于"按位置猜"，与 spec Req「页面或标签身份变化时，Agent 不按位置猜目标」（L120–134）冲突；而 `browser_tab_ambiguous` 恰好抓不到这种情形。
- 状态：CONFIRMED（规则缺失）。
- 建议：显式定义"已登记窗口集合"的语义（v1 是否只有 `browser_prepare` 得到的那个窗口）；若允许多窗口，补跨窗口规则：无匹配器时取"最近一次成功读取的窗口"，多窗口命中同一三元组 → `browser_tab_ambiguous`，并让 `browser_read` 返回 `window_id` 供下一次 `tab` 显式指定。

### 必须修改清单

进实施前必须闭环（按阻断程度排序）：

1. R1-C1：前台占用的事实表述（风险表/未验证清单/M1 第 3 条）与有界处置决定；unattended 会话是否允许 `prepare`。
2. R1-C2：`x/y` 的来源与缩放口径（返回视口尺寸 + DPR + ref 几何，或改归一化坐标，或删掉坐标点击）。
3. R1-W1：事件分类改为有序决策树（噪声需正识别、bind 失败落"未分类"）；"停下"改成模型可见指导。
4. R1-W3：`browser_type` 的验证门进 M1 退出标准，并写明验证失败时的范围回退。
5. R1-W4：审批出口按会话类型写清，并决定 unattended 是否允许 `browser_act` 自动放行。
6. R1-W2：delta 补「画面证据」Requirement 与「超出边界请求被拒绝」场景。
7. R1-W7：多窗口解析规则。
8. R1-W5：画面证据链（`read_image` 消费路径、workspace 归属）、截图 TTL 与"不持久化"表述一致。
9. R1-W6：证据行号改正。

### 已接受限制（本轮判断可以进实施，不需要修改）

- 不自建 MV3 + native messaging 扩展桥；不接 `existing_profile`。L376 把"驱动 `standard` 权限模式需要显式启动授权、普通 MCP/工具审批不能替代 profile 授权"写清了，也没有暗示"用户点一下就能接"；spec L183 与 delta 把该通道留在非目标，与授权文案一致（文案本身未在本 unit 实施）。
- 不做前台自动恢复：理由成立（恢复本身是一次前台激活、且没有验证证据），折进 R1-C1 的是"要有界"而不是"要恢复"。
- `delivery_mode:"foreground"` 全部分支不实测、不使用；多显示器/其它 Space、Windows/Linux/iOS、真实登录态站点未验证；截图为本地证据不入库。
- 不新增 Feature、不改 IM 前端、无 `prototype.html`：设置页工具来自 node 投影的 `default_on`（`apps/node/src/capabilities.ts` L53），`src/IM/frontend/src` 没有按工具名的硬编码标签（`exit_plan_mode`/`subagent_fork` 无命中），因此"无 delta 之外的产品面改动、无前端设计面"成立，原型省略合理。
- 驱动工具白名单（L284）确实只留 9 个入口，`run_script`/`run_steps`/`hotkey`/`type_text`/`page` 在客户端无调用入口并有测试断言，"没有第二套 agent loop"成立；`browser_read` 进 `safeTools`、`browser_act` 全动作走分类器，与 spec"只有只读可自动放行"一致（首次读取会启动实例这一点被 spec L101–104 明确为"用户不需要做任何授权确认"，不算越界）。

### 未验证声明

- 本次审查只读文档与源码；未启动浏览器或服务、未调用 `cua-driver`、未运行模型。证据判断基于 `evidence/desktop-verification.md`（与 `/tmp/desktop-verify/report.md` `diff` 为空）与抽查的 `shots/08-after-scroll.png`（2400×1464，内容 `Row 18`–`Row 33`，与 L425–426 一致）。
- 证据中的其它截图未逐一打开；"画面与结论一致"的判断部分依赖报告里转录的数字与文本。
- 未核前端实际渲染（本 unit 无前端改动）；未在真实模型上观察工具选择、参数填写与结果理解（Context 部分只给方案级判断，不外推为模型行为）。
- `docs_check.py` 结果见本轮 Metadata 与末尾"本轮执行记录"。

### Recommendations（可选，不阻断）

- R1-R1：原始报告与截图在 `/tmp`（L55），随时可能消失；建议把支撑每条硬约束的关键观测行（如 L463–465、L535–538 已有）保证在 evidence 正文里可独立复核，避免长期依赖临时目录。
- R1-R2：一次点击预计 4–5 次 CLI `spawn`（bind / snapshot / action / 回读 / `list_windows`），单次超时 20s/30s 叠加后一次调用可能到分钟级；建议在 M1 记录一次真实点击与输入的端到端延迟，并给"同 Agent 串行排队"单独的超时口径。
- R1-R3：工具描述必含句（L370）建议补一条"第一次读取可能打开一个浏览器窗口（可能短暂占前台）"，否则模型无法在动作前告知用户会多出一个窗口。
- R1-R4：D9 用文本匹配 `daemon is running` / `permission mode` 判断 `status`；建议失败时把原始输出片段一并回传（malformed 分支 L112 已这样做），便于用户自查。
- R1-R5：M1 worker 第 10 条写"由独立 context review 确认"，workflow 中 context review 已由 design reviewer（本轮）与 code review 承担；建议改为"由 code review 按 `agent-context-review` Implementation 模式确认"，不新增门禁。
- R1-R6：`existing_profile` 文案里的"30 分钟空闲/8 小时总计"（spec L11、L183）在证据里没有对应语义（只有 `isolated_new` 的 300 秒空闲）；将来实施该通道前需重新核对驱动语义，本 unit 仅留提醒。
- R1-R7：`design.md` L5 的空 `## Changelog` 段建议删除或写实质内容（Gate 1 不收模板残留）。

### 本轮执行记录

- `diff /tmp/desktop-verify/report.md docs/changes/feat-720-cua-browser-page-control/evidence/desktop-verification.md` → 空（逐字副本成立）
- `sips -g pixelWidth -g pixelHeight /tmp/desktop-verify/shots/08-after-scroll.png` → 2400×1464（= 1200×732 CSS px，dpr=2）
- `/Users/czj/Repos/nano-multiagent/.venv/bin/python scripts/docs_check.py` → `documentation integrity passed: 220 maintained Markdown sources, 68 required routes`（本报告写入后复跑结果同，见 commit 说明）
