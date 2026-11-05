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

### Author Resolutions

- resolved_at: 2026-11-05T18:29:23+08:00
- 修复范围：只改本 unit 文档（`spec.md`、`design.md`、`specs/gateway/agent-capabilities.md`）；未改代码、未启动浏览器或驱动、未 push。`evidence/desktop-verification.md` 保持逐字副本不变。
- 修复提交：本轮文档修复与本节同属一个本地 commit（spec/design/delta + 本节）；未 push。
- 用户指定的前台承诺原句未改：`spec.md` 前台 Req 的承诺句与 delta 的承诺句逐字保留；本轮只补机制、事实与验收口径。

**逐条处置**

| 编号 | 处置 | 主要落点 |
|---|---|---|
| R1-C1（前台占用无上界） | 采纳“给上界”，不采纳“自动恢复用户前台 app”。① 事实改为实测口径：新窗口后前台持续 ≥4 秒（连续 4 次采样）、直到 `end_session`；不干预时按 `idle_expires_in_seconds: 300` 兜底（约 5 分钟）。② 机制上界：**TurnGate**——只有当轮出现真实用户消息才允许首次 `browser_prepare`；无人值守/后台委派轮次只复用实例，否则 `browser_launch_requires_user_turn`。③ **真实新窗口**：完成本次回读与截图后立即 `end_session`，返回 `foreground_released:true`；失败重试一次，仍失败返回 `browser_foreground_release_failed` 并请用户手动关闭。④ 删除 `browser_act close`（模型自觉不是机制）。⑤ 300 秒只是兜底，不是正常路径。 | `spec.md` 场景二/七、前台 Req 的首次接入与真窗口场景、审批 Req；`design.md` 约束二 3–7、D6、D8、错误表、审批表、失败与恢复、风险表、M1 1/3/9、已知限制；delta 前台 Req 与 2 个新增场景 |
| R1-C1 的建议 3（unattended 是否允许 prepare） | 不允许 `prepare`；已有实例的只读仍可复用（读不会新开窗口）。`browser_act` 另在审批层加入“无人值守回退不放行”排除集：分类器要求人工时一律拒绝，不读 `unattendedFallback`；分类器明确放行的低风险动作仍可执行。 | `design.md` D7、审批与边界、现状分析 approval 行；`approval.ts` 影响面已在“涉及范围”写明 |
| R1-C1 与建议 2 的差异 | 没有把 `browser_read` 改成“只复用、不 prepare”。read 与 act 是两项**可独立选择**的能力，若 read 不能 prepare，只启用 read 的 Agent 永远读不到页面；改用 TurnGate 同时对两个工具的首次启动生效（比只约束 act 更强）。 | `design.md` 约束二 3、D7、browser_read/browser_act 接口、Agent Context；`spec.md` 前台 Req 的场景 |
| R1-C2（坐标无可靠来源） | 采纳方案 ③：**v1 删除坐标点击**，`browser_act` 只接受 `ref`（无 `x/y` 字段）；滚动改为 `ref` 锚点并列为实施前阻断验证 V5（失败则移除滚动，不退回坐标）。截图尺寸写明是设备像素（2400×1464 = 1200×732 CSS px，dp=2），读数不提供几何，因此不接受“按画面估算坐标”。 | `spec.md` 范围/非目标、场景五；`design.md` 约束四、接口、错误表、审批表、D7、风险表、M1；delta 未含坐标能力 |
| R1-W1（判定表语义含糊） | 改为**有序决策树**：① bind 成功 + 至少一个 http(s) tab → 真窗口；② 只有 bind 失败 **且** 无 target **且** 无 URL **且** 标题空/自带文案 **且** 尺寸属于 `284×87`/`1038×218` 才是噪声；③ 其余（含 bind 失败但证据不完整、`about:blank`）→ `browser_unexpected_event` 并结束本次调用。删除“停止本批次”的机制表述，改为模型可见指导（先告知用户再继续）。 | `design.md` 约束三、D4、失败与恢复、M1 worker 4；`spec.md` 噪声 Req 与真窗口场景；delta 噪声 Req |
| R1-W2（delta 漏契约） | delta 新增 Requirement「浏览器页面结论 SHALL 以画面证据为准，读数不得冒充已验证」（含“只有读数时明示未验证”场景），并在审批 Req 下新增「超出边界的请求被拒绝并说明」场景；同时把首次启动边界、真实新窗口归还前台、无人工出口不放行补进前台/审批 Req。 | `specs/gateway/agent-capabilities.md` 全文；`design.md` 契约层增量 |
| R1-W3（type 未实测） | 新增实施前验证 V1（后台写入 + DOM 回读 + 前台不变），M1 e2e 只在 V1 通过后包含输入；评审旅程第 3 条改为“导航/读取/点击（V1/V5 通过后再加输入/滚动）”；失败处置写明移除输入并同步 spec/delta/M1/旅程。 | `design.md` Milestones 前置表 V1、M1 reviewer 3、worker 8、已知限制；`spec.md`/delta 待 V1 失败时按处置同步 |
| R1-W4（审批出口随会话类型） | D7 写清三种出口：interactive → 分类器/人工卡片；Global 根与子 Agent → 只有分类器放行，否则 `NanoApprovalDenied`（无卡片），模型须请用户在单聊确认；unattended → 回退不放行。spec 新增“没有人工审批出口时不自动放行”场景；M1 审批旅程明确在 interactive 单聊执行，并新增第 9 条检查；Consumer 不再写成“Global/子 Agent 可完整使用”。 | `design.md` D7、审批与边界、Agent Context、Runbook 验收前置、M1 6/9；`spec.md` 审批 Req 与新增场景；delta 审批 Req |
| R1-W5（画面证据链） | 截图只写 `<agent workspace>/.nanoassistant/browser/<agentId>/`（resolve 后前缀校验，越界不写并返回 `screenshot_omitted:"outside_workspace"`）；返回 workspace 相对路径并写明用 `read_image` 读；每 Agent 最多 20 张、TTL 1 小时，Agent 销毁或实例结束时删除；把“页面内容不持久化”改为“不长期持久化，截图是临时证据”；新增 V6 验证 `read_image` 可读。 | `design.md` 约束四 2、失败与恢复、风险表、Agent Context、M1 reviewer 8/worker 9、V6、已知限制；`spec.md` 画面证据 Req；delta 画面证据 Req |
| R1-W6（证据行号） | 改为 `L267–268`、`L543–549`、`L549–554`；`design.md` 证据引言的“行号一致”声明改为“引用的行号已逐条核对”（审查稿 L55）。这是作者错误（锚点写错且过度声明一致性），本轮已改正。 | `design.md` 约束二、验证结论引言 |
| R1-W7（同 pid 多窗口） | v1 一个实例只登记**一个主窗口**：prepare 后 `list_windows {pid}` + 逐候选 bind，恰好一个 `exact` 且含 http(s) tab → 登记；零个 → `browser_session_lost`；多个 → `browser_window_ambiguous`。所有读写只解析主窗口；请求 `window_id` 非主窗口 → `browser_window_not_registered`；`tab` 匹配器只在主窗口内；新窗口不登记（真窗口还会结束实例）。`browser_read` 返回主窗口 `window_id`。 | `design.md` 新增“约束五”、架构图、错误表、身份表、接口、M1 worker 3；`spec.md`/delta 的身份 Req 已有“不按位置猜”覆盖 |

**可选建议**

| 编号 | 处置 |
|---|---|
| R1-R1 | 不改 evidence 副本。关键观测（窗口集合、bind 结果、前台变化、截图尺寸）已在报告正文；`/tmp` 依赖已在 `design.md` 证据引言标注为原始材料位置。 |
| R1-R2 | M1 worker 8 增加“记录一次点击与一次输入的端到端延迟，并说明同 Agent 串行排队的超时口径”。 |
| R1-R3 | 工具描述必含句新增“第一次读取可能打开一个浏览器窗口（可能短暂占前台）”，写入 M1 worker 11 与 Agent Context Validation。 |
| R1-R4 | D9 增加“status 文本匹配失败时错误带原始输出片段（截断）”。 |
| R1-R5 | M1 worker 12 改为“由 code review 按 `agent-context-review` Implementation 模式确认”，不新增门禁。 |
| R1-R6 | 保留 `existing_profile` 文案原样（本 unit 不实施该通道）；“30 分钟空闲/8 小时总计”仍无本机证据，已在 spec 非目标中限定为将来接入时的固定文案。 |
| R1-R7 | 删除空的 `## Changelog` 段。 |

**需要 Round 2 复核的新增判断**

1. TurnGate 把 `task-execution`/`task-change` 轮次排除在“可启动实例”之外（这些在审批上算 interactive，但不代表用户在场）。代价是：用户接受任务后，后续续跑轮次不能自己新开浏览器，只能复用首次用户轮次打开的实例。请复核这个收窄是否可接受。
2. unattended 下仍允许“分类器明确放行”的页面动作（只排除回退放行）。理由是与既有“低风险可自动执行”语义一致；如果要求无人值守完全禁止页面动作，需要再收紧并同步 spec/delta。
3. V2 把“`end_session` 不能归还前台”定为**发布阻断**（不是继续按披露发布），这是产品级取舍；请复核是否同意这种处理方式。
4. V6 若 `read_image` 读不到 workspace 相对路径，处置是改截图目录位置（仍做前缀校验），会再改一次 spec/design 文案。

**本轮执行记录（Author）**

- `../../.venv/bin/python scripts/docs_check.py` → `documentation integrity passed: 221 maintained Markdown sources, 68 required routes`（修复后复跑；221 比审查时的 220 多一份已入库的 `design-review.md`）。
- `git status --porcelain` → 干净；本轮修复与本节在同一个本地 commit 内。
- 未执行 V1–V6：用户正在使用本机，且这些验证需要启动驱动与浏览器窗口；C1 的“`end_session` 归还前台”依据仍是证据 L549–554 的单次观察，需 V2 复采。

## Round 2

### Metadata

- reviewer: 同一独立 delegated design reviewer（子 Agent `nano-manager`，未参与设计与修复；本轮只读文档与源码）
- target: worktree `.worktrees/feat-720-cua-browser-page-control`，branch `unit/feat-720-cua-browser-page-control`，head `07d3b84c7`，上轮报告 `a506f5b6e`，审查开始时工作树干净
- 受审 diff（`git show --numstat 07d3b84c7`）：`spec.md` +24/−12、`design.md` +159/−107、`specs/gateway/agent-capabilities.md` +45/−6、`design-review.md` +48/−0（仅追加 Author Resolutions，无删除）；`evidence/desktop-verification.md` 未改（`git diff` 空）
- review_mode: `delta`
- mode_reason: 有界设计变化——前台占用上界机制（TurnGate + 真窗口归还 `end_session`）、坐标点击移出 v1、新增“约束五 主窗口登记”、新增 V1–V6 验证门；职责归属、依赖方向、工具注册面、审批分层骨架与 milestone 数量未变。R1 已核且本轮未变的现状断言按 `retained_from: Round 1` 沿用，本轮只展开变化与其波及面。
- started_at: 约 2026-11-05T18:31（近似，未精确取时）
- completed_at: 2026-11-05T18:41:04+08:00
- duration: 约 10 分钟（按工具调用估算；中途会话上下文中断后按 head `07d3b84c7` 重新核对行号与引用，结论未变）
- 本地检查: `scripts/docs_check.py` → 见本节末尾执行记录

### Verdict

**Approved（可实施）— 0 CRITICAL / 0 WARNING**。

9 项“实施时顺手改”（其中 3 项须在实现对应路径前先落文字），不阻断 M1 开工。严重度口径：按本轮调用方给出的阻断标准（会让用户桌面被抢 / 会让未验证能力进范围 / 会让“未验证”看起来像“已验证”）逐项判定，剩余问题全部是**局部文档措辞与列举完整性**，改法唯一、不涉及重新设计，因此不记 WARNING；若把其中任何一项拖到实现之后，风险最高的是 R2-1（截图在真窗口路径被提前删除）与 R2-2（归还失败后的冷却语义），两项已在下面限定为“实现该路径前先落文字”。

### 历史问题闭环

| 编号 | 本轮证据 | 状态 |
|---|---|---|
| R1-C1 前台无上界 | `design.md` L71（前台持续 ≥4 秒/连续 4 次采样、直到 `end_session`、`idle_expires_in_seconds:300` 兜底、无人干预上界约 5 分钟）、L79（TurnGate）、L81（真窗口后归还）、L82（v1 不做自动恢复 ≠ 无上界）、L341（风险表“最坏约 5 分钟”）、L430/L438；`spec.md` L104–108、L119–123；delta L28–30、L48–58 | closed（余项见 R2-1/R2-2/R2-4） |
| R1-C2 坐标无来源 | `design.md` L185（静态守卫：click 无 ref 拒绝）、L220–231 参数表无 `x`/`y`、L225（click 只能用 ref）、L228（滚动以 ref 锚定）、L261、L295、L414、L429（坐标点击不在 v1 且无可靠来源）；`spec.md` L188、L194 | closed |
| R1-W1 判定表语义 | `design.md` L92–97 有序决策树（噪声需同时满足五项证据，bind 失败但证据不全落“未分类”）、L170（不再声称宿主能阻止下一次调用）、L309 | closed |
| R1-W2 delta 漏契约 | delta L111–123（画面证据 Requirement）、L62/L69–73（无人工出口）、L75–78（超出边界被拒） | closed |
| R1-W3 type 未实测 | `design.md` L383（V1 + 失败处置“删 type 并同步 spec/delta/M1/旅程”）、L400（旅程条件化）、L417（e2e 条件化）、L427 | closed |
| R1-W4 审批出口 | `design.md` L179–186、L293–299、L275（`NanoApprovalDenied` 含无人工出口）、L321、L406（M1 第 9 条）、L374（Runbook）；`spec.md` L143、L150–154；delta L62、L69–73 | closed（L321 措辞见 R2-9） |
| R1-W5 画面证据链 | `design.md` L111（workspace 前缀校验、`read_image` 可读、20 张/1 小时）、L326、L351、L388（V6）、L405/L418 | closed（生命周期冲突见 R2-1） |
| R1-W6 行号 | `design.md` L71 改为 `L267–268`、`L543–549`、`L549–554`；L53 声明改为“已逐条核对”。本轮抽查新增引用 L543–558、L320–325、L411–416、L418 均指向正确段落 | closed |
| R1-W7 多窗口 | `design.md` 约束五 L117–129、身份表 L281、错误码 L264–265、V4 L386、M1 L412 | closed |
| R1-R1…R7 | 逐条有落点（L53、L417、L420、L192、L421、L426、空 Changelog 已删） | closed |

### Coverage（delta）

- 逐条读全文：`spec.md`(201)、`design.md`(438)、delta `specs/gateway/agent-capabilities.md`(123)、Author Resolutions；`evidence/desktop-verification.md` 未变，R1 的行号核对与截图抽查（`08-after-scroll.png` 2400×1464、`Row 18–33`）继续有效。
- `retained_from: Round 1`（未变、本轮未重核）：`capabilities.ts` `defaultOff`、`approval.ts` `safeTools`/`route`/`review` 行号、`index.ts` `tools/pre-execute` 装配、`apps/node` `default_on` 排除清单、`product-contracts` `featureDependencies` 形态、全仓无 `cua-driver` 命中、`RuntimeSupervisor` 拓扑。
- 本轮新核：TurnGate 判定链（`packages/dsh-integration/src/input-source.ts` L21–25 的 `isHumanSource`、`policy/approval.ts` L76–83 的 `turn/start` 之后输入窗口与 L77 的 `origin === 'subagent'` 早退）、`end_session` 幂等（证据 L320–325）、错误码表 20 个码与正文互引、`browser_act` 参数表与 schema 断言、约束五与身份表/错误表/M1 测试项的互引、真窗口清理后用户 Chrome 5 个窗口未变（证据 L556–558）。
- Context（Mode A，仅核变化面）：Consumer 已按会话类型收窄（L321）、Validation 增“只接受 ref / 截图用 `read_image` / 非用户轮次不能新开实例”（L329），描述必含句进 M1 L420。两条新增模型可见事实（TurnGate 与真窗口归还）都能在错误码表（L266、L272）与结果字段（`foreground_released` L214/L233）找到出口。

### 逐项回答

#### 1) C1 闭合度

- **事实口径已改成实测口径**：`design.md` L71 写“前台持续 ≥4 秒不恢复（连续 4 次采样），直到 `end_session` 才回到用户 app（证据 L549–554）；不主动结束时按 `idle_expires_in_seconds: 300` 回收，所以无人干预时前台占用上界约 5 分钟”，风险表 L341 同步为“最坏约 5 分钟”，L430/L438 承认未做时长分布；全文不再出现“数秒”，也没把 300 秒当正常路径（L82 明确“300 秒只是兜底”）。
- **TurnGate 是否可判定**：是。条件是“当轮 `turn/start` 之后存在 `isHumanSource` 输入”：`input-source.ts` L22–25 定义为 `kind === 'nano-human'`，或 `kind === 'user'` 且带 `actorId`/`channel`/`messageId`；`approval.ts` L76–83 用的正是同一批输入（`turn/start` 之后过滤 `user/message`）与同一函数，纯同步、无 I/O，实现上把它抽成 `currentTurnInputs` 是同处逻辑，不存在两套语义。`task-execution`/`task-change` 在 L82 被算作 interactive，但不满足 `isHumanSource`，因此被排除——这与 L79 写的“不计入可启动轮次”一致。
- **是否只挡“首次 prepare”**：是。L79 写“只复用已有实例”，L204/L218 只在“本 Agent 还没有实例且当轮有真实用户消息”时要求 prepare，L293 的确定性拒绝只在“首次启动实例”一栏；已有实例时非用户轮次仍可读（M1 L416 第 7 条断言）。所以只读能力没有被整体挡掉，但代价必然存在：脚本/定时任务基本拿不到实例（见判断 (a)），设计没把这条后果写出来（R2-4）。
- **“自动关窗”的动作边界**：结论是**当前设计下不会关掉用户自己的窗口**，四条同时成立：① 只用 `browser_prepare`（`allow_launch:true` + `isolated_new`）产生实例，之后一切窗口操作都以该次 prepare 返回的 pid 为准（L125、L281）；② `end_session` 只作用于本 Agent 的 session label（L189，`nano-br-<8hex>`，按 agentId 复用、不跨 Agent 共享）；③ 窗口集合来自 `list_windows {pid}`（L93），用户自己的 Chrome 是另一个 pid，既不在集合内也不会被判成真窗口；④ 证据里 `end_session` 后用户 Chrome（pid 660）仍是原来的 5 个窗口（证据 L556–558），作者只引了 L549–554 的前台归还，没引这一条。
  仍需补两处硬化（R2-2）：`end_session` 前校验“label 属于本 Agent 且实例 pid 仍等于 prepare 返回值”；以及归还失败后的冷却语义（否则模型可在同一用户轮次反复动作、反复把窗口带回前台）。L556–558 这条“用户窗口未受影响”的清理核实值得直接引到约束二，它是“关窗不波及用户”的最直接证据。

#### 2) C2 闭合度

- 坐标能力确实移出 v1：参数表（L220–231）没有 `x`/`y`；`click` 只接受 ref（L225）；`scroll` 改为“在 `ref` 元素处滚动”（L228）；静态守卫（L185）、错误表（L261）、审批表（L295）、Context 必含句（L324/L329）、M1 单测（L414 断言 schema 不接受 `x`/`y`）全部对齐；`spec.md` L188 改为“点击元素（按最近一次读取返回的 ref）”，L194 把坐标点击写进非目标。
- 残留检查：全文“坐标”字样只剩解释性语句（为什么不做）与证据叙述（L428/L429 说明本次实测用的是 `x/y`）。没有功能残留。
- V5 可失败判据：L387“用最近一次读取的 ref 滚动成功；截图前后对照可见位移；前台不变”——ref 滚动若静默 no-op，截图对照可直接判失败，判据成立。建议补一条旁证“回读 `in_viewport` 至少同向变化”（不替代截图），因为截图对照依赖人工判读（R2-R2）。

#### 3) V1–V6 六项阻断验证

- 六项都是“验证 + 通过标准 + 失败处置”齐全，处置明确到**改范围**：V1 不通过→删 `type`（并同步 spec/delta/M1/旅程）；V5 不通过→删 `scroll`（不得退回坐标）；V2 不通过→不发布或另立同意流决策；V4 不通过→保留 `browser_window_ambiguous`、窗口选择 UI 另立 unit；V6 不通过→改截图目录并同步文案；V3 只影响措辞，不影响范围。这满足“不许带着未验证动作进 M1 验收”。
- **V2 定为发布阻断合理**：C1 的“上界”完全建立在“真窗口后 `end_session` 会把前台还给用户”上，而现有依据只有一次观察（证据 L549–554），作者自己也写了需 V2 复采；若 V2 不成立，产品承诺就只剩“披露”，正是 R1-C1 判为阻断的形态。因此“找到可验证的归还手法前不发布”是比例适当的处置，不是过度保守。流程建议：V2 比 V1/V5 更便宜也更能定生死，应先跑（R2-R3）。
- **V6 有两个问题**（R2-5）：① 判据“模型用返回的相对路径成功读图”在实施前无法完整执行——返回路径的是尚未实现的工具；应改为“以该 workspace 相对路径调用 `read_image` 能读到文件内容（一次直接工具调用或最小 agent 轮次即可观测）”。② 失败处置“改到 Agent 当前工作目录下的等价临时目录”没有限定位置，可能被实现成 `/tmp` 或 node home，直接违反“只写约定目录/不落仓库”与设计自己的前缀校验；须写成“改到 V6 实测可读、且仍在该 Agent workspace 内的根，保留解析后前缀校验”。

#### 4) 四个新判断

**(a) TurnGate 排除 `task-execution`/`task-change` 轮次——有条件接受。**
理由：任务续跑轮次的输入是 host 生成的 `nano-system`（`task-context`/`task-execution`），它只证明“这条任务被用户接受过”，不证明用户此刻在机器前；而这条路径的失败后果恰好是 C1 要消除的“用户桌前凭空弹窗并占前台”，且夜间或离开时无人纠正。代价可控：首文档的场景一至七都发生在对话内，没有承诺“定时任务自己开浏览器”。因此收窄成立。
条件：① spec/delta 必须把“任务续跑”写进被排除的轮次（现在只列定时/心跳/后台委派，见 R2-4），否则契约漏掉一条用户可观察限制；② 明确写下后果——“实例空闲 300 秒即回收，所以周期任务几乎永远拿不到实例，本能力 v1 实际是按需/对话内能力”，避免用户按“每小时巡检页面”的预期报 bug；③ TurnGate 依赖 `isHumanSource` 把 native child 首轮提示（`user` 但不一定带身份字段）判为非人类，这是 DSH 侧行为，本仓未能静态核实，需一条 fixture 断言固定（R2-3）。

**(b) 无人值守仍允许“分类器明确放行”的页面动作——接受。**
理由：① 与既有产品语义一致——`bash`/`write` 在无人值守下同样靠分类器判定，只把“需要人工”的判断交给 `unattendedFallback`；本 design 收紧的正是后者（L183、L299“不读 `unattendedFallback`”），没有引入新的放行分支。② 残留风险被 TurnGate 实质压小：无人值守轮次不能新建实例，只能复用“最近一次用户轮次留下的实例”，而该实例最多 300 秒后就回收，所以“无人在场时点页面”的窗口只有用户轮次后约 5 分钟。③ `spec.md` L143 的措辞是“无人值守轮次不会把‘没人在场’当作自动放行的理由；需要人工确认的动作被拒绝”，与该选择一致；若反过来“无人值守一律禁止页面动作”，必须改 spec/delta，且会让“用户在单聊里启动、随后由 Task 续跑完成点击”这类路径失效。
条件：把这条残留写进风险表（R2-R1），并修正 L321“无人值守只能只读”的表述——它与 D7/L299 的实际口径相反（R2-9）。

**(c) V2 失败＝发布阻断而非继续披露——接受。**
理由见上（C1 的上界依赖它，且披露已被判定不足以承担承诺）。补充：失败处置里“改为动作前显式征得同意每次可能开窗的动作（需另立决策）”应明确标注“V2 失败时**不进入本 unit 实现**”，否则实施者可能自行设计一套同意流，超出本 unit 范围与审批语义（R2-R3）。

**(d) V6 若 `read_image` 读不到则改截图目录并同步文案——有条件接受。**
接受“改目录 + 同步文案”的方向（用户不可观察、改动局部）；条件见 R2-5：目录必须仍在该 Agent workspace 内、保留解析后前缀校验、判据改为实施前可观测的形式（直接工具调用或最小 agent 轮次），且不得写到仓库、`/tmp` 或 node home。

#### 5) 范围纪律

- 没有长出 v1 之外的东西：驱动白名单仍是同一组入口（L317），未加 `close`（`browser_act` 只有 `open`/`click`/`type`/`scroll`，L222）；没有坐标；没有多窗口并发或窗口选择 UI（约束五只登记一个主窗口，多候选即 `browser_window_ambiguous`，V4 失败处置明确“另立 unit”）；没有登录态（`existing_profile` 仍在非目标，L195/L426）。
- 唯一新增的既有文件改动是 `src/policy/approval.ts` 抽出 `currentTurnInputs`（L16、L392），属同文件内重构，design 要求“行为不变 + 现有审批测试全绿”（M1 L416），不构成第二套审批或第二套 loop。
- “未验证写成已验证”审计：唯一接近的是 L83“`end_session` 是…在证据里验证过会归还前台的唯一动作”——依据是 1 次观察，而同文档 L384（V2 要求 ≥2 次采样）与 L430（未做时长分布）已把不确定性与复核门写清，不构成误导，但建议改措辞（R2-8）。其余新增断言（TurnGate、归还、主窗口登记）都以“验证项/未验证清单”形式出现，没有伪装成已验证。

#### 6) 三处（含波及面共六处）仍存在的原文不一致

1. **非用户轮次的枚举不一致**：`design.md` L79 排除“无人值守（`schedule`/`heartbeat`）与后台委派（子 Agent）”，但把 `task-execution`/`task-change` 单独论述为“不计入可启动轮次”；`spec.md` L54（场景七）只写“定时任务、心跳或后台委派”，L108 只写“无人值守（定时/心跳）或后台委派”；delta L30/L48–52 同。→ 用户接受的任务续跑被挡，但用户契约里没有这一条。
2. **“会话”语义不一致**：`spec.md` L75/L84–86“实例随会话结束或空闲回收…用户下次再用时是一个干净的、未登录的新实例”；`design.md` L189“不按‘每个对话一个实例’：一个 Agent 的多个会话应看到同一页面上下文”。→ 结束一段对话并不会结束实例（只有 Agent 销毁、真窗口归还、300 秒空闲会），双方需要一个共同定义。
3. **场景一叙述与首次接入披露冲突**：`spec.md` L36“整个过程里用户的前台应用一直是他写文档的那个应用”，而 `spec.md` L106“启动过程可能把该窗口短暂带到前台”，`design.md` L80 也承认首次 prepare 可能抢前台。
4. **`browser_launch_requires_user_turn` 的判定位置**：`design.md` L185 把它列在“执行期”静态守卫里，`design.md` L293 又列进“确定性拒绝（先于审批/执行）”。
5. **截图清理时机**：`design.md` L111“Agent 销毁或实例结束时删除”，L326“随 Agent 销毁清理”，而 L81 要求在“完成本次回读与截图后立即 `end_session`”（真窗口路径）——按 L111，模型还没读那张截图，它就被删了。
6. **无人值守可用面**：`design.md` L321“无人值守只能只读”与 D7 L183、审批表 L299（分类器明确放行仍可执行页面动作）相反。

### 实施时顺手改（不阻断 M1 开工；标 ★ 的须在实现对应路径前先落文字）

- **R2-1 ★ 截图生命周期与真窗口归还冲突**：位置 L81 / L111 / L326 / M1 L418。改法：统一为“只按 TTL（1 小时）与 20 张上限清理，实例结束不立即删除截图”，并说明理由（画面证据要在模型下一次 `read_image` 时仍可读）；M1 第 9 条断言同步。
- **R2-2 ★ 归还失败后的冷却语义**：位置 L81、L310。现在只写“重试一次→`browser_foreground_release_failed`→不再派发动作”，没写同一 Agent 后续调用的行为，模型可在同一用户轮次再次触发动作把窗口带回前台。改法：失败后该 Agent 进入“需人工恢复”状态，后续调用直接返回该错误，直到实例消失（用户手动关闭或 300 秒回收）；`end_session` 前校验 session label 归属与实例 pid 仍等于 prepare 返回值；并把证据 L556–558 引到约束二，作为“关窗不波及用户窗口”的直接依据。
- **R2-3 ★ TurnGate 对子 Agent 首轮的判定依据**：位置 L79、M1 L416。`isHumanSource`（`packages/dsh-integration/src/input-source.ts` L22–25）自身注释即写明“native child task prompts also use `user`”，因此子 Agent 的 seed 提示至少满足 `kind === 'user'`，能否启动全看它是否带 `actorId`/`channel`/`messageId`；本仓 `node_modules` 未安装，无法静态核实 DSH seed 形状，L79 的结论目前只能算 PLAUSIBLE。改法：不要只靠 source 形状——`approval.ts` L77 已有仓内可核实的现成闸门 `agent.session.header.origin === 'subagent'`，TurnGate 应叠加该判据（子 Agent 一律不可新开实例）+ `isHumanSource` 判用户轮次，再加一条 fixture 断言“子 Agent 首轮 → `browser_launch_requires_user_turn`”，并在 design 注明判定依赖 DSH seed source 形状。参考：`capabilities.ts` L134 在同类判定上额外要求 `kind === 'nano-human'`，说明本仓对“人类来源”存在更严口径；但直接照搬会连带排除 `nano-user`（真实用户）路径，本轮未核实实时输入的实际 kind，故不推荐改谓词，推荐叠加 origin 判据。
- **R2-4 spec/delta 补“任务续跑”**：位置 `spec.md` L54、L108；delta L30、L48–52；并在已知限制写一句“空闲 300 秒即回收，周期任务几乎拿不到实例，本能力 v1 实际按需/对话内使用”。
- **R2-5 V6 判据与失败目录**：位置 L388。判据改为“以 workspace 相对路径调用 `read_image` 能读到该文件（直接工具调用或最小 agent 轮次观测）”；失败目录限定“V6 实测可读且仍在该 Agent workspace 内，保留解析后前缀校验”，明示不得落 `/tmp`、node home 或仓库。
- **R2-6 `browser_launch_requires_user_turn` 的判定位置统一**：位置 L185 与 L293。选一处（建议保留“审批前确定性拒绝”，理由是它不需要页面状态、可省一次分类器调用），另一处删掉或注明“执行期复核”。
- **R2-7 “会话”语义与场景一叙述**：位置 `spec.md` L75/L84–86、L36；delta L28。改法：把“会话结束”明确为“该 Agent 的浏览器会话结束（Agent 销毁、真窗口归还或空闲回收）”；场景一补一句“（实例刚启动那一下可能例外，见首次接入场景）”。
- **R2-8 措辞强度**：位置 L83。把“在证据里验证过会归还前台”改为“证据中有 1 次观察（L549–554）；V2 复采确认后作为机制依据”。
- **R2-9 无人值守可用面表述**：位置 L321。把“无人值守只能只读”改为“无人值守不能新开实例；能复用已有实例时，只读始终可用，页面动作仅在该动作被分类器明确放行时执行（不读 `unattendedFallback`）”。

### 建议（可选，不阻断）

- R2-R1：风险表补一行“无人值守下分类器明确放行的页面动作仍会执行（无人工闸门；受 TurnGate 限制为最近用户轮次 300 秒内的实例）”，把判断 (b) 的残留显式化。
- R2-R2：V5 加一条旁证判据“回读 `in_viewport` 至少同向变化”，减少对人工判图的依赖；M1 用户旅程第 8 条（L405）的“1 小时后/超过 20 张被清理”无法在一次评审里观察，建议改为 worker 测试（注入旧时间戳）+ 评审只核对目录与条数。
- R2-R3：验证顺序建议 V2 → V1 → V5 → V4 → V6 → V3（先跑决定发布与否和范围的项）；并把 V2 失败处置里“另立决策”的分支标注为“本 unit 不实现”。

### 已接受限制（本轮新增，随实施保留）

- 页面能力 v1 实际是“用户发起轮次 + 最近 5 分钟内可复用实例”的能力：定时任务、心跳、任务续跑与后台委派都不会新开浏览器（spec 场景七要按 R2-4 补齐枚举）。
- 真窗口出现后实例立即结束、继续操作需要新的用户轮次；`browser_act` 无 `close` 动作，实例寿命由宿主与驱动空闲回收决定。
- 只接受 ref 点击/滚动；V1/V5 未通过时 `type`/`scroll` 不进首版；坐标点击在本 unit 内不再出现。

### 未验证声明

- 本轮只读文档与源码：未执行 V1–V6，未启动驱动/浏览器/服务，未运行模型；`node_modules` 未安装，DSH 原生子 Agent 的 seed source 形状无法静态核实（R2-3 记为 PLAUSIBLE，不作已确认缺陷）。
- C1 的“归还前台”依据仍是证据 L549–554 的单次观察；本报告的闭合判断以“机制已就位 + V2 阻断发布”为准，不代表已实测。
- 本轮未改任何受审文件，只追加本 Round。

### 本轮执行记录（Reviewer）

- `git rev-parse HEAD` → `07d3b84c766b4486ca6d216fe2d9cdd5ab259b4d`；审查开始时 `git status --porcelain` 为空。
- `git show --numstat 07d3b84c7` → 上表所列四份文件；`git diff --stat -- evidence/` 为空。
- `../../.venv/bin/python scripts/docs_check.py` → `documentation integrity passed: 221 maintained Markdown sources, 68 required routes`（本节写入后复跑，源文件数不变，仍为 221）。

### Author Resolutions（Round 2）

下列处置对应本轮 9 项“实施时顺手改”与 3 条可选建议。标 ★ 的三项（R2-1/R2-2/R2-3）已在文字层落到实现对应路径之前；本轮只改文档，不改代码、不 push。

| 编号 | 处置 | 落点 |
|---|---|---|
| R2-1 ★ 截图生命周期 | 统一为“只在写入新截图时按 TTL 1 小时与 20 张上限清理；实例结束（含真窗口后的 `end_session`）与 Agent 销毁都不立即删除”，并写明理由：真窗口路径要求“回读与截图后立即结束实例”，若结束时删图，模型下一次 `read_image` 就没有证据可读。补“进程启动时对截图根目录做一次过期清理”，覆盖已销毁 Agent 留下的文件。M1 第 8 条降为“评审只核对目录与当前张数”，TTL/20 张改由 worker 测试注入旧时间戳验证。 | `design.md` L114、L316、L329、L355、L409、L422；delta L119 |
| R2-2 ★ 归还失败冷却 | 补 `end_session` 前置校验：session label 属于本 Agent **且** 实例 pid 仍等于 `browser_prepare` 返回的 `owner_pid`，任一不符则不调用驱动、直接按失败处理。失败后该 Agent 进入“需人工恢复”：后续调用不派发任何驱动动作、直接返回同一错误，直到实例消失（用户关闭或 300 秒回收）。证据 L556–558（用户 Chrome pid 660 仍是原 5 个窗口）引到约束二，作为“关窗不波及用户窗口”的直接依据。 | `design.md` L71、L84、L188、L275、L313 |
| R2-3 ★ 子 Agent 判定依据 | **改判据、不改用法**：不采纳“子 Agent 一律不可新开实例”，改为“认请求来自哪一层”——普通会话看本会话；子 Agent 沿 `header.parentSession` 上溯（≤8 跳，经 `ctx.agents.get`）到最近的非子 Agent 祖先，要求**该祖先本轮**有真实用户消息；链断、超过 8 跳、或祖先本轮非用户发起即拒绝。理由：`approval.ts` L77 的 `origin === 'subagent'` 早退确实存在，但子 Agent 的实例按 Agent 归属，若一律禁止，“主 Agent 在用户轮次里把浏览任务委派给子 Agent”这条正常路径会永久不可用（子 Agent 既没有实例也不能建实例）；按层判定仍把“能否开窗”绑定在同一轮次的在场证据上，风险与不委派相同。审查意见的实质同时被保留：判定完全不读子 Agent 自己的 source（`input-source.ts` L21 注释写明 native child 首轮也用 `user`），因此 R2-3 的 PLAUSIBLE 依赖被移除，而不是被断言成已核实。fixture 覆盖：人类父轮次 → 允许；`heartbeat`/`task-execution` 祖先 → 拒绝；父会话缺失 → 拒绝；子轮次 source 无身份字段但父层有人类消息 → 允许。 | `design.md` L79–L82、L192、L221、L420；spec L109；delta L30、L54 |
| R2-4 任务续跑枚举 | spec 场景七、首次接入场景、delta 的实例 Req 与无人值守场景都补“任务续跑（用户先前接受过的任务再次执行）及其派生的子 Agent”；已知限制写清“实例 300 秒空闲即回收，周期任务几乎拿不到实例，v1 实际是按需/对话内能力”。 | `spec.md` L54、L109；delta L30、L49；`design.md` L434、L345 |
| R2-5 V6 判据与失败目录 | 判据改为“以该 workspace 相对路径调用 `read_image` 能读到文件内容（一次直接工具调用或最小 agent 轮次即可观测）”；失败目录限定为“V6 实测可读、仍在该 Agent workspace 内、保留 `resolve` 后前缀校验”，明示不得落 `/tmp`、node home 或仓库。 | `design.md` L392 |
| R2-6 判定位置统一 | 统一到“审批前确定性拒绝”（`tools/pre-execute` 静态守卫，省一次分类器调用）；执行期清单删除“当轮是否有用户消息”，只留依赖页面实时状态的三项复核（pid/窗口、`read` 后页面是否变了、标签是否仍唯一）。 | `design.md` L188、L296、L310 |
| R2-7 “会话”语义与场景一 | 定义“会话 = 该 Agent 的浏览器会话”：Agent 销毁、真窗口归还前台、空闲回收会结束它，结束一段聊天不会；design 同步。场景一补“实例刚启动那一下可能例外，见首次接入场景”。 | `spec.md` L36、L75、L83、L190；delta L28；`design.md` L192 |
| R2-8 措辞强度 | 改为“证据中有 1 次观察（L549–554）；V2 复采确认后才作为机制依据”。 | `design.md` L86、L179 |
| R2-9 无人值守可用面 | 改为“无人值守轮次不能新开实例；能复用已有实例时只读始终可用，页面动作仅在该动作被分类器明确放行时执行（不读 `unattendedFallback`）”，与 D7/审批表对齐。 | `design.md` L324 |

**可选建议**

| 编号 | 处置 |
|---|---|
| R2-R1 | 风险表新增一行“无人值守残留：无人在场时，分类器明确放行的页面动作仍会执行”；处置写明只有用户轮次（含其派生的子 Agent）能新开实例、残留窗口仅限最近用户轮次后约 5 分钟内、`unattendedFallback` 不参与放行、不改分类器判定。（`design.md` L345） |
| R2-R2 | V5 加旁证判据“回读 `in_viewport` 至少同向变化（旁证，不替代截图）”；M1 第 8 条的 TTL/20 张改为 worker 测试注入旧时间戳，评审只核对目录与当前条数。（`design.md` L391、L409、L422） |
| R2-R3 | 验证顺序写为 **V2 → V1 → V5 → V4 → V6 → V3**；V2 失败处置里的“同意流”分支标注**本 unit 不实现**（另立决策）。（`design.md` L383、L388） |

**判断 (a)–(d) 的条件落实**

- (a) 三个条件都已落：任务续跑进 spec/delta（R2-4）；“周期任务几乎拿不到实例”写进已知限制（`design.md` L434）；fixture 按 R2-3 的按层口径断言（`design.md` L420）——条件③的形态随判据调整：不再断言“子 Agent 首轮一定是非人类”，而是断言“子 Agent 自身 source 形状不参与判定、按祖先层判定”。
- (b) 残留写进风险表（`design.md` L345），并修正了与 D7 相反的 Consumer 表述（L324）。
- (c) V2 失败＝发布阻断保留；“另立同意流”标注本 unit 不实现（`design.md` L388）。
- (d) V6 的目录条件与可观测判据已写入（`design.md` L392）。

**R2-3 的取舍说明（供下一轮复核）**

审查建议“叠加 `origin === 'subagent'` 硬闸门 + fixture 断言子 Agent 首轮被拒”。作者的判断是：这条闸门会连带否掉本能力最自然的用法（用户在对话里要求做一件事，主 Agent 把它委派给子 Agent 执行），而子 Agent 的浏览器实例本来就按 Agent 归属、不能借用父实例，所以硬闸门的净效果是“委派即不可用”，不是“更安全”。按层判定保留的正是被审查认可的风险边界（同一用户轮次、同一在场证据），并把“后台/任务续跑派生的子 Agent”继续挡在外面。若实施时发现 `ctx.agents.get` 在本进程内拿不到根会话（例如跨进程根），则按层判定无法成立，此时退回硬闸门（子 Agent 一律不可新开实例）、保持同一错误码，并在实现记录里说明原因。

**本轮执行记录（Author）**

- `../../.venv/bin/python scripts/docs_check.py` → `documentation integrity passed: 221 maintained Markdown sources, 68 required routes`。
- `git status --porcelain` → 干净；本轮改动与本节在同一个本地 commit 内（未 push）。
- 未执行 V1–V6：用户正在使用本机，且这些验证需要启动驱动与浏览器窗口；C1 的“归还前台”依据仍是证据 L549–554 的单次观察（已按 R2-8 降级措辞）。

## Round 3 (closure)

### Metadata

- reviewer: 同一独立 delegated design reviewer（子 Agent `nano-manager`，未参与设计与修复；本轮只读文档、源码，以及主仓 `node_modules` 里已安装的 DSH `0.2.1-alpha.1` 类型与实现，用来回答“能不能静态确认”）
- target: worktree `.worktrees/feat-720-cua-browser-page-control`，branch `unit/feat-720-cua-browser-page-control`，head `a8b91bf95`，父 `d9d728c00`，审查开始时工作树干净，未 push
- 受审 diff（`git show --numstat a8b91bf95`）：`design.md` +39/−34、`spec.md` +8/−7、`specs/gateway/agent-capabilities.md` +10/−4、`design-review.md` +41/−0（仅追加 Author Resolutions）；`evidence/desktop-verification.md` 未改
- review_mode: `closure`——核对 Round 2 的 9 项 + 3 条建议 + 判断 (c) 是否真闭合，并对本轮唯一实质性设计变更（R2-3 从“硬闸门”改为“按层判定”）做一次完整复核（含 DSH 侧可达性的静态核实）
- started_at: 约 2026-11-05T18:57（近似，未精确取时）
- completed_at: 2026-11-05T19:23:00+08:00
- duration: 约 26 分钟（按工具调用估算，含 DSH 包静态取证）
- 本地检查: `scripts/docs_check.py` → 见本节末尾执行记录

### Verdict

**CHANGES REQUESTED — 1 项阻断实施（R3-C1）/ 4 项实施时顺手改（R3-1…R3-4）**。

其余 8 项（R2-1 主体、R2-4、R2-5、R2-6、R2-7、R2-8、R2-9、R2-R1…R3）**确认闭合**，逐条核对后没有被改写成长短不一的另一种说法；R2-2 的前置校验部分闭合、冷却清除机制部分仍不可判定（见 R3-2）。

阻断项只归入三类之一：**R3-C1 属于“会让用户桌面被抢”**。现文本允许“祖先最近一次人类发言在 1 小时前、甚至该祖先的轮次已经结束”时由子 Agent 新开浏览器窗口，而 C1 的全部上界论证（准入 + 真窗口归还 + V2 阻断发布 + spec 承诺）都建立在“开窗时用户在场”。修法是三句话判定条件 + 一条 spec/delta 语义 + 一条 fixture，不涉及重新设计，也不需要再跑全流程复审。

### 阻断实施（must-fix）

#### R3-C1 — 按层判定把“在场”判成了“曾经在场”，缺轮次打开状态与时间绑定

- 位置：`design.md` L79（判定条款）、L420（M1 第 7 条 fixture）、`spec.md` L109、delta L30。
- 现文本（L79）：“……找到第一个 `origin !== 'subagent'` 的祖先后在那一层判定。判定条件是该会话本轮 `turn/start` 之后存在真实用户消息……”。缺陷有两点，都可复现：
  1. **没有时间绑定**：只要求“存在”，不要求“刚刚”。祖先在 t0 收到人类消息、开一个长轮次，Agent 在 t0+60 分钟才把浏览任务委派给子 Agent，判定仍然通过——此时用户在不在桌前完全未知，窗口照开，`browser_prepare` 还可能把窗口带到前台（证据 L543–549，≥4 秒不恢复）。
  2. **“本轮”未定义，轮次关闭后仍然通过**：原生后台委派（`delegation:'background'`）的子 Agent 可以在父轮次结束之后继续跑或被再次唤醒；父会话“最后一个 `turn/start` 之后”仍然存在那条人类消息，于是几小时后仍然通过。这与设计自己在别处的主张（“后台委派轮次只复用已有实例”，L79、delta L30）直接矛盾。
- 为什么算阻断而不是顺手改：这两条路径的净效果就是“用户不在桌前时凭空弹窗并可能占前台”，属于本轮调用方划定的第一类阻断；它不是措辞问题，而是判定条件少了一半。
- 修法（**仍然满足 L82“同步、无 I/O”的约束**，因为只读内存事件）：
  1. 判定会话必须是**打开的轮次**：最后一个 `turn/start`（`data.turn`）之后没有同号的 `turn/end`；若最后一轮已关闭，按“不在场”拒绝（依据 `dsh-session` 的 `turn/start {turn}` / `turn/end {turn, reason}` 事件，见静态取证）。
  2. 该打开轮次内存在 `isHumanSource` 的 `user/message`（沿用现有谓词）。
  3. 该消息的 `event.time`（`SessionEvent.time`，epoch 毫秒）距本次请求 ≤ **在场窗口**；建议取 300 秒，与实例 `idle_expires_in_seconds: 300` 同一量级，也与本 unit 已知限制里“最近约 5 分钟”的说法一致。作者可另取常数，但必须在 design 里写明取值与理由。
  4. 链断 / 超跳 / 无打开轮次 / 无人类消息 / 超窗 → 一律 `browser_launch_requires_user_turn`，**任何分支都不得回退为放行**（现文本 L79“一律拒绝”保持）。
- 用户可见契约同步：`spec.md` L109 与 delta L30 现在只说“包括该轮次里被委派的子 Agent”，没有“窗口”。必须补一句用户可读的限制，例如“只有你最近一次发言后的几分钟内、且那一轮还没结束时委派的子 Agent 才可能新开窗口；更早的委派只复用已有实例”。否则用户按“委派就能开窗”预期使用会报 bug（与 R2-4 的同类后果并列，写进已知限制 L434）。
- fixture（扩写 M1 L420 第 7 条，全部可单测、无浏览器）：
  - 祖先轮次打开 + 人类消息 60 秒前 → 允许 `browser_prepare`；
  - 祖先轮次打开 + 人类消息 10 分钟前（长循环后段委派）→ 拒绝；
  - 祖先最后一轮已关闭、子 Agent 仍在运行 → 拒绝；
  - 祖先 `heartbeat`/`task-execution` 轮次 → 拒绝（现有断言）；
  - 链断 / 超跳 → 拒绝（现有断言）。

### 逐项回答

#### 1) 按层判定是否等价于“开窗绑定在同一轮次的在场证据上”

**不等价**。现文本把绑定降成了“祖先历史上出现过人类消息”，缺“轮次仍打开”与“新鲜度”两个维度。三种方案在四种场景下的实际行为（“硬闸门”= R2 建议的子 Agent 一律禁止；“现设计”= L79 原文；“加绑定”= R3-C1 修法）：

| 场景 | 硬闸门 | 现设计 | 加绑定（R3-C1） |
|---|---|---|---|
| 用户轮次内前台（同步）委派 | 不可用（能力缺口） | 可用 | 可用（消息在窗口内） |
| 用户轮次内长循环 1 小时后才委派 | 不可用 | **可开窗（风险）** | 拒绝 |
| 后台委派，父轮次已结束、子 Agent 继续跑 | 不可用 | **可开窗（风险）** | 拒绝 |
| 定时/心跳/任务续跑派生的子 Agent | 拒绝 | 拒绝 | 拒绝 |

两个洞的具体处置：(i) 需要“打开轮次 + 时间上界”，不能只判“有”——R3-C1 第 1、3 条；(ii) 断链默认行为现文本已经是**拒**（L79“祖先链断…→ 一律拒绝”），这一点写对了，但要把它固定成 fixture，并按第 3 问删掉“拿不到就退回硬闸门再决定”的模糊表述，避免实现时被读成“拿不到就放行”。

#### 2) 硬闸门的被拒理由成立吗？有没有“父 Agent 传递在场证据”的替代？

**理由成立**：子 Agent 的实例按 Agent 归属（D8 L192，label 按 agentId），不能借用父实例；在硬闸门下子 Agent 既无实例也不能建实例，“用户轮次里把页面任务委派给子 Agent”确实永远是缺口。这不是过度保守的推断，而是设计自身结构的直接结论。

**替代方案可行，但成本不同**：在 `agent/created`（或 `subagents.start` 的包裹点）为子会话铸一个**带到期时间的在场租约**（`{childSessionId, expiresAt: parentHumanMsg.time + window}`），子 Agent 的 TurnGate 只认租约——技术上可行（本仓测试已经在 `agent/created` 里读 `agent.session.header.parentSession` 与 `delegationDepth`，见 `packages/dsh-integration/tests/schedule-deletion-native.test.ts` L23）。代价：多一份进程内状态要管生命周期（子会话结束/崩溃/恢复时清理）、要覆盖 fork 与 resident 子 Agent，且**仍然需要“到期”这个概念**——所以无论选哪条路，R3-C1 第 3 条的在场窗口都是共需成本，省不掉。收益：到期显式、可审计，不依赖祖先是否仍活着。

**本 unit 的建议**：保留按层判定（不新增状态、无 I/O），但必须叠加 R3-C1 的轮次与时间绑定；如果作者更看重可审计性，可以改选租约方案，但要在 design 里二选一写清并给对应 fixture。**不要**让“硬闸门 / 按层判定”两套并存成一个实现期分支。附带一句必须承认的边界：无论哪种方案，“后台委派”都拿不到实例，所以按层判定带来的能力恢复只覆盖**同步/前台委派**，L80 的论证应把这句写进去。

#### 3) 退路条件（`ctx.agents.get` 拿不到根会话）能否在实施前静态确认

**能，已经确认；而且这条退路比需要的更悲观**。静态取证（主仓已安装的 DSH `0.2.1-alpha.1`，与 `packages/dsh-integration/package.json` 声明一致）：

- `AgentRegistry.get(id: SessionId): Agent | undefined` 与 `list(): Agent[]` 存在（`@deepseek-ai/dsh-agent` 类型 `lib/types/index.d.ts` L343、L357）；
- 本插件同一上下文已在用 `ctx.agents.list()`（`packages/dsh-integration/src/index.ts` L201），说明 `ctx.agents` 在这个 `tools/pre-execute` 所在的 ctx 上可用；
- 子 Agent 创建时由 `childSessionMeta()` 写入 `parentSession: parentHeader.id`、`origin:'subagent'`、`delegationDepth`（`@deepseek-ai/dsh-subagent` `lib/index.js` L470–481），即 `parentSession` 就是**父 Agent 的会话 id**；
- DSH 自己的 `liveLineage()` 就是用 `ctx.agents.get(parentSession)` 上溯（同文件 L1038–1049），并带 `seen` 环检测。

结论：子 Agent 存活期间其父 Agent 在注册表里是活的（子 Agent 的运行时所有权挂在父上），链条在进程内可解析；“拿不到根会话”只会发生在父已被销毁/恢复后链条不可解析的边界情形，此时 deny 是正确行为。因此**不需要**为它新增 V7 阻断验证项（它是静态事实，不是待验证实验）。但要把现文本的“退路”改写成三条可执行的要求：① 静态可解析这一事实入 design（附上面证据）；② 链断即 deny（已有，补 fixture）；③ 用**环检测**替代固定“≤8 跳”（当前子 Agent 工具栏 `maxDepth` 默认 1，链通常只有 1 跳；固定跳数会掩盖环，DSH 自己的实现就是 `seen` 集合）。另需在 design 里点明：`ctx.agents.get` 是**活 Agent 注册表**而非持久血缘，这正是“轮次关闭后必须 deny”的同源理由。

### 其余 8 项是否真闭合

| 项 | 核对结果 |
|---|---|
| R2-1 截图生命周期 | **闭合（余项 R3-1）**。`design.md` L114、L316、L329、L355、L409、L422 与 delta L119 全部改成“只在写入新截图时按 TTL/上限清理，实例结束与 Agent 销毁都不删”，并写明理由；真窗口路径不再自相矛盾 |
| R2-2 归还失败冷却 | **部分闭合**：label 归属 + `owner_pid` 预校验已写（L84、L275、L313，证据 L84 确有 `owner_pid`）；但“直到实例消失才清除”没有定义如何观察消失 → R3-2（现文本不可判定） |
| R2-4 任务续跑枚举 | **闭合**。spec L54（场景七）、L109、delta L30/L49、已知限制 L434 都补了“任务续跑及其派生的子 Agent”，并写了“周期任务几乎拿不到实例” |
| R2-5 V6 判据与目录 | **闭合**，且这次真的实施前可观测：判据不再依赖尚未实现的工具——在 workspace 放一张 PNG 后直接调用 `read_image` 即可；失败目录限定在“V6 实测可读且仍在 workspace 内”，明示不得落 `/tmp`、node home、仓库 |
| R2-6 判定位置统一 | **闭合**。L188 把 `browser_launch_requires_user_turn` 与恢复态拒绝并入 `tools/pre-execute` 静态守卫；L296（读取页面）与 L297（打开 http(s) 页面）的“确定性拒绝”列都带上它；执行期只留 pid/窗口、`read` 后是否变化、标签是否唯一三项 |
| R2-7 “会话”语义与场景一 | **闭合，不是两边都留**。spec L75 现在给出唯一定义（浏览器会话；Agent 销毁/真窗口归还/空闲回收会结束它；结束一段聊天不触发），scenario L83–86 与 delta L28、design D8 L192 同步，场景一 L36 加了例外注。残留只是叙述句强度（R3-3） |
| R2-8 措辞强度 | **闭合**。L86“证据中观察到会归还前台”与 D6 L179“1 次观察，V2 复采确认后才作为机制依据” |
| R2-9 无人值守可用面 | **闭合**。L324 现在是“不能新开实例；能复用实例时只读始终可用；页面动作仅在分类器明确放行时执行（不读 `unattendedFallback`）”，与 D7/L299 一致 |
| R2-R1 / R2-R2 / R2-R3 | **闭合**。风险表新增“无人值守残留”行（L345）；V5 加 `in_viewport` 旁证、M1 第 8 条改为“评审只看目录与张数、TTL/上限由 worker 注入旧时间戳验证”（L391、L409）；验证顺序 V2→V1→V5→V4→V6→V3（L383）、V2 失败分支标注“本 unit 不实现”（L388） |

### 实施时顺手改（不阻断 M1 开工；标 ★ 的须在实现该分支前先落文字）

- **R3-1 ★ 进程启动清理的范围与失败语义**：位置 L114、L316。判断：这是**必要兜底，不是范围蔓延**——既然删掉了“实例结束/Agent 销毁时删除”，唯一剩下的清理触发点就是“写入新截图”，一个不再截图的 Agent 目录会永久残留，直接违背 spec 的“临时证据”与本 design L355 的风险处置。但现文本没限定范围：改法为“只扫描已配置 Agent workspace 下的 `.nanoassistant/browser/<agentId>/`，不遍历 home 或仓库；单次、有界、失败不阻塞进程启动（记录后继续）；只删本能力自己按 TTL/张数规则判定的文件”，并在 M1 L422 第 9 条补一条断言（现有断言只覆盖“写入时清理”）。
- **R3-2 ★ 冷却清除机制**：位置 L84、L313、L275。现写法“直到实例消失（用户关闭或 300 秒空闲回收）”**不够可判定**：谁去观察消失？如果实现成“每次调用前 `ps` 查 pid”，那是进程 I/O（破坏 pre-execute 无 I/O 的前提）且 pid 会被复用；如果实现成“永不检查”，能力被永久锁死（这属于“实质能力缺口”）。改法：冷却状态带截止时间 `failedAt + 300s`（与驱动 `idle_expires_in_seconds` 同量级），到期惰性清除；若要保留“用户手动关窗后恢复”，用**新实例的 `end_session` 成功**作为清除条件，而不是 pid 探测。worker 测试固定：失败后 300 秒内每次调用都直接返回 `browser_foreground_release_failed` 且零驱动调用；到期后状态清空、可再次按 TurnGate 决策。
- **R3-3 场景一叙述强度**：位置 `spec.md` L36。现在是“没有被打断输入”+ 例外注，读起来仍像绝对句；建议改为“没有被持续打断输入（启动那一下除外）”，与 L106 的披露同向。
- **R3-4 契约层不写机制**：位置 delta L30 的“（判定按请求上溯到最近的用户会话）”。这是实现手法，不是用户可观察契约；建议删除该括注（机制留在 `design.md` L79），并按 R3-C1 补“在场窗口”这条**行为**语义。

### 已接受限制（本轮新增）

- 委派开窗只覆盖“同步/前台委派 + 该轮次仍打开 + 用户最近一次发言在约 5 分钟内”；后台委派（父轮次已结束）与长轮次末端委派都拿不到实例，只复用已有实例。这条要按 R3-C1 落进 spec/delta 与 L434。

### 未验证声明

- 本轮只读文档、源码与主仓 `node_modules` 中已安装的 DSH `0.2.1-alpha.1`（worktree 未安装依赖，未做 `pnpm install`）；静态取证只说明 API 与语义存在，不代表本 unit 已在运行时验证按层判定与在场窗口。
- 未执行 V1–V6，未启动驱动/浏览器/服务，未运行模型；证据副本未改（`git diff` 空），C1 的“归还前台”仍是证据 L549–554 的单次观察。
- 本轮未改任何受审文件，只追加本 Round。

### 本轮执行记录（Reviewer）

- `git rev-parse HEAD` → `a8b91bf95b100d9f16073b163996fcf96689ccad`；`git status --porcelain` → 审查开始时为空。
- `git show --numstat a8b91bf95` → `design-review.md` +41/−0、`design.md` +39/−34、`spec.md` +8/−7、`specs/gateway/agent-capabilities.md` +10/−4。
- 静态取证：`node_modules/@deepseek-ai/dsh-agent/lib/types/index.d.ts` L343/L357（`get`/`list`）、`node_modules/.pnpm/@deepseek-ai+dsh-subagent@…/lib/index.js` L470–481（`childSessionMeta`）、L1038–1049（`liveLineage`）、`@deepseek-ai/dsh-session` 类型 `types.d.ts` L262/L273（`turn/start`/`turn/end`）与 L493/L495（`seq`/`time` 信封）。
- `../../.venv/bin/python scripts/docs_check.py` → `documentation integrity passed: 221 maintained Markdown sources, 68 required routes`（本节写入后复跑，源文件数不变）。
