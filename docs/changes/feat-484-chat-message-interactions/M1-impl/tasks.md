# feat-484-M1: message-interactions — Tasks

> 对齐: ../design.md v1

## 目标

完成 Web IM 消息内容交互改造：正文恢复原生文本选择/链接操作，消息级操作通过 toolbar（桌面）、右键菜单（mouse 普通区域）和 More action sheet（compact/coarse）统一入口；复制整条消息得到结构化纯文本并给出反馈；代码块独立复制；链接按 origin 分类导航；保持 fork 资格与禁用语义不变。

## 退出标准

- [x] M1-R1: mouse secondary click / Control-click 在选区内保留浏览器菜单、选区外开 IM menu；touch/pen/keyboard 原生；caret point 精确判断。
- [x] M1-R2: hover/focus toolbar、mouse context menu、compact/coarse More 共享同一 action model；Branch 四状态一致。
- [x] M1-R3: whole-message copy 得到干净正文，rich-copy fixture 逐字符匹配；Clipboard success/failure 反馈正确；async ownership guard 防止 stale notice/surface 关闭。
- [x] M1-R4: named external 新标签打开并带克制外跳提示；raw URL 不重复提示；same-origin/relative/hash 当前标签导航；mailto 交系统；unsupported 不渲染为可用链接。
- [x] M1-R5: fenced code block 独立精确复制；inline code 无按钮。
- [x] M1-R6: toolbar/menu/sheet/link/code button 焦点、本地化、回焦、More 触控区 >=44px、Radix Dialog 焦点陷阱正确。
- [x] M1-R7: fork `onFork(message.id)`、资格、offline/pending disabled、防双击与成功跳转语义不变；`message-pane-fork.test.tsx` 全绿。
- [x] M1-R8: `message-content-policy.test.ts` + `message-pane.test.tsx` 覆盖策略与三表面行为；删除/改写 feat-451 旧长按测试。
- [x] M1-R9: 真浏览器验收 Chromium desktop/hybrid 与 Playwright WebKit mobile，证据落 `M1-impl/evidence/`。
- [x] M1-R10: `npm run test`（指定三文件）、`npm run build`、`git diff --check` 全绿；不提交 `dist/`。

## 测试策略

- 被测行为（来自退出标准）：
  - 链接分类：same-origin-document / external / system / unsupported。
  - context menu modality 解析：mouse secondary、Control-click、ContextMenu/Shift+F10、touch/pen/unknown、recent pointer fallback。
  - 选区判定：同一 text node 内/外、跨 node、caret API fallback、native target。
  - 消息正文序列化：段落、嵌套列表、有序列表、引用、表格、代码块、mention、具名/裸链接、clipboard-exclude。
  - 代码文本提取：保留缩进与内部空行，仅去 renderer 尾换行。
  - 三表面行为：toolbar、context menu、More action sheet 的 Copy/Branch 可用性、disabled reason、关闭回焦。
  - Clipboard 异步 ownership：same-pane 新 surface、conversation switch、A→B→A、newer attempt、旧 notice timer。
  - Markdown 渲染：external anchor target/rel/aria-label、code block copy button、inline code 无按钮。
- 已有测试在：
  - 扩展 `src/IM/frontend/src/features/chat/components/message-pane.test.tsx`（覆盖新交互）。
  - 扩展 `src/IM/frontend/src/features/chat/components/message-pane-fork.test.tsx`（保持 fork 语义）。
  - 新建 `src/IM/frontend/src/features/chat/components/message-content-policy.test.ts`（纯策略）。
- 落层/目录/marker：Vitest 组件/单元测试，无 marker；Playwright 一次性验收证据不进套件。
- 可选依赖 importorskip：无（Vitest 已装；Playwright 仅用于一次性验收）。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：
  - `M1-impl/evidence/` 下的浏览器截图、录屏、事件 facts 记录。

## 前端 UI 额外计划

### 用户路径分类

- critical-path：复制整条消息、代码块复制、Branch fork、链接导航。
- normal-ui：toolbar / context menu / More action sheet 的打开与关闭、焦点管理。
- visual-only：外跳提示 ↗、snackbar 样式、hover 状态。
- bug-regression：修复“选中文本复制整条消息”“外部链接本页跳转”“移动端长按被菜单覆盖”。

### UI 状态矩阵

| 状态 | 覆盖计划 |
|---|---|
| default | toolbar 隐藏、More 在 compact/coarse 显示、正文可选 |
| loading | N/A（不涉及） |
| empty | N/A |
| error | Clipboard 失败显示失败 snackbar |
| disabled | Branch offline/pending 显示 aria-disabled + reason |
| submitting | N/A |
| permission denied | N/A |
| long content | 序列化保留结构与空行 |
| missing/nullable data | Clipboard API 缺失显示失败 |
| mobile viewport | 390×844 WebKit 验收 |
| desktop viewport | 1440×900 Chromium 验收 |
| dark mode | N/A（当前主题无 dark mode） |

### 测试与验收映射

| 风险点 | 验收方式 | 是否落库 |
|---|---|---|
| 内容策略正确性 | Vitest `message-content-policy.test.ts` | 是 |
| 三表面 Copy/Branch 行为 | Vitest `message-pane.test.tsx` | 是 |
| fork 资格与禁用语义 | Vitest `message-pane-fork.test.tsx` | 是 |
| 真实浏览器交互与视觉 | Chromium + Playwright WebKit 验收，截图落 evidence | 否（一次性） |
| 焦点/回焦/ARIA | Vitest + 浏览器验收 | 部分落库 |

### Prototype / Reference Contract

| Reference | Required contract | Evidence plan | Owner |
|---|---|---|---|
| fine pointer/keyboard 普通阅读态 + hover/focus icon toolbar | must-match | 1440×900 截图：default / hover / keyboard focus；Branch 四状态 | worker |
| mouse 精确选区/链接/code 保留原生菜单；普通区域开短 IM menu | must-match | 同一 text node 选区内/外、跨 node、具名外链；截图 + 事件 facts | worker |
| clean whole-message copy + success/error snackbar | must-match | rich body / existing selection / Clipboard reject 截图/录屏 | worker |
| named external、raw URL、same-origin product/resource 与 unsupported link | must-match | pointer hover/focus/right-click/click 截图 | worker |
| code block 独立 copy button | must-match | desktop + mobile / keyboard 截图 | worker |
| compact/coarse More + shallow Radix action sheet | must-match | 390×844 + 1024×768 hybrid；Branch 四状态；focus trap / close+restore | worker |
| 原型色值、阴影和微间距 | may-adapt | 按现有 token 微调截图 | worker |
| prototype viewport/state/language 控制条和演示侧栏内容 | out-of-scope | 无 | N/A |

## Roadpoints

### R1 — 内容策略与单元测试

- 步骤:
  1. 创建 `message-content-policy.ts`，暴露 `classifyChatLink`、`resolveContextMenuModality`、`shouldKeepNativeContextMenu`、`serializeMessageBody`、`extractCodeText`。
  2. 创建 `message-content-policy.test.ts`，覆盖 modality、选区、链接分类、序列化 fixture、代码提取。
- 验证:
  - `npm run test -- src/features/chat/components/message-content-policy.test.ts` 全绿且红测已跑。

### R2 — 气泡事件路由与共享 action model

- 步骤:
  1. 在 `MessageBubble` 移除 long-press 定时器与 touch 接管逻辑；新增 pointerdown 记录。
  2. 实现 context-menu handler：modality 解析 → caret point / native target 判断 → 仅在 mouse 普通区域阻止默认并请求 Pane 打开菜单。
  3. 派生共享 action model（copy-message + optional fork），统一 disabled 与 reason。
  4. 渲染 desktop toolbar（hover/focus 显示）与 compact/coarse More 按钮。
- 验证:
  - `npm run test -- src/features/chat/components/message-pane.test.tsx` 中新增/改写测试绿。

### R3 — Pane copy coordinator、反馈与 Radix action sheet

- 步骤:
  1. 在 `MessagePane` 实现 copy coordinator：conversation generation、attempt token、surface token、notice token 管理。
  2. 实现单一 copy snackbar / live region，success 1.6s / error 4s，旧 timer 不污染新 notice。
  3. 实现受控 Radix Dialog action sheet：Portal/Overlay/Content/Title、focus trap、outside/Escape/Cancel 关闭、回焦 More。
  4. 实现 mouse context menu：viewport clamp、Arrow 导航、Escape/外部点击关闭、回焦 trigger。
- 验证:
  - Vitest 覆盖 Clipboard success/failure、surface ownership、conversation switch、A→B→A、newer attempt、旧 notice timer。

### R4 — Markdown 链接分类与代码块复制

- 步骤:
  1. 新增 `ChatMarkdownLink` component：按 `classifyChatLink` 渲染 external target/rel、same-origin 无 target、system、unsupported span。
  2. 具名 external 用 CSS pseudo-element `↗`，aria-label 本地化。
  3. 新增 `MarkdownCodeBlock`：pre 包 copy button，inline code 保持纯文本。
  4. 把 `components.a` 与 `components.pre` 接入 `MarkdownContent`。
- 验证:
  - Vitest 覆盖 external aria-label、target/rel、same-origin 无 target、code block copy button 存在/行为、inline code 无按钮。

### R5 — i18n 与 CSS

- 步骤:
  1. 更新 `zh.json` 与 `en.json`：新增“复制整条消息”“复制代码”“更多操作”“已复制”“复制失败，请重试”“在新标签页打开”“从此处分支”“Agent 离线，暂不可分支”“正在创建分支…”。
  2. 更新 `global.css`：toolbar、menu、action sheet、link indicator、code copy button、focus ring、More 触控区。
  3. 移除 `.chat-bubble-card` 上的 `user-select:none` 与 `-webkit-touch-callout:none`；保留其他样式。
- 验证:
  - Vitest 覆盖中文无孤立 `fork`、英文文案。
  - 浏览器验收检查 computed `user-select`、`-webkit-touch-callout`、focus ring、触控区。

### R6 — 扩展测试与完整门禁

- 步骤:
  1. 改写 `message-pane.test.tsx` 中 feat-451 旧长按/复制测试为新行为。
  2. 更新 `message-pane-fork.test.tsx`：toolbar/More/sheet 中 Branch disabled 语义、不调用 onFork。
  3. 跑 `npm run test -- message-content-policy.test.ts message-pane.test.tsx message-pane-fork.test.tsx`。
  4. 跑 `npm run build` 与 `git diff --check`。
- 验证:
  - 三测试文件 + build + diff-check 全绿。

### R7 — 真浏览器验收与证据归档

- 步骤:
  1. 按 design.md Runbook 起隔离真栈。
  2. Chromium desktop 1440×900：选区右键、toolbar、Branch 四状态、copy、link、code copy、焦点回焦。
  3. Chromium hybrid 1024×768：toolbar + More 同时存在、mouse/touch 路径区分。
  4. Playwright WebKit 390×844 + touch：Selection、长按、More/sheet、focus trap、safe area、computed CSS。
  5. 保存证据到 `M1-impl/evidence/`，记录事件 facts 与对照结论到 `progress.md`。
- 验证:
  - 证据文件存在且可复查；`progress.md` Prototype Comparison 完成。
