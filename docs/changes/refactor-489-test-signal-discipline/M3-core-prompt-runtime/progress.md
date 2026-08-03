# refactor-489-M3 — Progress

## Baseline

- Claim: M3 派发范围在清理前全绿，后续失败可归因于本 milestone。
- Baseline: `origin/unit/refactor-489@8d6cfb3e8`。
- Method: 运行 `setopt null_glob; m3_tests=(tests/unit/agent tests/unit/test_{agent,core,loop,compaction,memory,session,jsonl_store,merge_adjacent,nested_memory,build_chat,prompting}_*.py tests/unit/test_curator.py); /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q "${m3_tests[@]}"`。首次 glob 范围 `840 passed`；orchestrator 澄清无后缀 `test_curator.py` 也归 M3 后，单独补跑该文件。
- Result: PASS，原范围 `840 passed in 11.67s`；`test_curator.py` `5 passed in 0.04s`，合计 845 个测试节点。
- Limit: 零用户面测试资产重构；无浏览器或 live runtime。

## R1 — 删除迁移终态与墓碑断言

- 状态: DONE
- Context: location/removed/tombstone 测试把 refactor-387、bugfix-355/417 的迁移终态固定成永久 CI；部分文件同时含真实 resolver、path、bash policy 与 foreground wiring 行为，不能整文件粗删。
- Decision: 删除纯模块位置、旧 root 缺失、退役 HTTP 与 ToolSafety 方法墓碑；把 skill resolver 改为 workspace 输入输出测试，保留 path/read、ShellRunner、bash allow/review/deny 和 Kernel foreground stopper 的现行行为。
- Rationale: 架构回归由 contract 直接检查依赖，运行风险由当前 seam 的行为测试保护；私有字段或旧目录不存在不再作为第二套迁移 contract。
- Evidence:
  - Tests: 删除前替代保护 `223 passed in 9.35s`；删除后定向组合 `149 passed in 9.12s`，ruff `All checks passed!`。
  - Entry: `test_cross_loop_streaming_receives_run_status_event` 经 `agent.sdk` 提交并消费 Event hub；skill resolver、read、bash policy 与 foreground stopper 均从当前调用入口验证输入输出。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面）。
  - E2E/Regression: 相关 contract + unit 定向回归，命令见本段 Tests；无真实进程需求。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 roadpoint 提交；计划基点为 `dcd4b8b6d`。
- Commits: 本 roadpoint 提交（SHA 以 Git history 为准）。
- Next: R2 收敛 prompt golden、片段措辞、feature registry skeleton 与重复 assembler 测试。

## R2 — 收敛 prompt 条件与消费者输入输出

- 状态: TODO

## R3 — 合并 runtime/persistence 重复并完成门禁

- 状态: TODO

## Promotion Candidates

None.
