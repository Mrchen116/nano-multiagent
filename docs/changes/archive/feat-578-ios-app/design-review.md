# feat-578 Design Review

## Round 1

### Metadata

- reviewer_target: `/root/ios_design_review`（独立于 author `/root`）
- review_mode: `full`
- mode_reason: 首轮无历史 Round；覆盖首文档、全部设计决定、delta、原型与唯一 milestone。
- started_at: 2026-10-05T00:29:59+08:00
- completed_at: 2026-10-05T00:33:46+08:00
- duration: 227 seconds（显式计时的综合复核与报告阶段；之前的阅读/交互未记录精确起点，不计入此数）
- checkout: `/Users/czj/Repos/nano-multiagent`，`main`；报告时 HEAD `1daf6676debe129088d9bd0612b489d1eba0301a`。受审首文档 `ae625313c`，产品基线 `e6a5c0ea5`；`git diff --name-only e6a5c0ea5 HEAD -- src/IM` 为空。
- author/design revision: 当前未提交设计快照；review 期间只写本报告，不改受审文档、代码、分支或提交。不触碰主 chat 的 iPhone/Mirroring/Chrome 或 Mini 服务。

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING。Gate 2 未通过。**

全原生、首版 Web 全量管理、当前 Mac 构建与 Mini AltServer 的用户决定保持不变。客户端职责和主要协议方案可行；目前阻断是必验资源未落实、真机隔离接入方案不闭合，以及一个错误的 Work 原型入口。不能把这些问题改写成“已批准、实施时再解决”。

### Coverage 与证据

| 受审面 | 独立核对与结论 |
|---|---|
| 首文档与范围 | 读取 `spec.md` R1–R12 / S1–S30，与 `coverage.md` C01–C34、设计模块和 M1 退出标准对账。首版保留聊天、Tasks、Agent/Work/创建/配置/Skills/心跳/cron/通道、绑定/节点、账号/公司/策略/容量；没有将高级管理延期，也没有混入 APNs、离线发送队列、额外扩展或手机执行 Agent。 |
| 实际产品组装 | 从 `src/IM/frontend/src/app/router.tsx` 核对活跃页面，从 `src/IM/app.py:528` 的真实 router 装配核对 auth、account、agents、Work、task graph、channels、web_im、messages、images、nodes、policies；并非只读测试替身。`AgentProfilePage` 对非 owner 使用公开 contact 与 global Work，不读取 writable config。 |
| Auth / WS / 消息恢复 | `api/routes/auth.py:179`、`:210`、`:263` 支持显式程序 token pair、refresh 与 Bearer ticket；`app.py:597` 和 `api/public_boundary.py:31` 执行精确 Origin 与当前 session/公司资格检查。设计的 Keychain/session generation、单次 refresh、前后台取消、消息幂等键、快照/resume 和历史不补弹符合既有边界。`messages.py:436` 实际接收 `Idempotency-Key`，先持久化后 relay 可返回 503，设计已处理不确定结果。没有要求为 iOS 放宽后端鉴权。 |
| 管理与数据面 | 对照 current `auth-tenancy.md`、`agents-nodes.md`、`agent-work.md`、`task-graphs.md` 及实际配置/通道/策略 API 调用。已覆盖版本冲突、apply pending、owner/admin 区分、明文密钥不可读、desired/observed/removal、公司准入、只读策略、受保护附件及任务不直接执行。`policies-page.tsx:31` 确认容量为 `/im/v1/attachments/capacity`。Cron 路径与 Sessions 占位漂移已被设计明确说明，不应发明新后端能力。 |
| 架构职责与复用 | HTTP/WS 会话、鉴权、恢复、受保护媒体适合放在原生 Client/Session/UserStream；草稿和分页属于 feature store；实际业务权限、配置 apply 和 Gateway 中继继续由 IM/PA 承担。复用现有协议比新增 iOS backend 或跨端 UI schema 更小且可审；SwiftUI/必要 UIKit 和 Markdown AST 是实现完整原生所需，不是额外平台抽象。没有 Python 包反向依赖或 iPhone 直连 Gateway。 |
| 原型 / 当前风格 | 独立读取 `output/feat578/current-web-{chat,agent,me}-600.png`，与原型 390 配置顶部/底部、600 普通成员策略截图及后台 IAB 的 430 实际画面对照。四入口、浅色分组、青绿主操作、详情返回与底栏隐藏保持清楚；已读画面未发现遮挡或拥挤到妨碍操作的新增问题。见下述交互检查；W3 为实际语义错误而非审美偏好。 |
| Delta 与归并 | `specs/im/ios-client.md` 的 ADDED 要求针对 iOS 独立入口、会话隔离、媒体、提醒和免费维护，canonical target 为 `docs/specs/im/ios-client.md`；没有 MODIFIED 删除旧 Scenario。设计安排更新 IM 短索引/消费者、docs 地图与构建/运维入口；未提前覆盖 current。现有业务语义仍由对应 current areas 承担。 |
| Milestone 与资源 | `M1-native-app` 只有 `.gitkeep`，未预填 tasks/progress；单 M1 作为完整可安装客户端交付合理，范围、依赖及 reviewer/worker 双轨均明确，含原生、真栈、真机、签名维护和独立 gates。资源与真实入口仍有 W1/W2，退出标准本身不能证明可执行。 |
| 免费安装与恢复 | 独立打开 Apple developer account 与 AltStore 官方安装文档复核免费维护路径；Apple 当前说明 Personal Team profile 7 天。安装计划正确区分 unsigned archive、AltStore 重签、拔 USB 同网刷新和过期恢复；要求保持同一 identity、不先卸载、不重启生产 IM/Gateway。自然过期恢复仍属未来 M1 实测，不要求设计阶段提前验收未实现 App，也不把手动提前刷新替代过期恢复。 |

官方证据：[Apple Developer account overview](https://developer.apple.com/help/account/basics/about-your-developer-account)、[AltStore macOS 安装](https://faq.altstore.io/altstore-classic/how-to-install-altstore-macos)。外部文档能证明能力与前提，不能证明本机已具备这些条件。

### 原型独立交互记录

后台 IAB 打开 `http://127.0.0.1:58781/prototype.html`；未使用用户正在下载 Xcode 的 Chrome。

1. 聊天 → 产品讨论 → 选择审批结果 → 本次允许：返回聊天显示“已提交，等待确认”，未冒充实际完成；详情不显示全局导航。此为演示语义检查。
2. 任务 → 原生 App 方案 → 原生交互设计 → 回到产品讨论并引用：引用进入 composer，未自动发送；节点详情、前后关系、子任务和返回可见。
3. 演示身份切换“普通成员 / 非 Owner” → Agent → 列表中标为“单 Thread”的日常助手 → 工作记录：仍进入主/子执行与权限页。与实际 Work 可用范围矛盾，见 W3。
4. 独立目视作者已保存的 390 配置长表单上/下部及 600 只读策略画面：主要字段与保存入口可达，普通成员没有保存/容量入口。与当前 Web 截图对照后，原生分组形式属于既有授权内的实现变化。

这里不将 HTML、AX/DOM、截图认定为 SwiftUI、中文 IME、真实键盘、Dynamic Type、VoiceOver、系统分享、后台恢复或签名已通过。上述原生行为保留在 M1，不构成本轮提前索要实现。

### 历史问题闭环

无历史 Round / Author Resolutions。本轮三个 WARNING 均为新问题、状态 `open`。

### Issues

#### R1-W1 — 必验构建、真机与 Mini 续签资源尚未落实

- 位置：`design.md:151–160`；`installation-plan.md:33–43`；M1 依赖及 S29–S30。
- 证据：受审文件明确 Xcode/runtime 未完成、真机时段/Apple 身份/配对/Developer Mode 未落实、Mini SSH 超时而 AltServer 版本/进程/GUI/同网条件未知。review 期间 author 补充：官方 Xcode 26.4.1 已解包安装且 codesign 检查成功，但首次启动停在协议，平台尚未安装；第二次 Mini SSH 仍超时。该补充推进了准备，未消除资源缺口。author 另补充专用 Lark profile `verified=true`、App ID 匹配且 bot ready；不因其 user token `needs_refresh` 单独推断 Bot 不可用，但真实通道试验的独占使用仍需确认。
- 未修后果：M1 所需原生构建/真机输入/安装维护旅程没有可用运行条件；继续实施等于绕过当前流程明确的验收前置，不能只列“稍后安排”。
- 闭环要求：按各必验旅程落实并记录工具链/平台、可用真机时段与用户侧签名/配对条件、Mini AltServer/GUI/同网资源和测试 Bot 独占来源；不要求提前完成未实现 Nano 的产品验收。资源事实更新后复核；若希望改变验收前置或替代标准，必须有用户明确调整。
- 规则来源：[`change-design-author` 原型与验收前置](../../../.claude/skills/change-design-author/references/prototype-and-runbook.md#实施验收前置) 第 44 行：“未落实的必验资源阻塞 Gate 2；只有用户明确调整验收范围或授权替代验证后才能改变标准。”这是显式要求，不是 reviewer 自加批准步骤。

#### R1-W2 — Release 真机到隔离 IM 的接入路径尚不闭合

- 位置：`design.md:82`、Runbook 隔离 IM/Gateway 行（`:146`）；`installation-plan.md:24`。
- 证据：设计仅允许 Release 使用 HTTPS origin，Debug 例外仅 loopback；安装计划又要求 iPhone 的全量管理测试连接隔离栈。唯一给出的 `scripts/e2e-up.sh:253–254` 将 `IM_PUBLIC_URL` 固定成 `http://127.0.0.1:$IM_PORT` 且 uvicorn 只监听 127.0.0.1。iPhone 的 loopback 是手机自身；目前没有手机可达的隔离 HTTPS endpoint、可信证书/代理及相应 WS Origin 配置。现有 Vite origin 只解决 Mac 浏览器预览。
- 未修后果：即使 W1 硬件全部到位，按 runbook 仍无法从已签名 Release App 登录隔离服务；可能被迫切生产对象测试，或临时放宽网络/证书/ATS 边界，与既定隔离验收矛盾。
- 闭环要求：确定一个具体的真机隔离 HTTPS 接入方案，记录地址来源、代理/证书/监听/停止健康检查及精确 WS Origin 配置，验证手机可达性；继续隔离数据库、node identity 和测试对象，不改生产服务。无需新增 iOS backend 或通用联网框架。

#### R1-W3 — 原型给 single_thread Agent 提供了 global Work 入口

- 位置：`prototype.html:36–38`（agents/publicagent），与 `design.md:94` 和 P3 must-match 冲突。
- 证据：真实渲染中“日常助手”列表明确标记“林 · MacBook · 单 Thread”；进入后文案说可查看工作记录并可继续进入主/子执行。实际装配的 `AgentProfilePage` 在 `src/IM/frontend/src/features/settings/agents/agent-profile-page.tsx:28,75` 只对 `work_mode === "global"` 开启 Work；`src/IM/api/routes/agent_work.py:13–23` 对非 global 返回 404。设计正文也明确 Work 沿既有全局 Agent 语义。
- 未修后果：P3 被列为 must-match，但按该入口实施会给当前不支持的 Agent 模式提供必然失败页面，或误导实现者扩展首版既有业务范围。
- 闭环要求：原型将模式与可用 Work 入口对齐；非 owner global 可阅读，single_thread 不显示不存在的 Work。若要演示非 owner global Work，使用明确的 global 示例并保留另一 single_thread 示例的正确入口。重新点击受影响路径即可，不需重画全产品。

### Recommendations

无额外非阻断建议；不要求为假想边界新增抽象或扩大 milestone。

### 受审快照

SHA-256（便于后续 reviewer 区分本轮受审内容与 author 修订）：

| 文件 | SHA-256 |
|---|---|
| spec.md | `db446fad0d9dad9b50551ae492f78d3cae3ea62bd64b61baacf7916f46f5222b` |
| design.md | `ecd959b0c3de5b5c0c339c35638828aecc3de557de83a07671c6329f367d1d2c` |
| coverage.md | `bb940794312efa878c6710a1228c5a59355a4868b93344012b983e7c8368229f` |
| prototype.html | `3a5c71ccc730ba6ebde28baa976ad064314da12cf43cd25e26e683d24de8a96c` |
| installation-plan.md | `e2ba373d145cde984cd9198bd85f030d4187388c53227403fcbf54041fd38bdc` |
| specs/im/ios-client.md | `a760e17cfe34c084d96d50c31b2841971e4832cefe2dc6603a4442c11462551e` |
| evidence/design-validation.md | `f62c63ccdf9fdaf5446299d9bb03e5fdb9d86be5e67826268d11764935668d0a` |

Author 后续只追加 resolutions；本轮结论和问题不回写。下一轮 reviewer 按实际变化选 closure/delta/full；仅改 W2 的有界接入方案、W3 原型入口及 W1 资源证据时，可以限定为对应变化和闭环复核。

### Author Resolutions（R1 后追加）

- R1-W1 — accepted / open。Xcode 26.4.1 已装且 Apple 签名校验通过；用户已明确同意协议，iOS runtime 安装中。Mini 第二次 SSH 仍超时；真机时段、配对和 AltServer 未落实。未改变范围，未声明 Gate 2 通过。
- R1-W2 — accepted / design corrected，连通证据仍 open。新增 `evidence/device-access-plan.md`，选定 tailnet-only Tailscale Serve、独占 HTTPS 端口、可信证书、精确 Origin 与前台进程清理，不改 Release TLS 要求；实际手机连通等待 W1。
- R1-W3 — accepted / corrected。移除原型 `publicagent` 中 single_thread 的 Work 入口与错误说明，保留 private chat；全局 Agent 的非 owner Work 示例由已有 global 调研 Agent 在普通成员身份下演示。复查证据见 design-validation 的 R1 修订记录。

### Author Resolutions 补充：用户调整前置时机

- R1-W1 — accepted as factual gaps / sequencing changed by user。用户明确回复“你这么着急需要真机了吗？”、“你还没做出来呢，着啥急”。author 接受纠正：先做出原生 App、SDK 构建与模拟器验证，有可安装版本后再安排真机/Mini/配对/同网和通道资源；仍保留最终真机与续签验收全部要求。不是把未验证资源改写为已准备，也没有授权占用手机。当前 Xcode/SDK 与 SwiftUI 类型检查已通过，runtime 下载中，证据见 toolchain-readiness。
- R1-W2 — accepted / design corrected。隔离 HTTPS 的具体接入与清理方案已补齐；实际手机连通随上述用户决定放到可安装版本阶段验收。
- R1-W3 — accepted / corrected and rechecked。实际点击两条受影响路径、保存并目视截图；single_thread 无 Work，非 owner global 可进工作记录，见 design-validation。


## Round 2

### Metadata

- reviewer_target: `/root/ios_design_review`；与 R1 相同的独立 reviewer，author 为 `/root`。
- review_mode: `full`
- mode_reason: 除 W2 的有界接入方案和 W3 原型修复，本轮用户调整了 M1 资源依赖时机，涉及 milestone 准入语义，按 reviewer skill 扩至 full。复核完整设计/退出标准；未变的首文档、coverage、delta 和实际产品事实沿用 R1 已读证据，并以摘要/代码检查确认未漂移。
- started_at: 2026-10-05T00:43:36+08:00
- completed_at: 2026-10-05T00:46:28+08:00
- duration: 172 seconds
- checkout/revision: `main` / `1daf6676debe129088d9bd0612b489d1eba0301a`，设计仍为本 unit 未提交快照；只追加本报告，保留 R1 与 author resolutions。
- received user decision: 主 chat 传递本轮用户直接回复“你这么着急需要真机了吗？”、“你还没做出来呢，着啥急”；结合 author 当时已接受的执行顺序，解释为先完成 App/模拟器，再安排可安装版本的手机与 Mini 验收，不解释为取消真机或续签。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

本轮设计审查通过，允许按用户调整后的顺序进入实施。该结论不表示模拟器已经可用、Nano App 已构建、真机已验收、Mini 已连通或续签成功。S1–S30、P1–P5 和 M1 最终退出条件保持；仍须以实际客户端/真栈/真机/同网刷新及过期恢复证据关闭实施验收。

### Coverage 与证据

| 受审面 | 本轮复核与判断 |
|---|---|
| 范围、用户决定与 delta | `spec.md`、`coverage.md`、`specs/im/ios-client.md` SHA-256 与 R1 完全一致。全原生、Web 全量管理、免费维护和最终验收没有减少；`design.md:162,168` 与安装顺序明确只调整资源落实时机。该用户指令优先于 skill 默认前置要求，无需再要求用户提前占用手机。 |
| 架构、接口与既有装配 | 重新通读 design 全部决策/模块/数据流，核对本轮变动没有新增后端、改变 Keychain/session/幂等与恢复设计、改变 owner/admin 或包依赖。`git diff --name-only e6a5c0ea5 HEAD -- src/IM` 仍为空；R1 对真实 router、auth、messages、Work、channels 和策略的证据 retained。新增 Tailscale Serve 仅属于隔离验收传输入口，继续代理既有 loopback IM，不成为产品服务或替代 IM 鉴权。 |
| 本机构建资源 | reviewer 独立运行指定 `DEVELOPER_DIR` 的 `xcodebuild -version`、`-showsdks`，确认 Xcode 26.4.1 / 17E202 及 iOS/Simulator 26.4 SDK；`simctl list runtimes` 仍为空。读取实际 `/tmp/nano-feat578-toolchain/Probe.swift`，确为极小 SwiftUI 探针；其 typecheck exit 0 来自 author 准备记录，不当成产品构建。runtime 尚未完成不阻止先写项目与 SDK 构建；完成真实模拟器 UI 验证前必须安装并启动 runtime。 |
| 真机隔离接入 | 阅读 `evidence/device-access-plan.md` 全文，独立读取本机 `Tailscale serve --help` 并核实官方 Serve/HTTPS 文档。自定义 HTTPS 端口代理 loopback、自动证书、精确 IM Origin、同源 ticket/WSS/媒体、只停止自身 Foreground 配置形成闭环；清理禁用 reset，不覆盖其他任务配置，不启 Funnel，不修改 Release ATS/TLS。手机可达性和真实 WS 路径的实证按用户决定后置，仍列为 M1 验收。 |
| 原型、模式与权限边界 | 当前源码 `publicagent` 只保留 single_thread 说明和发消息；global 的普通成员 Work 路径保留。再次核对真实 `AgentProfilePage:28,75` 和 `agent_work.py:20` 的 global 限制。reviewer 独立目视两张修订实际截图，single_thread 无 Work，非 owner global 工作列表完整，未见新增遮挡或层级混淆。具体交互证据与限制见下一段。 |
| 原型其余区域 | retained_from: Round 1。P1–P5 契约和聊天/Tasks/管理/安装界面未实质改变；R1 已实际走通审批待确认与任务引用草稿，并目视 390/430/600 代表画面，不重复扩大 UI 复查。 |
| Milestone、安装与最终验收 | 单 M1 及 `.gitkeep` 骨架保持；只更新依赖时机，reviewer/worker 退出标准仍覆盖 S1–S30、全部 C01–C34、原生截图/IME/权限/恢复、真实通道、签名安装/同网刷新/过期恢复和独立 gates。安装方案明确步骤 1–3 先行、4–8 在可安装版本后；没有用模拟器或提前手动刷新代替真机/自然过期恢复。 |

官方复核：[Tailscale Serve CLI](https://tailscale.com/docs/reference/tailscale-cli/serve)、[HTTPS certificates](https://tailscale.com/docs/how-to/set-up-https-certificates)。本轮未启用代理、申请证书、改变 tailnet ACL 或操作手机/Mini。

### 原型证据与检查边界

- reviewer 独立目视 `output/feat578/prototype-single-thread-fixed.png` 与 `prototype-global-nonowner-fixed.png`；它们对应 author 本轮实际点击的两条路径，记录于 `evidence/design-validation.md` 的 R1 修订复查。
- 本轮后台 IAB 已不可用；浏览器只读 inventory 仅有用户 Chrome，遵守不争用要求，没有转去 Chrome。`prototype.html` HTTP 200，但不把此项当视觉证据。
- 本轮没有声称重新独立点击成功。W3 的实质 delta 仅为删除错误 Work 按钮和说明，不是新增交互；以本轮实际渲染截图、作者已完成的路径走查、当前原型代码及 R1 reviewer 亲自走通的保留路径组合核实。该有界修复已有充分视觉与行为证据，不因 reviewer 当前浏览器缺席再造资源阻断。原型的其他已验证区域 retained，不推断原生 App 通过。

### 历史问题闭环

| Issue | Author Resolution 与本轮证据 | 状态 |
|---|---|---|
| R1-W1 | author 接受资源事实，记录 Xcode/SDK 实际就绪和 runtime/真机/Mini 的未完成状态；用户明确纠正提前要求手机的顺序。新 design/M1/installation plan 将硬件及外部验收资源后置且不降低最终标准。独立 SDK/runtime 检查与记录一致。 | **closed（设计/实施准入）**；未完成资源转为对应 M1 执行条件，绝非标成已就绪。 |
| R1-W2 | author 提供 Tailscale tailnet-only HTTPS 具体入口、独占端口、精确 Origin、可信 TLS、手机验证和限定清理；CLI/官方能力与当前 IM Origin 接线相容。真实手机连通随用户明确调整后置。 | **closed（设计缺口）**；手机 HTTPS/WSS/附件实际验收仍必做。 |
| R1-W3 | 删除 single_thread 的 Work，保留 non-owner global Work；当前实际页面截图、源码和已装配前后端模式限制一致。 | **closed**。 |

### Issues

无新增 CRITICAL / WARNING；R1 三项均按上述含义闭环。

### Recommendations

无额外建议。实施应直接按已审范围推进，避免为了资源时序重复请求用户提前交手机。

### 受审快照

本轮 SHA-256：

| 文件 | SHA-256 |
|---|---|
| spec.md | `db446fad0d9dad9b50551ae492f78d3cae3ea62bd64b61baacf7916f46f5222b` |
| design.md | `3920257ebbb4716454cef44a058efc7f489cbdcdd5cbc5f79a3aa62918b72e8e` |
| coverage.md | `bb940794312efa878c6710a1228c5a59355a4868b93344012b983e7c8368229f` |
| prototype.html | `1f3d34195a8b9c5574410762e0fdd52cbe3ba51c17d52ea4f3d5a85f6a7c4db2` |
| installation-plan.md | `37bd70697a873297c18ac1a3ab9b0ac0e98cdb01daa71a50fb753ba7e4f3e4ee` |
| specs/im/ios-client.md | `a760e17cfe34c084d96d50c31b2841971e4832cefe2dc6603a4442c11462551e` |
| evidence/design-validation.md | `d54b40db4dddd7fc67b383b4d21ef3f3e49b805038774244609edf2c72ad42bd` |
| evidence/device-access-plan.md | `696e30a1213f1584b69afd7f93108ef8553afff736836ace8d96f4347bc06819` |
| evidence/toolchain-readiness.md | `40df5a8870a8251b86e3175f7760abf4d950cb0f3c2f3fc0b0b8e1607912fa37` |

Author 判真后可以按 workflow 交给实施；本轮以后若发生实质设计变化，仍需按实际影响复审，纯进度/资源事实更新不能冒充已完成验收。

### Author Resolutions（R2）

作者判真：接受 Approved 与三个历史 issue 的闭环含义，无实质异议。实现和最终产品/签名验收仍待执行。R2 后仅更新 design 状态为 Gate 2 已通过；其余受审设计不变，此为纯进度标记，保留本轮审查有效性。
