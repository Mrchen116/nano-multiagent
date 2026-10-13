# M1 implementation evidence

Baseline: `a3b2c8aa5a7e8aa23d0b57c2adb0289ccd5a541d` (`origin/main`). Product changes are in the dedicated `codex/feat-584-task-progress-permissions` checkout. This is author evidence; independent product acceptance and static gates remain separate reports.

## Implementation and test ownership

- IM uses a shared current-conversation read/write decision, fixed task conversation, real node creators/assignees, six states, claim semantics and independent subtree deletion authorization. Task mutation, system notice, durable relay and receipt commit together. Replay rechecks current access, including after removal/dissolution.
- `task-collaboration.test.ts` is the SQLite boundary owner for new task identity/ACL/transaction semantics; `control.test.ts` retains existing DAG/explore and revision coverage. `e2e/conversation-tasks.test.ts` owns HTTP/WebSocket integration of public read/member write, Agent join, dissolution and relay reconnect revocation. Existing private-task outsider expectations were changed to the new contract, not removed.
- PA retains its two existing execution paths; system sender identity and valid mentions reach attention/Inbox without becoming human deletion consent. Existing external/global/single-thread tests were extended. DSH task and conversation mutation calls retain ordinary approval; permission tests cover allow and deny before product dispatch.
- Web existing task tests were rewritten for the overview/overlay flow; the task editor has its own mutation/conflict boundary. iOS adds task decoding/state tests and extends chat cache revocation tests. Existing unrelated coverage is retained.
- New Agent creation exposed an actual integration fault: its IM user placeholder can be pending while its registered profile and human owner are active. Assignment previously returned 400. A SQLite regression reproduced that failure, then passed after Agent qualification was resolved from its active registration/owner rather than the placeholder's human-membership flag.

## Automated validation

All commands run in the unit checkout unless specified. Local logs are temporary evidence and are not committed.

| Gate | Result / locator |
|---|---|
| Root build | `pnpm build` passed; `/tmp/feat584-final-build.log` |
| Typecheck | `pnpm typecheck` passed; `/tmp/feat584-typecheck.log` |
| Runtime / IM suite | 185 cases covered. Serial complete run passed 183; two timing failures were individually reproduced and then passed without product/test changes. `/tmp/feat584-all-runtime-serial.log`, `/tmp/feat584-runtime-recheck.log`, `/tmp/feat584-cold-recheck.log`. The last cold-recovery check passed in 2.67s. A standalone measurement of the same three-launch recovery sequence completed in 5.115s with all durable outcomes present (`/tmp/feat584-runtime-timing.log`). This is aggregate evidence, not a claim of one all-green full run. |
| New Agent qualification | Before fix: 1 failed / 2 passed; after: 3 passed, `/tmp/feat584-new-agent-red.log`, `/tmp/feat584-new-agent-green.log` |
| Python tooling / architecture | `python -m pytest -m "not e2e" -q`: 54 passed, 31 deselected; `/tmp/feat584-python-tests.log` |
| Ruff | `ruff check .` and `ruff format --check .`: passed (82 files) |
| Web | All 835 existing/new cases covered across initial run and six-file 200-case recheck; CPU contention caused initial timeouts. After final claim fix, task tests 16/16 and editor/group-setting tests 17/17 passed. `tsc` + Vite build passed. Author logs/screenshots under `/tmp/feat584-web-ui/`. |
| iOS | Final native build and 40 tests passed (27 XCTest + 13 Swift Testing), `/tmp/feat584-ios-final-test.log`; native evidence `/tmp/feat584-ios-evidence.md`. A clipboard fixture failed while simultaneous Simulator GUI clipboard operations ran; a clean rerun passed without disabling/changing the test. |
| Migration | Temporary old-schema SQLite fixture: startup guard, mapped dry-run/apply/verify, repeat refusal and backup restore passed; graph/node IDs, structure/result, history and default old-group privacy verified. `/tmp/feat584-migration-check.log`. No production data was inspected or migrated. |

## Real isolated product observations

IM `http://127.0.0.1:58435`, Web Vite `http://127.0.0.1:58436`, dedicated node `wt-nano-feat584-e2e-99833`, own SQLite/workspace/runtime under `/tmp/nano-feat584-e2e`. The fixture starts with seven roots, 15 direct children under the main root and three deeper children; later test-created roots are distinguishable by acceptance titles.

- Web author observed 1440/1024/390 layouts, bordered status groups, overlay detail and direct counts; real create/claim/edit, unassigned child creation, a genuine 409 with retained draft and explicit retry, notice backlinks/mentions, and public visitor browse followed by joining. The live claim request initially missed required `change_note`; a red/green regression accompanied the fix.
- Native author used the actual SwiftUI app on dedicated iPhone 17 / iOS 26.4 simulator `7CB77F12-2282-4AA0-BCC9-D368A4DD1122`: root/15-child/3-child navigation, ancestor/overview returns, sheet details, create/claim/result editing, real 409 draft retention and retry, child creation and task-notice backlink. Host clipboard timing affected one test title, which was normalized via API; this is not claimed as native text-entry success. This is simulator evidence, not physical-device acceptance.
- Real single-thread Agent `e2e` consumed task collaboration messages through PA/DSH. With explicit human task instructions it claimed `tg_be6daf6c/n1`, saved `ACCEPT584_RECEIVED`, and submitted `in_review`; the owning group contains the one result notice. A prior system-only request was denied by ordinary approval rather than treated as fresh human consent.
- Real global Agent `e2e-global` was created through the public management API. In `c_e1205q8j` it consumed the addressed system notice, acknowledged through `send_message`, then used task tools on an explicit human request to save `GLOBAL584_OK` and `in_review` on `tg_a6ff99f4/n1`. The model initially supplied invalid read fields and received validation errors; a correctly scoped follow-up completed the operation. The unmentioned `mention_only` peer did not emit an answer in that group.
- Initial model routes failed at the configured upstream (DeepSeek stream missing stop reason; MiMo invalid API key). Only isolated Agent configuration was switched to an existing `codexOAuth:gpt-5.6-luna` route for successful inference. No production or upstream source/config changes.

Complete R1–R5 UI/Agent journeys, including deletion, assignment transitions, visibility/dissolution and busy/offline/stop behavior, are assigned to independent acceptance. These author checks do not pre-approve them.

## Review repair batch — 2026-10-13

Pre-fix report head `86b0685a1`; integration head `e9edbdc5c907f0b9f51ce483b54b6ce486dbf3a1` merges `origin/main` at `b70d4a7bd80b4424fea430e507390c5dde7c0a05`. Main added skill standards and feat-587 design documents only; no runtime/client/schema change. Prior behavior evidence remains applicable outside the changes below.

- V1: dissolution clears a selection pointing at a newly closed candidate in the same transaction and preserves `selection_reason`. Existing HTTP lifecycle regression now uses a selected exploration candidate and observed the prior invalid selection before the fix.
- V2: ordinary-message delivery state and durable relay creation share the same eligible Agent set. New SQLite messaging regression covers stale registration and suspended owner; both previously returned `pending` with zero relays.
- V3: assignment rejects a human actor reference resolving an Agent user row. SQLite create/add/set-assignee cases preserve the canonical Agent identity and prove rejected mutations do not create notices or advance the graph.
- V4: Web labels the current page/total and each partial column; iOS labels cumulative loaded/total and partial groups. The existing pagination regression now reaches a later-page done task instead of treating an empty partial page as a genuinely empty collection.
- V5: visible public nonmember timelines poll messages at the same interval as their read-access metadata. A real ChatWorkspace query regression receives a later message without a member WebSocket and remains read-only.
- F1: independently reproduced the menu picker toggling Create group. Group settings now occupy their own section with an explicit Public/Private segmented choice. The rebuilt native app selected Private and created `c_cq8p4avt`; the API confirms private/member state. The host Chinese IME transformed the test name, so name-entry behavior is not claimed by this check.
- F2: error and conflict recovery are one prominent section before the editor fields. In the real app, `tg_d99a06d3` was opened at revision 2 with result draft `584123`; another API update advanced to revision 3. Save showed the conflict and Read latest action, retained the draft, displayed the latest server description for comparison, and explicit Retry save persisted the result. CUA `scroll`/`drag` did not actually move the Simulator Form; its exposed accessibility `Scroll Down` action did. Therefore the earlier claim that the old recovery section was absent after reaching the bottom is not independently established. This repair improves recovery visibility and was verified through the full action sequence.

Validation: the three backend regression files passed 7/7 (`/tmp/feat584-review-green.log`) after meaningful failures; all IM tests then passed 35/35 in one serial run (`/tmp/feat584-im-review-tests.log`). Web task/visitor regressions passed 17/17 after red runs, and TypeScript/Vite build passed (`/tmp/feat584-web-review-green.log`, `/tmp/feat584-web-review-build.log`). IM typecheck/build passed. Rebuilt iOS passed all 40 tests (`/tmp/feat584-ios-review-tests.log`). Unchanged PA/DSH, Python and other frontend evidence above is retained.

Live pagination fixture contains 51 roots matching `584999` in dedicated `c_o53hx8s4`; the oldest is done. Web first page shows 20/51 and qualified empty columns, then two Next operations reveal the done task on the 11/51 last page. Screenshots `/tmp/feat584-pagination-web-first.png` and `...-last.png` were visually inspected. Native shows Loaded 50/51 and 50 loaded for To do. In public `c_h1yjg4un`, a nonmember Web page first loaded one message; another member then created `tg_e1588752`. The task notice appeared without navigation or joining, while Join group remained available (`/tmp/feat584-visitor-refreshed.png`). These are author checks; independent closure is still required.

## Final local preparation and remaining acceptance prerequisite

At `0627e1b52`, independent static review and verification pass, and product Round 2 closes F1/F2 plus V1/V5/Web V4. Its only remaining inconclusive item is the native long-list pagination tail (Load more and partial empty groups). The author independently reproduced the automation limitation: CUA drag, wheel, keyboard navigation and raising the dedicated Simulator window did not move the displayed list. No new product defect is claimed, and the acceptance gate remains open.

The iOS Release device archive succeeded (`/tmp/feat584-ios-release.log`, unsigned local IPA `/tmp/feat584-ios-release/NanoIM-unsigned.ipa`). The baseline feat-587 gateway-relay link was corrected in `caf97aff1`; docs-check now passes with 260 maintained Markdown sources and 64 required routes. This one-link documentation repair does not alter reviewed product behavior.

A temporary XCUITest harness was prepared at `/tmp/feat584-pagination-ui/Tests/PaginationProof.swift` and **build-for-testing passed** (`/tmp/feat584-pagination-ui-build.log`). Its product app source is a byte-identical copy of the tracked iOS source; only its temporary test target differs. It would operate the dedicated `Nano feat584` simulator, search the 51-root fixture, scroll to Load more, verify qualified partial empty groups, load the last done task, and confirm 51/51 remains after returning to the top. It has **not run**: the CUA tool's restriction on alternative UI automation requires explicit user instruction before using XCUITest. The choice is pending. No current-spec merge, unit archive, PR, production migration or deployment is claimed while that required acceptance evidence is unresolved.

## Q41 用户真实试用反馈后的修正

用户指出公共群发现入口/弹窗与既有聊天不一致，以及五列数量不同却统一翻页。根因为独立按钮和固定 inset 裸弹层，以及先全局截页再分列。修订设计经过独立 Round 7/8，最后 Approved 0 CRITICAL / 0 WARNING。

实现改为 IM list 可选 statuses（先筛选再limit，状态集合参与cursor绑定与total），Web 五列独立InfiniteQuery与列内自然追加，轮询重读累计页，搜索/负责人重置五列；完整图内直属看板保持纯展示。公开群发现移入既有＋菜单，复用chat-modal/GroupAvatar，搜索、关闭/Escape恢复焦点、内容高度与手机sheet。

预期红测：API真实请求statuses=done返回400 Unknown action or argument fields，SQLite新状态案例1 fail/3 pass；Web短完成首屏缺失和独立Discover按钮案例2 fail/28 pass。修复后SQLite4/4、既有控制与协作15/15、Web相关30/30通过，IM/DSH typecheck与IM/Web build通过。日志：`/tmp/feat584-ux-{api-red,api-green,api-regression,web-red,web-green,web-build}.log`。真实浏览器复验和最终独立门禁在后续追加；本段不宣称产品验收通过。原生累计加载实际操作边界仍保持。

## Q41 冻结版本真实走查 — 2026-10-13

产品冻结 `6c87d7f160caf56cba64052e8180cbff5f02da6a`，集成 main `6275f271d8af552c065ce7cca35dd044f926eb67`。最终全包 build 通过（`/tmp/feat584-ux-final-build.log`）；合并后的 IM + channels/web-relay 11 文件 50/50 通过（`/tmp/feat584-ux-final-im-tests.log`）。

真实 Web 1440×1000 的 51 根任务搜索：待办首批20/总50，完成1立即出现；鼠标在待办列自然滚动追加40→50，再经过轮询保持50，完成列仍为1且位置不变；无全局翻页。已查看 首屏（历史图片 `author-q41-root-first.png`，按用户要求不随 Git 交付） 与 待办末页（历史图片 `author-q41-root-tail.png`，按用户要求不随 Git 交付）。

聊天＋菜单进入公共群发现；桌面弹窗（历史图片 `author-q41-discovery-desktop.png`，按用户要求不随 Git 交付） 有群头像、名称、成员信息，按内容高度显示五行。搜索 FIX584 剩一行，Escape关闭并恢复＋按钮焦点；390×844 的 底部sheet（历史图片 `author-q41-discovery-phone.png`，按用户要求不随 Git 交付） 内容未溢出。打开非成员群仍显示加入按钮、只读提示，输入与发送均禁用，见 手机访客页（历史图片 `author-q41-visitor-phone.png`，按用户要求不随 Git 交付）。过程中Vite曾重连关闭modal，两个等待超时是失去弹窗前置；重新从＋菜单完成完整检查通过。一次检查错误地把disabled composer的存在判失败，读取实际disabled状态后验证通过，未改产品。

iOS原生 V4：用户在专用 Nano feat584 模拟器亲自按住鼠标向上拖，并点击 Load more，回复“好了”。模型随后读取同一运行App的AX与实际截图，观察 Done=1的584999 Page00、完整分组计数、无Load more，见 真实原生末页（历史图片 `author-q41-native-tail.png`，按用户要求不随 Git 交付）。这项是用户手动操作、模型观察结果，不冒称CUA或XCUITest自动操作；XCUITest未执行。独立产品reviewer接管后再独立核实，报告另记。

## Round 3 confirmed-issue repair

Source commit: `f3b8c498d002b74e43b004d8210b732a34dd2a9d`. R3-F1: column InfiniteQuery pages persist while actively observed, with `gcTime: 0` removing inactive filter results; returning to an earlier search/assignee starts from page one. The existing pagination regression now uses a production-like five-minute global cache and searches away/back. Before the fix it failed because View Todo tail remained; after the fix all 31 tests in the three affected Web files passed. R3-F2: next-page failures now explicitly say loading more failed and offer Retry; refresh failures name the column and retained tasks. IM and native source were not changed.

A Mac reboot around 11:10 on 2026-10-13 removed the old processes, temporary runtime data and /tmp logs. Original command results and committed screenshots/reports remain. After reboot the 31 tests and Web TypeScript/Vite build were rerun successfully; local logs are `output/filter-cache-green.log` and `output/filter-cache-build.log`. A new isolated runtime under `output/acceptance-runtime` uses IM51283/Web58436. Recreated fixtures: query584999 has 51 roots (50 todo, one done); query584996 has Test User todo41 including one paused, one doing root, one done child, and Guest todo1. Prior native and PA/DSH journeys are retained only where their source is unchanged; this is a new test environment, not continued old runtime data.


## M1 closeout and final gate retention - 2026-10-13

M1 is deliverable. Product acceptance Round 4 passes all 28 Scenarios through its explicit retained mapping: R1/R3 include independent columns and filter reset; R2/R4 include editing, access, group lifecycle and native repair; R5 retains real PA/DSH notice, busy/offline and stop evidence. Native pagination is user-operated Load more plus independent reviewer observation of 51/51 and Page 00, not XCUITest or physical-device evidence. W1/W2 retain the SQLite/HTTP/WS/runtime checks and real Agent journeys; W3 retains the Web and native build/test/visual checks with fresh affected Web 31/31 and build; W4 retains isolated migration/restore, Python architecture and documentation checks. Earlier aggregate timing failures and the reboot loss of temporary logs remain documented above.

Independent code review Round 3 passes with no findings; verification Round 3 aligns all six corrected deltas. Both static gates and product Round 4 executed at `6052ec92e54f6f7123523f53129a7f5a3fe031b7` against `6275f271d8af552c065ce7cca35dd044f926eb67`. Final fetch still resolves origin/main to that same base. Subsequent `89be6e207` and `8ee4df5d3` only add review evidence. This closeout only merges the 25 verified requirement blocks into six current specs, updates lifecycle/entry links and archives the entire unit; product source remains identical to the validated tree. Gate 2 Round 8, static Round 3 and product Round 4 are retained through the closeout commit. The final PR records its exact effective_through SHA. No new intended behavior or unreviewed delta is introduced.

The existing feat-587 gateway-relay Markdown target repair is retained as the single documentation-integrity fix needed by the repository check; its behavior text is unchanged. No production migration, merge or deployment was performed. Runtime cleanup is owned by the orchestrator after PR checks finish.

Closeout checks: documentation integrity passed (246 maintained Markdown sources, 64 required routes); explicit unit/feat-584 archive check passed; git diff --check passed. The first post-merge docs check identified four stale area counts; package indexes now match the merged Requirements. These were documentation-only corrections.
