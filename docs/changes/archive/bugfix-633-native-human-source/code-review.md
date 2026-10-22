# Code review

- Unit: `bugfix-633-native-human-source`
- Review mode: `full`
- Review round: `1`
- Checkout: `/Users/czj/.codex/worktrees/unit-bugfix-633/nano-multiagent`
- Branch: `unit/bugfix-633`
- Diff range: `8363845c74cff832862e94cde6ec1eeaef7613c6...e5a1522c34c0a04a945d9c2d5bb1a9ea19a079bc`
- Executed base: `8363845c74cff832862e94cde6ec1eeaef7613c6`
- Validated at: `e5a1522c34c0a04a945d9c2d5bb1a9ea19a079bc`
- Reviewer: independent agent, not involved in implementation

## Scope and evidence

Reviewed the complete specified diff against the original report in `fix.md`, including native human source mapping, host identity checks, legacy reads, approval routing/evidence, Workflow input recognition/linkage, readable history, task source linkage, work projection and explicit Skill handling. Checked the actual single-thread input producer and searched runtime/product/frontend consumers for remaining `nano-human` dependencies.

Compared the compatibility adapter with the installed DSH `dsh-tool-skill` implementation: native whitespace-bounded `/name` recognition and the adapter's suppression use the same grammar; native lookup uses the selected provider surface. Confirmed the original Inbox raw-result extraction, pending queue and persistent invocation IDs remain intact. Inbox authority bridging, `nano-system`, invocation-ID redesign, context-window cancellation and Issue #377 remain outside this review's change scope.

Independent validation at the specified head:

```text
pnpm exec vitest run packages/dsh-integration/tests/native-human-source.test.ts packages/dsh-integration/tests/approval-sources.test.ts packages/personal-assistant/tests/source-provenance.test.ts
Test Files  3 passed (3)
Tests       21 passed (21)
Duration    5.63s
```

`git diff --check 8363845...e5a1522` also passed. Reused the caller's broader build/typecheck, security, history, model fallback, Inbox and Guardian validation evidence; did not duplicate the caller's full test run. Runtime evidence uses the installed native DSH with deterministic model fixtures; it does not establish real-model or production acceptance. No product/test code was changed and no service was started by this review.

## Conclusion

No confirmed or plausible actionable findings survived review within the specified scope.

```json
[]
```

## Review round 2: final base synchronization

- Review mode: `full`
- Review round: `2`
- Diff range: `a782cdd3f9f19fa40da6e836857107ca21681825...02308ad8e7766fe4eb9db19e4f93811921a7d6db`
- Executed base: `a782cdd3f9f19fa40da6e836857107ca21681825`
- Validated at: `02308ad8e7766fe4eb9db19e4f93811921a7d6db`
- Checkout and branch: unchanged; clean at review start

Rechecked the complete rebased unit diff and the relevant upstream `8363845..a782cdd` changes from feat-630. The product and test delta under `packages/` has the same stable patch ID in both review rounds: `80d226eef5acc1a3a3d5565c34c0cd076d5b043d`. The DSH integration directory is unchanged between the two validated heads, so R1's source/approval/Skill/runtime evidence remains applicable.

The upstream single-thread change only nests the permission resolution request ID; the direct input producer still preserves human/system attribution and its identity metadata before the DSH boundary. The global task source consumer continues reading the same durable runtime events. Upstream global Inbox recovery still submits system wakes, without granting direct human identity. Channels changes correlate and schedule outer requests without translating the inbound sender or the task source message ID.

Checked the new Work publication chain: global reconciliation still calls `projectWorkEvent`; the local journal retains its payload, WorkSync serializes that journal payload, and the IM Work append path persists it without rewriting trigger/source fields. Consequently, the R1 work-view source assertions remain relevant despite the new upload transport. The existing source-provenance fixture still exercises the actual task source consumer and projection; its single-thread binding does not depend on the new global session authority handshake.

Independent validation at the R2 head:

```text
pnpm exec vitest run packages/personal-assistant/tests/source-provenance.test.ts packages/personal-assistant/tests/single-thread.test.ts
Test Files  2 passed (2)
Tests       16 passed (16)
Duration    1.52s
```

`git diff --check a782cdd...02308ad` passed. The caller owns full build/typecheck/test validation at the new base; this review did not repeat Guardian or the full suite, modify product/tests, start services, or commit files. R1's evidence limits still apply.

R2 conclusion: no confirmed or plausible actionable findings survived the targeted upstream compatibility review or the full rebased unit diff review.

```json
[]
```
