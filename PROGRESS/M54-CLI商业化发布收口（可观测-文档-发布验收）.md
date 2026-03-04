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
- Commits: Plan=`c8e93db`, C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 执行 R1 红测并提交 C1。

### R1 可观测收口：指标契约 + 故障归因助手
- Context:
  - M53 已产出 `perf_metrics`，但缺少从 machine metrics 到运维建议的稳定解释层，发布排障信息分散。
  - 需要纯 CLI 层实现，不依赖 server/core 改造。
- Decision:
  - 新增 `src/nano_multiagent/cli/release_observability.py`，提供 `summarize_perf_metrics` 与 `build_guardrail_hints`。
  - 通过 `guardrail_reason` + `stable` 判定构建可执行排障建议。
- Rationale:
  - 在不改现有 REPL 输出协议的前提下，先固化“可观测解释契约”，供文档与发布脚本复用。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_refactor_boundaries.py -k "release_observability"` -> `2 failed`（模块缺失）。
    - 绿测：同命令 -> `2 passed`。
    - 全量门禁：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `121 passed, 46 warnings`。
  - Entry:
    - 可观测摘要与归因建议现可通过独立模块统一生成，避免散落在 REPL 逻辑中。
- Rollback:
  - 回退到 `8835e99`（R1 红测提交）。
- Commits: C1=`8835e99`, C2=`4638ce1`, C3=`TBD`
- Next:
  - 执行 R2：新增可执行发布验收/回滚 playbook 脚本与测试。

### R2 发布验收与回滚流程：可执行脚本化
- Context:
- 里程碑已具备可观测摘要，但缺少“一键发布验收 + 回滚模板”执行入口，交付仍依赖手工命令。
- 约束：不改 server/core，只在 CLI 层落地可执行 playbook。
- Decision:
- 新增 `src/nano_multiagent/cli/release_playbook.py`，提供 `build_release_playbook_report` 与 CLI 入口。
- 支持 `--execute` 开关：dry-run 只输出步骤；execute 顺序执行门禁与 managed smoke，并返回结构化执行结果。
- managed smoke 命令使用当前解释器（`sys.executable`），避免 `python3` 指向系统环境导致依赖缺失。
- Rationale:
- 将发布检查流程统一结构化后，可被文档、自动化任务与人工值班同时复用，降低发布歧义。
- Evidence:
  - Tests:
    - 红测（C1）：`PYTHONPATH=src pytest -q tests/unit/test_cli_refactor_boundaries.py -k "release_playbook"`（提交 `f54e86a`，缺失模块导致失败）。
    - 绿测子集：`PYTHONPATH=src pytest -q tests/unit/test_cli_refactor_boundaries.py -k "release_playbook"` -> `2 passed, 9 deselected`。
    - 全量门禁：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `123 passed, 46 warnings`。
  - Entry:
    - `PYTHONPATH=src /Users/czj/miniforge3/bin/python3 -m nano_multiagent.cli.release_playbook --base-url http://127.0.0.1:8127 --token test-token --execute` -> `status=passed`（包含 `cli_gate_tests` + `managed_smoke_ping` 执行记录）。
- Rollback:
- 回退到 `f54e86a`（R2 红测稳定点）。
- Commits: C1=`f54e86a`, C2=`89c3598`/`0e9182c`/`947e092`, C3=`TBD`
- Next:
- 执行 R3：README 与运维入口文档收口、补 managed 实跑证据并集成 main。

### R3 文档收口 + 发布验收 + 集成
- Context:
- R1/R2 能力已落地，但 README 尚未覆盖“可观测解释器 + 发布 playbook”入口，发布值班不可直接按文档执行。
- Decision:
- 在 `README.md` 新增 `Release observability helpers` 与 `Release acceptance & rollback playbook` 两节，补齐命令入口与 JSON 产物字段说明。
- 使用 playbook execute 与 managed 命令做实跑留证，作为发布验收前后对比样本。
- Rationale:
- 让“能力实现”转化为“可执行操作手册”，并保证值班场景不需要阅读源码也可完成验收/回滚准备。
- Evidence:
  - Tests:
    - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `123 passed, 46 warnings`。
  - Entry:
    - `PYTHONPATH=src /Users/czj/miniforge3/bin/python3 -m nano_multiagent.cli.release_playbook --base-url http://127.0.0.1:8127 --token test-token --execute` -> `status=passed`。
    - `PYTHONPATH=src /Users/czj/miniforge3/bin/python3 -m nano_multiagent.cli.main --mode managed --base-url http://127.0.0.1:8131 --token test-token health` -> `{"healthy": true, ...}`。
    - `PYTHONPATH=src /Users/czj/miniforge3/bin/python3 -m nano_multiagent.cli.main --mode managed --base-url http://127.0.0.1:8131 --token test-token create-session --title m54-managed-smoke-8131` -> `{"session_id": "...", "status": "active", ...}`。
- Rollback:
- 回退到 `947e092`（R2 实现全绿且可执行 playbook）。
- Commits: C1=`N/A`, C2=`N/A`, C3=`TBD`
- Next:
- 提交 R2/R3 文档收口后执行 rebase/merge/push 与 dev_tasks DONE。
