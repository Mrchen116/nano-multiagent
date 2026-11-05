# bugfix-717 浏览器验证记录

本目录只保存可复核的结论与命令。复现页、构建产物、截图都留在 `/tmp/bugfix717/`，不进仓库。

## 环境

- 浏览器：本机 Google Chrome 156.0.8078.80（Playwright `channel: "chrome"`，headless）。
- CSS：用仓库自己的构建链生成，不是手抄规则——`vite build` + `@tailwindcss/vite` 处理
  `src/IM/frontend/src/styles/global.css`（与 `src/IM/frontend/vite.config.ts` 的插件相同），
  产物在 `/tmp/bugfix717-dist/css-prefix`（改动前）与 `/tmp/bugfix717-dist/css-fixed`（改动后）。
  这样层叠顺序、Tailwind preflight 与压缩后的规则形态都与生产一致。
- 组件：复现页挂载的是**仓库里的真实 `NewConversationMenu`**
  （`src/IM/frontend/src/features/chat/components/new-conversation-menu.tsx`，esbuild 打包，
  i18n 用仓库的 `src/i18n`，中文环境），只有外层侧栏结构性 markup 按
  `conversation-sidebar.tsx:206-262` 复刻（`html/body/#root` 与侧栏骨架）。
- 服务：`http://127.0.0.1:4319` 临时静态服务（ES module 不能在 `file://` 下加载）；轮次结束即关闭。

## 复现/验证脚本

```bash
cd src/IM/frontend
# 改动前
CSS_OUT_DIR=/tmp/bugfix717-dist/css-prefix npx vite build --config /tmp/bugfix717/vite.css.config.mjs
# 改动后
CSS_OUT_DIR=/tmp/bugfix717-dist/css-fixed  npx vite build --config /tmp/bugfix717/vite.css.config.mjs
# 断言（三档视口，每档 19 条）
CSS_PATH=<built css> OUT_DIR=/tmp/bugfix717/shots LABEL=prefix node /tmp/bugfix717/verify.mjs
```

`verify.mjs` 每档视口断言：行 `overflow`、行/侧栏/文档 `scrollTop`、浮层高度、三个菜单项是否
`inViewport` 且 `document.elementFromPoint(中心)` 命中自身、标题与「+」是否仍在视口内且可命中、
焦点是否落在首项、第二项是否能点、Esc 与选择后焦点归还、以及搜索折叠动画的中间帧与终态。

## 结果（改动前 → 改动后）

| 检查项（每档视口） | 改动前 | 改动后 |
|---|---|---|
| `.chat-sidebar-header-row` computed `overflow` | `hidden` | `visible` |
| 点「+」后行 `scrollTop` | 375px: **55**；1072/1440px: **53** | 0 / 0 / 0 |
| 侧栏 `.chat-sidebar` `scrollTop` | 0 | 0 |
| `document.scrollingElement.scrollTop` | 0 | 0 |
| 浮层 `getBoundingClientRect().height` | 142（但被裁，只有首项一条可见） | 142 |
| 菜单项 1/2/3 命中测试 | `true / false / false` | `true / true / true` |
| 标题「消息」在视口内 | 否（`y=-27.4`，375px 为 `y=-35.8`） | 是（`y=25.6`，375px 为 `y=19.3`） |
| 「+」在视口内且可命中 | 否（`y=-39`/`y=-45`） | 是 |
| 断言合计 | 15 条失败 / 42 通过 | **57 条全部通过** |

改动前 1072x444 的截图 `/tmp/bugfix717/shots/prefix-1072x444-open.png` 与用户截图形态一致
（只剩一条被裁的「新聊天」碎片，标题与「+」不见）；改动后 `fixed-1072x444-open.png` 三项完整展开。

补充探针（改动后，`/tmp/bugfix717/short.mjs`）：1440x300、1072x200、768x400、767x444、320x480
五档下，行/侧栏/文档 `scrollTop` 全为 0，三项菜单均命中，浮层右边界始终 ≤ 侧栏右边界
（桌面 `right=249`，侧栏 262）。

## 搜索折叠动画（`359109c98` 引入的体验）是否保住

同一视口 1072x444 与 375x600，用 `/tmp/bugfix717/frames.mjs` 采样进入/退出搜索的中间帧：

| 状态 | 1072x444 | 375x600 |
|---|---|---|
| 进入搜索 ~60ms | 行高 0，行 opacity 0，标题已随行收起 | 行高 0，opacity 0 |
| 进入搜索终态 | 行高 0、opacity 0，搜索视图独占表头 | 同（移动端独立搜索页） |
| 退出搜索 ~30ms | 行高 13.9，opacity 0.47 | 行高 13.9，opacity 0.47 |
| 退出搜索终态 | 行高 40（桌面）/44（窄屏），opacity 1，标题回到原位 | 行高 44，opacity 1 |

中间帧截图（`/tmp/bugfix717/shots/fixed-enter-*.png`、`fixed-exit-*.png`）没有出现内容溢出到搜索框上方的
可见瑕疵：`overflow` 只在 `.chat-sidebar--searching` 下裁切，退出动画期间内容已随 `opacity` 淡入。

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
