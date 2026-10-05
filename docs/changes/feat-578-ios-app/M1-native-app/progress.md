# M1 progress

Status: native implementation and observed review fixes integrated at product revision `107290abe`; 27 native tests and the latest arm64 device archive pass. Independent R16 closes the task-reference/root-detail failures; [R17](acceptance-r17.md) is the latest product scenario matrix. Remaining product branches and physical iPhone/Mini signing and renewal keep final acceptance open. No PR or production deployment.

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
- root核对S11发现失败文件未逐项保留，同时客户端10MiB与策略表15MB不一致。移除重复客户端阈值，由当前服务限制裁决；失败数据按聊天保留，显示移除/适用重试和Retry-After倒计时，普通发送在失败项存在时禁用。显式“仅发送文字，保留附件”保留失败文件及所有已上传未发送附件；撤权/账号清理销毁本次失败数据及其UUID，迟到上传不能恢复旧账号内容。R8实际核对确认上传路由仍固定10MiB，策略表15MB并未驱动该边界，纠正此前把15当生效上传上限的推断。
- 原生25项测试通过（15 XCTest+10 Swift Testing），新增状态契约验证失败阻止普通发送、仅文字保留全部附件、重试使用原字节、遵守Retry-After，以及clear后迟到上传不回填。日志`/tmp/nano-feat578-attachment-tests-r10.log`，xcresult为`Test-NanoIM-2026.10.05_14-00-20-+0800.xcresult`。此处实现缺口依据源码与当前契约核对，未宣称16MiB或故障UI已复现/修复通过。
- 锁屏后不尝试绕过，已请求用户手动解锁。S11新候选仍需独立静态审查、重新归档及实际失败/冷却/仅文字/删除复验；整体Full门禁、Mini与真机安装续签仍未收口，无PR/生产部署。

- 独立静态R15确认一个P2：后台停止实时流会轮换epoch，使在途上传响应被忽略，保留的行一直uploading。新gated-upload测试对成功/失败两分支均实际失败（4断言），日志`/tmp/nano-feat578-upload-background-red.log`。最小修复移除上传对stream epoch的依赖；已有单次upload UUID存在性同时隔离clear/撤权后的迟到响应，不增加另一套代际计数。
- 修复后全26项原生测试通过（16 XCTest+10 Swift Testing），日志`/tmp/nano-feat578-upload-background-green.log`，xcresult `Test-NanoIM-2026.10.05_14-09-50-+0800.xcresult`；后台完成与账号清理两种生命周期分别验证。R15 source closure与原生S11实际操作仍待完成。
- root只读辅助核实R7的TXT完成消息唯一，附件为83 bytes，授权GET200且SHA-256与本次夹具原字节一致。为解锁后窄复验新增12MiB边界测试文件与各一小型重试/冷却合成文件，独立夹具容器未改变产品。62009代理仅更新单次精确uploads路径处理，普通401转发已验证，当前未启用任何fault；两台隔离节点保持online。
- `2505c9772`独立R16为`[]`、R15 finding closed；verification保留not_pass，只待已列出的实际产品门禁，不机械重审已留存范围。Release archive R9成功，最新unsigned IPA及hash见[工具链记录](../evidence/toolchain-readiness.md)。390旧候选及未确认的分享现场保留，解锁后先核实状态再安排安全安装；没有把构建成功或锁屏归档计作产品通过。

### 2026-10-05 用户模型指令与R8媒体续验

- 用户要求后续subagent使用GPT-6.1 Sol，覆盖技能角色模型表。root停止此前Astra产品reviewer，委派新的独立Sol reviewer，保留此前证据；未重跑已通过范围。
- Mac可操作后完成旧TXT分享保存的“保留两者”；root只读确认新83-byte副本SHA与原字节一致。安全断点后原地安装`2505c9772`，390进程92311，数据未清，UI交还独立reviewer。
- 新包PDF真实选择/取消、再选发送完成、两页Quick Look和系统分享保存完成；root确认新副本2038 bytes及SHA与原PDF一致，真实发送消息唯一且仅一个PDF附件。
- 12MiB实测被服务拒绝，原生保留对应文件、显示大小原因、移除可用/无重试/普通发送禁用。只读代码确认`messages.py:54`上传上限10MiB，流存储超过此值返回413；与Web同一通路。策略表仍15MB但未驱动上传边界，此为既有IM不一致，不能把root此前15MB推断当成运行事实。本次按实际10MiB继续验收，不修改既有服务上限，追加9MiB合成合法文件；12MiB已覆盖真实超限，16MiB不重复同一分支。
- [产品R8](acceptance-r8.md) 完成9MiB真实上传发送、单次503逐项失败保留及原字节重试、显式仅文字保留所有附件、429倒计时和恢复。TXT/PDF系统导出的新副本与原合成文件字节一致；受控故障只代表该HTTP响应处理，不冒充平台自然限流。429代理未记录所有普通POST计数，提前重试证据限于实际禁用UI与独立transport测试。
- [产品R9及最新合并表](acceptance-r9.md) 独立裁决S4、S11通过：下载503在原消息可见，原文件按钮正常重试打开正确内容；外部合成PNG在独立loopback端口显示且接收端Auth/Cookie/credential-query均为空，保护资源302跨origin未被跟随，正常重试恢复。凭据隔离结论限定本次不同端口受控origin，不扩大为所有外站。
- 在途上传已真实到达上游201/47bytes，但JSON主体由本次代理延迟；退出时native取消旧tracked请求，代理观察连接关闭、未超时、未释放主体。普通B账号只见本人及空聊天，恢复nano后无旧待发/失败文件，历史中未出现该附件。此为实际退出中断与账号隔离证据；不能宣称旧201主体在B账号完整到达。忽略取消的迟到transport回填保护保留为独立26项原生测试的另一层证据。
- R10只继续精确剩余可见域已读、有效群提及/配置分界及前后台回复/提醒，已通过管理范围不重复。当前没有新产品finding或source修改，native候选仍`2505c9772`；整体Full门禁与物理安装/同网续签尚未收口。

### R10 长历史跳转现场与最小候选

- [产品R10](acceptance-r10.md) 确认major R10-01：专用真人历史的02/03处收到新11后保持位置，权威未读为1；点击“最新消息”后停在08/09，11未实际可见、AX无法读取正文。native进程92311持续约99% CPU，2秒采样主线程持续在SwiftUI/AttributeGraph事务与LazyStack布局；没有crash，采样不单独证明具体触发代码。
- 点击后权威未读变0，只记录为异常现场，不据此关闭可见域验收。R10独立裁决S6及整体fail，已暂停其余功能旅程并保存安全安装断点。
- 最小候选仅移除Latest按钮的显式滚动动画，沿用自动跟随/分页已有的不动画scrollTo路径，不改已读、消息合并、API或数据。build-r10成功；同一长历史从早期内容回到11的原生复验仍待完成，不先把候选或根因假设标为修复通过。

### R11 Latest闭环与配置分界窄修

- [产品R11](acceptance-r11.md)在同一长历史从02/03点击Latest后实际看见10及11完整正文，返回/重入仍响应；root随后只读CPU为0.0%，R10-01关闭。独立静态R17无finding，仍保留其它未完成产品门禁。
- 原生新群有效提及e2e-peer，两轮真实Gateway/LLM均由该Agent完成42；custom_prompt从空改为精确`578-R11`、保存获节点确认，再清空保存获确认。root核对恢复version11，除版本/更新时间外全部配置与version9 baseline一致。
- R11-01 major直接复现：API的配置标记锚定M2请求且位于M2前，原生两次显示在M2后。TimelineMerge保留先缓存M2，再追加迟到标记，是此顺序的实际原因。新增原生回归测试在旧实现失败，日志`/tmp/nano-feat578-timeline-red-r12.log`；测试包含已缓存请求、后续配置标记、最终回复和重复刷新。
- 修复按服务与Web的created_at/id顺序排列消息，按before_message_id把标记紧邻对应请求之前；尚未载入锚消息的标记保留在内存但暂不渲染。现有分页测试原将121条消息设为相同日期却期待数字ID顺序，已改为各条实际递增时间，保留跨两页恢复及旧cursor断言。
- 全27项原生测试通过（17 XCTest+10 Swift Testing），日志`/tmp/nano-feat578-timeline-green-r12b.log`，xcresult `Test-NanoIM-2026.10.05_15-55-51-+0800.xcresult`。第一次全量的同日期fixture失败完整保留在`timeline-green-r12.log`，未当作通过。实际新包M2顺序和下一轮迟到标记仍需独立UI复验；未先关闭R11-01或整体Full门禁。

### R12 分界闭环与发送布局现场

- [产品R12](acceptance-r12.md)直接核实已有M2与唯一实时M3分界均紧邻对应请求前，R11-01关闭。root实际API核对M3请求、peer completed回复和唯一新标记；profile_version11、custom_prompt空，除版本/更新时间外与v9 baseline全部字段一致。独立静态R18无finding，旧有效范围保留。
- R12-01 major：原生唯一多行bash算数请求发送后界面停在旧M2/M3与发送spinner；API请求已持久、peer真实bash调用1次并completed500500，App2067 CPU99.0%。2秒sample保存为`/tmp/nano-feat578-native-send-sample-r12.txt`，1267主线程样本中1257处于SwiftUI GraphHost.flushTransactions，持续更新布局；没有先重启、重复发送或将服务完成冒充UI完成。
- 窄候选移除LazyVStack底部行的onAppear/onDisappear状态写入，使用滚动geometry的实际visibleRect计算底部可见性；build-r13成功。此为待实测候选，采样不单独证明具体回调根因；同多行发送、历史保持与Latest需要真实UI复验。
- `f77b34633`设备归档成功，hash及准确限制见工具链记录；它仍含R12-01，不能作为已验收安装候选。Mini只读SSH再次8秒超时，未修改该机器或生产服务。用户真机后置约定保持。

### R13 发送与后台闭环、冻结候选

- [产品R13](acceptance-r13.md)关闭R12-01：同类唯一多行请求立即清空composer、Latest直接见真实bash进行中及0:09–0:10，按Simulator Home后从主屏图标恢复唯一500500 completed、17.1s，过程/结果详情可见exit0/stdout500500/13383ms；Back响应正常。root实际API唯一性及工具状态一致，App4396 CPU0.0%。长历史02完整/03顶部→Latest10/11/12完整可见且AX正常，滚动影响范围闭环。
- S27计划人类消息唯一201，但reviewer收到明确观察时刻的控制消息时已晚于3秒banner窗口，未捕捉点击；准确保留inconclusive，不再用该时序方式追加消息。后台真实恢复/去重通过子范围保留，短banner点击由真机补齐。独立R19 code `[]`，verification保留未完成门禁。
- `5de8ffdb4`冻结源码27项原生测试、4120项Python及808项Web全部通过，Ruff及文档完整性通过；Release最新IPA成功且校验arm64/bundle/最低iOS/无ATS例外，具体hash见工具链记录。未推送或创建PR，产品门禁/签名安装/同网续签仍未完成。
- 已以具体App/最新IPA向用户询问本chat iPhone时段与Mini桌面/同网状态，尚待答复。Mini Tailscale探测经DERP(nue) pong 3.594s；实际SSH无ProxyCommand/ProxyJump且8秒超时，直连HTTP8011拒绝连接。环境代理下curl502未作为Mini服务证据；没有修改网络、节点选择或生产进程。
- R14只补可完成的Company/Work分页。Company当前51人（45个额外受控pending fixture：5经HTTP注册、触发既有5/900秒限流后停止；40由现有UserRepository种子创建，不是注册入口证据），真实API50+1无重叠。Work仅578001的临时loopback条件使用实际API合法limit1获得1+1真实轮次；初始39真实过程项按3项/实际seq游标呈现，更多过程仍读取真实items API。条件减小与真实执行数据分开记录，不声称自然100项以上历史。临时控制由root收回后清除；无产品源码修改或认证限制关闭。

### R14 分页闭环与 R15 补充前置

- [产品R14](acceptance-r14.md)完成公司成员首50→末页1追加、旧页保留和末页无更多；Work在受控分页条件下完成1→2真实轮次、3→39真实过程、顺序/归属/详情与刷新保页。记录实际页首下拉后两轮仍在，未独立捕捉手动spinner；caller真实refresh请求包含首/旧页重读，不能区分手动与前台3秒自动刷新。S15按此限定范围通过，不扩展为自然大历史。
- root在安全handoff后清除唯一work_paging控制；直连62008与经62009正常Work均2轮、39/38过程项、cursor=nil，实际执行数据未改。目录初次定位只是Agent ID578001当前展示名578002未对齐，真实contacts有6个Agent且无下页，原生目录分页已有实现；没有目录缺失finding。
- R15只补S14明确关系字段/失效聊天关联和S25机器资格。全新隔离群c_82otvgr8由真实e2e-peer/LLM调用task_graph生成tg_b839513e revision2；探索选择/派生、嵌套DAG前后依赖、结果/选择理由/变更说明是明确记录的合成比较，不声称任务被实际执行。未碰旧私聊，未删除任务图。
- 为S25在R9一次性普通测试成员iosr9late下真实绑定第三个隔离Gateway wt-feat578-owner-revoke-r15，独立配置/workspace/数据、autostart=false、heartbeat=false、无飞书。实际owner节点online/1Agent、旧runtime WS握手HTTP101与浏览器active已记录；原生停用及机器拒绝结果待独立验收。两个原测试Gateway和生产不变；caller清理新增进程。
- R15实测发现嵌套TaskNodeView回聊只pop一层，连续点击会积累多份引用到草稿，但没有自动发送；根scope有子节点时也缺根详情入口。root确认同一modal owner未关闭及入口缺失，最小修由TaskGraphView在引用时清selected关闭整张sheet、子层不再dismiss，并增加当前scope的详情按钮复用既有字段页。构建`/tmp/nano-feat578-task-reference-build-r16.log`成功；实际新包闭环及独立delta审查待验。既有R15失败不改写为通过。
- S25原生仅确认停用一次性iosr9late，随后caller真实旧runtime WS握手101→403、旧browser访问401、持久节点offline/owner suspended/node_epoch2/机器credential清除；两个原节点仍online。新增第三Gateway PID9311已请求正常退出，未更改生产或旧节点。

### R16 任务闭环与 R17 工作记录补验

- [独立 R16](acceptance-r16.md)在新候选 `107290abe` 直接关闭 R15-01/02：根 Details 可读 todo、记录结果、选择 A、理由和 change_note；最深 Check 一次引用直接关闭整张详情进入正确新群，唯一草稿可编辑且未自动发送，随后已清空。真实删除本次新群后重新读取，B/A 显示未关联并移除回聊入口，五节点与 Prepare→Check 依赖保持；S14 pass。合成比较记录不代表任务实际执行。
- 原生27项测试及 Release archive 在新候选重新通过；独立 R20 code `[]`，其[verification closure](verification-task-reference-r1.md)保留原失败事实并关闭 TR-C1。IPA 版本与哈希只在[工具链记录](../evidence/toolchain-readiness.md)维护。Python/Web 源码未变，保留 `5de8ffdb4` 全量证据；未机械重跑全量。
- 一次性第三 Gateway PID9311 已正常退出且进程消失，未创建 autostart。两个原 owned 节点仍 online；真实停用后的机器资格撤销证据保留，不改生产或原节点。
- [独立 R17](acceptance-r17.md)补验 S12：只对578001 Work的本机 HTTP 响应暂时移除最近主usage、保留各轮原output，其余真实数据不变。原生主/本轮缺字段显示“未报告”，保留output3330和26.50s，不伪造0或0%进度；真实后台subagent completed1641、父/子归属、工具调用完成与实际聊天投递分别可读。结论限定本次真实执行和受控缺失metadata，不冒充自然provider缺报或全部子任务类型。
- reviewer安全交还UI后清除唯一 `work_missing_usage` 控制。实际62008/62009均200，最近主usage恢复11 keys、两轮usage恢复8 keys，两个原节点online；私有恢复回执 `/tmp/nano-feat578-r17-restoration.json`。没有新源码、LLM执行或平台消息。整体 Full 门禁仍未通过，真机/Mini资源问题仍待用户答复。
