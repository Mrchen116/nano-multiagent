# Verification Report: feat-530

> Validation snapshot: `c40a9aa80f3f9107327217b868f11ec664d34bf9 → 6f848d2798f538cf9bdc499b67b19cfedfbbf2fb`

## Summary

Mode: full
Delta range: N/A
Focus issues: N/A
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 5/5 requirements covered; 1/1 implementation milestone evidenced |
| Correctness | 12/12 scenarios covered |
| Coherence | Followed |

All checks passed. Ready for PR.

## Completeness

- Tasks: 7/8 checkboxes are checked. The sole open item is C4, which is the orchestrator-owned verifier/reviewer/code-review and archive closeout currently being executed; it is not missing product implementation (`M1-sealed-human-message-envelope/tasks.md:31`).
- Milestone: feat-530-M1 implementation and worker exit criteria are present in the unit diff; focused and complete non-E2E suites pass, and durable real-stack evidence covers Web IM, Feishu direct/live group, restart/steer, and Feishu REST catch-up (`M1-sealed-human-message-envelope/progress.md:14`, `M1-sealed-human-message-envelope/evidence/web-im-real-stack.md:3`).
- Spec coverage: all five requirements have concrete implementation and permanent regression coverage. Real external-channel journeys remain acceptance evidence rather than permanent tests, consistent with `docs/development/testing.md`.
- Prototype / Reference coverage: N/A. `design.md` has no frontend prototype or must-match reference contract.

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 每条真人消息时间 / 长会话跨时段 | `src/personal_assistant/gateway/human_message_context.py:90`; `src/personal_assistant/gateway/session_run_coordinator.py:1174`; `src/agent/core/agent/prompt_sections/core_sections.py:320` | `tests/unit/personal_assistant/test_human_message_context.py:37`; `tests/integration/test_personal_assistant_prompt_integration.py:86`; real-stack `evidence/web-im-real-stack.md:12` | covered |
| 每条真人消息时间 / channel 来源时间优先 | `src/personal_assistant/channels/web_relay_adapter.py:346`; `src/personal_assistant/channels/feishu/client.py:1092`; `src/personal_assistant/gateway/human_message_context.py:100` | `tests/unit/personal_assistant/test_web_relay_adapter_attachments.py:133`; `tests/unit/test_feishu_client.py:63`; `tests/unit/test_feishu_history_client.py:21` | covered |
| 每条真人消息时间 / 缺少来源时间时固定 Gateway receipt | `src/personal_assistant/gateway/inbound_dispatcher.py:39`; `src/personal_assistant/gateway/human_message_context.py:103` | `tests/unit/personal_assistant/test_inbound_dispatcher.py:90`; `tests/unit/personal_assistant/test_human_message_context.py:61`; invalid Web time `tests/unit/personal_assistant/test_web_relay_adapter_attachments.py:143` | covered |
| 逐消息实际入口 / 同一 shadow 中 Feishu 后 Web IM | `src/personal_assistant/gateway/human_message_context.py:202`; `src/personal_assistant/gateway/inbound_pipeline.py:140` | same-buffer cross-ingress `tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py:206`; real ingress evidence `evidence/web-im-real-stack.md:39` | covered |
| 逐消息实际入口 / 群聊保留 sender 且不输出 chat type/路由身份 | `src/personal_assistant/gateway/session_run_coordinator.py:1185`; `src/personal_assistant/gateway/human_message_context.py:100` | `tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py:206`; real group evidence `evidence/web-im-real-stack.md:39` | covered |
| 逐消息实际入口 / 私聊只输出平台 | `src/personal_assistant/gateway/human_message_context.py:100` | direct Web/Feishu mappings `tests/unit/personal_assistant/test_human_message_context.py:37`; real direct evidence `evidence/web-im-real-stack.md:3` and `evidence/web-im-real-stack.md:39` | covered |
| envelope 不改原文 / 原入口查看与复制 | `src/personal_assistant/gateway/human_message_context.py:119`; `src/personal_assistant/gateway/readable_input_projection.py:16`; `src/personal_assistant/hooks/chat_history.py:77` | `tests/unit/personal_assistant/test_human_message_context.py:123`; `tests/unit/personal_assistant/test_gateway_readable_projection.py:59`; real Web/Feishu evidence `evidence/web-im-real-stack.md:3` | covered |
| envelope 不改原文 / Feishu shadow 正文不带 prefix | shadow sync precedes model decoration at `src/personal_assistant/gateway/inbound_pipeline.py:140`; decoration only copies metadata at `src/personal_assistant/gateway/human_message_context.py:119` | exact readable/no-strip tests `tests/unit/personal_assistant/test_chat_history_hook.py:136`; real Feishu evidence `evidence/web-im-real-stack.md:39` | covered |
| 新消息稳定延续 / Gateway 重启后沿用原时间与入口 | Kernel receives final decorated bytes at `src/personal_assistant/gateway/session_run_coordinator.py:1217`; group metadata is durable at `src/personal_assistant/gateway/group_context_store.py:62` | SQLite reopen `tests/unit/personal_assistant/test_group_context_store.py:42`; real restart/catch-up `evidence/web-im-real-stack.md:21` and `evidence/web-im-real-stack.md:48` | covered |
| 新消息稳定延续 / 旧历史不补造 | missing/invalid provenance returns no header at `src/personal_assistant/gateway/human_message_context.py:53`; Coordinator preserves undecorated parts at `src/personal_assistant/gateway/session_run_coordinator.py:1217` | mixed legacy/new buffer `tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py:252` | covered |
| 非 PA 保持现状 / Coding CLI | footer policy defaults to the old bytes at `src/agent/core/agent/prompt_sections/core_sections.py:336`; registry default is on at `src/agent/core/agent/prompt_sections/feature_registry.py:77` | omitted equals explicit true `tests/integration/test_personal_assistant_prompt_integration.py:110`; full non-E2E suite covers existing CLI prompt contracts | covered |
| 非 PA 保持现状 / heartbeat、cron、subagent、内部通知无真人 envelope | only Web/Feishu channel names map at `src/personal_assistant/gateway/human_message_context.py:202`; all PA top-level origins share stable footer policy at `src/personal_assistant/gateway/session_composition.py:52` | unknown/internal channel `tests/unit/personal_assistant/test_human_message_context.py:75`; human/heartbeat/cron runtime equality `tests/unit/personal_assistant/test_pa_time_prompt_policy.py:34` | covered |

Validation executed independently at the snapshot:

- Focused behavior + architecture set: 136 passed, 2 upstream warnings.
- Complete `pytest -m 'not e2e' -n 4`: 3272 passed, 28 warnings.
- Ruff on all changed Python files: passed.
- `scripts/docs_check.py`: passed (236 maintained Markdown sources, 67 required routes).
- `git diff --check c40a9aa80..6f848d279`: passed.

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 1. Dispatcher 固定 receipt，Pipeline 只 freeze 一次 | 是 | `src/personal_assistant/gateway/inbound_dispatcher.py:39`; `src/personal_assistant/gateway/inbound_pipeline.py:149` |
| 2. Adapter 只归一化 provider time，Feishu live/history 同 parser | 是 | `src/personal_assistant/channels/web_relay_adapter.py:412`; `src/personal_assistant/channels/feishu/client.py:1092`; `src/personal_assistant/channels/feishu/client.py:1147`; `src/personal_assistant/channels/feishu/client.py:1188` |
| 3. v1 稀疏 header，sender 与附件顺序保持 | 是 | `src/personal_assistant/gateway/human_message_context.py:90`; `src/personal_assistant/gateway/human_message_context.py:144`; `src/personal_assistant/gateway/session_run_coordinator.py:1205` |
| 4. Gateway 启动时只解析一份 timezone snapshot | 是 | `src/personal_assistant/gateway/composition.py:218`; shared injection at `src/personal_assistant/gateway/composition.py:274`, `src/personal_assistant/gateway/composition.py:555`, `src/personal_assistant/gateway/composition.py:583` |
| 5. raw/model/readable 三层，readable 只 exact provenance 消费 | 是 | `src/personal_assistant/gateway/session_run_coordinator.py:1174`; `src/personal_assistant/gateway/readable_input_projection.py:8`; `src/personal_assistant/hooks/chat_history.py:77` |
| 6. complete-runtime feature 控制 session-created datetime | 是 | `src/agent/core/agent/prompt_sections/feature_registry.py:77`; `src/agent/core/agent/prompt_sections/core_sections.py:320`; `src/personal_assistant/gateway/session_composition.py:80`; `src/agent/sdk/kernel.py:1855` |
| 7. cache/历史只追加，旧 bytes 不重写 | 是 | header 只在 admission parts 构建时应用：`src/personal_assistant/gateway/session_run_coordinator.py:1174`; missing provenance remains undecorated: `src/personal_assistant/gateway/human_message_context.py:53` |
| 8. 不新增 SDK 方法/DTO/字段、IM schema/表或时间工具 | 是 | unit diff only extends existing `Kernel.list_features()` at `src/agent/sdk/kernel.py:1855` and updates `FeatureInfo` documentation at `src/agent/sdk/dto.py:368`; SDK/import boundary contract tests pass |

Architecture is coherent with `SPEC.md`: PA imports the Kernel only through `agent.sdk`; Core remains product-neutral; IM does not depend on `agent`; the feature extends the existing runtime/configuration mechanism instead of creating a parallel policy channel.

### Prototype / Reference Contract

N/A.

## Issues

### CRITICAL（提 PR 前必须修）

None.

### WARNING（提 PR 前必须修）

None.

### SUGGESTION（可以修）

- `src/personal_assistant/hooks/chat_history.py:62`: the public `setup()` function gained `readable_input_projection_store`, but its Google-style `Args` section still documents only `hooks`. Add one concise argument entry describing the exact-provenance handoff to keep the new public signature aligned with `docs/development/coding-guidelines.md`; this does not affect the verified behavior.

# Round 2

## Verification Report: feat-530

> Validation snapshot: `c40a9aa80f3f9107327217b868f11ec664d34bf9 → 255b41d0499336bd27136a0c523a3c45bef2bede`

### Summary

Mode: delta
Delta range: `c40675fee132cf50dda0c85d06b772566521fa4e..255b41d0499336bd27136a0c523a3c45bef2bede`
Focus issues: Round 1 verification suggestion; acceptance R1-I1; pathname `TZ`, Feishu platform timestamp range, and capability documentation findings
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 5/5 focused fixes covered |
| Correctness | 5/5 focused behaviors covered |
| Coherence | Followed |

All checks passed. Ready for PR.

## Completeness

- Round 1 verification suggestion is closed: public `chat_history.setup()` now documents `readable_input_projection_store` in its Google-style `Args` section (`src/personal_assistant/hooks/chat_history.py:62`).
- Acceptance R1-I1 is closed at implementation/test level: the Kernel preserves and rewrites `/skill:*` after the composed time/channel and sender annotations (`src/agent/core/agent/skill_commands.py:15`; `tests/contract/test_skill_commands_contract.py:33`). A new real Feishu product journey remains the reviewer’s independent acceptance responsibility, not missing verifier coverage.
- The three code-review findings are all represented in the delta and permanent tests: pathname-form `TZ`, Feishu `OSError` timestamp fallback, and corrected SDK/PA capability documentation.
- The delta is localized to one product-neutral command parser, two existing PA normalization helpers, documentation/docstrings, and their focused tests. It does not modify message lifecycle, storage schema, SDK surface, IM schema, or product import direction, so a new full verification is not required after Round 1’s passing full suite.
- Prototype / Reference coverage: N/A.

## Correctness

| Requirement / focused behavior | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| Existing `/skill:*` rewrite survives `[time/channel] [sender]` composition | `src/agent/core/agent/skill_commands.py:6-18` preserves zero or more opaque bracket annotations before parsing the command | Existing zero/single-prefix contracts plus the new two-prefix assertion at `tests/contract/test_skill_commands_contract.py:4-44` | covered |
| Gateway startup accepts pathname-form `TZ` while retaining IANA/localtime/fixed-offset fallback | `src/personal_assistant/gateway/human_message_context.py:172-202`; pathname normalization at `src/personal_assistant/gateway/human_message_context.py:219-226` | Existing fallback table plus pathname case at `tests/unit/personal_assistant/test_human_message_context.py:137-163` | covered |
| Invalid/platform-out-of-range Feishu create time becomes missing source time, enabling the designed receipt fallback | `src/personal_assistant/channels/feishu/client.py:1188-1195` catches `OSError` together with parse/range errors; frozen selection remains source-first/receipt-second at `src/personal_assistant/gateway/human_message_context.py:90-107` | Platform `OSError` regression at `tests/unit/test_feishu_client.py:80-86`; existing receipt fallback at `tests/unit/personal_assistant/test_human_message_context.py:61-73` | covered |
| Kernel capability metadata accurately describes default-on tool-independent runtime policies without changing DTO/API shape | `src/agent/sdk/dto.py:368-384`; PA UI projection ownership clarified at `src/personal_assistant/reporter/capability_projection.py:17-26,76-80` | Existing list-feature and Gateway payload tests in `tests/unit/agent/test_kernel_list_capability_queries.py` and `tests/unit/personal_assistant/test_gateway_upstream_reporter.py` remain green | covered |
| New public `setup()` parameter follows repository docstring rules | `src/personal_assistant/hooks/chat_history.py:62-76` | Ruff plus focused hook tests; direct signature/docstring inspection | covered |

Independent delta validation:

- Focused behavior/regression set: 76 passed.
- SDK/product import and architecture contracts: 18 passed.
- Ruff check and Ruff format check on all changed Python files: passed.
- `scripts/docs_check.py`: passed (238 maintained Markdown sources, 67 required routes).
- `git diff --check c40675fee..255b41d04`: passed.

## Coherence

| design / architecture decision | 遵守? | 代码证据（file:line） |
|---|---|---|
| Header precedes the existing group sender and adjacent behavior remains usable | 是 | The generalized parser treats every leading annotation as opaque and preserves it verbatim (`src/agent/core/agent/skill_commands.py:6-18`), matching the designed `[header] [sender] body` composition (`design.md:123-130,265`). The canonical single-annotation scenario in `docs/specs/kernel/skills.md:22-24` remains satisfied; accepting the composed sequence is a backward-compatible generalization, not a conflicting contract. |
| Timezone is resolved once at Gateway startup with IANA semantics and fixed-offset fallback | 是 | Path-form `TZ` is reduced to its IANA suffix before the existing one-time resolution/fallback path (`src/personal_assistant/gateway/human_message_context.py:172-202,219-226`), consistent with design decision 4 (`design.md:137-144`). |
| Missing, malformed, or out-of-range provider time delegates to frozen receipt time | 是 | Feishu parser maps the platform-specific `OSError` to `None` (`src/personal_assistant/channels/feishu/client.py:1188-1195`), exactly matching design decision 2 (`design.md:116-121`). |
| Extend existing feature/catalog and UI projection boundaries; do not add a parallel API or leak internal policy into PA toggles | 是 | The delta changes only `FeatureInfo` and projection documentation (`src/agent/sdk/dto.py:368-384`; `src/personal_assistant/reporter/capability_projection.py:17-26,76-80`); data structures and runtime projection are unchanged. |
| Preserve dependency direction and product neutrality | 是 | The only Core behavior change parses generic opaque annotations and contains no PA/channel identifiers; SDK/import boundary contracts pass. |

### Prototype / Reference Contract

N/A.

## Issues

### CRITICAL（提 PR 前必须修）

None.

### WARNING（提 PR 前必须修）

None.

### SUGGESTION（可以修）

None.

# Round 4

## Verification Report: feat-530

> Validation snapshot: `5dd22bb4fa2fbcbd10d247ff3f3c77f71f598535 → ddd0ead71dc5113d94ef73c79f376eeed0b1c579`

### Summary

Mode: delta
Delta range: `6426d722ef5328114775dc29706e1c94d05462e6..ddd0ead71dc5113d94ef73c79f376eeed0b1c579`
Focus issues: R3-I1 dynamic slash candidate cache invalidation after saved Workflow config
requires_full_verification: false

| Dimension | Result |
|---|---|
| Completeness | 1/1 focused fix covered |
| Correctness | 5/5 affected seams covered |
| Coherence | Followed |

All checks passed. R3-I1 is closed. Ready for PR.

## Completeness

- The delta is intentionally narrow: the saved Agent configuration mutation now invalidates the real active query prefix, `['chat', 'slash-candidates']`, rather than the obsolete and unconsumed `['chat', 'slash-skills']` (`src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx:1352-1373`). No Gateway, ingress, workspace, model catalog, or command composition code changed.
- The affected query is scoped by the sorted conversation Agent ids and reads both `getAgentConfig(agentId, 'live')` and `getAgentCapabilities(agentId)` before rebuilding skills and authorized dynamic commands (`src/IM/frontend/src/features/chat/chat-workspace-page.tsx:412-465`). Prefix invalidation therefore refreshes every currently observed conversation containing the saved Agent and marks inactive variants stale; it neither introduces a second candidate source nor leaves the 60-second cache authoritative after a save.
- The new integration regression begins with a cached no-Workflow profile, invalidates the exact production prefix after the simulated saved profile changes, then observes `/workflows` and model-specific `/effort` without navigation or expiry (`src/IM/frontend/src/features/chat/chat-workspace.integration.test.tsx:443-490`). The companion mutation test asserts the config-save hook emits that same prefix (`src/IM/frontend/src/features/settings/agents/agent-detail-page.test.tsx`). Together they cover the connection that R3-I1 lacked, rather than merely asserting a cache helper call.

## Correctness

| Affected behavior | Implementation evidence | Regression evidence | Status |
|---|---|---|---|
| Saved Workflow/config state refreshes dynamic candidates | The only runtime invalidation changed is the actual `slash-candidates` prefix; active candidates fetch live Gateway config and capabilities. | New cached-profile integration path shows absent candidates, invalidates the production prefix, then finds `/workflows` and `/effort`. | covered |
| Selected dynamic command retains the established composer form | The picker selects the returned command and `MessagePane` inserts `/<name> ` without a new conversion path (`src/IM/frontend/src/features/chat/components/message-pane.tsx:545-567`). | New integration test selects `/workflows` and asserts `/workflows `; existing picker/MessagePane tests pass. | covered |
| Per-Agent group `/effort` remains targeted, not unioned | `buildSlashCommands()` emits each effort candidate with its source Agent and `targetAgentId`; group selection records an Agent mention before command text (`src/IM/frontend/src/features/chat/components/slash-candidates.ts:43-68`; `message-pane.tsx:548-559`). | Existing MessagePane regression asserts visible `@Coder /effort ` becomes `<mention type="agent" target_id="a-coder"/> /effort max`; Gateway no-fanout regression passes. | covered |
| Static slash commands retain their behavior | `SlashPicker` still prepends static `/stop`, `/new`, and `/compact` and appends dynamic commands; the delta does not alter this assembly (`src/IM/frontend/src/features/chat/components/slash-picker.tsx:50-66`). | Static and dynamic picker tests pass in the focused frontend run. | covered |
| Provider/model-specific reasoning levels remain Gateway-authoritative | Candidate descriptions remain verbatim `capabilities.commands` payloads; the UI does not compute or merge effort levels (`chat-workspace-page.tsx:434-460`). | The new profile refresh asserts the exact `low, medium, high, max` description; existing per-Agent distinct-level unit coverage passes. | covered |

Independent validation at `ddd0ead`:

- Frontend focused behavior suite: 196 passed (`agent-detail-page`, chat-workspace integration, slash-candidates, slash-picker, and MessagePane). It ran in the dependency-provisioned unit worktree at the identical `ddd0ead` snapshot; the dedicated verifier worktree contains no frontend dependency directory.
- Gateway control-routing, Workflow command, ingress/session, and Gateway-owned workspace-root contract set: 58 passed.
- Frontend production build (`tsc -b && vite build`): passed. Vite reported only its pre-existing-size advisory.
- `git diff --check 6426d722ef5328114775dc29706e1c94d05462e6..ddd0ead71dc5113d94ef73c79f376eeed0b1c579`: passed.

## Coherence

- The repair preserves one cache owner and one Gateway-authoritative candidate source. It corrects a cache key rather than adding frontend Workflow policy, an IM shadow of capability state, or an alternate command wire path.
- Query-key prefix invalidation is intentionally Agent-agnostic because a saved Agent can appear in more than one direct or group conversation. The existing per-conversation sorted Agent-id key continues to separate the fetched result and preserves group-specific rendering.
- The delta leaves the current-main Gateway boundary intact: workspace-root ownership remains in Gateway composition, and IM still only asks typed Gateway config/capability APIs. The passing `test_workspace_root_mirror_contract.py` covers this unchanged boundary.

### Prototype / Reference Contract

N/A.

## Issues

### CRITICAL（提 PR 前必须修）

None.

### WARNING（提 PR 前必须修）

None.

### SUGGESTION（可以修）

None.

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `specs/gateway/routing-delivery.md` ADDED Requirement: PA 为每条真人消息固定模型侧发生时间与实际入口 | Provider/receipt facts enter `InboundMessage` (`src/personal_assistant/channels/base.py:27-52`), are frozen after raw shadow consumers (`src/personal_assistant/gateway/inbound_pipeline.py:141-153`), and are projected only into model parts (`src/personal_assistant/gateway/session_run_coordinator.py:1174-1223`). | Gateway envelope, persistence, readable projection, prompt policy, and active-steer suites included in the 195-test reconciliation run. | aligned |
| Gateway Scenario: 长会话中的新消息各自保留发生时间 | `PaHumanMessageContext.freeze()` converts each admitted occurrence independently and stores complete frozen header bytes (`src/personal_assistant/gateway/human_message_context.py:79-116`); PA runtime supplies stable timezone and disables session-created datetime (`src/personal_assistant/gateway/session_composition.py:52-92`). | `tests/unit/personal_assistant/test_human_message_context.py:37-72`; `tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py:206-249`; `tests/integration/test_personal_assistant_prompt_integration.py:86-128`. | aligned |
| Gateway Scenario: 来源时间优先且缺失时固定 Gateway 接收时间 | Web/Feishu adapters normalize provider time; Dispatcher stamps receipt before scheduling; freezer selects aware source then receipt (`src/personal_assistant/channels/web_relay_adapter.py:346-424`; `src/personal_assistant/channels/feishu/client.py:1116-1195`; `src/personal_assistant/gateway/inbound_dispatcher.py:39-79`; `src/personal_assistant/gateway/human_message_context.py:100-108`). | `tests/unit/personal_assistant/test_web_relay_adapter_attachments.py:133-152`; `tests/unit/test_feishu_client.py:64-86`; `tests/unit/personal_assistant/test_inbound_dispatcher.py:90-114`; `tests/unit/personal_assistant/test_human_message_context.py:37-72`. | aligned |
| Gateway Scenario: 飞书历史补拉沿用消息原发生时间 | Live and REST history parsers share `_parse_feishu_create_time`, and Adapter carries that value into both direct/group inbound messages (`src/personal_assistant/channels/feishu/client.py:1116-1195`; `src/personal_assistant/channels/feishu/adapter.py:383-468`). | `tests/unit/test_feishu_history_client.py:21-50`; `tests/unit/test_feishu_group_history_catchup.py:60-84`. | aligned |
| Gateway Scenario: 同一 shadow context 按逐消息实际入口标注 | Header channel derives only from `message.channel_name`, not shadow metadata (`src/personal_assistant/gateway/human_message_context.py:100-115,205-210`). | Cross-ingress buffer assertion at `tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py:206-249` intentionally gives the Web IM trigger Feishu shadow metadata yet expects `Web IM`. | aligned |
| Gateway Scenario: 群聊延续 sender 语义但不重复 chat type | Coordinator applies existing sender projection before the frozen header; header labels contain only `Web IM`/`Feishu` and time (`src/personal_assistant/gateway/session_run_coordinator.py:1205-1218`; `src/personal_assistant/gateway/human_message_context.py:108-115`). | `tests/unit/personal_assistant/test_human_message_context.py:37-58,87-107`; `tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py:206-249`. | aligned |
| Gateway Scenario: model envelope 不污染用户可见正文 | Pipeline performs external shadow sync before attaching generated metadata; attachment returns a copied message whose raw text is unchanged (`src/personal_assistant/gateway/inbound_pipeline.py:140-153`; `src/personal_assistant/gateway/human_message_context.py:119-141`). | `tests/unit/personal_assistant/test_human_message_context.py:123-134`; exact raw/model split at `tests/unit/personal_assistant/test_gateway_readable_projection.py:59-71`. | aligned |
| Gateway Scenario: workspace 可读聊天副本保持既有正文语义 | Coordinator builds model/readable projections from one ordered source; normal submission stages exact provenance and the hook consumes only an exact match (`src/personal_assistant/gateway/session_run_coordinator.py:909-928,1174-1223`; `src/personal_assistant/gateway/readable_input_projection.py:8-59`; `src/personal_assistant/hooks/chat_history.py:78-89`). | `tests/unit/personal_assistant/test_gateway_readable_projection.py:59-89`; `tests/unit/personal_assistant/test_readable_input_projection.py:8-45`; `tests/unit/personal_assistant/test_chat_history_hook.py:136-178`. | aligned |
| Gateway Scenario: 功能启用前的旧历史不补造 context | Only trusted v1 metadata yields a header; missing legacy metadata remains undecorated (`src/personal_assistant/gateway/human_message_context.py:53-76,144-169`; `src/personal_assistant/gateway/session_run_coordinator.py:1214-1218`). | Mixed legacy/new group regression at `tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py:252-275`; durable frozen metadata at `tests/unit/personal_assistant/test_group_context_store.py:42-59`. | aligned |
| Gateway Scenario: 非 PA 真人入口保持现状 | Freezer ignores channels other than Web relay/Feishu; all PA top-level runtime origins share the same footer policy without adding a human envelope; default Kernel consumers retain the old footer (`src/personal_assistant/gateway/human_message_context.py:205-210`; `src/personal_assistant/gateway/session_composition.py:80-89`; `src/agent/core/agent/prompt_sections/core_sections.py:336-339`). | `tests/unit/personal_assistant/test_human_message_context.py:75-84`; `tests/unit/personal_assistant/test_pa_time_prompt_policy.py:34-64`; `tests/integration/test_personal_assistant_prompt_integration.py:110-128`. | aligned |
| Gateway Requirement paragraph: normal submit / group buffer / active steer / retry / replay reuse the same envelope without lifecycle changes | Pipeline freezes once; group buffer persists only frozen metadata; Coordinator reuses the same projection for steer and queued fallback, while transcript replay consumes previously submitted bytes (`src/personal_assistant/gateway/inbound_pipeline.py:149-162`; `src/personal_assistant/gateway/session_run_coordinator.py:240-300,896-928,1174-1223`). | `tests/unit/personal_assistant/test_group_context_store.py:42-59`; `tests/unit/personal_assistant/test_session_run_coordinator_admission.py:629-711`; submit rollback at `tests/unit/personal_assistant/test_gateway_readable_projection.py:74-89`. | aligned |
| `specs/kernel/prompts.md` ADDED Requirement: session 创建时间由完整运行配置显式控制 | Registry declares the product-neutral default-on policy and runtime footer reads only its resolved flag (`src/agent/core/agent/prompt_sections/feature_registry.py:77-88`; `src/agent/core/agent/prompt_sections/core_sections.py:320-339`). | `tests/integration/test_personal_assistant_prompt_integration.py:86-128`; `tests/unit/personal_assistant/test_pa_time_prompt_policy.py:34-82`. | aligned |
| Prompts Scenario: 显式关闭 session 创建时间 | False returns the working-directory line only; PA adds stable timezone through ordinary `PromptSlots` (`src/agent/core/agent/prompt_sections/core_sections.py:336-339`; `src/personal_assistant/product.py:295-340`; `src/personal_assistant/gateway/session_composition.py:80-89`). | `tests/integration/test_personal_assistant_prompt_integration.py:86-108`; `tests/unit/personal_assistant/test_pa_time_prompt_policy.py:34-64`. | aligned |
| Prompts Scenario: 默认或显式开启时保持 runtime footer bytes | Missing flag defaults to `True`; explicit `True` follows the same old two-line rendering (`src/agent/core/agent/prompt_sections/core_sections.py:336-339`). | Byte-identity assertion at `tests/integration/test_personal_assistant_prompt_integration.py:110-128`; registry defaults wiring at `tests/unit/agent/test_session_metadata_features_wiring.py:19-30`. | aligned |
| Prompts Scenario: PromptText name 不改变 Kernel policy | Footer consults only `PromptContext.flags`; no PromptText name/workspace/routing branch exists (`src/agent/core/agent/prompt_sections/core_sections.py:320-339`). | Arbitrary non-PA prompt-name case at `tests/integration/test_personal_assistant_prompt_integration.py:86-108`. | aligned |
| Prompts MODIFIED Requirement: feature 内核只留通用项，产品 prompt 经 PromptSlots 持久归属会话配置 | Registry keeps general guidance/runtime policy in Core; PA timezone remains a normal product PromptText and complete-runtime feature (`src/agent/core/agent/prompt_sections/feature_registry.py:54-88`; `src/personal_assistant/product.py:327-340`; `src/personal_assistant/gateway/session_composition.py:80-89`). | Core condition tests, feature-default wiring, PA projection, and SDK PromptSlots restart tests included in the reconciliation run. | aligned |
| Prompts Scenario: 工具相关通用 feature 由会话开关与工具在场门控 | Existing memory/skill guidance conditions check both feature and tool presence (`src/agent/core/agent/prompt_sections/core_sections.py:243-268`). | `tests/unit/agent/test_core_prompt_conditions.py:23-54,68-95`. | aligned |
| Prompts Scenario: 无工具通用 policy 继承默认值并接受显式布尔覆盖 | The policy declares `requires_tool=None`, defaults true, and footer applies its boolean without tool gating (`src/agent/core/agent/prompt_sections/feature_registry.py:77-88`; `src/agent/core/agent/prompt_sections/core_sections.py:336-339`). | `tests/unit/agent/test_session_metadata_features_wiring.py:19-43`; `tests/integration/test_personal_assistant_prompt_integration.py:86-128`. | aligned |
| Prompts Scenario: 产品 prompt 只经会话配置改变 | PA projects timezone into complete runtime PromptSlots; Kernel persists/rehydrates PromptSlots at explicit session/runtime boundaries (`src/personal_assistant/gateway/session_composition.py:52-92`; `src/agent/sdk/kernel.py:1115-1167`). | Existing restart/rehydration contract at `tests/contract/test_sdk_kernel_wiring.py:589-622`; PA runtime/preview same-source test at `tests/unit/personal_assistant/test_pa_time_prompt_policy.py:34-82`. | aligned |
| `specs/kernel/sdk-boundary.md` MODIFIED Requirement: Kernel 提供单项中立能力查询 | `Kernel.list_features()` now projects the general runtime policy as the existing `FeatureInfo` DTO; methods/DTO fields are unchanged (`src/agent/sdk/kernel.py:1855-1886`; `src/agent/sdk/dto.py:368-384`). | `tests/unit/agent/test_kernel_list_capability_queries.py:52-90,93-220`; `tests/contract/test_sdk_kernel_wiring.py:525-565`. | aligned |
| SDK Scenario: 能力查询与运行时事实一致 | Models/tools/features/skills remain typed projections of assembled Kernel catalogs; the new feature is sourced from the same registry used by runtime (`src/agent/sdk/kernel.py:1810-1938`; `src/agent/core/agent/prompt_sections/feature_registry.py:54-88`). | `tests/unit/agent/test_kernel_list_capability_queries.py:52-156`; `tests/contract/test_sdk_kernel_wiring.py:525-565`. | aligned |
| SDK Scenario: session 创建时间 policy 可发现且默认开启 | Projection returns `include_session_created_datetime/default_on=True/requires_tool=None`, and runtime footer implements omitted/false semantics (`src/agent/sdk/kernel.py:1869-1885`; `src/agent/core/agent/prompt_sections/core_sections.py:336-339`). | `tests/unit/agent/test_kernel_list_capability_queries.py:65-90`; `tests/integration/test_personal_assistant_prompt_integration.py:86-128`. | aligned |
| SDK Scenario: 消费者可在工具目录中启用 skill_view | Existing Kernel assembly registers `SkillViewTool` in the built-in catalog (`src/agent/sdk/kernel.py:945-984`); feat-530 does not alter that path. | Existing functional coverage at `tests/unit/test_skill_view.py:120-140`; catalog DTO coverage at `tests/unit/agent/test_kernel_list_capability_queries.py:52-62`. | aligned |
| SDK Scenario: 部署级共享 skill 根叠加在每 workspace 布局之后 | Existing resolver construction receives ordered workspace directories followed by shared roots (`src/agent/sdk/kernel.py:1888-1917`). | `tests/unit/agent/test_runtime_skill_resolution_same_source.py:128-180`; ordered same-name assertion at `tests/unit/agent/test_kernel_list_capability_queries.py:190-220`. | aligned |
| SDK Scenario: 无真实 workspace 时只查询共享 Skill | `list_shared_skills()` resolves only configured shared roots (`src/agent/sdk/kernel.py:1927-1938`). | `tests/unit/agent/test_kernel_list_capability_queries.py:159-187`. | aligned |
| `specs/kernel/skills.md` MODIFIED Requirement: skill 列表与显式命令改写 | Existing prompt/list behavior remains; command parser now accepts a sequence of opaque annotation segments (`src/agent/core/agent/skill_commands.py:6-60`; multi-part application at `src/agent/core/agent/runtime.py:67-90,456-471`). | `tests/contract/test_skill_commands_contract.py:4-44`; available-skill prompt coverage at `tests/unit/test_agent_prompting.py:82-125`. | aligned |
| Skills Scenario: 显式 skill 命令被改写 | Parser/rewrite preserves the prior no-argument and argument forms (`src/agent/core/agent/skill_commands.py:30-60`). | `tests/contract/test_skill_commands_contract.py:4-13`. | aligned |
| Skills Scenario: 命令前带一个或多个标注段时改写保留全部标注 | Regex captures zero or more complete bracket segments and reuses the exact prefix in rewritten text (`src/agent/core/agent/skill_commands.py:6-18,54-60`). | Single-prefix and composed time/channel + sender assertions at `tests/contract/test_skill_commands_contract.py:21-39`. | aligned |
| Skills Scenario: 多 part 输入中命令所在 part 被改写 | Runtime iterates ordered `InputPart`s, rewrites the first matching text part, and leaves every other part unchanged (`src/agent/core/agent/runtime.py:67-90,456-471`). | Pre-existing behavior carried forward unchanged by feat-530; unit-added parser tests exercise the only changed condition (multiple annotations). | aligned |
| Skills Scenario: skill_view 启用时 available skills guidance 引导按名加载 | Skills formatter receives actual `skill_view` availability from Core prompt assembly (`src/agent/core/agent/prompt_sections/core_sections.py:194-207`; `src/agent/core/skills/formatter.py:26-40`). | `tests/unit/test_agent_prompting.py:82-106,134-146`. | aligned |
| Skills Scenario: skill_view 关闭时不渲染调用 guidance | The same formatter switches to context-only guidance when `skill_view` is absent (`src/agent/core/agent/prompt_sections/core_sections.py:194-207`; `src/agent/core/skills/formatter.py:26-40`). | `tests/unit/test_agent_prompting.py:108-125`. | aligned |

### Uncovered Observable Behavior

None. `git diff origin/main...a26e5ca4fee9033bd9c701bd9213320b0c83f2da` uses merge-base `c40a9aa80f3f9107327217b868f11ec664d34bf9`; every changed consumer-visible behavior maps to one of the four reconciled deltas above. Optional PA-internal dataclass fields, process-local provenance plumbing, capability docstrings/comments, tests, and evidence do not create additional consumer contracts. Focused reconciliation validation: 195 passed.

Outcome: aligned

# Round 3

## Verification Report: feat-530

> Validation snapshot: `5dd22bb4fa2fbcbd10d247ff3f3c77f71f598535 → d2e7032ea7b963bdf8089c93d00e12bfab6b9c95`

### Summary

Mode: full
Delta range: N/A
Focus issues: current-main Gateway re-integration: Workflow, model-aware effort, typed ingress and time/channel envelope coexistence
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 5/5 requirements covered; 1/1 implementation milestone evidenced |
| Correctness | 12/12 scenarios covered; current-main integration seams covered |
| Coherence | Followed |

All checks passed. Ready for PR.

## Completeness

- Tasks: 8/8 complete (`M1-sealed-human-message-envelope/tasks.md:24-31`). The archived milestone records the implementation, independent gates, corrected deltas, and current-main integration evidence.
- Milestone: feat-530-M1 still satisfies every worker exit criterion after merging current main. Adapter normalization, Dispatcher receipt capture, one-time Pipeline freeze, durable group metadata, normal/steer projection, readable-history handoff, PA timezone policy, and Kernel capability discovery remain present.
- Spec coverage: all five top-level requirements and twelve scenarios retain implementation and permanent regression coverage. The historical real Web IM/Feishu direct/group/catch-up evidence remains correctly scoped to the earlier implementation snapshot; Round 3 does not claim a new real-channel journey at `d2e7032` (`M1-sealed-human-message-envelope/progress.md:31-39`).
- Current-main integration: Workflow runtime/commands/delivery, model-aware `/effort`, typed ingress, reasoning catalog composition, and Gateway-owned workspace roots are all present in the merged tree and covered at their stable seams.
- Prototype / Reference coverage: N/A. `design.md` has no frontend prototype or must-match reference contract.

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 每条真人消息时间 / 长会话跨时段 | `src/personal_assistant/gateway/human_message_context.py:90-116`; `src/personal_assistant/gateway/session_run_coordinator.py:1482-1531`; `src/agent/core/agent/prompt_sections/core_sections.py:320-339` | `tests/unit/personal_assistant/test_human_message_context.py`; `tests/integration/test_personal_assistant_prompt_integration.py` | covered |
| 每条真人消息时间 / Channel 来源时间优先 | `src/personal_assistant/channels/web_relay_adapter.py:346-424`; `src/personal_assistant/channels/feishu/client.py:1161-1195`; `src/personal_assistant/gateway/human_message_context.py:100-108` | Web ISO, Feishu live, REST history, and freezer table tests in the 196-test focused run | covered |
| 每条真人消息时间 / 缺来源时固定 Gateway receipt | `src/personal_assistant/gateway/inbound_dispatcher.py:39-79`; `src/personal_assistant/gateway/human_message_context.py:103-107` | `tests/unit/personal_assistant/test_inbound_dispatcher.py`; receipt fallback tables | covered |
| 逐消息实际入口 / 同一 shadow 中 Feishu 后 Web IM | Channel label derives from each message at `src/personal_assistant/gateway/human_message_context.py:100-115,205-210`; typed shadow identity remains separate at `src/personal_assistant/channels/base.py:23-62` | Cross-ingress durable group assertion at `tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py:245-281` | covered |
| 逐消息实际入口 / 群聊保留 sender 且不输出 chat type/路由身份 | Sender is projected before the frozen header at `src/personal_assistant/gateway/session_run_coordinator.py:1513-1526`; header labels are restricted at `src/personal_assistant/gateway/human_message_context.py:205-210` | Sender/image/mixed-buffer coverage in `test_gateway_pipeline_sender_prefix.py` | covered |
| 逐消息实际入口 / 私聊只输出平台 | `src/personal_assistant/gateway/human_message_context.py:100-116,205-210` | Direct Web/Feishu mapping cases in `test_human_message_context.py` | covered |
| envelope 不改原文 / 原入口查看与复制 | Pipeline completes raw shadow sync before metadata attachment at `src/personal_assistant/gateway/inbound_pipeline.py:150-176`; `attach_frozen_context()` copies metadata without changing text at `src/personal_assistant/gateway/human_message_context.py:119-141` | Raw/model split and header-shaped raw-body tests in `test_gateway_readable_projection.py` and `test_chat_history_hook.py` | covered |
| envelope 不改原文 / Feishu shadow 正文不带 prefix | Typed external identity controls shadow routing at `src/personal_assistant/gateway/inbound_pipeline.py:242-261`; model decoration happens later | External shadow + exact readable-projection coverage in the focused run | covered |
| 新消息稳定延续 / Gateway 重启后沿用原时间与入口 | Buffer stores the frozen metadata allowlist at `src/personal_assistant/gateway/inbound_pipeline.py:453-465`; Coordinator drains metadata unchanged at `src/personal_assistant/gateway/session_run_coordinator.py:1486-1526` | SQLite reopen, mixed buffer, active-steer identical-parts, and historical real restart evidence | covered |
| 新消息稳定延续 / 旧历史不补造 | Only valid v1 provenance is accepted at `src/personal_assistant/gateway/human_message_context.py:53-76`; absent metadata produces an undecorated copy at `src/personal_assistant/gateway/human_message_context.py:144-169` | Legacy/new mixed-row test at `tests/unit/personal_assistant/test_gateway_pipeline_sender_prefix.py:284-307` | covered |
| 非 PA 保持现状 / Coding CLI | Kernel registry default remains on at `src/agent/core/agent/prompt_sections/feature_registry.py:77-88`; footer defaults to old bytes at `src/agent/core/agent/prompt_sections/core_sections.py:320-339` | Default/explicit-true byte identity in `test_personal_assistant_prompt_integration.py`; SDK capability contracts | covered |
| 非 PA 保持现状 / heartbeat、cron、subagent、内部通知 | PA top-level runtime fixes only footer policy at `src/personal_assistant/gateway/session_composition.py:52-97`; freezer accepts only Web relay/Feishu at `src/personal_assistant/gateway/human_message_context.py:205-210` | Human/heartbeat/cron runtime equality and unknown-channel cases | covered |

Current-main coexistence checks:

- Workflow and model-aware effort: Pipeline parses `/effort` before Workflow dispatch and preserves explicit group targeting (`src/personal_assistant/gateway/inbound_pipeline.py:120-139,206-240,302-356`). The combined regression proves `/effort ultracode` stays control-only while a named Workflow ordinary turn receives the frozen header (`tests/unit/personal_assistant/test_inbound_pipeline_session.py:232-398`).
- Group targeting: an `/effort` addressed to another Agent cannot fall through to an `ALWAYS` peer; the peer buffer retains the exact raw command and frozen provenance (`tests/unit/personal_assistant/test_gateway_pipeline_no_fanout.py:208-252`).
- Typed ingress: `InboundIngress` remains the routing identity owner (`src/personal_assistant/channels/base.py:53-62`); `RoutedInbound` carries typed message + Gateway shadow state (`src/personal_assistant/gateway/inbound_models.py:43-48`). Envelope metadata is orthogonal and does not recreate legacy routing dictionaries.
- Workflow delivery and composition: current-main permission bindings, event observer, background reply sender, and Workflow config owner remain wired at `src/personal_assistant/gateway/composition.py:498-646`; feat-530 adds only the shared time/readable owners alongside them.
- Reasoning catalog: one `ModelReasoningCatalog` is constructed from the active LLM config and passed to binder, Kernel shim, config sync, coordinator, and capability reporters (`src/personal_assistant/gateway/composition.py:222-225,280-295,393-425,618-646,722-737`).
- Gateway-owned workspace roots: dynamic creation still uses `_make_workspace_root_factory(config.node.workspace_base)` at `src/personal_assistant/gateway/composition.py:402-425`; session/runtime SDK calls use the captured local Agent workspace (`src/personal_assistant/gateway/session_run_coordinator.py:1223-1230,1592-1625`). The opaque IM mirror boundary and import boundaries pass independently.

Independent validation at `d2e7032`:

- Focused feat-530 + current-main integration set: 196 passed.
- Import / SDK / Gateway-owned workspace boundary set: 23 passed, 48 deselected.
- Complete non-E2E collection: 3444 selected tests; `pytest -m 'not e2e' -n 4` exited successfully.
- Ruff over `src/personal_assistant`, `src/agent`, and affected unit/contract/integration tests: passed.
- `scripts/docs_check.py`: passed (210 maintained Markdown sources, 70 required routes).
- `git diff --check 5dd22bb4f..d2e7032ea`: passed.

The added integration tests protect distinct stable seams: one checks Workflow/effort command dispatch composed with envelope projection, and one checks group control targeting composed with raw durable buffering. They do not duplicate the lower-level formatter/parser tests and do not turn historical real-stack evidence into permanent E2E tests.

## Coherence

| design / architecture decision | 遵守? | 代码证据（file:line） |
|---|---|---|
| 1. Dispatcher 固定 receipt，Pipeline 只 freeze 一次 | 是 | `src/personal_assistant/gateway/inbound_dispatcher.py:39-79`; `src/personal_assistant/gateway/inbound_pipeline.py:150-163` |
| 2. Adapter 只归一化 provider time，Feishu live/history 共用 parser | 是 | `src/personal_assistant/channels/web_relay_adapter.py:346-424`; `src/personal_assistant/channels/feishu/client.py:1161-1195`; `src/personal_assistant/channels/feishu/adapter.py:383-468` |
| 3. v1 稀疏 header，sender/附件顺序保持 | 是 | `src/personal_assistant/gateway/human_message_context.py:90-169`; `src/personal_assistant/gateway/session_run_coordinator.py:1482-1531` |
| 4. Gateway 启动时共享一份 timezone snapshot | 是 | `src/personal_assistant/gateway/composition.py:222-225,280-295,618-653,745-747` |
| 5. raw/model/readable 分层，readable 只 exact provenance 消费 | 是 | `src/personal_assistant/gateway/session_run_coordinator.py:1214-1236,1482-1531`; `src/personal_assistant/gateway/readable_input_projection.py:8-59`; `src/personal_assistant/hooks/chat_history.py:62-90` |
| 6. complete-runtime feature 控制 session-created datetime | 是 | `src/agent/core/agent/prompt_sections/feature_registry.py:77-88`; `src/agent/core/agent/prompt_sections/core_sections.py:320-339`; `src/personal_assistant/gateway/session_composition.py:52-97`; `src/agent/sdk/kernel.py:2269` |
| 7. cache/历史只追加，旧 bytes 不重写 | 是 | Decoration occurs only during new admission at `src/personal_assistant/gateway/session_run_coordinator.py:1482-1531`; missing provenance remains plain |
| 8. 不新增 PA-specific SDK/IM schema/DB table/时间工具 | 是 | Existing SDK feature catalog and existing group metadata JSON are extended; SDK/import contracts pass |
| Current-main Workflow / effort / typed ingress 与 envelope 正交组合 | 是 | `src/personal_assistant/gateway/inbound_pipeline.py:120-240`; `src/personal_assistant/gateway/session_run_coordinator.py:794-951`; combined tests cited above |
| #274 Gateway-owned workspace root 边界不倒退 | 是 | `src/personal_assistant/gateway/composition.py:402-425`; `tests/im_service/contract/test_workspace_root_mirror_contract.py:13-126`; workspace/import focused set passes |

Architecture remains coherent with `SPEC.md`: PA imports the Kernel only through `agent.sdk`; Core stays product-neutral; IM does not import or directly access Agent/Gateway workspaces; feat-530 extends existing ingress, runtime feature, group metadata, and hook mechanisms instead of creating parallel routing, timing, or workspace authorities.

### Prototype / Reference Contract

N/A.

## Issues

### CRITICAL（提 PR 前必须修）

None.

### WARNING（提 PR 前必须修）

None.

### SUGGESTION（可以修）

None.
