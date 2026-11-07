# bugfix-717 浏览器验证记录

结论与命令都在本目录，**复现脚本已随 unit 提交**（`harness/`），不是只活在临时目录里。
构建产物与截图仍写在仓库外的临时目录：它们可由下面的命令重新生成，不进仓库。

## 环境

- 浏览器：本机 Google Chrome 156.0.8078.80（Playwright `channel: "chrome"`，headless）。
- CSS：用仓库自己的构建链生成，不是手抄规则——`vite` + `@tailwindcss/vite` 处理
  `src/IM/frontend/src/styles/global.css`（插件与 `src/IM/frontend/vite.config.ts` 相同），
  「改动前」那份用 `git show <prefix-ref>:src/IM/frontend/src/styles/global.css` 取出后同样构建，
  因此层叠顺序、Tailwind preflight 与压缩后的规则形态都与生产一致。
- 组件：fixture 挂载的是**仓库里的真实 `NewConversationMenu`**
  （`src/IM/frontend/src/features/chat/components/new-conversation-menu.tsx`，esbuild 打包）
  和真实 `src/i18n`（中文环境）；只有外层侧栏结构性 markup 按
  `conversation-sidebar.tsx:206-262` 复刻（差 `distillMode` 与 `personalAgentEntry` 两个不在行内的分支）。
- 服务：`127.0.0.1:4319` 临时静态服务（ES module 不能在 `file://` 下加载），脚本结束即关闭。

## 复现 / 验证脚本

```bash
node docs/changes/bugfix-717-new-chat-menu-overflow/M1-fix/evidence/harness/run-verification.mjs
# 可选参数：--prefix-ref <git ref>（默认 origin/main）、--out <目录>（默认系统临时目录）、--port <端口>
```

- `harness/sidebar-harness.tsx`、`harness/harness.html`：fixture（真实菜单组件 + 复刻的侧栏骨架）。
- `harness/run-verification.mjs`：重建两份 CSS → 打包 fixture → 起隔离端口 → 用真实 Chrome 跑
  375x600 / 1072x444 / 1440x900 三档主视口与 1440x300 / 1072x200 / 768x400 / 767x444 / 320x480
  五档边界尺寸，把 `summary.json` 与 `shots/*.png` 写进 `--out`。
- 断言分两类：`behavior`（用户可观察）与 `property`（实现属性，例如 computed `overflow`）。
  改动前那份 CSS 的行为断言按「复现缺陷」的方向断言，所以**全绿的含义是「缺陷在旧 CSS 上复现、
  在新 CSS 上消失」**，而不是把旧行为也断言成正确。
- 中间帧不再用墙钟采样：`getAnimations()` → `pause()` → `currentTime = 40ms / 20ms`，可重复。

最近一次运行（`node .../run-verification.mjs`，连跑 3 次结果一致）：

```
ALL CHECKS PASSED — 90/90 behavior, 6/6 property   （共 96 条：3 档主视口各 27 条 + 5 档边界各 3 条）
```

## 结果（改动前 → 改动后；三档主视口结论一致，差异写在单元格里）

| 检查项 | 改动前（`origin/main` 的 CSS） | 改动后 |
|---|---|---|
| `.chat-sidebar-header-row` computed `overflow` | `hidden`（每档 1 条，共 3 条实现属性断言） | `visible` |
| 行是否把自己的内容滚走：行 `scrollTop` | 375px: **55**；1072/1440px: **53** | 0 / 0 / 0 |
| 三个菜单项是否都可达（`inViewport` + `elementFromPoint` 命中自身） | `true / false / false` | `true / true / true` |
| 标题「消息」是否在视口内 | 否（`y=-27.4`，375px 为 `y=-35.8`） | 是（`y=25.6`，375px 为 `y=19.3`） |
| 「+」是否在视口内且可命中 | 否（`y=-39`，375px 为 `y=-45`） | 是 |
| 侧栏 `.chat-sidebar` / 文档 `scrollTop` | 0 / 0（两种状态都成立） | 0 / 0 |
| 浮层 `getBoundingClientRect().height` | 142（被裁，只有首项一条可见） | 142 |
| 浮层是否落在侧栏宽度内 | 是 | 是 |

把同一批断言按「修复后应成立」的方向读，改动前有 15 条不成立 = **12 条行为断言 + 3 条实现属性断言**
（每档视口各 4 条行为 + 1 条属性，提交的脚本对旧 CSS 反向断言它们以证明缺陷复现）。
它们不是 15 个独立的用户可见故障：行为层面归结为 4 个现象——行被滚走、三项不可全达、标题出视口、「+」出视口。

- 改动前 1072x444 的截图 `prefix-1072x444-open.png` 与用户截图形态一致（只剩一条被裁的「新聊天」碎片，
  标题与「+」不见）；改动后 `fixed-1072x444-open.png` 三项完整展开。两张都在 `--out` 的 `shots/` 下。
- 五档边界尺寸（1440x300、1072x200、768x400、767x444、320x480）：行/侧栏/文档 `scrollTop` 全为 0，
  三项全部命中，`documentElement.scrollWidth === clientWidth`（无横向滚动），浮层右边界 ≤ 侧栏右边界
  （320px: `304 < 320`；767px: `751 < 767`；桌面 `249 < 262`）。

## 搜索折叠动画（`359109c98` 引入的体验）是否保住

冻结 `transition` 后按固定 `currentTime` 采样（不是墙钟等待），三档视口：

| 采样点 | 375x600 | 1072x444 | 1440x900 |
|---|---|---|---|
| 进入搜索，`currentTime=40ms` | 行高 26，opacity 0.42 | 行高 26，opacity 0.42 | 行高 26，opacity 0.42 |
| 进入搜索终态 | 行高 0，opacity 0 | 行高 0，opacity 0 | 行高 0，opacity 0 |
| 退出搜索，`currentTime=20ms` | 行高 6，opacity 0.22 | 行高 6，opacity 0.22 | 行高 6，opacity 0.22 |
| 退出搜索终态 | 行高 44，opacity 1 | 行高 40，opacity 1 | 行高 40，opacity 1 |

三档中间帧数值相同是正常的：被动画的属性是 `max-height`（44px → 0），窄屏媒体查询改的是 `height`
（`global.css:5047-5051`）而不是 `max-height`，所以冻结时刻的行高与视口无关，只有终态行高不同（44 / 40）。

**早先记录的「退出 ~30ms 行高 13.9 / opacity 0.47」是墙钟采样的产物，不是属性**：
同一时刻重跑会得到不同数值（375 档曾读到 0/0），本文件已用冻结采样替换该列。

## 退出动画期间的溢出为什么看不见（以及为什么这是偶然耦合）

冻结在退出 20ms 那一帧，行盒只有 6px，而标题与「+」按 40/44px 的内容盒居中，几何上必然溢出到行盒下方。
它不可见的原因**不是 `opacity` 淡入**（那一刻 opacity 是 0.22，内容仍然画出来了），而是被后一个定位兄弟节点盖住：

- `.chat-search-input-row`（`global.css:1826`）是 `position: relative` 的定位元素，DOM 顺序在表头行之后，
  按绘制顺序盖过行内溢出的内容，它自己的白底把重叠带抹平。
- 实测（`run-verification.mjs` 的 overlap cover probe，同一冻结帧）：重叠带 = 触发器与搜索行框的交集，
  1072/1440 为 15.6px、375 为 36.6px；带中心的 `elementFromPoint` 三档都返回 `input.chat-sidebar-search`。
- 把 `.chat-search-input-row` 临时改成 `position: static` 后，同一坐标的顶层元素变成
  `button.chat-sidebar-create-trigger`（1072/1440）和它的 SVG `<path>`（375）——溢出内容一直都在那里。
  375 档尤其说明「透明」不是原因：36.6px 的重叠带已经压到「+」的图形本身；deviceScaleFactor=2 的
  像素差分里，取消定位后 375 档有 207 px 发生变化，桌面只有 26 px（搜索框边框）。

因此这是**偶然耦合**，不是设计：若以后去掉 `.chat-search-input-row` 的 `position: relative`，或把行内容做得更高
（重叠带变宽超出搜索框覆盖范围），同一处就会出现可见溢出。要让它成为有意设计，可以给
`.chat-search-input-row` 显式加 `z-index` 并同步更新 `global.css:1704-1706` 的注释——本 unit 不做
（超出这个缺陷的修复范围，且需要单独确认层叠意图）。

## 单测

```bash
cd src/IM/frontend
npx vitest run src/features/chat/components/conversation-sidebar.test.tsx
```

改动前后均 `1 passed (1) / 21 passed (21)`。这条测试在 jsdom 里只断言菜单节点出现与焦点，
**没有布局能力，不能覆盖本次几何回归**；本次不把它算作覆盖证据（`M1-fix` 说明见 `fix.md`）。

## 全量前端测试（说明与本改动无关的环境缺口）

```bash
cd src/IM/frontend && npx vitest run
# Test Files 4 failed | 109 passed (113)
# Tests      2 failed | 1052 passed (1054)
```

- 3 个文件在 transform 阶段失败：`Failed to resolve import "maplibre-gl/dist/maplibre-gl.css"`，
  本机 `src/IM/frontend/node_modules` 里没有 `maplibre-gl`（安装缺口），与 CSS 无关。
- `chat-workspace.integration.test.tsx` 的 2 条 `adopts edited text ...` 失败在**改动前**同样失败
  （把 `global.css` 的改动 stash 后单跑该文件：`2 failed | 58 skipped`），属既有失败。
- 前端没有任何测试导入 `global.css`，因此本次纯 CSS 改动不可能影响上述结果。

## 这套证据覆盖不到什么

- `harness/` 是**证据**，不是仓库的浏览器测试基线：它没有被任何长期门禁调用，`pnpm test` / CI 都不会跑它。
  仓库目前也没有 committed 的 Playwright 测试约定（`playwright` 只是 `src/IM/frontend` 的 devDependency）。
- 验收范围是「生产等价的 CSS + 真实菜单组件 + 复刻的侧栏骨架」，不是完整前端应用（需要后端与登录）。
  行内几何契约等价，但真实应用里的点击路径、焦点上下文属于推断。
