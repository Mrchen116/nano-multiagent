# M1-fix — Progress

## Done

- 已从 clean `unit/bugfix-543` `b42c14464` 创建隔离 milestone worktree 与 `milestone/bugfix-543-M1` 分支。
- 已用真实临时符号链接复现 Python 路径被解析的回归，修复后 plist 的 `Program` 和 `ProgramArguments[0]` 都保留 venv 路径。
- 已校正真 macOS E2E 断言，并用 repo venv 的真实 Python 符号链接跑通隔离 LaunchAgent 旅程。
- 已闭环 code review 指出的 transient coverage gap：E2E 在首次启动后直接检查 loaded job，再独立检查 retained stable plist。

## Notes

- plist 中的 Python 路径要保留 venv 符号链接身份；源码根目录继续按 feat-542 的稳定 checkout 语义解析。
- 修复仅将 Python 路径的 `resolve()` 改为不解引用符号链接的 `absolute()`；LaunchAgent 加载、恢复、停止与降级逻辑未改。

## Validation

- RED：新回归测试在修复前失败，`Program` 实际值是符号链接的 base Python，而非 `venv/bin/python`。
- `pytest -q tests/unit/personal_assistant/test_macos_launch_agent.py tests/unit/personal_assistant/test_gateway_autostart.py`：15 passed。
- 在 clean 实现提交 `914b1da95` 上执行
  `NANO_MULTIAGENT_RUN_LAUNCH_AGENT_E2E=1 pytest -q tests/e2e/critical_paths/test_gateway_autostart_critical_path.py`：
  1 passed in 19.37s。
- `ruff check` 及 `ruff format --check` 覆盖受影响 Python 文件；`bash -n scripts/e2e-gateway-autostart.sh` 和 `git diff --check` 通过。
- 二次 E2E 结束后已核对本轮 config-scoped job/plist 未残留，也无指向 pytest 临时 config 的 Gateway/IM 进程。
- Review closure：扩展后的 macOS E2E `1 passed in 20.77s`；loaded transient job 保留
  repo venv Python 路径且含本轮 `--auto-bind` / `--im-service-url`，stable plist 仍不含这些参数。
- Closure 上的两个受影响单测文件：15 passed in 0.63s；`bash -n` 与 `git diff --check` 通过。
- Closure E2E 结束后已确认 config-scoped job/plist 及指向 pytest 临时 config 的 Gateway/IM 进程无残留。
- 详细证据见 [`evidence/implementation.md`](evidence/implementation.md)。
