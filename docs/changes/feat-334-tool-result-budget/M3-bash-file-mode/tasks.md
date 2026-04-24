# M3: Bash 文件模式 + 30K 阈值 + 真实用户旅程

## 目标

将 Bash 工具改为文件模式（stdout 实时落盘），BashTool 从文件读取内容后交给 compressor 统一按 30K 压缩。完成真实 CLI 端到端测试。

## 任务列表

1. **safety.py 文件模式**
   - `run_command_stream` 改为实时写入临时文件
   - 1MB 硬上限（超过后停止写入，继续排空 stdout）
   - `CommandExecution` 新增 `output_file_path` 和 `file_size`
   - `_truncate_tail_output` 不再被 `run_command_stream` 调用

2. **bash.py 更新**
   - 声明 `max_result_size_chars = 30_000`
   - `run()` 读取文件内容，清理临时文件
   - `serialize_result` 简化（只做文本清洗）

3. **单元测试**
   - Safety 文件模式：大输出不爆内存、文件 ≤1MB
   - Bash 30K 触发 compressor
   - Bash 小输出不触发
   - 临时文件清理

4. **集成测试**
   - AgentLoop + Bash 文件模式 + compressor 端到端

5. **CLI 真实用户旅程**
   - 运行 `python -c "print('x'*60000)"`
   - 验证 `.nano/tool-results/` 落盘、`<persisted-output>` 格式
   - 运行 `ls`、`read README.md` 验证无回归

## 验收标准

- Bash 输出 60K → compressor 触发，落盘到 `.nano/tool-results/`，LLM 收到 `<persisted-output>`
- Bash 输出 10K → 不触发压缩，正常返回
- 进程内存不随输出大小增长（10MB 输出时 RSS 稳定）
- 临时文件 `.agent/tmp/bash-stdout-*.log` 不残留
- Read 工具大文件不受限（max_result_size_chars=None）
