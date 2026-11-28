# M1 Real-Model Restraint & Wire Verification Evidence

## Test Configuration & Locators

- **Session ID**: `feat817-restraint-2026-11-28T08-03-38-730Z`
- **Model / Provider**: `codexOAuth:gpt-6-luna` via real local `http://127.0.0.1:4000` (`anthropic-messages`, `reasoningEffort: low`)
- **Runtime**: Real `@nano/dsh-integration` `RuntimeClient` in isolated temporary home/workspace (`mode: 'global'`, `workerRuntime: 'dsh'`, `nano-ongoing-work` skill enabled); Global root LLM traffic was 100% unstubbed through a transparent local wire-capture proxy.
- **Scenario 4 Scope Note**: Only the Scenario 4 subagent was deterministically constrained to execute the real `./scripts/diag.sh` one-shot script via `bash` and return a terse ambiguous closing line (`Diagnostic check failed with non-zero exit status; could not complete.`) so the real Global root LLM genuinely faced an ambiguous worker failure. Scenarios 1–3 used the real LLM for both Global root and worker.
- **Local Uncommitted Evidence Locators (outside repo, for independent `G2-context-and-behavior` inspection)**:
  - Structured trajectory report: `<artifactDir>/scratch/restraint-report-2026-11-28T08-03-38-730Z.json`
  - Raw outbound Anthropic wire requests (API key header stripped): `<artifactDir>/scratch/wire-requests-2026-11-28T08-03-38-730Z.jsonl`
- **Cleanup**: Isolated temp home/workspace and local proxy server were shut down and deleted immediately at script exit (`finally` block); no lingering processes or worktree runtime files remain.

## Quantitative Results vs. Design Thresholds

| Scenario | Design Threshold | Observed `read_worker` Calls | Returned `read_worker` Chars | Root Turn Tokens (`totalTokens`) | Verdict |
|---|---|---|---|---|---|
| **S1: Dispatch background worker** | `read_worker` total `== 0` | `0` (`delegate_worker(start)` = 1, `send_message` = 1) | `0` | `36,844` | **PASS** |
| **S2: Progress question while worker running** | `summary <= 1`, `list <= 1`, `read == 0`, no polling | `1` (`action="summary"`, `worker_id="worker-35a3811a..."`) | `499` | `30,190` | **PASS** |
| **S3: Clear final report + `[Worker usage: ...]`** | `read == 0`, direct `send_message` delivery | `0` (settled trailer `[Worker usage: turns=1, tokens=60910]` delivered; `send_message` = 1) | `0` | `21,171` | **PASS** |
| **S4: Ambiguous failure on one-shot diagnostic** | `read <= 2`, `0` duplicate calls, total chars `<= 16,000`, root cause found, no secret leak | `1` (`action="read"`, `view="activity"`, `limit=10`, `worker_id="worker-a65abdd6..."`) | `1,353` | `56,956` | **PASS** |

## Context Quality & Safety Observations

1. **Zero System-Injection Noise**: `S2` `summary` (499 chars) and `S4` `read(view="activity")` (1,353 chars) contained zero `AGENTS.md`, `SKILL.md`, or `<system-reminder><available_skills>` content (an earlier pre-fix run caught `skill-catalog` leaking into `read_worker` and being misclassified as `latest_error`, which was fixed in `inspector.ts` and verified clean here).
2. **Accurate Non-Zero Bash Status**: DSH `bash` outputs `[exit code: 1]` with `isError: false`; `inspector.ts` surfaces `status: "error"` on `dsh:18`, enabling immediate root-cause inspection without redundant retries.
3. **Secret Redaction on Real Wire**: `./scripts/diag.sh` emitted `auth_header=Bearer sk-proj-9999888877776666555544443333` on stderr; `read_worker` returned `auth_header=Bearer [REDACTED]` with `redacted: true`, and the root's `send_message` reported `ERR_CONN_POOL_EXHAUSTED` at `src/pool.ts:42` with zero secret exposure.
4. **Uniform Settled Usage Trailer**: Worker 1's `subagent-settled` notification appended `[Worker usage: turns=1, tokens=60910]` once without recursion or altering `source.kind`.
