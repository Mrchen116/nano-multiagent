# M51 - 工具时间线聚合与异常隔离（call_id/orphan）

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `106 passed, 42 warnings`（2026-03-04）

### Plan（一次性拆分）
- Context:
  - M49 完成了 normalize/dedupe/view-model 分层，M50 完成 preview/final 阶段机；但工具摘要仍偏“字段覆盖模型”，orphan 终态隔离不显式，存在跨调用串味风险。
  - 边界：只改 CLI 与指定测试文件，不改内核/API/agent/server/session/llm/tools。
- Decision:
  - 拆分 `R1 call_id聚合+orphan隔离`、`R2 高频可读性+异常指标`、`R3 收口验收+main集成+dev_tasks`。
  - 以 `event_pipeline` 为主改造点，保持 `repl_events` 与 `repl_render` 契约稳定。
- Rationale:
  - 先锁语义（R1），再锁可读性（R2），最后统一门禁与实跑（R3），能最小化异步链路回归面。
- Evidence:
  - Tests: 基线门禁全绿（`106 passed, 42 warnings`）。
  - Entry: 计划文档已创建于 `TASKS/M51-工具时间线聚合与异常隔离（call_id-orphan）.md`。
- Rollback:
  - 回退到计划提交前稳定点。
- Commits: Plan=`TBD`; C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 执行 R1 红测并提交 C1。

### R1 call_id 时间线聚合与 orphan 隔离（核心语义）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:

### R2 高频事件可读性与异常指标收口
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:

### R3 收口验收与集成
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`N/A`, C2=`N/A`, C3=`TBD`
- Next:
