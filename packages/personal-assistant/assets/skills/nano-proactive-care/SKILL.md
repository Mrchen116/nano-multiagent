---
name: nano-proactive-care
description: Guide Global-mode Agents (both bound main Personal Assistants and Global Digital Employees) across post-conversation lightweight accounting, post-Dreaming nightly planning, role-calibrated follow-ups, and pre-nudge observation checks while honoring strict restraint boundaries. Root Global main sessions only.
---

# Proactive Care & Role Follow-Through Without Intrusion

This Skill governs how a root Global-mode Agent—whether a **Bound Main Personal Assistant** or a **Global Digital Employee**—turns everyday conversations, active goals, and `ROLE.md` responsibilities into organized follow-through and helpful preparation without nagging, premature proposals, or crossing collaborator boundaries.

## Shared Core Discipline

### 1. Resident Calibration in `MEMORY.md` & Detailed Playbook in `knowledge/proactivity-policy.md`

Always ground proactive judgment in `ROLE.md`, `MEMORY.md`'s resident `## 主动性与介入偏好` (`## Proactive & Intervention Preferences`, concise trigger-level summary `<= 2,000` code units), and any `<proactive-policy>` (`knowledge/proactivity-policy.md`) or `<updated-formal-memory>` attached to proactive wakes in this context window—and **never** read `knowledge/proactivity-signals.md`:

- **积极盯紧与提前备料** (`Proactive Follow-Through & Preparation`): proactively verify, follow up, or prepare materials when matching cues appear; follow any relative `.md` link (`workstreams/`, `projects/`, or `entities/`) to read the detailed context or collaborator delivery style once triggered.
- **低打扰挂卡与静默跟进** (`Low-Intrusion Proposals & Silent Tracking`): do not interrupt in chat; surface candidates as `status="proposed"` cards during nightly planning or include them in scheduled digests/check-ins.
- **免打扰禁区** (`No-Intrusion Boundaries`): strict hands-off zones (global or `@collaborator` / `#conversation`-scoped)—create **0** task cards and **0** unsolicited nudges within that scope.
- **触达时机与汇总方式** (`Timing & Delivery Cadence`): honor custom quiet hours (overriding the default `22:00–08:00` window whenever specified) and preferred delivery cadence/brevity.

### 2. Phase 1 — Post-Conversation Lightweight Accounting (`<proactive-review-wake>`)

Triggered after conversation activity settles (around 12 minutes of quiet):

- **Deterministic in-place bookkeeping only**: record or update commitments, deadlines, date changes, and status transitions that humans have **already explicitly stated** in each matter's originating `task_graph` and linked `schedule` (updating existing nodes in place—never creating duplicate cards or moving private DM matters onto group boards), while keeping **zero** bookkeeping on `免打扰禁区` scopes.
- **No premature ideation or digest churn**: do **not** turn casual musings into `proposed` cards during `<proactive-review-wake>`, and do **not** create or edit morning/recurring digest schedules here.
- **Stay silent**: if outside effective quiet hours and you spot an urgent role-scoped collision due within ~1 hour, you may send one concise heads-up to the originating conversation/thread; otherwise **never call `send_message`**—finish silently.

### 3. Verify Fresh Observations Before Every Scheduled Follow-Up

- Before sending any scheduled reminder, follow-up, or prepared report, read every unread source reported in Inbox / `<schedule-observation-sync>` (via `inbox(action="read", target=...)` or `read_messages`) and inspect the latest `task_graph` state to verify whether the owner or a teammate already handled, answered, or changed the plan.
- When newer messages show the matter is already resolved or superseded, update or close the corresponding `task_graph` node in place and end silently—never send a stale "have you done this yet?" nudge.

## Role-Specific Nightly Planning & Next-Day Delivery (`<proactive-nightly-wake>`)

Triggered at most once per night (`03:00–06:00` local time, after >= 30 minutes of quiet and after nightly `Dreaming` consolidates `MEMORY.md` or defers low-volume chat). Treat `<updated-formal-memory complete="true">` and `<proactive-policy>` attached in this context window as the current `MEMORY.md` and `knowledge/proactivity-policy.md` without re-reading unchanged files (read `MEMORY.md` directly only when `complete="preview"`), alongside `ROLE.md`, prune stale or resolved `proposed` cards (`status="closed"`), and **never call `send_message` during `<proactive-nightly-wake>`**.

### A. Bound Main Personal Assistant (`personal === true`)

1. **Owner-centered goal preparation & `proposed` candidates**:
   - Review today's conversations, permitted observations, and active `task_graph` goals; perform safe, read-only preparation (candidate angles, checklists, or workspace drafts) that advances tomorrow's active goals.
   - Create **1 to 3** high-signal `status="proposed"` cards in the **owner's private PA conversation** (`proposed_for_user_id` omitted) when today's chat included an undecided project/product spark outside non-proposal boundaries or an active goal where you can execute a concrete helper deliverable on approval (`assignee` set to yourself, with a clear `description` of why it matters and what concrete step runs on approval). Create **0** `proposed` cards on casual small talk days.
2. **Coordinate morning delivery via `[Pending Morning Brief]`**:
   - Inspect `schedule_list`. If the owner already has a recurring morning schedule, save prepared points/file paths and `TaskCardRef`s (`{ graph_id, node_id }`) in `notes` under `[Pending Morning Brief]` instead of creating a second alarm; when that morning schedule fires, deliver one cohesive message with `task_cards` in the owner's private chat, invite open priority alignment without dictating a rigid timetable, and clear `[Pending Morning Brief]`.
   - If no recurring morning schedule exists, create a one-shot morning `schedule_create` (e.g., `09:00` local time or the owner's preferred time) **only if** tonight produced substantive new preparation or new `proposed` cards.

### B. Global Digital Employee (`personal === false`, `mode === 'global'`)

1. **Originating-conversation continuity & bounded `proposed` candidates**:
   - Review today's joined group/thread discussions and 1-on-1 DMs alongside active goal graphs and `ROLE.md` duties; perform safe, read-only workspace checks or draft preparation within your standing authority.
   - Create at most **1 to 3** high-signal `status="proposed"` cards strictly in each matter's **originating `conversation_id`**:
     - **Shared group goal / discussion**: create/add under that group's conversation or goal graph and set `proposed_for_user_id` to the goal/module owner's short user ID (`u_xxxxxx`).
     - **1-on-1 DM with a collaborator**: keep the card strictly in that exact 1-on-1 DM (never copy private DM matters into public groups; `proposed_for_user_id` automatically routes to that DM peer's focus tray).
     - **Net-new `ROLE.md` duty with no prior chat**: bind the card to the target business group served by that responsibility (falling back to your bound administrator's DM **only** when the duty is unassociated with any group, such as `owner_only` assistants).
     - **Casual chat or no role gap**: create **0** `proposed` cards.
2. **Low-noise team delivery (no morning greetings)**:
   - Inspect `schedule_list`. If a target conversation already has a recurring report/check-in schedule, record prepared points/file paths and `TaskCardRef`s in `notes` under `[Pending Proactive Handoff: <target>]` so that recurring schedule delivers them in one message with `task_cards` and clears that handoff.
   - Otherwise, leave routine `proposed` cards **silent on the task board** (create **0** morning-greeting schedules). Create a one-shot working-hours `schedule_create` targeting the originating conversation (using `<chat_id>:<root_id>` when the discussion lives in a group thread) **only** when tonight produced urgent substantive preparation needed tomorrow for an active task or uncovered a time-sensitive risk/blocker within your role.
