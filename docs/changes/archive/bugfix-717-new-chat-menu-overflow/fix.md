# bugfix-717: 聊天侧栏「+」创建菜单被表头行裁切并滚出视野

## 原始报告

2026-11-05T15:29:55+08:00，Web 会话 `c_f2mbtxa9`（消息 `843b7bf49e3b490e84dfaf5883a1ee87`）报告：

> 还有，我发现我想新建群聊按了+，出现的弹窗卡在里面了，而不是展开的状态

同一条消息附带截图 `image/png`（文件名 `image.png`），IM 附件路径
`/im/v1/conversations/c_f2mbtxa9/attachments/b0634681b9f44d40b705a4e3d9d71b20`。该附件不在仓库内，不随本 unit 提交。
截图窗口尺寸 1072x444 为 Agent 实测记录，不属于用户原话。

用户从「+」入口进入；该入口的菜单同时承载新建会话与新建群聊（当前中文文案分别为「新聊天」「创建群聊」「发现公开群」），用户本次要点的「新建群聊」对应菜单第二项。

## 现象 / 复现

**用户看到什么**：点侧栏右上角「+」后，菜单没有作为完整浮层展开在按钮下方，而是"卡在里面"——
侧栏顶部只剩一条被裁切的「新聊天」碎片，表头标题「消息」和「+」按钮本身都从视野里消失；
菜单第二项（新建群聊）和第三项完全看不到、也点不到，因此用户想建的群聊无法完成。

**复现条件**：与本机无关、与是否先进入某个会话无关；普通会话列表状态下只要点「+」即可复现。
桌面宽度与窄屏（<768px，侧栏占满宽、触发器 44px）都能复现，窄屏只是数值略大。

**真实浏览器复现（改动前，生产等价 CSS，真实 `NewConversationMenu` 组件）**：

| 视口 | 表头行盒高 | `overflow` | 点「+」后行 `scrollTop` | 菜单项 2/3 可点击 | 标题/「+」在视口内 |
|---|---|---|---|---|---|
| 375x600  | 44 | hidden | **55** | 否 | 否（`y=-35.8` / `y=-45`） |
| 1072x444 | 40 | hidden | **53** | 否 | 否（`y=-27.4` / `y=-39`） |
| 1440x900 | 40 | hidden | **53** | 否 | 否（`y=-27.4` / `y=-39`） |

复现脚本随 unit 提交：`M1-fix/evidence/harness/run-verification.mjs`（Playwright + 真实 Chrome，见「验证」段），
一条命令即可重建两份 CSS 并复跑全部断言；它把构建产物与截图写进仓库外的临时目录（默认系统临时目录，
可用 `--out` 指定，文件名如 `shots/prefix-<视口>-open.png`），不进仓库。

用户报告的 1072x444 与 1440x900 落在同一个断点（>767px 的桌面侧栏 262px 宽、行高 40px），
数值一致；375x600 属窄屏断点（行高 44px），把行滚走的是 55px。

## 根因

**触发链**（file:line 为 `src/IM/frontend` 下改动前（`50c90bd3e`）的代码，改动后的行号见「修复」）：

1. 侧栏把创建入口渲染在表头行内：`features/chat/components/conversation-sidebar.tsx:208` 是
   `.chat-sidebar-header-row`，`:210` 在其中放 `<NewConversationMenu />`。
2. 该菜单是**内联条件渲染的绝对定位子节点，没有 portal**：
   `features/chat/components/new-conversation-menu.tsx:47`（根 `.chat-sidebar-create`，`position:relative`）、
   `:54-75`（`open` 时才渲染 `role="menu"` 的浮层）、`styles/global.css:5718-5722`
   （`.chat-conversation-menu-items{position:absolute;right:0;top:calc(100% + 6px);z-index:30}`）。
   绝对定位只改变绘制位置，不改变包含块——浮层因此在几何上仍是表头行的后代。
3. 表头行自 2026-10-30 `359109c98`（"Smooth chat search transitions"）起带裁切：
   `styles/global.css:1694-1703` 的 `max-height:44px; overflow:hidden`（`blame` 落在该 commit），
   与 `:1705-1709` 的 `.chat-sidebar--searching` 折叠态配套。
4. 组件在打开时**把焦点移到第一个菜单项**：`new-conversation-menu.tsx:18`
   （`menu.current?.querySelector("button")?.focus()`，`:16-24` 的 effect）。
5. 关键机制：`overflow:hidden` 的元素**不是"不滚动"，而是"不可由用户滚动、仍可被程序/焦点滚动"的滚动容器**。
   浮层作为绝对定位后代计入该行的 `scrollHeight`（实测 188-192px）而行盒只有 40/44px，
   浏览器为保证焦点可见，把这一行向下滚了 53px（桌面）/55px（窄屏）：
   标题与「+」被滚到行窗口上方（`y` 为负），行窗口里只剩首项的中段。这与用户截图形态完全一致。

**为什么这种错能进来**：

- `359109c98` 的意图只是"切到搜索视图时表头平滑收起"（对应
  [`docs/specs/im/web-chat-ux.md`](../../../specs/im/web-chat-ux.md) 的「独立搜索视图」：
  桌面端侧栏切换为搜索视图，普通列表不与结果同时展示）。它把 `max-height/overflow:hidden/transition`
  加在一个**同时承载非 portal 浮层**的行上，而该次提交只检查了收起动画本身。
- 现有单测 `features/chat/components/conversation-sidebar.test.tsx` 在 jsdom 中只断言菜单节点出现与焦点，
  jsdom 没有布局与裁切，因此该回归出现后测试一直是通过的——它不具备覆盖这层几何行为的能力。
- 这不是"设计如此"：菜单 2026-09-14 `692e5180e` 引入时该行没有 `overflow`，浮层可以正常溢出显示。

**原始设计意图与修复必须保住的不变量**：

- `692e5180e` 把创建入口收敛为单个「+」+ 菜单，组件注释写明目的是让新建会话与新建群聊两个动作
  在窄屏都可到达（`new-conversation-menu.tsx:4`）。所以"菜单必须完整展开、三项都可点"是原本的功能意图，
  不能靠删掉菜单、删掉分项或退回两个独立按钮来消症状。
- `359109c98` 的搜索折叠动画是有效体验，不能为了露出浮层就取消折叠；
  进入/退出搜索视图时表头行的收起与复原必须继续成立（`web-chat-ux.md` 的搜索视图与
  「协作入口沿用现有 IM 导航和语言设置」）。
- 打开菜单后焦点落到首项、Esc 关闭并归还焦点、外点关闭、方向键导航属于可访问性行为，必须保留；
  修复不能靠取消聚焦来躲开症状。
- 浮层仍须落在侧栏宽度内（桌面侧栏 262px，浮层 160px 起），不引入横向裁切或把浮层推到视口外。

## 修复

commit `929a2ca3a`，单文件 `src/IM/frontend/src/styles/global.css`，净变化 1 行删除、4 行新增（其中 3 行是注释）：

| 位置（改动后） | 改动 |
|---|---|
| `.chat-sidebar-header-row`（`:1694-1702`） | **删除** `overflow: hidden`（原 `:1700`）；保留 `max-height: 44px` 与 `transition: max-height 160ms …` |
| 同一选择器上方（`:1704-1706`） | 新增 3 行注释：说明该行常态不得裁切，否则会切掉「+」浮层并让打开时的 `focus()` 把菜单滚走 |
| `.chat-sidebar--searching .chat-sidebar-header-row`（`:1707-1712`） | **新增** `overflow: hidden` |

**为什么这样就够**：

- 触发链里唯一真正的裁切者就是这一行（`conversation-sidebar.tsx` 的表头行是浮层的唯一内联祖先）；
  去掉它的 `overflow` 后，它既不再裁切、也不再是滚动容器，`new-conversation-menu.tsx:18` 的 `focus()`
  没有可滚动的祖先行，行 `scrollTop` 保持 0，标题与「+」不再被滚出视野。
- 裁切只留在 `.chat-sidebar--searching` 折叠态：那里整行 `max-height: 0`、`opacity: 0` 且
  `conversation-sidebar.tsx:208` 已把它设为 `inert`，浮层不可能处于打开状态，因此裁切不会伤到菜单，
  而 160ms 收起动画的表现与改动前完全一致（见「验证」的中间帧）。
- 浮层仍是内联绝对定位子节点，退回 portal + `position: fixed`（调查报告的方案 B）没有采纳：
  那会同时动定位、外点关闭判定、Esc 后焦点归还和移动端覆盖层 z-index，风险与本缺陷不成比例。
  浮层 160px 宽、右贴侧栏内边距，`.chat-sidebar{overflow:hidden}` 只做侧栏边界兜底，实测未产生裁切。
- TSX 一行未改：打开时聚焦首项、方向键导航、Esc 关闭并归还焦点、外点关闭全部保留（可访问性没有被牺牲）。

**没有额外加 guard 的理由**：修复后没有任何祖先需要为聚焦而滚动（实测行/侧栏/文档 `scrollTop` 全为 0），
所以没有加 `focus({preventScroll: true})` 或 `scroll-margin`。反过来说，若只给打开时的聚焦加
`preventScroll`，同一组件里方向键导航的 `items[next]?.focus()`（`new-conversation-menu.tsx:37`）仍是会滚动的那种，
两条路径行为不一致，反而更难解释；极矮视口下的残余风险写在「验证」末尾。

## 验证

完整命令、逐项数值与截图路径见
[`M1-fix/evidence/browser-verification.md`](M1-fix/evidence/browser-verification.md)。

1. **真实浏览器复现→修复（不是断言）**：用仓库自己的 `vite` + `@tailwindcss/vite` 构建
   `global.css`（与 `vite.config.ts` 同插件，层叠与 preflight 同生产），复现页挂载**仓库里真实的
   `NewConversationMenu` 组件**，Playwright 驱动本机 Chrome 156。脚本已随 unit 提交，一条命令可复跑
   （`M1-fix/evidence/harness/run-verification.mjs`，会自己重建「改动前」与「改动后」两份 CSS）：
   375x600 / 1072x444 / 1440x900 三档主视口各 27 条、五档边界尺寸各 3 条，共 **96 条断言
   （90 条行为 + 6 条实现属性）**，连跑 3 次结果一致。
   改动前那份 CSS 的行为断言按「复现缺陷」方向断言，因此全绿的含义是「缺陷在旧 CSS 上复现、在新 CSS 上消失」。
   - 改动前不成立的是 **12 条行为断言 + 3 条实现属性断言**（每档视口 4 + 1）：行 `overflow=hidden`，
     点「+」后行 `scrollTop` = 53（375px 为 55），三项菜单只有首项可命中，标题 `y=-27.4`、`+` `y=-39`
     均在视口外。行为层面是 4 个现象，不是 15 个独立故障。
   - 改动后：行 `overflow=visible`，行/侧栏/文档 `scrollTop` 均为 0，浮层高度 142、三项都 `inViewport`
     且可命中，标题与「+」回到视口内，第二项（创建群聊）可点并触发分组创建，Esc 关闭后焦点回到「+」。
   - 五档边界尺寸 1440x300 / 1072x200 / 768x400 / 767x444 / 320x480：无任何滚动、
     `documentElement.scrollWidth === clientWidth`、浮层右边界 ≤ 侧栏右边界（320px: `304 < 320`；
     767px: `751 < 767`；桌面 `249 < 262`）。
2. **搜索折叠动画没有被削弱**：用 `getAnimations()` + `pause()` + 固定 `currentTime` 冻结采样，
   而不是墙钟等待（早先的 `waitForTimeout(30/90ms)` 采样会落在过渡起点之前，读数不可复现）。
   三档视口：进入 `currentTime=40ms` 行高 26 / opacity 0.42，终态 0 / 0；退出 `currentTime=20ms`
   行高 6 / opacity 0.22，终态行高 40（375px 为 44）/ opacity 1。中间帧的不可见溢出由
   `.chat-search-input-row` 的定位绘制顺序盖住，机制与偶然耦合的说明见证据文件。
3. **单测**：`cd src/IM/frontend && npx vitest run src/features/chat/components/conversation-sidebar.test.tsx`
   → 改动前后均 `21 passed (21)`。jsdom 没有布局，这条测试**不能**覆盖本次几何回归，
   仅证明菜单的存在/焦点契约未变。
4. **全量前端测试**：`npx vitest run` → `Test Files 4 failed | 109 passed (113)`，`Tests 2 failed | 1052 passed (1054)`。
   两个失败来源都与本改动无关：3 个文件因本机 `node_modules` 缺 `maplibre-gl` 在 transform 阶段失败；
   `chat-workspace.integration.test.tsx` 的 2 条 `adopts edited text …` 在改动前同样失败（stash 掉本改动后单跑该文件复现）。
   前端没有测试导入 `global.css`。

**仍显脆弱的地方**：

- 没有自动回归测试守住这条几何契约：jsdom 无法发现，仓库目前也没有 Playwright 测试约定
  （`playwright` 只是 `src/IM/frontend` 的 devDependency，没有 checked-in 的浏览器测试目录）。
  `M1-fix/evidence/harness/` 是可复跑的**证据**，不被 `pnpm test` / CI 调用，也不应被当成基线。
  本次只在 `global.css` 该处留注释。若要长期守住，应另立 unit 建立前端布局回归测试基线。
- 退出搜索的 160ms 展开动画期间，行内容不再被裁切，它之所以看不见是**偶然耦合**：行内容被
  `.chat-search-input-row`（`position: relative`，`global.css:1826`）这个后出现的定位兄弟节点盖住，
  而不是因为 `opacity` 淡出（冻结帧 opacity 仍有 0.22）。若去掉该定位、或把行内容做得更高让重叠带
  超出搜索框覆盖范围，同一处就会出现可见溢出。
- 侧栏 `.chat-sidebar{overflow:hidden}` 仍是兜底：菜单当前 160px 宽、侧栏 262px 宽没有问题，
  但若菜单宽度涨到约 238px 以上会被侧栏裁切。同类隐患还有 `DirectConversationMenu`
  （`direct-conversation-menu.tsx`）复用的同一个 `.chat-conversation-menu-items`，它同样没有 portal。
- 极矮视口（<约 270px 高）下浮层底部会超出视口，`.chat-sidebar` 自己也是 `overflow:hidden` 的滚动容器，
  理论上聚焦仍可能让它滚动几像素（1072x200 实测 `scrollHeight 202 / clientHeight 200`，未触发滚动）。

## canonical spec 是否需要归并

**决定：本次不改 canonical spec，也不新增 delta-spec。**

依据：`docs/specs/im/web-chat-ux.md:561-565` 的 Requirement「协作入口沿用现有 IM 导航和语言设置」，
其 Scenario「桌面和移动端寻找协作者」要求用户从新聊天入口使用的弹层「沿用现有导航、搜索与弹层，
**能选择合法对象并开始沟通**」。菜单被裁到只剩首项碎片、第二、三项不可达，违反的正是这条既有契约；
修复是恢复契约，不是引入新行为，所以没有需要归并的契约变化。

已知边界（显式记录，不留给后来者猜）：该 Requirement 约束的是**结果**——能从该入口选到对象并开始沟通，
它没有写「菜单必须以完整浮层展开、不得被祖先裁切」这类几何不变量。因此这条几何约束目前只由
`src/IM/frontend/src/styles/global.css:1704-1706` 的注释与本文件守卫，既没有 spec 也没有自动化测试兜底。
要把它变成可执行契约，需要另立 unit：在 `web-chat-ux.md` 增补对应的 Requirement/Scenario，并建立前端布局
回归基线（本 unit 的 `M1-fix/evidence/harness/` 可作为起点，但它是证据、不是基线）。
