# feat-790: Review

## 范围与版本

- 本次问题与需求/设计位置：[`spec.md`](spec.md)、[`design.md`](design.md)、[`design-review.md`](design-review.md)、[`prototype.html`](prototype.html)、[`specs/im/desktop-client.md`](specs/im/desktop-client.md)、[`specs/im/agents-nodes.md`](specs/im/agents-nodes.md)、[`specs/im/agent-work.md`](specs/im/agent-work.md)、[`specs/gateway/service-lifecycle.md`](specs/gateway/service-lifecycle.md)、[`M1/verification.md`](M1/verification.md)、[`M2/verification.md`](M2/verification.md)
- 实际 `executed_base` / `validated_at`：`db7167c9d13a5e09fc23224359442a49582a8025` (`origin/develop`) → Round 1 `2d7606a7670219e2279a36166bd45843d409c7ce` → Round 2 `810ff89c872ffb4a64b1768f58915e760b24274d` → Round 3 `abb2d3ff618b5da21eab128f21605e594eb8f519`
- 最终 `effective_base` / `effective_through` 与保留依据：同步最新 `origin/develop`（`73f20d6ea43e6c9d3dcc422a2036fec0f627afeb`，期间合入 `#550` `feat-787` DSH `0.2.2-rc.5` 升级、`#553` 身份头像一致性、`#554` `bugfix-792` worker Work 记录修复与 `#555` `feat-791` 插件/工具权限统一模型）并完成全量构建、类型检查、契约测试、前端与 Rust 宿主测试复验后保持全部独立审查结论有效（`retained`）。

## 审查结果

| 问题 / 要求 | 能力、执行者与模式 | 判断 | 决定性证据 / 限制 |
|---|---|---|---|
| 跨包架构红线、Tauri v2 常驻回环门卫与 JTI 串行轮换、多账号 `owner_id` 隔离、`feat-781` 并存与接管、拆分 `runtime`/`app` 归档热更新、本机 IPC 轨迹与附件鉴权、`single_thread` PA 工作区打开、4 类 Worker 配置及最终 4 份 delta-specs 对齐 | `change-code-review`，独立审查子代理（`c6441360-a915-467c-876e-5420bfe78130`），`full`（`db7167c9d..2d7606a76`）+ Round 2 `closure` / `patch`（`2d7606a76..810ff89c8`）+ Round 3 `closure` / `patch` / `corrected-delta`（`810ff89c8..abb2d3ff6`） | `pass` | 逐行审查 `apps/desktop`、`apps/node`、`apps/im-server`、`packages/product-contracts`、`src/IM/frontend`、`packaging/desktop` 与 `scripts/*`；复跑 `test_runtime_dependency_contract.py`（40/40 通过，所有新增测试文件 `<400` 行）、`./scripts/docs-check`、`cargo test` 与 Vitest 目标套件。Round 1 四项问题（`CR-1`–`CR-4`）及 Round 2 两项补丁问题（`R2-1`、`R2-2`）在 `abb2d3ff6` 全部独立验证关闭；4 份 delta-specs 最终核对为 `aligned`。 |
| **Q1** Web 双入口连接引导（`1280` & `390` 及 `/settings/nodes` `456px` 右抽屉）、**Q2** Desktop 登录切服与绑机/接管/`foreign_owner` 保护、**Q3** `/settings/nodes`「这台电脑」渐进披露、真实工具卡本地路径动作、品牌极简双色图标与全透明圆角悬浮通知 | `frontend-experience-review`，独立审查子代理（`191de864-929e-421c-be53-64183117fe77`），实施模式（Round 1 `2d7606a76` 画面与代码审查 + Round 2 `810ff89c8` 刷新实拍与补丁关闭核验） | `pass` | 目视核验 `M1/evidence/` 与 `M2/evidence/` 全套桌面/窄屏实拍及 `prototype.html` `must-match` 对照：`Q1` 确认 `390px` 初始/唤起/未发布降级态完整入画且 `456px` 抽屉通过 `@container (max-width: 620px)` 单列排布无挤压；`Q2` 确认切服条、绑机、接管与异账号保护语义自明；`Q3` 确认真实 `NativeToolDetail` 展开态展示 `打开文件` / `在 Finder 中显示`、中文校验错误保草稿、运行中任务二次确认条、`CrewdenMark` 双色图标及 `22px` 全透明圆角悬浮通知横幅全部闭合（`Q1`/`Q2`/`Q3` 均为 `pass`）。 |
| **J1** 零命令行首装绑机与已有节点无损接管、**J2** 登录静默自启/关窗常驻通知唤醒/崩溃自愈/受管热更新与回滚、**J3** `>16 MiB` 本机轨迹直读/工作区安全打开/「这台电脑」图形化配置与在途任务保护 | `product-journey-review`，独立审查子代理（`c3ca0565-42e1-4261-a145-2cf9bb6763e6`），实施模式（Round 1 `2d7606a76` 真栈证据与代码链路核查 + Round 2 `810ff89c8` 隔离实测回执复审 + Round 3 `abb2d3ff6` 收口确认） | `pass` | 核实干净无 Node/WSL 的 Windows 10 LTSC（自动补装 WebView2 `158.0.4370.33`）与 Windows 11 Hyper-V VM（含两次真实 `shutdown.exe /r` 重启、`feat-781` 并存接管、`0 B` runtime 复用升级与 `1.0.2-bad` 回滚）及 macOS `arm64` `Crewden.app`（真实大模型问答、`~19 MB` 本机轨迹 `4.1 ms` 直读、`work.crewden.desktop` 归属与浮窗弹出、`crewden-desktop://open?route=...` 唤醒路由及在途 DSH 任务重启拦截）全链路闭环（`J1`/`J2`/`J3` 均为 `pass`）。限制：Windows WinRT 协议 Toast 的桌面交互点击未在 `2d7606a76` 后重跑 Hyper-V GUI 点击，由 `x86_64-pc-windows-gnu` API 类型检查、`parse_deep_link_route` 单测、macOS 同源深链实测与 PR `desktop-candidate.yml` 构建冒烟联合覆盖。 |

## Findings 与关闭

- **CR-1**（`apps/desktop/src/host_server.rs`、`apps/node/src/local-bridge.ts`）：本机原生轨迹 `session/attachment` 读取未查 DSH `trajectory/attachment-source` 来源表，导致受保护聊天来源图片或缺失来源附件绕过中心会话鉴权。
  - 严重度 / 证据状态：`blocking` / `CONFIRMED`。
  - Resolution（`810ff89c8`）：在 `LocalNodeBridge` 新增 `local.trajectory.attachment_sources` 与只读方法白名单，对 `session/attachment` 实施 `hostAttachmentAuthorized === true` 默认拒绝（fail-closed）门禁；`host_server.rs` 剥离客户端伪造字段，先查原生来源并经 `POST /im/v1/agents/:id/trajectory/authorize-attachment` 校验通过后才放行。
  - 独立关闭依据与版本：`change-code-review`（`c6441360`）与 `product-journey-review`（`c3ca0565`）核对 `desktop-local-bridge.test.ts` 与真栈 `attachment_forbidden` 实测回执，在 `810ff89c8` / `abb2d3ff6` 判定 **`closed`**。
- **CR-2 / PJ-F3**（`apps/node/src/configuration.ts`、`apps/node/src/local-admin.ts`、`src/IM/frontend/src/desktop/desktop-local-computer-card.tsx`）：`validateNodeSettings` 与「这台电脑」前端硬编码仅允许 `dsh`/`codex`/`claude`，遗漏 `antigravity` 且在 `stop` 前执行配置校验阻断停机。
  - 严重度 / 证据状态：`blocking` / `CONFIRMED`。
  - Resolution（`810ff89c8`）：`validateNodeSettings` 改为对齐 `@nano/product-contracts` 的 `workerRuntimes`（含 `antigravity`），`stop` 跳过配置与模型校验，前端从浏览器安全子路径 `@nano/product-contracts/worker-runtimes` 渲染完整 4 类 Worker 选项。
  - 独立关闭依据与版本：`c6441360`、`191de864`、`c3ca0565` 核对单测与真栈 `worker_runtime: "antigravity"` 保存生效回执（HTTP `200`），判定 **`closed`**。
- **CR-3**（`apps/im-server/src/trajectory.ts`、`apps/desktop/src/host_server.rs`）：`/desktop/v1/workspace/open` 复用仅面向 `global` 模式的 `/trajectory/authorize` 且未传播 `410 GONE`，导致 `single_thread` 个人助手工作区文件无法本地打开。
  - 严重度 / 证据状态：`should-fix` / `CONFIRMED`。
  - Resolution（`810ff89c8`）：新增 `POST /im/v1/agents/:agent_id/workspace/authorize`，统一执行已删除 Agent `410 GONE` 拦截并同时支持本人所有的 `global` 与 `single_thread` PA 鉴权（异账号返回 `403`）。
  - 独立关闭依据与版本：`c6441360` 与 `c3ca0565` 核对 `desktop-trajectory-auth.test.ts` 与真栈 PA `200`/`403` 实测，判定 **`closed`**。
- **CR-4**（`apps/desktop/src/notifications.rs`）：后台通知守护对全公司广播的 `agent.work.updated` 未校验 `owner_id` 即拉取 `/work` 并发出 `waiting_permission` 通知，且 `permission.request` 未检查会话免打扰状态。
  - 严重度 / 证据状态：`should-fix` / `CONFIRMED`。
  - Resolution（`810ff89c8`、`abb2d3ff6`）：新增 `ensure_agent_owned_by_session`（并在 `agent.status_changed` / `agent.lifecycle.changed` 时刷新归属缓存）仅对本人管理 Agent 处理 `waiting_permission`，为 `permission.request` 补齐免打扰过滤与单测。
  - 独立关闭依据与版本：`c6441360` 在 `810ff89c8` / `abb2d3ff6` 复核通过，判定 **`closed`**。
- **FE-F1 / FE-F2**（`src/IM/frontend/src/desktop/desktop.css`、`desktop-install-picker.tsx`、`M1/evidence/`）：`390px` 初始与未发布降级截图未滚至卡片区域，且 `/settings/nodes` `456px` 右抽屉按视口媒体查询导致双列挤压。
  - 严重度 / 证据状态：`should-fix` / `CONFIRMED`。
  - Resolution（`810ff89c8`）：为 `.desktop-picker-root` 启用 `container-type: inline-size` 与 `@container (max-width: 620px)` 单列自适应，统一中性 `Intel 芯片 Mac` 文案，并补齐滚动到位与右抽屉实拍。
  - 独立关闭依据与版本：`191de864` 目视复查 `m1-web-onboarding-390.png`、`m1-web-unpublished-390.png` 与 `m1-web-nodes-drawer-1280.png` 确认单列舒展无溢出，判定 **`closed`**。
- **FE-F3**（`src/IM/frontend/src/features/chat/components/native-tool-detail.tsx`、`agent-work-panel.tsx`）：真实 DSH 工具事件走 `NativeToolDetail` 分支而漏接 `<WorkspacePathActions />`，Work 正文 Markdown 未接 `file://` 本地打开。
  - 严重度 / 证据状态：`blocking` / `CONFIRMED`。
  - Resolution（`810ff89c8`）：在 `NativeToolDetail` 的 `diff`/`read`/`search`/通用读写分支挂载 `<WorkspacePathActions />`，在 `agent-work-panel.tsx` 挂载 `DesktopWorkspaceFileLink`，补充 `native_view` 单测与展开态实拍 `m1-desktop-work-paths-1280.png`。
  - 独立关闭依据与版本：`191de864` 与 `c3ca0565` 复核代码与展开态截图确认 `.md` 打开/定位与 `.sh` 仅定位闭合，判定 **`closed`**。
- **FE-F4**（`desktop-local-computer-card.tsx`、`workspace-path-actions.tsx`、`desktop.css`）：中文界面配置校验失败直接展示英文底层异常，`<select>` 右侧文字与下拉箭头重叠。
  - 严重度 / 证据状态：`should-fix` / `CONFIRMED`。
  - Resolution（`810ff89c8`）：后端输出结构化校验错误码并映射中英文可行动文案，`.desktop-select-input` 增加 `padding-right: 34px; text-overflow: ellipsis;`。
  - 独立关闭依据与版本：`191de864` 目视核验 `m1-desktop-nodes-error-390.png` 与 `m1-desktop-nodes-expanded-1280.png`，判定 **`closed`**。
- **PJ-F1 / PJ-F2 / FE-F5**（`apps/desktop/Cargo.toml`、`notifications.rs`、`tray.rs`、`host_server.rs`、`CrewdenDesktop.iss`）：Windows 原生通知借用 `POWERSHELL_APP_ID` 且监听器提前释放，macOS `mac-notification-sys` 将进程 `NSBundle` 篡改为 `com.apple.Finder`，`--background` 自启累积未读数在首次建窗时未同步角标，且通知/托盘未按语言切换。
  - 严重度 / 证据状态：`blocking` / `CONFIRMED`。
  - Resolution（`810ff89c8`、`abb2d3ff6`）：移除 `mac-notification-sys` 与 `tauri-winrt-notification`；实现全透明无外框 `22px` 圆角不抢焦点屏幕角落悬浮通知窗（macOS `NSStatusWindowLevel` + 真实 `.app` `NSUserNotificationCenter` 代理，Windows WinRT `WINDOWS_AUMID = "work.crewden.desktop"` 协议激活 Toast + 浮窗兜底 + Inno Setup 快捷方式 `AppUserModelID` 与图标资源），通过 `crewden-desktop://open?route=...` 单实例转发唤醒目标路由，并在 `ensure_main_window` 补齐 `--background` 未读角标、动态托盘提示与中英文菜单/通知同步。
  - 独立关闭依据与版本：`191de864`、`c3ca0565`、`c6441360` 在 `810ff89c8` / `abb2d3ff6` 复核通过，判定 **`closed`**。
- **PJ-F4**（`apps/node/src/main.ts`、`local-admin.ts`、`desktop-local-computer-card.tsx`）：「这台电脑」保存配置重启本机节点时未统计真实在途 DSH 会话并提示二次确认。
  - 严重度 / 证据状态：`blocking` / `CONFIRMED`。
  - Resolution（`810ff89c8`）：在 `apps/node/src/main.ts` 订阅各分区 DSH `session.status`（`running`）与产品侧 `busy` 状态汇总至 `LocalNodeBridge.activeTasks`，`updateLocalNodeConfig` 在 `active_tasks > 0` 且未带 `confirm_restart: true` 时返回 `409 active_tasks_running`，前端展示「等待任务完成 / 确认立即保存并重启」二次确认条并经真栈在途任务实测。
  - 独立关闭依据与版本：`c3ca0565`、`191de864`、`c6441360` 复核 `m1-desktop-nodes-busy-confirm-1280.png` 与代码单测，判定 **`closed`**。
- **R2-1 / F1-win-compile**（`apps/desktop/src/config.rs`、`notifications.rs`、`M2/verification.md`）：Round 2 补丁在 `#[cfg(target_os = "windows")]` 中调用了未定义的 `DesktopPaths::is_isolated_autostart()`。
  - 严重度 / 证据状态：`blocking` / `CONFIRMED`。
  - Resolution（`abb2d3ff6`）：在 `DesktopPaths` 补齐 `is_isolated_autostart(&self) -> bool`，经 `--target x86_64-pc-windows-gnu` 对 `config.rs`、`autostart.rs` 与 `windows_notify` 完成 `windows 0.61` + `winreg 0.52` 跨目标类型检查并对齐 `M2/verification.md` 记录。
  - 独立关闭依据与版本：`c6441360` 与 `c3ca0565` 在 `abb2d3ff6` 复核通过，判定 **`closed`**。
- **R2-2**（`apps/desktop/src/host_server.rs`、`tray.rs`）：`/desktop/internal/popup-banner` 将未转义 `<` 的通知 JSON 内联拼入同源 `<script>`，若消息含 `</script>` 可触发脚本逃逸。
  - 严重度 / 证据状态：`blocking` / `CONFIRMED`。
  - Resolution（`abb2d3ff6`）：改为零服务端插值的静态常量 `POPUP_BANNER_HTML`（前端经 `URLSearchParams` 读取查询参数并仅写 `.textContent`）+ 严格 `Content-Security-Policy` 响应头，`tray.rs` `eval` 改为双层 JSON 字符串 `JSON.parse(...)`，并在 `host_server::tests` 新增 `</script><script>evil()</script>` 回归单测。
  - 独立关闭依据与版本：`c6441360` 与 `c3ca0565` 在 `abb2d3ff6` 复核通过，判定 **`closed`**。

最终状态：**无存活 findings（0 open）**。

## 流程收口

- 重要目标和关键设计覆盖：[`spec.md`](spec.md) 与 [`design.md`](design.md) 的全部 V1 范围（双端零命令行首装绑机与 CLI/`feat-781` 平滑接管、常驻菜单栏/托盘与登录自启、不抢焦点圆角屏幕角落弹出通知与路由直达、按 `imOrigin` 与账号隔离、本机 IPC 原生轨迹直读与工作区路径安全打开、「这台电脑」图形化配置/日志/在途任务保护、`shell_protocol: 1` 拆分归档 `0 B` runtime 复用热更新与回退，以及候选/正式发布流水线）均已实现并通过 `M1`（macOS `arm64`）与 `M2`（干净 Windows 10/11 `x64` Hyper-V VM）验收及三项独立审查。
- 开放问题 / pending / inconclusive：0 项。
- 最终 delta 校对：独立代码审查（`c6441360-a915-467c-876e-5420bfe78130`）在 `abb2d3ff618b5da21eab128f21605e594eb8f519` 完成 `corrected-delta` 核对，[`specs/im/desktop-client.md`](specs/im/desktop-client.md)、[`specs/im/agents-nodes.md`](specs/im/agents-nodes.md)、[`specs/im/agent-work.md`](specs/im/agent-work.md)、[`specs/gateway/service-lifecycle.md`](specs/gateway/service-lifecycle.md) 全部判定为 **`aligned`**（归并后新增 `im/desktop-client.md` 5 条 Requirement，`gateway/service-lifecycle.md` Requirement 数由 `18` 增至 `19`，`im/agents-nodes.md` `56` 与 `im/agent-work.md` `20` 保持不变）。
- 版本变化后保留 / 补验的判断与依据：Round 1（`2d7606a76`）→ Round 2（`810ff89c8`）→ Round 3（`abb2d3ff6`）已完成三名独立审查者闭环复验；随后同步最新 `origin/develop`（`6e23f90a9`）合并上游 DSH `0.2.2-rc.5` 与身份头像改动，复跑全量构建、类型检查、契约测试、Vitest、前端测试与 `cargo test` 全部通过，独立审查判断保持有效（`retained`）。
- 测试资源回收结果 / 例外保留项、owner 与回收触发：本地 `./scripts/e2e-down.sh` 隔离栈、临时目录、`dist/`、`src/IM/frontend/dist/`、`apps/desktop/target/` 及 gitignored 验收截图目录均已完整清理；`~/Library/LaunchAgents` 与 `/Users/czj/.nanoassistant` 前后核对零污染；云端 Windows 10/11 临时 Hyper-V 虚拟机、虚拟交换机与临时验收脚本已销毁移除。专属开发 worktree `/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-790-desktop-client` 按仓库规则保留至 PR 合入 `develop` 后由执行合并或接手后续工作的 Agent 清理。
- 交付范围与剩余事项：完成 4 份 canonical specs 归并、归档 `docs/changes/archive/feat-790-desktop-client`、通过全部本地 CI 等价门禁后推送 `unit/feat-790-desktop-client` 并创建目标为 `develop` 的 PR，触发远端 CI 与 `desktop-candidate.yml` 检查并交由用户审阅合入（不自动 merge）。
