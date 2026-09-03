# M1-fix implementation evidence

## 虚拟环境解释器路径

- **Claim**：LaunchAgent 稳定和临时 plist 的 `Program` / `ProgramArguments[0]`
  保留调用 Gateway 的绝对 venv Python 路径，不解析到 base Python；源码根路径仍解析为稳定 checkout。
- **Baseline**：`milestone/bugfix-543-M1`，基于 unit head `b42c14464`的实施树。
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
- **Baseline**：`milestone/bugfix-543-M1` 实施树，macOS；
  `/Users/czj/Repos/nano-multiagent/.venv/bin/python` 是绝对符号链接。
- **Method**：
  `NANO_MULTIAGENT_RUN_LAUNCH_AGENT_E2E=1 /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/e2e/critical_paths/test_gateway_autostart_critical_path.py`。
  该测试创建 pytest 临时 config、独立 IM/runtime 与 config-scoped LaunchAgent label，
  并在 `finally` 中停止 Gateway/IM、移除本轮 plist。
- **Result**：`1 passed in 20.86s`；E2E 内同时核对 `Program` 和
  `ProgramArguments[0]` 等于未解引用的绝对 Python 路径。
- **Locator**：`tests/e2e/critical_paths/test_gateway_autostart_critical_path.py`；
  `scripts/e2e-gateway-autostart.sh`。
- **Limit**：本轮以 retained plist 的 `launchctl bootstrap` 模拟下次登录，未注销当前 macOS 用户；
  未读写生产 Gateway config，也未执行部署。

## 清理

- E2E 结束后未发现指向本 milestone 或 pytest 临时 config 的 Gateway plist。
- 未发现指向本 milestone 或 pytest 临时 config 的残留进程。
