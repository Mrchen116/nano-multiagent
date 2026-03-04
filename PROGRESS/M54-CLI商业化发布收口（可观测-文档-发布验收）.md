# M54 - CLI商业化发布收口（可观测/文档/发布验收）

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `119 passed, 46 warnings`（2026-03-04）

### Plan（一次性拆分）
- Context:
  - M53 已补齐高频性能快照，但商业化发布仍缺“可观测解释层 + 发布验收脚本 + 文档化操作手册”闭环。
  - 约束：仅改 CLI 与指定测试/文档；禁止改内核/API/工具/agent/server/session/llm。
- Decision:
  - 拆分 `R1 可观测诊断助手`、`R2 发布验收脚本化`、`R3 文档与发布收口`。
  - 避免改 `app/commands.py`，优先新增独立 CLI 模块与文档入口。
- Rationale:
  - 通过“可观测解释 + 可执行 playbook + 文档化验收”三件套形成发布前可操作闭环。
- Evidence:
  - Tests: 基线门禁全绿（`119 passed, 46 warnings`）。
  - Entry: 计划已写入 `TASKS/M54-CLI商业化发布收口（可观测-文档-发布验收）.md`。
- Rollback:
  - 回退到计划提交前稳定点。
- Commits: Plan=`TBD`, C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 执行 R1 红测并提交 C1。

### R1 可观测收口：指标契约 + 故障归因助手
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:

### R2 发布验收与回滚流程：可执行脚本化
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:

### R3 文档收口 + 发布验收 + 集成
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`N/A`, C2=`N/A`, C3=`TBD`
- Next:
