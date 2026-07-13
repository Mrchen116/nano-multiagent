# refactor-461-M2 — Progress

## Baseline

- Context: unit integration head `6882c85a` 上执行 post-acceptance fix round 1。
- Evidence: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -m "not e2e"` 通过（3497 selected，23 deselected）。

## R1 — 公共 Gateway 生命周期与操作输出

- Context: 验收发现操作文档仍描述已删除的 `STARTED health_url=...`，且公共生命周期 API 的默认 waiter 与强制 stop 分支缺少耐久回归。
- Decision: 通过公共 `launch_gateway_in_background` 覆盖 child early exit、PID timeout、PID success；通过公共 `stop_gateway` 覆盖 SIGTERM→SIGKILL 进程组回收、`forced=true`、PID/state 清理。README/runbook 改为真实三行输出并明确 PID 确认边界。
- Rationale: 测试锁定用户调用的公共 API，不把私有 waiter/kill helper 当成行为契约；文档不再把“子进程存活”误报成 channel readiness。
- Evidence:
  - Tests: `pytest -q tests/unit/personal_assistant/test_gateway_launch.py tests/unit/personal_assistant/test_gateway_pid_lifecycle.py tests/contract/test_no_dead_kernel_subprocess_seam.py` → 22 passed。
  - Entry: CLI 实际格式由 `_print_gateway_started` 产生 `Gateway started` / `IM service` / `Log`；文档逐行对齐。
  - Frontend State Matrix: N/A，非前端。
  - Browser QA: N/A，非前端。
  - E2E/Regression: public lifecycle regressions 落在既有 unit/contract 文件；真实栈统一在 milestone 收尾验证。
  - Visual/Interaction: N/A，非前端。
  - Prototype Comparison: N/A，design 无前端 prototype/reference。
- Rollback: 回退 R1 三个提交即可恢复原文档与测试，不影响运行时代码。
- Commits: `eeb7ac71` (C1), `130b2e11` (C2)

## R2 — legacy migration backup 事务边界

- Context: 原实现把 deterministic backup 当成普通文件写入；`O_EXCL` race loser 会无条件 unlink winner，已有 symlink/hardlink alias 可伪装成匹配备份，且缺少目录 fsync、权限收紧和 finite-number 校验。
- Decision: 备份创建改为独占 fd + `os.write` 完整写入 + file fsync + parent-directory fsync；记录新 inode，只在失败路径仍指向该 inode时删除。已有备份经 no-follow open、regular-file/源 inode/content 校验，权限只收紧不放宽，并重新 fsync file + directory。数值解析增加 `math.isfinite`。
- Rationale: config overwrite 只能发生在独立备份及其目录项均达到 durability gate 后；失败清理以 inode ownership 为界，不能误删并发 winner 或路径替换者。
- Evidence:
  - Tests: `pytest -q tests/unit/personal_assistant/test_local_store.py` → 58 passed；新增 open/write/file-fsync/directory-fsync、race、alias、mode、nan/inf 回归。
  - Entry: `save_local_config` / `load_local_config` 公共入口驱动全部断言。
  - Frontend State Matrix: N/A，非前端。
  - Browser QA: N/A，非前端。
  - E2E/Regression: `ruff check src/personal_assistant/config/local_store.py tests/unit/personal_assistant/test_local_store.py` → passed；完整套件在 milestone 收尾执行。
  - Visual/Interaction: N/A，非前端。
  - Prototype Comparison: N/A，design 无前端 prototype/reference。
- Debug note: 初次 non-finite 夹具先被 `agents must contain at least one entry` 截断；按 systematic-debugging 从栈回溯数据流，改为合法单 agent 配置后稳定复现 `.nan` / `.inf` 被误接收，未把夹具错误计为产品红测。
- Rollback: 回退 C2 恢复原 backup helper；回退 C1 删除对应行为门禁。
- Commits: `a8ecd5fb` (C1), `7d830467` (C2)

## R3 — M170 authenticated auto-bind 真实入口

- Status: pending

## R4 — e2e-down owned Gateway residue cleanup

- Status: pending
