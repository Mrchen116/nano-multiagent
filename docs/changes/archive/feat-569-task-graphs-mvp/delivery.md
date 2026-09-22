# Delivery record

## Final integration and gate validity

- Implementation: `21f79e3d8`; independent static Round 2: `29fca728d`; independent product Round 2: `45f6e2fb4`. Both are PASS, with no remaining findings. Product S01–S20 and prototype P1–P6 are covered by executed or explicitly retained evidence.
- Effective base: `origin/main=2e9c83df99ba1b9313dbea7c449ed43635e7ee59`, merged in `d9e289f7c`. Since the original `499774a56` baseline, the incoming main delta only adds the `refactor-570` motivation, design, design-review and milestone skeleton. It does not alter any runtime, UI, test, or feat-569 requirement.
- Gate 2 Round 3 remains valid: approved target design unchanged; latest note/list total clarifications were reconciled against implementation by the independent verifier.
- Static code review and verification retain their full review through `cb45a06a5`, supplemented by the targeted `2126ccab0..21f79e3d8` navigation review. Product acceptance retains its first-round runtime snapshot `99f6e1633`, supplemented by actual Round 2 frontend `21f79e3d8`.
- Metadata clarification: acceptance Round 2's `executed_base=99f6e1633` names the inherited integrated runtime snapshot. Under the workflow's main-baseline definition, execution began with `origin/main=363eefc5d`; this applies to the static and product revalidation. `effective_base=2e9c83df9` after final sync. The exact final archive head (`effective_through`) is recorded in the PR because the archive commit cannot include its own hash.
- Changes after the reviewed implementation are reports, selected browser evidence, canonical text copied from the reconciled deltas, index/architecture summaries, and whole-unit archive with rebased outgoing links. These mechanical changes do not invalidate the three executed implementation gates.

## Canonical ownership and milestone closure

The IM and Gateway task-graph areas preserve all 6 + 4 reconciled Requirements, with the package indexes, global docs map and SPEC owner boundary updated. M1's W1–W5/W7 are supported by source and regression tests; W6 is supported by independent desktop/mobile and real Agent/Feishu journeys; W8 closes with canonical merge, whole-unit archive, the final local checks and isolated-runtime cleanup. Current behavior belongs to the canonical areas; this unit preserves the original imported spec/design/prototype, all review rounds, deltas, implementation and selected evidence.

[Local and real-stack validation](M1-task-graphs/evidence/integration.md), [independent verification](verification.md), [product acceptance](acceptance.md), [code review](M1-task-graphs/code-review.md), and [curated browser evidence](M1-task-graphs/evidence/browser/README.md) provide reproducible checks and the limits of each kind of evidence. Remote CI status is recorded against the delivered PR head.

## Final local checks and runtime cleanup

After canonical merge and archive: `scripts/docs-check` passed (238 maintained sources / 75 routes); Ruff check and format passed (1096 files); `git diff --check` passed; the archive gate explicitly run with `unit/feat-569-task-graphs` confirmed this unit is uniquely archived (the actual Codex branch prefix remains `codex/`). Earlier Python CI results remain valid because subsequent implementation changes are frontend-only; the final frontend suite passed 777 tests and TypeScript/Vite build passed.

The owner ran `scripts/e2e-down.sh` for this exact worktree and removed tmux session `nano-task-graphs-569`. IM port 56231 is released and both service PID files are gone. Test signing/credential/config copies were removed by the runbook. Raw isolated sessions, service logs and databases moved to private local directory `/tmp/feat569-runtime-_wq0ncvt` for traceability; none are committed. The old runtime paths in earlier reports describe where checks actually ran. Worktree removal follows pushed archive and green PR CI. Main's five pre-existing tracked modifications were SHA-256 compared with the initial sync snapshot and preserved byte-for-byte.

## Open-PR follow-up: dependency layout

After the initial delivery, the user requested that the isolated stack be restarted for hands-on testing, then requested left-to-right dependency layers with parallel tasks in the same column and explicitly accepted an open-source layout library. The existing worktree and test data were retained. The earlier cleanup above remains a historical event; the isolated services at `http://127.0.0.1:56231` are now running for the user and must remain available until that testing finishes.

Implementation `24bb6faad681c859f60388dcee1cd585e4575739` uses Dagre to order and route the existing direct edges. Tasks occupy their earliest prerequisite layer; same-column tasks have no dependency between them. The update preserves direct cross-column edges, exploration derivation, explicit status, navigation, tool and authorization semantics. The clarified layout contract is recorded in the canonical IM spec, corrected delta and appended design decision.

Independent static Round 3 (`fc1e21254`) and product Round 3 (`51e0167bb`) both pass with zero findings. Their `validated_at` is `24bb6faad`; `executed_base` and `effective_base` remain `2e9c83df9`. Product P2/P3/P4 and S04/S09/S19 were re-exercised on desktop and mobile; unaffected earlier gates remain valid as explicitly documented in the reports. Changes after `24bb6faad` are only reports and selected evidence; final `effective_through` is recorded on PR #313.

The regression reproduced the previous crossed independent branches, then passed with the new layout. The focused suite passed 8 tests, the full frontend suite passed 779 tests, and TypeScript/Vite build, critical dependency audit, docs check and diff check passed. All four remote CI checks passed at `24bb6faad`; the final report/evidence head is checked separately on the PR. See [integration evidence](M1-task-graphs/evidence/integration.md) and [Round 3 screenshots](M1-task-graphs/evidence/browser/README.md#round-3-dependency-layout).
