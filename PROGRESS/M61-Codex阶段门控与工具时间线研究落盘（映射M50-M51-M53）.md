# M61 - Codex阶段门控与工具时间线研究落盘（映射M50-M51-M53）

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `113 passed, 42 warnings`（2026-03-04）

### Plan（一次性拆分）
- Context:
  - M61 为研究型里程碑，硬约束是不改实现代码；交付物是可执行研究结论与迁移清单。
  - 目标聚焦 codex 的阶段门控、工具时间线/orphan、summary 去重，并映射到 M50/M51/M53。
- Decision:
  - 拆分为三轮研究：`R1 阶段门控`、`R2 工具时间线与去重`、`R3 迁移清单与验收模板收口`。
  - 每轮补充“新问题 -> 新锚点 -> 迁移决策 -> 风险”闭环，及时写入 PROGRESS。
- Rationale:
  - 多轮递进能确保研究不是静态摘录，而是可被后续里程碑直接执行的工程清单。
- Evidence:
  - Tests: baseline gate 全绿。
  - Entry: 必读文件已完成（`LOGBOOK.md`、`内核设计蓝图.md`、`PROGRESS/M44-Codex-CLI-研究补充-输入历史-事件折叠-去重策略.md`、`tdd-execution-worker`）。
- Rollback:
  - 回退到计划提交前稳定点。
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 执行 R1：补全 STREAMING/FINALIZING/FINALIZED 与 frame coalesce 关键锚点。

### R1 阶段门控与渲染调度锚点深挖（STREAMING/FINALIZING/FINALIZED）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:

### R2 工具时间线聚合/orphan隔离与summary去重研究
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:

### R3 迁移总清单与managed CLI观感验收模板收口
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
