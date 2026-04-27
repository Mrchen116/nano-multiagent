# M3-streaming-tool-executor: 流式工具执行器

## Goal
实现 `StreamingToolExecutor` 类，以及所有内置工具的动态并发安全判断。

## Roadpoints

### R3.1 Tool 协议扩展
- `Tool` 协议增加 `is_concurrency_safe(self, args) -> bool`
- `ToolSpec` 移除静态 `is_concurrency_safe` 字段（废弃）
- **文件**: `src/agent/core/tools/base.py`
- **验收**: `mypy` 通过

### R3.2 内置工具实现并发安全判断
| 工具 | 安全条件 |
|------|----------|
| `read` | 始终安全（只读） |
| `bash` | 动态：检查命令内容（`ls`/`cat`/`grep`/`find` 安全；`git commit`/`rm`/`mv` 不安全） |
| `write` | 不安全（文件系统写操作） |
| `edit` | 不安全（文件系统写操作） |
| `task` | 不安全（subagent 有副作用） |
- **文件**: `src/agent/platform/tools/builtins/*.py`
- **验收**: 每个工具有对应的单元测试

### R3.3 StreamingToolExecutor 实现
- FIFO 队列 + 动态并发判断
- `_process_queue()`: 同步设 `status="executing"` 后再 `create_task`
- `_execute_tool()` / `_collect_results()`: 分离 launcher 和 worker
- `get_completed_results()`: 非阻塞 yield
- `get_remaining_results()`: 阻塞等待所有未完成工具
- `discard()`: 取消所有排队/执行中任务
- Bash 错误级联：`sibling_event.set()` + `_should_cancel()`
- **文件**: `src/agent/core/agent/streaming_tool_executor.py`
- **验收**: `test_streaming_tool_executor_*.py` 全部通过

### R3.4 移除旧 ToolExecutor
- 删除 `partition_into_batches()`
- 删除 `ToolExecutor` 类
- 更新所有引用（如有）
- **文件**: `src/agent/core/agent/tool_executor.py`
- **验收**: 全仓库无引用旧类

## 验收标准
1. 两个 Read 调用可并行执行（总耗时 < 0.15s，单工具 0.1s）
2. `[safe, unsafe, safe]` 中第三个 safe 等 unsafe 完成
3. Bash 错误取消并行 sibling Bash，Read 错误不影响他人
4. `discard()` 后所有 queued/executing 工具被取消
5. 所有内置工具 `is_concurrency_safe()` 有单元测试覆盖
