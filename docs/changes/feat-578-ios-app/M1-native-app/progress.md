# M1 progress

Status: native implementation and review fixes integrated; 22 native tests and device archive pass. Independent product R1 remains fail/inconclusive; Mac lock blocks remaining UI checks. Final product acceptance remains open.

## Implementation

- Added independent native SwiftUI client under `src/IM/ios`, including four tabs and all management areas in coverage C01-C34.
- Root integrated Session/Keychain/HTTP/WebSocket, Auth, Chat, Tasks, Markdown/media and project/build scripts. First-round feature workers supplied Agents and Me; root owns follow-up fixes.
- Pinned Swift Markdown 0.8.0 (Swift 6.2 minimum, compatible with installed Swift 6.3.1). Swift language mode is 5; deployment target iOS 26.
- User's resource sequencing applies: simulator and installable artifact first, then physical iPhone / Mini signing and renewal. No S1-S30 final scenarios waived.

## Evidence so far (2026-10-05 local)

- Xcode 26.4.1 (17E202), Apple silicon official download, signature verified. SDK 26.4, Swift 6.3.1 and iOS 26.4 simulator runtime installed. Selected iPhone 17 Pro simulator `1CE31893-672F-495A-B2B5-3ACF39A7A257` runs the actual App.
- All Swift app sources passed direct iOS simulator type checking against the resolved actual Markdown/cmark packages. This does not prove successful app linking, installation or UI behavior.
- Actual isolated IM/Gateway stack: `/tmp/nano-feat578-ios-runtime`, tmux `feat578-ios`, IM loopback port 62008, two online test agents. No production config or Feishu listener used.
- The startup script's readiness login hit the current one-login-per-second target limiter after its earlier bootstrap login. A local-only copy `/tmp/nano-feat578-e2e-up.sh` waits 1.1 seconds before the second login; no authentication check was disabled and no shared script changed. IM access logging also reports an existing formatter error; API status and responses remain observable directly.
- A temporary Swift executable compiled the actual client/model source and decoded real responses: sync, contacts, Agent config/capabilities, account, direct conversation, messages, nodes, tasks, policies, capacity (11 PASS). Empty history/tasks prove envelope decoding only.
- Integration corrections: periodic task refresh retains loaded pages; attachment download cancels on view disappearance; foreground reconnect revalidates current company membership before snapshots/stream.

## Event implementation note

Backend message snapshots persist text/tool deltas. The client coalesces relevant WebSocket event invalidations (250 ms) and rereads authoritative visible history, merging by message id and keeping discard tombstones. It deliberately does not append raw deltas to a snapshot that may already contain them. Resume event ids are deduplicated, reconnect first refreshes sync/membership, and historical replay does not produce foreground reminders. Live streaming, reconnect and discard races still require real runtime verification.

## Remaining gates

- Simulator rendered journeys, keyboard/scrolling, API mutations and real LLM chat/Work/task evidence.
- Independent static review/verification and independent product review.
- Installable version then physical device/Mini/free-signing/renewal scenarios, final canonical merge and archive, CI-green PR. Not complete and no PR created yet.

## R1 review and runtime fixes

- Fixed the eight findings in `code-review-r1.json`: cursor-free revocation, group command target, paginated reconnect gap, structured pending error code, Skill command namespace, exact mention identity, unsaved feature preview, and actionable reminder target.
- Added regression tests for cursor-free revocation and a 61-message offline gap. Both failed against the reviewed implementation (`/tmp/nano-feat578-chat-red.log`) and passed after the fix.
- Added group command/prefix-collision/Skill/display contracts and explicit heartbeat/cron preview assertions. Actual iPhone simulator XCTest run passed 20 tests (10 XCTest + 10 Swift Testing), 2026-10-05 01:51; result bundle `/tmp/nano-ios-build/Logs/Test/Test-NanoIM-2026.10.05_01-51-11-+0800.xcresult`, log `/tmp/nano-feat578-xctest-r2.log`.
- Actual build/launch exposed missing Keychain entitlements when the simulator build disabled signing. `securityd` directly reported -34018 (missing application identifier/access groups). Restored Xcode's default simulator ad-hoc signing, verified generated FAKETEAMID application identifier, then actual login succeeded. No Keychain fallback introduced.
- Test build exposed app/dependency architecture disagreement (app x86_64 versus dependency arm64 on the selected simulator). Set normal Debug `ONLY_ACTIVE_ARCH=YES`; actual native tests then passed.
- Initial Release archive succeeded and generated `/tmp/nano-ios-build/NanoIM-unsigned.ipa`; it predates review fixes and must be rebuilt before device handoff.
- Actual native UI login, four-tab shell and a real persisted LLM Markdown reply were observed. Screenshot `output/feat578/native-chat-r1.png` is local-only. This is partial runtime evidence, not full acceptance.

## R2 closure and native chat evidence

- R2 found ordinary creation/rename/add-member notifications were being treated as access revocation. The client now hides history while re-reading authoritative membership, preserves drafts/attachments for retained access, and clears protected state only on confirmed removal. The rename regression failed before the fix and passed afterward (`/tmp/nano-feat578-membership-red.log`, `/tmp/nano-feat578-membership-green.log`).
- Fixed implementation `b970e20a6`: actual simulator tests passed 21 cases (11 XCTest, 10 Swift Testing); `/tmp/nano-feat578-xctest-r3.log` and xcresult `Test-NanoIM-2026.10.05_01-56-09-+0800.xcresult` under `/tmp/nano-ios-build/Logs/Test/`.
- Native UI opened the peer conversation, sent the numeric prompt `123+456=?`, received `579` from the real Gateway/LLM, and displayed Completed. UI rename to `iOS Peer Check` retained history and composer. Safe local screenshot: `output/feat578/native-peer-reply-r3.png`.
- Independent code-review closure R3 has no remaining findings. Simulator product review is separately in progress; these checks do not close physical-device or free-signing scenarios.
- Added the native test and device archive job to CI using Xcode 26.4.1 on macOS 26; official runner inventory lists that installed toolchain and its default simulator runtime. Remote execution is pending PR creation.

## Local integration checks

- Release archive for implementation `b970e20a6` passed; generated IPA contains the arm64 executable and no Release ATS exception. Version/hash and artifact locator are in [toolchain readiness](../evidence/toolchain-readiness.md).
- Full Python non-E2E suite: **4119 passed**, 29 warnings, 108.75 seconds (`/tmp/nano-feat578-pytest-full.log`). Used repository `.venv` with worktree `src` via pytest's configured pythonpath.
- Existing Web suite: **85 files / 804 tests passed**, 34.75 seconds (`/tmp/nano-feat578-vitest.log`). `npm ci` and critical-level dependency audit passed; audit reports seven existing lower-severity advisories (two high, three moderate, two low). No dependency manifest changed.
- Documentation integrity: **251 maintained sources / 75 required routes passed**. Ruff check passed; format check reports **1134 files already formatted**. Logs `/tmp/nano-feat578-docs.log`, `/tmp/nano-feat578-ruff.log`, `/tmp/nano-feat578-format.log`.
- These checks cover build/regression boundaries, not missing device or user-journey evidence. Final remote CI remains pending an eligible delivery PR.

## Product R1 and follow-up fixes

- Independent [acceptance R1](acceptance-r1.md) at `b970e20a6` records real chat, Agent creation, global Work, task-graph reference, admin and configuration-conflict journeys. S1/S28 pass; S10 fails because Photos did not open; the other scenarios retain explicit incomplete branches. This is not complete product acceptance.
- `8b30e2361` restores the inherited response-metrics behavior: running Agent timer, fixed final wall clock, collapsed inline token details and cache count/percentage including zero. It also adds the HTTPTransport regression for a persisted message whose response is lost: history refresh and normal send do not retransmit; explicit retry retains the caller key and a single canonical history item.
- `1708bdd74` moves PhotosPicker presentation from the transient menu into the stable Conversation view, driven by a menu button. Root build passes; actual UI closure still requires unlocking the Mac and re-testing selection/upload/preview/share.
- Actual simulator suite after both fixes: **22 passed** (12 XCTest + 10 Swift Testing), log `/tmp/nano-feat578-xctest-r5.log`, xcresult `/tmp/nano-ios-build/Logs/Test/Test-NanoIM-2026.10.05_02-18-15-+0800.xcresult`. Release archive passes at `/tmp/nano-feat578-archive-r5.log`; current unsigned IPA and hash are in toolchain readiness.
- [Static closure R2](closureverification-r2.md) and `code-review-r4.json` retain no new code finding. Source metric omission and uncertain-send regression are closed; metric rendering, Photos UI, delayed config confirmation and final gates remain open. Real UI 409 conflict recovery is independently evidenced by product R1.
- Synced main `d87ffa3d1` via merge `7cdb515c9`. Incoming Web viewport/manifest changes did not change native source or API contracts used by the App. Retained prior full-suite evidence; affected checks passed (6 app-factory tests, 97 Web tests, docs integrity 248 sources/75 routes).

## Locked-desktop checkpoint

- CUA reported the Mac locked; user has been asked to unlock manually. No attempt to bypass the lock. No phone, Mini or production operation was performed.
- Stopped own isolated IM/Gateway and design HTTP preview; loopback ports 62008/58781 are released. Retained local test DB/workspaces and scoped configuration under a private 0700 resume directory with 0600 files. None is tracked or committed.
- Resume without wiping the prepared test objects: `tmux new-session -d -s feat578-ios 'bash /tmp/nano-feat578-resume.sh'`. This local-only helper restores the scoped config and starts the same IM/Gateway; it has passed shell syntax validation but has not yet been executed. Verify live API, owner/node and process cwd on resume. Do not use the fresh-bootstrap e2e-up path against this retained DB, because it recreates the database.
- Reinstall the current Debug build after manual unlock, then resume product R2 from the explicit IDs/actions in acceptance R1. Prior installed UI was `b970e20a6`; current source is `1708bdd74`. Do not label the older UI screenshots as the fixed version.
- No PR, current-spec merge, unit archive or completed delivery claim yet. Phone/Mini/free-signing and actual renewal remain the later stage once simulator acceptance is ready.

## Resumed simulator R2

- User unlocked the Mac and explicitly requested continuation. Restored the same isolated IM/Gateway without recreating the DB; confirmed process working directories, loopback port, owner and node. Reinstalled implementation `1708bdd74`.
- Independent product review exercised the fixed Photos entry through real selection, upload/send, Quick Look and system sharing. It found the separate in-app image sheet cropped the 600×400 test image. Removed the unbounded horizontal scroll axis so `scaledToFit` receives the viewport width; native build passes (`/tmp/nano-feat578-build-r6.log`), visual closure pending installation. The image is a generated test fixture, not user media.
- Real response timing and expanded token/cache metrics were observed. A genuine `web_fetch` permission request was allowed once; another request was denied while the owned Gateway was paused, and the UI showed submitted/waiting with the choices removed. Gateway was resumed immediately after that capture; final late-receipt verification remains with the reviewer.
- Actual CLI device binding completed through the native account confirmation and subsequent terminal confirmation. Started that separately isolated node for node-switching journeys. Both runtimes are owned test resources and must be stopped at the next handoff.
- Prepared an active ordinary test member, actual global-agent child execution/exploration graph, and a real far-future cron entry for the remaining native journeys. These preparations alone are not product acceptance.
- Dedicated Feishu test App/Bot identity matches by the existing credential lookup, and the test user verifies. CLI Bot verification currently fails with an OAuth endpoint EOF, so real channel connection testing remains unstarted pending the repository profile prerequisite. No production Bot or service was touched.

## User visual rejection and design reopen

- User inspected actual login and chat screens and rejected the UI/UX. Functional coverage and prior semantic prototype matching do not establish visual acceptance. Stopped product reviewer clicks and received `acceptance-r2.md` with overall fail.
- Last installed binary is `28ba862fc`; it closes image aspect ratio and localized invalid-credentials feedback by real UI evidence. No new feature acceptance is being counted while visual design is reopened.
- Root is revising the existing design/prototype from current Web source and rendered 390-wide pages, with explicit typography, palette, content density, action placement and real SwiftUI screenshot requirements. Function/API/permission/install scope remains unchanged.
- Pending uncommitted code folds tool descriptions after the reviewer encountered multi-screen descriptions. This is not a completed redesign. New visual implementation follows the limited independent design review.

### 2026-10-05 原生视觉修订第一轮

- 视觉设计 R3 Approved（0 CRITICAL / 0 WARNING）；R2 因 reviewer 的 IAB 连接不可用保留未完成记录，R3 独立目视 root 实拍的 390/430 配置页关闭保存断行。
- 原生落实：语义颜色资产及深色变体；登录改品牌/持久字段标签/单主动作/连接折叠；四根页紧凑标题；聊天连续白底列表、单行摘要/时间/未读；Agent 身份与设备状态；详情概览/发消息/管理分组；配置顶部保存、能力与工具说明折叠；消息双方缩进、边界和 composer；任务真实字段与画布顶部锚定。
- 实际模拟器首轮发现根标题被 iOS toolbar 压为省略号、全局文字样式影响主按钮；root 已修正并重建。模拟器已安装 visual-build-r2，恢复登录与真实隔离 API 读取成功。
- 已目视并保存 `output/feat578/native-visual-{login,chats,tasks}.png`（本地缓存不提交）。Agent 列表/详情与配置已目视 R1；R2 修改后的这些页面、聊天详情、任务图、管理代表页、390/430 及 Dynamic Type 尚待完成，不能宣称 P6 通过。
- `visual-build-r1/r2` 构建成功；`/tmp/nano-feat578-visual-tests-r1.log` XCTest 12 + Swift Testing 10，共 22 tests passed。无 API/权限范围调整。最后配置 DisclosureGroup onChange 的闭合位置恢复到外层 Section，需最终编译覆盖。
- Mac 锁屏使 CUA 无法继续，已请求用户手动解锁；不绕过锁屏，不恢复功能旅程或真机门槛。六条新会话为真实隔离服务的测试 fixture，未硬编码到 App。
- 本轮最终提交 `c8eafc360` Release archive 成功（`/tmp/nano-feat578-visual-archive-r1.log`），覆盖最后配置 onChange 调整；产物为 `output/feat578/NanoIM-c8eafc360-unsigned.ipa`，仅供后续重签安装，不声明真机已安装或视觉通过。
- 独立静态 R6 发现普通 TextField 仍监听 `.search` submit trigger，键盘搜索不会即时查询；root 已改为普通 `.onSubmit`，保留现有 load()/分页逻辑。静态 verifier 明确 P6 尚未通过；该缺口不以 archive/tests 掩盖。
- R7 限定静态 closure 为 `[]`，关闭普通 TextField 提交事件问题；键盘现场验证仍待解锁，P6 未通过。`3691c0f8b` 最终 Release archive 成功，日志 `/tmp/nano-feat578-visual-archive-r2.log`，最新产物 `output/feat578/NanoIM-3691c0f8b-unsigned.ipa`。

### 2026-10-05 窄屏逐页目视与输入/任务布局修正

- 用户“继续”后 Mac 解锁；构建 visual-build-r3 成功，新建专用 iPhone 14（390）和 iPhone 14 Pro Max（430）模拟器，原 iPhone 17 Pro 保留但关闭。
- root 逐页实际查看 390 普通字体下登录、聊天、对话、任务、关系图、Agent/详情、配置、我的及设备代表页；本地截图 `output/feat578/native-visual-r3/390-*.png`，不提交缓存。
- 发现空 UITextView 外层 min/max frame 总取最大高度，改为使用已有 sizeThatFits 的固有高度，并添加消息占位提示。真实 UI 验证空白 1 行、数字草稿 3 行随内容增高、清空后缩回；未发送检查草稿。
- 依赖图改为按原 ranks 纵向排列，同层兄弟保持横向；连线从下到上对应依赖方向，节点高度随 Dynamic Type 缩放。真实两节点计划首屏完整可见，点击第一个节点仍打开正确详情。图只展示标题/状态，完整描述仍在节点详情，关系/API 不变。
- 统一管理页滚动背景为语义 canvas。visual-build-r4 编译通过并安装于 390 模拟器。两种宽度/大字体仍待独立 P6 验收，不能用 root 自检替代。
- `5ab02fd65` 独立静态 R8 无具体 finding，报告由 `440093403` 提交；该提交只增加报告，未改变当前模拟器 binary。Release archive R3 成功，产物版本与哈希见 [工具链记录](../evidence/toolchain-readiness.md)。
- 独立 P6 正在同一 binary 上检查 390/430 普通字体、大字体及直接布局交互；root 已释放 Simulator 控制。整体功能及安装验收仍未通过。
- 专用 `e2e-feishu-testagent` profile 重新验证成功：bot/user ready、token valid。仅恢复前置条件，没有启动通道 listener，也未将此计为 S20/S21 通过。

### 2026-10-05 独立 P6 完成与功能续验

- [原生视觉独立 R3](acceptance-visual-r3.md)：九页 × 390/430 × 普通/大字体共 36 必需画面，另 8 交互/滚动截图；P6 scoped PASS，0 major/blocking，2 minor。已向用户展示新版登录、聊天与对话实际截图；reviewer 结论不替代用户本人后续视觉意见。
- 清空任务搜索的立即反馈作为小修落实于 `051abdcf8`：空 query 显式 reload。visual-build-r5 成功；独立 reviewer 窄复验清空后一次观察已恢复两条任务，无再次 Return。节点内部留白保留为非阻塞 minor，不为其扩大实现循环。
- `051abdcf8` Release archive R4 成功，版本/hash 见工具链记录。当前仅390安装此版；430保留上一版且已关闭。P6 未变页面证据 retained。
- 恢复 `acceptance-r2` 未完成功能旅程；真实2099测试Cron已从App明确删除，后端 GET jobs 200 [] 辅助确认。整体 S1–S30 和物理安装/续签仍未通过。
- 专用 Feishu profile 曾一次临时验证失败，随后 live App/Bot/user 全部验证通过且凭据lookup匹配；取得专用Bot listener lock，owner为本次Gateway，登记在本次e2e-down环境中。尚未把准备工作计作通道连接验收。

### 功能续验发现：心跳保存后读回缺字段

- 独立产品 R3 用真实键盘输入24h、03:00–03:01，暂停节点提交后出现pending，恢复节点重读显示已确认但字段为空。已将临时心跳关闭，当前实际feature为false。
- 只读核对同一真实operation：candidate与Gateway applied result均保存完整cadence；问题在既有IM live读取合并重新构造AgentProfile时漏传heartbeat_json，默认为null。不是原生绑定或写入丢失；Web使用同一路径也受影响。
- 服务端修复只保留既有persisted heartbeat_json，不新增接口或管理能力。扩展已有live配置契约测试，修复前复现NoneType失败；补字段后配置契约、API集成及operation flow共32项通过（`/tmp/nano-feat578-heartbeat-{red,green}.log`），窄Ruff/diff检查通过。
- 本次自有IM需协调重启载入修复，再由reviewer窄复验；生产、Gateway与DB保持原状。此处不将尚未完成的原生复验记作通过。
- 独立静态 R10 为 `[]`；本次IM已协调重启载入 `c4794acef`，新PID69765（Gateway45904未重启）。实际mirror/live均返回heartbeat_json `{}`、enabled=false、profile_version4；非空cadence的原生重读仍需窄复验。
- [产品续验 R3](acceptance-r3.md) 已落盘：搜索清除、Cron删除、配置pending分支通过；心跳回显原生复验未完成，整体仍fail。用户未批准降低最终门槛。
- Mac再次锁屏，已请求手动解锁，未绕过。停在e2e添加飞书通道表单，输入可能部分执行但从未点击保存；reviewer清除了CUA凭据变量。root实际API确认通道列表为空后释放自己尚未使用的Bot listener lock，避免占用其他测试；续验前需重新执行专用profile/identity/lock准备。
- 保留本次隔离IM/Gateway与第二绑定node用于续验；当前没有暂停进程或Feishu listener。源head `c4794acef`，原生binary仍 `051abdcf8`，最新IPA也为051。没有生产变更、手机操作、PR或最终完成声明。

### 2026-10-05 解锁续验：空心跳配置的冲突与反馈位置

- 用户回复“开了”后恢复；主IM69765/Gateway45904均正常运行。专用测试Bot重新完成App/Bot/user验证及listener锁准备，reviewer开始e2e的原生通道生命周期。
- 心跳续存实际被operation_conflict拒绝，节点online且未暂停。对比最后committed candidate与Gateway本地配置规范化快照，仅heartbeat_json不同：持久化`{}`，运行时未配置为null。两者节律相同却导致指纹不同。
- 仅在IM与Gateway的fingerprint入口等价化空对象与null；wire仍保留`{}`，避免破坏显式清空（持久化层null代表保留）的语义。跨两端回归先红，修复后配置操作单元/恢复/集成/契约50项通过，窄Ruff/diff通过，日志`/tmp/nano-feat578-heartbeat-empty-{red,green}.log`。
- reviewer还观察到顶部保存后字段禁用，结果提示位于长表单底部而不可见。原生改为错误或确认结果出现时滚到已有状态/恢复操作区；不新增保存状态或改变草稿逻辑。functional-build-r6成功，仍待安装及实际冲突/成功窄复验。
- 独立静态 R11 无具体 finding，保留wire显式清空语义与既有保存状态分支，实际滚动/保存交由产品窄复验。
- [产品 R4](acceptance-r4.md) 已完成e2e专用飞书通道：v1新增并实际连接、v2保留密钥、v3替换为同一测试密钥并连接、v4停用并实际停用、确认删除后列表为空。未外发消息/改平台权限；root实际API核实删除后释放listener锁。S20本轮凭据旅程通过，S21未完分支仍inconclusive。
- reviewer交还UI后，正常终止本次旧IM/Gateway并从`ba202f5d3`启动：新IM72554、Gateway72564，两node均online，DB/config不重建；第二绑定node保持原进程。390安装functional-build-r6，AppPID72595。只更新本次隔离资源。


### 2026-10-05 R5/R6 功能续验与蒸馏入口修复

- 产品R5在`ba202f5d3`验证心跳24h/03:00–03:01保存重开、空cadence清空再保存，以及真实profile_version冲突的可见反馈与保留草稿恢复。R3-01、R4-01均关闭。
- 新增真实旅程：65条历史分页保留位置、新消息不抢历史滚动、真人双向消息与两聊天草稿隔离、已打开图片撤权后自动关闭并清空、多节点切换和自定义既有目录确认、重复Agent ID反馈、完整配置与显式空Skills名单持久化。
- 仅本次测试消息经临时loopback故障代理制造“服务端201落库、客户端HTTP回执和WS中断”。原生显示待确认，恢复后单次重试核对清除草稿并显示唯一完成消息；收件方前后实际GET均仅同一个message ID。代理已停止、62009端口释放、App回到62008直连。未改生产或外发真人消息。
- R5发现整理知识的两个默认Picker无法展开；`c2cbfa7a1`仅改为原生导航列表选择。build-r7成功、独立R12为[]；产品实际选择来源/执行Agent/目标范围均保持，R5-02关闭。
- 继续生成时暴露目标聊天标题为空且输入禁用：蒸馏响应创建了聊天，但客户端列表未重读。`6155e1b86`在写草稿/导航前调用既有loadConversations，与fork入口一致；build-r8成功、独立R13为[]。390原地安装PID78253，产品确认正确标题、可编辑/删除草稿和发送按钮状态，未自动执行Skill，R6-01关闭。
- 以上是实际失败→最小UI接线修复→真实原生复验；未为Picker样式或回调顺序添加重复实现的单测。既有22项原生测试保留，服务端50项相关测试保留；本次Python窄Ruff与diff-check通过，docs-check通过264份维护文档/75条必需路由。
- 当前产品功能续验仍进行中；最新Release IPA仍是工具链记录中的`ba202f5d3`，需在候选稳定后重新归档。真机安装、Mini续签和完整S1–S30门禁未完成，未创建PR/部署生产。

- `6155e1b86` Release archive R6成功，已保存对应unsigned IPA并核实bundle ID、版本、最低iOS与Release ATS限制，hash见工具链记录。产品R6仍在续验；此归档不等同免费签名/真机通过。

- [产品R6与S1–S30当前合并表](acceptance-r6.md)已完成：已观察major均关闭，仍为inconclusive。12:48 CUA再次明确Mac locked后停止；用户手动解锁前不重试。停在未提交的578 Group R6新群草稿，原生6155e1b86；保留隔离服务与现场用于恢复。

### 2026-10-05 R7 续验与附件失败处理补齐

- [产品R7与最新S1–S30合并表](acceptance-r7.md)新增通过注册准入、群管理、无设备/路径、配置能力、Skills/Cron/心跳、绑定拒绝/过期、节点离线恢复与策略失败草稿旅程。单次loopback 429/503夹具仅对本次明确请求返回故障，不转发或记录密码；`b8f9a9bc6` 中文提示经原生窄复验通过，下一次真实登录恢复成功。R14独立静态无finding。
- 单实例恢复第二节点自启动服务并核实两个节点online；没有留下SIGSTOP。策略失败后全字段仍等于原baseline。临时绑定拒绝/过期operation及其链接、非法目录夹具均已清理。
- 仅为390 Simulator创建独立`578 Test Files`容器，提供新命名的83-byte TXT、两页PDF和16-MiB文件，无私人内容/产品配置变化。TXT经原生选择、带文字发送给专用测试真人、Quick Look显示正确标记已证明；分享入口存在，但13:55 Mac锁屏使导出点击/保存结果无法验证，立即停止UI。
- root核对S11发现硬编码10MiB违反当前服务15MiB策略，且失败文件未逐项保留。移除客户端固定阈值，由当前服务限制裁决；失败数据按聊天保留，显示移除/适用重试和Retry-After倒计时，普通发送在失败项存在时禁用。显式“仅发送文字，保留附件”保留失败文件及所有已上传未发送附件；撤权/账号清理销毁本次失败数据及其UUID，迟到上传不能恢复旧账号内容。
- 原生25项测试通过（15 XCTest+10 Swift Testing），新增状态契约验证失败阻止普通发送、仅文字保留全部附件、重试使用原字节、遵守Retry-After，以及clear后迟到上传不回填。日志`/tmp/nano-feat578-attachment-tests-r10.log`，xcresult为`Test-NanoIM-2026.10.05_14-00-20-+0800.xcresult`。此处实现缺口依据源码与当前契约核对，未宣称16MiB或故障UI已复现/修复通过。
- 锁屏后不尝试绕过，已请求用户手动解锁。S11新候选仍需独立静态审查、重新归档及实际失败/冷却/仅文字/删除复验；整体Full门禁、Mini与真机安装续签仍未收口，无PR/生产部署。

- 独立静态R15确认一个P2：后台停止实时流会轮换epoch，使在途上传响应被忽略，保留的行一直uploading。新gated-upload测试对成功/失败两分支均实际失败（4断言），日志`/tmp/nano-feat578-upload-background-red.log`。最小修复移除上传对stream epoch的依赖；已有单次upload UUID存在性同时隔离clear/撤权后的迟到响应，不增加另一套代际计数。
- 修复后全26项原生测试通过（16 XCTest+10 Swift Testing），日志`/tmp/nano-feat578-upload-background-green.log`，xcresult `Test-NanoIM-2026.10.05_14-09-50-+0800.xcresult`；后台完成与账号清理两种生命周期分别验证。R15 source closure与原生S11实际操作仍待完成。
- root只读辅助核实R7的TXT完成消息唯一，附件为83 bytes，授权GET200且SHA-256与本次夹具原字节一致。为解锁后窄复验新增12MiB合法文件与各一小型重试/冷却合成文件，独立夹具容器未改变产品。62009代理仅更新单次精确uploads路径处理，普通401转发已验证，当前未启用任何fault；两台隔离节点保持online。
- `2505c9772`独立R16为`[]`、R15 finding closed；verification保留not_pass，只待已列出的实际产品门禁，不机械重审已留存范围。Release archive R9成功，最新unsigned IPA及hash见[工具链记录](../evidence/toolchain-readiness.md)。390旧候选及未确认的分享现场保留，解锁后先核实状态再安排安全安装；没有把构建成功或锁屏归档计作产品通过。
