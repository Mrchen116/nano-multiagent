# feat-446-fix-r1-product — Progress

## R1 — Product reachability and IM boundary hardening

- Context: Round 1 acceptance found four product-path failures: missing Skills/statistics reachability, missing F2 conversation-list entry, `/skill:` not producing `skill_view`, and `default-agent` resolving to `luban` workspace.
- Decision: Keep this fix slice in IM/frontend and minimal IM boundary code. Treat `/skill:` runtime rewrite and e2e config workspace rewrite as handoffs when the root file is outside this worker's ownership.
- Rationale: The dashboard and F2 components already exist but were not explicit enough from the reviewer-used paths. The workspace symptom is explainable by `scripts/e2e-up.sh` rewriting all agent workspaces to the last agent when `yq` is available; this script is outside the slice. IM can still reject mismatched live config responses so one agent's payload cannot be overlaid onto another requested profile.
- Evidence:
  - Tests: pending.
  - Entry: pending.
  - Frontend State Matrix: pending.
  - Browser QA: pending.
  - E2E/Regression: pending.
  - Visual/Interaction: pending.
- Rollback: Revert this milestone branch merge.
- Commits: pending.
