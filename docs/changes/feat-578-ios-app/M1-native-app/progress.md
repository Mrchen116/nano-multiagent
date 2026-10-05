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
