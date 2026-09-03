# M1 implementation evidence

## Claim

On macOS, a stopped Gateway started through the normal CLI is supervised by one
config-scoped user LaunchAgent by default. It recovers from a crash, manual `stop`
pauses it for the current login while retaining the stable definition, and
`gateway.autostart: false` removes that definition before starting one detached
Gateway. Stable config environment and one-launch CLI controls keep their defined
precedence without persisting transient controls in the plist.

## Baseline and focused tests

- Red config tests initially failed because `GatewayLifecycleConfig` had no
  `autostart` or `environment` fields.
- Red lifecycle tests initially failed collection because the macOS LaunchAgent
  owner and `GatewayLaunchResult` did not exist.
- Focused Green command:
  `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/unit/personal_assistant/config/test_gateway_lifecycle_config.py tests/unit/personal_assistant/test_macos_launch_agent.py tests/unit/personal_assistant/test_gateway_autostart.py tests/unit/personal_assistant/test_gateway_autostart_cli.py tests/unit/personal_assistant/test_gateway_launch.py tests/unit/personal_assistant/test_gateway_main_command.py tests/unit/personal_assistant/test_gateway_pid_lifecycle.py tests/unit/personal_assistant/test_auto_bind.py`
- Result: `65 passed in 1.06s`.
- Expanded Gateway package result: `1133 passed, 1 warning in 26.40s`.
- Repository non-E2E result: `3553 passed, 33 deselected, 20 warnings in 178.74s`.

## Real macOS LaunchAgent journey

Method: `tests/e2e/critical_paths/test_gateway_autostart_critical_path.py` drives
`scripts/e2e-gateway-autostart.sh` with an isolated temporary IM, config, node
identity, workspace, state and config-derived LaunchAgent label. It never reads or
changes `~/.nanoassistant/config.yaml`.

The journey asserts:

1. Normal start reports `Autostart: enabled`, launchctl reports the job loaded,
   state identifies a live Gateway, and the isolated IM reports its node online.
2. The stable plist has `KeepAlive`, the expected absolute interpreter/source
   paths, and no one-launch `--auto-bind` or IM URL.
3. `SIGKILL` produces a different live PID and the node returns online.
4. Product `stop` leaves the stable plist but the current GUI-domain job stays
   unloaded.
5. Bootstrapping the retained stable plist, modeling the next login load, produces
   another live PID and online node.
6. After setting `autostart: false`, normal start reports `disabled`; the stable
   plist and loaded job are absent while one detached Gateway runs.

Command:
`NANO_MULTIAGENT_RUN_LAUNCH_AGENT_E2E=1 NANO_MULTIAGENT_E2E_PYTHON=/Users/czj/Repos/nano-multiagent/.venv/bin/python PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q -s tests/e2e/critical_paths/test_gateway_autostart_critical_path.py`

Result: `1 passed in 18.27s`.

The first run exposed that successful `launchctl bootout` can remain visible to an
immediate `launchctl print`. The later read-only probe showed the same job absent,
and a focused delayed-unload test reproduced the boundary. The implementation now
condition-polls job state after successful bootout; the focused suite and the same
real journey then passed.

## Cleanup and limits

- After the passing run, process inspection found no Gateway for the isolated
  pytest path, the config-derived LaunchAgent plist was absent, and no generated
  isolated config remained.
- The test re-bootstraps the retained stable plist to exercise what login loading
  consumes; it does not log the developer out or reboot the machine.
- The journey does not call a real LLM and does not manage the IM lifecycle beyond
  its own isolated test instance.
