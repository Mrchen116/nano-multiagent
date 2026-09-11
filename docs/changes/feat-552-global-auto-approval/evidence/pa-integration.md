# PA integration evidence

## Claim and boundary

The PA integration applies the shared Auto permission policy to global main sessions while retaining each input's actual source. It keeps the existing Inbox receipt, work-recording and dispatch paths; it does not add an approval ledger, reply-pairing service or parked permission Future. Kernel classifier decisions, model selection, source serialization and interaction precedence remain owned by the shared kernel implementation.

The baseline is this unit's pre-implementation PA code. The affected observable seams are the tool projections, shared runtime construction, Gateway-submitted input parts and existing real-SDK Gateway loop. All validation below uses temporary workspaces and deterministic model fixtures. This evidence does not claim real-model classification accuracy or production deployment.

## Changes and source facts

- `tools/inbox.py` preserves every received message in the classifier projection, including mixed human, agent, system and unknown senders. It includes actual message ID, sender, target, channel, text, partial flag and existing reply fields. `user` and `external` map to human context; agent/system/unknown do not acquire human authority. The existing `self.name == "inbox"` guard keeps inherited `conversations(read)` history from becoming a fresh live Inbox projection. Successful call/result matching and live/restored treatment remain the kernel projector's responsibility.
- `tools/inbox_result.py` supplies the single `INBOX_SOURCE_INSTRUCTIONS` paragraph reused by the main Agent and the Inbox tool's optional classifier instructions. The model-facing page and classifier share supplied reply fields. `gateway/global_inbox.py` copies only existing reply metadata into the current source record. External-user identity remains the existing Gateway mapping: `_read` remaps only an actual `sender.kind == "user"` on an external channel; no name/body inference was added.
- `tools/send_message.py` projects the complete action arguments and retains returned `message_id`, `status` and `accepted` fields. Existing `held_for_revalidation` behavior remains intact. It has no host-intent result projection: a model's sent text is not a new user instruction. `tools/cron.py` likewise projects complete action arguments, removing its former 240-character payload truncation.
- `gateway/global_run_coordinator.py` marks the Inbox wake text part as `context_origin="system"`, independently of the existing `RunOrigin.HUMAN` scheduling value. The wake contains no received message body; the Agent still reads Inbox to obtain it.
- `gateway/inbound_pipeline.py` retains `sender_type` and `sender_agent_id` in buffered metadata. `gateway/session_run_coordinator.py` marks each message's submitted parts from that transport metadata; an agent ID takes precedence, known user/external/agent/system values map directly, and unknown values remain unclassified. Missing metadata keeps the existing native-human entry behavior. Image parts retain their existing order and bodies.
- `gateway/session_composition.py` sets `SessionRuntimeConfig.auto_mode_interaction="return_to_agent"` exactly for `pa_work_scope="global_main"`, without switching it according to run origin. The SDK owns persistence and runtime identity. `product.py` gives global main Agents the shared Inbox source guidance and the three denial choices: a permitted alternative, a specific confirmation through ordinary chat, or stopping. While waiting they may do independent work or become idle; silence is not consent, and `no_verdict` is a classifier failure rather than a user rejection.

## Runtime construction paths

| Entry | Existing path through shared construction | Scope |
|---|---|---|
| New global main | `SessionBinder.resolve_global` → `project_agent_runtime` → SDK `create_session` | `global_main` |
| Existing/restored main with new Inbox work | `GlobalRunCoordinator._drain` → `InProcessKernelClient.ensure_agent_runtime` → `project_agent_runtime` and identity comparison → idle-only reconfiguration when needed → `try_submit_idle` | `global_main` |
| Global Heartbeat | `HeartbeatScheduler._submit_run` → `ensure_agent_runtime` before idle submission | `global_main`; scheduled origin is retained |
| Global model fallback | `GlobalRunCoordinator` passes the global scenario to `run_with_fallback`; fallback uses `project_agent_runtime` before reconfiguration and replay | `global_main` |
| Detached Cron | `CronRunner` → `create_agent_session` → `InProcessKernelClient.create_session` → `project_agent_runtime` | `cron`; the shared gate handles scheduled policy, not the main-session flag |

An existing `resolve_global` row remains a lookup: merely observing or restoring a binding does not replace a busy session's frozen runtime. Before later admitted work, the existing coordinator/Heartbeat paths perform the shared runtime check. This preserves the current busy-session boundary while allowing the newly persisted interaction field to participate in runtime identity.

### M2 runtime field refinement

The initial design described an application metadata choice, but PA create/reconfigure/restore and Heartbeat refresh already compose a complete SDK runtime. Keeping the choice only in creation metadata or the wake call would leave it outside that shared replacement/identity boundary. The implementation therefore adds the optional `auto_mode_interaction: Literal["return_to_agent"] | None = None` field to the existing SDK-owned `SessionRuntimeConfig`; SDK metadata encoding, `get_session_runtime` readback and `identify_runtime` carry the same value. `None` removes the override and is the readback default for older sessions.

This is an implementation detail within the confirmed M2 scope: no new DTO, provider, public export, `build_kernel` parameter or configuration root is introduced. [Design D6](../design.md#d6计数和分流接入现有产品交互) retains the same child/Heartbeat/Cron/global-main routing priority. The consumer-visible addition is now recorded in the minimal [SDK boundary delta](../specs/kernel/sdk-boundary.md); canonical specs remain unchanged until integration acceptance and delta merging.

## Test ownership and red/green

| Regression risk | Existing owner and disposition | Lowest seam exercised |
|---|---|---|
| Mixed sender authority, action truncation, send status | `test_global_query_tools.py`, `test_cron_tool_permissions.py`, `test_send_message_tool.py`: rewrite/extend existing cases | Tool projections and HTTP-result handling |
| Source/reply metadata survives current Inbox protocol | `test_global_inbox_model_protocol.py`: extend existing current-name/receipt case | Stored source → model-facing page |
| Global flag is independent of scheduled origin | `test_pa_time_prompt_policy.py`: extend shared runtime owner | Public SDK runtime object from PA projection |
| Buffered nonhuman text/images retain their source | `test_gateway_image_inbound.py`: parameterize existing mixed-input test | Gateway-submitted parts with unchanged image ordering |
| One shared source paragraph is in the real main prompt | `test_personal_assistant_prompt_integration.py`: extend prompt assembly owner | PA prompt → SDK assembly |
| System wake, persisted flag and restored main remain usable | `test_global_gateway_runtime.py`, `test_global_gateway_lifecycle.py`: extend existing real-SDK journeys | Actual kernel loop, Inbox read/commit, dispatch and restart |

No test file or new fixture hierarchy was created for PA. Existing scheduled-work, steer-identity, external-dispatch and dispatch-failure tests are retained and rerun for adjacent behavior. No optional dependency or live service is required.

The initial tool/runtime red run had 9 failures and 33 passes: mixed sources were dropped, Cron payloads were truncated, accepted status was discarded, send-message action projection was absent, and the runtime field was not yet available. The source/prompt red run had 2 failures and 10 passes: reply fields and shared source instructions were absent. Focused PA runs then passed 49 tool/service/prompt tests and 27 runtime/source/scheduled/steer tests after the SDK field landed.

The first real-SDK integration run found a hook-discovery assembly failure before any loop began. Shared helper imports must be absolute because hooks are imported as standalone modules; helper filenames must start with `_` because the existing loader treats other top-level `.py` files as `setup(hooks)` modules. The final helpers are `src/agent/platform/hooks/builtins/_auto_mode_policy.py` and `src/agent/platform/hooks/builtins/_auto_mode_transcript.py`, imported by their absolute module paths. These failures were not bypassed with an empty registration function.

After hook assembly, the combined run reached 79 passes and 8 failures. Each remaining failure was a scripted-model fixture returning a main-Agent tool call to an actual classifier request, which now matters because `send_message` correctly leaves the safe-tool allowlist. The existing `_runtime` fixture now selects the already registered `test-model-xyz` as the approval model and routes only that model to a deterministic `<block>no</block>` response. It emits content and terminal metadata separately according to the existing LLM streaming contract. Main-model scripts are unchanged; Auto and the real gate stay enabled. The first existing journey also asserts that its classifier request contains the live Inbox text, send-message tool name, target and full message text.

Final focused verification:

- The eight PA unit owners in the table/adjacent-owner paragraph plus `tests/integration/test_personal_assistant_prompt_integration.py`: **76 passed** in the combined run. The subsequent fixture-only adjustment does not affect these tests.
- `.venv/bin/python -m pytest tests/integration/test_global_gateway_runtime.py tests/integration/test_global_gateway_lifecycle.py tests/integration/test_global_external_dispatch.py tests/integration/test_global_dispatch_failures.py -q --tb=short`: **11 passed in 10.73s** after fixture adaptation. These include actual Inbox consumption/commit, dispatch revalidation, external-delivery acknowledgement, restart and control-failure journeys.
- Scoped `.venv/bin/ruff check` across all 19 changed PA implementation/test files: **passed**; the two subsequently adjusted integration files were checked again and passed.
- Scoped `git diff --check` for the PA implementation/tests and the two evidence documents: **passed**. The existing Gateway runtime test file remains below 400 lines.

## Verification limits

The in-process integration fixtures run the actual SDK/Gateway/Inbox/dispatch code with a deterministic model. They establish request shape, source persistence and the application lifecycle; they do not establish a real LLM's permission verdict or a real Feishu delivery. This owner started no background service, changed no production configuration and performed no staging, commit or push.
