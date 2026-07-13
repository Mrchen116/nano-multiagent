# refactor-461-M5: Startup publication and lifecycle cleanup — Tasks

> 对齐: ../design.md；post-acceptance fix round 4

## 目标

把 Gateway 启动发布、进程身份观测与 e2e evidence 清理收敛为 fail-atomic 事务：启动失败必须确认 child 退出或明确保留完整证据；任何 signal 都只依赖同一 PID + 稳定 birth identity；cleanup 在零删除验证全部证据后统一提交，异常时不拆半栈、不误删新实例。

## 退出标准

- [ ] parent start confirmation 后的 state publication 失败会停止并确认 child；cleanup 失败保留原 startup cause、明确报告 PID，且未确认退出时保留 lifecycle evidence。
- [ ] foreground signal handler 安装后的 identity/PID publication 与 runtime 均在同一 `try/finally` 内；PID 原子发布，identity/PID 任一步失败都恢复 handler 且只清本实例证据。
- [ ] Python/public stop 与 e2e shell 使用同一 process snapshot 边界；birth 查询固定 `LC_ALL=C LANG=C TZ=UTC`，新 identity 的 signal authority 只依赖 PID + birth，含空格/引号 config path 不再经 `ps command` + `shlex` 重建。
- [ ] legacy `health_url` state 仍能以本项目确切 foreground command 安全升级；每次 signal 前继续重验同一 birth，locale/TZ 变化不影响身份。
- [ ] e2e-up rollback 无法确认 Gateway 退出时保留 Gateway、IM 与双方 evidence，零 IM signal。
- [ ] e2e-down 对 dangling/nonregular/malformed/drift evidence fail closed；cleanup 先验证完整 PID/identity/state snapshot，再统一条件删除，同 PID/new birth 不误删。
- [ ] full teardown/timeout rollback 只在 Gateway/IM 都确认退出且无协作 writer 后删除 ephemeral `.gateway-config.yaml.lock`。
- [ ] affected、ruff、format、bash syntax、唯一 full non-e2e 与真实 default/e2e lifecycle 全部通过，无本轮 residue。

## 测试策略

- 被测行为（来自退出标准）：parent/foreground publication failure rollback；cleanup failure outcome；PID+birth snapshot 的空格/引号路径与 locale/TZ 稳定性；legacy adoption；e2e survivor/dangling/drift/two-phase cleanup/sidecar removal。
- 已有测试在：`tests/unit/personal_assistant/test_gateway_launch.py`、`test_gateway_process_identity.py`、`test_gateway_pid_lifecycle.py`（扩展）；`tests/integration/test_gateway_legacy_state_upgrade.py`、`test_e2e_up_script.py`、`test_e2e_down_script.py`（扩展）。若单文件超过软上限，按行为新建 `test_gateway_startup_publication.py` 或拆分 e2e evidence 文件，避免继续堆叠。
- 落层/目录/marker：`tests/unit/` 与 `tests/integration/`，marker：无；真实长驻进程只作一次性验收，不进入 non-e2e 套件。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：隔离临时目录中的真实 default start/restart/legacy stop、含空格/引号 config + locale/TZ、cold/timeout/survivor/missing/dangling/cleanup-drift/normal-down 日志与进程核对；结论写入 `progress.md`。

## Roadpoints

### R1 — Startup publication transaction

- 状态：DONE
- [x] C1 Red：补 parent state publication 失败、TERM/KILL 后仍存活、foreground identity fail、PID publish fail 的 public regression。
- [x] C2 Green：让 parent post-spawn state 与 foreground identity/PID publication 各自形成事务；明确 confirmed cleanup result/failure，原子发布 PID，只条件清本实例 evidence。
- [x] C3 Docs：记录失败因果链、evidence 保留边界与回退点。

### R2 — Shared process snapshot and birth identity

- 状态：DONE
- [x] C1 Red：补真实子进程空格/引号 config path、不同 locale/TZ、new identity stop 与 legacy upgrade regression。
- [x] C2 Green：提供 Python/shell 共用的 snapshot 边界；固定 birth 环境；新 identity 只以 PID+birth 授权，argv 仅审计，legacy raw exact command adoption 保持 forward-read。
- [x] C3 Docs：记录 signal authority、legacy 边界与跨环境证据。

### R3 — e2e rollback and evidence cleanup transaction

- 状态：DONE
- [x] C1 Red：补 surviving Gateway 零 IM signal、dangling external/internal、malformed/different state、same-PID/new-birth、cleanup drift 与 sidecar residue regression。
- [x] C2 Green：rollback 遇 survivor 立即停止；down 实施完整 snapshot 的 validate-then-delete；所有 evidence 存在性含 symlink；confirmed full teardown/rollback 清 ephemeral sidecar。
- [x] C3 Docs：记录状态矩阵、两阶段 cleanup 原子边界与回退点。

### R4 — Full validation and live signoff

- 状态：TODO
- 执行 selective affected、`ruff check .`、`ruff format --check .`、`bash -n`；共享 runner 空闲后只跑一次完整 `pytest -m "not e2e"`。
- 真实入口覆盖含空格/引号 config + 不同 locale/TZ 的 default start/restart/stop、legacy state；cold/timeout/survivor/missing/dangling/cleanup drift/normal down，确认无 residue；不改 canonical/acceptance/verification，不发 P2P。
