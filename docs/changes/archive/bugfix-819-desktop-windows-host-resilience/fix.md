# bugfix-819-desktop-windows-host-resilience: 桌面宿主缓存卫生、窗口容错、锁残留恢复、空间预检与彩色托盘

Platform-Parity-Exempt: 本次修复聚焦 Crewden Desktop 原生宿主（macOS / Windows）与受管本机节点生命周期锁恢复，不涉及共享客户端协议、Web IM 前端源码或 iOS 原生客户端变更。

## Relations

- Related: [IM - Desktop Client Specification](../../../specs/im/desktop-client.md)
- Related: [Gateway - Service Lifecycle Specification](../../../specs/gateway/service-lifecycle.md)
- Related: `bugfix-807-desktop-seed-retry`、`bugfix-810-desktop-node-lifecycle`、`bugfix-812-windows-installer-lifecycle`

## 原始报告

> Issue B（阻断）：客户端更新 UI 不清 webview 缓存 → 左下角账号入口空白
> 现象：客户端左下角账号入口/头像不显示（浏览器访问同一 IM 正常）；即使把客户端内置 UI 替换成新前端，重开客户端仍空白。
> 根因：客户端更新内置 UI（%LOCALAPPDATA%\CrewdenDesktop\versions<sha>\ui\frontend）时，Tauri webview（%LOCALAPPDATA%\work.crewden.desktop\EBWebView）仍缓存旧 assets；新 index.html + 旧 chunk 混用，导致账号入口组件渲染失败。清理 EBWebView\Default{Cache,Code Cache,GPUCache} 后立即恢复。
>
> Issue C（体验）：安装后首次启动无窗口/无托盘反馈，静默退出无错误
> 现象：安装完成点"打开"后看不到窗口，也没有托盘图标；某些情况进程启动即退，无任何提示。
>
> Issue D（体验）：实例锁/状态残留导致"启动即退"
> 现象：进程被强制结束后，%LOCALAPPDATA%\CrewdenDesktop\instance.lock、~/.nanoassistant/connections/<hash>/.gateway-state.json、.gateway-lifecycle.lock 残留；新实例检测到后直接退出，用户看到"双击没反应"。
>
> Issue E（体验）：磁盘空间不足时报 os error 5（拒绝访问），误导为权限/杀毒问题
> 现象：C 盘剩余 1.1GB 时首次启动报"运行环境初始化未完成——拒绝访问 (os error 5)，请检查磁盘空间或防病毒"。
> 建议修复：解压前预检可用空间并给出明确提示（"需要约 X GB，当前仅 Y GB"）。
>
> Issue F（体验）：Windows 托盘图标为纯黑单色，不符合彩色习惯
> 现象：Windows 托盘区的客户端图标显示为纯黑色；Windows 下用户通常期望彩色图标。
> 根因：托盘图标资源 apps/desktop/icons/tray.png 是 44x44、RGB(0,0,0) 纯黑 + alpha 的单色图标；apps/desktop/src/tray.rs 用 include_bytes!("../icons/tray.png") 加载。项目里已有彩色 128x128.png，但托盘未使用它。

## 现象 / 复现

基于 `origin/develop`（`890d74f70`）逐项核查已有保护与仍可复现的真实缺口：

- **基线已覆盖保护（须完整保留，不得回退）**：
  - 首次启动解包期间已立即呈现内联「正在准备运行环境…」进度页并注册托盘（`bugfix-807`）；
  - `main.rs` 在 `run_from_env()` 返回 `Err` 时已写入 `desktop-host.log` 并弹出原生错误提示框；
  - `InstanceLock` 已采用 OS 级文件句柄排他锁（Unix `flock(LOCK_EX|LOCK_NB)`、Windows `share_mode(0)`），进程退出后内核自动释放句柄；`.gateway-state.json` 已校验 `process_start` 与 Windows `boot-filetime`（`bugfix-810`、`bugfix-812`）。
- **仍在 `origin/develop` 真实存在并可复现的 4 类缺陷**：
  1. **Issue B（回环静态资源无 `Cache-Control` + 旧版升级遗留 WebView2 磁盘缓存污染）**：
     - 请求 `http://127.0.0.1:<port>/assets/app.js` 等 `ui/frontend` 静态文件时，响应头缺少 `Cache-Control`。因 `persisted_port` 跨重启与升级固定复用，WebView2 对无缓存头资源执行启发式强缓存；且从旧版本升级或原地替换 `versions/<sha>/ui/frontend` 时，`EBWebView\Default\{Cache,Code Cache,GPUCache}` 内已有污染缓存，重开客户端仍混用旧静态文件。
  2. **Issue C & D（窗口创建错误吞没静默假活 + Windows 前台唤醒受限 + `.gateway-lifecycle.lock` 强杀残留永久失管）**：
     - 前台启动时若 `WebviewWindowBuilder::build()` 失败（如 WebView2 环境异常），`ensure_main_window` 以 `.ok()?` 吞掉错误，`lib.rs` 忽略返回值并继续常驻持有 `instance.lock`；此后用户再次双击均被 `forward_to_running_instance` 转发后退出，表现为“无窗口、无报错、双击没反应”。
     - Windows 下二次启动向已有常驻实例转发唤醒请求前未调用 `AllowSetForegroundWindow`，后台实例 `set_focus()` 易被 Windows 11 Foreground Lock 拦截。
     - 当持有 `.gateway-lifecycle.lock` 的节点生命周期进程被强杀（`SIGKILL` / `TerminateProcess`）后，锁目录残留在连接目录中：`apps/desktop/src/lib.rs:170` 在 `supervise_node` 中只要检测到 `.gateway-lifecycle.lock` 存在即无条件返回 `Ok(false)`，永不触发恢复；同时 `apps/node/src/lifecycle.ts:294` 的 `proper-lockfile` 设 `stale: 120000`（120 秒）且无持锁进程存活校验，而重试总预算仅 30 秒（`120 * 250ms`），死锁残留后 90 秒内所有 CLI 启停直接报 `ELOCKED` 失败。
  3. **Issue E（解包前缺少可用磁盘空间预检，且错误分类与准备页提示笼统误导）**：
     - 磁盘剩余空间约 1.1 GB 时启动首次解包，`ensure_seed_bundle_installed` 未预检峰值空间便直接复制归档并解压，中途写满或触发句柄错误后，`render_seed_preparation_html` 统一显示「请检查本机磁盘空间或防病毒拦截情况后点击重试」，无法在解包前给出明确的所需/可用容量提示，也未区分磁盘满与目录权限/占用错误。
  4. **Issue F（非 macOS 平台托盘误用纯黑单色图标）**：
     - `apps/desktop/src/tray.rs` 在所有平台固定加载纯黑 `icons/tray.png`（RGB 全 0），在 Windows 11 深色任务栏下几乎不可见，不符合 Windows 彩色应用托盘习惯。

## 根因

### 原始设计意图与必须保住的不变量

`c75e0415e`（`feat-790-desktop-client`）引入 Crewden Desktop 原生宿主与本地节点桥接，`ea158bdbf` / `722fc1b16`（`bugfix-807`）建立随包种子校验与重试恢复，`15f289a86`（`bugfix-810`）建立低开销 `local.ping` 节点监督与手停/登录自启语义。修复必须保住以下核心不变量：

1. **同源持久状态不丢失**：`persisted_port` 固定复用是为了保住 WebView `http://127.0.0.1:<port>` 同源下的 `Local Storage`、`IndexedDB` 与能力 Cookie；清理 WebView 缓存时严禁调用全量清除浏览数据 API 或删除 `Cookies`、`Local Storage`、`IndexedDB`、`sessions.json`。
2. **后台自启与前台启动边界清晰**：`--background` 登录自启仍须无窗口静默驻留托盘；前台启动（`!cli.background`）必须成功建立主窗口，失败时写入 `desktop-host.log`、弹出原生致命错误提示并释放 `instance.lock` 退出，绝不以无窗口半死状态占锁常驻。
3. **并发串行与健康期零子进程开销**：`.gateway-lifecycle.lock` 仍须严格串行化同一配置下的真实存活并发启停；`supervise_node` 在真实存活进程持锁期间继续礼让，且节点健康在线期间维持 `local.ping` 零子进程/零日志重读（`bugfix-810`）。
4. **种子解包原子性与诊断可追溯**：保留归档 SHA-256 校验、Windows runtime junction 原子发布与 `os error 5` 短暂占用退避重试（`bugfix-807`），保留底层路径与系统错误码以便排障，同时在前置空间不足与磁盘满场景提供准确中文引导。
5. **macOS 菜单栏模板图标语义**：macOS 继续使用单色 `icons/tray.png` + `icon_as_template(true)` 适配系统深浅色菜单栏；仅非 macOS（Windows 等）切换为彩色品牌图标 + `icon_as_template(false)`。

### 具体代码根因

1. **回环静态缓存与升级遗留缓存**：
   - `apps/desktop/src/host_server.rs` 在返回 `bundle.ui_frontend` 静态资源时仅设置了 `content-type`，遗漏了 `cache-control: no-store`，导致 Chromium/WebView2 对同端口静态资源启用启发式缓存。
   - 宿主未记录上次已服务的 UI bundle 标识，升级或替换 `ui/frontend` 时未清理已污染的 `EBWebView\Default\{Cache,Code Cache,GPUCache}`；`reload_webview` 复用了无防缓存参数的固定 URL。
2. **窗口创建错误吞没、前台权限缺失与生命周期锁死锁**：
   - `apps/desktop/src/tray.rs` 使用 `.build().ok()?` 丢弃了 `tauri::Error`，`apps/desktop/src/lib.rs` 用 `let _ = coord_setup.ensure_main_window(...)` 忽略失败，导致无窗口进程驻留后台占住单实例锁。
   - `apps/desktop/src/lib.rs` 在 Windows 转发唤醒前未向目标宿主 PID 授予 `AllowSetForegroundWindow`；`ensure_main_window` 在恢复已有窗口时对隐藏/最小化窗口的 `show` / `unminimize` 顺序未顾及已最大化窗口状态保持。
   - `apps/node/src/lifecycle.ts` 使用 `proper-lockfile` 时未写入持锁进程身份（`pid` + `process_start`）也未在加锁前回收死进程遗留锁；`apps/desktop/src/lib.rs` 仅凭 `.gateway-lifecycle.lock` 路径存在就短路跳过 `supervise_node`，导致强杀残留锁永久阻断自动恢复。
3. **空间预检缺失与错误提示一刀切**：
   - `apps/desktop/src/local_node.rs` 在复制缓存与调用 `tar` 解压前未检查目标分区可用字节数是否满足归档缓存 + 解包峰值空间。
   - `local_node.rs` 未区分磁盘满（Windows `os error 112`/`39`、Unix `ENOSPC`、`tar` 空间不足输出）与权限拒绝（`os error 5`），且 `apps/desktop/src/host_server.rs` 将所有准备失败副标题硬编码为「请检查本机磁盘空间或防病毒拦截情况后点击重试」。
4. **托盘图标未按平台分流**：
   - `apps/desktop/src/tray.rs` 无条件编译嵌入并使用纯黑单色 `icons/tray.png`，未在非 macOS 平台选用彩色品牌图标资源（`icons/128x128.png`）。

## 本次审查安排

| 审查编组 | 必须回答的问题 | 能力 | 验证方法与已有证据 |
|---|---|---|---|
| G1 独立代码与桌面引导体验审查 | 1. 4 类缺陷（B/C+D/E/F）是否完整修复且未破坏 `bugfix-807`/`810`/`812` 既有不变量与数据安全边界（保留 Cookies/Local Storage、严格校验持锁进程存活与原子回收）；<br>2. 首次准备页错误状态文案（空间不足 vs 权限/占用 vs 归档损坏）与平台托盘图标选择是否自明、准确且不误导用户；<br>3. canonical spec 归并是否与实现及测试严格一致。 | `change-code-review` + `frontend-experience-review` | Rust 单元/集成测试（`cargo test --locked --manifest-path apps/desktop/Cargo.toml`）、Node 生命周期与桌面监督回归（`vitest` + `apps/desktop/tests/node-lifecycle.mjs`）、准备页各错误态 1280×840 渲染截图核对 |

## 修复

1. **回环静态资源防缓存与升级遗留 WebView 缓存按指纹清理（Issue B）**：
   - 在 `apps/desktop/src/host_server.rs` 为 `bundle.ui_frontend` 静态文件及 `/desktop/bootstrap` 响应统一补充 `Cache-Control: no-store`（静态资源同时附带 `X-Content-Type-Options: nosniff`），避免固定复用的 `127.0.0.1:<persisted_port>` 触发 Chromium/WebView2 启发式强缓存。
   - 在 `apps/desktop/src/config.rs` 与 `apps/desktop/src/local_node.rs` 新增 `<desktop_home>/webview-ui-cache.json` 指纹标记（综合活跃 bundle 版本、摘要、路径与 `ui/frontend/index.html` SHA-256）；首次启用该标记（从旧版升级）或检测到 UI bundle 切换/原地替换时，在创建 WebView 窗口前及热重载入口仅清理 `EBWebView\Default\{Cache,Code Cache,GPUCache}` 等瞬态 HTTP/代码/着色器缓存目录，完整保留 `Cookies`、`Network\Cookies`、`Local Storage`、`IndexedDB` 与 `sessions.json`；`reload_webview` 使用带 `_cb` 防缓存参数的新引导 URL 触发原生导航并保持当前路由。
2. **主窗口创建失败显式退出弹窗、Windows 前台唤醒授权与生命周期死锁快速回收（Issue C & D）**：
   - `apps/desktop/src/tray.rs` 的 `ensure_main_window` 改为返回 `Result<WebviewWindow, String>` 并记录 `ERROR` 日志，恢复已有窗口时按 `show()` → 条件 `unminimize()` → `set_focus()` 顺序避免破坏已最大化状态；`apps/desktop/src/lib.rs` 在前台冷启动创建主窗口或系统托盘失败时清理 `host-state.json` 并向上返回错误，由 `main.rs` 写入 `FATAL` 日志、弹出原生错误提示框并释放 `instance.lock` 退出，杜绝无主窗口后台假活。后台常驻期间交互唤起失败亦通过异步原生弹窗与日志提示。
   - `apps/desktop/src/lib.rs` 的 `forward_to_running_instance` 在 Windows 平台向运行实例转发唤醒前调用 Win32 `AllowSetForegroundWindow(live_pid)` 授予前台激活权限。
   - `apps/node/src/lifecycle.ts` 在已被 `.gitignore` 忽略的 `.gateway-owner/` 目录下维护伴随身份文件 `<lock>.json`（记录 `pid`、`process_start` 与获取时间，不改动 `proper-lockfile` 自身目录 `mtime` 心跳）与基于唯一身份标记 + 非递归 `rmdir` 的过渡互斥目录 `<lock>.guard`，串行完成死锁探测、清理 `signal-exit` 遗留伴随文件、`lockfile.lock` 获取及伴随写入，并注册进程 `exit` 同步清理；`apps/desktop/src/lib.rs` 的 `supervise_node` 改用纯只读 `is_active_gateway_lifecycle_lock` 识别死锁并交由 Node 侧原子回收，彻底消除跨进程与并发回收竞态。
3. **种子解包前可用磁盘空间预检与精准错误分类引导（Issue E）**：
   - `apps/desktop/src/local_node.rs` 在 `ensure_seed_bundle_installed` 复制/解压前通过平台磁盘空闲查询（Windows `GetDiskFreeSpaceExW`、Unix `df -Pk`）对比待缓存归档与解包峰值空间需求，空间不足时在写盘前直接返回明确提示（如 `磁盘可用空间不足：初始化运行环境需要约 1.6 GB，当前仅剩 1.1 GB。`）。
   - 新增 `classify_seed_error_for_os`（精确解析 `os error <N>` 整数边界并区分 Windows `112/39`、`5/32/33` 与 POSIX `28/69/122`、`13/1`，避免误匹配 `os error 50` 或 POSIX `EIO`/`EPIPE`）与 `seed_error_guidance`，同步更新 `render_seed_preparation_html` 与 `/desktop/v1/context`，消除重复提示与误导文案并优化长路径折行。
4. **Windows 系统托盘彩色品牌图标（Issue F）**：
   - `apps/desktop/src/tray.rs` 按平台分流：macOS 继续使用单色 `icons/tray.png` + `icon_as_template(true)`，Windows 等非 macOS 平台改用彩色品牌图标 `icons/128x128.png` + `icon_as_template(false)`。

## 验证

- **TDD 修前失败复现 → 修后通过**：
  - `pnpm exec vitest run apps/node/tests/lifecycle.test.ts -t "recovers immediately"`：修前强杀持锁 `cli.js stop` 后 `cli.js status` 超时报错 `ELOCKED`；修后在 `<2s` 内自动回收死锁并返回 `NOT RUNNING`，且真实存活持锁期间仍严格串行等待（4/4 通过）。
  - `cargo test --locked --manifest-path apps/desktop/Cargo.toml`：修前静态资源缺少 `Cache-Control: no-store`、准备页对权限错误误报磁盘空间、Windows 托盘图标彩色像素数为 0、1.1 GB 低空间未拦截；修后 22 项测试（17 项库测试 + 4 项附件传输 + 1 项实例锁）全部通过，含 `EBWebView` 缓存目录清理且 `Cookies`/`Local Storage`/`IndexedDB` 保态、前台窗口创建失败中止启动并清理 `host-state.json`。
  - `node apps/desktop/tests/node-lifecycle.mjs apps/desktop/target/debug/crewden-desktop .`：验证健康期 10 秒零 `local-admin` 子进程与零 `gateway.log` 重读，以及网关被 `SIGKILL` 同时残留死进程 `.gateway-lifecycle.lock` 时的自动清理与崩溃恢复、版本切换重启和登录自启状态机。
- **界面体验自检与限制说明**：
  - 在 1280×840 桌面默认视口下实际渲染核对首次准备页「准备中」「磁盘空间不足（1.6 GB / 1.1 GB）」「目录访问受阻（os error 5）」三态画面，标题、引导说明、诊断详情与日志路径层级清晰无重复说教。
  - 本机为 macOS arm64，Windows 原生 WebView2 窗口焦点表现、Windows 11 任务栏托盘实机渲染与 `GetDiskFreeSpaceExW` 原生安装包冷启动由远端 CI `Desktop client candidates / windows-x64` 进一步覆盖。
