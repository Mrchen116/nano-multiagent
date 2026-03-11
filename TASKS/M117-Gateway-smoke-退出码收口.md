# M117 Gateway smoke 退出码收口

## 前置确认
- 已先阅读 `LOGBOOK.md`、`COMMENTING_GUIDE.md`、`/Users/czj/.claude/skills/tdd-execution-worker/SKILL.md`。
- 本 Milestone 的代码与文档将遵守 `COMMENTING_GUIDE.md` 的 public API docstring / 注释规范。
- 参考 LOGBOOK 与派发约束：只修当前唯一阻塞 M104 完成的 smoke runtime 正常关闭退出码问题，不改 `ROADMAP.md`，不手改 `data/dev-tasks.json`，不扩散到 smoke runtime / gateway 正常关闭语义之外。

## 当前处境
- Milestone: M117 / Gateway smoke 退出码收口
- execution_mode: parallel
- use_worktree: true
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M117`
- branch: `milestone/M117`
- 测试门禁命令: `cd /Users/czj/Repos/nano-multiagent && python -m pytest tests/e2e/test_personal_assistant_main_e2e.py tests/unit/personal_assistant/test_main.py -q 2>&1 | tail -120`
- 基线结果: `tests/e2e/test_personal_assistant_main_e2e.py` 中两个 smoke 用例因 `SHUTDOWN exit_code=-15` 失败，其余相关单测通过。
- 当前已发现差距:
  - `personal_assistant.smoke_runtime` 通过 `process.terminate()` 触发关闭时，gateway 入口最终进程退出码为 `-15`。
  - 现有单测覆盖了 `GatewayRuntime.request_shutdown()` 的进程内关闭路径，但没有覆盖真实 CLI 入口上的 SIGTERM 语义。

## Roadpoints

### R1 关闭信号语义收口
- Status: TODO
- Acceptance:
  - 为 gateway 入口补足“收到 SIGTERM 后走 graceful shutdown 并返回 exit code 0”的回归测试。
  - 修复真实入口关闭路径，使 smoke runtime 输出 `SHUTDOWN exit_code=0`。
  - 保持现有 READY/RUNNING/SHUTDOWN 观测语义不变，不通过放宽测试掩盖异常退出。
- Tests Plan:
  - unit: 补充 `personal_assistant.main` 入口上的 SIGTERM 处理语义测试，快速定位退出码漂移的根因。
  - e2e: 复用现有 `tests/e2e/test_personal_assistant_main_e2e.py` smoke 脚本验证 READY/RUNNING/SHUTDOWN 与退出码收口。
  - contract/integration: 本次不新增；问题集中在入口信号关闭语义，现有 gateway runtime 单测已覆盖进程内关闭顺序。
- Expected Tests:
  - `tests/unit/personal_assistant/test_main.py::<新增 SIGTERM 入口回归测试>`
  - `tests/e2e/test_personal_assistant_main_e2e.py::test_smoke_runtime_script_reports_ready_running_and_shutdown`
  - `tests/e2e/test_personal_assistant_main_e2e.py::test_smoke_runtime_script_keeps_gateway_alive_after_ready`
  - `cd /Users/czj/Repos/nano-multiagent && python -m pytest tests/e2e/test_personal_assistant_main_e2e.py tests/unit/personal_assistant/test_main.py -q 2>&1 | tail -120`
- DoD:
  - `test_command` 全绿。
  - C1/C2/C3 齐全。
  - `PROGRESS/M117-Gateway-smoke-退出码收口.md` 写清决策、证据、回滚点与提交哈希。
