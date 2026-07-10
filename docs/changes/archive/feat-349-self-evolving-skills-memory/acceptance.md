# feat-349 Acceptance Report — Round 1

**Date**: 2026-05-14
**Reviewer**: change-reviewer (Round 1)
**Unit**: feat-349-self-evolving-skills-memory
**Branch**: unit/feat-349 @ HEAD 003ed60e
**Verdict**: fail
**Highest Required Action**: fix-implementation
**Issues**: blocking: 1 / major: 1 / minor: 1

---

## Service Startup Notes

- IM service: restarted from worktree (PID 79002). Frontend rebuilt from unit/feat-349 source.
- PA Gateway: started with fresh test config (`/tmp/test-pa-config/config.yaml`) — existing `~/.nano-assistant/config.yaml` has stale `user_id` from a prior IM instance; the Gateway couldn't re-use it. Used worktree kernel directly for PA product testing (PA kernel app: `personal_assistant.kernel_app:app`).
- LC kernel: `coding_cli.kernel_app:app` on port 8000. Both kernels confirmed healthy before journeys.

---

## User Journeys Exercised

| # | Journey | Product | Result |
|---|---------|---------|--------|
| J1 | Verify skill_manage + memory tools are registered in session | LC + PA | pass |
| J2 | Verify memory files seeded at correct path when Gateway starts | PA | pass (via Gateway) |
| J3 | Verify memory tool can write entries to .nanoassistant/memory/USER.md | PA (direct) | pass |
| J4 | Verify skill tool can create SKILL.md under .nanocode/skills/ | LC (direct) | pass |
| J5 | Verify skills created are discovered by SkillRegistry on next load | LC | pass |
| J6 | Verify self_evolution default config is injected into session metadata | LC + PA | pass |
| J7 | Verify self_evolution can be disabled via workspace config file | LC | pass (config level) |
| J8 | Verify agent isolation — different agents have different memory/skill roots | PA | pass |
| J9 | Verify CLI self_evolution_review event formatter emits "· background..." line | LC (code path) | code present, unreachable |
| J10 | Verify IM system message rendering for sender_type=system | PA (code path) | code present, not tested E2E |
| J11 | Observe actual auto-skill/memory creation after a multi-turn conversation | LC + PA | FAIL — hook never fires |

---

## Acceptance Criteria Coverage

| # | Criterion | Expected Source | Verification Method | Evidence | Result | Notes |
|---|-----------|----------------|---------------------|----------|--------|-------|
| AC-1 | 多轮协作后 agent 自动沉淀新 skill | spec.md L75 | Observe skill file creation after 10+ tool iterations | No skill created; background hook never fires | **fail** | Root cause: `_filter_hook_registry` drops `mode=background` (see Issue #1) |
| AC-2 | agent 自动更新已有 skill | spec.md L76 | Observe skill file update | Cannot test — hook never fires | **fail** | Same root cause as AC-1 |
| AC-3 | 用户透露偏好后 agent 自动写 memory | spec.md L77 | Observe USER.md entry after conversation | No memory written; background hook never fires | **fail** | Same root cause as AC-1 |
| AC-4 | 轻量系统提示回显（CLI 一行 / IM meta 消息） | spec.md L78 | Observe "· background self-evolution review" in REPL / IM conversation flow | Never reached; hook never fires | **fail** | CLI formatter code is correct and would emit `· background self-evolution review: skills updated`; IM system-type message code present; but both are unreachable |
| AC-5 | 沉淀过程不打断当前对话 | spec.md L79 | fire-and-forget verified at code level | `asyncio.create_task` in `dispatch_background` confirmed | **pass** (design) | AC is architecturally satisfied; cannot verify E2E because hook never triggers |
| AC-6 | skill/memory 是可直接访问的纯文本文件 | spec.md L80 | Inspect disk; edit and verify next session loads changes | PA: `/tmp/feat349-pa-workspace/.nanoassistant/memory/{MEMORY.md,USER.md}` seeded by Gateway; LC: SkillWriter writes to `.nanocode/skills/<name>/SKILL.md`; MemoryStore writes to `.nanocode/memory/USER.md` | **pass** | Files are plain text, user-editable |
| AC-7 | agent 后续会话会用到自己沉淀的内容（越用越懂） | spec.md L81 | Skill discovery includes skill_root; memory injected in system prompt | SkillRegistry discovers skills from workspace skill_root. Memory block injection code in prompting.py. Cannot E2E verify because nothing is auto-created | **pass** (partial) | Discovery and injection wired correctly; E2E blocked by AC-1/2/3 failure |
| AC-8 | 自进化能力默认开启 | spec.md L82 | Check default_session_metadata.self_evolution.enabled | `bootstrap_product` injects `{"enabled": True, ...}` when no workspace config present | **pass** |  |
| AC-9 | 用户可整体关闭 / 分别关 skill / memory | spec.md L83 | Create `.nanocode/config.yaml` with `self_evolution.enabled: false`; verify metadata | `bootstrap_product` reads workspace config and injects correct disabled values | **pass** (config level) | Hook reads the config from `ctx.metadata`; config mechanism works; E2E trigger path blocked |
| AC-10 | 关闭后不再自动沉淀，不再回显 | spec.md L84 | Observe no new files, no notifications after disable | Hook checks `enabled` flag first and returns early — code verified | **pass** (code path) | Cannot observe E2E because even with enabled=true, hook never fires |
| AC-11 | 不同 agent 各自隔离 skill/memory | spec.md L85 | Two agents with different workspace_roots have different paths | Agent A: `.../feat349-pa-workspace/.nanoassistant/memory`; Agent B: `.../feat349-pa-workspace-b/.nanoassistant/memory` — different | **pass** |  |
| AC-12 | Coding CLI 和个人助手两产品都有此能力 | spec.md L86 | Both kernel apps have skill_manage+memory in tool registry | LC session: `['read','write','edit','bash','agent','task_stop','skill_manage','memory']`; PA session same plus web tools | **pass** |  |

---

## Issues

### Issue #1 — [BLOCKING] `_filter_hook_registry` drops `background` mode — self-improvement hook never fires

**Severity**: blocking

**Recommended Action**: fix-implementation

**Action Rationale**: `bootstrap.py:_filter_hook_registry()` calls `filtered.on(...)` without passing `mode=registration.mode`. The `self_improvement` hook's `agent_end` registration (mode=BACKGROUND) is re-registered as mode=OBSERVE (the default). An OBSERVE-mode hook context never gets `fork_conversation` injected (`dispatch_observe` strips it). The hook's `on_agent_end` checks `if fork_fn is None: return` as the first line — so it always exits immediately. No skill or memory is ever created automatically. All of AC-1, AC-2, AC-3, AC-4 fail as a result.

**Evidence**:
- `full_hook_registry` (pre-filter) has: `event=agent_end mode=background handler=on_agent_end` — confirmed by introspection
- `resolved.hook_registry` (post-filter) has: `event=agent_end mode=observe handler=on_agent_end` — mode dropped
- `self_improvement.py` `on_agent_end` first line: `fork_fn = getattr(ctx, "fork_conversation", None); if fork_fn is None: return`
- Fix: add `mode=registration.mode` to `filtered.on(...)` call in `bootstrap.py:_filter_hook_registry`

**Affected file**: `/Users/czj/Repos/nano-multiagent/.worktrees/main/src/agent/platform/bootstrap.py`, function `_filter_hook_registry`

---

### Issue #2 — [MAJOR] PA Gateway cannot start with fresh IM service due to user_id mismatch in persisted config

**Severity**: major

**Recommended Action**: fix-implementation

**Action Rationale**: `~/.nano-assistant/config.yaml` persists `user_id` and `token` from prior IM instances. When IM is restarted with a new JWT secret (or the DB is fresh), the Gateway silently fails to start ("node demo-node did not appear in IM bootstrap") and the kernel never comes up. The `username`/`password` re-login mechanism works correctly, but the persisted `user_id` in the config prevents successful node registration. Users restarting the IM service will find their PA Gateway broken with no clear recovery path. This affects AC-4 (PA meta message) and E2E verification of the full PA self-evolution journey.

**Evidence**: Gateway log showed "Gateway failed to start — node demo-node did not appear in IM bootstrap" repeatedly. The issue was traced to `user_id: b3954df...` in config not matching the new IM user `e458c7e3...` after IM restart.

**Note**: This may be a pre-existing issue with the `user_id` persistence model, but it blocked PA E2E testing in this review round.

---

### Issue #3 — [MINOR] IM system messages rendered as regular chat bubbles — no visual differentiation from user/agent messages

**Severity**: minor

**Recommended Action**: fix-implementation

**Action Rationale**: spec AC-4 requires "对话流里浮现一条轻量的 meta 提示（不是 agent 发的聊天消息）". The frontend `MessageBubble` component renders `sender_type=system` messages with the same bubble style as user/agent messages — only the sender name shows as "System". A true "meta prompt" should be visually distinct (e.g. centered text, muted style, no avatar bubble) to distinguish it from conversational messages. The current implementation looks like another chat participant, not a system notification.

**Evidence**: `message-pane.tsx` line 1008 passes all messages to `MessageBubble`; system messages receive the same bubble/avatar layout. `getGroupMessageSenderLabel` returns "System" string but no distinct styling class is applied.

---

## Side Findings

- Multiple stale kernel processes from prior worktrees are running on various ports (PID 87524, 15587, 74161, etc). These consume memory but don't block this unit's functionality. Recommend cleanup (`pkill -f "personal_assistant.kernel_app"`).
- LC session tools endpoint unexpectedly includes `send_message` and `web_search` despite LC profile `DEFAULT_TOOL_IDS` not declaring them and `OPTIONAL_TOOL_IDS = []`. Possible `_filter_tool_registry` issue or default builtin tools being added on top of profile filter. Not blocking, but worth investigating.

---

## Upper-Level Document Sync

| Document | Check | Notes |
|---|---|---|
| `SPEC.md` | No update needed | No new architectural concepts introduced |
| `docs/内核设计SPEC.md` | May need update | New `background` hook mode, `fork_conversation` contract, `MemoryStore`, `SkillWriter` are new kernel contracts not yet documented |
| `AGENTS.md` / `CLAUDE.md` | No update needed | Developer workflow unchanged |
| `docs/CodingCLI-SPEC.md` | May need update | LC now has `skill_manage`/`memory` tools and workspace config file |
| `docs/NodeGateway-SPEC.md` | May need update | design.md §3 notes `NodeGateway-SPEC.md` uses `.nano-assistant` while code uses `.nanoassistant` — should be synced |
| `docs/IM-SPEC.md` | May need update | New `sender_type=system` message type added |
| `docs/operator-runbook.md` | May need update | Self-evolution enable/disable config not documented |
