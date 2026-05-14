# feat-349-M1 Progress

## Overview

实现 hook 内核 background fork 基础设施。核心改动：
- `core/hooks/types.py`：`HookEventMode.BACKGROUND` + `HookRegistration.mode`
- `core/hooks/registry.py`：`on()` 支持 `mode` 参数
- `core/hooks/runner.py`：`dispatch_background()` fire-and-forget
- `core/hooks/context.py`：`fork_conversation` callable 注入
- `core/agent/context_fork.py`：`ForkConversationCallable` + `make_fork_conversation`
- `core/agent/loop.py`：turn_meta 暴露 `tool_iterations`
- `core/agent/runtime.py`：`_run_locked` 读 tool_iterations、dispatch background hook context

<!-- Roadpoints below -->
