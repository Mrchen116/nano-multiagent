# FIX-round-1-runtime — progress

## Startup

- Read: requested `change-impl-worker/SKILL.md`, `systematic-debugging/SKILL.md`, `SPEC.md`, `COMMENTING_GUIDE.md`, `docs/TESTING_GUIDE.md`, unit `spec.md`, `design.md`, `verification.md`, `acceptance.md`.
- Sync gate: local `unit/feat-446` matched `origin/unit/feat-446` at `c7d23b6e9585a0da3e8ade5fb1b75d7c55acc52b`; created worktree branch `milestone/feat-446-fix-r1-runtime` from `origin/unit/feat-446`.
- Baseline: `PYTHONPATH=src pytest tests/unit/test_skill_view.py tests/unit/test_usage.py tests/unit/test_skill_batch_review.py tests/unit/test_agent_prompting.py tests/unit/agent/test_core_sections.py tests/unit/agent/test_feature_registry.py tests/unit/personal_assistant/test_gateway_im_connection_behavior.py tests/im_service/unit/test_repositories_user_conversation.py tests/im_service/integration/test_agent_config_api.py tests/contract/test_core_no_platform_imports.py -x` -> 127 passed.
- Scope confirmation: backend/runtime only. Frontend acceptance issues I1/I2 are out of this worker's ownership and are not fixed here.

## R1 — Runtime compaction, prompt gating, usage root

Pending.

## R2 — F4 drain and backend review nits

Pending.

## R3 — Final gates and integration

Pending.
