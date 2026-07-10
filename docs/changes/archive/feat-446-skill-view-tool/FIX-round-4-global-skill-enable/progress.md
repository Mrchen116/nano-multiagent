# FIX-round-4-global-skill-enable Progress

## 2026-07-09

- Context: Product review found a newly created skill appears in the Agent configuration page but stays disabled/gray, and the older `pa` scope name is too product-internal for users. The desired behavior is that a user-created agent skill is enabled for that agent by default, while a user-created global skill is enabled for all agents by default.
- Decision: Keep `skill_manage` product-neutral and return structured create metadata. PA Gateway observes only successful `skill_manage(create)` results through a narrow `skill_created` realtime event, validates the root against the executing agent or configured global root, then updates IM/local config for affected agents. Existing kernel sessions are dropped for next-use refresh but their current system prompts are not hot-mutated.
- Boundary: Unset `agent.skills` keeps the existing "all discoverable skills" behavior and is not expanded into a materialized full list. Explicit empty `skills=[]` remains a deliberate "no skills enabled" state. Historical existing skills are not auto-enabled by directory scans.
- Implementation evidence:
  - `skill_manage(create)` now accepts `scope="agent"|"global"` and returns `success/action/name/scope/location/skill_root/message`.
  - Session metadata carries the enabled `skills` allowlist when it is explicitly configured; `skill_manage(list)` and `skill_view` respect that visibility.
  - Gateway handles `skill_created` events by appending the created skill to non-empty allowlists, dropping sessions for unset allowlists, and syncing IM agent config.
  - F2 distillation UI and `conversation-skill-distiller` guidance now use `target_scope: agent|global`.
- Verification:
  - `PYTHONPATH=src pytest -q tests/unit/test_skill_manage_tool.py tests/unit/test_skill_view.py tests/unit/platform/hooks/test_realtime_stream_events.py tests/unit/personal_assistant/test_tool_end_detail_passthrough.py tests/unit/personal_assistant/test_gateway_im_config_sync.py` — 88 passed.
  - `PYTHONPATH=src pytest -q tests/unit/personal_assistant/test_gateway_reconcile_on_connect.py` — 4 passed.
  - `PYTHONPATH=src pytest -q tests/unit/test_skill_view.py` — 11 passed.
  - `PYTHONPATH=src ruff check src/agent/core/agent/runtime.py src/agent/core/skills/root_resolver.py src/agent/platform/hooks/builtins/realtime_stream.py src/agent/platform/tools/builtins/skill_manage.py src/agent/platform/tools/builtins/skill_view.py src/agent/sdk/kernel.py src/personal_assistant/main.py src/personal_assistant/product.py tests/unit/test_skill_manage_tool.py tests/unit/test_skill_view.py tests/unit/platform/hooks/test_realtime_stream_events.py tests/unit/personal_assistant/test_tool_end_detail_passthrough.py tests/unit/personal_assistant/test_gateway_im_config_sync.py tests/unit/personal_assistant/test_gateway_reconcile_on_connect.py` — all checks passed.
  - `cd src/IM/frontend && npm test -- --run src/features/chat/v2/chat-workspace.integration.test.tsx` — 37 passed.
  - `cd src/IM/frontend && npm test -- --run src/features/settings/agents/agent-detail-page.test.tsx` — 27 passed.
  - `ruff check .` — all checks passed.
  - `ruff format --check .` — 761 files already formatted.
  - `PYTHONPATH=src pytest -m "not e2e"` — 3401 passed, 1 skipped, 22 deselected.
  - `cd src/IM/frontend && npm run test` — 613 passed.
  - `cd src/IM/frontend && npm run build` — passed with existing Vite dynamic/static import and chunk-size warnings.
  - `git diff --check` — passed.
