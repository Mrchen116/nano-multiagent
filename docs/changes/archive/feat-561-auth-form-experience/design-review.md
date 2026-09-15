# Design Review: feat-561

## Round 1

### Metadata

- reviewer: `/root/feat561_design_review`
- review_mode: `full`
- mode_reason: 首轮独立 Gate 2 审查；完整核对冻结 spec、design、prototype、IM delta-spec、M1 骨架，并从 current specs、真实 frontend/auth/AppShell/CSS/i18n/tests、后端 auth 规则和 worktree runtime 约束追到实际产品组装入口。
- started_at: `2026-09-15T12:19:00+08:00`
- completed_at: `2026-09-15T12:31:00+08:00`
- duration: `12m 00s`
- baseline: `main@7e313956275f`；主仓已有大量与本 unit 无关的 dirty/untracked 内容，本轮仅新增本报告。没有运行产品实现或把原型当作实现证据；原型仅在本地临时 HTTP 服务中以 Playwright 查看了 `1280x800` 初始态、`390x844` 初始态及空提交态，临时浏览器和 HTTP 服务均已关闭。

### Verdict

Issues Found — **2 CRITICAL / 2 WARNING**。

前端-only 的职责边界、现有 auth API/i18n/session 复用、共享 `NanoBrand`、小型 field/feedback 模块和单一 M1 垂直切片总体合理；原型也确实把旧居中卡片迁到了与当前 AppShell 同源的现代视觉语言。进入实施前仍须补齐移动端真实滚动边界和完整原去向导航，并消除 pending 语言切换与冻结场景的冲突；delta-spec 还不能无损承接首文档。

### Issues

- **[R1-C1][CRITICAL] [移动布局 / `design.md:57-61,130,157-165,174-181,197`] 方案没有承接当前应用的滚动所有权，较矮手机上认证主操作可能被全局裁掉。** 原型自己的 `body` 允许文档自然滚动（`prototype.html:32`），所以本轮在 `390x844` 看起来完整；真实前端却在 `global.css:71-82` 固定 `body/#root` 为 `100vh`，并对 `body` 设置 `overflow: hidden`。新注册页的移动单列包含品牌栏、产品语境、三字段、hint/error、主按钮和页脚，内容高度会随错误文案、英文换行和较矮 viewport 增长；设计只定义宽/窄重排，没有指定 `AuthPageFrame` 自己成为 `height/min-height: 100%` 下的纵向滚动容器，也只验 `390x844`，无法暴露常见较矮手机的裁切。**不改的后果：** worker 完全按原型/CSS token 实现仍可能在 `375x667` 一类 viewport 看不到密码错误、提交按钮或页脚，且由于 body 被锁无法滚到它们，直接违反 `spec.md:45-48,127-130`。请拍定认证 frame 的纵向 overflow/可滚动责任，并把一个较矮手机 viewport 的空提交或长文案状态加入 must-match/reviewer 验收；无需改变现有登录后 AppShell 的全局 overflow 策略。

- **[R1-C2][CRITICAL] [提交流 / 原去向 / delta-spec，`design.md:132-139,193-197`] “返回 route guard 保留的 `from`”把当前不完整行为误当成已闭合能力。** 真实 `RequireAuth` 只保存 `location.pathname`（`src/IM/frontend/src/features/auth/require-auth.tsx:20-29`），`LoginPage` 再把这个字符串交给 `navigate()`（`login-page.tsx:14-19,29-32`）；它会丢失 query/hash。仓内受保护页面确实使用 query 作为页面语义：聊天读取 `?message_id=` 定位原消息（`chat-workspace-page.tsx:308`），Agent 页读取 `?view=work`（`agent-profile-page.tsx:19`、`agent-detail-page.tsx:1284`），并存在生产链接生成这些地址（`message-pane.tsx:1702`、`work-thread-link.tsx:12`）。M1 仅写“原去向不回归/成功导航”，delta-spec 完全没有成功后导航场景，都不足以迫使实现保存并验证完整 location。**不改的后果：** 未登录用户打开原消息或 Agent Work 深链，登录后只回到基础 path，丢失真正尝试访问的视图，不满足 `spec.md:120-123`。请明确 `from` 的完整内部 URL 形态、守卫 producer 与登录 consumer，以及最低层含 query 的回归用例；同时把成功导航行为投影到 IM delta-spec。这里不要求新增路由抽象。

- **[R1-W1][WARNING] [决策 6/7 / prototype pending，`design.md:83-89,176-180`] pending 时禁用语言切换与冻结的语言场景相冲突。** `spec.md:136-139` 和 delta `auth-tenancy.md:29-32` 明确列出“提交状态”也应在切换后立即使用新语言；但设计要求请求期间锁定语言控件，原型也在 `state.submitting` 时给两个 locale button 加 `disabled`（`prototype.html:267`）。语言切换复用 i18n store，只影响渲染文案，并不改变正在发送的 auth payload；设计没有说明这里存在必须牺牲冻结场景才能规避的竞态。**不改的后果：** reviewer 无法按同一份契约验证 pending 文案即时切换，worker 只能在 spec 与 must-match prototype 之间任选其一。请让语言控件在 pending 时仍可用，或回到首文档显式收口另一种行为并同步 delta/prototype/M1。

- **[R1-W2][WARNING] [IM delta-spec，`specs/im/auth-tenancy.md:3-36`] delta 是首文档的有损摘要，遗漏两项计划长期维持的新认证契约。** 首文档要求服务端拒绝可修正输入时给出本地化字段反馈且不暴露内部原文（`spec.md:91-94`），并要求辅助技术能依靠字段状态、文案、焦点及控件可读名称定位问题（`spec.md:131-134`）；design 的 feedback 投影和 field `aria-*` 接口虽然覆盖它们（`design.md:71-77,107-130`），delta 只枚举重名/凭据/服务异常与一般本地校验，没有这两个 Scenario。成功导航缺口另见 R1-C2。**不改的后果：** unit 归并后 canonical auth-tenancy 无法完整承接本次用户可观察行为，后续 verifier/维护者可能把服务端字段投影或无障碍语义当作一次性实现细节。请把遗漏场景补入当前 ADDED Requirement；无需把内部 feedback code、DOM 结构或精确文案写入 canonical spec。

### Recommendations

- **[R1-R1]** 将 prototype 顶栏的 `Nano IM`（`prototype.html:266`）改为 current i18n/AppShell 的 `nano IM`（`src/IM/frontend/src/i18n/en.json` 与 `zh.json` 的 `shell.appName`），或在 must-match 表明确 casing 可适配。设计已要求共享 `NanoBrand` 并保持 AppShell 可观察文案，因此实现方向不会受阻，但当前截图会制造一个不必要的视觉对照差异。
- **[R1-R2]** 修正 Runbook 的“无仓库外资源”措辞：`global.css:1` 和 prototype 均从 Google Fonts 加载 IBM Plex。若验收允许系统 fallback，写明 font 网络加载不是前置；若要求精确字体，则把网络可用性列为前置。该点不影响结构与交互判断。

### Coverage

本轮完整覆盖：6 条现状断言与既有约束、7 项关键决策、内部组件接口与提交流、前端原型及 7 行对齐契约、风险/回退、Runbook、唯一 M1；首文档 6 个 Requirement/19 个 Scenario、用户场景、范围/非目标；IM delta 的 1 个 ADDED Requirement/6 个 Scenario；M1 目录只含 `.gitkeep`，符合设计阶段骨架约束。

#### 现状、组装入口与运行约束

| 核实项 | 独立证据与结论 |
|---|---|
| 认证页面真实入口 | `src/IM/frontend/src/app/router.tsx:17-18` 直接挂载 `LoginPage`/`RegisterPage`；两页当前各自持有 value/error/submitting，使用 `noValidate` 且无本地校验（`login-page.tsx:15-25,35-69`；`register-page.tsx:12-25,44-94`）。设计 grounding 成立。 |
| API 与服务错误 | `auth-api.ts:11-39` 将非 2xx 包为 `AuthApiError(status, detail)`；当前页面仅投影登录 401、注册 409。FastAPI schema 限制 username 1-64、password 1-256、display_name 1-128（`src/IM/api/routes/auth.py:43-52`），应用服务另检查空白、保留身份、密码 8 位和重名（`auth_service.py:99-135`）。本地镜像少量稳定规则并保留服务端权威是合理的；无需为本 unit 扩后端 schema。 |
| 防枚举与成功会话 | 登录 route 将未知用户名/错密码统一为 401 `invalid credentials`（`auth.py:115-129`）；注册/登录成功返回现有 token pair。设计复用 `setSession()` 且不区分凭据字段，符合 current `docs/specs/im/auth-tenancy.md:10-20`。 |
| i18n | `i18n/index.ts:7-46` 已有 `im_lang`、中英文、即时 changeLanguage 与 localStorage 持久化；`user-menu.tsx:170-193` 的 `EN | 中` 是真实既有语法。复用 store 正确，pending 禁用冲突见 R1-W1。 |
| 现代视觉 grounding | `global.css:5-43` 定义浅蓝灰/白色、青绿、边框、品牌、IBM Plex token；`app-shell.tsx:32-49` 的 48px 顶栏含勾选方形、`nano IM` 与 internal badge。原型在本轮实看 `1280x800` 和 `390x844`，宽屏双区、窄屏单列、字段错误与首错 focus 表达清晰；真实 body overflow 缺口见 R1-C1。 |
| 测试 seam | `auth-gate.test.tsx:37-106` 已覆盖 guard、成功登录入库和 401；`app-shell.test.tsx:55-76` 覆盖桌面品牌与移动导航。扩展 auth 页面 seam 并保留 shell 测试是最低合适层；真实 layout/网络拦截留给 browser reviewer，没有要求跨层复制 Python 测试。 |
| 隔离运行 | `docs/development/worktree-runtime.md` 明确 `e2e-up/down` 隔离端口、SQLite/JWT、Gateway config/workspace/node，IM 直接服务已构建 dist；design Runbook 使用高位脚本且不碰 `:8011`。视觉旅程由真浏览器补足，方向成立；字体前置措辞见 R1-R2。 |

#### 决策、需求、delta 与 milestone

| 原子 | 本轮结论 |
|---|---|
| 决策 1：现代认证 frame | 共享品牌顶栏、产品语境和独立表单面板能承接用户明确要求的近期 Web IM 风格，又没有复制登录后导航；`NanoBrand` 抽取让 AppShell/auth 使用同一真实标识，职责正确。纵向滚动边界未闭合，见 R1-C1。 |
| 决策 2-5：校验与反馈 | 受控本地校验、反馈代码延迟翻译、字段/页面分层、编辑时局部清理共同覆盖空值、短密码、重名、凭据错误、服务异常和切语言保留状态；小纯函数/字段组件足够深且没有引入表单引擎。服务端可修正拒绝需进入 delta，见 R1-W2。 |
| 决策 6-7：pending 与 locale | 只在 pending 禁止重复提交、保留可触发完整校验的 submit 是合理选择；语言也被一起禁用则和冻结场景相反，见 R1-W1。 |
| 可访问字段接口 | `label/id`、hint/error `aria-describedby`、`aria-invalid`、首错 ref、显隐按钮 label 和可读 pending 文案能覆盖键盘/辅助技术场景；组件不读取 API/router/store，职责内聚。长期契约遗漏见 R1-W2。 |
| 成功导航 | 注册入首页与登录返原去向都有 spec 驱动；真实守卫只保存 pathname，完整深链不成立，见 R1-C2。 |
| 视觉 Requirement（桌面/手机） | 原型和现有 token/品牌同源，desktop 聚焦且 mobile 自然重排；没有伪造 Chat/Agents 导航。真实较矮 viewport 的滚动仍未设计。 |
| 表单规则与显隐 Requirement | optional display-name、8 位 hint、两页 password toggle 都有原型、组件接口与 M1 reviewer/worker 投影；切换不提交/改值的边界明确。 |
| 字段反馈 Requirement | 空注册/登录、短密码、首错 focus、edit clear、无 fetch 均在提交流和 M1-W2；不是仅靠浏览器气泡。 |
| 服务拒绝/异常 Requirement | 409 重名、401 统一凭据、network/unknown retry、输入保留均有落点；不显示 raw detail 的边界正确。delta 未记录一般服务端字段拒绝。 |
| pending/成功 Requirement | pending 文案和去重有 page state、prototype 与 M1；注册成功沿用 session+home。原去向缺陷见 R1-C2。 |
| 设备/语言/操作方式 Requirement | 双 viewport、反馈 code 延迟翻译、持久 locale 与 field aria 设计基本覆盖；mobile scroll 为 C1，pending locale 为 W1，a11y delta 为 W2。 |
| delta-spec | canonical target `docs/specs/im/auth-tenancy.md` 正确，ADDED 不覆盖 current JWT/tenancy Requirement；但场景集合有损，见 C2/W2。 |
| M1 | 单一前端垂直切片没有可并行的跨包工作，scope 包含 shell/auth/i18n/CSS/测试/evidence，worker 与 reviewer 退出标准总体可观测；C1/C2/W1/W2 修订后无需拆 milestone。 |

### Architecture Judgment

- **职责与依赖方向：** 变更留在 IM frontend，不引入 `agent` 或 sibling package 依赖；页面拥有 API/session/navigation，纯反馈模块拥有规则投影，field 组件拥有 DOM 可访问性，frame 拥有未登录布局，边界合理。
- **已有能力复用：** 复用 auth API、session store、i18n store、全局 token 和现有品牌，避免第二套 locale/state/token；抽取一个共享 brand 组件有两个真实消费者，不是为假想扩展造抽象。
- **复杂度：** 两个小内部组件模块加一个反馈纯函数足以消除登录/注册重复，又没有配置化成通用表单框架；单 M1 比横切拆分更容易保持 must-match 与行为一致。
- **治本性：** 字段级反馈、延迟翻译和共享视觉身份能直接修复用户指出的旧反馈与旧风格断层。剩余 C1/C2 是实际 runtime/navigation 边界，不是追求架构最优；修订它们不需要扩大到后端或新状态容器。

### Author Resolutions

- **R1-C1 — accepted.** `spec.md` 已增加较矮视口及错误增高时的纵向可达标准；`design.md` 拍定 `AuthPageFrame` 为 `#root` 内唯一认证纵向滚动 owner，不改全局 body/AppShell，并把 375×667 英文多错误态加入 prototype must-match、Runbook 与 M1-R1/W1；`prototype.html` 同步锁住 body 并让 shell 自身滚动。
- **R1-C2 — accepted.** `spec.md` 已把成功返回明确为完整 path/query/hash；`design.md` 拍定 `RequireAuth` 生产 `pathname + search + hash`、`LoginPage` 消费原字符串，补充最低层测试与 reviewer 深链旅程；IM delta 新增登录返回原始深链 Scenario。
- **R1-W1 — accepted.** `design.md` 将 pending 锁定范围收窄为字段、密码显隐、页脚跳转和提交；locale 继续可用，M1-R4/W3 明确验 pending 即时翻译。`prototype.html` 移除 locale 的 pending disabled。
- **R1-W2 — accepted.** IM delta 补入服务端可修正输入的本地化字段反馈/不暴露内部原文，以及字段状态、文案、首错焦点和控件可读名称的辅助技术 Scenario。
- **R1-R1 — accepted.** 原型品牌文案改为 current AppShell/i18n 的 `nano IM`。
- **R1-R2 — accepted.** Runbook 明确 Google Fonts 网络不是验收前置，断网时允许现有系统 sans fallback。

## Round 2

### Metadata

- reviewer: `/root/feat561_design_review`
- review_mode: `full`
- mode_reason: Round 1 修订不仅处理历史问题，还改变了冻结 spec、完整 URL 的 route-guard producer/consumer 契约、delta-spec、prototype must-match 与 M1 退出标准；涉及需求、核心导航边界和 milestone，按 reviewer skill 重新执行 full review，不能只做 closure。
- started_at: `2026-09-15T12:34:00+08:00`
- completed_at: `2026-09-15T12:43:00+08:00`
- duration: `9m 00s`
- baseline: `main@d8d78af3f8e5`；`7e313956275f..d8d78af3f8e5` 没有触及本轮核实的 auth/frontend、auth backend、current IM spec 或 worktree runtime 路径。主仓仍有既有 dirty/untracked 内容，本轮只向本文件追加 Round 2。
- static_check_note: `PYTHON=.venv/bin/python ./scripts/docs-check` 仅报告 `docs/research/studies/README.md` 指向两个未跟踪研究目录的既有 dirty-worktree 断链；本 unit 未引用这些路径，本轮未越界修改。报告自身无 trailing whitespace。

### Verdict

Approved — **0 CRITICAL / 0 WARNING**。

Round 1 的四项阻断发现已全部闭环，两项 recommendation 也已正确吸收。修订后的方案能够在 current Web IM 的真实滚动、路由、auth API、i18n 与测试边界中兑现冻结需求；delta-spec、prototype must-match、Runbook 和唯一 M1 已重新对齐，可进入实施。

### 历史问题闭环

| 历史项 | Author Resolution | 本轮独立证据 | 状态 |
|---|---|---|---|
| R1-C1 | 认证 frame 成为 `#root` 内唯一纵向滚动 owner，并新增 375×667 英文长错误态 | `design.md:24,65,167,188,198,206` 明确 `height:100%`、`min-height:0`、`overflow-y:auto`、sticky topbar，不改全局 body/AppShell；与 current `global.css:71-82` 的 `100vh + overflow:hidden` 精确咬合。原型 `prototype.html:32-48,73-83,189-200` 同样模拟该约束。本轮 Playwright 在 375×667 英文空提交态实测 `.shell clientHeight=667 / scrollHeight=864 / maxScroll=197`，滚到底后 footer bottom `606.4375 < 667`，主操作与页脚可达。 | closed |
| R1-C2 | `RequireAuth` 保存、`LoginPage` 恢复完整 pathname/search/hash；补最低层与 reviewer 深链验证 | `design.md:11,52,95-97,145,198,206` 明确 producer、consumer、内部来源与测试；`spec.md:120-124` 和 delta `auth-tenancy.md:48-52` 写成消费者可见完整位置。current 深链消费者仍是 `chat-workspace-page.tsx:308` 的 `message_id` 与 `agent-detail-page.tsx:1284-1286` 的 `view`，故修订准确覆盖真实缺口，没有新增路由抽象。 | closed |
| R1-W1 | pending 只锁字段、显隐、页脚与 submit，locale 保持可用 | `design.md:87-97,187,198,206`、delta `auth-tenancy.md:42-46` 和 prototype `:272,285-287` 一致。独立原型实测 pending locale `disabled=false`，按钮文案从 `Creating…` 即时变成“正在创建…”，输入状态未被重建。 | closed |
| R1-W2 | delta 补服务端可修正字段反馈/不泄露 raw detail，以及辅助技术场景 | delta `auth-tenancy.md:29-34,37-40` 分别承接 `spec.md:91-94,133-136`；设计仍以反馈代码、字段 `aria-describedby`/`aria-invalid`、首错 ref 与可读按钮文案实现（`design.md:71-81,103-138`），没有把 DOM 或内部 feedback code 泄漏进 canonical 契约。 | closed |
| R1-R1 | 原型品牌 casing 改成 `nano IM` | prototype `:271` 已与 current `shell.appName` 和共享 `NanoBrand` 决策一致；桌面/手机 snapshot 均显示同一品牌。 | closed |
| R1-R2 | Google Fonts 不再被误写成必需前置 | `design.md:200` 明确网络字体只是尝试加载，断网允许现有 system sans fallback；与 `global.css:1,41-42` 的真实 fallback stack 一致，不再阻塞隔离验收。 | closed |

### Coverage

本轮重新覆盖修订后的全部输入：首文档 6 个 Requirement/19 个 Scenario、8 项关键决策、内部组件与提交流、原型全部交互和 7 行 must-match/may-adapt 契约、风险/回退、Runbook、IM delta 的 1 个 ADDED Requirement/9 个 Scenario，以及唯一 M1 和仅含 `.gitkeep` 的骨架。Round 1 未受修订影响的 auth API、backend rule、i18n/session、AppShell token/brand 与既有测试证据也在当前 baseline 重新抽查；main 增量未改变这些结论。

#### 现状、设计决定与真实落点

| 原子 | Round 2 结论与证据 |
|---|---|
| 页面/API grounding | `app/router.tsx` 仍直接挂载 login/register；两页当前仍是页面 local state + `noValidate`，`auth-api.ts` 仍提供 status/detail，FastAPI/AuthService 仍以 1-64/1-256/1-128、8 位、保留身份与重名为权威。设计的本地校验是请求前 UX，不替代 server authority，也无需后端 schema。 |
| 现代视觉与滚动 | 全局 token/AppShell 品牌仍是实际基线；共享 `NanoBrand`、AuthPageFrame 双区/单列与 frame-owned scroll 分别隐藏身份复用和未登录布局复杂度。原型同时复现真实 body lock，较矮 viewport 已有可重查数值与 M1 evidence 要求，R1-C1 闭合。 |
| feedback/field 边界 | `auth-form-feedback.ts` 只承接稳定规则与 API error 投影，field 组件只承接 label/id/hint/error/显隐；页面保留 submit/API/session/focus/navigation。三个层次各有真实职责，不是通用表单引擎或第二套状态容器。 |
| locale | 继续复用 `im_lang` 和 `setLanguage()`；反馈 state 保存 code 后在 render 翻译，使静态、字段错误、服务错误与 pending 文案都可即时切换。pending 不再锁 locale，R1-W1 闭合。 |
| 完整原去向 | 一个内部 URL 字符串足以封装 pathname/search/hash；producer 在 guard、consumer 在 login，符合现有 React Router 用法并保护真实 `message_id`/`view` 深链。没有把外部 URL/query 变成 redirect target，R1-C2 闭合。 |
| 服务拒绝与安全语义 | 409 重名进 username，已知可修正规则映射到字段，401 仍统一凭据错误，网络/未知服务错误进 retry alert，raw detail 不展示；当前防用户枚举语义不变。 |
| 测试与运行 | `auth-gate.test.tsx` 是 guard/login 成功与 401 的现有最低 seam，`app-shell.test.tsx` 保留品牌回归；M1 扩展 path+query+hash、无 fetch、focus/clear/toggle/pending/locale。真实 layout、network interception、deep-link journey 留给隔离栈浏览器 reviewer，分层正确。 |

#### 全部需求、delta 与 milestone

| 范围 | Round 2 结论 |
|---|---|
| 现代设计语言（desktop/mobile） | 品牌、token、字体 fallback、线性图标、surface/border、宽屏双区和窄屏单列都有 must-match 与真浏览器验收；375×667 长错误态补齐纵向可达，不复制登录后导航。 |
| 输入规则与密码显隐 | required/optional、8 位 hint、两页 show/hide、不改值/不提交均有组件接口、prototype 和 M1 reviewer/worker 投影。 |
| 本地字段反馈 | 注册/登录空值、短密码、首错 focus、edit clear、无请求完整落在 validate → FieldErrors → ref 流程，且不在每键持续责备。 |
| 服务拒绝与异常 | 重名、可修正 server rule、401、网络/服务错误、输入保留和 raw detail 边界均由 design 与 delta 承接；current API 足以实现。 |
| pending 与成功 | 明确 processing、重复提交门禁、注册进首页、登录恢复完整深链均在提交流/M1；locale pending 可切，不与 pending 去重冲突。 |
| 设备、语言、键盘/辅助技术 | viewport/scroll、延迟翻译+持久化、field state/described-by/focus 和控件 readable name 全部闭合；原型证明结构可行，M1 要求在产品真栈验收。 |
| delta-spec | canonical target `docs/specs/im/auth-tenancy.md` 正确；ADDED Requirement 不覆盖 current JWT/tenancy，9 个 Scenario 已包含视觉/scroll、规则/显隐、本地反馈、拒绝/异常、server field feedback、locale、a11y、pending 与完整深链。消费者视角成立，无内部类型/DOM 泄漏。 |
| M1 | 仍是一个合理的前端垂直切片；scope 包含新增 `require-auth.tsx` 所在 auth 目录、shell/auth/i18n/CSS、最低层测试与 browser evidence。worker/reviewer 退出标准逐项投影 spec、delta 与 prototype，无并行冲突或未指定 milestone。 |

### Architecture Judgment

- **职责/依赖：** 仍严格位于 IM frontend；没有引入 `agent`、Gateway 或 sibling package 依赖。frame/field/feedback/page/guard 的职责与实际变化原因一一对应。
- **复用/抽象：** 复用 auth API、session store、i18n store、全局 token 和品牌组件；新增模块只集中两页真实重复点，没有表单 DSL、兼容路径或新状态容器。
- **数据流闭合：** input → local codes → translated field/page feedback、valid submit → auth API → session → home/full internal URL，以及 locale/pending 和 height/overflow 两条交叉状态都有明确 owner 与验证点。
- **实施与回退：** 单 M1 可独立实现、测试、真栈验收和整体回退；不涉及后端、数据迁移或生产部署。当前方案在满足用户的错误交互与现代视觉迁移时保持了最小跨层面积。

### Issues

- None.

### Recommendations

- None; Round 1 的 findings 与 recommendations 均已闭环。
