# bugfix-545: Web IM 统一浅色界面、群聊身份与移动端交互

## 最终交付状态

用户完成逐项预览后，明确要求自行 review（不使用 skill）、提 PR、关闭服务并删除 worktree。以下过程记录保留迭代证据；本节及 current spec 表示最终范围，覆盖此前暂停 PR 的临时约定。

- 统一聊天、导航、菜单、Agents 侧栏、过程和 token 明细的浅色视觉；Agent 使用稳定浅色字母头像，群聊使用独立群组图标。
- 新建群聊候选为名称/状态与 Agent ID/机器两行，状态使用正确中英文翻译。
- 手机具体会话隐藏全局底栏，返回与设置为线条图标和 44px 点击区域；调整输入区，技能生成移至侧栏次级入口。
- Process 内工具默认收起；用量详情保留浅色内联卡片（已撤回两列无框实验）。
- 手机移除 More 三个点，新增约 500ms 长按并复用原有右键菜单及选区/链接/代码策略；未禁用文字选择，未改变原有悬浮 toolbar。
- 仅 frontend 与其 current 行为文档变更，不含 runtime config、凭据、数据库、日志、截图或构建产物，不执行生产部署。

自审与交付验证见 [review.md](review.md)。

## 原始报告

> 新建群聊根本看不出哪个agent在哪个机子上，不好选择agent。chat.status.online是啥意思，为啥这么一串，而不是直接online？

截图：`/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-ca939b25-5e9e-4d41-aaa5-51101996adf6.png`

## 现象 / 复现

打开 Chat → 新建群聊，候选 Agent 行只有名称、描述和状态，没有独立机器标识；描述被截断后无法据此判断机器归属。在线状态直接显示 `chat.status.online`。

## 根因

- `new-group-modal.tsx` 使用 `chat.status.${a.status}`，但中英文资源定义在 `chat.newGroup.online/offline`。缺失键经 i18next 返回原始键名。
- `chat-workspace-page.tsx` 已按 Agent 的 `node_id` 找到节点，但传入弹窗时仅提取状态，没有传机器名或节点 ID；弹窗的 AgentRow 也没有机器归属字段。
- 当前 online 表示所属节点状态为 online，并非 Agent 正在执行任务；其他节点状态在现有映射中均显示 offline。
- 最近修改该组件的提交为 `86b07fee7`（canonical Chat 迁移）；此处不据此认定它就是最初引入问题的提交。

## 修复范围提议

每个候选 Agent 独立展示所属机器，保留名称、描述与勾选操作；状态按界面语言显示 online/offline 或在线/离线。机器标识不依赖描述文本。


## 用户确认与交付边界

> [$change-orchestrator-simple](/Users/czj/Repos/nano-multiagent/.claude/skills/change-orchestrator-simple/SKILL.md) 开个worktree改下，改完给我截图告诉我效果，我看看满不满意，不需要开code review等繁琐的后续步骤

依照用户指令，仅实施与截图预览，保留 worktree 等待用户反馈，不执行 code review、归档、push 或 PR。

## 修复

在 `codex/bugfix-545` worktree 完成：页面传递机器名（名称为空时显示节点 ID）；弹窗在 Agent 名下独立展示机器标识，允许长标识换行；状态使用已有中英文 newGroup 翻译。

## 验证

- 修改前原有弹窗 4 项测试通过；扩展既有文件检查中英文机器归属和状态，修前 2 项失败、修后 6 项通过。
- 弹窗与 ChatWorkspace integration 共 58 项通过；TypeScript + Vite build 通过；git diff --check 通过。已有 integration act 警告和构建 chunk-size 提示仍存在。
- 隔离 IM + Gateway + Vite，通过浏览器真实登录 → 新建群聊 → 选择两个 Agent → 创建群聊，POST conversations 返回 201。
- 浏览器 1440×1100 与 390×844 验证，截图位于 `output/playwright/group-desktop.png` 和 `output/playwright/group-mobile.png`。
- 机器名 mac-mini/macbook-air 对应本次隔离数据库示例，不是生产状态；两个 e2e Agent 来自真实隔离 Gateway。示例 Agent 无运行时连接，创建后能力查询 409 为该 fixture 的边界；选择弹窗获取 agents/nodes 均 200，无新 JavaScript 异常。
- 起初启动脚本的后台进程被工具 shell 回收，登录 500；改为 tmux 托管后登录正常。验收结束已停止本次 IM、Gateway、Vite 与浏览器，保留 worktree 和截图供用户反馈。


## 后续用户反馈与当前预览

> 另外，本unit还要改上，群聊头像能不能和单聊做区分呢？设计个不同的，比如两个小头像? 你自己考虑，常见IM怎么从头像看出这是群聊

> 你这个三行好丑，没必要三行吧，参考这里也没用三行

参考截图：`/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/codex-clipboard-cbf19416-89db-4e0c-bd2f-ab6b9748a5ab.png`。

当前实现取代上面的三行初版：候选项只保留两行，第一行名称/状态，第二行 Agent ID/机器名，移除描述。会话 type=group（含 Agent network）的列表、选择模式和聊天顶部使用同一双人叠放 SVG；单聊与消息发送者头像保持原样。

最新验证：扩展既有 sidebar 测试，修前缺少群聊图标而失败；修后 sidebar、message-pane、new-group-modal 共 109 项通过，TypeScript/Vite 构建通过。浏览器真实隔离接口创建两个单聊和一个群聊，列表与顶部可见不同头像，agents/nodes/conversations 请求成功，无新增 console error。两行弹窗在桌面与 390×844 手机尺寸检查通过。

最新截图：`output/playwright/group-two-line-desktop.png`、`output/playwright/group-two-line-mobile.png`、`output/playwright/group-avatar-desktop.png`。均为本 unit 隔离环境，不代表生产部署。保留 worktree 等待用户效果反馈，继续不执行独立 review 或 PR。


## 群头像第二轮预览

> 你这个双人叠放头像好丑，非常丑。

> 改完给我看看

当前群头像取代双人人像 SVG：浅灰圆角方形底板，两个成员的彩色首字母圆头像并排展示，颜色沿用成员姓名的既有算法。优先展示两个 Agent，否则选现有成员；不以群名冒充成员身份。列表与顶部共用 GroupAvatar，单聊仍为原圆形头像。

验证：sidebar/message-pane 103 项通过，TypeScript/Vite build 通过；真实隔离浏览器完成群聊/单聊并列展示。截图 `output/playwright/group-member-tile-desktop.png`；局部截图命令失败，本轮没有另存局部或手机截图。示例将隔离 e2e 成员名称设置为 plato/hume。保留 worktree 等待用户反馈，停止本轮服务，不部署。


## 已选方案 A 实施

> A吧

用户从三套视觉稿选择 A。当前实现取代先前所有群头像试稿：单聊使用固定六组柔和浅色背景与配套深色字母，继续以完整 display_name 确保 Agent 跨入口一致；群聊采用深蓝灰圆角方形与 Lucide users-round 线条标识。列表、顶部、群设置、提及选择、Agents 页面通过已有共享 Avatar 接入；消息头像和发送者名称也使用对应前景色，避免浅色文字。

验证：组件套件首轮 338/339 通过；唯一失败为原断言比较浏览器 RGB 序列化与新的十六进制颜色，改为 toHaveStyle 后该文件 8/8 通过。TypeScript/Vite build 通过，git diff --check 通过。真实隔离浏览器完成群聊/单聊切换，桌面 1100×720 与手机 390×844 截图；console 无 error。

当前截图：`output/playwright/avatar-a-desktop.png`、`avatar-a-direct.png`、`avatar-a-mobile.png`。保留 worktree，停止本轮临时服务，未部署、未开 PR。


## Logo 与用户头像统一

> 头像浅色了，logo是不是也要浅一点？以及右上角的用户头像

> 改

Logo 改为低饱和浅青绿底与深青色勾；右上角触发器和展开菜单中的用户头像共用浅灰青背景、深色字母与 600 字重。

验证：app-shell 4 项测试通过，TypeScript/Vite 构建通过，git diff --check 通过。浏览器打开真实隔离 IM 并展开用户菜单检查，截图 `output/playwright/avatar-a-shell.png`、`avatar-a-user-menu.png`。本次只启动隔离 IM 与 Vite，未启动 Gateway；两个 capabilities 请求返回 503 是隔离节点离线的预期限制，与头像修改无关。结束时停止本次两个服务与浏览器，保留 worktree。


## 整体配色统一

> 整体灰灰沉沉的为啥，是要把背景色调整下吗？你能不能整套配色方案统一调下，不是指一下改一下。给一套最佳的配色

根因：导航使用写死的深灰，聊天区、输入区与气泡则使用明度接近的多组灰色；只改头像使低饱和色继续叠加，缺少层次。本轮将基础色集中在 global.css 的语义 token，旧暗色导航规则改为引用这些 token：白色内容/顶部/输入区、冷灰侧栏、浅青选中态、深青主要操作、深色正文与有足够对比度的辅助文字。头像沿用已选 A。同步范围为桌面/手机导航、Chat 列表/背景/气泡/输入区、群聊弹窗、用户菜单，以及 Agents 列表与详情侧栏。

本轮不改变消息内容、交互或数据协议。气泡预览内容直接写入隔离数据库作为视觉 fixture，未发送消息或调用模型。

验证：相关套件首轮 335/336 通过，唯一失败是既有 Agents rail 测试要求暗色侧栏白字；更新为新的语义颜色后该文件 3/3 通过。最终 TypeScript/Vite build 与 git diff --check 通过。桌面 1200×850 和手机 390×844 实际浏览器检查聊天、选中态、弹窗、Agents 导航与输入区；计算样式确认顶部/聊天/输入区为 rgb(255,255,255)，侧栏为 rgb(245,248,250)。辅助文字进一步收紧为 #60717e，正文/辅助文字/主要操作/选中态/用户气泡五组对比度均超过 4.5:1。

截图：`output/playwright/unified-theme-chat.png`、`unified-theme-mobile.png`、`unified-theme-picker.png`、`unified-theme-agents.png`。本次只启动隔离 IM/Vite，capabilities 503 来自未运行 Gateway，与主题无关；数据加载请求正常。保留 worktree 等待视觉确认，不部署、不 PR。


## Config 齿轮尺寸

> 有没有发现config那个齿轮非常小，很怪异
> 改

将字体齿轮替换为固定 16×16 的 Lucide settings SVG，与 Config 文字通过 inline-flex 居中对齐；桌面按钮最小高度 32px，手机图标按钮保持 44×44 点击区域。

验证：message-pane 92/92 测试通过，TypeScript/Vite build 通过。真实浏览器点击 Config 正常打开 Group settings；手机视口计算尺寸确认按钮 44×44、图标 16×16。桌面实际截图 `output/playwright/config-icon-header.png`。仍仅本地 worktree 修改，未部署或提交 PR。

## Unified UI polish and comparison screenshots

User authorized adjusting the five reviewed UI issues and requested before/after images.

Changes: consistent 18px outline menu icons and aligned sign-out row; shared composer border containing the send button and focus indication; secondary Generate skill entry at the sidebar bottom; tighter mobile message/status spacing with 44px More targets retained; desktop Agents selection placeholder with English/Chinese copy and a 240px sidebar.

Validation: initial message-pane/sidebar/Agents run passed 107 tests; final sidebar/Agents/app-shell run passed 19 tests (overlapping coverage). Final TypeScript/Vite build and git diff --check passed. Actual browser screenshots at 1200x850 desktop and 390x844 mobile were arranged as left-before/right-after comparisons: output/playwright/compare-desktop.png, compare-mobile.png, compare-menu.png, compare-agents.png. Menu and Agents before images reuse the preceding same-size captures; chat before images were captured immediately before this change. Gateway was not started; capabilities 503 reflects offline isolated nodes. Isolated IM, Vite, comparison server, and browser were stopped. Local worktree only; no PR or deployment.

## Mobile conversation navigation

User confirmed hiding the bottom Chat/Agents/Me navigation inside an individual mobile conversation. AppShell now matches /chat/:conversationId and hides that navigation only on mobile; the composer retains bottom safe-area padding. The chat list retains all three tabs. AppShell tests passed 5/5 and TypeScript/Vite build passed. Browser verification at 390x844 confirmed the input at the bottom and navigation restored after pressing Back. Screenshot: output/playwright/mobile-chat-no-nav.png. Isolated services stopped after verification; no deployment.

## Mobile Back icon

User accepted enlarging the Back control ("gai" typo interpreted in context). Replaced the text chevron with a 20px outline left arrow and a 44x44 button aligned by inline-flex. Existing Back handler and accessible name retained. Message-pane 92/92 tests, TypeScript/Vite build and git diff --check passed. Local only; no deployment.

## Mobile settings icon without a box

User requested showing only the gear on mobile. Removed the mobile Config border, padding, and hover fill while retaining the 44x44 hit area and visible keyboard focus. Desktop Config styling remains as before. TypeScript/Vite build and git diff --check passed; local only.

## Real reply process and usage styling

User supplied a real reply screenshot showing incompatible dark process/token panels and a bright green machine badge, then requested implementation and screenshots. Unified process, thinking, tool detail and usage surfaces with the light palette, removed heavy shadows and pill backgrounds, and replaced the thinking emoji with an outline icon. Node identity is now muted small text with an online dot. Token detail expands in normal layout instead of an absolute overlay. Existing default-collapsed process/usage interactions remain intact; semantic failure and diff colors retained.

Validated the actual hume reply through browser at 550x844 and 390x844, including opening both thinking and usage. Screenshots: output/playwright/real-reply-collapsed.png, real-reply-expanded.png, real-reply-expanded-mobile.png. Process/token tests passed 75/75; final build and git diff --check passed. Preview IM/Vite/Gateway remain running for the user's manual testing, per explicit request. No deployment or PR.

## Process tool rows default collapsed

User confirmed that opening Process should show summaries only. Removed the first-tool default-open special case and its index counter. Every tool row now initializes collapsed, including after closing and reopening Process. Updated the behavior regression to check explicit expansion and reset, and adjusted expanded-body tests to click the tool before inspecting details. All 68 process tests and TypeScript/Vite build passed; git diff --check clean. Live preview remains available.

## Borderless token details

User requested removing the remaining nested token card and trying a better disclosure layout. Token detail now has no border, fill or rounding. Four metrics use a two-column layout with small labels above aligned numeric values; context utilization remains a thin full-width indicator. Disclosure remains inline and click-controlled. Actual 390px browser screenshot of the real reply: output/playwright/token-borderless.png. Token tests 7/7 and build passed; diff check passed. Preview services kept running.

The user rejected the borderless two-column token experiment as worse than the preceding version. Reverted only that experiment, restoring the preceding light inline card and label/value rows. Other accepted UI changes remain.

## Mobile long-press actions

User requested removing the mobile message More dots in favor of long-press. Mobile bubbles now open the existing action sheet after a 500ms touch hold. Touch movement beyond 10px, release, cancellation, and unmount cancel the timer; embedded buttons and links are excluded. Removed mobile More buttons and hover toolbars, suppressed native text callout on the message body, and retained a focusable bubble with ContextMenu/Shift+F10 keyboard access and focus restoration. Desktop actions remain available. Tests cover hold, scroll cancellation, quick tap, copying and focus restoration; message-pane 93/93 tests passed. Build and diff check passed. Preview services remain running for manual testing.

## Restore right-click alongside long-press

User caught that the mobile contextmenu branch consumed right-click without opening actions. Corrected it to cancel the pending hold and call the same action-sheet entry as long-press. Desktop context menu behavior retained. Added a mobile mouse-right-click regression alongside the existing hold/cancel tests. All 94 message-pane tests and build passed; diff check clean.

## Correct long-press scope after user regression report

User clarified only two authorized changes: remove mobile dots and add long-press through the ORIGINAL right-click logic. Removed the selection/callout CSS overrides, toolbar hiding, mobile-specific contextmenu/action-sheet branch and added keyboard behavior. Long-press now calls the same extracted menu-opening function as the original right-click handler, including existing native selection/link/code policy. Scrolling still cancels the timer. Original right-click event classification remains unchanged. Added regression for mobile right-click and hold opening the original menu (not a dialog), move cancellation and preserving an existing text selection. Message-pane and content-policy suites passed 117/117; build and diff check passed. Earlier action-sheet approach is superseded.
