# Verification Report: bugfix-499

> Validation snapshot: `9a6d2e5493220c278242d38ca3c8ed1f64226fb1 → fdb61afae1bf0dfe024333b3829ebf870cfb88bc`

## Summary

Mode: `full`

Delta range: N/A

Focus issues: N/A

requires_full_verification: false

| Dimension | Result |
|---|---|
| Completeness | 1/1 milestone complete |
| Correctness | 3/3 incident requirements covered |
| Coherence | Followed |

The late `fdb61afae` test-double signature update is included in this
snapshot. R8 remains the approved architecture review; the recorded user
waiver applies only to the later non-behavioral bundle-source wording refresh.

## Completeness

- **M1 `lark-skill-bundle`: complete.** The simplified-flow implementation
  record at `M1-lark-skill-bundle/progress.md` records the fixed decisions,
  source comparison, focused checks, rollback, and the outstanding real-fixture
  product gate. Its implementation is present in the scoped package resources,
  configuration owners, managed activation, and regression suites.
- **No frontend prototype/reference contract:** N/A. The design's Feishu
  runbook is a real external-channel product-review gate, not a mockable
  verifier substitute. It remains explicitly outstanding in the implementation
  record rather than being counted as completed verification evidence.
- **Delta scope:** both delta files describe the implemented observable changes:
  complete Feishu Lark capability discovery/allowlists in
  `specs/gateway/agent-capabilities.md`, and current-chat Gateway reply
  ownership in `specs/gateway/external-channels.md`. They have not yet been
  merged into canonical specs; that is the later corrected-delta/closure step.

## Correctness

| Requirement / Scenario | Implementation evidence | Regression evidence | Status |
|---|---|---|---|
| Complete Lark capability discovery; current CLI/auth guidance | `src/personal_assistant/builtin_skills/lark_bundle.py:6-41` is the unique 27-skill manifest; `builtin_skills/bootstrap.py:39-54` installs complete directories without overwriting local skills; `lark-shared/SKILL.md:11-145` provides `lark-cli` setup, user identity, and authorization recovery instructions. The packaged tree matches the current global `lark-*` directory set; only the two intentional D3 `SKILL.md` adaptations differ. | `test_builtin_skill_bootstrap.py:60-90,104-158` checks manifest/resource agreement, complete installation, discovery, and prompt projection; focused suite passed. | covered |
| Explicit Feishu allowlists receive the bundle exactly once; empty lists retain default discovery | Static startup uses `config/local_store.py:645-714`; managed activation uses `gateway/channel_manager.py:155-192` and `gateway/managed_channel_control.py:144-157`; remote explicit profiles use `gateway/agent_config_sync.py:268-407`. Each preserves existing order, appends only missing entries, and leaves an empty list unmaterialized. | `test_gateway_launch.py:200-271`, `test_channel_manager.py:264-283`, and `test_gateway_im_config_sync.py:640-724` cover static/managed explicit, idempotent, and empty-list paths; focused suite passed. | covered |
| Static IM mirror ingress cannot erase the bundle; current-chat reply stays Gateway-owned; independent IM/event actions retain their boundary | The shared ingress check is invoked after each stale-version guard in `gateway/agent_config_sync.py:134-160,419-442,459-510`; reconnect isolates a failed PATCH to its agent. `builtin_skills/lark-im/SKILL.md:13-19` reserves normal current-chat replies for Gateway and permits direct IM only for an explicitly different chat. `builtin_skills/lark-event/SKILL.md:13-18` limits event consumption to explicit independent automation. The unit does not alter runtime delivery. | `test_gateway_im_config_sync.py:727-815`, `test_gateway_reconcile_on_connect.py:351-426`, and `test_gateway_reconcile_callback.py:204-297` cover realtime/reconnect convergence and failure isolation. Existing delivery protection in `test_external_visible_delivery.py` and `test_gateway_relay_lifecycle.py` passed (39 tests). The isolated real-Feishu journey remains for `change-reviewer` per the approved Runbook. | covered |

Executed checks:

- `pytest` focused capability/configuration suite plus managed-control seam: **59 passed**.
- Existing Gateway delivery protections: **39 passed**.
- `pytest tests/contract/test_personal_assistant_package_contract.py tests/contract/test_agent_sdk_boundary_contract.py`: **4 passed**.
- `ruff check` on all changed Python source/tests, `scripts/docs-check`, and
  `git diff --check`: passed.

## Coherence

| Design decision | Followed? | Evidence |
|---|---|---|
| D1 — package a deterministic Lark snapshot; do not add `~/.agents/skills` as a runtime root | Yes | The manifest is isolated in `builtin_skills/lark_bundle.py:6-41`; all 27 resource directories are package data and the generic installer remains directory-level/non-overwriting at `builtin_skills/bootstrap.py:39-54`. No product root change is in the unit diff. |
| D2 — one manifest, explicit-only activation, empty-list semantics, and shared static profile ingress | Yes | Static provisioning consumes `lark_skill_names()` at `config/local_store.py:681-714`; managed policy and control consume the same interface at `gateway/channel_manager.py:155-192` and `gateway/managed_channel_control.py:150-154`; both IM ingress paths share `_ensure_static_feishu_bundle()` at `gateway/agent_config_sync.py:146-155,419-442,494-503`. |
| D3 — document the two known channel conflicts without creating another delivery path | Yes | The only snapshot divergences are the declared boundary paragraphs in `lark-im/SKILL.md:13-19` and `lark-event/SKILL.md:13-18`; no runtime-delivery module was changed. Existing Gateway delivery tests passed. |
| Existing architecture and PA-to-SDK boundary | Yes | All executable changes remain inside `personal_assistant`; new imports are PA-local bundle imports. `test_personal_assistant_package_contract.py` and `test_agent_sdk_boundary_contract.py` passed. |

## Issues

### CRITICAL (must fix before PR)

None.

### WARNING (must fix before PR)

None.

### SUGGESTION (optional)

None.

All checks passed. Ready for PR.
