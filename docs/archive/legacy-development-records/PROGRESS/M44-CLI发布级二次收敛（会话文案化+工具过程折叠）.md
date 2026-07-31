# M44 - CLI发布级二次收敛（会话文案化+工具过程折叠）

## Baseline
- Test command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `101 passed, 40 warnings`
  - Verified at `2026-03-04`

## Handover
- Context: 上一位 worker 中断；当前 `milestone/M44` 未产生 M44 功能提交，仅存在文档草稿与工作区运行态文件。
- Decision: 在不回滚他人改动前提下复用已有草稿，先完成“计划提交”，随后按 R1->R2->R3 执行。
- Rationale: 先固化接手上下文与基线证据，避免后续提交链条缺失。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
  - Entry: 基线已复跑全绿，可进入 Red 阶段。
- Rollback: `5cc9da2`（接手前稳定点）
- Commits: C1=<N/A>, C2=<N/A>, C3=<N/A>
- Next: 提交 TASKS/PROGRESS 计划变更，然后开始 R1 红测。

## Constraints / Notes
- 仅改 CLI 层与相关测试，禁止触碰 server/runtime/tools/hooks/agent/core。
- `send-message` stdout 单 JSON 契约必须保持。
- REPL 异步消费必须保留 `event_id` 去重与 `run_id` 过滤。
- 输出遵循 `event -> semantic -> render`，默认以会话主内容优先可读。

### R1 会话创建文案化（去 JSON 直出）
- Context: 现状 `/new`、`/use`、`/session` 与“无会话时首条消息自动建会话”都直接打印 JSON，阅读流不友好且与发布态摘要风格不一致。
- Decision: 在 REPL 路径统一改为人类文案：`Started new session ...`、`Switched to session ...`、`Active session: ...`，并在自动建会话分支复用同一文案；非交互命令 JSON 契约保持不变。
- Rationale: REPL 面向人读，单命令模式面向机读，二者输出职责分离可减少噪音并保持兼容。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `101 passed, 40 warnings`
  - Entry: REPL `/new` + `/session` + `/use` 均输出人类文案，且 REPL 不再出现会话 JSON 直出。
- Rollback: `3611048`（R1 红测基线）
- Commits: C1=`3611048`, C2=`622105e`, C3=`TBD`
- Next: 进入 R2，收敛工具过程为关键节点摘要并继续保持 run_id/event_id 与排队能力。

### R2 工具过程折叠（关键节点摘要优先）
- Context: 现状虽然已隐藏 running/chunk 明细，但最终摘要仍重复展示 `start`，且缺少对 chunk 的聚合进度表达；工具过程信息密度仍偏高。
- Decision: 调整 `repl_events._build_repl_view`：默认不在最终摘要重复 `start`；保留 `output/exit/error`；将 `tool_exec_chunk` 汇总为单条 `progress chunks=...` 关键进度行。
- Rationale: 把事件细粒度信息收束成“关键节点 + 聚合进度”，兼顾可读性与排障信息。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `101 passed, 40 warnings`
  - Entry: bash 工具链路只保留 start/started/exit 与聚合 progress，无 running/chunk 明细；`run_id` 过滤、`event_id` 去重与排队用例持续通过。
- Rollback: `724407a`（R2 红测基线）
- Commits: C1=`724407a`, C2=`148945e`, C3=`TBD`
- Next: 执行 R3 收口：门禁复跑、managed 真实验收、rebase+merge+push、dev_tasks 更新 DONE。

### R3 收口验收与集成（managed 真机验收 + main 集成）
- Context: M44 进入收口阶段，需要确认“会话文案化 + 工具过程折叠 + 关键兼容约束”在门禁与真实 managed CLI 下都成立。
- Decision: 先执行全量门禁，再用真实 managed CLI 做两轮脚本化验收（普通回复 + 强制 bash 工具调用），并记录变更前后对比。
- Rationale: 单测/集成可验证行为边界，managed 实跑可验证真实入口与运维参数下的最终体验。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `101 passed, 40 warnings`
  - Entry:
    - Managed 验收命令：
      - `printf '/new\nping\n/exit\n' | PYTHONPATH=src NANO_MULTIAGENT_LLM_BASE_URL=http://127.0.0.1:4000 /Users/czj/miniforge3/bin/python -m nano_multiagent.cli.main --mode managed --base-url http://127.0.0.1:8003 --token test-token`
      - `printf '/new\n请调用bash工具执行 echo hi 并返回结果\n/exit\n' | PYTHONPATH=src NANO_MULTIAGENT_LLM_BASE_URL=http://127.0.0.1:4000 /Users/czj/miniforge3/bin/python -m nano_multiagent.cli.main --mode managed --base-url http://127.0.0.1:8003 --token test-token`
    - Before -> After（对比）：
      - 会话创建提示：`{"session_id":"..."}` -> `Started new session sess_... .`
      - 会话查看提示：`{"session_id":"sess_..."}` -> `Active session: sess_... .`
      - 工具过程：重复 `Tool: ... start args=...` + 明细噪音 -> `Tool ... start` / `Tool ... exit` + `Tool: ... progress chunks=...`（隐藏 running/chunk 明细）
- Rollback: `148945e`（R2 完成后稳定点）
- Commits: C1=<N/A>, C2=<N/A>, C3=<TBD>
- Next: rebase `origin/main`，合并并 push 到 `main`，随后更新 `dev-tasks` 为 DONE。
