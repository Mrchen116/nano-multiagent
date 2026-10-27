# Validation and delivery record

## Authorized scope and baseline

- Sole isolated checkout: `/Users/czj/.codex/experiments/pa667-issue361/repository`; branch `codex/feat-625-ab-e2e`.
- Original shallow baseline: `5454f3140f9c92532c690db8dec80b9f77080384`. The owner explicitly requires no later implementation/history fetch before final delivery synchronization. Initial gates use this known baseline, **not a claim that current origin/main has been fetched**.
- Current workflow comes from the supplied read-only `current-workflow` snapshot. The original unit, independent design review, and implementation were produced from this baseline, not copied from an older feat-625 implementation.
- No merge, deployment, package publication, shared 4000 change, or change to `/tmp/pa667-issue361-runtime` is authorized or performed.

## Initial implementation freeze

| Field | Actual value |
|---|---|
| validated_at | `dfee3df40116757346ef6a7edcaa5d10734c9a61` |
| executed_base | `5454f3140f9c92532c690db8dec80b9f77080384` (authorized independent baseline) |
| working tree at freeze | clean; executor verified |
| diff check | clean |
| executor workspace build | `pnpm build`: passed |
| executor workspace typecheck | `pnpm typecheck`: passed |
| executor frozen full Node regression | `env -u NANO_OWNER_CONFIG_ROOT pnpm test`: 109 files / 494 tests passed, 58.60s |
| implementation narrow regression | 10 files / 49 tests passed; see [M1 evidence](M1-auto-review-retry/progress.md) |
| runtime dependency boundary | 13 tests passed; see M1 evidence |
| independent static / product gates | R1 dispatched against this freeze; pending, not passed |
| final sync / effective_base / effective_through | pending |
| PR / remote CI | not yet created / not yet run |

Node commands use the supplied Node 24 binary. Test commands unset inherited `NANO_OWNER_CONFIG_ROOT`; configuration expectations otherwise resolve the host Harness owner root rather than the isolated fixture root.

### Broader checks and environmental dispositions

- Pre-freeze full Node run: 108 files, 490 passed / 1 failed. The failure was the old context-window diagnostic substring. The final narrow fixture preserves no-verdict, config category, one attempt, zero extras, original return-to-agent denial, no overflow reviewer request and no overflow effect. See M1 validation history for the explicit before/after reason; no routing assertion was removed to hide failure.
- Unchanged frontend: 100 files / 936 tests passed, including interactive-asset check. `npm audit --audit-level=critical` exited successfully; 11 existing noncritical findings remain (4 low / 2 moderate / 5 high); no dependency changes were made to hide them.
- Python non-E2E baseline: 61 passed / 1 failed / 31 deselected. The sole failure is the diff-aware new-test-size gate attempting `git diff origin/main...HEAD` when the deliberately shallow isolated clone has no origin/main ref. It must be rerun after authorized final sync; this is not recorded as a passed gate.
- Ruff check and format check passed (83 Python files).
- Documentation integrity passed (244 maintained sources / 67 required routes before this record). The wrapper initially selected a Python without PyYAML; the same checker passed with the explicitly authorized installed interpreter. No dependency or product change was made to bypass it.

## Isolated product runtime proof

The baseline checkout lacks the current workflow's daily template/profile. The caller approved the existing default E2E stack as the available equivalent for this scoped global-Agent journey. Two dedicated global CC/Codex Agents, actual IM/Work entry points and isolated owner/workspaces are retained; this does **not** claim validation of the daily P/E/Q team fixture or unaffected team behavior.

- Own IM: `127.0.0.1:53939`, PID 95854. Its source and frontend source are unchanged by this unit; baseline-built artifacts and this isolated process are reused.
- After the frozen workspace build, executor restarted **only the own Node** with the explicit checkout-local `.gateway-config.yaml`.
- New Node PID 3657, DSH PID 3660 (child of 3657), state ready/connected. Prior Node/DSH PIDs 95896/95899 were confirmed exited.
- The DSH profile's `@nano/dsh-integration` link resolves to this checkout's `packages/dsh-integration`.
- Both dedicated Agents compile as global DeepSeek Flash execution, Auto enabled, skip disabled, unattended fallback deny; respective rules nano/CC and Codex. The reviewer is a separate Luna registration on the own fault proxy `127.0.0.1:56096`; main-model routing is unchanged.
- The proxy forwards healthy reviewer traffic to the already running 4000 service; it does not alter or restart that service. Its actual live probe returned HTTP 200/PONG before product acceptance. A probe is availability evidence, **not** a plugin-journey pass.
- Fault injection is scoped by planned tool name and a unique argument marker. Proxy HTTP request counts are not review attempt counts: CC stages and Guardian inspection steps can produce multiple model requests in one complete attempt. Synthetic verdict usage must be labeled synthetic, never live measurement.
- Product review uses the actual isolated public API used by the client, not policy helper calls. Public `session.observe` capture will be performed through the existing RuntimeClient only after the own Node and DSH are stopped and their exit confirmed. No private database read substitutes for that consumer.

Frozen compiled artifact SHA-256 values, unchanged before and after the own Node restart:

| Artifact (`packages/dsh-integration/lib/policy/`) | SHA-256 |
|---|---|
| approval.js | `c0b9a4efbc710834273deee4c393e739a3a33f653535ff45678cddd1c48a7bcd` |
| retry.js | `84120fcf5012f01bad50b6c41ed8f772be1fa1cc381205238b1c77455e8f4084` |
| classifier.js | `f1df526865a1f501b762abb7a33b54653307d4bf0493d6916fabfb0229bdd453` |
| codex.js | `3bbd2ba5ec9699739dafec2848e8ec599736e26424981eaff4106ff63e42c670` |

## Product availability and evidence-permission boundary

- The first real CC and Codex tasks on the default DeepSeek Flash execution model both stopped in turn 1 with HTTP 402 / QUOTA (Insufficient Balance), before any tool. This is a real main-provider availability failure, not a retry-feature pass or failure.
- The caller confirmed that DeepSeek was an execution default, not an original user constraint. The original failed roles/profiles are preserved; separately named isolated Sol/high execution roles with the same Luna reviewer are permitted using existing registrations/available quota. No recharge or shared-provider change is authorized. The product report must identify this substitution and its limits.
- An attempted raw Work/execution export by the product reviewer was explicitly denied by tool policy. That denial remains in force: no retry, tool/Agent substitution, splitting, or copying raw data into the report. Only permitted public read-only observation and the minimum necessary acceptance conclusions may be used.
- A proposed edit changing the public observe consumer to print only selected-call calculated metrics was also explicitly refused as another form of the same export. The replacement was not applied; that consumer is stopped and must not run. No live observe data was read or exported by it. This audit-consumer evidence gap remains open; it cannot be hidden by changing output paths, tools, Agents, or report formatting.

## Independence and pending work

- Original requirements/design author, design reviewer, implementation worker, independent static reviewer and independent product reviewer are distinct native Agents. Static review explicitly combines code-review and verification responsibilities with separate outputs; it is independent of implementation and product acceptance.
- Static and product R1 were started together on the frozen SHA. Native test evidence may be reused for its actual scope, never as a substitute for the independently observed real product journey.
- After initial implementation handoff, all subsequent fixes belong to the main executor, not a repair worker. Findings will be batched, a new version frozen, and affected gates revalidated with explicit retained-evidence reasoning.
- Final sync, gate invalidation assessment, corrected-delta verification, canonical merge, full local CI, archive, Ready PR and remote CI remain pending. Own test processes must be stopped at overall completion; the checkout remains for PR review.
