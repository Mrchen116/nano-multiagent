# refactor-461-M5 — Progress

## Baseline

- Context: unit integration head `d8df1b124` 上执行 post-acceptance fix round 4。
- Scope: `src/personal_assistant/main.py`、`scripts/e2e-up.sh`、`scripts/e2e-down.sh` 与相关 launch/identity/e2e regression；不修改 canonical/acceptance/verification，不发送 P2P。
- Evidence: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -m "not e2e" -q` → `3558 passed, 1 skipped, 23 deselected, 16 warnings in 134.59s`，exit 0。
- Plan: R1 startup publication transaction；R2 shared process snapshot + birth identity；R3 e2e rollback/evidence cleanup transaction；R4 automated + real-entry signoff。

## R1 — Startup publication transaction

- Status: DONE。
- Context: parent waiter 成功后 state write 位于 rollback `try` 外；foreground handler 安装后 identity/PID publication 位于 `try/finally` 外；失败 child 的第二次 wait timeout 被 suppress，caller 无法区分已回收与仍存活。
- Decision: background start confirmation 与 atomic/durable state publication 组成一个 post-spawn transaction。任一步失败先 TERM/process-group TERM，再 KILL/process-group KILL 并二次确认；确认退出后只条件清本 PID/identity/state，未确认则抛 `GatewayProcessCleanupError(pid)` 并保留全部 evidence。外层 `GatewayStartupError` 以 `ExceptionGroup` 同时保留 startup cause 与 cleanup failure。foreground 从 identity build 起全部进入 handler `try/finally`，identity、PID、state 共用 atomic write + file fsync + replace + directory fsync primitive，finally 只按本 identity/PID 条件删除。
- Rationale: publication 也是启动成功的一部分；只要 operator state 不可持久化，就不能返回一个无法正常管理的“成功” child。cleanup 的 confirmed/failed 结果必须成为控制流事实，不能由 suppress 猜测。
- Evidence:
  - Tests: startup publication + launch + process identity + PID lifecycle + forced stop → `37 passed, 2 warnings in 2.02s`。
  - Entry: public `launch_gateway_in_background()` 覆盖 state post-write failure 与二次 wait timeout；public `run_gateway()` 覆盖 identity/PID publish failure 和 handler restore。真实入口统一在 R4 执行。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/unit/personal_assistant/test_gateway_startup_publication.py`；非长驻 public lifecycle regression，marker 无。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Debug note: 首轮 Green 的 cleanup-failure case 传入 `subprocess.TimeoutExpired`，但共享 `_FakeProcess` 只对 `TimeoutError` 执行 raise，导致 timeout 被当普通 wait 返回值。逐字追栈后确认是 C1 夹具未进入预期边界，不是 cleanup 实现；改为 fixture 支持的 `TimeoutError`，并把 child evidence 移到 spawn 时写入，避免 launch preflight 把预置 stale PID 清掉。随后真实 legacy stop 暴露 publication-window 竞态：handler 已安装并收到 SIGTERM 后，`run_forever()` 才清 `_shutdown_requested`，把关闭请求抹掉并最终强杀；根因修复为 fresh runtime 不再在入口重置已发布的 shutdown 请求，真实回归与 shutdown suites 共 `11 passed`。
- Rollback: 回退 `704f770ce` 恢复非原子 PID/state publication 和 suppress cleanup；C1 两提交保留失败契约。
- Commits: C1=`87e730077`,`e53c6e431`；C2=`704f770ce`,`d19183bf0`；C3=`6d2962b74`,本提交。
- Next: R2 shared process snapshot and birth identity。

## R2 — Shared process snapshot and birth identity

- Status: DONE。
- Context: Python public stop 与 shell e2e-down 分别解析 `ps command`；命令含空格/引号时 `shlex` 无法还原 OS 原始 argv，且 `lstart` 受 locale/TZ 影响。新 identity 已持久化精确 launch audit，不应再次从易变的显示字符串授予 signal 权限。
- Decision: 新增 public `GatewayProcessSnapshot` / `read_gateway_process_snapshot()`，在固定 `LC_ALL=C LANG=C TZ=UTC` 下读取 birth/status/raw command，并以 birth-before/birth-after 防 PID 观测竞态。新 identity 的每次 signal 授权只比较 PID + birth；持久化 module/config/argv 仍做静态审计。仅 legacy state 在首次升级时用 anchored、项目专属 foreground command pattern 校验 raw command，升级后立即写入结构化 identity。shell 调用同一 Python snapshot；TERM/KILL 各只向 owned process group 发一次，避免 leader 连续收到 PID 与 group 双 SIGTERM 的 handler-restore 竞态。
- Rationale: OS process birth identity 是同 PID 实例的稳定事实；command 是面向人的渲染，不是 argv 序列。把 raw command 限制在 legacy adoption，既保留 forward-read，又消除新 identity 对 quoting、locale 与 shell parser 的授权依赖。
- Evidence:
  - Tests: R1/R2 affected Python + shell suites → `52 passed, 2 warnings in 21.68s`；`ruff check` 通过，9 个受影响 Python 文件 `ruff format --check` 通过。
  - Entry: 真实 background start/stop 覆盖含空格路径；legacy public stop 在不同 `TZ` 与含空格路径下安全升级并退出；两条真实集成入口 `3 passed in 7.00s`。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/integration/test_gateway_legacy_state_upgrade.py` 与 `tests/integration/test_e2e_down_script.py`；marker 无。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Debug note: 首次真实 quoted-path test 的 child 继承了主仓 `PYTHONPATH`，因此实际运行了错误 checkout；测试显式把当前 worktree `src` 放到 child import path 后，才对本分支做真实验证。随后 background stop 返回 `-15`：追踪 signal 记录确认 stop 先向 PID 发 SIGTERM、再立刻向同组发第二次 SIGTERM；runtime 在第一次 handler 后恢复默认 handler，第二次命中默认动作。修复为每阶段只向 owned group 发一次 signal。
- Rollback: 回退 `9ca8f5826` 恢复 command reconstruction；保留 C1 `dfaa43565` 可稳定重现 quoted path/TZ failure。
- Commits: C1=`dfaa43565`；C2=`9ca8f5826`；C3=本提交。
- Next: R3 e2e rollback and evidence cleanup transaction。

## R3 — e2e rollback and evidence cleanup transaction

- Status: DONE。
- Context: up 的 EXIT rollback 在 Gateway TERM/KILL survivor 后仍继续停止 IM，制造 live Gateway + dead IM 半栈；down 用 `-e` 漏掉 dangling symlink，且 confirmed exit 后逐文件只按 PID 删除，无法识别同 PID/new birth 或相同内容/new inode drift。config sidecar 也没有 full-teardown commit gate。
- Decision: up rollback 以 Gateway 为第一道 barrier，未确认退出立即报告并保留 Gateway/IM 与全部现存 evidence，禁止触碰 IM。down 的 public `capture_gateway_lifecycle_evidence()` 冻结 external/internal PID、identity、optional state 的 regular-file type、device/inode、size、mtime、digest 与内容；每次 signal 前复核同一 revision，退出后 `clear_gateway_lifecycle_evidence()` 先完成全量二次验证，再进入统一删除 commit。所有 residue preflight 以 `-e || -L` 判存在。IM 也必须在 PID evidence 未漂移下确认 TERM/KILL exit。`.gateway-config.yaml.lock` 仅在两服务退出后通过 non-blocking exclusive `flock` 并复核 held/path inode 才删除。
- Rationale: teardown 的“可删”权限必须同时绑定进程实例与 evidence revision；PID 相同不代表文件仍属于旧 lifecycle。Gateway 是 IM teardown 的顺序 barrier，任何 survivor 都应保留完整可诊断现场。sidecar inode 是 cooperative writer 的协调点，只能在没有 writer 时结束其生命周期。
- Evidence:
  - Tests: R1-R3 affected launch/identity/up/down suites → `68 passed, 2 warnings in 71.28s`；新增 IM survivor 与 busy-sidecar regression 后 e2e up/down 全文件 `28 passed`；`bash -n`、受影响 `ruff check` / `ruff format --check` 通过。
  - Entry: shell harness 真实执行 `e2e-up.sh` / `e2e-down.sh`，以真实 child PID 与 exported signal shim 覆盖 Gateway survivor 零 IM signal；真实 filesystem 覆盖 dangling symlink、same-birth-content/inode drift 与 advisory lock holder。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: survivor → 全栈保留；missing/dangling/malformed/drift → 零 signal 或零删除；confirmed Gateway+IM exit → evidence/config/sidecar 全清；IM survivor/busy lock → generated state 保留。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 `856108cbc` 恢复原 rollback/cleanup；保留 C1 `766e34e8e` 可稳定复现八个失败分支。
- Live correction: 第一次真实 live-down 发现 foreground `finally` 在进程退出前会正常自清 internal PID/identity，原 cleanup 把这一提交态误判为 drift。条件提交现仅额外接受“external snapshot 未变，且所有 runtime-owned internal evidence 同时消失”；任一仍存在但内容/inode 漂移继续零删除。补 regression 后 down + legacy 真实进程套件 `27 passed`，第二次 live-down 成功。
- Commits: C1=`766e34e8e`；C2=`856108cbc`,`c4750efcf`；C3=本提交。
- Next: R4 full validation and live signoff。

## R4 — Full validation and live signoff

- Status: DONE。
- Automated: `ruff check .` → pass；`ruff format --check .` → `787 files already formatted`；`bash -n scripts/e2e-up.sh scripts/e2e-down.sh` 与 `git diff --check` → pass；唯一 post-change full `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -m "not e2e" -q` → `3575 passed, 1 skipped, 23 deselected, 16 warnings in 187.91s`，日志 `/tmp/refactor-461-m5-final-full.log`。
- Real default lifecycle: 新增并执行真实 command start → restart → stop；连同 quoted path background stop 与跨 `Pacific/Honolulu` → `UTC` legacy `health_url` upgrade 共 `4 passed, 2 warnings in 9.42s`，PID/identity/state 零 residue。
- Real e2e lifecycle: 在含空格隔离目录同一 shell 内执行真实 `e2e-up.sh`，确认 Gateway `pid=64207` 与 IM PID 均 live 后执行真实 `e2e-down.sh`；正常停止，external/internal PID、identity/state、IM PID、config、sidecar、ports env 全部不存在。timeout/survivor/missing/dangling/malformed/same-PID-new-birth/same-content-new-inode/IM-survivor/busy-lock 由真实 shell entry harness 覆盖；up/down 收口套件 29 cases，相关最终 down + legacy 套件 `27 passed`。
- Residue: 本 milestone 创建的 live/debug 临时目录已删除；验证端口无 listener；未修改 canonical/acceptance/verification，未发送 P2P。
- Outcome: R1-R4 与全部退出标准完成，可进入 rebase、unit merge、push 与 worktree cleanup。
