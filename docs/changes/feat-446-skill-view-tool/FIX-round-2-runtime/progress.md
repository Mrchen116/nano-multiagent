# FIX-round-2-runtime progress

## Baseline

- `PYTHONPATH=src pytest tests/integration/test_agent_runtime_skill_command_integration.py tests/unit/test_agent_runtime.py::test_runtime_skill_command_rewrite_runs_through_normal_pipeline tests/contract/test_skill_commands_contract.py tests/unit/test_cli_product.py tests/unit/test_skill_batch_review.py tests/unit/personal_assistant/test_gateway_process_manager.py tests/unit/personal_assistant/test_gateway_im_connection_behavior.py -x` -> 37 passed before changes.

## Debugging Notes

- `/skill:` root cause: runtime rewrote slash commands to natural language before the loop and never created a tool call. Usage/session refs/visible row only happened if the model later chose `skill_view`.
- F4 live drain root cause: products drained only during startup/session-open; `runtime.enqueue_skill_batch_review()` only updated in-memory queue.
- F4 identity root cause: queue state keyed only by `skill_name`, colliding same-name skills across roots; background prompt named the root but could still be ambiguous in same-name search-order cases.
- Dashboard root cause: Gateway usage RPC read only `<workspace>/.nanoassistant/skills/.usage.json`, while `skill_view` now writes usage to the owning priority-hit root for shared/PA/compat skills.
- F2 transcript backend gap: IM repository scanned only direct `sessions/*.jsonl`, missing nested subagent/session files.

## Implementation

- R1: `/skill:<name>` now parses to a structured command before rewrite, persists the rewritten user turn, then executes `skill_view` through `ToolRegistry.execute` with a synthetic visible assistant tool-call row and tool result row. The normal `skill_view` side effects now run for slash commands: usage bump, current `session_id`, transcript path, and invoked-skill registration for compaction survival.
- R2: `AgentRuntime.enqueue_skill_batch_review()` now keys queued/running state by owning root + skill name and fires an optional product scheduler when a new trigger is accepted. CLI installs the scheduler after session open; Gateway installs it during runtime startup and resolves the owning workspace from session refs before draining. F4 usage refs now carry `transcript_path` so shared-root reviews can load evidence without guessing a workspace path.
- R3: Gateway `node.skills.usage.request` now reads local plus shared PA/compat usage roots and filters shared records to sessions present under the requested agent workspace. IM conversation transcript discovery now uses recursive `sessions/**/*.jsonl` lookup.

## Review Candidate Disposition

- High/overlapping F4 live drain: fixed for CLI and Gateway product paths with regression coverage.
- Background patch target ambiguity: queue/dedupe and prompt identity are now root-aware and include exact `Target SKILL.md`; remaining hardening would require a root/location-aware `skill_manage(patch)` schema, because the tool patch API still accepts `name`/scope rather than an absolute target path.
- Batch review transcript lookup: fixed for new usage refs by recording exact `transcript_path`; IM conversation `source_jsonl_path` also recurses nested sessions.
- F4 queued/running dedupe collision: fixed by root + skill name key.
- `run_skill_maintenance()` shared-root scan: left as explicit semantics. Maintenance remains per-agent workspace-local to avoid a Gateway agent mutating shared PA/compat skills on behalf of other agents; shared usage visibility is fixed in the dashboard path.
- Gateway Skills dashboard shared usage: fixed in backend aggregation.
- Distill `/skill:conversation-skill-distiller` without `skill_view`: runtime deterministic slash loading still requires `skill_view` to be enabled. Product/frontend should disable or surface a clear error when the selected execution agent lacks `skill_view`.
- F2 disabled checkbox/dialog: backend now returns nested `source_jsonl_path` when the transcript exists. If disabled rows can still be checked or the dialog stays silent after a valid path is present, that is frontend selection-state/dialog handling and should be fixed separately.

## Verification

- `PYTHONPATH=src pytest tests/integration/test_agent_runtime_skill_command_integration.py tests/unit/test_agent_runtime.py::test_runtime_skill_command_rewrite_runs_through_normal_pipeline tests/contract/test_skill_commands_contract.py -q` -> 7 passed.
- `PYTHONPATH=src pytest tests/unit/test_cli_product.py tests/unit/test_skill_batch_review.py tests/unit/personal_assistant/test_gateway_process_manager.py -q` -> 12 passed.
- `PYTHONPATH=src pytest tests/unit/personal_assistant/test_gateway_im_connection_behavior.py tests/im_service/unit/test_repositories_user_conversation.py -q` -> 30 passed.
- `PYTHONPATH=src pytest tests/integration/test_agent_runtime_skill_command_integration.py tests/unit/test_agent_runtime.py::test_runtime_skill_command_rewrite_runs_through_normal_pipeline tests/contract/test_skill_commands_contract.py tests/unit/test_cli_product.py tests/unit/test_skill_batch_review.py tests/unit/personal_assistant/test_gateway_process_manager.py tests/unit/personal_assistant/test_gateway_im_connection_behavior.py tests/im_service/unit/test_repositories_user_conversation.py tests/unit/test_skill_view.py tests/unit/test_usage.py -q` -> 64 passed.
