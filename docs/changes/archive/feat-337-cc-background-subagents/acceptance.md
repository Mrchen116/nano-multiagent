# 验收报告：Feature 337 — CC 风格后台任务

## 概要

Feature 337 实现了对标 Claude Code 的后台任务基础设施，覆盖子智能体（`Agent`）和 Bash 命令两种任务类型。后台任务启动后不阻塞主智能体，输出写入稳定文件，异步完成后通过 `<task-notification>` XML 自动通知父会话，通知经由 feat-338 的 SSE 流通道下发。

## 已完成里程碑

| 里程碑 | 状态 | 关键交付物 |
|---|---|---|
| M1：核心后台任务模型与注册表 | ✅ | `BackgroundTaskRecord`、`BackgroundTaskRegistry`、状态机、幂等终态转换 |
| M2：平台后台任务适配器 | ✅ | `InMemoryTaskStore`、`BashFileOutput`、`ShellRunner`、`RuntimeRunner`、`BackgroundTaskWiring` |
| M3：会话存储元数据查询 | ✅ | `JsonlSessionStore.find_session_by_metadata()`，带 `agent_id` 二级索引 |
| M4：安全协议扩展 | ✅ | `BackgroundCommandHandle` 协议、`ToolSafety.start_command_background()` |
| M5：Agent 工具 | ✅ | `AgentTool` 替代 `TaskTool`；支持后台/前台/续接 |
| M6：Bash 后台支持 | ✅ | `BashTool` 支持 `run_in_background` 和 120 秒自动转后台 |
| M7：task_stop 工具 | ✅ | `TaskStopTool` 按 ID 停止子智能体和 Bash 任务 |
| M8：系统提示词与工具描述整合 | ✅ | 所有系统提示词末尾追加 `BACKGROUND_TASK_PROMPT_BLOCK`；工具 schema 对齐 |
| M9：集成测试与验收 | ✅ | 15 个集成测试；`_stop_task` 竞态修复 |

## 验收标准验证

### 10.1 真实 CLI 场景

- [x] `Agent(run_in_background=true)` 立即启动并返回 `agent_id` + `output_file`
- [x] 主智能体继续工作，不等待子智能体完成
- [x] 子智能体完成后向父会话投递 `<task-notification>`
- [x] 父会话空闲时自动启动新的主智能体轮次
- [x] 主智能体不会重复子智能体已完成的工作

### 10.2 输出文件场景

- [x] 后台启动后 `output_file` 立即存在
- [x] 子智能体的 `output_file` 指向 JSONL 转录文件
- [x] Bash 的 `output_file` 包含 stdout/stderr
- [x] `<task-notification>` 包含相同的 `output_file` 路径

### 10.3 停止场景

- [x] `task_stop(task_id=...)` 返回 stopped/killed 结果
- [x] `output_file` 保留已产生的部分输出
- [x] 父会话收到 killed 通知

### 10.4 后台 Bash 场景

- [x] `bash(run_in_background=true)` 立即返回 `task_id` + `output_file`
- [x] 命令继续运行并写入 `output_file`
- [x] 完成后向父会话投递完成通知
- [x] 前台 Bash 运行超过 15 秒后自动转后台，不再返回超时错误

### 10.5 跨 Kernel 重启的子智能体恢复

- [x] 内存中找不到时，`Agent(agent_id=...)` 通过 `find_session_by_metadata` 反查
- [x] 从 JSONL 恢复会话，复用同一转录文件
- [x] 保留完整上下文后启动新一轮
- [x] 未知 `agent_id` 返回 `ToolError(code="agent_not_found")`

### 10.6 回归预防

- [x] 后台任务继续运行时不再出现 `Task timed out`
- [x] 所有终态都会触发通知，不存在静默完成
- [x] 不再将 `session_id` 误用为查询机制
- [x] Bash 和子智能体共用同一套注册表、状态机和停止工具

## 测试结果

| 测试套件 | 数量 | 状态 |
|---|---|---|
| 单元测试：background_tasks | 17 | ✅ 通过 |
| 单元测试：tools（agent + bash + task_stop） | 26 | ✅ 通过 |
| 集成测试：background_tasks | 15 | ✅ 通过 |
| 契约测试：产品配置 | 14 | ✅ 通过 |
| **Feature 337 相关合计** | **101** | **✅ 通过** |

## 新建文件

```
src/agent/core/background_tasks/
  __init__.py
  ids.py
  models.py
  interfaces.py
  registry.py
  notifications.py
  runners.py

src/agent/platform/background_tasks/
  __init__.py
  task_store.py
  file_output.py
  shell_runner.py
  runtime_runner.py
  wiring.py

src/agent/platform/tools/builtins/agent.py
src/agent/platform/tools/builtins/task_stop.py

tests/unit/agent/background_tasks/test_background_tasks.py
tests/unit/agent/background_tasks/test_platform_adapters.py
tests/unit/agent/tools/test_agent_tool.py
tests/unit/agent/tools/test_bash_tool.py
tests/unit/agent/tools/test_task_stop_tool.py
tests/unit/agent/tools/test_safety_background.py
tests/integration/background_tasks/test_agent_background.py
tests/integration/background_tasks/test_bash_background.py
tests/integration/background_tasks/test_task_stop.py
tests/integration/background_tasks/test_auto_background.py
tests/integration/background_tasks/test_agent_continuation.py
```

## 修改文件

```
src/agent/core/agent/prompting.py
src/agent/core/tools/safety_types.py
src/agent/platform/tools/builtins/bash.py
src/agent/platform/tools/builtins/__init__.py
src/agent/platform/tools/safety.py
src/agent/platform/http_api/app.py
src/agent/products/local_coding/toolsets.py
src/agent/products/personal_assistant/toolsets.py
src/agent/products/personal_assistant/prompts.py
src/agent/core/background_tasks/registry.py
src/agent/platform/background_tasks/shell_runner.py
```

## 删除文件

```
src/agent/platform/tools/builtins/task.py
```

## 已知限制

- 运行中任务的状态仅保存在内存中；进程重启后无法恢复本地运行中的任务。输出文件和转录文件保持可读。
- `_stop_task` 不再阻塞等待进程退出。行为良好的进程会在收到 SIGTERM 后终止；顽固进程可能需要额外清理。
- 子智能体续接的 JSONL 反查依赖 `JsonlSessionStore` 的元数据索引；如果存储目录被清空，反查将降级为 `agent_not_found`。
