# feat-515 — Product Acceptance

## Accepted product contract

- Creating an Agent initially shows the selected Gateway's resolved default path without a mode picker.
- Clicking that path changes it in place to a focused custom-path input prefilled with the default path;
  the user can return to the default path.
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

- The UI must preserve default/custom state and the entered custom path across a
  recoverable validation error.
- The default Workspace state must remain visually subordinate to the create form: one path row, no large
  choice cards, repeated node id, or redundant outcome copy.
- The UI must make no host-local path judgement beyond a required custom value;
  typed Gateway errors drive the displayed state.
- Desktop and narrow layouts retain the Workspace card between Identity and
  Behavior.

## Final user acceptance

The user reviewed each iteration in the isolated service at `/settings/agents/new`. After the default path row,
click-to-edit behavior, and prefilled edit value were live, the user said: “好，就按这个吧。PR更新一下。”

## Explicitly deferred

Conversation transcript lookup and “Generate skill” execution are not accepted
by this unit. The follow-up bugfix moves JSONL reading and distillation to the
owning Gateway.
