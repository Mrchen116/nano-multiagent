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

<!-- 实施后回填。 -->

## 验证

<!-- 实施后回填。 -->
