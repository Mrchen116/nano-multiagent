# feat-446-fix-r1-script progress

- Scope: fix `scripts/e2e-up.sh` worktree config isolation so each configured agent keeps
  its own `agent_id` when `workspace_root` is rewritten.
- Change: switched the yq mutation from `.agents[].workspace_root = ... .agents[].agent_id`
  to `.agents |= map(.workspace_root = ... + .agent_id)`, matching the safe pattern already
  used in `scripts/e2e-resilience.sh`.
- Verification:
  - Updated `tests/unit/personal_assistant/test_gateway_im_resilience_e2e_wrapper.py` to run
    the real `scripts/e2e-up.sh` yq path against a temp config containing two agents.
  - Asserted the generated `.gateway-config.yaml` rewrites roots to distinct paths:
    `.gateway-workspace/alpha` and `.gateway-workspace/beta`.
