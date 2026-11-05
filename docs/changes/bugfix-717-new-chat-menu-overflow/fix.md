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
侧栏顶部只剩一条被裁切的「新聊天」碎片（首项的焦点底色仍在），表头标题「消息」和「+」按钮本身都从视野里消失；
菜单第二项（新建群聊）和第三项完全看不到、也点不到，因此用户想建的群聊无法完成。

**复现条件**：与本机无关、与是否先进入某个会话无关；普通会话列表状态下只要点「+」即可复现。
桌面宽度与窄屏（<768px，侧栏占满宽、触发器 44px）都能复现，窄屏只是数值略大。

**真实浏览器复现（改动前，生产等价 CSS，真实 `NewConversationMenu` 组件）**：

| 视口 | 表头行盒高 | `overflow` | 点「+」后行 `scrollTop` | 菜单项 2/3 可点击 | 标题/「+」在视口内 |
|---|---|---|---|---|---|
| 375x600  | 44 | hidden | **55** | 否 | 否（`y=-35.8` / `y=-45`） |
| 1072x444 | 40 | hidden | **53** | 否 | 否（`y=-27.4` / `y=-39`） |
| 1440x900 | 40 | hidden | **53** | 否 | 否（`y=-27.4` / `y=-39`） |

复现件与截图在 `/tmp/bugfix717/`（`shots/prefix-<视口>-open.png`），不进仓库；
构建脚本与断言脚本同样只在 `/tmp`：`/tmp/bugfix717/verify.mjs`（Playwright + 真实 Chrome，见「验证」段）。

用户报告的 1072x444 与 1440x900 落在同一个断点（>767px 的桌面侧栏 262px 宽、行高 40px），
数值一致；375x600 属窄屏断点（行高 44px），把行滚走的是 55px。

## 根因

**触发链**（file:line 为 `src/IM/frontend` 下当前代码）：

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

（实施后回填）

## 验证

（实施后回填）
