# M2 Verification — Windows 10 & Windows 11 (`x64`) Crewden Desktop & Release Pipeline

## 1. 验收范围与真实干净虚拟机环境

- **目标里程碑**：`M2` — Windows 10/11 `x64` 桌面安装包（`Crewden-Desktop-Setup-x64.exe`）、`.NET Framework 4` `DesktopGatewayHost.exe` 独立计划任务与控制命名管道监督（`CrewdenDesktop-<24hex>` / `crewden-desktop-host-<24hex>`）、与 `feat-781` 轻量后台节点安装器（`Crewden-Setup-x64.exe`）同机无损并存与平滑接管、系统托盘常驻与登录自启（`HKCU\Software\Microsoft\Windows\CurrentVersion\Run\CrewdenDesktop --background`）、Windows Named Pipe 本机轨迹直连、资源管理器文件定位与 `.bat` 可执行后缀拦截、Windows 受管热更新与损坏候选自动回退，以及候选构建与正式发布流水线（`.github/workflows/desktop-candidate.yml`、`scripts/publish-node-release.mjs`、`.github/workflows/node-release.yml`）。
- **干净官方客户机基线**（复用 `feat-781` 云端嵌套 Hyper-V 隔离验收方法，零触碰开发机 macOS 宿主）：
  - **Windows 10 `x64`**：Microsoft 官方 `Windows 10 Enterprise LTSC Evaluation`（镜像版本 `10.0.19041.1288`，运行内核 `10.0.19044`，ISO SHA-256 `e4ab2e3535be5748252a8d5d57539a6e59be8d6726345ee10e7afd2cb89fefb5`），非提权标准用户 `nanoqa`（`elevated = false`），系统预装 `node = false`、`npm = false`、`pnpm = false`，`Microsoft-Windows-Subsystem-Linux = Disabled`；安装器在无内置 WebView2 的干净 LTSC 系统上自动静默补装 Evergreen WebView2 Runtime（实测 `158.0.4370.33`）。
  - **Windows 11 `x64`**：Microsoft 官方 `Windows 11 Enterprise Evaluation`（镜像版本 `10.0.26300.9457`，运行内核 `10.0.26300`，ISO SHA-256 `bc3f24086ebadc94489066b5ad78089e2cf5c3491e90e790bb81a2b199c10e38`，启用硬件虚拟 TPM 2.0 + UEFI Secure Boot），非提权标准用户 `nanoqa`（`elevated = false`），系统预装 `node = false`、`npm = false`、`pnpm = false`，`Microsoft-Windows-Subsystem-Linux = Disabled`，WebView2 Runtime `152.0.4191.66`。
  - 验收完成后两台临时 Hyper-V 虚拟机、虚拟交换机、NAT 规则与临时 VHDX 镜像已在 `finally` 块中全量销毁回收。

## 2. 安装包体积、内置官方 Node 校验与热更新字节账单

| 产物 | 版本 | 字节大小 | SHA-256 | 说明 |
|---|---|---:|---|---|
| `Crewden-Desktop-Setup-x64.exe` | `1.0.0` | `87,086,971 B` (`83.05 MiB`) | `8a14467158266ace0f21d1eba651f86967ec062aa3929383419c57eeab0fde0d` | 用户态 Inno Setup 6 安装器（`PrivilegesRequired=lowest`），内嵌 `CrewdenDesktop.exe`、`seed-archives/` 与官方 `MicrosoftEdgeWebView2Setup.exe` 离线引导器 |
| `desktop-runtime-win32-x64.tar.gz` | `1.0.0` & `1.0.1` | `72,261,346 B` (`68.91 MiB`) | `d832102c1ff1f93bca0928304ae5cafbca3d0efbf43bd4270ace6d30a33feead` | 内置 nodejs.org 官方校验的 `node-v24.22.1-win-x64` + 锁定 DSH 依赖 + `DesktopGatewayHost.exe`；`1.0.0` 与 `1.0.1` 跨版本确定性构建 SHA-256 完全一致（`runtimeIdenticalAcrossV1AndV2 = true`） |
| `desktop-app-win32-x64.tar.gz` | `1.0.0` | `7,140,932 B` (`6.81 MiB`) | `4ca2b9511b2be84fcd0ce6ec7eefcc8844196e1a9d35bbfed9c4fc9048fd54fa` | 节点应用代码 + `ui/frontend` + `ui/trajectory` |
| `desktop-app-win32-x64.tar.gz` | `1.0.1` | `7,140,979 B` (`6.81 MiB`) | `a350f4feaf6af0897046858e7c216ac294aa976d84e6f5ba59a543631e5bb195` | 纯应用/前端更新候选包 |

- **受管热更新字节账单（Windows 10 & Windows 11 实测一致，`1.0.0 -> 1.0.1`）**：
  - `/v1.0.1/desktop-win32-x64.json`：`736 B`
  - `/v1.0.1/desktop-app-win32-x64.tar.gz`：`7,140,979 B` (`6.81 MiB`)
  - `/v1.0.1/desktop-runtime-win32-x64.tar.gz`：**`0 B`**（直接命中 `%LOCALAPPDATA%\CrewdenDesktop\runtimes\d832102c...` 本地缓存，`.desktop-active.json` 记录 `runtime_reused: true`）
  - 切换完成后 IM 节点在线版本升为 `1.0.1`，桌面宿主热重载 `/build-note.txt` 返回 `upgraded-1.0.1`。
- **损坏候选包自动回滚验证（`1.0.1 -> 1.0.2-bad`）**：
  - 注入启动失败的 `1.0.2` 候选包发起更新后，Windows 更新工作进程检测到新实例未就绪，自动恢复 `.desktop-active.json` 并重新拉起 `1.0.1` 受管实例；两版系统终态均为 `state = "rolled_back"`、`error_code = "start_failed"`，`versionAfterRollback = "1.0.1"` 且节点保持在线。

## 3. Windows 10 与 Windows 11 全链路实测矩阵（含两次真实系统重启）

本地客户机截图保存在 gitignored 目录 `docs/changes/feat-790-desktop-client/M2/evidence/` 下供本地复查（GitHub Actions 运行 `45729507062`）。

| 阶段 | 验证内容与关键断言 | Windows 10 (`10.0.19044`) 实测结果 | Windows 11 (`10.0.26300`) 实测结果 | 本地截图定位（gitignored） |
|---|---|---|---|---|
| **Phase 1 & 2 — 干净客户机零 Node 安装、WebView2 准备与 `feat-781` 并存/接管** | 先安装运行 `feat-781` `Crewden-Setup-x64.exe` 建立独立任务 `\Crewden-Gateway-*`，再从 IM 下载校验安装 `Crewden-Desktop-Setup-x64.exe`；验证异账号 `winbob` `inspect` 仅返回 `foreign_owner`、`lifecycle` `403`、未确认 `connect` `409`；切回原 owner `nano` 平滑接管，核实 `\Crewden-Gateway-*` 退役归零、`\CrewdenDesktop-*` 注册为 `1`、旧进程退出，且 `.windows-active.json`、`Crewden.lnk`、`crewden://` 与原工作区文件原样保留。 | WebView2 `158.0.4370.33` 自动补装成功；平滑接管 `computer-344cebca`，`standaloneTasks = 0`、`desktopTasks = 1`、`crewdenLnk = true` | WebView2 `152.0.4191.66` 就绪；平滑接管 `computer-d90ae249`，`standaloneTasks = 0`、`desktopTasks = 1`、`crewdenLnk = true` | `M2/evidence/win10-01-login-gui.png`、`win11-01-login-gui.png` |
| **Phase 3 & 4 — 应用内配模型、创建 PA 与真实对话回复** | 零命令行配置模型服务并创建个人助手「桌面助手」，发送消息验证内置官方 `node.exe` (`v24.22.1`) + DSH 子进程完成真实回复并展示原生 Windows 系统通知。 | `pa_045c8f1ef516` (`c_iknu83`) 真实回复 `"42"` | `pa_69451bc7fcb1` (`c_2wt5yn`) 真实回复 `"42"` | `M2/evidence/win10-02-chat-reply-gui.png`、`win11-02-chat-reply-gui.png` |
| **Phase 5 — `WM_CLOSE` 收起托盘、后台 `/im/ws/user` 通知与外链安全门禁** | 向主窗口发送 `WM_CLOSE` 验证隐藏至系统托盘而不退出；后台捕获群消息（`human_message`）、`@提及`（`mention`）与助手完成（`message_completed`），唤醒窗口精准跳转目标群路由；`https://` 外链 `200`、`file:///C:/Windows/System32/calc.exe` 拦截 `400`。 | 捕获 3 类通知并唤醒跳转 `/chat/c_4frb8j`；外链 `200/400` 通过 | 捕获 3 类通知并唤醒跳转 `/chat/c_p9vena`；外链 `200/400` 通过 | —（JSON 回执核验通过） |
| **Phase 6 — Windows Named Pipe 本机轨迹直连与 Explorer 定位/脚本拦截** | 通过当前用户专属命名管道 `\\.\pipe\crewden-desktop-node-<24hex>` 建立 `/desktop/ws/trajectory` 本机直读连接（远端节点 `remote-ci` 自动回退 `mode: "remote"`）；验证工作区 `.md` 打开 `200`、小写盘符 `file:///c:/...` 资源管理器定位 `200`、`.bat` 脚本定位 `200`、`.bat` 直接运行 `403`、`..\` 越界 `403`。注：大体积 `>16 MiB` 输出端到端已在 M1 macOS 实测（`~19 MB`、`4.1 ms`），Windows 侧重点验证 Named Pipe ACL/忙重试握手与盘符大小写归一化。 | Named Pipe 直连握手 **`21.6 ms`**；工作区检查 `200/200/200/403/403` 全通过 | Named Pipe 直连握手 **`21.9 ms`**；工作区检查 `200/200/200/403/403` 全通过 | `M2/evidence/win10-03-work-trajectory-gui.png`、`win11-03-work-trajectory-gui.png` |
| **Phase 7 & 8 — `这台电脑` 首屏紧凑管理、`taskkill /F` 崩溃自愈、配置校验与热更新/回滚** | `/settings/nodes` 首屏同时呈现 `This computer` 与远端 `Team-Build-Server`；`taskkill /F` 强杀节点进程后由 `DesktopGatewayHost` 在锁过期后自动拉起新 PID 恢复 `ready = true`；`socks5://` 非法代理返回 `422`；完成 `1.0.0 -> 1.0.1` `0 B` runtime 复用升级与 `1.0.2-bad` 自动回滚。 | 强杀 PID `7092` -> 自愈恢复 PID `5100`；`422` 拦截、`0 B` runtime 升级与 `rolled_back` 通过 | 强杀 PID `12648` -> 自愈恢复 PID `4328`；`422` 拦截、`0 B` runtime 升级与 `rolled_back` 通过 | `M2/evidence/win10-04-nodes-admin-gui.png`、`win10-05-updated-101-gui.png`、`win11-04-nodes-admin-gui.png`、`win11-05-updated-101-gui.png` |
| **Step 2（第 1 次真实重启）— 默认开机静默托盘自启与免中断关闭自启** | 执行 `shutdown.exe /r` 重启 Windows 并自动登录 `nanoqa`：验证 `CrewdenDesktop.exe --background` 静默驻留托盘不弹窗（`window_focused = false`），受管节点自动上线并完成重启后真实问答 `"42"`；随后通过桌面 API 关闭 `autostart`，验证运行中节点 PID 不中断且 `HKCU\...\Run\CrewdenDesktop` 已移除。 | 静默自启 PID `6824`，回复 `"42"`，关闭自启 PID 零中断 | 静默自启 PID `8292`，回复 `"42"`，关闭自启 PID 零中断 | —（`step2-reboot-autostart-on.json`） |
| **Step 3（第 2 次真实重启）— 关闭自启后重启保持离线** | 再次执行 `shutdown.exe /r` 重启登录 `nanoqa` 并等待 25 秒：验证无任何 `CrewdenDesktop` / `DesktopGatewayHost` / `GatewayHost` 进程自启运行，IM 中节点保持 `offline`。 | `runningCrewdenProcesses = []`，`imNodeStatus = "offline"` | `runningCrewdenProcesses = []`，`imNodeStatus = "offline"` | —（`step3-reboot-autostart-off.json`） |

## 4. Windows 构建与单测套件记录

- `cargo test --manifest-path apps/desktop/Cargo.toml` & `cargo build --manifest-path apps/desktop/Cargo.toml --release`（Windows Server 2022 `x86_64-pc-windows-msvc` 原生编译与单测全绿）
- `node --test apps/node/tests/desktop-windows-host.test.mjs`（验证 `DesktopGatewayHost.exe` 独立计划任务/控制管道、崩溃恢复、`feat-781` `GatewayHost.exe` 同机并存与 `retire-standalone` 接管）
- `./packaging/desktop/windows/smoke.ps1`（精简系统 `PATH` 下静默安装 `Crewden-Desktop-Setup-x64.exe`、解包内置官方 Node `v24.22.1` 与 DSH 探针冒烟通过）
- **Stage 4 审查补丁与 Windows 候选流水线复验**：移除旧版 PowerShell AUMID 依赖，改用官方 `windows` WinRT `ToastNotificationManager`（固定注册 `WINDOWS_AUMID = "work.crewden.desktop"`、Inno Setup 快捷方式 `AppUserModelID: "work.crewden.desktop"` 与 `crewden-desktop://open?route=...` 协议激活，异常或系统策略禁用时回退右下角全透明圆角悬浮通知窗），并通过 `.github/workflows/desktop-candidate.yml` 双平台（`macos-arm64` + `windows-x64`）编译、安装器构建与冒烟复验。
