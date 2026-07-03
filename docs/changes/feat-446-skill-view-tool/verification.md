# Verification Report: feat-446 skill-view-tool

- unit_id: `feat-446`
- review_round: 1
- verification_mode: full
- validated_head: `6df4fdeb6e0edd1c9d844ca71313058264ebca4e`
- verdict: FAIL
- issue_counts: critical=2, warning=2, suggestion=0

## Scope

Verified the unit integration branch against:

- `docs/changes/feat-446-skill-view-tool/spec.md`
- `docs/changes/feat-446-skill-view-tool/design.md`
- delta specs under `docs/changes/feat-446-skill-view-tool/specs/`
- M1/M2/M3/M4 `tasks.md` and `progress.md`
- project architecture/spec/testing/commenting rules (`SPEC.md`, `COMMENTING_GUIDE.md`, `docs/TESTING_GUIDE.md`, evergreen subsystem specs)

This was a static code/docs verification. I did not run tests, to keep the verifier pass read-only except for this report.

## Task Status Cross-Check

The milestone task files mark all checklist items complete:

- M1 skill-view-core: 9/9 complete
- M2 curator-f4: 11/11 complete
- M3 f2-distill: 15/15 complete
- M4 dashboard: 9/9 complete

Several core pieces are present and coherent: `skill_view` is a real built-in tool, `skill_manage` no longer exposes `view`, PA/default tool projections include `skill_view`, usage sidecar writes are idempotent by call key, Curator state transitions exist, the distiller skill is packaged as a PA built-in, and IM/Gateway/frontend dashboard paths are implemented.

The branch still fails verification because two promised runtime behaviors are only partially wired and will not occur in normal production paths.

## Critical Issues

### CRITICAL-1: Compaction survival only works for manual `Kernel.compact()`, not real automatic compaction paths

The spec requires any conversation compaction after `skill_view` to re-inject previously viewed skill content as a `<system-reminder>`:

- `docs/changes/feat-446-skill-view-tool/spec.md:297-305`
- `docs/changes/feat-446-skill-view-tool/spec.md:309-314`
- `docs/changes/feat-446-skill-view-tool/specs/kernel/spec.md:22-24`

The implementation appends the skill re-injection reminder only in the public SDK wrapper:

- `src/agent/sdk/kernel.py:910-935` calls `_append_skill_reinjection_reminder(...)` after `runtime.compact(...)`
- `src/agent/sdk/kernel.py:1457-1484` builds and appends the synthetic `<system-reminder>`

However, the actual runtime compaction paths used during normal agent execution bypass that wrapper:

- overflow recovery calls `AgentRuntime._compact_session(...)` directly at `src/agent/core/agent/runtime.py:701-710`
- proactive threshold compaction is triggered inside the loop at `src/agent/core/agent/loop.py:296-314`
- `AgentLoop._maybe_compact(...)` rewrites in-memory LLM messages to only the summary and returns a summary message, with no skill re-injection at `src/agent/core/agent/loop.py:874-962`
- `AgentRuntime._compact_session(...)` persists compact boundary + summary and returns, with no skill re-injection at `src/agent/core/agent/runtime.py:2066-2198`

The existing test covers only the SDK/manual path (`tests/unit/test_skill_view.py:224-288`). It does not cover threshold or overflow compaction during an actual run.

Impact: after a long conversation triggers normal compaction, the model can lose the SKILL.md instructions it loaded via `skill_view`, violating a central feat-446 requirement.

Required fix: move skill re-injection into the shared runtime compaction persistence/update path, or add a core/runtime callback invoked by every compaction path. Add tests for threshold and overflow compaction, not only `Kernel.compact()`.

### CRITICAL-2: Per-skill F4 batch review is enqueued but never drained by production Gateway/CLI paths

The spec and design require batch review to trigger when `skill_view` crosses the threshold:

- `docs/changes/feat-446-skill-view-tool/spec.md:479-488`
- `docs/changes/feat-446-skill-view-tool/spec.md:514-526`
- `docs/changes/feat-446-skill-view-tool/design.md:234-245`

The implementation does enqueue the trigger:

- `src/agent/platform/tools/builtins/skill_view.py:152-155`
- `src/agent/core/agent/runtime.py:1002-1016`

The SDK also contains a drain method:

- `src/agent/sdk/kernel.py:1373-1396`

But no production code calls it. A repository search for `run_queued_skill_batch_reviews` finds only the SDK method definition, while Gateway and CLI startup/housekeeping only run deterministic skill maintenance:

- `src/personal_assistant/main.py:1701-1712`
- `src/coding_cli/product.py:170-172`

The unit tests validate the background runner itself and the enqueue/dedupe state, but not any production consumer:

- `tests/unit/test_skill_batch_review.py:56-88`
- `tests/unit/test_skill_view.py:78-152`

Impact: users can reach the threshold and see `uses_since_last_B` reset after enqueue, but the promised cross-session batch analysis and patch-only optimization never actually run in normal Gateway/CLI operation.

Required fix: wire a production drain after enqueue or in a real housekeeping/background loop with an injected background fork callable, and test that a threshold-crossing `skill_view` call is eventually consumed through the Gateway/CLI entrypoint.

## Warnings

### WARNING-1: `<available_skills>` still tells agents to call `skill_view` even when the tool is disabled

The kernel delta spec says sessions without `skill_view` must not render guidance instructing the agent to call it:

- `docs/changes/feat-446-skill-view-tool/specs/kernel/spec.md:47-50`

The default PA behavior preserves explicit allowlists without adding `skill_view`, which is correct:

- `tests/unit/test_runtime_tool_allowlist_filtering.py:59-77`

But the available-skills formatter unconditionally emits `skill_view` guidance whenever any skills are listed:

- `src/agent/core/skills/formatter.py:8-14`
- `src/agent/core/skills/formatter.py:17-35`

The newer prompt-section guidance is gated by tools (`src/agent/core/agent/prompt_sections/core_sections.py:247-267`), but the skill listing itself is not gated (`src/agent/core/agent/prompt_sections/core_sections.py:198-210`). The legacy prompting path has the same unconditional listing behavior at `src/agent/core/agent/prompting.py:269-282`.

Impact: an agent with an explicit tool allowlist excluding `skill_view` can still be prompted to call a tool it does not have, making `/skill:` and matching listed skills degrade poorly.

Recommended fix: make `format_available_skills_section` or its callers aware of whether `skill_view` is active, and render a no-`skill_view` fallback when it is not. Add a regression test with `available_skills` non-empty and `available_tools` excluding `skill_view`.

### WARNING-2: Usage is written to the agent workspace sidecar even when the priority-hit skill lives in a shared/PA root

The spec states that same-name resolution must record usage/session refs/compaction survival to the concrete priority-hit skill:

- `docs/changes/feat-446-skill-view-tool/spec.md:123-129`
- `docs/changes/feat-446-skill-view-tool/specs/kernel/spec.md:30-34`

`skill_view` correctly reads the priority-hit location from the registry, but always writes usage to `resolved.agent_skill_root`:

- `src/agent/platform/tools/builtins/skill_view.py:137-156`
- `src/agent/platform/tools/builtins/skill_view.py:179-188`
- `src/agent/core/skills/root_resolver.py:75-86`

The dashboard RPC also reads only the agent workspace `.usage.json`:

- `src/personal_assistant/ws/im_connection.py:948-956`

Impact: a PA/shared skill usage entry is stored under the current agent workspace rather than the sidecar for the root that actually owns the loaded SKILL.md. This can misattribute usage if a same-name agent skill is later created, and F4/Curator side effects can target the wrong root even though the `location` points elsewhere.

Recommended fix: either resolve the owning search root from `skill.location` and write usage to that root, or explicitly update the spec/design to define these records as per-agent audit records while ensuring Curator/F4 never treats shared-root hits as agent-local skills.

## Passed Checks

- Tool schema split is implemented: `skill_view` exposes `{name}` only and `skill_manage` no longer exposes `view`.
- PA defaults and capability projection include `skill_view`; explicit tool allowlists are not widened automatically.
- `skill_manage(create, scope=agent|pa)` uses controlled roots and errors when PA root is unavailable.
- Usage writes are idempotent for repeated `{session_id, tool_call_id}` and failed reads do not create usage.
- Curator excludes `.archive`, marks stale/archived for F3/F4 sources, keeps F1/F2/manual/unknown out of automatic lifecycle transitions, and revives stale records on successful use.
- Distiller built-in bootstrap and IM prefill flow are present; the UI blocks prefill when the execution agent cannot see `conversation-skill-distiller`.
- IM usage dashboard uses Gateway WS RPC rather than reading workspace files directly from IM.
- Frontend usage list, heatmap, health view, empty/offline states, and `skill_view` tool-call card are implemented.
- Project import boundaries appear respected in the touched product/kernel areas: products continue to go through `agent.sdk`; IM does not import `agent`; core code does not import platform.

## Verdict

FAIL. The branch has the visible UI/API/tool surface, but two core promised runtime behaviors are not wired through normal execution: automatic compaction survival and production F4 batch review execution.
