# feat-596 Design Review

## Round 1

### Metadata

- reviewer: 独立 subagent `/root/design_review`，未参与本轮设计编写。
- reviewer_target: `480893430d279157dab746fbd4e6cae597e4096f`；产品代码基线 `f486d889f`。
- review_mode: `full`。
- mode_reason: 首次 Gate 2，覆盖首文档、设计、三份 delta、原型及 M1 骨架；不存在可继承的历史审查。
- started_at: `2026-10-13T23:40:43+08:00`。
- completed_at: `2026-10-13T23:47:01+08:00`。
- duration: `6m18s`。
- checkout: 独立 unit worktree，detached HEAD；审查前 clean。仅新增本报告，不修改设计、产品代码或后台服务，不提交。

### Verdict

**Issues Found — 0 CRITICAL / 3 WARNING。**

产品方向和主要职责分配成立：按单台电脑明确授权，完整准备后再切换，复用固定发布包、生命周期和 relay 持久化。当前不能进入实施门禁：准备屏障的消息交接、屏障持有者失联后的恢复、失败终态的聊天反馈仍会让实现者作出互不兼容的选择。

### Coverage 与证据

**需求与范围。** 已核对 [spec](spec.md) 全部场景与 [design](design.md) 的决定、接口、Runbook、M1。按钮才授权下载、页面关闭后独立推进、等待可取消、单机隔离、真实上线后成功、失败保留数据、旧用户一次桥接均有设计落点。用户要求的真实操作录屏已落到 M1-W1，不能用原型或此轮浏览器观察代替。单一 M1 适合这个贯穿 Node/DSH/IM/Web 的更新事务；`M1-update/.gitkeep` 存在。真实隔离栈账号与服务可用，受控候选包/transport 明确为实施验收 fixture；本轮不声称已验证更新器、真实重启或生产发布。

**实际组装与复用。** 独立读取了以下实现，并据调用关系判断可行性，而非仅核标题或引用：

- `apps/im-server/src/install.ts:10` 与 `assets/install.sh:46`：实际安装入口已限定显式 manifest、GitHub URL 和 SHA，适合将共同格式验证移到 product-contracts，保留 shell 自举。无需再建分发源。
- `apps/node/src/cli.ts:49`、`lifecycle.ts:82,215`：setup 当前以已 ready 提前退出；lifecycle 已按 config 串行并核 PID birth，且启动 entry 来自 CLI 所在 release。独立 updater 调用目标 CLI、扩充实际 release readiness 是合理延伸，不应另写一套进程控制。
- `apps/node/src/main.ts:48,58,147,182,206,234,250`：真实 Node 组装 runtime、Web relay、ExternalChannels、PA/global、heartbeat 和 shutdown。新 admission gate 应在这里协调，由 PA 暴露其在途/reconciliation 状态；不把产品投递逻辑移到 DSH。
- `packages/dsh-integration/src/index.ts:457,476,497`：当前 shutdown 会 cancel，并非更新安全屏障；设计没有错误地复用它来等待任务自然结束。安装依赖 `@deepseek-ai/dsh-agent` 的公开 `AgentRegistry.list()` 包括 live child；`lib/types/runtime-types.d.ts:165` 的 `runMaintenance` 同步取得 true-idle 独占，任务期间新输入留 inbox，公开 status 仍为 idle。与本仓 ModelPolicy/Fallback、Workflow、Knowledge 和 CronOwners 的受控扩展结合，设计的屏障可实现，不需要 private import 或上游 patch；但不能仅以 status=idle 当作冻结完成证据。
- `apps/im-server/src/identity.ts:558`：持久 runtime token 的 authenticateRuntime 校验 owner/node/epoch，确实不要求 WS 在线，适用于窄更新 report 接口。普通 gateway HTTP token 与该持久凭据不能混用。`gateway.ts:1018` 的注册后重放及 `messaging.ts:524` 的发送必须共同接入 gate，不能只改 HTTP send。
- `messaging.ts:483-535`、`gateway.ts:1042` 与 `packages/personal-assistant/src/external.ts:44-89`：已有 IM relay rows 和外部 inbound ledger，复用它们比新建另一条消息队列简单；当前机制不会自动解决 R1-W1 的准备/取消窗口。
- Web 的 `chat-workspace-page.tsx:460,744` → `message-pane.tsx:980` → `node-chip.tsx` 是实际聊天 presence 组装链。新的聊天状态需进入这些真实消费者，而非仅电脑列表 cache。

**独立体验判断。** 先以独立 IAB tab 观察原型，再核设计表格。随后登录 `http://127.0.0.1:52529/settings/nodes` 实际基线：现有设备身份、KPI、别名/快照双栏及独立保存被保留；原型新增更新区将版本、影响和一个主动作放在同区，用户能先确定设备再决定更新，未与保存混淆。独立操作“更新→下载→等待→取消”，以及切换中输入消息、切到恢复失败和点击恢复入口；下载等待文案与取消动作清晰。恢复入口当前是明确标注的演示 alert，不能视为真实命令验收。

桌面实际渲染与作者 [基线截图](evidence/current-desktop.png)、[桌面原型](evidence/prototype-desktop.png) 的关系一致。另直接查看 [390 等待](evidence/prototype-mobile-waiting.png)、[390 聊天](evidence/prototype-mobile-chat.png)、[820 回退](evidence/prototype-820-recovery.png)：窄屏版本换行、主动作纵向、设备名及输入框可辨认。这些截图仅支持所示布局；本轮尝试独立 390 交互时浏览器 CDP 超时，已恢复临时 viewport，因此不新增“独立手机交互通过”结论。原型整体增量布局可指导实施，失败旅程存在 R1-W3 的实质误导。

**契约层。** 三份 delta 的 canonical target 分别是 current IM agents-nodes、gateway-relay 与 Gateway service-lifecycle，消费者正确，均为 ADDED，未删除或重写现有 Scenario。新更新排队必须保持普通离线失败与成员/owner/epoch 校验；失败终态与准备窗口需按下列 findings 补足后，同步到 delta 和 M1 针对性验收。现有 must-match 已投影到 reviewer R1/R2 与 worker W1；iOS 原生新增管理页面明确不在范围，Web 手机布局已有方案。

### 历史问题闭环

无；首次审查。

### Issues

#### R1-W1：本地准备屏障与 IM gate 之间的消息交接未闭合

- 位置：[design](design.md) 第 43、45、66 行。
- 证据：第 43 行先打开本地 admission gate 并承诺输入留在 IM，第 45 行却到拿到 ready handoff 后的 claim-switch 才开启 IM relay gate；第 66 行又要求 waiting 短屏障内保持 queued。当前 `Messaging.deliverRelays()` 在 socket send 成功即将 relay 标为 sent（`messaging.ts:531`），Node 的 relay 路由只有正常 receive（`main.ts:147`），重放触发是重新注册（`gateway.ts:1042`）。因此本地已冻结、IM 尚未 claim 的窗口中，已有帧仍可能到达 Node。
- 未修后果：实现者若拒绝/跳过这类帧，用户的 send 已成功但消息不会进入 PA；随后用户取消更新，旧连接不重连，现有注册重放不会触发。若为了避免丢消息直接准入，又会破坏已宣告的安全屏障。当前一句“仍留在 IM”不足以决定哪方负责恢复。
- 修订要求：明确 prepare 阶段 gate 的建立顺序、已在途 relay 的处理与回执/状态，以及 busy、取消、准备失败释放时的重投触发。可提前建立可撤销的 IM prepare gate，或定义本地拒绝准入后的持久回执与 IM 重投；不要求增加另一套队列。验收补“屏障前后边界发消息→取消→不重连也继续处理且只一次”。

#### R1-W2：更新进程失联后，仍存活旧 Node 的冻结没有释放责任

- 位置：[design](design.md) 第 41、43、45、64 行。
- 证据：冻结通过等待中的 runMaintenance 和暂停 cron 持有，设计仅明确取消/准备失败释放；独立 updater 的心跳超时只规定页面变 interrupted/recovery_required，第 64 行恢复发生在“每次进程启动”。若 detached updater 在 ready handoff 之后、旧 Node 停止之前退出，旧 Node 仍运行，既没有新的启动，也没有负责调用释放的 updater。公开 runMaintenance 要等所持任务 settles 才恢复 inbox 驱动（上述 DSH type 契约）。
- 未修后果：下载或切换进程故障会让原本可用的旧版长期不接收新工作/不运行 cron；仅更新页面显示失联不能恢复助手。若简单超时释放但迟到 updater 仍使用旧 handoff，则可能在恢复工作后再停止旧节点。
- 修订要求：指定 Node 侧屏障所有权与持有者死亡/失联处理，说明 claim 前与 claim 后如何查明权威阶段、释放或继续恢复，并使已释放屏障的 handoff 不能再授权 stop。可复用 operation 与 PID birth 做有限的存活/失效处理，无需另建通用协调框架。验收补“冻结后 updater 退出，旧版继续服务”及“失效 handoff 不得停止已恢复工作的旧进程”。

#### R1-W3：恢复失败后，聊天仍承诺等待正常更新，终态消息去向未决定

- 位置：[design](design.md) 第 41、47、66、72 行；[prototype](prototype.html) 的 `render`/chat chip/queued 文案；[relay delta](specs/im/gateway-relay.md)。
- 证据：独立实际操作切换中发送“更新好以后，继续整理明天的待办。”，再选择“需要恢复”：电脑卡片显示新旧版本均未恢复，但聊天 chip 变成“有新版本 ↗”，刚发的消息仍为“等待电脑更新完成”。源码 fallback 对 recovery_required 也确实选择“有新版本”。设计说“终态解除 gate”，同时等待说明只按“仍 gated”计算，却没有决定 recovery_required/interrupted 下已有持久消息是继续等待人工恢复、明确失败，还是何时自动重投。
- 未修后果：停留聊天页的用户看到的是可更新/正常等待，无法知道需要到电脑上恢复；刷新后等待文案可能消失而消息仍未处理。实现者也无法从契约确定恢复成功后是否应该处理之前已成功接收的消息，容易引导重发或重复回复。
- 修订要求：明确失败终态下已接收消息的持久状态、用户下一步、人工恢复后的重投规则，区分它们与失败后新发消息的普通离线语义；让聊天 chip 与消息说明表达“需要恢复”等真实状态，owner 提供恢复入口，普通聊天成员不获得设备管理权。原型补这段连续失败旅程，delta/M1 补刷新与恢复后的结果。

### Recommendations

无额外可选项。以上三项闭环后，按实际设计变更选择 delta 或 closure 复审，无需扩展为全产品重设计。

## Round 2

### Metadata

- reviewer: 同一独立 subagent `/root/design_review`。
- reviewer_target: `bfb2c01447da92c21d68389cdf4cc4b3f9ded76a`，审查前工作树 clean。
- review_mode: `delta`。
- mode_reason: 按窄复审范围核对 R1 三项及其影响；修订新增 waiting/prepare/resumed 时序和本机屏障租约，属于有界协议变化，故采用 delta 而非仅核文案的 closure。不扩大为完整重审。
- retained_from: Round 1；安装分发、DSH public API 可行性、模块职责、旧用户桥接、总体布局、canonical target、M1 范围和真实验收前置均未发生实质变化。
- started_at: `2026-10-13T23:48:01+08:00`。
- completed_at: `2026-10-13T23:49:37+08:00`。
- duration: `1m36s`。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

R1 三项在设计层闭环，未发现本次修订引入新的阻断项。本结论允许据此实施，不代表 updater、消息持久恢复、故障回退或真实录屏已经验收。

### Coverage 与影响判断

核对 `480893430..bfb2c0144` 的设计/原型/relay delta 差异，并阅读修订段落与相邻取消裁决、真实 readiness、鉴权和持久状态条款。新的 prepare 只在新包完整准备后建立；busy 时释放并主动重放，因此没有将整个下载或长任务等待期间改成停收。取消仍由 IM 原子拒绝后续 claim，取消完成则等本地释放确认，分别承担授权裁决与恢复事实，不要求重新确认用户授权。

屏障租约由 Node 承担，发布包下载与进程切换仍由 worker 承担，IM 只保存授权/投递状态；没有引入另一套 Agent Loop、消息队列或跨包 DSH import。声明“已释放 handoff 不可使用”及 stop 前重新核对是实施时必须兑现的不变量，不可仅通过查看某次历史 ready 文件满足。恢复失败时不解除既有消息的保留责任；具体恢复段落限定了常规终态释放规则，正常 succeeded/rolled_back 仍必须通过真实 readiness。

本轮直接查看新增 [390 恢复失败截图](evidence/mobile-recovery-chat.png)，并核对原型 `render` 修改：电脑恢复入口、聊天 chip 的“电脑需要恢复”和原消息的“电脑恢复后继续处理，无需重发”在同一连续上下文可辨认，明确指出需要恢复且无需重发，不再暗示正常自动更新仍在进行。尝试独立打开原型时此前 IAB browser 已不可用，因此本轮证据是亲自查看已渲染截图及其代码变更，没有声称重新完成手机交互。Round 1 的更新/等待/取消独立交互证据保持原范围。

M1 的 reviewer R2、worker W2 已包括取消、消息幂等、安全屏障和恢复相关测试，本轮收口的边界案例属于这些退出条件的具体化：prepare 期间发消息后取消、不重连重投；worker 冻结后退出与旧 handoff 失效；恢复失败消息刷新和同身份恢复重投。应在真实实施中验证，不能拿原型截图替代。

### 历史问题闭环

| 原 issue | Author Resolution（依据本轮受审设计） | 本轮核实证据与结果 |
|---|---|---|
| R1-W1 | IM 先持久建立 waiting/prepare gate，再请求本地屏障；在途 relay 保留且拒绝准入不写 accepted；busy/取消先恢复本地，再 ACK 并主动重放 | `design.md:47,51,72`；relay delta 新增“取消与恢复失败”。已明确 gate 顺序、在途责任及无需重连的恢复触发，**closed**。 |
| R1-W2 | Node 监控 worker PID/birth/每秒心跳，15 秒失联释放屏障、恢复 cron/admission、删除 handoff，并独立 report；claim/stop 前核对且禁止使用失效 handoff | `design.md:49,68,70`。冻结不再依赖 worker 自己解锁；IM 未得到 resumed/ready 仍保留消息，迟到 worker 不能凭旧 ready 停机，**closed**。 |
| R1-W3 | interrupted/recovery_required 的既有消息保留并提示恢复后继续；新发消息恢复普通离线语义；同身份同 epoch 恢复注册重新校验并重投；聊天显示需要恢复 | `design.md:72`、relay delta 新场景、原型 `render` 和新增 390 截图。消息去向、入口文案及恢复后幂等身份已明确；管理权限仍沿用设计中的本人设备限制，**closed**。 |

### Issues

无。

### Recommendations

无。保持既定 M1 范围，实施和真实验收按收口后的契约执行。
