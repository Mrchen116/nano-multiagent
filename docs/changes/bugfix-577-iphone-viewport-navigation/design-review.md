# bugfix-577 Design Review

## Round 1

### Metadata

- reviewer target: `/root/review_577_design`，独立 reviewer，未参与本 unit 设计或实现。
- review_mode: `full`
- mode_reason: Gate 2 首轮；无历史 Round，完整覆盖 incident、现状接线、design、delta、prototype、milestone 和验收前置。
- started_at: `2026-10-04T23:54:13+08:00`（首个显式时钟记录；此前已开始读取文档和查看原型）
- completed_at: `2026-10-04T23:59:24+08:00`
- duration: 已记录时钟区间 `PT5M11S`，含等待 caller 提供隔离产品基线；不把此前未计时部分伪记为精确时长。
- executed_base: `main e6a5c0ea537c35b9b30f99627d2f1046f3c7fa77`
- validated_at: 上述 checkout 的本地未提交 unit 文档。design 声明的源码基线 `d21848653` 到 executed_base，在 `src/IM/frontend` 与 `src/IM/app.py` 范围内无 diff。
- effective_base / effective_through: 本轮以上述 executed_base 和下列内容摘要为界；后续实质修订需失效判断。

| 受审文件 | SHA-256 |
| --- | --- |
| incident.md | `66058421dbb67677628cd64cde114808c645cd401cf8c715dad99e838ed30056` |
| design.md | `891583ea58dcad107b916c190806053d29afc7385b754a539c4978688b6e3e91` |
| prototype.html | `60b9d48ffdb15db7553bea927596074981593c415539bcbb52bfce17543bd9b2` |
| specs/im/web-chat-ux.md | `68ba28a5c67a2987286db3bcbdf395148e02df17c4c274ef60099eabc67e52b7` |

### Verdict

**Approved — 0 CRITICAL / 0 WARNING.**

设计足以指导一个有界的 M1 实现。批准的是设计及局部原型表达，不是修后产品验收、真机键盘通过或生产发布。作者仍须按 workflow 核实本报告，并保持受审内容与上述快照一致。

### Coverage 与证据

**现状与真实接线。** 独立读取 `src/IM/frontend/src/main.tsx`、`app/providers.tsx`、`app/router.tsx`、`app/shell/app-shell.tsx`、`features/auth/auth-page-frame.tsx`、`features/auth/login-page.tsx`、`features/chat/components/message-pane.tsx`、`styles/global.css`、`index.html` 及 `src/IM/app.py`。`main.tsx` 确实把登录与受保护路由共同包在 AppProviders 中，新增统一 hook 的挂载点可达实际产品；`/` 经 RequireAuth 和 index Navigate 去 `/chat`，登录保留 safeReturnPath / replace 导航。AppShell 用既有移动判断在具体会话隐藏全局底栏；composer 的 mirror 与 textarea 都有独立的 0.9rem 声明，设计要求同步字号、行高和换行是必要的。body/root/shell 现用 100vh，认证页自有滚动与最小高度，聊天 header/composer 已有局部 safe-area，设计已明确避免重复计算。

**故障机制和范围。** incident 区分了线上观察、同设备最小对照、CSS 折算与尚未完成的产品验收；本轮没有重新操作 iPhone，也不把文档中的同机实验声称为 reviewer 新测。字号、standalone 导航契约及容器高度分别处理，不用一个 CSS 改动解释全部现象。独立核读 [Apple WWDC23 Web Apps](https://developer.apple.com/videos/play/wwdc2023/10120/) 的 manifest/display/scope 说明和 [WebKit Safari 26](https://webkit.org/blog/17333/webkit-features-in-safari-26-0/) 的 Web App 行为说明；它们支持显式配置的方向，但不替代该设备上的对照结论。没有将缺 manifest 等同于“不能成为 Web App”，也没有把该次 iOS 路径行为概括为所有版本规则。

**职责与复杂度。** CSS 继续拥有字号、flex、高度默认值和安全区；AppProviders 下单个 hook 仅拥有输入期间 visualViewport 生命周期与根变量，不持有身份、消息或表单内容；manifest 属于 Vite public 资产及 IM 既有静态服务边界。复用现有组件比重新建立移动页面、每页监听视口或引入 PWA 框架更直接。scale 约为 1、手机断点和编辑焦点的条件，配合 blur/卸载清理，明确保留手动缩放；offset 补偿只在真机出现可复现问题后修订，未引入假想机型特例。没有跨包 import、认证协议或 Gateway 责任迁移。

**manifest 接线的确定事实。** `src/IM/app.py:186` 起的 `_install_frontend_entrypoints` 当前只显式提供 assets、favicon 和 SPA 页面，没有 `/manifest.webmanifest`。因此 design 中“如需”分支在当前基线上实际需要执行：按现有 favicon 分发方式增加窄静态入口，并验证构建产物经 IM 返回正确 JSON MIME，不能只验证 Vite。此项已由 design 的可复用能力、接口契约和 M1 W1/范围覆盖，不构成未收口设计问题。无需增加通用文件服务器或 PWA 插件。

**当前画面与原型的直接对照。** 本轮用独立浏览器 tab 只读查看 `https://im.nanoim.win/login` 的桌面及 375px 登录画面；随后在 caller 提供的未修改产品隔离栈 `http://127.0.0.1:18779` 用仓库 E2E 身份登录，在 375×812 下看真实列表，通过 New conversation → New chat → e2e 建立空测试会话，进入 `/chat/c_wk6jrsx0` 并 Back 返回。实际看到白色认证卡、teal 主操作、列表搜索与四个底部入口、详情顶部返回及底部 composer；详情没有全局底栏。未发送消息、未访问生产会话。这个空会话是隔离测试数据，交由 caller 随隔离环境清理。

原型是三个局部组件上下文的展示，未声称复刻整个产品。简化的会话文案、图标、列表过滤器及消息空态属于背景表达；must-match 聚焦可用区域、输入/发送与既有导航层级，不授权实施时删除当前产品的筛选器、菜单、语言选择或其他既有控件。真实画面与源码共同确认原型没有引入新的产品导航或改变详情底栏语义。

**原型实际渲染与操作。** 独立打开 `http://127.0.0.1:18778/prototype.html`，通过浏览器 viewport 与截图检查：

| Viewport / 状态 | 独立观察结果 |
| --- | --- |
| 1440×900，默认 | 三列局部展示完整，认证主操作、列表四入口和 composer 均有明确层级，没有横向裁切。 |
| 375×812，默认 | 单列展示，各组件边界完整，输入及发送按钮均留在组件宽度内。 |
| 375×812，短高度 + 键盘占位 | 开启两个演示控件，输入两行草稿；textarea 增高，返回和发送仍可见，消息区让出空间。登录内容可滚动到 Sign in 与页脚。 |
| 短高度，导航切换 | 点击 Tasks 后选中态正确变化，四个按钮完整可达；此处仅核对原型选中反馈，不声称真实 Tasks 路由验收。 |
| 430×932，恢复默认高度并关闭占位 | 两行输入仍保留，输入和发送区域恢复到组件底部，列表四入口完整。 |
| 600×960，中间宽度 | 实际查看全页渲染，认证与列表扩大、详情限制最大宽度；文字和按钮不挤压、无横向裁切。 |

原型页外层明确标出背景、修改及演示边界，键盘占位明确标注“仅演示”。截图保留在本轮浏览器工具结果；本报告记录了可重现 URL、尺寸、操作和结论，未把 DOM 检查替代视觉证据。原型设备框是局部容器，375/430/600 的外层 viewport 不等于同尺寸的真实 iPhone CSS 视口；以上仅审查布局表达。浏览器临时 viewport 已复原，本轮创建的 tab 已关闭，未控制 iPhone。

**需求、delta 与 milestone。** incident 的三组需求分别落到 M1 R1（输入及跨页）、R2（主屏导航/再启动）、R3（真实软件键盘与草稿）、R4（Safari/桌面）；W1/W2 对应 HTTP/测量及 must-match 截图证据，W3 保留 Full 验证职责。delta 只添加两个消费者可观察的 Requirement，canonical target 为 `docs/specs/im/web-chat-ux.md`，没有 MODIFIED 导致既有 Scenario 丢失；没有把认证字段表现扩展成认证协议改动。现有移动回车、composer 增高、按会话草稿、消息历史和手动缩放都仍须保留。`M1-mobile-viewport/.gitkeep` 骨架存在，没有提前填写 tasks/progress。feat-578 的原生 App、签名续期和通知能力与 577 分离，没有共享实施边界冲突。

**验收前置和边界。** Runbook 提供 e2e-up/e2e-down、构建、Vite 到隔离 IM 的路径及健康检查；独立核读 `scripts/e2e-up.sh:281-284` 确认测试身份由脚本准备，且本轮真实隔离栈已能登录并进入聊天。设备与同 LAN 来源已落实，软件键盘明确需要用户真机配合且不能由镜像硬件 Return 代替。这不是当前已通过项：实施后没有取得 R3 实测就不能产品验收通过。旧安装可能需要一次重新添加，与“日常使用不反复重装”要求兼容；应在产品验收记录中区分新安装、旧安装恢复和后续启动。

### 历史问题闭环

无历史 Round，无待关闭问题。

### Issues

无。

### Recommendations

无额外阻断或可选重设计要求。实施时落实上文已在设计范围内的 manifest 静态路由与真机验收即可。

### Author Resolutions

2026-10-05，author 核实本轮无 Issues，无实质异议；四个受审文件与上述内容摘要一致。manifest 显式静态路由按设计已允许分支实施。Gate 2 有效，交由 change-orchestrator-simple 推进；新增本段不改变受审设计。

## Round 2

### Metadata

- reviewer target: `/root/review_577_design`，复用 Round 1 独立 reviewer；未参与设计修订或产品实现。
- review_mode: `delta`
- mode_reason: 新增编辑期间 visualViewport.offsetTop 补偿，属于有界实质设计变化；不是旧文档问题的 closure。需求、模块职责、milestone、delta-spec 和原型目标未变，无需 full 重审。
- started_at: `2026-10-05T00:36:32+08:00`
- completed_at: `2026-10-05T00:37:21+08:00`
- duration: `PT49S`
- checkout: `/Users/czj/.codex/worktrees/unit-bugfix-577/nano-multiagent`
- branch: `codex/bugfix-577-iphone-viewport-navigation`
- executed_base: `main 1daf6676debe129088d9bd0612b489d1eba0301a`
- validated_at: `e6b202cb87c4deb4e9f9763d5c78e59d28576dba` 加本地 `design.md` 第 4 决定及末节修订。
- design SHA-256: `119ce27fe77ee66977738e2add9505a4a525a02078a2ac7434fc53af1b53a3b1`
- effective_base / effective_through: 上述 executed_base 与受审设计摘要；不包含尚未形成的 offset 实现及修后产品结论。
- retained_from: `Round 1`。独立重算 incident、prototype、delta-spec 的 SHA-256，分别仍为 `66058421…0056`、`60b9d48f…d9b2`、`68ba28a5…52b7`，与 Round 1 完全一致；milestone 行未修改。保留 Round 1 的范围、manifest、字号、原型呈现与职责判断，不把旧源码现状断言当作当前实现状态。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING.**

这次补偿回应已实测的编辑期视口平移，仍由原有 hook/CSS 承担，无需新的全局滚动控制或平台框架。批准的是修订方向；产品回归 I1/I2 均不因设计批准而关闭。

### Coverage 与证据

**必要性与证据边界。** 独立阅读 `M1-mobile-viewport/regression.md` Round 1 的 I1：主屏聊天在 composer 聚焦后标题/返回进入状态栏，Done 后恢复，发送与草稿仍可用。继而读取本机 `output/bugfix-577/viewport-samples.log` 三个 JSON 样本及 `viewport-observer.js`：pageshow 时 height=873、scale=1、offsetTop=0、scrollY=0、root.top=0；focusin 时 visual height 已变 805；稳定 scroll 样本中 innerHeight/visual height 都为 805、scale=1、offsetTop=68、scrollY=68，root/shell/header.top 均为 -68，header.bottom=-3。高度覆盖已发生但顶部仍被移出，支持“现有高度调整不足”的判断。记录脚本只读 DOM/样式与视口值并向同源诊断 URL 报样本，不写 DOM 样式、不调用 scrollTo、不读取输入文本。composer 选择器在这些样本中未命中，均为 null；因此不从该日志推导发送区的修后位置。失焦恢复的证据来自独立产品报告，日志本身没有失焦样本。

**实际接线和责任。** 重新读取当前 `app/providers.tsx`、`hooks/use-mobile-viewport.ts` 及 `styles/global.css`。AppProviders 已在真实入口调用 useMobileViewport；该 hook 已拥有 focusin/out、visualViewport resize/scroll、window resize/pageshow 及清理，当前只发布 height。`#root` 当前只有统一高度，移动 shell/header 仍处理安全区。新增 offset 应与 height 由同一条件和生命周期发布/移除，由移动 `#root` 的 relative top 消费；不需要第二组监听器、各页面补丁或保存额外业务状态。这里的根容器指 `#root`，不是把 body 或 documentElement 整体设为 fixed。

**偏移、缩放与滚动。** 对当前稳定样本，既有 root/header.top=-68，加实际 offsetTop=68 能表达将内容上缘恢复到原点的目标；68 只用于说明证据，不成为实现常量。设计继续要求手机断点、可编辑焦点和 scale≈1，失焦/缩放/桌面及卸载清理覆盖，CSS 默认偏移 0。这把作用域限制在既有输入生命周期，不借浏览器 offset 改写消息列表 scrollTop、认证页内部滚动、路由或草稿。relative top 不使用 transform，也不把根节点变为 fixed，因此不会因新 transform 改变既有 fixed 浮层的包含块。补偿对浏览器后续自动滚动的最终影响仍须真机回归证明，现有日志不是修后 A/B；当前没有证据要求增加轮询、强制 scrollTo 或另一层补偿。

**未变的产品目标与验证投影。** 修订恢复原有 must-match 的标题/返回位置，没有新增产品交互或新的视觉目标；保留 Round 1 原型与当前回归报告已有的真实渲染证据，本轮按 caller 边界不操作手机、不重绘或重跑未变原型。M1 R3/W1/W2 已涵盖该偏移的生命周期测量、关键操作及真实画面对照；修后至少重走已失败的 standalone focus → 多行输入 → Done，并核对 header/发送可达、内部滚动与草稿，同时按原矩阵完成真实软件键盘、手动缩放及恢复。无需为了此实现细节修改消费者 delta-spec，也不扩展 feat-578。设计末节明确诊断注入在交付构建移除。

### 历史问题闭环

- Round 1 设计 Issues：无；Author Resolutions 已确认原设计，本轮没有追溯改写旧结论。
- 产品回归 I1：设计修订已覆盖其已测原因；**仍待实现及独立产品复验**，本轮不标 closed。
- 产品回归 I2：真实软件键盘、手动缩放等证据缺口不在本轮设计审查中关闭；原验收要求继续有效。

### Issues

无。

### Recommendations

- **R2-R1（可选，文档一致性）**：`design.md:45-46` 的接口摘要仍写“唯一作用”是发布 height，数据流也只列高度。第 4 决定已明确新增 offset 的范围和生命周期，不妨碍正确实施；可在 author resolution 时将摘要同步为 height/offset 两项，避免单独阅读接口节时遗漏已批准内容。这是已批准决定的摘要同步，不要求再次实质复审。

### Author Resolutions（Round 2）

作者核实0 CRITICAL / 0 WARNING；接受编辑期间实际offsetTop补偿，范围未扩大。接口摘要同步height/offset文字，与本轮已审决定同义；不新增Round。真正软件键盘、I1/I2产品复验仍为实施退出条件，未将设计批准代替产品通过。
