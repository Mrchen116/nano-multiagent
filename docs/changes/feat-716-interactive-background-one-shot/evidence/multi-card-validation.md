# feat-716 — 多卡真实旅程与 Context 观察

本页记录当前多卡增量的作者执行事实，独立判断由 [review](../review.md) 持有；不是整体实施验收或交付声明。产品版本 `fc5e19066046920f8a6bfa3245bd63a9f718d8ed`，报告 HEAD `29f402e29616e090aaa2eda2c682d25c0b12a6a0`。后续仅修改了原生 UI 测试的可见性 helper 和术语/证据文档，未改产品。旧 [单卡实施证据](implementation-validation.md) 是历史记录，不代表当前多卡验收。

## 新隔离实例与对象绑定

- 自建 runtime：`/tmp/feat716-multi-5601db41-cfc8-44d8-b443-8a0b798ed952`；run ID `5601db41-cfc8-44d8-b443-8a0b798ed952`。新 daily 由标准 `e2e-up.sh` 启动，非复用旧 62814。
- IM：`http://127.0.0.1:59469`，PID `49976`，出生时间 `Mon Nov 9 01:25:58 2026`；已核对 command 指向本 unit 的 `apps/im-server/lib/main.js`、cwd 指向新 runtime、端口 listener 与 PID 一致。
- Node：`wt-feat716-multi-5601db41-cfc8-44d8-b443-8a0b798ed952-48274`；PA `pa_5c9eab27c541`；合成 owner `u_3z5y8ktt`；会话 `c_104d871f7a5e`（`PA · 个人助手`）。只读数据库核对 self-owned 合成用户、新建 direct/nonexternal 会话、owner/participants/唯一标题，未借用其他事项或生产对象。
- 工作及审批配置均为 `codexOAuth:gpt-6.1-sol`，4 个 agent 无 fallback。标准 daily 复制配置后，在任何消息/模型调用之前仅对自有副本设置审批模型并正常重启 Node。native request header/journal 中本次实际模型集合也只有 Sol；配置成立不等于每次动作都触发了独立审批模型。
- A/B 均从新会话的真实产品 composer 请求 PA 生成，不直接造 DB 卡片：

| 卡片 | 来源消息 ID | 创建 UTC | 可编辑字段 | 初始值 |
|---|---|---|---|---|
| A | `9cc91fd1da434202bb139544b6f383ba` | `2026-11-08T17:47:25.010Z` | `方案A人数` / `$peopleA` | 2 |
| B | `1915b3d802f640d68fc842518ed5978d` | `2026-11-08T17:48:16.199Z` | `方案B人数` / `$peopleB` | 3 |

两张来源均为上述 PA 的真实 executor provenance，`read_only=0`、`superseded_by=null`，schema/标签各自独立。A/B 请求到卡片分别约 15.0s / 12.2s；未调用日历、任务等外部业务。只读 host validator 的真实成功结果保存在 runtime `.native-fixture-binding.json`，检查了新 UUID root、启动记录/HEAD、PID 出生时间/command/cwd/listener、本地 DB/合成 owner/会话/卡来源、唯一标题和 Sol 配置。**对象证明不是人类授权**，没有解除任何此前被拒动作。

## Web：实际 A+B → 无新背景 → 仅 A

真实浏览器 session `feat716multi`，仅打开新 origin、正常登录合成账号；真实 DOM 输入/Send，不调用测试 API 代替操作。先将 A 改为 4、B 改为 5，再发第一条；不编辑直接第二条；只将 A 改为 6，再发第三条。正文只要求确认/收到，不在正文提供人数答案。

| 序号 | 实际消息 ID / UTC | 实际 relay 冻结来源与 state | 实际模型下一步回复 |
|---|---|---|---|
| 1 | `d5d36e7b86994ac3957c642c7178c761` / `17:52:56.530Z` | `[A,B]`；A `$peopleA=4,$noteA=方案A讨论`，B `$peopleB=5,$noteB=方案B复核` | `已确认，方案A人数为4人，方案B人数为5人。` |
| 2 | `18c3de448dee4182b1433852803eae13` / `17:53:39.755Z` | 无 `interaction_contexts` | `收到` |
| 3 | `991e05d473434acdb0f87b7315ab251f` / `17:55:10.907Z` | `[A]`；A `$peopleA=6,$noteA=方案A讨论`；不新带 B | `已确认，刚才新改的方案A人数为6人。` |

三行 UTC 日期均为 `2026-11-08`，relay 状态均 `completed`，只投给上述卡片作者。三次真实页面均确认消息/回复，后续只读断言精确检查 `[A,B] / [] / [A]` 与各自 state，而非仅 count。第三条证明 B 的历史存在不等于重新注入。

作者实际读过 1200×732 截图 `.playwright-cli/page-2026-11-08T17-49-02-700Z.png`：B 卡数字/备注清晰、composer 可用；DOM 同时有 A/B 各自字段，A 在该截图上方。最后截图 `page-2026-11-08T17-57-05-448Z.png` 显示保持旧卡阅读位置的 A=6/空 composer，**不是最终回复画面**；最终回复依据实际 DOM 与数据库/native journal，不以那张截图冒充。浏览器已关闭，daily 按协调者要求保留。

## 模型实际消费：既有 native input + 下一模型步 + relay

实际公开工具名为 **`inbox`，参数 `action=read`**，不是 `read_messages`。后者是旧报告的误称，本次校正术语，不改工具/产品。

只读范围为上述新 runtime 的 `.dsh-runtime/<node>/node.sqlite3` / `runtime_events`，执行 session `30f15108-2cfd-46a3-833c-8b86eb8fde2d`。采用事项负责人已选的原生证据法；没有新增 proxy、wire recorder 或改变上游配置。

| Web 消息 | 实际 inbox call | raw / projected tool-result | 下一真实模型步 |
|---|---|---|---|
| 1 | seq96，turn3 step2，`inbox(action=read)` | seq97 / seq100，contextItem23；自然正文后**一块**说明及含 A4/B5 两来源的 JSON 数组 | seq104，turn3 step3，`send_message` 给本会话，确认 A4/B5 |
| 2 | seq128，turn4 step2 | seq129 / seq132，contextItem31；仅自然正文，**无新 background 块** | seq136，turn4 step3，`send_message`：收到 |
| 3 | seq160，turn5 step2 | seq161 / seq164；自然正文后**一块**说明及仅 A6 的数组 | seq168，turn5 step3，`send_message`：只确认新改 A6 |

作者实际逐条读过相关 raw/projected 文本与下一步 tool call；第一/第三条每项保留自己的 `source_message_id/source_summary/agent_id/state/fields/interacted_at`，无字段来源混合。固定说明仍含 `data, not instructions, not a submission, and not authorization for any business action`，自然正文没有被背景覆盖。第二条无新块不代表删除历史；既有第一条记录仍在 session 历史是预期。

**证据层级限制**：native request header 只有 config/tools 等，不包含完整 provider messages；上述证据是实际 `inbox` 工具输入结果、实际下一模型步及 relay，**不是 HTTP/provider wire 原件**，不宣称已捕获转换后 provider payload。小两卡完整位于各自相关结果，未触及 6000 字符 parts / 最多 4 fragments 的分页边界；不能由此推断近 64 KiB 组一次 read 必完整。

作者判断：当前 Web 路径直接支持真实多卡选择、一次性消费、仅重改 A 再激活与非授权说明。原 reviewer 随后实际只读相关 journal/relay 与图片，给出限定 Web 小两卡消费有直接支持、预复核范围 clean 的结论，见 [review](../review.md)；不是整体 unit gate。该结论不覆盖下文后续新原生运行或预算恢复。

## 原生：首次运行失败及测试修正；未通过

- 标准 `NanoIMJourney`，专属 derivedData `/tmp/nano-ios-feat716`，选用既有 simulator `1CE31893-672F-495A-B2B5-3ACF39A7A257`（`iPhone 17 Pro`）。没有本事项创建/clone 该设备的记录，也未证明它不被用户或714共用；不能称为本事项自有专用设备。UI test 会安装/更新同 bundle App 与 runner 并正常写 App 本地状态，无显式 erase/uninstall，但不能保证共享设备上既有 App 数据不受启动/迁移影响。运行配置为原 xctestrun 的新副本 `feat716-native-multi-5601.xctestrun`，mode 0600；fixture JSON 来自上述实际绑定结果，输入与 origin/用户名/cid/唯一标题/卡 ID/标签逐项一致。无产品 hook。
- 首次实际运行：`/tmp/feat716-native-multi-5601.log` / `.xcresult`，`testTwoEditedCardsAreConsumedTogetherThenOnlyReeditedCardReturns` **1 failed，exit 65**，test 39.207s，总测试阶段约 68.9s。正常 App 入口/登录/聊天与 A6→7 的真实编辑完成；在 B 编辑前失败，**没有 native-multi Send，数据库对应消息为 0**。
- 直接原因是 UI 测试的可见性前置错误：旧 helper 只判 `exists && isHittable`，实际 AX tree 的 B field 在 y1161–1207，而 App 高874；因此跳过滚动。A 仍 Keyboard Focused，B tap 未建立焦点，`typeText` 报 `Neither element nor descendant has keyboard focus`。这不证明产品多卡派生有缺陷，也不把未发送视为 native 一次性通过。
- 失败附件导出目录 `/tmp/feat716-native-multi-5601-attachments/`，作者实际读图 `5D9ECD82-7C0E-4C0C-94A7-7BEEDDAA62B8.png`（第二 probe：B 不在画面，A 键盘在）与 `A4EED37C-575D-4B85-8D7C-BDAC927F7297.png`（首 A probe：A6 可见）；AX tree `20171CE7-B51D-41DC-8D29-2D548F4466B7.txt:53,152,162` 分别证明 A 焦点、真实 Done 按钮及键盘。
- 仅修 `UITests/OneShotBackgroundUITests.swift` helper：正常 Done 收起 WK 键盘，要求字段 frame 完整位于导航栏下/真实 composer 上的可见区，滚动手势限制在该区，保留最多8次、原10/20s等待和120s allowance。不改产品/预算规则/超时。修正后 `build-for-testing` **exit0**，日志 `/tmp/feat716-native-multi-viewport-build.log:334`；既有 Swift6 actor isolation、manual order、AppIntents warnings 仍在，不宣称 warning-free。
- 正常请求再次运行同一个窄 UI 用例时，整条“只读复核绑定 + 原生测试”命令被权限工具拒绝：认为缺少本次 simulator 操作的明确人类许可，并引用共享主机历史限制。该命令未执行，**未重试、未换工具/路径**；已向父级给出具体对象与拒绝原文。因此 helper 的运行验证仍 pending，不把编译通过写成旅程通过。
- 此阶段首失败的 App 已 teardown terminate，旧 simulator 已 Shutdown；新59469与旧62814保留。A7 可能是已保存待发状态，未通过 API 清除/重置。

## 新空模拟器执行与资源回收

负责人随后明确澄清真实隔离测试无需再逐项请求许可，本轮没有可用手机、仅需模拟器；此前具体拒绝仍作为历史保存，不再把常规隔离验证写成等待用户批准。继续限定新59469合成服务，不使用未证独占的旧 simulator，不触及62814或真实数据。

- 实际通过 `simctl create` 使用已安装 iOS26.4 runtime 新建空设备 `feat716-empty-5601-a1bf5251` / `D65E5440-153F-4A99-9700-FF6D2E7BB613`，UTC `2026-11-09T01:34:28.659985Z`；没有 clone/import 旧数据。新进程/DB/fixture/Sol 绑定再次实际全部通过；0600 xctestrun 与 fixture JSON/origin/标签、App fc5 revision 的检查也实际通过。
- 两项测试前置脚本错误已就地修正：系统 Python 缺 PyYAML，复用仓库已有 `.venv`；既有 xctestrun 是旧版 `NanoIMUITests` 顶层而非 `TestConfigurations`。它们均发生在原生测试启动前，不计为产品失败。
- 随后唯一一次新空设备 multi 测试：`/tmp/feat716-native-multi-empty-5601.log`，**exit65，1 failed**；本地09:36:27启动，09:38:41结束，测试阶段132.412s，实际 case26.804s。真实登录成功，但在聊天列表点击 PA 入口前失败；没有进入卡片编辑或 Send，故仍未验证 viewport 修正。
- 新失败直接证据：日志`:104` 为 `not hittable`；截图 `C9DC9077-79CA-4219-BC3E-CE38111851BD.png` 与失败 AX 树 `156FD8EA-1F91-4DCC-BF88-A2147146FA55.txt:132-157` 显示系统“保存密码？”Sheet/“以后”按钮覆盖列表。旧 helper 在列表 ready 前检查可选弹层，检查结束后才出现系统提示。仅将同一弹层处理移到真实列表 ready 后，并检查入口可点；不改产品、不延长超时。此第二项 test-only 修正尚未编译/运行。
- 读取失败日志时曾有一次工具结果存储 `ENOSPC` 报错；后续 read/glob/export/清理成功。Data卷清理后实际约407Gi used、17Gi available、97%，inode7%。**不据此宣称宿主持续0空间，也不将这条工具错误归因成原生 UI 失败原因**。
- 已核对自建 JSON、唯一设备名称与 UDID，关闭并删除 D65 设备，`simctl list` 确认已无；没有停止/删除其他设备。Xcode20697、runner25043、App25718均已退出，无自有运行批或浏览器。
- 按新资源规则先提取必要证据到 `/tmp/feat716-evidence-5601`（348KiB：上述日志、截图、AX树、manifest），再删除独占 derivedData `/tmp/nano-ios-feat716`（302MiB，含 App/runner 与凭据 xctestrun）、本次完整 xcresult（7.9MiB）及全量导出附件（7.5MiB）。原路径不再保证存在，后续审查读最小证据目录。该最小证据由事项执行者负责保留至失败修正复核后回收。
- 新59469 runtime 为后续未闭合旅程保留，事项执行者负责在最终验证/交付或事项停止时清理；旧62814为先前明确保留的预览，不因新测试失败删除。当前批已释放 native/heavy 窗口，未启动新测试探测。

## 再次空设备复验：实际完成第一条多卡 Send，后置测试查询失败

本段是原独立预复核之后的新作者执行事实，未冒充 reviewer 已审结论。串行 native/heavy 窗口重新分配后，再次只读 host validator 验证自有进程/出生时间/端口/DB/owner/两卡来源/配置，`59469/health` 正常；结果位于 runtime `.native-fixture-binding-next.json`。运行前 native-multi 消息为0，执行 session 最大 seq177。

- 实际 `simctl create`（不 clone/import）新建 `feat716-empty-sheet-5601-ae5a5efd` / `CEF24E76-B72D-4833-9504-0B2732704B6A`，UTC `2026-11-09T03:46:43.129486Z`，同一已安装 iOS26.4.1 runtime。最新 helper 以 jobs2 / parallel NO **build-for-testing exit0**，`feat716-native-multi-sheet-build.log:2558`；App revision仍 fc5，UITest哈希仍为预复核的 `665c785b…`。0600新 xctestrun逐项绑定当前 fixture，未改产品。
- 唯一实际 UI test 为同一三消息 multi case，日志 `feat716-native-multi-sheet-5601.log`：本地11:53:09开始，case11:57:39开始；**exit65，1 failed，case97.391s，测试阶段365.560s**。冷启动/automation setup较长是实际时长，不据负载单指标推定原因或扩大超时。
- **先前两个前置已实际走过**：`:65–83` 正常点击“以后”关闭保存密码Sheet并进入聊天；`:117–195` A7→8真实输入、正常Done、在可见区滚动B、B5→8真实输入全部成立。实际读图 `BDA43439…png` / `05CF6ADD…png` 分别显示 A7 和 B5 在无键盘 probe 时完整可见；`CFAE4695…png` 显示编辑B后键盘/旧卡阅读位置，不冒充双卡同时可见或输入后值截图，输入后值来自真实字段断言与 relay。
- **实际第一条 Send 已完成**：run marker `4E2328B7-6561-4BE7-9384-28788A26E655`；消息 `90b8a94ef47444bfa691636ff84af74d` / UTC `2026-11-09T03:59:12.616Z`。正文只请求读取两卡，不给人数答案；唯一 relay `completed`，独立来源精确为 `[A,B]`、state A `$peopleA=8` / B `$peopleB=8`，各自 notes/fields/time保留。没有第二或第三条 native-multi Send。
- 同一真实 session 的 `inbox(action=read)` seq192 → raw193 → projected196/contextItem47，作者实际逐条读取：正文后一块data/not-instructions/not-submission/not-authorization说明与A8/B8数组；下一真实模型 seq200 turn6step3 `send_message`“方案A人数为8人，方案B人数为8人。”，实际保存回复 `f5dd959193b44dc5a6241eaf24aae685` / UTC `03:59:29.395Z` 一致，seq209 turn/end。仍非 provider wire。
- 测试停止的确切新原因在`:228–229`，**不是产品Send失败**：第一条已经Send、点击Latest messages后，`app.staticTexts[text]` 用超过128字符的正文作identifier查询触发 XCTest 的128字符上限 `NSInternalInconsistencyException`，尚未执行第二条。`Complete Issue Description` 也直接给出相同上限/建议谓词。仅将公共 send helper 的回执查询改为 `matching(NSPredicate(format: "label == %@", text))` 精确匹配；不缩短正文、不降低断言、不增加等待/allowance。该第三项 test-only 修正尚未编译/运行。
- 结束后按JSON/设备名/UDID/实际设备绝对路径核对，自建CEF24已Shutdown并**删除**，`simctl list`及设备目录均确认不存在；Xcode82351、runner88296、App89131均已退出，未碰旧1CE/62814。必要小证据集中保留于 `/tmp/feat716-evidence-5601`，由事项执行者负责至修正/独立复核关闭后回收；独占完整 xcresult、导出附件和 derivedData（含0600凭据 xctestrun）在提取后回收，具体核实见本批报告。

本次只支持 **原生真实编辑A/B→第一条两来源派生→实际Global消费/回复**；未完成第二条无新背景及重改A第三条，不把一条成功写成三消息路径通过。新真实工具拒绝为0，没有绕过或更换入口重试。原 reviewer 随后对该哈希版本实际读原DB/三张图/日志做限定补验，确认首条路径有直接支持、新谓词补丁静态clean/新存活findings=[]、未编译运行，完整结论见 [review](../review.md)。输入结果的通用 `channel=web` 不改称native；原生来源由真实XCTest输入/Send、marker和时间关联。

## 精确标签谓词编译与系统 Sheet 关闭竞态（当前批继续中）

- 新批已再次验证原59469对象绑定，记录 `.native-fixture-binding-predicate.json`。实际新建空设备 `feat716-empty-predicate-5601-a84bebe2` / `CC5B5086-01BC-429B-8A06-F466257471AE`，UTC `2026-11-09T05:19:33.955698Z`，不clone/import；原生产品仍fc5。精确标签谓词版本 `3fb8d168…` 已实际 `build-for-testing exit0`，日志 `feat716-native-multi-predicate-build.log:2558`。
- 运行前两项脚本错误均未启动测试：App plist 的真实键为 `NanoIMBuildRevision`，不是 `NanoBuildRevision`；命令须带已安装 Xcode 的 `DEVELOPER_DIR`，不能使用宿主默认 CommandLineTools。修正后受保护fixture配置/App版本核对成功，未发生权限工具拒绝。
- 同一multi用例实际执行 `feat716-native-multi-predicate-5601.log`：本地13:24:20启动、13:25:38开始case，**exit65，1 failure，case16.697s，测试阶段93.398s**。真实登录/列表成功；`:66–73` 点击“以后”返回后立即检查chat.isHittable失败，未进卡片、未Send，故没有补齐三消息或验证超128字符谓词的运行路径。
- 本次附件只有实际screen recording，没有独立failure PNG/AX。作者用ffmpeg从原录屏末尾前1s提取并实际读图 `feat716-native-multi-predicate-final.png`，画面仍有保存密码Sheet；末尾前0.15s帧已为teardown后的主屏。二者不证明tap永久无效或产品故障，但证实当前即时断言没有等待系统Sheet消失/entry ready，不能用推测覆盖失败。
- test-only修正：在原chat等待前建立同一20s deadline，点击系统Sheet后以剩余时间等待真实entry `hittable == true`，再断言，失败前也保存实际截图。不增加chat等待预算、120s allowance，不缩正文/断言，不改产品；AX查询/tap本身并非硬实时墙钟保证。
- 该修正第一次 `build exit0` 后，`feat716-native-multi-entry-5601.log` 实际13:29开始case，**exit65 / case53.628s**：登录/entry ready、A7/B9编辑、首条Send及完整label匹配均已通过；`:249–250` 随后composer waiter出现 `expectations can only be waited on once`。根因为helper用 `self.expectation(for:)` 注册entry后又以局部XCTWaiter等待，后续 `waitForExpectations` 再次收集该旧expectation。仅改为独立 `XCTNSPredicateExpectation`，不在self outstanding集合登记。原reviewer独立读源码/日志确认静态修复clean，新存活findings=[]；不代替完整运行。
- 独立expectation版本实际再编译0，`feat716-native-multi-standalone-5601.log` run marker `DBAEBEC5-F62B-434D-BE04-DCD0B9F9C089`，**exit65 / case84.502s / 测试阶段110.435s**；首条Send完整回执与composer清空均通过，旧重复wait已不再出现。实际两条消息已保存/relay completed：`c0671447fdcc4b9488d031d50617f22c` / UTC05:32:40.043Z 为A8+B8；`0ef981e40cc64ab89dcb8ed7d71438df` / 05:32:47.654Z 为[]；未执行重改A/第三条。
- 此次第二条的UI回执等待失败不是中心缺消息：`:273`立即查询Latest时未出现，随后仅等精确staticText，20s后失败；实际AX `EA500445-D076-42A8-BC1C-26A333DF6B1B.txt:95–115` 底部仍为首条，Latest已存在，第二条在当前lazy viewport之外。仅将同一Latest操作移入原20s回执条件等待，等待完整label；Latest变可用后最多点击一次，不增加时间或降低完整正文断言。当前正在编译/实际复验，不把已有两条写成三消息通过。
- 本批自建CC5设备与独占derivedData/0600配置仅为同批立即修正复验暂留，owner为716执行者；本批结束（含失败/阻塞）删除设备与完整构建/凭据/结果，仅保留必要证据。没有触及旧1CE、62814或其他事项资源。

## 原生完整三消息已实际通过与限定独立核对

- `feat716-native-multi-receipt-5601.log` 实际 **1 test / 0 failures / exit0**，case82.282s、测试阶段108.986s。受执行helper SHA256 `9ac8d5fbb2edd331afa74c755f808b8e00b1397d7ecf411f8e7296d36080a080`；产品fc5未改。末尾diagnostics的宿主`simctl` lookup72不是测试失败，也不宣称诊断采集完整。run `3C6C6AC8-B9A9-4F89-B9BE-E32BC709B75A`，真实A7/B9、重改A9，三次完整正文精确label回执/空composer断言通过。

| Native序号 | 消息 / UTC 2026-11-09 | completed relay | 冻结背景 |
|---|---|---|---|
| 1 | `5c3c2f13d3df47bb85eed676fca78b73` / 05:36:46.370Z | `9304a3f2c444420ab75efab713675f59` | `[A7,B9]`，各自notes/fields/time保留 |
| 2 | `fe56d9d44dc44379b556cb8ba722524c` / 05:36:55.085Z | `faa13f4f798e415da4f69aa3d63da1d3` | 无新背景 |
| 3 | `66bf9e5f35874e3ea1f780e1b7f6a47c` / 05:37:18.360Z | `a3ce789676834fc5a019b32771056528` | 仅`[A9]` |

- 实际模型消费同一session、**同一turn9内分步**：seq302 `inbox(read)` → raw303 / projected306、contextItem75 **批取前两条**，first一块完整A7/B9、second无新块；随后311拟发送`received`，但312/316结果是 **held_for_revalidation，未送达**，不能写成second已回复。第三条到达后321check → 329read → raw330 / projected333、contextItem82仅A9；337真实send，338/341 `status=sent`，实际保存回复 `128e4c5c151741818b31633818e4d043` / 05:37:36.818Z 为“方案A人数为9人。”，346turn/end。
- 作者与原独立reviewer均逐条实际读上述raw/projected、relay/工具结果：每块与relay内容逐项相等，raw首text与projected首text相同；来源/state/fields/time与非指令/非提交/非业务授权说明保留。直接支持native真实编辑/三Send、`[A,B]→[]→[A]` 持久快照进入下一实际模型步、最新A9实际交付；**不证明本run独立AB回答或second received交付，不称三个模型turn**。此前单独native首AB回复可保留原范围，不与本run批取混同。
- 作者与reviewer实际读图 `6088F606…png`：第二receipt时仍旧阅读位置，不能称每次回执均完整visible。最终 `0BBCA310…png` 本次三条正文整段可见且composer空；未含后续A9回复，回复依据实际调用/DB。仍用通用channel=web，不以其冒充native专有channel；原生来源由XCTest/marker/时间交叉证明。
- 原reviewer限定结论 **SUPPORTED / findings=[]**，不是whole-unit最终Gate；未新增provider wire、分页边界/恶意授权/跨Agent负例证明。随后flag-before-tap仅作非阻塞one-shot稳健性顺序修正，独立标识新hash，不能把旧9ac8 PASS挪给新hash。
- 完成的4组完整xcresult及3组全量附件已在必要日志/最终图/AX/context提取到 `/tmp/feat716-evidence-5601`（约5.4MiB）后实际删除；本批CC5与derivedData仅供紧接的自有副本transient复验暂留，owner/回收点不变。

## 原生 transient：自有合成副本实际保存失败与恢复

- 未运行旧outage runner。新runner `feat716-native-owned-outage-v2.py` 先再次运行原完整source validator，再以SQLite online backup复制59469合成DB到新UUID `feat716-outage-a8a8b7db-02c0-4647-8548-c277bd68fc36`，新origin `http://127.0.0.1:63068`；记录source绑定、卡/owner拷贝相等、原卡创建早于副本而归属原source proof，不伪造after-copy来源。只启动独占IM，不启动额外Node/模型。
- 新测试按fixture首card label、正式GET的fields.label→name绑定真实`$peopleA`，保留仅fixture card可访问守卫；不再对新A卡使用旧`参会人数/$participants`。最新版本build-for-testing exit0。原CC5自建sim在同批复用，不触碰旧1CE。
- 实际 `testNativeTransientSaveBlocksAndRecovers` **PASS / 1test / 0failures / exit0**，case50.815s、测试阶段76.721s。实际runner持有Popen句柄停原副本IM68559，恢复同一DB的新IM70326；ready/recover只协调真实进程停启。原59469及62814始终不停止。
- `native-transient-xcode.log:191–240`：实际health连接拒绝后编辑A9→5，真实Retry saving出现、Send禁用，输入完整 `716-native-transient: Keep this message while saving recovers.` 并保持；`:332–344` 服务正常恢复后真实点击Retry，Send恢复enabled、正文相同、正式GET stateKey为5。**本case没有点击恢复后的Send，不宣称该正文投递，也不宣称自动恢复被本case执行**。
- 作者实际读图 `21AEF732…png`：会话级失败标题、原因/全会话范围/离线说明与Retry全部可读，composer完整正文和灰Send可见；`51ACC0CD…png`：失败notice消失、同正文保留、Send绿色可用。图片未显示卡字段最终5，字段成功依据正式GET与只读DB，而非猜图。
- `native-transient-db-proof.json`：源/副本message21、attempt21、relay12与空discard均相同；副本A5/rev9 @05:44:52.261Z，源仍A9/rev8 @05:37:13.671Z。没有新增用户消息或relay，副本状态恢复不污染源。
- 核实两IM PID/Xcode68587/runner69080/App69289均退出、63068释放；在必要日志/源码/ownership/DB proof/两张图提取到最小证据目录后，副本DB/uploads/完整xcresult/全附件目录已实际删除。CC5与derivedData仅为同批下一预算准备暂留，owner为716执行者，批结束即删。原reviewer已实际读runner/ownership/proof/build/日志/两图，给出限定SUPPORTED / findings=[]、必要失败/手动恢复画面局部体验PASS；不冒充最终Gate。两图顶端仍Disconnected.Reconnecting，不把保存成功解阻写成WS重连成功。

## 其余恢复项的准备与当前范围

以下为当时轻量准备的历史，当前真实结果见上节transient及下节预算，不能由准备推定通过。

- **transient（历史准备已落实）**：真实 App 用例已从旧 `参会人数/$participants` 改为按新fixture首卡label→正式GET fields→真实state key绑定，并实际通过；不是仍待适配或未执行。已有 Web 自动恢复证据与 iOS 单测/静态重连判断，不扩大为本case实际自动恢复。
- 旧本地 outage runner 引用旧 worktree/data、旧 cid/card、未证独占的1CE及陈旧 xctestrun，**不得执行**。实际已采用上述新UUID/新端口/持有Popen句柄的v2 runner，并回收副本；没有运行旧runner。
- **预算 fixture**：先完成原多卡完整三消息，再经真实产品 composer/PA生成3张新的可编辑合成卡（各有独立数字标签与一个备注TextArea），不向DB造卡。对新卡重新做validator绑定；用正式CAS API把每张备注填约12000 ASCII字符，逐卡实际序列化state须小于16384bytes，并对包括state、fields、来源及time的整组实际JSON计数确认大于65536bytes。数值是构造假设，必须实测字节，不能只按字符/三张数量假定触发预算。
- **预算双端路径**：分别以真实Web窄屏和新空sim App composer输入唯一正文、加入仅本轮生成的合成附件（原生走正常Photos选择，媒体只加入自建sim）。真实Send应显示可完整阅读的可恢复错误，正文/附件/卡片草稿保留；失败前后只读核对messages/attempt/relay及消费边界无新增/推进。再通过同一正式CAS API缩短三张备注，不离开会话、不清背景或丢附件，真实重发须整组成功、保留正文/附件身份，后续无新背景。截图要包含错误容器与composer，不能用422受控单测或API响应代替窄屏体验。
- API仅操作当前重新绑定的合成owner/cid/card IDs，附件只来源于本轮自制文件；新权限拒绝则完整停报，不绕过。原生预算恢复用例仍未写入/运行，原生附件picker的实际可访问结构未观察，不把静态设想当已验证交互。

## Web预算：实际73,021-byte拒绝分支；恢复被工具阻塞

本节为上述准备后的新作者事实，不改产品或helper；HEAD29f/产品fc5/UITest6df不变。恢复与原生预算均没有通过。两次精确被拒调用/原文/资源只读回执见[工具拒绝与恢复点](budget-tool-refusals.md)。

- 真实浏览器新session `feat716budget` 正常登录原59469合成账号，从真实composer要求PA另发三张独立卡。PA实际消息：甲 `63de19a567354bb5b89ac7aa948c2e65` @05:55:38.239Z、乙 `dc9cc2e1bc26412f8b807493229b8b54` @05:55:44.648Z、丙 `f3adf4bb564449fbab2101c0ef79579a`；均为2026-11-09、该PA provenance、各自人数Input/备注TextArea，未复用A/B或造DB。新host validator `.budget-fixture-binding.json` 再次全部通过。
- 通过普通auth/interaction-state GET+CAS PUT填充各备注12000 ASCII字符。最初脚本误以为无草稿时GET state含默认值，KeyError发生在任何写之前；从正式fields.value补齐默认值后，第一次三卡CAS确实完成，但记录count误用不存在的独立attempt表失败；改为实际messages caller key/relay_tasks并再次CAS记录，不能声称仅写过一次。最终各卡rev2，state分别12,030/12,028/12,032 UTF-8bytes（全部<16,384），包括来源/state/fields/time的实际整组JSON **73,021bytes>65,536**；记录 `budget-web-expanded.json`。这只是fixture准备，不冒称真实12000字符键入测试。
- Web真实resize 390×844；通过当前composer正式DOM drop handler加入本轮新建 `716-budget-5601.txt`（44bytes自制文本），无React内部hook。上传完成后真实输入完整正文 `716-web-budget-5601: Keep this full message and my attachment. Confirm all three card counts only; do not create anything.` 并点击Send，实际请求422。没有API代替这次composer提交。
- 作者实际读图 `.playwright-cli/page-2026-11-09T06-01-19-952Z.png`：顶部Send failed及整段预算原因、两条恢复建议、正文/草稿保留说明全部可读；composer中自制txt附件与完整四行正文同时可见、Send可用。当前卡的旧short渲染不是服务器大草稿丢失证明；大草稿依据CAS/DB，不改称画面显示12000字符。DOM `page-2026-11-09T06-01-17-302Z.yml` 同时保留完整alert、正文、同文件名附件/Remove。
- 失败前后 `budget-web-expanded.json` / `budget-web-rejected.json` 精确相同：messages25、带caller key的attempt25、relay_tasks13、localHumanAt `2026-11-09T05:55:25.012Z`、空discard、三卡rev2/updated_at全部不变。没有预算正文保存为message或relay；由此支持无部分创建/消费，不能把附件上传这个独立预备写入也称为“零写入”。
- 下一条“正式CAS缩短三卡备注→同一composer正文/附件正常Send→snapshot”的整条命令被权限工具拒绝，**未执行**，已停、未拆分/换工具/缩小测试重试；原生预算测试未写入或执行。父级确认这是原unit隔离恢复范围，但不以其判断撤销工具拒绝，也不调查用户正在修的独立审批缺陷，不断言与其他事项同根因。
- browser已正常close且PID82519实际不存在。随后本批临时sim/derivedData回收命令也被工具拒绝、整条未执行。只读2026-11-09T06:04:48Z实际状态：自建CC5为 **Shutdown但目录仍在**，独占 `/private/tmp/nano-ios-feat716` 279,318,859bytes仍在，未读凭据；没有matching Xcode/runner/App进程，所有job收齐。没有把sim的Shutdown归因成被拒命令已执行；也没有声称删除完成或全资源释放。59469及62814原服务仍保留。新图未复制到最小/tmp证据目录，审查应读上述实际原路径。
- 原reviewer随后独立实际读取原截图/DOM/console第2行messages端点422、binding/脚本/两记录与原59469只读SQLite，结论 **SUPPORTED / findings=[]；该390×844拒绝/保留状态局部体验PASS**。独立依source字段/原state/executor/摘要/time重建本fixture投影，73017+括号2+逗号2=73021bytes，与生产计数一致；Input/TextArea无choice-options且短BMP摘要，使readDraft withOptions与background默认投影、Python/JS摘要在本fixture无差异。独立SQL精确排除delegation后floor仍不变、无预算正文message/relay，三卡rev2/time/submission null均保留。console证明422、专属UI文案与代码映射一致，但无原始HTTP response body抓包，不称已读完整HTTP JSON或wire；不推广到精确65536边界/任意Unicode/其他所有投影种类。恢复后仍须原现场重核、同正文/附件正常发送全组三来源、后续无新背景，以及原生预算；不假定浏览器已关闭后老DOM ref仍有效。

## 用户更新工具策略后：Web同context预算失败与恢复已通过

用户实际新答复“工具审核策略已经更新了，应该不会被拒绝了”，父级沿原事项接续，要求仍走正常审核、若新拒绝即停；不修改审批实现、不绕过。新批重新核对HEAD29f/产品fc5、原完整host validator三卡绑定与59469 health均通过，旧拒绝继续作为历史，不倒算旧调用执行。

- 重开CLI browser为新context，需要正常登录；实际DOM读得composer为空/无附件。`composer-draft-store.ts`为内存Map，不宣称关闭后旧44byte附件/正文跨重启保留。为完成真正连续旅程，使用相同完整正文与本轮**新52byte**自制 `716-budget-resumed-5601.txt`，正常DOM drop上传后真实Send重新触发原73021byte组422；从该次失败开始保持同context，不清或重填正文/附件，随后正式CAS缩短再真实点Send。旧负向与本次新附件身份不混同。
- 新失败图 `page-2026-11-09T09-24-18-185Z.png`（SHA `342b3351…`）及DOM09-24-14-366Z已由作者/原reviewer实际读取：完整预算错误/恢复建议、同完整正文及新附件chip保留。`budget-web-resumed-before.json` / `budget-web-resumed-rejected.json`的messages25/attempt25/relay13、floor、空discard及各draft revision/time精确相同。前后图/DB本身不单独证明中间从未重填，连续操作记录补足这一点。
- 正式CAS缩短到 `Recovered web-resumed-reduced`：三卡rev3，保存UTC09:25:13.224/.240/.252Z、完整背景1195bytes；真实同composer Send后消息 `e83e69858dcf45228591a9e5265f16fa` @09:25:18.734Z，唯一relay `9f1d7440d08c49889ebf1fae1ff4ed67` completed，精确完整[丙f3ad…,甲63de…,乙dc9c…]，各source/state/fields/time完整，无截断/丢卡。真实next消息 `1aa06e216fa44e678a500a9009d05d33` @09:27:04.130Z，唯一relay `f55a26abe05945c69a0d2d0e8cae4a0c` completed且无interaction_contexts。日期均2026-11-09；精确持久proof为 `budget-web-recovered-relays.json`。
- 同一新52byte附件唯一持久行：image `44c4ed1fa7624a4cad06ae29b0d82029`、source_key `upload:4eab2e9c-a15c-4123-b6c2-64d5a01c7c55`、storage `4864b842c1b44ebbbd4a84633ab14342`、SHA256 `6c0749923c394bc572af40585898b132f85d1db78550583352aee6bfa6553373`，与自制字节相同；恢复message/caller_payload/relay/Inbox中的URL/type/name精确相等。未重新选择或新建附件；不由唯一持久行单独断言全部HTTP上传请求从未重试，也不称模型已读附件正文。
- 实际同session：409 Inbox read→raw410/projected413（item102）首text byteeq；同一次read的part1/2含自然正文+一块完整三背景，part2/2含附件，无next_cursor，并非文本被截断或仅返回半组。416下一实际模型→417 send三卡均2，418/421 sent，已存回复 `b01c2217195e43208fd1e8438ceea450` @09:25:33.494Z completed。next441→442/445（item110）仅正文无新块→448/449 send received→450/453 sent，回复 `f892681e33b049a182e3060a5b7953db` @09:27:16.830Z completed，458 turn/end。所有context与relay逐项等，无held；证据 `budget-web-context.json`。仍非provider wire，初始人数也为2，不把回复数值说成只能由新背景因果推得，历史旧块不因nextnone抹除。
- 作者与原reviewer实际读最终390×844图 `page-2026-11-09T09-31-32-794Z.png`（SHA `8ecc26e1…`）：完整恢复正文、已发同附件、三卡回复、next完整正文/received、空composer同时清晰可见。09-25旧位置空composer图不冒充成功消息画面；上方XXXX为当前页面仍渲染外设备CAS前大备注，不称UI已刷新short。限定独立结论 **SUPPORTED / findings=[]；此连续恢复局部体验PASS**，不覆盖原生预算/whole-unit Gate。
- 新browser已正常close、所有Web jobs收齐。此后owner仅轻准备Photos picker probe，helper变为 `2fe14e73…`，尚未编译运行；上述Web结论不覆盖新probe，也不挪用旧9ac8/6df原生运行哈希。当前native窗口已协调给714，本事项到实际build/test节点另行协调，不把全程文档/归档算独占。

## 原生预算：真实拒绝与同附件成功保存；回执与后续消息尚未闭合

本节为后到的作者实际证据，HEAD29f/产品fc5仍未改变，不把失败测试算通过。此前仅有轻准备的描述是历史状态。

- 真实 picker probe 的初版在到 Photos 前误用旧卡字段滚动 helper，exit65；修为正常登录→会话→添加附件→Photos 后实际 exit0。作者读过完整 picker 图与 AX：自制蓝色 PNG 为唯一标签 `照片, 11月09日, 下午5:35`、`PXGGridLayout-Info`，不选择模拟器自带样图。首次完整 case 对该可见 tile 的普通 AX tap 报 Not hittable，未上传，host 的唯一新附件断言失败；没有预算消息。改为该实际可见 tile 中心的标准坐标 tap，并以成功附件前置/抛错与显式 stdout flush 防止失败后继续准备。
- 修正后的实际 host run `c0f5d0b0-134d-4c81-852b-92394b0d8161`，UI run `C26C8D11-F3D3-4993-A19C-5432DBC41144`：build exit0；UI case **exit65 / 118.558s**。测试源码 SHA `d70fdbcc…`、host SHA `682fe2a6…`、fixture SHA `26a4c909…`，完整绑定为 `/tmp/feat716-evidence-5601/native-budget-tested-source-binding.json`；本次无新工具拒绝。
- 本次确实完成正常 Photos 上传、输入完整正文、正常 CAS 准备三卡、真实 Send 预算拒绝、保留正文/同图片、正常 CAS 缩短和同 composer 再 Send。`host-record.json` 中 expanded/rejected/reduced 均为 true；失败前后 messages/attempt/relay、floor、discard、三卡 revision/time 及附件行完全相等，不消费或部分创建。实际组 73,021 bytes，不按字符数假定预算。上传为独立预备写入，不称全程零写入。
- 作者实际读拒绝图 `ACD1AD9D…png` / SHA `68b29ab0…`：顶部完整可恢复错误与两种恢复说明清晰可读，自制蓝图、可编辑正文与 Send 同时存在；正文尾部在原输入框内部滚动范围内，完整字符串由真实控件值和 AX 保留，不称整段正文同时全在画面。卡片仍显示先前大备注，是设备渲染未刷新外端 CAS，不冒称已显示缩短值。
- 恢复消息实际唯一保存 `31fcd38c46a54c60aa7f92a676df9163` @ `2026-11-09T12:10:06.232Z`，唯一 completed relay `03d5345305404df7b258bd834f923188`，精确全组三来源[丙、甲、乙]、state/fields/time保留，备注均为本run缩短值。相同 image `fdc717d4bf6149779ac143e399e8d541`、`photo-DF8811E2.jpg`、929-byte JPEG、SHA `6ce02e4f…` 在拒绝/成功消息/caller payload/relay一致；JPEG为App正常转码，不要求其与原179-byte PNG同hash。持久 proof 为该run目录 `delivery-proof.json`。
- 实际 Inbox read seq473→raw474/projected477 含完整三来源与同图片，下一步481真实 send，482/485 sent；回复 `e01facebc5794f0e93168182cf0c4c67` 已 completed，确认三卡均2。仍非provider wire，未推广到预算边界或图像语义理解。
- **未闭合**：本case首次成功 Send 后的精确正文回执等待20s失败，图 `58F2D8E5…png` 与最终图显示空白 timeline/Latest 控件和空 composer，不能冒充成功消息画面。异步 case 在失败后仍继续运行，数据库未产生其下一条消息；不能将截图名称“next-sent”当发送回执。当前只将 UI wait 改为异步 fulfillment 并在失败时抛错，保持完整正文、精确回执、20s/10s与120s allowance不变；它是待验证的测试修正，不先断言空白由 harness 而非产品引起。

## 原生预算连续恢复：后到的真实绿色执行

同步 receipt 等待改为异步 fulfillment 后，保持完整正文、精确相等回执、20s/10s 和120s allowance，产品未变。当前 helper SHA256 `862b8128546731ba24067eb19c2465e6e0c4a676afe89d18dfddb14f936000e4`；本次 build-for-testing exit0，日志 `/tmp/feat716-native-budget-async-receipt-build.log`。这是测试 harness 修正，不以单次绿色断言旧空白的唯一根因。

- host run `c5de4112-95fb-40be-b9c7-0520741040f4`，UI run `F2AFB026-E167-4D3A-9B76-B298E902DCCB`，2026-11-09 UTC12:15:35.963–12:16:44.860，**Xcode exit0；1 test / 0 failures / 57.915s**。本run目录为 `/tmp/feat716-evidence-5601/native-budget-c5de4112-95fb-40be-b9c7-0520741040f4`，包含原 `host-record.json`、`xcode.log`、xcresult/attachments、`delivery-proof.json`、`model-context-proof.json` 和可读 `readable-inbox-proof.json`。HEAD29f/产品fc5、同自有CC5/59469绑定不变；正常审核，无新工具拒绝。
- 真实 Photos 选择自制蓝图→上传完成→完整正文→host正常CAS扩展（73,021bytes）→真实Send拒绝→同正文/同附件保留→host正常CAS缩短（1,387bytes）→**不重填/不重选，真实Send成功**→下一条真实Send。host expanded/rejected/reduced全true；拒绝前后messages31/attempts31/relay16、生产human floor12:10:06.232Z、空discard、三卡rev7/timestamps及附件行完全相等。缩短为rev8、备注均为本run标识，未丢来源。
- 恢复message `2d5a2d75fbd64c7da8e4eb87e5363216` @12:16:28.030Z、唯一completed relay `0cf2852753d74d5593425d702bdb4294`；metadata中精确[丙f3ad…、甲63de…、乙dc9c…]全组，source/state/fields/time逐项相同。next `e3298fdb1f4e4f16a5e3aa8b8948fcd2` @12:16:37.568Z、唯一completed relay `5f409d1ccf3a44d2aba0ab4b54302492`，无新contexts/attachments。
- 同一image `9b91ed1a068945368fdb692d9229402a`、source_key `upload:8c0eae65-0bb0-4f66-8c2e-911c8f63e6db`、storage `227fef45165c4712b9aa8767ff698f57`、`photo-A0FCAC4B.jpg`、929-byte JPEG、SHA256 `6ce02e4f98d9de4cf45d4473a142835ac33b6bbd9f1ab386c7753d1a30abba85`，在上传/拒绝/成功message/caller_payload/relay一致。独立预备上传不算消息事务零写入，唯一持久行不证明HTTP从不重试；179-byte PNG→App JPEG及模型292-byte JPEG为正常转码，不声称逐层相同二进制hash。
- 作者实际读取拒绝图 `54024170-8BD9-462F-A248-4A7E1CF463C2.png`（SHA256 `0b9ff6bdfec07d35d303eb4d430734f2182da541bffaf80cd50355a40b1f3bc6`）：完整预算错误/两条恢复建议、蓝图、可编辑正文仍在；长正文尾部在输入框内部滚动范围，完整控件值/AX保留，不称全部正文同时可见。最终图 `4B6F0596-5DAB-414D-820F-E15A7C74C908.png`（SHA256 `989c82a166647c7a696176f63b53d4ff56ac5d0367d74e8f2136cca45a2f92af`）同时显示完整恢复正文、已发蓝图/同文件名、完整next和空composer；不包含其后agent回复。卡片显示前一run短备注，不声称外端CAS已刷新本端卡片。
- 实际Inbox seq505 read→506 raw/509 projected item126，首text byteeq，正文+完整三背景逐项等relay；同read的part1/2为正文背景、part2/2为同附件，非两个human消息、无next_cursor。513/514拟send三卡2被515/519 **held_for_revalidation，未送达**；next532 read→533/536 item133仅next正文、无新块→539/540真实send received→541/544 sent `bbee98a7797345fc89cac572ed65e735`，549 turn/end completed。人数原即2，不把拟回复说成新背景唯一因果证明；历史背景不因nextnone删除。不是provider wire，也不推广到所有64KiB组一次read或图像理解。

## 最终集成 MERGE-1 的最低层红绿

原reviewer对375d11416集成树指出同runtime重挂漏复位`left`。作者新增独立的`InteractionDraftReentryTests.swift`（复用既有fixture/同步gate，不扩大原400行测试文件），只经真实`leave`→`load`→`webRequest`与原draft coordinator测试边界观察：

- 保存干净后的新页面ready/state可用；离场旧页面ready被拒绝。
- 503后保留本机编辑和transient失败；重挂允许继续重试，旧页面高序号state不能覆盖本机。
- 409后保留本机编辑和冲突；重挂仍disabled，必须先只读比较才能显式采用远端。
- gated PUT在离场/重挂后成功，真实ack仍推进自有水位，行回收不产生会话discard；旧页面被拒绝。

**实际红测**：产品未改的375d11416 + 新测试，`/tmp/feat716-merge-reentry-red.log:862–879`，四项全部执行且均以422 `This card session is no longer active`失败，0.736s、xcodebuild exit65。日志随后独立的xcrun CLT路径诊断错误不改变四项已执行断言；未修改全局xcode-select。只读bundler构建先已通过。

**产品修复**：有效store内load先复位left，再执行保留未保存/冲突的guard；渲染页面token与draft/engine代际分开，leave仅撤销页面token和序号，不旋转draft token，避免真实在途PUT确认/水位丢失。异步附件和业务回执仍检查页面token；业务busy/composing清理绑定操作所处draft代际，不能因页面撤销而永久busy。未改变公开API、自动采用规则或会话discard所有权。

**实际绿测**：相同四项、相同自有CC5与derived data、Xcode `-jobs 2 -parallel-testing-enabled NO`，`/tmp/feat716-merge-reentry-green.log:381–402`，4 tests / 0 failures / 0.063s、exit0。随后完整Native unit target `/tmp/feat716-final-native-tests.log:318–320,396`，80 tests / 0 failures / 10.134s、exit0。再补一项同gate的业务动作保护：在动作等待PUT时离场/重挂，旧页动作拒绝、未发送、busy/composing释放、新页ready恢复可用；此增量不改产品runtime。最终完整Native unit `/tmp/feat716-final-native-tests-actions.log:264–265,401–403,479`，**81 tests / 0 failures / 10.277s、TEST SUCCEEDED、exit0**（执行时间含建置/启动则更长，不将test时间当总时长）。当前runtime SHA256 `30ba3486f9869a6be9aee15d8b6104ff133d4b43fcadc902a59ef19668689015`，新测试最终SHA256 `f191261e4528e2a948e55b277360ba6e5bf42fbca0a24724f3481f60bbe599b6`；四项红绿时测试hash为30aa1b37…，不把后加的第五项说成已红测。测试构建标签375d但以上两文件为工作树增量，**不是clean375d实测**。完整unit包含WK mock，不冒称当前真实App入口旅程或工具拒绝已解除；修复仍待原reviewerclosure。

## 当前未关闭范围

原reviewer已对冻结ea438576f实际核对新增helper/全部决定证据、两图与原始SQLite，**APPROVED / findings=[]，原生预算连续恢复缺口CLOSED、限定旅程/体验PASS、Context SUPPORTED**；此前已选目标均有对应限定支持，详情归集于[review](../review.md#冻结树-ea438576f-的独立关闭)。后续81d036d54已实际sync固定develop1e38c6a3d并解决9冲突，不能套用本批准；MERGE-1已实际红绿/完整Native unit通过，仍待独立关闭及当前双端核心真实旅程。受影响复验、canonical归并、archive、本地/远端CI与Ready PR尚未完成，整体不宣布交付。
