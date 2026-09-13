# Code Review — feat-554

## Full review, round 1

- `executed_base`: `94338a2a7d2e01b7868648895e6cfdcf0f6c53f4`
- `validated_at`: `1f14e77db`
- `review_mode`: `full`; `diff_range`: `94338a2a7...1f14e77db`
- Independent finder: `/root/code_finder`; independent candidate verifier: `/root/code_candidates_verify`. Neither edited implementation.

| Finding | Independent confirmation | Disposition |
|---|---|---|
| P2 ordinary human direct title showed receiver's own name | Alice and Carol each contact Bob: Bob saw two chats named Bob; explicitly renamed Project note remained shared | Fix viewer projection only for uncustomized ordinary human directs |
| P3 public Agent rail lost node alias | Actual Nodes PATCH saved Office Laptop, but Contacts returned Raw MacBook; React AgentRow rendered raw name | Preserve existing alias as the public device label |

No other confirmed findings survived full coverage. Optional speculative changes were not requested.

## Patch and closure, round 2

- `validated_at`: `a62b98d45991b47a0a874403e6625c58142cdd6a`
- `executed_base`: unchanged
- `review_mode`: `patch + closure`; `fix_delta_range`: `1f14e77db..a62b98d45`
- Includes migration Markdown calibration, the two fixes, and product review's missing mobile Policies entry.

Finder independently reviewed the entire narrow delta; surviving findings: `[]`. Both original findings are closed. Independent candidate verifier performed fresh HTTP checks: Bob's list/detail/sync showed Alice or Carol, explicit shared rename remained, special direct_key=NULL titles remained unchanged. Fork/distill creation paths retain their titles; 13 related tests passed. Actual node alias save was returned to both owner and another account; clearing alias restored raw node name. AgentRow renders the label on desktop/mobile; 14 existing row tests passed. Mobile Policies uses its actual registered route, existing English/Chinese strings and a separate icon row; the 3 MePage tests passed.

The source delta does not alter membership, credentials, permission routing or PA execution. Full review's unaffected findings and coverage are retained through this patch. Product acceptance remains a separate gate; this report does not claim browser product acceptance or production migration.
