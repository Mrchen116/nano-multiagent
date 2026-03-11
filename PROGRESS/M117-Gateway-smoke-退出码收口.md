# M117 Gateway smoke 退出码收口

## 前置确认
- 已先阅读 `LOGBOOK.md`、`COMMENTING_GUIDE.md`、`/Users/czj/.claude/skills/tdd-execution-worker/SKILL.md`。
- 本 Milestone 的代码与文档将遵守 `COMMENTING_GUIDE.md` 的 public API docstring / 注释规范。
- 约束：仅处理 smoke runtime / gateway 正常关闭语义；不改 `ROADMAP.md`；不手改 `data/dev-tasks.json`；不在 M104 worktree 直接提交。

## 当前处境
- Milestone: M117 / Gateway smoke 退出码收口
- execution_mode: parallel
- use_worktree: true
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M117`
- branch: `milestone/M117`
- 测试门禁命令: `cd /Users/czj/Repos/nano-multiagent && python -m pytest tests/e2e/test_personal_assistant_main_e2e.py tests/unit/personal_assistant/test_main.py -q 2>&1 | tail -120`
- 基线结果: `2 failed, 9 passed`；失败点为 smoke 收尾 `SHUTDOWN exit_code=-15`。

## Roadpoint 记录

### R1 关闭信号语义收口
- Context: smoke 测试把 `kernel.command` 改成随机 `uvicorn --port`，但未同步 `kernel.base_url`；gateway 仍按默认 `http://127.0.0.1:8000` 轮询健康检查，可能误把别的本地服务当作 READY，随后过早向真实 gateway 发送 SIGTERM，导致收尾看到 `exit_code=-15`。
- Decision: 在 `load_local_config()` 的 kernel 解析里，当 `base_url` 未显式配置时，从本地 `kernel.command` 的 `--host/--port` 推导实际健康检查地址；仅对 `127.0.0.1` / `localhost` / `0.0.0.0` 这类本地监听生效，推导失败时继续保留默认 `:8000`。
- Rationale: 问题不在“正常关闭应该容忍 -15”，而在 smoke 与 gateway 就绪探测地址错位。把配置装载层收口为单一真源后，READY、RUNNING、SHUTDOWN 会自动对齐真实子进程语义，且不会放宽验收口径。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M117 && python -m pytest tests/e2e/test_personal_assistant_main_e2e.py tests/unit/personal_assistant/test_main.py -q 2>&1 | tail -120` → `11 passed in 4.88s`
  - Entry: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M117/src python -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M117/tests/e2e/test_personal_assistant_main_e2e.py -q -k "smoke_runtime_script_reports_ready_running_and_shutdown or smoke_runtime_script_keeps_gateway_alive_after_ready"` → `2 passed in 4.64s`，输出回到 `SHUTDOWN exit_code=0`。
  - Boundary: 显式配置 `kernel.base_url` 的场景保持原样；无法从命令中安全识别 host/port 时仍回退默认 `http://127.0.0.1:8000`。
- Rollback: 如需回退，可退回 C1 `b0d3a3d` 仅保留回归测试，或退回计划提交 `1b5b282` 重新拆分方案。
- Commits: C1=`b0d3a3d`, C2=`c3ecf33`, C3=<pending>
- Next: 提交文档并回传主 agent。
