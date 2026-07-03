# feat-446-fix-r1-product — Progress

## R1 — Product reachability and IM boundary hardening

- Context: Round 1 acceptance found four product-path failures: missing Skills/statistics reachability, missing F2 conversation-list entry, `/skill:` not producing `skill_view`, and `default-agent` resolving to `luban` workspace.
- Decision: Keep this fix slice in IM/frontend and minimal IM boundary code. Treat `/skill:` runtime rewrite and e2e config workspace rewrite as handoffs when the root file is outside this worker's ownership.
- Rationale: The dashboard and F2 components already exist but were not explicit enough from the reviewer-used paths. The workspace symptom is explainable by `scripts/e2e-up.sh` rewriting all agent workspaces to the last agent when `yq` is available; this script is outside the slice. IM can still reject mismatched live config responses so one agent's payload cannot be overlaid onto another requested profile.
- Evidence:
  - Tests:
    - `npm run test -- src/features/settings/agents/agent-detail-page.test.tsx src/features/chat/v2/components/conversation-sidebar.test.tsx src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/slash-candidates.test.ts` — 74 passed.
    - `pytest -q tests/im_service/integration/test_agent_config_api.py tests/im_service/unit/test_gateway_handler.py tests/im_service/unit/test_repositories_agent_profile.py tests/unit/personal_assistant/test_gateway_im_config_sync.py` — 85 passed.
    - `npm run build` — passed (`tsc -b && vite build`; existing Vite chunk warnings only).
  - Entry: Agent detail Access card now exposes `View skill statistics`; conversation list right-click now opens `Conversation actions` with `Distill to skill` and preselects the row.
  - Frontend State Matrix: default desktop/mobile checked by browser; selected distill row checked; Skills dashboard list checked with usage data from fake Gateway RPC.
  - Browser QA:
    - `/tmp/feat446-fix-r1-product-agent-skills-desktop.png`
    - `/tmp/feat446-fix-r1-product-agent-skills-mobile.png`
    - `/tmp/feat446-fix-r1-product-distill-menu-desktop.png`
    - `/tmp/feat446-fix-r1-product-distill-menu-mobile.png`
    - `/tmp/feat446-fix-r1-product-distill-select-desktop.png`
    - `/tmp/feat446-fix-r1-product-distill-select-mobile.png`
  - E2E/Regression: Browser QA used isolated IM port 53658, built frontend dist, seeded local DB, and a fake Gateway WS that handled `agent.capabilities.resolve` and `node.skills.usage.request`.
  - Visual/Interaction: Inspected desktop screenshots; Skills dashboard renders usage row and F2 menu/selection states render without overlap.
  - Handoffs:
    - Runtime owner: `/skill:<name>` is currently rewritten in `src/agent/core/agent/skill_commands.py` to natural language and does not force a `skill_view` tool call/tool row/usage increment. Runtime worker should route this command through the `skill_view` tool path and update runtime tests there.
    - Script owner: `scripts/e2e-up.sh` yq rewrite uses `.agents[].workspace_root = "$WORKSPACE_DIR/" + .agents[].agent_id`, which can cross-product agents and explain `default-agent` showing the `luban` workspace. Replace with `.agents |= map(.workspace_root = "$WORKSPACE_DIR/" + .agent_id)` as used by the Python fallback.
- Rollback: Revert this milestone branch merge.
- Commits:
  - `0f81b1e5 fix(feat-446/feat-446-fix-r1-product/R1): make skill paths reachable`
  - `be376c75 test(feat-446/feat-446-fix-r1-product/R1): cover distill menu workflow`
  - `fe350cba fix(feat-446/feat-446-fix-r1-product/R1): type distill entry handler`
