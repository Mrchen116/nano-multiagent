# Validation record

## Versions and scope

- Implementation: `25c6d866fb2423fdb0e2d941deabe48a33dd7f76`.
- executed_base: `a78e9498560f6943e934bc29a68e0ac9918270f1`.
- Initial main: `85910853ebe4a7a22c5b761029cf46da2f78cd5a`.
- First final-sync: `54b1214c8d52dc1645df3b526756b9b2d2353a2a`, effective_base `69d01e4557bcc87a5f7194dcb947c7473ead20d9`.
- Main advanced only with feat-667 input/spec documents; no product, tests, schema, build or config changes. Existing design/code/performance evidence remains applicable. Independent acceptance runs the unchanged implementation built from 25c6d866f.

## Tests and evidence

- Baseline related suite: 4 files / 38 tests passed.
- Red reproduction: expanded the existing ACK-gated stream test to deliver `_COMPLETE` as 9 fragments. Original SingleThread sent each fragment separately; expected merged batch failed. Initial new-worktree test collection lacked built workspace exports; dependencies were built before this valid red reproduction.
- Narrow candidate suite: 8 files / 68 tests passed; then added an ACK-loss parameter, with model-fallback 7 tests passed. Independent reviewer reran model-fallback + contacts + watchdog (10 tests) and server process E2E + interactive replies + lifecycle (15 tests), all passed.
- `pnpm build`: passed. This builds a local candidate only; no package published.
- `pnpm typecheck` and `pnpm check:ios-runtime`: passed.
- `npm ci`, `npm audit --audit-level=critical`, frontend `npm test`: passed; 108 files / 1031 tests. The audit gate passing does not claim all severity levels are absent.
- Python `pytest -m 'not e2e' -q`: 70 passed / 32 deselected.
- Ruff check and format: passed (88 files already formatted).
- docs-check: found two baseline links in feat-665's imported blueprint pointing into the external source bundle. A separate documentation-only commit preserves the source paths as explicit original-bundle references rather than unresolved repository links; no product behavior or requirement changed.

## Backend full-suite timeout investigation

First default-parallel `pnpm test`: 141 files / 765 tests passed, one workspace-tools test exceeded its 90s timeout; overall duration 201.87s. Typecheck/frontend verification and isolated stack preparation overlapped this run. The unchanged workspace-tools test then passed alone in 35.31s. Resource contention is a hypothesis, not a proven root cause; no runtime/test timeout patch was made. A full run with four workers passed: 142 files / 766 tests, 173.58s. This confirms the whole suite under lower local contention without changing product or test timeouts; it does not establish a precise root cause for the initial timeout. Raw logs: `/tmp/perf-666-tests.log`, `/tmp/perf-666-workspace-tools.log`, `/tmp/perf-666-tests-rerun.log`.

## Isolation

Daily stack was built from 25c6d866f and started inside this managed worktree. The first preparation attempt lacked PyYAML on PATH and stopped before services; rerun with the existing project virtualenv succeeded. Extra single_thread Agent `perf-stream` was created through the product API, using the configured real Sol model and isolated workspace. The final acceptance report owns scenario outcomes. Native iOS UI is unchanged; no separate simulator run is required by the CI path filter.

## Real-provider streaming prerequisite

The default Sol route produced one complete text chunk per turn: 2028 and 9130 characters. Read-only inspection of this isolated node's durable runtime events showed `data.stream` with one `text-chunks.texts` entry and empty `dt` in each turn; the IM single delta therefore did not result from batching many upstream chunks. The external local proxy's `src/handlers/messages_stream.py` Responses branch collects the full Codex result before emitting one text delta (approximately lines 169–264). No proxy code/config was changed.

For the gradual-display acceptance, an additional ordinary `perf-stream-incremental` Agent was created through the product API using the existing catalog's real `deepseek:deepseek-v4-flash` / high route; the daily P/E/Q/PA baseline was retained. This isolates the changed delivery path from the preexisting full-response proxy behavior. Acceptance owns the observed verdict. This PR cannot make a provider that sends only a final text chunk become progressively visible during generation.

The configured DeepSeek route returned `402 insufficient_balance_error` during independent acceptance. Small read-only readiness probes of the other existing non-Codex routes returned MiMo 401 and Kimi 403; no credential/account/subscription was changed. The proxy also exposes an existing native `/v1/responses` streaming passthrough (`LLM_PROXY` source commit `0002bee2dbcda8e29c9dda6ebfe9245dfe2847fa`, relevant file clean). A temporary custom model service using `openai-responses` and that same local proxy/Sol account was prepared successfully through the normal isolated product setup API, avoiding the buffering Anthropic conversion. This is test-environment setup only, not a production/proxy change or release content.


## Acceptance closure

Independent acceptance Round 3 passed all five scenarios. The real Sol Responses route emitted 270 deltas across 53.514 seconds; the 1868-character final answer contained each of 50 numbered items exactly once, and delta concatenation, completed payload and HTTP history matched. The earlier single-chunk and unavailable-provider observations remain in acceptance.md as limitations and evidence, not erased or relabeled successful runs. The product code stayed at 25c6d866f throughout. Independent verifier owns the final evidence closure.

The main agent stopped the isolated IM/Gateway/DSH stack after acceptance using `scripts/e2e-down.sh`; local runtime evidence is retained outside Git. No production deployment, package publication or PR merge was performed.
