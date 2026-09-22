# M1 implementation evidence

- Baseline: 2e9c83df9 (code baseline 499774a56 plus this unit's approved documents).
- Implemented concrete ShadowReplyPublisher; composition shares the existing saga store explicitly. MessageDelivery retains frozen projection and ledger. Sync passes typed saga/output/snapshot instead of itself; removed unused _project_images.
- Tests: keep all existing shadow behavior assertions. Rewrite shared fixture construction only; existing tests own HTTP payloads, identity, rotated token, retry and frozen-image admission ordering. No parallel implementation-mirroring suite added.
- Baseline narrow suite: 43 passed before refactor.
- Implemented narrow suite plus composition: `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/personal_assistant/test_gateway_shadow_sync.py tests/unit/personal_assistant/test_gateway_im_relay.py tests/unit/personal_assistant/test_shadow_auth.py tests/integration/test_shadow_reply_images.py tests/unit/personal_assistant/test_gateway_build_runtime.py` → 54 passed (5.55s).
- Ruff affected files and git diff --check passed. Full CI-equivalent checks and independent gates follow on the frozen implementation commit.
