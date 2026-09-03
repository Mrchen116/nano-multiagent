# M1-fix implementation evidence

## 虚拟环境解释器路径

- **Claim**：LaunchAgent 稳定和临时 plist 的 `Program` / `ProgramArguments[0]`
  保留调用 Gateway 的绝对 venv Python 路径，不解析到 base Python；源码根路径仍解析为稳定 checkout。
- **Baseline**：`milestone/bugfix-543-M1` 实现提交 `914b1da95`，基于 unit head
  `b42c14464`。
- **Method**：新增
  `tests/unit/personal_assistant/test_macos_launch_agent.py::test_plist_preserves_virtualenv_python_symlink`，
  用 `tmp_path` 创建真实 `venv/bin/python -> homebrew/bin/python3` 符号链接，并另用源码根符号链接核对两者语义。
- **Result**：修复前单测 RED，`Program` 得到 base Python；将 Python 路径改为
  `absolute()` 后，受影响的两个单测文件共 15 个测试全部通过。
- **Locator**：`src/personal_assistant/gateway/macos_launch_agent.py`；
  `tests/unit/personal_assistant/test_macos_launch_agent.py`。
- **Limit**：单测证明 plist 生成与源码根路径语义，不单独证明 launchd 真正执行该解释器；真实入口由下一条证据覆盖。

## macOS LaunchAgent 真实入口

- **Claim**：实际 macOS `launchctl` 可以从 repo venv 的 Python 符号链接启动 Gateway，
  并继续满足 feat-542 的崩溃恢复、人工停止、模拟下次登录和关闭自启旅程。
- **Baseline**：`milestone/bugfix-543-M1` 实现提交 `914b1da95`，macOS；
  `/Users/czj/Repos/nano-multiagent/.venv/bin/python` 是绝对符号链接。
- **Method**：
  `NANO_MULTIAGENT_RUN_LAUNCH_AGENT_E2E=1 /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/e2e/critical_paths/test_gateway_autostart_critical_path.py`。
  该测试创建 pytest 临时 config、独立 IM/runtime 与 config-scoped LaunchAgent label，
  并在 `finally` 中停止 Gateway/IM、移除本轮 plist。
- **Result**：`1 passed in 19.37s`；E2E 内同时核对 `Program` 和
  `ProgramArguments[0]` 等于未解引用的绝对 Python 路径。
- **Locator**：`tests/e2e/critical_paths/test_gateway_autostart_critical_path.py`；
  `scripts/e2e-gateway-autostart.sh`。
- **Limit**：本轮以 retained plist 的 `launchctl bootstrap` 模拟下次登录，未注销当前 macOS 用户；
  未读写生产 Gateway config，也未执行部署。

## Review closure：transient payload

- **Claim**：首次带 `--auto-bind` 和 `--im-service-url` 启动时，launchd 实际加载的
  transient job 在 program 和首个 argument 中保留未解引用的绝对 venv Python 路径；
  retained stable plist 仍不持久化一次性控制。
- **Baseline**：`milestone/bugfix-543-M1-closure`，基于已推送的 unit head `47e5fb971`；
  macOS 与 repo venv 真实 Python 符号链接。
- **Method**：E2E 首次启动完成后，在读取 stable plist 前执行
  `/bin/launchctl print gui/<uid>/<label>`，从 loaded job 输出中提取 `program` 和 `arguments`；
  同时核对 transient controls 在 loaded job 中，之后复用原 stable plist 断言确认它们不在持久定义中。
- **Result**：扩展后的 macOS 隔离 E2E `1 passed in 20.77s`；loaded job 的 program 和
  `arguments[0]` 等于 `NANO_MULTIAGENT_E2E_PYTHON` 的未解引用绝对路径，一次性参数未出现在 stable plist。
- **Locator**：`scripts/e2e-gateway-autostart.sh` 中首次 `wait_for_new_gateway` 之后的
  loaded-job 检查；`tests/e2e/critical_paths/test_gateway_autostart_critical_path.py`。
- **Limit**：transient plist 文件按产品契约在 bootstrap 返回后立即删除；本证据检查的是 launchd 从该文件实际加载的 job 定义。

## 清理

- E2E 结束后已用本轮临时 config 重新派生 label，确认 job 未 loaded 且对应 plist 不存在。
- 未发现命令行指向 pytest 临时 config 的残留 Gateway 或 IM 进程。
