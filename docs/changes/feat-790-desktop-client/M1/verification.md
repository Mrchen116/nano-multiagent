# M1 Verification — macOS Apple Silicon (`arm64`) Crewden Desktop & Shared Workspace

## 1. 验收范围与真实运行环境

- **目标里程碑**：`M1` — `apps/desktop`（Tauri v2 常驻菜单栏/托盘宿主 + Loopback 能力门卫与 Auth Token Vault + 后台 `/im/ws/user` 通知守护进程 + 自崩溃恢复监督）、`apps/node`（`local-bridge` 本机 IPC 直连轨迹流 + `local-admin` 生命周期/接管/配置原子校验回滚 + Desktop 拆分归档热更新）、`apps/im-server`（双入口安装元数据与本机轨迹鉴权）、`src/IM/frontend`（双入口安装引导、`/login` 服务切换栏、零命令行绑定/接管/跨账号防护、`/settings/nodes` `这台电脑` 管理卡、本机直读轨迹与工具卡片文件打开/定位）以及 macOS `arm64` `Crewden.app` / `Crewden-Desktop-arm64.dmg` 自包含打包。
- **隔离运行拓扑**：
  - 全部真栈验收均在独立临时目录与 `./scripts/e2e-up.sh --profile daily` 隔离栈上完成；`Crewden.app` 以精简系统 `PATH="/usr/bin:/bin:/usr/sbin:/sbin"`、`--isolated-root` 启动，验证不依赖宿主机全局 `node` / `npm` / `pnpm`。
  - 保护路径前后快照核对：`~/Library/LaunchAgents` 条目数与时间戳完全一致（`launchAgentsIdentical = true`），`/Users/czj/.nanoassistant` 新增条目数为 `0`（`newNanoAssistantEntries = []`），临时目录与 `dist/node-release` 已在验收结束时完整回收。

## 2. 安装包体积、内置官方 Node 校验与热更新字节账单

| 产物 | 版本 | 字节大小 | SHA-256 | 说明 |
|---|---|---:|---|---|
| `Crewden-Desktop-arm64.dmg` | `1.0.0` | `89,092,913 B` (`84.97 MiB`) | `ab0fee07ec1c888bcf509349f156772a0cb4ed5c1a9501fb7c56ebdb81630123` | 含签名 `Crewden.app` + `seed-archives/` |
| `desktop-runtime-darwin-arm64.tar.gz` | `1.0.0` & `1.0.1` | `74,168,772 B` (`70.73 MiB`) | `b6ff31228477689b0ea007b0bf6ee9ac2dc5146a58d966602886ee7aa3b52947` | 内置 nodejs.org 官方 `SHASUMS256.txt` 校验的 `node-v24.22.1-darwin-arm64` + 锁定 DSH 依赖 + `pnpm@11.7.0`；跨小版本确定性构建 SHA-256 完全一致 |
| `desktop-app-darwin-arm64.tar.gz` | `1.0.0` | `7,110,493 B` (`6.78 MiB`) | `0d78500f436e704b18a0390a11947fe57e5fa4fb4613723e7565de7b03ad1a9d` | 节点应用代码 + `ui/frontend` + `ui/trajectory` |
| `desktop-app-darwin-arm64.tar.gz` | `1.0.1` | `7,110,513 B` (`6.78 MiB`) | `8abdd409ffa927076d92df2230d5f1803528061981a5e13827cf298e0dc3d510` | 纯应用/前端更新候选包 |

- **受管热更新字节账单（`1.0.0 -> 1.0.1`）**：
  - `/v1.0.1/desktop-darwin-arm64.json`：`748 B`
  - `/v1.0.1/desktop-app-darwin-arm64.tar.gz`：`7,110,513 B` (`6.78 MiB`)
  - `/v1.0.1/desktop-runtime-darwin-arm64.tar.gz`：**`0 B`**（命中本机 `desktop/runtimes/b6ff3122...` 缓存，`.desktop-active.json` 记录 `runtime_reused: true`）
  - 切换完成后 IM 节点在线版本为 `1.0.1`，宿主热重载静态资源 `/build-note.txt` 返回 `upgraded-1.0.1`。
- **损坏候选包回滚验证（`1.0.1 -> 1.0.2-bad`）**：
  - 注入启动失败的 `1.0.2` 应用归档触发受管更新，切换校验失败后自动回退至 `1.0.1`，IM 更新操作终态 `state = "rolled_back"`、`error_code = "start_failed"`，原版本 `1.0.1` 节点与前端资源保持在线可用。

## 3. 六阶段端到端真栈验收记录

本地截图证据按仓库规则保存在 gitignored 目录 `docs/changes/feat-790-desktop-client/M1/evidence/` 下供本地复查。

| 阶段 | 验证内容与关键断言 | 实测结果摘要 | 本地截图定位（gitignored） |
|---|---|---|---|
| **Phase 1 — Web 双入口安装引导** | `/onboarding` 在 `1280x860` 与 `390x844` 并排/纵向展示「下载完整 Desktop 客户端」与「仅装轻量后台节点」；Intel Mac 明确提示切至轻量节点；点击 `crewden-desktop://` 展示已发起态与回退下载；未发布 manifest 时诚实显示置灰提示且保留轻量节点可用；全视口 `scrollWidth === innerWidth` 无横向溢出。 | 4 态全部通过（`1280/1280`、`390/390`） | `M1/evidence/m1-web-onboarding-1280.png`、`m1-web-onboarding-390.png`、`m1-web-launched-390.png`、`m1-web-unpublished-390.png` |
| **Phase 2A — 精简 PATH 冷启动、零命令行绑定与真实 LLM 回复** | `Crewden.app --background` 在无全局 Node 的精简 PATH 下解包 `seed-archives`（实测内置 Node `v24.22.1`），静默后台驻留（`window_focused = false`）；`/login` 顶部栏完成双 IM 地址切换；新账号 `m1fresh` 应用内一键绑定 `computer-748b2e5b`（`1.0.0`），配置模型并创建个人助手，在会话 `c_t92tuv` 完成真实大模型问答。 | 真实 LLM 回复 `"42"` 通过 | `M1/evidence/m1-desktop-login-server-1280.png`、`m1-desktop-bind-fresh-1280.png`、`m1-desktop-chat-reply-1280.png` |
| **Phase 2B/2C — 跨账号保护与同账号 CLI 平滑接管** | 异账号 `m1bob` 登录检测到本机已有其他账号配置，`inspect` 仅返回 `foreign_owner`（不回显 `environment` / `logs`），`lifecycle` / `config` / `workspace/open` 均返回 `403`，未确认转移的 `connect` 返回 `409`；选择「仅使用聊天」后切回原 owner `nano`，一键平滑接管原独立 CLI 节点，旧进程退出、新受管进程以相同 `node_id` 上线，工作区文件完整保留。 | `403/403/403/409` 拦截与同 `node_id` 无损接管全部通过 | `M1/evidence/m1-desktop-foreign-owner-1280.png`、`m1-desktop-takeover-1280.png` |
| **Phase 3 — 常驻后台 `/im/ws/user` 通知、原生窗口唤醒、外链拦截与 `imOrigin` 隔离** | 主窗口未聚焦时，Rust 守护进程完成 `/im/ws/user` `resume` 握手并实时捕获群普通消息（`human_message`）、`@提及`（`mention`）与个人助手完成回复（`message_completed`），累计 `unread_total = 3`；触发通知唤醒原生 Tauri 窗口并准确路由至 `/chat/<group_id>` 与 `/settings/agents/daily-engineering?view=work`；外链点击经 `/desktop/v1/open-external` 安全拦截；切换两个 IM origin 后 `im-message-attempts::<origin>` IndexedDB 与草稿互不串库。 | 通知捕获、双路由唤醒、外链拦截与 IndexedDB 分库全部通过 | —（守护进程状态快照与 `open-actions.jsonl` 审计通过） |
| **Phase 4 — `>16 MiB` 本机直读轨迹与工具卡片路径动作** | 向本机 `daily-engineering` 发送真实任务读取 `reports/m1-summary.md`、`scripts/deploy.sh` 并运行脚本产生约 `19 MB` 标准输出（session `d679f502-99f4-4562-8bbb-2625169c4f3d`）；Work 原生轨迹切至 `/desktop/ws/trajectory` 本机 IPC 直连，状态栏显示 `本机直读 · 实时更新 · 只读`，直连握手耗时 **`4.1 ms`**；远端节点 `remote-ci` 自动回退 `mode: "remote"`；工作区文件校验 `.md` 打开 `200`、`.sh` 定位 `200`、`.sh` 直接打开 `403`、`../` 越界 `403`、工作区外软链 `403`。 | `4.1 ms` 本机直读建立、`>16 MiB` 完整可展开、`200/200/403/403/403` 路径边界全部通过 | `M1/evidence/m1-desktop-work-paths-1280.png`、`m1-desktop-trajectory-local-1280.png` |
| **Phase 5 & 6 — `/settings/nodes` `这台电脑` 渐进披露、免重启自启、`SIGKILL` 恢复与配置回滚** | `1280x940` 首屏同时可见紧凑态 `这台电脑` 与远端节点 `Team-Build-Server`（`top = 522px`）；切换「开机登录自启」开/关/开全程本机节点 `pid` 不变；对受管节点发送 `SIGKILL` 后桌面守护在锁过期后自动拉起新进程恢复 `ready = true`；`390x960` 窄窗填写非法 `socks5://` 代理触发 `422` 错误横幅并完整保留草稿，修正后保存重启写入生效且无横向溢出；随后完成 Phase 6 热更新与损坏包自动回滚。 | 渐进披露、免中断自启、崩溃自愈、配置回滚与热更新全部通过 | `M1/evidence/m1-desktop-nodes-compact-1280.png`、`m1-desktop-nodes-error-390.png`、`m1-desktop-update-available-1280.png` |

## 4. 自动化测试套件记录

- `pnpm build && pnpm typecheck && pnpm test`（覆盖 `@nano/product-contracts`、`@nano/im-server`、`@nano/node` 全部桌面本地管理、IPC 直连轨迹与热更新单测）
- `npm --prefix src/IM/frontend test -- --run` & `npm --prefix src/IM/frontend run build`（含 `src/IM/frontend/src/desktop/desktop-client.test.tsx` 等全部前端套件）
- `pytest -m "not e2e"`（含 `tests/contract/test_runtime_dependency_contract.py` 跨包依赖红线契约）
- `cargo test --manifest-path apps/desktop/Cargo.toml`（覆盖深链协议安全解析、`/im/ws/user` 四类通知分类与免打扰/焦点抑制、能力 Cookie/Origin 门卫、JTI 串行轮换锁、上游 `503` 保态与静态 UI 热切换）
