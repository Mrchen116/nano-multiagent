# FIX-round-1-runtime — progress

## Startup

- Read: requested `change-impl-worker/SKILL.md`, `systematic-debugging/SKILL.md`, `SPEC.md`, `COMMENTING_GUIDE.md`, `docs/TESTING_GUIDE.md`, unit `spec.md`, `design.md`, `verification.md`, `acceptance.md`.
- Sync gate: local `unit/feat-446` matched `origin/unit/feat-446` at `c7d23b6e9585a0da3e8ade5fb1b75d7c55acc52b`; created worktree branch `milestone/feat-446-fix-r1-runtime` from `origin/unit/feat-446`.
- Baseline: `PYTHONPATH=src pytest tests/unit/test_skill_view.py tests/unit/test_usage.py tests/unit/test_skill_batch_review.py tests/unit/test_agent_prompting.py tests/unit/agent/test_core_sections.py tests/unit/agent/test_feature_registry.py tests/unit/personal_assistant/test_gateway_im_connection_behavior.py tests/im_service/unit/test_repositories_user_conversation.py tests/im_service/integration/test_agent_config_api.py tests/contract/test_core_no_platform_imports.py -x` -> 127 passed.
- Scope confirmation: backend/runtime only. Frontend acceptance issues I1/I2 are out of this worker's ownership and are not fixed here.

## R1 — Runtime compaction, prompt gating, usage root

- Context: Reviewer found skill reinjection only lived in `Kernel.compact()`, while threshold/overflow compaction used runtime paths. Prompt listing also advertised `skill_view` even when active tools excluded it, and usage for PA/shared hits was written to the current agent root.
- Decision: Runtime now owns skill reinjection. `AgentLoop` asks runtime for a reinjection message during threshold compaction and inserts it into the live post-compact prompt; `AgentRuntime._compact_session()` writes the same message for manual/overflow compaction. SDK `Kernel.compact()` delegates only to runtime to avoid duplicate appends. Skill usage root is resolved from the matched skill location's owning search root. Available-skills listing receives a `skill_view_enabled` flag and renders no unavailable tool name when false.
- Rationale: The runtime is the common path for automatic compaction and manual compaction. Root ownership must follow the same registry priority hit that supplied `location`, otherwise dashboard/F4 can target the wrong sidecar.
- Evidence:
  - Red: `PYTHONPATH=src pytest tests/integration/test_compaction_runtime_integration.py tests/unit/test_skill_view.py tests/unit/test_agent_prompting.py tests/unit/agent/test_core_sections.py -x` -> failed at `test_threshold_compaction_reinjects_viewed_skill_into_live_prompt`, no `<system-reminder>` in post-compaction prompt.
  - Green: same command -> 72 passed.
  - Entry: integration tests exercise runtime threshold and overflow compaction through `AgentRuntime.run`; unit tests cover SDK manual delegate, prompt allowlist gating, and priority-hit owning root usage.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: permanent backend regression tests in existing unit/integration files.
- Rollback: revert `767b766e` and `29576e4e`.
- Commits: C1=`29576e4e`, C2=`767b766e`, C3=pending.
- Next: R2 F4 drain and backend review nits.

## R2 — F4 drain and backend review nits

Pending.

## R3 — Final gates and integration

Pending.
