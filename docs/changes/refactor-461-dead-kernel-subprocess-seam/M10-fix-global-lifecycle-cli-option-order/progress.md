# refactor-461-M10 — Progress

## Baseline

- Round 7 acceptance 在真实隔离环境执行
  `main --config <isolated> --im-service-url <ephemeral> --auto-bind restart`；CLI 接受命令，却启动默认
  `~/.nano-assistant/config.yaml` 的 Gateway，使用 IM `:8011` 与默认 log。
- 对照的 command-first 形式 `main restart --config <isolated> --im-service-url <ephemeral>` 正确只替换
  isolated Gateway。审阅方已以公开 default `stop` 清理错误启动的 PID，并确认 default lifecycle evidence
  不存在。
- 根因已用 in-process public entrypoint 稳定复现：root parser 先解析 global target options，随后
  `stop` / `restart` subparser 对相同 destination 写入缺省 `None`，覆盖之前的值。

## R1 — Preserve global lifecycle target values

- C1 `6e73fcd7b`: new behaviour-level tests reproduce both failures. With global-first
  `restart`, the old parser sent both stop/start to the default config and dropped the IM override; with
  global-first `stop`, it likewise managed the default config.
- C2 `264c5402a`: `stop` and `restart` retain their command-first spellings but use
  `argparse.SUPPRESS` for missing post-command target options. A subparser now writes `config` or
  `im_service_url` only when that option was actually supplied after the command, preserving an already
  parsed global value.
- Final code-review finding: the initial regression test exposed a second, real embedded-process bug:
  `main(... --auto-bind ...)` set `NANO_MULTIAGENT_AUTO_BIND=1` permanently in its caller. An independent
  Phase-2 reproduction proved a later no-flag launch inherited it and auto-confirmed binding. C2 follow-up
  `6f799b0a9` scopes the setting to the current invocation, restores the caller's original value in `finally`,
  and still leaves it present while the background child is spawned. `b0fea7bfd` proves an immediate second
  no-flag launch sees no auto-bind value.
- Targeted evidence: lifecycle option regressions, existing main command coverage, the browser-binding regression,
  and the test naming/size contract passed (`19 passed`). Target Ruff check/format and `git diff --check` passed.
- Full-regression diagnosis: the first serial non-e2e run reached `3474 passed` then failed the existing browser
  binding test because this new test invoked `main(... --auto-bind ...)`, whose production entrypoint deliberately
  sets a process-level environment variable. The fixture's initial `monkeypatch.delenv` did not undo that direct
  production mutation. The exact new-test → browser-test sequence reproduced the failure; explicit `try/finally`
  restoration now makes that sequence pass (`2 passed`). This is test isolation only, not a product behavior change.
- Live isolated evidence: final tmux-owned `e2e-up.sh` created IM port `49227` and Gateway PID `63948`.
  `main --config <worktree>/.gateway-config.yaml --im-service-url http://127.0.0.1:49227 --auto-bind restart`
  replaced only that Gateway with PID `65663`; its argv and state both named the worktree config and ephemeral
  IM, while the default lifecycle PID/state/identity files remained absent. Global-first `stop` then returned
  `STOPPED pid=65663` and left that process exited.
- Cleanup note: the deliberately restarted process replaced the e2e script's recorded Gateway generation, so
  `e2e-down.sh` correctly failed closed rather than signalling the new PID through stale ownership evidence.
  After public isolated `stop` and verification that both known Gateway PIDs had exited, only the stale external
  PID file was removed; `e2e-down.sh` then validated and stopped its IM generation. All generated PID,
  identity, state, config, lock, port-map, and tmux artifacts were absent afterward.
- Full non-e2e: `3475 passed, 1 skipped, 20 deselected, 16 warnings in 538.83s` after the production auto-bind
  restoration fix. The stricter same-process second-launch assertion added afterward passed in the final targeted
  bundle above; it changes no production code.
- Status: LOCAL GATES COMPLETE; independent product re-review, delta verifier, and final patch code review pending.

## R2 — Final gates

- Status: PENDING.
