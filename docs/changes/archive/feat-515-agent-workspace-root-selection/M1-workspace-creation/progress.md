# feat-515-M1 — Progress

## Delivered scope

- Gateway owns default/custom Workspace Root selection, target-parent validation,
  existing-directory confirmation, initialization, and node-local uniqueness.
- IM keeps a successful root as an opaque mirror; it neither canonicalizes nor
  validates a Gateway-local path.
- Workspace Root and its default/custom provenance are immutable after creation.
- A create operation is durable enough to recover one lost `agent.created` ACK,
  without allowing ordinary registration or a changed request to claim an Agent.
- The create page exposes default/custom modes, preserves the draft on a typed
  rejection, and gives an explicit existing-directory warning.

## Scope boundary

Conversation JSONL discovery, transcript availability states, and cross-Gateway
skill-distillation selection are not part of feat-515. They are deferred to the
follow-up bugfix where the owning Gateway reads its own JSONL and performs the
distillation.

## Milestone record

1. Gateway-local workspace creation and persisted provenance.
2. Typed IM/Gateway create outcome and opaque IM mirror.
3. Default/custom workspace create UI and localized recovery states.
4. Focused creation, immutable-root, and lost-ACK recovery verification.
5. Isolated browser acceptance for default/custom, existing-directory
   confirmation, and independent node-local roots.
