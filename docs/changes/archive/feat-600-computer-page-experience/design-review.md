# feat-600 电脑页面体验重设计 — Design Review

## Round 1

### Metadata

- reviewer target: `/root/computer_design_review`，独立于 design author；使用 `change-design-reviewer` skill。
- review_mode: `full`。
- mode_reason: 首轮 Gate 2，完整覆盖需求、实际原型、现状与架构、delta-spec、milestone 和验收前置。
- started_at: `2026-10-14T08:04:25+08:00`。
- completed_at: `2026-10-14T08:11:34+08:00`。
- duration: `7m09s`，以独立浏览器走查开始计。
- 受审基线：`b487ee4bc` 的 spec / design / delta / prototype / M1 骨架。审查期间 main 合入聊天 Markdown 修复至 `8566973600321ef839a6b4f552a05f85ac244a8d`；本 reviewer 用 `git diff b487ee4bc -- docs/changes/feat-600-computer-page-experience` 确认受审文件未变。
- 依赖实现：只读核对 feat-596 worktree，HEAD 为 `21cdafb5d3f04b1f04ab532a6f82d3d519cba60c`。未把 main 尚未含该依赖当作设计缺口。
- 独立环境：Chromium session `computer600review`，访问作者静态服务的 `/prototype.html`；没有复用或关闭作者浏览器，没有启动真实业务服务。

### Verdict

**Approved — 0 CRITICAL / 0 WARNING。**

这版方案已对“粗糙的内部系统页面”作出完整且适度的体验调整：日常列表围绕电脑身份、实际可用性和当前动作组织；编辑与诊断退出常驻主画面；桌面抽屉与手机全屏详情各自成立。功能保持与视觉层级改善均有独立依据。没有发现会使下游实施实质走偏的未决设计问题。

此结论是设计通过，不表示新 UI 已在真实产品、物理手机或生产环境通过验收。

### 独立体验观察与覆盖

先查看[用户原图](evidence/before.png)和[相邻聊天页](evidence/adjacent-chat.png)，再在独立浏览器辨认默认画面、点击更新、进入详情、改名及连接说明，之后才读取作者走查和逐项核对设计契约。没有从作者的功能清单直接继承体验结论。

| 用户过程 | 本轮实际观察与判断 | 覆盖 |
|---|---|---|
| 认出电脑，判断要处理哪台 | 1440×960 和 820×900 下，两台电脑名称、状态、现用版本和主动作在首屏连续可读。相比旧页，四块统计、常驻表单、原始 ID 和连接错误不再打断扫读；浅青绿、字体和轻边界仍与聊天界面有连续性。更新按钮与普通操作的尺寸、形状和主次关系一致。 | S1 / M1 A；[设计桌面证据](evidence/desktop.png)、[820 证据](evidence/tablet.png)与 reviewer 独立截图相符。 |
| 手机浏览及长名称 | 390×844、360×780 下更新说明与按钮分行，不挤占电脑身份；两台电脑仍可比较。360 长名在列表截断，打开后在完整详情自然换行；返回列表路径清楚。手机详情有独立顶部返回、单栏内容与滚动空间，不是缩窄的桌面抽屉。 | S2 / M1 A、B；[长名](evidence/mobile-long.png)，另独立观察长名详情。 |
| 改名及失败 | 从详情显式进入输入，保存“随身 MacBook”后列表、详情一致；在失败场景保存“保留的名称”，错误紧邻输入且草稿仍在，取消和保存保持同一操作组。关闭详情后列表仍是原名。相关失败不是只能从调试信息理解的状态。 | S3 / M1 B；[编辑](evidence/mobile-rename.png)、[失败](evidence/mobile-rename-error.png)，本轮重走成功与失败。空名规则由设计与原型表单逻辑核对，本轮未另宣称真实 API 验证。 |
| 离线详情与诊断 | 实际打开 Mac mini 详情并展开诊断。先读到需回到该电脑打开 Nano；改名/创建不可执行且有原因。ID、心跳与 `connection_closed` 只在主动展开后出现，普通断连不再像必须立即修复的红色更新故障。 | S4 / M1 B；[离线详情](evidence/mobile-offline-details.png)。 |
| 更新、取消与继续 | 实际点击更新→准备→取消→再次更新→等待→切换→完成。取消后明确继续使用 0.3.0；等待说明自动继续及可以离开；切换没有取消，说明消息可继续发送并在恢复后处理；完成显示 0.4.0。手机阶段文案、动作和电脑身份能在同一画面内理解。 | S5 / M1 C；[等待](evidence/mobile-waiting.png)，本轮另独立截取切换画面。计时只是原型模拟，未作为真实更新证据。 |
| 失败、回退和人工恢复 | 实际切换失败/回退/恢复场景并打开恢复方法。恢复态用琥珀色“需要恢复”和“上次版本”，不暗示旧版在线；引导明确指向“我的 MacBook”。源码、旧安装方式、不兼容、无法获取更新信息均没有伪装成可立即一键更新的正常动作。 | S6 / M1 C；[恢复](evidence/mobile-recovery.png)、[恢复指引](evidence/mobile-recovery-guide.png)。异常选择器用于准备状态，不是产品必经步骤。 |
| 连接与读取异常 | 从日常列表实际进入连接说明并返回；目标电脑、Agent/手动两种方式与绑定交接已决定。未发布安装包场景没有复制按钮。另切换空列表、加载、首次错误与 stale；已有数据刷新失败时提示位于列表上方，电脑卡仍保留，不误报没有电脑。 | S7–S8 / M1 D；[连接](evidence/mobile-connect.png)，本轮另保存无安装包与 stale 截图。 |

本 reviewer 原始截图保存在本机 `output/playwright/computer600-review-*.png`，包括 desktop、details、rename、connect、recovery、long、long-details、rename-error、tablet、stale、waiting、switching、offline、noinstaller；这些是独立浏览器输出，未拼接。上述 unit 内链接是可随设计交付的作者证据，本轮观察与其对应，不将两者混称为同一来源。

### 现状、职责与可实施性

1. 从实际装配入口核实 `app/router.tsx` 的 `/settings/nodes` → `SettingsPageShell` → `NodesPage`；Shell 是 Outlet，桌面 UserMenu 与手机 MePage 确有电脑入口，现有创建助手路由也存在。新设计无需新增设置壳层或改变全局导航。
2. `NodesPage` 已持有节点查询、改名 mutation 和用户事件流消费；把详情选择与 alias 草稿留在同一 feature、从实时列表对象派生只读详情，比复制整份节点状态或另设设备管理 store 更简单。已有别名保存后的节点/助手设备名缓存失效可复用；设计明确要求保持列表、详情及已有消费者一致。
3. feat-596 实际 `node-update-panel.tsx` 已提供 active/switching/recovery 判断、request ID、start/cancel mutation、取消 pending 与查询失效。设计选择保留这些 owner，只替换呈现，避免再造操作状态机或把后端更新屏障移入 UI。active/recovery 优先、旧终态与新版本优先级、relay_gated、POST/WS 不倒退均写明；没有引入 PA/Channels/IM 对 DSH 的新依赖。
4. `onboarding-api.ts` 的 `getOnboarding` 现有返回 install.available/origin/command 与带 node_id 的 agents；服务端 `onboarding.ts` 按 owner 返回节点与助手。按需复用可以完成连接说明与详情助手身份，无需为该页增加后端聚合接口。恢复继续使用 NodeUpdateView.install_command，避免将普通新安装来源误用为恢复事实源。legacy 指引先等待任务结束、保留原身份配置的要求已写入设计。
5. 方案不增加搜索、批量操作、通用设备框架或第二套更新管理；单 feature 拆分与局部样式足以承担当前需求，维护代价与改动面相称。全局通知遮挡、原生 iOS 和助手配置页明确排除，没有借本次重设计扩大产品范围。

### 需求、delta 与交付契约

- 原始用户意图及 S1–S8 均已映射到具体信息关系、交互和反馈，不只是统一按钮 CSS。页面默认正常使用状态；演示控制在产品区域外，安装执行与创建助手下一页清楚标注为交接。
- delta 以 `ADDED Requirements` 指向 canonical `docs/specs/im/agents-nodes.md`；消费者承诺是身份/可用性优先、渐进管理、草稿保留、当前服务连接指引及空态/失败区分。没有 MODIFIED 段落遗漏旧 Scenario，也没有复制依赖更新生命周期或把 proposed 写入 current。
- must-match 表覆盖列表、详情/改名、更新、连接/异常，每项投影到 M1 A–D 的 `[reviewer]` 用户结果和 `[worker]` 对照证据。may-adapt 仅精确色值、圆角、图标等形式；没有用“平台适配”推迟手机关键流程决定。
- 单 M1 范围闭合、依赖 feat-596 明确；`M1/.gitkeep` 骨架存在，无提前伪造 tasks/progress。只读本地核实 Node、pnpm、主仓 `.venv` 存在；依赖 worktree 的真实更新测试与 M1 真栈记录确实可读。Runbook 给出了隔离栈启停、构建、健康检查、账号来源、受控更新夹具和真实浏览器驱动方式；无需新的第三方账号、公共 release 或物理 iPhone 才能验收本 unit。
- 本轮未重跑依赖真栈或全仓测试；这是设计审查。author 报告 clean archive 的 docs-check 通过，属于 author 验证，未冒充本 reviewer 重跑。工作区既有 dirty 文档的坏链接不归因于本 unit。

### 验证边界与下游责任

中文原型的四种 viewport 与关键路径已经实际渲染并独立观察。英文文本、真实请求 pending/网络失败、heartbeat 与编辑并发、跨页更新恢复、真实剪贴板成功/失败和软键盘仍需由 M1 在真实客户端按既定退出标准验收。本轮没有物理手机、VoiceOver 或原生 iOS 结论。手机“我”入口仅从真实装配代码核实，本轮原型导航仍是背景；设计对此有明确标注，并将真实入口驱动留给 M1。上述边界未隐藏未作出的产品决定，不阻塞设计通过。

### 历史问题闭环

首轮审查，无历史 issue 或 Author Resolution。

### Issues

无。

### Recommendations

无必须额外展开的可选设计工作。按当前范围实施和验收即可，不延伸为全产品重设计。

### Author Resolutions

- 2026-10-14：接受 R1 Approved。无 issue；作者复核原型、基线和完整报告后无实质异议。受审产物自 b487ee4bc 起未变，本次只加入审查报告与该 resolution，保留 R1 结论。真实实现及其中英文/事件/软键盘验收仍按 M1 执行。
- 文档验证：受审提交的干净快照 `docs-check` 通过（241 maintained Markdown sources / 64 routes），`git diff --check` 通过。主工作区四个既有 dirty 文档链接问题与本 unit 无关，未改动。
