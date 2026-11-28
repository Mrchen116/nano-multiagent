# bugfix-820: IM 桌面端设置返回导航、日常 Chrome 配对说明与用户向术语统一

Platform-Parity-Exempt: Web IM 与 Desktop 主窗口 WebView 共享本次导航与中英文文案修复；原生 iOS 使用独立 SwiftUI Tab/NavigationStack 结构且不含桌面端 `/me` 路由与本机 Chrome 扩展配对入口。

## Relations

- Related: `feat-604`（账号与策略页设置体验）、`feat-790`（Desktop 客户端与日常 Chrome 引导配对）、`feat-804`（真人自定义头像裁剪上传）

## 原始报告

> Issue G（设计）：独立 Account 整页是为移动端网页设计的，桌面端冗余
> 现象：桌面端（客户端/浏览器）点左下角头像会进入独立的 Account 整页（单列、大间距的移动式布局），"返回"逻辑也绕；而桌面端已有头像下拉菜单（Nodes / Model services / Policies / Language / Sign out）。
> 判断：该整页显然是为手机上打开网页设计的（移动端单列布局），在桌面端与下拉菜单功能完全重复。
> 建议：桌面端移除独立 Account 页（或仅移动端保留），桌面统一使用头像下拉菜单；避免"返回"落到单列列表页。
>
> Issue H（文案）："连接 Chrome"功能描述不清，只提"复用登录态"未提"控制/自动化"
> 实际功能（packages/dsh-integration/src/computer/browser.ts）：连接后 agent 可控制这台电脑的 Chrome——open/navigate/new_tab/tabs/select_tab/close_tab/snapshot/screenshot/console/network/click/type/upload/copy/paste，即完整浏览器自动化；daily 模式复用已登录会话，isolated 模式不碰用户数据。
> 问题：UI 只写"配对一次后，助手可在后台标签页复用已登录状态（免重启生效）"，完全没有提到"控制浏览器 / 自动化"，用户无法判断这是让 agent 操作 Chrome。
> 建议：文案改为明确表达"连接后助手可控制 Chrome 浏览器（打开网页、点击、输入、截图、读取页面），并使用你已登录的网站会话；daily=复用登录，isolated=隔离环境"。
>
> Issue I（文案/术语）：Account 整页是内部黑话，专业用户与小白都不易理解
> 现象：Account 页菜单/内容使用内部术语：Root、Nodes、Model services、Policies、Company members 等。
> 问题：这些是产品内部"黑话"而非通用表达：
> Nodes → 用户不知道是"设备 / 电脑"（还要配对 Gateway）
> Model services → 不知道是"AI 模型 / API Key 配置"
> Policies → 不知道是"权限 / 审批 / 安全规则"
> Company members → 不知道是"成员管理"
> Root → 像角色名，实际是账号名
> 建议：改为通用表达并附一句说明，避免内部术语裸奔。

Agent 解读：
1. 用户在反馈中提到的「单列、大间距、与头像下拉菜单完全重复的独立 Account 整页」实际是窄屏专用的 `/me`（`MePage`），而非 `/settings/account`（`AccountPage`）。`AccountPage` 承载修改显示名、个人头像裁剪上传/移除、个人空间与团队状态查看等独占能力，桌面端 `UserMenu` 无法替代，必须保留；真正需要消除的是桌面视口下把用户带入 `/me` 的错误返回链接，以及桌面视口直接停留 `/me` 的路径。
2. `PoliciesPage` 的真实功能是「查看实际附件存储容量用量 + 维护尚未接入运行执行的团队策略预设」，并非工具审批开关；术语重命名与副标题说明必须诚实反映真实页面能力（如「用量与团队规则 / Usage & Policies」），不制造虚假功能承诺。
3. 用户反馈中的 `Root` 为测试账号自身的注册显示名，但 `MePage` 身份卡副标题确实直接渲染了内部 UUID（`user?.id`），应与桌面端 `UserMenu` 对齐改为 `@username`（缺失时优雅不展示，不暴露内部 ID）。

## 现象 / 复现

1. **桌面视口误入移动端 `/me` 单列菜单页（Issue G）**：
   - 在桌面浏览器或 Crewden Desktop（窗口宽度 `>= 768px`）从左下角 `UserMenu` 进入 `/settings/account`、`/settings/nodes` 或 `/settings/policies`；
   - 页面左上角始终显示 `‹ 我的账号` / `‹ My account`（目标路由为 `/me`）；点击后跳入专为窄屏底部第 5 个 Tab 设计的单列大间距 `MePage`（`/me`），与左下角 `UserMenu` 菜单项完全重复；
   - 同时，窄屏（`< 768px`）从 `/me` 进入 `/settings/models` 时顶部反而缺少 `‹ 我 / ‹ Me` 返回链接。
2. **「日常 Chrome 浏览器」配对卡片未说明浏览器控制/自动化能力与隔离边界（Issue H）**：
   - 在电脑页（Desktop 本机卡片或 Web 电脑详情抽屉）或 Agent 配置/新建页勾选 `computer_use` 后查看 `BrowserPairingSection`；
   - 摘要文案仅写「配对一次后，助手可在后台标签页复用已登录状态（免重启生效）」，未提及助手会在后台操作该 Chrome（打开网页、点击、输入、读取页面与截图），也未完整交代未配对/无需登录态时使用「干净隔离浏览器（独立环境，不触碰个人浏览器数据）」的边界。
3. **导航菜单与移动端 `/me` 页残留内部术语、硬编码文案及内部用户 ID（Issue I）**：
   - `MePage` 顶部身份卡副标题直接显示 `user.id`（内部 UUID）；
   - `UserMenu` 与 `MePage` 硬编码三元表达式 `lang === 'zh' ? '模型服务' : 'Model services'`，未走 `i18n`；
   - `UserMenu`、`MePage` 及部分设置入口仍使用 `节点 / Nodes`、`资料与网关 / Nodes and gateway`、`策略 / Policies`、`公司成员 / Company members` 等内部工程术语，`MePage` 多项设置入口缺少帮助理解用途的一句话副标题。

## 根因

1. **桌面与窄屏设置导航未按视口职责隔离（Issue G）**：
   - **原始设计意图**：`feat-604`（提交 `4068b2cfdd`、`f8e8731935`）重构 `NodesPage`、`AccountPage`、`PoliciesPage` 时，旨在让手机端从底部第 5 个 Tab `/me` 进入各设置子页后能返回上级入口，同时由 `AccountPage`（`/settings/account`）集中承载个人资料编辑、头像裁剪（`feat-804`）与空间/团队资格查看。
   - **缺陷引入原因**：实现时未接入 `useIsMobile()`（`< 768px`）区分桌面与窄屏，直接在桌面端也无条件渲染了 `<Link to="/me">‹ {t("computers.account")}</Link>`（且文案写成了「我的账号 / My account」而非「我 / Me」），而 `CompanyMembersPage` 单独做了 `isMobile` 判断、`ModelsPage` 则漏掉了窄屏返回入口；同时 `/me` 路由缺少桌面视口重定向保护。
   - **修复必须保住的不变量**：
     - 桌面与窄屏均可正常访问并完整操作 `/settings/account`（修改显示名、上传/裁剪/移除头像、查看个人空间与团队状态、跳转电脑管理）；
     - 窄屏（`< 768px`）保留底部 `Me` Tab（`/me`）以及 `/settings/{account,nodes,models,policies,company}` 顶部的返回 `/me` 入口；
     - 桌面视口（`>= 768px`）隐藏所有指向 `/me` 的返回链接，且直接访问或窗口拉宽停留在 `/me` 时自动 `replace` 重定向至 `/settings/account`。
2. **Chrome 配对组件摘要只概括了凭据收益、遗漏了动作能力与隔离模式对比（Issue H）**：
   - **原始设计意图**：`packages/dsh-integration/src/computer/browser.ts` 提供完整受控浏览器自动化（`open/navigate/new_tab/tabs/select_tab/close_tab/snapshot/screenshot/console/network/click/type/upload/copy/paste`），其中 `daily` 模式通过官方 Playwright Extension 在后台标签页操作用户日常 Chrome 并复用已登录会话，`isolated` 模式在独立干净目录启动隔离浏览器、不触碰个人浏览器数据。
   - **缺陷引入原因**：`feat-790` / `9614cc280` 编写 `BrowserPairingSection`（`src/IM/frontend/src/features/settings/nodes/browser-pairing-section.tsx`）时，为压缩字数将摘要简化为「复用已登录状态」，导致用户看不出这是授权助手操作浏览器。
   - **修复必须保住的不变量**：保留 `desktop-strip`、`drawer`、`agent-callout` 三种变体的两步引导配对流程、状态徽标（未配对 / 已配对 / 已验证 / 需重新配对）、Enter 键局部提交隔离及 `/settings/nodes?pair_browser=1` 深链行为不变。
3. **演进期术语局部改造未统一收口到 `UserMenu` / `MePage` / `i18n`（Issue I）**：
   - **原始设计意图**：电脑页主标题在 `feat-604` 中文已改为「电脑」（`computers.title`），Desktop 托盘也使用「电脑与运行设置」，但早期原型遗留的 `MePage`（`bb334d869e`）仍把 `user.id` 当副标题，且 `shell.userMenu.*`、`me.sections.*`、`en.json` `settings.nodes.title` 及 `ModelsPage` 硬编码字符串未同步收口为用户语言。
   - **修复必须保住的不变量**：
     - 路由路径（`/settings/nodes`、`/settings/models`、`/settings/policies`、`/settings/company`、`/settings/account`）与权限门禁（非活跃团队成员隐藏规则入口、非管理员隐藏成员管理入口且策略预设只读）完全不变；
     - `PoliciesPage` 标题与说明如实表达「附件存储用量 + 团队运行/安全策略预设（预设暂未接入运行执行）」，不虚构工具审批开关。

## 本次审查安排

| 审查编组 | 必须回答的问题 | 能力 | 验证方法与已有证据 |
|---|---|---|---|
| Review-1（代码、契约与前端体验联合审查） | 1. 桌面端是否彻底消除误入 `/me` 的返回入口与直达停留，同时完整保留 `AccountPage` 与窄屏 `/me` 闭环导航？<br>2. `BrowserPairingSection` 三种变体与各连接状态的中英文文案是否准确传达「后台操作 Chrome + 复用登录态 vs 干净隔离浏览器」且不破坏配对交互与排版？<br>3. `UserMenu`、`MePage` 及关联设置页是否消除内部 UUID、硬编码词条与黑话，且 `PoliciesPage` 命名/说明与真实页面能力严格一致？<br>4. 归并后的 `docs/specs/im/{web-chat-ux,agents-nodes}.md` 与实现、测试是否一致？ | `change-code-review` + `frontend-experience-review` | Vitest 单元/路由/组件回归测试、`tsc -b` + `vite build`、真实浏览器桌面（1280px）与移动视口（390px）中英文画面及连续导航走查截图 |

## 修复

1. **桌面与移动端个人导航按视口隔离（Issue G）**：
   - 在 `src/IM/frontend/src/features/settings/account/account-page.tsx`、`src/IM/frontend/src/features/settings/nodes/nodes-page.tsx`、`src/IM/frontend/src/features/settings/policies/policies-page.tsx` 与 `src/IM/frontend/src/features/settings/models/models-page.tsx` 接入 `useIsMobile()`（`< 768px`）：仅在窄屏渲染返回 `/me` 的顶部链接并统一文案为 `‹ 我` / `‹ Me`（`t("me.title")`），桌面视口（`>= 768px`）隐藏所有指向 `/me` 的返回入口；
   - 在 `src/IM/frontend/src/features/me/me-page.tsx` 中对桌面视口（`!isMobile`）增加 `<Navigate to="/settings/account" replace />` 自动重定向（同时仅在窄屏启用 `listNodes` 查询），确保直接访问或拉宽窗口停留在 `/me` 时自动落回桌面账号设置页，完整保留 `AccountPage` 的显示名修改、头像裁剪上传与空间/团队状态能力。
2. **「日常 Chrome 浏览器」配对卡片明确传达控制能力与隔离边界（Issue H）**：
   - 更新 `src/IM/frontend/src/features/settings/nodes/browser-pairing-section.tsx`（含 `desktop-strip`、`drawer`、`agent-callout` 三种变体及未配对/已配对/已验证/需重新配对/未装 Chrome 各状态）的中英文文案，清晰说明连接后助手可在后台标签页操作该 Chrome（打开网页、点击、输入、读取页面与截图）并复用已登录网站会话，未连接或无需个人登录态时使用干净隔离浏览器（独立环境，不触碰个人浏览器数据）；
   - 调整 `src/IM/frontend/src/features/settings/nodes/browser-pairing-section.css` 头排与全宽摘要段落结构，避免英文窄抽屉下操作按钮掉行。
3. **消除内部 UUID 与硬编码词条，统一中英文用户向术语与副标题（Issue I）**：
   - `MePage` 身份卡副标题由裸露 `user.id` 改为 `@username`（缺失用户名时不渲染空 `@` 且不回退暴露内部 ID）；
   - 消除 `UserMenu`（`src/IM/frontend/src/app/shell/user-menu.tsx`）、`MePage`、`ModelsPage` 与 `ModelServicesPanel` 中硬编码的 `'模型服务' : 'Model services'`，统一纳入 `src/IM/frontend/src/i18n/{zh,en}.json`；
   - 将残留的 `节点 / Nodes` 与 `资料与网关 / Nodes and gateway` 统一为 `电脑 / Computers`（含窄屏连接摘要副标题与 Agent 空态 `前往电脑 / Open Computers`），模型入口统一为 `AI 模型与 API / AI Models & API`，策略入口按真实页面能力统一为 `用量与团队规则 / Usage & Policies`（明确说明「附件存储用量与团队运行预设」），公司成员入口统一为 `成员管理 / Team members`，并为 `MePage` 各管理行补齐简洁用途副标题；
   - 将上述用户可见导航、术语与日常 Chrome 配对说明契约同步归并至 `docs/specs/im/web-chat-ux.md` 与 `docs/specs/im/agents-nodes.md`。

## 验证

- **TDD 红绿复现与回归测试**：
  - 修复前运行新增测试（`router.test.tsx`、`app-shell.test.tsx`、`me-page.test.tsx`、`web-browser-pairing.test.tsx`、`i18n.test.ts`）共 9 项断言精准失败；
  - 修复后运行全量前端测试套件 `npm --prefix src/IM/frontend run test`：**141 个测试文件、1,362 条用例全部通过**（含 `account-page.test.tsx`、`nodes-page.test.tsx`、`policies-page.test.tsx`、`models-page.test.tsx`、`company-access.test.tsx`、`desktop-client.test.tsx` 等既有回归测试）；
  - 前端类型与构建检查：`cd src/IM/frontend && npx tsc -b && npx vite build` 零错误通过（构建后已清理 `dist/`）。
- **真实浏览器双视口双语交互与视觉自检**：
  - 使用隔离端口 Vite + Playwright Chromium 实测桌面（`1280×840`，中/英）与窄屏移动（`390×844`，中/英）共 15 张画面及连续跳转回路：确认桌面访问 `/me` 即时 `replace` 落到 `/settings/account` 且各设置子页无 `/me` 返回链接；窄屏 `/me` 展示 `@alex` 与完整通俗标题/副标题，点击进入电脑/模型/规则/账号页再点 `‹ 我 / ‹ Me` 均闭环回到 `/me`；Chrome 配对卡在电脑详情抽屉与助手创建页排版工整、能力与隔离边界表达清晰。
- **文档与平台门禁检查**：
  - `./scripts/docs-check` 通过（242 份受管 Markdown 与 74 条必达路由零问题），`git diff --check` 无空白/冲突标记问题。
