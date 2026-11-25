---
name: nano-ongoing-work
description: Carry accepted multi-turn commitments across turns using progressive task graphs, event-driven doing wakes, flexible waiting, and background workers until verified delivery. Use for Global Agents, Personal Assistants, and their internal workers; skip for single-turn Q&A.
---

# Follow Through on Ongoing Work

Confirm the intended outcome, active constraints, and already-completed evidence first. Make concrete progress whenever executable; when work genuinely depends on another person or a future checkpoint, leave an explicit recovery path. Never turn this Skill into bureaucratic form-filling for the user.

## Own Responsibility by Role

- The Global / PA root Agent directly handles everyday conversation, status checks, quick lookups, and small actions. Delegate each self-contained investigation, draft, or implementation deliverable to one continuable background worker (`delegate_worker(action="start", label, message)` or a continuable `subagent` with `run_in_background: true`). Pass the goal, task-specific constraints, usable materials, and expected deliverable; quote relevant user words verbatim and keep IM conversation, user, and message IDs in the root Agent's own routing notes.
- Distinguish user instructions, your own working hypotheses, and decisions taken within existing authority. Check whether existing authorization covers broader scope or new side effects before acting; ask only when a real decision would change the outcome.
- First-level workers organize any sub-tasks, verify results, and report outcomes or actionable blockers back to their parent. Only the root Agent reads the product Inbox, queries product chats, or delivers public messages (`send_message` / `send_user_message`).
- Route follow-ups, corrections, answers, and revisions back to the original worker by ID rather than spawning duplicate workers. When passing chat images or attachments, provide an actual readable local path (such as `download_attachment` `local_path` or a workspace file) so the worker can open it directly.

## Coordinate Only When Action Changes

- Workers proceed through routine steps and recoverable issues without asking "continue" or streaming routine test logs. Message the parent only when missing parent-held facts/decisions, when delivery scope materially changes, or at an explicitly agreed checkpoint.
- When receiving an internal worker message, decide what action changes; routine progress needs no "received/continue" reply and does not automatically trigger a public user message.
- Continuable workers send one self-contained result to their parent before finishing, followed by a brief closing note; one-shot forks return through completion without a duplicate send.

## One Progressive Task System, Zero Duplicate Ledgers

- Track durable commitments and multi-step goals in `task_graph`—never maintain a parallel Markdown task ledger such as `.nanoassistant/ongoing-work.md`. Use `notes` only for concise session-local operational context (such as active worker IDs or pending morning handoff references), durable `MEMORY.md` (maintained by Dreaming) for lasting preferences/boundaries, and Skills for reusable procedures.
- **Start small, expand in place**:
  - Create a standalone commitment or candidate idea as a single-card root (`mode: "none"`, the default of `task_graph(action="create")`).
  - When a single card grows into ordered milestones or parallel options, upgrade that node in place from `mode: "none"` to `mode: "dag"` or `"explore"` via `task_graph(action="apply")` (or pass initial `operations` directly on `create` when the structure is already clear). Sub-containers can nest progressively while every deep task keeps its root North Star goal in focus.
  - Keep independent matters in separate cards/graphs; updating or pausing one matter must not overwrite or halt unrelated work.
- **Keep materials decoupled from task fields**: put concise talking points directly in the chat message, write longer drafts or research artifacts to workspace files and attach them via `send_message(local_files=[...])`, and embed live `task_cards: [{ graph_id, node_id }]` on `send_message` when presenting actionable cards in Nano IM.

## Event-Driven Execution and Flexible Waiting

- **Single-shot `doing` wakes**: entering `doing` (or being reassigned/resumed into `doing`) wakes the responsible Agent once with the task's root North Star context (`root_title`, `root_goal_summary`, `parent_path`). Make real progress in that turn; when the turn ends and no further step is immediately runnable, the session naturally settles to `idle` without a polling loop.
- **Choose the right recovery mechanism when waiting**:

| Waiting On | How to Record & Resume |
| --- | --- |
| Background worker | Keep the worker ID; its completion/report automatically wakes the parent—never poll in a loop. |
| Human reply or decision | Deliver clear findings/options first, then set `status="waiting"` with `wait: { reason, question, asked_user_id }` and **no** `schedule_id`. Incoming messages wake you naturally—do not set nagging timers. |
| External event with no fixed clock | Record `status="waiting"` with `wait: { reason }` (no `schedule_id`) or rely on an already-enabled `Heartbeat` check in `.nanoassistant/HEARTBEAT.md` when periodic scanning was authorized. |
| Specific future date/time or cross-day follow-up | Ensure the task is assigned to you (`assignee.type="agent"`), create a native `schedule` (`schedule_create`, up to 180 days out) for the actual milestone or follow-up time, then record `status="waiting"` with `wait: { reason, schedule_id }`. Never invent 1-hour busy-wait loops for multi-day deadlines. |

- When a scheduled check or message wakes you, read the latest Inbox / conversation messages and task state first; if the item was already resolved or superseded, update or close the task quietly without sending redundant follow-ups.

## Handling New Inputs, Blockers, Stops, and Completion

- Distinguish casual chat, brand-new assignments, and revisions to existing tasks. Apply user corrections to the active requirement first and forward updates to the original worker before judging late results.
- On a permission denial, inspect the exact denied action, reason, and original user scope. Continue permitted parts and safe alternatives that genuinely avoid the restricted data or side effect; never disguise or retry a denied action through another tool, and ask the user concisely only when new authorization is genuinely needed.
- On `/stop` or an explicit pause, halt the targeted workers/tasks, record preserved artifacts and remaining gaps accurately, and never auto-resume paused work from background events; resume only on explicit human instruction.
- Completion requires verified artifacts, state updates, and actual `send_message` delivery (`status: "sent"`) to the task's conversation—an internal draft or tool receipt alone is not user delivery. Prefer `in_review` when human sign-off is expected, or `done` when directly verified; clean up temporary task-specific schedules that are no longer needed.
