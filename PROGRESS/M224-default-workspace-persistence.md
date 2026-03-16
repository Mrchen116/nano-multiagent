# M224 修复已有 Agent 默认 Workspace 未持久化导致 Bash cwd 回落仓库根

## Notes
- 已阅读 `LOGBOOK.md`：新增关键 session metadata 时，旧 binding 复用前必须向 kernel 取回 session metadata，缺字段要自动重建；真实入口若与源码矛盾，先确认是否仍跑在旧 worktree/旧进程上。
- 已阅读 `COMMENTING_GUIDE.md`：后续 public API/docstring 与注释只写契约、边界和原因，不复述实现。
- 基线：派工中的 `tests/personal_assistant/test_inbound_pipeline.py` 在当前仓库不存在；本 milestone 用现有对应测试 `tests/unit/personal_assistant/test_gateway_pipeline.py` 建立 red/green，并在最终结果里报告这条测试命令漂移。

## Roadpoint Records
