# Design Review: feat-799-desktop-hardening-private-deploy

## Round 1

### Metadata

- **reviewer**: Independent Gate 2 Design Reviewer (`change-design-reviewer` + 设计态 `frontend-experience-review`)
- **target**:
  - `docs/changes/feat-799-desktop-hardening-private-deploy/spec.md`
  - `docs/changes/feat-799-desktop-hardening-private-deploy/design.md`
  - `docs/changes/feat-799-desktop-hardening-private-deploy/specs/im/desktop-client.md`
  - `docs/changes/feat-799-desktop-hardening-private-deploy/specs/im/agents-nodes.md`
  - `docs/changes/feat-799-desktop-hardening-private-deploy/prototype.html` 及 `docs/changes/feat-799-desktop-hardening-private-deploy/design-evidence/01..09.png`
- **review_mode**: `full`
- **mode_reason**: Round 1 首次独立 Gate 2 完整设计评审，同步执行设计态前端体验与桌面视口一屏化走查
- **started_at**: `2026-11-27T14:04:30+09:00`
- **completed_at**: `2026-11-27T14:23:30+09:00`
- **duration**: `19m`

### Verdict

**Issues Found（Changes Requested）** — `3 CRITICAL / 4 WARNING / 3 NIT (Recommendations)`

---

### Coverage 与证据

#### 1. 架构红线与跨包依赖边界核查（Pass）

对照 `AGENTS.md`、`SPEC.md` 与 `tests/contract/test_runtime_dependency_contract.py`：
- **DSH 接入边界合规**：针对 Issue 2（Windows `app.tar.gz` 缺失 `zod` 导致 `typert` 启动崩溃），本轮在真实 `node_modules/.pnpm` 上执行图闭合审计确认根因：`@deepseek-ai/dsh-web@0.2.2-rc.5/lib/typert.host.js` 直接 `import { z } from 'zod'` 但其 `package.json` 未声明 `zod`，且 `zod`、`parse5`、`@openuidev/lang-core` 等包未出现在顶层平铺 `node_modules/`。`design.md` §3 选择在构建期 `scripts/build-desktop-archives.py` 的 `build_graph()` 中对已遍历包补齐 `p/node_modules/<pkg>` 确定性回退与 `dsh-web -> zod` 显式边，并在打包阶段执行 `node --input-type=module` 冒烟校验，未做任何 `@deepseek-ai/*` 运行时 fork/patch 或 private import，符合架构红线。
- **包职责与进程通信边界合规**：`apps/desktop` 仍通过本地进程与回环控制面管理 `apps/node`，不直接 import DSH；`IM` 仅输出元数据/引导信息与校验白名单，不代理安装包二进制字节流；`@nano/product-contracts` 承载共享 schema 与超时常量，未引入跨包相对路径绕过。

#### 2. `spec.md` 场景、验收标准、Delta-Specs 与 Milestones 覆盖核查

- **场景 1 / 验收 1（首次启动秒级可感知反馈、重复点击唤醒不报错、异常可恢复）**：`design.md` §2 与 `specs/im/desktop-client.md` 覆盖了命名互斥量 + 先绑定回环控制面后异步解包的主体思路，但遗漏了未解包态 `resolve_active_bundle` 对 `CARGO_MANIFEST_DIR` 的开发目录回退隔离、极短间隔双击抢锁竞争分支，以及对现有 Windows 安装冒烟脚本 `packaging/desktop/windows/smoke.ps1` 的破坏性影响（见 `R1-W1`）。
- **场景 2 / 验收 2（官方/公网严格 HTTPS、内网 HTTP 准入、跨服唤起确认、私有化自托管发布源闭环）**：方向合理，但在真实代码触点上存在两处阻断性未闭环：
  1. 自托管内网 `http://` 受管更新被 `apps/node/src/update-worker.ts:45-53` 的 `--proto =https` 硬拦截，`desktop-defaults.json` 跨后台守护进程定位与种子清单文件名（`.release-manifest.json` 前导点）存在断层，且 `IM_ALLOW_PRIVATE_HTTP=1` / 自托管 `IM_RELEASE_BASE_URL` 下暴露未改造的 `windows_x64`（`Package.cs`）与 `install.sh` 会产生必败安装入口（见 `R1-C1`）；
  2. `crewden-desktop://connect` 在冷启动（`config.rs:71-74`）与 macOS `RunEvent::Opened`（`lib.rs:295-305`）上绕过了跨服确认弹窗，且公网明文 `http://` 唤起被静默吞掉或触发进程级致命错误框，违反 `spec.md:241-243` 与 `specs/im/desktop-client.md:44-45` 的明确提示要求（见 `R1-C2`）；内网地址匹配亦需修复域名前缀误判风险（见 `R1-W2`）。
- **场景 3 / 验收 3（Windows 网关运行时包依赖闭合与快败可诊断）**：依赖图闭合与 `LocalNodeBridge` 启动前存活探测合理（`design.md` §3）。
- **场景 4 / 验收 4（Windows 首次创建个人助手超时预算、预热与语义化错误）**：在真实协议链路上存在阻断性漏洞——非 `inspection` 命令在 `packages/channels/src/index.ts:306-309` 有硬编码 `10_000ms` 的 `serverRequests` TTL，超过 10s 返回的 `agent.create.result` 会被改写 `request_id` 导致必丢；同时 `createAgent`（`agent-creation.ts:161-166`）绕过 `CatalogReads` 触发第二次冷启动子进程，且 `node.register` 预热在新装引导第 1 步时尚无模型配置而落空，错误码映射也与 `ConfigOperations` 的 `503 config_apply_pending` 冲突（见 `R1-C3`）。
- **场景 5 / 验收 5（桌面端 `1280×840` 与 `1280×720` 全流程一屏化及 Web `/about`、窄屏无回归）**：Web `/about`（`PublicHomePage`）路径隔离清晰，但桌面一屏化在 `FirstUseWelcome` 原型缺失、引导第 2 步主操作按钮位于内滚表单而非固定底栏、第 3 步真实 DOM 高度超出 `design.md` 所列改动范围等方面尚未闭环（见 `R1-W3`），且前端验收 Runbook 缺少具体隔离命令（见 `R1-W4`）。
- **Milestone 出口标准完备性**：`design.md:366-377` 的 `M1` 退出条件遗漏了 `spec.md:241-243`（公网明文 `http://` 唤起拒绝并明确提示需用 `https://`）与 `spec.md:248`（自托管 IM + 自托管 Desktop 完成应用内受管更新且不回退官方源），需在修订时一并补入 `M1` 验收口径。

#### 3. 设计态前端体验审查（`frontend-experience-review`）

审阅了 `prototype.html` 与 `design-evidence/01..09.png`（覆盖 `1280×840` 与 `1280×720` 两组视口）并对照 `src/IM/frontend/src/**` 现有组件实现：
- **正向结论**：整体延续了产品现有的暖白底色、墨绿主行动按钮与克制圆角卡片气质；`04-switch-confirm-1280x840.png` 清晰呈现了“当前已连接服务 vs 外部请求切换目标”的对比卡片与双按钮决策；向导顶栏固定 + 卡片主体内滚 + 底栏操作钉住的布局方向符合桌面端预期，且对 `/about` 公共营销落地页做了明确路由隔离，避免破坏 Web 官网长滚叙事。
- **主要体验与实现偏差**：
  1. 聊天空态欢迎页 `FirstUseWelcome` 在原型与截图中完全缺席，且现有 `first-use-welcome.css` 垂直总高约 `904px`，按 `design.md:305` 的轻量缩减仍无法装入 `1280×720`；
  2. 引导第 2 步原型与真实 `ModelServicesPanel` + `ModelServiceEditor` 的按钮归属不一致（真实首次添加态主按钮 `验证并继续` 在内滚 `<form>` 底部而非 `.onboarding-footer`）；
  3. 引导第 3 步原型删除了真实 DOM 中的重复身份预览卡（`.onboarding-identity-preview`）并改用了双列字段排布，但 `design.md:303` 未写明这些结构收敛；
  4. `03-login-server-edit-1280x720.png` 同时渲染了收起态顶栏与展开态编辑框、漏掉了真实 `DesktopServerBar` 的 `取消` 按钮以及 `design.md:158` 要求的“内网明文 HTTP 提示”，且多个 `?clean=1` 截图内部混入了演示切换按钮（详见 `R1-W3`、`R1-R1`）。

---

### 历史问题闭环

Round 1 初审，无历史问题。

---

### Issues

#### `R1-C1` [CRITICAL] — 私有化/自托管受管更新与节点安装材料链路未闭环（内网 `http://` 更新被 `curl` 协议锁拦截、`desktop-defaults.json` 跨守护进程定位与 `.release-manifest.json` 契约断层、暴露不可用的 `windows_x64` / `install.sh`）

- **位置**：
  - 设计与规范：`design.md:159, 185-188, 203-220`、`specs/im/agents-nodes.md:38-42`、`spec.md:122-141, 244-248`
  - 真实源码：`apps/node/src/update-worker.ts:45-53, 66, 107, 227, 325`、`apps/node/src/node-updater.ts:57-67`、`apps/node/src/release.ts:15`、`apps/desktop/src/local_node.rs:234`、`apps/im-server/src/install.ts:70-98`、`packaging/windows/Package.cs:18, 41, 59-60, 128-132`、`apps/im-server/assets/install.sh:15, 59`
- **证据**：
  1. **内网 `http://` 自托管更新必败**：`design.md:209-216` 约定通过 `desktop-defaults.json` 的 `"trusted_release_base_url": "http://10.24.8.15:9000/releases/v0.1.0/"` + `"allow_private_http_release_base": true` 支持内网自托管 Desktop 应用内更新；但 `apps/node/src/update-worker.ts:45-53`（`curlProtoArgs`）仅当 `NANO_ALLOW_LOOPBACK_UPDATE_HTTP === '1'` **且主机名为 `127.0.0.1`/`localhost`** 时才放行 `http`，其余一律强制 `--proto =https --proto-redir =https`。连接 `http://10.x` / `192.168.x` 发布源时 `downloadVerifiedAsset`（`L66`）会直接报错退出；同时若放开 `--proto-redir` 而未禁用跨协议/跨公网重定向，私网 HTTP 源若发生 302 跳转到公网 `http://` 将破坏传输边界。
  2. **`desktop-defaults.json` 定位与 `.release-manifest.json` 文件名契约不一致**：
     - Windows 下 `update-worker` 由计划任务 / `DesktopGatewayHost.cs:208` 拉起（带 `CREWDEN_DESKTOP_HOME`），而 macOS 下由 `NodeUpdater.request`（`apps/node/src/node-updater.ts:61-67`）继承 Gateway 环境分离拉起；`design.md:214` 未定义 `update-worker` 与 `Gateway` 如何无歧义定位 `<desktop_home>/desktop-defaults.json`（例如由目录层级 `versions/<sha>` 向上两级推导并校验所有权，或统一注入环境变量）。
     - `design.md:219` 写明解包后将清单写入 `<versionRoot>/release-manifest.json`（无前导点），但真实代码 `apps/desktop/src/local_node.rs:234`、`apps/node/src/update-worker.ts:115, 227` 与 `apps/node/src/release.ts:15` 全部读写 **`.release-manifest.json`（带前导点）**；若去掉前导点，`loadNodeRelease` 会收到 `ENOENT` 并静默退化为 `{ kind: 'source', version: 'source' }`，导致受管更新与内置 `pnpm` 全部失效。
  3. **在私网 HTTP / 自托管源下暴露未改造的 `windows_x64` 与 `install.sh`**：`design.md:159` 计划在 `IM_ALLOW_PRIVATE_HTTP=1` 时将 `windows_x64` 与 `desktop_*` 一并暴露，且 `specs/im/agents-nodes.md:38-42` 声明安装命令与节点包下载地址从 `trustedReleaseBaseUrls` 派生；然而 `packaging/windows/Package.cs`（`L18` 硬编码 GitHub 仓库、`L41` 强制 `url.Scheme == "https"`、`L59-60` 仅允许 GitHub 重定向主机）与 `apps/im-server/assets/install.sh`（`L15` 硬编码 GitHub Releases、`L59` 硬编码 `--proto "=https"`）均未列入本单元改动。
- **未修后果**：
  - 私有化内网部署下应用内受管更新完全无法下载构建包，直接违反 `spec.md:248`；
  - 用户在私网/自托管 IM 页面看到“可用”的轻量 Windows 安装器或 `curl | sh` 命令后执行即报错，直接违反 `spec.md:139-140` 与 `specs/im/agents-nodes.md:34`（不展示指向不可用外部源的错误入口）。
- **收口要求**：
  1. 在 `design.md` §1 明确 `update-worker.ts` 对受信内网 `http://` 发布源的 `curl` 协议策略（如仅在匹配 `desktop-defaults.json` 的受信私网 origin 时允许 `--proto =http,https` 并禁止重定向或仅允许同源重定向），明确 `<desktop_home>/desktop-defaults.json` 在 Windows/macOS 守护与 worker 进程中的确定性寻址方式，并将 `<versionRoot>/.release-manifest.json` 文件名对齐现有前导点契约；同时把“自托管应用内受管更新闭环”补入 `M1` 出口条件。
  2. 对 `windows_x64` / `install.sh` 做出明确二选一闭环设计：要么同步改造 `Package.cs` 与 `install.sh` 使其支持注入的 `IM_RELEASE_BASE_URL` 与内网 `http://` 准入，要么按 `spec.md:140` 与 `specs/im/agents-nodes.md:34` 在非官方源 / 私网明文 HTTP 场景下仅开放已闭环的 `desktop_*` 引导方式并将未闭环的无头安装入口标记为 `unavailable`（同时修正 `design.md:159` 与 `specs/im/agents-nodes.md:38-42` 的表述范围）。

#### `R1-C2` [CRITICAL] — `crewden-desktop://connect` 跨服唤起在冷启动、macOS 原生事件与公网明文 `http://` 拒绝反馈上存在安全绕过与契约断层

- **位置**：
  - 设计与规范：`spec.md:115-120, 239-243`、`specs/im/desktop-client.md:35-45`、`design.md:163-184`
  - 真实源码：`apps/desktop/src/config.rs:68-75`、`apps/desktop/src/lib.rs:176-184, 295-305`、`apps/desktop/src/host_server.rs:114-126, 520-539`
- **证据**：
  1. **冷启动绕过跨服确认**：`apps/desktop/src/config.rs:71-74` 在解析命令行参数时，将位置参数 `crewden-desktop://connect?origin=...` 直接存入与 `--im-origin` 共用的 `opts.im_origin`。当客户端当前未在后台运行时，`forward_to_running_instance` 返回 `Ok(false)`，`start_host_server` -> `load_or_init_host_config`（`host_server.rs:118-125`）不经任何用户确认就将外部传入的 `origin` 持久化写入 `host-config.json` 并连接目标服务器。
  2. **macOS `RunEvent::Opened` 绕过跨服确认**：macOS 系统协议唤起走 `RunEvent::Opened { urls }`（`apps/desktop/src/lib.rs:295-305`），当前代码直接调用 `apply_server_switch(&state_run, &new_origin)` 并导航 `/chat`，未走 `design.md:166` 所述的 `/desktop/internal/deep-link` -> `pending_server_switch` 确认链路。
  3. **公网明文 `http://` 唤起缺少明确拒绝提示（或误报启动崩溃）**：`spec.md:241-243` 与 `specs/im/desktop-client.md:44-45` 明确要求收到指向公网/官方明文 `http://` 的外部连接唤起时，客户端拒绝切换并**向用户明确提示公网/官方服务必须使用 `https://`**。但当前 `lib.rs:297` 与 `host_server.rs:523` 用 `if let Ok(Some(...))` 静默丢弃非法地址（用户点击网页唤起后毫无反馈）；而在 Windows 已运行实例下，`DesktopCliOptions::parse_from`（`lib.rs:176`）先于 `forward_to_running_instance`（`lib.rs:179`）执行，在此处报错会直接触发第二进程 `main.rs` 致命启动错误弹窗，而非唤醒主窗口给出清晰的协议拒绝提示。
- **未修后果**：
  - 任意外部网页可在用户未启动 Desktop 时通过 `crewden-desktop://connect?origin=https://attacker.example` 静默劫持客户端连接的 IM 服务，或在 macOS 运行态下无确认强制切服；
  - 公网明文 `http://` 唤起无法满足 `spec.md:241-243` 的显式用户提示验收要求。
- **收口要求**：
  1. 在 `DesktopCliOptions` 中将显式命令行参数 `--im-origin`（开发/测试覆盖）与外部协议唤起原始 URL（`deep_link_url`）彻底分离：无论冷启动、Windows 第二实例转发还是 macOS `RunEvent::Opened`，凡来自 `crewden-desktop://connect` 且与当前 `im_origin` 不同的目标地址，统一进入同一套校验与 `pending_server_switch` 用户确认状态机（仅与当前已生效 `im_origin` 相同时直接聚焦窗口）。
  2. 明确公网明文 `http://`（及其他非法唤起地址）的前端可见拒绝反馈通路（例如第二实例转发原始唤起参数后由主实例校验，不合法时聚焦主窗口并在顶部横幅/弹窗中展示“公网或官方服务必须使用 `https://`”的被拒原因，同时保持原 `im_origin` 不变），并将该场景补入 `M1` 退出条件。

#### `R1-C3` [CRITICAL] — Windows 个人助手创建链路的超时扩展、预热与错误码设计与现有 Relay / `CatalogReads` / `ConfigOperations` 实现不一致

- **位置**：
  - 设计与规范：`spec.md:165-177, 254-258`、`design.md:22, 247-260`
  - 真实源码：`packages/channels/src/index.ts:145-149, 306-309`、`packages/product-contracts/src/node-rpc.ts:108-150`、`packages/product-contracts/src/configuration-rpc.ts:84-88`、`apps/im-server/src/node-rpc.ts:28, 56, 74-77`、`apps/im-server/src/agent-creation.ts:97-110, 161-166`、`apps/im-server/src/control.ts:158-163, 266-286`、`apps/im-server/src/personal-agent.ts:103-147`、`apps/node/src/capability-requests.ts:40-47`、`apps/node/src/main.ts:481-485`、`packages/dsh-integration/src/configuration-inspector.ts:103`
- **证据**：
  1. **Relay 节点侧硬编码 `10_000ms` 请求保活窗口导致 10s~60s 创建回包丢失**：
     - 首先，`design.md:22, 253` 所写的 `node.config.apply` 命令在代码库中不存在；真实配置变更为 `agent.create`、`agent.config.apply` 与 `agent.config.operation.status`（`packages/product-contracts/src/node-rpc.ts:150`）。
     - 更关键的是，`apps/im-server/src/node-rpc.ts:56` 仅对 `inspection` 命令附带 `deadline_at`。在节点侧 `packages/channels/src/index.ts:306-309` 中，凡无 `deadline_at` 的服务端请求一律被赋予硬编码 **`10_000ms`** 的 `serverRequests` TTL。若仅把 IM 侧 `NodeRpc` 超时提到 `60_000ms`，当 Windows 节点在 `15s` 完成 `agent.create` 并调用 `relay.request('agent.create.result', ...)` 时，`this.serverRequests.has(request_id)` 已在 `10s` 过期为 `false`，`packages/channels/src/index.ts:145, 149` 会把回包中的 `request_id` **改写为全新 `randomUUID()`**，导致 IM `NodeRpc.accept` 无法匹配等待者而白白挂满 `60_000ms` 超时！
  2. **`createAgent` 绕过缓存二次拉起冷检子进程，且 `node.register` 预热在首次引导链路中失效**：
     - `ConfigurationInspector`（`configuration-inspector.ts:103`）在单次运行结束后立即删除 `flights`，本身不缓存已完成结果；5 分钟缓存仅位于 IM 侧 `CatalogReads`（`catalog-reads.ts:73`）。
     - `POST /im/v1/personal-agent` 先调 `readNodeCreationCapabilities`（命中/写入 `CatalogReads`），紧接着调 `createAgent`（`b.skills === undefined`）；而 `apps/im-server/src/agent-creation.ts:161-166` 在 `skills === undefined` 时**绕过 `CatalogReads` 直接调用 `gatewayRequest(ctx, id, "node.capabilities.resolve", {})`**，在 Windows 上无条件再冷启动第二个 `ConfigurationInspector` 子进程（两次串行冷检 + 创建极易击穿前端 `150_000ms` 上限）。
     - 新装客户端在引导第 1 步完成 `node.register` 时还未配置任何模型，`apps/node/src/capability-requests.ts:40` 因 `!config.llm.default_model` 直接跳过 `inspector.inspect` 秒回空列表；直到第 2 步保存模型并发出 `node.capabilities.changed`（`main.ts:481-485`）后才具备真实 `candidate`。因此仅在 `node.register` 触发且不经 `catalogReads(ctx).read(...)` 写入缓存槽位的预热，在新装引导第 2 -> 第 3 步上命中率为 0。
  3. **错误码契约与 `ConfigOperations` 持久化恢复语义冲突，且非 Windows 基线数值有误**：
     - `design.md:258` 规定返回 `503 node_offline`、`503/504 node_capabilities_unavailable`、`504 create_confirmation_timeout`；但真实 `ops.create`（`control.ts:158-163, 276-286` + `node-rpc-request.ts:16`）在操作落入 `agent_config_operations` 后遇到节点离线（`503`）或确认超时（`504`）会统一抛出 **`503 { code: 'config_apply_pending' }`**，而 `readNodeCreationCapabilities`（`agent-creation.ts:100-109`）抛无 `code` 的字符串异常。
     - `design.md:251` 称非 Windows 保持 `{ workerMs: 15_000, nodeMs: 17_000, rpcMs: 20_000 }`，而 `packages/product-contracts/src/configuration-rpc.ts:87` 真实基线为 `{ workerMs: 7_000, nodeMs: 8_000, rpcMs: 9_000 }`。
- **未修后果**：
  - Windows 上任何耗时 `10s~60s` 的个人助手创建都会因 `RelayClient` 重写 `request_id` 而假超时；
  - 冷机器首次引导在未命中预热且触发二次 `ConfigurationInspector` 子进程时仍会超过 `150s` 失败；
  - 将已持久化的 `config_apply_pending` 误改或漏映射会导致前后端重试状态机错乱。
- **收口要求**：
  1. 修正命令名为 `agent.create` / `agent.config.apply` / `agent.config.operation.status`，并在 `node-rpc.ts` 与 `packages/channels/src/index.ts:306-309` 同步传递 `deadline_at`（或对齐 `serverRequests` 保活窗口），同时明确 `NodeRpc.disconnect` 在创建等待期间断连时的快败行为；修正非 Windows `inspectionTimeouts(false)` 基线数值为 `7_000 / 8_000 / 9_000`。
  2. 消除 `POST /im/v1/personal-agent` 的二次绕过缓存冷检（让 `personal-agent.ts` 复用 `readNodeCreationCapabilities` 已读取的默认技能或让 `createAgent` 复用 `CatalogReads`），并将后台预热改为通过 `catalogReads(ctx).read(...)` 在 **`node.register`（已配模型时）与 `node.capabilities.changed`（第 2 步配完模型后）** 异步触发（不阻塞注册 ACK）。
  3. 明确对齐 `personal-agent.ts` 与前端引导第 3 步的错误码契约：区分创建落库前的 `node_offline` / `node_capabilities_unavailable` 与落库后待节点确认的 `config_apply_pending`（或确认超时提示 + 幂等重试恢复语义）。

---

#### `R1-W1` [WARNING] — 首次启动异步解包状态机对 `smoke.ps1`、未解包态 `CARGO_MANIFEST_DIR` 回退隔离及毫秒级并发双击抢锁缺少闭环说明

- **位置**：
  - 设计文档：`design.md:96-135, 341-342`
  - 真实源码：`packaging/desktop/windows/smoke.ps1:53-68`、`apps/desktop/src/local_node.rs:334-348, 532`、`apps/desktop/src/host_server.rs:165, 2149-2206`
- **证据**：
  1. **`smoke.ps1` 必现抢跑失败**：`packaging/desktop/windows/smoke.ps1:53-68` 一旦读到 `host-state.json` 中 `ready == true` 便立即退出轮询并在第 68 行检查 `versions\<sha256>\runtime\node.exe` 是否存在。按 `design.md:101-103` 改为先绑定端口写 `host-state.json`（毫秒级）、后台再异步解包（`15~45s`）后，Windows CI 安装冒烟测试将稳定失败。
  2. **未解包态页面承载与开发目录穿透**：解包完成前 `versions/<sha>/ui/frontend/index.html` 尚不存在；且在存在源码树的构建机/CI 上，`resolve_active_bundle`（`apps/desktop/src/local_node.rs:334-348`）在找不到已安装版本时会回退到编译期 `CARGO_MANIFEST_DIR`，掩盖未解包态或造成混合文件读取。
  3. **首启前几毫秒双击的锁竞争**：`design.md:99-100` 先探测 `host-state.json` 再抢 `instance.lock`。若首启写 `host-state.json` 前的几毫秒窗口内用户快速双击，第二进程读不到 `host-state.json` 随后在 `instance.lock` 撞锁；若直接按错误退出会弹出致命错误框，违背 `spec.md:233-235`“重复点击静默唤醒已有窗口且不报错”。
- **未修后果**：Windows 打包冒烟流水线红灯；构建机/开发机测试首启准备页时意外穿透到源码目录；极端快速双击仍可能弹锁冲突报错。
- **收口要求**：
  1. 明确 `host-state.json` / `/desktop/internal/status`（及 `--headless-host`）区分 `host_ready` 与 `seed_ready`，并同步将 `packaging/desktop/windows/smoke.ps1` 纳入修改触点；
  2. 明确当检测到 `seed-archives/` 且 `seed_ready != true` 时，`resolve_active_bundle` 禁止回退 `CARGO_MANIFEST_DIR`，由 `host_server.rs` 直接内联返回零外部静态依赖的准备态/失败重试 HTML；
  3. 明确第二实例在 `instance.lock` 已被占用但 `host-state.json` 尚未就绪时，执行短时退避轮询等待 `host-state.json` 出现并调用 `/desktop/internal/activate` 后 `exit(0)`。

#### `R1-W2` [WARNING] — 内网明文 HTTP 地址判定的主机匹配规则存在公网域名误判漏洞与历史配置二次校验缺失

- **位置**：
  - 设计与原型：`design.md:150-158`、`prototype.html:1216`、`spec.md:107-108`、`specs/im/desktop-client.md:27`
  - 真实源码：`apps/desktop/src/config.rs:97-116`、`apps/desktop/src/host_server.rs:114-126`
- **证据**：
  1. `prototype.html:1216` 使用前缀正则 `/^http:\/\/(127\.0\.0\.1|localhost|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/`，会将公网恶意域名 `http://10.evil.com`、`http://192.168.attacker.org` 误判为合法私网地址！同时 `design.md:153` 额外放开了“不含公网点的单标签内网主机名”，超出了 `spec.md:107-108` 与 `specs/im/desktop-client.md:27` 约定的白名单范围（`127.0.0.1`、`localhost`、`[::1]`、RFC1918 私网 IP 段、`.local`）。
  2. `load_or_init_host_config`（`apps/desktop/src/host_server.rs:114-126`）从磁盘加载已有 `host-config.json` 时未调用 `validate_im_origin`，导致旧版本遗留或手工编辑的公网明文 `http://` 地址仍会被直接加载运行。
- **未修后果**：若实施阶段沿用前缀匹配或未收敛主机名白名单，攻击者可构造 `10.<domain>` 绕过公网 HTTPS 强制校验；持久化脏配置亦无法在启动时被拦截或安全回退。
- **收口要求**：
  1. 在 `design.md` §1 明确规定 Rust / Node / 前端三端统一先做严格 IPv4/IPv6 字面量解析再判定网段（`127.0.0.0/8`、`10.0.0.0/8`、`172.16.0.0/12`、`192.168.0.0/16`、`::1`、`fc00::/7`、`fe80::/10`），严禁对域名字符串做数字前缀匹配；主机名白名单与 `spec.md` 严格对齐（若确需单标签主机名则须同步更新 `spec.md` 与 delta-spec）。
  2. 明确 `load_or_init_host_config` 加载已有持久化配置时复验 `im_origin`，不合法时回退默认官方 HTTPS（或 `desktop-defaults.json` 预设值）并记录可观测提示。

#### `R1-W3` [WARNING] — 桌面端一屏化设计存在 `FirstUseWelcome` 缺失、引导第 2 步主按钮掉出固定底栏、第 3 步真实 DOM 超高及双栏裁剪风险

- **位置**：
  - 设计与规范：`spec.md:179-192, 259-262`、`specs/im/desktop-client.md:55-61`、`design.md:288-323, 376-377`、`prototype.html`、`design-evidence/01..09.png`
  - 真实源码：`src/IM/frontend/src/features/onboarding/first-use-welcome.tsx`、`src/IM/frontend/src/features/onboarding/first-use-welcome.css:8-45`、`src/IM/frontend/src/features/onboarding/onboarding-page.tsx:161-265`、`src/IM/frontend/src/features/onboarding/onboarding.css`、`src/IM/frontend/src/features/settings/models/model-services-panel.tsx:155`、`src/IM/frontend/src/features/settings/models/model-service-editor.tsx:35-69`、`src/IM/frontend/src/features/auth/auth-page.css:28-54`、`src/IM/frontend/src/features/auth/auth-scene.tsx:8-28`
- **证据**：
  1. **`FirstUseWelcome` 缺少原型验证且高度预算超标**：`spec.md:185, 260` 与 `design.md:305, 377` 均承诺聊天空态欢迎页（`FirstUseWelcome`）在 `1280×840` 与 `1280×720` 下满足 `scrollHeight <= clientHeight`，但 `prototype.html` 与 `design-evidence/` 未提供该页面；真实 `first-use-welcome.css:8-45` 的纵向堆叠（上下 `96px` padding + `72px` 头像 + 标题导语 + 三项准备状态大卡 + 底栏）总高约 `904px`，仅按 `design.md:305` 缩减上下 padding 仍约 `760px > 720px`。
  2. **引导第 2 步（连接模型）主 CTA 实际位于内滚区而非固定底栏**：`08-onboarding-step2-1280x720.png` 把“下一步：创建个人助手”画在固定 `.wizard-footer` 中；但真实代码 `onboarding-page.tsx:206-207` 与 `model-services-panel.tsx:155` 在首次添加模型（`editingModel === true`）时隐藏了底栏的“继续”，真正的主提交按钮 **`验证并继续` 渲染在 `<form className="model-editor">` 内部的 `.model-footer`（处于 `.onboarding-card-body` 内滚容器底部）**，固定底栏只剩 `← 返回`。当用户切到“自定义 API”展开协议、服务名称、API 地址与模型字段时，主按钮会滚出 `1280×720` 视口，违反 `spec.md:187`“主操作按钮保持在视口内可见”。
  3. **引导第 3 步与左侧进度栏的真实 DOM 结构超出 `design.md` 描述范围**：`09-onboarding-step3-1280x720.png` 之所以能装入 `720px`，是因为原型移除了真实 `onboarding-page.tsx:214-243` 中与 `AvatarPicker`（`88px` 实时头像）重复的 `.onboarding-identity-preview`（约 `152px` 高），将“助手名称 + 默认协作范围”并排为双列，并将左侧 `<aside>` 顶部的大号 `h1` 导语收起；而 `design.md:303` 仅写了拆分 `.onboarding-card-body`/`.onboarding-footer` 与缩小 `AvatarPicker`，未明确上述结构去重与紧凑排布，直接按文字实施仍会导致第 3 步在 `1280×720` 下内滚拥挤且左侧 `<aside>`（约 `666px`）溢出。
  4. **认证双栏在 `1280×720` 下的左侧故事栏裁剪与 `DesktopServerBar` 状态偏差**：`design.md:299` 对 `.crew-account-card` 设 `max-height: calc(100dvh - 76px)`（`720px` 视口下仅 `644px`）且 `overflow: hidden`，而真实 `AuthScene`（`auth-scene.tsx:8-28` + `auth-page.css:28-54`）高度约 `650px`，存在底部说明文字被硬裁剪风险；同时 `03-login-server-edit-1280x720.png` 展开编辑框时重复保留了收起态顶栏、漏掉了真实 `DesktopServerBar` 的 `取消` 按钮及 `design.md:158` 要求的“内网明文 HTTP 风险提示条”。
- **未修后果**：实施后在 `1280×720` 标准笔记本窗口下，`FirstUseWelcome` 仍出现外层滚动条、第 2 步自定义模型主按钮掉出首屏、第 3 步与登录左侧栏发生意外挤压或截断，无法通过 `M1` Playwright 零滚动断言。
- **收口要求**：
  1. 在 `design.md` §5 与 `prototype.html` 补齐 `FirstUseWelcome` 在 `1280×720` 下的紧凑布局规格与截图证据；
  2. 明确引导第 2 步在 `editingModel` 态下将主提交动作（`验证并继续`）收敛到固定 `.onboarding-footer`（例如通过 `form` 属性关联或统一底栏动作插槽），避免双底栏或主按钮滚出视口；
  3. 在 `design.md:303` 明确第 3 步去除/合并重复 `.onboarding-identity-preview`、紧凑双列排布及左侧 `<aside>` 高度预算；在 `design.md:299` 补齐桌面紧凑视口下 `AuthScene` 插画间距缩放规则，并修正 `DesktopServerBar` 展开态原地替换（含 `取消` 与内网 HTTP 提示条）的原型与文字说明。

#### `R1-W4` [WARNING] — 前端体验验收 Runbook 缺少可直接执行的 worktree 隔离启动、健康检查与资源回收命令

- **位置**：
  - 设计文档：`design.md:353-364`
  - 流程规范：`docs/development/frontend-experience.md:21-27`、`docs/development/worktree-runtime.md`
- **证据**：`docs/development/frontend-experience.md:21-27`（实施验收前置）要求前端改动在 `design.md` 中写清完备的 Reviewer Runbook，包含隔离启动命令、访问地址、健康检查、种子账号/前置条件以及测试资源回收命令，使独立验收者无需翻阅源码猜启动参数。当前 `design.md:353-364` 仅给出概括性文字描述（“启动本地隔离 IM 服务（测试端口 + `IM_ALLOW_PRIVATE_HTTP=1`）”），未给出基于 `./scripts/e2e-up.sh` / `./scripts/e2e-down.sh` 与隔离 `--desktop-home` / `--listen-port` 的具体命令序列。
- **未修后果**：独立体验审查与回归验证时容易误用默认端口/共享宿主目录或遗留未回收后台进程。
- **收口要求**：在 `design.md` 的前端体验验收 Runbook 中补齐具体的 worktree 隔离启动命令（含 `IM_ALLOW_PRIVATE_HTTP=1` / `IM_RELEASE_BASE_URL` 注入方式、隔离 Desktop Host 启动参数、健康检查 URL）与一键清理回收命令。

---

### Recommendations (`NIT`)

- **`R1-R1` [NIT] — 剥离 `prototype.html` 产品容器内的演示控制按钮与矛盾状态**：在 `?clean=1` 生成的 `design-evidence/01, 07, 08, 09.png` 中，“切换故障态预览”“步骤 1/2/3”“模拟启动崩溃快败”“状态反馈预览”等演示控件仍渲染在产品卡片内部，`02/03/05` 在 `ProductHeader` 右侧额外添加了真实组件不存在的 `Desktop 客户端` 标签，`07-onboarding-step1` 同时呈现“一键绑定并启动”与“已连接在线 + 步骤 1/2 已完成”。修订 `prototype.html` 时建议将演示态切换完全收归 URL query 参数或画布外浮层，保持产品画面自明、纯净。
- **`R1-R2` [NIT] — 明确 `100.64.0.0/10`（Tailscale / CGNAT）在内网地址策略中的归属**：不少团队私有化部署通过 Tailscale / WireGuard 组网（常用 `100.64.0.0/10`）。建议在 `design.md` §1 简短注明该网段是否视作私网范围或明确要求使用 Tailscale HTTPS 证书，避免运维配置歧义。
- **`R1-R3` [NIT] — Windows 安装器升级覆盖前联动命名互斥量优雅关闭旧进程**：`packaging/desktop/windows/CrewdenDesktop.iss` 既然将配合 `Global\CrewdenDesktop.<hash>` 单实例互斥量使用，建议顺带声明 `AppMutex` 或 `CloseApplications=yes`，在覆盖安装升级时引导优雅退出运行中的托盘宿主，减少文件占用报错。


### Author Resolutions

- **`R1-C1` (Resolved)**:
  1. 在 `design.md` §2.2 明确 `apps/node/src/release.ts` 新增 `loadTrustedReleaseOptions(root)`，从 `<root>/.nano-release.json` 与目录层级推导的 `<desktop_home>/desktop-defaults.json` 确定性加载受信源（不依赖分离 worker / 计划任务 / LaunchAgent 的进程环境变量继承）；修正清单文件名为带前导点的 `<versionRoot>/.release-manifest.json`。
  2. 在 `design.md` §2.2 明确 `apps/node/src/update-worker.ts` 的 `curlProtoArgs` 对匹配已授权私网 `http://` 源启用 `['--proto', '=http,https', '--max-redirs', '0']`（禁止明文跨源重定向并强制 SHA-256 校验），并将「自托管发布源应用内受管更新闭环」补入 `M1` 准出标准。
  3. 在 `design.md` §1 与 `specs/im/agents-nodes.md` 明确安装入口诚实边界：`IM_ALLOW_PRIVATE_HTTP=1` 与自托管 `IM_RELEASE_BASE_URL` 仅开放自包含离线运行的 `desktop_*` 入口，而依赖公网 HTTPS / 官方源的 `windows_x64` 与 `install.sh`（`available`）在不满足其协议与源前提时保持 `null` / `false`，绝不暴露必败入口。
- **`R1-C2` (Resolved)**:
  1. 在 `design.md` §1 与 `specs/im/desktop-client.md` 明确 `DesktopCliOptions` 将 `--im-origin` 与外部协议唤起原始 `deep_link_url` 分离：冷启动、Windows 第二实例转发与 macOS `RunEvent::Opened` 统一进入 `handle_deep_link_url` 状态机，跨服唤起一律进入 `pending_server_switch` 用户确认。
  2. 收到指向公网/官方明文 `http://` 的唤起链接时，保留原 `im_origin` 不变，写入 `deep_link_error` 并唤醒主窗口弹窗明确提示「官方及公网服务必须使用加密 `https://`」，同时补入 `M1` 准出标准。
- **`R1-C3` (Resolved)**:
  1. 修正 `design.md` §3.2 命令名为真实的 `agent.create` / `agent.config.apply` / `agent.config.operation.status` / `node.setup.request`，修正非 Windows `inspectionTimeouts(false)` 基线为 `{ workerMs: 7_000, nodeMs: 8_000, rpcMs: 9_000 }`，并在 `node-rpc.ts` 随慢配置命令附带 `deadline_at`，同步对齐 `packages/channels/src/index.ts:306-309` 的 `serverRequests` 保活窗口。
  2. 在 `design.md` §3.2 明确 `apps/im-server/src/agent-creation.ts:161-166` 改为复用 `CatalogReads` 消除二次冷检，并在 `node.register` ACK 与 `node.capabilities.changed` 异步触发 `readNodeCreationCapabilities` 预热缓存。
  3. 对齐错误码契约：落库前返回 `node_offline` / `node_capabilities_timeout` / `node_capabilities_unavailable`，落库后保持 `ConfigOperations` 既有 `503 config_apply_pending` 与幂等恢复语义不变。
- **`R1-W1` (Resolved)**:
  - 明确 `host-state.json` 的 `ready` 仅在回环宿主与 `seed_ready` 双就绪时置为 `true`（兼容 `packaging/desktop/windows/smoke.ps1` 并将其纳入修改验证）；在存在 `seed-archives/` 且未指定开发目录时阻断 `resolve_active_bundle` 向 `CARGO_MANIFEST_DIR` 回退；首启毫秒级双击撞 `instance.lock` 时执行短时退避轮询唤醒主窗口后 `exit(0)`。
- **`R1-W2` (Resolved)**:
  - 三端统一采用严格 IPv4/IPv6 字面量解析 + `.local` 后缀白名单（修复 `prototype.html` 前缀正则误放 `http://10.evil.com` 问题，移除单标签主机名并注明 CGNAT `100.64.0.0/10` 不纳入明文白名单）；`load_or_init_host_config` 启动时复验持久化 `im_origin`。
- **`R1-W3` (Resolved)**:
  - 在 `design.md` §5 与 `prototype.html` 补齐 `FirstUseWelcome`（`scene=first-use`）在 `1280×720` 下的零滚动紧凑规格；将引导第 2 步 `ModelServicesPanel` 首次添加态主按钮「验证并继续」通过 `form="onboarding-model-form"` 固定在 `.onboarding-footer`；明确第 3 步隐藏重复 `.onboarding-identity-preview` 与紧凑双列排布、`AuthScene` 缩放高度预算，以及 `DesktopServerBar` 原地展开替换（含 `取消` 与私网 HTTP 提示条）。
- **`R1-W4` (Resolved)**:
  - 在 `design.md` `## Runbook for Reviewer` 补齐可直接执行的 worktree 隔离启动、健康检查、视口实测与临时进程/目录回收命令。
- **`R1-R1` / `R1-R2` / `R1-R3` (Accepted)**:
  - 全部采纳：`prototype.html` 清理了所有混入产品画面的演示切换按钮、多余顶栏徽章与第 1 步状态矛盾；补充了 `100.64.0.0/10` 说明；在 `CrewdenDesktop.iss` 补充了 `CloseApplications=yes` 与 `AppMutex`。
