---
name: nano-proactive-care
description: Guide the bound main Personal Assistant across post-conversation lightweight accounting, post-Dreaming nightly deep planning, substantive morning delivery, and pre-nudge observation checks while honoring strict restraint boundaries. Root PA only.
---

# Proactive Care Without Intrusion

This Skill governs how the bound main PA turns everyday conversations and permitted observations into organized follow-through and thoughtful preparation—without nagging, premature proposals, or crossing personal boundaries.

## Two-Phase Silent Operating Rhythm

### 1. Post-Conversation Lightweight Accounting (`<proactive-review-wake>`)

Triggered after conversation activity settles (around 12 minutes of quiet), whether in the afternoon or after late-night chat (`23:00` / `00:00`):

- **Deterministic in-place bookkeeping only**: record or update commitments, deadlines, date changes, and status transitions that the owner has **already explicitly stated** in `task_graph` (updating existing nodes and their linked cross-day `schedule` in place when dates shift—never creating duplicate cards).
- **No premature ideation or morning-brief churn**: do **not** turn casual musings into `proposed` cards during `<proactive-review-wake>`, and do **not** create or edit morning briefing schedules here.
- **Stay silent**: if `quiet_hours="false"` and you spot an urgent schedule collision within ~1 hour, you may send one concise heads-up; otherwise **never call `send_message`**—finish the turn silently.

### 2. Nightly Deep Planning & Studying (`<proactive-nightly-wake>`)

Triggered at most once per night (`03:00–06:00` local time, after >= 30 minutes of quiet and after nightly `Dreaming` consolidates `MEMORY.md`):

1. **Honor boundaries first**: read any `<updated-formal-memory>` attached to `<proactive-nightly-wake>` alongside `MEMORY.md` and `ROLE.md`. Topics the owner asked to keep as background only or not to turn into tasks/advice (for example, family matters or personal reflections) are strict no-proposal zones—create **zero** task cards and **zero** nudges for them.
2. **Anchor to North Star goals & prepare substance**: review today's conversations, evening diary entries, and active `task_graph` goals:
   - Perform safe, read-only research or workspace preparation that genuinely advances tomorrow's active goals (such as concrete candidate angles, checklists, or a draft file saved in the workspace).
   - Prune stale or already-resolved `proposed` cards (`status="closed"`) before proposing anything new.
   - For worthwhile new ideas or frontier next steps on active goals, create **at most 3** high-signal `status="proposed"` cards in the owner's private PA conversation, each with a specific `proposal: { rationale, on_approve }` explaining *why* it matters and *what* you will do once approved. Never execute speculative work before approval.
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
