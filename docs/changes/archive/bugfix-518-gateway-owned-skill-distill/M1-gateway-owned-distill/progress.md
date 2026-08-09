# M1 progress

## 2026-08-09 browser acceptance

Ran an isolated IM and two isolated Gateways from this worktree. The source
conversation was bound on the first Gateway and its session JSONL existed only
under that Gateway's isolated workspace.

- In Web IM, selected the first source and execution Agent. The browser posted
  identities only; the first Gateway returned the existing complete
  `conversation-skill-distiller` prompt with its locally resolved JSONL path.
- Web IM created the pinned direct conversation, prefilled that returned prompt,
  and sent it through the ordinary chat path. The Gateway processed the normal
  skill request and returned its normal distillation result.
- A direct source conversation on the second Gateway appeared in the selector.
  Once the first source was selected, the second source was visibly disabled as
  `Different Gateway`.

The temporary IM, both Gateway processes, and the Vite server are stopped after
this evidence is recorded; the standard E2E lifecycle retains its ignored run
data for local debugging. No permanent browser E2E was added.
