# Design Review: feat-821-desktop-seamless-updates

## Round 1

### Metadata

- **reviewer**: Independent Gate 2 Design Reviewer (`change-design-reviewer` + 设计态 `frontend-experience-review`，subagent `61ebd252-4cb1-4784-a52e-692c974b31b0`)
- **target**:
  - `docs/changes/feat-821-desktop-seamless-updates/spec.md`
  - `docs/changes/feat-821-desktop-seamless-updates/design.md`
  - `docs/changes/feat-821-desktop-seamless-updates/prototype.html`（及作者走查截图 `01..06.png`）
  - `docs/changes/feat-821-desktop-seamless-updates/specs/im/desktop-client.md`
  - `docs/changes/feat-821-desktop-seamless-updates/specs/im/agents-nodes.md`
  - `docs/changes/feat-821-desktop-seamless-updates/specs/im/spec.md`
  - `docs/changes/feat-821-desktop-seamless-updates/M1-desktop-seamless-updates/.gitkeep`
- **review_mode**: `full`
- **mode_reason**: Gate 2 首轮独立完整设计审查，合并设计态 `frontend-experience-review` 原型与多视口交互核查。
- **started_at**: `2026-11-28T16:08:36+09:00`
- **completed_at**: `2026-11-28T16:20:30+09:00`
- **duration**: `11m54s`

### Verdict

- **Status**: **Changes Requested**（`Issues Found`）
- **Severity Counts**: `CRITICAL: 3` | `WARNING: 3` | `SUGGESTION (Recommendations): 2`

---

### Coverage 与证据

#### 1. 架构判断、职责归属与跨包边界（`AGENTS.md` / `SPEC.md`）

对照 `AGENTS.md`、`SPEC.md` 及生产组装代码（`apps/desktop`、`apps/node`、`apps/im-server`、`packages/product-contracts`、`src/IM/frontend`）独立评估：
- **架构红线合规**：方案保持 `apps/desktop` 不导入 DSH、`src/IM/frontend` 仅依赖 `@nano/product-contracts`、程序包与桌面安装器直接从官方 GitHub Release 或受信自托管发布源拉取而不经 `apps/im-server` 业务进程中转字节流，不引入第二套 Agent Loop 或内核 HTTP 服务，符合 `SPEC.md` 单向依赖边界。
- **模块职责与既有能力复用判断**：
  - 由 `apps/desktop/src/updater.rs` 独立持有桌面端清单发现、分包静默预部署与按 `im_origin` 隔离的本地 UI 指针，解耦了未绑定/已停止/非本人节点（`unbound` / `managed_stopped` / `foreign_owner`）对在线 `NodeUpdater` 的依赖，避免了为纯聊天桌面用户伪造后台隐藏节点的反模式；
  - 在 `managed_online` 场景下复用 `apps/im-server/src/node-updates.ts` 与 `apps/node/src/update-worker.ts` 的 `<desktop_home>/versions/<sha256>/.ready` 免二次下载能力及 `relay_gated` 任务排空屏障，模块分工合理；
  - `apps/node/src/local-admin.ts#L233` 在 `managed_stopped` 下 `rawState` 为空导致 `version` 退化为 `'source'` 的现状定位准确。
- **核心未闭合风险**：回到真实源码逐点核对后，检出 **3 项阻断级设计缺陷（`R1-C1..C3`）**——① 主聊天面板 `MessagePane` 并未在输入时实时写 `composer-draft-store`，且 `desktopScopedKey` 未包含 `context_epoch`，按当前方案热重载会 100% 丢失当前会话正在输入的草稿；② 现状断言中声称已存在的 `has_unsaved_form` 在全仓并不存在，且将窗口失焦（`!visible_and_focused` / `!document.hasFocus()`）误判为窗口隐藏后台，会导致切窗口复制密钥或配对 Chrome 时前台可见窗口自动刷新冲掉未保存表单，同时开机 `--background` 与托盘右键换新缺少宿主侧 `Bearer` 鉴权通路且启动直切指针存在强杀任务与无回退风险；③ 沿用 `Policy::none()` 无重定向策略会导致官方公网 GitHub Releases（必返 `302` 跳转 `objects.githubusercontent.com`）下载 100% 失败，且 `parseReleaseManifest`、`resolve_active_ui_bundle` 路径与指针同步存在契约断层。

#### 2. 需求覆盖、用户约束与五端对齐矩阵核查

- **五端对齐矩阵（`design.md#L50-L59`）**：5 个标准平台行名、处置方式（`Web` / `Desktop (macOS)` / `Desktop (Windows)` / `Node` 为 `native-sync`；`iOS` 为 `platform-exempt`）符合 `docs/development/change-workflow.md#五端对齐矩阵` 与 `scripts/check_platform_parity.py` 双向校验规则；`./scripts/docs-check` 实测通过。
- **用户约束与澄清结论核对（对照 `spec.md`）**：
  - 默认开启「自动保持最新」、可随时关闭且跨重启持久、零工程黑话（不在前端暴露哈希/内部协议字段）：状态模型与自然语言错误分类设计清晰；
  - 公网 HTTPS 与受信内网自部署一体化发现、纯聊天未绑定独立更新：主体链路清晰，但公网 GitHub Release `302` 重定向、切服并发下载取消与 `desktop-ui-active.json` / `.desktop-active.json` 优先级同步需修正（`R1-C3`）；
  - 保路由、保输入草稿与在途任务安全排空：保路由（`tray.rs` + `index.html` `no-store`）方向可行，但主会话实时草稿落盘、`context_epoch` 作用域、失焦误刷新及本机 `NodeUpdatePanel` 移除后的远端/恢复态承接需补齐（`R1-C1`、`R1-C2`、`R1-W2`）；
  - 外层客户端宿主升级（`.exe` / `.dmg`）：Windows `CrewdenDesktop.iss` 已具备 `CloseApplications=yes` 与 `DesktopGatewayHost.exe prepare-overwrite` 优雅停旧能力（`packaging/desktop/windows/CrewdenDesktop.iss#L10,#L100-L107`），衔接可行；macOS 未公证首次打开提示与多入口安装包就绪态在原型和窄视口中需补齐（`R1-W1`）。
- **一次性部署迁移**：无服务端数据迁移，判断正确。

#### 3. 设计态前端体验与原型走查（`frontend-experience-review`）

独立审阅了 `prototype.html` 源码、作者提供的 `01..06.png` 干净模式截图，并在独立 `/tmp/` 临时目录使用 Playwright Chromium（`2x`）补充实测了 `1280×840`、`1280×720` 与 `420×680` 下 `waiting_for_tasks`、`installer`（macOS / Windows）、`failed` 与 `computers-bound` 状态（临时目录已清理）：
- **成立的设计决定（Pass）**：
  1. **宽屏左下角胶囊视觉锚点与零遮挡**：`01-chat-ready-1280x840.png` 与 `02-chat-just-updated-1280x720.png` 中，`88px` 导航轨微章 + 右侧 `248px` 卡片（`x: 87..335px`）严格收束在左侧会话列表列内，右侧当前会话阅读流、回复引用条与输入框（`x: 356..1280px`）完全留白不抢视线，延续了 Crewden 暖奶油黄与紫色的亲和调性。
  2. **同屏主次操作去重**：`03-user-menu-ready-1280x840.png` 与 `04-computers-unbound-1280x840.png` 验证了展开 `UserMenu` 或进入 `/settings/nodes` 时自动收起导航轨浮层卡片，同一画面仅保留单一主行动点；`/settings/nodes` 顶置「Crewden 桌面端」卡片将客户端自身更新与下方电脑节点绑定/运维解耦，纯聊天用户一眼可懂。
- **需修订的体验与原型缺口（Fail -> 见 `R1-W1`、`R1-W2`）**：
  1. **窄窗口（`380px..767px`）状态断流与 `/me` 入口缺失**：Playwright 实测 `420×680` 下，当处于 `waiting_for_tasks`、`installer` 或 `failed` 时，`#mobile-capsule-slot` 高度为 `0`（完全空白）——用户在窄窗口点击「秒换新」遇到本机任务运行时，顶部条直接消失，既无等待反馈也无「取消本次换新」入口；且 `< 768px` 时 `AppShell` 隐藏 `UserMenu` 改走底栏「我（`/me`）」（`MePage`），方案未在 `MePage` 提供对应的版本与更新控制，造成窄窗口手动入口缺失。
  2. **`UserMenu`、`/settings/nodes` 安装包就绪态与 macOS 未公证打开提示未在原型闭环**：在 `prototype.html` 的 `UserMenu` 或 `/settings/nodes` 中点击「升级客户端 / 下载并升级客户端」后画面无任何进度或打开引导变化；且胶囊的 `.dmg` 指引（`05`）遗漏了 `spec.md#L37` 与 `design.md#L117` 承诺的未公证版本首次打开提示。

#### 4. `delta-spec`、审查安排、Runbook 与 Milestones 核查

- **`delta-spec` 核对**：
  - `specs/im/spec.md`：`Desktop Client` 区域摘要更新准确，Requirement 总数保持 `6` 不变。
  - `specs/im/desktop-client.md`：锚定 canonical 第 2 条 Requirement，完整保留了原有前 3 个 Scenario（登录自启恢复、关窗常驻唤起、手动启停与开关登录自启），并将第 4 个受管更新 Scenario 扩展为自动准备/纯聊天更新、保路由保草稿热切换、外层安装包升级引导 3 个 Scenario，抽象粒度适中，不会误伤合法替代实现（多入口手动检查反馈与跨服/`foreign_owner` 隔离建议补充见 `R1-R1`）。
  - `specs/im/agents-nodes.md`：锚定 `docs/specs/im/agents-nodes.md#L961-L978`，完整保留全部 4 个既有 Scenario 并准确区分 Web 远端手动发起与 Crewden Desktop 本机自动/引导体验。
- **审查安排、Runbook 与 Milestones**：
  - 编组 1 由独立子代理在同一隔离栈合并执行 `change-code-review` + `frontend-experience-review` 符合 `docs/development/frontend-experience.md` 低成本充分验证原则（Agent Context 确无影响）；
  - 但 `--headless-host` 下的 `NoopUiBridge::reload_webview` 为空实现，无法按当前设计完成 Playwright 热重载验证，且 `Runbook for Reviewer` 将启动命令推迟至实施产物并漏列了在途任务排空/取消的实测步骤（见 `R1-W3`）；`M1` 范围表亦需同步补入 `message-pane.tsx`、`me-page.tsx` 与 `notifications.rs` 等真实改动落点。

---

### 历史问题闭环

首轮审查（Round 1），无历史问题。

---

### Issues

#### `R1-C1` [CRITICAL] — `MessagePane` 主聊天输入框未实时写入 `composer-draft-store`，且 `desktopScopedKey` 未绑定 `context_epoch`，导致整页热重载丢失当前会话草稿且会话吊销后存在残留风险

- **具体位置**：
  - 设计与契约：`design.md#L21,#L34,#L113,#L188,#L245,#L307`、`spec.md#L28,#L62-L64`、`specs/im/desktop-client.md#L33-L36`
  - 真实源码：`src/IM/frontend/src/features/chat/components/message-pane.tsx#L322-L358,#L529-L565,#L766-L771,#L793-L796,#L929-L939`、`src/IM/frontend/src/features/chat/components/composer-draft-store.ts#L69-L91,#L148-L156`、`src/IM/frontend/src/desktop/desktop-context.ts#L177-L180`、`src/IM/frontend/src/app/providers.tsx#L54-L71`、`apps/desktop/src/host_server.rs#L1817-L1832`
- **证据与机理**：
  1. **主聊天输入框仅在 SPA 切会话或组件 unmount 时写 store**：`design.md#L113,#L188` 仅计划修改 `composer-draft-store.ts`，假设聊天草稿已实时写入该 store。核查 `message-pane.tsx` 可见（不同于话题侧栏 `thread-column.tsx#L66-L68` 每次输入即调用 `writeComposerSnapshot`），主会话输入框的 `changeDraft`（`#L793-L796`）、`replyToMessage`（`#L766-L771`）与 `handleMentionSelect`（`#L929-L939`）仅更新组件内部 `useState`，只有当切换 `conversation.id`（`#L530-L532`）或 React 卸载组件（`#L556-L560`）时才调用 `writeComposerSnapshot`。当用户停留在当前会话敲了一半文字直接点「秒换新」（或由系统托盘、`reload-assets` 回调触发 `window.location.replace(...)` 整页重载，`tray.rs#L379`）时，浏览器不会执行 React `useEffect` unmount 清理，当前会话的未发文字、`@` 提及与回复引用从未进入 `composer-draft-store`，重载后 100% 丢失。
  2. **`desktopScopedKey` 不含 `context_epoch`**：`design.md#L34` 断言 `desktopScopedKey` 绑定了 `im_origin`、`context_epoch` 与 `user_id`；但真实 `desktopScopedKey`（`desktop-context.ts#L177-L180`）仅返回 `` `${baseKey}::${origin}` ``，不含 `contextEpoch`。当重载首屏 `restoreSession()` 遇到服务端 `401` 吊销会话时（`host_server.rs#L1827,#L1939` 递增 `context_epoch`），`AppProviders`（`providers.tsx#L55-L65`）中的 `previousUserId` 为初始 `null`，不会触发 `forgetComposerUser`，导致被吊销会话的草稿仍残留在同 `imOrigin` 的 `sessionStorage` 中。
- **未修后果**：
  - `spec.md` 核心场景 1（「正在聊的会话与输入框草稿原样保留」）在主聊天窗口直接失效；
  - 凭据失效或异常退登后在同服务下残留上一会话草稿，违反 `docs/specs/im/desktop-client.md#L94` 隔离契约。
- **收口要求**：
  1. 将 `message-pane.tsx` 纳入改动范围：在 Desktop 模式下将当前会话的 `draft`、`draftMentions`、`replyTo` 变更实时（或短节流配合 `pagehide`/`beforeunload` 兜底刷盘）同步至 `composer-draft-store`，确保任意入口触发 `location.replace` 时主会话与群话题草稿均已写入 `sessionStorage`；
  2. 将 `contextEpoch` 显式纳入草稿 `sessionStorage` 存储键（热更新 `reload_webview` 不递增 `context_epoch`，而 `clear_auth_session_for_origin` 与 `apply_server_switch` 均递增 `context_epoch`），并在 `logout` / `useAuthStore.clear` 时兜底清理草稿键。

#### `R1-C2` [CRITICAL] — 后台静默换新误将「窗口失焦」等同于「隐藏在后台」、虚构 `has_unsaved_form` 现状，且启动直切指针与无 WebView 场景下的在线节点换新未安全闭环

- **具体位置**：
  - 设计与契约：`design.md#L42,#L109,#L156,#L184-L185,#L209-L210,#L216`、`spec.md#L19,#L28,#L47,#L79-L80`、`specs/im/desktop-client.md#L30,#L37`
  - 真实源码：`apps/desktop/src/notifications.rs#L27-L30`、`apps/desktop/src/host_server.rs#L720-L748,#L1905`、`apps/desktop/src/tray.rs#L210-L226`、`apps/desktop/src/lib.rs#L141-L143,#L221-L244,#L344,#L362`、`src/IM/frontend/src/app/shell/app-shell.tsx#L51-L67`、`src/IM/frontend/src/features/settings/agents/agent-create-page.tsx#L401`、`src/IM/frontend/src/desktop/desktop-local-computer-card.tsx#L112`
- **证据与机理**：
  1. **`has_unsaved_form` 不存在，且 `!visible_and_focused` / `!document.hasFocus()` 会在窗口仍可见时误触发整页刷新**：
     - `design.md#L42` 声称「`DesktopAttentionState` 已维护 `current_route`、`visible_and_focused` 与 `has_unsaved_form`」，但真实 `WindowAttentionState`（`notifications.rs#L27-L30`）与 `AttentionBody`（`host_server.rs#L721-L724`、`app-shell.tsx#L53-L59`）仅含 `visible_and_focused` 与 `current_route`，全仓不存在 `has_unsaved_form`，设计中也未定义任何表单脏状态采集与上报方案。
     - `tray.rs#L222-L224` 在 `WindowEvent::Focused(false)` 时即将 `visible_and_focused` 设为 `false`，且 `design.md#L216` 规定前端在 `auto_apply_requested && !document.hasFocus()` 时自动触发换新。当主窗口仍打开在屏幕上，用户仅切到浏览器/备忘录复制 API Key、代理地址、`ROLE.md` 约定，或在「这台电脑」点击日常 Chrome 配对引导自动拉起 Chrome 夺走焦点时，`!visible_and_focused` 与 `!document.hasFocus()` 立即为真，导致屏幕上的可见窗口突然自动刷新，直接清空新建/编辑 Agent（`useBlocker` 无法拦截 `location.replace`）、模型服务、本机配置与 Chrome Token 输入框中的未保存内容。
  2. **启动直切指针会触发 `supervise_node` 硬重启强杀任务且无失败回退**：
     - `design.md#L109` 规定「下次启动（在拉起本机节点之前直接切指针）」；但若启动时本机节点已在后台运行（如 Windows `DesktopGatewayHost` 计划任务或存活守护进程正在执行任务），直接改写 `.desktop-active.json` 会使 `supervise_node`（`lib.rs#L221-L226`）检测到 `inspect.body["version"] != bundle.version` 而立即执行 `lifecycle { action: "restart" }`，绕过 `NodeUpdates` 任务排空强行中断任务；且若新版本启动失败，`supervise_node`（`lib.rs#L141-L143,#L232-L243`）仅循环报错重试，**不会回退 `.desktop-active.json`**，违反 `spec.md#L79-L80` 切换失败自动回退保留原可用版本的契约。
  3. **开机 `--background`、托盘隐藏令牌过期及托盘右键点击换新缺少 `Bearer` 鉴权通路**：
     - `design.md#L156,#L210,#L216` 在 `managed_online` 下依赖前端 WebView 携带 `Authorization: Bearer` 调 `/desktop/v1/updater/apply` 再转发 `POST /im/v1/nodes/:id/update`；但开机自启 `--background` 模式（`lib.rs#L362`）根本未创建 WebView，窗口长时间隐藏托盘时前端内存 `accessToken` 也会过期，且用户在系统托盘菜单直接点击 `换新至 vX.Y.Z ✨` 同样发生在 Rust 宿主侧（无前端请求头），导致在线节点的托盘一键换新与后台空闲自动换新断链。
- **未修后果**：
  - 用户切出窗口复制配置信息时主界面突兀刷新并丢失所有未保存配置草稿；
  - 客户端重启时可能强杀运行中的助手任务或在新包异常时卡死在损坏版本无法回退；托盘换新与 `--background` 静默换新在已绑定在线节点下失效。
- **收口要求**：
  1. 在 `WindowAttentionState` 与 `/desktop/v1/attention` 中显式分离 **`window_visible`（仅窗口关闭隐藏至托盘 `w.hide()` 或 `--background` 无窗口时为 `false`）** 与 `window_focused`，并设计明确的 `has_unsaved_form` 登记与上报机制（覆盖 Agent 新建/编辑、本机运行配置与浏览器配对、模型服务、账号资料及首次引导编辑态）：仅在 `!window_visible && !has_unsaved_form` 且本机无运行中任务时才执行后台自动换新；窗口可见但失焦时只展示左下角胶囊，不自动刷新页面。
  2. 当托盘菜单或后台自动换新在无前端 `Bearer` 头下触发 `managed_online` 节点更新/取消时，由 Rust 宿主复用 `refresh_stored_session_serialized(&state, &im_origin)`（`host_server.rs#L1905`）安全换取 `access_token` 调用 `/im/v1/nodes/:id/update(&/cancel)`。
  3. 启动期若检测到当前连接本机节点已在线运行（`managed_online`），不直接覆写 `.desktop-active.json` 触发硬重启，交由 `NodeUpdates` 排空切换；若节点未运行而在启动期推进 `.desktop-active.json` 后首次 `start` 失败，自动回退 `.desktop-active.json` 与 `desktop-ui-active.json` 至原可用版本并记录 `error_code = "switch_rolled_back"`。

#### `R1-C3` [CRITICAL] — `Policy::none()` 无重定向下载策略会导致公网官方 GitHub Releases `302` 下载必败，且跨协议校验、UI 束校验路径与指针/切服同步存在契约断口

- **具体位置**：
  - 设计与契约：`design.md#L30,#L32,#L95,#L117,#L129,#L137,#L145-L147,#L195-L196,#L272`、`spec.md#L19,#L21,#L43-L47,#L85-L88`
  - 真实源码：`apps/desktop/src/host_server.rs#L374-L378,#L675-L684,#L800-L834,#L2416`、`apps/desktop/src/local_node.rs#L571,#L2780`、`apps/node/src/update-worker.ts#L55-L73,#L438-L479`、`packages/product-contracts/src/node-update.ts#L223-L226`、`apps/im-server/src/install.ts#L66-L75`
- **证据与机理**：
  1. **公网官方 GitHub Releases 必返 `302` 重定向，复用无重定向客户端会导致公网下载全灭**：
     - `HostSharedState.http_client`（`host_server.rs#L375`）设置了 `.redirect(reqwest::redirect::Policy::none())`，且 `design.md#L95`（`Updater -->|"2. 无重定向校验下载"| Bundles`）与 `#L272` 将「无重定向」写成了对 GitHub Releases 与自托管源的统一行为。
     - 事实上，`https://github.com/Mrchen116/nano-multiagent/releases/download/<tag>/<asset>` 下载归档或安装包时恒返回 HTTP `302 Found` 跳转至 `https://objects.githubusercontent.com/...`（对比 `apps/node/src/update-worker.ts#L55-L73`：对 `https://` 源使用 `--location --proto =https --proto-redir =https`，仅对明文私网 `http://` 源使用 `--max-redirs 0`）。本地 `NANO_LOOPBACK_RELEASE_ORIGIN` 测试直返 `200 OK` 会掩盖该问题，一旦连接公网官方 IM 将无法下载任何更新。
  2. **`parseReleaseManifest` 仍锁死 `updater_protocol === 1 && data_epoch === 1`**：
     - `design.md#L117,#L137` 声明当 `shell_protocol > CURRENT_DESKTOP_SHELL_PROTOCOL` 或 `updater_protocol` / `data_epoch` 演进时进入 `mode = "installer"`；但 `#L129` 仅放宽 `shell_protocol >= 1`，遗漏了 `packages/product-contracts/src/node-update.ts#L225` 的 `v.updater_protocol !== 1 || v.data_epoch !== 1` 硬拦截（大于 `1` 时 `im-server` 与客户端均返回 `null` / `503`）。
  3. **`resolve_active_ui_bundle` 校验路径笔误，且 Web 远端更新/回退及切服并发下载会导致指针错位**：
     - `design.md#L145` 写明 `resolve_active_ui_bundle` 校验 `ui/index.html`，但真实桌面分包结构为 `ui/frontend/index.html` 与 `ui/trajectory/index.html`（`local_node.rs#L571,#L2780`、`build-desktop-archives.py#L641-L642`），按 `ui/index.html` 校验会永远判定损坏并剔除指针；
     - 因 `desktop-ui-active.json` 优先级高于 `.desktop-active.json`（`#L145`），若用户曾做过纯聊天更新写入 `desktop-ui-active.json`，后续通过 Web 远端更新本机节点或 `update-worker.ts` 失败回退重写 `.desktop-active.json` 并回调 `/desktop/internal/reload-assets`（`update-worker.ts#L456,#L478`）时，未同步更新 `desktop-ui-active.json` 会导致 UI 卡在旧指针版本；
     - 后台下载期间执行 `apply_server_switch`（`host_server.rs#L800`）切服时，未规定取消在途旧服务下载任务与按 `(im_origin, context_epoch)` 校验归属，存在跨服串写风险。
- **未修后果**：
  - 公网生产环境无法完成任何自动预下载与安装包下载；
  - `desktop-ui-active.json` 因路径校验笔误失效，或在远端更新、回退、切服并发下载时发生 UI 与节点版本分裂。
- **收口要求**：
  1. 在 `design.md` 明确 `updater.rs` 下载客户端的分源重定向策略：初始 URL 为 `https://` 时使用自定义 `reqwest::redirect::Policy::custom` 允许有限跳数（如 `<= 10`）且**强制校验每一跳目标仍为 `https://` 且不含用户名密码**（拦截 `https -> http` 降级重定向），并在单测中覆盖 `302 -> https` 放行与 `302 -> http` 拒绝；初始 URL 为受信私网明文 `http://` 时严格 `0` 重定向（测试环境 `NANO_LOOPBACK_RELEASE_ORIGIN` 单独受控）。
  2. 对齐 `node-update.ts#L225` 与 `design.md#L117,#L137`：要么对桌面清单同步允许整数 `updater_protocol >= 1`、`data_epoch >= 1`（保持 `hot_bundle` 与 `update-worker.ts` 严格要求 `=== 1`），要么将 `installer` 触发条件收窄至 `shell_protocol > CURRENT_DESKTOP_SHELL_PROTOCOL`。
  3. 修正 `resolve_active_ui_bundle` 校验路径为 `ui/frontend/index.html`（并确保 `handle_static_or_spa` 切换至 `resolve_active_ui_bundle`）；明确 `/desktop/internal/reload-assets` 将同 owner 的 `.desktop-active.json` 同步回 `desktop-ui-active.json.origins[im_origin]`（若 `NodeUpdates` 结果为 `rolled_back` 则同步置 `switch_rolled_back`）；明确 `apply_server_switch` 立即取消旧 `im_origin` 在途任务并触发新服务检查。

---

#### `R1-W1` [WARNING] — 窄窗口（`< 768px`）状态断流、`/me` 个人页入口遗漏，且原型未闭环多入口安装包就绪态与 macOS 未公证打开提示

- **具体位置**：
  - 设计与原型：`design.md#L117,#L218-L220,#L251-L254,#L299,#L307`、`prototype.html#L890-L1072,#L1228-L1231`、`spec.md#L34,#L37,#L67-L76,#L85-L88`
  - 真实源码：`apps/desktop/src/tray.rs#L164`、`src/IM/frontend/src/app/shell/app-shell.tsx#L80,#L106-L150`、`src/IM/frontend/src/features/me/me-page.tsx`、`apps/im-server/src/install.ts#L118`
- **证据与机理**：
  1. **窄视口（`380px..767px`）顶部条缺失 `waiting_for_tasks` 与 `installer` 状态**：Crewden Desktop 最小窗口尺寸为 `380×560`（`tray.rs#L164`），宽度 `< 768px` 时隐藏左侧 `88px` 导航轨与 `UserMenu`（`app-shell.tsx#L80`）。`design.md#L251,#L307` 将 `420×680` 列为 `must-match` 视口，但 Playwright 实测 `prototype.html#L981-L1002`（`renderMobilePillHtml`）仅渲染 `ready_to_switch` 与 `justSwitched`：当窄窗口下点击「秒换新」进入 `waiting_for_tasks`，或遇到 `installer` 跨壳升级时，顶部提示条立即消失为空，用户既看不到「等待任务收尾」也无法点击「取消本次换新」。
  2. **窄视口底栏「我（`/me`）」页面缺少更新状态盒**：`< 768px` 时底栏「我」进入 `MePage`（`me-page.tsx`，桌面 `UserMenu` 的窄屏对应页），当前方案未将 `MePage` 纳入改动，窄窗口用户打开个人入口看不到桌面端版本、「检查更新」与「自动保持最新」开关。
  3. **原型遗漏 `UserMenu` / `/settings/nodes` 的安装包准备完成态及 macOS 未公证首次打开提示**：`design.md#L254` 将左下角胶囊、`UserMenu` 与 `/settings/nodes` 三处的安装包下载进度与平台引导均列为 `must-match`，且 `spec.md#L37`、`design.md#L117` 要求对 `macos_distribution !== "developer-id-notarized"`（默认分发形态，`install.ts#L118`）附带温和首次打开提示；但 `prototype.html` 中在 `UserMenu`（`#L1012-L1014`）或 `/settings/nodes`（`#L1063-L1066`）点击升级按钮后界面无任何变化，且 `.dmg` 引导卡（`#L965-L967` 及截图 `05`）也未展示未公证打开提示。
- **未修后果**：
  - 窄窗口下失去在途任务取消控制、客户端大版本升级提示与个人页手动更新入口；实施与验收在 `UserMenu`、`/settings/nodes` 安装包引导及未公证 macOS 提示上缺少一致参照。
- **收口要求**：
  1. 补齐 `< 768px` 顶部流式条在 `waiting_for_tasks`（含取消按钮）与 `installer`（含下载/打开动作）下的设计及 `prototype.html` 呈现，并在桌面模式下同步为窄屏 `MePage`（`/me`）挂载紧凑更新状态盒；
  2. 在 `prototype.html` 补齐 `UserMenu` 与 `/settings/nodes` 更新卡对 `installer` 下载/就绪态的交互展示，以及 `macos_distribution !== "developer-id-notarized"` 的温和首次打开说明。

#### `R1-W2` [WARNING] — 直接移除 `DesktopLocalComputerCard` 内 `NodeUpdatePanel` 后，未承接 Web 远端发起的本机更新与 `recovery_required` 恢复态

- **具体位置**：
  - 设计文档：`design.md#L220`
  - 真实源码：`src/IM/frontend/src/features/settings/nodes/nodes-page.tsx#L38-L43,#L141`、`src/IM/frontend/src/desktop/desktop-local-computer-card.tsx#L205-L209,#L358-L366`、`src/IM/frontend/src/features/settings/nodes/node-update-panel.tsx#L18-L20,#L52-L73`、`apps/im-server/src/node-updates.ts#L57,#L197`
- **证据与机理**：
  - `nodes-page.tsx#L38-L43` 会将已绑定的本机 `localNodeId` 从普通卡片列表 `visibleNodes` 中过滤掉，仅由 `DesktopLocalComputerCard` 承载。
  - `design.md#L220` 移除 `DesktopLocalComputerCard` 内的 `NodeUpdatePanel`，但未说明当 `matchedNode?.update` 存在由 **Web 远端管理页发起的在途 `NodeUpdateOperation`**（`waiting` / `switching` 等）或处于 **`recovery_required`（`relay_gated == true`，此时中继门禁阻塞消息且 `DesktopLocalComputerCard#L209` 禁用改名与新建助手）** 时，顶部的 `DesktopClientUpdateCard` / `useDesktopUpdater` 如何感知并呈现取消或恢复操作。
- **未修后果**：
  - 若用户在其他设备网页端对这台电脑发起了更新，或此前更新中断进入 `recovery_required`，在 Crewden Desktop 打开 `/settings/nodes` 时既看不到 `visibleNodes` 中的卡片，顶部桌面端更新卡又可能显示「已是最新」，导致用户无法取消等待中的更新，也无法解除 `recovery_required` 门禁。
- **收口要求**：
  - 在 `design.md` 明确：当本机节点归属当前登录用户（`managed_online` / `managed_stopped`）时，`useDesktopUpdater` / `DesktopClientUpdateCard` 融合 `matchedNode?.update` 状态——存在远端触发的活跃 `NodeUpdateOperation` 时统一映射展示对应阶段与取消按钮；处于 `recovery_required` 时以自然语言提示更新未完成并提供一键重启恢复/重试入口。

#### `R1-W3` [WARNING] — `--headless-host` 模式下 `NoopUiBridge::reload_webview` 为空实现导致真栈自动重载无法触发，且 Reviewer Runbook 缺少可直接执行的命令与任务排空步骤

- **具体位置**：
  - 设计文档：`design.md#L192,#L196,#L272,#L293-L301,#L307`
  - 真实源码与规范：`apps/desktop/src/lib.rs#L299-L321`、`apps/desktop/src/notifications.rs#L45-L98`、`docs/development/frontend-experience.md#L21-L27`
- **证据与机理**：
  1. **`--headless-host` 无法向 Playwright 外部浏览器推送 `reload_webview`**：`design.md#L272,#L295` 要求使用 `crewden-desktop --headless-host` 配合 Playwright Chromium 验证热切换保路由与保草稿；但 `--headless-host` 使用 `NoopUiBridge`（`lib.rs#L305`、`notifications.rs#L97`），其 `reload_webview` 是空函数 `{}`。尤其在 `managed_online` 节点重连后回调 `/desktop/internal/reload-assets`（`design.md#L195-L196`）的路径上，若前端 `use-desktop-updater.ts` 仅被动等待宿主 `win.eval("window.location.replace(...)")`，Playwright 页面将永远不会刷新。
  2. **Runbook 启动命令后置且缺少在途任务排空实测步骤**：`design.md#L295` 将具体启动参数推迟到阶段 3 才生成的 `verification.md`，未按 `docs/development/frontend-experience.md#L23` 直接给出可独立执行的隔离命令模板（含 `--isolated-root`、`--im-origin`、`NANO_LOOPBACK_RELEASE_ORIGIN`）；且 `#L299` 未覆盖 `M1` `[reviewer]` #2 必验的「已绑定在线节点存在在途任务时等待收尾与切换前取消」旅程。
- **未修后果**：
  - 实施自检与独立审查在 `--headless-host` + Playwright 环境下无法复现完整的在线节点热切换重载闭环；独立审查员无法仅凭 `design.md` Runbook 直接拉起隔离验证现场。
- **收口要求**：
  1. 在 `DesktopUpdaterSnapshot` 中暴露生效 UI 束标识或重载序号（如 `active_bundle_sha256` / `reload_generation`），使前端 `use-desktop-updater.ts` 在轮询发现本地激活版本已推进而当前页面尚未刷新时，主动以保路由缓存穿透 URL 执行 `window.location.replace(...)`（同时兼容 Tauri WebView 与 `--headless-host` 外部浏览器）；
  2. 在 `design.md` `Runbook for Reviewer` 中直接写明完整的隔离起栈/停栈命令模板，并补入已绑定节点在途任务等待排空与取消换新的验证步骤。

---

### Recommendations

- **`R1-R1` [SUGGESTION] — 在 `specs/im/desktop-client.md` 中补齐默认开启态下的手动检查即时反馈及按服务/`foreign_owner` 隔离条款**：
  `spec.md#L73-L75` 与 `design.md#L32-L33,#L307` 均明确要求：即使「自动保持最新」处于开启态，用户在个人菜单、托盘或「电脑」页手动点击「检查更新」时仍就地反馈「已是最新版本」或「当前服务暂未提供桌面更新包」，且切换 `im_origin` 后独立对齐目标服务版本、纯聊天用户更新不触碰本机 `foreign_owner` 节点。当前 `specs/im/desktop-client.md#L31` 仅在「关闭自动保持最新后」提及手动检查，建议把上述两条不变量精炼补入 delta-spec，确保归档后长青契约完整。
- **`R1-R2` [SUGGESTION] — 为 `<desktop_home>/cache/` 与 `cache/installers/` 增加保守的历史归档清理策略**：
  默认开启「自动保持最新」后，每次版本迭代都会在后台下载分包归档，跨壳升级还会写入上百 MB 的 `.dmg` / `.exe`。建议在 `updater.rs` 完成切换确认或新种子推进后，顺带清理未被 `seed-current.json`、`desktop-ui-active.json` 及任一连接 `.desktop-active.json` / `.desktop-switch.json` 引用的陈旧缓存归档与旧安装包文件，避免长期运行膨胀用户磁盘占用。

---

### Author Resolutions (Round 1)

- **`R1-C1` [Fixed]**：将 `src/IM/frontend/src/features/chat/components/message-pane.tsx` 正式纳入修改范围——Desktop 模式下在 `draft` / `draftMentions` / `replyTo` 变更时实时（并配合 `pagehide`/`beforeunload` 兜底刷盘）同步写入 `composer-draft-store`，并将 `sessionStorage` 键显式绑定为 `crewden:composer-drafts::${imOrigin}::${contextEpoch}::${userId}`，确保不切会话直接整页热重载 100% 保留当前草稿，而在退登、`401` 吊销（递增 `context_epoch`）或切服时立即隔离并清理（见 `design.md` §现状分析、§关键决策 #3、§接口与数据流 #3、`M1` `[worker]` #2）。
- **`R1-C2` [Fixed]**：修正现状描述并在 `WindowAttentionState` 与 `/desktop/v1/attention` 中显式拆分 `window_visible`（仅 `w.hide()` 关窗入托盘或 `--background` 无窗口时为 `false`，窗口可见失焦时仍为 `true`）与前端 `useDesktopUnsavedForm` 上报的 `has_unsaved_form`；明确系统托盘菜单、`--background` 常驻与后台自动换新在无前端请求头时统一通过 `refresh_stored_session_serialized` 安全换取 `access_token` 协同在线节点更新/取消；启动期检测到在线节点不直改 `.desktop-active.json`，离线推进指针后若首次 `start` 失败则自动回退双指针至 `previous_bundle` 并标记 `switch_rolled_back`（见 `design.md` §关键决策 #2、§接口与数据流 #2/#3、`specs/im/desktop-client.md`）。
- **`R1-C3` [Fixed]**：在 `updater.rs` 采用分源下载客户端——`https://` 源允许 `<= 10` 跳纯 `https://` 重定向（兼容官方 GitHub Releases `302 -> objects.githubusercontent.com` 并拦截 `https -> http` 降级），受信私网明文 `http://` 源保持 `Policy::none()` 零重定向；`node-update.ts` 对桌面清单同步允许正整数 `shell_protocol >= 1`、`updater_protocol >= 1`、`data_epoch >= 1`；修正 `resolve_active_ui_bundle` 校验路径为 `ui/frontend/index.html`，补齐 `/desktop/internal/reload-assets` 同 owner `.desktop-active.json -> desktop-ui-active.json` 反向同步与 `apply_server_switch` 取消旧 `(im_origin, context_epoch)` 在途下载（见 `design.md` §关键决策 #1/#4、§接口与数据流 #1/#2）。
- **`R1-W1` [Fixed]**：在 `design.md` 与 `prototype.html` 补齐窄窗口（`< 768px`）顶部流式条对 `waiting_for_tasks`（含取消按钮）、`installer`、`failed` 全状态的呈现，将窄屏 `MePage`（`/me`）纳入紧凑更新状态盒挂载范围，并闭环了 `UserMenu`/`MePage`/`/settings/nodes` 安装包就绪态交互及 `macos_distribution !== "developer-id-notarized"` 的温和首次打开说明。
- **`R1-W2` [Fixed]**：明确当本机节点归属当前登录用户时，`useDesktopUpdater` 与 `DesktopClientUpdateCard` 融合 `matchedNode?.update`，完整承接其他设备 Web 远端发起的在途 `NodeUpdateOperation`（含进度与取消）及 `recovery_required` 一键重启本机运行环境恢复入口（见 `design.md` §接口与数据流 #3、`M1` `[reviewer]` #3）。
- **`R1-W3` [Fixed]**：在 `DesktopUpdaterSnapshot` 增加 `active_ui_sha256` 与 `reload_generation`，使前端在 `--headless-host`（`NoopUiBridge`）下检测到版本世代推进后主动执行保路由重载；并在 `Runbook for Reviewer` 中直接给出可独立执行的隔离起栈/停栈命令及在线节点在途任务排空/取消验证旅程（见 `design.md` §接口与数据流 #2/#3、§Runbook for Reviewer）。
- **`R1-R1` [Accepted & Fixed]**：已在 `specs/im/desktop-client.md` 补充开启/关闭自动更新下一致的手动检查即时反馈，以及切换服务独立隔离与 `foreign_owner` 不越权改写条款。
- **`R1-R2` [Accepted & Fixed]**：已在 `design.md` §接口与数据流 #2 与 `M1` `[worker]` #1 纳入热切换完成或新种子推进后的 `cache/` 与 `cache/installers/` 保守清理策略。


---

## Round 2

### Metadata

- **reviewer**: Independent Gate 2 Design Reviewer (`change-design-reviewer` + 设计态 `frontend-experience-review`，subagent `61ebd252-4cb1-4784-a52e-692c974b31b0`)
- **target**:
  - `docs/changes/feat-821-desktop-seamless-updates/design.md`（Round 1 修订版）
  - `docs/changes/feat-821-desktop-seamless-updates/prototype.html`（Round 1 修订版，及更新/新增走查截图 `05-installer-dmg-guide-1280x840.png`、`07-narrow-waiting-420x680.png`、`08-narrow-me-420x680.png`）
  - `docs/changes/feat-821-desktop-seamless-updates/specs/im/desktop-client.md`（Round 1 修订版）
  - `docs/changes/feat-821-desktop-seamless-updates/design-review.md`（`Author Resolutions (Round 1)`）
- **review_mode**: `delta`
- **mode_reason**: `spec.md` 用户目标、跨包依赖红线、`specs/im/{spec,agents-nodes}.md` 与单 Milestone 切分未变；本轮变更聚焦闭合 Round 1 检出的 `R1-C1..C3`、`R1-W1..W3` 及 `R1-R1..R2`，涉及契约层协议号校验、Rust 宿主状态机与鉴权/回退链路、前端实时草稿作用域与窄视口多入口原型的有界设计修订，故采用 `delta` 模式复核改动及波及面。
- **retained_from**: `Round 1`（`spec.md` 需求与澄清边界、`SPEC.md` 跨包单向依赖边界、五端对齐矩阵结构、`specs/im/spec.md` 与 `specs/im/agents-nodes.md` delta-spec、宽屏左下角胶囊构图及同屏主次操作去重结论未受本轮局部修订破坏，沿用 Round 1 证据）
- **started_at**: `2026-11-28T16:31:00+09:00`
- **completed_at**: `2026-11-28T16:38:00+09:00`
- **duration**: `7m00s`

### Verdict

- **Status**: **Approved**
- **Severity Counts**: `CRITICAL: 0` | `WARNING: 0` | `SUGGESTION (Recommendations): 1`

---

### Coverage 与证据

1. **有界设计变化与跨层波及面复核（对照真实源码）**：
   - **草稿保态与跨用户/跨服务隔离（`MessagePane` + `composer-draft-store.ts`）**：`design.md#L22,#L35,#L120-L122,#L218-L220,#L317` 已将 `src/IM/frontend/src/features/chat/components/message-pane.tsx` 正式纳入修改范围，在 Desktop 模式下对 `draft`、`draftMentions`、`replyTo` 变更实时写入 store 并配合 `pagehide`/`beforeunload` 兜底刷盘；`sessionStorage` 键绑定 `crewden:composer-drafts::${imOrigin}::${contextEpoch}::${userId}`，与 `desktop-context.ts` 的 `context_epoch`（退登、`401` 吊销与切服递增）严格对齐，闭合了不切会话直接 `location.replace` 的草稿保留与退出清理链路。
   - **后台空闲判定、宿主无头鉴权与冷启动回退（`notifications.rs` + `host_server.rs` + `local_node.rs` + `updater.rs`）**：对照 `apps/desktop/src/host_server.rs#L721-L748,#L1905-L1956` 核实，`WindowAttentionState` 显式拆分 `window_visible: bool`（仅 `w.hide()` 关窗入托盘或 `--background` 无窗口时为 `false`，窗口打开失焦仍为 `true`）与前端 `useDesktopUnsavedForm` 上报的 `has_unsaved_form: bool`，阻断了切窗口复制密钥/配对浏览器时的可见窗口误刷新；托盘菜单、`--background` 常驻与后台自动换新在缺少前端 `Bearer` 头时统一复用 `refresh_stored_session_serialized`（受 `state.refresh_lock` 串行保护，避免 JTI 重放吊销）换取有效 `access_token`；启动期遇到已运行 `managed_online` 节点不直改 `.desktop-active.json`，离线推进指针前记录 `previous_bundle` 并在首次 `start` 失败时双指针回退、标记 `rollback_blocked`（`switch_rolled_back`）。
   - **分源下载重定向安全、契约演进与双指针一致性（`node-update.ts` + `updater.rs` + `host_server.rs`）**：`https://` 下载专用客户端允许 `<= 10` 跳纯 `https://` 且无内嵌凭据的重定向（兼容 GitHub Releases `302 -> https://objects.githubusercontent.com/...` 并拦截 `https -> http` 降级），受信私网明文 `http://` 源保持 `Policy::none()` 零重定向，且全部归档均经流式 SHA-256 核验后原子落盘；`parseReleaseManifest` 对桌面清单放宽为正整数 `shell_protocol >= 1`、`updater_protocol >= 1`、`data_epoch >= 1`（`hot_bundle` 与 `apps/node/src/release.ts` / `update-worker.ts` 保持 `=== 1` 热包边界，跨代清单走 `installer` 模式，互不冲突）；`verify_ready_ui_version_root` 已对齐真实产物路径 `<root>/ui/frontend/index.html`，并补齐 `/desktop/internal/reload-assets` 同 owner `.desktop-active.json -> desktop-ui-active.json` 反向同步与 `apply_server_switch` 取消旧 `(im_origin, context_epoch)` 在途下载。
   - **本机远端更新/恢复态融合与 `--headless-host` 重载闭环**：`useDesktopUpdater` 与 `DesktopClientUpdateCard` 在本机同 owner 节点下融合 `matchedNode?.update` 承接远端发起的 `NodeUpdateOperation` 及 `recovery_required` 一键重启本机运行环境恢复入口；`DesktopUpdaterSnapshot` 新增 `active_ui_sha256` 与 `reload_generation`，使 `--headless-host`（`NoopUiBridge`）与 Tauri WebView 均能可靠完成保路由缓存穿透重载。
2. **设计态前端体验与原型复验（`frontend-experience-review`）**：
   - 审阅更新后的 `prototype.html` 源码、作者截图 `05-installer-dmg-guide-1280x840.png`、`07-narrow-waiting-420x680.png`、`08-narrow-me-420x680.png`，并在独立 `/tmp/` 临时目录使用 Playwright Chromium（`2x`）交互复测 `420×680`（`waiting_for_tasks`、`installer` 下载与就绪、`failed`、`/me` 个人页）及 `1280×840`（`UserMenu` 与 `/settings/nodes` 点击下载并进入安装包引导态），临时目录已清理：
     - `05-installer-dmg-guide-1280x840.png`：左侧 `248px` 胶囊卡片内清晰展示两步 `.dmg` 拖入 `Applications` 指引及未公证版本「系统设置 → 隐私与安全性 → 仍要打开」温和说明，不侵入右侧会话阅读流与输入框；
     - `07-narrow-waiting-420x680.png` 与窄屏全状态实测：`420×680` 下顶部流式条完整覆盖 `ready_to_switch`、`waiting_for_tasks`（含直接可达的「取消换新」按钮）、`installer` 与 `failed`，首条消息与底部回复条/输入框无遮挡；
     - `08-narrow-me-420x680.png`：窄屏 `/me`（对应真实源码 `src/IM/frontend/src/features/me/me-page.tsx`）挂载紧凑桌面端更新状态盒，包含版本号、主操作按钮、平台升级说明与「自动保持最新」开关，进入 `/me` 时顶部流式条自动收起不叠床架屋；全流程点击切换 `0` `pageerror`。
   - `./scripts/docs-check` 复跑通过（`248 maintained Markdown sources, 74 required routes`）。

---

### 历史问题闭环

| 原 Issue ID | Author Resolution | Round 2 复核证据 | 状态 |
|---|---|---|---|
| `R1-C1` | 纳入 `message-pane.tsx` 实时 + `pagehide`/`beforeunload` 写入 `composer-draft-store`，`sessionStorage` 键绑定 `(imOrigin, contextEpoch, userId)` 并在退登/`401`/切服清理 | 核对 `design.md#L22,#L35,#L120-L122,#L218-L220,#L317` 与 `specs/im/desktop-client.md#L36`，主会话与话题未发文字、`@` 提及、回复引用实时落盘与跨用户/跨服隔离链路完整闭合 | `closed` |
| `R1-C2` | 拆分 `window_visible` 与 `has_unsaved_form`；无头/托盘换新经 `refresh_stored_session_serialized` 取 token；启动遇在线节点不直写指针，冷启动失败双指针回退至 `previous_bundle` | 核对 `design.md#L19,#L43,#L109,#L113-L118,#L170-L171,#L190-L192,#L215-L217`、`specs/im/desktop-client.md#L30` 及 `apps/desktop/src/host_server.rs#L1905` 真实签名，失焦保护、宿主鉴权与回退机制自洽 | `closed` |
| `R1-C3` | `https://` 允许 `<= 10` 跳纯 `https://` 重定向、私网 `http://` 零重定向；`node-update.ts` 桌面清单放宽协议号 `>= 1`；修正 `ui/frontend/index.html` 校验路径；补齐 `reload-assets` 反向同步与切服取消 | 核对 `design.md#L12,#L18,#L30-L33,#L106-L110,#L125,#L136-L160`，与 GitHub Releases `302` 行为、`local_node.rs` 真实目录布局及 `update-worker.ts` 热包校验边界完全一致 | `closed` |
| `R1-W1` | 补齐 `< 768px` 顶部流式条全状态、窄屏 `/me`（`MePage`）更新盒、`UserMenu`/`MePage`/`/settings/nodes` 安装包就绪态交互与 macOS 未公证打开说明 | 核对 `design.md#L23,#L128,#L223-L224,#L237-L270`、`prototype.html#L953-L1185`、截图 `05`/`07`/`08` 及 Playwright 多状态点击实测（`0` `pageerror`），视觉与交互均已闭环 | `closed` |
| `R1-W2` | 同 owner 本机节点下 `useDesktopUpdater` 与 `DesktopClientUpdateCard` 融合 `matchedNode?.update`，承接远端在途更新与 `recovery_required` 一键恢复 | 核对 `design.md#L222,#L225,#L258,#L317`，隐藏本机 `NodeUpdatePanel` 后远端操作进度/取消与恢复门禁不再丢失入口 | `closed` |
| `R1-W3` | `DesktopUpdaterSnapshot` 增加 `active_ui_sha256` 与 `reload_generation` 驱动前端主动重载；补全 `Runbook for Reviewer` 命令与旅程 A..D（含在途任务等待与取消） | 核对 `design.md#L160,#L167,#L198,#L222,#L296-L311`，`--headless-host` 重载闭环与必验旅程已完整落地（Runbook 命令行细节校准见 `R2-R1`） | `closed` |
| `R1-R1` | 在 `specs/im/desktop-client.md` 补入开启/关闭态一致的手动检查反馈及按服务/`foreign_owner` 隔离条款 | 核对 `specs/im/desktop-client.md#L31`，长青契约表述准确且无过拟合 | `closed` |
| `R1-R2` | 在 `updater.rs` 热切换确认或种子推进后保守清理无引用的 `cache/` 与 `cache/installers/` 归档 | 核对 `design.md#L161,#L317`，保留当前激活、回退及待切换归档引用，清理边界安全 | `closed` |

---

### Issues

无（`0 CRITICAL / 0 WARNING`）。

---

### Recommendations

- **`R2-R1` [SUGGESTION] — 实施与验收执行前校准 `Runbook for Reviewer`（`design.md#L300-L301`）中的真实 CLI 入口、静态包承载方式与探活路径**：
  当前 `design.md#L300-L301` 示例命令与仓库真实入口存在几处命令级出入（不影响架构设计与 `M1` 实现范围，建议在实施验证脚本及 `verification.md` 中直接对齐，或在顺手修订时同步更新）：
  1. `apps/im-server` 构建产物入口为 `node apps/im-server/lib/main.js --port "$IM_PORT"`（`apps/im-server/package.json#L9`、`src/main.ts#L60`，而非 `dist/cli.js` 与 `PORT=`），发布清单目录环境变量为 `IM_NODE_RELEASE_DIR="$E2E_ROOT/releases"`（`apps/im-server/src/server.ts#L198`，而非 `IM_INSTALL_DIR`）；
  2. `apps/im-server` 按架构红线仅注册 `/install/manifest*.json` 元数据路由、不托管 `/releases/*` 二进制字节流（`apps/im-server/src/install.ts#L136`），隔离栈验证时应为 `$E2E_ROOT/releases` 单独起回环静态 HTTP 服务（如 `python3 -m http.server "$RELEASE_PORT" --bind 127.0.0.1 --directory "$E2E_ROOT/releases"`），并将 `IM_RELEASE_BASE_URL="http://127.0.0.1:$RELEASE_PORT/"` 与 `NANO_LOOPBACK_RELEASE_ORIGIN="http://127.0.0.1:$RELEASE_PORT"` 指向该端口，切勿在 `im-server` 新增分包字节流路由；
  3. `--isolated-root "$E2E_ROOT/desktop-home"` 下宿主状态文件实际路径为 `$E2E_ROOT/desktop-home/desktop/host-state.json`（`apps/desktop/src/config.rs#L330,#L382`），且 `/desktop/v1/updater` 受 Capability Cookie 保护（裸 `curl` 返回 `403`），命令行健康检查可读取同文件中的 `reload_token` 请求 `-H "X-Crewden-Reload-Token: $RELOAD_TOKEN" "http://127.0.0.1:$DESKTOP_PORT/desktop/internal/status"`。
