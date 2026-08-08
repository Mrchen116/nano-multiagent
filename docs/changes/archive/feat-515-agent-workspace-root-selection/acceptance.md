# feat-515 — Product Acceptance

## Accepted product contract

- Creating an Agent offers **Use default directory** and **Custom path**.
- The selected Gateway owns path interpretation and creates the workspace.
- A custom path requires an existing usable parent. An existing directory is
  usable only after an explicit warning and confirmation; existing files remain.
- The same canonical root may be used on different Gateway nodes, but only once
  per node.
- Workspace Root is read-only after creation.
- If Gateway created an Agent but its create response was lost, only the exact
  durable create operation can recover the result. A later ordinary registration
  or changed create request cannot take over that Agent.

## Acceptance boundaries

- The UI must preserve default/custom choice and entered custom path across a
  recoverable validation error.
- The UI must make no host-local path judgement beyond a required custom value;
  typed Gateway errors drive the displayed state.
- Desktop and narrow layouts retain the Workspace card between Identity and
  Behavior.

## Explicitly deferred

Conversation transcript lookup and “Generate skill” execution are not accepted
by this unit. The follow-up bugfix moves JSONL reading and distillation to the
owning Gateway.
