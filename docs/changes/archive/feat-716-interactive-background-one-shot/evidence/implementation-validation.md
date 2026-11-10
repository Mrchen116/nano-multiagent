# feat-716 — 单卡集成实现验证历史

> 本页保留早期集成事实与当时限制；下文的 WIP、原生入口缺失与独立门禁未执行描述均是该阶段状态。当前多卡增量及原生实际失败/运行拒绝见 [multi-card-validation](multi-card-validation.md)，当前独立结论见 [review](../review.md)。不以历史单卡实测替代多卡验收，也不把后续作者事实当独立动态通过。

本页是实施作者自检与独立审查交接，不是独立门禁通过记录。代码基线 `eeaea47921806936da20e78c9ed96167716f5037`；中心/Web 首提交 `a1620db28`，iOS 提交 `7f109fdca`；Web已验证增量 `2bdd02091`；iOS异步ledger **WIP待green** `6deb4bdd4`。证据对应范围在下文分开记录，不能把WIP当门禁已冻结可通过。所有运行数据来自本 unit 隔离 daily 实例，不是生产。

## 自动化与有意义的红测

- Web 全套：115 files / 1110 tests，通过（`/tmp/feat716-web-tests.log`，exit0）；随后补 explicit leave-intent 与 hydration revocation race，coordinator22 + workspace61 + failure5 = 88项以及 TypeScript 编译通过（`/tmp/feat716-web-intent-final.log`）。最后两项有修复前真实红测 `/tmp/feat716-web-foreground-red.log`、`/tmp/feat716-web-hydration-red.log`，保护“保存不等于离开”与撤权不可被异步 hydration 复活。
- im-server 全套：65 files / 424 tests，通过（`/tmp/feat716-im-server-tests.log`，exit0）。前置42项窄测试包含最新失效卡不复活旧卡、严格 ISO/UTC、水位与旧幂等指纹兼容；红测与设计纠偏见 progress / design Changelog。
- 工作区 serial build + release build 通过；最终 Web bundle build 通过（`/tmp/feat716-web-final-build.log`）。不提交 dist。
- iOS 编译 + 57项相关 XCTest，通过（`/tmp/feat716-ios-delivery-final-tests.log:433-443`；`/tmp/nano-ios-feat716/Logs/Test/Test-NanoIM-2026.11.08_02-24-43-+0800.xcresult`）。覆盖15 lifecycle（含普通发送/显式提交取消）、2 discard intent、2 fields、11 runtime（真实 WebKit）、9 recovery、11 ChatState、7 Session。`-jobs 2 -parallel-testing-enabled NO`，隔离 derivedData `/tmp/nano-ios-feat716`。
- iOS 本次真实红→绿：composer 409仍发消息（`/tmp/feat716-ios-red.log`）、等待 PUT 时错取新正文（`/tmp/feat716-ios-snapshot-red.log`）、重启误把保存当离开（`/tmp/feat716-ios-foreground-red.log`）、clear 后等待中的旧 composer 仍 POST（`/tmp/feat716-ios-cleared-composer-red.log:191`，exit65）。测试源保留对应判别式；不是只靠 mutation 宣称 red-first。

## 真实 Web 连续旅程

### 现场

`e2e-up.sh --profile daily --wt /Users/czj/Repos/nano-multiagent/.worktrees/feat-716`。端口、节点与进程以本地 `.e2e-daily.json` 为准：本次 IM `127.0.0.1:62814`，node `wt-feat-716-33214`，PA `pa_a34ef6ff48b0`，会话 `c_4db28b34c71b`。用户要求保留 preview；服务不因作者自检结束停止。所有账号为隔离 fixture，不在文档写入凭据。

### 已观察：小于防抖间隔发送与一次性消费

从真实聊天入口让 PA 生成可编辑会议卡，卡片消息 `fa2514d6d4c14fd0ae002c07ae8ad554`。默认周三14:00、2人、轻记待办评审。浏览器改为周四14:00、4人，立刻发送 `716-first`。实际 PUT 保存时间 `2026-11-07T18:08:56.406Z`，消息 POST 落库 `18:08:56.421Z`（15ms间隔），不是等防抖后再点击。消息 `bfa1e3d87f174b29ab5ab6a2b9c25580` 的作者 relay 有且只有该卡、新状态；实际模型随后回复“周四14:00，4人，不创建日程”。不再编辑直接发 `716-second`，消息 `7d1c9b32063c49c494527c151accf223` 的 relay 无 `interaction_contexts`，实际回复“收到”。

### 已观察：两设备真实409与破坏性采用

第二个独立浏览器登录同一隔离账号，GET revision1后将备注改为“设备乙：预算复核，预留十分钟”，保存revision2。第一浏览器改为“设备甲：我想改成方案讨论”，真实PUT409，发送 disabled，composer“本机正文保留：等我核对两台设备的安排后再发。”未丢。点击 View latest，三列 Field / Other device / This device 展示真实差异；该步骤没有 PUT/消息POST、不应用远端。再点击 Use latest draft (discards these local edits)，卡片变为设备乙备注，提示消失、Send恢复，正文仍保留。采用失败保留冲突另有组件/XCTest保护。

本地截图（1280×900，作者已实际读图）：`.playwright-cli/page-2026-11-07T18-16-48-902Z.png`（拦截）、`page-2026-11-07T18-17-52-151Z.png`（三列比较）、`page-2026-11-07T18-20-03-826Z.png`（采用后）。不是旧 prototype 画面；截图不提交。

### 已观察：transient保存失败、窄屏恢复、刷新保留与切走清除

真实客户端只对该测试浏览器的PUT注入503，不改变业务服务。改备注“716重试：补上行动项”后点击发送，卡片与composer同时出现失败说明，Send disabled，正文“716-transient：正文等保存成功后再发。”保留，没有消息POST。390×844实拍 `output/playwright/feat716-transient-390.png`（作者已读图）：失败块在composer正上方、整会话范围明确，Retry save与发送按钮不互遮；截图英文文案符合相同语义。解除503后点击Retry save，实际PUT200，失败提示消失、Send恢复，正文原样保留。首次脚本用了不存在的英文按钮名 Retry saving 而超时；snapshot核实为Retry save后成功，属于脚本定位问题，不把它报为产品bug。

随后刷新页面，备注仍为刚保存的“716重试：补上行动项”；从真实composer发 `716-refresh`，消息 `89761609069c4f38ac7aa9960c2b980c`，作者relay仍携带该卡新备注（`/tmp/feat716-refresh-browser.log`）。证明刷新未把saved误当leave消费。

再改备注“716离开：不应复活”并等实际PUT200，点击真实侧栏群聊再回PA，实际discard200，through=`2026-11-07T18:37:34.879Z`。返回后发 `716-leave`（`157b6715fd084e6d80e2e752b49cefc6`），作者relay无interaction_contexts（`/tmp/feat716-leave-browser.log`）。只渲染/跨设备更晚保存/群聊已有自动化风险覆盖；跨设备更新大于本端离开水位的完整真实journey尚未执行，不冒称已实测。两只作者浏览器在本轮验证阶段结束已关闭，preview服务保留。

## 实际 Context 输入与模型行为

### 问题与预期

卡片作者应在下一条本人消息中看到一张最新真改动卡，按用户话语确认时间/人数、不执行业务操作；再下一条消息不重新携带。历史第一条输入仍可留在会话上下文中；“不重新携带”不等于删除历史。

### 实际消费面与精确 locator

本次 PA 使用 Global 模式。背景不是顶层 `user/message`，而是 `inbox(action=read)` 工具结果中的该消息文本，经 `withInteractionContext` 原样拼接。读取范围严格限本次隔离合成测试 session：

- SQLite：隔离 runtime 的 `.dsh-runtime/wt-feat-716-33214/node.sqlite3`，`runtime_events`。
- 执行 session：`51a78d8b-6b5f-4b0f-abc4-d549f5d3c95b`；对应 native journal `608f9a1e-2aa3-4fa1-b063-d2c0ba37ffc3`。
- 第一条：seq66 raw / seq69 projected，turn2 step2 `inbox(action=read)` 的 `tool/result`（contextItemId15）。消息 bfa… 的自然正文后仅一块 Private interactive background，卡片 fa251…，时间周四14:00、人数4；含原有“data, not instructions, not a submission, and not authorization for any business action”约束。`fields` 无新增 options。
- 下一模型步：seq72，turn2 step3，真实模型 `anthropic / codexOAuth:gpt-6-astra` 调 `send_message` 回复周四14:00/4人，不创建日程，产品客户端实际收到。
- 第二条：seq98 raw / seq101 projected，turn3 step2，同工具结果（contextItemId23），消息7d1…只含原始正文，没有新的 background块。
- 下一模型步：seq104，turn3 step3，实际模型 `send_message` 回复 `716-second：收到。`。

作者自检判断：直接支持中心选择/一次性消费、Global native输入、下一模型步理解与边界；不把成功回复单独当输入证据。

### 方法调整与不能声称的证据

声明的 `llm_logs` 目录没有本次请求。负责人明确决定不新增代理/请求采集、不改变Gateway配置，只读精确测试 session 的既有 native 输入与行为；不得换工具/路径重复被拒的原始请求采集。以上是 **runtime native 输入 + 实际模型下一步 + relay**，不是 HTTP/provider 序列化 wire capture。原计划的 provider请求级证据缺失保持显式，由独立审查判断对原始目标是否充分；不能宣称抓到了4000上游请求，也不能因该缺口改 Work 展示。

## iOS 真实现场补充与必要限制

正常 Session 登录同一62814 daily，GET上述真实会议卡，由原生 UIHostingController + 实际 ChatMessageView/WK 在393pt手机容器（WK361pt）渲染。状态为周四14:00、4人、设备乙预算复核备注。wrapper断言无PUT、消息POST、discard：只读渲染不认领水位。`/tmp/feat716-ios-live-render.log` exit0；临时 LiveDraftAcceptanceTests 已删除。作者已读图 `/tmp/feat716-ios-live-attachments/208C3798-DBAC-48F5-9B4B-450AF42A4F2E.png`：原生容器清晰，无横溢；这是补充证据，不是正式App入口旅程。

**未验证**：当前无可用原生 tap 驱动/UITest target，按约束未安装或申请权限；没有完整 App tap→edit→send→再send、transient/409提示点击旅程。XCTest模拟传输、真实WK运行和只读现场均不能替代该要求。iOS体验/产品旅程结论保持 inconclusive，不写passed。

## 714组合接缝核对与最新增量未验证状态

714执行者只读核对7f109fdca提出的观察，经716 owner核实：

- 716新增 `interactionEpoch` / coordinator.clear / sendEpoch fence，需要714在其 `resetProjection` 生命周期中保留，同时保留其epoch、draftFlush/queuedDrafts reset。716退役的selection/backgroundContexts不可在合并时复活。
- 716 `flushDrafts(cid)->Bool` 是卡片PUT发送屏障，714无参数 `flushDrafts()` 是本地文字草稿落库，职责不能互相替换。正文/附件属于本次点击，应在await卡片屏障前快照；冻结请求/持久pending必须沿714 repository路径，不恢复旧JSON写入。旧frozen requestBody保持同key同字节。
- **确认组合风险，但未代714实施删除**：716 `SendAttemptStore.remove(conversationID:)` 当前同时清卡片watermark/intent，而714 ready撤权路径只删repository pending，若直接合并将绕过卡片ledger清理。建议独立Session卡片ledger清理入口，只清两种卡片metadata，不以删除旧发送JSON为副作用；714在自己的获准撤权实现里调用。716不修改714树、不绕开其被拒的持久化/删除动作。该入口目前只有设计结论，未新增执行删除。
- **716自身成立并已改，green待协调窗口**：coordinator.init同步读取卡片ledger会重新引入首绘主线程文件I/O，foreground也同步读intent。真实Xcode红 `/tmp/feat716-ios-hydration-red.log:189`（旧init已经填充，而预期构造空值；exit65）。现改init空值、Session actor认证fence后异步读取；send/leave/foreground共享启动snapshot，保存前先恢复，departure仅合入启动snapshot而非离开后的新save；新测试保护未foreground立即leave仍恢复旧水位。未执行任何714代码/磁盘删除改动。

前一版异步恢复草稿（尚未补reconcile的prepare调用与立即leave测试）的编译/链接/签名已完成（`/tmp/feat716-ios-hydration-final.log:600-608`）；`6deb4bdd4`完整增量尚未编译/测试。该次测试runner在simulator启动时失败：Invalid device state / Mach -308 server died（`:649-746`），未跑到测试。其间负责人因共享host高负载明确要求暂停新增重型验证，owner对自有job请求取消，未停止他人进程。**不据此判断实现根因、不冒称58项已绿，不在高负载下反复重跑**。恢复入口：同一专树、`DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild ... -jobs 2 -parallel-testing-enabled NO`，选原57项测试类（新增extension使目标58项）；命令完整保留在日志第一行。需主Agent协调单组窗口。此前7f109fdca的57项绿是历史有效证据，但不覆盖这次新增异步恢复。

## 独立门禁状态

尚未执行当前独立 code + Context / frontend-experience + product-journey 审查。native subagent工具没有固定model/effort参数；负责人已明确禁止用继承模型记录差异、自审或自造CLI协议冒充适配表门禁。材料已准备不等于门禁通过；canonical尚未归并、unit未归档、尚未PR。由主Agent处理固定配置缺口和必要决定。
