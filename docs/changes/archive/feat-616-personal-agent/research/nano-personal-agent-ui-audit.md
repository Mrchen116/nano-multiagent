# nano personal agent: Web IM experience audit

Audit date: 2026-10-16. Checkout: `/workspace/shared/nano-personal-agent-design`, branch `main`, starting HEAD `481467ac16f0eda4561fca5c8230050541600de9`. Initially clean. This is investigation and recommendations, not a finalized change design, approved navigation decision, source implementation, or Gate 2 result.

Read AGENTS.md, docs/README.md, change-design-author/SKILL.md and references/prototype-and-runbook.md, product/web-im-principles.md, and relevant current IM specs/code. No product source was modified.

## Findings that affect the design

1. Current first agent has no durable special role in the UI. `features/onboarding/onboarding-page.tsx` generates a local candidate ID, creates a normal `work_mode: global` agent, and resolves `existingAgent` as candidate match or `agents[0]`. That fallback must not become the personal-agent identity contract. Browser-local drafts cannot guarantee one role per user across browsers or retries. Creation explicitly disables `heartbeat` and `cron_scheduling`; proactive behavior needs an explicit capability/default/policy decision, not only copy changes.
2. Current navigation already separates conversation, tasks, and agents. `app/router.tsx` has `/chat`, `/chat/:conversationId`, `/tasks`, `/tasks/:graphId`, `/settings/agents`, `/settings/agents/new`, `/settings/agents/:agentId`, plus node/model/account settings and `/onboarding`. `app/shell/app-shell.tsx` has desktop Chat / Tasks / Agents and mobile Chat / Tasks / Agents / Me. Mobile hides the bottom bar in `/chat/:conversationId`; new personal routing must preserve this conversation-space rule rather than accidentally leaving global navigation over the composer.
3. A new task dashboard would duplicate the established `/tasks` surface. `docs/specs/im/task-graphs.md` defines graph hierarchy, real/user assignees, sources, cross-tree owner views, revision-controlled writes, permissions, and status-versus-execution distinctions. Link concrete personal follow-ups to those existing records. Do not create parallel task IDs, statuses, or a synthetic completion score.
4. Existing conversation-scoped drafts are worth preserving. `components/composer-draft-store.ts` stores text, tracked mentions, attachments, failures and slash state per user and conversation; invalidated membership removes drafts and rejects late writes. `message-pane.tsx`'s existing `draftSeed` effect, however, unconditionally `setDraft(draftSeed.text)` and clears mentions. Reply assistance must add a safe apply flow rather than reuse this effect and overwrite a user's in-progress reply.
5. Source navigation already exists: `chat-workspace-page.tsx:321` reads `?message_id=...`, and its locator finds `[data-message-id]` around line 661. Suggested drafts and follow-ups should retain source conversation and message IDs and use this actual destination format.
6. Message interaction entry points exist but no current AI reply-assist action was found. `MessagePane` connects `MessageBubble` hover/keyboard toolbar, context menu and touch action sheet; current spec emphasizes native text selection and short copy/fork menus. An added “帮我回复” should preserve native selection and add only the relevant message action, not a persistent row of AI buttons under every message.
7. Agent management distinguishes public profile from owner configuration. `AgentProfilePage` only returns `AgentDetailPage` for owner; other users get public profile/work. `AgentsListPage` is a searchable 240px rail on desktop and full-width mobile list. Keep specialist create flow and owner-based configuration intact. Mark the owner's personal agent as “我的助手” with fixed role, while retaining its editable name. Do not infer personal role from name, sort order or global work mode.

## Recommended information organization (pending user navigation choice)

Preferred direction offered by parent, not yet approved: a main-navigation “我的助手” entry resolving a stable personal agent and canonical private conversation. It should open conversation immediately, with the assistant's name and small role cue; it is not a landing dashboard. Ordinary Chat remains the place for people, groups and specialist agents. A separate badge/count must not count the same unread event twice across personal and Chat entries.

Desktop: retain 48px topbar and existing conversation hierarchy. Add the personal tab consistently alongside the existing tabs. Within personal chat use the familiar message stream/composer. A compact on-demand “跟进中的事” surface may link to existing task records, without occupying the primary reading lane by default.

Mobile Web: do not shrink a desktop three-column assistant layout. Keep a full-width conversation, normal back affordance, and existing keyboard-safe composer. Five bottom destinations (personal/chat/tasks/agents/me) require an actual 360px and 390px touch-label check; do not silently remove Tasks/Agents or move them behind Me as an implementation detail. If personal is a dedicated route, extend AppShell's conversation detection explicitly. Back from source-linked help must restore the originating chat and its draft/reading position.

Alternative if user chooses list-only: pin a distinct role section above ordinary sorted chats, outside filters/search so it is always reachable, with a canonical stable conversation. This has less cross-product visibility than a top-level entry. Do not implement both unrelated personal homes.

Onboarding: preserve connection/model preparation and retained progress. Change step 3's framing from selecting a permanent specialist role to meeting the enduring personal assistant: editable name, current goals, optional help preferences. Explain that specialist agents remain independently creatable later. Continue into the canonical personal conversation with editable suggested first message, never auto-send. Retry and existing-user migration need explicit trustworthy identity resolution and result feedback. First-agent-purpose history can seed preferences, but must not retroactively label arbitrary `agents[0]` personal.

Proactive updates: deliver succinct messages in the same private assistant conversation, with evidence/source and a concrete next decision when needed. For tasks, link the existing task and distinguish “waiting for you” from “working” and “offline.” Avoid fixed daily statistic tiles, generic productivity scores, and a separate inbox competing with chat. Permission to follow progress does not itself authorize sending to other people; make context-linked draft versus sent message unmistakable.

## Reply-assistance journey and contract proposals

1. User opens a human/group conversation and invokes “帮我回复” on a specific message (or near the composer when target is unambiguous). Show source title, sender and a short exact source excerpt; make the selected scope understandable before generating. Group recipient and destination stay visible.
2. Desktop uses a modest contextual panel anchored to the conversation; narrow/mobile uses a full-height help surface with back-to-chat, preserving the original draft. Both are the same personal agent, not a temporary new specialist agent. If the assistant cannot read this source under its own allowed scope, show the limitation and a supported explicit-sharing path; do not silently grant ambient access to all private/team chats.
3. Draft appears with status “草稿”; primary action “放入输入框” (or “替换草稿” after deliberate selection), secondary edit/request refinement/cancel. It does not send to the original recipient. Keep source link and proposed recipient visible.
4. If target composer has text or attachments, preserve them and offer explicit replace/append/cancel, with a recoverable prior draft. A late response applies only to the captured conversation/draft version, never whichever chat is active now. Recheck membership and `can_write` before apply/send.
5. User returns to the source conversation, reviews the exact editable message, and uses existing Send. Successful send uses actual resulting message identity; a timeout is not shown as sent. Source deleted, lost access, assistant offline, generation failure and navigation away retain the original draft and provide a local recovery action.
6. “交给助手跟进” is a separate bounded intent, not synonymous with reply generation. Let the user see what will be watched and what can happen; create/reuse existing task records where appropriate, and acknowledge in the private assistant conversation with a source link. Do not automatically send external follow-ups under generic “help me” language.

## Visual baseline actually inspected

Opened and visually inspected `docs/changes/archive/feat-600-computer-page-experience/evidence/adjacent-chat.png` (1280×900). It is a historical real-chat screenshot reused by feat-600, not a fresh current-HEAD run. Its provenance is explicitly described in `.../evidence/walkthrough.md`: adjacent chat uses earlier real screenshots, and that change did not rerun chat journeys.

Observed: 48px white topbar; centered Chat / Tasks / Agents; light cool-gray approx. 262px sidebar with search, filters and selected conversation; white reading surface; low-contrast assistant bubbles on left and muted pale-teal user bubbles on right; avatar/name/node metadata above; composer spans the main content at bottom; technical token/time details are subordinate. This hierarchy supports adding a personal identity and bounded help panel without a new visual system. Do not reproduce the historical sidebar's clipped last filter label as a design requirement.

Source counterpart `styles/global.css`: white `--im-surface`, `--im-sidebar:#f5f8fa`, text `#243440`, muted `#60717e`, teal accent `#0f766e`, pale accent `#e5f3ef`, borders `#e2e8ed`; IBM Plex Sans/Mono with system fallbacks. `use-is-mobile.ts` switches at 768px. Continue these semantic tokens and restrained typography, avatars and border treatments rather than inventing saturated assistant branding or large dashboard cards.

No screenshot for new proposed personal-agent behavior exists yet. No claim of current live UI, responsive prototype approval, or real-backend behavior verification is made.

## Preview feasibility and exact limits

Available `/usr/bin/chromium` and `/opt/codex/cua_node/lib/node_modules/playwright` can render a standalone prototype directly with `require('/opt/codex/cua_node/lib/node_modules/playwright')`, `chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']})`, and a local file URL. This needs no product install. Screenshots must be actually opened and inspected after scripted actions, with demo controls outside the product region and mock states marked.

For a true current-source frontend with mocked data: after a verified dependency install, run Vite from `src/IM/frontend` on an isolated high port (e.g. 43127, not 5173). Intercept `/im/**` in Playwright, fulfill `/im/v1/auth/refresh` with synthetic BrowserSession and `/im/v1/auth/me` with same user, then fixture conversations/messages/agent/node capabilities. Old `localStorage.im_auth_v1` injection will not work: `auth-store.ts` explicitly removes it and hydration uses the refresh route. Session token must have a valid future `exp` for the client's freshness check. Mock all writes too so no message/data reaches a real server, and label evidence “current React UI, mocked data/transport.” Existing integration test fixtures supply valid data shapes.

Parent was installing dependencies but reported tarball integrity retries. One local Vite startup attempt returned missing `.bin/vite` (127), so no service started and no port/process cleanup was needed. Do not bypass integrity checks. The current audit therefore uses current code plus the explicitly dated historical screenshot, with fresh-current rendering left unverified.

## Required prototype walkthrough before design approval

- Desktop personal entry → private conversation → context-linked proactive update → source chat.
- Source message → reply help → generation → edit → apply to composer → user-controlled send simulation; all destination and source cues visible.
- Existing draft conflict and late response after switching chats; no overwrite/leak.
- Onboarding create/retry/open same assistant and specialist creation still discoverable.
- Offline, deleted source/lost membership, empty/failed generation, loading and recovery.
- 1440/820/390/360 widths, long assistant/group names, keyboard focus, close/back, scrolling and mobile composer space.
- Record which observations are prototype-only and which remain backend/device acceptance requirements. Gate 2 requires actual rendered walkthrough and independent reviewer; code inspection alone is insufficient.

## Prototype follow-on, 2026-10-16

Parent supplied explicit user request for an interactive prototype to judge UI. Added discussion-only dual-entry HTML at `/workspace/shared/nano-personal-entry-options.html` and `docs/changes/feat-616-personal-agent/prototype.html`. A/B toggle, source navigation, editable reply, existing-draft conflict, append/replace/cancel, bounded follow-up confirmation and existing-task reference are implemented as mock behavior. Initial source is explicitly already shared by the user; draft does not invent availability. No ambient monitoring or automatic send contract was chosen.

DOM-only JSDOM check passed A/B rendering, source switch, conflict warning, append retaining prior text, follow-up and task reference. This is not visual verification. Current React mock and prototype screenshot scripts could not launch Chromium from restricted shell (socket Operation not permitted); approved escalation failed at environment bwrap initialization. Cloud browser accepts HTTP(S) only, while shell HTTP server is unreachable from that browser. Cloud terminal opened, but documented typing APIs reported no Paste action. Clipboard/terminal paste call was denied; retried once with exact user authorization evidence, then rejected by browser URL/frame policy (protocol not allowed on error-frame context). Stopped that route. No screenshots generated; prototype remains VISUALLY UNVERIFIED and not Gate 2 ready.
