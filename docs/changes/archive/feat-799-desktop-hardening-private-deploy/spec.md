# feat-799: Crewden Desktop 打包运行加固、一屏化引导体验与受控私有化部署

## Relations

- Related: `feat-790`, `feat-781`

## 原始需求

```text
我实际在内部用了下windows的desktop版本，遇到了很多问题，我不知道哪些问题是因为内部需要连单独的IM服务引起，哪些是通用问题。我让agent总结了下：

nano-multiagent 私有化部署问题清单（供上游反馈）
面向仓库：Mrchen116/nano-multiagent（develop @ 3fafe61c5） 场景：Windows 11 内网私有化部署（IM 跑在 WSL2，客户端为本地构建的 Crewden-Desktop-Setup-x64.exe） 说明：以下为上游代码/打包问题，已在真实部署中复现；文末单独列出不属于上游的环境因素。
#-issue-1阻断构建的-manifest-使用短-shagateway-启动校验直接失败 🔴 Issue 1（阻断）：构建的 manifest 使用短 sha，Gateway 启动校验直接失败
#现象 现象
安装客户端后，Gateway 反复输出 Invalid installed release manifest（无间隔刷屏）
界面长期卡在 Binding and starting...（Zero-CLI setup 弹窗），最终 Gateway startup timed out
修复 source_commit 为完整 40 位后，Gateway 立即 ready + connected
#根因 根因
scripts/build-desktop-windows.ps1 -SourceCommit <sha> 允许传短 sha（如 3fafe61c5），scripts/build-desktop-archives.py 原样写入 .release-manifest.json 与 .nano-release.json
packages/product-contracts/src/node-update.ts 的 parseReleaseManifest 要求 source_commit 必须是 40 位完整 sha（/^[a-f0-9]{40}$/），否则返回 null
apps/node/src/release.ts:17 对 null 抛 Invalid installed release manifest
#位置 位置
scripts/build-desktop-archives.py
packages/product-contracts/src/node-update.ts（parseReleaseManifest）
apps/node/src/release.ts
#建议 建议
构建脚本使用 git rev-parse <short> 自动补全为完整 40 位后再写入 manifest
或在校验层统一接受短 sha 并在内部补全
#-issue-2阻断windows-runtime-打包漏-zoddsh-web-的-typert-加载失败 🔴 Issue 2（阻断）：Windows runtime 打包漏 zod，dsh-web 的 typert 加载失败
#现象-1 现象
Gateway 日志：Cannot find package 'zod' imported from .../@deepseek-ai/dsh-web/lib/typert.host.js
伴随 dsh: warning: 1 entry did not activate
typert-loader 报 1 typert contributor(s) failed to register
#根因-1 根因
Windows runtime 目录（runtimes/<hash>/）的 dependencies.json 中没有 dsh-web → zod 的边
p/ 下虽然存在 zod 包（p/bb739deb762aad55），但未被链接到 dsh-web 的 node_modules
@deepseek-ai/dsh-web 的 lib/typert.host.js 直接 import 'zod'（硬依赖）
DSH 的 typert-loader 使用虚拟依赖图解析，不遵循 Node 的标准向上查找，导致手动放置的目录不生效
#位置-1 位置
scripts/build-desktop-archives.py（runtime 依赖收集 / dependencies.json 生成）
上游 @deepseek-ai/dsh-web 的依赖声明
#建议-1 建议
打包 runtime 时确保 dsh-web 的直接依赖（zod 等）被写入 dependencies.json 并创建链接
或在 dsh-web 的 package.json 中补齐 zod 依赖，使 pnpm 依赖图完整
#-issue-3阻断dsh-首次配置检查-30-秒硬超时--创建助手-504 🔴 Issue 3（阻断）：DSH 首次配置检查 30 秒硬超时 → 创建助手 504
#现象-2 现象
IM 服务端日志：{"event":"catalog_refresh","result":"timeout","duration_ms":30454}
前端点击创建助手后一直 loading，最终 504
重试多次仍然每次超时（非"仅首次慢"）
模型 API 本身响应很快（实测 http://127.0.0.1:31943/v1/models 约 178ms）
#根因-2 根因
packages/product-contracts/src/configuration-rpc.ts 的 inspectionTimeouts(windows) 在 Windows 下返回 { workerMs: 30_000, nodeMs: 32_000, rpcMs: 35_000 }
DSH 的 configuration-inspection（preview/inspect）加载 505 个包并做模型校验，超过 30 秒即被 worker 判超时
catalog-reads.ts 将超时映射为 504，前端 onboarding 显示通用错误 “Your computer has not confirmed creation”
#位置-2 位置
packages/product-contracts/src/configuration-rpc.ts:84-88
apps/im-server/src/catalog-reads.ts:86-100
#建议-2 建议
增大 Windows 下的 workerMs（如 120s），或对首次 inspect 做预热/缓存
或返回明确的"检查中"状态让前端轮询，而不是硬超时后返回通用错误
错误信息应携带具体失败原因（node_capabilities_unavailable / timeout），便于用户自查
#-issue-4设计限制内网-http-部署不显示桌面客户端下载入口 🟠 Issue 4（设计限制）：内网 http 部署不显示桌面客户端下载入口
#现象-3 现象
通过 http://<LAN-IP>:8011/#download 访问时，Windows 客户端卡片显示"未发布"，无法下载
GET /im/v1/public/install 返回 desktop_win32_x64: null
#根因-3 根因
apps/im-server/src/install.ts 的 allowsDesktopConnectOrigin 仅允许 https: 或 loopback http:（127.0.0.1/localhost/[::1]）
内网 http://10.x.x.x:8011 不满足条件，desktop_win32_x64 被置为 null
#位置-3 位置
apps/im-server/src/install.ts:18-21（allowsDesktopConnectOrigin）
apps/im-server/src/install.ts（installMaterials）
#建议-3 建议
允许私有网段 http（10.* / 192.168.* / 172.16-31.*），或提供显式配置项（如 IM_ALLOW_INSECURE_ORIGIN=true）
私有化/内网部署是常见场景，不应强制 https 或 localhost
#-issue-5设计限制manifest-下载地址硬编码-github-release无法自托管 🟠 Issue 5（设计限制）：manifest 下载地址硬编码 GitHub Release，无法自托管
#现象-4 现象
内网用户无法访问 GitHub，安装包无法下载
即使自托管安装包，manifest 校验也会拒绝
#根因-4 根因
packages/product-contracts/src/node-update.ts 的 parseReleaseManifest 强制：
const base = `https://github.com/Mrchen116/nano-multiagent/releases/download/${tag}/`; if (typeof v.package !== 'string' || v.download_url !== base + v.package) return null;
即 download_url 只能是 GitHub Release 地址，任何自托管/镜像地址均被判无效
#位置-4 位置
packages/product-contracts/src/node-update.ts:61
#建议-4 建议
支持可配置的下载基地址（环境变量或 manifest 字段），使私有化部署可自托管安装包
或在 installMaterials 中允许"本地自托管包"分支（当前需自行改代码绕过）
#-issue-6设计限制客户端安装后默认连官方-im安装包无法预设部署地址 🟠 Issue 6（设计限制）：客户端安装后默认连官方 IM，安装包无法预设部署地址
#现象-5 现象
内网用户安装后默认连接 https://im.crewden.work（内网不可达）
必须手动设置环境变量 CREWDEN_DEFAULT_IM_ORIGIN=http://<LAN-IP>:8011 或命令行 --im-origin 才能连内网
#根因-5 根因
apps/desktop/src/config.rs 的 DesktopCliOptions::default() 仅在环境变量 CREWDEN_DEFAULT_IM_ORIGIN 存在时覆盖，否则硬编码 https://im.crewden.work
packaging/desktop/windows/CrewdenDesktop.iss 安装时未写入默认 origin（快捷方式/环境变量/注册表均无）
安装包 manifest 中的 download_url 指向 GitHub，未提供部署 origin 的传递通道
#位置-5 位置
apps/desktop/src/config.rs:331
packaging/desktop/windows/CrewdenDesktop.iss
#建议-5 建议
安装包支持"预设 IM origin"：构建时注入或安装时写入（iss 的 [Registry]/快捷方式参数）
或支持从安装材料（/im/v1/public/install 的 origin）在首次启动时自动写入
#-issue-7兼容deep-link-只允许-https--loopback-http 🟡 Issue 7（兼容）：deep link 只允许 https / loopback http
#现象-6 现象
crewden-desktop://connect?origin=http://10.x.x.x:8011 被拒绝
错误：“Deep-link origin must use https:// (or loopback http://)”
#根因-6 根因
apps/desktop/src/config.rs 的 parse_deep_link_origin 只允许 https 或 loopback http
#位置-6 位置
apps/desktop/src/config.rs:124-128
#建议-6 建议
与 Issue 4 一致，允许私有网段 http，便于内网部署通过网页一键拉起客户端并切换服务器
#-issue-8体验安装后首次启动无窗口无托盘反馈且静默退出无错误 🟡 Issue 8（体验）：安装后首次启动无窗口/无托盘反馈，且静默退出无错误
#现象-7 现象
安装完成点击"立即启动"后，看不到窗口，也没有托盘图标（用户以为没启动）
再次手动启动才出现
某些情况下进程启动后立即退出，无任何可见错误
#可能根因 可能根因
首次启动需要解压 runtime（76MB）并初始化 DSH，期间无进度反馈
forward_to_running_instance / .gateway-lifecycle.lock / .gateway-runtime.lock 的残留锁会让新实例"转发后退出"或"检测到实例后退出"，且不提示
main.rs 的错误仅 eprintln!，GUI 子系统（windows_subsystem = "windows"）下不可见
#位置-7 位置
apps/desktop/src/lib.rs（run_from_env / forward_to_running_instance）
apps/desktop/src/main.rs
#建议-7 建议
首次启动显示 splash/进度（“正在准备运行时…”）
启动失败写日志文件并弹窗提示（而不是静默退出）
残留锁/状态应自动清理并给出说明
#️-不属于上游的问题本机环境仅供参考 ⚠️ 不属于上游的问题（本机环境，仅供参考）
WSL2 的 IPv6 被公司策略禁用（HKLM\SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters\DisabledComponents=0xff），导致：
WSL 的 localhost forwarding 失效（依赖 IPv6 loopback）
networkingMode=mirrored 无法启用，回退 NAT
已用 netsh interface portproxy + IPv4 直连绕过
Hyper-V 防火墙默认阻止 WSL 入站（MPSSVC_DEFAULT_RULE_INBOUND_* = Block），需手动设为 Allow 或加放行规则
Windows 端口转发/防火墙为部署环境配置，与产品代码无关

另外，我个人体验上发现，就在登录页，以及首次进入的配置页，就很奇怪了。desktop版本竟然也是一个滚动的版本，我理解作为桌面软件，这些页面都没必要滚动。

你帮我审视下问题，看哪些是真问题，哪些是误判。
```

补充需求原话：

```text
我希望你发现真问题，并检查周边问题。然后新开一个unit统一修复。
```

```text
以及本unit应该也做一个事情，win desktop版本应该安装的时候可以选择带桌面快捷方式（默认）
```

```text
如果走的官方IM服务，如果http是不是有安全风险？也跟我说下这个问题
```

> [!NOTE] Agent 审计与范围解读
> - **通用真问题（与是否独立部署 IM 无关）**：Issue 1（构建传短 SHA 致安装清单校验失败，且周边含 macOS 打包同病、Windows 内嵌种子清单安装包哈希失真、后台确定性启动崩溃时无退避刷屏与前端盲等超时）、Issue 2（三端受管包共用图构建在多版本与漏声明依赖场景下缺失 `zod` 等包，导致内置 Web 能力激活失败且冒烟漏检）、Issue 3（Windows 实时杀软与大量小文件下冷启动能力检查及配置应用多层超时、未做连接后后台预热与创建缓存复用、错误提示笼统）、Issue 8（首次启动解包在建窗口与单实例互斥之前同步执行，15~45 秒无界面且二次点击并发写缓存冲突闪退、GUI 子系统无日志无报错弹窗、无路由唤醒误跳走当前页）、桌面端登录/注册与首次三步引导页沿用长网页留白导致在标准桌面窗口内整页滚动，以及 Windows 安装向导缺少默认勾选的桌面快捷方式选项。
> - **独立 IM 私有化部署限制与分层安全边界**：Issue 4~7 源于此前仅面向官方公网 HTTPS 与 GitHub Release 固定源设计（且已有构建脚本 `--base-url` 存在生成包自爆的周边缺陷）。针对官方与公网环境放开明文 HTTP 存在凭据嗅探、恶意网页唤起钓鱼切服、更新中间人篡改远程执行与协议降级高危风险，本单元确立「官方/公网默认严格 HTTPS 零退化 + 私有化显式受控开启 + 外部唤起切服强制用户确认 + 自托管发布源受信绑定」边界。

## 澄清记录

- Q1: 新建的统一修复单元（Change Unit），对「内部独立 IM / 内网私有化部署（Issue 4~7）」希望纳入到什么深度？
  A: (Recommended) 全部纳入同一 feat 单元：修齐通用阻断/启动体验 + 桌面端登录与引导免滚动 + 完整支持独立 IM 私有化部署（受控放行内网 HTTP 下载与唤起、安装包/构建预设默认 IM 地址、支持自托管安装包与受管更新源）
- 补充确认 1（用户主动提出）：Windows Desktop 安装包在安装向导中提供「创建桌面快捷方式」勾选项，且默认勾选。
- 补充确认 2（用户安全关切澄清）：用户询问「如果走的官方IM服务，如果http是不是有安全风险？也跟我说下这个问题」，针对我们提出的分层边界（「因此 feat-799 采用『官方/公网默认严格 HTTPS 零退化 + 私有化显式受控开启』」）明确确认：「可以的，按你说的来」——即官方 IM 服务及公网地址严格保持仅允许加密 HTTPS（及本机开发回环），禁止降级为明文 HTTP；内网明文 HTTP 仅在私有化部署显式启用且限定私网范围时放行，且所有外部唤起切换不同服务地址的操作均须用户在应用内明确确认（明文内网连接额外展示未加密风险提示）。

## 用户场景

### 1. 构建发布、Windows 快捷方式与节点启动故障快速可见
运维或发布人员在构建 macOS 或 Windows 桌面安装包时，无论传入短提交号还是完整提交号，构建流程都会在产出安装包前解析并校验完整的版本身份，且包内种子清单与外部发布清单保持一致；传入非法提交引用或不受支持的发布地址时在构建期直接报错中止，不会产出安装后无法启动的坏包。Windows 用户运行安装向导时，默认已勾选「创建桌面快捷方式」（也可取消勾选），安装完成后可从桌面或开始菜单直接打开应用。安装后的受管运行环境完整包含内置工具与 Web 能力所需的依赖包，启动后所有内置能力正常就绪、不产生缺包告警。若本机后台节点因清单损坏或配置错误发生确定性启动失败，后台不会无间隔死循环刷屏，客户端绑定界面也会立即结束等待并展示具体失败原因与日志查看指引，而非卡在加载中直到两分钟超时。

### 2. 首次启动即时反馈、单实例防冲突与致命错误可诊断
Windows 或 macOS 用户首次安装完点击「立即启动」或双击图标打开 Crewden Desktop 时，即使首次准备内置运行环境需要数十秒，屏幕上也会立即出现应用窗口展示「正在准备运行环境…」进度状态并创建系统托盘/菜单栏图标，让用户明确知道程序已启动。在首次准备期间或日常运行中，若用户再次双击桌面/开始菜单图标，新进程不会与正在准备或运行中的实例争抢文件导致闪退，而是直接唤醒并聚焦现有窗口，且保留用户当前正在操作的登录页或首次设置页（除非外部唤起明确指定了目标会话路由）。若宿主在窗口就绪前遇到端口、目录权限或归档损坏等致命启动错误，会将详细原因追加写入本机宿主日志文件并弹出系统原生错误提示框，不再静默消失。

### 3. Windows 电脑首次连接、能力预热与个人助手顺畅创建
在开启实时防病毒扫描的 Windows 10/11 电脑上，当用户完成本机绑定或验证保存模型服务后，系统会在后台提前预热本机运行能力目录，同时桌面客户端代理、中心服务与本机运行环境全链路为冷启动能力检查和首次配置落地预留一致且充裕的完成窗口。用户在首次引导第三步填好名称点击「创建个人助手」时，优先复用已确认的能力目录并顺畅完成创建进入私人对话；即使遇到冷启动较慢也能在单次请求内完成，不会反复在固定秒数被强杀导致重试永远失败。若因电脑刚离线、模型能力暂不可用或确认超时未能完成，引导页保留已填写的名称、头像与协作范围，并区分展示「电脑已离线」「正在准备运行能力，请稍后重试」或「创建确认超时」等具体原因。

### 4. 官方公网严格 HTTPS 保护与企业内网私有化部署闭环
使用官方发行版连接官方 IM 或公网服务时，系统保持零安全退化：下载入口、外部链接唤起与受管更新均要求加密 HTTPS（本地开发回环地址除外），且禁止将官方域名或公网服务地址切换为明文 HTTP。在企业内网独立部署场景下：
- 运维人员显式开启内网私有化 HTTP 支持并配置自托管安装包/更新包发布地址后，内网用户通过局域网地址访问网页下载页或首次引导页时，可直接看到并下载桌面客户端安装包，也可点击「打开桌面客户端并连接当前服务」；
- 运维人员在构建或打包企业内部分发安装包时，可预设默认内部 IM 服务地址与受信自托管发布源——员工安装后首次打开客户端即默认指向企业内部 IM 服务（无需先连不可达的公网默认域名，也无需手动配环境变量），后续在客户端内触发受管更新时也能从该受信自托管发布源安全下载校验并完成升级；
- 无论公网 HTTPS 还是受控内网 HTTP，凡由外部唤起链接请求切换到与客户端当前已保存服务不同的新服务地址时，客户端都会唤醒主窗口并弹出明显的服务切换确认提示（展示目标服务地址，若为未加密内网 HTTP 额外醒目标示「未加密内网连接，请确认处于受信任局域网」），仅在用户点击确认后才执行切换，防止恶意网页静默劫持登录入口。

### 5. 桌面客户端登录、注册与首次设置的一屏化原生体验
用户在桌面客户端标准窗口尺寸（`1280×840`）以及常见高分屏缩放下的桌面视口（高度 `720px` 及以上）打开 Crewden Desktop 时，登录页、注册页、首次欢迎页、三步助手引导页与聊天空态引导页均采用紧凑、平衡的桌面软件视口布局：省去浏览器营销页式的高顶栏与大幅上下留白，整张页面稳定落在一屏之内，主页面外框不出现整页垂直滚动条，标题、核心表单与底部主操作按钮同屏直达；当用户在模型连接步骤展开较长表单或列表超出卡片可用高度时，仅在右侧卡片内容区域内部平滑滚动，左侧步骤进度与底部主操作区保持稳定可见。普通浏览器访问公共官网首页与移动端窄屏访问时，仍保留各自原有的响应式阅读与导航体验。

## 验收标准

### Requirement: 桌面发行构建校验完整版本身份、提供默认勾选的 Windows 桌面快捷方式并确保内置能力无缺包

#### Scenario: 使用短提交号构建安装包并在受管环境完整激活内置能力
- **GIVEN** 运维或发布人员基于有效提交（传入短提交号或完整提交号）构建桌面客户端安装包并在目标电脑完成安装与本机连接
- **WHEN** 本机后台节点启动并加载全部内置运行能力（含内置 Web 检索/抓取能力声明）
- **THEN** 本机节点正常就绪上线且包内版本身份与外部发布清单一致，运行日志中不出现安装清单无效错误，也不出现因缺失依赖包导致内置能力模块激活失败的告警
- **WHEN** 构建时传入无法解析的提交标识或不合法的发布基地址参数
- **THEN** 构建命令直接报错退出并指出具体参数问题，不生成损坏的安装包或清单文件

#### Scenario: Windows 安装向导默认勾选桌面快捷方式并支持用户取消勾选
- **WHEN** 用户在 Windows 10/11 上运行 Crewden Desktop 安装程序进入安装选项页
- **THEN** 向导默认勾选「创建桌面快捷方式」选项；保持默认完成安装后，用户桌面与开始菜单均生成可正常启动应用的快捷方式
- **WHEN** 用户在安装向导中取消勾选「创建桌面快捷方式」（或静默安装未启用桌面图标任务）并完成安装
- **THEN** 开始菜单快捷方式正常生成，用户桌面不强制创建快捷方式

#### Scenario: 本机后台节点发生确定性启动失败时快速反馈具体原因
- **GIVEN** 本机受管安装文件或本地配置损坏导致后台节点进程启动即刻退出
- **WHEN** 用户在客户端内点击绑定或启动这台电脑
- **THEN** 客户端在数秒内结束启动等待并展示包含具体失败原因的错误提示与本机日志查看入口，后台守护进程不会无间隔死循环重启刷屏

### Requirement: 桌面客户端首次启动即时呈现准备进度、保证单实例唤醒并暴露致命启动故障

#### Scenario: 首次安装后启动在准备运行环境期间立即展示窗口进度与托盘图标
- **GIVEN** 用户首次安装完 Crewden Desktop，本机尚未解包内置运行环境
- **WHEN** 用户在安装完成页点击「立即启动」或从快捷方式启动应用
- **THEN** 应用立即显示带有「正在准备运行环境…」状态提示的窗口并注册系统托盘/菜单栏图标，准备完成后自动进入登录或工作台界面，全程不出现无窗口无托盘的空白等待期

#### Scenario: 准备期间或运行中重复启动图标仅唤醒聚焦当前页面而不冲突闪退
- **GIVEN** Crewden Desktop 正在执行首次运行环境准备，或已停留在登录页/首次设置引导页
- **WHEN** 用户再次双击桌面或开始菜单快捷方式启动应用（未携带特定深链目标路径）
- **THEN** 新启动请求不会引发文件占用报错或静默退出，已有应用主窗口被唤醒置顶并保持当前所在的准备页、登录页或首次设置步骤，不会被强制跳转到其他页面

#### Scenario: 宿主发生致命启动错误时落盘诊断日志并弹出原生可见提示
- **WHEN** Crewden Desktop 在窗口就绪前遇到归档损坏、目录不可写或本地服务无法绑定等致命启动错误
- **THEN** 客户端将带时间戳的详细错误原因写入本机用户数据目录下的宿主日志文件，并弹出系统原生错误提示框说明原因与日志位置，不会无声无息退出

### Requirement: Windows 电脑在冷启动检查下稳定完成个人助手创建并给出可区分的失败反馈

#### Scenario: Windows 电脑完成模型连接后顺畅创建个人助手
- **GIVEN** 用户在 Windows 10/11 上通过 Crewden Desktop 连接本机并完成模型服务验证（即使本机首次冷启动能力检查耗时超过 30 秒）
- **WHEN** 用户在首次设置第三步输入助手名称并点击「创建个人助手」
- **THEN** 个人助手在单次操作内成功创建并自动进入私人对话，不会因中间代理或前序能力检查硬超时而反复报创建未确认

#### Scenario: 创建个人助手受阻时保留草稿并区分展示具体原因
- **GIVEN** 用户在首次设置第三步填写了助手名称、头像与协作范围
- **WHEN** 提交创建时遇到本机刚离线、运行能力检查繁忙/不可用或节点确认超时
- **THEN** 页面完整保留用户已填草稿，并根据实际原因分别展示「电脑暂时离线」「正在获取电脑运行能力，请稍后重试」或「电脑确认超时，点击核对同一助手结果」等明确提示，不将能力检查失败笼统混报为同一文案

### Requirement: 官方及公网连接严格保持 HTTPS 安全边界，并受控支持独立 IM 私有化部署与自托管分发

#### Scenario: 默认安全模式下官方服务与公网地址严格拒绝明文 HTTP 降级与静默唤起
- **GIVEN** IM 服务未显式开启内网明文 HTTP 模式，或目标地址为官方域名及公网非私网地址
- **WHEN** 客户端收到指向公网明文 `http://` 的外部连接唤起链接，或用户在客户端服务切换栏输入官方域名/公网地址的 `http://` 形式
- **THEN** 客户端拒绝该不安全地址并明确提示公网与官方服务必须使用 `https://`（本机开发回环地址除外）

#### Scenario: 企业内网私有化部署预设内部服务地址、受控开放私网连接与自托管安装更新
- **GIVEN** 企业运维人员在私有化 IM 服务端显式启用内网私有化连接与自托管发布包配置，并使用预设了内部 IM 服务地址与受信发布源基地址的构建参数打包桌面客户端
- **WHEN** 内网员工通过局域网访问 Web 下载/引导页下载安装该桌面客户端并首次打开
- **THEN** Web 页面正常展示桌面客户端下载与一键连接入口；员工安装打开客户端后默认连接该企业内部 IM 服务（无需先请求不可达的官方公网域名或手动设置环境变量）
- **AND** 后续企业发布新版本至该受信自托管发布源时，客户端可在应用内校验并完成受管更新，同时拒绝指向非该受信源或未授权明文地址的更新包

#### Scenario: 外部唤起链接请求切换不同 IM 服务地址时须经用户确认
- **GIVEN** Crewden Desktop 当前已指向某一 IM 服务地址
- **WHEN** 用户从浏览器点击连接唤起链接请求切换到另一个不同的 IM 服务地址（包括另一 `https://` 服务或已获受控允许的内网私网 `http://` 服务）
- **THEN** 客户端唤醒主窗口并展示服务切换确认提示（列出当前服务与目标服务地址；若目标为内网明文 `http://`，额外显著提示该连接未加密、仅应在受信任内网确认）
- **AND** 用户点击取消时保留原服务与原登录会话不变；仅在用户点击确认后才切换目标服务并隔离会话数据

### Requirement: 桌面客户端登录、注册与首次引导页面适配桌面视口一屏呈现无需整页滚动

#### Scenario: 标准桌面窗口与常见高分屏缩放下登录、注册及首次引导主框架一屏完整可见
- **GIVEN** 用户在桌面客户端默认窗口尺寸（`1280×840`）或常见高分屏缩放后的桌面视口（宽度 `≥1024px`、高度 `≥720px`）中打开应用
- **WHEN** 用户浏览登录页（含服务地址栏及展开编辑态）、注册页、首次欢迎页、三步设置引导页各步骤初态及聊天空态引导页
- **THEN** 各页面以紧凑协调的桌面布局一屏呈现核心信息、输入项与底部主操作按钮，外层页面容器不出现整页垂直滚动条
- **AND** 当用户在设置引导卡片内展开超出卡片高度的动态表单或列表时，仅卡片内容区内部可滚动且底部返回/继续/创建主操作栏保持可见；浏览器端公共官网首页与移动端窄屏响应式布局保持正常

## 范围与非目标

- **在范围**：
  - 桌面端（macOS / Windows）与 Windows 轻量受管安装包的提交号归一化校验、种子清单一致性、受管运行时依赖图完整性（补齐漏链与多版本兜底）及构建冒烟断言加固；
  - Windows Desktop 安装向导增加默认勾选的「创建桌面快捷方式」任务选项；
  - 桌面客户端首次启动单实例互斥锁、运行环境解包期间的即时准备窗口与托盘反馈、无路由重复启动的原页面聚焦保持，以及宿主致命启动错误的日志落盘与原生弹窗提示；
  - 本机后台节点确定性启动崩溃的退避保护与快速错误透传，以及 Windows 下冷启动能力检查、连接后后台预热、创建缓存复用与跨层（桌面代理 / IM 服务 / 节点检查与配置应用）超时对齐和可区分错误提示；
  - 保持官方与公网默认严格 HTTPS 零退化前提下，支持独立 IM 私有化部署的显式内网私网 HTTP 开关、构建/打包预设默认 IM 地址、受信自托管安装包与受管更新源，以及外部唤起跨服切换的应用内确认机制；
  - 桌面客户端下登录、注册、首次欢迎页、三步引导页与空态引导页的视口一屏化紧凑布局改造。
- **非目标**：
  - 不对官方服务或任意公网非私网域名放开明文 `http://` 登录、唤起或自动更新；
  - 不在客户端或安装程序内自动篡改企业组策略禁用的宿主机系统级网络栈（如 Windows 注册表 IPv6 禁用项或 Hyper-V 全局防火墙策略）；
  - 不重做普通浏览器公共营销着陆页（`/about`）的长页面叙事结构或 iOS 原生客户端界面。
