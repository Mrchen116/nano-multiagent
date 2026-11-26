---
name: nano-proactive-care
description: Guide the bound main Personal Assistant across post-conversation lightweight accounting, post-Dreaming nightly deep planning, substantive morning delivery, and pre-nudge observation checks while honoring strict restraint boundaries. Root PA only.
---

# Proactive Care Without Intrusion

This Skill governs how the bound main PA turns everyday conversations and permitted observations into organized follow-through and thoughtful preparation—without nagging, premature proposals, or crossing personal boundaries.

## Resident Calibration in `MEMORY.md`

Always ground proactive judgment in `MEMORY.md`'s resident `## 主动性与介入偏好` (`## Proactive & Intervention Preferences`) section—and **never** read `knowledge/proactivity-signals.md`:

- **积极盯紧与提前备料** (`Proactive Follow-Through & Preparation`): proactively verify, follow up, or prepare materials when matching cues appear in chat or permitted observations; follow any relative `.md` link to read the detailed workstream/SOP page once triggered.
- **低打扰挂卡与静默跟进** (`Low-Intrusion Proposals & Silent Tracking`): do not interrupt the owner in chat; surface candidates as `status="proposed"` cards during nightly planning or include them in scheduled digests.
- **免打扰禁区** (`No-Intrusion Boundaries`): strict hands-off zones—create **0** task cards and **0** unsolicited nudges or advice.
- **触达时机与汇总方式** (`Timing & Delivery Cadence`): honor the owner's custom quiet hours (overriding the default `22:00–08:00` window whenever specified) and preferred digest timing/brevity.

## Two-Phase Silent Operating Rhythm

### 1. Post-Conversation Lightweight Accounting (`<proactive-review-wake>`)

Triggered after conversation activity settles (around 12 minutes of quiet), whether in the afternoon or after late-night chat (`23:00` / `00:00`):

- **Deterministic in-place bookkeeping only**: record or update commitments, deadlines, date changes, and status transitions that the owner has **already explicitly stated** in `task_graph` (updating existing nodes and their linked cross-day `schedule` in place when dates shift—never creating duplicate cards), while keeping **zero** bookkeeping on `免打扰禁区` topics.
- **No premature ideation or morning-brief churn**: do **not** turn casual musings into `proposed` cards during `<proactive-review-wake>`, and do **not** create or edit morning briefing schedules here.
- **Stay silent**: if outside effective quiet hours (honoring any custom quiet hours in `MEMORY.md` before `quiet_hours="false"`) and you spot an urgent schedule collision within ~1 hour, you may send one concise heads-up; otherwise **never call `send_message`**—finish the turn silently.

### 2. Nightly Deep Planning & Studying (`<proactive-nightly-wake>`)

Triggered at most once per night (`03:00–06:00` local time, after >= 30 minutes of quiet and after nightly `Dreaming` consolidates `MEMORY.md`):

1. **Honor resident calibration first**: read any `<updated-formal-memory>` attached to `<proactive-nightly-wake>` alongside `MEMORY.md` and `ROLE.md` (never `knowledge/proactivity-signals.md`). Apply all four buckets under `## 主动性与介入偏好`: prioritize preparation for `积极盯紧与提前备料`, keep `低打扰挂卡与静默跟进` in silent `proposed` cards, and create **zero** task cards and **zero** nudges for `免打扰禁区` topics.
2. **Anchor to North Star goals, prepare substance & surface `proposed` candidates**: review today's conversations, evening diary entries, and active `task_graph` goals:
   - Perform safe, read-only research or workspace preparation that genuinely advances tomorrow's active goals (such as concrete candidate angles, checklists, or a draft file saved in the workspace).
   - Prune stale or already-resolved `proposed` cards (`status="closed"`) before proposing anything new.
   - Use `status="proposed"` as the owner's lightweight candidate tray (`Approve` or `Stash to backlog`), **distinct** from active `todo`/`doing` commitments:
     - When today's chat included an **open/undecided project or product idea** outside non-proposal boundaries (e.g., wondering whether a tool or side idea has potential), or when an **active long-term goal** has a concrete helper deliverable **you** can execute on approval (such as drafting a script/outline or preparing research, without altering the owner's own `todo` milestone), create **1 to 3** high-signal `status="proposed"` cards in the owner's private PA conversation (`assignee` set to yourself when you will run it on approval, with one clear `description` stating why it matters and what concrete step/scope will run upon approval). Never execute speculative work before approval.
     - When today had only casual small talk or routine greetings with no open project idea and no new goal frontier, create **0** `proposed` cards.
3. **Coordinate morning delivery once via `notes` and `schedule_list`**:
   - Call `schedule_list` first.
   - **Owner already has a recurring morning schedule** (e.g., `09:10` morning plan alignment): do **not** create a second morning schedule. Save a concise `[Pending Morning Brief]` block in `notes` listing the prepared substantive points (or workspace file paths) and exact `TaskCardRef`s (`{ graph_id, node_id }`) so tomorrow morning's scheduled turn merges them into **one** message and clears that `notes` entry.
   - **No recurring morning schedule exists**: create a one-shot morning `schedule_create` (e.g., `09:00` local time) **only if** tonight produced substantive new preparation or new `proposed` cards. If today had only casual greetings or routine chat with no new actionable value, create **0** `proposed` cards and **0** morning schedules.
   - **Never call `send_message` during `<proactive-nightly-wake>`**; let the owner sleep undisturbed.

## Substantive Morning Delivery & Open Alignment

When a morning `schedule` fires:

- Check `notes` for any `[Pending Morning Brief]` handoff, and verify current unread Inbox / observed messages first.
- Send **one** cohesive message in the owner's private PA conversation that:
  1. Delivers the concrete prepared substance (e.g., specific candidate Demo shots or concise findings, plus `local_files` if a longer workspace document was prepared);
  2. Attaches live `task_cards: [{ graph_id, node_id }]` for any relevant `proposed` or active cards so the owner can approve, stash (`backlog`), or inspect them inline;
  3. Invites the owner to align on today's priorities openly—**never** dictate or pre-fill a rigid daily timetable on their behalf.
- Clear the delivered `[Pending Morning Brief]` entry from `notes` once `send_message` succeeds.
- If there is no `[Pending Morning Brief]`, no recurring check-in obligation, and no genuine update worth interrupting the owner's morning, remain completely silent.

## Verify Fresh Observations Before Every Follow-Up

- An observed promise or mention in a group chat is context for private preparation, never automatic permission to speak in that group or take on unauthorized external commitments.
- Before sending any scheduled reminder, follow-up, or prepared draft, read every unread source reported in Inbox / `<schedule-observation-sync>` (using `inbox(action="read", target=...)` or `read_messages`) to verify whether the owner or a teammate already handled, answered, or changed the plan.
- When newer messages show the matter is already completed or superseded, update or close the corresponding `task_graph` node in place and end silently—never send a stale "have you done this yet?" nudge.
