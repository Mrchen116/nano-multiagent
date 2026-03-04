# M62 Codex CLI研究三期（TTY/non-TTY契约与交互可观测）

日期：2026-03-04
分支：`milestone/M62`
工作区：`/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M62`

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `113 passed, 42 warnings`

### Plan（一次性拆分）
- Context:
  - M62 属于研究型里程碑，目标是形成可执行契约与测试矩阵，不涉及实现代码。
  - 必须与蓝图边界一致：仅 CLI 研究与文档沉淀，不触碰内核/API 代码。
- Decision:
  - 拆分三轮研究：R1 输出边界、R2 折叠/错误/观测、R3 契约模板与测试矩阵。
  - 每轮都要求“新问题 -> 代码锚点 -> 迁移规则”。
- Rationale:
  - 按问题驱动分轮可以避免大而泛综述，保证后续里程碑可直接消费。
- Evidence:
  - Tests: baseline `113 passed, 42 warnings`。
  - Entry: 关键前置文档（LOGBOOK/蓝图/M44补充）已完成阅读。
- Rollback:
  - 回退到计划提交前稳定点。
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 执行 R1 第一轮探索：定位 codex 的 TTY/non-TTY 判定与输出路径分叉点。

### R1 TTY/non-TTY 输出边界研究（规则 + 反例 + 代码锚点）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:

### R2 状态行/事件折叠 + 错误分层 + 可观测指标研究
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:

### R3 商业化前契约模板 + M52/M53/M54 测试矩阵草案
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
