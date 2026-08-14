# Verification Report: feat-523

> Validation snapshot: `6683c3f10 → 1c15711ba32bf0eaaa1238a3871dc1599fa784f4`

> This report is rebased after `bec1cce0bb65148f6e0a918e3f9846040f05300f`, whose only change is the independent Round 3 design-review record; the validated implementation head remains `1c15711ba`.

## Summary

Mode: full
Delta range: N/A
Focus issues: N/A
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 1/1 milestone complete; 3/3 requirements mapped |
| Correctness | 8/8 first-spec scenarios and 5/5 Gateway delta scenarios covered |
| Coherence | Followed |

Independent checks at this snapshot passed:

- `pytest tests/unit/personal_assistant` — 1085 passed (one third-party Lark protobuf deprecation warning).
- `pytest tests/contract/test_cli_sdk_only_contract.py tests/contract/test_core_no_platform_imports.py` — 5 passed.
- `ruff check src/personal_assistant tests/unit/personal_assistant`, `python scripts/docs_check.py`, and `git diff --check 6683c3f10..HEAD` — passed.

## Completeness

- Tasks: no `tasks.md` is present. This is permitted for the unit; M1's implementation and worker exits are evidenced by the typed config and pure formatter, accepted/recovery lifecycle model propagation, cached terminal projection, permanent tests, Gateway delta, and isolated Feishu evidence (`design.md:182`, `M1-gateway-runtime-footer/evidence.md:3-25`).
- Spec coverage: all three first-spec requirements are implemented. The Gateway delta is a narrow additive contract and maps each observable footer condition to the same implementation.
- Prototype / Reference coverage: N/A. The design has no frontend prototype or reference contract.
- Isolated E2E precondition: the repository-owned, secret-free fixture enables only the dedicated E2E stack (`config/e2e/gateway.yaml:12-16`); the Runbook now records that reviewers must use this fixture rather than alter local or production config (`design.md:170-176`). This matches the recorded dedicated Feishu round trip and its plain Web IM shadow (`M1-gateway-runtime-footer/evidence.md:12-25`).

## Correctness

| Requirement / Scenario | Implementation evidence | Permanent test / durable evidence | Status |
|---|---|---|---|
| Final external reply shows resolved model and actual context percentage | `runtime_delivery/context.py:426-453` freezes accepted model; `runtime_delivery/observer.py:533-561` builds terminal facts from successful `turn_end`; `runtime_footer.py:47-60` formats and rounds/clamps | `test_runtime_footer.py:28-44`; `test_gateway_relay_lifecycle.py:887-1002`; E2E evidence | covered |
| Intermediate text, tool, approval, control, and internal messages have no footer | `observer.py:316-372` chooses the projection only for `phase="final"`; `observer.py:1510-1519` invokes final mirror only at `turn_end`; `session_run_coordinator.py:1638-1696` consumes a projection only in the normal external final fallback | `test_gateway_relay_lifecycle.py:948-1002`; existing control-delivery suite in `test_external_visible_delivery.py` | covered |
| Missing facts silently degrade to one available value or plain text | `runtime_footer.py:47-60` only appends valid model / prompt-window values and returns original text when neither exists | `test_runtime_footer.py:66-107` | covered |
| Default configuration exposes nothing | `DisplayConfig` defaults false (`config/local_store.py:317-326`); formatter retains plain text when disabled (`runtime_footer.py:34-37`) | `test_runtime_footer.py:12-25`; `test_local_store.py:190-219` | covered |
| Global enable applies to every external adapter name | `runtime_footer.py:40-44` uses the global value absent a platform override | `test_runtime_footer.py:66-107` exercises a non-Feishu future channel | covered |
| Platform override can disable a globally enabled footer | `runtime_footer.py:40-44`; typed parser preserves explicit platform booleans (`config/local_store.py:1472-1512`) | `test_runtime_footer.py:47-63` | covered |
| Platform override can independently enable Feishu | `runtime_footer.py:40-44`; config round-trip writes and reloads the explicit override (`config/local_store.py:938-947`) | `test_runtime_footer.py:28-44`; `test_local_store.py:222-284` | covered |
| Internal Web IM and external shadow retain original body | shadow preparation receives `cleaned_text`, while external sender receives only the cached final projection (`observer.py:332-369`) | `test_gateway_relay_lifecycle.py:942-1002`; E2E evidence | covered |
| Exact observer/fallback projection and one-final-bubble behavior | observer caches the one external string before the mirror branch (`observer.py:533-561`); composition exposes it read-only to fallback (`composition.py:506-519,629-645`); fallback sends that value and router semantic-dedupes final text (`session_run_coordinator.py:1661-1695`, `outbound_router.py:180-194`) | `test_session_run_coordinator_terminal.py:336-381`; existing cross-path router tests in `test_gateway_web_relay_adapter.py:267-308,493-537` | covered |
| Recovery successor retains the admission-resolved model before it seeds a new delivery context | recovery handoff receives the frozen model and emits it on `recovery_adopted` (`session_run_coordinator.py:1434-1441,2195-2202,2287-2298`); lifecycle seeding uses the same update carrier (`runtime_delivery/lifecycle.py:44-50`, `runtime_delivery/context.py:426-453`) | `test_recovery_handoff_coordinator.py:36-62,101-128`; affected footer/lifecycle suite also passed | covered |

The five delta scenarios are respectively covered by the first, fifth/sixth/seventh, seventh, second/eighth, and third rows above; no new externally observable behavior in `6683c3f10..1c15711ba` is outside the delta. The final recovery-only correction preserves the existing run-bound model invariant for an adopted successor.

## Coherence

| design decision | 遵守? | Code evidence |
|---|---|---|
| D1: observer formats once; mirror and fallback consume the cached external projection | 是 | `observer.py:533-561`, `observer.py:1513-1519`, `session_run_coordinator.py:1661-1695` |
| D2: default-off typed global setting with full platform precedence and fixed two fields | 是 | `config/local_store.py:317-326,938-947,1472-1512`; `runtime_footer.py:40-60` |
| D3: admission-frozen model plus successful-terminal facts make both paths byte-identical, including recovery adoption | 是 | `session_run_coordinator.py:1421-1441,2195-2202,2287-2298`; `runtime_delivery/context.py:426-453`; `composition.py:640-644` |
| D4: one small pure Gateway formatter, not adapter or IM forks | 是 | `runtime_footer.py:1-61`; only Gateway composition imports it (`composition.py:77,506-519`) |

The implementation preserves the repository architecture: it remains inside `personal_assistant`, leaves `IM`, adapters, and `OutboundRouter` generic, and passed the relevant import-boundary contracts. It adds no cross-process filesystem dependency or parallel configuration owner.

## Prototype / Reference Contract

N/A.

## Issues

### CRITICAL（提 PR 前必须修）

None.

### WARNING（提 PR 前必须修）

None.

### SUGGESTION（可以修）

None.

All checks passed. Ready for PR.

## Corrected Delta Reconciliation

> Reconciled snapshot: `6683c3f10 → d46478a726434d0474979670df3cb84b6da8b5fe`

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `external-channels.md` Requirement: 外部 channel 最终回复的可配置运行信息页脚 | `runtime_footer.py:20-60` resolves the platform policy and renders only the available model / prompt-window percentage; `composition.py:506-519` injects that one policy into Gateway delivery | `test_runtime_footer.py:12-107`; targeted verifier run: 109 passed | aligned |
| Scenario: 全局启用后外部最终回复显示本轮运行信息 | The accepted lifecycle carries the resolved model (`session_run_coordinator.py:1418-1441`); terminal facts are cached from the successful `turn_end` and passed to the formatter (`runtime_delivery/observer.py:533-561,877-878`) | `test_gateway_relay_lifecycle.py:887-1002`; real isolated Feishu result in `M1-gateway-runtime-footer/evidence.md:12-25` | aligned |
| Scenario: 单一外部 channel 覆盖全局设置 | `runtime_footer.py:40-44` gives an explicit adapter-platform value precedence over the global flag; typed parsing retains explicit `true` and `false` overrides (`config/local_store.py:1472-1512`) | `test_runtime_footer.py:47-63`; `test_local_store.py:222-256` | aligned |
| Scenario: 单一外部 channel 可以独立启用页脚 | The same precedence path applies an explicit `feishu` enable even while the global default is false (`runtime_footer.py:40-44`) | `test_runtime_footer.py:28-44`; `test_local_store.py:222-256` | aligned |
| Scenario: 非最终或内部消息不附加运行信息 | The projection is created only for `turn_end` (`runtime_delivery/observer.py:867-878`); intermediate sends retain `cleaned_text`, while final sends use the cached value and shadow records retain plain text (`runtime_delivery/observer.py:316-369,1510-1519`) | `test_gateway_relay_lifecycle.py:948-1002`; isolated shadow evidence in `M1-gateway-runtime-footer/evidence.md:20-21` | aligned |
| Scenario: 运行信息缺失时静默省略 | The formatter emits only valid values and returns the unmodified body when neither is available (`runtime_footer.py:47-60`) | `test_runtime_footer.py:66-107` | aligned |

### Uncovered Observable Behavior

None. The final unit diff's only new external presentation surface is the opt-in footer above. Its accepted-model propagation (including recovery adoption at `session_run_coordinator.py:2195-2202,2287-2298`) preserves that same run-bound model fact rather than creating a second user-visible feature; `test_recovery_handoff_coordinator.py:100-128` covers it. The committed `config/e2e/gateway.yaml:12-16` only enables the dedicated isolated Feishu fixture and does not alter production or local defaults.

Outcome: aligned

# Round 2 — Native Feishu Card Reverification

> Validation snapshot: `6683c3f10296a971affefc3f7e5eb3bba58bf67f → c4d411dd8aef8faaf72839602cdbe4d90e18672d`
>
> Mode: `full` · Delta range: N/A · Focus issues: the previous plain-text presentation is superseded by the approved native-card design · requires_full_verification: false

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 1/1 milestone complete; 3/3 requirements mapped |
| Correctness | 10/10 spec scenarios and 7/7 delta scenarios covered |
| Coherence | Followed |

This round verifies the user-corrected Feishu behavior at the exact `c4d411dd8`
implementation commit. The active unit retains a `MODIFIED` Gateway delta for
the still-unmerged evergreen text-footer rule; its replacement describes the
card behavior and does not compete with a second parallel requirement.

Independent checks at this snapshot passed:

- `pytest tests/unit/personal_assistant tests/unit/test_feishu_adapter_send.py tests/unit/test_feishu_client.py tests/unit/test_feishu_client_interactive.py tests/unit/test_e2e_feishu_probe.py` — **1116 passed**.
- `pytest tests/contract/test_cli_sdk_only_contract.py tests/contract/test_core_no_platform_imports.py` — **5 passed**.
- `ruff check src/personal_assistant tests/unit/personal_assistant tests/unit/test_feishu_adapter_send.py tests/unit/test_e2e_feishu_probe.py`, `python scripts/docs_check.py`, and `git diff --check 6683c3f10...HEAD` — passed.

## Completeness

- **M1 (1/1):** its projection policy, final-path propagation, Feishu renderer,
  shared Markdown-image preparation, bounded-card handling, delta, durable
  tests, and isolated Feishu evidence are present at
  `design.md:125-163`, `runtime_footer.py:20-79`,
  `channels/feishu/{client,adapter}.py:134-177,362-370,680-718`, and
  `M1-gateway-runtime-footer/evidence.md:3-24`. The unit has no `tasks.md`;
  the design's single milestone has concrete implementation and evidence
  instead.
- **Spec coverage (3/3):** the final-presentation requirement maps to the
  Gateway projection and adapter card; the config requirement maps to
  `DisplayConfig` and platform precedence; the Web IM requirement maps to the
  original-body-only shadow path.
- **Prototype/reference contract:** N/A. `design.md` has no frontend prototype.
  Its explicit native-card contract is instead covered by the Feishu adapter
  payload test and recorded isolated-platform evidence.

## Correctness

| Requirement / Scenario | Implementation evidence | Permanent test / durable evidence | Status |
|---|---|---|---|
| Enabled Feishu final reply is one native card with body and `model · ctx N%` | `runtime_footer.py:43-51`, `observer.py:332-370`, `adapter.py:160-177,680-712` | `test_runtime_footer.py:26-42`; `test_feishu_adapter_send.py:66-107`; isolated card evidence `M1-gateway-runtime-footer/evidence.md:10-24` | covered |
| Enabled non-Feishu external channel receives the same facts using its existing text capability | `runtime_footer.py:48-51` | `test_runtime_footer.py:45-55` | covered |
| Intermediate, tool, approval, and control delivery does not acquire a footer | `observer.py:332-363,1511-1520`; `adapter.py:671-677` | `test_gateway_relay_lifecycle.py:984-1007`; `test_feishu_adapter_send.py:121-145` | covered |
| Incomplete facts omit unknown fields; no facts leave the body and card transport unchanged | `runtime_footer.py:45-50,65-79` | `test_runtime_footer.py:70-99` | covered |
| Oversized Feishu body remains one UTF-8-bounded card with an explicit truncation marker and retained footer | `adapter.py:680-718` | `test_feishu_adapter_send.py:110-118` | covered |
| Default configuration exposes no runtime information | `config/local_store.py:316-326`; `runtime_footer.py:43-47` | `test_runtime_footer.py:13-23` | covered |
| Global enable covers all external adapters; per-platform settings override it in either direction | `runtime_footer.py:54-62`; `config/local_store.py:1476-1515` | `test_runtime_footer.py:26-67`; `test_local_store.py:222-284` | covered |
| Internal Web IM and the external shadow retain the original body | `observer.py:324-349`; `session_run_coordinator.py:1674-1686` | `test_gateway_relay_lifecycle.py:984-1007`; isolated shadow evidence `M1-gateway-runtime-footer/evidence.md:21-24` | covered |
| Observer mirror and coordinator fallback send the same run-owned projection and hint | `observer.py:534-562`; `composition.py:506-512,640-644`; `session_run_coordinator.py:1665-1704` | `test_session_run_coordinator_terminal.py:337-389` | covered |

The seven delta scenarios are covered by the first five rows plus the
configuration and shadow rows. The `scripts/e2e-feishu-probe.py:162-210,240-259`
probe is a durable E2E helper with safety guards and selects only the nonce-bound
`interactive` reply before checking that the linked shadow lacks `ctx`; its
parser behavior is covered by `test_e2e_feishu_probe.py:60-100`.

## Coherence

| Design decision | 遵守? | Code evidence |
|---|---|---|
| D1: observer creates one run-owned projection; mirror and fallback only consume it | 是 | `observer.py:534-562,1511-1520`; `context.py:109-115`; `session_run_coordinator.py:1665-1704` |
| D2: Gateway owns configuration, fact formatting, and future-channel semantics | 是 | `runtime_footer.py:28-79`; `composition.py:506-512`; no adapter reads config or token/model facts |
| D3: Feishu renders a prepared, single native card within the full UTF-8 budget | 是 | `client.py:321-370,476-490`; `adapter.py:160-177,680-718` |
| D4: `runtime_footer` is final-delivery metadata only; dedupe and Web IM remain generic | 是 | `observer.py:356-370`; `session_run_coordinator.py:1687-1703` |

The change stays within `personal_assistant`, uses the existing Feishu interactive
message seam, and does not add an IM-to-Agent import, cross-process filesystem
coupling, or a second configuration owner. The targeted import-boundary contracts
passed.

## Prototype / Reference Contract

N/A. The explicit Feishu visual structure in the design is represented by the
card payload test and isolated real-platform evidence, not a frontend artifact.

## Issues

### CRITICAL（提 PR 前必须修）

None.

### WARNING（提 PR 前必须修）

None.

### SUGGESTION（可以修）

None.

All checks passed. Ready for PR.

# Round 3 — P1 Runtime-Footer Budget Closure

> Validation snapshot: `2e343507d71434a733ca1430585ce95f7b43ea62 → b58d3be2188758da24c1b05095976c5b62686cb1`
>
> Mode: `targeted-closure` · Focus issues: `P1 oversized runtime footer / card limit` · requires_full_verification: false

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | P1 closure change and its two durable regressions present |
| Correctness | The configured-model-label path and full card payload are bounded |
| Coherence | Followed |

## Focus-Issue Verification

| Focus issue | Implementation evidence | Test evidence | Status |
|---|---|---|---|
| A pathological configured model label could make a nominally truncated Feishu card exceed the 30,000-byte payload limit | `runtime_footer.py:10,67-89` normalizes the model display label at the Gateway policy owner to at most 512 characters before it becomes `runtime_footer`; `adapter.py:680-718` still measures the full serialized UTF-8 card and retains the exact Gateway footer | `test_runtime_footer.py:102-111` protects the 30,000-character model-label projection; `test_feishu_adapter_send.py:126-140` sends that projection through `_build_runtime_card` and asserts the serialized card remains `<30_000` bytes while retaining the footer | closed |

The cap is byte-safe even for multibyte Unicode labels: at most 512 Python
characters can contribute at most 2,048 UTF-8 bytes, leaving the existing card
builder's full-payload check as the final guard. The change remains in the
Gateway's semantic presentation policy; the Feishu adapter does not invent a
second model-label truncation rule.

Independent targeted checks passed:

- `pytest tests/unit/personal_assistant/test_runtime_footer.py tests/unit/test_feishu_adapter_send.py` — **17 passed**.
- `ruff check src/personal_assistant/gateway/runtime_footer.py tests/unit/personal_assistant/test_runtime_footer.py tests/unit/test_feishu_adapter_send.py`, `python scripts/docs_check.py`, and `git diff --check 2e343507d..HEAD` — passed.

## Issues

### CRITICAL（提 PR 前必须修）

None.

### WARNING（提 PR 前必须修）

None.

### SUGGESTION（可以修）

None.

All checks passed. Ready for PR.
