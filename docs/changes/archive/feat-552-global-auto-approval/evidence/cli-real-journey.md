# T1 CLI real execution evidence

## Result and scope

One real Coding CLI PTY journey completed an explicitly authorized temporary Python project: three files were created, one `unittest` passed, and a server bound only to `127.0.0.1:62670` returned HTTP 200 with the expected marker before exiting. Seven real Terra S1 decisions returned `<block>no</block>`; no manual permission response, skip mode or allowlist was used. This is implementation verification of the CLI interaction and shared kernel, not a reviewer acceptance verdict or a classification-accuracy estimate.

The journey exposed a separate request-shape defect: the Anthropic mapper omitted S1 `stop_sequences` even though the gate supplied it. After the integration owner fixed that mapping, a small additional real PTY write/read task captured Terra S1 with `stop_sequences=["</block>"]`, budget 2112, disabled thinking and the complete policy. The fix confirmation is recorded separately below; the initial seven requests are not retrospectively described as having the missing field.

## Baseline, entry and isolation

- Unit worktree: `.worktrees/unit-feat-552`, branch `codex/feat-552`, HEAD `1d22797b40b4f6affb9f8b1d1d21c14c8eda4abe` plus the in-progress unit implementation.
- Session: `sess_84749ba9224aa510`; initial task's proxy request/response range: 2026-09-12 02:31:14.961–02:32:56.928, UTC+08. The stop-sequence confirmation later resumed this same session in a fresh CLI process.
- Main model: `codexOAuth:gpt-5.6-sol`; approval model: `codexOAuth:gpt-5.6-terra`; Anthropic Messages through the existing `http://127.0.0.1:4000` proxy, whose health endpoint returned `{"ok":true}`. The proxy was not restarted.
- Temporary root: `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/nano-feat552-cli-z9lkm8qq` (macOS resolves it under `/private/var`). Workspace is its `workspace/` child; deployment config is `config/.nanocode/`; session data is `workspace/.nanocode/`.
- Both temporary config files contain only `auto_mode.enabled: true` and `auto_mode.dangerously_skip_permissions: false`. No custom allow/deny rules or safe-tool additions were supplied. `HOME` was unchanged.
- `/usr/bin/script -q <temporary-root>/cli.pty.log <unit-python> <temporary-root>/launch.py` ran through an allocated terminal. The actual CLI line editor received the user prompt and later `/exit`; neither a scripted input reader nor `--text` replaced the interactive path.

The default CLI factory cannot meet this test's separate-model/strict-isolation setup: `coding_cli/product.py::build_cli_kernel` fixes the personal global roots and does not pass an independent approval model, while workflow configuration and the banner separately read the personal config path. Following the integration owner's direction, a temporary launcher used the existing `run_cli(kernel_factory=...)` seam to build the real SDK kernel with temporary roots and the two actual models. It retained the original CLI permission coordinator/callback and every real tool, gate and model caller. The two CLI-owned read-only workflow/banner projections used the same temporary files, preventing a side read of personal configuration. No product source, model response or permission decision was replaced.

This covers the real CLI REPL plus real SDK execution using controlled assembly. It does **not** cover the default `python -m coding_cli.main` factory's personal-config loading or add a new CLI configuration interface. The temporary launcher SHA-256 is `8ecfbd686fd220a4456bd332b77b279e6095276b76477778efd24b87ca70ca8e`.

## Authorized input and observed actions

The typed user request named marker `NANO_FEAT552_CLI_Z9LKM8QQ` and explicitly authorized creating `app.py`, `test_app.py` and `web/index.html` in the temporary workspace, running `python3 -m unittest -v`, and starting/requesting/stopping a loopback HTTP server in one Bash invocation. It requested a trap for the specific child PID, an eight-second observation interval after a successful request, and saved `server.log`, `server.pid` and `response.txt`. It prohibited work outside that temporary directory, other network destinations, personal configuration, production and delegation.

| Observable step | Actual result and locator |
|---|---|
| Create project | Three successful `write` results in the session JSONL; `banner()` returns the marker and the HTML contains it. No directory-external path was in these writes. |
| Execute test | Bash ran `python3 -m unittest -v`; output: `Ran 1 test in 0.000s`, `OK`, exit code 0. |
| Start and request service | Bash output: `http_code=200`, `marker_found=true`, `service_pid=44408`. `server.log` records `GET / HTTP/1.1` with 200; `response.txt` exactly matches `web/index.html` (SHA-256 `5a90f931da0646c129336daa0ac21133a0cae6a76d6b5ad7e5fa96c87c6cce5e`). |
| Observe listener independently | A separate read-only `lsof` observer saw PID 44408 running `python3 -m http.server 62670 --bind 127.0.0.1`, listening at `127.0.0.1:62670`, at 02:32:24.413 UTC+08. It observed release at 02:32:33.440. |
| Stop service | The same Bash invocation sent TERM, completed `wait` with status 143 and printed `service_exited=true`; a later real Bash call returned `process_exists=false`. |
| Finish CLI | CLI displayed `State: completed | stop=end_turn`, then accepted `/exit` and returned process exit code 0. |

The first curl connection raced server readiness and was retried inside the generated command. The retained tool output includes that initial connection error; the subsequent HTTP 200, matching body, server access log and independently observed listener establish the final successful request. It was not an approval denial.

## Actual approval requests

All seven captured Terra requests contain the same 127891-character system prompt, SHA-256 `5bdc15970fed2ec73c35b76565ad5add7c1af7c50edb41ddf37da229a86f6c51`. Each was compared byte for byte with `build_system_prompt(AutoModeConfig(), workspace_root=<resolved temporary workspace>, product_config_dir=<resolved temporary global root>, workspace_config_dirname=".nanocode")` from `_auto_mode_policy.py`; every comparison matched the complete `cc-2.1.267-nano-v1` policy. The request budget was 2112, thinking was disabled, the final user text had the pinned S1 suffix, and each response was `<block>no</block>`. No S2, refusal, classifier fault or manual approval was needed for this case.

| Request timestamp, UTC+08 | Action reaching Terra S1 | Result |
|---|---|---|
| 02:31:37.688 | Inspect temporary workspace with Bash | Allow |
| 02:31:47.841 | Write `app.py` | Allow |
| 02:31:50.068 | Write `test_app.py` | Allow |
| 02:31:52.672 | Write `web/index.html` | Allow |
| 02:31:58.866 | Run `unittest` | Allow |
| 02:32:20.978 | Start/request/wait/stop loopback HTTP service | Allow |
| 02:32:42.174 | Verify the server PID has exited | Allow |

Three subsequent `read` calls retained their existing safe-tool behavior. The initial denominator is seven approvals in one authorized task, not seven independent tasks or a benchmark result. This case does not exercise denial, S2, the three/twenty thresholds, assistant-to-human authorization pairing, single-chat PA, restored host-context authority, or the default CLI factory.

### S1 stop-sequence finding

All seven initial Terra `*-req-anthropic_messages.json` captures lacked `stop_sequences`. Source tracing found the gate passed `["</block>"]` and the core hook model caller copied it into `LLMGenerateRequest`; `AnthropicMapper.map_generate_request` mapped budget/temperature/system/tools/extra body but did not serialize `request.stop_sequences`. The OpenAI mapper already serialized its corresponding stop field. This located the gap inside the Nano Anthropic request mapper, before the proxy. No mapper change or bypass was made by this verification owner.

### Real confirmation after the mapper fix

After the integration owner applied the mapping fix, the same temporary launcher was restarted with `--resume sess_84749ba9224aa510`, appending to the PTY log. The new typed user request explicitly authorized only creating `wire_check.txt` in the temporary workspace with `NANO_FEAT552_CLI_Z9LKM8QQ_STOP_FIX`, then reading it back. Real `write` and `read` calls completed, and the file contained exactly that marker plus a newline (SHA-256 `076bdc864e06b9ea6b7befeb8ebcc58098ac3adb83cc9b6439aa90d1d775b1dd`). The CLI reported `State: completed | stop=end_turn` and exited normally after `/exit`.

The new proxy ingress capture `2026-09-12_02-38-39_960-req-anthropic_messages.json` contains:

| Field | Captured value |
|---|---|
| model | `codexOAuth:gpt-5.6-terra` |
| max_tokens | `2112` |
| stop_sequences | `["</block>"]` |
| thinking | `{"type":"disabled"}` |
| suffix | Exact pinned S1 suffix |
| complete system policy | 127891 characters; same SHA-256 `5bdc15970fed2ec73c35b76565ad5add7c1af7c50edb41ddf37da229a86f6c51`; byte-for-byte assembly comparison passed |
| response | `<block>no</block>`, completed at 02:38:42.172 UTC+08 |

This is one additional actual side-effect approval after the mapping change. It confirms the repaired Nano→proxy S1 request shape without repeating the HTTP-service journey or changing policy rules. It does not establish how an external proxy's downstream adapter applies the stop sequence to its own upstream protocol.

## Evidence locations and cleanup

Raw proxy data remains outside the repository at `/Users/czj/Repos/LLM_PROXY/logs/session/2026-09-12_02-30-19_678_sess_84749ba9224aa510/`. The table timestamps identify each request and its paired `non-stream-res` result; the first/last Sol requests identify the main-model conversation. These proxy logs are subject to retention and are not copied into the unit.

The temporary root retains `settings.json`, `launch.py`, `cli.pty.log`, `request-summary.json`, `listener-observation.json`, `cleanup.json`, `stop-fix-confirmation.json`, `cleanup-after-stop-fix.json` and the project/session artifacts for local inspection. At 02:35:17.941 UTC+08, `ps` found neither first launcher PID 41344 nor server PID 44408, and `lsof` found no listener on 62670. At 02:39:40.831, the second launcher PID 52419 had also exited and the port remained free. The observation process exited as well. No task-owned service remains running; no production process or personal configuration was changed, and no temporary artifact was staged or committed.
