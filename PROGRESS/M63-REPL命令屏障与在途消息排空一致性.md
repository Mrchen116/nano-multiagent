# M63 REPL命令屏障与在途消息排空一致性

日期：2026-03-04
分支：`milestone/M63`
工作区：`/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M63`

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `112 passed, 44 warnings`

### Plan（一次性拆分）
- Context:
  - 当前 REPL 在 `in-flight` 消息存在时，会对非 `/exit` 命令执行屏障等待；但 timeout 反馈粒度与 `/exit` 收口提示不一致。
  - 本里程碑只允许改 CLI 与指定测试，不改 events/render 深层逻辑。
- Decision:
  - 在 `commands.py` 收敛队列屏障提示与 timeout 判定策略，避免 `/history` 假阳性超时。
  - 在 `repl_runtime.py` 修正 `wait_for_drain` 截止边界竞态，降低“已排空却判定超时”的概率。
- Rationale:
  - 问题核心在命令入口编排与队列排空判定边界，最小修复路径是 CLI 层统一屏障函数 + 队列等待判定微调。
- Evidence:
  - Tests: baseline `112 passed, 44 warnings`。
  - Entry: 已完成 `LOGBOOK/COMMENTING_GUIDE/内核设计蓝图` 阅读并确认作用边界。
- Rollback:
  - 回退到计划提交前稳定点。
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 执行 R1：先补红测锁定 false-timeout 与 `/exit` 剩余信息场景。

### R1 /history 与 /exit 的 in-flight 屏障一致性修复
- Context:
- `/history` 在命令屏障阶段依赖 `wait_for_drain` 布尔返回值，遇到“已排空但返回 False”的边界竞态会误判 timeout 并跳过命令。
- `/exit` 超时提示只给泛化文案，缺少剩余 in-flight 数量，不利于用户判断是否需要重试或等待。
- Decision:
- 在 `commands.py` 引入统一 `_wait_for_inflight_messages` 屏障函数：统一等待提示，timeout 后二次读取 backlog，若已排空则继续执行命令。
- 在 `repl_runtime.py` 的 `wait_for_drain` 增加 deadline 命中后的最终 backlog 复检，减少竞态假阳性。
- `/exit` 超时文案改为包含剩余在途数量，保持命令收口一致可读。
- Rationale:
- 缺陷位于 CLI 命令编排与队列状态判定边界，最小修复应集中在 CLI 层，不触碰 events/render 深层实现。
- Evidence:
  - Tests:
    - 红测子集：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py::test_run_cli_repl_history_command_ignores_false_timeout_when_queue_already_drained tests/unit/test_cli_main.py::test_run_cli_repl_exit_reports_remaining_inflight_messages_after_timeout tests/integration/test_cli_http_flow_integration.py::test_cli_repl_history_wait_barrier_ignores_false_timeout_after_drain` -> `3 failed`。
    - 绿测子集：同上命令 -> `3 passed, 4 warnings`。
    - 全量门禁：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `115 passed, 46 warnings`。
  - Entry:
    - 关键行为验证：
      - `/history` 场景：队列已排空但 `wait_for_drain=False` 时不再误判跳过，历史稳定输出。
      - `/exit` 场景：timeout 提示包含 remaining in-flight 数量。
    - managed CLI 实跑：
      - `PYTHONPATH=src python -m nano_multiagent.cli.main --mode managed --base-url http://127.0.0.1:8127 --token test-token health`
        -> `{\"healthy\": true, \"version\": \"0.1.0\", \"node_id\": \"local-dev\"}`
      - `PYTHONPATH=src python -m nano_multiagent.cli.main --mode managed --base-url http://127.0.0.1:8127 --token test-token create-session --title m63-managed-smoke`
        -> `{\"session_id\": \"sess_2b2ffe0431ee76b2\", \"status\": \"active\", \"created_at\": \"2026-03-04T08:23:08.526752+00:00\"}`
- Rollback:
- 回退到 `1ac385e`（C1 红测稳定点）。
- Commits: C1=`1ac385e`, C2=`19eee35`, C3=`TBD`
- Next:
- 提交文档收口（TASKS/PROGRESS/LOGBOOK）并进入 main 集成。
