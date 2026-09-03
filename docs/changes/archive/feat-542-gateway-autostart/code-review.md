# code-review (feat-542)

- Initial mode: `full`
- Initial head: `aab3ebcfa4d4400d58d920f417c913da6cc3a19b`
- Initial diff: `origin/main...HEAD`
- Closure mode: `closure`
- Closure head: `ac6e8e6f0`

## Initial findings

Phase 1 finder produced eight concrete candidates. Phase 2 assigned one independent
verifier vote to each candidate; all eight were `CONFIRMED` and in unit scope.

```json
[
  {
    "file": "src/personal_assistant/gateway/macos_launch_agent.py",
    "line": 123,
    "summary": "bootout success did not prove the managed child had exited when no state file existed",
    "failure_scenario": "launchctl removed the namespace before the child exited -> rollback or stop continued early and could overlap another Gateway",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "src/personal_assistant/config/local_store.py",
    "line": 433,
    "summary": "a one-launch IM URL could be written back as stable YAML",
    "failure_scenario": "token or config synchronization persisted the runtime snapshot -> --im-service-url replaced the configured durable URL",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "src/personal_assistant/gateway/process_lifecycle.py",
    "line": 640,
    "summary": "configured PATH could hide the lifecycle owner's own ps command",
    "failure_scenario": "gateway.environment.PATH omitted /bin -> foreground startup raised FileNotFoundError before publishing state",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "src/personal_assistant/gateway/process_lifecycle.py",
    "line": 229,
    "summary": "bare start missed a loaded LaunchAgent before state publication",
    "failure_scenario": "launchd job loaded while its child had not written state -> another start replaced the service instead of reporting already running",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "src/personal_assistant/gateway/macos_launch_agent.py",
    "line": 207,
    "summary": "default-on LaunchAgent lost common Homebrew command paths",
    "failure_scenario": "an existing config without gateway.environment.PATH moved from shell launch to launchd -> Agent tools in /opt/homebrew/bin or /usr/local/bin stopped resolving",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "tests/e2e/critical_paths/test_gateway_autostart_critical_path.py",
    "line": 39,
    "summary": "E2E timeout cleanup could leave its launchd job and plist",
    "failure_scenario": "the shell trap exceeded ten seconds -> SIGKILL interrupted cleanup while the launchd-owned Gateway survived outside the shell process group",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": ".claude/skills/prod-fleet-deploy/SKILL.md",
    "line": 172,
    "summary": "standalone deployment snippets reused an undefined prod_worktree variable",
    "failure_scenario": "an operator ran key rotation or verification by itself -> cd used an empty path or the wrong checkout",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "src/personal_assistant/config/local_store.py",
    "line": 1558,
    "summary": "environment parsing accepted names and values rejected by os.environ",
    "failure_scenario": "a key containing '=' or NUL, or a value containing NUL, passed config load -> Gateway crashed while applying the environment",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
```

## Closure

`ac6e8e6f0` fixed the eight roots and added focused regression coverage. Closure
reused one independent verifier per original finding; every vote returned `closed`.
The final closure result is:

```json
[]
```

The closure head also passed 70 focused tests, both local CI pytest shards
(`1748` and `1810` tests), repository Ruff/format/docs checks, and the real macOS
LaunchAgent journey (`1 passed`).
