# M1 progress

Status: native implementation and review fixes integrated; simulator tests and real chat work. Independent simulator acceptance is in progress. Final product acceptance remains open.

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

- Updated Release archive and CI integration.
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
