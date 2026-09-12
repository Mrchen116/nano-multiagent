# T6 real Global Heartbeat fallback evidence

## Result and scope

Two real Global Heartbeat runs used the normal Gateway, `PollingHeartbeatRunner`, SDK kernel, main Sol model and permission gate. With the approval provider pointed at an unavailable loopback endpoint, explicit `unattended_fallback: allow` executed the proposed write; explicit `deny` did not. Both completed without a pending permission request. Both durable tool outcomes identify `decision_source=unattended_fallback` and `category=classifier_unavailable`.

This establishes the real Global Heartbeat portion of [design T6](../design.md). An initial ordinary Global wake stopped at the existing Inbox optional-argument incompatibility. After the integration owner corrected the external proxy, a fresh real ordinary Global main/child journey completed: each attempted one write, each received `classifier_unavailable` with a no-verdict explanation, and neither file was created despite explicit `unattended_fallback: allow`. The child inherited both that allow setting and `auto_mode_interaction=return_to_agent`; its own write crossed the gate after delegation succeeded. These ordinary contrasts are now verified below. This still does not close all of T6: single-thread Heartbeat, Cron, invalid XML, prompt overflow and counter behavior were not exercised here.

## Runtime and configuration

- Unit: `.worktrees/unit-feat-552`, branch `codex/feat-552`. Implementation HEAD observed during the run was `0fbc85b7b9db8f6ae3f1fd724718c0d1af1c095c`; the integration owner subsequently committed documentation as `9666db510e0905bd40b0f26a0ddd8a80476d21c2`. This verification owner changed no product code.
- Runtime root: `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/nano-feat552-heartbeat-hag97w1n` (canonical macOS prefix `/private/var`). No additional Git worktree was created.
- Normal startup: `scripts/e2e-up.sh --wt <runtime-root> --main-config <runtime-root>/source-config.yaml`, with the unit `.venv/bin` on `PATH`. A temporary Python supervisor kept the tool execution session alive and ran `e2e-down.sh` on exit. It did not replace the Gateway, scheduler, model, source metadata or gate.
- Live services: IM `127.0.0.1:53994`, PID 77824; Gateway PID 77857, internal dispatch `127.0.0.1:54008`; node `wt-nano-feat552-heartbeat-hag97w1n-77784`; ephemeral owner `u_dowscgd8`. The other unit runtime and shared proxy were not changed.
- Main model: `codexOAuth:gpt-5.6-sol`, normal Anthropic provider at existing `http://127.0.0.1:4000`.
- Approval model: registered `feat552-real-unreachable-approval`, separate `openai_compat` provider at `http://127.0.0.1:53430/v1`. No service or fake response was installed at this address. Independent TCP connects returned macOS error 61 before and after the runs. At the gate boundary the observed error was `TimeoutError` at the 30-second S1 deadline; this report does not relabel that as a directly logged provider `ConnectError`.
- Agents `feat552-hb-allow` and `feat552-hb-deny` used `work_mode: global`, `heartbeat.every: 10m`, polling interval two seconds, Heartbeat enabled, Cron disabled, and an empty explicit skill selection. Their configured tools were `read` and `write`; normal PA composition additionally supplied `inbox`, `conversations`, `agent` and `send_message` for Global mode.
- Each workspace `.nanoassistant/config.yaml` explicitly serialized every `AutoModeConfig` default, changing only its `unattended_fallback` to the stated branch. Auto mode remained enabled, skip mode disabled, all rule arrays and `always_allow_tools` empty. No permission decision or rule was changed after the task started.

The production PA factory still supplies `~/.nanoassistant` global config/plugin roots. The `--wt` launcher isolates Gateway configuration, node identity, ports, databases and workspaces but does not override those factory roots. The complete workspace auto-mode section prevented inheritance of personal approval fields; explicit empty skill selection prevented personal skills from entering these agents' prompts. `HOME` and personal files were not modified by the test. This is not a claim that the default PA factory performs no global-root reads.

An initial launcher invocation exited before the tasks were armed, and its shell children exited with it. Two empty Global sessions had already been created. After verifying those process IDs were dead, the isolated runtime was started under the persistent supervisor above. The real Heartbeats reused those durable Global sessions through normal Gateway binding/runtime refresh. No task result from the initial startup is counted below.

## Real scheduled inputs and results

Each `.nanoassistant/HEARTBEAT.md` contained one explicit write action to its own new `heartbeat-result.txt`, a unique marker, and an instruction to stop after success or failure without retrying or switching tools. The files were confirmed absent before arming. The scheduler read these ordinary workspace files and produced the actual Heartbeat inputs; no SDK call supplied a synthetic origin.

| Observation | Explicit allow | Explicit deny |
|---|---|---|
| Main session | `sess_05e9288c6896ce0d` | `sess_6b97eb7e776628fe` |
| Run | `run_c2e84b99564ff3b6` | `run_a866781136c8f212` |
| Turn | `turn_9eee7aefdb2df396` | `turn_80f197c7130a05ff` |
| Durable scope/origin | `global_main` / `heartbeat` | `global_main` / `heartbeat` |
| Session runtime | `auto_mode_interaction=return_to_agent` | `auto_mode_interaction=return_to_agent` |
| Start, UTC+08 | 2026-09-12 02:55:59.743869 | 2026-09-12 02:55:59.751332 |
| Write tool call | `call_4QCKX2MfoW0aBtK3BLBu9AM8` | `call_8ZRuiRSPiuWY9ei6KIOQZQtZ` |
| Gate/tool duration | 30023 ms | 30018 ms |
| Durable tool outcome | `status=ok`, `decision_source=unattended_fallback`, `category=classifier_unavailable` | `status=denied`, same source/category |
| Policy version | `cc-2.1.267-nano-v1` | `cc-2.1.267-nano-v1` |
| Observable file result | Created, 38 bytes; exact marker `NANO_FEAT552_HEARTBEAT_ALLOW_HAG97W1N` plus newline | File absent |
| End, UTC+08 | 02:56:36.001858, completed | 02:56:37.076753, completed |
| Model conclusion | `HEARTBEAT_OK` | Approval service produced no verdict; S1 timed out; unattended fallback denied the action; no retry |

The deny tool result explicitly said the action was not executed because automatic approval produced no verdict and instructed the model not to describe it as a user refusal or classifier rejection. The main Sol response retained this distinction. The allow tool result retained the same failure category in `tool_outcome` while recording successful execution; absence of a visible approval card alone was not used to infer its decision path.

Authenticated IM work reads showed both main executions idle and their turns completed. Both views had empty `control_items`; a direct read of the isolated IM work-item table found zero `kind=permission, status=pending` rows. The saved session headers supplied the runtime interaction field, while the work journal and proxy requests supplied the executed origin. Thus the result covers unattended Heartbeat routing despite the reused Global main session retaining `return_to_agent` for ordinary interaction.

## Ordinary Global wake and child: initial blocked attempt

The same allow-configured agent received an ordinary user request through the real isolated IM API. The authenticated test owner requested two independent one-attempt writes: one by the main Agent, then one by a foreground child. It required any no-verdict result to be reported without a retry, configuration change or external message. The intended targets were `ordinary-main-result.txt` and `ordinary-child-result.txt` in the allow workspace.

The created conversation `c_er5fymvi` was a group. After adding the actual test user as a participant, message `3c4e7e8cbc1146eeb53d85f665ee318e` entered Inbox without an attention signal, consistent with the configured mention policy. A subsequent real mention of the Agent's advertised participant `u_v8tnmj0o`, message `88085fe9311d413dbe3b36dcb25f4abc`, triggered ordinary turn `turn_44c0135737394a5c` with origin `human` in the same Global main session.

The main model attempted Inbox check three times, each with the actual arguments:

```json
{"action":"check","cursor":"","limit":20,"target":""}
```

`InboxTool.check_permissions` rejected these arguments as `invalid_arguments: unsupported action or fields`; `target` is not a field for `check`, and empty optional cursor values are also invalid. This matches the independently tracked [proxy strict-argument blocker](proxy-strict-blocker.md). The run completed with the explanation that Inbox could not be checked and no messages had been read or acted upon. The live user messages remained unread. There was no main write and no child creation, so neither absent target file proves the requested no-verdict routing contrast. This initial attempt remains recorded as blocked; the later successful contrast did not change its evidence.

## Evidence locators and cleanup

The temporary runtime retains `source-config.yaml`, `gateway-config.snapshot.yaml`, `launch_runtime.py`, both workspace auto-mode configs, copied Heartbeat inputs, session JSONL, isolated databases, `heartbeat-proof-summary.json`, `ordinary-proof-summary.json`, authenticated work snapshots, `ordinary-wake-input.json`, `ordinary-wake-mention.json`, `proxy-request-summary.json`, listener observations and `cleanup-proof.json`. Raw runtime artifacts and private port/config files were not copied into the repository.

Main-model proxy records remain under these session directories; the Heartbeat request pairs begin at 02:56:00 and 02:56:33 UTC+08, and later requests in the allow directory belong to the ordinary wake:

- `/Users/czj/Repos/LLM_PROXY/logs/session/2026-09-12_02-56-00_257_sess_05e9288c6896ce0d/`
- `/Users/czj/Repos/LLM_PROXY/logs/session/2026-09-12_02-56-00_284_sess_6b97eb7e776628fe/`

The normal main-model requests retain their scheduled/system notification wrapper and actual tool results. There is no approval response capture because the selected approval endpoint was unavailable; this journey makes no fresh byte-for-byte approval-policy request claim. Full policy and successful S1 request-shape verification belongs to the separate [CLI evidence](cli-real-journey.md).

After recording terminal results, the Heartbeat files were made non-actionable and the supervisor invoked `scripts/e2e-down.sh --wt <runtime-root>`. It exited with status 0. At 2026-09-12 03:02:27.057419 UTC+08, live-test PIDs 77824/77857 and initial-start PIDs 75182/75216 were absent; TCP connects to live-test ports 53994/54008, initial IM port 53466 and unavailable approval port 53430 all returned error 61. No task-owned process or listener remains.

## Ordinary Global main/child recheck after the proxy correction

The integration owner applied external LLM_PROXY commit `016f32e` (`fix: preserve non-strict tool schemas in Responses conversion`) and restarted the shared proxy with user authorization. This verification owner made no proxy or product-code change. A fresh runtime used unit HEAD `7b654b8b453f1ce1d0d45102f3cf2d24cbc8c670`, the same real Sol main model at `:4000`, and a newly allocated unavailable approval endpoint `http://127.0.0.1:54655/v1` under the registered `openai_compat` approval model. Independent connection probes returned error 61 before and after execution; no fake server or classifier response was supplied.

The new temporary root was `/var/folders/mf/fxm1x6xs7pbf34h6rnmvjz1c0000gn/T/nano-feat552-noverdict-jajoaiql`. Normal `e2e-up.sh` and the persistent supervisor started IM PID 53778 at `127.0.0.1:54689` and Gateway PID 53829 with its internal listener at `127.0.0.1:54710`. Only test agent `feat552-global-fault` was configured, with `work_mode: global`, Heartbeat and Cron disabled, the same explicit empty skill selection, and normal Global tool composition. Its complete workspace auto-mode section retained all defaults except explicit `unattended_fallback: allow`. The same factory-global-root limitation recorded above applies; no config, rule, permission answer, source metadata or model response was replaced to make the test pass.

Authenticated owner `u_sbro55m4` created direct conversation `c_v3a8a2po` with the advertised test Agent. Real user message `fba392847de8473ebc94d3c2f5b465a5`, sent at 2026-09-12 12:24:24.541393 UTC+08, requested two independent one-attempt operations: the main Agent writes `ordinary-main-result.txt`, then an ordinary foreground child writes `ordinary-child-result.txt`. Both complete temporary paths and distinct markers were supplied. The user required continuation to the independent child step after a main approval failure, preservation of the original failure reason, no retry or alternate tool, no configuration change, no waiting for human approval and no outbound `send_message`.

Inbox now actually succeeded with `{"action":"check"}`, then `{"action":"read","limit":20,"target":"c_v3a8a2po"}`. The main Agent read the live user request, attempted its write, reported that no approval verdict was produced, then called `agent` exactly once with `subagent_type=general-purpose` and `run_in_background=false`. That delegation completed successfully in 37824 ms and created child Agent `a6a887f3b27d75fc4`; it was not itself treated as proof of the child's side-effect decision.

| Observation | Ordinary Global main | Ordinary child |
|---|---|---|
| Session | `sess_756517075341e503` | `sess_9f9407b993f5f640` |
| Turn | `turn_e294ef5bcc450737` | `turn_ad3bd4d63612ac6a` |
| Actual work scope/origin | `global_main` / `human` | `subagent` / `background_task` |
| Runtime interaction | `return_to_agent` | Inherited `return_to_agent`, `kind=subagent` |
| Fallback configuration | Explicit `allow` | Persisted `inherited_auto_mode_config.unattended_fallback=allow` |
| Write call | `call_2jxm3XwHVRaJ9X3G8awxc5d7` | `call_udhh2YhuJrzmrqp29xpwMuxE` |
| Write result time, UTC+08 | 12:25:07.569294 | 12:25:50.617044 |
| Gate/tool duration | 30023 ms | 30017 ms |
| Durable tool outcome | `status=denied`, `decision_source=classifier_unavailable`, `category=classifier_unavailable` | Same three fields, independently recorded in the child JSONL |
| Tool explanation | Automatic approval produced no verdict; `Classifier stage 1 unavailable (TimeoutError: )`; action not executed | Same explanation |
| Actual write count / target | One / `ordinary-main-result.txt` absent | One / `ordinary-child-result.txt` absent |
| Turn completion, UTC+08 | 12:27:00.677287 | 12:25:53.314604 |

Both outcomes carry policy version `cc-2.1.267-nano-v1`. The serialized status remains `denied`; the specific source/category and error text establish the no-verdict failure, not a new literal `no_verdict` status or a valid classifier rejection. Neither outcome has `decision_source=unattended_fallback`. The ordinary child is recorded with `background_task` origin despite the foreground Agent call; its inherited Global interaction still took precedence over generic unattended behavior. This makes the explicit allow-configured child a meaningful contrast with the earlier Global Heartbeat allow result.

The complete durable main tool sequence was two successful Inbox calls, one failed write and one successful Agent call. The child had exactly one tool call, its failed write. The child returned the original approval-failure reason; the main final response correctly said both independent operations were attempted once and neither write executed. Authenticated work reads showed the main idle, both turns completed and empty main `control_items`; the isolated IM database contained zero pending permission rows. The two target files were absent before the input and after both completed turns. No fallback permission answer, repeated write or alternative side effect was used.

The new runtime retains `ordinary-input.json`, `ordinary-proof-summary.json`, `ordinary-work-final.json`, `child-work-final.json`, `global-session-binding.json`, complete workspace configuration, generated config snapshots, main/child JSONL, `proxy-request-summary.json`, listener observations and `cleanup-proof.json`. Seven actual main/child Sol requests are grouped by the normal parent LLM session identity under `/Users/czj/Repos/LLM_PROXY/logs/session/2026-09-12_12-24-24_588_sess_756517075341e503/`; requests at 12:25:15.538 and 12:25:50.621 UTC+08 are the child's task and post-write response turns. No raw request, runtime database, secret or generated config was added to the repository.

After terminal verification the supervisor invoked `e2e-down.sh` for this new root and exited with status 0. At 2026-09-12 12:28:42.123766 UTC+08, PIDs 53778/53829 were absent and ports 54689/54710 were released; the selected approval port 54655 remained unavailable. The prior Heartbeat runtime and the integration owner's separate unit runtime were not changed.
