# M108 — REPL 粘贴与退出语义修复

## Plan Notes
- 遵守 `LOGBOOK.md` 中与 CLI 边界、REPL run_id/event_id、命令屏障二次复检相关规则。
- 遵守 `COMMENTING_GUIDE.md`：public API/docstring 写契约，注释只写意图/约束。
- 当前测试门禁命令：`PYTHONPATH=src python3 -m pytest tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py -q`
- 基线说明：派发包中的默认 `tests/coding_cli` 路径在本仓不存在，已记录为 baseline 偏差；后续统一使用 focused test 命令。

### R1 输入聚合：多行粘贴应作为一次用户输入提交
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `PYTHONPATH=src python3 -m pytest tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py -q`
  - Entry: 待补充
- Rollback:
- Commits: C1=, C2=, C3=
- Next: 写红测验证一次粘贴多行只提交一条消息

### R2 退出语义：/exit 立即止收止派并清队
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `PYTHONPATH=src python3 -m pytest tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py -q`
  - Entry: 待补充
- Rollback:
- Commits: C1=, C2=, C3=
- Next: 在 R1 后补红测验证 `/exit` 清队与 managed stop
