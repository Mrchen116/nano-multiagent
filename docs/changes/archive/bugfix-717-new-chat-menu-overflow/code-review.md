# bugfix-717 代码审查（change-code-review）

- **Unit**：`bugfix-717-new-chat-menu-overflow`（Bugfix lite，M1-fix）
- **审查对象**：worktree `.worktrees/bugfix-717-new-chat-menu`，branch `unit/bugfix-717`，HEAD `d0b3716f0`，base `origin/main`
- **范围**：`git diff origin/main...HEAD`（3 个文件：`src/IM/frontend/src/styles/global.css`（+4/−1）、`fix.md` +147、`M1-fix/evidence/browser-verification.md` +95），commit `50c90bd3e → 929a2ca3a → b7308be0e → c18f3a0f6 → d0b3716f0`
- **审查方式**：只读源码审查 + 本机真实 Chrome（Playwright 1.60，headless）复跑 unit 自己的 `/tmp/bugfix717` 证据脚本 + 我另写的确定性探针（冻结 CSS transition，不用 timing 采样）；未启动任何后端服务，未改动源码
- **结论**：**Approved**

```
BLOCKER 0    MAJOR 0    MINOR 3    NIT 3
```

修复本身是成立且收敛的：唯一真正的裁切者确认是 `.chat-sidebar-header-row` 的 `overflow:hidden`；去掉它之后行不再是滚动容器，打开菜单时 `focus()` 不再滚动任何祖先；`.chat-sidebar--searching` 下的裁切只影响已经 `inert` 且不可能有浮层的折叠态；无 TSX 改动，可访问性契约逐条保持。3 个 MINOR 都在 `M1-fix/evidence/browser-verification.md` 的度量/机理论述（`fix.md:120` 复述了其中两处结论），表现为不能完全复现或机制说错，不影响修复正确性，建议在提 PR 前改正（不需要复审）。

---

## BLOCKER

无。

## MAJOR

无。

## MINOR

### MINOR-1 `57 条全部通过` 不能稳定复现（证据脚本其中一个断言是竞态）

**证据**：`M1-fix/evidence/browser-verification.md:46`、`fix.md:120`。

我用 unit 自己记录的同一份构建产物和同一份脚本复跑两次，两次都是 **56 通过 / 1 失败**，失败项相同：

```bash
cd /tmp/bugfix717
CSS_PATH=/tmp/bugfix717-dist/css-fixed/assets/css-entry-By7Ix20p.css OUT_DIR=/tmp/bugfix717/review-shots LABEL=rev-fixed  node verify.mjs
# FAIL  [375x600] entering search animates the row height down  44
# 1 CHECK(S) FAILED — 56 passed          （连跑两次结果相同）
```

`verify.mjs:150-156` 在 `page.click(".chat-sidebar-search")` 之后固定 `waitForTimeout(90)` 再读行高，断言 `0 < height < 44`。命中 90ms 采样点时读到 44 就是"过渡还没开始"。

这不是修复引入的行为变化。我在页面内用 rAF 连续采样（`/tmp/bugfix717/probe-enter-timeline.mjs`，直接 `input.focus()`，无跨进程往返），两个构建的收起时间线一致：

```
[fixed  375x600] 首个采样 62ms h=44 → 92ms h=30.2 → 136ms h=7.8 → 215ms h=0
[prefix 375x600] 首个采样 47ms h=44 → 82ms h=30.2 → 105ms h=13  → 181ms h=0
```

即过渡起点本身落在 focus 后约 50–90ms 之间，90ms 采样天然骑在边界上；prefix 那次恰好采到 7.8 而通过，与 `overflow` 无关（`overflow` 不参与 transition）。

**建议改动**：把该断言改成确定性判定（`document.getAnimations()` 后 `pause()` + `currentTime = 40`，再测量；本审查就是用这个方法拿到稳定中间帧的），或把这类 timing 采样降级为 `INFO`，只断言终态；同时在证据文件里把 `57 条全部通过` 写成"记录那次运行 57/57，其中 `entering search animates the row height down` 是 timing 采样"，不要把它当稳定属性。

### MINOR-2 搜索折叠中间帧表里 375x600 一列的数值不可复现

**证据**：`M1-fix/evidence/browser-verification.md:67`（"退出搜索 ~30ms | 行高 13.9，opacity 0.47 | 行高 13.9，opacity 0.47"）。

两列数值完全相同，但 `frames.mjs` 是 `waitForTimeout(30)` 采样。我复跑：

```
[1072x444] exit 30 {"h":13.9,"op":"0.469809",...}     # 与证据一致
[375x600]  exit 30 {"h":0,"op":"0",...}               # 与证据不一致（采样早于状态生效）
```

结论（"中间帧看不出瑕疵"）不受影响，但 375x600 那一列不是这次能测出来的数。**建议**：按实际采样值分列记录，或与 MINOR-1 一起换成冻结 `currentTime` 的确定性采样。

### MINOR-3 退出动画"没有可见瑕疵"的机制写错了

**证据**：`M1-fix/evidence/browser-verification.md:70-71`——"退出动画期间内容已随 `opacity` 淡入"。

真实机制不是 `opacity`。我在退出方向把 transition 冻结在 20ms 后测量（`/tmp/bugfix717/probe-freeze.mjs`）：

```
row 14→20（6px 高），trigger −3→37，searchRow 21.4→58.6
trigger 与 search row 重叠 15.6px
document.elementFromPoint(重叠带中心) → INPUT.chat-sidebar-search
```

即溢出的行内容被搜索框**盖住**，因为它不是被裁掉而是被压在下面：`.chat-search-input-row { ... position: relative }`（`global.css:1826`）是行之后的一个定位兄弟节点，按绘制顺序盖过 `.chat-sidebar-header-row` 的溢出内容（行内 `.chat-sidebar-create` 的 `position: relative` 见 `global.css:1722`）。真正让瑕疵不可见的第二层原因是溢出带里本来只有触发按钮的透明内部（40ms 帧：glyph 22px 居中，`y 12→34`，未进入 `36→43` 的重叠带）。

**建议**：把这句改成"行内容的溢出由 `.chat-search-input-row` 的定位绘制顺序遮住，且重叠带内只有按钮透明区域"，并注明这是**偶然耦合**——若以后有人去掉 `.chat-search-input-row` 的 `position: relative`，或把行内容做高，同一处会出现可见溢出。若想让它变成有意设计，可在 `.chat-search-input-row` 上显式加 `z-index` 并把注释一并更新。

## NIT

### NIT-1 `15 条失败` 里混了 3 条实现属性断言

`fix.md:117`、`browser-verification.md:46` 的 15 条中，每个视口各有 1 条是断言实现属性（`verify.mjs:121` 的 `row.overflow === "visible"`）。真实行为断言是 12 条。证据表的逐行内容是透明的，不影响判断；建议措辞改成"12 条行为断言 + 3 条实现属性断言"，避免把"15 条失败"读成 15 条用户可见行为失败。顺带一提，`verify.mjs:121` 这种断言把 harness 绑死在"删 overflow"这一种实现上（若将来改用 portal 修，行为更好但这 1 条会红）；因为它不在仓库里，只是记录一下。

### NIT-2 证据脚本只活在 `/tmp`，仓库内无法复跑

`browser-verification.md:3` 已明确声明复现页、构建产物、截图都在 `/tmp/bugfix717/`，`fix.md:137-139` 也把"没有前端布局回归测试基线"写成了已知缺口并指向后续 unit。作为 lite unit 的**证据**这是可接受的（我按文档命令确实复跑成功），但要提醒：`/tmp` 被清理后，仓库里只剩结论与命令，`verify.mjs` / `frames.mjs` / `sidebar-harness.tsx` 本身不可恢复。若不打算很快立那个后续 unit，建议把三个脚本原文放进 `M1-fix/evidence/`（纯文本，不是浏览器测试基线，不改变仓库测试约定）。

### NIT-3 "必须完整展开"这条不变量目前只有 CSS 注释守着

`global.css:1704-1706` 的注释是对的（见下"已核实"），但 canonical spec 没有对应的行为契约：`docs/specs/im/web-chat-ux.md` 只在 `:556-557` 提到"用户打开新建群聊"，没有"「+」菜单以完整浮层展开、契约内各项均可到达"。Bugfix lite 的"必要的 canonical spec 归并"因此是一个需要**显式判断**的步骤。建议在 PR 描述或证据文件里写明"本次不改 spec"的理由，或补一行契约，让这条几何不变量不只依赖一段注释。

---

## 我实际验证的 vs 我推断的

### 已核实（读代码 / 本机实跑）

1. **裁切链收敛**。popover 祖先链：`.chat-sidebar-create`（`global.css:1722`，`position: relative`，无 `overflow`）→ `.chat-sidebar-header-row`（`:1694-1702`）→ `.chat-sidebar-header`（`:1685`，无 `overflow`）→ `.chat-sidebar`（`:1672-1683`，`:1681` `overflow:hidden`）→ `.chat-workspace`（`:1663-1669`，`:1667` `overflow:hidden`）。链上无 `transform` / `contain` / `clip-path` / `filter` / `will-change`，`.chat-sidebar-header-row` 是唯一在 popover 垂直方向真正裁切的祖先。
2. **剩下的 `.chat-sidebar{overflow:hidden}` 在真实几何下不裁 popover**：桌面 popover `menuRect = {x 89, y 60, w 160, bottom 202}`，右边界 249 < 侧栏 262，底边 202 < 用户窗口 444；320–1440 五档横向 `documentElement.scrollWidth === clientWidth`、`menuRight < sidebarRight` 与证据一致。
3. **RCA 归属正确**。`git blame 929a2ca3a^`：`:1700 overflow: hidden` 与被保留的 `max-height/opacity/transition` 同属 `359109c98`（2026-10-30）；`git show 692e5180e:...global.css` 中该行只有 `display/align-items/justify-content/margin-bottom`，无 `overflow`、无 `max-height`——`fix.md:41-44`、`:58-64`、`:60` 的历史论断成立。
4. **`overflow:hidden` 原本没在保护别的东西**。行的子节点只有静态表头文案 `.chat-sidebar-title`（`conversation-sidebar.tsx:209`，不是会话标题；i18n 只有 `zh 消息` / `en Messages`，`src/i18n/{zh,en}.json`）和 `.chat-sidebar-create`（`:210`）。桌面行内容高 40 ≤ `max-height:44`；窄屏 `.chat-sidebar-create` 变成 `position:absolute`（`global.css:5061-5065`）不参与行内布局——常态没有任何溢出需要裁，`overflow:hidden` 此前实际只裁到 popover。水平溢出仍由 `.chat-sidebar{overflow:hidden}` 兜住，不新增"paint 到 pane 上"的风险。
5. **退出动画的溢出窗口存在，但不可见**（见 MINOR-3 的冻结实测）。glyph 与标题都不在重叠带内，进入重叠带的只有透明区域，且被搜索框盖住。`prefers-reduced-motion` 下 `global.css:1887` 直接关掉该行的 transition，连窗口都没有。
6. **`.chat-sidebar--searching` 与布局变化同一时刻生效**：class 加在 `<aside>`（`conversation-sidebar.tsx:206`），与 `:208` 的 `inert` 同源于 `searchActive`；`max-height:0` 和 `overflow:hidden` 同属 `global.css:1707-1712` 一条规则，同一帧生效，**进入方向不存在"未裁切窗口"**。
7. **a11y 契约未动**：`new-conversation-menu.tsx:16-24`（打开聚焦首项 + 外点 pointerdown 关闭）、`:26-39`（Esc 关闭、跨项方向键导航）、`:41-45`（选择后焦点回「+」）、`:56`（blur 出 root 关闭）。TSX 一行未改。修复后打开菜单时 row / `.chat-sidebar` / `document.scrollingElement` 的 `scrollTop` 全为 0（harness 实测），聚焦不再把行滚走——即"焦点可见"从被破坏变为成立。
8. **测试诚实性**：`verify.mjs` 用的是仓库真实的 `NewConversationMenu`（esbuild 直接打包 `new-conversation-menu.tsx`）、真实 `src/i18n`，CSS 走仓库自己的 `vite` + `@tailwindcss/vite` 构建 `global.css`（`vite.css.config.mjs` 插件与 `src/IM/frontend/vite.config.ts` 一致）；只有外层侧栏骨架是手抄 `conversation-sidebar.tsx:206-262`，我逐行对照后确认结构一致（差 `distillMode` 分支与 `personalAgentEntry`，都不在行内、不影响几何）。
9. **`conversation-sidebar.test.tsx:182-222` 不是覆盖**：它只断言菜单出现/选择回调/焦点归还与键盘导航，jsdom 无布局无裁切。我实跑该文件 `21 passed (21)`，与证据一致。仓库确实没有 Playwright 配置或浏览器测试目录（`src/IM/frontend/playwright.config.*`、`e2e/`、`tests/` 均无），也没有测试 import `global.css`（全仓 grep 只命中 `src/main.tsx`）。**没有新增任何已提交的回归测试**，`fix.md:137-139` 主动承认了这一点。
10. **修复前后数值全部复现**：我用同一 harness 复跑 prefix 构建得到 42 通过 / 15 失败，逐条数值与 `fix.md:117-119` 完全相同（375x600 行高 44、`scrollTop 55`、标题 `y=-35.8`、「+」`y=-45`；1072/1440 行高 40、`scrollTop 53`、`y=-27.4`/`-39`；`scrollHeight 188 / clientHeight 40`）。
11. **作用域纪律**：分支只动 3 个文件，`global.css` 净变化 −1/+4（其中 3 行注释），无 TSX、无 `src/IM/frontend/dist/`、无无关格式化；4 条 docs commit + 1 条 fix commit，逐个 commit 的文件列表都只含本 unit 相关文件。文档里引用的 `fix.md` 行号（`:1694-1702`、`:1704-1706`、`:1707-1712`、原 `:1700`、`conversation-sidebar.tsx:208/:210`、`new-conversation-menu.tsx:18/:37`）逐条对得上；`fix.md:46` 引用的 `global.css:5718-5722` 是按改动前的行号（改动后为 `5721-5725`，语句一致），符合该节"行号为改动前"的声明；`fix.md:66` 引用 `docs/specs/im/web-chat-ux.md` 的"独立搜索视图"存在于该文件 `:32-35`。

### 仅推断（本审查无法证实的部分)

1. **原始报告与截图**：`c_f2mbtxa9` 的消息 `843b7bf49e3b490e84dfaf5883a1ee87`、"弹窗卡在里面了"原话、`1072x444` 窗口尺寸、IM 附件 `b0634681…`——我无法访问 IM 会话与附件，只能确认 `fix.md:3-13` 的表述内部自洽，且截图形态与我在 prefix 构建下复现的画面一致（`/tmp/bugfix717/shots/prefix-1072x444-open.png` 只剩一条被裁的「新聊天」碎片、标题与「+」不可见）。
2. **生产等价性**：我用的是 unit 自己构建的 CSS 产物 + 手抄外层骨架，不是完整前端应用（需要后端与登录）。几何契约上等价，但"真实应用里点击路径、焦点上下文完全相同"属于推断。
3. **全量前端测试的 2 个失败与本改动无关**：我核实了本机 `node_modules` 里确实没有 `maplibre-gl`、前端测试确实不 import `global.css`（两者足以解释 3 个 transform 失败与该改动的无关性），但没有复跑 `chat-workspace.integration.test.tsx` 去亲验"改动前同样失败"，这一点采信证据文件的 stash 复验记录。
4. **极矮视口残余风险**：`fix.md:145-146` 承认 <270px 高时 `.chat-sidebar{overflow:hidden}` 仍可能间接裁切/滚动。我确认这是既有风险（修复前更糟）且与用户 444px 窗口无关，但没有在 <200px 高下做独立复验。

---

## 对"修复方案选择"的判断

维持纯 CSS、不引入 portal 是合理的：改动面 1 行删除 + 1 行条件化 + 3 行注释，且把 portal 方案要连带处理的定位、外点关闭、Esc 回焦、移动端覆盖层 z-index 全部留空。`fix.md:100-108` 对"不加 `focus({preventScroll:true})`"的论证也成立——`new-conversation-menu.tsx:37` 的方向键导航同样会触发滚动，只挡打开路径会让两条路径行为不一致，而修复后已无任何祖先需要为聚焦而滚动。

唯一结构性弱点是这条不变量现在只由 `global.css:1704-1706` 的注释守着（NIT-3），并在退出动画上偶然依赖 `.chat-search-input-row` 的定位绘制顺序（MINOR-3）；两者都不构成本次交付的阻塞。
