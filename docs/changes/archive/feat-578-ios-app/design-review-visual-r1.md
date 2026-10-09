# feat-578 视觉设计复审

## Visual Round 1（Gate 2 delta）

### Metadata

- reviewer_target: `/root/ios_visual_design_review`；独立 reviewer，author 为 `/root`。
- review_mode: `delta`
- mode_reason: 用户实际查看原生登录/聊天后否定整体 UI/UX；本轮只审 `design.md` 新增视觉修订/P6、`prototype.html` 视觉变化及同源九页总览。功能、API、权限、签名安装路线没有改变，不重新打开此前架构与资源时序决定。
- retained_from: `design-review.md` Round 2；保留架构/Session/HTTP/WS/权限/完整范围与用户授权资源顺序。该 retained 不等于保留此前对新视觉的通过结论。
- checkout/revision: `codex/feat-578-ios-app` / `28ba862fc70eb7c558ea4bb5a4db914f4b3e52a3`，受审视觉修订为未提交冻结快照。
- started_at: 2026-10-05T10:41:32+08:00（首张保存的独立渲染证据时间；此前已完成文本与 Web 源码核对）
- completed_at: 2026-10-05T10:43:34+08:00
- duration: 121 seconds（以上渲染证据区间）。
- 报告按派发要求独立新增此文件，不改 `design-review.md` 历史，不改设计或产品代码，不提交。

### Verdict

**Issues Found — 0 CRITICAL / 1 WARNING。**

Web 气质、标题/正文层级、聊天列表密度、管理分组及关系图上对齐整体成立，可由原生布局兑现。配置页主操作在两个代表宽度都发生确定的文字断行，尚不能把本轮原型作为 P6 通过基准。修复 R-V1-W1 后做限定 closure 即可，不需重启架构审查。

这是设计复审，不能视为 SwiftUI 完成或用户已接受新 UI。用户反馈的最终闭环仍需实际 App 九页截图与普通/大字体检查，然后恢复产品功能旅程；真机、Mini 续签等最终门槛没有豁免。

### 渲染证据与方法

reviewer 在自己的后台 IAB tab 打开 `http://127.0.0.1:62319/visual-review.html`，目视总览，再逐页访问同源 `prototype.html?embed=1&screen=<page>`。分别设置 **390×844** 与 **430×932** viewport，独立截图并逐张目视；没有使用 Simulator、用户 Chrome 或用户现有页面。九页统一来自同一原型，未另造静态设计版本。

截图缓存（本地、不提交）：`output/feat578/visual-review-r1/{390,430}-{login,chat,conversation,tasks,agents,me,config,agent,graph}.jpg`，共 18 张。截图是实际浏览器渲染；AX 仅辅助定位操作，DOM 尺寸只用于解释已目视发现的问题，不作为视觉通过替代。

实际点击配置页“保存”得到“已保存（演示）”，进入“指令与能力”看到独立分组和底部主按钮。此操作只证明设计模型入口可达，不证明真实 API 保存或原生交互。

### Coverage 与判断

| 页面/约束 | 390 / 430 实际目视结果及判断 |
|---|---|
| Web grounding | 独立读取真实 `src/IM/frontend/src/styles/global.css:6–40` 的背景、正文、次级文字、accent、边界、品牌和用户气泡 token；核对 `auth-page-frame.tsx` 与 `conversation-sidebar.tsx` 的品牌/字段/筛选/摘要与时间结构。本轮白色内容、冷灰分层、深色正文、青绿主操作与这些源样式一致，未要求原生复制 Web 的桌面横排结构。 |
| 登录 | 品牌、欢迎引导、持久标签与输入、单一实心登录形成明确顺序；两个尺寸主按钮和注册/连接次入口均首屏可见。留白位于表单之后，不挤压主任务。 |
| 聊天 | 连续白底列表、6 条样例会话均在两种尺寸首屏完整可见，超过设计至少 5 条目标；名字/时间、单行摘要/未读分层清楚；群头像与个人/Agent 身份呈现有差异。没有巨大外层卡片或整行青色正文。 |
| 对话 | 双方气泡位置、深色正文、发送者与设备辅助信息可区分；工具过程入口收束，审批卡与普通回复分离；composer 处于内容区下方且未被 home bar 遮挡。键盘与中文 IME 不在 HTML 证据范围，须原生验证。 |
| 任务 | 标题最突出，状态、描述、类型/进度/更新时间递减；两卡上对齐且留出合理滚动空间。样例进度和时间只作为布局数据，不能硬编码入产品。 |
| Agent | 紧凑搜索和列表，名称/设备/模式/在线文字连续可读；三条之后的空白由样本数量造成，列表起点没有巨大无理由留白。原生状态必须来自真实数据。 |
| 我的 | 账号身份和管理员标记、个人/设备、工作区、帮助、退出分组合理；危险动作单列，两种宽度都可见。普通成员权限沿原契约，不由本轮视觉材料授予。 |
| 配置 | 常用字段先于指令能力与提示词入口，顶部保存随内容独立可达；字段标签清楚。**顶部“保存”纵向断行，见唯一 WARNING。** 390 下低部内容可通过正常滚动访问，不把长表单整体超出首屏判为缺陷。 |
| Agent 详情 | 概览/设备状态、发消息、工作与管理分组顺序清楚；主按钮在首屏前段，六行管理项在 390/430 可阅读。单 Thread/global Work 边界 retained，自本轮无更改。 |
| 任务关系 | 摘要与三个依赖节点紧靠上部；连线、状态文字和可点击节点有清楚对比，不再在巨大画布中央漂浮。复杂图/列表替代与回聊草稿仍沿原设计验收，不从三个固定节点推断全部图行为通过。 |
| 原生可实现性 | NavigationStack/工具栏、ScrollView/列表、分组表单、safe-area composer、Canvas 与原生节点足以实现，无需 WebView、图片截图或新的跨端 UI schema。系统 Tab/字体度量允许适配；不能把 HTML 10px 辅助字直接等同 Dynamic Type 完成。 |
| P6 与原 gates | P6 明确独立于 P1–P5，绑定原生截图与大字体；M1-W2 已要求原生截图/原型对照，可承接新增视觉门槛。功能与权限、资源时序、完整真机/Mini 最终退出保持 Round 2，不以浏览器画面代替。 |

### Issues

#### R-V1-W1 — 配置页“保存”固定窄宽度导致主操作两字纵向断行

- Severity: **WARNING / open**。
- 修复位置：`prototype.html:8` 的 `header button{width:44px;color:var(--ink)}`，以及 `prototype.html:58` 配置页工具栏 action；目标约束为 `design.md:130,145` 的主操作清晰与 P6。
- 目视证据：`output/feat578/visual-review-r1/390-config.jpg` 与 `430-config.jpg` 中，右上角均显示第一行“保”、第二行“存”。这不是某个窄设备偶发，也不是系统字体差异：两种代表 viewport 都出现。
- 已渲染 DOM 解释：按钮 `width=44px`、`padding=7px`、`font-size=16px`、`white-space=normal`，实际高度 59px；可用于中文的内部宽度只有 30px，两个汉字放不下。统一 header 规则还把此主操作变成正文同色，进一步弱化区分。
- 未修后果：本轮专门承诺“分组字段、清晰保存”的唯一顶部主操作本身呈现破碎；直接按 must-match 原型交给原生实现会继续形成用户可见的设计缺陷。
- 闭环要求：文字型工具栏操作按内容给足宽度且保持单行，图标按钮继续保留正常触控面积；给保存保留清楚的动作层级（可沿青绿 accent）。不要把所有导航按钮做成固定字符宽度。重新实际渲染 390/430 配置页，确认保存一行、标题/返回不受挤压即可；无需重复完整架构或业务审查。

### Recommendations（不阻断）

- R-V1-R1：聊天时间与任务页底部元信息当前仅 10px，截图中明显弱于摘要；原生可使用合适的动态 caption 样式并略增强次要文字，不将 HTML px 逐项硬拷贝成固定 pt。P6 已要求大字体，后续实际原生对照时落实即可，不为此另造设计返工循环。

### 历史问题闭环

原 `design-review.md` Round 1 的资源、隔离 HTTPS 与 single_thread Work 三项按 Round 2 已关闭含义 retained。本轮没有重新声明这些资源已经落实；也没有把新的视觉否定追溯改写为原架构未通过。视觉 R1 是新 delta，仅 R-V1-W1 待关闭。

### 受审快照

- `design.md`: `3d59510dd11eee40200110e25d85deb0ce2839acc327dea3d93dafea82c79a99`
- `prototype.html`: `43c95778d53a1814055676919602e738fa7c9ddf568cfe430ec9d7f7734a8ffc`
- `visual-review.html`: `58a2c1c53a8939155dfd9f2ce7c0b792c563c065eba216d49e9df86db09e88fb`
