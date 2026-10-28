# Code Review: refactor-671-serialization-contracts

## Metadata

- Reviewer: independent static reviewer; not an implementation author.
- Skill / mode: `change-code-review(full)`; complete unit diff.
- Worktree: `/Users/czj/.codex/worktrees/serialization-contracts/nano-multiagent`.
- Branch: `codex/serialization-contracts`; HEAD confirmed at `validated_at` before review.
- Executed base: `ff326c351d104447028f4b185740ab6d6be55de6`.
- Validated at: `8289e5634b64c64c18d421eff58801b2a2c745b1`.
- Reviewed range: `ff326c351d104447028f4b185740ab6d6be55de6...8289e5634b64c64c18d421eff58801b2a2c745b1`.
- Compatibility capture baseline: `a34af8473c15f1145d6a1dbbc036bc320560f351`.
- Source, tests and design were not modified by this reviewer. Reports are handed to the caller uncommitted.

## Findings

```json
[]
```

No confirmed or plausible actionable defect survived review of this frozen diff. Code review passes; this does not assert completion of the separately required full CI gate.

## Coverage and evidence

| Risk | Review evidence and result |
|---|---|
| Shared encoding ownership and exact implementation | `packages/product-contracts/src/serialization.ts:12,33` preserves the Task/Workflow replacer and configuration pre-traversal implementations. The module has no imports, Buffer, crypto or runtime dependency. `package.json:23` explicitly exports its built JS and types. |
| Actual callers and ambiguous root export | All production `canonicalJson` callers were searched and traced. UTF-8 callers in Task, IM Channels, migration and Workflow use `sortedJsonUtf8`; configuration and IM/PA publication, submission and Inbox identities use `sortedJsonAscii`. The old configuration root export had explicitly shadowed the interactive star export; removal of the unused locale-sorted implementation does not switch any live caller's algorithm. No source `canonicalJson` references remain. |
| Unicode, DEL, recursive and shallow ordering | `serialization.test.ts:5,11` pins nested objects/arrays, numeric/non-ASCII keys, Chinese, emoji, combining characters, U+007F/U+0080/U+2028, lone surrogate, missing/null and native/pre-traversal Date handling. `control.ts:41` retains candidate DEL escaping; `identity.ts:96` composes ASCII encoding with the original DEL rule. `channel-credentials.ts:65` and `device-binding.ts:44` retain their original shallow encoding bodies. No DEL behavior was treated as a new bug or normalized. |
| Independent pre-change comparison | Read the original four pure function bodies from the baseline Git objects, transpiled in memory and compared with built new functions on 12 representative inputs; all 48 comparisons passed. Five captured fixed outputs also matched the old implementations. `output/refactor-671/reviewer-equivalence.json` records the baseline, frozen head and method. The corresponding old function source files have no changes between capture baseline and executed base. |
| Persistent hashes, identities and replay | `approval-configuration.test.ts:67` pins both distinct historic fingerprints and candidate heartbeat bytes; `message-attempts.test.ts:58` accepts the exact old payload; existing PA receipt recovery remains. `workflow-control.test.ts:121` replays the fixed historic Unicode/nested-schema key without starting a child. `WorkflowControl.call:128` keeps the projection, ordinal and SHA-256 unchanged. |
| Credential compatibility and independent byte oracle | `channel-credentials.test.ts:22` opens fixed baseline IM/node envelopes after key reload and rejects changed owner/revision. `control.test.ts:516` runs actual IM seal → actual ChannelKey open and additionally decrypts using captured AAD/plaintext bytes, so JSON.parse or two changing encoders cannot hide drift. The fixture is explicitly synthetic, generated offline at the pre-change baseline and never deployed. Crypto, context strings, versions, nonce/salt generation and AAD projections are unchanged. |
| Package boundaries | Only the three actual consumers gain the declared serialization subpath in the existing allowlist. Production IM does not import Channels; the direct Channels source import is solely the interoperation test. Independent runtime dependency contract run: 13 passed. No Row/ImContext changes or DSH private imports. |

Independent validation on the frozen head: Node 24.22.1, `pnpm exec vitest run` on the eight changed serialization/consumer test files passed **8 files / 56 tests** (`output/refactor-671/reviewer-narrow.log`). `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/contract/test_runtime_dependency_contract.py -q` passed **13 tests**. `git diff --check` on the frozen range passed.

## Context review applicability and limits

The `agent-context-review` applicability check covered the PA Inbox duplicate identity, PA/Global publication identities, interactive snapshots and Workflow completion-prefix selection. Their data projections and downstream assembly/selection/timing are unchanged, and the exact selected encodings remain equal to the original functions. These are internal equivalence changes with no Context delta, so a full Implementation Context Review and provider/model task are not required by this unit. No actual provider capture or model behavior was tested, and no claim about model quality or full product journeys is made.

## CI limitation

At report time, full backend Vitest evidence remains unresolved: the default concurrent run has native-integration timeouts and is still being diagnosed by the caller. This reviewer neither attributes them to this diff nor reports that suite as passed. Build/typecheck/iOS-runtime, frontend tests and Python evidence are recorded in `verification.md`; necessary-CI completion remains pending there. The frontend audit reports 11 existing dependency vulnerabilities (5 high), with no critical severity; the critical-level gate passes and this diff changes no dependency versions or lockfiles.
