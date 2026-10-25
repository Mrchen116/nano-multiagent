# feat-658 Code Review

- Reviewer: independent agent; did not implement the reviewed change.
- Mode: full.
- Reviewed range: `8e4054197908a1a433f748525c9650a831a950b6..3689a8b84ba09e69eae013bb79d93a1c4d1f2010`.
- Checkout HEAD was the frozen reviewed head. Untracked runtime `packages/personal-assistant/assets/skills/.usage.json` was ignored.
- Scope: all implementation and test changes in the range, with calling paths in IM messaging/PA/interactive/fork, PA admission/publication/Inbox/SingleThread, DSH tool registration/normalization/approval/context inheritance, Web/iOS identity and ComposeMessage, migration and generated assets. Requirements and design are review context; this report does not grant product acceptance.

## Findings

```json
[
  {
    "file": "packages/dsh-integration/src/policy/codex-context.ts",
    "line": 42,
    "summary": "[P2] Recognize the actual conversations sender shape when preserving user history",
    "failure_scenario": "A receiving Agent restores the original represented user instruction through conversations read/search, then performs more than 40 subsequent non-user evidence entries. IM Work emits sender.kind=user (work.ts:726-730), but the new retention predicate only accepts sender.type=user. The restored instruction is classified as optional tool evidence and can be omitted entirely, including pa_agent_id and original restrictions. A direct reproduction using exported reviewInput, a real-shaped conversations_result followed by 41 recent tool rows, and budget=50000 drops the original scope. Changing only kind to type preserves it. The new approval-sources fixture uses type for both Inbox and conversations and therefore misses the real wire shape. Normalize or recognize the existing conversations shape and protect it with a real-shaped retention regression; do not rely on the synthetic fixture shape.",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

## Independent reproduction

Executed in the frozen checkout with `pnpm exec tsx -e` importing `reviewInput` from `packages/dsh-integration/src/policy/codex-context.ts`. No service was started or mutated. Input was one historical `conversations_result` containing `{message_id:"m",sender:{id:"u",kind:"user"},pa_agent_id:"pa",content:[{type:"text",text:"PRESERVE_ORIGINAL_SCOPE do not merge or deploy"}]}`, followed by 41 `{outcome:"ok",tool_result:"recent"}` rows. Planned action was `{tool:"bash"}`, budget 50000.

| Sender shape | Original scope retained | Evidence omission marker |
|---|---|---|
| actual `kind:user` | false | true |
| comparison `type:user` | true | true |

The controlled comparison isolates the field mismatch from token pressure. This establishes missing evidence; it does not assert that a real reviewer approved an out-of-scope action.

## Limits

The caller's narrow test and synthetic actual-context evidence was reused where relevant. Full local CI and true-model/client journeys were still pending at review time. The first true-model journey's missing mention is recorded by the caller as a failure and is not counted as product acceptance. This review did not operate the running daily instance or start new real services. Implementation/design conformance and outstanding evidence are reported separately in `verification.md`.

## Round 2 — targeted closure

- `review_mode=closure`; `finding_origin_head=3689a8b84ba09e69eae013bb79d93a1c4d1f2010`.
- `validated_at=16798fb3be2e46500ba25c01996f3c615ac29288`; `effective_base=b4ea8f908691d6a309ceb787d4d37d36ec7dfc69`; `effective_through=16798fb3be2e46500ba25c01996f3c615ac29288`.
- Reviewed repair `abdf2afc75f11f38ec2e888cd2f31a9ea3011504`, related test delta `9c5aecd558e1d16c5e5d948c010859a70e0901f8`, and intervening changes. The merge contribution from old base to effective_base consists only of three feat-659 design assets; no product implementation or test changed upstream. R1 full-review conclusions are retained outside this targeted scope.

### Focus finding closure

| Focus | Status | Evidence |
|---|---|---|
| R1 sender.kind/type history retention finding | **closed** | `policy/codex-context.ts:42` now checks `sender.type ?? sender.kind`. `approval-sources.test.ts:202` uses actual history `kind:user` and protects scope plus PA ID after 41 later tool entries. |
| R1 verifier WARNING 2, model interactive constants | **closed** | `work.ts:747` filters only format/catalog_version in the model read/search projection. `personal-sources.test.ts:142` verifies source retained and client `Messaging.message()` wire unchanged. |

Independently executed at the validated head with Node 24.22.1:

```sh
/Users/czj/.npm/_npx/ef8b185be06dfeb4/node_modules/node/bin/node node_modules/vitest/vitest.mjs run packages/dsh-integration/tests/approval-sources.test.ts apps/im-server/tests/personal-sources.test.ts apps/im-server/tests/personal-representation.test.ts apps/im-server/tests/pa-representation-migration.test.ts --maxWorkers=2
```

Result: **4 files / 30 tests passed**, start 20:57:33, duration 593 ms. The additional legacy regression exercises missing representation payload, self decoding, owner identity conflict and confirmed commit retry; the migration fixture now also contains an actual legacy relay row. No further concrete defect was found in this repair/test delta. No source was changed and no running daily instance was operated.

Surviving code findings:

```json
[]
```

This closes the reviewed code findings, not the outstanding independent product/native acceptance gate. See verifier R2 for corrected-delta outcome and evidence limits.
