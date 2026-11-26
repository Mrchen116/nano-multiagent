# feat-790: Crewden Desktop 桌面客户端（V1） — Design Review

## Round 1

### Metadata

- **reviewer**: `change-design-reviewer` + `frontend-experience-review`（设计模式，独立审查会话 `5259af1d-20e6-4041-afc3-f3a19309c44d`）
- **target**: `docs/changes/feat-790-desktop-client`（`spec.md`、`design.md`、`prototype.html`、`design-evidence/*.png`、`specs/im/desktop-client.md`、`specs/im/agents-nodes.md`、`specs/im/agent-work.md`、`specs/gateway/service-lifecycle.md`、`M1/`、`M2/`）
- **review_mode**: `full`
- **mode_reason**: Round 1 首次 Gate 2 独立全量设计审查，需完整核实现状断言、跨包职责与安全隔离边界、前端原型与多视口体验、delta-specs 闭合及里程碑拆分。
- **started_at**: `2026-11-25T20:59:04+09:00`
- **completed_at**: `2026-11-25T21:18:50+09:00`
- **duration**: `19m46s`

### Verdict

**Issues Found** — `3 CRITICAL / 5 WARNING`（另有 `2 Recommendations` 可选建议）

---

### Coverage 与证据

#### 1. 现状断言与产品组装入口核实

从仓库实际生产组装入口逐项核对了 `design.md` 的现状声明与改动落点：

- **跨包依赖与运行时边界**：核对 [`SPEC.md`](../../../SPEC.md) 与 [`tests/contract/test_runtime_dependency_contract.py`](../../../tests/contract/test_runtime_dependency_contract.py)（L13-L94）。当前仅 `packages/dsh-integration`、`packages/dsh-trajectory-viewer`、`packages/trajectory-ui` 允许导入公开 `@deepseek-ai/*`；`apps/desktop` 不直接导入 DSH、`personal-assistant` 或 `channels`，并将自身 TypeScript 辅助源码纳入 `ALLOWED` 白名单（仅依赖 `@nano/product-contracts`）符合架构红线。
- **IM 会话同源门禁与原生令牌通道**：核对 [`apps/im-server/src/identity-routes.ts`](../../../apps/im-server/src/identity-routes.ts)（L14、L37-L58、L84-L101）与 [`apps/im-server/src/server.ts`](../../../apps/im-server/src/server.ts)（L98-L139、L231-L234）。携带 `X-IM-Session: browser` 时强制校验 `Origin` 白名单并使用 `SameSite=Strict; HttpOnly` Cookie；省略 `X-IM-Session: browser` 时确已原生支持 JSON `{ access_token, refresh_token, user }` 登录/刷新/登出。桌面宿主在出站侧走非浏览器 JSON 令牌会话、入站侧在 `127.0.0.1` 提供同源代理的总体方向成立。
- **发布清单、安装材料与受管更新状态机**：核对 [`packages/product-contracts/src/node-update.ts`](../../../packages/product-contracts/src/node-update.ts)、[`apps/im-server/src/install.ts`](../../../apps/im-server/src/install.ts)、[`apps/im-server/src/node-updates.ts`](../../../apps/im-server/src/node-updates.ts)、[`apps/node/src/update-worker.ts`](../../../apps/node/src/update-worker.ts)、[`packaging/windows-host/GatewayHost.cs`](../../../packaging/windows-host/GatewayHost.cs) 与 [`packaging/windows/Launcher.cs`](../../../packaging/windows/Launcher.cs)。发现 Windows 激活指针 `.windows-active.json` 与 Desktop/Node 三段归档更新切换存在实质未闭合冲突（见 `R1-C3`）。
- **本机节点配置、设备绑定与生命周期**：核对 [`apps/node/src/bootstrap.ts`](../../../apps/node/src/bootstrap.ts)、[`apps/node/src/device-binding.ts`](../../../apps/node/src/device-binding.ts)、[`apps/node/src/configuration.ts`](../../../apps/node/src/configuration.ts)、[`apps/node/src/lifecycle.ts`](../../../apps/node/src/lifecycle.ts) 与 [`apps/node/src/main.ts`](../../../apps/node/src/main.ts)。发现跨账号本机归属隔离与 `bindDevice(..., { auto: true })` 静默跳过整机转移确认的安全漏洞（见 `R1-C2`），以及代理环境变量映射、空节点 `tool_approval_model` 校验和 macOS 在线切换 `autostart` 的实现缺口（见 `R1-W3`）。
- **原生轨迹与附件授权链路**：核对 [`apps/im-server/src/trajectory.ts`](../../../apps/im-server/src/trajectory.ts)、[`apps/im-server/src/work-records.ts`](../../../apps/im-server/src/work-records.ts)、[`apps/node/src/trajectory.ts`](../../../apps/node/src/trajectory.ts)、[`packages/dsh-integration/src/trajectory.ts`](../../../packages/dsh-integration/src/trajectory.ts)、[`packages/dsh-integration/src/trajectory-attachments.ts`](../../../packages/dsh-integration/src/trajectory-attachments.ts) 与 [`packages/dsh-trajectory-viewer/src/transport.ts`](../../../packages/dsh-trajectory-viewer/src/transport.ts)。复用隔离 `/trajectory/` iframe + `MessagePort` + 附件按 `workspace`/`chat` 来源分级校验的设计成立，但中心 `/trajectory/authorize` 沿用 `work.session` 查询会在 `>16 MiB` 阻断同步后误拒子执行（见 `R1-W1`）。
- **前端会话、本地存储与通知链路**：核对 [`auth-session.ts`](../../../src/IM/frontend/src/features/auth/auth-session.ts)、[`providers.tsx`](../../../src/IM/frontend/src/app/providers.tsx)、[`chat-local-db.ts`](../../../src/IM/frontend/src/features/chat/chat-local-db.ts)、[`composer-draft-store.ts`](../../../src/IM/frontend/src/features/chat/components/composer-draft-store.ts)、[`use-global-message-toast.ts`](../../../src/IM/frontend/src/features/chat/hooks/use-global-message-toast.ts) 与 [`agent-completion-notifier.tsx`](../../../src/IM/frontend/src/features/notifications/agent-completion-notifier.tsx)。发现关窗/静默自启后的通知生产者矛盾与通知类型缺漏（见 `R1-C1`），以及随机回环端口破坏 `IndexedDB`/`localStorage` 跨重启持久性与多服务隔离的问题（见 `R1-W2`）。
- **Agent Context 影响核查**：本需求不修改系统提示词、工具 schema、Skill 注入、记忆或上下文裁剪恢复逻辑，无需触发 `agent-context-review` 的判断成立。

#### 2. 架构职责与复用判断

- **合理且应保留的架构选择**：
  1. 以 Tauri v2 原生壳 + 本地 `127.0.0.1` 同源网关 + `HttpOnly; SameSite=Strict` 能力 Cookie 承载既有 `src/IM/frontend` SPA，对比改造远端 IM CORS 或重写全部前端图片/附件/WS 调用，维护代价最低且不削弱存量 IM 安全边界。
  2. 共享 `~/.nanoassistant/connections/<origin-hash>/config.yaml` 与 `proper-lockfile` 配置锁，同时保持 Windows 安装目录（`%LOCALAPPDATA%\CrewdenDesktop`）与协议（`crewden-desktop://`）同 `feat-781` 独立，避免再造第二套节点身份目录。
  3. 轨迹直读继续复用 `@nano/dsh-trajectory-viewer` 沙箱 iframe 与 `MessagePort`，由父窗口切换底层传输，不维护第二套轨迹 UI。
  4. 本机工作区打开先经 `realpath` 限定在工作区根内并拦截可执行脚本后缀直接运行，安全边界清晰。
- **职责尚未收口之处**：
  - 后台常驻期的用户实时事件订阅与系统通知触发归属（Rust 宿主直连用户事件流 vs 常驻隐藏 WebView）自相矛盾（`R1-C1`）；
  - 本机节点单实例共享目录与 Desktop 多账号登录之间的所有权校验缺失（`R1-C2`）；
  - Desktop 宿主版本激活指针与 `apps/node` `update-worker` 的跨进程协调缺失（`R1-C3`）。

#### 3. 前端体验与原型审查（`frontend-experience-review` 设计模式）

- **原型范围判断**：本次包含 Web 双入口选择、Desktop 登录服务栏与绑机/接管引导、「这台电脑」图形化配置面板、本机轨迹状态与工作区打开 4 处高耦合布局与交互决定，建立 [`prototype.html`](prototype.html) 必要且范围恰当；顶部深色演示控制栏与下方产品区域区分清楚，Toast 采用 `position: fixed` 不挤动表单控件坐标。
- **实际画面独立观察结论**（已逐张查看 [`baseline-onboarding.png`](design-evidence/baseline-onboarding.png)、[`web-onboarding-1280.png`](design-evidence/web-onboarding-1280.png)、[`web-onboarding-390.png`](design-evidence/web-onboarding-390.png)、[`desktop-bind-takeover-1280.png`](design-evidence/desktop-bind-takeover-1280.png)、[`desktop-local-admin-1280.png`](design-evidence/desktop-local-admin-1280.png)、[`desktop-local-admin-error-390.png`](design-evidence/desktop-local-admin-error-390.png)、[`desktop-local-work-1280.png`](design-evidence/desktop-local-work-1280.png)）：
  - **通过项**：Web 首次连接电脑页（`1280` / `390`）延续暖黄左栏 + 白色主卡风格，「下载完整 Desktop 客户端」与「仅装轻量后台节点」主次分明，窄屏单列排布自然无溢出；Desktop 登录服务地址栏与接管确认卡信息精炼、保留项与后果表达清楚。
  - **需修订项（`fail`，见 `R1-W4`）**：①「这台电脑」卡片丢掉了原电脑卡片承载的**检查更新/升级面板（`NodeUpdatePanel`）**、电脑改名与新建助手入口，且把所有低频配置项与运行日志默认全量展开，并在 `390px` 下环境变量行缺少行级分组边界；② Work 视图虚构了真实产品没有的左侧「本轮关联工作区路径」栏并标为 `must-match`，却未定义真实聊天消息与工具卡片中工作区路径的打开交互；③ 桌面顶栏多出了真实 [`AppShell`](../../../src/IM/frontend/src/app/shell/app-shell.tsx) 不存在的第 4 个一级导航项 `电脑`，且缺少现有 `/settings/nodes` 与 `Agent Work` 基线对照。

#### 4. Delta-Specs、一次性迁移与 Milestones 核查

- **Delta-Specs 锚定与保留性**：
  - `specs/im/desktop-client.md`（ADDED，5 条 Requirement）覆盖 `spec.md` 全部验收场景；归并时按 `design.md` L253 补齐 `Purpose`、`> 对齐: feat-790` 并登记至 `docs/specs/im/spec.md` `Canonical Areas`。
  - `specs/im/agents-nodes.md`（MODIFIED，2 条 Requirement）完整保留原有 4 + 2 个 Scenario，新增双入口并存条款未误伤既有 CLI 或 Windows 轻量安装实现。
  - `specs/im/agent-work.md`（MODIFIED，1 条 Requirement）保留全部既有 Scenario，但第 7 行 `../../../../specs/im/ios-client.md` 存在归并后越出仓库根导致 `docs-check` 失败的相对路径问题（见 `R1-W5`）。
  - `specs/gateway/service-lifecycle.md`（ADDED，1 条 Requirement）锚定正确。
- **一次性部署迁移**：无生产库表破坏性变更或历史状态强迁移，不设 `deployment-prompt.md` 结论正确。
- **Milestones 与 Runbook 核查**：M1（macOS `arm64` 全功能闭环）→ M2（Windows 10/11 `x64` 安装包、并存接管与发布闭环）纵向拆分合理，但 M1 `[reviewer]` 漏掉了 macOS 受管更新验收（`R1-C3`），且 M1 隔离启动命令与打包构建在开发机 `air`（存在受保护 `~/.nanoassistant` 且系统 Node 为 `v25.8.2`）上存在隔离逃逸与版本误用风险（`R1-W5`）。

---

### 历史问题闭环

Round 1 首次审查，无历史遗留问题。

---

### Issues

#### `R1-C1` [CRITICAL] 关窗释放视图/静默登录自启与前端驱动通知架构自相矛盾，且缺失真人消息、`@提及` 与工具权限审批通知及跳转路由

- **位置**：
  - [`design.md`](design.md) 关键决策 1（L77）、关键决策 5（L94）、第 4 节 `/desktop/v1/notifications`（L180、L188）、涉及范围（L15）
  - 对照需求：[`spec.md`](spec.md) L119-L123、L138-L141；[`specs/im/desktop-client.md`](specs/im/desktop-client.md) L32-L36、L50-L54
- **证据**：
  1. `design.md` L77 与 L94 规定关闭主窗口后“释放窗口视图 / 仅保留轻量原生托盘进程”，且登录自启以 `--background` 静默驻留托盘（不打开主窗口），但第 4 节（L180、L188）将系统通知和 Dock/任务栏未读数设计为由携带 `__crewden_desktop_cap` Cookie 的主窗口前端调用 `POST /desktop/v1/notifications`。当 `--background` 冷启动尚未建窗、或关窗释放 WebView（即便仅 `hide()`，macOS WKWebView App Nap 与 Windows WebView2 也会挂起后台页面定时器与连接）时，前端 [`useGlobalMessageToast`](../../../src/IM/frontend/src/features/chat/hooks/use-global-message-toast.ts)（L198-L237）根本未运行或已被冻结，无法产生任何通知或角标更新。
  2. 现行前端 [`AgentCompletionNotifier`](../../../src/IM/frontend/src/features/notifications/agent-completion-notifier.tsx)（L102-L134）与 [`reduceAgentCompletionEvent`](../../../src/IM/frontend/src/features/notifications/agent-completion-accumulator.ts)（L79-L119）仅对 Agent 回复完成事件（`message.completed`）发送通知：真人消息与 `@提及`（`message.created` + `sender_type === "user"`）在 [`use-global-message-toast.ts`](../../../src/IM/frontend/src/features/chat/hooks/use-global-message-toast.ts)（L289-L297）只渲染页内浮层 `InAppToast`，而聊天待决工具权限（[`canonical-event.ts`](../../../src/IM/frontend/src/realtime/user-stream/canonical-event.ts) L167 `permission.request`）与 Global Agent Work 待决权限（`waiting_permission` / `agent.work.updated`）完全没有接入通知管道，也未定义点击系统通知唤醒窗口后定位到目标聊天或待审批入口的路由协议。
- **未修后果**：
  - 开机静默自启后或关闭主窗口期间，后台无法弹出系统通知或更新未读角标；即便主窗口挂载，收到真人 `@提及` 或待确认的工具权限请求时也不会触发系统原生通知与点击直达，直接违反 `spec.md` 第 2、3 条核心验收要求。
- **收口要求**：
  - 明确唯一一致的后台事件消费与通知产生者（例如由常驻 Rust 宿主凭已保存的当前活跃会话在后台维护 `/im/ws/user` 订阅、未读计数与系统通知，并在点击通知时创建/恢复窗口导航至目标路由；或明确保留隐藏常驻 WebView 且禁用后台挂起并解决 `--background` 冷启动加载），同时完整覆盖未静音新消息、`@提及` 与聊天/Work 待决工具权限请求及其点击跳转目标路由。

---

#### `R1-C2` [CRITICAL] 本机节点检查、接管绑机、配置/日志管理与工作区文件打开缺少当前登录账号归属隔离，`auto` 绑机会静默触发整机转移

- **位置**：
  - [`design.md`](design.md) 可复用能力（L29）、关键决策 4 / 7 / 8（L90、L102、L106）、时序图（L129-L140）、第 4 节 `/desktop/v1/local-node/*` 与 `/desktop/v1/workspace/open`（L189-L194）
  - 对照需求与契约：[`spec.md`](spec.md) L102-L106、L143-L146、L162-L166；[`docs/specs/im/agents-nodes.md`](../../specs/im/agents-nodes.md) L429-L433、L826
- **证据**：
  1. [`apps/node/src/bootstrap.ts`](../../../apps/node/src/bootstrap.ts)（L16-L17）生成的 `~/.nanoassistant/connections/<origin-hash>/config.yaml` 仅按 `imOrigin` 哈希区分，不按登录账号隔离。当账号 A 在本机完成绑定后退出、同机登录同一 IM 服务的账号 B 时，`GET /desktop/v1/local-node/inspect`（L130、L189）仅按 `--origin <imOrigin>` 读取本地配置与日志，未校验当前登录用户 `owner_id` 是否等于 `config.node.user_id`，会将账号 A 的环境变量（含潜在第三方密钥）、`gateway.log` 及节点启停/改配能力直接暴露给账号 B。
  2. `POST /desktop/v1/local-node/connect`（L29、L135、L190）计划复用 [`apps/node/src/device-binding.ts`](../../../apps/node/src/device-binding.ts) 的 `auto` 分支实现应用内一键确认。但现行 `device-binding.ts` L154 与 L185 将“免打开外部浏览器自动 `accept`”与“跳过整机转移本地二次确认（`if (transfer && !options.auto && ...)`）”绑在同一个 `options.auto` 布尔值上——若本机连接目录已绑定账号 A（或已有 Agent），账号 B 调用该接口会**不经任何整机转移提示静默夺取设备及全部 Agent 所有权**，违反 `agents-nodes.md` 整机交接双端明确确认契约。
  3. `POST /desktop/v1/workspace/open`（L106、L194）仅校验 `__crewden_desktop_cap` Cookie 与 `realpath` 位于本机某 Agent `workspace_root` 内，未核验当前 Desktop 登录会话的身份是否拥有该本机节点或具备目标 Agent 的有效访问权，切换至无权限账号后仍可打开原主人私人 PA 工作区内的文件。
- **未修后果**：
  - 同机切换账号时泄露上一账号的本机环境变量与运行日志、越权打开私人 PA 本地工作区文件，甚至在未确认整机转移的前提下静默转移设备与全部助手归属。
- **收口要求**：
  - 在 `/desktop/v1/local-node/*` 与 `/desktop/v1/workspace/open` 中强制绑定当前 `(imOrigin, userId / ownerId)` 权限核验：当本机 `config.node.user_id` 已绑定其他账号时，禁止向非归属账号暴露 `gateway.environment` 明文、运行日志、生命周期修改与工作区文件打开；将 `bindDevice` 的“应用内会话令牌确认”与“整机设备转移显式二次确认”拆开，仅原所属账号可执行无缝接管，跨账号必须走显式整机转移确认或只连接远端聊天而不接管本机节点。

---

#### `R1-C3` [CRITICAL] 三段式受管更新与 Windows `feat-781` 并存/接管在版本激活指针、桌面宿主切换及 M1 验收覆盖上未闭合

- **位置**：
  - [`design.md`](design.md) 可复用能力（L34-L36）、关键决策 1 / 4（L77、L90）、第 2 节发布清单与受管更新（L157-L163）、Milestones M1/M2（L291-L292）
  - 对照实现：[`packaging/windows-host/GatewayHost.cs`](../../../packaging/windows-host/GatewayHost.cs)（L23-L24、L180-L199）、[`packaging/windows/Launcher.cs`](../../../packaging/windows/Launcher.cs)（L134-L164）、[`apps/node/src/lifecycle.ts`](../../../apps/node/src/lifecycle.ts)（L374-L380）、[`apps/node/src/update-worker.ts`](../../../apps/node/src/update-worker.ts)（L19-L59、L127-L185）、[`apps/im-server/src/node-updates.ts`](../../../apps/im-server/src/node-updates.ts)（L15-L60）
- **证据**：
  1. **Windows 共享连接目录下的 `.windows-active.json` 指针冲突**：在已安装 `feat-781` 轻量后台节点的 Windows 电脑上，`connections/<hash>/.windows-active.json` 存的是 `windows-x64.json` 的 SHA-256（对应 `%LOCALAPPDATA%\Crewden\versions\<sha>`）。当 Desktop（`%LOCALAPPDATA%\CrewdenDesktop`）接管该连接目录并复用 `GatewayHost` 启动时，`GatewayHost.SelectedPackage`（`GatewayHost.cs` L182-L198）会读取既有 `.windows-active.json` 去 `%LOCALAPPDATA%\CrewdenDesktop\versions\<win32-x64-sha>` 查找 `.ready`，必然因平台包 SHA 与根目录不同而报错退出；反之若直接把 `.windows-active.json` 覆写为 `desktop-win32-x64` 的 SHA，并存保留的开始菜单 `Crewden.lnk`（`Launcher.cs` L158-L164）枚举该文件时又会因 `%LOCALAPPDATA%\Crewden\versions\` 下不存在该 SHA 而报错，破坏“两套安装器并存互不破坏”的约束。
  2. **三段归档（`shell` + `runtime` + `app`）更新未闭合到运行中的 Desktop 宿主**：`design.md` L162 将前端 `dist`、轨迹查看器 `dist` 打入 `app` 归档，将 Tauri 原生壳打入 `shell` 归档，但受管更新由 `apps/node` 拉起的 [`update-worker.ts`](../../../apps/node/src/update-worker.ts) 执行，该 worker 仅负责停止/启动后台 `apps/node`（且非 Windows 分支 L20/L128/L176 现仍写死 `nano-node.tgz`、`pnpm install` 与旧 `process.execPath`）。方案未说明：
     - 常驻运行的 Desktop Rust 宿主从何处读取当前连接（及多服务切换下不同版本连接）对应的激活 `app` 归档路径，并在 `update-worker` 完成切换后热更新所挂载的前端 `dist` 与 `/trajectory/` 静态资源；
     - 当新版本的 `shell` 归档哈希（或 `shell_protocol`）发生变化时，macOS 在“不改写 `.app` 签名包体避免 TCC 失效”（L77）前提下、Windows 在 `CrewdenDesktop.exe` 进程占用可执行文件前提下，如何完成原生 `shell` 切换或精确拒绝伪报 `succeeded`（目前 `node-updates.ts` L15 仅比对 `apps/node` 上报的顶层 `manifest.sha256`）。
  3. **M1 验收遗漏 macOS 受管更新**：[`spec.md`](spec.md) L131-L135 要求双平台支持受管更新与失败回退，M1 范围已包含 `node-update.ts`、`node-updates.ts`、`update-worker.ts` 与 `build-desktop-archives.py`，但 `design.md` M1 `[reviewer]`（L291）未纳入 macOS `arm64` 受管更新复用 `runtime` 缓存及失败回滚的真实端到端验收。
- **未修后果**：
  - Windows 接管 `feat-781` 节点立即因版本目录指针不匹配崩溃或破坏原轻量启动器；双平台升级后出现“后台 Node 已升新版、前台 Web 界面和原生壳仍停在旧版却显示升级成功”的版本撕裂；macOS 受管更新未经 M1 产品验收。
- **收口要求**：
  - 为 Desktop 受管节点定义与 `feat-781` 互不踩踏的激活版本元数据与接管迁移规则；明确 `update-worker` 与常驻 Desktop 宿主之间同步切换 `app`/`runtime`（及 `shell` 变更时的可落地方案或协议边界）的完整机制；在 M1 `[reviewer]` 退出标准补齐 macOS `arm64` 受管更新与回退验收。

---

#### `R1-W1` [WARNING] IM `/trajectory/authorize` 沿用中心 `work.session` 查询，会在 `>16 MiB` 事件阻断同步后误拒本机子执行/fork 轨迹直读

- **位置**：
  - [`design.md`](design.md) 关键决策 6（L98）、第 3 节 `POST /im/v1/agents/:agent_id/trajectory/authorize`（L171-L175）
  - 对照需求与实现：[`spec.md`](spec.md) L150-L154；[`apps/im-server/src/trajectory.ts`](../../../apps/im-server/src/trajectory.ts)（L70-L75）；[`apps/im-server/src/work-records.ts`](../../../apps/im-server/src/work-records.ts)（L92-L95）；[`docs/specs/im/agent-work.md`](../../specs/im/agent-work.md)（L201-L205）；[`packages/dsh-integration/src/trajectory.ts`](../../../packages/dsh-integration/src/trajectory.ts)（L57-L75）
- **证据**：
  - 按 `docs/specs/im/agent-work.md` L201-L204（`perf-754`），当单条事件超过 16 MiB 时，`WorkSync` 返回 `event_too_large`，**该条及后续所有 Work 记录均保留在本机待处理，不会写入中心 IM 数据库**。
  - `design.md` L174 规定 `/im/v1/agents/:agent_id/trajectory/authorize` 执行与 `TrajectoryObservers.create()` 完全相同的 `work.session` 根范围校验。而 `TrajectoryObservers.create()`（`apps/im-server/src/trajectory.ts` L70-L74）依赖中心 IM 的 `agent_work_sessions` 表查询 `session_id` 及其父链。一旦主执行在产生 `>16 MiB` 工具输出后继续派生子 Agent / fork（或 `WorkSync` 尚在补传中），中心 IM 库中并不存在该子执行的 `session_id`，用户在原生轨迹视图点击「进入本次执行 ›」触发 `authorize` 时会被中心直接返回 `404 该执行不可访问`。
  - 同时，本机 [`apps/node/src/main.ts`](../../../apps/node/src/main.ts)（L432-L437）与 [`NativeTrajectory.prepare`](../../../packages/dsh-integration/src/trajectory.ts)（L58-L70）已具备从本机 `store.bindings()` 解析 `global:${agentId}` 根会话并沿原生持久 `parentSession` 链核验非 `worker` 子执行归属的完整权威能力。
- **未修后果**：
  - 在出现 `>16 MiB` 大体积输出（本方案核心动机场景）或同步延迟时，本机 Agent 后续关联子执行/fork 的原生轨迹直读失败。
- **收口要求**：
  - 调整中心 `/trajectory/authorize` 与本机 `local.trajectory.prepare` 的职责切分：中心负责核验当前用户对该 `agent_id` 的空间/PA 访问资格、未删除状态（含针对传入 `session_id` 的 `rejectDeletedExecution`）及目标节点绑定归属（`nodeId`、`ownerId`、`nodeEpoch`），不强求未同步的子执行 `session_id` 已出现在中心 `agent_work_sessions`；根会话绑定与原生 `parentSession` 祖先链校验由本机 `apps/node` + `NativeTrajectory.prepare` 闭环执行，并明确本地 IPC / `WS /desktop/ws/trajectory` 对 `>16 MiB` 载荷的分片（复用 `encodeTrajectoryValue`）或无上限帧配置。

---

#### `R1-W2` [WARNING] 每次启动随机分配 `127.0.0.1:<ephemeral>` 端口及切服清库策略会丢失本地未确认发送记录或造成同源多服务串台

- **位置**：
  - [`design.md`](design.md) 关键决策 2 / 3（L81-L87）、第 4 节 `PUT /desktop/v1/server`（L187）
  - 对照实现：[`chat-local-db.ts`](../../../src/IM/frontend/src/features/chat/chat-local-db.ts)（L4-L10）、[`send-attempt-store.ts`](../../../src/IM/frontend/src/features/chat/components/send-attempt-store.ts)（L63-L84）、[`composer-draft-store.ts`](../../../src/IM/frontend/src/features/chat/components/composer-draft-store.ts)（L55-L64）、[`providers.tsx`](../../../src/IM/frontend/src/app/providers.tsx)（L24-L37）
- **证据**：
  1. 浏览器 WebView 的 `IndexedDB` 与 `localStorage` 严格按 `(scheme, host, port)` 分区。`design.md` L81 使用随机临时端口 `127.0.0.1:<ephemeral>`，意味着每次重启 Desktop 后端口号变化，前端写入 `IndexedDB`（`im-message-attempts` 中的未确认消息恢复记录与交互卡片离开水位线）和 `localStorage`（首次引导进度 `nano-onboarding:${userId}`、语言和通知开关）全部失联失效。
  2. 现行前端存储层明确以浏览器 `origin` 作为不同 IM 服务的隔离边界（`chat-local-db.ts` L4-5），且 [`AppProviders`](../../../src/IM/frontend/src/app/providers.tsx)（L26-L36）仅在 `userId` 变化时清理缓存与草稿。在 Desktop 单一本地宿主同时代理多个 `imOrigin` 时，若按 L85 在切换服务时直接清空 WebView 存储，会误删用户在原服务上待恢复的未确认发送记录；若不清库且未将 `imOrigin` 纳入 `IndexedDB` / `localStorage` / 内存草稿键及切服页面重载契约，不同自建 IM 服务上相同 `userId`（例如两套本地/测试栈的预设账号）会发生草稿、水位线与缓存串台。
- **未修后果**：
  - Desktop 重启后丢失未确认发送恢复状态与用户界面偏好；多服务切换时破坏原服务持久恢复保证或发生跨服务数据污染。
- **收口要求**：
  - 保证同一 `imOrigin` 跨重启拥有稳定且按服务隔离的本地存储命名空间（例如前端存储键与 IndexedDB 库名在桌面模式下纳入当前 `imOrigin`，或采用 Tauri 按服务隔离的自定义协议/子域 scheme，并在 `PUT /desktop/v1/server` 切换时执行完整文档重载 + `context_epoch` 断流，只清理退出账号对应范围而非跨服务抹除其他有效服务的持久发送记录）。

---

#### `R1-W3` [WARNING] 「这台电脑」配置管理与现行 `NodeConfiguration` / macOS `lifecycle` 存在代理映射、空节点审批模型校验、macOS 免重启改自启及 Worker `PATH` 探测缺口

- **位置**：
  - [`design.md`](design.md) 关键决策 5 / 7（L94、L101-L103）、第 4 节 `/desktop/v1/local-node/lifecycle` 与 `/config`（L191-L192）
  - 对照需求与实现：[`spec.md`](spec.md) L175-L181；[`apps/node/src/configuration.ts`](../../../apps/node/src/configuration.ts)（L21-L29、L90-L106）；[`apps/node/src/lifecycle.ts`](../../../apps/node/src/lifecycle.ts)（L178、L235-L259、L286-L290）；[`docs/operations/gateway.md`](../../operations/gateway.md)（L92-L106）
- **证据**：
  1. **代理配置存储映射与双写冲突**：`NodeConfigurationFile` 无独立代理字段，实际运行时依赖 `gateway.environment` 中的 `NODE_USE_ENV_PROXY="1"` 与大小写成对的 `HTTP_PROXY`/`http_proxy`、`HTTPS_PROXY`/`https_proxy`、`ALL_PROXY`/`all_proxy`、`NO_PROXY`/`no_proxy`，且 DSH 不支持 `socks://`（见 `gateway.md` L94-L106）。方案未定义「网络代理」表单与下方「本机运行环境变量」表格之间的读写归一与屏蔽规则，也未声明拒绝非 `http(s)://` 代理 URL。
  2. **空节点 `tool_approval_model` 漏检**：[`configuration.ts`](../../../apps/node/src/configuration.ts) L102-L106 仅在 `runtime(agent)` 中校验 `llm.tool_approval_model` 是否已注册；当节点刚绑定、尚无 Agent（`agents: []`）时，非法 `tool_approval_model` 会跳过校验直接落盘。
  3. **macOS 切换登录自启的运行态冲突**：[`spec.md`](spec.md) L177 与原型均将「开机登录自启」作为免重启即时生效开关，但 [`lifecycle.ts`](../../../apps/node/src/lifecycle.ts) L286-L287 的 `autostart-on` / `autostart-off` 在非 Windows 平台直接抛出 `Windows login task required`，而调用 `restart` 又会中断正在执行的本机任务。
  4. **Worker 探测未使用候选 `PATH`**：原型引导用户在下方环境变量添加 `PATH` 以发现 `claude` / `codex`（`prototype.html` L1134），但 `design.md` 未规定 `local-admin` 按合并后的默认服务 `PATH` + `gateway.environment.PATH` 执行探测与保存前可用性核对。
- **未修后果**：
  - 代理设置与环境变量列表互相覆盖或保存无效 SOCKS 代理；空节点写入非法审批模型；macOS 在线开关登录自启直接报错或意外杀掉运行中任务；自定义目录安装的 `codex`/`claude` 无法被探测识别。
- **收口要求**：
  - 明确代理表单与 `gateway.environment` 9 个标准代理键的双向映射及 `http(s)://` 协议校验；在 `local-admin` 配置预检中无条件校验 `llm.tool_approval_model`（即使 `agents` 为空）并结合候选 `gateway.environment.PATH` 探测 Worker；补齐 macOS 在不中断当前运行任务前提下切换 `gateway.autostart`、`LaunchAgent` 持久定义与桌面登录项的协同流程。

---

#### `R1-W4` [WARNING] 前端原型与现有产品结构存在三处实质偏差：「这台电脑」丢失受管更新与改名入口且全量展开过重、Work 虚构无数据源的左侧路径栏而漏掉真实文件入口、全局主导航不一致

- **位置**：
  - [`design.md`](design.md) 前端原型（L204-L240，含 L220-L225 `must-match` 表）；[`prototype.html`](prototype.html)（L1175-L1430）；截图 [`desktop-local-admin-1280.png`](design-evidence/desktop-local-admin-1280.png)、[`desktop-local-admin-error-390.png`](design-evidence/desktop-local-admin-error-390.png)、[`desktop-local-work-1280.png`](design-evidence/desktop-local-work-1280.png)
  - 对照现有实现与契约：[`spec.md`](spec.md) L80、L131-L135、L162-L166；[`nodes-page.tsx`](../../../src/IM/frontend/src/features/settings/nodes/nodes-page.tsx)（L80-L90）；[`node-details.tsx`](../../../src/IM/frontend/src/features/settings/nodes/node-details.tsx)（L28-L50）；[`app-shell.tsx`](../../../src/IM/frontend/src/app/shell/app-shell.tsx)（L44-L52）；[`agent-profile-page.tsx`](../../../src/IM/frontend/src/features/settings/agents/agent-profile-page.tsx)（L88-L90）；[`tool-detail-renderers.tsx`](../../../src/IM/frontend/src/features/chat/components/tool-detail-renderers.tsx)；[`docs/specs/im/agents-nodes.md`](../../specs/im/agents-nodes.md)（L936-L946）
- **证据（画面事实 → 用户影响）**：
  1. **「这台电脑」遗漏核心操作且信息密度失衡**：在 [`desktop-local-admin-1280.png`](design-evidence/desktop-local-admin-1280.png) 与 [`desktop-local-admin-error-390.png`](design-evidence/desktop-local-admin-error-390.png) 中，置顶的 `Air-Studio 这台电脑` 卡片替换了原 `NodesPage` 电脑卡，却**遗漏了 `NodeUpdatePanel`（检查更新/一键升级/取消与回退恢复——对应 `spec.md` L80 与 L131-L135 的受管更新入口）、电脑改名以及在该电脑新建助手入口**；同时将 Worker 选择、代理三输入框、环境变量动态行与深色日志框全部默认平铺展开（单卡高度超 900px，将其他远端电脑挤出首屏，违背 `agents-nodes.md`“优先显示名称、可用性、现用版本及可执行动作，按需展开管理操作”）。此外，在 `390px` 窄屏（`desktop-local-admin-error-390.png`）下，环境变量行的内部间距与行间距同为 `8px` 且无分组框/分隔线，导致第一行 `移除` 按钮视觉上夹在上一行值与下一行 `PATH` 变量名正中间，极易误删；报错演示态的错误文案写死 `http://127.0.0.1:9999` 与上方输入框显示的 `http://127.0.0.1:7890` 不一致；`spec.md` L80 要求的日志搜索过滤也未在日志区提供。
  2. **本机工作区文件打开错放在虚构侧栏，漏掉真实聊天与工具过程入口**：在 [`desktop-local-work-1280.png`](design-evidence/desktop-local-work-1280.png) 中，原型移除了 Work 页原有的左侧 `AgentsRailDesktop` 与顶部 `工作记录 / 原生轨迹` 切换栏，改画了一个后端并无聚合接口的 `本轮关联工作区路径` 左栏并标为 `must-match`（`design.md` L225）；而 `spec.md` L163 明确要求在**聊天消息、工具过程或工作记录**关联本机工作区文件或目录时提供打开/定位。真实产品中路径出现在聊天/Work Markdown 的 `file://` 链接以及 `read` / `write` / `edit` / `skill_manage` / `agent.output_file` / `Workflow` 工具详情卡（[`tool-detail-renderers.tsx`](../../../src/IM/frontend/src/features/chat/components/tool-detail-renderers.tsx)、[`agent-work-presenters.tsx`](../../../src/IM/frontend/src/features/settings/agents/agent-work-presenters.tsx)），方案未定义这些真实落点及相对路径结合所属 `agent_id` 的解析方式。
  3. **顶栏一级导航与现有产品不一致**：原型顶栏绘制了 `聊天 | 任务 | 助手 | 电脑` 四个主导航按钮（且在查看 Agent Work 时错误高亮了 `聊天`），而真实 [`AppShell`](../../../src/IM/frontend/src/app/shell/app-shell.tsx) 一级导航固定为 `聊天 | 任务 | 助手`（「电脑」位于右上角用户菜单），设计文档也未声明修改全局一级导航或提供 `/settings/nodes`、`Agent Work` 的现状基线截图对照。
- **未修后果**：
  - 下游按 `must-match` 还原原型会导致本机电脑无法在界面内点击受管更新或改名、Work 页破坏现有 Agent 导航栏去拼凑无数据源的侧栏，而用户在聊天回复和工具卡片里看到真实产物路径时却无处点击打开。
- **收口要求**：
  - 修订 `design.md` 与 `prototype.html`（并刷新对应多视口截图与现状基线对照）：① 在「这台电脑」卡片保留受管更新（`NodeUpdatePanel`）、改名与建助手入口，优化默认收展层级（高频状态/启停/更新直露，低频环境变量/代理细节或运行日志按需展开或紧凑分区，补齐日志筛选/搜索与窄屏环境变量每行明确分组边界，修正报错态代理地址一致性）；② 移除 Work 虚构的左侧路径栏，恢复真实 Work 壳层上下文，改为在真实聊天消息链接与工具详情路径处呈现「打开文件 / 在 Finder（资源管理器）中显示」并说明相对路径归属解析；③ 对齐真实 `AppShell` 顶栏导航结构（或明确决策是否在 Desktop 调整导航）。

---

#### `R1-W5` [WARNING] M1 隔离运行命令、macOS 受管包 Node 来源及 delta-spec 归并链接存在污染开发机生产目录或触发门禁失败的具体风险

- **位置**：
  - [`design.md`](design.md) 既有约束（L22）、Runbook for Reviewer（L274、L282）、`scripts/build-desktop-archives.py`（L11、L33）
  - [`specs/im/agent-work.md`](specs/im/agent-work.md) L7
- **证据**：
  1. **macOS `open -n` 环境变量透传与登录项隔离漏洞**：`design.md` L274 启动命令为 `CREWDEN_DESKTOP_HOME="$WT_ROOT/desktop-home" NANO_INSTALL_ROOT="$WT_ROOT/nano-home" open -n "$WT_ROOT/dist/desktop/Crewden.app" --args --isolated-home "$WT_ROOT/desktop-home"`。在 macOS 上，`open` 经 `LaunchServices` 拉起 `.app` 时不保证继承调用方 shell 的 `NANO_INSTALL_ROOT`，而 `--args` 只传了 `--isolated-home` 未传隔离 `nano-home`；同时 [`apps/node/src/lifecycle.ts`](../../../apps/node/src/lifecycle.ts)（L128-L133、L178）的 `gatewayPlist()` 固定写入真实 `~/Library/LaunchAgents` 且 plist 内不携带 `NANO_INSTALL_ROOT`，`SMAppService` 也会污染开发机真实系统登录项。经 `python3 scripts/dev_host.py check` 核实，当前开发机 `air` 的 `/Users/czj/.nanoassistant` 为受保护生产目录，一旦 `NANO_INSTALL_ROOT` 在 GUI 子进程或 `LaunchAgent` 重拉时丢失，将直接读写开发机生产配置。
  2. **开发机 Node 版本与受管包 `node_major: 24` 不一致**：`design.md` L282 称当前 `air` 已具备 `Node 24.22.1`，但实测 `air` 当前 `/opt/homebrew/bin/node` 为 `v25.8.2`。`build-desktop-archives.py` 构建 `darwin-arm64` 的 `runtime` 归档时必须显式下载并按 SHA-256 校验官方 `node-v24.22.1-darwin-arm64` 二进制（严禁打包宿主 PATH 上的 `node`），且 M1 验证“干净无 Node/npm/pnpm 环境”时需在剥离 `/opt/homebrew/bin` 的隔离环境中启动 `Crewden.app`。
  3. **`specs/im/agent-work.md` 归并相对链接越界**：[`specs/im/agent-work.md`](specs/im/agent-work.md) L7 将原 canonical [`docs/specs/im/agent-work.md`](../../specs/im/agent-work.md) L74 的 `[iOS 客户端](ios-client.md)` 改成了 `[iOS 客户端](../../../../specs/im/ios-client.md)`。归并回 `docs/specs/im/agent-work.md` 时，`../../../../` 会向上越出仓库根目录，导致 `./scripts/docs-check` 失败（同目录下应保持 `ios-client.md`，如同行 `desktop-client.md` 的写法；若需兼顾 active change 期间的 `docs-check`，须在归并说明或路径写法上避免越界）。
- **未修后果**：
  - M1 隔离实测误触开发机真实 `~/.nanoassistant` 与真实系统登录项，或打入错误的 Node 25 运行时；收尾归并 delta-spec 时破坏文档完整性门禁。
- **收口要求**：
  - 让 `--isolated-home`（或显式 CLI 参数 `--install-root`）在 Desktop 宿主及派生的 `apps/node` / 测试登录自启适配器中端到端显式传递隔离根目录并隔离 `LaunchAgents`/`SMAppService` 注册，同时在 Runbook 明确剥离宿主开发工具 `PATH` 的验证方式；明确 `build-desktop-archives.py` 固定拉取官方 Node `24.22.1` 发行包；修正 `specs/im/agent-work.md` 的 `ios-client.md` 链接处理方式。

---

### Recommendations

#### `R1-R1` Web 连接电脑页对 Intel Mac（`darwin-x64`）与 Windows ARM64 用户给出清晰分流提示

- **位置**：[`prototype.html`](prototype.html) L995-L1013、[`web-onboarding-1280.png`](design-evidence/web-onboarding-1280.png)
- **建议**：当前原型系统分段直接写为 `macOS · Apple Silicon` 并默认高亮下载 `arm64` 桌面端，但存量 `install.sh` 仍支持 `darwin-x64`（Intel Mac）。建议将分段名称保持为 `macOS`（或在桌面端卡片副文案中注明“支持 Apple Silicon M 系列；Intel Mac 请选右侧仅装轻量后台节点”），避免旧款 Intel Mac 用户下载 `arm64` 安装包后无法运行。

#### `R1-R2` 将 `SPEC.md` 跨包职责表与拓扑图更新纳入 M1 范围

- **位置**：[`design.md`](design.md) Milestones M1（L291）、[`SPEC.md`](../../../SPEC.md)（L15-L44）
- **建议**：新增 `apps/desktop`（Tauri 原生宿主、本地回环代理与 `apps/node` 本地 IPC 通路）扩展了客户端接入拓扑与顶层目录归属，建议在 M1 文件范围中同步列入 `SPEC.md` 更新，使跨包架构单一权威文档与 `test_runtime_dependency_contract.py` 保持同步。

---

### Author Resolutions

- `R1-C1` — **accepted**: 收敛后台事件消费与通知产生者为常驻 Rust 宿主（见 [`design.md`](design.md)「架构总览」、关键决策 2、第 4 节「Rust 宿主后台通知守护」）。宿主利用当前活跃 `(imOrigin, userId)` 的 `refresh_token` 独立维护 `/im/ws/user` 连接与未读角标，在 `--background` 冷启动及关窗释放/隐藏 WebView 时照常运行（桌面模式下前端抑制浏览器 `new Notification` 避免双弹）；完整覆盖未静音会话的 `message.completed`、非本人 `message.created`（含 `@提及`）、聊天 `permission.request(pending)` 以及本人管理 Agent 的 Work `waiting_permission`，点击通知唤醒/创建窗口并分别路由至 `/chat/<conversationId>` 或 `/settings/agents/<agentId>?view=work`。
- `R1-C2` — **accepted**: 在 `/desktop/v1/local-node/*` 与 `/desktop/v1/workspace/open` 强制执行 `(imOrigin, owner_id / user.id)` 归属核验，并在 [`device-binding.ts`](../../../apps/node/src/device-binding.ts) 拆分 `inAppAccessToken` 与 `confirmTransfer`（见 [`design.md`](design.md) 关键决策 4、第 1 节时序图、第 4 节接口表、[`specs/im/desktop-client.md`](specs/im/desktop-client.md) 及原型新增跨账号保护态 [`desktop-bind-foreign-1280.png`](design-evidence/desktop-bind-foreign-1280.png)）。当本机 `config.node.user_id` 属于其他账号时仅返回 `{ ownership: 'foreign_owner', nodeName }`，禁止读取环境变量/代理/日志/工作区或执行启停；未带 `confirmTransfer: true` 时跨账号或涉及已有 Agent 转移返回 `409 transfer_confirmation_required`，默认引导「仅使用聊天（推荐）」。
- `R1-C3` — **accepted**: 采用固定协议薄宿主 `shell_protocol: 1` 动态从连接目录独立的 `.desktop-active.json` 挂载 `<version_root>/ui/`（含前端与 `/trajectory/` 静态产物），并在 Windows 使用独立的 `%LOCALAPPDATA%\CrewdenDesktop` 与 `DesktopGatewayHost.exe`（`\CrewdenDesktop-<key>`），完全不触碰 `feat-781` 的 `.windows-active.json` 与 `Crewden.lnk`（见 [`design.md`](design.md) 关键决策 1 / 5、第 2 节）。`update-worker.ts` 切换 `.desktop-active.json` 后通知常驻宿主同步热重载静态资源根并刷新打开的 WebView；当未来 `shell_protocol` 不匹配时由 `node-updates.ts` 标为 `incompatible` 拒绝伪报成功。同时已在 M1 `[reviewer]` ② 补入 macOS `arm64` 两个固定测试版本的受管更新复用 `runtime` 缓存与坏包回退端到端验收。
- `R1-W1` — **accepted**: 调整中心 `POST /im/v1/agents/:agent_id/trajectory/authorize` 与本机 `LocalNodeBridge` 职责切分（见 [`design.md`](design.md) 关键决策 6、第 3/4 节）。中心仅校验当前用户的空间/PA 访问资格、`rejectDeletedExecution` 与节点绑定归属，不查询中心 `agent_work_sessions`；本机由 `apps/node` 从持久 `store.bindings()` 解析根会话并调用 `NativeTrajectory.prepare` 沿原生 `parentSession` 链闭环核验子执行归属，经 `encodeTrajectoryValue` 分片流无 `1 MiB` 缓冲上限直读 `>16 MiB` 原文与未同步子执行。
- `R1-W2` — **accepted**: 桌面宿主将回环端口持久化保存在 `<desktop-home>/host-config.json` 保持 WebView `origin` 跨重启稳定，并在桌面模式下为前端 `IndexedDB`（`im-message-attempts::<imOrigin>`）、`composer-draft-store`、`onboarding` 进度及用户流游标加上 `imOrigin` 命名空间前缀（见 [`design.md`](design.md) 关键决策 3、第 4 节及 [`specs/im/desktop-client.md`](specs/im/desktop-client.md)）。切换服务递增 `context_epoch` 并保留原服务待恢复的未确认发送记录，退出登录时仅清理对应 `(imOrigin, userId)` 分区。
- `R1-W3` — **accepted**: 在 [`design.md`](design.md) 关键决策 7 与第 4 节明确固化四项闭环：① 代理表单强制校验 `http(s)://`（拒绝 `socks://`），双向归一映射 `NODE_USE_ENV_PROXY="1"` 及大小写成对的 `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY`/`NO_PROXY` 共 9 个键，并在通用环境变量列表中屏蔽这 9 个键与 `NANO_OWNER_CONFIG_ROOT`；② 即使 `agents: []` 也强制校验 `llm.tool_approval_model` 已在 `llm.providers` 注册；③ Worker 探测合并默认服务 `PATH` 与候选 `gateway.environment.PATH`；④ 为 `darwin` 补齐免中断当前在途任务的 `autostart-on` / `autostart-off` 切换。
- `R1-W4` — **accepted**: 全面修订 [`prototype.html`](prototype.html)、[`design.md`](design.md) 及对应多视口截图与现状基线对照（新增 [`baseline-nodes.png`](design-evidence/baseline-nodes.png)、[`baseline-agent-work.png`](design-evidence/baseline-agent-work.png)、[`desktop-local-trajectory-1280.png`](design-evidence/desktop-local-trajectory-1280.png) 并重渲 [`desktop-local-admin-1280.png`](design-evidence/desktop-local-admin-1280.png)、[`desktop-local-admin-error-390.png`](design-evidence/desktop-local-admin-error-390.png)、[`desktop-local-work-1280.png`](design-evidence/desktop-local-work-1280.png)）：① 对齐真实 `AppShell` 桌面左侧竖向三项主导航轨（`聊天 | 任务 | 助手`）+ 左下角 `UserMenu` 及窄屏底部四栏导航；② 在置顶「这台电脑」卡片恢复 `NodeUpdatePanel` 更新横幅、原位改名与 `+ 新建助手`，将运行配置与带关键字搜索的运行日志改为渐进披露折叠区（首屏直接可见下方远端电脑），在 `390px` 为每条环境变量提供独立 `.env-item-card` 边框分组并统一回退报错代理地址为 `http://127.0.0.1:9999`；③ 移除 Work 虚构的左侧路径栏，恢复真实 `AgentsRailDesktop` 与 `工作记录 | 原生轨迹` 切换，改为在真实 `write`/`edit`/`read` 等工具详情卡路径及聊天 `file://` 链接处提供本地打开/Finder 定位（脚本后缀仅提供定位显示）。
- `R1-W5` — **accepted**: ① 新增宿主显式 CLI 参数 `--isolated-root <dir>` 端到端注入 `CREWDEN_DESKTOP_HOME`、`NANO_INSTALL_ROOT` 与 `NANO_TEST_AUTOSTART_DIR`（不依赖 `open -n` 环境变量透传，隔离测试绝不触碰 `/Users/czj/.nanoassistant`、`~/Library/LaunchAgents` 或 `SMAppService`），并在 Runbook 使用剥离 `/opt/homebrew/bin` 的洁净 `env -i ... PATH="/usr/bin:/bin:/usr/sbin:/sbin"` 启动验证；② 明确 `build-desktop-archives.py` 始终从官方源拉取并按 `SHASUMS256.txt` 校验 `node-v24.22.1`；③ 修正 [`specs/im/agent-work.md`](specs/im/agent-work.md) 链接并在 [`design.md`](design.md) 明确归并时保持同目录 `[iOS 客户端](ios-client.md)`，通过 `./scripts/docs-check`。
- `R1-R1` — **accepted**: 在 [`prototype.html`](prototype.html)（见 [`web-onboarding-1280.png`](design-evidence/web-onboarding-1280.png)、[`web-onboarding-390.png`](design-evidence/web-onboarding-390.png)）、[`design.md`](design.md) 与 [`specs/im/agents-nodes.md`](specs/im/agents-nodes.md) 将系统分段统一为 `macOS`，并在 Desktop 卡片中明确说明支持 Apple Silicon (M 系列)、引导旧款 Intel Mac 选择右侧「仅装轻量后台节点」。
- `R1-R2` — **accepted**: 已在 [`design.md`](design.md)「涉及范围」与 M1 文件范围中纳入 [`SPEC.md`](../../../SPEC.md) 更新。


---

## Round 2

### Metadata

- **reviewer**: Independent Design Reviewer (Gate 2)
- **target**: `docs/changes/feat-790-desktop-client`（[`spec.md`](spec.md)、[`design.md`](design.md)、[`prototype.html`](prototype.html)、`design-evidence/*.png`、`specs/**`、`M1/`、`M2/`）
- **review_mode**: `delta`
- **mode_reason**: [`spec.md`](spec.md) 与四层总体边界（`apps/desktop` Tauri v2 本地回环宿主 + `src/IM/frontend` 共享 SPA + `apps/node` 本地桥接 + `apps/im-server` 非浏览器会话与轨迹授权）未变；本轮围绕 `R1-C1..C3`、`R1-W1..W5` 与 `R1-R1..R2` 同步修订了后台通知守护归属、`shell_protocol: 1` 动态静态资源挂载与 `.desktop-active.json`、跨账号 `owner_id` 门禁与整机转移确认拆分、Agent 级轨迹鉴权 + 本机 `parentSession` 链直读、固定端口与按 `imOrigin` 存储命名空间隔离、本机代理 9 键归一与免中断 `autostart`、多视口原型及里程碑验收条件，波及相邻契约与模块边界但未改变整体技术路线，故按 `delta` 复审变化面与波及范围。
- **retained_from**: `Round 1`（保留未发生变化的架构结论：`apps/desktop` 仅依赖 `@nano/product-contracts` 且不越界导入 DSH / `personal-assistant` / `channels`；模型可见 Agent Context 零变更；无一次性数据库或部署迁移；M1 macOS `arm64` → M2 Windows 10/11 `x64` 双里程碑拓扑保持合理）
- **started_at**: `2026-11-25T21:47:30+09:00`
- **completed_at**: `2026-11-25T21:57:10+09:00`
- **duration**: `9m 40s`

### Verdict

**Approved**（`0 CRITICAL / 0 WARNING / 2 Recommendations`）

---

### Coverage 与证据（Delta 变化面与波及核验）

> 基于 `retained_from: Round 1`，本节聚焦本轮修订涉及的 7 个架构/契约/体验变化面及其对既有生产代码的波及影响。

1. **后台常驻通知守护归属与四类提醒闭环（对应 `R1-C1`）**：
   - 核对 [`design.md`](design.md) 架构总览（L50、L58）、关键决策 2（L87-L89）与第 4 节接口表（L175），对照 [`apps/im-server/src/identity-routes.ts`](../../../apps/im-server/src/identity-routes.ts) 与 [`apps/im-server/src/work.ts`](../../../apps/im-server/src/work.ts)（L124-L127）：后台 `/im/ws/user` 连接、游标恢复、未静音会话未读汇总及系统原生通知已完全收归常驻 Rust 宿主，不依赖 WebView 存活（完美覆盖 `--background` 登录静默自启与关窗隐藏/释放场景，且桌面模式下前端禁用 `new Notification` 避免重复弹窗）。触发范围覆盖 `message.completed`、非本人未静音 `message.created`（含 `@提及`）、聊天 `permission.request(pending)` 及本人管理 Agent 的 Work `waiting_permission`，点击通知分别唤醒定位至 `/chat/<conversationId>` 或 `/settings/agents/<agentId>?view=work`。
2. **单机多账号 `owner_id` 归属隔离与 `bindDevice` 转移二次确认拆分（对应 `R1-C2`）**：
   - 核对 [`design.md`](design.md) 既有约束（L24、L35）、关键决策 4（L95-L97）、时序图（L133-L143）、第 4 节接口表（L177-L182）与 [`specs/im/desktop-client.md`](specs/im/desktop-client.md)（L20），对照 [`apps/node/src/device-binding.ts`](../../../apps/node/src/device-binding.ts)（L148-L214）：`options.auto` 拆分为独立的 `inAppAccessToken` 与 `confirmTransfer`，跨账号或含已有 Agent 归属转移而未显式携带 `confirmTransfer: true` 时返回 `409 transfer_confirmation_required`；当 `config.node.user_id` 为其他账号时 `inspect` 仅返回 `{ ownership: 'foreign_owner', nodeName }`，`lifecycle`/`config` 强制校验 `owner_id === config.node.user_id`（`403` 拒绝越权），消除了跨账号配置/日志泄露与静默夺权风险。
3. **`shell_protocol: 1` 动态挂载、`.desktop-active.json` 隔离与受管更新闭环（对应 `R1-C3`）**：
   - 核对 [`design.md`](design.md) 涉及范围（L15-L17、L39）、关键决策 1/5（L83-L85、L99-L101）、第 2 节（L159-L164）与 M1/M2（L278-L279），对照 [`packages/product-contracts/src/node-update.ts`](../../../packages/product-contracts/src/node-update.ts)（L2-L76）、[`apps/im-server/src/node-updates.ts`](../../../apps/im-server/src/node-updates.ts)（L42-L61）及 [`packaging/windows-host/GatewayHost.cs`](../../../packaging/windows-host/GatewayHost.cs)（L110-L199）：已移除无效的 `shell` 更新包，改为 `shell_protocol: 1` 薄宿主动态从连接目录独立的 `.desktop-active.json` 挂载 `<version_root>/ui/`（含前端与 `/trajectory/` 静态资源），升级后由 [`update-worker.ts`](../../../apps/node/src/update-worker.ts) 切换指针并通知常驻宿主同步热重载 UI 与后台 Node，`shell_protocol` 不匹配时由 `node-updates.ts` 标为 `incompatible`。Windows 采用独立的 `%LOCALAPPDATA%\CrewdenDesktop`、`DesktopGatewayHost.exe` 与 `.desktop-active.json`，不触碰 `feat-781` 的 `.windows-active.json` 与 `Crewden.lnk`；M1 `[reviewer]` ② 已补齐 macOS `arm64` 双测试版本复用 `runtime` 缓存与坏包回退实测。
4. **本机原生轨迹 Agent 级授权 + 本机 `parentSession` 父链无上限直读（对应 `R1-W1`）**：
   - 核对 [`design.md`](design.md) 关键决策 6（L103-L105）、时序图（L145-L154）与第 3/4 节（L166-L170、L181），对照 [`apps/im-server/src/trajectory.ts`](../../../apps/im-server/src/trajectory.ts)（L65-L76）与 [`packages/dsh-integration/src/trajectory.ts`](../../../packages/dsh-integration/src/trajectory.ts)：中心 `/im/v1/agents/:agent_id/trajectory/authorize` 对齐 `trajectory.ts` L65-L69 的删除拦截、空间访问权、PA 主人校验与节点绑定核验，明确**不查询**中心 `agent_work_sessions`；本机由 `LocalNodeBridge` 解析持久 `global:${agentId}` 根会话并调用 `NativeTrajectory.prepare` 沿原生 `parentSession` 链校验子执行归属，解除公网中继 `1 MiB` `bufferedAmount` 断连上限，确保 `>16 MiB` 输出阻断 `WorkSync` 期间的新子执行与完整工具原文均可本地秒开。
5. **持久化本地回环端口与前端按 `imOrigin` 命名空间存储隔离（对应 `R1-W2`）**：
   - 核对 [`design.md`](design.md) 关键决策 3（L91-L93）、第 4 节（L176）与 [`specs/im/desktop-client.md`](specs/im/desktop-client.md)（L57-L61），对照 [`chat-local-db.ts`](../../../src/IM/frontend/src/features/chat/chat-local-db.ts) 与 [`send-attempt-store.ts`](../../../src/IM/frontend/src/features/chat/components/send-attempt-store.ts)：回环端口持久化于 `<desktop-home>/host-config.json` 保持 WebView `origin` 跨重启稳定，同时将 `im-message-attempts::<imOrigin>`、草稿、引导状态与流游标按 `imOrigin` 分区，兼顾切服保留待恢复消息与同 `userId` 跨服务零串台。
6. **本机配置四项边界与开发机 `--isolated-root` / 官方 Node `24.22.1` 隔离（对应 `R1-W3`、`R1-W5`）**：
   - 核对 [`design.md`](design.md) 既有约束（L25、L36）、关键决策 7（L107-L109）、风险与回退（L250）与 Runbook（L260-L273），对照 [`apps/node/src/configuration.ts`](../../../apps/node/src/configuration.ts) 与 [`apps/node/src/lifecycle.ts`](../../../apps/node/src/lifecycle.ts)：已补齐 `http(s)://` 代理 9 键归一映射与受管键屏蔽、空 `agents` 下的 `llm.tool_approval_model` 强校验、合并候选 `PATH` 的 Worker 探测及 macOS 免中断在途任务的 `autostart` 切换；`--isolated-root` 显式注入三项隔离目录且剥离宿主 `/opt/homebrew/bin`，`build-desktop-archives.py` 固定拉取校验官方 `node-v24.22.1`。
7. **前端体验与多视口原型独立走查（`frontend-experience-review` 设计模式，对应 `R1-W4`、`R1-R1`）**：
   - 独立读取并逐张核验现状基线 [`baseline-onboarding.png`](design-evidence/baseline-onboarding.png)、[`baseline-nodes.png`](design-evidence/baseline-nodes.png)、[`baseline-agent-work.png`](design-evidence/baseline-agent-work.png) 与本轮重渲的全部原型截图（[`web-onboarding-1280.png`](design-evidence/web-onboarding-1280.png)、[`web-onboarding-390.png`](design-evidence/web-onboarding-390.png)、[`desktop-bind-takeover-1280.png`](design-evidence/desktop-bind-takeover-1280.png)、[`desktop-bind-foreign-1280.png`](design-evidence/desktop-bind-foreign-1280.png)、[`desktop-local-admin-1280.png`](design-evidence/desktop-local-admin-1280.png)、[`desktop-local-admin-error-390.png`](design-evidence/desktop-local-admin-error-390.png)、[`desktop-local-work-1280.png`](design-evidence/desktop-local-work-1280.png)、[`desktop-local-trajectory-1280.png`](design-evidence/desktop-local-trajectory-1280.png)）：
     - **壳层与信息层级**：桌面端对齐真实 [`AppShell`](../../../src/IM/frontend/src/app/shell/app-shell.tsx) 左侧竖向三项主导航轨 + 左下角用户菜单，窄屏对齐底部四栏导航；`/settings/nodes` 置顶「这台电脑」完整保留原位改名、`+ 新建助手` 与 `NodeUpdatePanel` 更新横幅，并以渐进披露折叠运行配置与带搜索框的运行日志，使下方远端电脑 `Team-Build-Server` 在桌面首屏直接可见（与 [`baseline-nodes.png`](design-evidence/baseline-nodes.png) 首屏扫描节奏一致）。
     - **窄屏防误触与状态自洽**：在 [`desktop-local-admin-error-390.png`](design-evidence/desktop-local-admin-error-390.png) 中，每条环境变量拥有独立边框卡片容器（`移除此项` 归属清晰无误触风险），且回退报错横幅中的 `http://127.0.0.1:9999` 与上方输入框草稿完全一致；[`desktop-bind-foreign-1280.png`](design-evidence/desktop-bind-foreign-1280.png) 将「仅使用聊天（推荐）」设为主按钮、整机转移设为次按钮，符合防误夺权安全直觉；[`web-onboarding-1280.png`](design-evidence/web-onboarding-1280.png) 与 [`web-onboarding-390.png`](design-evidence/web-onboarding-390.png) 明确给出 Intel Mac 选用轻量后台节点的分流说明。
     - **真实路径落点**：[`desktop-local-work-1280.png`](design-evidence/desktop-local-work-1280.png) 与 [`desktop-local-trajectory-1280.png`](design-evidence/desktop-local-trajectory-1280.png) 已移除虚构侧栏，恢复左侧助手栏与 `工作记录 | 原生轨迹` 切换；普通文件（`reports/perf-audit.md`）提供 `打开文件` + `在 Finder 中显示`，可执行脚本（`scripts/run-bench.sh`）仅提供 `在 Finder 中显示`。
8. **Delta-spec 与文档门禁核验（对应 `R1-W5`、`R1-R2`）**：
   - 核验 [`specs/im/desktop-client.md`](specs/im/desktop-client.md)、[`specs/im/agents-nodes.md`](specs/im/agents-nodes.md)、[`specs/im/agent-work.md`](specs/im/agent-work.md)、[`specs/gateway/service-lifecycle.md`](specs/gateway/service-lifecycle.md) 及 [`SPEC.md`](../../../SPEC.md) M1 范围登记；实跑 `./scripts/docs-check` 通过（`documentation integrity passed`）。

---

### 历史问题闭环

| ID | Author Resolution 摘要 | 本轮核验证据 | 状态 |
|---|---|---|---|
| `R1-C1` | 由常驻 Rust 宿主利用活跃会话 `refresh_token` 独立维护 `/im/ws/user` 通知与角标守护，覆盖四类提醒并支持点击路由唤醒，前端抑制浏览器重复通知 | [`design.md`](design.md) L50、L58、L87-L89、L130、L175、L278（M1 `[reviewer]` ② / `[worker]` ②）；关窗与 `--background` 自启均不再依赖 WebView 存活 | **closed** |
| `R1-C2` | `/desktop/v1/local-node/*` 与工作区打开增加 `owner_id`/访问权门禁；`device-binding.ts` 拆分 `inAppAccessToken` 与 `confirmTransfer`，跨账号默认进入纯聊天 | [`design.md`](design.md) L24、L35、L95-L97、L134-L141、L177-L182、L251；[`specs/im/desktop-client.md`](specs/im/desktop-client.md) L20；截图 [`desktop-bind-foreign-1280.png`](design-evidence/desktop-bind-foreign-1280.png) | **closed** |
| `R1-C3` | 采用 `shell_protocol: 1` 薄宿主动态从独立 `.desktop-active.json` 挂载 `<version_root>/ui/`，Windows 独立使用 `DesktopGatewayHost.exe` 与 `%LOCALAPPDATA%\CrewdenDesktop`，M1 补入 macOS 受管更新实测 | [`design.md`](design.md) L15、L39、L83-L85、L99-L101、L159-L164、L267、L278；前后端与 Node 原子同步切换且不触碰 `.windows-active.json` | **closed** |
| `R1-W1` | 中心 `/trajectory/authorize` 不查 `agent_work_sessions`，改由本机 `apps/node` 解析持久根会话并经 `NativeTrajectory.prepare` 核验 `parentSession` 链，解除 `1 MiB` 中继缓冲上限 | [`design.md`](design.md) L103-L105、L147-L154、L168-L170、L181；与 [`apps/im-server/src/trajectory.ts`](../../../apps/im-server/src/trajectory.ts) L65-L69 权限模型完全对齐 | **closed** |
| `R1-W2` | `<desktop-home>/host-config.json` 持久化回环端口，`IndexedDB`/草稿/游标在桌面模式下按 `imOrigin` 分区命名 | [`design.md`](design.md) L91-L93、L176；[`specs/im/desktop-client.md`](specs/im/desktop-client.md) L57-L61；切服保留原服务未确认发送记录且同 `userId` 不串台 | **closed** |
| `R1-W3` | 固化 `http(s)://` 代理 9 键归一映射与屏蔽、空节点 `tool_approval_model` 校验、合并候选 `PATH` Worker 探测及 macOS 免中断在途任务 `autostart` 切换 | [`design.md`](design.md) L36、L107-L109、L177、L179-L180、L278；覆盖 [`apps/node/src/configuration.ts`](../../../apps/node/src/configuration.ts) 与 [`apps/node/src/lifecycle.ts`](../../../apps/node/src/lifecycle.ts) 全部现状约束 | **closed** |
| `R1-W4` | 对齐真实 `AppShell` 导航；「这台电脑」补回改名、建助手、`NodeUpdatePanel`、渐进披露折叠、日志搜索与 `390px` 环境变量分组卡片；移除虚构 Work 侧栏并落回真实工具卡路径 | [`prototype.html`](prototype.html) L654-L1239；[`design.md`](design.md) L186-L229；新增基线 [`baseline-nodes.png`](design-evidence/baseline-nodes.png)、[`baseline-agent-work.png`](design-evidence/baseline-agent-work.png) 与重渲多视口截图均已逐张核实无溢出或裁剪 | **closed** |
| `R1-W5` | 宿主新增 `--isolated-root` 显式端到端隔离三类目录并剥离 Homebrew `PATH`；`build-desktop-archives.py` 固定拉取校验官方 Node `24.22.1`；修正 `specs/im/agent-work.md` 链接与归并说明 | [`design.md`](design.md) L25、L161、L244、L250、L263；[`specs/im/agent-work.md`](specs/im/agent-work.md) L7；`./scripts/docs-check` 实跑通过 | **closed** |
| `R1-R1` | 系统分段统一为 `macOS`，并在 Desktop 卡片副文案明确引导 Intel Mac 选择「仅装轻量后台节点」 | [`prototype.html`](prototype.html) L728、L779、L794；[`specs/im/agents-nodes.md`](specs/im/agents-nodes.md) L33；截图 [`web-onboarding-1280.png`](design-evidence/web-onboarding-1280.png)、[`web-onboarding-390.png`](design-evidence/web-onboarding-390.png) | **closed** |
| `R1-R2` | 将 `SPEC.md` 纳入「涉及范围」与 M1 实施范围 | [`design.md`](design.md) L13、L278 | **closed** |

---

### Issues

无（`0 CRITICAL / 0 WARNING`）。

---

### Recommendations

#### `R2-R1` 在 `foreign_owner` 纯聊天模式下对 `/desktop/v1/workspace/open` 与本地轨迹桥接统一前置 `owner_id` 短路

- **位置**：[`design.md`](design.md) 第 4 节接口表（L181-L182）与风险与回退（L251）
- **建议**：L251 已声明“所有本机读取/配置/打开接口强校验 `owner_id` 与 Agent 访问资格”，而 L181-L182 表格简写为“IM `/trajectory/authorize` 通过 + 本机 `node_id` 匹配”及“PA 主人或已核验 Agent 访问权”。实施时建议按 L251 统一前置 `config.node.user_id === user.id`（非 `foreign_owner`）校验：当同机切换登录另一账号并选择「仅使用聊天」时，即使查看同一公司空间内的共享 Global Agent，也自动回退走中心 IM 远端轨迹通路且不暴露本机 Finder 打开按钮，使跨账号纯聊天模式与原主人本机目录完全解耦。

#### `R2-R2` M2 Windows 接管既有 `feat-781` 轻量节点时对齐 `Crewden-Gateway-<hash>` 真实计划任务前缀

- **位置**：[`design.md`](design.md) 涉及范围（L39）与关键决策 5（L100）；对照 [`packaging/windows-host/GatewayHost.cs`](../../../packaging/windows-host/GatewayHost.cs)（L110-L113）
- **建议**：`design.md` L39 将 `feat-781` 既有计划任务简写为 `\Crewden-<key>`，而现行 `GatewayHost.cs` L112 实际注册名为 `Crewden-Gateway-<24位SHA256前缀>`（按 `User.Value + "|" + config.ToUpperInvariant()` 计算）。M2 实现平滑接管停用原独立自启触发器时，建议复用同一哈希规则精确查找并停用 `Crewden-Gateway-<hash>`，确保即使接管时原轻量节点处于停止态也能干净移除其开机登录触发器。

---

### Author Resolutions

- `R2-R1` — **accepted**: 同意并在 M1 实施时按 [`design.md`](design.md) L251 既有约束统一落实——在 `/desktop/v1/workspace/open` 与 `/desktop/v1/trajectory/prepare` 入口前置 `config.node.user_id === user.owner_id`（非 `foreign_owner`）短路核验；同机跨账号纯聊天模式下自动回退走中心 IM 远端轨迹通路且不展示本机打开按钮（无需改动已通过审查的设计契约）。
- `R2-R2` — **accepted**: 同意并在 M2 Windows 接管实现时直接对齐 [`packaging/windows-host/GatewayHost.cs`](../../../packaging/windows-host/GatewayHost.cs) L110-L113 的 `Crewden-Gateway-<24位SHA256前缀>`（`User.Value + "|" + config.ToUpperInvariant()`）精确查找并停用原 `feat-781` 计划任务，Desktop 自身则使用独立前缀 `CrewdenDesktop-Gateway-<hash>`（实现细节收口，不改动已审受控文档）。
