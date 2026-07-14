# refactor-461-M10: Global lifecycle CLI option order — Tasks

> 对齐：Round 7 acceptance、`../design.md`、`docs/specs/gateway/service-lifecycle.md`

## 目标

关闭最终产品验收发现的 CLI 目标错配：公开全局 `--config` / `--im-service-url` 在 `stop` 或
`restart` 前出现时，必须仍定位到该自定义 config 的 Gateway，不能被子命令 parser 的空默认值覆盖为
`~/.nano-assistant/config.yaml`。

## 退出标准

- [ ] `--config <A> ... restart` 与 `restart --config <A> ...` 管理相同的 A；前者绝不启动、停止或替换
  默认 config 的 Gateway。
- [ ] `--im-service-url` 与 `--auto-bind` 的 global-first `restart` 调用保持传递给新 Gateway 的行为；
  `stop` 的 global-first `--config` 同样只操作 A。
- [ ] canonical Gateway lifecycle 契约明确 lifecycle target option 在子命令前后的一致目标语义。
- [ ] 新回归、affected lifecycle tests、static、full non-e2e 与隔离真 CLI lifecycle 通过；随后完成独立
  reviewer、verifier 和 final code review。

## 测试策略

- 以 `main([...])` mock 住 public stop/background launcher，精确断言 global-first `restart` 的 stop/start
  都收到 isolated config 和 IM override，且 auto-bind 环境开关被设置；旧 parser 会把 config / IM 变成
  default / `None`。
- 单独守护 global-first `stop`，避免只修 restart 而继续让 stop 操作默认 Gateway。
- 真 CLI 验收使用 worktree 隔离 config 与 ephemeral IM，同时观察 default lifecycle evidence 始终不存在。

## Roadpoints

### R1 — Preserve global lifecycle target values

- [x] C1 `6e73fcd7b`：为 global-first restart / stop 写红测，复现子 parser 以默认 `None` 覆盖 root parser 值。
- [x] C2 `264c5402a`：让子 parser 未显式收到 option 时不写同名 destination；保留 command-first 兼容性。
- [ ] C3：将 option-order target contract 归并到 canonical lifecycle spec，并记录本地验证。

### R2 — Final gates

- [ ] targeted / static / full non-e2e / isolated lifecycle evidence。
- [ ] independent reviewer re-review、delta verifier、final code review 全部通过。
