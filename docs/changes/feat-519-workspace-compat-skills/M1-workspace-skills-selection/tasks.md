# feat-519-M1 Tasks

## Goal

Deliver workspace Claude/Codex Skill compatibility and truthful grouped Skill selection as one end-to-end slice across the SDK/kernel, PA/CLI product composition, Gateway/IM configuration, and Web IM.

## Baseline

- Executed base: `1d0c2cb45`
- Python focused baseline: 27 passed.
- Frontend focused baseline: 37 passed; existing React `act(...)` warnings only.

## Implementation checklist

- [x] Add an ordered workspace Skill layout to `agent.sdk` and share one root sequence across list, preview, runtime, `skill_view`, and `skill_manage` reads while retaining the native writer root.
- [x] Configure PA and Coding CLI with their required workspace/global root priority and add shared-only capability discovery.
- [x] Add PA capability `source_group` and preserve old capability payload fallback.
- [x] Persist `skills_selection_mode` across IM profiles, Gateway YAML/config operations/live snapshots, session projection, Feishu reconciliation, and `skill_created` mutations.
- [x] Make SlashPicker and runtime distinguish default discovery from explicit allowlists, including explicit empty.
- [x] Implement default-to-explicit grouped tri-state selection in create/detail pages with keyboard/focus/mobile behavior and invisible-name preservation.
- [x] Add focused Python, contract, repository/API, Gateway, and frontend tests.
- [ ] Run focused validation, real CLI/PA/browser journeys, full verifier/reviewer/code-review gates, CI-equivalent checks, canonical spec merge, and archive.

Worker-side automated validation is complete; real product journeys, independent gates,
canonical spec merge, and archive remain owned by the orchestrator.

## Test strategy

- Resolver unit/integration fixtures cover ordered roots, same-name first-root wins, missing directories, shared-only discovery, and writer-root stability.
- Product tests assert exact PA/CLI layouts and Gateway source projection.
- IM/Gateway tests cover legacy absent mode, default, explicit non-empty, explicit empty, automatic writers, operation recovery, API normalization, runtime projection, and SlashPicker parity.
- Frontend tests cover default initial rendering, first edit conversion, group none/partial/all, individual follow-up, hidden names, old payloads, and narrow layout semantics.
- Reviewer runs real Coding CLI and isolated PA/IM browser journeys; automated tests are not treated as product acceptance.

## Exit criteria

- The single M1 reviewer and worker exit criteria in `design.md` are met.
- `change-verifier`, `change-reviewer`, and `change-code-review` all pass with no unresolved blocking findings.
- Canonical specs are merged, the unit is archived, local CI-equivalent commands and required GitHub checks pass, and the PR is Ready for Review.
