# M3 InboundPipeline 32-file behavior coverage inventory

Baseline: `a3ce27d93170fb13cde7f7c8004ab5df198a8ab1` (`git grep -l '\bInboundPipeline\b' <baseline> -- tests` = 32 files). This inventory distinguishes real construction/private-layout coupling from documentation-only references and records the stable public replacement.

| # | Baseline test file | M3 disposition | Stable behavior/interface retained |
|---:|---|---|---|
| 1 | `tests/im_service/integration/test_event_bridge_kernel_stream.py` | unchanged; documentation-only mention | runtime-delivery event bridge behavior |
| 2 | `tests/im_service/integration/test_gateway_im_direct_chat.py` | migrated to test composition graph | public `InboundPipeline.handle_inbound`, explicit `LiveAgentCatalog` publication |
| 3 | `tests/im_service/integration/test_gateway_im_group_chat.py` | migrated to test composition graph | public group routing, config snapshot publication, NO_REPLY visibility |
| 4 | `tests/im_service/integration/test_gateway_im_roundtrip.py` | migrated to test composition graph | public browserless IM round-trip and session reuse |
| 5 | `tests/im_service/integration/test_group_chat_events.py` | migrated to test composition graph | public multi-agent relay identity and completion events |
| 6 | `tests/im_service/integration/test_group_chat_flow.py` | migrated to test composition graph | public group mention round-trip and NO_REPLY |
| 7 | `tests/im_service/integration/test_heartbeat_config_sync_pipeline.py` | migrated to test composition graph | explicit catalog/binder owners plus public heartbeat/config path |
| 8 | `tests/unit/agent/test_session_metadata_features_wiring.py` | unchanged; documentation-only mention | Kernel session feature metadata contract |
| 9 | `tests/unit/personal_assistant/test_gateway_build_runtime.py` | private graph inspection replaced by constructor spies | composition injects persistent binder storage and delivery callbacks |
| 10 | `tests/unit/personal_assistant/test_gateway_channel_and_session.py` | migrated to explicit catalog/binder owners | public channel bootstrap and stale-session invalidation |
| 11 | `tests/unit/personal_assistant/test_gateway_dispatch_url_injection.py` | private metadata helper replaced by public turn | observable created-session `gateway_dispatch_url` |
| 12 | `tests/unit/personal_assistant/test_gateway_im_integration.py` | migrated to test composition graph | public group gate, live config, local channel, context behavior |
| 13 | `tests/unit/personal_assistant/test_gateway_image_inbound.py` | callback passed at construction | public image success/fixed failure/follow-up behavior |
| 14 | `tests/unit/personal_assistant/test_gateway_pipeline_no_fanout.py` | private key helper replaced | public `build_group_context_key` plus pipeline buffer behavior |
| 15 | `tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py` | private formatter tests deleted | sender prefix and buffer drain verified through public turns |
| 16 | `tests/unit/personal_assistant/test_gateway_stop_command.py` | active-map mutation deleted | public running dispatch followed by facade `/stop`; idle/group syntax retained |
| 17 | `tests/unit/personal_assistant/test_heartbeat_prompt_openclaw.py` | facade private token helper replaced | public `is_protocol_silence_token` policy |
| 18 | `tests/unit/personal_assistant/test_inbound_pipeline_agent_sessions.py` | migrated to explicit catalog/binder owners | public live snapshot update and invalidation behavior |
| 19 | `tests/unit/personal_assistant/test_inbound_pipeline_kernel_sdk.py` | private active/drain instrumentation deleted | public SDK submit/model/stream/idle behavior; steer races moved to coordinator admission tests |
| 20 | `tests/unit/personal_assistant/test_inbound_pipeline_metadata.py` | migrated to test composition graph | public session creation metadata behavior |
| 21 | `tests/unit/personal_assistant/test_inbound_pipeline_permission_watchdog.py` | deleted | quiet/stall/failure behavior replaced by `test_session_run_coordinator_terminal.py` public coordinator tests |
| 22 | `tests/unit/personal_assistant/test_inbound_pipeline_session.py` | drain-lock layout tests deleted | public route/shadow/session/reply/lifecycle/config behavior retained |
| 23 | `tests/unit/personal_assistant/test_inbound_pipeline_session_metadata.py` | migrated to test composition graph | public session metadata and feature behavior |
| 24 | `tests/unit/personal_assistant/test_inbound_pipeline_shutdown_terminal.py` | migrated to test composition graph | public seal/cancellation terminal lifecycle |
| 25 | `tests/unit/personal_assistant/test_inbound_pipeline_sse.py` | migrated to test composition graph | public stream/reply/failure/watchdog behavior |
| 26 | `tests/unit/personal_assistant/test_inbound_pipeline_user_interrupt_content.py` | deleted | user-stop reconcile content replaced by public coordinator terminal test |
| 27 | `tests/unit/personal_assistant/test_inbound_pipeline_user_interrupt_leak.py` | deleted | interrupt-marker cleanup replaced by public coordinator terminal test |
| 28 | `tests/unit/personal_assistant/test_persistent_session_binding_store.py` | documentation-only reference updated | repository persistence behavior remains binder-owned |
| 29 | `tests/unit/personal_assistant/test_pipeline_kernel_event_observer.py` | migrated to test composition graph | public turn drives observer event order |
| 30 | `tests/unit/personal_assistant/test_session_reuse_regression.py` | binder-private assertion deleted | consecutive public turns prove workspace-safe reuse |
| 31 | `tests/unit/personal_assistant/test_steer_reply_relay_regression.py` | migrated to test composition graph | public steer reply relay regression; coordinator tests own linearization detail |
| 32 | `tests/unit/test_feishu_integration.py` | facade private key helper replaced | public group-context key matches Feishu external identity |

Permanent new coverage:

- `test_session_run_coordinator_admission.py`: same-session FIFO, cross-session parallelism, continuous steer, submit-marker linearization, lost-steer prepared-parts exactly once.
- `test_session_run_coordinator_terminal.py`: quiet liveness, real stall, active/idle stop, original-consumer reconcile, terminal failure cleanup, group/external NO_REPLY.
- `test_gateway_inbound_ownership_contract.py`: narrow facade, no lifecycle back-import, coordinator-only runtime/heartbeat composition.
