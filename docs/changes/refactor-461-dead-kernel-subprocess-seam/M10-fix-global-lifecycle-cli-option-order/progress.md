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

- Status: IN PROGRESS.
- Decision pending implementation: command parser 只有在 option 实际出现于 subcommand 位置时才应写该
  destination；缺省解析不能抹掉 root parser 已取得的 value。

## R2 — Final gates

- Status: PENDING.
