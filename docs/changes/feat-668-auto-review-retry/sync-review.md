# Final synchronization and validation invalidation

## Provenance and unique unit identity

- Original independent baseline:5454f3140f9c92532c690db8dec80b9f77080384. All initial independent gates formally passed before the first history fetch; preserved closure commit:da2dfe96550018e49c4cffe9f88689ea38ceba85.
- First final-stage `git fetch --unshallow origin main` succeeded. Integrated main:c4ebad992ae99e75ee9c3fca88b3eab43abd9ea5,461 commits and948 changed files beyond original baseline. No early future-history fetch occurred.
- Main contains no policy/retry.ts and its ordinary approval still performs one complete strategy. The task is not a duplicate implemented feature, but the approval/runtime context has materially changed.
- Main already owns `docs/changes/feat-625-auto-review-bounded-retry`. Only its path was inspected; its design/old evidence was not used as an implementation answer. It remains untouched.
- The task's independently authored `feat-625-auto-review-retry` collided by numeric ID. The repository's atomic `next_unit_id.py feat` allocated **feat-668**. Only this task's directory moved to `docs/changes/feat-668-auto-review-retry`; branch remains the authorized `codex/feat-625-ab-e2e`. Historical SHA, execution rounds and results are retained, not rewritten as668 executions.

## Permission-sensitive conflict decisions

Source conflicts were limited to policy/approval.ts, classifier.ts and codex.ts; associated type/tests auto-merged. Executor resolves all fixes directly; no repair worker.

| Area | Current-main invariant retained | Retry integration |
|---|---|---|
| Ordinary approval evidence | Effective conversation history, current source provenance, manual approvals and precise action; no separate full-owner-database authorization payload | Freeze current-main evidence once per original review; same frozen evidence across bounded attempts |
| Human/source and task-control routing | isHumanSource and current task-execution/task-change routing; normalized public message arguments; internal context tool behavior | No new source label confers authority, technical failures preserve existing fallback |
| PA disclosure | Host-bound personal scope/ancestor checks; frozen audience, payload, source exclusions and recipient restrictions; independent disclosure policy/parser | Existing disclosure review is not wrapped in tool retry and does not receive a new automatic retry allowance |
| Guardian purpose | Separate tool/disclosure cache keys, native guidance isolation, read-only inspection and supported configured effort | Tool cancellation invalidates only tool cache; configuration/disposal release still invalidates both purposes |
| Budgets/errors | Main's evidence rebuild and model effort selection preserved | Tool review keeps fresh90s attempt, CC30/60 stages, structured failures and available child usage; disclosure retains native90s AbortSignal deadline |

The exact removal of the merge-leftover `pa.authorization` call was initially refused by the normal edit permission check. No alternate-tool, identity, whole-file or merge-strategy bypass was attempted. Other equivalent personalAuthorization prompt/action removal also remained stopped. After the owner explicitly authorized compatibility with c4ebad's existing effective-context and disclosure chain, the **same exact edit** passed the normal check. Only then were equivalent obsolete merged fields removed. This is not a change to the executing Harness's permissions or a rollback of current-main security.

The identifier `pa.authorization` still exists in the product bridge contract/compatibility handler; it is the **ordinary Auto review invocation and extra evidence field** that current main removed, not a claim that every API identifier disappeared.

### Read-only source evidence for that decision

- Current-main `ApprovalSources.transcript`/`history` (sources.ts53–66,96–185 before integration renumbering): derives effective messages, scoped instructions, trusted human/source labels and exact pending action. It does not fetch the owner's complete database to invent authority.
- Current-main index.ts535–551 checks personal identity/binding/ancestor scopes;562–583 handles pa.review(action) through personalReviewAction and reviewDisclosure, with current lineage evidence. personal-security.ts42–70 validates/project frozen audience, action and restrictions.
- Current-main codex.ts separates tool/disclosure keys, policy and strict parser; pre-step filtering isolates native reviewer guidance, inspection tools stay host-owned/read-only.
- Existing main personal-security.test.ts10–58 explicitly verifies authorityReads0/no database-history pollution while authorized ordinary operations succeed and unauthorized/restricted/invalid identity operations fail. This test is evidence of current behavior, not authorization to override a tool refusal.
- sources.ts, index.ts, personal-security.ts and that existing test were independently compared to origin/main with `git diff --quiet` and matched before integration edits. None of those current-main source files is modified by this feature.

## Gate invalidation matrix

| Gate | Initial evidence retained for | Current integrated tree requirement |
|---|---|---|
| Design | Original bounded retry policy, exact-action/no-new-authorization constraints, budget and effect limits | Main compatibility decisions documented here; no changed retry requirement |
| Code review / Context implementation review | Historical original diff finding-free result and synthetic evidence | **FULL rerun** against c4ebad…integrated HEAD; inspect authority chain, two purposes, cancellation and updated composed Context |
| Verifier | Historical native budgets/cache/effect tests with exact prior version | **FULL rerun** for integrated implementation and corrected delta; verify new native artifacts and main security regression coverage |
| Product reviewer | Original Sol/Luna journey,30 cases and36call/62attempt associations, only on original tree | **FULL rerun** applicable real entry on integrated frozen runtime; main changed shared runtime/provenance/PA disclosure, no automatic inheritance |
| Local CI | Historical494-test pass and other old-tree checks | All current CI-equivalent commands on final integrated tree |

No effective_through is claimed yet. Initial PASS is historical and cannot authorize archive/Ready PR without integrated-tree gates.

## Integration validation history

1. Frozen dependencies installed successfully with supplied Node24.22.1; current-main package/runtime versions retained.
2. Initial integrated build and typecheck passed. First focused run:12 files,73 passed/7 failed. Failures exposed integration/fixture deltas and were not hidden by dropping cases:
   - old native human-source matcher no longer recognized main's actor-bearing user source;
   - two CC-only fixtures inherited main's now-Codex default rather than explicitly selecting nano;
   - preparation cancellation fixture still depended on the obsolete pa.authorization seam;
   - a disclosure lifecycle stub has no stream, but new tool-attempt collection unnecessarily decoded it even without a collector;
   - changing the shared deadline primitive broke main's blocked-disclosure fixture and would broaden disclosure behavior;
   -100ms accelerated tool fixture sometimes expired during native startup before all expected reviewer instances existed.
3. Corrections: match native actor-bearing user/heartbeat sources; explicitly pin CC-only fixtures; hold effective inherited preparation instead of obsolete owner-database call; collect stream usage only when an attempt collector exists; preserve disclosure's native AbortSignal.timeout while retaining structured tool deadlines; widen only synthetic wall scheduler100→500ms (production remains90000ms), keeping exact creation/disposal and six-budget assertions.
4. Added purpose-isolation assertion to existing lifecycle test: releasing canceled tool scope disposes its tool cache, preserves disclosure checkpoint, and a new tool review begins full. No duplicate suite.
5. Corrected narrow run: dsh-integration rebuild plus8 files/46 tests **PASS**,20.67s. Includes retry arithmetic/native/cancellation, Guardian lifecycle/native blocked-I/O, personal-security, personal child delivery and native human-source boundaries. Other initial focused approval/source/workspace tests had already passed but full integrated regression is still required.

6. Integrated native evidence regeneration passed2 files/4 tests on334bf622; preserved as `M1-auto-review-retry/integrated-native-context-evidence.json` and `integrated-guardian-context-evidence.json`, without overwriting original-tree history.
7. First full integrated Node run:788/789 passed; unchanged-main knowledge-policy step-limit poll failed. Same unchanged file independently reran5/5 PASS. A full rerun overlapping frontend installation/build produced784/789: native deadline cleanup confirmation plus unchanged-main model-policy, supervisor and task-execution timing failures. Neither run is recorded as PASS. The failed supervisor fixture left a CPU-active native process; exact executable, fixture cwd and process start were verified, then that task-owned orphan was stopped (TERM did not suffice; KILL and absence verification followed). A fresh full run without other task-owned heavy runners is required; production budgets and assertions remain unchanged.
8. Integrated Python standalone70 PASS/32 deselected, ruff check and88 format checks PASS; packaged iOS interactive-runtime checks PASS. Frontend frozen install, shared-contract build, critical audit gate,108 files/1031 tests and production build PASS. Audit retains11 existing noncritical vulnerabilities (4 low/2 moderate/5 high); no dependency upgrade or suppression was applied.

## Remaining delivery sequence

Freeze completed merge and updated synthetic evidence; run full applicable independent gates on the new base/runtime. Then assess corrected delta, merge canonical contract, run current local CI, archive only this unit, create authorized Ready PR and observe required remote CI. Preserve old main unit and all original evidence. Own prior stack/proxy was stopped before sync; any new acceptance stack must use only this checkout's isolated resources and be cleaned afterward.
