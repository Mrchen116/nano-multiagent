# TASKS (Current Milestone: M6)

## [DONE] R6.1 tools 基础层 + 内置工具 + 安全护栏 + /v1/tools
- Steps:
  - 先补 tools 子系统与 `/v1/tools` 的 unit/contract/integration/e2e 失败测试（Red）
  - 实现 `tools/base.py`、`tools/registry.py`、`tools/loader.py`、`tools/safety.py`
  - 实现 `tools/builtins/read.py`、`write.py`、`edit.py`、`bash.py`（不实现 `task`）
  - app 启动时扫描 `<repo_root>/.nano/tools` 并注册目录工具
  - 扩展 server：新增 `GET /v1/tools` 返回工具列表与 schema
  - 跑目标测试与 `pytest -q` 全量验收
- Expected Tests:
  - `tests/unit/test_tools_builtins.py`
  - `tests/integration/test_tools_registry_loader_integration.py`
  - `tests/contract/test_tools_contract.py`
  - `tests/e2e/test_tools_list_e2e.py`
  - `pytest -q`
- DoD:
  - `pytest -q` 全绿
  - C1/C2/C3 三次提交完整
  - 四文档写入 R6.1 hash 与证据
  - 回填任何 `PENDING-C3-*` 或历史占位（含 R5.2 C3）

## Milestone M6 状态
- R6.1 已完成并完成 C1/C2/C3 闭环。
- 按当前指令，先在此停留并回报 R6.1，不进入后续 Roadpoint。
