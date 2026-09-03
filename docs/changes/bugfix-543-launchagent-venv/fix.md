# bugfix-543: preserve Gateway virtualenv interpreter in LaunchAgent

## Relations

- Related: feat-542

## 原始报告

> ok，merge吧，然后部署

部署 `feat-542` 后，Mac mini 的 Gateway 报：

> ERROR Gateway is running, but macOS login autostart failed: timed out waiting for gateway startup confirmation (lifecycle state never appeared)

CLI 按既定降级契约启动了普通后台 Gateway，但 LaunchAgent 没有成功运行。

## 现象 / 复现

在 macOS 上用项目 `.venv/bin/python` 执行默认 Gateway 启动时，LaunchAgent 的受管进程使用
Homebrew 基础 Python，日志出现 `ModuleNotFoundError: No module named 'httpx'`，因此未写入
Gateway 运行状态，命令在确认超时后降级。

## 根因

`feat-542` 的稳定 LaunchAgent 定义要求使用“当前绝对 Python”（归档设计的
LaunchAgent 定义）。实际代码对 `sys.executable` 调用了 `Path.resolve()`；macOS venv 的
`python` 是指向基础解释器的符号链接，解析后丢失 venv 路径和依赖上下文。

该行为由 `feat-542` 的实现提交 `427b5dcbf` 引入。原单测使用非符号链接的测试路径，只验证了
绝对路径，没有覆盖真实 macOS venv 链接。修复必须保住：稳定 plist 仍使用调用 Gateway 的
绝对解释器与源码 checkout，登录自启、崩溃恢复和降级契约均不变。

## 修复

生成 LaunchAgent plist 时，当前 Python 只转换为绝对路径，不再解析符号链接。
因此稳定和带一次性参数的临时 plist 都会在 `Program` 及
`ProgramArguments[0]` 中保留调用 Gateway 的 venv 解释器，launchd 能继承其已安装依赖。

源码根路径仍按 feat-542 的原有语义解析，`WorkingDirectory`、`PYTHONPATH`、
LaunchAgent 加载/停止/崩溃恢复及失败降级逻辑均未改变。真 macOS E2E 中的
plist 断言也改为要求保留未解引用的绝对 Python 路径。

## 验证

- 回归测试使用真实临时 `venv/bin/python -> homebrew/bin/python3` 符号链接；修复前
  `Program` 被解析为 base Python，测试如期失败。
- `tests/unit/personal_assistant/test_macos_launch_agent.py` 与
  `tests/unit/personal_assistant/test_gateway_autostart.py`：15 passed。
- macOS 隔离 LaunchAgent critical path：1 passed in 20.86s；使用 repo venv 的真实符号链接，
  覆盖 plist、启动、崩溃恢复、人工暂停、模拟登录恢复和关闭自启。
- 受影响 Python 文件通过 Ruff，E2E shell 通过 `bash -n`，最终 diff 通过
  `git diff --check`。

详细方法、结果与证据边界见
[`M1-fix/evidence/implementation.md`](M1-fix/evidence/implementation.md)。
