# feat-546 M1 implementation

## Scope and authorization

- Started 2026-09-09 from `origin/main=e9a097277ab1fe9696fb8be389c150289f03c200` in `.worktrees/unit-feat-546`, branch `codex/feat-546` (desktop branch naming convention).
- Full design Gate 2 passed Round 3, 0 CRITICAL / 0 WARNING. The user explicitly selected `change-orchestrator-simple` and instructed: “干完自测就可以了，一定要自测多种实际场景使用，看agent是否能实际理解你的prompt，工具，能不能实际场景正常work。不需要Code Review那些检查Subagent操作。”
- Accordingly, independent code/product/verifier checking gates, including corrected-delta verifier delegation, are waived for this run. Implementation, self-testing, actual model/product journeys, canonical alignment, archive and PR/CI remain required. No skipped gate is reported as executed or passed.
- One vertical M1; implementation ownership within it: Kernel SDK/events; IM backend/frontend; Inbox storage/new tools; root owns PA configuration/prompt/runtime integration and final real-stack scenarios. Implementation workers do not run review gates. Main checkout's unrelated modifications stay untouched.

## Baseline

- `PYTHONPATH=src .venv/bin/python -m pytest tests/contract tests/unit/agent/runs/test_kernel_executor.py tests/unit/agent/test_kernel_create_subagent.py tests/unit/personal_assistant/test_inbound_pipeline_session.py tests/unit/personal_assistant/test_gateway_session_binder.py tests/unit/personal_assistant/test_internal_dispatch_endpoint.py tests/unit/personal_assistant/test_heartbeat_session_binding.py tests/unit/personal_assistant/test_cron_runner_awareness.py tests/unit/platform/hooks/test_realtime_stream_events.py -q`: **236 passed**, 15.02s.
- Frontend `npm ci --no-audit --no-fund` then `npm test -- --run`: **71 files / 689 tests passed**, 23.88s. Existing act/localstorage test warnings, no failing test.
- Worktree reuses main `.venv` dependencies only; all Python execution sets `PYTHONPATH=src` to this worktree.

## Test strategy

- Preserve existing single_thread behavior and public SDK/PA/IM boundaries through their current owner tests. Add tests only where the new mode, persistent receipt/wake/observer or work projection creates a distinct observable failure reason.
- Real loop tests protect durable content/fallback consumption; Inbox tests protect bounded parts and persistent effective signal; IM tests protect authenticated projection and message membership. Browser and model E2E protect wiring, routing, actual prompt/tool understanding and user interaction that those tests cannot establish.
- Final self-test matrix: J1–J9 in design.md, including multi-chat supplement to the same delegated child, independent concurrent work, simple direct answer, target revalidation, background/Bash/Cron sources, control commands, restart/history/permissions, native and dedicated Feishu routes.
- Record actual model/session/turn/call/source/destination identities, input and result claims, and limitations. Never count an API schema/unit/mock/prototype check as a real-model journey.

## Progress

Implementation and native/Feishu real-stack self-tests are complete. User explicitly requested retaining the running demo and its worktree for inspection. Final PR and remote CI are tracked live in GitHub.

### Implemented seams and focused evidence

- Kernel worker delivered idle admission/receipts/ordered observation, exact serialized durable tool proof, real child Session/Turn events, Bash return sidecar and post-settlement `session_idle`. Combined boundary suite: **320 passed**, with final narrow SDK tests rechecked. Same-ID terminal admission may be retried only when no input was durably committed; this is the necessary clarification to the original idempotency wording.
- Added `reconfigure_session(only_if_idle=True)` to reject changed-runtime lifecycle admission while busy; unchanged runtime remains a no-op. This prevents a busy global heartbeat from waiting behind a configuration update and then executing late.
- IM worker delivered mode/config/work APIs and UI, authenticated journal/query/permission path and real tool/child/chat linking. IM suites **413 passed**; frontend initial full run **694 passed**, then final affected **81 passed** including one added background-return case; production build passed.
- Inbox worker delivered durable pages/proofs/opaque cursors and two query tools: **22 focused tests passed**. Scheduler follow-up delivered main-session heartbeat, isolated cron/work-only process display and global canonical awareness: **100 focused tests passed**.
- Configuration follow-up delivered immutable mode/global workspace, omitted-field preservation and aligned IM/PA operation fingerprints: **135 tests passed**.
- Root implemented PA composition, persistent global binding, coalesced wake/control coordinator, source-target send guard and ACK work facts, one work recorder/relay, loopback query routes and existing WS queue integration. Root regression of dispatch/listener/runtime/inbound/binder: **52 passed**.
- Root actual SDK-loop + HTTP-tool integration (scripted provider, not live-model evidence): initial **3 passed**, proving full Inbox content durable proof precedes consumption/send, target new input holds an old draft and requires a new read, and stop/new preserve inbox/main identity. Recheck with scheduler cases: **9 passed**. Restart receipt/no-repeat coverage added next.
- At this implementation checkpoint, live-model/browser/Feishu tests had not yet run; subsequent actual-entry evidence is below. No independent review gate was run or represented as passed.

### 2026-09-09 actual native model and UI evidence

- J2 live-proxy critical path: `1 passed in 61.47s` using `deepseek:deepseek-v4-flash`; same child follow-up, amended CSV calculation, real Inbox commit and dispatch ACK asserted. Initial startup failed because shell Python lacked PyYAML; corrected PATH to the repository venv.
- Repeated J2 on the manual isolated stack for browser inspection: Agent `e2eGlobald90ff842`, main `sess_7f292d978bc14d2d`, child `sess_b23fb17fd990cc6c`, child Agent `ac32799d2244a030b`. A `651123e6a48e4e398ee723d11106c2c7`, original message `f865e415e87e4eaf948f482686c5be75`; final JSON `AMENDD90FF842 / total 63420 / count 60` only appears in A. Internal assistant text remains in work view.
- Browser self-test found and reproduced an IM projection bug: link-event envelope parent `session_id` overrode the registered child row when materializing API data. Added a red test with the actual SDK envelope shape, then made authoritative stored identity win. Original-data IM restart restores the correct historical child without rewriting events. Gateway original-data restart also verified a new online node generation.
- Desktop and 390x844 mobile: actual child read/Bash/write details, token counts, Inbox body and source message link inspected. Fixed grid intrinsic-width overflow; mobile document width remains 390. Source jump reports the original message located; return retains expanded Inbox read.
- Additional real model Agent `globalLivea6e9f1`, main `sess_f136a82f5db729f0`: write/read/edit/Bash produced `alpha=11` (dispatch `6d56662267654ab6b2254f1d0b0ee99d`), conversations history recalled 7 and 11, `/new` rejected and `/compact` preserved main identity. Initial fixture omitted tool_allowlist (explicit empty means fixed tools only); corrected the test Agent configuration before these successful assertions.
- Heartbeat actually delivered `HB_a6e9f1`, message `09319d57a86e43a2a48af53e524b7bb4`. Initial fixture used an obsolete root HEARTBEAT.md location; moved task to canonical `.nanoassistant/HEARTBEAT.md`, then verified delivery and disabled the test cadence.
- First full local regression: frontend 73 files / 695 tests passed. Python shards found 16 + 6 failures: missing EventHub fixtures, no-publisher standalone engine, duplicate raw/final tool events, and expected metadata additions. These are tracked through root self-test and implementation fixes; no independent review/verifier gate was run or claimed.


### Actual controls, permissions and scheduled delivery

- Full local Python regression after the first fixes: agent/PA shard **1833 passed** and remaining shard **1828 passed**; frontend **695 passed**, production build and critical dependency audit passed. Ruff check and format check passed. These precede the final approval-context and cron UI fixes; final checks are recorded separately below.
- True multi-agent group race: Agent `globalRacea863a8`, main `sess_9521d6bd7eb42fca`, chat `305eb1accbe0463faff458106ebf2d10`. The model's OLD draft was held after NEW was durably ingested, then the model reread Inbox and delivered only NEW, message `0cb028c6412245d8ad515b9964fa9606`. An initial two-member fixture was correctly classified as direct and therefore did not exercise the group guard; corrected to two Agents plus user before this assertion.
- Heartbeat has actual origin `heartbeat` on main `sess_f136a82f5db729f0`, turn `turn_b7711478bd0e529e`; its main Session did not change. Non-owner work requests and forged Session requests returned HTTP 404.
- Ordinary Agent children retain existing unattended permission-deny semantics. Interactive Workflow children use their existing permission broker: deny Session `sess_7fe0ee5afc0ee919` did not create its test file; allow Session `sess_a8d0a9724e8a0307` wrote the exact marker. Source transport `session_id` initially attached the Workflow permission to its parent; the actual `execution_session_id` now owns both pending and resolved work facts.
- Real browser permission action: Workflow `wf_b361c4f0f83f03d9`, child `sess_8a976ab3f9b9ec63`, request `a40ee6ac-a01b-4e6d-bca0-ba0dfa01b07e`. Expanded the child, clicked **Allow once**, saw HTTP 200 on the permission endpoint, and independently read exact file content `WFUI3_allow_a6e9f1`. Earlier browser fixture timed out while inspection was paused; retried with a new request and marker, never treated the timed-out request as success.
- Desktop CUA became unavailable because the Mac locked. Continued in an isolated Playwright Chromium session against the same real services; permission UI has no console errors or warnings, and the successful permission POST and work GETs were observed. This completed the interaction without requiring a desktop unlock.
- Real cross-chat `/stop`: main `sess_0a07ad599cb12ada` was cancelled from another group, remained idle across an observation interval, and resumed only for fresh input while retaining main identity. A first fixture tried to hold a Bash row, but the model chose background Bash; the successful test instead anchors actual new main-run identity before stopping it.
- Real cron uncovered two actual integration omissions: global mode rejected all legacy turn starts including declared cron final delivery; auto approval saw only the synthetic Inbox wake rather than actual user requests carried by Inbox. Kept the global-main filter and added the cron final-delivery marker. Added an opt-in tool-result approval projection only on the new Inbox tool; the classifier retains original rules, ignores errors/non-opt-in results and receives source-authored user text without Agent replies or image bytes.
- After those fixes, Agent `globalCron4de484`, main `sess_eb44445e2cb5e18a`, actually created and ran jobs with manual and scheduled triggers. Child Sessions `sess_156adb2b8c5eb5ea` (manual), `sess_45a8b81a609487fa` (scheduled) and `sess_8adb133a82efd1af` (scheduled) remain separate from main. Actual output messages: manual `64cb35d4698e45a6af2fa1b668caedca`, scheduled `b22d5f4e8ba74088994545c1aefe0780`. The model then removed both temporary jobs. Each confirmed work delivery records the actual final ACK, target, message and text.
- UI created `global-ui-546`: mode remains immutable; fixed tools are selected/disabled in the UI while configurable default read/write/edit/Bash tools remain present. Actual Inbox + Bash + explicit send produced `UI_GLOBAL_546`, message `a9d81fcffa0446139985b7606634c623`. The fixed tools are composed into the effective runtime rather than duplicated in the editable stored allowlist.


### Final local checks and remaining external prerequisite

- Final Python CI-equivalent shards: **1835 passed** (agent/PA) and **1840 passed** (remaining); frontend **73 files / 699 tests passed**; production build passed. Critical dependency audit passed (zero critical vulnerabilities). Ruff check and format check passed after formatting the two final hook/prompt files. Latest live J2 rerun after Inbox approval projection: **1 passed in 51.47s**.
- Single-thread UI-created Agent `single-ui-546` retained the existing direct reply and `/new` behavior, with actual model replies before and after the new Session.
- Actual browser inspected held OLD draft plus the new-message source link, manual/scheduled Cron labels, final `CRON_MANUAL_4de484` work delivery and link to actual message `64cb35d4698e45a6af2fa1b668caedca`. After stopping the isolated Gateway, work view displayed “节点离线，正在显示已保存记录” and retained the main/child history. The subsequent standalone API offline assertion was attempted after the owning stack exited, so connection refusal is not counted as API evidence. Browser connection errors after deliberate service shutdown are expected teardown evidence.
- Refreshed `origin/main` equals the original base; there are no upstream changes to reconcile. Canonical area additions and corresponding ten delta areas were aligned with actual implementation. Independent checking subagents remain explicitly waived by the user.
- J9 prerequisite failure: started a fresh isolated `--feishu` runtime in `/tmp/feat546-feishu-runtime`, created `globalFeishu546` in global mode, and changed only its generated copy's dedicated channel binding. The test Bot/App verification and actual Gateway listener startup succeeded. Sending as the dedicated test user failed before delivery with lark-cli exit 3, `authentication/token_missing`; status reports the user identity `missing`. Bot verification alone had not proved a usable user token. **No actual Feishu input/reply is claimed.** Resume with user authorization, then the same dedicated Bot-only Inbox/read/dispatch/platform-reply assertions.
- Pending final delivery: complete J9, archive the unit, create a non-draft PR and wait for remote CI. Preserve this unit worktree while paused; shut down all owned runtime processes.

- After staging all task code/docs, documentation integrity passed (**236 maintained Markdown sources / 72 routes**), all **156 contract tests passed**, Ruff and staged diff checks passed. Only the two canonical additions initially appeared missing to the tracked-file documentation checker; staging them resolved those diagnostics.
- Both isolated stacks, the owned Vite server and the isolated Playwright browser have been stopped. Process inspection found no remaining unit-owned runtime. The active unit and worktree are retained solely for the pending Feishu authorization and final PR delivery.


### Authorized Feishu completion and retained cross-chat demonstration

- The user completed the dedicated test identity authorization. Its real Feishu message reached global Agent `globalFeishu546`, main `sess_262eecbb881aba8e`, and the model correctly called Inbox/read/send_message. The first platform assertion then exposed a real omission: `agent.message` had confirmed the IM shadow bubble but never invoked the external Channel sender. No platform receipt was inferred from that ACK.
- Added a reproducing SDK-loop integration test for provider success and failure: both cases first failed because no external delivery was attempted. Global dispatch now passes the saved ReplyContext to the existing OutboundRouter, uses the stable dispatch identity for its existing dedupe, and records `dispatch_confirmed` only after external send succeeds. The focused dispatch/runtime suite passed **17 tests**; final Python CI-equivalent shards passed **1835 + 1842 = 3677 tests**.
- Real Feishu rerun passed: source `om_x100b6523846748a0debf099ac1aa2dc`, send call `call_00_ET_rgDgBXkXoOo2VklIjHti0747`, IM shadow reply `4e81f3a064c541d1ab7b73bb699efa35`, actual Feishu Bot reply `om_x100b652385de38a4c33f6fed0ee88f3`, exact body `FEISHU546_d0b980=42`. The platform query returned one matching user request and one matching Bot final; internal reasoning did not appear there. The source target was direct/external and gained no group-revalidation gate.
- Repeated actual J2 on that retained stack after the external fix: Agent `e2eGlobala3052729`, main `sess_73623c2b60394dd1`, original child Agent `ad8979b1fddb04948` / Session `sess_840d29e37b897138`. A `fe502d4d9f92467cac7f2899b2a3a80a` launched the task; B `5b3a94fea7154fa68b2785cf34a9d6b2` amended it; the exact same child received the change. Final `AMENDA3052729 / total 63420 / count 60` was delivered only to A as message `6e544bae913140c08fecdcfe8da35eeb`. The actual A chat and Agent work view were opened in the app.
- Native inspection of that final work view found repeated copies of the same background return because its source sidecar accompanies multiple assistant messages. Added a failing UI reproduction, then deduplicated by real task type/id within each turn while preserving distinct task returns. The panel suite passed **8 tests** and production build passed; final frontend regression follows below.
- Retention authorization: user explicitly said “跑完不要关服务。我要看一下改好后，跨thread工作的具体的效果。” Therefore keep IM/Gateway at `http://127.0.0.1:59669`, runtime `/tmp/feat546-feishu-authorized`, and this implementation worktree. These are the task's isolated processes/config/workspaces; production was not changed. Clean them when the user finishes inspection or explicitly requests shutdown. Do not apply the normal post-CI removal while this instruction remains in effect.

- Final frontend regression after deduplicating background source display: **73 files / 700 tests passed**. Production build, Ruff, format, documentation and staged diff checks passed. No remaining implementation or actual-entry verification blocker.

### 2026-09-10 prototype conformance correction

- User review invalidated the previous visual-acceptance claim: the initial work view reused chat tool rows, constrained the canvas to 880px, exposed lifecycle JSON, and had overflow and undersized controls. Functional/model evidence above remains separate from visual acceptance.
- Restored the prototype hierarchy: responsive canvas up to 1440px, bordered tool cards with status and business outcome, structured Agent prompt/result, distinct assistant text, main/child columns, and inline context/output/cache statistics. Mobile child navigation replaces the main trace and retains its scroll position. Kept existing presenter payloads and permission endpoint.
- Resolved conversation names through the existing authenticated conversation list; inbox/send targets retain their exact Chat locator. Participant names and local timestamps replace display-only IDs/raw timestamps. Agent-authored text stays verbatim. Internal config/run status stays in the journal; missing-record warnings and actual injected-input receipts remain visible.
- Localized work labels and conversation detail labels through the existing language resources. Established readable sizes: 14px body/tool names, 12px metadata, 14px expansion indicator; desktop close target 36px and mobile 44px. Long paths, prompts and output wrap within both columns.
- Live retained runtime at 127.0.0.1:59669: checked real main/child expansion, named J2 A/B targets, desktop card layout, English/Chinese switch, and mobile child/back behavior. Browser measurements found no overflowing work-view descendants; visible expanded tool bodies had scrollWidth equal to clientWidth. Close target measured 36px and expansion indicator 14px. No new model execution is claimed for this presentation-only correction.
- Frontend regression: 74 files / 705 tests passed; production build passed. Added coverage for named inbox/send targets preserving hrefs, hidden lifecycle noise, language changes preserving original text, empty/error/retry, denied/in-band failure states, and unknown/cumulative usage. Existing tests retain main/child linking, real Chat route restoration, cron delivery, workflow scope, and offline permission protection.

### 2026-09-10 — 聚餐演示审查问题修复

用户要求直接修复审查发现及截图中的 mention 原始标记。主会话完成修复；未继续派发实施或验收子 Agent。

- Inbox 来源分页冻结来源顺序，消费前页不会跳过仍待读来源；在线历史查询将已物化的本地别名解析为原生会话 ID。
- IM 历史分页把完整 ID 快照留在持久存储，返回有界游标，逐页继续校验查询归属与当前访问权限。10,000 条消息下游标小于 256 字符，新增消息不会进入已冻结快照。
- IM 恢复后的 unknown 轮次允许未决审批送至在线 Gateway，由其真实 pending broker 决定是否仍可处理；离线仍禁用，终结请求仍拒绝。
- 工作轮次后续页进入查询缓存与实时刷新，跨 Chat 返回保留已加载内容和展开状态；新增分页入口随轮次增长更新。
- 工作视图恢复发送错误详情、后台 error 与 stopped/killed 终态；新增模式说明及固定工具文案接入中英文。
- Inbox 正文复用 mention 解析器及人员名称，截图中的标记实际显示为「@小策 · 聚餐统筹」；发送目标为已知 Agent 时显示其名称。

验证：前端 74 文件 / 709 测试通过；后端相关测试及架构契约 182 通过，最终分页补充后相关 12 测试通过；前端生产构建、Ruff 与文档完整性检查通过。实际浏览器复查原聚餐消息及 mention 展示。测试服务加载新代码后，原两群、300→400 元消息、两个主 Session 均保留，节点在线。未声称将每项后端失败场景重跑为真实模型旅程。

### 2026-09-10 — Inbox 提醒语义与查询权限开销

- Inbox 唤醒改用已有 `<system-reminder>`，明确表达新消息已到、通知不含正文、先查看待读聊天再选择读取并决定处理。内部 submission ID 仅用于去重／回执，不作为模型可见的批次解释。
- Inbox 与 conversations 使用工具既有 `check_permissions` 放行合法查询；参数验证、Gateway Session 身份和来源访问检查保持。后续其他操作所需的用户请求审批上下文投影保持。
- 49 项工具／权限钩子／真实 SDK 循环测试通过。保留的聚餐现场追加简短请求「人数和预算不变，请在策划群补充提醒：周五晚上聚餐。」；真实 DeepSeek 调用了 inbox、inbox、send_message，在策划群回复「补充提醒：本次聚餐时间为周五晚上，人数8人、预算400元不变。」。代理原始请求确认 system reminder 到达模型，此次新增权限分类请求为 0，主 Session 保持不变，服务继续保留。

### 2026-09-10 — 仅暂扣正文向模型提醒

按用户侧聊转达要求，正常放行正文仅保留内部 `output_status` 审计元数据，不再向模型追加成功状态 system reminder。暂扣仍提供 NOT SENT 及明确的当前正文范围；历史模型上下文和 compaction 共用的组装入口过滤旧成功提醒，原持久记录不改写。

48 项 output revalidation、prompting、loop、compaction 与全局 SDK 测试通过，包括先前同文已发送、后来同文暂扣、重载后仅排除暂扣正文且保留两次独立审计状态。真实聚餐主 Session 再次读取跟进并发布「提醒大家周五晚上准时到场，人数8人、预算400元不变。」；新增模型请求不包含 COMMITTED FOR DELIVERY，Inbox 两次调用无权限分类请求。原 IM、群聊和服务继续保留。

### 2026-09-10 — mention 展示归一补漏

- 用户截图确认会话列表摘要直接泄露 mention wire 标签。正文原有解析已存在，但列表与通知没有复用；通知还提前截断 wire 文本。
- 正文、工具卡片、列表摘要、应用内通知与桌面通知共用 mention-parser 的名字解析和 unknown 回退；列表搜索基于显示名。通知仅在展示层完成名字转换后截断，保留缓存中的原始消息。
- 验证：前端全量 74 文件 / 713 测试通过，生产构建通过。新增 Agent/user mention、列表两种模式、名字搜索、缺失成员、长标签跨截断位置、toast 与桌面通知覆盖。
- 实际保留环境 :59669 重新加载构建：人数确认群摘要为 @小策 · 聚餐统筹，请在策划群提醒大家准时到，人数和预算不变；搜索小策可找到该群，已目视检查。服务与消息记录保留。

### 2026-09-10 — 简化正文暂扣提醒并复测

- 按用户确认的核心意思，将长状态说明简化为 `Your previous reply was NOT SENT because new messages arrived. Consider the new messages and reply again.`；保留 system-reminder 包装、正常提交的空内容审计记录和历史过滤。
- 读取 feat-544 的 cases.json、supplementary-cases.json 和旧报告，选六个正文场景改用日常短句，另加同文先发后扣；真实 DeepSeek V4 Flash/high 七场景通过，六个有更新场景共七次实际暂扣，连续更新消费两批输入。无关插话仍完整回复，取消通知保持静默，正常跟进不新增暂扣提醒。
- 每次核对实际 LLM 请求均为新短提醒、无成功提醒；原始证据/执行前计划/运行脚本/摘要保留在 `output/simple-reminder-evaluation/`。这是针对性行为验证，不是原历史全集重放或提示词因果 A/B；未重跑工具、后台、图片和报数压力场景。
- 相关内核测试 39 passed；Ruff、diff check 通过。保留 :59669 演示服务与旧数据，仅重载隔离 Gateway 以加载新提醒。

### 2026-09-10 — Agent 私聊原消息链接 404

- 用户从小策向小算的 send_message 投递确认点击原消息，进入空聊天。实测回执 ID 与真实记录一致，但 GET 会话/消息均 404；数据库显示两个 Agent profile 同属登录 owner，合成用户各自拥有独立 owner，Gateway 传入空 caller owner 后私聊被分配随机归属。
- Gateway 会话持久层用两个 Agent profile 的共同 owner 创建私聊。复用旧随机归属会话时，仅当旧 owner 不属于任何用户或 Agent profile 才修复归属；保留会话/消息 ID，不改其他真实租户会话，不为跨 owner Agent 推断共同归属。
- 先补真实 WebSocket agent.message → 回执 ID → owner 会话/消息 API 回归，新建与旧随机归属两例均 404 红；修后通过，其他 owner 仍 404。连同 Gateway 相关测试 67 passed；会话与租户/架构补充回归 173 passed。
- 已用同一修复路径校正 :59669 原测试会话 d96b6935c57c4c1e809f29380fe0b3a2，4 条消息内容/ID 不变。重新加载保留运行环境后，实际浏览器打开原深链接显示“已定位原消息”，预算请求高亮，300/400 元核算记录完整。修复证据在 output/chat-link-repair/evidence.json。
