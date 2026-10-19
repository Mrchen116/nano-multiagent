# M1 implementation and live evidence

Status: implementation candidate; independent gates and delivery are pending. No production deployment.

## Implemented paths

- Canonical PA identity and owner DM, current owner ACL history without a day limit, source observation with independent cursors, private Work and source exclusions.
- Unified PA on an isolated official DSH host, controlled adapters, independent no-tools semantic review, frozen IM/network/task/Channels effects and real receipts.
- Existing top navigation and chat layout, fixed named PA entry, one-step creation, goals, decisions, drafts, source navigation, visible delegated identity and incident controls.
- Durable native followup, natural-language owner preferences, private task completion, source retirement and existing ordinary Agent routing.

## Reproducible evidence so far

2026-10-19, local isolated worktree (Node 25.8.2, pnpm 11.7.0):

- `pnpm test`: 97 files / 380 tests passed before the final completion/incident fixes; subsequent affected suites are recorded below and the final delivery must run the current full gate.
- `python -m pytest -m 'not e2e' -q`: 62 passed, 31 deselected.
- `scripts/docs-check`: 273 maintained Markdown sources / 64 required routes passed.
- Frontend worker: 97 files / 893 tests passed; later PA/stream targeted tests cover the final UI changes.
- Real DeepSeek via local model proxy, isolated IM and Node: owner created 小航 in the real browser with a first goal; PA retrieved a synthetic 2024 conversation, quoted the agreement and kept the original chat unread.
- Owner granted ongoing coordination in a private message. PA sent the time question into the existing two-human DM, with server-generated PA delegation identity. Receiver DTO contains that identity; DM membership remains the two humans.
- Private synthetic medical canary was present in the owner's request and PA context, absent from messages delivered to the peer. This is sample evidence, not a zero-leak guarantee.
- PA scheduled an actual native followup; after the synthetic peer replied, it observed the reply without forwarding or @mention, confirmed the agreed time and notified the owner.
- Explicit probing/impersonation fixture was refused and an incident was recorded. The initial fixed peer notice was incorrectly denied by the reviewer; the policy and final live rerun must verify this correction.

## Failures found and corrected in live testing

- Host PA RPC replies were not correlated by Channels, causing timeouts. Regression reproduced the failure on real WebSockets; corrected response matching passes.
- DeepSeek supports high/max but the reviewer forced low. Reviewer effort now follows declared capabilities; output budget includes its reasoning requirements.
- Scope reviewer failure must retry before admission, not ask the owner to approve an already authorized message.
- Completed-only WebSocket events did not create new message bubbles. Real-message creation now publishes after commit, including final delegation metadata.
- Completion must update the original private task and cancel its followup, not merely leave an assistance row saying completed beside an unfinished task.

## Explicit remaining verification / boundaries

Final independent product acceptance, code review, verification, full final CI, canonical-spec merge and archive remain pending. The worktree and isolated runtime contain only test identities and synthetic messages.

The current adapters reject Channels groups without a verified audience, external binary attachments without a semantic content adapter, and uncontrolled executable tools/plugins in PA; ordinary Agents retain their original capabilities. Same-owner node relocation/credential-epoch recovery, rename runtime synchronization, all revocation event sources, and per-PA availability require specific final verification against the design rather than assuming a passing unit suite proves them.

Raw logs, fixture credentials, screenshots and recordings stay outside tracked documentation. Final evidence will link only shareable artifacts and exact tested versions.

## Independent review corrections

Review of `cf1befff9` independently reproduced source-policy bypass through direct relays, broken device epoch recovery, and PA recovery preventing ordinary global work. The next candidate corrects all three:

- Every personal input now revalidates current IM source/contact authority before review or storage, including queued direct relays. Channels inputs first obtain a persisted IM source and use that identity for checks.
- Same-device credential recovery rotates the trusted PA marker and retires old permits; local partition data moves to the new epoch before startup. An explicit same-owner restore operation prepares the same PA on another computer, preserves canonical DM/goals, and fences the old node before committing the new runtime receipt. It does not copy local private history.
- Recovery failures are isolated per Agent. PA host availability is reported separately from node health. Retiring a context recreates still-authorized goal timers; completed/paused/inaccessible goals do not regain timers.

The corrected live privacy probe produced both an actual private owner notice and a PA-labelled fixed peer refusal, with no canary disclosure. The private goal completion now updates its real task to done and cancels its native followup. A separate real public search completed without an additional owner approval. Final acceptance remains pending; these observations are not a claim of exhaustive leakage prevention.

## Subsequent integration and user-journey checks

- `439a75144` separates multiple accepted goals, reuses the cached independent scope interpretation after partial failures, and assigns the original private tasks. The UI keeps the existing shell, moves the goal index into the chat header, and collapses informational privacy notices.
- Independent R2 static probes verified actual Channels ingress through HTTP handlers and current contact blocking on both new preparations and already-reviewed delivery. Incoming provider mirroring has its own authenticated private ingestion route and cannot publish outward messages.
- Real R2 product testing exposed a source-retirement recovery gap: the new PA execution session could not replace the old Work main, so new owner requests stayed pending before Inbox admission. `f8edd7971` permits the current active PA node to retire the old Work main while retaining its private history; ordinary Agent main-session rules stay unchanged. The stored owner request resumed after restart and yielded two independent tasks.
- The frontend now models the actual `pending` delivery status, preserves deep-link reading position, and keeps the mobile header compact. Independent R3 product checks are recorded in acceptance.md, including actual source navigation and pending-request feedback.
- The full `439a75144` suite passed 391 of 392 backend tests; the unchanged workspace-tools integration test timed out under simultaneous full-suite load, then passed alone in 34.85 seconds. The frontend full suite passed 897 tests across 97 files. Later narrow recovery/UI suites and build/typecheck results apply to their specific candidates; they do not erase the original failed run.
- Fixed-notice retry now refreshes only conclusively unsent review evidence. A further independent concurrent-disclosure probe required binding the review result to the exact evidence digest as well as the frozen payload, so a late pre-refresh review cannot approve refreshed evidence.

The user's test service remains available at its isolated local URL while they inspect it. All headed test Chrome instances were closed when requested; subsequent independent checks use headless browsers and close their sessions on completion.

## R3 product and corrected-delta follow-up

- The R3 choice receipt was persisted, but its system notification explicitly said it was not authority; the main model then demanded another chat confirmation. Owner choice notifications now identify the authenticated UI receipt and require reading its recorded option before continuing within existing goal constraints. Both main and independent reviewer policies recognize this evidence, while assistant-authored options alone remain insufficient authority.
- A thank-you-only draft included an unrelated reservation commitment. The draft policy now explicitly preserves the requested content boundary even when a separate goal authorizes that commitment. This prompt correction still requires another real-model product sample.
- Two owner messages stayed pending before Inbox admission because their cached control interpretation referenced a stale assistance revision. Already-applied pause/resume controls are idempotent; a real revision conflict discards the stale interpretation and re-resolves the same authenticated message against current state once. It does not replace the revision check with an unchecked write. A regression verifies that stale interpretation cannot permanently block the rest of the owner's message.
- Independent corrected-delta review found task reads using PA membership rather than owner access. Gateway now authenticates the current binding and reads through owner access plus the current source policy. Excluded graphs are removed before summaries/counts/cursors, linked provenance uses the same policy, and the read projection grants no task write capability. Shared writes still use reviewed delivery.
- The targeted backend suite passed 68 tests across personal IM, PA coordination, and global recovery. Full build/typecheck and independent targeted rechecks follow; prior accepted UI layout/history evidence remains valid because these corrections do not change frontend code.

## R4 product follow-up

- The ordinary Nano permission classifier rejected the explicitly authorized new Saturday inquiry because its transcript did not contain the PA's persisted current scope. The same missing projection affected owner UI choices. It now fetches current authorization through a host-only product call before review. CC/Nano, DSH and Codex strategies receive the server record as evidence under their unchanged permission rules; no allow fast path was added. The independent PA disclosure check remains required at delivery. A real DSH dispatch test supplies a server choice, observes the ordinary reviewer allowing the matching action, and confirms a separate denied action is not sent.
- A normal peer quote remained queued after the independent input reviewer timed out. The persistent event was intact, but recovery required another event or reconnect. Existing node heartbeats now wake pending observations, so transient review failures recover without another user message. Processed events do not wake again; observation pause still suppresses automatic message processing.
- Full backend validation on `19458a27e` passed **97 files / 397 tests** with two workers; Python passed **62 tests / 31 deselected**, and ruff passed with **83 files unchanged**. The later ordinary-review projection and heartbeat retry receive targeted native/runtime/IM tests and independent rechecks rather than repeating unrelated full suites.

## Current acceptance configuration

- On 2026-10-19 at 15:38 Asia/Shanghai, the user specified **GPT-6.1 Sol for the main PA and GPT-6 Luna for review**. The isolated test node now sets `codexOAuth:gpt-6.1-sol` as its default/main PA model and `llm.tool_approval_model: codexOAuth:gpt-6-luna`. The latter feeds both ordinary tool permission review and independent PA semantic review through the existing `approval.reviewer` configuration. This is local acceptance configuration, not a production deployment or a committed credential/config file.
- Before that correction, DeepSeek V4 Flash independent review calls returned HTTP 402 `Insufficient Balance`. Pending events were retained and heartbeat retries reached the reviewer; waiting in that period does not establish a heartbeat implementation failure. After the model configuration and node restart, pending quote event 35 became processed and proxy request logs recorded the main session using GPT-6.1 Sol. Full choice-to-delivery acceptance remains separate from these configuration/recovery facts.
- Main sync included `cc47abe3f` (feat-617 design documents only) at merge `073a9784a`; no implementation changed, so the running `ed73cb9b8` build and R7 targeted static evidence remain applicable. Documentation integrity passed with **285 maintained Markdown sources / 64 required routes** using the repository Python environment. The fresh onboarding stack was stopped after its UI evidence was captured; the user's port 53808 stack remains available.

- The spec authorization history and W7 validation model now reflect the user's explicit Sol/Luna correction. This changes the acceptance model parameter only; permission semantics, independent review architecture, UI and required scenarios are unchanged, so the prior design approval is retained for those contracts. Live ordinary approval audit now records `codexOAuth:gpt-6-luna`, alongside main-session proxy requests for `codexOAuth:gpt-6.1-sol`.

## R8 observed failure corrections

- R5 UI saw PA naming time out during a long execution, then diverge between profile and fixed chat entry. Metadata-only configuration now avoids waiting for execution idle; configuration commit/recovery atomically updates the PA binding and canonical chat name. All configuration entry points refresh those projections. The existing Agents page already allowed owner model/instruction/capability editing; this round labels the PA role clearly and links its chat settings to that full configuration page.
- R5 mixed group creation failed because the PA's private asset space was selected for a peer collaboration group. Explicit mixed groups use the shared conversation space while retaining private visibility and all participant/PA asset ACL checks.
- Actual turn 29 on main session b92e1c24-3e06-48b0-b217-22c65daade18 received the generic Inbox wake but interpreted observation pause as a reason to ignore the owner's direct question. PA wake instructions now distinguish direct requests and on-demand lookup from ambient observation. Cleanup keeps queued direct-owner requests; Inbox sequence assignment remains above persisted wake watermarks after source deletion. The latter regression reproduced red before correction.
- Static S1 late knowledge notification could ACK a same-ID fact in a replacement runtime. Knowledge/workflow reconciliation now captures a generation-bound runtime port; a stale completion fails instead of acting on a new host. Actual partition integration test protects this race.
- Validation: backend build and typecheck passed; affected backend suites total 91 tests passed (77 IM/PA/Inbox + 14 runtime/knowledge/workflow); frontend typecheck/build passed. UI targeted validation and independent rechecks follow. Logs in /tmp/feat616-r8-*; real services had not yet been restarted at this entry.

### R8 full-suite regression and correction

- Full frontend on 9cebd17b7: 97 files / 898 tests passed (`/tmp/feat616-r8-all-frontend.log`). Backend full run: 402/403 passed; the existing historical-fork regression caught revision-only apply skipping a fork that intentionally retained older tool/prompt settings (`/tmp/feat616-r8-all-backend.log`).
- Revision-only apply now checks every template/live configuration, not just the node's current template. A historical fork with different execution choices still follows the existing full apply path; genuinely unchanged execution revisions remain nonblocking. The unchanged history and busy capability suites then passed all 4 tests (`/tmp/feat616-r8-history-regression.log`). This correction does not alter PA privacy or owner UI contracts.

## R9 — 复用 Global 与 feat-617（2026-10-19）

- 基线：最新 `origin/unit/feat-617` `87f5214a7`，集成于 `b50704bdd`；R9 Gate 2 为 Round 18 Approved。
- 移除 PA scopes/assistance/decisions/cleanup/观察暂停、受限工具/个人文件/搜索替代、逐工具附加审核、退休上下文和专属定时恢复。正常 task_graph 数据保留，旧本地表不再读取。
- 普通 Global 的工具目录、插件/Skills、配置、内存与执行机制复用。PA 私人消息走普通 agent.message，私人任务走普通 task_graph.command；具体外发才冻结 payload/独立审查/实际提交。普通自动审批不再重复审 PA send_message，显式执行限制仍生效。
- 两种身份的历史查询合入 conversations；主人双向消息与实际角色进入 Inbox。personal_sources 由主 PA 直接调用，服务端校验原主人消息、revision 和访问权；撤销待摄入来源，不销毁已有上下文或提醒。
- 草稿正文唯一保存在 feat-617 interaction_drafts；reply_draft 仅定位原聊天和字段。采用前保存编辑，已有输入明确替换，采用不提交或发消息。保留既有导航与 PA 代发标记。
- 修正 PA→Agent 私聊投递缺少持久 relay_tasks 的链路；真实接收节点与幂等回归通过。
- 测试处置：删除退休机制专属断言；保留绑定/epoch/ACL/真实回执/incident 保护，改写为双身份与双向消息、当前来源、普通能力一致和617真实提交/草稿保护。新增5项PA行为先红后绿；首轮runtime/IM/Web窄测分别通过。
- 整合前验证：PA/Global/617/Node 4文件61 tests；最终PA 12 tests；runtime权限/能力11 tests；IM 8文件73 tests；Web 100文件922 tests、typecheck和build；Python非E2E 62 passed/31 deselected；ruff check/format通过。Web草稿完整往返用例将总预算5秒改15秒，冷加载仍有独立条件等待，整套重新通过。
- 本段不宣告真实模型、产品验收或最终CI通过；运行与独立审查证据随后补充。

### R9 integrated verification and fixes

- Candidate `649881496`: backend build/typecheck passed; Web full suite 922 passed. Backend default concurrency produced 427 passed/7 timeouts, then the seven files passed 19 tests with two workers (47.57s); one full `vitest run --maxWorkers=2` passed all 434 tests in 102 files (212.03s). Logs: `/tmp/feat616-r9-backend-tests.log`, `backend-recheck.log`, `backend-limited.log` under the same prefix. No backend test timeout was increased. npm audit found no critical vulnerabilities (5 low).
- Latest feat-617 `e61588616` merged as `d370ab6b7`; `git diff 87f5214a7 e61588616 -- apps packages src scripts tests` and `git diff 649881496 d370ab6b7 -- apps packages src scripts tests` were empty. The remote has equivalent implementation history plus documentation/evidence changes; integration retained the exact R9 product tree. origin/main remains `cc47abe3f`. Existing runtime and tests remain applicable.
- The isolated 53808 service was restarted from the candidate; its PA fixture was updated through ordinary config API to Global default tools plus fixed tools/personal_sources, Skill creation and IntelligentUI. Main model remains 6.1 Sol and reviewer 6 Luna. The two obsolete PA follow-up fixture schedules were explicitly deleted through the normal cron API, without touching other work.
- Independent review reproduced native child public delivery failing on `Unknown personal evidence binding`. The correction verifies the native ancestor chain to the trusted product root and collects child plus ancestor execution evidence. A real DSH child integration test reproduced the failure against the old build, then passed for public delivery and shared task creation, retaining rejection of unknown identities/sessions.
- Real product testing rejected a reply draft whose metadata used the TextArea input name instead of its `$draft` state key. The tool schema and PA guidance now specify the state key including `$`; IM returns actionable validation detail and Channels preserves that rejection instead of hiding it. The shared interactive Skill also corrects its contradictory Form argument instruction (buttons are second). These changes do not authorize sending drafts or weaken validation.
- Earlier prototype PNGs are retained locally under `data/acceptance/feat-616/legacy-prototype/`, with SHA-256 in the historical evidence README. The old security matrix is explicitly superseded by R9. Product acceptance and independent closure remain pending at this entry.
