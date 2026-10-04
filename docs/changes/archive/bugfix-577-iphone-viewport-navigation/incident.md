# bugfix-577: iPhone 输入缩放与主屏 Web App 导航遮挡

状态：completed，2026-10-05 用户实体确认与独立门禁完成；canonical 已归并，待 PR 审查及合并，未生产发布。

路径：Full Bugfix。需要独立覆盖 Safari / 主屏 Web App、未登录安装 / 已登录启动、聚焦 / 收起输入 / 页面切换的回归矩阵；桌面窄视口测试不能覆盖系统导航栏与真实输入行为。

## Relations

- Related: feat-340, feat-451

## 原始报告与范围确认

2026-10-04，用户要求在真实 iPhone 上体验 IM：

> 各种界面，各种体验都可以做做，来发现真正的问题

用户在体验过程中确认：

> 又是一个小幅放大的状态

本轮体验报告列出的前两项问题分别是“输入框聚焦后的页面放大与裁切”和“主屏 Web App 登录后的浏览器栏遮挡”。用户随后要求：

> 好，新开unit，专门修前两项问题

Agent 解读：本 unit 只修复这两项及必要的共同视口、导航适配。不包含主屏品牌/图标设计、Overview/Sessions 占位页、历史加载空态、Agent 功能扩展。若修复导航必须补充 Web App 配置，其范围限于正确启动与站内导航，不扩展为完整 PWA、离线缓存或推送项目。

## 环境与证据基线

- 观察时间：2026-10-04 约 23:00–23:24（Asia/Shanghai）。
- 正式入口：`https://im.nanoim.win/`；通过 macOS iPhone Mirroring 操作真实 iPhone。
- 安装路径：Safari `/login` → 分享 → Add to Home Screen，Open as Web App 开启 → 从 `IM Frontend` 图标启动。首次登录页没有浏览器工具栏，用户本人完成登录；登录后观察到工具栏。
- 通过系统应用切换器确认前台卡片名为 `IM Frontend`；不能把出现浏览器控件简单解释为用户误开普通 Safari。
- 当次线上静态资源：`index-D9aTLu4x.js`、`index-DVUR9I21.css`。本地源码参考为 `main` 的 `d357729af`，不将它冒充线上部署 revision。
- 完整本机体验记录：`output/iphone-im-review-20261004/review.md`；线上 CSS 样本：同目录 `live.css`。关键事实已写入本文；这些本机产物不提交，也不是接手此 unit 的必需文件。
- 实机截图保留在本聊天工具结果中；本次未形成仓库内图片证据。实施验收须新采修前/修后的真实渲染证据。
- 系统设置实读：iPhone 15 Pro Max，iOS 26.4。隔离实验使用同一设备与浏览器。

## 现象与复现

### 问题 A：输入框聚焦后页面放大，离开后仍裁切

1. 主屏启动，点击登录页 Username；或登录后进入单聊点击消息输入框。
2. 在聊天列表点击 Search，或在 Agent 列表点击 Find Agent。
3. 结束输入，再进入群聊、群设置、Agent 配置或工作页。

实际：页面整体放大，右侧登录表单、发送按钮、搜索框边缘或设备信息被裁出可见区域；结束输入和切换页面后仍保留放大状态。用户直接确认了小幅放大。一次工作页刷新恢复正常宽度，但再次聚焦可重现；不承诺刷新总能恢复。

期望：正常输入不引起额外放大和横向裁切，收起输入及站内切换后布局保持可用，用户仍能主动缩放页面。

### 问题 B：登录后主屏应用中的浏览器栏遮挡关键操作

1. 从上述主屏图标启动并完成登录，进入聊天列表。
2. 打开具体会话，再进入 Agent 页面，并尝试使用一级导航。

实际：顶部出现域名/页面菜单，底部出现返回、分享、刷新和 Safari 入口。部分状态的标题/返回被顶部遮挡，聊天输入区与列表页底部导航被底部遮挡。Tasks、Me 未能可靠进入。缩放与遮挡叠加，因此不把单次坐标点击失败额外认定为路由缺陷。

期望：主屏启动后的正常站内登录和导航保持应用内体验，列表页一级入口、详情返回和聊天输入区完整可见、可点击。普通 Safari 保留系统浏览器栏时也能正常使用。

具体会话按现有契约隐藏全局底栏属于正确行为；本问题不要求聊天详情页常驻全局导航。

## 影响范围

两项均为 P1 可用性问题，影响 iPhone 登录、搜索、发消息和跨页导航。现有验证证明至少一条真实消息成功发出并获得回复，但不证明发送按钮和软件键盘旅程通过。没有观察到数据损坏；此 unit 不改变消息、成员权限或认证协议。

## 根因分析（RCA）

### 已确认的实现事实

1. 当次线上 CSS 中 `.im-auth-field` 为 `0.8125rem`，其输入框 `font: inherit`；聊天 `.chat-pane-composer-input` 为 `0.9rem`，移动端规则未覆盖字号。本地 `src/IM/frontend/src/styles/global.css` 同样如此。以 16px 根字号折算分别约 13px 与 14.4px；未采集真机 computed style，折算不冒充实测值。
2. `body`、`#root`、`.im-shell` 使用 `height: 100vh`，`body` 还设置 `overflow: hidden`。页面需要与系统可视区域协同，但当前观察尚不能量化布局视口和可视视口的差值。
3. 线上首页及本地 `src/IM/frontend/index.html` 包含 `width=device-width, initial-scale=1.0, viewport-fit=cover`，没有 manifest 声明。部分聊天区域已有安全区处理，因此不能笼统声称全站没有 safe-area 适配。
4. 本地 `login-page.tsx` 登录成功使用路由 `navigate(..., { replace: true })`。尚无真实设备导航轨迹证明此动作为何触发系统栏，也不能据源码单独排除其他导航环节。

### 同设备单变量对照与根因结论

2026-10-04 23:35–23:42，在同一 iPhone 上打开局域网静态实验页；没有 IM 后端、登录、令牌或 React 依赖。实验脚本与原始测量在本机 `output/bugfix-577-rca/probe.py`、`probe.log`。以下为可独立理解的证据摘要，页面截图保存在本聊天工具结果。

| 对照 | 操作与实测 | 结论 |
| --- | --- | --- |
| 16px / 13px 输入 | 16px 聚焦及 blur 后 scale=1，宽度 430px；13px 聚焦后 scale=1.2302326，宽度约 350px，blur 后仍保留 | 过小输入字号触发 iOS 自动聚焦缩放；失焦不会恢复，SPA 路由继续复用该视口 |
| Safari 100vh / 100dvh | 可视高度 775px，100vh shell=815px，底部与浏览器栏重叠；仅改为 100dvh 后 shell=775px、底部完整露出 | 固定大视口高度不能代表浏览器控件显示时的可用高度 |
| 无 manifest 主屏安装 | `/raw/login` 启动为 standalone；仅 `history.pushState` 到 `/raw/chat` 就出现顶部域名栏和底部工具栏，visual height 从 873 降至 743px，shell 仍为 848px | 无明确应用导航契约时，该 iOS 版本在入口路径以外的 SPA 导航引入系统浏览器控件；不依赖账号或 IM 业务代码 |
| 显式 manifest 主屏安装 | 同页面、同设备，声明 `display: standalone`、`start_url: /scoped/login`、`scope: /`；`/scoped/login → /scoped/chat` 无系统栏，visual height 保持 873px | 明确应用启动和导航范围可消除该最小复现的系统栏切换；不把结果推广为所有 iOS 版本的内部 scope 算法 |
| 主屏 100vh / 100dvh | scoped 应用中 100vh shell=932px、visual height=873px，底部不可用；切为 100dvh 后 shell=873px、底部文字露出 | 去除系统栏仍需独立修复可用高度与安全区，不应只加 manifest |

**根因 A**：前端沿用桌面偏小字号作为手机输入字号，未与 iOS 聚焦放大行为适配。只调整容器宽度不消除自动缩放来源。

**根因 B**：未声明 Web App 的启动/站内导航范围，iOS 26.4 对当前安装路径后的 SPA 导航显示系统控件；同时 shell 以 `100vh` 作为可用高度，移动底栏缺少统一安全区占位，导致系统控件或设备底部侵入关键操作区。导航模式与布局高度是两个都要修的环节。

这些隔离实验收口的是故障机制与修复方向，不是 IM 修后产品验收；完整登录、路由、消息和软件键盘仍按下方矩阵验证。实验通过镜像硬件输入，不能冒充软件键盘证据。

### 官方与社区实践的适用边界

- [WebKit Safari 26](https://webkit.org/blog/17333/webkit-features-in-safari-26-0/#every-site-can-be-a-web-app-on-ios-and-ipados)：无 manifest 也能安装为 Web App；因此不能说缺 manifest 导致“根本不是 Web App”。本机实验定位到的是后续导航行为。
- [Apple WWDC23 Web Apps](https://developer.apple.com/videos/play/wwdc2023/10120/)：manifest 的 scope 定义站内导航边界，iOS 范围外链接使用 Safari View Controller。它支持显式导航配置的选择，不替代本机复现。
- [浏览器工程师的 viewport/keyboard 行为说明](https://github.com/bramus/viewport-resize-behavior/blob/main/explainer.md)：iOS 软件键盘调整 visual viewport，不能把 dvh 视为键盘高度方案。
- [piclaw 的 iOS PWA 实践](https://github.com/rcarmo/piclaw/blob/main/docs/PWA.md)：提供真实聊天应用的高度、安全区和焦点经验；其机型特定补偿、延时重置等只作线索，不整套引入本项目。

### 原始意图、历史与必须保住的不变量

`feat-340` 的 spec“Alex 用手机继续”与 design 的移动布局要求，目标是同一 Web 应用在手机提供可用的单栏聊天、Agent 和 Me 入口；`feat-451` 与 current Web Chat UX 契约保留移动输入发送和 composer 自动增高。修复须保住这些体验、桌面布局、登录后的原深链、既有路由目的地、草稿及正常手动缩放能力。

`git blame` 将 composer `0.9rem` 追溯到 `f7a57e3c67`，登录样式后续经过 `5db91abfcf`；这些是样式历史线索，不等于已经证明的回归引入点。未定位平台版本或导航改变造成的首个坏版本，不编造导致漏检的流程责任。

权威 current 契约见 [Web Chat UX](../../../specs/im/web-chat-ux.md)、[认证与租户](../../../specs/im/auth-tenancy.md)、[任务图](../../../specs/im/task-graphs.md)。修前窄屏单列、底栏可用、聊天详情保留安全区的意图与实机结果存在差距；本 unit 的已验收目标现已归并为 current。

## 验收标准

### Requirement: iPhone 输入不破坏页面比例与宽度

#### Scenario: 登录、搜索与聊天聚焦后保持完整布局
- **WHEN** 用户分别聚焦登录字段、聊天搜索、Agent 搜索和消息输入框，输入文字后结束输入
- **THEN** 页面不因该动作额外放大或横向裁切，字段、右侧操作及发送按钮完整可见、可操作
- **AND** 手动放大能力保留，composer 文本与 mention 高亮不发生错位

#### Scenario: 输入后跨页继续使用
- **WHEN** 用户在搜索或聊天输入后进入群设置、Agent 详情及工作页，再返回列表
- **THEN** 各页保持正常宽度，无需刷新或手动缩小才能操作

### Requirement: 主屏 Web App 的登录与站内导航保持可用

#### Scenario: 从未登录安装进入完整应用
- **GIVEN** 用户从登录页以 Open as Web App 添加到主屏幕
- **WHEN** 用户从图标启动、登录并在聊天、Tasks、Agents、Me 间切换
- **THEN** 正常站内导航保留应用内体验，一级入口及详情返回不被系统栏或安全区盖住

#### Scenario: 已登录再次启动与刷新
- **WHEN** 用户已登录后再次从主屏图标启动，或在详情页刷新并返回列表
- **THEN** 页面可继续使用，保持登录与既有路由语义，不依赖反复重新安装来日常恢复布局

### Requirement: 可视区域变化时输入与导航仍可操作

#### Scenario: 软件键盘弹出与收起
- **WHEN** 用户在真实 iPhone 弹出软件键盘编辑消息，再收起键盘
- **THEN** 编辑时能看到输入内容与发送操作，收起后页面恢复可用高度，消息和列表仍能正常滚动

#### Scenario: 普通 Safari 与既有桌面体验
- **WHEN** 用户在 Safari 显示浏览器栏时浏览列表或聊天，或在桌面打开相同页面
- **THEN** Safari 中标题、导航和输入不被系统栏遮挡，桌面布局与已有收发、草稿行为保持

## 独立回归矩阵与证据要求

| 入口 / 状态 | 必须覆盖的操作 | 验收关注点 |
| --- | --- | --- |
| 真机 Safari | 登录、列表搜索、单聊输入，浏览器栏展开/收起 | 无自动放大裁切，关键操作可达 |
| 真机主屏应用，登录页安装 | 启动 → 登录 → 四个一级入口 → 具体会话 | 站内导航模式、顶底栏、发送按钮 |
| 真机主屏应用，已有登录 | 再次启动、详情刷新、返回列表 | 登录保持、宽度与高度恢复 |
| 真机输入状态 | focus → 输入 → 软件键盘收起 → 跨路由 | 比例、输入区、安全区与滚动 |
| 桌面浏览器 | 列表/详情、搜索、草稿与收发 | 原有布局和交互不回归 |

真实键盘必须单独验收；镜像硬件 Return 发送不等于手机输入法通过。窄视口截图、DOM/CSS 断言和桌面 WebKit 可以辅助定位，不替代真机产品结论。最终证据须标明构建版本、设备/iOS、入口、实际操作与截图；未测场景明确保留为未通过。

## 修复方向与下一阶段

隔离验证已完成，进入设计。高层方向是让手机输入可读字号、应用可视高度和站内启动/导航范围协调一致；不以禁用用户缩放、隐藏必要入口或强迫刷新来消除表象。软件键盘的 visual viewport 处理只覆盖当前产品需要的输入场景。

设计只包含支撑这两项的必要改动。实现完成后按 Full 门禁执行独立一致性、产品回归与代码审查；部署及生产验收另行按实际授权执行，不把文档提交或测试通过称为已上线修复。

## 补充用户指示与客户端路线判断

用户原话：

> 这类问题可能也比较常见，你如果不太懂，你可以上网搜索社区的优秀实践方案。

> 如果没有合适方案可能要考虑做一个ios app，但是我不会给付费，所以可能要做一个同一个内网内定期更新凭证的方案。
>
> 你要自己衡量是否要做一个ios app

本次 Web 机制已有同机有效对照，577 继续修复。用户随后明确要求无论 Web 修复结果、是否有新增特性，都另做 iOS App，并提出 Mac mini 上 AltServer 同 Wi-Fi 刷新；已建立独立 feat-578 和并行 chat 承接。免费原生分发的 7 天 provisioning profile 续签与安装维护，参考 [Apple 官方限制](https://developer.apple.com/help/account/basics/about-your-developer-account)和 [AltServer 同网刷新条件](https://faq.altstore.io/altstore-classic/altserver)，由 feat-578 收口；本 unit 不扩展 iOS App 或续签服务。

## 2026-10-05 用户实体键盘反馈与范围补充

用户原话：

> 我真机测了，两个问题：
>
> 1. 输入框下方的白色为啥这么多，浪费了纵向空间
> 2. 没法真正换行，下面写的是换行实际是发送，这个可能要思考下怎么设计呢？

附件`IMG_9428.PNG`显示同一隔离e2e会话、00:51真实中文九宫格软件键盘：键帽为“换行”；composer下方白色留白，之后才是iOS上下字段/完成辅助条及键盘。本机原图`/Users/czj/Downloads/IMG_9428.PNG`不入仓。用户授权本unit继续修复这两项实际输入体验，不将实体键盘“已操作”误记为验收通过。

RCA补充：现行MessagePane无设备区分地截获Enter并commit；current契约与旧测试本来要求手机Enter发送，但与本次明确要求可真正换行冲突，现以新用户反馈修订。原composer外层无条件保留safe-area-inset-bottom。caller在同一iPhone镜像的输入辅助条状态实测：clientHeight=873、visualViewport.height=805、scale=1；composer padding-bottom=34px，dropzone padding-bottom=9.6px，输入行bottom=761.40625而composer bottom=805，实际空白43.59px。与附件可见白带一致；辅助条本身属于iOS系统界面，不承诺隐藏。

### Requirement: 手机键盘语义与可用空间符合输入意图

#### Scenario: 手机换行与发送分开
- **WHEN** 用户在手机输入消息并按键盘“换行”，包括输入提及或斜杠前缀时
- **THEN** 编辑区插入新行，保留草稿，不立即发送或自动选择候选
- **AND** 点击候选可插入提及/命令，点击发送箭头才发送完整多行文字；中文候选确认不被劫持

#### Scenario: 键盘占用底部时不重复留安全区
- **WHEN** 手机编辑期间键盘或输入辅助条缩小可视高度
- **THEN** 输入框下方只保留正常组件内边距，不再叠加为Home指示条预留的整段空白
- **AND** 键盘收起后恢复底部安全区，标题返回、滚动及草稿不回归

#### Scenario: 桌面键盘保留既有快捷键
- **WHEN** 桌面用户编辑消息
- **THEN** Enter发送、Shift+Enter换行，中文输入法候选确认与候选菜单原有键盘选择保持
